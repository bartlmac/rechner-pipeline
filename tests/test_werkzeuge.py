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
* Das Umbaubudget unterscheidet Hinzufuegen von Ersetzen. Wer das
  vermischt, meldet gewoehnliche Arbeit als Architekturbruch — und ein
  Alarm, der immer schlaegt, wird abgeschaltet.

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
import umbaubudget as ub  # noqa: E402
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


# --------------------------------------------------------------------------- #
# Umbaubudget: die Schranke gegen das stille Ersetzen
# --------------------------------------------------------------------------- #


def _repo(tmp_path: Path) -> Path:
    """Ein winziges Repo mit einem Ausgangsstand auf ``basis``."""
    import subprocess

    repo = tmp_path / "repo"
    (repo / "tests" / "fixtures" / "kern_referenzwerte").mkdir(parents=True)
    (repo / "src" / "rechner_pipeline" / "kern").mkdir(parents=True)

    def git(*args):
        subprocess.run(["git", *args], cwd=repo, check=True,
                       capture_output=True)

    git("init", "-q", "-b", "basis")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "test")
    (repo / "tests" / "fixtures" / "kern_referenzwerte"
     / "referenz_alt.json").write_text('{"wert": 1}\n', encoding="utf-8")
    (repo / "src" / "rechner_pipeline" / "kern" / "modul.py").write_text(
        "\n".join(f"zeile_{i} = {i}" for i in range(60)) + "\n",
        encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "Ausgangsstand")
    git("switch", "-q", "-c", "lauf")
    return repo


def test_ein_neuer_referenzwert_ist_gewoehnliche_arbeit(tmp_path: Path):
    """Hinzufuegen stellt einen Massstab daneben, Aendern verschiebt ihn.

    Ein Alarm, der schon beim Danebenstellen schlaegt, meldet gewoehnliche
    Arbeit als Architekturbruch — und wird deshalb abgeschaltet.
    """
    import subprocess

    repo = _repo(tmp_path)
    (repo / "tests" / "fixtures" / "kern_referenzwerte"
     / "referenz_neu.json").write_text('{"wert": 2}\n', encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True,
                   capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "neuer Referenzwert"],
                   cwd=repo, check=True, capture_output=True)

    messung = ub.messe(repo, "basis")
    assert messung["stolperdraehte"] == []
    assert ub.befunde(messung) == []


def test_ein_geaenderter_referenzwert_reisst_den_draht(tmp_path: Path):
    """Wer den bestehenden Massstab umschreibt, aendert nicht das
    Gemessene, sondern das Mass."""
    import subprocess

    repo = _repo(tmp_path)
    (repo / "tests" / "fixtures" / "kern_referenzwerte"
     / "referenz_alt.json").write_text('{"wert": 99}\n', encoding="utf-8")
    subprocess.run(["git", "commit", "-q", "-am", "Referenzwert gedreht"],
                   cwd=repo, check=True, capture_output=True)

    messung = ub.messe(repo, "basis")
    assert [d["datei"] for d in messung["stolperdraehte"]] == [
        "tests/fixtures/kern_referenzwerte/referenz_alt.json"
    ]
    assert len(ub.befunde(messung)) == 1


def test_loeschen_im_kern_reisst_das_budget_hinzufuegen_nicht(
    tmp_path: Path, monkeypatch,
):
    """Loeschen ist Ersetzen — nur darauf zielt die Schranke."""
    import subprocess

    monkeypatch.setattr(ub, "VORGABE_LOESCHUNG", {"kern": 10})
    repo = _repo(tmp_path)
    modul = repo / "src" / "rechner_pipeline" / "kern" / "modul.py"

    modul.write_text(
        modul.read_text(encoding="utf-8")
        + "\n".join(f"neu_{i} = {i}" for i in range(500)) + "\n",
        encoding="utf-8")
    subprocess.run(["git", "commit", "-q", "-am", "viel hinzugefuegt"],
                   cwd=repo, check=True, capture_output=True)
    assert ub.befunde(ub.messe(repo, "basis")) == []

    modul.write_text("zeile_0 = 0\n", encoding="utf-8")
    subprocess.run(["git", "commit", "-q", "-am", "Kern ersetzt"],
                   cwd=repo, check=True, capture_output=True)
    offene = ub.befunde(ub.messe(repo, "basis"))
    assert len(offene) == 1
    assert "kern/" in offene[0] and "Ersetzen" in offene[0]


def test_ueberschreiten_ja_verschweigen_nein(tmp_path: Path):
    """Die Begruendung macht aus einer Nebenwirkung eine Entscheidung."""
    import subprocess

    repo = _repo(tmp_path)
    (repo / "tests" / "fixtures" / "kern_referenzwerte"
     / "referenz_alt.json").write_text('{"wert": 99}\n', encoding="utf-8")
    subprocess.run(["git", "commit", "-q", "-am", "Referenzwert gedreht"],
                   cwd=repo, check=True, capture_output=True)
    ziel = tmp_path / "budget.json"

    ohne = ub.main(["--repo", str(repo), "--basis", "basis",
                    "--json", str(ziel)])
    assert ohne == 20
    assert json.loads(ziel.read_text(encoding="utf-8"))[
        "ueberschreitung_begruendet"] is None

    mit = ub.main(["--repo", str(repo), "--basis", "basis",
                   "--json", str(ziel),
                   "--ueberschreitung-begruendet",
                   "Tafelwechsel, als Mensch entschieden"])
    assert mit == 0
    gespeichert = json.loads(ziel.read_text(encoding="utf-8"))
    assert gespeichert["ueberschreitung_begruendet"] == (
        "Tafelwechsel, als Mensch entschieden")
    assert gespeichert["befunde"], "der Befund bleibt sichtbar"
