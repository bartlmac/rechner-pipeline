"""Testgruppen — abgeleitet, nicht abgetippt.

Die Suite ist auf rund 2400 Tests gewachsen und braucht am Stueck rund
zwanzig Minuten. Das ist als Vorbedingung JEDES Commits untragbar
geworden. Dieses Modul macht Teillaeufe moeglich, ohne die Regel
aufzuweichen: Die volle Suite bleibt die Commit-Vorbedingung, aber der
Weg dorthin hat jetzt Zwischenstufen.

**Zwei Achsen, beide abgeleitet.**

1. *Knoten* (fachliche Linie) — aus der ``Knoten:``-Annotation im
   Modul-Docstring, die ``ontologie.code_index`` ohnehin drift-frei
   haelt. Ein Modul, das keine traegt, faellt dort auf, nicht hier.
   ``system/gates`` wird zu ``system_gates``, weil Marker keine
   Schraegstriche tragen. Das Vokabular ist damit das der KNOTEN
   (klv, bu, system_betrieb, ...) und nicht das der Schichten — wer
   ``-m kern`` versucht, bekommt eine leere Auswahl, keinen Fehler.
2. *Kosten* — ``langsam`` fuer die gemessenen Schwergewichte. Die Liste
   ist gemessen (``pytest --durations``), nicht geschaetzt, und ein Test
   in ``test_testgruppen.py`` haelt sie gegen die Wirklichkeit: ein
   Eintrag, den es nicht mehr gibt, ist ein Befund.

Warum abgeleitet und nicht annotiert: 128 Testmodule von Hand zu
markieren heisst, dass das 129. es vergisst — und ein Modul ohne Gruppe
faellt aus jedem Teillauf heraus, ohne dass es jemand merkt. Genau diese
Bauform ("Detektor ohne Treffer") hat in dieser Codebasis schon mehrfach
Fehler durchgelassen.

**Die Kommandos** (siehe auch ``AGENTS.md``)::

    pytest -m "not langsam"       # schnelle Rueckmeldung beim Bauen
    pytest -m system_betrieb      # eine Linie (klv, bu, system_betrieb,
                                  # system_bestand, system_assurance,
                                  # system_entscheid, system_architektur,
                                  # system_gates, system_fall,
                                  # system_skills, klv_tg2015, klv_tg2012)
    pytest -m "klv and not langsam"
    pytest $(git diff --name-only | python -m rechner_pipeline.ontologie.impact \\
             | python -c "import json,sys; print(' '.join(json.load(sys.stdin)['pytest_args']))")

Der letzte Weg ist der genaueste: ``ontologie.impact`` rechnet geaenderte
Dateien ueber die Import- und Knoten-Kanten auf die Testmodule um, die
sie ueberhaupt beruehren koennen.

Knoten: system/architektur
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent

#: Die gemessenen Schwergewichte (``pytest --durations``, 2026-09-20).
#: Zusammen tragen sie den weit groessten Teil der Laufzeit; ohne sie
#: laeuft der Rest in unter zwei Minuten. Wer hier etwas eintraegt,
#: nimmt es aus dem schnellen Lauf heraus — also nur mit Messung.
LANGSAM: frozenset = frozenset({
    "test_baldrian2_e2e.py",
    "test_baldrian_e2e.py",
    "test_betrieb_lange_geschichte.py",
    "test_betrieb_tageslauf.py",
    "test_betrieb_uebernahme.py",
    "test_betrieb_seite.py",
    "test_betrieb_neuaufsetzen.py",
    "test_betrieb_datenverlust_t24.py",
    "test_bestand_uebernommen_fortschreiben.py",
    "test_bestand_generator.py",
    "test_bestand_bewegung_klv.py",
    "test_code_karte_und_impact.py",
    "test_kern_algebraisch.py",
    "test_migrationssuite.py",
    "test_pk1_fixture_e2e.py",
    "test_at_pruefpunkte.py",
})

#: Die Annotation steht irgendwo im Modul-Docstring — auch direkt hinter
#: den oeffnenden Anfuehrungszeichen (``"""Knoten: system/assurance``).
#: Ein Zeilenanker uebersah genau diese Schreibweise; gelesen wird
#: deshalb der DOCSTRING, nicht der Dateitext.
_KNOTEN = re.compile(r"^\s*Knoten:\s*(.+)$", re.M)


def _marker_namen(pfad: Path) -> list:
    """Die Marker eines Testmoduls: seine Knoten plus ggf. ``langsam``."""
    namen = []
    docstring = ast.get_docstring(ast.parse(pfad.read_text("utf-8"))) or ""
    treffer = _KNOTEN.search(docstring)
    if treffer:
        for knoten in treffer.group(1).split(","):
            knoten = knoten.strip()
            if knoten:
                namen.append(knoten.replace("/", "_").replace("-", "_"))
    if pfad.name in LANGSAM:
        namen.append("langsam")
    return namen


def pytest_configure(config) -> None:
    """Die Marker anmelden, die in dieser Suite vorkommen.

    ``filterwarnings = error`` macht einen unbekannten Marker zum
    Fehler — das ist gewollt, aber es heisst, dass die Liste vollstaendig
    sein muss. Sie wird deshalb aus den Dateien selbst gebildet.
    """
    namen = {"langsam"}
    for pfad in sorted(TESTS.glob("test_*.py")):
        namen.update(_marker_namen(pfad))
    for name in sorted(namen):
        config.addinivalue_line(
            "markers", f"{name}: abgeleitete Testgruppe (tests/conftest.py)")


def pytest_collection_modifyitems(config, items) -> None:
    """Jedem Test die Marker seines Moduls geben."""
    je_datei: dict = {}
    for item in items:
        pfad = Path(str(item.fspath))
        if pfad.name not in je_datei:
            je_datei[pfad.name] = _marker_namen(pfad)
        for name in je_datei[pfad.name]:
            item.add_marker(getattr(pytest.mark, name))


def pytest_collection_finish(session) -> None:
    """Ein ``-m``-Ausdruck, der NICHTS auswaehlt, ist ein Fehler.

    pytest meldet eine leere Auswahl als Erfolg — "0 selected, 2381
    deselected", Exit 0. Wer sich im Markernamen vertippt oder eine
    SCHICHT statt eines KNOTENS nennt (``-m kern`` gibt es nicht),
    bekommt einen gruenen Lauf, der nichts geprueft hat. Das ist der
    Detektor ohne Treffer in Reinform, und mir ist er beim Schreiben
    dieser Datei selbst passiert.
    """
    ausdruck = session.config.option.markexpr
    if ausdruck and not session.items:
        raise pytest.UsageError(
            f"-m {ausdruck!r} waehlt keinen einzigen Test aus. Ein leerer "
            "Lauf ist kein gruener Lauf. Bekannte Gruppen: "
            + ", ".join(sorted(
                {n for p in TESTS.glob("test_*.py") for n in _marker_namen(p)}))
        )


@pytest.fixture(autouse=True, scope="session")
def _testschluesselring():
    """Jede Registrierung im Testlauf prueft die Freigabesignatur mit dem
    Testring (tests/freigabe_testschluessel.py) — die Naht
    ``betrieb.uebernahme._STANDARD_SCHLUESSELRING``. Produktiv ist sie
    None; dort kommt der Ring aus ``--freigabe-schluessel``.

    SESSION-weit, nicht je Funktion: Modul-weite Fixtures (etwa
    ``gefuehrt_mit_schicht`` in test_betrieb_drift_n01) registrieren ihren
    Eingang, BEVOR eine funktionsweite Naht greift — der Eingang stuende
    dann als "nicht verifiziert" da, und der Tageslauf verweigerte ihn,
    genau wie entschieden. Tests, die den unverifizierten Zustand pruefen,
    setzen die Naht per monkeypatch selbst auf None (funktionsweit,
    darunter bleibt der Testring)."""
    from rechner_pipeline.betrieb import uebernahme as _ueb
    from tests.freigabe_testschluessel import TESTRING

    vorher = _ueb._STANDARD_SCHLUESSELRING
    _ueb._STANDARD_SCHLUESSELRING = TESTRING
    yield
    _ueb._STANDARD_SCHLUESSELRING = vorher
