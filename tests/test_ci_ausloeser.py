"""Der Test-Workflow laeuft je Commit genau einmal.

Liefe ``tests.yml`` fuer Zweige sowohl bei push als auch bei pull_request,
bekaeme jeder Commit eines offenen Pull Requests zwei Laeufe namens
``pytest``. Die Gruppenregel bricht einen davon ab, und der abgebrochene
Lauf zaehlt als Pflicht-Check: Der Merge bleibt gesperrt, obwohl der andere
Lauf gruen ist (gemessen am 10.11.2026). Deshalb startet push nur auf main;
Zweige laufen ueber pull_request.

Knoten: system/architektur
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "tests.yml"


def ausloeser(text: str) -> dict:
    """Die Ausloeser unter ``on:`` als {Ereignis: [Zeilen des Blocks]}, ohne Kommentare."""
    zeilen = text.splitlines()
    start = zeilen.index("on:")
    ereignisse: dict = {}
    aktuell = None
    for zeile in zeilen[start + 1:]:
        if zeile and not zeile.startswith(" "):
            break
        inhalt = zeile.split("#", 1)[0].rstrip()
        if not inhalt.strip():
            continue
        if inhalt.startswith("  ") and not inhalt.startswith("    "):
            aktuell = inhalt.strip().rstrip(":")
            ereignisse[aktuell] = []
        elif aktuell is not None:
            ereignisse[aktuell].append(inhalt.strip())
    return ereignisse


def test_push_laeuft_nur_auf_main():
    on = ausloeser(WORKFLOW.read_text(encoding="utf-8"))
    assert on.get("push") == ["branches: [main]"], on.get("push")


def test_zweige_laufen_ueber_pull_request():
    on = ausloeser(WORKFLOW.read_text(encoding="utf-8"))
    assert "pull_request" in on, sorted(on)
    assert on["pull_request"] == [], "pull_request ohne Einschraenkung erwartet"


def test_der_leser_erkennt_einen_push_auf_alle_zweige():
    text = 'name: tests\non:\n  push:\n    branches: ["**"]\n  pull_request:\njobs:\n'
    assert ausloeser(text) == {"push": ['branches: ["**"]'], "pull_request": []}
