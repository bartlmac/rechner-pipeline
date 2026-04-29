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


def build_openai_client(env_path: Path | None = None) -> Any:
    if env_path is not None:
        load_env_file(env_path)

    if not os.getenv("OPENAI_API_KEY"):
        location = f" or in {env_path}" if env_path is not None else ""
        raise RuntimeError(f"OPENAI_API_KEY is not set in environment variables{location}.")

    try:
        from openai import OpenAI  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "Missing LLM dependency. Run: pip install -e '.[llm]'"
        ) from exc

    return OpenAI()
