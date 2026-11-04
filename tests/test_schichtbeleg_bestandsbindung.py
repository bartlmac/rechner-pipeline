"""A-020 H3, ADR-030 Stufe 2c: Der abgeleitete Schichtbeleg gehoert zum
Bestand des Laufs, das Ergebnis nennt die Bindung, die Vorlage A-M1
verlangt sie (5.0.0). Jede Regel mit Positivkontrolle; die drei Haken, mit
denen die Regeln im Erzeuger und in der Vorlage haengen, ueber den
gefahrenen Lauf (A-057, B2).

Knoten: klv
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

import pytest

from rechner_pipeline.gates import aktuartest, aktuartest_lauf
from tests.test_baldrian2_e2e import ABNAHMEN, REPO_ROOT, gefahrener_fall
from tests.test_verankerung_belegen import _wrapper_datei

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
    assert aktuartest.GATE_VERSION == "6.0.0"
    doku = (Path(__file__).resolve().parents[1] / "docs/architektur/gate-vertrag-und-versionen.md"
            ).read_text(encoding="utf-8")
    assert "| A-M-Vorlagen (Version `6.0.0`) |" in doku
    assert re.search(r"^- `5\.0\.0`: Ein Ergebnis mit Schichtbeleg nennt den Bestand", doku, re.M)
    assert re.search(r"^- `6\.0\.0`: Im Bestands-Scope verweigert der Lauf", doku, re.M)


# --------------------------------------------------------------------------- #
# Ueber den Lauf (A-057, B2): Die Regeln oben sind je Funktion gehalten; dass
# der Lauf sie ruft, zeigten bis hierher nur die Lektuere und die Fall-3-Probe.
# --------------------------------------------------------------------------- #


def _sha256(pfad: Path) -> str:
    return hashlib.sha256(pfad.read_bytes()).hexdigest()


def test_der_lauf_haelt_einen_echten_beleg_an_den_gebundenen_bestand(tmp_path: Path):
    """Haken 1: ``_schichten`` ruft die Bindungspruefung. Derselbe echte Beleg
    des Producers (Provenienz nachgerechnet) wird mit dem SHA-256 des eigenen
    Bestands angenommen und mit einem fremden verweigert."""
    fall = _wrapper_datei(tmp_path)
    name = "abgeleitet/schichten/verankerung_schichten.json"
    eigener = _sha256(fall / "abgeleitet" / "bestand" / "bestand.parquet")
    schichten = aktuartest_lauf._schichten(
        fall, name, repo_root=REPO_ROOT, bestand_sha256=eigener)
    assert "7000001" in schichten
    with pytest.raises(SystemExit, match="gehoert zu einem anderen Bestand"):
        aktuartest_lauf._schichten(
            fall, name, repo_root=REPO_ROOT, bestand_sha256="c" * 64)


def test_das_gefahrene_ergebnis_traegt_die_bestandsbindung(gefahrener_fall: Path):
    """Haken 2: ``fuehre_test`` schreibt den Block. Jedes Ergebnis der drei
    Abnahmen nennt den Schichtbeleg des Laufs, seine Art und den SHA-256 des
    mit ``--bestand`` gebundenen Bestands, der unter den Eingaben steht."""
    fall = gefahrener_fall
    sha = _sha256(fall / "abgeleitet" / "bestand" / "bestand.parquet")
    schichten = fall / "abgeleitet" / "schichten" / "verankerung_schichten.json"
    for abnahme, _ in ABNAHMEN:
        name = "aktuartest" if abnahme == "A-M1" else f"aktuartest-{abnahme}"
        ergebnis = json.loads(
            (fall / "abgeleitet" / "berichte" / f"{name}.json").read_text(encoding="utf-8"))
        assert ergebnis["schichtbeleg"] == {
            "name": str(schichten), "art": "abgeleitet", "bestand_sha256": sha}, abnahme
        assert sha in ergebnis["eingaben"].values(), abnahme


def test_die_vorlage_verweigert_das_gefahrene_ergebnis_ohne_bindung(
        gefahrener_fall: Path, tmp_path: Path):
    """Haken 3: ``aktuartest.main`` ruft ``schichtbeleg_gebunden``. Das
    gefahrene Ergebnis traegt die Vorlage (Positivkontrolle, mit Nachrechnung
    im Bestands-Scope); dasselbe Ergebnis ohne den Block endet mit "keine
    Bestandsbindung", bevor die Vorlage nachrechnet."""
    def vorlage(fall: Path):
        return aktuartest.main([
            "--fall", str(fall), "--abnahme", "A-M1", "--titel", "Stichtagstest",
            "--repo-root", str(REPO_ROOT)])

    getragen = vorlage(gefahrener_fall)
    assert getragen.exit_code == 0, getragen.errors
    kopie = tmp_path / "kopie"
    shutil.copytree(gefahrener_fall, kopie)
    pfad = kopie / "abgeleitet" / "berichte" / "aktuartest.json"
    ergebnis = json.loads(pfad.read_text(encoding="utf-8"))
    del ergebnis["schichtbeleg"]
    pfad.write_text(json.dumps(ergebnis, sort_keys=True), encoding="utf-8")
    verweigert = vorlage(kopie)
    assert verweigert.exit_code == 20, verweigert.errors
    assert any("keine Bestandsbindung" in e["message"] for e in verweigert.errors), verweigert.errors
