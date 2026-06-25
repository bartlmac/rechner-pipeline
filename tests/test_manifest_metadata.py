from __future__ import annotations

import json
from pathlib import Path

import pytest

from rechner_pipeline.models.manifest import ExportManifest, ManifestWarning
from rechner_pipeline.orchestrate.runner import PipelineOptions, PipelineRunner


def _options(**overrides) -> PipelineOptions:
    values = {
        "model": "test-model",
        "skip_export": True,
        "skip_main_llm": False,
        "skip_test_llm": True,
        "skip_compare_run": True,
        "main_max_chars_per_file": 10,
        "main_max_total_chars": 1_000,
        "test_max_chars_per_file": 10,
        "test_max_total_chars": 1_000,
        "reasoning_effort": "low",
        "strict_manifest_warnings": False,
    }
    values.update(overrides)
    return PipelineOptions(**values)


def _main_output() -> str:
    blocks = []
    for filename in (
        "inputs.py",
        "params.py",
        "tafeln.xml",
        "commutation.py",
        "actuarial.py",
        "test_run.py",
    ):
        content = "<tafeln></tafeln>\n" if filename.endswith(".xml") else "VALUE = 1\n"
        blocks.append(
            f"===FILE_START: {filename}===\n"
            f"{content}"
            f"===FILE_END: {filename}==="
        )
    return "\n".join(blocks)


class _FakeResponses:
    def __init__(self, output_text: str) -> None:
        self._output_text = output_text

    def create(self, **kwargs):
        del kwargs
        return type("FakeResponse", (), {"output_text": self._output_text})()


class _FakeClient:
    def __init__(self, output_text: str) -> None:
        self.responses = _FakeResponses(output_text)


def test_main_llm_records_prompt_warnings_and_hashes(tmp_path: Path) -> None:
    prompts_dir = tmp_path / "prompts" / "v1"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "excel_to_py.txt").write_text(
        "META\n{{PIPELINE_META}}\nINPUT\n{{INPUT_FILES}}\n",
        encoding="utf-8",
    )
    (prompts_dir / "test_advanced.txt").write_text("unused", encoding="utf-8")

    out_dir = tmp_path / "info_from_excel"
    out_dir.mkdir()
    input_path = out_dir / "source.csv"
    input_path.write_text("x" * 50, encoding="utf-8")
    manifest = ExportManifest(
        out_dir=out_dir,
        sheet_csvs=[input_path],
        vba_txts=[],
        names_manager_csv=None,
        replacements={},
        llm_inputs=[input_path],
        all_outputs=[input_path],
        warnings=[],
        prompt_runs=[],
        output_hashes=[],
    )
    (out_dir / "export_manifest.json").write_text(
        json.dumps(manifest.to_dict(), indent=2),
        encoding="utf-8",
    )

    runner = PipelineRunner(repo_root=tmp_path, options=_options())
    runner._client = _FakeClient(_main_output())

    runner.run_main_llm(manifest)

    saved = json.loads((out_dir / "export_manifest.json").read_text(encoding="utf-8"))
    assert saved["warnings"][0]["code"] == "prompt.file_truncated"
    assert saved["warnings"][0]["strict_error"] is True
    assert saved["prompt_runs"][0]["stage"] == "main_llm"
    assert len(saved["prompt_runs"][0]["prompt_sha256"]) == 64
    assert len(saved["prompt_runs"][0]["output_sha256"]) == 64
    hashed_paths = {Path(item["path"]).name for item in saved["output_hashes"]}
    assert {"source.csv", "inputs.py", "test_run.py"} <= hashed_paths


def test_strict_manifest_warnings_fail_prepare(tmp_path: Path) -> None:
    out_dir = tmp_path / "info_from_excel"
    out_dir.mkdir()
    input_path = out_dir / "source.csv"
    input_path.write_text("ok", encoding="utf-8")
    manifest = ExportManifest(
        out_dir=out_dir,
        sheet_csvs=[input_path],
        vba_txts=[],
        names_manager_csv=None,
        replacements={},
        llm_inputs=[input_path],
        all_outputs=[input_path],
        warnings=[
            ManifestWarning(
                code="export.vba_access_unavailable",
                stage="export",
                message="Cannot access VBA.",
                strict_error=True,
            )
        ],
        prompt_runs=[],
        output_hashes=[],
    )
    (out_dir / "export_manifest.json").write_text(
        json.dumps(manifest.to_dict(), indent=2),
        encoding="utf-8",
    )

    runner = PipelineRunner(
        repo_root=tmp_path,
        options=_options(strict_manifest_warnings=True),
    )

    with pytest.raises(RuntimeError, match="Strict manifest warning policy failed"):
        runner.prepare_manifest()
