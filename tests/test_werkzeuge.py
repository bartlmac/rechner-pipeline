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


def _fallseite(*args, **kwargs) -> str:
    """Die Fallseite — EINE Seite, von der Lieferung bis zum Zugang.

    Sie war einmal dreizehn Seiten. Der Helfer bleibt, weil er die
    Erzeugerfunktion kapselt; ``_seiten`` gibt seit dem Umbau genau
    einen Eintrag zurueck.
    """
    import vorzeigeseite as _vz

    return "\n".join(_vz._seiten(*args, **kwargs).values())



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
    "regie/drehbuch-lauf2.md",
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


def test_die_sperrliste_traegt_alle_spielleiter_bereiche():
    """Befund T19-01 (externes Review): ``regie/`` fehlte in REGIE.

    Der Unit-Test oben haette den Fehler nie gefunden — er prueft die
    Funktion mit den Werten, die die Konstante ohnehin kennt. Die
    Zusicherung steht aber woanders: dev-docs/regie.md nennt DREI
    Spielleiter-Bereiche und verspricht den Abbruch fuer alle. Diese
    Zusicherung ist hier festgeschrieben, damit ein vierter Bereich
    nicht wieder nur in Prosa existiert.
    """
    assert set(vz.REGIE) == {"simulation", "docs-local", "regie"}


def test_dokumentation_unter_docs_ist_keine_regie(tmp_path):
    """docs/simulation/ ist das versionierte Fachkonzept, simulation/ die
    Regie. Nur der Elternteil docs/ nimmt aus — eine Regie-Datei, die
    tiefer unter simulation/ liegt, sperrt weiter."""
    vz._pruefe_regie(tmp_path / "docs" / "simulation" / "tagesbetrieb.md")  # darf nicht werfen
    for pfad in ("simulation/docs/x.md", "x/simulation/tagesbetrieb.md",
                 "docs/x/simulation/tagesbetrieb.md", "docs/regie/drehbuch.md",
                 "docs-local/plan.md", "docs/docs-local/plan.md"):
        with pytest.raises(vz.VeroeffentlichungFehler):
            vz._pruefe_regie(tmp_path / pfad)


def test_echter_seitenbau_kopiert_kein_regie_dokument(tmp_path):
    """Der Weg, nicht nur die Wache: So hat das externe Review den
    Befund reproduziert — ueber die CLI, nicht ueber die Funktion.

    Ohne diesen Test bliebe die Luecke bestehen, wenn jemand die
    Pruefung im Renderer versehentlich hinter das Lesen schoebe.
    """
    fall = tmp_path / "faelle" / "ein-fall"
    (fall / "abgeleitet").mkdir(parents=True)
    (fall / "fall.json").write_text('{"name": "ein-fall"}', encoding="utf-8")
    daten = tmp_path / "modell.json"
    daten.write_text('{"fall": {"name": "ein-fall"}}', encoding="utf-8")
    drehbuch = tmp_path / "regie" / "drehbuch.md"
    drehbuch.parent.mkdir(parents=True)
    drehbuch.write_text("GEHEIME AUFLOESUNG", encoding="utf-8")
    ziel = tmp_path / "seite"

    exit_code = vz.main([
        "--fall", str(fall), "--daten", str(daten),
        "--out", str(ziel), "--verlauf", str(drehbuch),
        "--repo", str(tmp_path),
    ])

    assert exit_code != 0, "der Seitenbau muss abbrechen"
    erzeugt = list(ziel.rglob("*")) if ziel.exists() else []
    assert not any(
        p.is_file() and "GEHEIME AUFLOESUNG" in p.read_text(encoding="utf-8")
        for p in erzeugt), "kein Regie-Text darf im Zielbaum liegen"


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


def _modell(fall: Path):
    """Das Datenmodell so erheben, wie es auch der Lauf taete.

    Die Seite ist Konsument von ``falldaten.py``; ein von Hand gebautes
    Modell testete sonst eine Form, die der Erzeuger nie schreibt.
    """
    import falldaten
    return falldaten.sammle(fall, [])


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
    seite = _fallseite(fall, _modell(fall), tmp_path, [], None)

    assert "**nicht bestanden**" in seite
    assert "| Prüflücken | 2 |" in seite
    assert "| davon bestanden | 494 |" in seite
    assert "geglätteter Wert wäre eine Behauptung ohne Rechnung" in seite


def test_der_kopf_zaehlt_dieselben_urteile_wie_die_ergebnistabelle(tmp_path: Path):
    """Der Kopf sagt in einem Satz, wie es ausging; die Tabelle unten sagt
    es je Abnahme. Beide muessen dasselbe Feld lesen.

    Vorfall beim Bau dieser Seite: ``urteil`` ist ein Wahrheitswert (so
    liest es ``_urteilswort``), der Kopf verglich ihn gegen den
    Gate-Status "passed". Ueber einer Tabelle mit vier Mal "bestanden"
    stand "0 von 4 Abnahmen bestanden" — auf einer Seite, deren ganzer
    Zweck Nachpruefbarkeit ist. Kein Test hat es gemerkt; gesehen hat es
    der Blick auf den gebauten Entwurf.
    """
    gruen = _fall_mit_berichten(
        tmp_path / "gruen",
        aktuartest={"anzahl": 40, "bestanden": 40, "test_bestanden": True},
        migrationssuite={"anzahl": 500, "bestanden": 500, "pruefluecken": [],
                         "vollstaendig_geprueft": True, "suite_bestanden": True,
                         "stichtag_1": "2026-01-01", "stichtag_2": "2027-01-01"},
    )
    seite = _fallseite(gruen, _modell(gruen), tmp_path, [], None)
    assert "**Wie es ausging.** Alle 2 Abnahmen bestanden, keine Prüflücke" in seite
    assert "**nicht bestanden**" not in seite

    # Gegenprobe in die andere Richtung: Faellt eine Abnahme, faellt die
    # Zahl im Kopf mit.
    rot = _fall_mit_berichten(
        tmp_path / "rot",
        aktuartest={"anzahl": 40, "bestanden": 37, "fehlgeschlagen": 3,
                    "test_bestanden": False},
        migrationssuite={"anzahl": 500, "bestanden": 500, "pruefluecken": [],
                         "vollstaendig_geprueft": True, "suite_bestanden": True,
                         "stichtag_1": "2026-01-01", "stichtag_2": "2027-01-01"},
    )
    seite = _fallseite(rot, _modell(rot), tmp_path, [], None)
    assert "1 von 2 Abnahmen bestanden, die übrigen **nicht**" in seite
    assert "Alle 2 Abnahmen bestanden" not in seite
    assert "**nicht bestanden**" in seite


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
    seite = _fallseite(fall, _modell(fall), tmp_path, [], None)
    # Der Umbau ist eine eigene Seite mit Kennzahlen — nicht mehr ein
    # Unterpunkt der Grenzen, wo er als Vorbehalt gelesen wurde.
    assert "# Was sich am System änderte" in seite
    assert "| Ausgeschöpft | 117 % |" in seite
    assert "**1 Befund der Messung.**" in seite
    assert "**Ohne Begründung.**" in seite

    fall2 = _fall_mit_berichten(
        tmp_path / "zweiter",
        umbaubudget={"gesamt": {"summe": 21000, "vorgabe": 18000},
                     "befunde": ["Gesamtaenderung 21000 Zeilen ueber 18000"],
                     "ueberschreitung_begruendet": "Kern ersetzt, bewusst"},
    )
    seite2 = _fallseite(fall2, _modell(fall2), tmp_path, [], None)
    assert "Kern ersetzt, bewusst" in seite2
    assert "**Ohne Begründung.**" not in seite2


def test_ein_fall_ohne_berichte_behauptet_kein_ergebnis(tmp_path: Path):
    """Das Werkzeug laeuft auch auf einem leeren Fall durch — eine
    Vorzeigeseite ist deshalb KEIN Nachweis, dass der Lauf vollstaendig
    war. Sie darf dann aber auch nichts anderes behaupten."""
    fall = _fall_mit_berichten(tmp_path)
    seite = _fallseite(fall, _modell(fall), tmp_path, [], None)
    assert "*(noch keine Berichte im Fall)*" in seite
    assert "bestanden" not in seite


def test_modell_verweise_passieren_die_regie_sperre_nicht_ungeprueft(
    tmp_path: Path,
):
    """Das Modell listet Artefakt-Verweise; die Seite prueft sie trotzdem
    selbst. Sonst waere die Liste ein Weg an der Regie-Sperre vorbei —
    die Zwei-Quellen-Lage beseitigt und dafuer die Sperre aufgeweicht."""
    fall = _fall_mit_berichten(tmp_path)
    modell = _modell(fall)
    modell["abnahmen"]["bestandsberichte"] = [
        "abgeleitet/berichte/NOTIZEN.md"]

    with pytest.raises(vz.VeroeffentlichungFehler):
        _fallseite(fall, modell, tmp_path,
                  ["artefakte/abgeleitet/berichte/NOTIZEN.md"], None)


def test_verlinkt_wird_nur_was_kopiert_wurde(tmp_path: Path):
    """Ein Link auf eine nicht kopierte Datei waere eine Behauptung ohne
    Artefakt daneben."""
    fall = _fall_mit_berichten(tmp_path)
    (fall / "abgeleitet" / "berichte" / "bestandsbericht-vor.html").write_text(
        "<p>Bericht</p>", encoding="utf-8")
    modell = _modell(fall)
    assert modell["abnahmen"]["bestandsberichte"] == [
        "abgeleitet/berichte/bestandsbericht-vor.html"]

    ohne = _fallseite(fall, modell, tmp_path, [], None)
    assert "bestandsbericht-vor.html" not in ohne

    mit = _fallseite(fall, modell, tmp_path,
                    ["artefakte/abgeleitet/berichte/bestandsbericht-vor.html"],
                    None)
    assert 'href="artefakte/abgeleitet/berichte/bestandsbericht-vor.html"' in mit
    # Was der Bericht ist, sagt er selbst: im Rechenkern bewertet, nicht
    # aus der Lieferung uebernommen (Gegenlesung 03.10.2026).
    assert "Übernommener Bestand zum Stichtag" in mit and "Gelieferter Bestand" not in mit


# --------------------------------------------------------------------------- #
# Unternehmensseite: die Banderole
# --------------------------------------------------------------------------- #

import falldaten as fd  # noqa: E402
import fallbericht as fb  # noqa: E402
import unternehmensseite as us  # noqa: E402


def _quellseiten(tmp_path: Path) -> Path:
    quellen = tmp_path / "plv/seite"
    quellen.mkdir(parents=True)
    (quellen / "_config.yml").write_text("theme: x\n", encoding="utf-8")
    (quellen / "index.md").write_text(
        "Fiktives Unternehmen — Vorfuehrung\n\n# Willkommen\n",
        encoding="utf-8")
    return quellen


def test_jede_seite_traegt_die_kennzeichnung_auch_ohne_zutun_des_autors(tmp_path: Path):
    """Je echter der Auftritt wirkt, desto wichtiger die Kennzeichnung:
    Eine Unternehmensseite ohne Fiktions-Hinweis saehe aus wie ein
    echter Versicherer. Der Bau garantiert die Fusszeile "Hinter den
    Kulissen" auf jeder Seite — der Autor kann sie nicht vergessen."""
    quellen = _quellseiten(tmp_path)
    (quellen / "it").mkdir()
    (quellen / "it" / "index.md").write_text(
        "# IT\nohne Hinweis\n", encoding="utf-8")
    us.baue(quellen, tmp_path / "seite", {})
    seite = (tmp_path / "seite" / "it" / "index.md").read_text(encoding="utf-8")
    assert us.BANDEROLE in seite
    assert seite.rstrip().endswith("Hinter den Kulissen</a></div>")
    assert 'href="../hinter-den-kulissen/"' in seite


def test_mit_banderole_wird_der_baum_gespiegelt(tmp_path: Path):
    quellen = _quellseiten(tmp_path)
    ziel = tmp_path / "seite"
    kopiert = us.baue(quellen, ziel, {})
    assert sorted(kopiert) == ["_config.yml", "index.md"]
    assert (ziel / "index.md").is_file()


def test_kennzahlen_kommen_aus_dem_modell_oder_der_bau_bricht(
    tmp_path: Path,
):
    """Generiert statt gepflegt: Die Zahlen der Quellseiten loest der
    Bau aus dem falldaten-Modell auf — eine Zahl, die niemand abtippt,
    kann dem Fall nicht davonlaufen. Ein unaufloesbarer Platzhalter
    bricht ab; eine Seite, die '{{...}}' zeigt, waere schlimmer."""
    quellen = _quellseiten(tmp_path)
    (quellen / "index.md").write_text(
        "Fiktives Unternehmen\n\n# Willkommen\n"
        "{{zahl:bestand.anzahl}} Vertraege, "
        "DK {{euro:bestand.abzuege.0.deckkap.summe}} €, "
        "Stichtag {{datum:abnahmen.controlling.stichtag_1}}\n"
        "{{svg:zugang_status}}\n\n{{tabelle:gevo_je_art}}\n",
        encoding="utf-8")
    modell = {
        "bestand": {
            "anzahl": 834,
            "abzuege": [{"deckkap": {"summe": 33437445.97}}],
            "verteilungen": {"status_code": {"POL": 674, "PEX": 160}},
            "vorfaelle_im_zeitraum": {"je_art": {
                "ERH": {"anzahl": 128}, "STO": {"anzahl": 14}}},
        },
        "abnahmen": {"controlling": {"stichtag_1": "2026-01-01"}},
    }

    us.baue(quellen, tmp_path / "seite", modell)
    seite = (tmp_path / "seite" / "index.md").read_text(encoding="utf-8")
    assert "834 Vertraege" in seite
    assert "33.437.445,97" in seite
    assert "01.01.2026" in seite
    assert "beitragspflichtig 674" in seite and "beitragsfrei 160" in seite
    assert "| Erhöhung | 128 |" in seite
    assert "{{" not in seite

    (quellen / "index.md").write_text(
        "Fiktives Unternehmen\n{{zahl:gibt.es.nicht}}\n", encoding="utf-8")
    with pytest.raises(vz.VeroeffentlichungFehler):
        us.baue(quellen, tmp_path / "seite2", modell)


def test_fachdokumente_werden_mit_banderole_importiert(tmp_path: Path):
    """Der Auftritt importiert die Fachdokumente beim Bau (eine Quelle,
    eine Heimat: docs/); der YAML-Vorspann wird zum Seitentitel, die
    Banderole kommt davor, Formeln bekommen MathJax. Ein fehlendes
    Dokument bricht den Bau ab, statt eine vollstaendig aussehende
    Seite ohne Tarifplaene zu bauen."""
    docs = tmp_path / "docs"
    (docs / "tarifplaene").mkdir(parents=True)
    (docs / "tarifplaene" / "probe.md").write_text(
        '---\ntitle: "Tarifplan Probe —\n  umbrochen"\nlang: de\n---\n\n'
        "# 1 Inhalt\nFormel $S_x$ und `$HOME/$PFAD`\n", encoding="utf-8")

    ziel = tmp_path / "seite"
    importiert = us.fachdokumente(
        docs, ziel,
        dokumente=(("tarifplaene/probe.md",
                    "aktuariat/tarifplaene/probe.md", "Aktuariat", "../"),))
    assert importiert == [
        ("aktuariat/tarifplaene/probe.md", "Tarifplan Probe — umbrochen")]
    seite = (ziel / "aktuariat" / "tarifplaene" / "probe.md").read_text(
        encoding="utf-8")
    assert us.BANDEROLE in seite
    assert "# Tarifplan Probe — umbrochen" in seite
    assert "title:" not in seite
    assert "mathjax" in seite.lower()
    # So, wie Pages es liest (gemessen mit dem Renderer von Pages am
    # 08.10.2026): die Formel als $$...$$, Code unberuehrt, der Rumpf in raw,
    # der Titel davor als erste Zeile (jekyll-titles-from-headings).
    assert "Formel $$S_x$$ und `$HOME/$PFAD`" in seite
    assert seite.splitlines()[0] == "# Tarifplan Probe — umbrochen"
    assert seite.index("# Tarifplan") < seite.index(us.ROH_AUF) < seite.index("# 1 Inhalt")
    assert seite.index("`$HOME/$PFAD`") < seite.index(us.ROH_ZU) < seite.index('class="fuss-fiktion"')
    uebersicht = (ziel / "aktuariat" / "tarifplaene" / "index.md").read_text(
        encoding="utf-8")
    assert "[Tarifplan Probe — umbrochen](probe.html)" in uebersicht
    assert uebersicht.splitlines()[0] == "# Tarifpläne"   # Titel vor dem Reiter

    with pytest.raises(vz.VeroeffentlichungFehler):
        us.fachdokumente(
            docs, ziel,
            dokumente=(("tarifplaene/fehlt.md",
                        "aktuariat/tarifplaene/fehlt.md",
                        "Aktuariat", "../"),))


def test_die_fallseite_als_unterseite_haengt_im_auftritt(tmp_path: Path):
    """Als Unterseite gehoert die Jekyll-Konfiguration der Wurzel des
    Auftritts, nicht dem Fall — und der Rueckverweis haengt den Bericht
    in die Migrations-Uebersicht ein."""
    fall = _fall_mit_berichten(tmp_path)
    daten = tmp_path / "daten.json"
    fd.main(["--fall", str(fall), "--out", str(daten)])
    ziel = tmp_path / "seite" / "migrationen" / "probe"

    code = vz.main(["--fall", str(fall), "--daten", str(daten),
                    "--out", str(ziel), "--als-unterseite"])
    # Der Probe-Fall ist unvollstaendig: geschrieben wird die Seite, der
    # Exit sagt es (3, Review T20-03) — hier geht es um die Unterseite.
    assert code == 3
    assert not (ziel / "_config.yml").exists()
    seite = (ziel / "index.md").read_text(encoding="utf-8")
    # Die Unterseite traegt die Hausgestaltung: Das Stylesheet setzt das
    # Layout, die Seite selbst nur Ueberschrift und Kopfband — dieselbe
    # Reihenfolge wie auf jeder anderen Seite, sonst faellt das Band aus.
    assert "stylesheet" not in seite
    assert seite.startswith("# ")
    assert 'nav class="kopf"' in seite and 'href="../../"' in seite

    # Ohne den Schalter bleibt die Seite eigenstaendig veroeffentlichbar.
    solo = tmp_path / "solo"
    vz.main(["--fall", str(fall), "--daten", str(daten), "--out", str(solo)])
    assert (solo / "_config.yml").is_file()
    assert 'class="chrom"' not in (solo / "index.md").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Auftritt: die Kette als ein Kommando
# --------------------------------------------------------------------------- #

import auftritt as at  # noqa: E402


def test_der_auftritt_reicht_den_fehler_der_kette_durch(tmp_path: Path):
    """Bricht ein Kettenglied, bricht die Kette — mit demselben Urteil.
    Ein Entwurf aus einer halb gelaufenen Kette saehe vollstaendig aus
    und waere es nicht."""
    code = at.main(["--fall", str(tmp_path / "kein-fall"), "--name", "x",
                    "--out", str(tmp_path / "seite"), "--vorschau", ""])
    assert code == 2
    assert not (tmp_path / "seite").exists()


# --------------------------------------------------------------------------- #
# Bereinigung: Hostpfade aus der veroeffentlichten Fassung (03.10.2026)
# --------------------------------------------------------------------------- #

import bereinigung as br  # noqa: E402


def _fall_mit_hostpfaden(tmp_path: Path):
    """Ein Fall unter ``<baum>/faelle/probe``, dessen Belege tragen, was die
    Belege von Fall 3 tragen: Hostpfade im Protokoll einer Zeichnung und im
    Eingangsregister, dazu ein ueberholter Snapshot mit einer Angabe, die
    nicht auf die Seite gehoert. Das Modell erhebt ``falldaten`` selbst."""
    fall = tmp_path / "faelle" / "probe"

    def schreibe(rel: str, inhalt) -> None:
        pfad = fall / rel
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_text(inhalt if isinstance(inhalt, str) else json.dumps(inhalt), encoding="utf-8")

    schreibe("fall.json", {"name": "probe", "scope": {"typ": "bestand"}})
    # Der Eintrag in der Form, die fall.registrieren schreibt.
    schreibe("eingang.json", {"quellen": [{
        "datei": "abzug.csv", "bytes": 8, "sha256": "c" * 64,
        "quelle_pfad": "/home/nutzer/apps/welt-x/quelle/postausgang/abzug.csv",
        "registriert_am": "2026-10-02T10:00:00+00:00"}]})
    schreibe("eingang/abzug.csv", "a;b\n1;2\n")
    schreibe("abgeleitet/diagnostics/gate_entscheid_am6.gate.json", {
        "gate": "entscheid.A-M6", "status": "passed", "input_hashes": {},
        "summary": {"command_line": [
            str(fall), "--linie", "/home/nutzer/apps/welt-x/linie", "--repo", str(tmp_path),
            "--zeichnungsordnung", "/home/nutzer/.rechner-pipeline-schluessel/zo.json",
            # Der Anker liegt in einem Laufverzeichnis ausserhalb des Falls:
            "--anker", "/home/nutzer/git/baum-y/runs/anker-2026/anker.jsonl",
            # Ein Nachbar mit demselben Praefix ist nicht der Baum:
            "--nachbar", f"{tmp_path}-nachbar/x"]}})
    schreibe("abgeleitet/diagnostics/abox_validate.gate.json", {
        "gate": "P-Q3.fachliche-pruefung", "status": "passed", "input_hashes": {}, "summary": {}})
    alt = "entscheide/A-M6-" + "a" * 64 + ".json"
    neu = "entscheide/A-M6-" + "b" * 64 + ".json"
    # Die Schreibweise, die der Snapshot in Fall 3 traegt:
    schreibe(alt, {"gate": "A-M6", "entschieden_am": "2026-10-02T12:56:00+00:00",
                   "begruendung": "Vorbereitung eines DAA-Worskhops am 6.10.2026"})
    # Der geltende bindet das Eingangsregister ueber dessen Pruefsumme, das
    # Protokoll seiner Zeichnung nicht (es entsteht mit ihr).
    schreibe(neu, {"gate": "A-M6", "entschieden_am": "2026-10-02T15:28:00+00:00",
                   "begruendung": "Auftrag erteilt.",
                   "artefakt_hashes": {"eingang.json": _sha(fall / "eingang.json")}})
    return fall, _modell(fall), alt, neu


def _sha(pfad: Path) -> str:
    import hashlib
    return hashlib.sha256(pfad.read_bytes()).hexdigest()


def test_die_bereinigung_ersetzt_hostpfade_nach_regel_und_haelt_den_ueberholten_snapshot_zurueck(
        tmp_path: Path):
    """Entscheid des Maintainers (03.10.2026): Die Belege bleiben, wie sie
    gebunden sind; bereinigt wird die veroeffentlichte Fassung — nach Regel,
    mit Manifest. Ein Snapshot wird nie veraendert: Der ueberholte mit einer
    Angabe, die nicht auf die Seite gehoert, bleibt aus und steht benannt
    da. Was keine Regel kennt, findet die Wache — mit Positivkontrolle."""
    fall, modell, alt, neu = _fall_mit_hostpfaden(tmp_path)
    ziel = tmp_path / "seite"
    kopiert, bericht = vz._kopiere(fall, ziel, modell)

    protokoll = ziel / "artefakte/abgeleitet/diagnostics/gate_entscheid_am6.gate.json"
    assert json.loads(protokoll.read_text(encoding="utf-8"))["summary"]["command_line"] == [
        "<baum>/faelle/probe", "--linie", "<welt>/linie", "--repo", "<baum>",
        "--zeichnungsordnung", "<schluesselverzeichnis>/zo.json",
        "--anker", "<laufordner>/anker.jsonl", "--nachbar", f"{tmp_path}-nachbar/x"]
    eintraege = {x["original"]: x for x in bericht["bereinigt"]}
    assert set(eintraege) == {"abgeleitet/diagnostics/gate_entscheid_am6.gate.json", "eingang.json"}
    e = eintraege["abgeleitet/diagnostics/gate_entscheid_am6.gate.json"]
    assert e["sha256_original"] == _sha(fall / e["original"])
    assert e["sha256_veroeffentlicht"] == _sha(protokoll)
    assert e["ersetzungen"] == {"<baum>": 2, "<welt>": 1, "<schluesselverzeichnis>": 1, "<laufordner>": 1}
    assert eintraege["eingang.json"]["ersetzungen"] == {"<welt>": 1}
    # Gebunden heisst: Ein Entscheid nennt die Pruefsumme des Originals. Das
    # Protokoll der Zeichnung bindet keiner (Gegenpruefung 03.10.2026).
    assert e["gebunden_von"] == [] and eintraege["eingang.json"]["gebunden_von"] == ["A-M6"]
    # Ohne Hostpfad bytegleich und nicht im Manifest:
    sauber = "abgeleitet/diagnostics/abox_validate.gate.json"
    assert _sha(ziel / "artefakte" / sauber) == _sha(fall / sauber)
    # Der ueberholte Snapshot bleibt aus, benannt mit seiner Pruefsumme; der
    # andere steht unveraendert da.
    assert f"artefakte/{alt}" not in kopiert and not (ziel / "artefakte" / alt).exists()
    assert [(x["original"], x["sha256"]) for x in bericht["zurueckgehalten"]] == [(alt, _sha(fall / alt))]
    assert _sha(ziel / "artefakte" / neu) == _sha(fall / neu)
    # Das Manifest liegt auf der Seite; derselbe Fall ergibt dieselben Bytes.
    manifest = (ziel / "artefakte" / br.MANIFEST).read_bytes()
    inhalt = json.loads(manifest)
    assert inhalt["bereinigt"] == sorted(bericht["bereinigt"], key=lambda x: x["datei"])
    assert [(x["original"], x["sha256"]) for x in inhalt["zurueckgehalten"]] == [(alt, _sha(fall / alt))]
    assert [r["platzhalter"] for r in inhalt["regeln"]] == ["<baum>", "<schluesselverzeichnis>", "<welt>", "<laufordner>"]
    vz._kopiere(fall, tmp_path / "zweimal", modell)
    assert (tmp_path / "zweimal" / "artefakte" / br.MANIFEST).read_bytes() == manifest
    # Die Wache findet nichts, die Pruefung rechnet das Manifest gegen den Fall nach.
    assert br.wache(ziel) == []
    assert br.pruefe(ziel, fall) == []
    # Positivkontrollen der Wache: je Marke und Wort eine Datei, dazu ein Name
    # allein und zwei komprimierte Formate, deren Rohbytes nichts verraten.
    import zlib
    import pyarrow as pa
    import pyarrow.parquet as pq

    a = ziel / "artefakte"
    (a / "eingeschleust.json").write_text('{"p": "/home/x/y"}', encoding="utf-8")
    (a / "maskiert.json").write_text('{"p": "\\/home\\/x"}', encoding="utf-8")
    (a / "agent.txt").write_text("/tmp/claude-1000/x\n", encoding="utf-8")
    (ziel / "notiz.md").write_text("Termin: Workshop\n", encoding="utf-8")
    (ziel / "Workshop.txt").write_text("leer\n", encoding="utf-8")         # der Name allein
    # gzip kodiert auch einen kurzen Wert so, dass er in den Rohbytes nicht steht.
    pq.write_table(pa.table({"quelle": ["/home/x/apps/y/z.csv"] * 50}), a / "daten.parquet",
                   compression="gzip", write_statistics=False)
    (a / "brief.pdf").write_bytes(b"%PDF-1.4\n1 0 obj<</Filter/FlateDecode>>stream\n"
                                  + zlib.compress(b"BT (Workshop) Tj ET") + b"\nendstream\nendobj\n")
    assert b"/home/" not in (a / "daten.parquet").read_bytes()
    assert b"workshop" not in (a / "brief.pdf").read_bytes().lower()
    assert br.wache(ziel) == [
        ("Workshop.txt", "workshop"), ("artefakte/agent.txt", "/tmp/claude"),
        ("artefakte/brief.pdf", "workshop"), ("artefakte/daten.parquet", "/home/"),
        ("artefakte/eingeschleust.json", "/home/"), ("artefakte/maskiert.json", "\\/home\\/"),
        ("notiz.md", "workshop")]
    assert br.main(["--wache", str(ziel)]) == 1
    for name in ("eingeschleust.json", "maskiert.json", "agent.txt", "daten.parquet", "brief.pdf"):
        (a / name).unlink()
    # Was die Wache nicht lesen kann, hat sie nicht geprueft — ein Befund.
    (a / "kaputt.parquet").write_bytes(b"PAR1 kein Parquet PAR1")
    assert [m for rel, m in br.wache(ziel) if rel == "artefakte/kaputt.parquet"][0].startswith(
        "Parquet nicht lesbar")
    (a / "kaputt.parquet").unlink()
    protokoll.write_bytes(protokoll.read_bytes().replace(b"<welt>", b"<WELT>"))
    assert any("weicht vom Manifest ab" in f for f in br.pruefe(ziel, fall))
    (ziel / "artefakte" / sauber).write_text("{}", encoding="utf-8")
    assert any(f.startswith(f"artefakte/{sauber}: nicht im Manifest") for f in br.pruefe(ziel, fall))


def test_ein_geltender_snapshot_oder_eine_binaerdatei_mit_befund_haelt_den_bau_an(tmp_path: Path):
    """Ein geltender Snapshot wird weder bereinigt (seine Signatur) noch
    still weggelassen — ob er fehlen darf, entscheidet ein Mensch. Ebenso
    haelt eine Datei an, die einen Hostpfad traegt und kein Text ist: Eine
    Ersetzung zerbraeche ihr Format."""
    fall, modell, alt, neu = _fall_mit_hostpfaden(tmp_path)
    for e in modell["kette"]["entscheide"]:
        e["geltend"] = e["snapshot_datei"] == alt
    with pytest.raises(vz.VeroeffentlichungFehler, match="geltender Entscheid-Snapshot"):
        vz._kopiere(fall, tmp_path / "seite", modell)
    # Einer, den das Modell nicht kennt, verschwindet ebenso wenig still.
    bekannt = modell["kette"]["entscheide"]
    modell["kette"]["entscheide"] = [e for e in bekannt if e["snapshot_datei"] != alt]
    with pytest.raises(vz.VeroeffentlichungFehler, match="unbekannter Entscheid-Snapshot"):
        vz._kopiere(fall, tmp_path / "seite1", modell)
    modell["kette"]["entscheide"] = bekannt
    for e in modell["kette"]["entscheide"]:
        e["geltend"] = e["snapshot_datei"] == neu
    (fall / "abgeleitet" / "vorverdichtung").mkdir(parents=True)
    (fall / "abgeleitet" / "vorverdichtung" / "x.parquet").write_bytes(
        b"PAR1 /home/nutzer/apps/welt-x/y PAR1")
    modell["belegkette"] = fd.belegkette(fall)
    with pytest.raises(vz.VeroeffentlichungFehler, match="kein Text"):
        vz._kopiere(fall, tmp_path / "seite2", modell)


def test_die_wache_haelt_den_bau_der_fallseite_an(tmp_path: Path, capsys):
    """Ein Hostpfad, den keine Regel kennt, wird nicht still ersetzt: Die
    Fallseite endet mit Exit 1 und nennt Datei und Marke. Gegenprobe: ohne
    ihn steht die Seite (Exit 3 — der Probefall hat Luecken)."""
    fall, modell, alt, neu = _fall_mit_hostpfaden(tmp_path)
    daten = tmp_path / "daten.json"
    daten.write_text(json.dumps(modell), encoding="utf-8")
    argv = ["--fall", str(fall), "--daten", str(daten), "--als-unterseite"]
    assert vz.main(argv + ["--out", str(tmp_path / "ohne")]) in (0, 3)
    ledger = fall / "abgeleitet/diagnostics/abox_validate.gate.json"
    ledger.write_text(json.dumps({"gate": "P-Q3.fachliche-pruefung", "status": "passed",
                                  "input_hashes": {}, "summary": {"ort": "/home/nutzer/anderswo/x"}}),
                      encoding="utf-8")
    daten.write_text(json.dumps(_modell(fall)), encoding="utf-8")
    capsys.readouterr()
    assert vz.main(argv + ["--out", str(tmp_path / "mit")]) == 1
    assert ("Wache: artefakte/abgeleitet/diagnostics/abox_validate.gate.json traegt '/home/'"
            in capsys.readouterr().err)


def test_die_seite_sagt_offen_was_bereinigt_und_was_zurueckgehalten_ist(tmp_path: Path):
    """Die Kette bleibt ueber das Manifest nachvollziehbar statt ueber
    identische Bytes — und die Seite sagt das: Kapitel mit Tabelle, Vermerk
    in der Liste der Station, Status auf der Seite der Snapshots."""
    import re

    fall, modell, alt, neu = _fall_mit_hostpfaden(tmp_path)
    kopiert, bericht = vz._kopiere(fall, tmp_path / "seite", modell)
    seite = _fallseite(fall, modell, tmp_path, kopiert, None, unterseite=True, bereinigt=bericht)
    seiten = vz._seiten(fall, modell, tmp_path, kopiert, None, unterseite=True, bereinigt=bericht)
    # Das Verzeichnis ist eine eigene Seite; die Fallseite verweist nur.
    assert "## Bereinigt veröffentlicht {#bereinigt}" in seiten["belege.md"]
    assert "Bereinigt veröffentlicht" not in seiten["index.md"]
    assert "[Verzeichnis der Belege](belege.html)" in seiten["index.md"]
    assert f"[Bereinigungsmanifest](artefakte/{br.MANIFEST})" in seite
    # Je Datei, wer das Original bindet — keine Pauschale "gebunden".
    assert "| Datei | Original im Fall | gebunden von | veröffentlicht | ersetzt |" in seite
    assert "| [`eingang.json`](artefakte/eingang.json) | `" in seite
    zeile_e = next(z for z in seite.splitlines() if z.startswith("| [`eingang.json`]"))
    zeile_p = next(z for z in seite.splitlines() if "gate_entscheid_am6.gate.json`]" in z)
    assert '| <span class="kennung">A-M6</span> |' in zeile_e and "| keinem Entscheid |" in zeile_p
    assert "1 der 2 Originale bindet kein Entscheid" in seite
    assert "Original (gebunden)" not in seite and "die der Entscheid bindet" not in seite
    assert "die Ansichten der Lieferung sind Ansichten" in seite
    # Die Zaehlung der Station zaehlt Veroeffentlichtes und nennt das andere.
    assert re.search(r"\[Station 1 · [^\]]+\]\(\./#[^)]+\) — \d+ Dateien, dazu 1 nicht veröffentlicht", seite)
    assert f"Nicht veröffentlicht: `{alt}`" in seite
    assert "Snapshot A-M6 <small>(überholt, nicht veröffentlicht)</small>" in seite
    assert '(<a href="belege.html#bereinigt">bereinigt</a>)' in seite
    snaps = vz._entscheide_seite(fall, modell, kopiert, True, "2026-10-03",
                                 {"commit": "0" * 12, "branch": "test"}, bereinigt=bericht)
    # Die Zeile sagt den Status; die Pruefsumme steht ueber der Tabelle — eine
    # lange Zelle verbreiterte die Spalte ueber den Seitenrand (Sichtung 03.10.).
    zeilen = [z for z in snaps.splitlines() if "| überholt, nicht veröffentlicht |" in z]
    assert len(zeilen) == 1 and "](artefakte/" not in zeilen[0]
    assert f"Prüfsumme der Datei: A-M6 vom 2026-10-02 `{_sha(fall / alt)}`." in snaps
    assert '| <span class="kennung">A-M6</span> |' in zeilen[0]


def _verfaelsche(ziel: Path, fall: Path, alt: str, art: str) -> None:
    """Je Art eine Verfaelschung der gebauten Seite oder des Falls."""
    a = ziel / "artefakte"
    m_pfad = a / br.MANIFEST
    if art == "vorschau":
        v = a / "lieferung" / "abzug.csv.html"
        v.write_text(v.read_text(encoding="utf-8").replace("1", "9"), encoding="utf-8")
    elif art == "untergeschoben":
        (a / "abgeleitet" / "fremd.json").write_text("{}", encoding="utf-8")
    elif art == "umbenannt":
        (a / "abgeleitet" / "kopie.json").write_bytes((fall / alt).read_bytes())
    elif art == "fehlt":
        (a / "abgeleitet" / "diagnostics" / "abox_validate.gate.json").unlink()
    elif art == "unbereinigt":
        (a / "abgeleitet" / "diagnostics" / "abox_validate.gate.json").write_text("{}", encoding="utf-8")
    elif art in ("zahl", "bindung"):
        m = json.loads(m_pfad.read_text(encoding="utf-8"))
        for e in m["bereinigt"]:
            if e["original"] == "eingang.json":
                if art == "zahl":
                    e["ersetzungen"] = {"<welt>": 2}
                else:
                    e["gebunden_von"] = []
        m_pfad.write_text(json.dumps(m), encoding="utf-8")
    elif art == "original":
        (fall / "eingang.json").write_text('{"quellen": []}', encoding="utf-8")


@pytest.mark.parametrize("art, meldung", [
    ("vorschau", "die Vorschau entspricht nicht der Lieferung"),
    ("untergeschoben", "artefakte/abgeleitet/fremd.json: liegt auf der Seite, hat aber kein Gegenstueck"),
    ("umbenannt", "artefakte/abgeleitet/kopie.json: traegt die Bytes der zurueckgehaltenen Datei"),
    ("fehlt", "abgeleitet/diagnostics/abox_validate.gate.json: Beleg der Station 4 fehlt auf der Seite"),
    ("unbereinigt", "abox_validate.gate.json: nicht im Manifest, aber nicht bytegleich"),
    ("zahl", "artefakte/eingang.json: die Ersetzungszahlen weichen ab"),
    ("bindung", "eingang.json: die genannten Bindungen stimmen nicht mit der Belegkette"),
    ("original", "eingang.json: Original hat nicht die genannte Pruefsumme"),
])
def test_die_nachpruefung_findet_jede_verfaelschung(tmp_path: Path, art: str, meldung: str):
    """--pruefe ist die Nachpruefung, auf die Seite und README verweisen. Die
    Gegenpruefung (03.10.2026) fand sie gruen bei veraenderter Lieferung, bei
    untergeschobenen Dateien, bei einem fehlenden Beleg. Je Pruefung eine
    Verfaelschung, die genau sie ausloest; die unverfaelschte Seite besteht."""
    fall, modell, alt, neu = _fall_mit_hostpfaden(tmp_path)
    ziel = tmp_path / "seite"
    kopiert, _ = vz._kopiere(fall, ziel, modell)
    vz._lieferung_ansichten(fall, ziel, modell["lieferung"]["quellen"], kopiert)
    assert (ziel / "artefakte" / "lieferung" / "abzug.csv.html").is_file()
    assert br.pruefe(ziel, fall) == []
    _verfaelsche(ziel, fall, alt, art)
    fehler = br.pruefe(ziel, fall)
    assert any(meldung in f for f in fehler), fehler


def test_die_auslieferung_a_b1_steht_an_station_13(tmp_path: Path):
    """A-B1 gibt den Stand nach aussen frei; gezeichnet wird es mit --fall,
    Snapshot und Protokoll liegen im Fall. Ohne Station stuenden sie als
    "Arbeitsunterlagen" unter "Nicht auf dieser Seite" — die Abnahme, die die
    oeffentlichen Zahlen deckt, fehlte auf der Seite (Messung 03.10.2026).
    Jetzt: Station 13, veroeffentlicht, das Protokoll bereinigt, der
    Entscheid mit dem Gate benannt."""
    fall, _, alt, neu = _fall_mit_hostpfaden(tmp_path)
    ab1 = "entscheide/A-B1-" + "e" * 64 + ".json"
    (fall / ab1).write_text(json.dumps({
        "gate": "A-B1", "entscheid": "angenommen", "entschieden_am": "2026-10-04T09:00:00+00:00",
        "pflichtbelege": {"anker": ["a" * 64]}}), encoding="utf-8")
    (fall / "abgeleitet/diagnostics/gate_entscheid_ab1.gate.json").write_text(json.dumps({
        "gate": "entscheid.A-B1", "status": "passed", "input_hashes": {},
        "summary": {"command_line": [str(fall), "--gate", "A-B1"]}}), encoding="utf-8")
    ab2 = "entscheide/A-B2-" + "f" * 64 + ".json"
    (fall / ab2).write_text(json.dumps({
        "gate": "A-B2", "entscheid": "angenommen", "entschieden_am": "2026-10-02T16:35:00+00:00"}),
        encoding="utf-8")
    modell = _modell(fall)
    kette = modell["belegkette"]["dateien"]
    assert kette[ab1]["station"] == 13
    # Der Kasten der Karte zeigt den Snapshot des Haupt-Gates zuerst.
    import darstellung
    zeilen = darstellung.kasten_belege(modell, 13, lambda f: f, "#13")
    assert [z for z, _ in zeilen if z.startswith("Snapshot")][0] == "Snapshot A-B2"
    assert kette["abgeleitet/diagnostics/gate_entscheid_ab1.gate.json"]["station"] == 13
    kopiert, bericht = vz._kopiere(fall, tmp_path / "seite", modell)
    assert f"artefakte/{ab1}" in kopiert
    assert "abgeleitet/diagnostics/gate_entscheid_ab1.gate.json" in {x["original"] for x in bericht["bereinigt"]}
    seite = _fallseite(fall, modell, tmp_path, kopiert, None, unterseite=True, bereinigt=bericht)
    station_13 = seite.split("## Station 13 ", 1)[1].split("\n## ", 1)[0]
    assert "`A-B1` **Auslieferung**" in station_13
    assert "A-B1: Entscheid **angenommen** am 04.10.2026" in station_13
    assert f"(artefakte/{ab1})" in station_13
    assert "entscheide" not in modell["belegkette"]["ohne_station"]


def test_der_auftritt_bewacht_den_ganzen_push_baum(tmp_path: Path, monkeypatch):
    """Die Wache laeuft nach dem letzten Bauschritt ueber den ganzen
    Push-Baum — Stands-Paket und Fachdokumente eingeschlossen — und vor der
    Vorschau; ein Befund haelt die Kette an."""
    aufrufe: list = []
    monkeypatch.setattr(at, "_schritt",
                        lambda kommando, erlaubt=(0,): aufrufe.append(kommando) or 0)
    aus = tmp_path / "seite"
    argv = ["--fall", "f", "--name", "n", "--out", str(aus), "--vorschau", "vorschau"]
    assert at.main(argv) == 0
    assert [Path(k[1]).name for k in aufrufe] == [
        "falldaten.py", "vorzeigeseite.py", "unternehmensseite.py", "bereinigung.py", "vorschau.py"]
    assert aufrufe[3][2:] == ["--wache", str(aus)]
    aufrufe.clear()
    monkeypatch.setattr(at, "_schritt", lambda kommando, erlaubt=(0,): (
        aufrufe.append(kommando) or (1 if "--wache" in kommando else 0)))
    assert at.main(argv) == 1
    assert Path(aufrufe[-1][1]).name == "bereinigung.py"


# --------------------------------------------------------------------------- #
# Drift: das Urteil ueber den veroeffentlichten Stand
# --------------------------------------------------------------------------- #

import drift as dr  # noqa: E402


def _seitenrepo(tmp_path: Path) -> Path:
    """Ein Mini-Repo wie plv-fiktion: Zweig main traegt die Seite."""
    import subprocess
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args):
        subprocess.run(["git", *args], cwd=repo, check=True,
                       capture_output=True)

    git("init", "-q", "-b", "main")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "test")
    (repo / "index.md").write_text(
        "# Fall\n| Veröffentlicht | 2026-08-28 |\n"
        "| Systemstand | `alt` auf `main` |\nInhalt A\n", encoding="utf-8")
    (repo / "artefakte").mkdir()
    (repo / "artefakte" / "a.json").write_text('{"wert": 1}',
                                               encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "veroeffentlichter Stand")
    return repo


def _entwurf(tmp_path: Path, inhalt: str, wert: int) -> Path:
    entwurf = tmp_path / "entwurf"
    (entwurf / "artefakte").mkdir(parents=True, exist_ok=True)
    (entwurf / "index.md").write_text(
        f"# Fall\n| Veröffentlicht | 2026-08-31 |\n"
        f"| Systemstand | `neu` auf `vorzeige-url` |\n{inhalt}\n",
        encoding="utf-8")
    (entwurf / "artefakte" / "a.json").write_text(
        f'{{"wert": {wert}}}', encoding="utf-8")
    return entwurf


def test_volatile_stempel_sind_kein_drift(tmp_path: Path):
    """Datum und Systemstand aendern sich mit jedem Bau, ohne dass sich
    inhaltlich etwas bewegt haette. Ein Test, der darauf schluege,
    schluege immer — und wuerde abgeschaltet."""
    repo = _seitenrepo(tmp_path)
    entwurf = _entwurf(tmp_path, "Inhalt A", wert=1)

    assert dr.main(["--seite", str(entwurf), "--repo", str(repo)]) == 0


def test_inhaltliche_abweichung_ist_drift(tmp_path: Path, capsys):
    """Geaenderte, neue und verschwundene Dateien werden benannt; das
    Werkzeug urteilt nur — veroeffentlicht wird von Hand."""
    repo = _seitenrepo(tmp_path)
    entwurf = _entwurf(tmp_path, "Inhalt B", wert=2)
    (entwurf / "neu.md").write_text("Neue Seite\n", encoding="utf-8")

    code = dr.main(["--seite", str(entwurf), "--repo", str(repo)])
    aus = capsys.readouterr().out
    assert code == 1
    assert "GEAENDERT: index.md" in aus
    assert "GEAENDERT: artefakte/a.json" in aus
    assert "NEU: neu.md" in aus
    assert "menschliche Handlung" in aus


# --------------------------------------------------------------------------- #
# Grafik: der Befund ist der Regelfall
# --------------------------------------------------------------------------- #

import grafik  # noqa: E402


def test_ein_befund_faellt_nicht_aus_dem_bild():
    """Ein Maximum jenseits seiner Schranke steht in Kontrastfarbe und
    wird benannt; ein Abgrenzungsband ohne Karten behauptet keine
    Vollstaendigkeit, sondern nennt, was die Artefakte hergeben."""
    svg = grafik.toleranz([
        {"titel": "A-M1", "ist_max": 0.08, "ist_p95": 0.03,
         "grenze_max": 0.05, "grenze_p95": 0.02, "werte": 10},
        {"titel": "A-M4", "ist_max": 0.03, "ist_p95": 0.01,
         "grenze_max": None, "werte": 20},
    ])
    assert "ÜBER SCHRANKE" in svg
    assert grafik.KONTRAST in svg
    assert "Schranke je Prüfung" in svg

    band = grafik.abgrenzungsband([], ["Umbaubudget des Fall-Laufs"])
    assert "Lücke: Umbaubudget" in band
    leer = grafik.abgrenzungsband([], [])
    assert "keine Lücke aus" in leer and "Abschlussbericht" in leer


# --------------------------------------------------------------------------- #
# Falldaten: das Datenmodell einer Falldarstellung
# --------------------------------------------------------------------------- #


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


def test_das_modell_traegt_beschreibung_und_berichtsverweise(tmp_path: Path):
    """Die Vorzeigeseite konsumiert das Modell; was sie zeigt, muss es
    tragen — sonst bliebe sie fuer genau diese Reste ein zweiter Leser
    desselben Datenraums."""
    fall = _fall_mit_berichten(
        tmp_path,
        aktuartest={"anzahl": 1, "bestanden": 1, "fehlgeschlagen": 0,
                    "test_bestanden": True})
    (fall / "abgeleitet" / "berichte" / "aktuartest.html").write_text(
        "<p>Vorlage</p>", encoding="utf-8")
    # Der Bestandsbericht der Fortschreibung liegt NICHT unter berichte/,
    # sondern im Konventionspfad der Fortschreibung — gefunden wird er
    # ueber den Dateinamen, den stabileren Anker.
    nach = fall / "abgeleitet" / "bestand-nach"
    nach.mkdir()
    (nach / "bestandsbericht_nach_uebernahme.html").write_text(
        "<p>Fortschreibung</p>", encoding="utf-8")
    (fall / "fall.json").write_text(json.dumps(
        {"name": "probe", "beschreibung": "Ein Vorfuehrfall.",
         "scope": {"typ": "bestand"}}), "utf-8")

    modell = fd.sammle(fall, [])
    assert modell["fall"]["beschreibung"] == "Ein Vorfuehrfall."
    [t] = modell["abnahmen"]["aktuariell"]
    assert t["bericht"] == "abgeleitet/berichte/aktuartest.html"
    assert modell["abnahmen"]["bestandsberichte"] == [
        "abgeleitet/bestand-nach/bestandsbericht_nach_uebernahme.html"]
    # Ein abgeschlossener Fall traegt die Umbau-Messung IMMER: Ein Lauf,
    # dessen Umbau niemand gemessen hat, saehe sonst aus wie ein Lauf
    # ohne Umbau.
    assert modell["umbau"] == {"vorhanden": False}
    # Seit der Abnahme des Stands traegt ein Fall statt des Umbaubudgets die
    # Aenderungsbelege von Kern und Tarifwerk; fehlt beides, ist es eine Luecke.
    assert modell["systemaenderung"]["vorhanden"] is False
    assert any(l["gruppe"] == "systemaenderung" for l in fd.luecken(modell))


def test_die_finale_zeichnungskette_wird_abgeleitet(tmp_path: Path):
    """Der Abschluss-Snapshot (A-M4) bindet die Snapshots der
    Vorgaenger-Zeichnungen; die finale Kette ist damit ABLEITBAR, nicht
    kuratiert. Ueberholte Zeichnungsrunden bleiben als Historie im Fall
    (entscheide/ wird nie entfernt) und werden nachgeordnet gezeigt."""
    fall = _leerfall(tmp_path)
    verzeichnis = fall / "entscheide"
    verzeichnis.mkdir()

    def schreibe(name, gate, snap, wann, pflicht=None):
        (verzeichnis / name).write_text(json.dumps({
            "gate": gate, "entscheid": "angenommen", "rolle": "mensch",
            "entscheider": "plv-aktuar", "entschieden_am": wann,
            "snapshot_sha256": snap,
            "pflichtbelege": pflicht or {},
            "freigabe": {"schluessel_sha256": "f" * 64},
        }), encoding="utf-8")

    schreibe("A-M1-alt.json", "A-M1", "a" * 64, "2026-09-01T10:00:00")
    schreibe("A-M1-neu.json", "A-M1", "b" * 64, "2026-09-01T12:00:00")
    schreibe("A-M4-abschluss.json", "A-M4", "c" * 64, "2026-09-01T13:00:00",
             pflicht={"am1_snapshot": ["b" * 64],
                      "abnahmebericht": ["d" * 64]})

    k = fd.kette(fall)
    assert k["finale_kette_ableitbar"] is True
    flags = {(e["gate"], e["snapshot_sha256"]): e["in_finaler_kette"]
             for e in k["entscheide"]}
    assert flags[("A-M1", "b" * 16)] is True
    assert flags[("A-M4", "c" * 16)] is True
    assert flags[("A-M1", "a" * 16)] is False
    # Der Abnahmebericht ist gebunden, aber keine Zeichnung — er macht
    # die Kette nicht laenger.
    assert sum(1 for wert in flags.values() if wert) == 2

    # Die Seite zeigt EINE Tabelle, juengste zuerst, mit Status-Spalte:
    # final fuer die abgeleitete Kette, ueberholt fuer fruehere Runden.
    modell = fd.sammle(fall, [])
    seite = _fallseite(fall, modell, tmp_path, [], None)
    # Der Fallbericht fasst zusammen und verweist; die Tabelle mit neun
    # Spalten je Snapshot beherrschte sonst die Seite.
    assert "(entscheide.html)" in seite and "in der" in seite
    entscheide = vz._entscheide_seite(fall, modell, [], False, "2026-09-21",
                                      {"commit": "0" * 12, "branch": "test"})
    assert "finale Entscheidkette" in entscheide
    assert "| **final** |" in entscheide and "| überholt |" in entscheide
    assert entscheide.index("`" + "c" * 8 + "`") < entscheide.index("`" + "a" * 8 + "`")


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


def _controlling_fall3(**ueber) -> dict:
    """Das Controlling von Fall 3, wie das Modell es traegt: zwei Groessen am
    Uebernahmestichtag, eine am Kontrollstichtag, 23 beendende Vorfaelle."""
    je = {"bjb_stichtag_1": 834, "dk_stichtag_1": 834, "dk_stichtag_2": 811,
          "gevo_abl_monat_144": 7, "gevo_pex_monat_120": 2, "gevo_pex_monat_132": 4,
          "gevo_sto_monat_120": 7, "gevo_sto_monat_132": 7, "gevo_tod_monat_120": 2}
    je.update(ueber)
    return {"bestand": {"anzahl": 834, "abzuege": [
                {"deckkap": {"anzahl": 834}, "jbrutto": {"anzahl": 834}},
                {"deckkap": {"anzahl": 811}, "jbrutto": {"anzahl": 811}}]},
            "abnahmen": {"aktuariell": [], "controlling": {
                "stichtag_1": "2026-01-01", "stichtag_2": "2027-01-01", "je_groesse": je}}}


def test_der_pruefumfang_des_controllings_steht_als_ein_satz():
    """Fall 3 (gemessen 06.10.2026): Die 23 Vertraege ohne Deckungskapital zum
    Kontrollstichtag sind genau die Abgaenge; das ist keine Einschraenkung.
    Eine ist es, dass der dort gelieferte Jahresbeitrag nicht verglichen wird."""
    aus = fd.abgrenzungen(_controlling_fall3())
    eintrag, = aus
    satz = eintrag["satz"]
    assert "Deckungskapital und Jahresbeitrag aller 834 Verträge" in satz
    assert "für die 811 Verträge, die dann noch bestanden" in satz
    assert "für die 23 ausgeschiedenen (14 Rückkäufe, 7 Abläufe, 2 Todesfälle)" in satz
    assert satz.endswith("Nicht verglichen haben wir den zum 01.01.2027 gelieferten Jahresbeitrag.")
    assert "fehlt der Vergleich" not in satz and "_stichtag_" not in satz

    # Fehlen mehr Vertraege, als ausgeschieden sind, ist der Rest eine Luecke.
    eintrag, = fd.abgrenzungen(_controlling_fall3(dk_stichtag_2=801))
    assert "Für 10 Verträge, die nicht ausgeschieden sind, fehlt der Vergleich zum 01.01.2027." in eintrag["satz"]

    # Alles verglichen, jeder fehlende Vertrag ausgeschieden: nichts zu sagen.
    assert fd.abgrenzungen(_controlling_fall3(bjb_stichtag_2=811)) == []

    # Liefert die abgebende Gesellschaft den Beitrag nicht, sagt der Satz das.
    modell = _controlling_fall3()
    modell["bestand"]["abzuege"][1]["jbrutto"] = {"anzahl": 0}
    eintrag, = fd.abgrenzungen(modell)
    assert eintrag["satz"].endswith(
        "Zum 01.01.2027 hat die abgebende Gesellschaft den Jahresbeitrag nicht geliefert.")


def test_ein_vorfallschluessel_ist_kein_stichtag():
    """Frueher zaehlte die Endung: "gevo_x_monat_1" galt als Groesse des
    ersten Stichtags. Gezaehlt wird jetzt das Muster."""
    modell = _controlling_fall3(bjb_stichtag_2=811, gevo_sto_monat_1=0, gevo_pex_monat_2=3)
    assert fd.abgrenzungen(modell) == []


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


def test_beide_ergebnis_namensschemata_werden_gelesen(tmp_path: Path):
    """Lauf 1 schrieb ergebnis.json, Lauf 2 schreibt
    <quelle>.ergebnis.json — ein Leser, der nur ein Schema kennt,
    meldet ein Loch, wo keines ist."""
    fall = _leerfall(tmp_path)
    verzeichnis = fall / "abgeleitet" / "transformation"
    verzeichnis.mkdir(parents=True)
    (verzeichnis / "abzug.spec.json").write_text(
        json.dumps({"felder": [], "quelle_datei": "abzug.csv"}),
        encoding="utf-8")
    (verzeichnis / "abzug.ergebnis.json").write_text(
        json.dumps({"zeilen_quelle": 834, "zeilen_ziel": 834,
                    "quellspalten": ["POLNR"]}), encoding="utf-8")

    t = fd.transformation(fall)
    assert t["zeilen_quelle"] == 834
    assert t["quellspalten"] == ["POLNR"]


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


# --------------------------------------------------------------------------- #
# Das Stands-Paket als Quelle der Unternehmensseiten (Tagesbetrieb, 8.3 / B8)
# --------------------------------------------------------------------------- #

def _stands_paket(tmp_path: Path) -> tuple:
    import hashlib
    paket = tmp_path / "paket"
    paket.mkdir()
    # Paketschema 5 (main): die Tagesseite und die bezeugten Berichte des
    # juengsten Abschlusses liegen in der Wurzel des Pakets.
    index = (b"<html><body><h1>Bestand heute</h1>"
             b'<a href="bestandsbericht_2026-09-01.html">Bericht</a></body></html>')
    bericht = b"<html><body>Bestandsbericht</body></html>"
    (paket / "index.html").write_bytes(index)
    (paket / "bestandsbericht_2026-09-01.html").write_bytes(bericht)
    betrieb = {
        "vorhanden": True, "stand": "2026-09-06", "gefuehrt_seit": "2026-01-01",
        "bestand": {"in_force": 2556, "je_produkt": {"klv": 1893, "bu": 663},
                    "uebernommen_in_force": 818, "policiert_beginn_folgt": 2},
        "neugeschaeft": {"seit_betriebsbeginn": 99, "woche_summe": 2},
        "geschaeftsentwicklung": {
            "zeitraeume": {
                "letztes_jahr": {"von": "2025-01-01", "bis": "2025-12-31", "ausserhalb_betrieb": True},
                "aktuelles_jahr": {"von": "2026-01-01", "bis": "2026-09-06", "ausserhalb_betrieb": False},
                "aktueller_monat": {"von": "2026-09-01", "bis": "2026-09-06", "ausserhalb_betrieb": False},
            },
            "je_zeitraum": {
                "letztes_jahr": {},
                "aktuelles_jahr": {
                    "ZUG": {"anzahl": 933, "je_herkunft": {"neugeschaeft": 99, "uebernahme": 834},
                            "betraege": {"VS": 62172288.0, "BU_Jahresrente": 208500.0},
                            "betraege_je_herkunft": {"neugeschaeft": {"VS": 7037000.0, "BU_Jahresrente": 208500.0},
                                                     "uebernahme": {"VS": 55135288.0}}},
                    "STO": {"anzahl": 38, "je_herkunft": {"fortschreibung": 38},
                            "betraege": {"RKW": 1538623.4}, "betraege_je_herkunft": {"fortschreibung": {"RKW": 1538623.4}}},
                },
                "aktueller_monat": {
                    "STO": {"anzahl": 5, "je_herkunft": {"fortschreibung": 5},
                            "betraege": {"RKW": 169828.6}, "betraege_je_herkunft": {"fortschreibung": {"RKW": 169828.6}}},
                },
            },
        },
        "buchungen": {"gesamt": 1460, "je_ereignis": {"ZUG": 933, "ERH": 257, "PEX": 174}},
        "abschluesse": [{"stichtag": "2026-09-01", "datei": "abschluss_2026-09-01.parquet",
                         "sha256": "9b" * 32, "bericht": "bestandsbericht_2026-09-01.html"}],
        "uebernahmen": [{"fall": "probe", "stichtag": "2026-01-01", "vertraege": 834,
                         "snapshot_sha256": "32" * 32}],
        "provenienz": {"manifest_sha256": "ed" * 32, "kern_version": "3.4.0", "pb1": "gruen"},
        "dateien": {"index.html": hashlib.sha256(index).hexdigest(),
                    "bestandsbericht_2026-09-01.html": hashlib.sha256(bericht).hexdigest()},
        "quelle": str(paket),
    }
    return paket, betrieb


def test_das_stands_paket_wird_gehalten_uebernommen_und_verlinkt(tmp_path: Path):
    """B8: Der gefuehrte Bestand kommt aus dem Stands-Paket — Dateien nur
    bytegleich zu stand.json und unveraendert uebernommen (das Paket ist in
    sich konsistent), Kennzahlen und Tabellen aus dem Modell."""
    paket, betrieb = _stands_paket(tmp_path)
    quellen = _quellseiten(tmp_path)
    (quellen / "index.md").write_text(
        "Fiktives Unternehmen\n\n# Willkommen\n"
        "{{zahl:betrieb.bestand.in_force}} in Kraft, Stand {{datum:betrieb.stand}}, "
        "Manifest {{hash:betrieb.provenienz.manifest_sha256}}\n"
        "{{svg:buchungen_je_art}}\n{{svg:bestand_je_produkt}}\n\n"
        "{{tabelle:buchungen_je_art}}\n\n{{tabelle:abschluesse}}\n\n"
        "{{tabelle:uebernahmen_im_stand}}\n", encoding="utf-8")
    modell = {"betrieb": betrieb}
    ziel = tmp_path / "seite"
    (ziel / "plv").mkdir(parents=True)
    (ziel / "plv" / "alt.html").write_text("Rest eines frueheren Stands", encoding="utf-8")
    assert us.stand(modell, ziel) == ["plv/bestandsbericht_2026-09-01.html", "plv/index.html"]
    assert (ziel / "plv" / "index.html").read_bytes() == (paket / "index.html").read_bytes()  # byteweise
    assert (ziel / "plv" / "bestandsbericht_2026-09-01.html").is_file()
    assert not (ziel / "plv" / "alt.html").exists()

    us.baue(quellen, ziel, modell)
    seite = (ziel / "index.md").read_text(encoding="utf-8")
    assert "2.556 in Kraft, Stand 06.09.2026, Manifest " + "ed" * 8 in seite
    assert "| Zugang | 933 |" in seite
    assert "[Monatsbericht zum 01.09.2026](plv/bestandsbericht_2026-09-01.html)" in seite
    assert "| probe | 01.01.2026 | 834 |" in seite
    # Die Uebernahme des eigenen Falls heisst wie auf der Startseite, nicht
    # wie ihr Verzeichnis (Nachpruefung 04.10.2026).
    us.baue(quellen, ziel, dict(modell, fall={"name": "probe"}))
    assert "| Probe | 01.01.2026 | 834 |" in (ziel / "index.md").read_text(encoding="utf-8")
    assert "KLV" in seite and "{{" not in seite
    # Eine Ebene tiefer zeigt derselbe Verweis nach oben.
    (quellen / "tiefer").mkdir()
    (quellen / "tiefer" / "index.md").write_text(
        "Fiktives Unternehmen\n{{tabelle:abschluesse}}\n", encoding="utf-8")
    us.baue(quellen, ziel, modell)
    assert "](../plv/bestandsbericht_2026-09-01.html)" in (
        ziel / "tiefer" / "index.md").read_text(encoding="utf-8")

    # Ohne Paket: Kennzahl unaufloesbar, mit dem Hinweis auf den Aufruf.
    with pytest.raises(vz.VeroeffentlichungFehler, match="stands-paket"):
        us.baue(quellen, tmp_path / "seite2", {"betrieb": {"vorhanden": False}})
    # Eine Datei, die nicht zu stand.json passt, wird nicht veroeffentlicht.
    (paket / "index.html").write_bytes(b"<html>manipuliert</html>")
    with pytest.raises(vz.VeroeffentlichungFehler, match="weicht von stand.json ab"):
        us.stand(modell, tmp_path / "seite3")


def test_die_vorschau_verlinkt_das_stands_paket_ganz(tmp_path: Path):
    import vorschau
    assert "plv" in vorschau.GANZ_VERLINKEN
    pytest.importorskip("markdown")  # Systempaket; die Vorschau laeuft mit python3
    seite = tmp_path / "seite"
    (seite / "plv").mkdir(parents=True)
    (seite / "plv" / "index.html").write_text("<p>Bestand heute</p>", encoding="utf-8")
    (seite / "index.md").write_text("# Start\n[Bestand heute](plv/)\n", encoding="utf-8")
    assert vorschau.main(["--seite", str(seite), "--out", str(tmp_path / "vorschau")]) == 0
    assert (tmp_path / "vorschau" / "plv").is_symlink()
    assert (tmp_path / "vorschau" / "plv" / "index.html").read_text(encoding="utf-8") == "<p>Bestand heute</p>"


def test_die_vorschau_gibt_ueberschriften_die_ids_von_pages():
    """Die Regel aus kramdown-parser-gfm (generate_gfm_header_id), mit der
    Pages jeder Ueberschrift ohne eigene id eine gibt: klein, Wortzeichen
    (auch Umlaute), Bindestrich, Leerzeichen und Tab bleiben, jedes
    Leerzeichen und jeder Tab einzeln ein Bindestrich, nichts zusammengefasst,
    nichts abgeschnitten; eine wiederkehrende id zaehlt -1, -2. Das Glossar
    verweist so auf seine Begriffe ([T-Box](#t-box))."""
    import vorschau
    assert vorschau._gfm_ids(["Schlüssel", "T-Box", "PLV und Baldrian", "T-Box", "T-Box",
                              "A-M4: die Abnahme (Gate)", "a  b\tc", " x "]) == [
        "schlüssel", "t-box", "plv-und-baldrian", "t-box-1", "t-box-2",
        "a-m4-die-abnahme-gate", "a--b-c", "-x-"]


def test_die_pruefgates_seite_kommt_aus_dem_register(tmp_path: Path):
    """Generiert, nicht gepflegt: Die Seite traegt jedes Gate des Registers
    mit seinem Ledger-Namen und die erzwungenen Vorgaenger von A-M4."""
    from rechner_pipeline.gates import register
    us.pruefgates(WERKZEUGE.parent, tmp_path)
    seite = (tmp_path / "migrationen" / "pruefgates.md").read_text(encoding="utf-8")
    assert "Fiktives Unternehmen" in seite and "# Unsere Prüfgates" in seite
    # Je Gate ein Sprungziel fuer die Verweise der Fallseite; ohne die
    # Entwicklerspalte Werkzeug, der Kopf mit Umlauten.
    assert '| <span id="A-M4"></span>**A-M4** `migrationscontrolling`' in seite
    assert "| Gate | Art | Stufe | Was geprüft bzw. abgenommen wird | Hinterlässt | Vorgänger (Tarif / Bestand) |" in seite
    assert "`gates.abox_merge`" not in seite and "Pruefung durch" not in seite
    for g in register.REGISTER:
        assert f"**{g.kennung}** `{g.name}`" in seite
    assert "P-Q3, A-Q1, A-M1, A-M2, A-M3, P-K1, A-K2, A-O1, A-T1, P-B1" in seite
    assert "{{" not in seite


def test_geschaeftsentwicklung_zeigt_anzahl_und_betrag_oder_benannten_platzhalter(tmp_path: Path):
    """Drei Sichten, zwei Bloecke; Neugeschaeft und Migration sind beide
    Zugaenge und werden ueber die Herkunft getrennt. Was das Journal nicht
    traegt (Bruttojahresbeitrag) oder nicht belegen kann (vor
    Betriebsbeginn), steht als Platzhalter da — nicht als Null."""
    _, betrieb = _stands_paket(tmp_path)
    html = us._html_baustein("geschaeftsentwicklung", {"betrieb": betrieb}, None)
    # Je Bezugsgroesse eine eigene Tabelle: Anzahl und Betrag nie in
    # derselben Zelle uebereinander.
    assert html.count("<table") == 4
    for titel in ("Neuzugang — Anzahl", "Neuzugang — Bruttojahresbeitrag",
                  "Leistungen — Anzahl", "Leistungen — ausgezahlte Leistung"):
        assert f"<caption>{titel}</caption>" in html
    assert "<b>99</b>" in html and "<b>834</b>" in html          # Neugeschaeft / Migrationen
    # Kein Ersatzbetrag: Wo der Bruttojahresbeitrag fehlt, steht die Luecke,
    # nicht die Versicherungssumme derselben Buchung.
    assert "nicht gebucht" in html and "Versicherungssumme" not in html
    assert "<b>1.539 Tsd. €</b>" in html and "<b>170 Tsd. €</b>" in html
    assert html.count("vor Betriebsbeginn") == 16                # 8 Zellen x 2 Tabellen
    assert "<b>0</b>" in html                                    # Ablauf im Monat: keine Buchung
    ohne = {"betrieb": {**betrieb, "geschaeftsentwicklung": {}}}
    with pytest.raises(KeyError, match="betrieb.seite"):
        us._html_baustein("geschaeftsentwicklung", ohne, None)


def test_migrationsbloecke_kommen_aus_dem_fallmodell(tmp_path: Path):
    modell = {
        "fall": {"name": "baldrian-klv-tg2015-lauf2"},
        "bestand": {"anzahl": 834, "abzuege": [{"deckkap": {"summe": 33437445.97}}],
                    "verteilungen": {"status_code": {"POL": 674, "PEX": 160},
                                     "produkt": {"klv": 834}, "tarif_generation": {"TG2015": 834}}},
        "abnahmen": {"aktuariell": [{"kennung": "A-M1", "titel": "Stichtagstest", "anzahl": 100,
                                     "bestanden": 100, "verteilung": {"max_abs_residuum": 0.0223},
                                     "grundtoleranz": {"max_abs_residuum": 0.05}}],
                     "controlling": {"stichtag_1": "2026-01-01", "anzahl": 834, "bestanden": 834,
                                     "pruefluecken": 0, "verteilung": {"anzahl_werte": 2508,
                                                                       "max_abs_residuum": 0.0315}}},
        "parameter": {"diskrepanzen": []},
    }
    ziel = tmp_path / "seite"
    (ziel / "migrationen" / "baldrian").mkdir(parents=True)
    (ziel / "migrationen" / "baldrian" / "index.md").write_text("# Fall", encoding="utf-8")
    html = us._html_baustein("migrationen_bloecke", modell, ziel, "../")
    assert "<h3>Baldrian KLV TG2015<small>abgeschlossen</small></h3>" in html
    assert "<tr><td>Zugangsdatum</td><td>01.01.2026</td></tr>" in html
    assert "33 Mio. €" in html                                   # gerundet, mit Einheit
    # Die Beschreibung endet mit den Kosten: keine Bestandsstruktur, keine
    # Abnahme-Kennzahlen — die stehen im Fallbericht.
    assert "beitragspflichtig" not in html and "Stichtagstest" not in html
    # Ohne Aufwand im Modell bleiben Dauer und Aufwand der Agenten offen;
    # eine Kostenzeile gibt es nicht (Maintainer 05.10.2026).
    assert html.count("noch nicht erfasst") == 2
    assert "Stunden" not in html and "Token" not in html
    assert 'href="../migrationen/baldrian/"' in html


def test_jede_seite_traegt_den_reiter(tmp_path: Path):
    quellen = _quellseiten(tmp_path)
    (quellen / "index.md").write_text(
        '<div class="banderole">Fiktives Unternehmen</div>\n# Willkommen\n', encoding="utf-8")
    (quellen / "aktuariat").mkdir()
    (quellen / "aktuariat" / "index.md").write_text(
        '# Aktuariat\n', encoding="utf-8")
    us.baue(quellen, tmp_path / "seite", {})
    start = (tmp_path / "seite" / "index.md").read_text(encoding="utf-8")
    tief = (tmp_path / "seite" / "aktuariat" / "index.md").read_text(encoding="utf-8")
    # Die Startseite fuehrt zu ihren Abschnitten, jede andere Seite zurueck.
    assert '<nav class="kopf"><a href="#ueber-uns">Über uns</a>' in start
    assert '<a href="#know-how">Unser Know-how</a></nav>' in start
    assert 'href="../aktuariat/"' not in start and "Startseite</a>" not in start
    assert tief.count('class="kopf"') == 1
    assert '<nav class="kopf"><a href="../">← Startseite</a></nav>' in tief
    assert start.count('class="kopf"') == 1
    # Der Reiter steht UNTER der Ueberschrift, nicht darueber: erst wissen,
    # wo man ist, dann wohin man springen kann. Das Stylesheet setzt das
    # Layout, nicht die Seite.
    assert tief.startswith("# Aktuariat\n\n<nav class=\"kopf\">")
    assert "stylesheet" not in tief
    # Die Fusszeile fuehrt hinter die Kulissen, mit der Tiefe der Seite:
    assert 'href="../hinter-den-kulissen/">Hinter den Kulissen' in tief
    assert 'href="hinter-den-kulissen/">Hinter den Kulissen' in start


def test_die_fallseite_erzaehlt_jede_station_mit_gate_und_geschehen(tmp_path: Path):
    """Station fuer Station auf EINER Seite: Gate aus dem Register (was es
    prueft, was es hinterlaesst) und das Geschehen aus dem Fallmodell —
    Anlaeufe, Ergebnis, Entscheid, ueberholte Runden, Befunde. Kein
    Erfolgspfad allein.

    Diese Erzaehlung stand bis zum Umbau in ``unternehmensseite._journey``
    und die Zahlen dazu auf einer zweiten Seite; sie ist hierher gewandert,
    nicht kopiert worden.
    """
    modell = {
        "fall": {"name": "baldrian-klv-tg2015-lauf2"},
        "lieferung": {"anzahl": 16, "anzahl_nachgereicht": 4},
        "transformation": {"vorhanden": True, "zeilen_quelle": 834, "zeilen_ziel": 834, "anzahl_quellspalten": 15,
                           "anzahl_zielfelder": 15, "nicht_uebernommen": ["a", "b", "c"], "befunde": []},
        "parameter": {"anzahl_diskrepanzen": 14, "diskrepanzen": [
            {"feld": "zins", "gewaehlt": "0.0125", "entscheider": "plv-aktuar", "begruendung": "Rechner massgeblich",
             "knoten": "klv/tg2015/zelle:x", "lesarten": [{"quelle": "a.pdf", "wert": "1"}, {"quelle": "b.xlsm", "wert": "2"}]}],
            "golden_master": {"werte_verglichen": 616, "abweichungen": 0, "zellen_gesamt": 6, "zellen_ohne_erwartungswerte": 5},
            "deckung": {"vorhanden": True, "pflichtfelder": 13, "zellen": 6, "pflicht_gesamt": 78, "belegt_quote": 1.0,
                        "zaehler": {"belegt": 78, "nicht_belegt": 0, "mehrdeutig": 0, "widerspruechlich": 0, "fehlt_in_extraktion": 0}}},
        "abnahmen": {"aktuariell": [{"kennung": "A-M1", "bestanden": 100, "anzahl": 100,
                                     "stichprobe": {"umfang": 100, "grundgesamtheit": 834, "profil": "geschichtet"},
                                     "verteilung": {"max_abs_residuum": 0.0223}, "grundtoleranz": {"max_abs_residuum": 0.05}}],
                     "controlling": {"anzahl": 834, "bestanden": 834, "pruefluecken": 0, "stichtag_1": "2026-01-01",
                                     "stichtag_2": "2027-01-01", "verteilung": {"anzahl_werte": 2508, "max_abs_residuum": 0.0315}}},
        "kette": {"anzahl_gate_laeufe": 14,
                  "gates": [{"gate": "P-Q2.zusammenfuehrung", "status": "passed", "versuch": 1, "ledger": "q.json"},
                            {"gate": "P-K1.golden-master", "status": "passed", "versuch": 2, "ledger": "k.json"},
                            {"gate": "P-Q3.fachliche-pruefung", "status": "passed", "versuch": 25, "ledger": "x.json"},
                            {"gate": "A-M4.migrationscontrolling", "status": "passed", "versuch": 11, "ledger": "y.json"}],
                  "entscheide": [
                      {"gate": "A-Q1", "entscheid": "angenommen", "entschieden_am": "2026-09-01T18:00:00", "rolle": "mensch",
                       "schluesselklasse": "nicht ausgewiesen (Schema 6)", "in_finaler_kette": False},
                      {"gate": "A-Q1", "entscheid": "angenommen", "entschieden_am": "2026-09-07T14:18:00", "rolle": "mensch",
                       "schluesselklasse": "simulation", "in_finaler_kette": True},
                      {"gate": "A-M4", "entscheid": "angenommen", "entschieden_am": "2026-09-07T14:19:00", "rolle": "mensch",
                       "schluesselklasse": "simulation", "in_finaler_kette": True, "artefakte_gebunden": 64}]},
        "verankerung": {"vorhanden": True, "getragen": 834, "vertraege": 834, "residuum_summe": -0.14, "residuum_max_abs": 0.02},
        "abgrenzungen": [{"was": "dk_stichtag_2 liegt nicht fuer jeden Vertrag vor", "zahlen": "811 von 834"}],
        "umbau": {"vorhanden": True, "gesamt": {"summe": 4269, "vorgabe": 18000}, "befunde": ["ein Stolperdraht"]},
        "betrieb": {"vorhanden": True, "stand": "2026-09-08", "bestand": {"in_force": 2556, "uebernommen_in_force": 818},
                    "uebernahmen": [{"stichtag": "2026-01-01", "vertraege": 834}]},
    }
    import darstellung

    seite = _fallseite(tmp_path / "faelle" / "probe", modell, tmp_path, [], None)
    # Jede Station EINMAL, mit Ueberschrift, Anker und Gate-Kasten.
    for nummer, titel, _ in darstellung.WEG_STATIONEN:
        anker = darstellung.STATION_ABSCHNITT[nummer]
        marke = f"## Station {nummer} · {titel} {{#{anker}}}"
        assert seite.count(marke) == 1, marke
    assert "`P-Q3` **Fachliche Prüfung**" in seite
    assert "Bestanden nach 25 Anläufen" in seite
    # Das Register steht einmal unter Pruefgates; die Station verweist nur.
    assert "*Prüft:*" not in seite and "pruefgates.html#P-Q3)" in seite
    assert "davon 1 echte Wertkonflikte" in seite
    # Wer entschieden hat, steht im Snapshot, nicht auf der Seite (Entscheid
    # des Maintainers 04.10.2026: die Seite spricht mit der Stimme des Hauses).
    assert "Beispiel zins: gewählt 0.0125." in seite and "plv-aktuar" not in seite
    assert "616 Werte gegen den Tarifrechner verglichen, 0 Abweichungen" in seite
    assert ("78 von 78 Pflichtfeldern belegt — 13 Pflichtparameter aus dem "
            "Begriffsmodell mal 6 Merkmalszellen") in seite
    assert "fehlt in der Extraktion 0" in seite
    assert "Geschützt ist die Feldliste, nicht die Zellenzahl" in seite
    assert "gegen sie rechnet der Rechenkern an Station 7 616 Werte nach" in seite
    assert "100 von 100 bestanden (Stichprobe 100 von 834, geschichtet)" in seite
    assert "Entscheid **angenommen** am 07.09.2026, Rolle mensch" in seite
    assert "Schlüsselklasse simulation" not in seite
    assert "1 frühere Runde überholt" in seite
    assert "bindet 64 Artefakte" in seite
    assert "Zum 01.01.2026 treten 834 Verträge" in seite
    # Was nicht glatt lief, steht nicht in einem Kasten am Rand, sondern
    # in den beiden Kapiteln, die dafuer da sind.
    assert "811 von 834" in seite and "ein Stolperdraht" in seite
    # Die Einleitung der Stationen verweist auf Dauer und Aufwand, sobald der
    # Fall sie traegt, vorher nicht (05.10.2026).
    assert "Nach den Stationen" in seite and "[Dauer und Aufwand](#aufwand)" not in seite
    modell["aufwand"] = {"dauer": None, "agenten": {"summe": _SUMME_FALL3, "je_rolle": _JE_ROLLE_FALL3}}
    assert "[Dauer und Aufwand](#aufwand)" in _fallseite(
        tmp_path / "faelle" / "probe", modell, tmp_path, [], None)


def _entscheid(gate: str, rolle: str = "mensch/aktuariat", klasse: str = "simulation",
               final: bool = True) -> dict:
    return {"gate": gate, "rolle": rolle, "schluesselklasse": klasse,
            "mandat_sha256": "ab" * 32 if klasse == "simulation" else None,
            "entscheid": "angenommen", "entschieden_am": "2026-09-20T14:24:12+00:00",
            "in_finaler_kette": final}


def test_rollen_wer_vorlegt_und_wer_zeichnet_ist_gemessen(tmp_path: Path):
    """Die Agentenrollen aus ihren Definitionen, je Rolle die menschliche
    Gegenrolle (ADR-018: derselbe Name, andere Ebene), und wer im Fall
    gezeichnet hat aus den Snapshots — ob eine Agentenrolle einen Entscheid
    traegt, ist ein Messergebnis. Mutationsprobe: ein Entscheid mit
    Agentenschluessel macht aus der Pointe einen Befund.

    Bis 2026-09-22 las rollen() faelle/zeichnungsordnung.json — Schema 1,
    das models.zeichnung seit ADR-018 abweist. Die Seite zeigte plv-aktuar,
    plv-it und "mensch" mit allen Gates; keine dieser Rollen gibt es noch,
    und das Gate A-K1 ebenso wenig. Der Test hier pinnt deshalb die
    QUELLE: Snapshots und Definitionen, keine Ordnungsdatei.
    """
    import falldaten as fd
    from rechner_pipeline.models.zeichnung import GUELTIGE_GATES

    fall = tmp_path / "faelle" / "probe"
    fall.mkdir(parents=True)
    # Eine Schema-1-Ordnung liegt daneben und darf NICHTS bewirken.
    (tmp_path / "faelle" / "zeichnungsordnung.json").write_text(json.dumps({
        "schema_version": 1, "rollen": {
            "plv-it": {"schluessel_sha256": "9c" * 32, "gates": ["A-K1"]},
            "mensch": {"schluessel_sha256": "ea" * 32, "gates": ["*"]}}}), encoding="utf-8")
    kette = {"entscheide": [
        _entscheid("A-M1", rolle="mensch", klasse="nicht ausgewiesen (Schema 6)", final=False),
        _entscheid("A-Q1"), _entscheid("A-M1"), _entscheid("A-M4")]}
    r = fd.rollen(fall, kette)
    assert r["vorhanden"] and [a["name"] for a in r["agenten"]] == [
        "aktuariat", "architektur", "betrieb", "programmleitung", "rechenkern"]
    assert all(a["zeichnet_nie"] or a["entscheidet_nie"] for a in r["agenten"])
    assert sum(a["zeichnet_nie"] for a in r["agenten"]) >= 3
    # Ohne tools:-Zeile hat eine Definition alle Werkzeuge, nicht keines.
    assert all(a["werkzeuge"] for a in r["agenten"])
    assert [z["gate"] for z in r["zeichnungen"]] == ["A-Q1", "A-M1", "A-M4"]
    assert r["agenten_gezeichnet"] == [] and "migrationsfall-durchfuehren" in r["faehigkeiten"]
    assert "zeichnungsordnung" not in " ".join(r["gelesen_aus"])

    html = us._html_baustein("rollen", {"rollen": r}, None)
    assert "<b>Programmleitung</b><small>agent/programmleitung</small>" in html
    assert "<b>Verantwortlicher Aktuar</b><small>mensch/aktuariat</small>" in html
    assert "<b>Rechenkern-Verantwortung</b><small>mensch/rechenkern</small>" in html
    for tot in ("plv-it", "plv-aktuar", "A-K1", "alle Gates", "<b>mensch</b>"):
        assert tot not in html, tot
    # Gemessen im Fall: Entscheid, Datum und Rolle je Gate; die uebrigen
    # Gates laut ADR, und als solche gekennzeichnet. Schluesselklasse und
    # Mandat stehen im Snapshot, nicht auf der Seite (Entscheid des
    # Maintainers 04.10.2026) — die Entscheide hier tragen beides.
    assert ("<code>A-M4</code></td><td><b>Verantwortlicher Aktuar</b>" in html
            and "durch <code>mensch/aktuariat</code></td>" in html)
    for verraet in ("Simulationsschlüssel", "Schlüssel einer Person", "unter Mandat",
                    "Vorführung", "Sitzung"):
        assert verraet not in html, verraet
    # Jede Agentenrolle mit ihrem Satz der Seite, keine mit der englischen
    # Rohbeschreibung ihrer Definition (so stand bis 04.10. der Betrieb da).
    assert "<b>Betrieb</b><small>agent/betrieb</small>" in html
    assert not any(a["beschreibung"][:40] in html for a in r["agenten"])
    assert "<code>A-O1</code></td><td><b>IT-Verantwortung</b><small>mensch/architektur</small>" in html
    assert "kein Gegenstand dieser Übernahme" in html
    assert "3 geltende Entscheide in diesem Fall, jeder von einer menschlichen Rolle" in html
    assert 'class="befund"' not in html

    # Mutation: ein Agentenschluessel an einem finalen Entscheid.
    kette2 = {"entscheide": kette["entscheide"] + [_entscheid("A-M2", rolle="agent/rechenkern", klasse="agent")]}
    r2 = fd.rollen(fall, kette2)
    assert r2["agenten_gezeichnet"] == ["A-M2"]
    assert "<b>Befund:</b> Entscheid(e) durch eine Agentenrolle oder einen Agentenschlüssel: A-M2" \
        in us._html_baustein("rollen", {"rollen": r2}, None)

    # Faehigkeiten je Rolle sind GEMESSEN — an der Definition, nicht an
    # einer Liste — und die Ratsche laeuft in beide Richtungen: kein
    # Skill ohne Rolle, keine Rolle mit einem Skill, den es nicht gibt.
    assert [a["skills"] for a in r["agenten"] if a["name"] == "programmleitung"] == [["migrationsfall-durchfuehren"]]
    assert r["skills_ohne_rolle"] == [] and r["skills_unbekannt"] == []
    assert {sk for a in r["agenten"] for sk in a["skills"]} == set(r["faehigkeiten"])
    assert set(us.SKILL_TITEL) == set(r["faehigkeiten"]), (
        f"Skill ohne Satz bzw. Satz ohne Skill: {set(us.SKILL_TITEL) ^ set(r['faehigkeiten'])}")
    assert fd._skills_aus_definition(
        "x\n## Was du tust (Skills)\n- ``a-b``: eins\n- ``c``, dann ``a-b``\n## Naechstes\n``nein``") == ["a-b", "c"]
    assert "<td><code>migrationsfall-durchfuehren</code></td><td>Programmleitung</td>" in html
    # Werkzeuge: die Laufzeit liest die Lieferungen — gemessen an den
    # Importen, und jede gepinnte Bibliothek hat ihren Satz.
    bibs = {b["name"]: b for b in r["bibliotheken"]}
    assert bibs["openpyxl"]["module"] and bibs["pypdf"]["module"], "Excel- und PDF-Leser ohne Modul"
    assert set(us.BIBLIOTHEK_ZWECK) == set(bibs), set(us.BIBLIOTHEK_ZWECK) ^ set(bibs)
    assert "Rechenkern: alle Werkzeuge" in html and "<code>openpyxl</code>" in html

    # Ratsche: Jedes zeichenbare Gate hat eine zeichnende Rolle auf der
    # Seite — ein neues Gate faellt hier auf, statt still zu fehlen.
    assert set(us.GATE_ZEICHNER) == set(GUELTIGE_GATES), (
        f"Gates ohne Rolle bzw. ohne Gate: {set(us.GATE_ZEICHNER) ^ set(GUELTIGE_GATES)}")
    assert all(rolle in us.MENSCH_TITEL for rolle, _ in us.GATE_ZEICHNER.values())


def test_monatstabelle_zeigt_zahlen_erst_wenn_das_paket_sie_traegt():
    """Die Abschlusstabelle traegt die Monatszahlen, sobald das Stands-Paket
    sie liefert — vorher bleibt sie bei Stichtag und Bericht, statt zwoelf
    leere Spalten zu zeigen. Ein fehlendes Feld ist dabei eine Luecke und
    keine Null: Ein Abschluss aus einem Altlauf darf nicht "0 Zugaenge"
    behaupten.
    """
    ohne = {"betrieb": {"vorhanden": True, "abschluesse": [
        {"stichtag": "2026-08-01"}, {"stichtag": "2026-09-01"}]}}
    tab = us._generiert("tabelle", "abschluesse", ohne, None, "")
    assert tab.splitlines()[0] == "| Stichtag | Bericht |"
    assert "01.09.2026" in tab and "in Arbeit" not in tab   # kein Bericht = leere Zelle

    mit = {"betrieb": {"vorhanden": True, "abschluesse": [
        {"stichtag": "2026-08-01"},
        {"stichtag": "2026-09-01", "in_kraft": 2550, "zugaenge": 48, "leistungen": 11}]}}
    tab = us._generiert("tabelle", "abschluesse", mit, None, "")
    assert tab.splitlines()[0] == "| Stichtag | Verträge in Kraft | Zugänge | Leistungen | Bericht |"
    assert "| 01.09.2026 | 2.550 | 48 | 11 |" in tab
    # der Abschluss ohne Zahlen: leere Zellen, keine Nullen
    leer = [z for z in tab.splitlines() if z.startswith("| 01.08.2026")][0]
    assert leer.startswith("| 01.08.2026 |  |  |  |"), leer
    assert " 0 " not in leer
    # keine Spalte "Vorfaelle gesamt" — PEX ist weder Zugang noch Leistung
    assert "gesamt" not in tab.lower()


def test_bestandskennzahlen_kommen_aus_zwei_monatsabschluessen(tmp_path: Path):
    """Vertraege, Bruttojahresbeitrag und Deckungskapital je Produkt aus dem
    juengsten Abschluss und dem zwoelf Monate davor. Fehlt der aeltere,
    steht nur der juengste da — kein Ersatzstichtag."""
    betrieb = {"vorhanden": True, "abschluss_kennzahlen": {
        "aktuell": {"stichtag": "2026-09-01",
                    "je_produkt": {"klv": {"vertraege": 1893, "jahresbeitrag": 5_400_000.0, "deckungskapital": 91_000_000.0},
                                   "bu": {"vertraege": 656, "jahresbeitrag": 900_000.0, "deckungskapital": 3_000_000.0}},
                    "gesamt": {"vertraege": 2549, "jahresbeitrag": 6_300_000.0, "deckungskapital": 94_000_000.0}},
        "vorjahr": {"stichtag": "2025-09-01",
                    "je_produkt": {"klv": {"vertraege": 1100, "jahresbeitrag": 3_000_000.0, "deckungskapital": 70_000_000.0},
                                   "bu": {"vertraege": 600, "jahresbeitrag": 800_000.0, "deckungskapital": 2_500_000.0}},
                    "gesamt": {"vertraege": 1700, "jahresbeitrag": 3_800_000.0, "deckungskapital": 72_500_000.0}}}}
    md = us._generiert("tabelle", "bestand_kennzahlen", {"betrieb": betrieb})
    assert "| BU, 01.09.2026 | 656 | 900.000,00 € | 3.000.000,00 € |" in md
    assert "| KLV, 01.09.2025 | 1.100 |" in md
    assert "| Gesamt, 01.09.2026 | 2.549 |" in md and "| Gesamt, 01.09.2025 | 1.700 |" in md
    ohne = {"betrieb": {"vorhanden": True, "abschluss_kennzahlen": {"aktuell": betrieb["abschluss_kennzahlen"]["aktuell"]}}}
    md2 = us._generiert("tabelle", "bestand_kennzahlen", ohne)
    assert "01.09.2025" not in md2 and md2.count("01.09.2026") == 3
    with pytest.raises(KeyError, match="kein Monatsabschluss"):
        us._generiert("tabelle", "bestand_kennzahlen", {"betrieb": {"vorhanden": True}})


def test_belege_auf_vertragsebene_werden_geprueft_aber_nicht_veroeffentlicht(tmp_path: Path):
    """Das Paket ist der Nachweis, der Auftritt die Veroeffentlichung: Ein
    Tagesjournal (Police, Betrag, Buchungstag je Buchung) wird gegen
    stand.json gehalten, landet aber nicht im Push-Baum. Protokoll und
    Manifest bleiben — sie tragen keinen Vertrag. Mutationsprobe: ein
    manipuliertes Journal bricht den Bau, obwohl es nicht kopiert wird."""
    import hashlib
    paket, betrieb = _stands_paket(tmp_path)
    journal = b"PAR1-nicht-echt-aber-bytegleich"
    protokoll = b'{"heute": "2026-09-06"}\n'
    (paket / "tagesjournal.parquet").write_bytes(journal)
    (paket / "protokoll.jsonl").write_bytes(protokoll)
    betrieb = {**betrieb, "dateien": {**betrieb["dateien"],
               "tagesjournal.parquet": hashlib.sha256(journal).hexdigest(),
               "protokoll.jsonl": hashlib.sha256(protokoll).hexdigest()}}
    ziel = tmp_path / "seite"
    uebernommen = us.stand({"betrieb": betrieb}, ziel)
    assert "plv/protokoll.jsonl" in uebernommen and "plv/index.html" in uebernommen
    assert not any(n.endswith(".parquet") for n in uebernommen)
    assert not (ziel / "plv" / "tagesjournal.parquet").exists()
    assert (ziel / "plv" / "protokoll.jsonl").is_file()
    (paket / "tagesjournal.parquet").write_bytes(b"manipuliert")
    with pytest.raises(vz.VeroeffentlichungFehler, match="weicht von stand.json ab"):
        us.stand({"betrieb": betrieb}, tmp_path / "seite2")


def test_startseiten_diagramme_vergleichen_zwei_zeitraeume(tmp_path: Path):
    """Startseite statt Tabellen: je Kennzahl ein Balkenpaar. Der Bestand
    vergleicht zwei Monatsabschluesse, die Bewegung das laufende Jahr mit
    DEMSELBEN Abschnitt des Vorjahres — ein ganzes Vorjahr daneben saehe
    wie ein Einbruch aus. Zahlen gerundet mit Einheit."""
    _, betrieb = _stands_paket(tmp_path)
    betrieb = {**betrieb, "abschluss_kennzahlen": {
        "aktuell": {"stichtag": "2026-09-01",
                    "je_produkt": {"klv": {"vertraege": 1893, "jahresbeitrag": 7_789_315.59,
                                           "deckungskapital": 77_305_930.0},
                                   "bu": {"vertraege": 656, "jahresbeitrag": 464_970.9,
                                          "deckungskapital": 3_195_700.0}},
                    "gesamt": {"vertraege": 2549, "jahresbeitrag": 8_254_286.48,
                               "deckungskapital": 80_501_630.0}},
        "vorjahr": {"stichtag": "2025-09-01",
                    "je_produkt": {"klv": {"vertraege": 1044, "jahresbeitrag": 4_864_247.92,
                                           "deckungskapital": 43_288_817.0},
                                   "bu": {"vertraege": 649, "jahresbeitrag": 458_765.0,
                                          "deckungskapital": 3_432_295.0}},
                    "gesamt": {"vertraege": 1693, "jahresbeitrag": 5_323_013.16,
                               "deckungskapital": 46_721_112.0}}}}
    # Startseite: eine Kennzahl-Kachel mit Veraenderung, darunter der Anteil
    # nach Produkt — ein Balkendiagramm mit einem Balken waere keine Aussage.
    bestand = us._generiert("svg", "bestand_vergleich", {"betrieb": betrieb})
    # Zwei SVG, nicht eines: die breite Fassung und die fuers Telefon. Eine
    # feste viewBox schrumpft auf 390 px auf 40 Prozent — Schrift inbegriffen
    # —, und CSS kann eine viewBox nicht aendern. Das Stylesheet zeigt eine.
    assert bestand.count("kennzahl-kachel") == 1 and bestand.count("<svg") == 2
    assert 'class="nur-breit"' in bestand and 'class="nur-handy"' in bestand
    assert "<table" not in bestand and "Deckungskapital" not in bestand
    assert '<span class="wert">2.549</span>' in bestand
    assert "856 (+51 %) ggü. 01.09.2025" in bestand and 'class="delta auf"' in bestand
    assert "KLV 1.893" in bestand and "BU 656" in bestand
    # Vertiefung: drei Kacheln, Betraege gerundet mit Einheit.
    tief = us._generiert("svg", "bestand_vergleich_tief", {"betrieb": betrieb})
    assert tief.count("kennzahl-kachel") == 3
    assert "81 Mio. €" in tief and "8.254 Tsd. €" in tief

    betrieb["geschaeftsentwicklung"]["zeitraeume"]["vorjahr_bis_heute"] = {
        "von": "2025-01-01", "bis": "2025-09-06", "ausserhalb_betrieb": False}
    betrieb["geschaeftsentwicklung"]["je_zeitraum"]["vorjahr_bis_heute"] = {
        "ZUG": {"anzahl": 101, "je_herkunft": {"neugeschaeft": 101}},
        "ERH": {"anzahl": 140, "je_herkunft": {"fortschreibung": 140}}}
    zugang = us._generiert("svg", "zugang_vergleich", {"betrieb": betrieb})
    assert "2025 bis 06.09." in zugang and "2026 bis 06.09." in zugang
    # Zeit ist geordnet, nicht identisch: zwei Stufen EINER Rampe, nicht zwei Farben.
    assert "--zeit-frueher" in zugang and "--zeit-jetzt" in zugang
    assert "--serie-1" not in zugang
    assert ">Neugeschäft</text>" in zugang and ">Migrationen</text>" in zugang
    # Ohne den Vergleichszeitraum bricht der Bau mit dem Ausweg im Text.
    ohne = {"betrieb": {**betrieb, "geschaeftsentwicklung": {"zeitraeume": {}, "je_zeitraum": {}}}}
    with pytest.raises(KeyError, match="betrieb.seite"):
        us._generiert("svg", "zugang_vergleich", ohne)


def test_kurzformat_behaelt_zwei_stellen():
    """Gerundet, mit Einheit, ohne Nachkommastellen — aber nie so grob,
    dass aus 8,25 Millionen ein nichtssagendes '8 Mio.' wird."""
    from grafik import kurz
    assert [kurz(x) for x in (0, 834, 2550, 9999, 10_000, 465_000, 8_254_286, 80_501_630)] == [
        "0", "834", "2.550", "9.999", "10 Tsd.", "465 Tsd.", "8.254 Tsd.", "81 Mio."]
    # Stueckzahlen erst ab einer Million: "10 Tsd. Vertraege" klingt geschaetzt.
    assert [kurz(x, stueck=True) for x in (10_000, 999_999, 2_400_000, 24_000_000)] == [
        "10.000", "999.999", "2.400.000", "24 Mio."]


def test_jede_station_steht_an_genau_einer_stelle():
    """Die Regel der Fallseite, maschinell geprueft.

    Der Fall lag einmal auf dreizehn Seiten: "Der Weg der Uebernahme"
    erzaehlte die Stationen, ein Fallbericht erzaehlte sie nach, und die
    Belege lagen am Fuss einer dritten. Jede Umsortierung hat die
    Dopplung verschoben statt beseitigt, weil ZWEI Listen denselben Weg
    beschrieben.

    Jetzt gibt es eine: ``WEG_STATIONEN``. Sie setzt Nummer, Titel und
    Gate; ``STATION_ABSCHNITT`` gibt jeder Station ihren Anker; die
    Erzeugerfunktion haengt Geschehen, Zahlen und Belege daran. Dieser
    Test haelt fest, dass keine Station aus einer der Zuordnungen
    herausfaellt — eine neue Station faellt hier auf, auch wenn sie im
    Fallmodell einer Fixture keine Zeile erzeugt.
    """
    import re

    import darstellung

    nummern = [n for n, _, _ in darstellung.WEG_STATIONEN]
    assert nummern == list(range(1, len(nummern) + 1)), "Luecke in der Nummerierung"

    # Jede Station hat einen eigenen Anker. Vier Stationen lagen einmal
    # unter "wie-geprueft-wurde"; wer in der Uebersicht auf Station 10
    # klickte, landete bei Station 9.
    anker = [darstellung.STATION_ABSCHNITT[n] for n in nummern]
    assert len(set(anker)) == len(anker), f"Anker doppelt vergeben: {anker}"
    assert set(darstellung.STATION_ABSCHNITT) == set(nummern)

    # Und die Erzeugerfunktion spricht ueber dieselben Stationen: Das
    # Geschehen wird je Nummer geschrieben, die Zahlenbloecke werden je
    # Nummer eingehaengt. Eine Nummer, die es nicht gibt, faellt still
    # unter den Tisch — hier nicht.
    quelle = (WERKZEUGE / "vorzeigeseite.py").read_text("utf-8")
    ab = quelle.index("geschehen: Dict[int, List[str]] = {")
    bis = quelle.index("\n        aus: List[str] = []", ab)
    erzaehlt = {int(x) for x in re.findall(r"^\s+(\d+): \[", quelle[ab:bis], re.M)}
    assert erzaehlt == set(nummern), (
        "Stationen ohne Geschehen bzw. Geschehen ohne Station: "
        f"{sorted(set(nummern) ^ erzaehlt)}")

    montage = quelle[quelle.index("z += _stationen({"):]
    montage = montage[:montage.index("})")]
    eingehaengt = {int(x) for x in re.findall(r"(\d+): s_", montage)}
    assert eingehaengt <= set(nummern), (
        f"Zahlenblock an einer Station, die es nicht gibt: {eingehaengt}")


def test_der_prozessplan_nennt_jede_station_genau_einmal_mit_ihrem_anker():
    """Dreizehn Kaesten aus WEG_STATIONEN — dieselbe Liste wie die
    Fallseite —, jeder mit Link auf seinen Anker; keine Station doppelt,
    keine vergessen."""
    import darstellung

    svg = darstellung.prozess_stationen()
    nummern = [n for _, ns in darstellung.PROZESS_REIHEN for n in ns]
    assert sorted(nummern) == [n for n, _, _ in darstellung.WEG_STATIONEN]
    assert svg.count('<a href="baldrian/#') == 13
    for n in nummern:
        assert f'href="baldrian/#{darstellung.STATION_ABSCHNITT[n]}"' in svg
    assert svg.count("STATION ") == 13 and "A-M4" in svg and "P-Q2" in svg


def test_die_festlegung_des_eigenen_hauses_folgt_dem_herkunftspfad_des_registers(tmp_path: Path):
    """Station 1 trennt die Lieferung der abgebenden Gesellschaft von den
    Festlegungen des uebernehmenden Hauses — gelesen am Herkunftspfad, den
    ``fall.registrieren`` ins Register schreibt. Registriert wird mit dem
    Produzenten selbst, nicht mit einem selbstgebauten Register: Aendert
    sich, wie der Herkunftspfad geschrieben wird (die Hostpfade in den
    Belegen sind ein offener Befund, 03.10.2026), wird dieser Test rot,
    statt dass die Seite eine Festlegung still als Lieferung zaehlt."""
    import falldaten as fd
    from rechner_pipeline.fall import anlegen, registrieren

    fall = tmp_path / "faelle" / "probe"
    anlegen(fall, scope="bestand")
    fremd = tmp_path / "lieferung" / "abzug.csv"
    fremd.parent.mkdir()
    fremd.write_text("a;b\n1;2\n", encoding="utf-8")
    eigen = fall / "abgeleitet" / "festlegung.md"
    eigen.parent.mkdir(parents=True, exist_ok=True)
    eigen.write_text("# Festlegung\n", encoding="utf-8")
    registrieren(fall, fremd)
    registrieren(fall, eigen)
    lieferung = fd.lieferung(fall)
    assert {q["datei"]: q["eigenes_haus"] for q in lieferung["quellen"]} == {
        "abzug.csv": False, "festlegung.md": True}
    assert lieferung["anzahl_eigenes_haus"] == 1


def _belegfall(tmp_path: Path) -> Path:
    """Ein Fall, dessen Belegkette jede Regel einmal trifft — gebaut aus
    Ledgern und Snapshots in der Gestalt, die die Gates schreiben."""
    import hashlib

    fall = tmp_path / "faelle" / "probe"

    def schreibe(rel: str, inhalt) -> str:
        p = fall / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        daten = inhalt if isinstance(inhalt, bytes) else (
            inhalt if isinstance(inhalt, str) else json.dumps(inhalt)).encode("utf-8")
        p.write_bytes(daten)
        return hashlib.sha256(daten).hexdigest()

    schreibe("fall.json", {"name": "probe", "scope": {"typ": "bestand"}})
    schreibe("eingang.json", {"quellen": [{"datei": "abzug.csv"}]})
    schreibe("eingang/abzug.csv", "a;b\n1;2\n")
    schreibe("eingang/fremd.csv", "nicht registriert\n")
    h_frag = schreibe("abgeleitet/abox/fragmente/f-meldung.json", {"f": 1})
    h_abox = schreibe("abgeleitet/abox/abox.json", {"abox": 1})
    schreibe("abgeleitet/protokoll/kopie-abox.json", {"abox": 1})        # dieselben Bytes
    schreibe("abgeleitet/protokoll/notiz.md", "Arbeitsnotiz des Agenten\n")
    schreibe("abgeleitet/protokoll/a-q1-dossier.md", "# Dossier\n")
    schreibe("abgeleitet/berichte/nur-gebunden.html", "<p>x</p>")
    h_kern = schreibe("abgeleitet/kern/aenderung.json", {"von_version": "1", "nach_version": "2"})
    schreibe("abgeleitet/kern/aenderung.md", "# Aenderung\n")
    h_suite = schreibe("abgeleitet/berichte/migrationssuite.json", {"suite": 1})
    h_spec = schreibe("abgeleitet/transformation/x.spec.json", {"spec": 1})
    # Die Vorverdichtung bindet kein Protokoll — sie steht trotzdem da, benannt.
    schreibe("abgeleitet/vorverdichtung/bestand-x.json", {"quelle_datei": "abzug.csv"})
    schreibe("abgeleitet/fachspez/rest.json", {"rest": 1})                  # Ort ohne Kette
    praefix = "faelle/probe/"
    schreibe("abgeleitet/diagnostics/abox_merge.gate.json", {
        "gate": "P-Q2.zusammenfuehrung", "status": "passed",
        "input_hashes": {praefix + "abgeleitet/abox/fragmente/f-meldung.json": h_frag},
        "summary": {"output_hashes": {praefix + "abgeleitet/abox/abox.json": h_abox}}})
    schreibe("abgeleitet/diagnostics/abox_merge.historie.jsonl", "{}\n")
    # Wie in Fall 3: Das Controlling liest die Spez der Uebersetzung.
    schreibe("abgeleitet/diagnostics/abnahmebericht.gate.json", {
        "gate": "A-M4.migrationscontrolling", "status": "passed",
        "input_hashes": {"abgeleitet/transformation/x.spec.json": h_spec}, "summary": {}})
    h_pq3 = schreibe("abgeleitet/diagnostics/abox_validate.gate.json", {
        "gate": "P-Q3.fachliche-pruefung", "status": "passed",
        "input_hashes": {"abgeleitet/abox/abox.json": h_abox}, "summary": {}})
    # Das Protokoll einer ZEICHNUNG nennt alles, was der Entscheid bindet —
    # gelesen zur Pruefung hat es nichts.
    schreibe("abgeleitet/diagnostics/gate_entscheid_aq1.gate.json", {
        "gate": "entscheid.A-Q1", "status": "passed",
        "input_hashes": {"abgeleitet/berichte/nur-gebunden.html": "0" * 64,
                         "abgeleitet/protokoll/notiz.md": "0" * 64}, "summary": {}})
    h_aq1 = schreibe("entscheide/A-Q1-" + "1" * 64 + ".json", {
        "gate": "A-Q1", "pflichtbelege": {}, "entschieden_am": "2026-10-02T10:00:00+00:00"})
    schreibe("entscheide/A-K2-" + "2" * 64 + ".json",
             {"gate": "A-K2", "pflichtbelege": {"kernaenderung": [h_kern]},
              "entschieden_am": "2026-10-02T10:30:00+00:00"})
    # Der Abschluss bindet den Snapshot von A-Q1 ueber die Pruefsumme der
    # Datei, den von A-K2 nicht.
    schreibe("entscheide/A-M4-" + "4" * 64 + ".json", {
        "gate": "A-M4", "entschieden_am": "2026-10-02T11:00:00+00:00",
        "artefakt_hashes": {"entscheide/A-Q1-" + "1" * 64 + ".json": h_aq1},
        "pflichtbelege": {"pq3_ledger": [h_pq3], "migrationssuite": [h_suite],
                          "kernstand": ["9" * 64]}})
    return fall


def test_die_belegkette_ordnet_jede_datei_nach_der_kette_zu(tmp_path: Path):
    """Welche Datei an welche Station gehoert, steht nicht in einer Tabelle
    von Hand, sondern folgt aus dem, was die Kette sagt — je Regel eine
    Zusicherung, und die Fallen dazu: Das Protokoll einer Zeichnung liest
    nichts, dieselben Bytes in einem Arbeitsordner sind eine Doublette, die
    Arbeitsunterlagen der Agenten gehoeren zu keiner Station."""
    import falldaten as fd

    k = fd.belegkette(_belegfall(tmp_path))
    station = {f: e["station"] for f, e in k["dateien"].items()}
    regel = {f: e["regel"] for f, e in k["dateien"].items()}
    assert station["eingang/abzug.csv"] == 1 and regel["eingang/abzug.csv"] == "Ort im Fall"
    assert station["abgeleitet/abox/fragmente/f-meldung.json"] == 2          # Ort, nicht "gelesen von P-Q2"
    assert station["abgeleitet/abox/abox.json"] == 3
    assert station["abgeleitet/diagnostics/abox_merge.gate.json"] == 3       # Pruefprotokoll
    assert station["abgeleitet/diagnostics/abox_merge.historie.jsonl"] == 3  # Geschwister
    # Pflichtbeleg der Abschlussabnahme: zur Station SEINES Gates (P-Q3), nicht A-M4.
    assert station["abgeleitet/diagnostics/abox_validate.gate.json"] == 4
    assert station["abgeleitet/berichte/migrationssuite.json"] == 12         # Beleg des Controllings
    # Ueber die Pruefsumme gefunden, nicht ueber einen Namen:
    assert station["abgeleitet/kern/aenderung.json"] == 7
    assert ("A-K2", "kernaenderung") in k["dateien"]["abgeleitet/kern/aenderung.json"]["rollen"]
    assert station["abgeleitet/kern/aenderung.md"] == 7                      # lesbare Fassung daneben
    # Die deterministische Extraktion gehoert zu "Quellen lesen", auch wenn
    # kein Protokoll sie ueber die Pruefsumme bindet — dann benannt.
    assert station["abgeleitet/vorverdichtung/bestand-x.json"] == 2
    assert k["dateien"]["abgeleitet/vorverdichtung/bestand-x.json"]["ungebunden"] is True
    assert "ungebunden" not in k["dateien"]["abgeleitet/abox/fragmente/f-meldung.json"]
    assert station["entscheide/A-M4-" + "4" * 64 + ".json"] == 12
    assert station["abgeleitet/transformation/x.spec.json"] == 6             # Ort, gelesen von A-M4
    assert station["abgeleitet/diagnostics/abnahmebericht.gate.json"] == 12
    # Die Fallen:
    assert station["abgeleitet/berichte/nur-gebunden.html"] is None         # nur von einer Zeichnung genannt
    assert k["dateien"]["abgeleitet/berichte/nur-gebunden.html"]["gelesen_von"] == []
    assert station["abgeleitet/protokoll/notiz.md"] is None
    assert station["abgeleitet/protokoll/a-q1-dossier.md"] is None          # ein Name bindet nichts
    assert station["abgeleitet/fachspez/rest.json"] is None                 # der Ort allein auch nicht
    assert station["eingang/fremd.csv"] is None                             # nicht registriert
    assert station["abgeleitet/protokoll/kopie-abox.json"] is None
    assert k["dateien"]["abgeleitet/protokoll/kopie-abox.json"]["doublette_von"] == "abgeleitet/abox/abox.json"
    # Gezaehlt, nicht gezeigt — die ganze Tabelle:
    assert k["ohne_station"] == {"abgeleitet/berichte": 1, "abgeleitet/fachspez": 1,
                                 "abgeleitet/protokoll": 3, "eingang": 1}
    # In Arbeit: die Station ohne Gate; keine Regression, wo kein Beleg sie als Ausnahme fuehrt.
    assert k["in_arbeit"] == {"6": ["Prüfung und Abnahme"]}
    assert set(k["je_station"]) == {str(n) for n in (1, 2, 3, 4, 5, 6, 7, 12)}


def test_der_abschluss_entscheid_nennt_die_snapshots_die_er_bindet(tmp_path: Path):
    """Welche Snapshots der Abschluss-Entscheid bindet, ist gemessen — die
    Pruefsumme der Snapshot-Datei steht in ihm —, nicht "alle vorangehenden
    Abnahmen" behauptet (so stand es bis zum 03.10.2026, ohne Messung). Ein
    geltender Entscheid davor, den er nicht bindet, steht benannt da."""
    import falldaten as fd
    import vorzeigeseite as vz

    k = fd.kette(_belegfall(tmp_path))
    am4 = next(e for e in k["entscheide"] if e["gate"] == "A-M4")
    assert am4["snapshots_gebunden"] == ["A-Q1"]
    for e in k["entscheide"]:
        e["geltend"] = True
    satz = vz._bindet_satz(am4, k["entscheide"])
    assert "darunter die Snapshots der Entscheide A-Q1." in satz
    assert "Nicht gebunden ist der Snapshot von A-K2, obwohl vor der Abschlussabnahme entschieden." in satz


def test_die_vokabulare_der_kette_sind_geschlossen():
    """Ein Gate ohne Station, eine Belegrolle ohne Titel: beides waere ein
    stiller Weg vorbei an der Seite. Hier faellt es laut (``==``)."""
    import darstellung
    import falldaten as fd
    from rechner_pipeline.gates import register
    from rechner_pipeline.models.belegrollen import BELEGROLLEN

    linie = {"A-B3"}   # zeichnet ausserhalb jedes Falls (ADR-025)
    assert set(fd.GATES_DER_LINIE) == linie
    assert set(darstellung.GATE_STATION) == {g.kennung for g in register.REGISTER} - linie
    # A-B1 nimmt die Linie ab, gezeichnet wird es im Fall: Station 13 (03.10.2026).
    assert darstellung.GATE_STATION["A-B1"] == 13
    rollen = {r for je_scope in BELEGROLLEN.values() for t in je_scope.values() for r in t}
    assert set(fd.ROLLE_TITEL) == rollen | set(register._BELEGROLLE_GATE)
    assert set(fd.BELEG_ARTEN) >= set(fd._MEHRFACH)


def test_der_prozessplan_zeigt_die_belege_der_kette_und_was_in_arbeit_ist(tmp_path: Path):
    """Jeder Kasten nennt Belege seiner Station aus der Belegkette des
    Modells (Bedingung des Projektteams: Artefakte IN den Kaesten). Verlinkt
    wird nur, was die Fallseite kopiert hat; "In Arbeit" steht nur, wo die
    Kette es sagt — ein nicht kopierter Beleg faellt weg, statt als "In
    Arbeit" zu erscheinen. Ohne Fall behauptet die Karte nichts."""
    ohne = us._html_baustein("prozess_stationen", {}, None, "")
    assert 'class="artefakt"' not in ohne and ">In Arbeit<" not in ohne

    snapshot = "entscheide/A-Q1-" + "1" * 64 + ".json"
    modell = {"belegkette": {
        "dateien": {
            snapshot: {"station": 5, "art": "entscheid", "titel": "Snapshot A-Q1"},
            "abgeleitet/protokoll/a-q1-dossier.md": {"station": 5, "art": "bericht", "titel": "Dossier je Diskrepanz"},
            "abgeleitet/abox/abox.json": {"station": 3, "art": "beleg", "titel": "A-Box, die Faktenbasis"},
            "abgeleitet/abox/coverage.json": {"station": 3, "art": "beleg", "titel": "Abdeckung je Pflichtfeld"},
            "abgeleitet/abox/fragmente/a.json": {"station": 2, "art": "fragment", "titel": "a.json"},
            "abgeleitet/abox/fragmente/b.json": {"station": 2, "art": "fragment", "titel": "b.json"},
        },
        "je_station": {"2": ["abgeleitet/abox/fragmente/a.json", "abgeleitet/abox/fragmente/b.json"],
                       "3": ["abgeleitet/abox/abox.json", "abgeleitet/abox/coverage.json"],
                       "5": [snapshot, "abgeleitet/protokoll/a-q1-dossier.md"]},
        "in_arbeit": {"6": ["Prüfung und Abnahme"]},
    }}
    ziel = tmp_path / "seite"
    fallseite = ziel / "migrationen" / "baldrian"
    (fallseite / "artefakte" / "abgeleitet" / "abox").mkdir(parents=True)
    (fallseite / "artefakte" / "abgeleitet" / "protokoll").mkdir(parents=True)
    (fallseite / "index.md").write_text("# Fall", encoding="utf-8")
    (fallseite / "artefakte" / "abgeleitet" / "abox" / "abox.json").write_text("{}", encoding="utf-8")
    (fallseite / "artefakte" / "abgeleitet" / "protokoll" / "a-q1-dossier.md.txt").write_text("x", encoding="utf-8")
    svg = us._html_baustein("prozess_stationen", modell, ziel, "../")
    assert 'href="../migrationen/baldrian/artefakte/abgeleitet/abox/abox.json"' in svg
    assert "Abdeckung je Pflichtfeld" not in svg                 # dieselbe Art: der erste genuegt
    assert 'href="../migrationen/baldrian/artefakte/abgeleitet/protokoll/a-q1-dossier.md.txt"' in svg
    assert "Quellfragmente (2)" in svg and 'href="../migrationen/baldrian/#quellen-lesen"' in svg
    assert "Snapshot A-Q1" not in svg                            # nicht kopiert: faellt weg
    assert svg.count(">In Arbeit<") == 1 and "Prüfung und Abnahme" in svg
    assert svg.count('class="artefakt"') == 6   # A-Box, alle 2 (St. 3), Dossier, alle 2 (St. 5), Fragmente, alle 2 (St. 2)
    assert svg.count('href="../migrationen/baldrian/#') == 13 + 4


def test_ein_leerer_fall_nennt_an_keiner_station_eine_zahl(tmp_path: Path):
    """Eine Zahl an einer Station ist eine Aussage ueber den Fall — sie steht
    nur, wenn ihre Quelle im Fall liegt. Am leeren Fall stand "0 von 0
    Vertraegen bestanden (None und None)", "0 Werte gegen den Tarifrechner
    verglichen" und ein Satz ueber einen Abschluss-Entscheid, den es nicht
    gab (03.10.2026). Die Invariante statt der Woerter: Im Fliesstext der
    Stationen eines leeren Falls steht keine Ziffer ausser in Gate-Namen.
    Gegenprobe: Am gefuellten Fall stehen Zahlen dort."""
    import re

    def fliesstext(seite: str) -> str:
        teil = seite.split("## Station 1 ", 1)[1].split("# Was herauskam", 1)[0]
        zeilen = [z for z in teil.splitlines()
                  if z and not z.startswith(("#", "`", "{:", "|", "<", "*", ">"))]
        return re.sub(r"\b[APB]-[A-Z]{1,2}\d\b", "", "\n".join(zeilen))

    fall = _fall_mit_berichten(tmp_path)
    modell = _modell(fall)
    ziffern = re.findall(r".{0,40}\d.{0,20}", fliesstext(_fallseite(fall, modell, tmp_path, [], None)))
    assert ziffern == []
    # Ohne Ziffer, aber derselbe Fehler: ein Satz ueber einen
    # Abschluss-Entscheid, den es nicht gibt.
    assert "Abschlussabnahme dieses Falls" not in _fallseite(fall, modell, tmp_path, [], None)
    # Gegenprobe: Ein einziger Lauf, und seine Zahlen stehen da.
    modell["kette"]["gates"] = [{"gate": "P-Q2.zusammenfuehrung", "status": "passed",
                                 "versuch": 3, "ledger": "x.json"}]
    assert "Bestanden nach 3 Anläufen" in fliesstext(_fallseite(fall, modell, tmp_path, [], None))


def test_die_fallseite_zeigt_je_gate_den_geltenden_entscheid(tmp_path: Path):
    """Die Menge der Gates, deren Entscheid die Stationen verlinken, ist die
    Menge der geltenden Entscheide des Modells — beidseitig (Merge-Strategie:
    Mengen statt Anzahl). Geltend ist der Entscheid der finalen Kette, sonst
    der juengste: Fallauftrag und Zugang stehen vor und nach der Kette und
    waren bis zum 03.10.2026 auf der Seite unsichtbar."""
    import re

    fall = _fall_mit_berichten(tmp_path)
    modell = _modell(fall)

    def e(gate, nr, final=False, geltend=False, am="2026-10-02T10:00:00+00:00"):
        return {"gate": gate, "entscheid": "angenommen", "rolle": "mensch/x",
                "schluesselklasse": "simulation", "entschieden_am": am,
                "snapshot_datei": f"entscheide/{gate}-{nr * 64}.json",
                "snapshot_sha256": nr * 16,
                "in_finaler_kette": final, "geltend": geltend or final,
                "strukturell_verifiziert": True, "verifikationsbefunde": [],
                "signatur_verifiziert": False, "artefakte_gebunden": 3, "pflichtbelege": []}

    modell["kette"]["entscheide"] = [
        e("A-M6", "a", am="2026-10-02T09:00:00+00:00"), e("A-M6", "b", geltend=True),
        e("A-K2", "c", geltend=True), e("A-Q1", "d", final=True), e("A-B2", "f", geltend=True)]
    kopiert = [f"artefakte/{x['snapshot_datei']}" for x in modell["kette"]["entscheide"]]
    seite = _fallseite(fall, modell, tmp_path, kopiert, None, unterseite=True)
    stationen = seite.split("## Station 1 ", 1)[1].split("# Was herauskam", 1)[0]
    verlinkt = set(re.findall(r"\(artefakte/entscheide/([A-Z]-[A-Z]\d)-([0-9a-f]{64})\.json\)", stationen))
    geltend = {(x["gate"], x["snapshot_datei"].rsplit("-", 1)[1][:64])
               for x in modell["kette"]["entscheide"] if x["geltend"]}
    assert verlinkt == geltend
    assert ("A-M6", "a" * 64) not in verlinkt                    # die fruehere Runde nicht
    assert "1 frühere Runde überholt" in stationen
    # Die Seite der Snapshots sagt dasselbe: geltend, nicht "ueberholt".
    snaps = vz._entscheide_seite(fall, modell, kopiert, True, "2026-10-03",
                                 {"commit": "0" * 12, "branch": "test"})
    zeilen = {re.search(r"\[`(\w)\w{7}`\]", z).group(1): z
              for z in snaps.splitlines() if z.startswith('| <span class="kennung">A-')}
    assert "| **geltend** |" in zeilen["b"] and "| **geltend** |" in zeilen["f"]   # Auftrag, Zugang
    assert "| **final** |" in zeilen["d"]                                        # A-Q1 in der Kette
    assert "| **geltend** |" not in zeilen["a"]                                  # die fruehere Runde
    # Die Seite nennt Schluesselklasse und Zweig nicht (Entscheid des
    # Maintainers 04.10.2026); der Prüfstand bleibt.
    assert "Schlüsselklasse" not in snaps and "(test)" not in snaps and "Prüfstand" in snaps


def test_der_prozessplan_bricht_bei_einer_zeile_die_nicht_in_den_kasten_passt():
    """Der Kasten ist 236 Pixel breit; was nicht hineinpasst, laeuft im
    Browser ueber den Rand und faellt keinem Test auf — deshalb bricht der
    Bau. Gegenprobe: der echte Text passt."""
    import darstellung

    alt = darstellung.PROZESS_STATIONEN_TEXT[7]
    darstellung.PROZESS_STATIONEN_TEXT[7] = (
        alt[0], "diese Zeile ist viel zu lang für einen Kasten von 236 Pixeln", *alt[2:])
    try:
        with pytest.raises(ValueError, match="passt nicht"):
            darstellung.prozess_stationen()
    finally:
        darstellung.PROZESS_STATIONEN_TEXT[7] = alt
    darstellung.prozess_stationen()


def _kaesten_der_karte(svg: str):
    """Die Kaesten der Prozesskarte, wie der Browser sie zeichnet:
    (Station, x, y, Breite, Hoehe) je Kasten, die Station aus dem Anker."""
    import re
    import darstellung

    station = {anker: n for n, anker in darstellung.STATION_ABSCHNITT.items()}
    return [(station[anker], *(float(v) for v in xywh))
            for anker, *xywh in re.findall(
                r'<a href="[^"#]*#([^"]+)" class="station"><title>[^<]*</title>'
                r'<rect x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="([\d.]+)"', svg)]


def test_die_prozesskarte_liest_sich_in_der_folge_der_stationen():
    """Funktional geteilt (Entscheid des Maintainers 04.10.2026): oben
    Auftrag und Lieferung, dann Quellenanalyse, Transformation und
    aktuarielle Abnahmen, unten der Zugang in die Buecher. Von oben nach
    unten und von links nach rechts gelesen kommen die Stationen in ihrer
    Nummernfolge — die fruehere Teilung in zwei Wege (oben 1 bis 5 und 7,
    unten 6 und 8 bis 13) las sich nicht so. Jeder Abschnitt steht als
    Ueberschrift ueber seiner Reihe und unter der vorigen."""
    import re
    import darstellung

    svg = darstellung.prozess_stationen()
    kaesten = _kaesten_der_karte(svg)
    assert len(kaesten) == 13
    gelesen = [n for n, _x, _y, _b, _h in sorted(kaesten, key=lambda k: (k[2], k[1]))]
    assert gelesen == list(range(1, 14))
    oben = {n: y for n, _x, y, _b, _h in kaesten}
    unten = {n: y + h for n, _x, y, _b, h in kaesten}
    vorige = 0.0
    for titel, nummern in darstellung.PROZESS_REIHEN:
        if titel:
            y = re.findall(rf'<text x="[\d.]+" y="([\d.]+)"[^>]*>{titel}</text>', svg)
            assert len(y) == 1 and vorige < float(y[0]) < min(oben[n] for n in nummern), titel
        vorige = max(unten[n] for n in nummern)


def test_die_prozesskarte_ist_so_breit_wie_ihre_breiteste_kastenreihe():
    """Die Breite der Karte folgt der breitesten Reihe von Kaesten, nicht
    der Zahl der Stationen: Mit vier Kaesten passt sie auf dem Bildschirm in
    die Textspalte, und die Schrift bleibt gross (vorher sieben Kaesten,
    1920 Pixel, mit der Mindestbreite von 1100 Pixeln auf 0,57 verkleinert
    und seitlich zu verschieben). Eine Reihe mit einer
    einzigen Station — Auftrag und Zugang — ist ein Balken genau ueber das
    Kastenraster. Nichts Gezeichnetes liegt ausserhalb des Bildes, auch
    nicht mit vollen Kaesten."""
    import re
    import darstellung

    # Je Station vier Belege verschiedener Art: drei Zeilen und der Verweis
    # auf alle — die hoechsten Kaesten, die es gibt.
    dateien, je_station = {}, {}
    for n in range(1, 14):
        for art in ("entscheid", "bericht", "beleg", "pruefprotokoll"):
            dateien[f"{n}/{art}"] = {"station": n, "art": art, "titel": f"{art} {n}"}
            je_station.setdefault(str(n), []).append(f"{n}/{art}")
    gefuellt = {"belegkette": {"dateien": dateien, "je_station": je_station}}
    balken = {ns[0] for _, ns in darstellung.PROZESS_REIHEN if len(ns) == 1}
    assert balken == {1, 13}
    for modell in (None, gefuellt):
        svg = darstellung.prozess_stationen(modell=modell, aufloesen=lambda ref: ref)
        breite, hoehe = (float(v) for v in re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg).groups())
        kaesten = _kaesten_der_karte(svg)
        assert len(kaesten) == 13
        links = min(x for _n, x, _y, _b, _h in kaesten)
        rechts = max(x + b for n, x, _y, b, _h in kaesten if n not in balken)
        assert breite == links + rechts                      # gleicher Rand links und rechts
        assert {n: (x, x + b) for n, x, _y, b, _h in kaesten if n in balken} == {
            n: (links, rechts) for n in balken}
        rechtecke = re.findall(r'<rect x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="([\d.]+)"', svg)
        texte = re.findall(r'<text x="([\d.]+)" y="([\d.]+)"', svg)
        assert len(rechtecke) == svg.count("<rect ") and len(texte) == svg.count("<text ")
        for x, y, b, h in rechtecke:
            assert float(x) >= 0 and float(x) + float(b) <= breite and float(y) + float(h) <= hoehe
        for x, y in texte:
            assert float(x) <= breite and 0 < float(y) <= hoehe
    assert svg.count(">alle 4 Belege der Station</text>") == 13      # die vollen Kaesten sind voll


def test_die_rueckfrageschleife_bricht_um_statt_ueber_den_rand_zu_laufen(monkeypatch):
    """Seit die Karte so breit ist wie vier Kaesten, passt die
    Rueckfrageschleife nicht mehr in eine Zeile. Sie bricht an Leerzeichen
    um; jede Zeile passt in ihr Feld, und kein Wort geht verloren —
    gemessen an dem Text, den die Karte uebergibt."""
    import html
    import re
    import darstellung
    import grafik

    echt, uebergeben = grafik.prozessplan, []
    monkeypatch.setattr(grafik, "prozessplan",
                        lambda reihen, band, *rest: uebergeben.append(band) or echt(reihen, band, *rest))
    svg = darstellung.prozess_stationen()
    feld = re.search(r'<rect x="([\d.]+)" y="[\d.]+" width="([\d.]+)" height="[\d.]+" rx="8" '
                     r'fill="#fdf0e6"[^>]*/>((?:<text [^>]*fill="#7a2e12">[^<]*</text>)+)', svg)
    rand = float(feld.group(1)) + float(feld.group(2))
    zeilen = [(float(x), html.unescape(t))
              for x, t in re.findall(r'<text x="([\d.]+)"[^>]*>([^<]*)</text>', feld.group(3))]
    assert len(zeilen) > 1
    assert " ".join(t for _, t in zeilen) == uebergeben[0]
    for x, t in zeilen:
        assert x + grafik._textbreite(t, 15) <= rand - 16, t



def test_die_kastenfarbe_sagt_wer_an_der_station_entscheidet():
    """Gelb, sobald an einer Station ein Mensch abnimmt — auch neben einer
    Programmpruefung als Haupt-Gate —, gruen, wo nur das Programm prueft,
    grau ohne eigenes Gate (Entscheid des Maintainers 04.10.2026). Bis
    dahin faerbte das Haupt-Gate allein: Station 7 (P-K1 mit A-K2, A-T1,
    A-O1) stand gruen da, obwohl dort drei Menschen abnehmen."""
    import re
    import darstellung
    import grafik

    svg = darstellung.prozess_stationen()
    anker = {a: n for n, a in darstellung.STATION_ABSCHNITT.items()}
    fuellung = {anker[a]: f for a, f in re.findall(
        r'<a href="[^"#]*#([^"]+)" class="station"><title>[^<]*</title><rect x="[\d.]+" '
        r'y="[\d.]+" width="[\d.]+" height="[\d.]+" rx="10" fill="([^"]+)"', svg)}
    assert sorted(fuellung) == list(range(1, 14))
    for n, _, gate in darstellung.WEG_STATIONEN:
        gates = [g for g in (gate, *darstellung.STATION_WEITERE_GATES.get(n, ())) if g]
        art = ("A" if any(g.startswith("A-") for g in gates)
               else "P" if gates else None)
        assert fuellung[n] == grafik._PLAN_ART[art][0], (n, gates)
    assert fuellung[7] == grafik._PLAN_ART["A"][0]          # der Anlass
    assert fuellung[6] == grafik._PLAN_ART[None][0]         # ohne eigenes Gate


def test_jeder_satz_der_ki_seite_kennt_den_stand_seiner_definition(tmp_path):
    """Die KI-Seite fuehrt je Agentenrolle und je Faehigkeit einen Satz in
    der Sprache des Unternehmens; die Definitionen darunter aendern sich.
    Bis 04.10.2026 hielt nichts die beiden zusammen: Der Betrieb kam als
    Rolle dazu und stand mit seiner englischen Rohbeschreibung auf der
    Seite. Jetzt (1) hat jede Rolle und jede Faehigkeit genau einen Satz,
    (2) nennt jeder Satz den Fingerabdruck der Beschreibung, gegen die er
    geschrieben ist — aendert sich eine Definition, wird dieser Test rot,
    bis der Satz geprueft und der Fingerabdruck nachgezogen ist —, und
    (3) bricht eine Rolle ohne Satz den Bau ab."""
    import falldaten as fd

    repo = Path(__file__).resolve().parent.parent
    agenten = {p.stem: fd.beschreibung(p.read_text(encoding="utf-8"))
               for p in sorted((repo / ".claude" / "agents").glob("*.md"))}
    skills = {p.name: fd.beschreibung((p / "SKILL.md").read_text(encoding="utf-8"))
              for p in sorted((repo / ".claude" / "skills").iterdir()) if p.is_dir()}
    assert all(agenten.values()) and all(skills.values())
    assert set(us.ROLLEN_TITEL) == set(us.ROLLEN_STAND) == set(agenten)
    assert set(us.SKILL_TITEL) == set(us.SKILL_STAND) == set(skills)
    assert all(f"mensch/{name}" in us.MENSCH_TITEL for name in agenten)
    veraltet = sorted([n for n, b in agenten.items() if fd.fingerabdruck(b) != us.ROLLEN_STAND[n]]
                      + [n for n, b in skills.items() if fd.fingerabdruck(b) != us.SKILL_STAND[n]])
    assert veraltet == [], (
        f"Definition geaendert seit dem Satz der Seite: {veraltet} — den Satz in ROLLEN_TITEL "
        "bzw. SKILL_TITEL pruefen, dann den Fingerabdruck in ROLLEN_STAND bzw. SKILL_STAND nachziehen")

    fall = tmp_path / "faelle" / "probe"
    fall.mkdir(parents=True)
    r = fd.rollen(fall, {"entscheide": []})
    r["agenten"].append(dict(r["agenten"][0], name="neu", kennung="agent/neu"))
    with pytest.raises(us.VeroeffentlichungFehler, match="ohne Seitentext: neu"):
        us._html_baustein("rollen", {"rollen": r}, None)


def test_die_architekturdokumentation_steht_hinter_den_kulissen(tmp_path):
    """Die Architekturdokumente beschreiben das System, das die Seite
    herstellt. Seit 04.10.2026 (Entscheid des Maintainers) stehen sie unter
    Hinter den Kulissen, nicht unter IT: Der Import schreibt dorthin, der
    Weg zurueck fuehrt dorthin, und keine Seite in der Stimme des
    Unternehmens — Quelle oder Erzeuger — verlinkt auf sie."""
    repo = Path(__file__).resolve().parent.parent
    ziel = tmp_path / "seite"
    anzahl = us.architektur(repo / "docs", ziel)
    gespiegelt = sorted(p.name for p in (ziel / "hinter-den-kulissen" / "architektur").glob("*.md"))
    # Die ADRs nur auf GitHub, die Migrations-Pipeline v0.1 gar nicht (09.10.2026).
    assert anzahl == len(gespiegelt) >= 5, gespiegelt
    assert not [n for n in gespiegelt if n.startswith(("adr-", "migrations-pipeline"))], gespiegelt
    assert not (ziel / "it").exists()
    index = (ziel / "hinter-den-kulissen" / "architektur" / "index.md").read_text(encoding="utf-8")
    assert "Hinter den Kulissen" in index.split("\n## ", 1)[0]
    quellen = repo / "plv/seite"
    for md in sorted(quellen.rglob("*.md")):
        if md.relative_to(quellen).parts[0] != "hinter-den-kulissen":
            assert "architektur/" not in md.read_text(encoding="utf-8"), md
    erzeuger = Path(us.__file__).read_text(encoding="utf-8")
    assert "](architektur/" not in erzeuger and '"it/architektur' not in erzeuger


def test_ein_dokument_ohne_vorspann_beginnt_mit_seiner_ueberschrift(tmp_path):
    """Ohne YAML-Vorspann ist die erste Ueberschrift der Titel: Sie steht vor
    der Navigation wie auf jeder Seite des Auftritts, und Pages nimmt den
    Seitentitel nur aus einer Ueberschrift am Anfang. Bis 08.10.2026 begannen
    die Architekturdokumente mit der Navigation und trugen im Browser nur den
    Namen des Unternehmens. Ein Dokument mit Vorspann behaelt seine erste
    Abschnittsueberschrift im Text."""
    docs = tmp_path / "docs"
    (docs / "architektur").mkdir(parents=True)
    (docs / "architektur" / "probe-dokument.md").write_text("\n# Probe: ein Dokument\n\nText.\n", encoding="utf-8")
    (docs / "architektur" / "README.md").write_text("# Architektur\n\n## Abschnitt\n", encoding="utf-8")
    ziel = tmp_path / "seite"
    assert us.architektur(docs, ziel) == 2
    seite = (ziel / "hinter-den-kulissen" / "architektur" / "probe-dokument.md").read_text(encoding="utf-8")
    zeilen = seite.splitlines()
    assert zeilen[0] == "# Probe: ein Dokument" and zeilen[2].startswith('<nav class="kopf">'), zeilen[:3]
    assert seite.count("Probe: ein Dokument") == 1
    index = (ziel / "hinter-den-kulissen" / "architektur" / "index.md").read_text(encoding="utf-8")
    assert index.splitlines()[0] == "# Architektur" and "## Abschnitt" in index
    assert us._titel_und_rumpf("---\ntitle: \"T\"\n---\n# 1 Inhalt\n") == ("T", "# 1 Inhalt\n")
    assert us._titel_und_rumpf("Kein Titel\n# Spaeter\n") == ("", "Kein Titel\n# Spaeter\n")


def test_ein_verweis_vom_fallordner_aus_bekommt_eine_weiterleitung(tmp_path, monkeypatch):
    """Der Bericht der Migrationsabnahme von Fall 3 verweist vom Fallordner aus
    (href='abgeleitet/berichte/bestandsbericht-vor.html'); der Browser loest vom
    Ordner des Berichts aus auf und laeuft ins Leere. Der Beleg bleibt bytegleich,
    dort, wohin der Verweis zeigt, liegt eine Weiterleitung auf die Datei
    daneben, und das Manifest nennt sie. Ein Verweis, der traegt, oder einer ohne
    Ziel auch vom Fallordner aus, bekommt keine. bereinigung.pruefe kennt die
    Weiterleitung als Seite des Auftritts und rechnet ihre Bytes nach."""
    import bereinigung
    import falldaten
    fall, seite = tmp_path / "fall", tmp_path / "seite" / "migrationen" / "f"
    bericht = ("<a href='abgeleitet/berichte/vor.html'>vor</a> <a href=\"vor.html\">da</a> "
               "<a href='abgeleitet/berichte/fehlt.html'>weg</a> <a href='https://example.org/'>e</a>")
    for wurzel in (fall, seite / "artefakte"):
        (wurzel / "abgeleitet" / "berichte").mkdir(parents=True)
        (wurzel / "abgeleitet" / "berichte" / "abnahme.html").write_text(bericht, encoding="utf-8")
        (wurzel / "abgeleitet" / "berichte" / "vor.html").write_text("<p>vor</p>", encoding="utf-8")
    weiter = vz._weiterleitungen(seite / "artefakte")
    assert weiter == [{"datei": "artefakte/abgeleitet/berichte/abgeleitet/berichte/vor.html",
                       "ziel": "../../vor.html",
                       "verweis_aus": "artefakte/abgeleitet/berichte/abnahme.html"}]
    datei = seite / weiter[0]["datei"]
    assert datei.read_bytes() == bereinigung.weiterleitung("../../vor.html")
    assert b'url=../../vor.html' in datei.read_bytes()
    assert (seite / "artefakte" / "abgeleitet" / "berichte" / "abnahme.html").read_text(encoding="utf-8") == bericht
    assert not (seite / "artefakte" / "abgeleitet" / "berichte" / "abgeleitet" / "berichte" / "fehlt.html").exists()

    monkeypatch.setattr(falldaten, "belegkette", lambda f: {"dateien": {}})
    (seite / "artefakte" / bereinigung.MANIFEST).write_bytes(bereinigung.manifest([], [], [], weiter))
    assert bereinigung.pruefe(seite, fall) == []
    datei.write_bytes(bereinigung.weiterleitung("../../anders.html"))
    assert bereinigung.pruefe(seite, fall) == [
        "artefakte/abgeleitet/berichte/abgeleitet/berichte/vor.html: Weiterleitung weicht von ihrer Erzeugung ab"]
    leer = [dict(weiter[0], ziel="../../weg.html")]
    datei.write_bytes(bereinigung.weiterleitung("../../weg.html"))
    (seite / "artefakte" / bereinigung.MANIFEST).write_bytes(bereinigung.manifest([], [], [], leer))
    assert bereinigung.pruefe(seite, fall) == [
        "artefakte/abgeleitet/berichte/abgeleitet/berichte/vor.html: Weiterleitung zeigt ins Leere (../../weg.html)"]
    datei.write_bytes(bereinigung.weiterleitung("../../vor.html"))
    (seite / "artefakte" / bereinigung.MANIFEST).write_bytes(bereinigung.manifest([], [], []))
    assert bereinigung.pruefe(seite, fall) == [
        "artefakte/abgeleitet/berichte/abgeleitet/berichte/vor.html: liegt auf der Seite, "
        "hat aber kein Gegenstueck im Fall"]


def test_adrs_nur_auf_github_und_die_migrations_pipeline_gar_nicht(tmp_path, monkeypatch):
    """Entscheid des Maintainers 09.10.2026: Die ADRs werden nicht gespiegelt,
    nur auf GitHub verlinkt; die Migrations-Pipeline v0.1 kommt von der Seite,
    als Seite und als Verweis. Ein Verweis aus einem gespiegelten Dokument,
    einem Fachdokument der Simulation oder einer Quellseite zeigt dann auf
    GitHub oder wird zu Text; eine Zeile der Uebersichtstabelle, die nur auf
    das entfernte Dokument zeigt, faellt. Die Menge ist ueber die zwei Listen
    umschaltbar."""
    docs = tmp_path / "docs"
    (docs / "architektur").mkdir(parents=True)
    (docs / "simulation").mkdir()
    (docs / "architektur" / "README.md").write_text(
        "# Architektur\n\n| Dokument | Inhalt |\n|---|---|\n"
        "| [Glossar](glossar.md) | Begriffe |\n| [Pipeline v0.1](migrations-pipeline-v01.md) | alt |\n"
        "| [001](adr-001-probe.md) | erster Entscheid |\n", encoding="utf-8")
    (docs / "architektur" / "glossar.md").write_text(
        "# Glossar\n\nSiehe [ADR-001](adr-001-probe.md#folgen) und\n"
        "([Pipeline v0.1](migrations-pipeline-v01.md), Abschnitt 8).\n", encoding="utf-8")
    (docs / "architektur" / "adr-001-probe.md").write_text("# ADR-001\n", encoding="utf-8")
    (docs / "architektur" / "migrations-pipeline-v01.md").write_text("# Pipeline\n", encoding="utf-8")
    (docs / "simulation" / "s.md").write_text("# S\n\nNach [ADR-001](../architektur/adr-001-probe.md).\n",
                                             encoding="utf-8")
    ziel = tmp_path / "seite"
    assert us.architektur(docs, ziel) == 2
    a = ziel / "hinter-den-kulissen" / "architektur"
    assert sorted(p.name for p in a.glob("*.md")) == ["glossar.md", "index.md"]
    index = (a / "index.md").read_text(encoding="utf-8")
    assert f"| [001]({us.GITHUB_ARCHITEKTUR}adr-001-probe.md) | erster Entscheid |" in index
    assert "Pipeline v0.1" not in index and "| [Glossar](glossar.md) | Begriffe |" in index
    glossar = (a / "glossar.md").read_text(encoding="utf-8")
    assert f"[ADR-001]({us.GITHUB_ARCHITEKTUR}adr-001-probe.md#folgen)" in glossar
    assert "(Pipeline v0.1, Abschnitt 8)" in glossar
    us.fachdokumente(docs, ziel, dokumente=(("simulation/s.md", "hinter-den-kulissen/simulation/s.md",
                                             "Hinter den Kulissen", "../"),))
    s = (ziel / "hinter-den-kulissen" / "simulation" / "s.md").read_text(encoding="utf-8")
    assert f"[ADR-001]({us.GITHUB_ARCHITEKTUR}adr-001-probe.md)" in s

    # Umgeschaltet: auch Glossar und Uebersicht nur auf GitHub.
    monkeypatch.setattr(us, "NUR_AUF_GITHUB", ("adr-*.md", "glossar.md", "README.md"))
    assert us.architektur(docs, tmp_path / "seite2") == 0
    quelle = "[Architektur](architektur/) und [Glossar](architektur/glossar.html), [Karte](architektur/landkarte.html)"
    umgeschrieben = us._verweise_nach_aussen(
        quelle, us._gespiegelt_im_auftritt(ziel, ziel / "hinter-den-kulissen"))
    assert umgeschrieben == (f"[Architektur]({us.GITHUB_ARCHITEKTUR}README.md) und "
                             f"[Glossar]({us.GITHUB_ARCHITEKTUR}glossar.md), [Karte](architektur/landkarte.html)")
    # Der Bau wendet das auf die Quellseiten an.
    quellen = _quellseiten(tmp_path / "q")
    (quellen / "hinter-den-kulissen").mkdir()
    (quellen / "hinter-den-kulissen" / "index.md").write_text(
        "# Hinter den Kulissen\n\n* [Glossar](architektur/glossar.html)\n", encoding="utf-8")
    us.baue(quellen, tmp_path / "seite3", {})
    gebaut = (tmp_path / "seite3" / "hinter-den-kulissen" / "index.md").read_text(encoding="utf-8")
    assert f"[Glossar]({us.GITHUB_ARCHITEKTUR}glossar.md)" in gebaut


def test_jede_kastenart_hat_ihre_farbe_und_keine_ist_weiss():
    """Die Karte unterscheidet drei Kastenarten an der Farbe, und Weiss
    heisst in ihr: Mensch zeichnet (die weissen Marken). Bis 04.10.2026
    loeste der Kasten ohne eigenes Gate ueber var(--flaeche) auf das Weiss
    der Seite auf, waehrend Legende und Text "grau" sagten — gesehen in der
    Aufnahme, nicht im Test. Geprueft an den Werten des Stylesheets."""
    import re
    import grafik

    css = (Path(__file__).resolve().parent.parent / "plv/seite" / "assets" / "stil.css").read_text(
        encoding="utf-8")
    wurzel = dict(re.findall(r"(--[\w-]+):\s*(#[0-9a-fA-F]{3,6})\s*;", css.split("}", 1)[0]))

    def farbe(wert: str) -> str:
        m = re.fullmatch(r"var\((--[\w-]+),\s*(#[0-9a-fA-F]{3,6})\)", wert)
        return (wurzel.get(m.group(1), m.group(2)) if m else wert).lower()

    assert wurzel.get("--flaeche") and wurzel.get("--flaeche-matt")      # das Stylesheet ist gelesen
    fuellungen = {art: farbe(f) for art, (f, *_rest) in grafik._PLAN_ART.items()}
    assert len(set(fuellungen.values())) == 3, fuellungen
    assert not {"#fff", "#ffffff"} & set(fuellungen.values()), fuellungen


def test_jedes_werkzeug_der_rollen_steht_in_der_sprache_des_hauses(tmp_path):
    """Die KI-Seite sagt, was eine Agentenrolle bedienen darf; die
    Definitionen nennen die Werkzeuge mit ihren technischen Namen. Jedes
    Werkzeug, das eine Definition nennt, hat seinen Satz in WERKZEUG_TEXT —
    ein neues faellt hier auf, statt roh auf der Seite zu stehen
    (Nachpruefung der Seite, 04.10.2026)."""
    import falldaten as fd

    fall = tmp_path / "faelle" / "probe"
    fall.mkdir(parents=True)
    r = fd.rollen(fall, {"entscheide": []})
    genannt = {w for a in r["agenten"] for w in a["werkzeuge"] if w != "*"}
    assert genannt and genannt <= set(us.WERKZEUG_TEXT), genannt - set(us.WERKZEUG_TEXT)
    html = us._html_baustein("rollen", {"rollen": r}, None)
    absatz = html.split("Was eine Agentenrolle bedienen darf", 1)[1].split("</p>", 1)[0]
    assert not any(f" {w}" in absatz for w in genannt), absatz


def test_die_betriebssicht_des_pakets_findet_ihre_berichte(tmp_path):
    """Die Betriebssicht des Stands-Pakets verlinkt ihre Berichte so, wie die
    Ablage des Tagesbetriebs sie fuehrt (``../berichte/<name>``); das Paket
    selbst ist flach. Der Auftritt legt jeden so verlinkten Bericht des
    Pakets zusaetzlich dorthin — dieselben Bytes, gegen stand.json
    geprueft. Bis 04.10.2026 fuehrten die zwei Berichtslinks der
    Betriebssicht von Fall 3 ins Leere; der Linkcheck folgte den
    Verzeichnis-Symlinks der Vorschau nicht und sah es nicht."""
    import hashlib

    paket, betrieb = _stands_paket(tmp_path)
    index = (b'<html><body><a href="../berichte/bestandsbericht_2026-09-01.html">Bericht</a>'
             b'<a href="../berichte/fehlt.html">fehlt</a><a href="../plv/x.html">x</a></body></html>')
    (paket / "index.html").write_bytes(index)
    betrieb["dateien"]["index.html"] = hashlib.sha256(index).hexdigest()
    ziel = tmp_path / "seite"
    aus = us.stand({"betrieb": betrieb}, ziel)
    kopie = ziel / "berichte" / "bestandsbericht_2026-09-01.html"
    assert kopie.read_bytes() == (paket / "bestandsbericht_2026-09-01.html").read_bytes()
    assert "berichte/bestandsbericht_2026-09-01.html" in aus
    # Nur was das Paket traegt, und nichts unter plv/ doppelt.
    assert not (ziel / "berichte" / "fehlt.html").exists()
    assert sorted(p.relative_to(ziel).as_posix() for p in (ziel / "berichte").iterdir()) == [
        "berichte/bestandsbericht_2026-09-01.html"]


def _protokoll(pfad: Path, antworten, rolle=None, name=None) -> Path:
    """Ein Sitzungsprotokoll wie Claude Code es schreibt: Eine Antwort aus
    mehreren Teilen steht in mehreren Zeilen mit derselben Kennung und
    demselben vollstaendigen Verbrauch; mit welcher Agentenrolle und unter
    welchem Namen die Sitzung lief, steht in eigenen Zeilen."""
    zeilen = ['{"type": "user", "message": {"content": "Arbeitspaket"}}', "keine Zeile JSON"]
    if rolle:
        zeilen.append(json.dumps({"type": "agent-setting", "agentSetting": rolle}))
    if name:
        zeilen.append(json.dumps({"type": "agent-name", "agentName": name}))
    for i, (teile, usage, zeit) in enumerate(antworten):
        for _ in range(teile):
            zeilen.append(json.dumps({"type": "assistant", "timestamp": zeit, "message": {
                "id": f"msg_{i}", "model": "modell-x", "usage": usage}}))
    pfad.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    return pfad


_U1 = {"input_tokens": 3, "cache_creation_input_tokens": 100, "cache_read_input_tokens": 1000, "output_tokens": 50}
_U2 = {"input_tokens": 2, "cache_creation_input_tokens": 10, "cache_read_input_tokens": 2000, "output_tokens": 7}
_SUMME_FALL3 = {"antworten": 469, "eingabe": 938, "cache_schreiben": 2342525,
                "cache_lesen": 135839888, "ausgabe": 580961}
_JE_ROLLE_FALL3 = {
    "rechenkern": {"antworten": 69, "eingabe": 138, "cache_schreiben": 373259, "cache_lesen": 10629845, "ausgabe": 55608},
    "betrieb": {"antworten": 18, "eingabe": 36, "cache_schreiben": 147001, "cache_lesen": 1704634, "ausgabe": 33395},
    "programmleitung": {"antworten": 153, "eingabe": 306, "cache_schreiben": 699711, "cache_lesen": 42424587,
                        "ausgabe": 195522},
    "aktuariat": {"antworten": 229, "eingabe": 458, "cache_schreiben": 1122554, "cache_lesen": 81080822,
                  "ausgabe": 296436},
}


def test_der_aufwand_zaehlt_jede_antwort_einmal(tmp_path):
    """Der Aufwand der Agenten kommt aus den Sitzungsprotokollen, je Antwort
    der gemeldete Verbrauch. Eine Antwort aus drei Teilen steht in drei
    Zeilen mit demselben Verbrauch — zeilenweise summiert zaehlte sie
    dreifach (so stand es am 05.10.2026 kurz in einer Antwort an den
    Maintainer, 1,7- bis 1,9-fach zu hoch). Eine Rolle, die es nicht gibt,
    bricht ab; was festgehalten ist, wird nicht ueberschrieben."""
    import hashlib
    import aufwand

    a = _protokoll(tmp_path / "aaaa.jsonl", [(3, _U1, "2026-10-02T13:00:00Z"), (1, _U2, "2026-10-02T13:05:00Z")])
    b = _protokoll(tmp_path / "bbbb.jsonl", [(2, _U2, "2026-10-02T14:00:00Z")])
    fall = tmp_path / "fall"
    fall.mkdir()
    (fall / "fall.json").write_text("{}", encoding="utf-8")
    d = aufwand.erfasse(fall, [("programmleitung", a), ("aktuariat", b)])
    pl = d["je_rolle"]["programmleitung"]
    assert pl == {"antworten": 2, "eingabe": 5, "cache_schreiben": 110, "cache_lesen": 3000, "ausgabe": 57}
    assert d["summe"]["ausgabe"] == 57 + 7 and d["summe"]["antworten"] == 3 and d["zuordnung"] == "Aufruf"
    s = d["sitzungen"][0]
    assert s["protokoll_sha256"] == hashlib.sha256(a.read_bytes()).hexdigest()
    assert s["erste_antwort"] == "2026-10-02T13:00:00Z" and s["modelle"] == ["modell-x"]
    # Eine angehaengte Verwaltungszeile aendert die Datei, nicht das Gezaehlte.
    with a.open("a", encoding="utf-8") as h:
        h.write('{"type": "permission-mode", "permissionMode": "auto"}\n')
    s2 = aufwand.sitzung(a)
    assert s2["protokoll_sha256"] != s["protokoll_sha256"]
    assert s2["antworten_sha256"] == s["antworten_sha256"] and s2["tokens"] == s["tokens"]
    with pytest.raises(aufwand.AufwandFehler, match="unbekannte Rolle"):
        aufwand.erfasse(fall, [("regie", a)])
    with pytest.raises(aufwand.AufwandFehler, match="doppelt"):
        aufwand.erfasse(fall, [("programmleitung", a), ("aktuariat", a)])
    assert aufwand.main(["--fall", str(fall), "--sitzung", f"programmleitung={a}"]) == 0
    ziel = fall / "abgeleitet" / "aufwand.json"
    assert json.loads(ziel.read_text(encoding="utf-8"))["summe"]["ausgabe"] == 57
    assert not ziel.stat().st_mode & 0o222                       # schreibgeschuetzt
    assert aufwand.main(["--fall", str(fall), "--sitzung", f"aktuariat={b}"]) == 2
    ohne = tmp_path / "ohne.jsonl"
    ohne.write_text(json.dumps({"type": "assistant", "message": {"id": "m", "usage": _U1}}) + "\n",
                    encoding="utf-8")
    with pytest.raises(aufwand.AufwandFehler, match="Zeitstempel"):
        aufwand.sitzung(ohne)


def test_die_rollen_kommen_aus_dem_protokoll_selbst(tmp_path):
    """Fuer kuenftige Faelle ohne Handarbeit und ohne agentische
    Gegenpruefung: Claude Code haelt in jedem Protokoll fest, mit welcher
    Agentenrolle die Sitzung gestartet wurde (agent-setting) und unter
    welchem Namen (agent-name). Gezaehlt wird, was eine Rolle der
    Agentendefinitionen traegt und eine Antwort hat; eine Sitzung ohne Rolle
    bleibt draussen, ein Leerstart auch, das Praefix trennt Faelle. An Fall 3
    gemessen (05.10.2026): dieselben vier Sitzungen und Summen wie die
    Zuordnung von Hand."""
    import aufwand

    ordner = tmp_path / "protokolle"
    ordner.mkdir()
    _protokoll(ordner / "pl.jsonl", [(2, _U1, "2026-10-02T13:00:00Z")], "programmleitung", "fall9-programmleitung")
    _protokoll(ordner / "ak.jsonl", [(1, _U2, "2026-10-02T13:10:00Z")], "aktuariat", "fall9-aktuariat")
    _protokoll(ordner / "ohne-rolle.jsonl", [(1, _U1, "2026-10-02T13:00:00Z")], None, "fall9-regie")
    _protokoll(ordner / "leer.jsonl", [], "rechenkern", "fall9-rechenkern")
    _protokoll(ordner / "anderer.jsonl", [(1, _U1, "2026-10-01T10:00:00Z")], "aktuariat", "fall8-aktuariat")
    assert sorted((r, q.name) for r, q in aufwand.entdecke(ordner, "fall9-")) == [
        ("aktuariat", "ak.jsonl"), ("programmleitung", "pl.jsonl")]
    assert len(aufwand.entdecke(ordner)) == 3                       # ohne Praefix auch der andere Fall
    with pytest.raises(aufwand.AufwandFehler, match="keine Agentensitzung"):
        aufwand.entdecke(ordner, "fall7-")
    fall = tmp_path / "fall"
    fall.mkdir()
    (fall / "fall.json").write_text("{}", encoding="utf-8")
    assert aufwand.main(["--fall", str(fall), "--protokolle", str(ordner), "--sitzung",
                         f"aktuariat={ordner / 'ak.jsonl'}"]) == 2       # entweder, oder
    assert aufwand.main(["--fall", str(fall)]) == 2
    assert aufwand.main(["--fall", str(fall), "--protokolle", str(ordner), "--name-praefix", "fall9-"]) == 0
    d = json.loads((fall / "abgeleitet" / "aufwand.json").read_text(encoding="utf-8"))
    assert d["zuordnung"] == "agent-setting der Sitzung, agent-name fall9-*"
    assert d["je_rolle"]["programmleitung"]["ausgabe"] == 50 and d["je_rolle"]["aktuariat"]["ausgabe"] == 7


def test_dauer_und_aufwand_der_uebernahme_im_modell_und_auf_der_seite(tmp_path):
    """Die Dauer ist Uhrzeit vom ERSTEN Fallauftrag (fruehester A-M6) bis
    zum geltenden Zugang (A-B2), gemessen an den Snapshots (Entscheid des
    Maintainers 05.10.2026); der Aufwand kommt aus abgeleitet/aufwand.json,
    je Rolle geprueft gegen die Summe. Die Startseite fuehrt zur Vertiefung
    auf der Fallseite; eine Kostenzeile gibt es nicht, solange kein
    Preissatz beschlossen ist (Maintainer 05.10.2026)."""
    import falldaten as fd

    def e(gate, am, geltend=False):
        return {"gate": gate, "entschieden_am": am, "geltend": geltend}

    kette = {"entscheide": [e("A-M6", "2026-10-02T13:18:20+00:00"), e("A-M6", "2026-10-02T12:56:56+00:00"),
                            e("A-M6", "2026-10-02T15:28:16+00:00", True),
                            e("A-B2", "2026-10-02T16:00:00+00:00"), e("A-B2", "2026-10-02T16:35:25+00:00", True),
                            # eine spaetere, nicht geltende Runde darf das Ende nicht verschieben
                            e("A-B2", "2026-10-02T17:10:00+00:00")]}
    fall = tmp_path / "fall"
    (fall / "abgeleitet").mkdir(parents=True)
    leer = fd.aufwand(fall, {"entscheide": kette["entscheide"][:3]})
    assert leer["dauer"] is None and leer["agenten"] is None and leer["gelesen_aus"] == []
    (fall / "abgeleitet" / "aufwand.json").write_text(json.dumps({
        "art": "aufwand", "summe": _SUMME_FALL3, "je_rolle": _JE_ROLLE_FALL3}), encoding="utf-8")
    a = fd.aufwand(fall, kette)
    assert a["dauer"]["sekunden"] == 3 * 3600 + 38 * 60 + 29          # 12:56:56 bis 16:35:25
    assert a["gelesen_aus"] == [fd.AUFWAND_DATEI]
    html = us._migrationen_bloecke({"aufwand": a}, None, "")
    assert "<td>Dauer</td><td>3 h 38 min, vom ersten Fallauftrag bis zur Zugangsabnahme</td>" in html
    assert "<td>580.961 Tokens erzeugt, 138 Mio. gelesen, im ganzen Fall</td>" in html
    assert 'class="platzhalter"' not in html and "Kosten" not in html
    assert us._migrationen_bloecke({}, None, "").count('class="platzhalter"') == 2
    # Mit Fallseite fuehrt die Zeile zur Vertiefung je Rolle; ohne nicht.
    seite = tmp_path / "seite"
    assert "je Rolle" not in us._migrationen_bloecke({"aufwand": a}, seite, "")
    (seite / "migrationen" / "baldrian").mkdir(parents=True)
    (seite / "migrationen" / "baldrian" / "index.md").write_text("# Fall", encoding="utf-8")
    assert ('gelesen, im ganzen Fall (<a href="migrationen/baldrian/#aufwand">je Rolle</a>)'
            in us._migrationen_bloecke({"aufwand": a}, seite, ""))
    # Kaputt oder unvollstaendig bricht ab, benannt: sonst stuenden 0, negative
    # Werte oder eine Tabelle, die nicht zur Summe passt, als Angabe da.
    falsch = dict(_JE_ROLLE_FALL3, betrieb=dict(_JE_ROLLE_FALL3["betrieb"], ausgabe=1))
    for kaputt, meldung in (({}, "kein Aufwand nach Schema"),
                            ({"art": "aufwand", "summe": {"antworten": 469}}, "kein Aufwand nach Schema"),
                            ({"art": "aufwand", "summe": dict(_SUMME_FALL3, ausgabe=-5)}, "kein Aufwand nach Schema"),
                            ({"art": "aufwand", "summe": _SUMME_FALL3}, "je_rolle"),
                            ({"art": "aufwand", "summe": _SUMME_FALL3, "je_rolle": falsch}, "je_rolle")):
        (fall / "abgeleitet" / "aufwand.json").write_text(json.dumps(kaputt), encoding="utf-8")
        with pytest.raises(fd.FalldatenFehler, match=meldung):
            fd.aufwand(fall, kette)
    # Ein verletzter A-M6 mit frueherem Datum verlaengert die Dauer nicht;
    # ein Zeitstempel ohne Zone bricht benannt ab.
    (fall / "abgeleitet" / "aufwand.json").unlink()
    verletzt = dict(e("A-M6", "2026-10-02T09:00:00+00:00"), strukturell_verifiziert=False)
    assert fd.aufwand(fall, {"entscheide": kette["entscheide"] + [verletzt]})["dauer"][
        "sekunden"] == a["dauer"]["sekunden"]
    with pytest.raises(fd.FalldatenFehler, match="ohne Zeitzone"):
        fd.aufwand(fall, {"entscheide": kette["entscheide"] + [e("A-M6", "2026-10-02T09:00:00")]})


def test_die_vertiefung_dauer_und_aufwand_steht_auf_der_fallseite(tmp_path):
    """Die Tabelle je Rolle ist die Vertiefung zu den zwei Zeilen der
    Startseite (Wunsch des Maintainers 05.10.2026): Rollen in der Folge des
    Ablaufs, die Summenzeile, die Dauer in der Ortszeit des Hauses und der
    Beleg — nur, wenn die Fallseite ihn traegt."""
    a = {"dauer": {"von": "2026-10-02T12:56:56+00:00", "bis": "2026-10-02T16:35:25+00:00",
                   "sekunden": 13109},
         "agenten": {"summe": _SUMME_FALL3, "je_rolle": _JE_ROLLE_FALL3}}
    z = "\n".join(vz._aufwand_abschnitt({"aufwand": a}, lambda ref: f"artefakte/{ref}"))
    assert z.startswith("# Dauer und Aufwand {#aufwand}")
    assert ("Vom ersten Fallauftrag am 02.10.2026 um 14:56 Uhr bis zur Zugangsabnahme um 18:35 Uhr: "
            "**3 h 38 min**") in z
    zeilen = [x for x in z.splitlines() if x.startswith("| ") and "Rolle" not in x]
    assert [x.split(" | ")[0] for x in zeilen] == [
        "| Programmleitung", "| Aktuariat", "| Rechenkern", "| Betrieb", "| **zusammen**"]
    assert "| Aktuariat | 229 | 296.436 | 1.122.554 | 81.080.822 |" in z
    assert "| **zusammen** | **469** | **580.961** | **2.342.525** | **135.839.888** |" in z
    assert "Beleg: [`aufwand.json`](artefakte/abgeleitet/aufwand.json)." in z
    assert "Beleg:" not in "\n".join(vz._aufwand_abschnitt({"aufwand": a}, lambda ref: None))
    assert vz._aufwand_abschnitt({}, lambda ref: None) == []


def test_der_aufwand_kommt_ueber_das_modell_als_beleg_auf_die_fallseite(tmp_path):
    """Der ganze Weg, nicht von Hand gebaut: sammle liest abgeleitet/aufwand.json
    in die Gruppe aufwand, die Belegkette fuehrt die Datei als Quelle der
    Darstellung ohne Station, die Fallseite kopiert sie nach artefakte/ und
    zeigt die Vertiefung mit dem Beleg (Gegenlesen 05.10.2026: die Tests
    bauten sich Kette und Datei bis dahin selbst)."""
    fall = _fall_mit_berichten(tmp_path)
    summe = {"antworten": 3, "eingabe": 1, "cache_schreiben": 10, "cache_lesen": 100, "ausgabe": 7}
    (fall / "abgeleitet" / "aufwand.json").write_text(
        json.dumps({"art": "aufwand", "summe": summe, "je_rolle": {"aktuariat": summe}}), encoding="utf-8")
    modell = _modell(fall)
    assert modell["aufwand"]["agenten"]["summe"] == summe
    eintrag = modell["belegkette"]["dateien"]["abgeleitet/aufwand.json"]
    assert eintrag["station"] is None and eintrag.get("quelle_der_darstellung") is True
    kopiert, _ = vz._kopiere(fall, tmp_path / "seite", modell)
    assert "artefakte/abgeleitet/aufwand.json" in kopiert
    assert (tmp_path / "seite" / "artefakte" / "abgeleitet" / "aufwand.json").is_file()
    seite = _fallseite(fall, modell, tmp_path, kopiert, None)
    assert "## Dauer und Aufwand {#aufwand}" in seite
    assert "Beleg: [`aufwand.json`](artefakte/abgeleitet/aufwand.json)." in seite

