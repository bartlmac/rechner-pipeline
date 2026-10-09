"""Der Bericht der Migrationsabnahme verweist relativ zu sich selbst (10.1.0).

Bis 10.0.0 standen die Verweise auf die Bestandsberichte fallrelativ im
Bericht (``abgeleitet/berichte/bestandsbericht-vor.html``). Ein Browser loest
sie vom Ordner des Berichts aus auf und landet im Leeren: zwei tote Verweise
im gezeichneten Bericht von Fall 3.

Was hier gehalten wird:

* Mit ``bericht_ort`` zeigt der Verweis relativ zum Bericht; der sichtbare
  Text bleibt der gebundene, fallrelative Pfad.
* Ohne ``bericht_ort`` rendert der Bericht wie bisher, und nur die zwei
  Verweise unterscheiden die Fassungen: Ein frueher gezeichneter Bericht
  bleibt bytegleich reproduzierbar.
* Die Nachrechnung glaubt dem Feld nicht: Ein ``bericht_ort``, der nicht der
  Ort des Berichts ist, ist ein Befund, ein unbekanntes Feld ebenso.

Knoten: system/gates
"""

from __future__ import annotations

from pathlib import Path

from rechner_pipeline.gates import abnahmebericht as ab
from tests.test_abnahmebericht import _bericht_artefakte, _pruefung, _vollstaendige_suite

VOR = "abgeleitet/berichte/bestandsbericht-vor.html"
NACH = "abgeleitet/berichte/bestandsbericht-nach.html"
ORT = "abgeleitet/berichte/migrationsabnahme.html"


def _bericht(**mehr) -> str:
    args = dict(titel="t", stichtag_1="s1", stichtag_2="s2",
                suite=_vollstaendige_suite(_pruefung("P-1")), **_bericht_artefakte())
    args.update(bestandsbericht_vor=VOR, bestandsbericht_nach=NACH, **mehr)
    return ab.baue_bericht(**args)


def test_mit_bericht_ort_zeigen_die_verweise_relativ_zum_bericht():
    text = _bericht(bericht_ort=ORT)
    assert f"href='bestandsbericht-vor.html'>{VOR}</a>" in text
    assert f"href='bestandsbericht-nach.html'>{NACH}</a>" in text
    assert f"href='{VOR}'" not in text and f"href='{NACH}'" not in text


def test_ohne_bericht_ort_rendert_der_bericht_wie_bisher():
    alt = _bericht()
    assert f"href='{VOR}'>{VOR}</a>" in alt and f"href='{NACH}'>{NACH}</a>" in alt
    neu = _bericht(bericht_ort=ORT)
    assert alt.replace(f"href='{VOR}'", "href='bestandsbericht-vor.html'").replace(
        f"href='{NACH}'", "href='bestandsbericht-nach.html'") == neu


def _erzeugung(**mehr) -> dict:
    return ab._bericht_erzeugung(
        titel="t", stichtag_1="s1", stichtag_2="s2", spec_roh=None,
        transformation_ergebnis=None, bestandsbericht_vor=VOR, bestandsbericht_nach=NACH,
        **mehr)


def _fehler(tmp_path: Path, erzeugung: dict) -> list:
    fall = tmp_path / "fall"
    bericht = fall / ORT
    bericht.parent.mkdir(parents=True, exist_ok=True)
    bericht.write_text("x", encoding="utf-8")
    return ab._bericht_fehler(
        erzeugung=erzeugung, suite=_vollstaendige_suite(_pruefung("P-1")),
        bericht_pfad=bericht, erwartete_stichtage=["s1", "s2"], fall=fall)


def test_die_nachrechnung_glaubt_dem_ort_nicht(tmp_path):
    assert not [f for f in _fehler(tmp_path, _erzeugung(bericht_ort=ORT)) if "bericht_ort" in f]
    falsch = _fehler(tmp_path, _erzeugung(bericht_ort="abgeleitet/migrationsabnahme.html"))
    assert any("bericht_ort" in f for f in falsch), falsch


def test_die_erzeugung_kennt_genau_ein_neues_feld(tmp_path):
    feldfehler = "kanonischen Renderer-Felder"
    assert not any(feldfehler in f for f in _fehler(tmp_path, _erzeugung()))
    assert not any(feldfehler in f for f in _fehler(tmp_path, _erzeugung(bericht_ort=ORT)))
    fremd = {**_erzeugung(), "anderes": 1}
    assert any(feldfehler in f for f in _fehler(tmp_path, fremd))
