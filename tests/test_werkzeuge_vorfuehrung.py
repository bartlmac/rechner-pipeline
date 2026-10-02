"""Werkzeuge der Vorfuehrungssession: Lagebild, tmux-Aufbau, Aufzeichnung.

Die drei Werkzeuge sind Darstellung, keine Fachlichkeit. Test-wuerdig ist,
wo ein Fehler etwas Falsches BEHAUPTET:

* Das Lagebild zeigt den Stand eines Gates aus der Kette seiner Snapshots.
  Zwei Spitzen als "angenommen" zu zeigen, oder eine unlesbare Datei als
  "offen", waere eine falsche Auskunft vor Zuschauern. Es urteilt nicht: Es
  liest ohne Schluessel und sagt das in jeder Sicht.
* Der Aufbau gibt jeder Agentenrolle ein Fenster — der Menge der
  Agentendateien folgend, nicht einer eigenen Liste — und zeichnet nie in
  einem Agentenfenster: Das Fenster des Menschen startet keinen Chat.
* Die Aufzeichnung setzt Ausgabe und Zeitmarken zusammen. Passen sie nicht
  zueinander, wird verweigert statt eine verschobene Aufnahme zu schreiben;
  eine Terminalgroesse wird nie geraten.
* Die Sitzungsprobe sagt, ob ein Agenten-Werkzeug die Sitzungen traegt. Sie
  darf weder Ruhe melden, solange sich der Bildschirm bewegt, noch die
  Anzeige des eigenen Auftrags fuer die Antwort halten.

Knoten: system/betrieb
"""

from __future__ import annotations

import json
import shlex
import sys
from datetime import datetime
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "werkzeuge"))

import aufzeichnung as az  # noqa: E402
import lagebild as lb  # noqa: E402
import sitzungsprobe as sp  # noqa: E402
import vorfuehrung as vf  # noqa: E402


# --------------------------------------------------------------------------- #
# Lagebild
# --------------------------------------------------------------------------- #

def _snapshot(bereich: Path, gate: str, sha: str, entscheid: str, vorgaenger=(), *,
              freigabe: bool = True, am: str = "2026-10-02T08:00:00+00:00") -> None:
    daten = {"gate": gate, "entscheid": entscheid, "vorgaenger": list(vorgaenger),
             "entschieden_am": am, "rolle": "mensch/aktuariat",
             "pflichtbelege": {"aktuartest": "x"}}
    if freigabe:
        daten["freigabe"] = {"signatur": "s"}
    (bereich / "entscheide").mkdir(parents=True, exist_ok=True)
    (bereich / "entscheide" / f"{gate}-{sha}.json").write_text(json.dumps(daten))


def test_der_stand_eines_gates_ist_der_entscheid_der_einen_spitze(tmp_path):
    _snapshot(tmp_path, "A-M1", "a" * 64, "abgelehnt")
    _snapshot(tmp_path, "A-M1", "b" * 64, "angenommen", ["a" * 64])
    stand = lb.stand(tmp_path, "A-M1")
    assert (stand["stand"], stand["anzahl"], stand["snapshot"]) == ("angenommen", 2, "b" * 12)
    assert stand["belege"] == ["aktuartest"]


def test_ohne_snapshot_ist_ein_gate_offen_auch_ohne_verzeichnis(tmp_path):
    assert lb.stand(tmp_path, "A-M4")["stand"] == lb.OFFEN
    assert lb.stand(None, "A-M4")["stand"] == lb.OFFEN


def test_zwei_spitzen_sind_mehrdeutig_nie_angenommen(tmp_path):
    _snapshot(tmp_path, "A-M1", "a" * 64, "angenommen")
    _snapshot(tmp_path, "A-M1", "b" * 64, "angenommen")
    stand = lb.stand(tmp_path, "A-M1")
    assert stand["stand"] == lb.MEHRDEUTIG and len(stand["spitzen"]) == 2
    assert "mehrdeutig" in "\n".join(lb.sicht_lebenslauf(tmp_path, None))


def test_eine_unlesbare_datei_ist_nicht_offen(tmp_path):
    (tmp_path / "entscheide").mkdir()
    (tmp_path / "entscheide" / ("A-M4-" + "c" * 64 + ".json")).write_text("kein json")
    assert lb.stand(tmp_path, "A-M4")["stand"] == lb.UNLESBAR


def test_eine_ablehnung_ohne_freigabe_ist_als_solche_zu_sehen(tmp_path):
    _snapshot(tmp_path, "A-Q1", "a" * 64, "abgelehnt", freigabe=False)
    zeile = next(z for z in lb.sicht_lebenslauf(tmp_path, None) if z.startswith("A-Q1"))
    assert "abgelehnt" in zeile and "ohne Freigabe" in zeile


def test_eine_abnahme_der_linie_erscheint_im_lebenslauf_als_solche(tmp_path):
    fall, linie = tmp_path / "fall", tmp_path / "linie"
    fall.mkdir()
    _snapshot(linie, "A-K2", "f" * 64, "angenommen")
    zeile = next(z for z in lb.sicht_lebenslauf(fall, linie) if z.startswith("A-K2"))
    assert "angenommen" in zeile and "(Linie)" in zeile
    # Eine Abnahme im Fall geht vor; ohne Linie bleibt das Gate offen.
    assert "offen" in next(z for z in lb.sicht_lebenslauf(fall, None) if z.startswith("A-K2"))


def test_jede_sicht_sagt_dass_sie_nicht_prueft(tmp_path):
    for zeilen in (lb.sicht_lebenslauf(tmp_path, None), lb.sicht_entscheide(tmp_path, None, 5),
                   lb.sicht_rolle("aktuariat", tmp_path, None, None)):
        assert lb.VERMERK in zeilen


def test_die_entscheide_stehen_juengster_zuerst(tmp_path):
    _snapshot(tmp_path, "A-M6", "a" * 64, "angenommen", am="2026-10-02T08:00:00+00:00")
    _snapshot(tmp_path, "A-Q1", "b" * 64, "angenommen", am="2026-10-02T09:00:00+00:00")
    zeilen = [z for z in lb.sicht_entscheide(tmp_path, None, 5) if "A-" in z]
    assert [z.split()[2] for z in zeilen] == ["A-Q1", "A-M6"]


def test_das_lagebild_kennt_jede_agentenrolle():
    assert set(lb.ROLLEN) == set(vf.agentenrollen())


def test_die_laufzeit_nennt_eine_liegengebliebene_vorbereitung(tmp_path):
    ablage = tmp_path / "daten"
    (ablage / "uebernahme" / "fall-x").mkdir(parents=True)
    (tmp_path / "daten.neu-20260923T142406Z").mkdir()
    text = "\n".join(lb.sicht_laufzeit(ablage))
    assert "fall-x" in text and "daten.neu-20260923T142406Z" in text


def test_kommandozeile_verweigert_einen_fehlenden_fall(tmp_path, capsys):
    assert lb.main(["lebenslauf", "--fall", str(tmp_path / "fehlt")]) == 2
    assert "nicht gefunden" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# Aufbau der Session
# --------------------------------------------------------------------------- #

def _kommandos(**anders):
    argumente = dict(session="s", fall=Path("faelle/f"), linie=Path("linie"), stand=None,
                     modell=None, rollen=vf.agentenrollen(), interpreter="python",
                     mit_chat=True)
    return vf.kommandos(**(argumente | anders))


def _fenster(liste) -> list:
    return [k[k.index("-n") + 1] for k in liste if k[1] in ("new-session", "new-window")]


def _getippt(liste) -> list:
    return [(k[3], k[4]) for k in liste if k[1] == "send-keys"]


def test_jede_agentenrolle_bekommt_ihr_fenster_und_der_mensch_das_letzte():
    rollen = vf.agentenrollen()
    assert rollen[0] == vf.LEITUNG
    assert _fenster(_kommandos()) == ["cockpit", *rollen[1:], vf.MENSCH]


def test_eine_neue_agentendatei_bekommt_ein_fenster(tmp_path):
    agenten = tmp_path / ".claude" / "agents"
    agenten.mkdir(parents=True)
    for name in (*vf.REIHENFOLGE, "revision"):
        (agenten / f"{name}.md").write_text("x")
    assert vf.agentenrollen(tmp_path) == [*vf.REIHENFOLGE, "revision"]
    assert "revision" in _fenster(_kommandos(rollen=vf.agentenrollen(tmp_path)))


def test_je_rolle_genau_ein_chat_mit_ihrem_agenten_und_keiner_beim_menschen():
    chats = [(ziel, text) for ziel, text in _getippt(_kommandos(modell="opus"))
             if text.startswith("claude ")]
    assert sorted(text for _, text in chats) == sorted(
        f"claude --agent {r} --model opus" for r in vf.agentenrollen())
    assert not any(ziel.endswith(":" + vf.MENSCH) for ziel, _ in chats)
    assert ("s:cockpit", f"claude --agent {vf.LEITUNG} --model opus") in chats


def test_ohne_chat_startet_keine_sitzung():
    assert not any(text.startswith("claude") for _, text in _getippt(_kommandos(mit_chat=False)))


def test_die_anzeigen_lesen_fall_und_linie_des_aufrufs():
    anzeigen = [text for _, text in _getippt(_kommandos(stand=Path("/ablage")))
                if text.startswith("watch ")]
    # Cockpit drei Anzeigen, je weiterer Rolle eine.
    assert len(anzeigen) == 3 + len(vf.agentenrollen()) - 1
    assert all("werkzeuge/lagebild.py" in a for a in anzeigen)
    assert all("--linie linie" in a for a in anzeigen)
    assert sum("--fall faelle/f" in a for a in anzeigen) == len(anzeigen) - 1  # system ohne Fall


def test_kein_ziel_haengt_an_einer_fensternummer():
    """Die Zaehlung von Fenstern und Panes ist eine Einstellung des Kontos."""
    for kommando in _kommandos():
        if "-t" not in kommando:
            continue
        ziel = kommando[kommando.index("-t") + 1]
        fenster = ziel.split(":", 1)[1] if ":" in ziel else ""
        assert not fenster[:1].isdigit(), kommando


def test_ohne_programmleitung_wird_benannt_verweigert():
    with pytest.raises(ValueError, match="programmleitung"):
        _kommandos(rollen=["aktuariat"])


def test_trocken_gibt_die_kommandos_aus_und_baut_nichts(tmp_path, capsys):
    fall = tmp_path / "fall"
    fall.mkdir()
    assert vf.main(["--fall", str(fall), "--linie", str(tmp_path / "linie"), "--trocken",
                    "--modell", "opus"]) == 0
    aus = capsys.readouterr().out.splitlines()
    assert aus[0].startswith("tmux new-session -d -s vorfuehrung")
    assert sum("claude --agent" in z and "--model opus" in z for z in aus) == len(
        vf.agentenrollen())
    assert vf.main(["--fall", str(tmp_path / "fehlt"), "--linie", "x", "--trocken",
                    "--modell", "opus"]) == 2


def test_ohne_modell_startet_kein_chat(tmp_path, capsys):
    """Das Modell der Chats hat keine Vorgabe: Geerbt wuerde das Modell des
    Kontos, fuenfmal. Das Geruest ohne Chats braucht keines."""
    fall = tmp_path / "fall"
    fall.mkdir()
    basis = ["--fall", str(fall), "--linie", str(tmp_path / "linie"), "--trocken"]
    assert vf.main(basis) == 2
    assert "--modell fehlt" in capsys.readouterr().err
    assert vf.main([*basis, "--ohne-chat"]) == 0
    assert "claude --agent" not in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# Aufzeichnung
# --------------------------------------------------------------------------- #

KOPF = b'Script started on 2026-10-02 08:00:00+02:00 [TERM="tmux" COLUMNS="120" LINES="40"]\n'


def test_ausgabe_und_zeitmarken_werden_zu_ereignissen_mit_laufender_zeit():
    zeilen = az.cast_zeilen(KOPF + b"eins\r\nzwei\r\n", "0.5 6\n1.25 6\n")
    assert json.loads(zeilen[0]) == {"version": 2, "width": 120, "height": 40}
    assert [json.loads(z) for z in zeilen[1:]] == [[0.5, "o", "eins\r\n"], [1.75, "o", "zwei\r\n"]]


def test_ein_zeichen_ueber_der_ereignisgrenze_bleibt_ganz():
    daten = "Übernahme".encode("utf-8")           # das U mit Umlaut hat zwei Bytes
    ereignisse = list(az.ereignisse(KOPF + daten, f"0.1 1\n0.1 {len(daten) - 1}\n"))
    assert ereignisse == [(0.2, "Übernahme")]


@pytest.mark.parametrize("zeitmarken", ["0.1 99\n", "x 3\n", "0.1\n", "-1 3\n"],
                         ids=["zu_viele_bytes", "keine_zahl", "ohne_bytes", "negativ"])
def test_unpassende_zeitmarken_werden_verweigert(zeitmarken):
    with pytest.raises(az.AufzeichnungFehler):
        list(az.ereignisse(KOPF + b"abc", zeitmarken))


def test_die_terminalgroesse_wird_nie_geraten():
    ohne = b"Script started on 2026-10-02 [<not executed on terminal>]\n"
    with pytest.raises(az.AufzeichnungFehler, match="--spalten"):
        az.cast_zeilen(ohne + b"abc", "0.1 3\n")
    assert json.loads(az.cast_zeilen(ohne + b"abc", "0.1 3\n", spalten=80, zeilen=24)[0]) == {
        "version": 2, "width": 80, "height": 24}


def test_cast_ueberschreibt_keine_vorhandene_datei(tmp_path, capsys):
    basis = tmp_path / "lauf"
    Path(f"{basis}.out").write_bytes(KOPF + b"abc")
    Path(f"{basis}.tim").write_text("0.1 3\n")
    assert az.main(["cast", "--basis", str(basis)]) == 0
    erste = Path(f"{basis}.cast").read_text()
    assert az.main(["cast", "--basis", str(basis)]) == 2
    assert Path(f"{basis}.cast").read_text() == erste
    assert "nicht ueberschrieben" in capsys.readouterr().err


def test_aufgenommen_wird_die_ganze_session_im_klassischen_format():
    kommando = az.aufnahme_kommando("vorfuehrung", Path("runs/fall3"))
    assert kommando[:4] == ["script", "-q", "-m", "classic"]
    assert kommando[-1] == "tmux attach -t vorfuehrung"


# --------------------------------------------------------------------------- #
# Sitzungsprobe
# --------------------------------------------------------------------------- #

def test_ruhe_braucht_genug_gleiche_blicke():
    genug = sp.RUHE_BLICKE
    assert not sp.ruhig(["x"] * (genug - 1))                 # zu wenige Blicke sind kein Urteil
    assert sp.ruhig(["a", "b"] + ["x"] * genug)
    assert not sp.ruhig(["x"] * genug + ["y"])               # der letzte Blick bewegt sich wieder
    assert not sp.ruhig(["x", "y"] * genug)


def test_bewegte_zeilen_sind_die_die_nicht_in_jedem_blick_stehen():
    blicke = ["kopf\n> frage\n  arbeitet (1s)", "kopf\n> frage\n  arbeitet (2s)", "kopf\n> frage\nantwort"]
    assert sp.bewegte_zeilen(blicke) == ["  arbeitet (1s)", "  arbeitet (2s)", "antwort"]
    assert sp.bewegte_zeilen(["nur ein Blick"]) == []


def test_die_anzeige_des_auftrags_gilt_nicht_als_antwort():
    paare = ((sp.AUFTRAG_EINGABE, sp.ANTWORT_EINGABE), (sp.AUFTRAG_WEITERGABE, sp.ANTWORT_WEITERGABE))
    weitergabe = sp.weitergabe_auftrag(Path("/x/sitzungsprobe.py"), "s")
    for auftrag, antwort in paare:
        assert not sp.beantwortet(f"> {auftrag}\n", antwort)
        assert not sp.beantwortet(f"> {weitergabe}\n", antwort)
        assert sp.beantwortet(f"> {auftrag}\n{antwort}\n", antwort)
    # Ein Chat darf die Antwort mit Leerzeichen schreiben oder umbrechen ...
    assert sp.beantwortet("> frage\n42 BLAU\n", sp.ANTWORT_EINGABE)
    # ... aber ein Zaehler oder eine Uhrzeit auf dem Bildschirm ist keine.
    assert not sp.beantwortet("> frage\n42 tokens  14:42\n", sp.ANTWORT_EINGABE)


def test_gesendet_wird_erst_der_text_woertlich_dann_enter():
    assert sp.sende_kommandos("s", "b", "eine Zeile; $HOME") == [
        ["send-keys", "-t", "s:b", "-l", "eine Zeile; $HOME"], ["send-keys", "-t", "s:b", "Enter"]]


@pytest.mark.parametrize("text", ["zwei\nZeilen", "mit\rRuecklauf", "   "],
                         ids=["zeilenumbruch", "wagenruecklauf", "leer"])
def test_ein_mehrzeiler_oder_leerer_auftrag_wird_verweigert(text):
    with pytest.raises(sp.ProbeFehler):
        sp.sende_kommandos("s", "b", text)


def test_der_weitergabe_auftrag_ist_ein_einzeiler_mit_dem_eigenen_sende_kommando():
    auftrag = sp.weitergabe_auftrag(Path("/ein pfad/sitzungsprobe.py"), "meine session")
    assert sp.sende_kommandos("s", "a", auftrag)             # selbst ein zulaessiger Einzeiler
    kommando = auftrag.split(": ", 1)[1]
    assert shlex.split(kommando) == ["python3", "/ein pfad/sitzungsprobe.py", "sende", "b",
                                     sp.AUFTRAG_WEITERGABE, "--session", "meine session"]


def test_der_bericht_zeigt_ein_nein_als_nein_samt_bildschirm():
    zeilen = sp.bericht_zeilen("codex", "s", datetime(2026, 10, 2, 14, 0),
                               [("START", "ja", "x"), ("WEITERGABE", "NEIN", "y")],
                               ["  arbeitet (1s)"], [("Fenster a", "Rueckfrage: erlauben?")])
    text = "\n".join(zeilen)
    assert "| WEITERGABE | NEIN | y |" in text
    assert "  arbeitet (1s)" in text and "Rueckfrage: erlauben?" in text
