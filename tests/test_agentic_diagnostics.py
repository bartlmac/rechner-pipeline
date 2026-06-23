from __future__ import annotations

import json
from pathlib import Path

from rechner_pipeline.models.manifest import ExportManifest
from rechner_pipeline.orchestrate.agentic import (
    _format_repair_context,
    _record_error,
    gate_after_compare_node,
    gate_after_main_node,
    main_llm_node,
    repair_main_node,
    test_llm_node as _test_llm_node,  # Alias: sonst sammelt pytest es als Test
)
from rechner_pipeline.orchestrate.runner import PipelineOptions, PipelineRunner


def _options() -> PipelineOptions:
    return PipelineOptions(
        model="test-model",
        skip_export=True,
        skip_main_llm=False,
        skip_test_llm=True,
        skip_compare_run=False,
        main_max_chars_per_file=100,
        main_max_total_chars=100,
        test_max_chars_per_file=100,
        test_max_total_chars=100,
        reasoning_effort="low",
    )


def _manifest(tmp_path: Path) -> ExportManifest:
    out_dir = tmp_path / "info_from_excel"
    out_dir.mkdir()
    return ExportManifest(
        out_dir=out_dir,
        sheet_csvs=[],
        vba_txts=[],
        names_manager_csv=None,
        replacements={},
        llm_inputs=[],
        all_outputs=[],
        warnings=[],
        prompt_runs=[],
        output_hashes=[],
    )


def _state(tmp_path: Path) -> dict:
    return {
        "repo_root": str(tmp_path),
        "excel_path": "",
        "options": _options(),
        "manifest": _manifest(tmp_path),
        "step_status": {},
        "errors": [],
        "diagnostics": [],
        "repair_contexts": {},
        "repair_artifacts": {},
        "retries": {"_max_main": 1, "_max_test": 1},
        "human_review_required": False,
    }


def test_record_error_writes_structured_compare_diagnostic(tmp_path: Path) -> None:
    state = _state(tmp_path)
    generated_dir = tmp_path / "generated"
    generated_dir.mkdir()
    (generated_dir / "test_run_advanced_result.json").write_text(
        json.dumps(
            {
                "status": "failed",
                "returncode": 7,
                "stdout": "visible stdout",
                "stderr": "visible stderr",
            }
        ),
        encoding="utf-8",
    )

    update = _record_error(
        state,
        "compare",
        RuntimeError("Regression test failed with returncode 7."),
    )

    diagnostics_path = Path(update["agentic_diagnostics_path"])
    payload = json.loads(diagnostics_path.read_text(encoding="utf-8"))
    diagnostic = payload["diagnostics"][0]
    assert diagnostic["step"] == "compare"
    assert diagnostic["category"] == "test"
    assert diagnostic["exception"]["type"] == "RuntimeError"
    assert any(
        item.get("json", {}).get("returncode") == 7
        for item in diagnostic["artifacts"]
    )


def test_gate_routes_failed_main_step_to_repair_before_retry(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state["step_status"] = {"main_llm": "error"}

    update = gate_after_main_node(state)

    assert update["gate_decision"] == "repair"
    assert update["retries"]["main_llm"] == 1


def test_repair_node_creates_context_artifact_for_failed_main_step(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state.update(
        _record_error(
            state,
            "main_llm",
            RuntimeError("Python files in LLM main output do not compile."),
        )
    )

    update = repair_main_node(state)

    artifact_path = Path(update["repair_artifacts"]["main_llm"])
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert payload["target_step"] == "main_llm"
    assert payload["source_step"] == "main_llm"
    assert '"failed_step": "main_llm"' in update["repair_contexts"]["main_llm"]


def test_repair_context_summarizes_large_artifacts() -> None:
    diagnostic = {
        "step": "compare",
        "category": "test",
        "exception": {"type": "RuntimeError", "message": "Regression failed"},
        "artifacts": [
            {
                "path": "/repo/info_from_excel/export_manifest.json",
                "exists": True,
                "json": {
                    "warnings": [],
                    "llm_inputs": [f"input_{i}" for i in range(100)],
                    "prompt_runs": [
                        {
                            "stage": "main_llm",
                            "prompt_chars": 88_000,
                            "total_limit_reached": False,
                            "input_files": [
                                {
                                    "label": "huge.csv",
                                    "included_chars": 50_000,
                                    "truncated": False,
                                    "raw": "x" * 10_000,
                                }
                            ],
                        }
                    ],
                    "output_hashes": [{"path": f"file_{i}", "sha256": "x" * 64} for i in range(100)],
                },
            },
            {
                "path": "/repo/generated/test_run_advanced_result.json",
                "exists": True,
                "json": {
                    "status": "failed",
                    "returncode": 1,
                    "stdout": "noise\n" * 1000 + "ABWEICHUNG: Kalkulation:BJB erwartet=1 berechnet=2\n",
                    "stderr": "",
                },
            },
            {
                "path": "/tmp/run/main_prompt.txt",
                "exists": True,
                "text_excerpt": "prompt text should not be repeated " * 1000,
            },
        ],
    }

    context = _format_repair_context(diagnostic)

    assert len(context) < 5000
    assert "ABWEICHUNG: Kalkulation:BJB" in context
    assert "prompt text should not be repeated" not in context
    assert "output_hashes" not in context


def test_main_llm_node_passes_repair_context_to_runner(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    state["repair_contexts"] = {"main_llm": '{"failed_step": "main_llm"}'}
    seen = {}

    def fake_run_main_llm(self, manifest, repair_context=None):
        seen["repair_context"] = repair_context
        return manifest

    monkeypatch.setattr(PipelineRunner, "run_main_llm", fake_run_main_llm)

    update = main_llm_node(state)

    assert seen["repair_context"] == '{"failed_step": "main_llm"}'
    assert update["step_status"]["main_llm"] == "ok"
    assert update["repair_contexts"] == {}


def test_compare_gate_can_repair_test_generation_once(tmp_path: Path) -> None:
    import dataclasses

    state = _state(tmp_path)
    state["options"] = dataclasses.replace(state["options"], test_mode="llm")
    state["step_status"] = {"compare": "error"}

    update = gate_after_compare_node(state)

    assert update["gate_decision"] == "repair_test"


def test_test_llm_node_skipped_in_fixed_mode(tmp_path: Path) -> None:
    # fixed-Modus: kein LLM-generierter Test -> Stufe übersprungen, kein Call.
    def fail_if_called(self, *a, **k):
        raise AssertionError("run_test_llm darf im fixed-Modus nicht laufen")

    import pytest
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(PipelineRunner, "run_test_llm", fail_if_called)
    try:
        update = _test_llm_node(_state(tmp_path))  # _options() default test_mode="fixed"
    finally:
        monkeypatch.undo()

    assert update["step_status"]["test_llm"] == "skipped"


def test_compare_gate_repairs_main_in_fixed_mode(tmp_path: Path) -> None:
    # fixed: Compare-Fehler = Rechenkern weicht ab -> main neu generieren.
    state = _state(tmp_path)  # _options() -> test_mode default "fixed"
    state["step_status"] = {"compare": "error"}

    update = gate_after_compare_node(state)

    assert update["gate_decision"] == "repair_main"
    assert update["retries"]["compare"] == 1
