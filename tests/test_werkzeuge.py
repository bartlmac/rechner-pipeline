"""Werkzeuge der Vorfuehrung — Sprechertrennung und Regie-Sperre.

Die beiden Werkzeuge unter ``werkzeuge/`` sind kein Bestandteil der
Migrations-Pipeline (ADR-013-Nachbarschaft: Beobachtungshilfe, nicht
Fachlichkeit). Zwei ihrer Eigenschaften sind trotzdem test-wuerdig, weil
ein Fehler dort etwas Falsches BEHAUPTET statt nur etwas nicht zu
koennen:

* Das Verlaufsprotokoll trennt Mensch, Werkzeug und System-Einblendung.
  Wer das vermischt, legt dem Menschen Saetze in den Mund, die die
  Maschine geschrieben hat.
* Die Vorzeigeseite laesst die Regie nicht durch. ``simulation/`` und
  ``docs-local/`` tragen die Aufloesungen des Vorfuehrfalls; eine
  Sperre, die nur empfiehlt, ist keine.

Knoten: klv
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

WERKZEUGE = Path(__file__).resolve().parent.parent / "werkzeuge"
sys.path.insert(0, str(WERKZEUGE))

import verlaufsprotokoll as vp  # noqa: E402
import vorzeigeseite as vz  # noqa: E402


# --------------------------------------------------------------------------- #
# Verlaufsprotokoll: die Sprechertrennung
# --------------------------------------------------------------------------- #


def _transkript(tmp_path: Path, eintraege) -> Path:
    pfad = tmp_path / "sitzung.jsonl"
    pfad.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in eintraege),
        encoding="utf-8")
    return pfad


def _mensch(text: str, **rest):
    return {"type": "user", "timestamp": "2026-08-28T08:00:00Z",
            "message": {"role": "user", "content": text}, **rest}


def _operator(bloecke):
    return {"type": "assistant", "timestamp": "2026-08-28T08:00:01Z",
            "message": {"role": "assistant", "model": "claude-opus-5",
                        "content": bloecke}}


def test_system_einblendungen_gelten_nicht_als_menschliche_aeusserung(tmp_path):
    """Sonst stehen Maschinentexte unter der Ueberschrift 'Mensch'."""
    pfad = _transkript(tmp_path, [
        _mensch("Bitte den Bestand pruefen."),
        _mensch("<system-reminder>Kontext</system-reminder>"),
        _mensch("[Request interrupted by user]"),
        _mensch("This session is being continued from a previous conversation"),
        _mensch("egal", isMeta=True),
    ])
    lauf = vp.sammle(pfad, mit_denken=False)
    menschen = [e for e in lauf["eintraege"] if e["art"] == "mensch"]

    assert len(menschen) == 1
    assert menschen[0]["text"] == "Bitte den Bestand pruefen."


def test_konsolenkommando_ist_eine_eigene_art(tmp_path):
    """Ein '!'-Kommando gehoert ins Protokoll — aber nicht als Aeusserung."""
    pfad = _transkript(tmp_path, [
        _mensch("<bash-input>git status</bash-input>"
                "<bash-stdout>sauber</bash-stdout>"),
    ])
    lauf = vp.sammle(pfad, mit_denken=False)

    arten = {e["art"] for e in lauf["eintraege"]}
    assert arten == {"konsole"}
    assert lauf["eintraege"][0]["text"] == "git status"


def test_werkzeug_und_entscheid_werden_unterschieden(tmp_path):
    """Ein Entscheid schreibt den Lauf fest und wird hervorgehoben."""
    pfad = _transkript(tmp_path, [
        _operator([
            {"type": "text", "text": "Ich pruefe."},
            {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
            {"type": "tool_use", "name": "Bash",
             "input": {"command": "python -m rechner_pipeline.gates.gate_entscheid --gate A-M1"}},
        ]),
    ])
    lauf = vp.sammle(pfad, mit_denken=False)
    arten = [e["art"] for e in lauf["eintraege"]]

    assert arten == ["operator", "werkzeug", "entscheidung"]


def test_denkbloecke_bleiben_ohne_ausdrueckliche_anforderung_draussen(tmp_path):
    pfad = _transkript(tmp_path, [
        _operator([{"type": "thinking", "thinking": "innerer Monolog"}]),
    ])

    assert vp.sammle(pfad, mit_denken=False)["eintraege"] == []
    assert len(vp.sammle(pfad, mit_denken=True)["eintraege"]) == 1


@pytest.mark.parametrize("text,erwartet", [
    ("--freigabe-schluessel /home/x/.secrets/p9.key", "[redigiert]"),
    ("--freigabe-schluessel=/sicher/p9.key", "[redigiert]"),
    ("cat ~/.secrets/anthropic-api-key", "[Schluesselpfad redigiert]"),
    ("export ANTHROPIC_API_KEY=sk-ant-geheim", "[Geheimnis redigiert]"),
])
def test_schluesselmaterial_wird_redigiert(text, erwartet):
    """Das Protokoll ist zum Herumzeigen gedacht."""
    ergebnis = vp.redigiere(text)

    assert erwartet in ergebnis
    assert "p9.key" not in ergebnis
    assert "sk-ant-geheim" not in ergebnis
    # Kein Rest eines zweiten, ueberlappenden Musters.
    assert "redigiert]" not in ergebnis.replace(erwartet, "")


def test_harmloser_text_bleibt_unveraendert():
    assert vp.redigiere("ganz normaler Satz") == "ganz normaler Satz"


# --------------------------------------------------------------------------- #
# Vorzeigeseite: die Regie-Sperre
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("pfad", [
    "simulation/baldrian/irgendwas.csv",
    "docs-local/notiz.md",
    "irgendwo/MANIPULATIONEN.md",
    "ein/anderer/ort/NOTIZEN.md",
])
def test_regie_wird_nicht_veroeffentlicht(tmp_path, pfad):
    """Die Sperre bricht ab, statt zu warnen."""
    ziel = tmp_path / pfad
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text("Aufloesung des Vorfuehrfalls", encoding="utf-8")

    with pytest.raises(vz.VeroeffentlichungFehler):
        vz._pruefe_regie(ziel)


def test_gewoehnlicher_fallpfad_passiert_die_sperre(tmp_path):
    ziel = tmp_path / "faelle" / "ein-fall" / "eingang.json"
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text("{}", encoding="utf-8")

    vz._pruefe_regie(ziel)  # darf nicht werfen
