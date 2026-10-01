#!/usr/bin/env python3
"""Einen Fall aufzeichnen: die ganze tmux-Ansicht, ohne etwas zu installieren.

Aufgenommen wird mit ``script`` aus util-linux (auf jedem Linux vorhanden):
Es schneidet mit, was der Terminal-Client von ``tmux attach`` empfaengt —
tmux zeichnet das Layout selbst, also sind alle Panes der Session im Bild.
Das Ergebnis sind zwei Dateien, Ausgabe und Zeitmarken.

Aus ihnen erzeugt dieses Werkzeug eine Aufzeichnung im offenen
asciicast-Format (Version 2, ``.cast``): eine kleine Textdatei, in der der
Text kopierbar bleibt. Sie laeuft in jedem asciinema-Player (Terminal oder
Browser); ein GIF oder MP4 entsteht daraus mit ``agg`` und ``ffmpeg``
(siehe werkzeuge/README.md) — das braucht kein Programm auf dem Host, auf
dem aufgenommen wird.

    python werkzeuge/aufzeichnung.py aufnehmen --session vorfuehrung --out runs/fall3
    python werkzeuge/aufzeichnung.py cast --basis runs/fall3
    scriptreplay -T runs/fall3.tim -O runs/fall3.out      # Wiedergabe ohne alles

Die Aufnahme zeigt, was auf dem Bildschirm steht — auch einen Schluessel,
der versehentlich angezeigt wird. Schluesseldateien werden in der
Vorfuehrung nur als Pfad genannt, nie ausgegeben.
"""

from __future__ import annotations

import argparse
import codecs
import json
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterator, List, Optional, Tuple


class AufzeichnungFehler(ValueError):
    """Die Dateien einer Aufnahme passen nicht zusammen oder sind nicht lesbar."""


def _groesse(kopfzeile: str) -> Tuple[int, int]:
    """Spalten und Zeilen aus der Kopfzeile von ``script`` (``COLUMNS="194"
    LINES="59"``). Ohne die Angabe gibt es keine Vorgabe: Eine geratene
    Groesse zeichnete das Layout falsch um."""
    spalten = re.search(r'COLUMNS="(\d+)"', kopfzeile)
    zeilen = re.search(r'LINES="(\d+)"', kopfzeile)
    if not (spalten and zeilen):
        raise AufzeichnungFehler(
            "die Kopfzeile der Aufnahme nennt keine Terminalgroesse (COLUMNS/LINES) — "
            "Ausweg: --spalten und --zeilen angeben")
    return int(spalten.group(1)), int(zeilen.group(1))


def ereignisse(ausgabe: bytes, zeitmarken: str) -> Iterator[Tuple[float, str]]:
    """Die Ausgabe-Ereignisse einer ``script``-Aufnahme im klassischen Format:
    je Zeile der Zeitmarken ``<Abstand in Sekunden> <Bytes>``. Die Kopfzeile
    der Ausgabe ("Script started on ...") zaehlt nicht zu den Bytes.

    Ein Zeichen, das ueber eine Ereignisgrenze reicht, erscheint ganz im
    naechsten Ereignis (inkrementelle UTF-8-Dekodierung); ein Ereignis ohne
    vollstaendiges Zeichen entfaellt."""
    ende_kopf = ausgabe.find(b"\n")
    if ende_kopf < 0:
        raise AufzeichnungFehler("die Ausgabedatei hat keine Kopfzeile")
    rest = ausgabe[ende_kopf + 1:]
    dekoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    zeit, ort = 0.0, 0
    for nummer, zeile in enumerate(zeitmarken.splitlines(), 1):
        if not zeile.strip():
            continue
        teile = zeile.split()
        try:
            abstand, anzahl = float(teile[0]), int(teile[1])
        except (IndexError, ValueError) as exc:
            raise AufzeichnungFehler(
                f"Zeitmarken Zeile {nummer}: erwartet '<Sekunden> <Bytes>' (klassisches "
                f"Format, script -m classic), gelesen {zeile!r}") from exc
        if abstand < 0 or anzahl < 0 or ort + anzahl > len(rest):
            raise AufzeichnungFehler(
                f"Zeitmarken Zeile {nummer}: {anzahl} Bytes ab Stelle {ort}, die Ausgabe hat "
                f"{len(rest)} — Ausgabe und Zeitmarken gehoeren nicht zusammen")
        zeit += abstand
        text = dekoder.decode(rest[ort:ort + anzahl])
        ort += anzahl
        if text:
            yield round(zeit, 6), text


def cast_zeilen(ausgabe: bytes, zeitmarken: str, *, spalten: Optional[int] = None,
                zeilen: Optional[int] = None, titel: Optional[str] = None) -> List[str]:
    """Die Zeilen einer asciicast-v2-Datei: Kopf, dann je Ereignis
    ``[Zeit, "o", Text]``."""
    if spalten is None or zeilen is None:
        kopfzeile = ausgabe[:max(0, ausgabe.find(b"\n"))].decode("utf-8", errors="replace")
        spalten, zeilen = _groesse(kopfzeile)
    kopf = {"version": 2, "width": spalten, "height": zeilen}
    if titel:
        kopf["title"] = titel
    aus = [json.dumps(kopf, ensure_ascii=False, sort_keys=True)]
    aus += [json.dumps([zeit, "o", text], ensure_ascii=False)
            for zeit, text in ereignisse(ausgabe, zeitmarken)]
    return aus


def aufnahme_kommando(session: str, basis: Path) -> List[str]:
    return ["script", "-q", "-m", "classic", "-O", f"{basis}.out", "-T", f"{basis}.tim",
            "-c", "tmux attach -t " + shlex.quote(session)]


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="python werkzeuge/aufzeichnung.py",
                                description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="kommando", required=True)
    a = sub.add_parser("aufnehmen", help="die tmux-Session mitschneiden (endet mit dem Abhaengen)")
    a.add_argument("--session", default="vorfuehrung")
    a.add_argument("--out", type=Path, required=True, help="Basisname: <out>.out und <out>.tim")
    c = sub.add_parser("cast", help="aus <basis>.out und <basis>.tim eine .cast-Datei erzeugen")
    c.add_argument("--basis", type=Path, required=True)
    c.add_argument("--out", type=Path, default=None, help="Ziel (Standard: <basis>.cast)")
    c.add_argument("--spalten", type=int, default=None)
    c.add_argument("--zeilen", type=int, default=None)
    c.add_argument("--titel", default=None)
    args = p.parse_args(argv)

    if args.kommando == "aufnehmen":
        if shutil.which("script") is None or shutil.which("tmux") is None:
            print("aufzeichnung: script (util-linux) und tmux werden gebraucht", file=sys.stderr)
            return 2
        for endung in (".out", ".tim"):
            if Path(f"{args.out}{endung}").exists():
                print(f"aufzeichnung: {args.out}{endung} liegt schon — eine Aufnahme wird nie "
                      "ueberschrieben; anderen Basisnamen waehlen", file=sys.stderr)
                return 2
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        return subprocess.run(aufnahme_kommando(args.session, args.out)).returncode

    ziel = args.out or Path(f"{args.basis}.cast")
    if ziel.exists():
        print(f"aufzeichnung: {ziel} liegt schon — wird nicht ueberschrieben", file=sys.stderr)
        return 2
    try:
        zeilen = cast_zeilen(
            Path(f"{args.basis}.out").read_bytes(),
            Path(f"{args.basis}.tim").read_text(encoding="utf-8"),
            spalten=args.spalten, zeilen=args.zeilen, titel=args.titel)
    except (OSError, AufzeichnungFehler) as exc:
        print(f"aufzeichnung: {exc}", file=sys.stderr)
        return 2
    ziel.write_text("\n".join(zeilen) + "\n", encoding="utf-8", newline="\n")
    print(f"{ziel}: {len(zeilen) - 1} Ereignisse, {zeilen[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
