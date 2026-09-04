"""Knoten: system/assurance
"""

from __future__ import annotations

import csv
import errno
import json
import os
from pathlib import Path, PureWindowsPath

import pytest

from rechner_pipeline.quellen.extract.excel import (
    ExportArtifactTargetError,
    export_excel_infos,
    sheet_artifact_filenames,
)
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


def test_sheet_artifact_names_cover_portable_and_derived_collisions():
    assert sheet_artifact_filenames(
        [
            "Tarif",
            "tarif",
            "é",
            "e\u0301",
            "Tarif_table_values",
            "names_manager",
            "intern_compressed_name",
        ]
    ) == [
        "Tarif.csv",
        "tarif__2.csv",
        "é.csv",
        "e\u0301__2.csv",
        "Tarif_table_values__2.csv",
        "names_manager__2.csv",
        "intern_compressed_name.csv",
    ]
    assert sheet_artifact_filenames(
        [
            "intern_compressed",
            "intern_table_values",
            "intern_address_values",
            "intern_compressed_name",
        ]
    ) == [
        "intern_compressed__2.csv",
        "intern_table_values__2.csv",
        "intern_address_values__2.csv",
        "intern_compressed_name.csv",
    ]

    windows_reserved = sheet_artifact_filenames(
        ["CON", "CON.txt", "AUX", "NUL", "COM1", "LPT9"]
    )
    def is_reserved(name: str) -> bool:
        pruefer = getattr(os.path, "isreserved", None)
        return (
            bool(pruefer(name))
            if pruefer is not None
            else PureWindowsPath(name).is_reserved()
        )

    assert not any(is_reserved(name) for name in windows_reserved)
    assert len(windows_reserved) == len(
        {name.casefold() for name in windows_reserved}
    )


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
    with csvs[0].open(encoding="utf-8") as f:
        rows = list(csv.reader(f, delimiter=";"))
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


def test_colliding_cleaned_sheet_names_get_distinct_manifest_bound_artifacts(
    tmp_path: Path,
):
    openpyxl = pytest.importorskip("openpyxl")
    pytest.importorskip("oletools")
    pytest.importorskip("pandas")

    xlsx = tmp_path / "colliding.xlsx"
    wb = openpyxl.Workbook()
    first = wb.active
    first.title = "Tarif<Alt"
    first["A1"] = "first"
    second = wb.create_sheet("Tarif>Alt")
    second["A1"] = "second"
    wb.save(xlsx)

    out_dir = tmp_path / "out"
    manifest = export_excel_infos(xlsx, out_dir, backend="openpyxl")

    expected_binding = [
        {"original_name": "Tarif<Alt", "file_name": "Tarif_Alt.csv"},
        {"original_name": "Tarif>Alt", "file_name": "Tarif_Alt__2.csv"},
    ]
    assert manifest["sheet_artifacts"] == expected_binding
    persisted = json.loads(
        (out_dir / "export_manifest.json").read_text(encoding="utf-8")
    )
    assert persisted["sheet_artifacts"] == expected_binding

    with (out_dir / "Tarif_Alt.csv").open(encoding="utf-8", newline="") as f:
        first_rows = list(csv.reader(f, delimiter=";"))
    with (out_dir / "Tarif_Alt__2.csv").open(
        encoding="utf-8", newline=""
    ) as f:
        second_rows = list(csv.reader(f, delimiter=";"))
    assert first_rows[1] == ["Tarif<Alt", "$A$1", "first", "first"]
    assert second_rows[1] == ["Tarif>Alt", "$A$1", "second", "second"]


def test_derived_artifact_cannot_overwrite_another_sheet_csv(tmp_path: Path):
    openpyxl = pytest.importorskip("openpyxl")
    pytest.importorskip("oletools")
    pytest.importorskip("pandas")

    xlsx = tmp_path / "derived-collision.xlsx"
    wb = openpyxl.Workbook()
    first = wb.active
    first.title = "Tarif"
    first["A1"] = "label"
    first["B1"] = "=1+1"
    second = wb.create_sheet("Tarif_table_values")
    second["A1"] = "SECOND-SHEET-MARKER"
    wb.save(xlsx)

    out_dir = tmp_path / "out"
    manifest = export_excel_infos(xlsx, out_dir, backend="openpyxl")

    assert manifest["sheet_artifacts"] == [
        {"original_name": "Tarif", "file_name": "Tarif.csv"},
        {
            "original_name": "Tarif_table_values",
            "file_name": "Tarif_table_values__2.csv",
        },
    ]
    with (out_dir / "Tarif_table_values__2.csv").open(
        encoding="utf-8", newline=""
    ) as f:
        rows = list(csv.reader(f, delimiter=";"))
    assert rows[1] == [
        "Tarif_table_values",
        "$A$1",
        "SECOND-SHEET-MARKER",
        "SECOND-SHEET-MARKER",
    ]


def test_names_manager_sheet_cannot_collide_with_special_export(tmp_path: Path):
    openpyxl = pytest.importorskip("openpyxl")
    pytest.importorskip("oletools")
    pytest.importorskip("pandas")

    xlsx = tmp_path / "names-manager-collision.xlsx"
    wb = openpyxl.Workbook()
    sheet = wb.active
    sheet.title = "names_manager"
    sheet["A1"] = "SHEET-MARKER"
    wb.defined_names.add(
        openpyxl.workbook.defined_name.DefinedName(
            "meinWert",
            attr_text="names_manager!$A$1",
        )
    )
    wb.save(xlsx)

    out_dir = tmp_path / "out"
    manifest = export_excel_infos(xlsx, out_dir, backend="openpyxl")

    assert manifest["sheet_artifacts"] == [
        {"original_name": "names_manager", "file_name": "names_manager__2.csv"}
    ]
    with (out_dir / "names_manager__2.csv").open(
        encoding="utf-8", newline=""
    ) as f:
        sheet_rows = list(csv.reader(f, delimiter=";"))
    with (out_dir / "names_manager.csv").open(encoding="utf-8", newline="") as f:
        manager_rows = list(csv.reader(f, delimiter=";"))
    assert sheet_rows[1][0] == "names_manager"
    assert sheet_rows[1][3] == "SHEET-MARKER"
    assert manager_rows[0][0] == "Name"


@pytest.mark.parametrize("link_art", ["symlink", "hardlink"])
def test_sheet_export_rejects_preexisting_link_aliases_before_writing(
    tmp_path: Path,
    link_art: str,
):
    openpyxl = pytest.importorskip("openpyxl")
    from rechner_pipeline.quellen.extract.openpyxl_backend import export_all_sheets

    xlsx = tmp_path / "links.xlsx"
    wb = openpyxl.Workbook()
    first = wb.active
    first.title = "Tarif<Alt"
    first["A1"] = "first"
    second = wb.create_sheet("Tarif>Alt")
    second["A1"] = "second"
    wb.save(xlsx)
    wbf, wbv = _load_pair(xlsx)

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    victim = tmp_path / "victim.csv"
    victim.write_text("UNCHANGED", encoding="utf-8")
    targets = [out_dir / "Tarif_Alt.csv", out_dir / "Tarif_Alt__2.csv"]
    try:
        for target in targets:
            if link_art == "symlink":
                target.symlink_to(victim)
            else:
                target.hardlink_to(victim)
    except OSError as exc:
        pytest.skip(f"{link_art} is unavailable on this filesystem: {exc}")

    with pytest.raises(ExportArtifactTargetError, match=link_art):
        export_all_sheets(wbf, wbv, out_dir)

    assert victim.read_text(encoding="utf-8") == "UNCHANGED"


def test_sheet_export_does_not_follow_symlink_inserted_after_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    openpyxl = pytest.importorskip("openpyxl")
    from rechner_pipeline.quellen.extract import openpyxl_backend

    xlsx = tmp_path / "race.xlsx"
    wb = openpyxl.Workbook()
    first = wb.active
    first.title = "Tarif<Alt"
    first["A1"] = "first"
    second = wb.create_sheet("Tarif>Alt")
    second["A1"] = "second"
    wb.save(xlsx)
    wbf, wbv = _load_pair(xlsx)

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    victim = tmp_path / "victim.csv"
    victim.write_text("UNCHANGED", encoding="utf-8")
    second_target = out_dir / "Tarif_Alt__2.csv"
    real_preflight = openpyxl_backend._ensure_safe_artifact_targets

    def preflight_then_insert_symlink(path: Path, filenames) -> None:
        real_preflight(path, filenames)
        try:
            second_target.symlink_to(victim)
        except OSError as exc:
            nicht_verfuegbar = (
                getattr(exc, "winerror", None) in {5, 1314}
                or exc.errno in {
                    errno.EACCES,
                    errno.EPERM,
                    getattr(errno, "ENOTSUP", -1),
                    getattr(errno, "EOPNOTSUPP", -1),
                }
            )
            if nicht_verfuegbar:
                pytest.skip(
                    "Symlinks sind auf diesem Dateisystem nicht verfuegbar: "
                    f"{exc}"
                )
            raise

    monkeypatch.setattr(
        openpyxl_backend,
        "_ensure_safe_artifact_targets",
        preflight_then_insert_symlink,
    )

    exported = openpyxl_backend.export_all_sheets(wbf, wbv, out_dir)

    assert victim.read_text(encoding="utf-8") == "UNCHANGED"
    assert not second_target.is_symlink()
    with second_target.open(encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f, delimiter=";"))
    assert rows[1] == ["Tarif>Alt", "$A$1", "second", "second"]
    assert exported[1] == second_target


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

    with nm_csv.open(encoding="utf-8") as f:
        rows = list(csv.reader(f, delimiter=";"))
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

    example = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "Tarifrechner_KLV_TG2012.xlsm"
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
