from __future__ import annotations

import json
from pathlib import Path

import pytest

from rechner_pipeline.orchestrate.runner import PipelineOptions, PipelineRunner


def _options() -> PipelineOptions:
    return PipelineOptions(
        model="test-model",
        skip_export=True,
        skip_main_llm=True,
        skip_test_llm=True,
        skip_compare_run=False,
        main_max_chars_per_file=100,
        main_max_total_chars=100,
        test_max_chars_per_file=100,
        test_max_total_chars=100,
        reasoning_effort="low",
    )


def test_run_compare_raises_and_writes_structured_result_on_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    generated_dir = tmp_path / "generated"
    generated_dir.mkdir()
    test_file = generated_dir / "test_run_advanced.py"
    test_file.write_text(
        "\n".join(
            [
                "import sys",
                "print('visible stdout')",
                "print('visible stderr', file=sys.stderr)",
                "raise SystemExit(7)",
            ]
        ),
        encoding="utf-8",
    )

    runner = PipelineRunner(repo_root=tmp_path, options=_options())

    with pytest.raises(RuntimeError, match="returncode 7"):
        runner.run_compare()

    captured = capsys.readouterr()
    assert "visible stdout" in captured.out
    assert "visible stderr" in captured.err

    result = json.loads(runner.compare_result_path.read_text(encoding="utf-8"))
    assert result["status"] == "failed"
    assert result["returncode"] == 7
    assert "visible stdout" in result["stdout"]
    assert "visible stderr" in result["stderr"]
    assert result["test_file"] == str(test_file)


def test_run_compare_writes_passed_result_on_success(tmp_path: Path):
    generated_dir = tmp_path / "generated"
    generated_dir.mkdir()
    (generated_dir / "test_run_advanced.py").write_text(
        "print('ok')\n",
        encoding="utf-8",
    )

    runner = PipelineRunner(repo_root=tmp_path, options=_options())

    runner.run_compare()

    result = json.loads(runner.compare_result_path.read_text(encoding="utf-8"))
    assert result["status"] == "passed"
    assert result["returncode"] == 0
    assert "ok" in result["stdout"]
    assert result["stderr"] == ""
