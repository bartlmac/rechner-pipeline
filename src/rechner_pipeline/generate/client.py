from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen


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
    base_url = os.getenv("OPENAI_BASE_URL")

    try:
        from openai import OpenAI  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "Missing LLM dependency. Run: pip install -e '.[llm]'"
        ) from exc

    kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


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
_OLLAMA_NATIVE_REQUEST_TIMEOUT_SECONDS = 600
_OLLAMA_NATIVE_MAX_RESPONSE_BYTES = 16 * 1024 * 1024
_OLLAMA_NATIVE_SUPPORTED_SCHEMES = {"http", "https"}


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


def _is_local_ollama_base_url(base_url: Any) -> bool:
    parsed = urlparse(str(base_url))
    host = (parsed.hostname or "").lower()
    return host in {"127.0.0.1", "localhost", "::1"} and parsed.port == 11434


def _ollama_chat_url(base_url: Any) -> str:
    parsed = urlparse(str(base_url))
    scheme = parsed.scheme or "http"
    if scheme not in _OLLAMA_NATIVE_SUPPORTED_SCHEMES:
        raise RuntimeError(
            "Ollama native chat requires an http or https base URL; "
            f"got scheme {scheme!r}."
        )
    return urlunparse((scheme, parsed.netloc, "/api/chat", "", "", ""))


def _require_positive_int(name: str, value: Any) -> int:
    if type(value) is not int or value <= 0:
        raise RuntimeError(f"{name} must be a positive integer.")
    return value


def _positive_int_env(name: str) -> int | None:
    raw = os.getenv(name)
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a positive integer.") from exc
    if value <= 0:
        raise RuntimeError(f"{name} must be a positive integer.")
    return value


def _ollama_native_chat(
    *,
    base_url: Any,
    model: str,
    prompt: str,
    max_output_tokens: int,
) -> str:
    options = {"num_predict": max_output_tokens}
    num_ctx = _positive_int_env("OLLAMA_NUM_CTX")
    if num_ctx is not None:
        options["num_ctx"] = num_ctx

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        # Qwen reasoning models can spend the full OpenAI-compatible response
        # budget in the reasoning channel. Ollama's native API can disable it.
        "think": False,
        "options": options,
    }
    body = json.dumps(payload).encode("utf-8")
    req = Request(
        _ollama_chat_url(base_url),
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=_OLLAMA_NATIVE_REQUEST_TIMEOUT_SECONDS) as resp:
            raw_data = resp.read(_OLLAMA_NATIVE_MAX_RESPONSE_BYTES + 1)
    except Exception as exc:
        raise RuntimeError("Ollama native chat request failed.") from exc
    if len(raw_data) > _OLLAMA_NATIVE_MAX_RESPONSE_BYTES:
        raise RuntimeError(
            "Ollama native chat response exceeded "
            f"{_OLLAMA_NATIVE_MAX_RESPONSE_BYTES} bytes."
        )
    try:
        data = json.loads(raw_data.decode("utf-8"))
    except Exception as exc:
        raise RuntimeError("Ollama native chat response was not valid JSON.") from exc

    message = data.get("message")
    text = message.get("content") if isinstance(message, dict) else None
    if not isinstance(text, str):
        raise RuntimeError("Ollama native chat response did not contain text.")
    if data.get("done_reason") == "length":
        raise RuntimeError(
            "Ollama response was truncated at max_output_tokens "
            f"({max_output_tokens}). Partial generated code is unsafe to use. Increase "
            "--max_output_tokens and re-run."
        )
    return text


def _openai_response_text(resp: Any) -> str:
    output_text = getattr(resp, "output_text", None)
    if output_text:
        return output_text

    parts: list[str] = []
    for item in getattr(resp, "output", None) or []:
        if getattr(item, "type", None) != "message":
            continue
        for block in getattr(item, "content", None) or []:
            text = getattr(block, "text", None)
            if isinstance(text, str):
                parts.append(text)
    if parts:
        return "".join(parts)
    raise RuntimeError("OpenAI response did not contain extractable output text.")


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
    max_output_tokens = _require_positive_int("max_output_tokens", max_output_tokens)

    if provider == "replay":
        return client.next_output()

    if provider == "openai":
        base_url = getattr(client, "base_url", None)
        if base_url is not None and _is_local_ollama_base_url(base_url):
            return _ollama_native_chat(
                base_url=base_url,
                model=model,
                prompt=prompt,
                max_output_tokens=max_output_tokens,
            )

        resp = client.responses.create(
            model=model,
            input=prompt,
            reasoning={"effort": reasoning_effort},
            max_output_tokens=max_output_tokens,
        )
        return _openai_response_text(resp)

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
