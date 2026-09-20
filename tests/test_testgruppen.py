"""Die Testgruppen selbst pruefen — sonst faellt ein Modul still heraus.

``tests/conftest.py`` leitet die Gruppen aus den ``Knoten:``-Annotationen
ab, damit niemand 128 Dateien von Hand markieren muss. Der Preis dieser
Ableitung ist eine neue Fehlerquelle: Ein Modul ohne Annotation bekommt
keinen Marker, faellt aus jedem gruppenweisen Teillauf heraus — und
niemand merkt es, weil ein nicht ausgefuehrter Test nicht rot wird.
Genau die Bauform, die in dieser Codebasis schon mehrfach etwas
durchgelassen hat (siehe "Detektor ohne Treffer").

Deshalb pruefen diese Tests die Gruppierung, nicht den Code.

Knoten: system/architektur
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import LANGSAM, TESTS, _marker_namen

#: Module ohne ``Knoten:``-Annotation waeren ein Befund von
#: ``ontologie.code_index`` und nicht von hier. Die Ausnahme ist dieses
#: Modul-Verzeichnis selbst: Helfer sind keine Testmodule.
HELFER = {"conftest.py", "e2e_fixture.py", "zeichnung_fixture.py"}


def _testmodule() -> list:
    return sorted(p for p in TESTS.glob("test_*.py"))


def test_jedes_testmodul_traegt_mindestens_eine_gruppe():
    """Ohne Gruppe faellt ein Modul aus jedem Teillauf heraus.

    Das ist der eigentliche Zweck dieser Datei: Die Ableitung ist
    bequem, aber sie schweigt, wenn sie nichts findet.
    """
    ohne = [p.name for p in _testmodule() if not _marker_namen(p)]
    assert ohne == [], (
        "Testmodul ohne Knoten-Annotation — es liefe in keinem "
        "gruppenweisen Teillauf mit", ohne)


def test_die_langsam_liste_nennt_nur_module_die_es_gibt():
    """Ein Eintrag, den es nicht mehr gibt, ist eine stille Luege: Er
    suggeriert, dass etwas aus dem schnellen Lauf genommen wurde, was
    dort laengst nicht mehr liegt."""
    fehlend = sorted(n for n in LANGSAM if not (TESTS / n).is_file())
    assert fehlend == [], ("LANGSAM nennt Module, die es nicht gibt", fehlend)


def test_langsam_ist_eine_echte_teilmenge():
    """Positivkontrolle in beide Richtungen: Waere LANGSAM leer, brächte
    ``-m "not langsam"`` nichts; waere es alles, brächte es nichts
    anderes als ein leerer Lauf."""
    alle = {p.name for p in _testmodule()}
    assert LANGSAM, "ohne Eintraege ist die schnelle Bahn keine"
    assert LANGSAM < alle, "LANGSAM darf nicht die ganze Suite sein"


def test_die_marker_sind_angemeldet(pytestconfig):
    """``filterwarnings = error`` macht einen unangemeldeten Marker zum
    Fehler. Die Anmeldung wird aus den Dateien gebildet — wenn sie das
    nicht vollstaendig tut, faellt die Suite an einer Stelle, die nichts
    mit der Sache zu tun hat."""
    angemeldet = {
        zeile.split(":", 1)[0].strip()
        for zeile in pytestconfig.getini("markers")
    }
    gebraucht = {name for p in _testmodule() for name in _marker_namen(p)}
    fehlend = sorted(gebraucht - angemeldet)
    assert fehlend == [], ("Marker benutzt, aber nicht angemeldet", fehlend)


@pytest.mark.parametrize("modul, erwartet", [
    ("test_baldrian2_e2e.py", "langsam"),
    ("test_korrekturschicht.py", "klv"),
    ("test_code_karte_und_impact.py", "system_architektur"),
])
def test_die_ableitung_trifft_das_richtige(modul: str, erwartet: str):
    """Stichprobe gegen die Ableitung selbst: Ein Marker-Mechanismus,
    der jedem alles gibt, gruppiert nichts."""
    assert erwartet in _marker_namen(TESTS / modul), _marker_namen(TESTS / modul)


def test_der_schraegstrich_wird_ersetzt():
    """``system/gates`` ist ein gueltiger Knoten, aber kein gueltiger
    Markername. Die Ersetzung muss stattfinden, sonst meldet pytest den
    Ausdruck als Syntaxfehler statt als leere Auswahl."""
    for p in _testmodule():
        for name in _marker_namen(p):
            assert "/" not in name and "-" not in name, (p.name, name)
