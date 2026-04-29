from __future__ import annotations

import json
from pathlib import Path

import pytest

from rechner_pipeline.models.manifest import (
    ExportManifest,
    ManifestWarning,
    PromptInputRecord,
    PromptRecord,
)
from rechner_pipeline.orchestrate.dossier import write_run_dossier
from rechner_pipeline.orchestrate.runner import PipelineOptions, PipelineRunner


def _options(**overrides) -> PipelineOptions:
    values = {
        "model": "test-model",
        "skip_export": True,
        "skip_main_llm": True,
        "skip_test_llm": True,
        "skip_compare_run": False,
        "main_max_chars_per_file": 100,
        "main_max_total_chars": 100,
        "test_max_chars_per_file": 100,
        "test_max_total_chars": 100,
        "reasoning_effort": "low",
        "strict_manifest_warnings": False,
    }
    values.update(overrides)
    return PipelineOptions(**values)


def _manifest(tmp_path: Path) -> ExportManifest:
    out_dir = tmp_path / "info_from_excel"
    out_dir.mkdir()
    input_path = out_dir / "source.csv"
    input_path.write_text("input", encoding="utf-8")
    generated_file = tmp_path / "generated" / "test_run.py"
    generated_file.parent.mkdir()
    generated_file.write_text("print('generated')\n", encoding="utf-8")
    return ExportManifest(
        out_dir=out_dir,
        sheet_csvs=[input_path],
        vba_txts=[],
        names_manager_csv=None,
        replacements={},
        llm_inputs=[input_path],
        all_outputs=[input_path],
        warnings=[
            ManifestWarning(
                code="prompt.file_truncated",
                stage="main_llm",
                message="Prompt input was truncated.",
                strict_error=True,
                path=str(input_path),
            )
        ],
        prompt_runs=[
            PromptRecord(
                stage="main_llm",
                template_path=str(tmp_path / "prompts" / "v1" / "excel_to_py.txt"),
                debug_prompt_path=str(tmp_path / "DEBUG_first_llm_prompt.txt"),
                prompt_chars=12,
                prompt_sha256="p" * 64,
                input_files=[
                    PromptInputRecord(
                        path=str(input_path),
                        label="source",
                        original_chars=20,
                        included_chars=10,
                        original_sha256="i" * 64,
                        truncated=True,
                    )
                ],
                total_limit_reached=False,
                output_chars=21,
                output_sha256="o" * 64,
            )
        ],
        output_hashes=[],
    )


def test_run_dossier_bundles_manifest_hashes_files_tests_and_assumptions(
    tmp_path: Path,
) -> None:
    runner = PipelineRunner(repo_root=tmp_path, options=_options())
    manifest = _manifest(tmp_path)
    runner.manifest_path.write_text(
        json.dumps(manifest.to_dict(), indent=2),
        encoding="utf-8",
    )
    runner.compare_result_path.write_text(
        json.dumps(
            {
                "status": "passed",
                "returncode": 0,
                "stdout": "ok",
                "stderr": "",
                "test_file": str(runner.test_py_path),
                "command": ["python", str(runner.test_py_path)],
                "cwd": str(runner.generated_dir),
            }
        ),
        encoding="utf-8",
    )

    dossier_path = write_run_dossier(
        runner,
        manifest=manifest,
        run_status="completed",
    )

    payload = json.loads(dossier_path.read_text(encoding="utf-8"))
    assert payload["run"]["status"] == "completed"
    assert payload["manifest"]["llm_input_count"] == 1
    assert payload["prompt_hashes"][0]["prompt_sha256"] == "p" * 64
    assert payload["prompt_hashes"][0]["output_sha256"] == "o" * 64
    assert any(
        Path(item["path"]).name == "test_run.py"
        for item in payload["generated_files"]
    )
    assert payload["test_summary"]["status"] == "passed"
    assert payload["warnings"][0]["code"] == "prompt.file_truncated"
    assert any(
        item["code"] == "manifest_warning.prompt.file_truncated"
        for item in payload["open_assumptions"]
    )


def test_classic_run_writes_dossier_when_compare_fails(tmp_path: Path) -> None:
    prompts_dir = tmp_path / "prompts" / "v1"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "excel_to_py.txt").write_text("unused", encoding="utf-8")
    (prompts_dir / "test_advanced.txt").write_text("unused", encoding="utf-8")
    manifest = _manifest(tmp_path)
    runner = PipelineRunner(
        repo_root=tmp_path,
        options=_options(skip_compare_run=False),
    )
    runner.manifest_path.write_text(
        json.dumps(manifest.to_dict(), indent=2),
        encoding="utf-8",
    )
    runner.test_py_path.write_text("raise SystemExit(9)\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="returncode 9"):
        runner.run()

    payload = json.loads(runner.run_dossier_path.read_text(encoding="utf-8"))
    assert payload["run"]["status"] == "failed"
    assert payload["test_summary"]["status"] == "failed"
    assert any(
        item["code"] == "compare.failed"
        for item in payload["open_assumptions"]
    )
