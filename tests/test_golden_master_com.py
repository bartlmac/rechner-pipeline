from __future__ import annotations

from pathlib import Path

import pytest

from rechner_pipeline.qa.extraction_diff import (
    DiffReport,
    FileDiff,
    _close_precision,
    compare_dirs,
    tokens_equal,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "golden_master_com"
EXAMPLE = REPO_ROOT / "examples" / "Tarifrechner_KLV.xlsm"


# --- Pure-Logik (ohne optionale Deps) --------------------------------------


def test_tokens_equal_numeric_format():
    assert tokens_equal("0", "0.0")
    assert tokens_equal("24", "24.0")
    assert tokens_equal("0.025", "0.0250000")
    assert not tokens_equal("0.025", "0.026")
    assert tokens_equal("Text", "Text")
    assert not tokens_equal("=A1", "=A2")


def test_close_precision_accepts_4dp_rounding():
    # COM rundet auf 4 Dezimalen; openpyxl volle Praezision -> gleiche Zahl.
    assert _close_precision("-2232.8274", "-2232.8273513462004")
    assert _close_precision("34562.665", "34562.66495146083")
    # Echte Abweichung bleibt materiell.
    assert not _close_precision("100.0", "101.0")


def test_diffreport_material_gate():
    fd = FileDiff("x", material=["m"], accepted=["a"], cosmetic=["c"])
    rep = DiffReport(files=[fd])
    assert rep.has_material_differences()
    assert rep.material_count() == 1 and rep.accepted_count() == 1
    fd2 = FileDiff("y", accepted=["a"], cosmetic=["c"])
    assert not DiffReport(files=[fd2]).has_material_differences()


# --- Golden-Master gegen COM-Fixture (openpyxl + oletools) -----------------


def test_openpyxl_matches_com_golden_master(tmp_path: Path):
    pytest.importorskip("openpyxl")
    pytest.importorskip("oletools")
    if not (FIXTURE / "Kalkulation.csv").exists():
        pytest.skip("COM-Golden-Master-Fixture nicht vorhanden")
    if not EXAMPLE.exists():
        pytest.skip("Beispiel-Workbook nicht vorhanden")

    from rechner_pipeline.extract.openpyxl_backend import export_raw

    warnings: list = []
    export_raw(EXAMPLE, tmp_path, warnings)
    assert warnings == []

    report = compare_dirs(FIXTURE, tmp_path)
    # Akzeptierte Diffs (Praezision, Range-/interne Namen) sind erlaubt;
    # es darf KEINE unerwarteten materiellen Unterschiede geben.
    assert not report.has_material_differences(), "\n" + report.render()
