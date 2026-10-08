#!/usr/bin/env python3
"""Sitzungsprobe: Traegt ein Agenten-Werkzeug die Sitzungen der Vorfuehrung?

Die Vorfuehrung fuehrt je Rolle einen Chat in einem tmux-Fenster
(``system/vorfuehrung.py``). Soll ein Fall ohne Menschen an jeder Station
laufen, reicht eine Sitzung der anderen Auftraege weiter, indem sie ihr eine
Zeile ins Fenster schreibt. Ob das mit einem bestimmten Agenten-Werkzeug
traegt, haengt an vier Dingen — genau die misst die Probe:

1. START       Das Werkzeug startet in einem tmux-Fenster und kommt zur Ruhe.
2. EINGABE     Eine von aussen ins Fenster geschriebene Zeile kommt als
               Auftrag an und wird beantwortet.
3. RUHE        Von aussen ist erkennbar, wann die Sitzung fertig ist: Der
               Bildschirm steht still. Der Bericht nennt die Zeilen, die sich
               waehrend der Arbeit bewegt haben (dort zeigt das Werkzeug
               "arbeitet noch").
4. WEITERGABE  Eine Sitzung erreicht die andere: Sie faehrt auf Auftrag das
               Kommando, das der Nachbarsitzung eine Zeile schreibt. Haelt
               eine Rueckfrage oder die Sandbox des Werkzeugs das auf, zeigt
               der Bericht den Bildschirm dazu.

    python system/sitzungsprobe.py probe --kommando "<start eines chats>" \\
        [--session sitzungsprobe] [--bericht runs/sitzungsprobe.md] [--warten 180]
    python system/sitzungsprobe.py sende <fenster> "<einzeiler>" [--session sitzungsprobe]

Die Probe baut eine EIGENE tmux-Session mit zwei Fenstern und ersetzt nie eine
bestehende. Sie laesst die Session stehen, damit man hineinsehen kann, und
kostet zwei kurze Chats mit zusammen drei Einzeilern. Ein vorhandener Bericht
wird nicht ueberschrieben.

Die Probe urteilt nach dem, was auf dem Bildschirm steht. "Traegt" heisst:
In diesem Lauf kam die erwartete Antwort; "NEIN" heisst nicht, dass es nie
geht, sondern dass der Bericht zeigt, woran es hing.
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

#: Abstand zweier Blicke auf ein Fenster in Sekunden.
TAKT = 2.0
#: So viele gleiche Blicke hintereinander heissen "ruhig".
RUHE_BLICKE = 4
BREITE, HOEHE = 160, 45

#: Die Auftraege der Probe und die Antwort, an der sie erkannt wird. Die
#: Antwort steht in keinem Auftrag: Sonst gaelte schon die Anzeige des
#: Auftrags als Antwort. Zahl UND Wort zusammen, damit kein Zaehler und keine
#: Uhrzeit auf dem Bildschirm zufaellig passt.
AUFTRAG_EINGABE = "Antworte ohne Werkzeug in einem Wort: die Summe von 17 und 25, direkt gefolgt von BLAU."
ANTWORT_EINGABE = "42BLAU"
AUFTRAG_WEITERGABE = "Antworte ohne Werkzeug in einem Wort: das Produkt von 6 und 9, direkt gefolgt von ROT."
ANTWORT_WEITERGABE = "54ROT"


class ProbeFehler(Exception):
    """Die Probe kann nicht fahren; die Meldung nennt den Ausweg."""


def ruhig(blicke: Sequence[str], noetig: int = RUHE_BLICKE) -> bool:
    """Ruhig ist ein Fenster, dessen letzte ``noetig`` Blicke gleich sind.

    Weniger Blicke sind kein Urteil: Ein einzelner Blick auf ein arbeitendes
    Fenster sieht aus wie Ruhe.
    """
    return len(blicke) >= noetig and len(set(blicke[-noetig:])) == 1


def bewegte_zeilen(blicke: Sequence[str]) -> List[str]:
    """Zeilen, die nicht in jedem Blick stehen — dort zeigt ein Werkzeug,
    dass es arbeitet (Zaehler, Laufanzeige). Reihenfolge des ersten
    Auftretens, jede Zeile einmal."""
    if len(blicke) < 2:
        return []
    je_blick = [b.splitlines() for b in blicke]
    immer = set(je_blick[0]).intersection(*map(set, je_blick[1:]))
    bewegt: List[str] = []
    for zeilen in je_blick:
        for z in zeilen:
            if z.strip() and z not in immer and z not in bewegt:
                bewegt.append(z)
    return bewegt


def beantwortet(bild: str, antwort: str) -> bool:
    """Steht die erwartete Antwort auf dem Bildschirm? Leerraum zaehlt nicht:
    Ein Chat darf die Antwort umbrechen oder mit Leerzeichen schreiben."""
    return antwort in "".join(bild.split())


def sende_kommandos(session: str, fenster: str, text: str) -> List[List[str]]:
    """Die tmux-Aufrufe, die EINE Zeile als Auftrag in ein Fenster schreiben
    und abschicken: erst der Text woertlich, dann Enter."""
    if "\n" in text or "\r" in text:
        raise ProbeFehler("nur ein Einzeiler: Ein Zeilenumbruch schickte den Auftrag vorzeitig ab")
    if not text.strip():
        raise ProbeFehler("der Auftrag ist leer")
    ziel = f"{session}:{fenster}"
    return [["send-keys", "-t", ziel, "-l", text], ["send-keys", "-t", ziel, "Enter"]]


def weitergabe_auftrag(werkzeug: Path, session: str) -> str:
    """Der Auftrag an Fenster a, dem Fenster b eine Zeile zu schreiben."""
    kommando = " ".join(["python3", shlex.quote(str(werkzeug)), "sende", "b",
                         shlex.quote(AUFTRAG_WEITERGABE), "--session", shlex.quote(session)])
    return "Fuehre genau dieses eine Shell-Kommando aus und nenne mir danach nur seinen Exit-Code: " + kommando


def bericht_zeilen(kommando: str, session: str, beginn: datetime, schritte: Sequence[Tuple[str, str, str]],
                   bewegt: Sequence[str], bilder: Sequence[Tuple[str, str]]) -> List[str]:
    zeilen = [f"# Sitzungsprobe — {beginn:%Y-%m-%d %H:%M}", "",
              f"Kommando: `{kommando}`  ", f"tmux-Session: `{session}`", "",
              "| Schritt | traegt | Bemerkung |", "|---|---|---|"]
    zeilen += [f"| {name} | {urteil} | {bemerkung} |" for name, urteil, bemerkung in schritte]
    zeilen += ["", "## Woran man \"arbeitet noch\" sieht", "",
               "Zeilen, die sich zwischen zwei Blicken auf Fenster b bewegt haben:", "", "```"]
    zeilen += list(bewegt[:25]) or ["(keine — die Antwort kam, bevor der erste Blick fiel)"]
    zeilen += ["```", ""]
    for titel, bild in bilder:
        zeilen += [f"## {titel}", "", "```", bild or "(leer)", "```", ""]
    return zeilen


# --------------------------------------------------------------------------- #
# tmux
# --------------------------------------------------------------------------- #

def _tmux(*args: str) -> str:
    lauf = subprocess.run(["tmux", *args], capture_output=True, text=True)
    if lauf.returncode != 0:
        raise ProbeFehler(f"tmux {' '.join(args)} scheiterte: {lauf.stderr.strip()}")
    return lauf.stdout


def _bildschirm(ziel: str) -> str:
    roh = _tmux("capture-pane", "-p", "-t", ziel)
    return "\n".join(z.rstrip() for z in roh.splitlines()).strip("\n")


def _sende(session: str, fenster: str, text: str) -> None:
    erst, dann = sende_kommandos(session, fenster, text)
    _tmux(*erst)
    time.sleep(0.5)        # ohne die Pause verschluckt mancher Chat das Enter
    _tmux(*dann)


def _warte_auf_ruhe(ziel: str, hoechstens: float) -> Tuple[bool, List[str]]:
    blicke: List[str] = []
    ende = time.monotonic() + hoechstens
    while time.monotonic() < ende:
        blicke.append(_bildschirm(ziel))
        if ruhig(blicke):
            return True, blicke
        time.sleep(TAKT)
    return False, blicke


def probe(kommando: str, session: str, bericht: Path, warten: float) -> int:
    if subprocess.run(["tmux", "has-session", "-t", session], capture_output=True).returncode == 0:
        raise ProbeFehler(f"die tmux-Session {session} gibt es schon — ansehen: tmux attach -t {session}; "
                          f"beenden: tmux kill-session -t {session}; oder --session <anderer name>")
    if bericht.exists():
        raise ProbeFehler(f"der Bericht {bericht} liegt schon — anderen Namen waehlen (--bericht)")
    schritte: List[Tuple[str, str, str]] = []
    bilder: List[Tuple[str, str]] = []
    beginn = datetime.now()

    def halte(name: str, gut: Optional[bool], bemerkung: str) -> None:
        urteil = "ja" if gut else ("offen" if gut is None else "NEIN")
        schritte.append((name, urteil, bemerkung))
        print(f"  {urteil:5} {name}: {bemerkung}", flush=True)

    print(f"Sitzungsprobe mit: {kommando}")
    _tmux("new-session", "-d", "-s", session, "-n", "a", "-x", str(BREITE), "-y", str(HOEHE))
    # Eine abgehaengt gebaute Session erbt sonst die Groesse des Terminals,
    # aus dem sie gebaut wurde.
    _tmux("set-option", "-t", session, "window-size", "manual")
    _tmux("resize-window", "-t", f"{session}:a", "-x", str(BREITE), "-y", str(HOEHE))
    _tmux("new-window", "-d", "-t", session, "-n", "b")
    _tmux("resize-window", "-t", f"{session}:b", "-x", str(BREITE), "-y", str(HOEHE))
    for fenster in ("a", "b"):
        _sende(session, fenster, kommando)

    start = True
    for fenster in ("a", "b"):
        ok, blicke = _warte_auf_ruhe(f"{session}:{fenster}", warten)
        start = start and ok
        bilder.append((f"Fenster {fenster} nach dem Start", blicke[-1] if blicke else ""))
    halte("START", start, "beide Fenster sind nach dem Start zur Ruhe gekommen" if start
          else f"ein Fenster kam in {warten:.0f} s nicht zur Ruhe (Anmeldung oder Rueckfrage beim Start?)")

    _sende(session, "b", AUFTRAG_EINGABE)
    time.sleep(TAKT)
    ok, blicke = _warte_auf_ruhe(f"{session}:b", warten)
    kam_an = beantwortet(_bildschirm(f"{session}:b"), ANTWORT_EINGABE)
    bilder.append(("Fenster b nach dem ersten Auftrag", blicke[-1] if blicke else ""))
    halte("EINGABE", kam_an, f"die von aussen geschriebene Zeile wurde beantwortet ({ANTWORT_EINGABE})" if kam_an
          else f"keine Antwort {ANTWORT_EINGABE} auf dem Bildschirm von b")
    bewegt = bewegte_zeilen(blicke)
    halte("RUHE", ok, f"b stand nach der Antwort still; waehrend der Arbeit bewegten sich {len(bewegt)} Zeile(n)"
          if ok else f"b kam in {warten:.0f} s nicht zur Ruhe")

    _sende(session, "a", weitergabe_auftrag(Path(__file__).resolve(), session))
    time.sleep(TAKT)
    ok_a, blicke_a = _warte_auf_ruhe(f"{session}:a", warten)
    _, blicke_b = _warte_auf_ruhe(f"{session}:b", warten)
    erreicht = beantwortet(_bildschirm(f"{session}:b"), ANTWORT_WEITERGABE)
    bilder.append(("Fenster a nach dem Auftrag zur Weitergabe", blicke_a[-1] if blicke_a else ""))
    bilder.append(("Fenster b nach der Weitergabe", blicke_b[-1] if blicke_b else ""))
    if erreicht:
        halte("WEITERGABE", True, f"a hat b erreicht: b hat den Auftrag aus a beantwortet ({ANTWORT_WEITERGABE})")
    elif ok_a:
        halte("WEITERGABE", False, "a steht still, aber b hat nichts beantwortet — vermutlich eine Rueckfrage "
              "oder die Sandbox des Werkzeugs; der Bildschirm von a im Bericht zeigt es")
    else:
        halte("WEITERGABE", None, f"a kam in {warten:.0f} s nicht zur Ruhe")

    bericht.parent.mkdir(parents=True, exist_ok=True)
    bericht.write_text("\n".join(bericht_zeilen(kommando, session, beginn, schritte, bewegt, bilder)) + "\n",
                       encoding="utf-8")
    alle = all(urteil == "ja" for _, urteil, _ in schritte)
    print(f"Bericht: {bericht.resolve()}")
    print("ERGEBNIS: " + ("die Sitzungen tragen mit diesem Werkzeug" if alle
                          else "nicht alle Schritte tragen — der Bericht zeigt die Bildschirme"))
    print(f"Ansehen: tmux attach -t {session}   Beenden: tmux kill-session -t {session}")
    return 0 if alle else 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sub = parser.add_subparsers(dest="befehl", required=True)
    pr = sub.add_parser("probe", help="die vier Schritte fahren und einen Bericht schreiben")
    pr.add_argument("--kommando", required=True, help="womit ein Chat startet, z. B. \"codex\"")
    pr.add_argument("--session", default="sitzungsprobe")
    pr.add_argument("--bericht", default="runs/sitzungsprobe.md")
    pr.add_argument("--warten", type=float, default=180.0, help="Sekunden je Schritt, bis er als offen gilt")
    se = sub.add_parser("sende", help="einem Fenster eine Zeile schreiben und abschicken")
    se.add_argument("fenster")
    se.add_argument("text")
    se.add_argument("--session", default="sitzungsprobe")
    args = parser.parse_args(argv)
    try:
        if args.befehl == "sende":
            _sende(args.session, args.fenster, args.text)
            print(f"gesendet an {args.session}:{args.fenster}")
            return 0
        return probe(args.kommando, args.session, Path(args.bericht), args.warten)
    except ProbeFehler as fehler:
        print(f"HALT: {fehler}", file=sys.stderr)
        return 2
    except FileNotFoundError:
        print("HALT: tmux fehlt auf diesem Rechner", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
