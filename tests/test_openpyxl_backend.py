"""Knoten: system/assurance
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from rechner_pipeline.quellen.extract.excel import export_excel_infos
from rechner_pipeline.quellen.extract.openpyxl_backend import _strip_vba_attribute_lines


# --- Pure-Logik (ohne optionale Deps) --------------------------------------


def test_strip_vba_attribute_lines_removes_only_attribute_headers():
    code = (
        'Attribute VB_Name = "mGWerte"\n'
        "Attribute VB_GlobalNameSpace = False\n"
        "Sub Foo()\n"
        "    x = 1\n"
        "End Sub\n"
    )
    body = _strip_vba_attribute_lines(code)
    assert "Attribute VB_" not in body
    assert "Sub Foo()" in body
    assert "    x = 1" in body


def test_strip_vba_attribute_lines_empty_for_attribute_only_module():
    code = (
        'Attribute VB_Name = "Tabelle1"\n'
        "Attribute VB_Base = \"0{...}\"\n"
    )
    assert _strip_vba_attribute_lines(code).strip() == ""


def test_export_excel_infos_unknown_backend_raises(tmp_path: Path):
    # Datei muss existieren, damit der Backend-Check (nicht der Existenz-Check) greift.
    fake = tmp_path / "x.xlsm"
    fake.write_bytes(b"not really excel")
    with pytest.raises(ValueError, match="Unknown export backend"):
        export_excel_infos(fake, tmp_path / "out", backend="gnumeric")


# --- openpyxl-abhaengig ----------------------------------------------------


def _make_workbook(path: Path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Blatt1"
    ws["A1"] = "Label"          # Literal-Text
    ws["B1"] = 5                # Literal-Zahl
    ws["B2"] = "=B1+1"          # Formel (kein gecachter Wert in frischem WB)
    ws["A2"] = None             # leere Zelle -> nicht im CSV
    # Defined name auf eine einzelne Zelle (fuer ValueEvaluated-Aufloesung)
    openpyxl.workbook.defined_name.DefinedName  # noqa: B018  (API vorhanden?)
    wb.defined_names.add(
        openpyxl.workbook.defined_name.DefinedName("meinWert", attr_text="Blatt1!$B$1")
    )
    wb.save(path)


def _load_pair(path: Path):
    openpyxl = pytest.importorskip("openpyxl")
    wbf = openpyxl.load_workbook(path, data_only=False)
    wbv = openpyxl.load_workbook(path, data_only=True)
    return wbf, wbv


def test_export_all_sheets_csv_schema(tmp_path: Path):
    openpyxl = pytest.importorskip("openpyxl")
    from rechner_pipeline.quellen.extract.openpyxl_backend import export_all_sheets

    xlsx = tmp_path / "wb.xlsx"
    _make_workbook(xlsx)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    wbf, wbv = _load_pair(xlsx)
    csvs = export_all_sheets(wbf, wbv, out_dir)

    assert len(csvs) == 1
    rows = list(csv.reader(csvs[0].open(encoding="utf-8"), delimiter=";"))
    assert rows[0] == ["Blatt", "Adresse", "Formel", "Wert"]

    by_addr = {r[1]: r for r in rows[1:]}
    # Adressen in absoluter $-Form (wie COM), Literale: Formel == Wert
    assert by_addr["$A$1"] == ["Blatt1", "$A$1", "Label", "Label"]
    assert by_addr["$B$1"] == ["Blatt1", "$B$1", "5", "5"]
    # Formelzelle: Formel beginnt mit '='
    assert by_addr["$B$2"][2] == "=B1+1"
    # Leere Zelle nicht enthalten
    assert "$A$2" not in by_addr


def test_export_warns_on_formula_without_cached_value(tmp_path: Path):
    openpyxl = pytest.importorskip("openpyxl")
    from rechner_pipeline.quellen.extract.openpyxl_backend import export_all_sheets

    xlsx = tmp_path / "wb.xlsx"
    _make_workbook(xlsx)  # B2 = "=B1+1" ohne gecachten Wert (frisches WB)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    wbf, wbv = _load_pair(xlsx)
    warnings: list = []
    csvs = export_all_sheets(wbf, wbv, out_dir, warnings=warnings)

    assert len(csvs) == 1  # Rückgabetyp bleibt List[Path]
    assert len(warnings) == 1
    w = warnings[0]
    assert w["code"] == "export.formula_cache_missing"
    assert w["strict_error"] is True
    assert w["details"]["total"] >= 1
    assert "Blatt1" in w["details"]["sheets"]


def test_no_cache_warning_when_no_formulas(tmp_path: Path):
    openpyxl = pytest.importorskip("openpyxl")
    from rechner_pipeline.quellen.extract.openpyxl_backend import export_all_sheets

    xlsx = tmp_path / "literals.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Blatt1"
    ws["A1"] = "Label"
    ws["B1"] = 5
    wb.save(xlsx)

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    wbf, wbv = _load_pair(xlsx)
    warnings: list = []
    export_all_sheets(wbf, wbv, out_dir, warnings=warnings)

    assert warnings == []  # nur Literale -> keine Formel-ohne-Cache-Warnung


def test_export_name_manager_resolves_single_cell_value(tmp_path: Path):
    pytest.importorskip("openpyxl")
    from rechner_pipeline.quellen.extract.openpyxl_backend import export_name_manager_to_csv

    xlsx = tmp_path / "wb.xlsx"
    _make_workbook(xlsx)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    wbf, wbv = _load_pair(xlsx)
    nm_csv = export_name_manager_to_csv(wbf, wbv, out_dir)
    assert nm_csv is not None

    rows = list(csv.reader(nm_csv.open(encoding="utf-8"), delimiter=";"))
    header = rows[0]
    assert header[0] == "Name" and header[6] == "ValueEvaluated"
    by_name = {r[0]: dict(zip(header, r)) for r in rows[1:]}
    assert "meinWert" in by_name
    assert by_name["meinWert"]["RefersTo"] == "Blatt1!$B$1"
    # B1 == 5 -> ValueEvaluated aufgeloest
    assert by_name["meinWert"]["ValueEvaluated"] == "5"


# --- Integration gegen die Beispieldatei (openpyxl + oletools) -------------


def test_export_raw_against_example_workbook(tmp_path: Path):
    pytest.importorskip("openpyxl")
    pytest.importorskip("oletools")
    from rechner_pipeline.quellen.extract.openpyxl_backend import export_raw

    example = Path(__file__).resolve().parents[1] / "examples" / "Tarifrechner_KLV_TG2012.xlsm"
    if not example.exists():
        pytest.skip("Beispiel-Workbook nicht vorhanden")

    warnings: list = []
    sheet_csvs, vba_txts, nm_csv = export_raw(example, tmp_path, warnings)

    sheet_names = {p.stem for p in sheet_csvs}
    assert {"Kalkulation", "Tafeln"}.issubset(sheet_names)
    # Die drei Logik-Module mit Code, Klassen-Stubs ohne Code fehlen
    vba_names = {p.stem for p in vba_txts}
    assert {"mGWerte", "mBarwerte", "mConstants"}.issubset(vba_names)
    assert nm_csv is not None and nm_csv.exists()
    assert warnings == []
