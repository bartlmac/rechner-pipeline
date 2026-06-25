from __future__ import annotations

import json
from pathlib import Path

from rechner_pipeline.orchestrate.runner import PipelineOptions, PipelineRunner
from rechner_pipeline.qa.golden_master import _norm_colname, compare


def test_norm_colname_separators_but_case_sensitive():
    assert _norm_colname("A_xn") == _norm_colname("Axn")        # Trennzeichen egal
    assert _norm_colname("a xn") == _norm_colname("axn")
    assert _norm_colname("Axn") != _norm_colname("axn")          # Case zählt


def _expected(scalars=None, header=None, rows=None):
    return {
        "scalars": {"Kalkulation": scalars or {}},
        "tables": {"Kalkulation": (header or [], rows or [])},
    }


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


def test_compare_column_case_mismatch_is_unmatched_and_fails():
    # Erwartet 'Axn', berechnet nur 'axn' -> case-verschieden -> nicht zugeordnet.
    # Die Spalte traegt Daten, daher ist das eine Abweichung (nicht stillschweigend ok).
    expected = _expected(header=["Axn"], rows=[{"Axn": "1.5"}])
    computed = {"scalars": {}, "tables": {"Kalkulation": [{"axn": 1.5}]}}
    r = compare(expected, computed)
    assert r.table_cells_tested == 0
    assert "Kalkulation:Axn" in r.unmatched_columns
    assert not r.ok  # erwartete Spalte mit Daten nicht zugeordnet -> Fehlschlag


def test_compare_unmatched_column_with_data_fails():
    # Schadensfall: erwartete Tabellenspalte mit echten Werten wird vom Rechenkern
    # gar nicht geliefert -> darf NICHT als bestanden gelten.
    expected = _expected(header=["Axn"], rows=[{"Axn": "1.5"}, {"Axn": "3.0"}])
    computed = {"scalars": {}, "tables": {"Kalkulation": [{"foo": 9.9}, {"foo": 8.8}]}}
    r = compare(expected, computed)
    assert not r.ok
    assert "Kalkulation:Axn" in r.unmatched_columns
    assert r.table_cells_tested == 0


def test_compare_unmatched_empty_column_stays_ok():
    # Eine nicht zugeordnete Spalte OHNE Daten kippt ok nicht (col_has_data-Guard).
    expected = _expected(header=["Ghost"], rows=[{"Ghost": ""}, {"Ghost": ""}])
    computed = {"scalars": {}, "tables": {"Kalkulation": [{"axn": 1.5}, {"axn": 2.5}]}}
    r = compare(expected, computed)
    assert r.ok
    assert r.unmatched_columns == []


def test_compare_4decimal_rounding_tolerance():
    expected = _expected(scalars={"x": 1.23456})
    # 1.234561 rundet auf 1.2346 == round(1.23456,4) -> gleich
    computed = {"scalars": {"Kalkulation": {"x": 1.234561}}, "tables": {}}
    assert compare(expected, computed).ok
    # 1.23446 rundet auf 1.2345 != 1.2346 -> Abweichung
    computed2 = {"scalars": {"Kalkulation": {"x": 1.23446}}, "tables": {}}
    assert not compare(expected, computed2).ok


def _fixed_options() -> PipelineOptions:
    return PipelineOptions(
        model="x", skip_export=True, skip_main_llm=True, skip_test_llm=True,
        skip_compare_run=False, main_max_chars_per_file=1, main_max_total_chars=1,
        test_max_chars_per_file=1, test_max_total_chars=1, reasoning_effort="low",
        test_mode="fixed",
    )


def test_run_compare_fixed_mode_end_to_end(tmp_path: Path):
    """Integration: run_compare(fixed) führt den festen Harness via fs_confine
    aus, importiert den Contract aus generated/test_run.py und vergleicht gegen
    info_from_excel/ — ohne LLM-generierten Test."""
    gen = tmp_path / "generated"
    gen.mkdir()
    info = tmp_path / "info_from_excel"
    info.mkdir()
    (info / "Kalkulation_scalar.json").write_text(
        json.dumps({"BJB": 4465.6547, "ratzu": 0.05}), encoding="utf-8"
    )
    (gen / "test_run.py").write_text(
        "def golden_master_outputs():\n"
        "    return {'scalars': {'Kalkulation': {'BJB': 4465.6547, 'ratzu': 0.05}},\n"
        "            'tables': {}}\n",
        encoding="utf-8",
    )

    runner = PipelineRunner(repo_root=tmp_path, options=_fixed_options())
    runner.run_compare()  # darf nicht werfen

    res = json.loads(runner.compare_result_path.read_text(encoding="utf-8"))
    assert res["status"] == "passed"
    assert res["returncode"] == 0
    assert "BESTANDEN" in res["stdout"]


def test_run_compare_fixed_mode_detects_deviation(tmp_path: Path):
    gen = tmp_path / "generated"
    gen.mkdir()
    info = tmp_path / "info_from_excel"
    info.mkdir()
    (info / "Kalkulation_scalar.json").write_text(
        json.dumps({"BJB": 4465.6547}), encoding="utf-8"
    )
    (gen / "test_run.py").write_text(
        "def golden_master_outputs():\n"
        "    return {'scalars': {'Kalkulation': {'BJB': 9999.0}}, 'tables': {}}\n",
        encoding="utf-8",
    )

    runner = PipelineRunner(repo_root=tmp_path, options=_fixed_options())
    try:
        runner.run_compare()
    except RuntimeError:
        pass  # Abweichung -> returncode != 0 -> RuntimeError ok
    res = json.loads(runner.compare_result_path.read_text(encoding="utf-8"))
    assert res["status"] == "failed"


def test_run_compare_fixed_mode_blocks_unsafe_contract_before_execution(tmp_path: Path):
    """Auch im fixed-Modus muss unsicherer generierter Contract VOR der Ausführung
    geblockt werden (der Harness importiert generated/test_run.py)."""
    import pytest

    gen = tmp_path / "generated"
    gen.mkdir()
    info = tmp_path / "info_from_excel"
    info.mkdir()
    (info / "Kalkulation_scalar.json").write_text(
        json.dumps({"BJB": 4465.6547}), encoding="utf-8"
    )
    marker = tmp_path / "MARKER"
    (gen / "test_run.py").write_text(
        "import os\n"
        f"os.system('touch {marker}')\n"
        "def golden_master_outputs():\n"
        "    return {'scalars': {'Kalkulation': {'BJB': 4465.6547}}, 'tables': {}}\n",
        encoding="utf-8",
    )

    runner = PipelineRunner(repo_root=tmp_path, options=_fixed_options())
    with pytest.raises(RuntimeError, match="Static security check blocked"):
        runner.run_compare()

    assert not marker.exists()  # Code wurde nicht ausgeführt
    assert not runner.compare_result_path.exists()  # kein Compare gelaufen
    report = json.loads(runner.static_security_report_path.read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert any(v["symbol"] == "os.system" for v in report["violations"])


def test_run_compare_fixed_mode_missing_contract_raises(tmp_path: Path):
    """Fehlt generated/test_run.py, wirft run_compare(fixed) eine klare
    FileNotFoundError statt eines undurchsichtigen Import-Fehlers im Subprozess."""
    import pytest

    (tmp_path / "generated").mkdir()
    info = tmp_path / "info_from_excel"
    info.mkdir()
    (info / "Kalkulation_scalar.json").write_text(
        json.dumps({"BJB": 4465.6547}), encoding="utf-8"
    )

    runner = PipelineRunner(repo_root=tmp_path, options=_fixed_options())
    with pytest.raises(FileNotFoundError, match="test_run.py"):
        runner.run_compare()
