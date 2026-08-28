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
import hashlib
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


def auspraegungen_je_police(
    spez, zeilen: List[Dict[str, Any]]
) -> Dict[str, Dict[str, str]]:
    """Die Zellwahl-Auspraegungen je Police aus den transformierten Zeilen.

    Welche Dimensionen es gibt, sagen die Auspraegungs-Schluessel der
    Spez-Zellen; die Werte je Vertrag tragen die transformierten Zeilen
    (``gates.transformation_anwenden --zeilen``) unter genau diesen
    Feldnamen. Eine Zeile ohne Dimensionswert waere eine Police, deren
    Zelle sich nicht bestimmen laesst — harter Fehler, kein stilles
    Zurueckfallen auf irgendeine Zelle.
    """
    dimensionen = sorted({k for z in spez.zellen for k in z.auspraegungen})
    aus: Dict[str, Dict[str, str]] = {}
    for zeile in zeilen:
        police = str(zeile.get("police_id", "")).strip()
        if not police:
            raise SystemExit(
                "transformierte Zeile ohne police_id — die Zeilenliste "
                "gehoert aus gates.transformation_anwenden --zeilen")
        fehlend = [d for d in dimensionen if not str(zeile.get(d, "")).strip()]
        if fehlend:
            raise SystemExit(
                f"Police {police}: transformierte Zeile traegt keine "
                f"Auspraegung fuer {fehlend} — ohne sie ist keine "
                "Spez-Zelle bestimmbar")
        aus[police] = {d: str(zeile[d]) for d in dimensionen}
    return aus


def beitragsfrei_seit_jahr_je_police(
    vorgeschichte: List[Dict[str, str]], bestand, *, spalten: Dict[str, str],
) -> Dict[str, int]:
    """Anfangszustand aus der Vorgeschichte: PEX-Vertragsjahr je Police.

    Eine Beitragsfreistellung VOR dem Migrationsstichtag ist kein GeVo
    des Pruefzeitraums, sondern der Zustand, in dem der Vertrag
    uebernommen wird (``VertragsPruefung.beitragsfrei_seit_jahr``). Sie
    wirkt am Vertragsjahrestag; ein PEX-Datum abseits des Jahrestags
    ist eine Lieferungs-Inkonsistenz und faellt hart, statt still
    gerundet zu werden.
    """
    s = spalten
    beginne = {
        str(z["police_id"]): z["insurance_start"].date()
        for _, z in bestand.iterrows()
    }
    aus: Dict[str, int] = {}
    for zeile in vorgeschichte:
        if zeile[s["gevo"]] != "PEX":
            continue
        police = str(zeile[s["police"]])
        beginn = beginne.get(police)
        if beginn is None:
            # Vorgeschichte zu einer Police, die nicht uebernommen wurde
            # (z. B. verworfene Zeile) — hier kein Urteil, die
            # Mengenpruefung der Suite meldet Bestandsluecken selbst.
            continue
        monate = _monate(beginn, _parse(zeile[s["datum"]]))
        if monate % 12:
            raise SystemExit(
                f"Police {police}: PEX der Vorgeschichte bei Monat {monate} "
                "liegt nicht auf dem Vertragsjahrestag — Beitragsfreistellung "
                "wirkt am Jahrestag (Lieferung klaeren, nicht runden)")
        if police in aus:
            raise SystemExit(
                f"Police {police}: zwei PEX in der Vorgeschichte — eine "
                "zweite Beitragsfreistellung gibt es nicht")
        aus[police] = monate // 12
    return aus


def baue_auftraege(
    bestand, spez, abzug_1, abzug_2, protokoll, *,
    stichtag_1: dt.date, stichtag_2: dt.date, spalten: Dict[str, str],
    auspraegungen: Optional[Dict[str, Dict[str, str]]] = None,
    beitragsfrei_seit: Optional[Dict[str, int]] = None,
) -> List[VertragsPruefung]:
    """Je Vertrag genau einen Pruefauftrag."""
    s = spalten
    ab1 = {z[s["police"]]: z for z in abzug_1}
    ab2 = {z[s["police"]]: z for z in abzug_2}
    gevos: Dict[str, List[Dict[str, str]]] = {}
    for z in protokoll:
        gevos.setdefault(z[s["police"]], []).append(z)

    mehrzellig = len(spez.zellen) > 1
    if mehrzellig and auspraegungen is None:
        raise SystemExit(
            f"Spez traegt {len(spez.zellen)} Zellen — ohne die "
            "transformierten Zeilen (--zeilen) ist die Zellwahl je Police "
            "nicht bestimmbar")
    felder = {feld: wert.wert
              for feld, wert in _zelle(spez, {}).model_point.items()} \
        if not mehrzellig else None

    auftraege: List[VertragsPruefung] = []
    for _, zeile in bestand.iterrows():
        police = str(zeile["police_id"])
        if police not in ab1:
            raise SystemExit(
                f"Police {police} steht im Bestand, aber nicht im Abzug zum "
                "Migrationsstichtag — die Pruefmenge waere keine Bestandsmenge")
        beginn = zeile["insurance_start"].date()
        if felder is not None:
            generation = felder
        else:
            if police not in auspraegungen:
                raise SystemExit(
                    f"Police {police}: keine transformierte Zeile — die "
                    "Zellwahl ist nicht bestimmbar")
            generation = {
                feld: wert.wert
                for feld, wert in _zelle(
                    spez, auspraegungen[police]).model_point.items()}

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
            beitragsfrei_seit_jahr=(beitragsfrei_seit or {}).get(police),
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
    p.add_argument("--zeilen", default=None,
                   help="transformierte Zeilen (gates.transformation_anwenden "
                        "--zeilen) — Pflicht, sobald die Spez mehr als eine "
                        "Zelle traegt (Zellwahl je Police)")
    p.add_argument("--vorgeschichte", default=None,
                   help="REGISTRIERTE Metadatenliste der Geschaeftsvorfaelle "
                        "vor dem Stichtag (POLNR;GEVO;DATUM) — traegt den "
                        "Anfangszustand (PEX-Vertragsjahr) je Police")
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
    bestand_pfad = Path(args.bestand)
    bestand = read_portfolio(bestand_pfad)
    spez = lade_spez(fall, args.generation)
    abzug_1 = _lies_csv(fall, args.abzug_1)

    auspraegungen = None
    if args.zeilen is not None:
        zeilen = json.loads(Path(args.zeilen).read_text(encoding="utf-8"))
        if not isinstance(zeilen, list):
            print(f"{args.zeilen}: erwartet wird die Zeilenliste aus "
                  "gates.transformation_anwenden --zeilen", file=sys.stderr)
            return 2
        auspraegungen = auspraegungen_je_police(spez, zeilen)

    beitragsfrei_seit = None
    if args.vorgeschichte is not None:
        beitragsfrei_seit = beitragsfrei_seit_jahr_je_police(
            _lies_csv(fall, args.vorgeschichte), bestand, spalten=spalten)

    auftraege = baue_auftraege(
        bestand,
        spez,
        abzug_1,
        _lies_csv(fall, args.abzug_2),
        _lies_csv(fall, args.protokoll),
        stichtag_1=_parse(args.stichtag_1),
        stichtag_2=_parse(args.stichtag_2),
        spalten=spalten,
        auspraegungen=auspraegungen,
        beitragsfrei_seit=beitragsfrei_seit,
    )

    # Die Pruefmenge wird an der LIEFERUNG gemessen, nicht an sich
    # selbst: erwartete Anzahl ist die Zeilenzahl des Abzugs zum
    # Migrationsstichtag. Scope-Bindung (Stichtage, Bestand-Hash,
    # Systemstand) laeuft durch die validierende Suite-Signatur.
    ergebnis = pruefe_bestand(
        auftraege,
        erwartete_anzahl=len(abzug_1),
        stichtag_1=_parse(args.stichtag_1).isoformat(),
        stichtag_2=_parse(args.stichtag_2).isoformat(),
        bestand_sha256=hashlib.sha256(bestand_pfad.read_bytes()).hexdigest(),
        system=systemstand(Path(args.repo_root).resolve()),
    )

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
