#!/usr/bin/env python3
"""Vorfuehrungssession: ein Fall in tmux, je Agentenrolle ein Fenster.

Baut eine tmux-Session, in der ein Migrationsfall vor Zuschauern gefuehrt
wird:

* Fenster 0 ``cockpit`` — links der Chat mit dem Programmleitungs-Agenten,
  rechts drei Anzeigen: Lebenslauf des Falls, die letzten Entscheide, der
  Systemstand samt Laufzeit.
* Je Agentenrolle (jede Datei unter ``.claude/agents/`` ausser der
  Programmleitung) ein Fenster — links der Chat mit dem Agenten der Rolle,
  rechts die Anzeige ihrer Gates und Belege.
* Ein letztes Fenster ``mensch`` — eine leere Shell fuer die Zeichnungen.
  Gezeichnet wird nie in einem Agentenfenster: Ein Agent zeichnet keine
  Annahme, und die Schluessel liegen ausserhalb des Falls.

Die Anzeigen sind ``werkzeuge/lagebild.py`` unter ``watch`` — nur lesend.
Die Chats starten mit ``claude --agent <rolle> --model <modell>``. Das Modell
wird ausdruecklich genannt (``--modell``, keine Vorgabe): Ohne Angabe erbte
jeder der fuenf Chats das Modell des Kontos — gemessen das groesste, mit
hohem Aufwand. ``--ohne-chat`` laesst die linken Panes als leere Shell (Probe
des Aufbaus, ohne eine Sitzung zu oeffnen) und braucht kein Modell.

    python werkzeuge/vorfuehrung.py --fall faelle/<fall> --linie <linie> \\
        --modell <modell> [--stand <ablage>] [--session vorfuehrung] [--trocken]
    python werkzeuge/vorfuehrung.py --fall faelle/<fall> --linie <linie> --ohne-chat

``--trocken`` gibt die tmux-Kommandos aus, statt sie auszufuehren. Eine
Session gleichen Namens wird nie ersetzt: Das Werkzeug haelt an und nennt
den Ausweg.
"""

from __future__ import annotations

import argparse
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

REPO = Path(__file__).resolve().parent.parent
LAGEBILD = "werkzeuge/lagebild.py"
LEITUNG = "programmleitung"
MENSCH = "mensch"
#: Abstand der Anzeige in Sekunden.
TAKT = 5
#: Breite der rechten Spalte in Prozent.
RECHTS = 45

HINWEIS_MENSCH = (
    "Fenster des Menschen: Hier wird gezeichnet (gate_entscheid mit "
    "--freigabe-schluessel). Kein Agent arbeitet in diesem Fenster.")


#: Die Reihenfolge der Fenster folgt dem Weg eines Falls; eine Rolle, die
#: hier nicht steht, bekommt ihr Fenster dahinter (alphabetisch).
REIHENFOLGE = (LEITUNG, "aktuariat", "architektur", "rechenkern", "betrieb")


def agentenrollen(repo: Path = REPO) -> List[str]:
    """Die Rollen, fuer die es eine Agentendatei gibt — die Fenster der
    Session folgen dieser Menge, nicht einer eigenen Liste."""
    vorhanden = sorted(p.stem for p in (Path(repo) / ".claude" / "agents").glob("*.md"))
    return ([r for r in REIHENFOLGE if r in vorhanden]
            + [r for r in vorhanden if r not in REIHENFOLGE])


def _anzeige(interpreter: str, sicht: List[str]) -> str:
    kommando = " ".join(shlex.quote(t) for t in [interpreter, LAGEBILD, *sicht])
    return f"watch -t -n {TAKT} {shlex.quote(kommando)}"


def _chat(rolle: str, modell: Optional[str]) -> str:
    teile = ["claude", "--agent", rolle]
    if modell:
        teile += ["--model", modell]
    return " ".join(shlex.quote(t) for t in teile)


def kommandos(
    *, session: str, fall: Path, linie: Path, stand: Optional[Path], modell: Optional[str],
    rollen: List[str], interpreter: str, mit_chat: bool, repo: Path = REPO,
) -> List[List[str]]:
    """Die tmux-Kommandos der Session, in der Reihenfolge ihrer Ausfuehrung.

    Reine Funktion ueber ihre Argumente. Jedes Pane bekommt sein Kommando
    ueber ``send-keys``: Endet es, bleibt die Shell des Panes stehen, statt
    das Fenster zu schliessen."""
    if LEITUNG not in rollen:
        raise ValueError(
            f"keine Agentendatei fuer die Rolle {LEITUNG!r} — das Cockpit fuehrt ihren Chat")
    bereich = ["--fall", str(fall), "--linie", str(linie)]
    ablage = ["--stand", str(stand)] if stand is not None else []
    aus: List[List[str]] = []

    # Ziele sind Fensternamen und Lagen ({left}), nie Nummern: Die Zaehlung
    # von Fenstern und Panes haengt an der tmux-Einstellung des Kontos
    # (base-index, pane-base-index). Ein neues Pane ist nach dem Teilen das
    # aktive seines Fensters; ``send-keys`` an das Fenster trifft es.
    def tippe(ziel: str, text: str) -> None:
        aus.append(["tmux", "send-keys", "-t", ziel, text, "Enter"])

    def teile(fenster: str, *, senkrecht: bool, prozent: int) -> None:
        aus.append(["tmux", "split-window", "-v" if senkrecht else "-h", "-l", f"{prozent}%",
                    "-t", fenster, "-c", str(repo)])

    # Cockpit: links der Chat, rechts drei Anzeigen untereinander.
    cockpit = f"{session}:cockpit"
    aus.append(["tmux", "new-session", "-d", "-s", session, "-n", "cockpit", "-c", str(repo)])
    teile(cockpit, senkrecht=False, prozent=RECHTS)
    tippe(cockpit, _anzeige(interpreter, ["lebenslauf", *bereich]))
    teile(cockpit, senkrecht=True, prozent=55)
    tippe(cockpit, _anzeige(interpreter, ["entscheide", *bereich, "-n", "8"]))
    teile(cockpit, senkrecht=True, prozent=50)
    tippe(cockpit, _anzeige(interpreter, ["system", "--linie", str(linie), *ablage]))
    aus.append(["tmux", "select-pane", "-t", f"{cockpit}.{{left}}"])
    if mit_chat:
        tippe(cockpit, _chat(LEITUNG, modell))

    # Je weiterer Rolle ein Fenster: links der Chat, rechts ihre Gates.
    for rolle in rollen:
        if rolle == LEITUNG:
            continue
        fenster = f"{session}:{rolle}"
        aus.append(["tmux", "new-window", "-t", f"{session}:", "-n", rolle, "-c", str(repo)])
        teile(fenster, senkrecht=False, prozent=RECHTS)
        tippe(fenster, _anzeige(interpreter, ["rolle", rolle, *bereich, *ablage]))
        aus.append(["tmux", "select-pane", "-t", f"{fenster}.{{left}}"])
        if mit_chat:
            tippe(fenster, _chat(rolle, modell))

    # Das Fenster des Menschen: nur eine Shell und ein Satz.
    aus.append(["tmux", "new-window", "-t", f"{session}:", "-n", MENSCH, "-c", str(repo)])
    tippe(f"{session}:{MENSCH}", "clear; echo " + shlex.quote(HINWEIS_MENSCH))

    aus.append(["tmux", "select-window", "-t", cockpit])
    return aus


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="python werkzeuge/vorfuehrung.py",
                                description=__doc__.split("\n")[0])
    p.add_argument("--fall", type=Path, required=True, help="Fall-Arbeitsbereich (faelle/<fall>)")
    p.add_argument("--linie", type=Path, required=True, help="Linienbereich (ADR-025)")
    p.add_argument("--stand", type=Path, default=None, help="Ablage der Laufzeit (Anzeige)")
    p.add_argument("--session", default="vorfuehrung", help="Name der tmux-Session")
    p.add_argument("--modell", default=None,
                   help="Modell fuer alle Chats (claude --model); Pflicht, sobald Chats "
                        "gestartet werden — es gibt keine Vorgabe")
    p.add_argument("--ohne-chat", action="store_true",
                   help="linke Panes als leere Shell lassen (Probe des Aufbaus)")
    p.add_argument("--trocken", action="store_true",
                   help="die tmux-Kommandos ausgeben, nicht ausfuehren")
    args = p.parse_args(argv)

    if not args.fall.is_dir():
        print(f"vorfuehrung: Fall {args.fall} nicht gefunden — zuerst den Fall anlegen "
              "(python -m rechner_pipeline.fall)", file=sys.stderr)
        return 2
    if not args.ohne_chat and not args.modell:
        print("vorfuehrung: --modell fehlt — jeder Chat erbte sonst das Modell des Kontos. "
              "Ausweg: --modell <modell> nennen (z. B. opus oder sonnet), oder --ohne-chat "
              "fuer das Geruest ohne Chats", file=sys.stderr)
        return 2
    try:
        liste = kommandos(
            session=args.session, fall=args.fall, linie=args.linie, stand=args.stand,
            modell=args.modell, rollen=agentenrollen(), interpreter=sys.executable,
            mit_chat=not args.ohne_chat)
    except ValueError as exc:
        print(f"vorfuehrung: {exc}", file=sys.stderr)
        return 2
    if args.trocken:
        print("\n".join(" ".join(shlex.quote(t) for t in k) for k in liste))
        return 0
    if shutil.which("tmux") is None:
        print("vorfuehrung: tmux nicht gefunden", file=sys.stderr)
        return 2
    if subprocess.run(["tmux", "has-session", "-t", f"={args.session}"],
                      capture_output=True).returncode == 0:
        print(f"vorfuehrung: die Session {args.session!r} besteht schon — sie wird nicht "
              f"ersetzt. Ausweg: tmux attach -t {args.session}, oder sie beenden (tmux "
              f"kill-session -t {args.session}) und neu aufbauen, oder --session <name>",
              file=sys.stderr)
        return 2
    for kommando in liste:
        ergebnis = subprocess.run(kommando, capture_output=True, text=True)
        if ergebnis.returncode != 0:
            print(f"vorfuehrung: {' '.join(kommando)} scheiterte: {ergebnis.stderr.strip()} — "
                  f"die halb gebaute Session {args.session!r} bleibt zur Ansicht stehen "
                  f"(tmux kill-session -t {args.session})", file=sys.stderr)
            return 1
    print(f"Session {args.session!r} steht: tmux attach -t {args.session}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
