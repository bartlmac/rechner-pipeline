"""``drift`` — stimmt die veroeffentlichte Seite noch mit dem Entwurf ueberein?

Die Seite wird je Lauf aus Repo und Fall-Artefakten gebaut; zwischen
zwei Veroeffentlichungen driftet der Live-Stand vom Repo weg. Dieses
Werkzeug URTEILT darueber — mehr nicht: Es vergleicht einen frisch
gebauten Entwurf mit dem Stand des ``gh-pages``-Branches und endet bei
Abweichung mit Befund. Veroeffentlicht wird weiterhin ausschliesslich
von Hand (Runbook, Abschnitt "Je Lauf"): Ein Skript, das selbst
publizierte, waere ein Automat mit Push-Recht — genau das nicht.

**Volatile Stempel zaehlen nicht als Drift.** Das Veroeffentlichungs-
datum, der Systemstand-Stempel der Fall-Seiten und der Bau-Commit der
Landkarte aendern sich mit jedem Bau, ohne dass sich inhaltlich etwas
bewegt haette. Sie werden vor dem Vergleich normalisiert — sonst
schluege der Test immer, und ein Alarm, der immer schlaegt, wird
abgeschaltet.

Aufruf (nach dem Bau des Entwurfs, siehe Runbook)::

    python werkzeuge/drift.py --seite runs/seite [--ref gh-pages]

Exit 0: kein Drift. Exit 1: Drift, die Abweichungen sind gelistet.
Exit 2: Bedienfehler (kein Entwurf, Ref nicht vorhanden).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

#: Provenienz-Zeilen der Fall-Seiten, die sich je Bau aendern DUERFEN.
VOLATIL = (
    re.compile(r"^\| Veröffentlicht \|.*$", re.MULTILINE),
    re.compile(r"^\| Systemstand \|.*$", re.MULTILINE),
    re.compile(r"^\| Arbeitsbaum sauber \|.*$", re.MULTILINE),
)

#: Git-Kurz-SHAs in der Landkarte — der Stempel des Bau-Commits. Nur
#: dort: In den Artefakten waeren Hex-Woerter Pruefsummen, und die
#: sollen gerade NICHT weg-normalisiert werden.
HEX = re.compile(r"\b[0-9a-f]{7,12}\b")


def _normalisiert(name: str, inhalt: bytes) -> bytes:
    try:
        text = inhalt.decode("utf-8")
    except UnicodeDecodeError:
        return inhalt
    if name == "index.md":
        for muster in VOLATIL:
            text = muster.sub("| (volatil) |", text)
    if name == "landkarte.html":
        text = HEX.sub("(stand)", text)
    return text.encode("utf-8")


def _baum(wurzel: Path) -> Dict[str, bytes]:
    return {
        str(p.relative_to(wurzel)): _normalisiert(p.name, p.read_bytes())
        for p in sorted(wurzel.rglob("*")) if p.is_file()
    }


def vergleiche(entwurf: Path, veroeffentlicht: Path) -> Dict[str, List[str]]:
    """Beide Baeume nach Normalisierung gegenueberstellen."""
    neu, alt = _baum(entwurf), _baum(veroeffentlicht)
    return {
        "nur_im_entwurf": sorted(set(neu) - set(alt)),
        "nur_veroeffentlicht": sorted(set(alt) - set(neu)),
        "geaendert": sorted(
            name for name in set(neu) & set(alt) if neu[name] != alt[name]),
    }


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="python werkzeuge/drift.py",
        description="Entwurf gegen den veroeffentlichten Stand halten — "
                    "urteilt nur, veroeffentlicht nichts.")
    p.add_argument("--seite", required=True,
                   help="frisch gebauter Entwurf (Push-Baum, runs/seite)")
    p.add_argument("--ref", default="gh-pages",
                   help="Git-Ref des veroeffentlichten Stands "
                        "(Vorgabe: gh-pages; z. B. origin/gh-pages)")
    p.add_argument("--repo", default=".", help="Repo mit dem Pages-Branch")
    args = p.parse_args(argv)

    seite = Path(args.seite).resolve()
    if not (seite / "index.md").is_file():
        print(f"Kein gebauter Entwurf: {seite} — erst bauen "
              "(Runbook, 'Die Seite bauen').", file=sys.stderr)
        return 2

    archiv = subprocess.run(
        ["git", "archive", args.ref], cwd=args.repo, capture_output=True)
    if archiv.returncode != 0:
        print(f"Ref {args.ref!r} nicht lesbar: "
              f"{archiv.stderr.decode(errors='replace').strip()}",
              file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="drift-") as tmp:
        entpackt = subprocess.run(["tar", "-x", "-C", tmp],
                                  input=archiv.stdout, capture_output=True)
        if entpackt.returncode != 0:
            print("Archiv nicht entpackbar: "
                  f"{entpackt.stderr.decode(errors='replace').strip()}",
                  file=sys.stderr)
            return 2
        befund = vergleiche(seite, Path(tmp))

    treffer = sum(len(v) for v in befund.values())
    if not treffer:
        print(f"Kein Drift: {seite} entspricht {args.ref} "
              "(volatile Stempel normalisiert).")
        return 0

    for kennung, namen in (("NEU", befund["nur_im_entwurf"]),
                           ("FEHLT IM ENTWURF", befund["nur_veroeffentlicht"]),
                           ("GEAENDERT", befund["geaendert"])):
        for name in namen:
            print(f"  {kennung}: {name}")
    print(f"DRIFT: {treffer} Datei(en) weichen zwischen {seite.name} "
          f"und {args.ref} ab.")
    print("Aktualisieren ist eine menschliche Handlung — Runbook, "
          "Abschnitt 'Je Lauf'.")
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
