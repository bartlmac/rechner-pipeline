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


# --------------------------------------------------------------------------- #
# Vorzeigeseite: der Ergebnisabschnitt
# --------------------------------------------------------------------------- #


def _fall_mit_berichten(tmp_path: Path, **berichte) -> Path:
    fall = tmp_path / "fall"
    (fall / "abgeleitet" / "berichte").mkdir(parents=True)
    (fall / "fall.json").write_text(
        json.dumps({"name": "probe", "scope": {"typ": "bestand"}}), "utf-8")
    (fall / "eingang.json").write_text(json.dumps({"quellen": []}), "utf-8")
    for name, inhalt in berichte.items():
        (fall / "abgeleitet" / "berichte" / f"{name}.json").write_text(
            json.dumps(inhalt), "utf-8")
    return fall


def test_ein_roter_lauf_wird_als_roter_lauf_dargestellt(tmp_path: Path):
    """Eine Vorzeigeseite, die nur den Erfolgsfall zeigen kann, ist eine
    Werbebroschuere. Der Lauf ist keine: A-M4 duldet im Bestands-Scope
    keine Pruefluecke, und genau das muss lesbar sein."""
    fall = _fall_mit_berichten(
        tmp_path,
        aktuartest={"anzahl": 40, "bestanden": 37, "fehlgeschlagen": 3,
                    "test_bestanden": False},
        migrationssuite={"anzahl": 500, "bestanden": 494,
                         "pruefluecken": ["a", "b"],
                         "vollstaendig_geprueft": False,
                         "stichtag_1": "2026-01-01",
                         "stichtag_2": "2027-01-01"},
    )
    seite = vz._seite(fall, tmp_path, [], None)

    assert "**nicht bestanden**" in seite
    assert "| Prüflücken | 2 |" in seite
    assert "| Vollständig geprüft | nein |" in seite
    assert "geglätteter Wert wäre eine Behauptung ohne Rechnung" in seite


def test_eine_unbegruendete_ueberschreitung_bleibt_unbegruendet(
    tmp_path: Path,
):
    """Die Seite beschoenigt den Umbau nicht: Wer die Schranke ohne einen
    Satz reisst, steht ohne einen Satz da."""
    fall = _fall_mit_berichten(
        tmp_path,
        umbaubudget={"gesamt": {"summe": 21000, "vorgabe": 18000},
                     "befunde": ["Gesamtaenderung 21000 Zeilen ueber 18000"],
                     "ueberschreitung_begruendet": None},
    )
    seite = vz._seite(fall, tmp_path, [], None)
    assert "Eine Überschreitung:" in seite
    assert "**Ohne Begründung.**" in seite

    fall2 = _fall_mit_berichten(
        tmp_path / "zweiter",
        umbaubudget={"gesamt": {"summe": 21000, "vorgabe": 18000},
                     "befunde": ["Gesamtaenderung 21000 Zeilen ueber 18000"],
                     "ueberschreitung_begruendet": "Kern ersetzt, bewusst"},
    )
    seite2 = vz._seite(fall2, tmp_path, [], None)
    assert "Kern ersetzt, bewusst" in seite2
    assert "**Ohne Begründung.**" not in seite2


def test_ein_fall_ohne_berichte_behauptet_kein_ergebnis(tmp_path: Path):
    """Das Werkzeug laeuft auch auf einem leeren Fall durch — eine
    Vorzeigeseite ist deshalb KEIN Nachweis, dass der Lauf vollstaendig
    war. Sie darf dann aber auch nichts anderes behaupten."""
    fall = _fall_mit_berichten(tmp_path)
    seite = vz._seite(fall, tmp_path, [], None)
    assert "*(noch keine Berichte im Fall)*" in seite
    assert "bestanden" not in seite


# --------------------------------------------------------------------------- #
# Falldaten: das Datenmodell einer Falldarstellung
# --------------------------------------------------------------------------- #

import falldaten as fd  # noqa: E402
import fallbericht as fb  # noqa: E402


def _leerfall(tmp_path: Path) -> Path:
    fall = tmp_path / "leer"
    fall.mkdir()
    (fall / "fall.json").write_text(
        json.dumps({"name": "leer", "scope": {"typ": "bestand"}}), "utf-8")
    (fall / "eingang.json").write_text(json.dumps({"quellen": []}), "utf-8")
    return fall


def test_ein_fehlender_abschnitt_wird_laut_gemeldet(tmp_path: Path):
    """Der Bericht ist Konsument der Pipeline und kein Vertragsgeber: Er
    liest, was ohnehin entsteht. Der Preis dafuer ist, dass eine
    Formaenderung ihn treffen kann — also muss sie wehtun. Eine
    Darstellung, die vollstaendig aussieht und es nicht ist, waere die
    schlechteste Variante."""
    fall = _leerfall(tmp_path)
    ziel = tmp_path / "daten.json"
    code = fd.main(["--fall", str(fall), "--out", str(ziel)])

    assert code == 3, "ein unvollstaendiger Fall darf nicht auf 0 enden"
    modell = json.loads(ziel.read_text(encoding="utf-8"))
    # Das Modell entsteht trotzdem — wer die Luecke beheben will, braucht
    # zuerst das, was da ist.
    assert {l["gruppe"] for l in modell["luecken"]} == {
        g for g, _, _ in fd.ERWARTET}


def test_eine_vollerhebung_ist_keine_zu_kleine_pruefmenge():
    """Der Geschaeftsvorfalltest prueft ALLE Vorfaelle, nicht alle
    Vertraege. Seine Grundgesamtheit mit der Bestandsgroesse zu
    vergleichen erzeugte eine Einschraenkung, die keine ist — und ein
    Alarm, der falsch schlaegt, wird abgeschaltet."""
    def modell(vollerhebung: bool):
        return {
            "bestand": {"anzahl": 500},
            "abnahmen": {"aktuariell": [{
                "kennung": "A-M3",
                "stichprobe": {"grundgesamtheit": 42,
                               "vollerhebung": vollerhebung},
                "plausibilitaets_pruefungen": 0,
            }], "controlling": None},
        }
    ohne = [a for a in fd.abgrenzungen(modell(False))
            if "Pruefgesamtheit" in a["was"]]
    mit = [a for a in fd.abgrenzungen(modell(True))
           if "Pruefgesamtheit" in a["was"]]
    assert len(ohne) == 1 and ohne[0]["zahlen"] == "42 von 500"
    assert mit == []


def test_ersetzter_wertvergleich_wird_zur_abgrenzung():
    """"100 von 100" darf nicht verschweigen, dass ein Teil der
    Pruefungen kein Wertvergleich war."""
    modell = {
        "bestand": {"anzahl": 100},
        "abnahmen": {"aktuariell": [{
            "kennung": "A-M1",
            "stichprobe": {"grundgesamtheit": 100, "vollerhebung": False},
            "plausibilitaets_pruefungen": 50,
            "plausibilitaet_vertraege": 25,
            "verteilung": {"anzahl_werte": 500},
        }], "controlling": None},
    }
    treffer = [a for a in fd.abgrenzungen(modell)
               if "Plausibilitaet" in a["was"]]
    assert len(treffer) == 1
    assert "50 von 550" in treffer[0]["zahlen"]
    assert "25 Vertraege" in treffer[0]["zahlen"]


def test_stille_und_erklaerte_nichtuebernahme_sind_verschieden():
    """Eine Spalte, ueber die niemand nachgedacht hat, sieht im Ergebnis
    aus wie eine bewusst weggelassene. Genau das darf sie nicht."""
    grund = {
        "bestand": {}, "abnahmen": {},
        "transformation": {
            "vorhanden": True, "zeilen_quelle": 10, "zeilen_ziel": 10,
            "konflikte": [],
            "nicht_uebernommen": [
                {"quellen": ["ERKLAERT"], "begruendung": "operatives Feld"}],
            "stumm_weggelassen": ["VERGESSEN"],
        },
    }
    aus = fd.abgrenzungen(grund)
    stumm = [a for a in aus if "weder abgebildet" in a["was"]]
    assert len(stumm) == 1 and stumm[0]["zahlen"] == "VERGESSEN"
    # Die erklaerte Nichtuebernahme erzeugt KEINE Abgrenzung — sie ist
    # eine Aussage und kein Mangel.
    assert not any("ERKLAERT" in str(a.get("zahlen")) for a in aus)

    grund["transformation"]["nicht_uebernommen"][0]["begruendung"] = ""
    ohne_grund = [a for a in fd.abgrenzungen(grund)
                  if "ohne Begruendung" in a["was"]]
    assert len(ohne_grund) == 1


def test_zeilenverlust_der_transformation_faellt_auf():
    """Wer nur die transformierten Zeilen nimmt, migriert stillschweigend
    weniger Vertraege."""
    modell = {
        "bestand": {}, "abnahmen": {},
        "transformation": {"vorhanden": True, "zeilen_quelle": 500,
                           "zeilen_ziel": 497, "konflikte": [],
                           "nicht_uebernommen": [], "stumm_weggelassen": []},
    }
    treffer = [a for a in fd.abgrenzungen(modell) if "Zeilen verloren" in a["was"]]
    assert len(treffer) == 1 and treffer[0]["zahlen"] == "497 von 500"


# --------------------------------------------------------------------------- #
# Fallbericht: die Darstellung
# --------------------------------------------------------------------------- #


def test_die_darstellung_traegt_ohne_freien_text(tmp_path: Path):
    """Die Zahlen tragen fuer sich; der Text ordnet nur ein. Ein Bericht
    ohne Textdatei muss deshalb vollstaendig sein — sonst haengt die
    Aussage doch am Verfasser."""
    modell = {
        "fall": {"name": "probe", "scope": "bestand"},
        "lieferung": {"anzahl": 2, "anzahl_nachgereicht": 1, "quellen": [
            {"datei": "a.csv", "bytes": 10, "sha256": "ab" * 32,
             "nachgereicht": False},
            {"datei": "notiz.docx", "bytes": 20, "sha256": "cd" * 32,
             "nachgereicht": True}]},
        "bestand": {"vorhanden": True, "anzahl": 500, "groessen": {},
                    "abzuege": [], "kreuzproben": [
                        {"was": "Abgaenge", "links": 9, "rechts": 9,
                         "stimmt": True}]},
        "abnahmen": {"aktuariell": [], "controlling": None},
        "parameter": {"diskrepanzen": [], "belege": {}},
        "kette": {"gates": [], "entscheide": []},
        "abgrenzungen": [],
    }
    seite = fb.baue(modell, {})
    assert "500" in seite
    assert "notiz.docx" in seite and "nachgereicht" in seite
    assert "geht auf" in seite          # die Kreuzprobe steht drin
    assert "Fachliche Sicht" in seite and "Technische Sicht" in seite


def test_eine_nicht_aufgehende_kreuzprobe_wird_nicht_beschoenigt():
    modell = {
        "fall": {"name": "p", "scope": "bestand"},
        "lieferung": {"quellen": []},
        "bestand": {"vorhanden": True, "anzahl": 5, "groessen": {},
                    "abzuege": [], "kreuzproben": [
                        {"was": "Abgaenge", "links": 9, "rechts": 7,
                         "stimmt": False}]},
        "abnahmen": {"aktuariell": [], "controlling": None},
        "parameter": {"diskrepanzen": [], "belege": {}},
        "kette": {"gates": [], "entscheide": []},
        "abgrenzungen": [],
    }
    assert "GEHT NICHT AUF" in fb.baue(modell, {})


def test_abgrenzungen_landen_in_ihrer_sicht():
    """Fachliche Einschraenkungen gehoeren zum Fachteil, technische zum
    technischen — sonst liest der Aktuar Prüfsummen und der Entwickler
    Residuen."""
    modell = {
        "fall": {"name": "p", "scope": "bestand"},
        "lieferung": {"quellen": []},
        "bestand": {"vorhanden": False},
        "abnahmen": {"aktuariell": [], "controlling": None},
        "parameter": {"diskrepanzen": [], "belege": {}},
        "kette": {"gates": [], "entscheide": []},
        "abgrenzungen": [
            {"sicht": "fachlich", "abnahme": "A-M1", "was": "FACHBEFUND",
             "zahlen": "1 von 2"},
            {"sicht": "technisch", "abnahme": None, "was": "TECHNIKBEFUND",
             "zahlen": None},
        ],
    }
    seite = fb.baue(modell, {})
    fach = seite.index("FACHBEFUND")
    technik = seite.index("TECHNIKBEFUND")
    trenner = seite.index("Technische Sicht")
    assert fach < trenner < technik
