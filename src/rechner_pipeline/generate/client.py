from __future__ import annotations

import os
from typing import Any


def build_openai_client() -> Any:
    try:
        from openai import OpenAI  # type: ignore
    except Exception as exc:
        raise RuntimeError("Missing dependency. Run: pip install openai") from exc

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set in environment variables.")

    return OpenAI()
