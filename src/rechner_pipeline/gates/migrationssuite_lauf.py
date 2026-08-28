"""``migrationssuite_lauf`` — das Migrationscontrolling ueber den Fall fahren.

Produzent, kein Gate: Er baut je Vertrag einen Pruefauftrag, laesst
:func:`rechner_pipeline.qa.migrationssuite.pruefe_bestand` rechnen und
schreibt das zurueckgegebene Dict UNVERAENDERT als JSON. Geprueft wird
es von Gate A-M4 (``gates.abnahmebericht --suite``), das die Bindungen
nachrechnet, statt ihnen zu glauben.

Er liegt in ``gates/``, nicht in ``bestand/``: Nur diese Schicht darf
``fall``, ``spez`` und ``qa`` zugleich importieren.

**Die Spaltenbindung ist ein Parameter, keine Annahme.** Welche Spalte
eines Abzugs das Deckungskapital traegt, weiss nur der Fall. Die
Vorgaben passen zur Baldrian-Lieferung; jede andere Lieferung setzt sie
um. Sie im Code festzuschreiben hiesse, eine Lieferungskonvention zur
Systemeigenschaft zu machen.

**Was der Lauf NICHT tut: er glaettet nichts.** Traegt ein Vertrag
zwischen den Stichtagen eine Herabsetzung, weist die Suite den Wert am
Folgestichtag als Pruefluecke aus, statt ihn auf der urspruenglichen
Summe zu rechnen. Der Bestands-Scope von A-M4 duldet keine Luecke — der
Lauf endet dort also mit einem Befund, und das ist richtig so, solange
der Zielkern einen herabgesetzten Vertrag nicht fortschreiben kann
(``dev-docs/zahlungspfade-migrierter-vertraege.md``).

Knoten: klv
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from rechner_pipeline import fall as fall_mod
from rechner_pipeline.bestand.parquet_io import read_portfolio
from rechner_pipeline.gates._provenienz import systemstand
from rechner_pipeline.models.bestand import model_point_kwargs
from rechner_pipeline.qa.migrationssuite import (
    GeVoErwartung,
    VertragsPruefung,
    pruefe_bestand,
)
from rechner_pipeline.spez.validierung import lade_spez

#: Vorgabe-Spaltennamen der Lieferung. Sie passen zur
#: Baldrian-Lieferung; jede andere setzt sie ueber die Schalter um.
VORGABE = {
    "police": "POLNR",
    "deckkap": "DECKKAP",
    "jbrutto": "JBRUTTO",
    "beginn": "BEGINN",
    "gevo": "GEVO",
    "datum": "DATUM",
    "betrag": "BETRAG",
    "param": "PARAM",
}


def _lies_csv(fall: Path, name: str) -> List[Dict[str, str]]:
    """Eine REGISTRIERTE Lieferdatei lesen (ADR-002: kein freier Pfad)."""
    with fall_mod.eingang_datei(fall, name).open(encoding="utf-8") as datei:
        return list(csv.DictReader(datei, delimiter=";"))


def _parse(wert: str) -> dt.date:
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(str(wert).strip(), fmt).date()
        except ValueError:
            continue
    raise SystemExit(f"kein bekanntes Datumsformat: {wert!r}")


def _monate(von: dt.date, bis: dt.date) -> int:
    return (bis.year - von.year) * 12 + (bis.month - von.month) - (
        1 if bis.day < von.day else 0)


def _zelle(spez, auspraegungen: Dict[str, str]):
    gesucht = {k: str(v).strip().lower() for k, v in auspraegungen.items() if v}
    treffer = [z for z in spez.zellen if z.auspraegungen == gesucht]
    if not treffer:
        raise SystemExit(
            f"keine Spez-Zelle fuer {gesucht!r} — vorhanden sind "
            f"{[z.auspraegungen for z in spez.zellen]}")
    return treffer[0]


def baue_auftraege(
    bestand, spez, abzug_1, abzug_2, protokoll, *,
    stichtag_1: dt.date, stichtag_2: dt.date, spalten: Dict[str, str],
) -> List[VertragsPruefung]:
    """Je Vertrag genau einen Pruefauftrag."""
    s = spalten
    ab1 = {z[s["police"]]: z for z in abzug_1}
    ab2 = {z[s["police"]]: z for z in abzug_2}
    gevos: Dict[str, List[Dict[str, str]]] = {}
    for z in protokoll:
        gevos.setdefault(z[s["police"]], []).append(z)

    felder = {feld: wert.wert
              for feld, wert in _zelle(spez, {}).model_point.items()} \
        if len(spez.zellen) == 1 else None

    auftraege: List[VertragsPruefung] = []
    for _, zeile in bestand.iterrows():
        police = str(zeile["police_id"])
        if police not in ab1:
            raise SystemExit(
                f"Police {police} steht im Bestand, aber nicht im Abzug zum "
                "Migrationsstichtag — die Pruefmenge waere keine Bestandsmenge")
        beginn = zeile["insurance_start"].date()
        generation = felder if felder is not None else {
            feld: wert.wert
            for feld, wert in _zelle(spez, {}).model_point.items()}

        vorfaelle = []
        for g in sorted(gevos.get(police, []), key=lambda z: _parse(z[s["datum"]])):
            betrag = g.get(s["betrag"])
            anteil = g.get(s["param"])
            vorfaelle.append(GeVoErwartung(
                art=g[s["gevo"]],
                monate=_monate(beginn, _parse(g[s["datum"]])),
                betrag_erwartet=float(betrag) if betrag else None,
                anteil=float(anteil) if anteil else None,
            ))

        auftraege.append(VertragsPruefung(
            police_id=police,
            model_point=model_point_kwargs(zeile, generation),
            monate_stichtag_1=_monate(beginn, stichtag_1),
            monate_stichtag_2=_monate(beginn, stichtag_2),
            dk_erwartet_1=float(ab1[police][s["deckkap"]]),
            dk_erwartet_2=(float(ab2[police][s["deckkap"]])
                           if police in ab2 else None),
            bjb_erwartet_1=(float(ab1[police][s["jbrutto"]])
                            if ab1[police].get(s["jbrutto"]) else None),
            gevos=tuple(vorfaelle),
        ))
    return auftraege


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.gates.migrationssuite_lauf",
        description="Migrationscontrolling ueber den Fall fahren "
                    "(Produzent, kein Gate).")
    p.add_argument("--fall", required=True)
    p.add_argument("--generation", required=True,
                   help="Knoten-Id der Tarifgeneration, z. B. klv/tg2015")
    p.add_argument("--abzug-1", dest="abzug_1", required=True,
                   help="REGISTRIERTER Abzug zum Migrationsstichtag")
    p.add_argument("--abzug-2", dest="abzug_2", required=True,
                   help="REGISTRIERTER Abzug zum Folgestichtag")
    p.add_argument("--gevo-protokoll", dest="protokoll", required=True,
                   help="REGISTRIERTES Geschaeftsvorfall-Protokoll")
    p.add_argument("--bestand", required=True,
                   help="transformierter Bestand (Parquet), von P-B1 geprueft")
    p.add_argument("--stichtag-1", dest="stichtag_1", required=True)
    p.add_argument("--stichtag-2", dest="stichtag_2", required=True)
    p.add_argument("--repo-root", dest="repo_root", default=".")
    p.add_argument("--out", default=None)
    for name, vorgabe in VORGABE.items():
        p.add_argument(f"--spalte-{name}", dest=f"spalte_{name}",
                       default=vorgabe,
                       help=f"Spaltenname der Lieferung (Vorgabe: {vorgabe})")
    args = p.parse_args(argv)

    fall = Path(args.fall).resolve()
    if not (fall / "fall.json").is_file():
        print(f"Kein Fall-Arbeitsbereich: {fall}", file=sys.stderr)
        return 2

    spalten = {n: getattr(args, f"spalte_{n}") for n in VORGABE}
    auftraege = baue_auftraege(
        read_portfolio(Path(args.bestand)),
        lade_spez(fall, args.generation),
        _lies_csv(fall, args.abzug_1),
        _lies_csv(fall, args.abzug_2),
        _lies_csv(fall, args.protokoll),
        stichtag_1=_parse(args.stichtag_1),
        stichtag_2=_parse(args.stichtag_2),
        spalten=spalten,
    )

    ergebnis = pruefe_bestand(auftraege, erwartete_anzahl=len(auftraege))
    ergebnis["system"] = systemstand(Path(args.repo_root).resolve())
    ergebnis["stichtag_1"] = args.stichtag_1
    ergebnis["stichtag_2"] = args.stichtag_2

    ziel = Path(args.out) if args.out else (
        fall / "abgeleitet" / "berichte" / "migrationssuite.json")
    ziel.parent.mkdir(parents=True, exist_ok=True)
    with ziel.open("w", encoding="utf-8") as datei:
        json.dump(ergebnis, datei, indent=2, ensure_ascii=False,
                  sort_keys=True, default=str)
        datei.write("\n")

    print(f"Migrationssuite: {ergebnis['anzahl']} Vertraege, "
          f"{ergebnis['bestanden']} bestanden")
    luecken = ergebnis.get("pruefluecken") or []
    if luecken:
        print(f"  {len(luecken)} Pruefluecken — der Bestands-Scope von A-M4 "
              "duldet keine:")
        for l in luecken[:5]:
            print(f"    {str(l)[:140]}")
    print(f"  vollstaendig geprueft: {ergebnis.get('vollstaendig_geprueft')}")
    print(f"  {ziel}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
