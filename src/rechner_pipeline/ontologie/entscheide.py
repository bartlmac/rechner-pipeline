"""``entscheide`` — die menschliche Diskrepanz-Aufloesung als CLI (G-1).

Der Vorgang, den das Gate G-1 meint: ein benannter Mensch waehlt
zwischen den Lesarten einer Diskrepanz und begruendet die Wahl. Eine
VORLAEUFIGE (Agenten-)Aufloesung wird dabei ersetzt — das ist der
einzige erlaubte Weg, eine Aufloesung zu aendern; eine endgueltige
menschliche Entscheidung ist nur ueber eine neue T-Box-/A-Box-Revision
revidierbar, nicht durch Ueberschreiben.

Run via::

    python -m rechner_pipeline.ontologie.entscheide --fall faelle/klv-tg2015 \\
        --diskrepanz "klv/tg2015/zelle:nichtraucher,einzel#zins" \\
        --wert 0.0175 --entscheider "Bartek" \\
        --begruendung "Dirk bestaetigt: Rechner-Stand gilt, Meldung wird korrigiert"

    # oder alle auf einmal derselben Lesart-Quelle folgend:
    ... --alle-vorlaeufigen --quelle Tarifrechner_KLV_TG2015.xlsm ...

Knoten: klv
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import List, Optional

from rechner_pipeline.ontologie.abox import lade, speichere, validate_abox
from rechner_pipeline.ontologie.befuellung import (
    BefuellungsFehler,
    loese_diskrepanz_auf,
)


def _jetzt() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def _wert_parsen(roh: str):
    try:
        return json.loads(roh)
    except json.JSONDecodeError:
        return roh


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.ontologie.entscheide",
        description="Diskrepanz(en) menschlich aufloesen (Gate G-1).",
    )
    parser.add_argument("--fall", required=True)
    parser.add_argument("--entscheider", required=True)
    parser.add_argument("--begruendung", required=True)
    parser.add_argument(
        "--rolle", required=True, choices=["mensch"],
        help="Endgueltige Aufloesungen sind Menschen vorbehalten; "
        "Agenten nutzen die API mit vorlaeufig=True.",
    )
    parser.add_argument("--diskrepanz", default=None,
                        help="ID (<knoten>#<feld>); alternativ --alle-vorlaeufigen.")
    parser.add_argument("--wert", default=None,
                        help="Gewaehlter Wert (JSON-Literal oder String).")
    parser.add_argument(
        "--alle-vorlaeufigen", action="store_true",
        help="Alle vorlaeufig aufgeloesten Diskrepanzen endgueltig "
        "entscheiden, jeweils zur Lesart der --quelle.",
    )
    parser.add_argument("--quelle", default=None,
                        help="Quelldatei, deren Lesart bei --alle-vorlaeufigen gilt.")
    args = parser.parse_args(argv)

    fall = Path(args.fall)
    try:
        abox = lade(fall)
    except Exception as exc:  # noqa: BLE001
        print(f"entscheide: A-Box unlesbar: {exc}", file=sys.stderr)
        return 1

    jetzt = _jetzt()
    entschieden: List[str] = []
    try:
        if args.alle_vorlaeufigen:
            if args.diskrepanz or args.wert is not None:
                print("entscheide: --alle-vorlaeufigen schliesst "
                      "--diskrepanz/--wert aus (still ignorieren waere "
                      "eine halbe Anweisung)", file=sys.stderr)
                return 2
            if not args.quelle:
                print("entscheide: --alle-vorlaeufigen braucht --quelle",
                      file=sys.stderr)
                return 2
            for d in list(abox.diskrepanzen):
                if d.entscheidung is None or not d.entscheidung.vorlaeufig:
                    continue
                lesart = next(
                    (l for l in d.lesarten
                     if any(p.quelle_datei == args.quelle
                            for p in l.provenienz)),
                    None,
                )
                if lesart is None:
                    print(
                        f"entscheide: {d.id}: keine Lesart aus "
                        f"{args.quelle!r} — einzeln entscheiden",
                        file=sys.stderr,
                    )
                    return 1
                _ersetze_vorlaeufig(abox, d.id)
                loese_diskrepanz_auf(
                    abox, d.id, lesart.wert, args.entscheider,
                    args.begruendung, jetzt, vorlaeufig=False,
                )
                entschieden.append(d.id)
        else:
            if not args.diskrepanz or args.wert is None:
                print("entscheide: --diskrepanz und --wert sind "
                      "erforderlich (oder --alle-vorlaeufigen)",
                      file=sys.stderr)
                return 2
            _ersetze_vorlaeufig(abox, args.diskrepanz)
            loese_diskrepanz_auf(
                abox, args.diskrepanz, _wert_parsen(args.wert),
                args.entscheider, args.begruendung, jetzt, vorlaeufig=False,
            )
            entschieden.append(args.diskrepanz)
    except BefuellungsFehler as exc:
        print(f"entscheide: {exc}", file=sys.stderr)
        return 1

    fehler = validate_abox(abox)
    if fehler:
        print("entscheide: A-Box nach Aufloesung inkonsistent: "
              + "; ".join(fehler), file=sys.stderr)
        return 1
    speichere(abox, fall)
    print(json.dumps({
        "fall": str(fall),
        "entschieden": entschieden,
        "entscheider": args.entscheider,
        "verbleibend_vorlaeufig": sorted(
            d.id for d in abox.diskrepanzen
            if d.entscheidung is not None and d.entscheidung.vorlaeufig
        ),
        # OFFENE Diskrepanzen ebenfalls ausweisen: --alle-vorlaeufigen
        # beruehrt sie nicht, und der Bediener soll nicht "alles
        # erledigt" lesen, wenn Ungeloestes bleibt.
        "verbleibend_offen": sorted(
            d.id for d in abox.diskrepanzen if d.status == "offen"
        ),
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _ersetze_vorlaeufig(abox, diskrepanz_id: str) -> None:
    """Eine vorlaeufige Aufloesung zuruecknehmen, damit neu entschieden wird.

    Nur vorlaeufige Entscheidungen sind ersetzbar; eine endgueltige
    menschliche Entscheidung wird nie ueberschrieben.
    """
    for i, d in enumerate(abox.diskrepanzen):
        if d.id != diskrepanz_id:
            continue
        if d.status == "aufgeloest":
            if d.entscheidung is None or not d.entscheidung.vorlaeufig:
                raise BefuellungsFehler(
                    f"{diskrepanz_id}: endgueltig entschieden von "
                    f"{d.entscheidung.entscheider if d.entscheidung else '?'} "
                    "— wird nie ueberschrieben"
                )
            abox.diskrepanzen[i] = d.model_copy(update={
                "status": "offen",
                "entscheidung": None,
                # Die ersetzte vorlaeufige Entscheidung bleibt Teil der
                # Nachweiskette (append-only), sie wird nie vernichtet.
                "entscheidungs_historie": [*d.entscheidungs_historie,
                                           d.entscheidung],
            })
        return
    raise BefuellungsFehler(f"Diskrepanz {diskrepanz_id!r} unbekannt")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
