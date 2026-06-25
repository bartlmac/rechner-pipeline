from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value


def resolve_api_key(key_name: str, env_path: Path | None = None) -> str:
    """Loese einen API-Key auf, ohne ihn in einer persistenten Host-Variable zu verlangen.

    Aufloesungs-Reihenfolge:

    1. Echte Umgebungsvariable ``<key_name>`` (Rueckwaertskompatibilitaet).
    2. ``<key_name>_FILE`` -> Pfad zu einer restriktiv berechtigten Secret-Datei
       (empfohlen). ``.env`` enthaelt dann nur den Pointer, nie das Geheimnis.

    Der zurueckgegebene Key wird vom Aufrufer direkt an den SDK-Konstruktor
    uebergeben und landet bewusst nicht in ``os.environ``.
    """
    if env_path is not None:
        load_env_file(env_path)

    direct = os.getenv(key_name)
    if direct:
        return direct

    file_pointer = os.getenv(f"{key_name}_FILE")
    if file_pointer:
        secret_path = Path(file_pointer).expanduser()
        if not secret_path.exists():
            raise RuntimeError(
                f"{key_name}_FILE points to {secret_path}, but that file does not exist."
            )
        secret = secret_path.read_text(encoding="utf-8").strip()
        if not secret:
            raise RuntimeError(
                f"Secret file {secret_path} (from {key_name}_FILE) is empty."
            )
        return secret

    location = f" or in {env_path}" if env_path is not None else ""
    raise RuntimeError(
        f"{key_name} is not set: provide it via the {key_name} environment "
        f"variable or a {key_name}_FILE pointer to a secret file{location}."
    )


def build_openai_client(env_path: Path | None = None) -> Any:
    api_key = resolve_api_key("OPENAI_API_KEY", env_path)

    try:
        from openai import OpenAI  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "Missing LLM dependency. Run: pip install -e '.[llm]'"
        ) from exc

    return OpenAI(api_key=api_key)


def build_anthropic_client(env_path: Path | None = None) -> Any:
    api_key = resolve_api_key("ANTHROPIC_API_KEY", env_path)

    try:
        from anthropic import Anthropic  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "Missing LLM dependency. Run: pip install -e '.[anthropic]'"
        ) from exc

    return Anthropic(api_key=api_key)


# Replay-Index modulglobal pro Verzeichnis: der Zähler überlebt das
# Neu-Erzeugen des Runners (und damit des Clients) über Agentik-Iterationen.
_REPLAY_INDEX: dict[str, int] = {}


class _ReplayClient:
    """Liefert vorbereitete Modell-Ausgaben in Reihenfolge (für kostenfreie,
    wiederholbare Demo-/Testläufe). Verzeichnis via RP_REPLAY_DIR; jeder Aufruf
    gibt die nächste Datei (sortiert) zurück, letzte Datei wird wiederholt."""

    def __init__(self, directory: Path) -> None:
        self._dir = str(directory.resolve())
        self._files = sorted(directory.glob("*.txt"))
        if not self._files:
            raise RuntimeError(f"RP_REPLAY_DIR enthält keine *.txt-Ausgaben: {directory}")

    def next_output(self) -> str:
        i = _REPLAY_INDEX.get(self._dir, 0)
        _REPLAY_INDEX[self._dir] = i + 1
        return self._files[min(i, len(self._files) - 1)].read_text(encoding="utf-8")


def build_llm_client(provider: str, env_path: Path | None = None) -> Any:
    """Baue den passenden Raw-Client (OpenAI, Anthropic oder Replay) nach Provider."""
    if provider == "openai":
        return build_openai_client(env_path=env_path)
    if provider == "anthropic":
        return build_anthropic_client(env_path=env_path)
    if provider == "replay":
        directory = Path(os.environ.get("RP_REPLAY_DIR", "demo_fixtures"))
        return _ReplayClient(directory)
    raise ValueError(
        f"Unknown LLM provider: {provider!r} (expected 'openai', 'anthropic' or 'replay')."
    )


# reasoning_effort -> Extended-Thinking-Budget (Tokens) fuer Anthropic.
# 0 = Thinking deaktiviert (Anthropic verlangt sonst budget_tokens >= 1024).
_ANTHROPIC_THINKING_BUDGET = {"low": 0, "medium": 4096, "high": 12288}


def _anthropic_response_text(resp: Any) -> str:
    """Konkateniere die Text-Bloecke einer Anthropic-Messages-Antwort.

    Thinking-Bloecke werden uebersprungen, sodass der zurueckgegebene String
    nur den fuer den FILE-Block-Parser relevanten Modell-Output enthaelt.
    """
    parts = []
    for block in getattr(resp, "content", None) or []:
        if getattr(block, "type", None) == "text":
            parts.append(getattr(block, "text", ""))
    return "".join(parts)


def generate_completion(
    client: Any,
    *,
    provider: str,
    model: str,
    prompt: str,
    reasoning_effort: str,
    max_output_tokens: int,
) -> str:
    """Einheitlicher LLM-Aufruf ueber Provider hinweg; liefert reinen Text.

    OpenAI nutzt die Responses-API mit ``reasoning.effort``; Anthropic nutzt
    die Messages-API und mappt ``reasoning_effort`` auf ein Extended-Thinking-
    Budget. Beide Pfade liefern denselben Text-Vertrag wie zuvor
    ``resp.output_text``.
    """
    if provider == "replay":
        return client.next_output()

    if provider == "openai":
        resp = client.responses.create(
            model=model,
            input=prompt,
            reasoning={"effort": reasoning_effort},
        )
        return resp.output_text

    if provider == "anthropic":
        thinking_budget = _ANTHROPIC_THINKING_BUDGET.get(reasoning_effort, 0)
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_output_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if thinking_budget > 0:
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": thinking_budget}
            # Anthropic verlangt max_tokens > budget_tokens.
            if kwargs["max_tokens"] <= thinking_budget:
                kwargs["max_tokens"] = thinking_budget + max_output_tokens
        # Streaming: Das Anthropic-SDK verweigert nicht-gestreamte Requests,
        # sobald max_tokens eine potenzielle Laufzeit > 10 min impliziert.
        # Streaming funktioniert auch fuer kleine Antworten.
        with client.messages.stream(**kwargs) as stream:
            resp = stream.get_final_message()
        if getattr(resp, "stop_reason", None) == "max_tokens":
            raise RuntimeError(
                "Anthropic response was truncated at max_output_tokens "
                f"({kwargs['max_tokens']}). The output contract (FILE_START/"
                "FILE_END blocks) is therefore incomplete. Increase "
                "--max_output_tokens and re-run."
            )
        return _anthropic_response_text(resp)

    raise ValueError(f"Unknown LLM provider: {provider!r} (expected 'openai' or 'anthropic').")
