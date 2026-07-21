"""Golden-master gate tests (G5) + the §2.6 false-acceptance fix.

Three layers:

1. **Compare engine** (:mod:`rechner_pipeline.qa.golden_master`): the original
   AS-IS semantics that must be preserved (rounding, separator-insensitive but
   case-sensitive column matching, null-soll skipping).
2. **Regression of the fix**: an unmatched expected column now fails
   (``Report.ok is False``) where the AS-IS code passed; a zero-comparison run is
   flagged via ``compared_anything is False``.
3. **End-to-end command** (:mod:`rechner_pipeline.toolbox.golden_master`): the
   four mandated fixtures (match -> 0, mismatch -> 30, unmatched column -> 30,
   zero-comparison -> 31) run through fs_confine on a synthetic generated kernel.
"""

from __future__ import annotations

import json
from pathlib import Path

from rechner_pipeline.qa.golden_master import _norm_colname, compare
from rechner_pipeline.toolbox import golden_master as gm_cmd
from rechner_pipeline.toolbox._common import Exit


# --------------------------------------------------------------------------- #
# 1. Compare engine — preserved AS-IS semantics
# --------------------------------------------------------------------------- #


def _expected(scalars=None, header=None, rows=None):
    return {
        "scalars": {"Kalkulation": scalars or {}},
        "tables": {"Kalkulation": (header or [], rows or [])},
    }


def test_norm_colname_separators_but_case_sensitive():
    assert _norm_colname("A_xn") == _norm_colname("Axn")
    assert _norm_colname("a xn") == _norm_colname("axn")
    assert _norm_colname("Axn") != _norm_colname("axn")


def test_compare_all_match():
    expected = _expected(
        scalars={"BJB": 4465.6547, "ratzu": 0.05},
        header=["Axn", "axn"],
        rows=[{"Axn": "1.5", "axn": "2.5"}, {"Axn": "3.0", "axn": "4.0"}],
    )
    computed = {
        "scalars": {"Kalkulation": {"BJB": 4465.65470, "ratzu": 0.05}},
        "tables": {"Kalkulation": [{"Axn": 1.5, "axn": 2.5}, {"Axn": 3.0, "axn": 4.0}]},
    }
    r = compare(expected, computed)
    assert r.ok
    assert r.scalars_tested == 2
    assert r.table_cells_tested == 4
    assert r.deviations == []
    assert r.compared_anything


def test_compare_scalar_deviation():
    expected = _expected(scalars={"BJB": 4465.6547})
    computed = {"scalars": {"Kalkulation": {"BJB": 9999.0}}, "tables": {}}
    r = compare(expected, computed)
    assert not r.ok
    assert any("BJB" in d for d in r.deviations)


def test_compare_skips_null_scalars():
    expected = _expected(scalars={"BJB": None, "ratzu": 0.05})
    computed = {"scalars": {"Kalkulation": {"ratzu": 0.05}}, "tables": {}}
    r = compare(expected, computed)
    assert r.ok
    assert r.scalars_skipped == 1
    assert r.scalars_tested == 1


def test_compare_column_separator_variant_matches():
    expected = _expected(header=["A_xn"], rows=[{"A_xn": "1.5"}])
    computed = {"scalars": {}, "tables": {"Kalkulation": [{"Axn": 1.5}]}}
    r = compare(expected, computed)
    assert r.ok and r.table_cells_tested == 1


def test_compare_4decimal_rounding_tolerance():
    expected = _expected(scalars={"x": 1.23456})
    computed = {"scalars": {"Kalkulation": {"x": 1.234561}}, "tables": {}}
    assert compare(expected, computed).ok
    computed2 = {"scalars": {"Kalkulation": {"x": 1.23446}}, "tables": {}}
    assert not compare(expected, computed2).ok


# --------------------------------------------------------------------------- #
# 2. Regression of the §2.6 false-acceptance fix (engine level)
# --------------------------------------------------------------------------- #


def test_FIX_unmatched_expected_column_now_fails():
    """AS-IS: an unmatched expected column with data was recorded but ``ok`` was
    still True (false-green). NEW: it makes ``ok`` False."""
    expected = _expected(header=["Axn"], rows=[{"Axn": "1.5"}])
    computed = {"scalars": {}, "tables": {"Kalkulation": [{"axn": 1.5}]}}  # case-mismatch
    r = compare(expected, computed)

    assert "Kalkulation:Axn" in r.unmatched_columns
    assert r.table_cells_tested == 0
    # AS-IS verdict was `not r.deviations` == True; that would have been a pass.
    assert r.deviations == []  # still no "deviation" entry — proving the AS-IS pass
    # NEW verdict folds in unmatched_columns:
    assert r.ok is False


def test_FIX_zero_comparison_is_visible():
    """A run with no expectations compares nothing; ``compared_anything`` is False
    so the command can refuse full-acceptance (AS-IS reported it as passed)."""
    expected = {"scalars": {}, "tables": {}}
    computed = {"scalars": {}, "tables": {}}
    r = compare(expected, computed)
    assert r.deviations == []
    assert r.unmatched_columns == []
    assert r.ok is True  # no deviations/unmatched — looks green ...
    assert r.compared_anything is False  # ... but nothing was actually validated


# --------------------------------------------------------------------------- #
# 3. End-to-end command through fs_confine — the four mandated fixtures
# --------------------------------------------------------------------------- #

_KERNEL = (
    "def golden_master_outputs():\n"
    "    return {scalars_repr}\n"
)


def _make_run(tmp_path: Path, *, kernel_body: str, scalar_files=None, table_files=None):
    """Build repo_root/{{generated,info_from_excel}} with a synthetic kernel."""
    repo = tmp_path
    gen = repo / "generated"
    gen.mkdir()
    info = repo / "info_from_excel"
    info.mkdir()
    (gen / "test_run.py").write_text(kernel_body, encoding="utf-8")
    for name, content in (scalar_files or {}).items():
        (info / name).write_text(json.dumps(content), encoding="utf-8")
    for name, content in (table_files or {}).items():
        (info / name).write_text(content, encoding="utf-8")
    return repo, gen, info


def _invoke(repo, gen, info):
    result = gm_cmd.main(
        [
            "--repo-root", str(repo),
            "--generated-dir", str(gen),
            "--info-dir", str(info),
        ]
    )
    return result


def test_e2e_match_exits_0(tmp_path: Path):
    kernel = (
        "def golden_master_outputs():\n"
        "    return {\n"
        "        'scalars': {'Kalkulation': {'BJB': 4465.6547, 'ratzu': 0.05}},\n"
        "        'tables': {'Kalkulation': [{'Axn': 1.5}, {'Axn': 3.0}]},\n"
        "    }\n"
    )
    repo, gen, info = _make_run(
        tmp_path,
        kernel_body=kernel,
        scalar_files={"Kalkulation_scalar.json": {"BJB": 4465.6547, "ratzu": 0.05}},
        table_files={"Kalkulation_table_values.csv": "Axn\n1.5\n3.0\n"},
    )
    r = _invoke(repo, gen, info)
    assert r.exit_code == Exit.OK
    assert r.status == "passed"
    assert r.summary["scalars_tested"] == 2
    assert r.summary["table_cells_tested"] == 2
    assert r.summary["computed_output_hash"]


def test_e2e_mismatch_exits_30(tmp_path: Path):
    kernel = (
        "def golden_master_outputs():\n"
        "    return {'scalars': {'Kalkulation': {'BJB': 9999.0}}, 'tables': {}}\n"
    )
    repo, gen, info = _make_run(
        tmp_path,
        kernel_body=kernel,
        scalar_files={"Kalkulation_scalar.json": {"BJB": 4465.6547}},
    )
    r = _invoke(repo, gen, info)
    assert r.exit_code == Exit.GOLDEN_MASTER  # 30
    assert r.status == "failed"
    assert r.summary["deviation_count"] >= 1


def test_e2e_unmatched_column_exits_30(tmp_path: Path):
    """THE FIX: an expected column absent from generated output -> exit 30."""
    kernel = (
        "def golden_master_outputs():\n"
        "    return {'scalars': {}, 'tables': {'Kalkulation': [{'axn': 1.5}]}}\n"
    )
    repo, gen, info = _make_run(
        tmp_path,
        kernel_body=kernel,
        # Expected column 'Axn' (capital A) — generated only provides 'axn'.
        table_files={"Kalkulation_table_values.csv": "Axn\n1.5\n"},
    )
    r = _invoke(repo, gen, info)
    assert r.exit_code == Exit.GOLDEN_MASTER  # 30
    assert r.status == "failed"
    assert r.summary["unmatched_columns"] == ["Kalkulation:Axn"]
    assert any(e["code"] == "unmatched_expected_column" for e in r.errors)


def test_e2e_zero_comparison_not_accepted(tmp_path: Path):
    """THE FIX: a run with no expectations is human-review/coverage (exit 31),
    NOT a passed full golden-master."""
    kernel = (
        "def golden_master_outputs():\n"
        "    return {'scalars': {}, 'tables': {}}\n"
    )
    repo, gen, info = _make_run(tmp_path, kernel_body=kernel)  # no expectation files
    r = _invoke(repo, gen, info)
    assert r.exit_code == Exit.ALGEBRAIC  # 31 (human-review reason="coverage")
    assert r.status == "human_review_required"
    assert r.summary["compared_anything"] is False
    assert any(e["code"] == "zero_comparison" for e in r.errors)


def test_e2e_write_open_refused_by_g2_before_execution(tmp_path: Path):
    """Layered design: a kernel that attempts a write open() is caught by the
    static security gate (G2) and execution is REFUSED (exit 21), so the kernel is
    never run and no file is created. (Previously this reached G4 at runtime; the
    static gate now orders execution and stops it earlier.)"""
    kernel = (
        "def golden_master_outputs():\n"
        "    open('escaped.txt', 'w').write('boom')\n"
        "    return {'scalars': {}, 'tables': {}}\n"
    )
    repo, gen, info = _make_run(
        tmp_path,
        kernel_body=kernel,
        scalar_files={"Kalkulation_scalar.json": {"BJB": 1.0}},
    )
    r = _invoke(repo, gen, info)
    assert r.exit_code == Exit.SECURITY  # 21 — refused before execution
    assert r.status == "failed"
    assert any(e["code"] == "precondition_failed" for e in r.errors)
    assert not (gen / "escaped.txt").exists()


def test_e2e_g2_refuses_subprocess_import(tmp_path: Path):
    """A kernel importing subprocess fails G2; golden_master REFUSES to execute it
    (exit 21, precondition_failed) — it does not run unsafe code."""
    kernel = (
        "import subprocess\n"
        "def golden_master_outputs():\n"
        "    subprocess.run(['echo', 'hi'])\n"
        "    return {'scalars': {}, 'tables': {}}\n"
    )
    repo, gen, info = _make_run(
        tmp_path,
        kernel_body=kernel,
        scalar_files={"Kalkulation_scalar.json": {"BJB": 1.0}},
    )
    r = _invoke(repo, gen, info)
    assert r.exit_code == Exit.SECURITY  # 21
    assert r.status == "failed"
    assert any(e["code"] == "precondition_failed" for e in r.errors)
    assert r.summary["security_precondition"] == "failed"
    assert r.summary["security_violation_count"] >= 1


def test_e2e_g4_runtime_confinement_blocks_outside_read(tmp_path: Path):
    """G4 defense-in-depth at runtime: a kernel that passes G2 statically (a plain
    read open with a literal mode) but reads a path OUTSIDE the repo root is blocked
    by fs_confine at runtime. golden_master surfaces a confinement failure, not a
    pass, and the secret is never returned in the computed output."""
    repo, gen, info = _make_run(
        tmp_path,
        kernel_body="x = 0\n",  # placeholder, overwritten below
        scalar_files={"Kalkulation_scalar.json": {"BJB": 1.0}},
    )
    # A secret sibling OUTSIDE the repo root.
    secret = tmp_path.parent / f"{tmp_path.name}_secret.txt"
    secret.write_text("sk-ant-TOPSECRET", encoding="utf-8")
    # Read mode 'r' is statically allowed by G2 (path scope is a runtime concern),
    # so this kernel passes the static gate and reaches fs_confine.
    kernel = (
        "def golden_master_outputs():\n"
        f"    data = open({str(secret)!r}, 'r').read()\n"
        "    return {'scalars': {'Kalkulation': {'leak': data}}, 'tables': {}}\n"
    )
    (gen / "test_run.py").write_text(kernel, encoding="utf-8")
    try:
        r = _invoke(repo, gen, info)
        # fs_confine raised PermissionError inside the child -> no result envelope
        # -> confinement failure (exit 30), never a pass with the secret.
        assert r.exit_code == Exit.GOLDEN_MASTER
        assert r.status == "failed"
        assert "sk-ant-TOPSECRET" not in json.dumps(r.to_dict())
    finally:
        secret.unlink()


def test_e2e_ledger_written_on_pass(tmp_path: Path):
    """write_gate_ledger is invoked on the pass path; golden_master.gate.json is
    written into --diagnostics-dir and is loadable by the dossier loader."""
    from rechner_pipeline.orchestrate.dossier import load_gate_ledger

    kernel = (
        "def golden_master_outputs():\n"
        "    return {\n"
        "        'scalars': {'Kalkulation': {'BJB': 4465.6547}},\n"
        "        'tables': {},\n"
        "    }\n"
    )
    repo, gen, info = _make_run(
        tmp_path,
        kernel_body=kernel,
        scalar_files={"Kalkulation_scalar.json": {"BJB": 4465.6547}},
    )
    diag = repo / "diagnostics"
    r = gm_cmd.main(
        [
            "--repo-root", str(repo),
            "--generated-dir", str(gen),
            "--info-dir", str(info),
            "--diagnostics-dir", str(diag),
        ]
    )
    assert r.exit_code == Exit.OK
    ledger = diag / "golden_master.gate.json"
    assert ledger.is_file()
    entries, read_errors = load_gate_ledger(diag)
    assert read_errors == []
    assert any(e.command == "golden_master" and e.status == "passed" for e in entries)


def test_e2e_ledger_written_on_fail(tmp_path: Path):
    """write_gate_ledger is invoked on the fail path too (deviation -> exit 30)."""
    from rechner_pipeline.orchestrate.dossier import load_gate_ledger

    kernel = (
        "def golden_master_outputs():\n"
        "    return {'scalars': {'Kalkulation': {'BJB': 9999.0}}, 'tables': {}}\n"
    )
    repo, gen, info = _make_run(
        tmp_path,
        kernel_body=kernel,
        scalar_files={"Kalkulation_scalar.json": {"BJB": 4465.6547}},
    )
    diag = repo / "diagnostics"
    r = gm_cmd.main(
        [
            "--repo-root", str(repo),
            "--generated-dir", str(gen),
            "--info-dir", str(info),
            "--diagnostics-dir", str(diag),
        ]
    )
    assert r.exit_code == Exit.GOLDEN_MASTER
    ledger = diag / "golden_master.gate.json"
    assert ledger.is_file()
    entries, read_errors = load_gate_ledger(diag)
    assert read_errors == []
    assert any(e.command == "golden_master" and e.status == "failed" for e in entries)


def test_e2e_missing_callable_exits_30(tmp_path: Path):
    kernel = "def something_else():\n    return None\n"
    repo, gen, info = _make_run(
        tmp_path,
        kernel_body=kernel,
        scalar_files={"Kalkulation_scalar.json": {"BJB": 1.0}},
    )
    r = _invoke(repo, gen, info)
    assert r.exit_code == Exit.GOLDEN_MASTER
    assert r.status == "failed"
    assert any(e["code"] == "contract" for e in r.errors)
