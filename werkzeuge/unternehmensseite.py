"""``unternehmensseite`` — die Seiten des fiktiven Unternehmens zusammenbauen.

Die Vorfuehrung tritt als Unternehmensauftritt der (frei erfundenen)
Pfefferminzia Lebensversicherung AG auf: eine Startseite, Bereiche
(Aktuariat, IT, ...) und darunter die generierten Migrationsberichte
(``vorzeigeseite.py``, je Fall unter ``migrationen/<fall>/``).

Die Unternehmensseiten sind HANDGESCHRIEBENE, versionierte Quellen
unter ``vorzeige-seite/`` — im Gegensatz zu den Fall-Seiten, die je
Lauf aus den Artefakten entstehen. Dieses Werkzeug kopiert sie in den
Push-Baum und erzwingt dabei zwei Dinge:

*Die Banderole.* Je echter der Auftritt wirkt, desto wichtiger die
Kennzeichnung: JEDE Seite muss den Fiktions-Hinweis tragen. Eine Seite
ohne ihn wird nicht gebaut — eine oeffentliche Seite, die wie ein
echter Versicherer aussieht, waere keine Vorfuehrung mehr, sondern
eine Behauptung.

*Die Regie-Sperre.* Wie bei der Fall-Seite gelangt nichts aus den
Spielleiter-Bereichen in die Veroeffentlichung.

Aufruf (nach dem Bau der Fall-Seiten in denselben Baum)::

    python werkzeuge/unternehmensseite.py --quellen vorzeige-seite \\
        --out runs/seite
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import List, Optional

from vorzeigeseite import VeroeffentlichungFehler, _pruefe_regie

#: Jede Unternehmensseite muss diesen Hinweis woertlich tragen — die
#: Banderole oben auf der Seite. Fehlt er, wird nicht gebaut.
BANDEROLE = "Fiktives Unternehmen"


def baue(quellen: Path, ziel: Path) -> List[str]:
    """Die Quellseiten in den Push-Baum spiegeln, mit beiden Zwaengen."""
    if not (quellen / "index.md").is_file():
        raise VeroeffentlichungFehler(
            f"Keine Unternehmensseiten unter {quellen} (index.md fehlt).")
    if not (quellen / "_config.yml").is_file():
        raise VeroeffentlichungFehler(
            f"{quellen}/_config.yml fehlt — ohne Jekyll-Konfiguration "
            "nimmt GitHub Pages ein Vorgabethema, das die Seiten bricht.")

    kopiert: List[str] = []
    for datei in sorted(quellen.rglob("*")):
        if not datei.is_file():
            continue
        _pruefe_regie(datei)
        if datei.suffix == ".md" and BANDEROLE not in datei.read_text(
                encoding="utf-8"):
            raise VeroeffentlichungFehler(
                f"{datei.relative_to(quellen)} traegt die Banderole "
                f"({BANDEROLE!r}) nicht. Jede Unternehmensseite muss den "
                "Fiktions-Hinweis tragen — sonst saehe der Auftritt aus "
                "wie ein echter Versicherer.")
        zielpfad = ziel / datei.relative_to(quellen)
        zielpfad.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(datei, zielpfad)
        kopiert.append(str(zielpfad.relative_to(ziel)))
    return kopiert


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="python werkzeuge/unternehmensseite.py",
        description="Unternehmensseiten der Vorfuehrung in den Push-Baum "
                    "zusammenbauen.")
    p.add_argument("--quellen", default="vorzeige-seite",
                   help="versionierte Quellseiten (Vorgabe: vorzeige-seite)")
    p.add_argument("--out", required=True,
                   help="Push-Baum der Seite; die Fall-Seiten liegen dort "
                        "unter migrationen/<fall>/")
    args = p.parse_args(argv)

    quellen = Path(args.quellen).resolve()
    ziel = Path(args.out).resolve()
    ziel.mkdir(parents=True, exist_ok=True)
    try:
        kopiert = baue(quellen, ziel)
    except VeroeffentlichungFehler as exc:
        print(f"ABBRUCH: {exc}", file=sys.stderr)
        return 1

    print(f"{ziel}: {len(kopiert)} Unternehmensseiten-Dateien")
    faelle = sorted(
        p.parent.name for p in (ziel / "migrationen").glob("*/index.md")
    ) if (ziel / "migrationen").is_dir() else []
    if faelle:
        print(f"  eingehaengte Migrationsberichte: {', '.join(faelle)}")
    else:
        print("  noch KEIN Migrationsbericht eingehaengt "
              "(vorzeigeseite.py --out <ziel>/migrationen/<fall>)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
