"""``betriebszweig`` — was der Workflow von plv-fiktion aus dem Zweig betrieb nimmt.

Weg C (Entscheid des Maintainers 09.10.2026): Der Tagesbetrieb schiebt jeden
Abend mit einem Deploy-Key in den Zweig ``betrieb`` von plv-fiktion, und nur
dorthin. Der Workflow in ``main`` baut daraus den Betriebsteil der Seite.
Zwei Pruefungen dieses Moduls laufen dort, beide halten den Bau an:

* ``zweig``: Im Zweig liegt genau, was die Routine ablegt, und nichts sonst:
  ``anker.jsonl``, ``A-B1.json`` und unter ``paket/`` die oeffentlichen
  Dateien des Stands-Pakets, flach, jede in ``stand.json`` genannt und keine
  Parquet-Tabelle. Ein Dateiname unter ``paket/`` besteht nur aus a-z, 0-9,
  ``_``, ``.`` und ``-``: Er geht als Verweis in die Seite (Entscheid des
  Maintainers 16.10.2026). Geprueft werden die Dateien, nicht die Liste in
  ``stand.json``; die nennt auch die Abschluesse unter ``abschluesse/``, die
  nicht im Zweig liegen. Kein Verzeichnis ``.github`` an keiner Stelle: Ein Push
  auf ``betrieb`` startet die Workflows, die im Stand von ``betrieb`` liegen.
  Der Workflow in ``main`` kann das nicht verhindern, aber er liefert dann
  nicht aus, und der Lauf steht sichtbar rot da (ADR-029, Variante
  "Restrisiko benennen"; eine Pfadsperre per Ruleset oder eine GitHub App
  ersetzen diese Pruefung nicht, sie kommen dazu).
* ``rahmen``: Nach dem Bau ist ausserhalb von ``betrieb/`` jede Datei des
  gebauten Baums dieselbe wie im Rahmen aus ``main``, und keine ist dazu
  gekommen oder weggefallen. Automatisch aendert sich nur der Betriebsteil.

Aufruf::

    python werkzeuge/betriebszweig.py zweig <checkout des Zweigs betrieb>
    python werkzeuge/betriebszweig.py rahmen <checkout von main> <gebauter Baum>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

#: Die Dateien in der Wurzel des Zweigs, die die Routine ablegt.
WURZEL = ("anker.jsonl", "A-B1.json")
#: Das Paket im Zweig und die Endungen seiner oeffentlichen Dateien.
PAKET = "paket"
PAKET_ENDUNGEN = (".html", ".json", ".jsonl")
#: Die Zeichen eines Dateinamens im Paket; ``unternehmensseite`` haelt jeden
#: Namen, der in einen Verweis geht, noch einmal dagegen.
DATEINAME = re.compile(r"[a-z0-9_.-]+")
#: Der Betriebsteil im gebauten Baum (unternehmensseite.BETRIEB_DIR).
BETRIEB_DIR = "betrieb"


def zweig(wurzel: Path) -> List[str]:
    """Befunde zum Inhalt des Zweigs betrieb (ein Checkout, ``.git`` zaehlt nicht)."""
    befunde: List[str] = []
    dateien: List[str] = []
    for p in sorted(wurzel.rglob("*")):
        rel = p.relative_to(wurzel)
        if rel.parts[0] == ".git":
            continue
        if ".github" in rel.parts:
            befunde.append(f"{rel.as_posix()}: ein Workflow-Verzeichnis im Zweig betrieb")
            continue
        if p.is_symlink():
            befunde.append(f"{rel.as_posix()}: ein Symlink")
        elif p.is_file():
            dateien.append(rel.as_posix())
    stand: Dict = {}
    try:
        stand = json.loads((wurzel / PAKET / "stand.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        befunde.append(f"{PAKET}/stand.json: nicht lesbar ({exc})")
    genannt = set((stand.get("dateien") or {}) if isinstance(stand, dict) else ())
    for name in WURZEL:
        if name not in dateien:
            befunde.append(f"{name}: fehlt")
    for rel in dateien:
        teile = rel.split("/")
        if len(teile) == 1:
            if rel not in WURZEL:
                befunde.append(f"{rel}: nicht erlaubt")
        elif teile[0] != PAKET or len(teile) != 2:
            befunde.append(f"{rel}: nicht erlaubt (das Paket liegt flach unter {PAKET}/)")
        elif not DATEINAME.fullmatch(teile[1]):
            befunde.append(f"{rel}: Dateiname mit anderen Zeichen als a-z, 0-9, _ . -")
        elif teile[1] != "stand.json" and teile[1] not in genannt:
            befunde.append(f"{rel}: steht nicht in stand.json")
        elif not teile[1].endswith(PAKET_ENDUNGEN):
            befunde.append(f"{rel}: keine oeffentliche Datei des Pakets")
    return befunde


def _sha(pfad: Path) -> str:
    return hashlib.sha256(pfad.read_bytes()).hexdigest()


def _baum(wurzel: Path) -> Dict[str, Path]:
    return {p.relative_to(wurzel).as_posix(): p for p in sorted(wurzel.rglob("*"))
            if p.is_file() and p.relative_to(wurzel).parts[0] not in (".git", BETRIEB_DIR)}


def rahmen(rahmen_baum: Path, seite: Path) -> List[str]:
    """Befunde, wenn sich ausserhalb von ``betrieb/`` etwas geaendert hat."""
    befunde: List[str] = []
    if (rahmen_baum / BETRIEB_DIR).exists():
        befunde.append(f"{BETRIEB_DIR}/ liegt schon im Rahmen; den Betriebsteil baut nur der Workflow")
    alt, neu = _baum(rahmen_baum), _baum(seite)
    for rel in sorted(set(alt) - set(neu)):
        befunde.append(f"{rel}: im Rahmen, nicht im gebauten Baum")
    for rel in sorted(set(neu) - set(alt)):
        befunde.append(f"{rel}: im gebauten Baum, nicht im Rahmen")
    for rel in sorted(set(alt) & set(neu)):
        if _sha(alt[rel]) != _sha(neu[rel]):
            befunde.append(f"{rel}: anders als im Rahmen")
    return befunde


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="python werkzeuge/betriebszweig.py",
                                description=__doc__.splitlines()[0])
    teil = p.add_subparsers(dest="pruefung", required=True)
    q = teil.add_parser("zweig", help="was im Zweig betrieb liegen darf")
    q.add_argument("checkout")
    q = teil.add_parser("rahmen", help="ausserhalb von betrieb/ alles wie in main")
    q.add_argument("rahmen")
    q.add_argument("seite")
    args = p.parse_args(argv)
    if args.pruefung == "zweig":
        befunde, titel = zweig(Path(args.checkout)), "Zweig betrieb"
    else:
        befunde, titel = rahmen(Path(args.rahmen), Path(args.seite)), "Rahmen"
    for b in befunde:
        print(f"  BEFUND {b}")
    print(f"{titel}: " + ("mit Befund, nicht ausgeliefert" if befunde else "ohne Befund"))
    return 1 if befunde else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
