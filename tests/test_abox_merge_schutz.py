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
