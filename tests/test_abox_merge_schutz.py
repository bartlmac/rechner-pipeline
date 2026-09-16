"""Der A-Box-Merge ueberschreibt keine Entscheidungen.

Vorfall 2026-09-07 (zweiter Baldrian-Fall): Bei einer Neuerzeugung auf
neuem Systemstand wurde ``abox_merge`` erneut gefahren und baute die
A-Box frisch aus den Fragmenten — die 14 vom Verantwortlichen Aktuar
aufgeloesten Diskrepanzen (Gate A-Q1) waren weg. Die Aufloesungen leben
nur in dieser Datei. Was ein Test hier halten kann: dass das Kommando
eine A-Box mit aufgeloesten Diskrepanzen nicht still ersetzt, und dass
die ausdrueckliche Verwerfung ein Flag ist, kein Zufall.

Knoten: system/gates
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rechner_pipeline.fall import anlegen
from rechner_pipeline.gates import abox_merge
from rechner_pipeline.gates._common import Exit

REPO_ROOT = Path(__file__).resolve().parents[1]


def _fall_mit_abox(tmp_path: Path, status: str) -> Path:
    fall = tmp_path / "fall"
    anlegen(fall, scope="tarif")
    abox = fall / "abgeleitet" / "abox"
    abox.mkdir(parents=True, exist_ok=True)
    (abox / "abox.json").write_text(json.dumps({
        "schema_version": 1, "fall": "probe", "tbox_version": "x",
        "generationen": [],
        "diskrepanzen": [
            {"id": "klv/x/zelle:a#zins", "status": status, "entscheidung": None},
            {"id": "klv/x/zelle:a#tafel", "status": status, "entscheidung": None},
        ],
    }), encoding="utf-8")
    return fall


def test_merge_verweigert_das_ueberschreiben_aufgeloester_diskrepanzen(tmp_path):
    fall = _fall_mit_abox(tmp_path, "aufgeloest")
    vorher = (fall / "abgeleitet" / "abox" / "abox.json").read_bytes()
    ergebnis = abox_merge.main([
        "--fall", str(fall), "--repo-root", str(REPO_ROOT),
        "--diagnostics-dir", str(tmp_path / "diag"),
    ])
    assert ergebnis.exit_code == Exit.FILE_CONTRACT
    assert ergebnis.errors[0]["code"] == "abox_entschieden"
    assert "2 aufgeloeste" in ergebnis.errors[0]["message"]
    assert "--ueberschreiben" in ergebnis.errors[0]["message"]
    assert (fall / "abgeleitet" / "abox" / "abox.json").read_bytes() == vorher


def test_offene_diskrepanzen_und_ueberschreiben_lassen_den_merge_weiterlaufen(tmp_path):
    """Ohne Entscheidungen gibt es nichts zu schuetzen; mit --ueberschreiben
    ist die Verwerfung ausdruecklich. In beiden Faellen laeuft der Merge
    bis zu seiner naechsten Wache (hier: keine Fragmente im Fall)."""
    offen = _fall_mit_abox(tmp_path / "a", "offen")
    ergebnis = abox_merge.main([
        "--fall", str(offen), "--repo-root", str(REPO_ROOT),
        "--diagnostics-dir", str(tmp_path / "diag-a"),
    ])
    assert ergebnis.errors[0]["code"] != "abox_entschieden"

    entschieden = _fall_mit_abox(tmp_path / "b", "aufgeloest")
    ergebnis = abox_merge.main([
        "--fall", str(entschieden), "--repo-root", str(REPO_ROOT),
        "--diagnostics-dir", str(tmp_path / "diag-b"), "--ueberschreiben",
    ])
    assert ergebnis.errors[0]["code"] != "abox_entschieden"


@pytest.mark.parametrize("inhalt", [
    b'{"diskrepanzen": [{"id": "d1", "status": "aufgelo',   # abgeschnitten
    b"[]",                                                   # kein JSON-Objekt
    b"",                                                     # leer
])
def test_eine_unlesbare_abox_haelt_den_merge_an(tmp_path, inhalt):
    """Review T25-11: "Datei fehlt" und "Datei ist kaputt" lieferten beide
    eine leere Liste — und der Merge las daraus "keine aufgeloeste
    Diskrepanz vorhanden, ich darf schreiben".

    Ob dort Entscheidungen standen, weiss in diesem Moment niemand. Genau
    deshalb darf nichts ueberschrieben werden: Unklarheit ist ein
    benannter Zustand, kein stilles Ja. Die zweite Haelfte des Befundes
    (abox.speichere schreibt nicht atomar) machte die Datei zur Quelle
    genau dieser Beschaedigung.
    """
    fall = _fall_mit_abox(tmp_path, "aufgeloest")
    pfad = fall / "abgeleitet" / "abox" / "abox.json"
    pfad.write_bytes(inhalt)
    ergebnis = abox_merge.main([
        "--fall", str(fall), "--repo-root", str(REPO_ROOT),
        "--diagnostics-dir", str(tmp_path / "diag"),
    ])
    assert ergebnis.exit_code == Exit.FILE_CONTRACT
    assert ergebnis.errors[0]["code"] == "abox_unlesbar"
    assert pfad.read_bytes() == inhalt, "der Merge hat die Datei angefasst"


def test_auch_ueberschreiben_hilft_bei_einer_unlesbaren_abox_nicht(tmp_path):
    """``--ueberschreiben`` heisst "ich verwerfe die Aufloesungen bewusst".
    Bewusst kann das niemand tun, der nicht weiss, was dort steht."""
    fall = _fall_mit_abox(tmp_path, "aufgeloest")
    (fall / "abgeleitet" / "abox" / "abox.json").write_bytes(b"{kaputt")
    ergebnis = abox_merge.main([
        "--fall", str(fall), "--repo-root", str(REPO_ROOT),
        "--diagnostics-dir", str(tmp_path / "diag"), "--ueberschreiben",
    ])
    assert ergebnis.errors[0]["code"] == "abox_unlesbar"


def test_die_abox_wird_atomar_geschrieben(tmp_path, monkeypatch):
    """Review T25-11, zweite Haelfte: ``write_text`` schrieb direkt in die
    Zieldatei. Ein Absturz dabei hinterliess eine halbe abox.json — die
    Datei machte sich selbst zu der Beschaedigung, gegen die ihre Leser
    sich wappnen muessen.

    Geprueft wird das Verhalten, nicht die Schreibweise: Scheitert die
    Veroeffentlichung, steht die alte Datei unveraendert da und es bleibt
    kein Rest liegen.
    """
    import os as _os

    from rechner_pipeline.ontologie import abox as abox_mod

    from rechner_pipeline.ontologie.tbox import ABOX_SCHEMA_VERSION, ABox, TBOX_VERSION

    fall = _fall_mit_abox(tmp_path, "aufgeloest")
    pfad = fall / "abgeleitet" / "abox" / "abox.json"
    alt = pfad.read_bytes()
    geladen = ABox(fall=fall.name, schema_version=ABOX_SCHEMA_VERSION,
                   tbox_version=TBOX_VERSION, generationen=[], diskrepanzen=[])

    def _bricht_ab(*args, **kwargs):
        raise OSError("Platte voll")

    monkeypatch.setattr(_os, "replace", _bricht_ab)
    with pytest.raises(OSError):
        abox_mod.speichere(geladen, fall)
    monkeypatch.undo()

    assert pfad.read_bytes() == alt, "die alte A-Box wurde angetastet"
    assert not [p for p in pfad.parent.iterdir() if p.name.startswith(".")], (
        "ein Rest des abgebrochenen Schreibens blieb liegen")
    # Und der gelungene Schreibvorgang ersetzt sie vollstaendig.
    abox_mod.speichere(geladen, fall)
    assert pfad.read_bytes() != b"" and json.loads(pfad.read_text("utf-8"))
