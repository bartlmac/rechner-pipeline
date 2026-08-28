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
