"""A-020 H3, ADR-030 Stufe 2c: Der abgeleitete Schichtbeleg gehoert zum
Bestand des Laufs, das Ergebnis nennt die Bindung, die Vorlage A-M1
verlangt sie (5.0.0). Jede Regel mit Positivkontrolle.

Knoten: klv
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from rechner_pipeline.gates import aktuartest, aktuartest_lauf

SHA_A = "a" * 64
SHA_B = "b" * 64


def test_der_lauf_verweigert_einen_schichtbeleg_eines_anderen_bestands():
    prov = {"eingaben": {"abgeleitet/bestand/bestand.parquet": SHA_A, "x.json": SHA_B}}
    aktuartest_lauf._pruefe_bestandsbindung("s.json", prov, SHA_A)       # eigener Bestand
    with pytest.raises(SystemExit, match="gehoert zu einem anderen Bestand"):
        aktuartest_lauf._pruefe_bestandsbindung("s.json", prov, "c" * 64)
    with pytest.raises(SystemExit, match="gehoert zu einem anderen Bestand"):
        aktuartest_lauf._pruefe_bestandsbindung("s.json", {}, SHA_A)


def test_die_art_des_schichtbelegs(tmp_path: Path):
    fall = tmp_path / "fall"
    (fall / "abgeleitet").mkdir(parents=True)
    (fall / "abgeleitet" / "s.json").write_text("{}", encoding="utf-8")
    assert aktuartest_lauf.schichtbeleg_art(fall, None) is None
    assert aktuartest_lauf.schichtbeleg_art(fall, "abgeleitet/s.json") == "abgeleitet"
    assert aktuartest_lauf.schichtbeleg_art(fall, str(fall / "abgeleitet" / "s.json")) == "abgeleitet"
    assert aktuartest_lauf.schichtbeleg_art(fall, "schichten.json") == "registriert"


def _ergebnis(**aenderung):
    test = {"aufruf": ["--bestand", "b.parquet", "--schicht", "abgeleitet/s.json"],
            "eingaben": {"b.parquet": SHA_A, "spez.json": SHA_B},
            "schichtbeleg": {"name": "abgeleitet/s.json", "art": "abgeleitet",
                             "bestand_sha256": SHA_A}}
    test.update(aenderung)
    return test


def test_die_vorlage_verlangt_die_bestandsbindung():
    assert aktuartest.schichtbeleg_gebunden(_ergebnis()) == []
    assert aktuartest.schichtbeleg_gebunden(
        {"aufruf": ["--bestand", "b.parquet"], "eingaben": {}, "schichtbeleg": None}) == []
    ohne = aktuartest.schichtbeleg_gebunden(_ergebnis(schichtbeleg=None))
    assert ohne and "keine Bestandsbindung" in ohne[0]
    alt = aktuartest.schichtbeleg_gebunden({k: v for k, v in _ergebnis().items() if k != "schichtbeleg"})
    assert alt and "keine Bestandsbindung" in alt[0]
    fremd = aktuartest.schichtbeleg_gebunden(_ergebnis(
        schichtbeleg={"name": "abgeleitet/s.json", "art": "abgeleitet", "bestand_sha256": "c" * 64}))
    assert fremd and "keinen Bestand, den dieses Ergebnis gebunden hat" in fremd[0]
    unvollstaendig = aktuartest.schichtbeleg_gebunden(_ergebnis(
        schichtbeleg={"name": "", "art": "abgeleitet", "bestand_sha256": SHA_A}))
    assert unvollstaendig and "unvollstaendig" in unvollstaendig[0]
    assert aktuartest.schichtbeleg_gebunden(_ergebnis(
        schichtbeleg={"name": "s", "art": "woanders", "bestand_sha256": SHA_A}))


def test_die_version_der_vorlage_und_ihr_grund():
    assert aktuartest.GATE_VERSION == "5.0.0"
    doku = (Path(__file__).resolve().parents[1] / "docs/architektur/gate-vertrag-und-versionen.md"
            ).read_text(encoding="utf-8")
    assert "| A-M-Vorlagen (Version `5.0.0`) |" in doku
    assert re.search(r"^- `5\.0\.0`: Ein Ergebnis mit Schichtbeleg nennt den Bestand", doku, re.M)
