from __future__ import annotations

import os
import sys
import types
from pathlib import Path

from rechner_pipeline.generate.client import build_openai_client, load_env_file
from rechner_pipeline.orchestrate.runner import PipelineOptions, PipelineRunner


def _options() -> PipelineOptions:
    return PipelineOptions(
        model="test-model",
        skip_export=True,
        skip_main_llm=True,
        skip_test_llm=True,
        skip_compare_run=True,
        main_max_chars_per_file=100,
        main_max_total_chars=100,
        test_max_chars_per_file=100,
        test_max_total_chars=100,
        reasoning_effort="low",
    )


def test_load_env_file_sets_missing_values_without_overriding(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("OPENAI_API_KEY", "from-real-env")
    monkeypatch.delenv("SECOND_VALUE", raising=False)
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "# comment",
                "OPENAI_API_KEY=from-dotenv",
                "export SECOND_VALUE='quoted value'",
            ]
        ),
        encoding="utf-8",
    )

    load_env_file(env_path)

    assert os.environ["OPENAI_API_KEY"] == "from-real-env"
    assert os.environ["SECOND_VALUE"] == "quoted value"


def test_build_openai_client_loads_key_from_env_file(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    env_path = tmp_path / ".env"
    env_path.write_text('OPENAI_API_KEY="from-dotenv"\n', encoding="utf-8")

    fake_openai = types.ModuleType("openai")

    class FakeOpenAI:
        pass

    fake_openai.OpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    client = build_openai_client(env_path=env_path)

    assert isinstance(client, FakeOpenAI)
    assert os.environ["OPENAI_API_KEY"] == "from-dotenv"


def test_pipeline_runner_does_not_build_openai_client_on_init(monkeypatch, tmp_path: Path):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("client must be lazy")

    monkeypatch.setattr("rechner_pipeline.generate.client.build_openai_client", fail_if_called)

    runner = PipelineRunner(repo_root=tmp_path, options=_options())

    assert runner._client is None


def test_pipeline_runner_passes_repo_env_path_to_lazy_client(monkeypatch, tmp_path: Path):
    seen = {}
    sentinel = object()

    def fake_build_openai_client(*, env_path):
        seen["env_path"] = env_path
        return sentinel

    monkeypatch.setattr(
        "rechner_pipeline.generate.client.build_openai_client",
        fake_build_openai_client,
    )

    runner = PipelineRunner(repo_root=tmp_path, options=_options())

    assert runner.client is sentinel
    assert seen["env_path"] == tmp_path / ".env"


def test_pipeline_runner_reuses_lazy_openai_client(monkeypatch, tmp_path: Path):
    calls = []
    sentinel = object()

    def fake_build_openai_client(*, env_path):
        calls.append(env_path)
        return sentinel

    monkeypatch.setattr(
        "rechner_pipeline.generate.client.build_openai_client",
        fake_build_openai_client,
    )

    runner = PipelineRunner(repo_root=tmp_path, options=_options())

    assert runner.client is sentinel
    assert runner.client is sentinel
    assert calls == [tmp_path / ".env"]
