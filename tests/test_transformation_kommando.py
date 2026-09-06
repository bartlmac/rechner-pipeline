"""Das Transformationskommando: Blockade und Feldmenge.

Der Zusammenbau "Spec pruefen, dann anwenden" fiel bis 2026-08-28 je
Lauf als handgeschriebenes Fall-Skript an. Das alte Skript sagt es
selbst: "Es gibt fuer diesen Zusammenbau keine fertige CLI."

Zwei Eigenschaften sind test-wuerdig, beide vom Abnehmer erzwungen:

* Das Ergebnis-JSON traegt GENAU neun Felder. A-M4 vergleicht die
  Feldmenge exakt (abnahmebericht.py:344-351) und verwirft alles
  andere — ein Feld zu viel oder zu wenig, und die Migrationsabnahme
  ist nicht erreichbar.
* ``ziel_datei`` und ``ziel_sha256`` binden den BESTAND, nicht die
  Zeilenausgabe des Kommandos. Ohne ``--ziel`` bleiben sie leer, und
  das Kommando sagt das laut, statt es zu verschweigen.

Knoten: klv
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rechner_pipeline.gates.abnahmebericht import TRANSFORMATIONSERGEBNIS_FELDER
from rechner_pipeline.gates import transformation_anwenden as ta


def test_ergebnis_traegt_genau_die_felder_die_a_m4_verlangt(monkeypatch, tmp_path):
    """Die Feldmenge ist exakt, nicht "mindestens"."""
    fall = tmp_path / "fall"
    (fall / "eingang").mkdir(parents=True)
    quelle = fall / "eingang" / "abzug.csv"
    quelle.write_text("A;B\n1;2\n", encoding="utf-8")
    spec_pfad = tmp_path / "spec.json"
    spec_pfad.write_text('{"quelle_datei": "abzug.csv"}', encoding="utf-8")

    monkeypatch.setattr(ta.fall_mod, "eingang_datei",
                        lambda _fall, _name: quelle)

    class _Spec:
        quelle_datei = "abzug.csv"

    ergebnis = ta._ergebnis_json(
        fall, spec_pfad, _Spec(), ["A", "B"],
        zeilen_quelle=1, zeilen_ziel=1, befunde=[], ziel=None)

    assert set(ergebnis) == TRANSFORMATIONSERGEBNIS_FELDER


def test_ohne_ziel_bleiben_die_bestandsbindungen_leer(monkeypatch, tmp_path):
    """Sie binden den Bestand, nicht die Zeilenausgabe — fehlt er, ist
    das Ergebnis fuer A-M4 unbrauchbar, und zwar sichtbar."""
    fall = tmp_path / "fall"
    (fall / "eingang").mkdir(parents=True)
    quelle = fall / "eingang" / "abzug.csv"
    quelle.write_text("A\n1\n", encoding="utf-8")
    spec_pfad = tmp_path / "spec.json"
    spec_pfad.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(ta.fall_mod, "eingang_datei",
                        lambda _fall, _name: quelle)

    class _Spec:
        quelle_datei = "abzug.csv"

    ergebnis = ta._ergebnis_json(fall, spec_pfad, _Spec(), ["A"], 1, 1, [], None)

    assert ergebnis["ziel_datei"] == ""
    assert ergebnis["ziel_sha256"] == ""
    assert ergebnis["schema_version"] == 1
    assert isinstance(ergebnis["schema_version"], int)


class _Feld:
    def __init__(self, quellen, ziel, typ="direkt", kodierung=None,
                 berechnung=None, begruendung="aus der Quelle belegt"):
        self.quellen, self.ziel, self.typ = quellen, ziel, typ
        self.kodierung, self.berechnung = kodierung or {}, berechnung
        self.begruendung = begruendung


class _Konflikt:
    def __init__(self, quellspalte, frage, entscheidung, entscheider=None):
        self.quellspalte, self.frage = quellspalte, frage
        self.entscheidung, self.entscheider = entscheidung, entscheider


class _BerichtSpec:
    quelle_datei = "abzug.csv"
    quelle_sha256 = "ab" * 32
    akteur = "quelle-experte"
    felder = [
        _Feld(["POLNR"], "police_id"),
        _Feld(["VTG_STATUS"], "status", typ="kodierung",
              kodierung={"NR": "nichtraucher"}),
        _Feld(["STORNO_KZ"], "", typ="nicht_uebernommen",
              begruendung='<script>alert("x")</script>'),
    ]
    offene_konflikte = [
        _Konflikt("GESCHL", "Tarif rechnet unisex?",
                  "entschieden durch den Menschen",
                  "fachverantwortliche-rolle"),
    ]


def test_uebersetzungsbericht_traegt_abbildung_konflikte_und_ergebnis():
    """Entmischungs-Entscheid der Lauf-2-Sichtung: Die fachliche
    Darstellung der Uebersetzung zieht vom Abnahmebericht hierher um —
    der Bericht muss also genau das tragen, was dort entfiel."""
    seite = ta.baue_uebersetzungsbericht(
        titel="Uebersetzungsbericht", spec=_BerichtSpec(),
        quellspalten=["POLNR", "VTG_STATUS", "STORNO_KZ", "GESCHL"],
        zeilen_quelle=834, zeilen_ziel=834, befunde=[],
        ziel_datei="abgeleitet/bestand/bestand.parquet",
        ziel_sha256="cd" * 32)

    assert "POLNR" in seite and "police_id" in seite
    assert "NR -&gt; nichtraucher" in seite            # Kodierung, escaped
    assert "(nicht übernommen)" in seite
    assert ("entschieden (fachverantwortliche-rolle): "
            "entschieden durch den Menschen") in seite
    assert "<b>834</b>" in seite
    assert "Zielbindung" in seite and "cdcdcdcdcdcdcdcd" in seite
    # Begruendungen sind Browser-Eingaben — entschaerft, nie roh.
    assert "<script>" not in seite
    assert "&lt;script&gt;" in seite


def test_uebersetzungsbericht_ist_deterministisch_und_ohne_zeitstempel():
    args = dict(
        titel="Uebersetzungsbericht", spec=_BerichtSpec(),
        quellspalten=["POLNR"], zeilen_quelle=1, zeilen_ziel=1,
        befunde=["eine Zeile mit Befund"], ziel_datei=None,
        ziel_sha256=None)
    a = ta.baue_uebersetzungsbericht(**args)
    assert a == ta.baue_uebersetzungsbericht(**args)
    assert "erzeugt am" not in a.lower()
    assert "eine Zeile mit Befund" in a
    assert "Zielbindung" not in a                      # ohne --ziel: keine


def test_bericht_braucht_anwenden():
    """Fail fast statt leerer Behauptung: Ohne Anwendung gibt es kein
    Ergebnis, das der Bericht zeigen koennte."""
    assert ta.main(["--fall", "egal", "--spec", "egal",
                    "--bericht", "egal.html"]) == 2


def test_spec_hash_haengt_an_den_dateibytes(monkeypatch, tmp_path):
    """A-M4 rechnet spec_sha256 gegen die aktuellen Bytes nach.

    Jedes spaetere Umformatieren der Spec bricht die Bindung — deshalb
    darf der Hash NICHT ueber das geparste Objekt laufen.
    """
    fall = tmp_path / "fall"
    (fall / "eingang").mkdir(parents=True)
    quelle = fall / "eingang" / "abzug.csv"
    quelle.write_text("A\n1\n", encoding="utf-8")
    monkeypatch.setattr(ta.fall_mod, "eingang_datei",
                        lambda _fall, _name: quelle)

    class _Spec:
        quelle_datei = "abzug.csv"

    eng = tmp_path / "eng.json"
    eng.write_text('{"a":1}', encoding="utf-8")
    weit = tmp_path / "weit.json"
    weit.write_text('{\n  "a": 1\n}\n', encoding="utf-8")

    a = ta._ergebnis_json(fall, eng, _Spec(), ["A"], 1, 1, [], None)
    b = ta._ergebnis_json(fall, weit, _Spec(), ["A"], 1, 1, [], None)

    # Gleicher Inhalt, andere Bytes -> anderer Hash. Genau so prueft A-M4.
    assert a["spec_sha256"] != b["spec_sha256"]
