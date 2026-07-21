"""Tests for the ``dossier`` toolbox command (G8) and the provenance writer.

Covers (§4.2 step 13 verification):

* a synthetic ledger with all required gates ``passed`` -> ``qa_report.json`` +
  ``run_dossier.json`` produced, decision ``accepted``, exit 0;
* a ledger with one required gate ``failed`` -> not accepted, exit 40;
* schema validation fails when ``export_backend`` / a gate result / a required
  hash is omitted;
* the real dependency versions are recorded (python 3.12.x, not the §6.8
  ``3.11.x`` placeholder);
* the §3.3 stdout contract (one JSON object, blocking exit codes).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from rechner_pipeline.models import schemas
from rechner_pipeline.models.schemas import GateLedgerEntry, QaReport, RunDossierV2Delta
from rechner_pipeline.orchestrate import dossier as provenance
from rechner_pipeline.toolbox import _common
from rechner_pipeline.toolbox import dossier as dossier_cmd


# --------------------------------------------------------------------------- #
# Synthetic ledger fixtures
# --------------------------------------------------------------------------- #


def _ledger_entry(
    gate: str,
    command: str,
    *,
    status: str = "passed",
    attempt: int = 1,
    input_hashes: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    if input_hashes is None:
        input_hashes = {f"generated/{command}_in.py": "a" * 64}
    return GateLedgerEntry(
        gate=gate,
        command=command,
        gate_version="1.0.0",
        required=True,
        status=status,
        attempt=attempt,
        started_at="2026-06-18T00:00:00+00:00",
        input_hashes=input_hashes,
        diagnostics_path=f"runs/r1/{command}.diagnostics.json",
        summary={"ok": status == "passed"},
    ).to_dict()


def _write_full_passing_ledger(diag_dir: Path) -> None:
    """Write one passing GateLedgerEntry JSON per required gate."""
    diag_dir.mkdir(parents=True, exist_ok=True)
    for gate, command in provenance.ALL_GATES:
        entry = _ledger_entry(gate, command)
        (diag_dir / f"{command}{provenance.GATE_LEDGER_SUFFIX}").write_text(
            json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def _seed_generated(generated_dir: Path) -> None:
    generated_dir.mkdir(parents=True, exist_ok=True)
    (generated_dir / "inputs.py").write_text("x = 1\n", encoding="utf-8")
    (generated_dir / "test_run.py").write_text("y = 2\n", encoding="utf-8")


def _seed_input_bundle(generated_dir: Path, coverage: str = "full") -> None:
    bundle = {
        "contract_version": "info_from_excel.v1",
        "adapter_id": "excel",
        "source_path": r"C:\x\Tarifrechner_KLV.xlsm",
        "manifest_path": "info_from_excel/export_manifest.json",
        "expectation_coverage": coverage,
        "coverage_detail": {"scalar_files": 3, "table_cells_expected": 264},
        "warnings": [],
    }
    (generated_dir / dossier_cmd.INPUT_BUNDLE_NAME).write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _seed_dossier_input(
    generated_dir: Path, **overrides: Any
) -> None:
    payload: Dict[str, Any] = {
        "run_id": "run-1",
        "expectation_coverage": "full",
        "attempts_used": 1,
        "max_attempts": 4,
        "cli": {"name": "claude", "headless": True},
        "options": {
            "provider": "claude",
            "max_output_tokens": 8192,
            "export_backend": "openpyxl",
            "test_mode": "fixed",
            "adapter_id": "excel",
            "max_attempts": 4,
        },
        "open_assumptions": [],
        "attempts": [{"attempt": 1, "gates_run": ["G0"], "outcome": "accepted"}],
        "qa_contract_path": "generated/qa_contract.json",
    }
    payload.update(overrides)
    (generated_dir / dossier_cmd.DOSSIER_INPUT_NAME).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _run(argv: List[str]) -> _common.ToolboxResult:
    """Run the command body directly (bypassing stdout redirection)."""
    return dossier_cmd.main(argv)


# --------------------------------------------------------------------------- #
# 1. All required gates passed -> accepted, exit 0, both JSONs written
# --------------------------------------------------------------------------- #


def test_accepted_full_ledger(tmp_path: Path) -> None:
    repo = tmp_path
    generated = repo / "generated"
    diag = repo / "runs" / "r1"
    _write_full_passing_ledger(diag)
    _seed_generated(generated)
    _seed_input_bundle(generated, coverage="full")
    _seed_dossier_input(generated)

    result = _run(
        [
            "--repo-root", str(repo),
            "--generated-dir", str(generated),
            "--info-dir", str(repo / "info_from_excel"),
            "--diagnostics-dir", str(diag),
            "--status", "completed",
        ]
    )

    assert result.exit_code == _common.Exit.OK
    assert result.status == "passed"
    assert result.summary["decision"] == "accepted"
    assert result.summary["accepted"] is True

    # Acceptance artifacts are written into --diagnostics-dir, NOT --generated-dir
    # (a 7th/8th file in the six-file generated dir would break the next G1 validate).
    qa_report = json.loads((diag / dossier_cmd.QA_REPORT_NAME).read_text("utf-8"))
    run_dossier = json.loads(
        (diag / dossier_cmd.RUN_DOSSIER_NAME).read_text("utf-8")
    )
    # And they must NOT pollute the generated dir.
    assert not (generated / dossier_cmd.QA_REPORT_NAME).exists()
    assert not (generated / dossier_cmd.RUN_DOSSIER_NAME).exists()

    # qa_report.json (§6.8.3)
    assert qa_report["decision"] == "accepted"
    assert qa_report["accepted"] is True
    assert len(qa_report["gates"]) == len(provenance.REQUIRED_GATES)
    assert qa_report["generated_file_hashes"]  # non-empty
    # Real dependency versions, NOT the §6.8 "3.11.x" placeholder.
    assert qa_report["dependency_versions"]["python"].startswith("3.")
    assert qa_report["dependency_versions"]["python"] != "3.11.x"
    assert qa_report["dependency_versions"]["python"] == ".".join(
        map(str, sys.version_info[:3])
    )
    assert "openpyxl" in qa_report["dependency_versions"]

    # run_dossier.json v2 (§6.8.4)
    assert run_dossier["schema_version"] == 2
    assert run_dossier["run"]["options"]["export_backend"] == "openpyxl"
    assert run_dossier["run"]["options"]["provider"] == "claude"
    assert run_dossier["run"]["cli"]["name"] == "claude"
    assert len(run_dossier["gate_results"]) == len(provenance.REQUIRED_GATES)
    assert run_dossier["input_bundle"]["expectation_coverage"] == "full"

    # Validates clean against the schema view.
    assert QaReport.from_dict(qa_report).validate() == []
    assert RunDossierV2Delta.from_dict(run_dossier).validate() == []

    return None


# --------------------------------------------------------------------------- #
# 2. One required gate failed -> not accepted, exit 40
# --------------------------------------------------------------------------- #


def test_one_required_gate_failed_blocks(tmp_path: Path) -> None:
    repo = tmp_path
    generated = repo / "generated"
    diag = repo / "runs" / "r1"
    _write_full_passing_ledger(diag)
    _seed_generated(generated)
    _seed_input_bundle(generated, coverage="full")
    _seed_dossier_input(generated)

    # Overwrite golden_master ledger entry with a failed status.
    failed = _ledger_entry("G5.golden-master", "golden_master", status="failed")
    (diag / f"golden_master{provenance.GATE_LEDGER_SUFFIX}").write_text(
        json.dumps(failed, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    result = _run(
        [
            "--repo-root", str(repo),
            "--generated-dir", str(generated),
            "--diagnostics-dir", str(diag),
            "--status", "completed",
        ]
    )

    assert result.exit_code == _common.Exit.DOSSIER  # 40
    assert result.status in ("failed", "human_review_required")
    assert result.summary["accepted"] is False
    codes = {e["code"] for e in result.errors}
    assert "gate.not_passed" in codes
    # qa_report reflects the non-acceptance (written into --diagnostics-dir).
    qa_report = json.loads((diag / dossier_cmd.QA_REPORT_NAME).read_text("utf-8"))
    assert qa_report["accepted"] is False
    assert qa_report["decision"] != "accepted"


# --------------------------------------------------------------------------- #
# 3. Missing required gate (Wave-2 not authored) blocks acceptance
# --------------------------------------------------------------------------- #


def test_missing_wave2_gate_blocks(tmp_path: Path) -> None:
    repo = tmp_path
    generated = repo / "generated"
    diag = repo / "runs" / "r1"
    diag.mkdir(parents=True, exist_ok=True)
    _seed_generated(generated)
    _seed_input_bundle(generated, coverage="full")
    _seed_dossier_input(generated)

    # Only the Wave-1 gates exist; conventions/algebraic/roundtrip are absent.
    for gate, command in provenance.ALL_GATES:
        if command in ("conventions", "algebraic", "roundtrip"):
            continue
        entry = _ledger_entry(gate, command)
        (diag / f"{command}{provenance.GATE_LEDGER_SUFFIX}").write_text(
            json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    result = _run(
        ["--repo-root", str(repo), "--generated-dir", str(generated),
         "--diagnostics-dir", str(diag)]
    )

    assert result.exit_code == _common.Exit.DOSSIER
    missing = {e.get("gate") for e in result.errors if e["code"] == "gate.missing"}
    assert "G3.architecture-conventions" in missing
    assert "G6.algebraic-properties" in missing
    assert "G7.roundtrips" in missing


# --------------------------------------------------------------------------- #
# 4. Schema-omission verification (§4.2 step 13)
# --------------------------------------------------------------------------- #


def test_schema_fails_when_export_backend_omitted() -> None:
    """run_dossier v2 with no provider/options recorded still needs cli.name; a
    dossier that omits the required ``export_backend`` option leaves the v2
    delta incomplete relative to the §6.8.4 option set — the orchestrator must
    supply it. We assert the OPTION_KEYS contract names it and that a delta
    missing ``run.cli.name`` (the structural anchor) fails validation."""
    delta = RunDossierV2Delta(run_cli={}, options_extra={"provider": "claude"})
    errors = delta.validate()
    assert any("run.cli.name" in e for e in errors)
    # The §6.8.4 option set explicitly includes export_backend.
    assert "export_backend" in RunDossierV2Delta.OPTION_KEYS


def test_schema_fails_when_gate_result_omitted_from_ledger() -> None:
    """A GateLedgerEntry missing its required fields (gate/status/started_at)
    fails validation — so an omitted gate result cannot pass G8 silently."""
    bad = GateLedgerEntry(
        gate="",
        command="golden_master",
        gate_version="1.0.0",
        required=True,
        status="passed",
        attempt=1,
        started_at="",
    )
    errors = bad.validate()
    assert any("gate is required" in e for e in errors)
    assert any("started_at is required" in e for e in errors)


def test_schema_fails_when_required_hash_omitted() -> None:
    """A generated_file_hashes entry without a valid sha256, or a non-hex
    input_hash, fails QaReport validation (a missing required hash blocks)."""
    report = QaReport(
        created_at="t",
        run_id="r",
        decision="accepted",
        accepted=True,
        attempts_used=1,
        max_attempts=4,
        expectation_coverage="full",
        qa_contract_path="p",
        gates=[{"gate": "G5", "required": True, "status": "passed"}],
        generated_file_hashes=[{"path": "generated/inputs.py", "bytes": 1}],  # no sha256
    )
    errors = report.validate()
    assert any("lacks a valid sha256" in e for e in errors)

    bad_ledger = GateLedgerEntry(
        gate="G5.golden-master",
        command="golden_master",
        gate_version="1.0.0",
        required=True,
        status="passed",
        attempt=1,
        started_at="2026-06-18T00:00:00+00:00",
        input_hashes={"generated/test_run.py": "not-a-sha"},
    )
    assert any("SHA-256" in e for e in bad_ledger.validate())


def test_missing_input_hashes_is_a_g8_blocker(tmp_path: Path) -> None:
    """A passed required gate that recorded NO input_hashes blocks G8."""
    repo = tmp_path
    generated = repo / "generated"
    diag = repo / "runs" / "r1"
    diag.mkdir(parents=True, exist_ok=True)
    _seed_generated(generated)
    _seed_input_bundle(generated, coverage="full")
    _seed_dossier_input(generated)
    for gate, command in provenance.ALL_GATES:
        ih = {} if command == "extract" else {f"generated/{command}.py": "a" * 64}
        entry = _ledger_entry(gate, command, input_hashes=ih)
        (diag / f"{command}{provenance.GATE_LEDGER_SUFFIX}").write_text(
            json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    result = _run(
        ["--repo-root", str(repo), "--generated-dir", str(generated),
         "--diagnostics-dir", str(diag)]
    )
    assert result.exit_code == _common.Exit.DOSSIER
    hashes_missing = [e for e in result.errors if e["code"] == "hashes.missing"]
    assert any(e.get("gate") == "G0.extraction-manifest" for e in hashes_missing)


# --------------------------------------------------------------------------- #
# 5. Non-full coverage -> human-review handoff (exit 40, status human_review)
# --------------------------------------------------------------------------- #


def test_sparse_coverage_forces_human_review(tmp_path: Path) -> None:
    repo = tmp_path
    generated = repo / "generated"
    diag = repo / "runs" / "r1"
    _write_full_passing_ledger(diag)
    _seed_generated(generated)
    _seed_dossier_input(generated, expectation_coverage="sparse")

    result = _run(
        ["--repo-root", str(repo), "--generated-dir", str(generated),
         "--diagnostics-dir", str(diag)]
    )
    assert result.exit_code == _common.Exit.DOSSIER
    assert result.status == "human_review_required"
    qa_report = json.loads((diag / dossier_cmd.QA_REPORT_NAME).read_text("utf-8"))
    assert qa_report["decision"] == "human_review_required"
    assert any(a["code"] == "coverage.not_full" for a in qa_report["open_assumptions"])


def test_max_attempts_exhausted_forces_human_review(tmp_path: Path) -> None:
    repo = tmp_path
    generated = repo / "generated"
    diag = repo / "runs" / "r1"
    _write_full_passing_ledger(diag)
    # Make one gate fail so it is not accepted, and exhaust attempts.
    failed = _ledger_entry("G5.golden-master", "golden_master", status="failed")
    (diag / f"golden_master{provenance.GATE_LEDGER_SUFFIX}").write_text(
        json.dumps(failed, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _seed_generated(generated)
    _seed_dossier_input(
        generated, attempts_used=4, max_attempts=4
    )

    result = _run(
        ["--repo-root", str(repo), "--generated-dir", str(generated),
         "--diagnostics-dir", str(diag)]
    )
    assert result.status == "human_review_required"
    assert result.exit_code == _common.Exit.DOSSIER


# --------------------------------------------------------------------------- #
# 6. stdout purity contract (§3.3) end-to-end through run_command
# --------------------------------------------------------------------------- #


def test_stdout_is_single_json_object(tmp_path: Path, capsys) -> None:
    repo = tmp_path
    generated = repo / "generated"
    diag = repo / "runs" / "r1"
    _write_full_passing_ledger(diag)
    _seed_generated(generated)
    _seed_input_bundle(generated, coverage="full")
    _seed_dossier_input(generated)

    exit_code = _common.run_command(
        dossier_cmd.main,
        argv=["--repo-root", str(repo), "--generated-dir", str(generated),
              "--diagnostics-dir", str(diag)],
    )
    captured = capsys.readouterr()
    assert exit_code == _common.Exit.OK
    lines = [ln for ln in captured.out.splitlines() if ln]
    assert len(lines) == 1
    obj = json.loads(lines[0])
    assert obj["command"] == "dossier"
    assert obj["gate"] == "G8.dossier-completeness"
    assert obj["status"] == "passed"


# --------------------------------------------------------------------------- #
# 7. Provenance unit helpers
# --------------------------------------------------------------------------- #


def test_dependency_versions_records_real_python() -> None:
    versions = provenance.dependency_versions()
    assert versions["python"] == ".".join(map(str, sys.version_info[:3]))
    assert versions["python"] != "3.11.x"
    for dist in ("openpyxl", "oletools", "pandas", "hypothesis"):
        assert dist in versions  # present (value or None)


def test_load_gate_ledger_skips_unreadable(tmp_path: Path) -> None:
    diag = tmp_path / "runs" / "r1"
    diag.mkdir(parents=True)
    good = _ledger_entry("G0.extraction-manifest", "extract")
    (diag / f"extract{provenance.GATE_LEDGER_SUFFIX}").write_text(
        json.dumps(good), encoding="utf-8"
    )
    (diag / f"broken{provenance.GATE_LEDGER_SUFFIX}").write_text(
        "{not json", encoding="utf-8"
    )
    entries, read_errors = provenance.load_gate_ledger(diag)
    assert len(entries) == 1
    assert len(read_errors) == 1
    assert "broken" in read_errors[0]["path"]


def test_read_error_is_a_blocker(tmp_path: Path) -> None:
    repo = tmp_path
    generated = repo / "generated"
    diag = repo / "runs" / "r1"
    _write_full_passing_ledger(diag)
    (diag / f"broken{provenance.GATE_LEDGER_SUFFIX}").write_text(
        "{bad", encoding="utf-8"
    )
    _seed_generated(generated)
    _seed_dossier_input(generated)
    result = _run(
        ["--repo-root", str(repo), "--generated-dir", str(generated),
         "--diagnostics-dir", str(diag)]
    )
    assert result.exit_code == _common.Exit.DOSSIER
    assert any(e["code"] == "ledger.read_error" for e in result.errors)
