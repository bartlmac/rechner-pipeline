from __future__ import annotations

import os
import sys
import types
from pathlib import Path

import pytest

from rechner_pipeline.generate.client import (
    build_anthropic_client,
    build_llm_client,
    generate_completion,
)
from rechner_pipeline.orchestrate.runner import PipelineOptions, PipelineRunner


# --- Fakes -----------------------------------------------------------------


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.output_text = text


class _FakeResponses:
    def __init__(self, captured: dict) -> None:
        self._captured = captured

    def create(self, **kwargs):
        self._captured.update(kwargs)
        return _FakeResponse("OPENAI_OUTPUT")


class _FakeOpenAIClient:
    def __init__(self) -> None:
        self.captured: dict = {}
        self.responses = _FakeResponses(self.captured)


class _FakeBlock:
    def __init__(self, block_type: str, text: str = "") -> None:
        self.type = block_type
        self.text = text


class _FakeMessage:
    def __init__(self, content: list) -> None:
        self.content = content


class _FakeStreamCtx:
    """Context-Manager-Attrappe für client.messages.stream(...)."""

    def __init__(self, message) -> None:
        self._message = message

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self._message


class _FakeMessages:
    def __init__(self, captured: dict) -> None:
        self._captured = captured

    def stream(self, **kwargs):
        self._captured.update(kwargs)
        # Thinking-Block muss ignoriert werden; nur Text-Bloecke zaehlen.
        return _FakeStreamCtx(
            _FakeMessage(
                [
                    _FakeBlock("thinking", "internal reasoning"),
                    _FakeBlock("text", "ANTHROPIC_"),
                    _FakeBlock("text", "OUTPUT"),
                ]
            )
        )


class _FakeAnthropicClient:
    def __init__(self) -> None:
        self.captured: dict = {}
        self.messages = _FakeMessages(self.captured)


# --- generate_completion ---------------------------------------------------


def test_generate_completion_openai_uses_responses_api():
    client = _FakeOpenAIClient()
    out = generate_completion(
        client,
        provider="openai",
        model="gpt-5.2",
        prompt="PROMPT",
        reasoning_effort="medium",
        max_output_tokens=16_000,
    )
    assert out == "OPENAI_OUTPUT"
    assert client.captured["model"] == "gpt-5.2"
    assert client.captured["input"] == "PROMPT"
    assert client.captured["reasoning"] == {"effort": "medium"}


def test_generate_completion_anthropic_concatenates_text_blocks():
    client = _FakeAnthropicClient()
    out = generate_completion(
        client,
        provider="anthropic",
        model="claude-sonnet-4-6",
        prompt="PROMPT",
        reasoning_effort="medium",
        max_output_tokens=16_000,
    )
    assert out == "ANTHROPIC_OUTPUT"
    assert client.captured["model"] == "claude-sonnet-4-6"
    assert client.captured["messages"] == [{"role": "user", "content": "PROMPT"}]


def test_generate_completion_anthropic_enables_thinking_for_medium():
    client = _FakeAnthropicClient()
    generate_completion(
        client,
        provider="anthropic",
        model="claude-sonnet-4-6",
        prompt="PROMPT",
        reasoning_effort="medium",
        max_output_tokens=16_000,
    )
    assert client.captured["thinking"] == {"type": "enabled", "budget_tokens": 4096}
    # max_tokens muss groesser als das Thinking-Budget bleiben.
    assert client.captured["max_tokens"] > client.captured["thinking"]["budget_tokens"]


def test_generate_completion_anthropic_disables_thinking_for_low():
    client = _FakeAnthropicClient()
    generate_completion(
        client,
        provider="anthropic",
        model="claude-sonnet-4-6",
        prompt="PROMPT",
        reasoning_effort="low",
        max_output_tokens=16_000,
    )
    assert "thinking" not in client.captured
    assert client.captured["max_tokens"] == 16_000


def test_generate_completion_anthropic_bumps_max_tokens_above_budget():
    client = _FakeAnthropicClient()
    generate_completion(
        client,
        provider="anthropic",
        model="claude-sonnet-4-6",
        prompt="PROMPT",
        reasoning_effort="high",  # Budget 12288
        max_output_tokens=8_000,  # kleiner als Budget -> muss angehoben werden
    )
    assert client.captured["thinking"]["budget_tokens"] == 12288
    assert client.captured["max_tokens"] == 12288 + 8_000


class _FakeTruncatedMessages:
    def stream(self, **kwargs):
        msg = _FakeMessage([_FakeBlock("text", "===FILE_START: x===")])
        msg.stop_reason = "max_tokens"
        return _FakeStreamCtx(msg)


class _FakeTruncatedAnthropicClient:
    def __init__(self) -> None:
        self.messages = _FakeTruncatedMessages()


def test_generate_completion_anthropic_truncation_raises():
    with pytest.raises(RuntimeError, match="truncated"):
        generate_completion(
            _FakeTruncatedAnthropicClient(),
            provider="anthropic",
            model="claude-sonnet-4-6",
            prompt="P",
            reasoning_effort="low",
            max_output_tokens=8,
        )


def test_generate_completion_unknown_provider_raises():
    with pytest.raises(ValueError):
        generate_completion(
            object(),
            provider="gemini",
            model="x",
            prompt="P",
            reasoning_effort="low",
            max_output_tokens=10,
        )


# --- build_anthropic_client ------------------------------------------------


def test_build_anthropic_client_requires_key(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        build_anthropic_client(env_path=tmp_path / "missing.env")


def test_build_anthropic_client_loads_key_from_env_file(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    env_path = tmp_path / ".env"
    env_path.write_text('ANTHROPIC_API_KEY="from-dotenv"\n', encoding="utf-8")

    fake_anthropic = types.ModuleType("anthropic")

    class FakeAnthropic:
        def __init__(self, api_key=None):
            self.api_key = api_key

    fake_anthropic.Anthropic = FakeAnthropic
    monkeypatch.setitem(sys.modules, "anthropic", fake_anthropic)

    client = build_anthropic_client(env_path=env_path)

    assert isinstance(client, FakeAnthropic)
    assert client.api_key == "from-dotenv"


def test_resolve_api_key_reads_from_file_pointer_without_env(monkeypatch, tmp_path: Path):
    # Secret liegt in einer Datei; .env enthaelt nur den Pointer (kein Geheimnis).
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY_FILE", raising=False)

    secret_file = tmp_path / "anthropic.secret"
    secret_file.write_text("sk-secret-from-file\n", encoding="utf-8")
    env_path = tmp_path / ".env"
    env_path.write_text(f"ANTHROPIC_API_KEY_FILE={secret_file}\n", encoding="utf-8")

    from rechner_pipeline.generate.client import resolve_api_key

    key = resolve_api_key("ANTHROPIC_API_KEY", env_path=env_path)

    assert key == "sk-secret-from-file"
    # Das Geheimnis selbst darf nicht in os.environ landen, nur der Pointer.
    assert "ANTHROPIC_API_KEY" not in os.environ
    assert os.environ.get("ANTHROPIC_API_KEY_FILE") == str(secret_file)


def test_resolve_api_key_real_env_takes_precedence(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-real-env")
    secret_file = tmp_path / "anthropic.secret"
    secret_file.write_text("from-file\n", encoding="utf-8")
    monkeypatch.setenv("ANTHROPIC_API_KEY_FILE", str(secret_file))

    from rechner_pipeline.generate.client import resolve_api_key

    assert resolve_api_key("ANTHROPIC_API_KEY") == "from-real-env"


def test_resolve_api_key_missing_pointer_file_raises(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY_FILE", str(tmp_path / "does-not-exist"))

    from rechner_pipeline.generate.client import resolve_api_key

    with pytest.raises(RuntimeError, match="does not exist"):
        resolve_api_key("ANTHROPIC_API_KEY")


# --- build_llm_client dispatch ---------------------------------------------


def test_build_llm_client_unknown_provider_raises():
    with pytest.raises(ValueError):
        build_llm_client("gemini")


def test_runner_builds_anthropic_client_when_provider_anthropic(monkeypatch, tmp_path: Path):
    sentinel = object()
    seen = {}

    def fake_build_anthropic_client(*, env_path):
        seen["env_path"] = env_path
        return sentinel

    monkeypatch.setattr(
        "rechner_pipeline.generate.client.build_anthropic_client",
        fake_build_anthropic_client,
    )

    options = PipelineOptions(
        model="claude-sonnet-4-6",
        skip_export=True,
        skip_main_llm=True,
        skip_test_llm=True,
        skip_compare_run=True,
        main_max_chars_per_file=100,
        main_max_total_chars=100,
        test_max_chars_per_file=100,
        test_max_total_chars=100,
        reasoning_effort="low",
        provider="anthropic",
    )
    runner = PipelineRunner(repo_root=tmp_path, options=options)

    assert runner.client is sentinel
    assert seen["env_path"] == tmp_path / ".env"
