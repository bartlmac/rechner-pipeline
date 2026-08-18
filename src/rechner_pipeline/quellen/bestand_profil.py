"""Bestandsabzug-Vorverdichter: deterministisches Spaltenprofil (Plan P5).

Der Transformations-Agent (Skill ``transformiere-quellbestand``) liest
nie die Rohdatei (P10) — er liest DIESES Profil: je Spalte eine
Typ-Heuristik, Beispielwerte, Kardinalitaet und Leeranteil. Das ist die
D3-Entscheidung (Vorverdichter je Quelltyp) fuer den Quelltyp
Bestandsabzug/CSV.

Deterministisch: gleiche Datei -> byte-identisches Profil (sortierte
Beispielwerte, keine Zeitstempel; der Erhebungszeitpunkt gehoert in die
Provenienz des Fragments, nicht ins Profil).

Run via::

    python -m rechner_pipeline.quellen.bestand_profil \\
        --input <abzug.csv> --out <profil.json>

Knoten: klv
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

#: Mehr Beispielwerte helfen dem Agenten (vollstaendige Kodierungs-
#: Wertemengen erkennen), zu viele blaehen das Profil — 20 distinct
#: reicht fuer Kodierungsspalten und macht grosse Kardinalitaet sichtbar.
MAX_BEISPIELE = 20

_DATUM = re.compile(r"^\d{2}\.\d{2}\.\d{4}$|^\d{4}-\d{2}-\d{2}$")
_GANZZAHL = re.compile(r"^-?\d+$")
_ZAHL = re.compile(r"^-?\d+[.,]\d+$")


def _typ(werte: List[str]) -> str:
    """Grobe Typ-Heuristik ueber die NICHT-leeren Werte einer Spalte."""
    gefuellt = [w for w in werte if w.strip()]
    if not gefuellt:
        return "leer"
    if all(_DATUM.match(w.strip()) for w in gefuellt):
        return "datum"
    if all(_GANZZAHL.match(w.strip()) for w in gefuellt):
        return "ganzzahl"
    if all(_GANZZAHL.match(w.strip()) or _ZAHL.match(w.strip())
           for w in gefuellt):
        return "zahl"
    return "text"


def baue_profil(pfad: Path, trenner: str = ";") -> Dict[str, Any]:
    """Spaltenprofil eines CSV-Abzugs (deterministisch, sortiert)."""
    roh = pfad.read_bytes()
    with pfad.open(encoding="utf-8", newline="") as f:
        zeilen = list(csv.reader(f, delimiter=trenner))
    if not zeilen:
        raise ValueError(f"{pfad}: leere Datei — kein Profil ableitbar")
    kopf, daten = zeilen[0], zeilen[1:]
    if len(set(kopf)) != len(kopf):
        doppelt = sorted({s for s in kopf if kopf.count(s) > 1})
        raise ValueError(
            f"{pfad}: doppelte Spaltennamen {doppelt} — ein Mapping "
            "waere mehrdeutig, Lieferung klaeren"
        )
    spalten: List[Dict[str, Any]] = []
    for i, name in enumerate(kopf):
        werte = [z[i] if i < len(z) else "" for z in daten]
        distinct = sorted({w.strip() for w in werte if w.strip()})
        spalten.append({
            "name": name,
            "typ": _typ(werte),
            "kardinalitaet": len(distinct),
            "leeranteil": (
                round(sum(1 for w in werte if not w.strip()) / len(werte), 4)
                if daten else 1.0
            ),
            "beispiele": distinct[:MAX_BEISPIELE],
            "beispiele_vollstaendig": len(distinct) <= MAX_BEISPIELE,
        })
    return {
        "quelle_datei": pfad.name,
        "quelle_sha256": hashlib.sha256(roh).hexdigest(),
        "zeilen": len(daten),
        "trenner": trenner,
        "spalten": spalten,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.quellen.bestand_profil",
        description="Spaltenprofil eines Bestandsabzugs (CSV) erzeugen.",
    )
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--trenner", default=";")
    args = parser.parse_args(argv)
    quelle = Path(args.input)
    if not quelle.is_file():
        print(f"bestand_profil: keine Datei: {quelle}", file=sys.stderr)
        return 2
    try:
        profil = baue_profil(quelle, args.trenner)
    except ValueError as exc:
        print(f"bestand_profil: {exc}", file=sys.stderr)
        return 20
    ziel = Path(args.out)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(
        json.dumps(profil, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"datei": str(ziel), "spalten": len(profil["spalten"]),
                      "zeilen": profil["zeilen"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
