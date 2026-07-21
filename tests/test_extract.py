"""Tests for the ``extract`` toolbox command and the Excel input adapter.

These exercise the migrated extraction subsystem end-to-end against the synthetic
KLV workbook, plus the §4.2-step-3 clean/staged extraction guard, the blocking
exit-10 failure modes, and the COM fail-fast contract.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rechner_pipeline.adapters.excel import ExcelAdapter
from rechner_pipeline.toolbox import extract as extract_cmd

REPO_ROOT = Path(__file__).resolve().parents[1]
KLV = REPO_ROOT / "examples" / "Tarifrechner_KLV.xlsm"

pytestmark = pytest.mark.skipif(not KLV.exists(), reason="KLV example workbook missing")

# openpyxl + oletools + pandas are required for the openpyxl backend path.
pytest.importorskip("openpyxl")
pytest.importorskip("oletools")
pytest.importorskip("pandas")


def _run(out_dir: Path, *extra: str):
    """Invoke the command body and return its ToolboxResult dict."""
    argv = [
        "--repo-root",
        str(REPO_ROOT),
        "--input",
        str(KLV),
        "--out-dir",
        str(out_dir),
        "--adapter",
        "excel",
        "--export-backend",
        "openpyxl",
        *extra,
    ]
    result = extract_cmd.main(argv)
    return result.to_dict()


# --------------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------------- #


def test_klv_extract_full_coverage(tmp_path: Path):
    out_dir = tmp_path / "klv_info"
    out = _run(out_dir)

    assert out["exit_code"] == 0
    assert out["status"] == "passed"
    assert out["command"] == "extract"

    # info_from_excel-shaped artifacts exist on disk.
    assert (out_dir / "Kalkulation.csv").is_file()
    assert (out_dir / "Tafeln.csv").is_file()
    assert (out_dir / "Kalkulation_compressed.csv").is_file()
    assert (out_dir / "Kalkulation_scalar.json").is_file()
    assert (out_dir / "Kalkulation_table_values.csv").is_file()
    assert (out_dir / "names_manager.csv").is_file()
    assert (out_dir / "export_manifest.json").is_file()
    assert (out_dir / "vba" / "mConstants.txt").is_file()

    # Coverage is explicit and full (numeric scalar expectations present).
    assert out["summary"]["expectation_coverage"] == "full"
    bundle = out["summary"]["input_bundle"]
    assert bundle["contract_version"] == "info_from_excel.v1"
    assert bundle["adapter_id"] == "excel"
    detail = bundle["coverage_detail"]
    assert detail["scalar_keys_numeric"] == 5
    assert detail["table_files"] == 1
    assert detail["table_cells_expected"] > 0

    # llm_inputs: compressed sheet preferred, raw Tafeln (no formulas) kept.
    llm = out["paths"]["llm_inputs"]
    assert any(p.endswith("Kalkulation_compressed.csv") for p in llm)
    assert any(p.endswith("Tafeln.csv") for p in llm)
    assert not any(p.endswith("Kalkulation.csv") for p in llm)  # raw replaced

    # Hashes are recorded and repo-relative (no drive letter / absolute path).
    assert out["output_hashes"]
    for key in out["output_hashes"]:
        assert not key.startswith(str(REPO_ROOT))

    # input_hashes carries the genuine extraction input (the source workbook), so
    # G0's ledger never has an empty input_hashes -> no dossier 'hashes.missing'.
    assert out["input_hashes"]
    assert any(k.endswith("Tarifrechner_KLV.xlsm") for k in out["input_hashes"])
    for key in out["input_hashes"]:
        assert not key.startswith(str(REPO_ROOT))

    # The InputBundle (incl. expectation_coverage) is persisted into the out-dir
    # so the dossier can read coverage automatically (no manual file).
    bundle_path = out_dir / "input_bundle.json"
    assert bundle_path.is_file()
    persisted = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert persisted["expectation_coverage"] == "full"
    assert persisted["adapter_id"] == "excel"
    assert out["paths"]["input_bundle"].endswith("input_bundle.json")


def test_scalar_json_shape(tmp_path: Path):
    out_dir = tmp_path / "klv_info"
    _run(out_dir)
    scalars = json.loads((out_dir / "Kalkulation_scalar.json").read_text(encoding="utf-8"))
    # Exact key set from the synthetic KLV workbook (§2.2.11).
    assert set(scalars) == {"Bxt", "BJB", "BZB", "Pxt", "ratzu"}
    assert scalars["ratzu"] == 0.05


def test_addresses_are_absolute_dollar_form(tmp_path: Path):
    """The scalar/table lookups depend on $A$1 addresses (§2.2.3 caveat)."""
    out_dir = tmp_path / "klv_info"
    _run(out_dir)
    first_rows = (out_dir / "Kalkulation.csv").read_text(encoding="utf-8").splitlines()[1:4]
    for row in first_rows:
        addr = row.split(";")[1]
        assert addr.startswith("$") and "$" in addr[1:]


# --------------------------------------------------------------------------- #
# §4.2 step 3 — clean/staged extraction: stale derived files must not survive
# --------------------------------------------------------------------------- #


def test_stale_derived_file_is_removed_on_rerun(tmp_path: Path):
    out_dir = tmp_path / "klv_info"
    out_dir.mkdir()

    # Inject a stale compressed CSV for a sheet whose real compressed output would
    # differ, plus a stale scalar and table for a prefix that the real run would
    # never produce (so we can prove it was removed, not just overwritten).
    stale_compressed = out_dir / "Kalkulation_compressed.csv"
    stale_compressed.write_text("STALE;GARBAGE;DATA\n", encoding="utf-8")
    stale_scalar = out_dir / "GhostSheet_scalar.json"
    stale_scalar.write_text('{"stale": 1}', encoding="utf-8")
    stale_table = out_dir / "GhostSheet_table_values.csv"
    stale_table.write_text("stale\n1\n", encoding="utf-8")

    out = _run(out_dir)
    assert out["exit_code"] == 0

    # The ghost derived files are gone (cleaned, not inherited).
    assert not stale_scalar.exists()
    assert not stale_table.exists()
    # The compressed file was cleaned then regenerated; it must not contain the
    # stale garbage.
    regen = stale_compressed.read_text(encoding="utf-8")
    assert "STALE;GARBAGE;DATA" not in regen
    assert regen.startswith("Section;Blatt;Adresse")

    cleaned = out["summary"]["cleaned_stale_derived"]
    assert "Kalkulation_compressed.csv" in cleaned
    assert "GhostSheet_scalar.json" in cleaned
    assert "GhostSheet_table_values.csv" in cleaned


def test_clean_preserves_raw_and_source_artifacts(tmp_path: Path):
    """Cleaning only touches derived files, never raw CSVs / names / VBA."""
    out_dir = tmp_path / "klv_info"
    _run(out_dir)  # first run materializes everything
    # Mark the raw sheet CSV; a second run must not delete it.
    raw = out_dir / "Kalkulation.csv"
    raw_bytes_before = raw.read_bytes()
    names_before = (out_dir / "names_manager.csv").read_bytes()

    _run(out_dir)
    assert raw.read_bytes() == raw_bytes_before
    assert (out_dir / "names_manager.csv").read_bytes() == names_before


def test_clean_stale_helper_only_targets_derived(tmp_path: Path):
    out_dir = tmp_path / "info"
    out_dir.mkdir()
    (out_dir / "Sheet1.csv").write_text("raw", encoding="utf-8")
    (out_dir / "Sheet1_compressed.csv").write_text("c", encoding="utf-8")
    (out_dir / "Sheet1_scalar.json").write_text("{}", encoding="utf-8")
    (out_dir / "Sheet1_table_values.csv").write_text("", encoding="utf-8")
    (out_dir / "names_manager.csv").write_text("n", encoding="utf-8")

    removed = extract_cmd._clean_stale_derived(out_dir)
    assert set(removed) == {
        "Sheet1_compressed.csv",
        "Sheet1_scalar.json",
        "Sheet1_table_values.csv",
    }
    assert (out_dir / "Sheet1.csv").exists()
    assert (out_dir / "names_manager.csv").exists()


# --------------------------------------------------------------------------- #
# Blocking failures (exit 10)
# --------------------------------------------------------------------------- #


def test_missing_source_exits_10(tmp_path: Path):
    result = extract_cmd.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--input",
            str(tmp_path / "nope.xlsm"),
            "--out-dir",
            str(tmp_path / "out"),
            "--adapter",
            "excel",
        ]
    )
    out = result.to_dict()
    assert out["exit_code"] == 10
    assert out["status"] == "failed"
    assert out["errors"][0]["code"] == "source_missing"


def test_unsupported_adapter_auto_no_match_exits_10(tmp_path: Path):
    bogus = tmp_path / "doc.txt"
    bogus.write_text("not a workbook", encoding="utf-8")
    result = extract_cmd.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--input",
            str(bogus),
            "--out-dir",
            str(tmp_path / "out"),
            "--adapter",
            "auto",
        ]
    )
    out = result.to_dict()
    assert out["exit_code"] == 10
    assert out["errors"][0]["code"] == "unsupported_adapter"


def test_missing_input_flag_exits_10(tmp_path: Path):
    result = extract_cmd.main(["--repo-root", str(REPO_ROOT), "--out-dir", str(tmp_path)])
    out = result.to_dict()
    assert out["exit_code"] == 10
    assert out["errors"][0]["code"] == "missing_input"


def test_com_backend_unavailable_fails_fast(tmp_path: Path):
    """Selecting the COM backend without pywin32/Excel must fail fast (exit 10),
    not silently fall back to openpyxl."""
    # This host has no pywin32; if it ever did, skip rather than assert.
    try:
        import win32com.client  # type: ignore  # noqa: F401

        pytest.skip("pywin32 present on this host; COM fail-fast not exercised")
    except Exception:
        pass

    result = extract_cmd.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--input",
            str(KLV),
            "--out-dir",
            str(tmp_path / "com_out"),
            "--adapter",
            "excel",
            "--export-backend",
            "com",
        ]
    )
    out = result.to_dict()
    assert out["exit_code"] == 10
    assert out["errors"][0]["code"] == "dependency_unavailable"
    assert out["errors"][0]["backend"] == "com"
    # No openpyxl artifacts were written as a silent fallback.
    assert not (tmp_path / "com_out" / "Kalkulation.csv").exists()


# --------------------------------------------------------------------------- #
# Adapter-level behavior
# --------------------------------------------------------------------------- #


def test_adapter_builds_manifest_from_path_objects(tmp_path: Path):
    """The manifest's path fields are Path objects, not strings (byte-compat)."""
    out_dir = tmp_path / "klv_info"
    bundle = ExcelAdapter(backend="openpyxl").extract(KLV, out_dir)
    assert bundle.manifest is not None
    assert all(isinstance(p, Path) for p in bundle.manifest.sheet_csvs)
    assert all(isinstance(p, Path) for p in bundle.manifest.llm_inputs)
    assert isinstance(bundle.manifest.out_dir, Path)
    assert bundle.validate() == []
    assert bundle.expectation_coverage == "full"


def test_adapter_supports_suffixes():
    assert ExcelAdapter.supports(Path("x.xlsm"))
    assert ExcelAdapter.supports(Path("x.XLSX"))
    assert not ExcelAdapter.supports(Path("x.docx"))


def test_strict_manifest_warnings_pass_when_no_warnings(tmp_path: Path):
    """KLV produces no strict warnings, so --strict-manifest-warnings still passes."""
    out = _run(tmp_path / "klv_info", "--strict-manifest-warnings")
    assert out["exit_code"] == 0
    assert out.get("warnings", []) == []
