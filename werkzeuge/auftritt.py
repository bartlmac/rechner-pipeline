"""``auftritt`` — den ganzen Entwurf mit EINEM Kommando aus den Quellen bauen.

Wie stellt man sicher, dass der Entwurf mit Codebasis und
Fall-Artefakten uebereinstimmt? Indem er nie etwas anderes IST als
deren Ergebnis: Der Entwurf wird nicht gepflegt, sondern erzeugt.
Dieses Kommando faehrt die ganze Kette aus den aktuellen Quellen —

    falldaten  ->  vorzeigeseite (--als-unterseite)  ->
    unternehmensseite (inkl. Fachdoku, Landkarte, Techstack)  ->
    vorschau

— und bricht ab, sobald ein Schritt bricht. Vor Sichtung und
Veroeffentlichung einmal laufen lassen; danach kann der Entwurf nicht
veralten. Veralten kann nur noch der VEROEFFENTLICHTE Stand, und
darueber urteilt ``drift.py``.

Meldet ``falldaten`` Luecken (Exit 3), wird WEITERGEBAUT und die
Luecke deutlich wiederholt: Fuer die Sichtung eines unvollstaendigen
Falls ist eine Seite mit sichtbaren Luecken die richtige Auskunft —
veroeffentlicht wird sie deshalb noch lange nicht.

Aufruf::

    python werkzeuge/auftritt.py --fall faelle/<fall> --name <kurzname> \\
        --abzug <abzug-1>.csv --abzug <abzug-2>.csv \\
        [--verlauf verlauf.md] [--out runs/seite] \\
        [--vorschau runs/vorzeige-vorschau]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

WERKZEUGE = Path(__file__).resolve().parent


def _schritt(kommando: List[str], erlaubt: tuple = (0,)) -> int:
    print(f"== {' '.join(kommando[1:3])}")
    lauf = subprocess.run(kommando)
    if lauf.returncode not in erlaubt:
        print(f"ABBRUCH der Kette (Exit {lauf.returncode}).",
              file=sys.stderr)
    return lauf.returncode


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="python werkzeuge/auftritt.py",
        description="Den ganzen Entwurf aus den aktuellen Quellen bauen.")
    p.add_argument("--fall", required=True, help="Fall-Arbeitsbereich")
    p.add_argument("--name", required=True,
                   help="URL-Segment des Falls unter migrationen/ "
                        "(z. B. baldrian) — so, wie die "
                        "Unternehmensseiten ihn verlinken")
    p.add_argument("--abzug", action="append", default=[],
                   help="registrierter Bestandsabzug, zeitliche "
                        "Reihenfolge (mehrfach)")
    p.add_argument("--verlauf", default=None,
                   help="Verlaufsprotokoll der Operator-Sitzung")
    p.add_argument("--out", default="runs/seite",
                   help="Push-Baum des Entwurfs (Vorgabe: runs/seite)")
    p.add_argument("--vorschau", default="runs/vorzeige-vorschau",
                   help="Vorschau-Verzeichnis; leer ('') laesst die "
                        "Vorschau aus")
    args = p.parse_args(argv)

    aus = Path(args.out)
    daten = aus.parent / "falldaten.json"

    rc = _schritt(
        [sys.executable, str(WERKZEUGE / "falldaten.py"),
         "--fall", args.fall,
         *(teil for a in args.abzug for teil in ("--abzug", a)),
         "--out", str(daten)],
        erlaubt=(0, 3))
    if rc not in (0, 3):
        return rc

    fallseite = [sys.executable, str(WERKZEUGE / "vorzeigeseite.py"),
                 "--fall", args.fall, "--daten", str(daten),
                 "--out", str(aus / "migrationen" / args.name),
                 "--als-unterseite"]
    if args.verlauf:
        fallseite += ["--verlauf", args.verlauf]
    if (zwischen := _schritt(fallseite)) != 0:
        return zwischen

    if (zwischen := _schritt(
            [sys.executable, str(WERKZEUGE / "unternehmensseite.py"),
             "--out", str(aus)])) != 0:
        return zwischen

    if args.vorschau:
        # Die Vorschau rendert mit dem System-python3 (python3-markdown);
        # die .venv traegt das Paket nicht.
        if (zwischen := _schritt(
                ["python3", str(WERKZEUGE / "vorschau.py"),
                 "--seite", str(aus), "--out", args.vorschau])) != 0:
            return zwischen

    if rc == 3:
        print()
        print("Der Fall hat LUECKEN (siehe falldaten oben) — der Entwurf "
              "traegt sie sichtbar. So nicht veroeffentlichen.",
              file=sys.stderr)
    return rc


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
