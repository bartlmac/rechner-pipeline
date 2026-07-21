"""Round-trip + validation tests for the foundation data models.

Proves each schema serializes -> validates -> deserializes, that the AS-IS
``ExportManifest`` reproduces the §6.4 JSON shape, and that ``_common`` honors the
§3.3 contract (single JSON stdout object, exit codes, request-json reader).
"""

from __future__ import annotations

import io
import json
from pathlib import Path

from rechner_pipeline.models.bundle import (
    CONTRACT_VERSION,
    CoverageDetail,
    InputBundle,
)
from rechner_pipeline.models.manifest import (
    ExportManifest,
    FileHashRecord,
    ManifestWarning,
    PromptInputRecord,
    PromptRecord,
)
from rechner_pipeline.models.schemas import (
    CommonResult,
    GateLedgerEntry,
    QaContract,
    QaReport,
    RunDossierV2Delta,
)
from rechner_pipeline.toolbox import _common


# --------------------------------------------------------------------------- #
# ExportManifest §6.4 shape
# --------------------------------------------------------------------------- #


def _sample_manifest() -> ExportManifest:
    return ExportManifest(
        out_dir="info_from_excel",
        sheet_csvs=["info_from_excel/Kalkulation.csv"],
        vba_txts=["info_from_excel/Module1.txt"],
        names_manager_csv="info_from_excel/names_manager.csv",
        replacements={
            "info_from_excel/Kalkulation.csv": "info_from_excel/Kalkulation_compressed.csv"
        },
        llm_inputs=["info_from_excel/Kalkulation_compressed.csv"],
        all_outputs=[
            "info_from_excel/Kalkulation.csv",
            "info_from_excel/Kalkulation_compressed.csv",
        ],
        warnings=[
            ManifestWarning(
                code="prompt.file_truncated",
                stage="main_llm",
                message="truncated",
                strict_error=True,
                path="info_from_excel/big.csv",
                details={"limit": 1000},
            )
        ],
        prompt_runs=[
            PromptRecord(
                stage="main_llm",
                template_path="prompts/main.txt",
                debug_prompt_path="runs/r1/main_prompt.txt",
                prompt_chars=1234,
                prompt_sha256="a" * 64,
                input_files=[
                    PromptInputRecord(
                        path="info_from_excel/Kalkulation_compressed.csv",
                        label="kalk",
                        original_chars=2000,
                        included_chars=1000,
                        original_sha256="b" * 64,
                        truncated=True,
                    )
                ],
                total_limit_reached=False,
                output_chars=500,
                output_sha256="c" * 64,
            )
        ],
        output_hashes=[
            FileHashRecord(path="generated/inputs.py", bytes=1234, sha256="d" * 64)
        ],
    )


def test_export_manifest_roundtrip_and_shape():
    manifest = _sample_manifest()
    data = manifest.to_dict()

    # Top-level §6.4 keys all present.
    expected_keys = {
        "out_dir",
        "sheet_csvs",
        "vba_txts",
        "names_manager_csv",
        "replacements",
        "llm_inputs",
        "all_outputs",
        "warnings",
        "prompt_runs",
        "output_hashes",
    }
    assert set(data.keys()) == expected_keys

    # Paths serialize as strings.
    assert isinstance(data["out_dir"], str)
    assert all(isinstance(p, str) for p in data["sheet_csvs"])

    # Nested record shapes per §6.4.
    warning = data["warnings"][0]
    assert warning["strict_error"] is True
    assert warning["path"] == "info_from_excel/big.csv"
    assert warning["details"] == {"limit": 1000}

    prompt = data["prompt_runs"][0]
    assert prompt["output_chars"] == 500
    assert prompt["output_sha256"] == "c" * 64
    assert prompt["input_files"][0]["truncated"] is True

    assert data["output_hashes"][0] == {
        "path": "generated/inputs.py",
        "bytes": 1234,
        "sha256": "d" * 64,
    }

    # Full round trip through JSON is idempotent. The dataclass declares Path
    # fields, so from_dict() canonicalizes path strings (e.g. OS separators);
    # round-trip stability is asserted from the normalized form onward.
    reloaded = ExportManifest.from_dict(json.loads(json.dumps(data)))
    normalized = reloaded.to_dict()
    reloaded2 = ExportManifest.from_dict(json.loads(json.dumps(normalized)))
    assert reloaded2.to_dict() == normalized
    assert set(normalized.keys()) == expected_keys


def test_manifest_warning_omits_empty_optional_fields():
    warning = ManifestWarning(code="c", stage="s", message="m", strict_error=False)
    assert warning.to_dict() == {
        "code": "c",
        "stage": "s",
        "message": "m",
        "strict_error": False,
    }


def test_prompt_record_omits_output_when_none():
    record = PromptRecord(
        stage="test_llm",
        template_path="t",
        debug_prompt_path="d",
        prompt_chars=1,
        prompt_sha256="e" * 64,
        input_files=[],
        total_limit_reached=False,
    )
    out = record.to_dict()
    assert "output_chars" not in out
    assert "output_sha256" not in out


def test_manifest_names_manager_none_serializes_empty_string():
    manifest = _sample_manifest()
    manifest_no_nm = ExportManifest.from_dict(
        {**manifest.to_dict(), "names_manager_csv": ""}
    )
    assert manifest_no_nm.names_manager_csv is None
    assert manifest_no_nm.to_dict()["names_manager_csv"] == ""


# --------------------------------------------------------------------------- #
# InputBundle §6.5 / §6.8.5
# --------------------------------------------------------------------------- #


def test_input_bundle_roundtrip_and_validate():
    bundle = InputBundle(
        source_path=r"C:\x\Tarifrechner_KLV.xlsm",
        adapter_id="excel",
        out_dir="info_from_excel",
        manifest_path="info_from_excel/export_manifest.json",
        expectation_coverage="full",
        coverage_detail=CoverageDetail(
            scalar_files=3,
            scalar_keys_expected=12,
            scalar_keys_numeric=11,
            table_files=2,
            table_cells_expected=264,
            sheets_with_compressed=4,
            names_manager_present=True,
            source_text_files=5,
        ),
    )
    assert bundle.validate() == []

    data = bundle.to_dict()
    assert data["contract_version"] == CONTRACT_VERSION
    reloaded = InputBundle.from_dict(json.loads(json.dumps(data)))
    assert reloaded.to_dict() == data

    # Coverage block (§6.8.5) carries the audit subset.
    block = bundle.coverage_block()
    assert block["expectation_coverage"] == "full"
    assert block["coverage_detail"]["table_cells_expected"] == 264
    assert "out_dir" not in block  # block is the dossier subset


def test_input_bundle_rejects_bad_coverage():
    bundle = InputBundle(
        source_path="s",
        adapter_id="excel",
        out_dir="o",
        manifest_path="m",
        expectation_coverage="partial",
    )
    errors = bundle.validate()
    assert any("expectation_coverage" in e for e in errors)


# --------------------------------------------------------------------------- #
# §6.8.1 CommonResult
# --------------------------------------------------------------------------- #


def test_common_result_roundtrip_and_validate():
    result = CommonResult(
        command="golden_master",
        gate="G5.golden-master",
        gate_version="1.0.0",
        status="passed",
        exit_code=0,
        paths={"repo_root": r"C:\repo"},
        summary={"scalars_tested": 5},
        input_hashes={"generated/test_run.py": "f" * 64},
        metrics={"duration_ms": 812},
    )
    assert result.validate() == []
    data = result.to_dict()
    assert data["schema_version"] == 1
    assert data["errors"] == []
    assert data["repair_hints"] == []
    reloaded = CommonResult.from_dict(json.loads(json.dumps(data)))
    assert reloaded.validate() == []
    assert reloaded.to_dict() == data


def test_common_result_status_must_mirror_exit_code():
    bad = CommonResult(
        command="c", gate_version="1.0.0", status="passed", exit_code=20
    )
    assert any("mirror" in e for e in bad.validate())


def test_common_result_rejects_nonstandard_exit_code():
    bad = CommonResult(command="c", gate_version="1.0.0", status="failed", exit_code=7)
    assert any("standard exit code" in e for e in bad.validate())


# --------------------------------------------------------------------------- #
# §6.8.2 GateLedgerEntry
# --------------------------------------------------------------------------- #


def test_gate_ledger_entry_roundtrip_and_validate():
    entry = GateLedgerEntry(
        gate="G3.architecture-conventions",
        command="conventions",
        gate_version="1.0.0",
        required=True,
        status="passed",
        attempt=2,
        started_at="2026-06-18T00:00:00+00:00",
        input_hashes={"generated/actuarial.py": "a" * 64},
        diagnostics_path="runs/r1/conventions.diagnostics.json",
        summary={"circular": False},
    )
    assert entry.validate() == []
    data = entry.to_dict()
    reloaded = GateLedgerEntry.from_dict(json.loads(json.dumps(data)))
    assert reloaded.to_dict() == data
    assert reloaded.validate() == []


# --------------------------------------------------------------------------- #
# §6.8.3 QaReport
# --------------------------------------------------------------------------- #


def test_qa_report_accepted_roundtrip():
    report = QaReport(
        created_at="2026-06-18T00:00:00+00:00",
        run_id="run-1",
        decision="accepted",
        accepted=True,
        attempts_used=2,
        max_attempts=4,
        expectation_coverage="full",
        qa_contract_path="generated/qa_contract.json",
        gates=[{"gate": "G0.extraction-manifest", "required": True, "status": "passed"}],
        generated_file_hashes=[
            {"path": "generated/inputs.py", "bytes": 1234, "sha256": "b" * 64}
        ],
        dependency_versions={"python": "3.12.4", "openpyxl": "3.1.5"},
        tafeln_xml_canonical_sha256="c" * 64,
    )
    assert report.compute_accepted() is True
    assert report.validate() == []
    data = report.to_dict()
    reloaded = QaReport.from_dict(json.loads(json.dumps(data)))
    assert reloaded.to_dict() == data
    assert reloaded.validate() == []


def test_qa_report_non_accepted_requires_evidence():
    report = QaReport(
        created_at="t",
        run_id="r",
        decision="failed",
        accepted=False,
        attempts_used=4,
        max_attempts=4,
        expectation_coverage="full",
        qa_contract_path="p",
        gates=[{"gate": "G5", "required": True, "status": "failed"}],
    )
    assert report.validate() == []
    assert report.compute_accepted() is False


def test_qa_report_accepted_true_with_failed_decision_invalid():
    report = QaReport(
        created_at="t",
        run_id="r",
        decision="failed",
        accepted=True,
        attempts_used=1,
        max_attempts=4,
        expectation_coverage="full",
        qa_contract_path="p",
    )
    assert any("accepted=true" in e for e in report.validate())


# --------------------------------------------------------------------------- #
# §6.8.4 RunDossierV2Delta
# --------------------------------------------------------------------------- #


def test_run_dossier_v2_delta_roundtrip_and_merge():
    delta = RunDossierV2Delta(
        run_cli={"name": "claude", "headless": True},
        options_extra={
            "provider": "claude",
            "max_output_tokens": 8192,
            "export_backend": "openpyxl",
            "test_mode": "fixed",
            "adapter_id": "excel",
            "max_attempts": 4,
        },
        qa_report={"path": "generated/qa_report.json", "exists": True},
        gate_results=[{"gate": "G0.extraction-manifest", "status": "passed"}],
        attempts=[{"attempt": 1, "gates_run": ["G0"], "outcome": "accepted"}],
        input_bundle={"expectation_coverage": "full"},
    )
    assert delta.validate() == []
    data = delta.to_dict()
    assert data["schema_version"] == 2
    reloaded = RunDossierV2Delta.from_dict(json.loads(json.dumps(data)))
    assert reloaded.to_dict() == data
    assert reloaded.validate() == []

    # Merge onto an AS-IS dossier (§6.4) bumps version + adds keys.
    as_is = {
        "schema_version": 1,
        "run": {"status": "passed", "options": {"model": "x"}},
        "warnings": [],
    }
    merged = delta.merge_into(as_is)
    assert merged["schema_version"] == 2
    assert merged["run"]["options"]["model"] == "x"  # AS-IS preserved
    assert merged["run"]["options"]["provider"] == "claude"  # delta added
    assert merged["run"]["cli"]["name"] == "claude"
    assert merged["warnings"] == []  # AS-IS structure preserved
    assert as_is["schema_version"] == 1  # not mutated


def test_run_dossier_v2_delta_rejects_bad_provider():
    delta = RunDossierV2Delta(
        run_cli={"name": "x"}, options_extra={"provider": "gpt"}
    )
    assert any("provider" in e for e in delta.validate())


# --------------------------------------------------------------------------- #
# §6.8.6 QaContract
# --------------------------------------------------------------------------- #


def test_qa_contract_roundtrip_and_validate():
    contract = QaContract(
        product_type="endowment_net_premium",
        interest_basis={"annual_effective_rate": 0.025, "v": "1/(1+i)", "d": "i/(1+i)"},
        timing_convention="annuity_due",
        terminal_age_policy={"omega": 121, "q_omega": 1.0},
        function_mappings={"qx": "commutation.qx", "Ax": "actuarial.Ax"},
        tiers_enabled=["mortality_invariants", "commutation_identities"],
        tolerances={"rel_tol": 1e-9, "abs_tol": 1e-12},
        property_engine={"name": "hypothesis", "max_examples": 200},
    )
    assert contract.validate() == []
    data = contract.to_dict()
    reloaded = QaContract.from_dict(json.loads(json.dumps(data)))
    assert reloaded.to_dict() == data
    assert reloaded.validate() == []


def test_qa_contract_requires_tiers():
    contract = QaContract(
        product_type="p",
        interest_basis={"i": 1},
        timing_convention="annuity_due",
        terminal_age_policy={},
        function_mappings={"qx": "commutation.qx"},
        tiers_enabled=[],
    )
    assert any("tiers_enabled" in e for e in contract.validate())


# --------------------------------------------------------------------------- #
# _common contract (§3.3)
# --------------------------------------------------------------------------- #


def test_common_exit_codes_complete():
    for code in (2, 10, 20, 21, 22, 30, 31, 32, 40, 50):
        assert code in _common.EXIT.values()
    assert _common.SCHEMA_VERSION == 1


def test_common_emit_json_single_object():
    buf = io.StringIO()
    _common.emit_json({"a": 1, "b": "x"}, stream=buf)
    text = buf.getvalue()
    assert text.endswith("\n")
    assert json.loads(text) == {"a": 1, "b": "x"}
    assert text.count("\n") == 1  # exactly one object, one trailing newline


def test_common_build_result_status_derived_from_exit():
    passed = _common.build_result(
        command="extract", gate_version="1.0.0", exit_code=0
    )
    assert passed.status == "passed"
    assert passed.exit_code == 0

    failed = _common.build_result(
        command="extract", gate_version="1.0.0", exit_code=_common.Exit.EXTRACTION
    )
    assert failed.status == "failed"

    # errors / repair_hints always present (§6.8.1).
    out = passed.to_dict()
    assert out["errors"] == []
    assert out["repair_hints"] == []


def test_common_build_result_human_review_status():
    result = _common.build_result(
        command="dossier",
        gate_version="1.0.0",
        status="human_review_required",
        exit_code=_common.Exit.DOSSIER,
    )
    assert result.status == "human_review_required"


def test_common_read_request_json_stdin_and_merge():
    request = _common.read_request_json("-", stdin=io.StringIO('{"out_dir": "x"}'))
    assert request == {"out_dir": "x"}

    class Args:
        out_dir = None
        repo_root = "explicit"

    merged = _common.merge_request_into_args(Args(), {"out_dir": "x", "repo_root": "y"})
    assert merged.out_dir == "x"  # filled from request
    assert merged.repo_root == "explicit"  # explicit flag wins


def test_common_read_request_json_none_is_empty():
    assert _common.read_request_json(None) == {}


def test_common_invalid_status_rejected():
    import pytest

    with pytest.raises(ValueError):
        _common.ToolboxResult(command="c", status="bogus", gate_version="1.0.0")


# --------------------------------------------------------------------------- #
# Guardrails (wave0): run_command stdout purity, human-review, hash_files base
# --------------------------------------------------------------------------- #


def test_run_command_stdout_purity(capsys):
    import warnings as _warnings

    def main(argv):
        print("library banner")  # library chatter -> must NOT reach real stdout
        _warnings.warn("noisy pandas warning")  # must be silenced
        return _common.build_result(
            command="extract", gate_version="1.0.0", exit_code=0
        )

    exit_code = _common.run_command(main, argv=[])
    captured = capsys.readouterr()

    assert exit_code == 0
    # Real stdout is EXACTLY one JSON object and nothing else.
    lines = [ln for ln in captured.out.splitlines() if ln]
    assert len(lines) == 1
    obj = json.loads(lines[0])
    assert obj["command"] == "extract"
    assert obj["status"] == "passed"
    assert "library banner" not in captured.out
    assert "noisy pandas warning" not in captured.out
    # The banner was redirected to stderr.
    assert "library banner" in captured.err


def test_run_command_exception_path(capsys):
    def main(argv):
        raise RuntimeError("boom-secret-detail")

    exit_code = _common.run_command(main, argv=[])
    captured = capsys.readouterr()

    assert exit_code == _common.Exit.INTERNAL  # 50
    lines = [ln for ln in captured.out.splitlines() if ln]
    assert len(lines) == 1
    obj = json.loads(lines[0])
    assert obj["exit_code"] == 50
    assert obj["status"] == "failed"
    assert obj["errors"][0]["type"] == "RuntimeError"
    assert "boom-secret-detail" in obj["errors"][0]["message"]
    # No traceback leaks to stdout; it goes to stderr only.
    assert "Traceback" not in captured.out
    assert "Traceback" in captured.err


def test_run_command_accepts_result_exit_tuple(capsys):
    def main(argv):
        result = _common.build_result(
            command="dossier", gate_version="1.0.0", exit_code=_common.Exit.DOSSIER
        )
        return result, result.exit_code

    exit_code = _common.run_command(main, argv=[])
    captured = capsys.readouterr()
    assert exit_code == _common.Exit.DOSSIER
    assert json.loads(captured.out.strip())["status"] == "failed"


def test_human_review_result_dossier_code_and_validates():
    result = _common.human_review_result(
        command="dossier", gate_version="1.0.0", reason="dossier"
    )
    assert result.status == "human_review_required"
    assert result.exit_code == 40  # canonical DOSSIER handoff
    # Round-trips through the schema view and validates clean.
    common = CommonResult.from_dict(result.to_dict())
    assert common.validate() == []


def test_human_review_result_coverage_code_and_validates():
    result = _common.human_review_result(
        command="algebraic", gate_version="1.0.0", reason="coverage"
    )
    assert result.status == "human_review_required"
    assert result.exit_code == 31  # canonical ALGEBRAIC / sparse-coverage handoff
    common = CommonResult.from_dict(result.to_dict())
    assert common.validate() == []


def test_human_review_result_rejects_passing_exit_code():
    import pytest

    with pytest.raises(ValueError):
        _common.human_review_result(
            command="dossier", gate_version="1.0.0", exit_code=0
        )


def test_human_review_exit_code_mapping_constant():
    assert _common.HUMAN_REVIEW_EXIT_CODES == {"dossier": 40, "coverage": 31}


def test_hash_files_keys_are_repo_relative():
    # A file inside the repo root hashes to a repo-relative, non-absolute key.
    target = _common.REPO_ROOT / "pyproject.toml"
    out = _common.hash_files([target])
    (key,) = out.keys()
    assert key == "pyproject.toml"
    assert not Path(key).is_absolute()
    assert "\\" not in key and "/" not in key  # top-level file, no separator
    assert len(out[key]) == 64  # sha256 hex


def test_hash_files_base_none_keeps_path_as_given(tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("hello", encoding="utf-8")
    out = _common.hash_files([f], base=None)
    (key,) = out.keys()
    assert key == str(f)  # exact path string, not relativized


def test_schemas_constants_are_common_source_of_truth():
    from rechner_pipeline.models import schemas as _schemas

    assert _schemas.STATUS_VALUES is _common.STATUSES
    assert _schemas.SCHEMA_VERSION == _common.SCHEMA_VERSION
    assert _schemas._STANDARD_EXIT_CODES == _common.STANDARD_EXIT_CODES
