"""``auftritt`` — den ganzen Entwurf mit EINEM Kommando aus den Quellen bauen.

Wie stellt man sicher, dass der Entwurf mit Codebasis und
Fall-Artefakten uebereinstimmt? Indem er nie etwas anderes IST als
deren Ergebnis: Der Entwurf wird nicht gepflegt, sondern erzeugt.
Dieses Kommando faehrt die ganze Kette aus den aktuellen Quellen —

    Rahmen:       falldaten (Fall)  ->  vorzeigeseite (--als-unterseite)  ->
                  unternehmensseite --teil rahmen (inkl. Fachdoku, Landkarte,
                  Techstack)
    Betriebsteil: falldaten (Paket, Anker, A-B1, ohne Fall)  ->
                  unternehmensseite --teil betrieb
    dann:         Wache (bereinigung --wache)  ->  vorschau  ->
                  Seitenpruefung (seitenpruefung alle)

— und bricht ab, sobald ein Schritt bricht. Vor Sichtung und
Veroeffentlichung einmal laufen lassen; danach kann der Entwurf nicht
veralten. Veralten kann nur noch der VEROEFFENTLICHTE Stand, und
darueber urteilt ``drift.py``.

Die Seite hat zwei Teile (Entscheid des Maintainers 09.10.2026, Weg C):
Der Rahmen aendert sich nur per Pull Request, der Betriebsteil
(``betrieb/``) jeden Abend mit dem gefuehrten Bestand. ``--teil`` baut
einen davon oder beide:

* ``beide`` (Vorgabe): die ganze Seite, mit allen Pruefungen — fuer die
  Sichtung und den Pull Request des Rahmens.
* ``rahmen``: nur der Rahmen, ohne Stands-Paket. Seine Verweise in den
  Betriebsteil lassen sich so nicht pruefen; deshalb ohne Vorschau und
  Seitenpruefung.
* ``betrieb``: nur ``betrieb/``, in einen Baum, der den Rahmen schon
  traegt (``--out``), ohne Fall — so baut der Workflow von plv-fiktion den
  Abend. Die Seitenpruefung laeuft dann ohne Fall und prueft die Kennungen
  nur im Betriebsteil.

Meldet ``falldaten`` Luecken (Exit 3), wird WEITERGEBAUT und die
Luecke deutlich wiederholt: Fuer die Sichtung eines unvollstaendigen
Falls ist eine Seite mit sichtbaren Luecken die richtige Auskunft —
veroeffentlicht wird sie deshalb noch lange nicht.

Aufruf::

    python werkzeuge/auftritt.py --fall faelle/<fall> --name <kurzname> \\
        --abzug <abzug-1>.csv --abzug <abzug-2>.csv --film <film>.mp4 \\
        --stands-paket <paket> --anker <anker>.jsonl --ab1 <A-B1>.json \\
        [--verlauf verlauf.md] [--out runs/seite] \\
        [--vorschau runs/vorzeige-vorschau]

    python werkzeuge/auftritt.py --teil betrieb --out <baum mit Rahmen> \\
        --stands-paket <paket> --anker <anker>.jsonl --ab1 <A-B1>.json \\
        --vorschau <vorschau>
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

WERKZEUGE = Path(__file__).resolve().parent
#: Der Codebaum, aus dem gebaut wird. Quellseiten, Fachdokumente und Repo
#: gehen ausdruecklich von hier an die Schritte: Der Workflow von plv-fiktion
#: ruft die Kette aus einem anderen Verzeichnis auf (der Code liegt dort
#: unter code/), und eine Vorgabe relativ zum Arbeitsverzeichnis faende
#: nichts oder etwas anderes.
CODE = WERKZEUGE.parent


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
    p.add_argument("--teil", choices=("beide", "rahmen", "betrieb"), default="beide",
                   help="beide (Vorgabe), nur der Rahmen oder nur der Betriebsteil "
                        "betrieb/ in einen Baum mit Rahmen")
    p.add_argument("--fall", default=None, help="Fall-Arbeitsbereich (Rahmen)")
    p.add_argument("--name", default=None,
                   help="URL-Segment des Falls unter migrationen/ "
                        "(z. B. baldrian) — so, wie die "
                        "Unternehmensseiten ihn verlinken (Rahmen)")
    p.add_argument("--abzug", action="append", default=[],
                   help="registrierter Bestandsabzug, zeitliche "
                        "Reihenfolge (mehrfach)")
    p.add_argument("--verlauf", default=None,
                   help="Verlaufsprotokoll der Operator-Sitzung")
    p.add_argument("--stands-paket", dest="stands_paket", default=None,
                   help="Stands-Paket der Laufzeitumgebung (betrieb.seite "
                        "--paket): der gefuehrte Bestand (Betriebsteil)")
    p.add_argument("--anker", default=None,
                   help="Ankerdatei des Stands-Pakets (betrieb.seite "
                        "--anker). Pflicht mit --stands-paket: Das Paket wird "
                        "gegen einen Bezug AUSSERHALB des Pakets geprueft")
    p.add_argument("--ab1", default=None,
                   help="Snapshot der A-B1, der den Ankersatz des Pakets bindet "
                        "(Betriebsteil)")
    p.add_argument("--oeffentliches-paket", dest="oeffentlich", action="store_true",
                   help="das Paket traegt nur seine oeffentlichen Dateien, ohne "
                        "Tagesjournal und Abschluesse (so liegt es im Zweig betrieb "
                        "von plv-fiktion)")
    p.add_argument("--film", default=None,
                   help="die freigegebene Filmdatei der Startseite "
                        "(unternehmensseite.FILM; Rahmen)")
    p.add_argument("--out", default="runs/seite",
                   help="Push-Baum des Entwurfs (Vorgabe: runs/seite)")
    p.add_argument("--vorschau", default="runs/vorzeige-vorschau",
                   help="Vorschau-Verzeichnis; leer ('') laesst die "
                        "Vorschau aus")
    args = p.parse_args(argv)

    rahmen = args.teil in ("beide", "rahmen")
    betrieb = args.teil in ("beide", "betrieb")
    if rahmen and not (args.fall and args.name and args.film):
        p.error("der Rahmen braucht --fall, --name und --film")
    if betrieb and not (args.stands_paket and args.anker):
        p.error("der Betriebsteil braucht --stands-paket und --anker (und --ab1 fuer "
                "eine Auslieferung)")

    aus = Path(args.out)
    daten = aus.parent / "falldaten.json"
    betriebsdaten = aus.parent / "betriebsdaten.json"
    rc = 0

    if rahmen:
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
                     "--als-unterseite", "--repo", str(CODE)]
        if args.verlauf:
            fallseite += ["--verlauf", args.verlauf]
        # Auch die Fall-Seite meldet Luecken mit Exit 3 (T20-03): Sie steht,
        # traegt die Luecken sichtbar, und die Kette baut weiter — aber der
        # Gesamt-Exit bleibt 3.
        zwischen = _schritt(fallseite, erlaubt=(0, 3))
        if zwischen not in (0, 3):
            return zwischen
        rc = 3 if 3 in (rc, zwischen) else rc

        if (zwischen := _schritt(
                [sys.executable, str(WERKZEUGE / "unternehmensseite.py"),
                 "--teil", "rahmen", "--daten", str(daten), "--out", str(aus),
                 "--film", args.film, "--quellen", str(CODE / "plv" / "seite"),
                 "--docs", str(CODE / "docs"), "--repo", str(CODE)])) != 0:
            return zwischen

    if betrieb:
        zwischen = _schritt(
            [sys.executable, str(WERKZEUGE / "falldaten.py"),
             "--stands-paket", args.stands_paket, "--anker", args.anker,
             *(("--ab1", args.ab1) if args.ab1 else ()),
             *(("--oeffentliches-paket",) if args.oeffentlich else ()),
             "--out", str(betriebsdaten)],
            erlaubt=(0, 3))
        if zwischen not in (0, 3):
            return zwischen
        rc = 3 if 3 in (rc, zwischen) else rc
        if (zwischen := _schritt(
                [sys.executable, str(WERKZEUGE / "unternehmensseite.py"),
                 "--teil", "betrieb", "--daten", str(betriebsdaten),
                 "--out", str(aus), "--quellen", str(CODE / "plv" / "seite")])) != 0:
            return zwischen

    # Die Wache liest jede Datei des Push-Baums — nicht nur die Belege des
    # Falls, auch Stands-Paket, Fachdokumente, Landkarte: kein Hostpfad,
    # kein gesperrtes Wort (werkzeuge/bereinigung.py). Ein Befund haelt an.
    if (zwischen := _schritt(
            [sys.executable, str(WERKZEUGE / "bereinigung.py"),
             "--wache", str(aus)])) != 0:
        return zwischen

    # Ohne Betriebsteil zeigen die Verweise des Rahmens in ein leeres
    # betrieb/; Vorschau und Pruefung brauchen die ganze Seite.
    if args.vorschau and betrieb:
        # Die Vorschau rendert mit dem System-python3 (python3-markdown);
        # die .venv traegt das Paket nicht.
        if (zwischen := _schritt(
                ["python3", str(WERKZEUGE / "vorschau.py"),
                 "--seite", str(aus), "--out", args.vorschau])) != 0:
            return zwischen

        # Die Pruefungen vor der Veroeffentlichung (Entscheid des Maintainers
        # 04.10.2026): Verweise der Vorschau, Paket gegen stand.json, jede
        # angezeigte Kennung mit Quelle, Breite auf dem Telefon. Ein Befund
        # haelt an. Ohne Fall (nur der Betriebsteil) prueft sie die
        # Kennungen nur unter betrieb/.
        fall = (["--fall", args.fall, "--name", args.name, "--daten", str(daten)]
                if rahmen else [])
        if (zwischen := _schritt(
                [sys.executable, str(WERKZEUGE / "seitenpruefung.py"), "alle",
                 "--seite", str(aus), "--vorschau", args.vorschau, *fall,
                 "--paket", args.stands_paket, "--anker", args.anker,
                 *(("--ab1", args.ab1) if args.ab1 else ()),
                 "--repo", str(CODE)])) != 0:
            return zwischen

    if rc == 3:
        print()
        print("Das Modell hat LUECKEN (siehe falldaten oben) — der Entwurf "
              "traegt sie sichtbar. So nicht veroeffentlichen.",
              file=sys.stderr)
    return rc


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
