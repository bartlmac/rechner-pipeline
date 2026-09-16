"""Umbaubericht des Umbaubudget-Werkzeugs — Gruppierung und HTML.

Der Bericht haengt an der Fall-Seite und BEHAUPTET dort, was der Lauf
am System veraendert hat. Testwuerdig ist deshalb (Muster von
test_werkzeuge): dass die Gruppierung ableitbar bleibt statt kuratiert
(nur Konventions-Commits, erster bekannter Scope entscheidet), dass
fremder Text die Seite nicht verletzen kann (Botschaften sind
Nutzereingaben fuer den Browser), und dass gleiche Eingaben gleiche
Bytes ergeben — der Bericht traegt bewusst keinen Zeitstempel.

Knoten: klv
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "werkzeuge"))

import umbaubudget as ub  # noqa: E402

MESSUNG = {
    "basis": "abc1234",
    "gesamt": {"plus": 40, "minus": 2, "summe": 42, "vorgabe": 18000},
    "loeschung_je_schicht": {
        "kern": {"gemessen": 1, "vorgabe": 450},
        "ontologie": {"gemessen": 0, "vorgabe": 450},
    },
    "loeschung_uebrige_schichten": {"gemessen": 2, "vorgabe": 1200},
    "stolperdraehte": [],
}


def test_gruppierung_ist_ableitbar_nicht_kuratiert():
    zeilen = [
        "aaa1111\tfeat(kern,qa)!: Teilkuendigung als drittes Verfahren",
        "bbb2222\tfix(qa): Toleranz auch im Controlling",
        "ccc3333\tdocs: Abschlussbericht",              # keine Korrektur
        "ddd4444\tmerge: irgendein Ast",                # keine Korrektur
        "eee5555\tfix(werkzeuge): ausserhalb der Schichten",
        "fff6666\tfeat(bestand,gates): Serien je Police",
    ]
    gruppen = dict(ub._gruppiere(zeilen))

    assert [e["commit"] for e in gruppen["Rechenkern"]] == ["aaa1111"]
    assert [e["commit"] for e in gruppen["Pruef-Engines"]] == ["bbb2222"]
    assert [e["commit"] for e in gruppen["Bestandsfuehrung und Uebernahme"]] \
        == ["fff6666"]
    assert [e["commit"] for e in gruppen["Weitere"]] == ["eee5555"]
    # docs/merge tauchen nirgends auf.
    alle = [e["commit"] for eintraege in gruppen.values() for e in eintraege]
    assert "ccc3333" not in alle and "ddd4444" not in alle


def test_erster_bekannter_scope_entscheidet():
    (name, eintraege), = ub._gruppiere(
        ["abc9999\tfix(gates,kern): Reihenfolge im Scope ist egal"])
    # "kern" steht in BEREICHE vor "gates" — die BEREICHS-Reihenfolge
    # entscheidet, nicht die Scope-Reihenfolge der Botschaft.
    assert name == "Rechenkern"
    assert eintraege[0]["commit"] == "abc9999"


def test_html_traegt_kennzahlen_befund_und_begruendung():
    seite = ub._html_bericht(
        MESSUNG, ["kern/: 999 Zeilen ueber der Vorgabe"],
        "Bewusst: der Lauf baute die Serien-Faehigkeiten.",
        [("Rechenkern", [{"commit": "aaa1111", "betreff": "feat: x"}])],
        "Umbaubericht", "def5678")
    assert "42 Zeilen" in seite and "18000" in seite
    assert "999 Zeilen ueber der Vorgabe" in seite
    assert "Als Menschentscheidung begruendet" in seite
    assert "Serien-Faehigkeiten" in seite
    assert "abc1234" in seite and "def5678" in seite
    assert "Rechenkern (1)" in seite


def test_html_entschaerft_fremden_text():
    """Mutationsfaenger: Commit-Botschaften sind Browser-Eingaben."""
    seite = ub._html_bericht(
        MESSUNG, [], None,
        [("Weitere", [{"commit": "aaa1111",
                       "betreff": 'fix: <script>alert("x")</script>'}])],
        "Umbaubericht <b>fett</b>", "def5678")
    assert "<script>" not in seite
    assert "&lt;script&gt;" in seite
    assert "<b>fett</b>" not in seite


def test_html_ist_deterministisch():
    args = (MESSUNG, [], None,
            [("Rechenkern", [{"commit": "aaa1111", "betreff": "feat: x"}])],
            "Umbaubericht", "def5678")
    assert ub._html_bericht(*args) == ub._html_bericht(*args)
    assert "erzeugt am" not in ub._html_bericht(*args).lower()
