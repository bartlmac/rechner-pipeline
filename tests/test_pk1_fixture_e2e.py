"""Pflicht-E2E fuer das versionierte, anonymisierte P-K1-/A-M4-Fixture.

Diese Tests duerfen nicht skippen: fehlt das Fixture oder weicht seine
Quellbindung ab, ist das ein harter Testfehler. Der positive Pfad und die
Negativpfade laufen auf einer pro Test frisch materialisierten Fallkopie.

Knoten: klv/tg2012
"""

from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

import pytest

import tests.e2e_fixture as fixture_mod
from tests.e2e_fixture import (
    O3_GENERATION,
    REPO_ROOT,
    bereite_pk1_fall,
    lade_pk1_fixture,
)
from rechner_pipeline.gates.generation_golden import main as pk1
from rechner_pipeline.quellen.formeln import pruefe_ratzu_staffeln
from rechner_pipeline.quellen.vorverdichtung import verzeichnis_der_generation
from rechner_pipeline.spez.validierung import spez_pfad


def _o3(fall: Path):
    return pk1([
        "--fall", str(fall),
        "--generation", O3_GENERATION,
        "--repo-root", str(REPO_ROOT),
    ])


def test_versioniertes_fixture_ist_vollstaendig_und_quellgebunden():
    fixture = lade_pk1_fixture()
    assert fixture.generation == O3_GENERATION
    assert fixture.quelle.is_file()
    assert fixture.quelle.parent == fixture_mod.FIXTURE_PFAD.parent
    assert len(fixture.quelle_sha256) == 64
    assert fixture.fall == "anonymisierter-pk1-am4-testfall"

    with ZipFile(fixture.quelle) as paket:
        kern_metadaten = ElementTree.fromstring(
            paket.read("docProps/core.xml")
        )
        arbeitsmappe = ElementTree.fromstring(paket.read("xl/workbook.xml"))
        beziehungen = [
            ElementTree.fromstring(paket.read(name))
            for name in paket.namelist()
            if name.endswith(".rels")
        ]

    assert kern_metadaten.find(
        "{http://schemas.openxmlformats.org/package/2006/metadata/"
        "core-properties}lastModifiedBy"
    ) is None
    assert not any(
        element.tag.endswith("}absPath") for element in arbeitsmappe.iter()
    )
    assert not any(
        beziehung.attrib.get("TargetMode") == "External"
        for wurzel in beziehungen
        for beziehung in wurzel
    )


def test_fehlendes_pflicht_fixture_ist_harter_fehler(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    fehlend = tmp_path / "fehlt.json"
    monkeypatch.setattr(fixture_mod, "FIXTURE_PFAD", fehlend)

    with pytest.raises(AssertionError, match="Pflicht-Fixture fehlt"):
        fixture_mod.lade_pk1_fixture()


def test_hashdrift_der_fixture_quelle_ist_harter_fehler(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    fixture_roh = json.loads(
        fixture_mod.FIXTURE_PFAD.read_text(encoding="utf-8")
    )
    quelle = tmp_path / "synthetische-quelle.xlsm"
    quelle.write_bytes(lade_pk1_fixture().quelle.read_bytes() + b"manipuliert")
    fixture_roh["quelle"]["datei"] = quelle.name
    fixture_pfad = tmp_path / "fixture.json"
    fixture_pfad.write_text(
        json.dumps(fixture_roh, sort_keys=True), encoding="utf-8"
    )
    monkeypatch.setattr(fixture_mod, "FIXTURE_PFAD", fixture_pfad)

    with pytest.raises(AssertionError, match="versionierten SHA-256"):
        fixture_mod.lade_pk1_fixture()


def test_ratzu_extraktion_des_fixtures_haelt_dem_rueckcheck_stand(
    tmp_path: Path,
):
    fall = bereite_pk1_fall(tmp_path)
    pruefung = pruefe_ratzu_staffeln(fall, O3_GENERATION)

    assert pruefung.status == "geprueft"
    assert pruefung.geprueft == 3
    assert pruefung.fehler == ()
    assert pruefung.befunde == ()
    assert pruefung.blatt == "Kalkulation"


def test_gate_pk1_blockt_ohne_verlaufswerte(tmp_path: Path):
    fall = bereite_pk1_fall(tmp_path)
    verlaufswerte = (
        verzeichnis_der_generation(fall, O3_GENERATION)
        / "Kalkulation_table_values.csv"
    )
    verlaufswerte.unlink()

    result = _o3(fall)

    assert result.exit_code == 30
    assert any("Golden Master" in fehler["message"] for fehler in result.errors)
    ledger = fall / "abgeleitet" / "diagnostics" / "generation_golden.gate.json"
    assert json.loads(ledger.read_text(encoding="utf-8"))["status"] == "failed"


def test_gate_pk1_blockt_manipulierte_spez(tmp_path: Path):
    fall = bereite_pk1_fall(tmp_path)
    pfad = spez_pfad(fall, O3_GENERATION)
    spez = json.loads(pfad.read_text(encoding="utf-8"))
    for zelle in spez["zellen"]:
        zelle["model_point"]["beta1"] = 0.031
    pfad.write_text(json.dumps(spez), encoding="utf-8")

    result = _o3(fall)

    assert result.exit_code == 30
    assert any(fehler["code"] == "spez_projektion" for fehler in result.errors)


def test_gate_pk1_mit_versioniertem_fixture_besteht(tmp_path: Path):
    fixture = lade_pk1_fixture()
    result = _o3(bereite_pk1_fall(tmp_path))

    assert result.exit_code == 0, result.errors
    assert result.summary["werte_verglichen"] == fixture.erwartung[
        "werte_verglichen"
    ]
    assert result.summary["tabellen_zeilen"] == fixture.erwartung[
        "tabellen_zeilen"
    ]
    assert result.summary["abweichungen"] == 0
    assert result.summary["modellpunkt"]["tafel"] == fixture.erwartung[
        "modellpunkt_tafel"
    ]
    assert result.summary["parameter_geprueft"] == fixture.erwartung[
        "parameter_geprueft"
    ]
    assert result.summary["erwartung_uebersprungen"] == fixture.erwartung[
        "erwartung_uebersprungen"
    ]
