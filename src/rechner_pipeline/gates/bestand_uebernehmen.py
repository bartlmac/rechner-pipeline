"""``bestand_uebernehmen`` — transformierte Lieferzeilen zum gefuehrten Bestand.

Produzent, kein Gate (Muster ``bestand/cli_fortschreibung``: "a PRODUCER,
not a gate — it writes no ledger entry"). Geprueft wird sein Erzeugnis:
P-B1 (``gates.bestand_validate``) haelt Stamm, Historie und Ledger gegen
Schema und Invarianten, A-M4 bindet den Bestand ueber seinen SHA-256.

Es liegt in ``gates/``, nicht in ``bestand/``: Nur diese Schicht darf
``ontologie`` und ``fall`` zugleich importieren
(``ontologie/code_karte.py``). Ein ``bestand.cli_*`` waere ein
Schichtverstoss.

**Was es tut.** Aus den transformierten Zeilen
(``gates.transformation_anwenden --zeilen``) baut es die drei Tabellen
des Zielsystems:

* ``bestand.parquet`` — der Stamm nach ``STAMM_SPALTEN``
* ``historie.parquet`` — je Vertrag die erste Statuszeile
* ``ledger.parquet`` — die Zugangsbuchung je Vertrag

**Der Status kommt aus der HISTORIE, nicht aus dem Stamm.** Das
Zielmodell fuehrt im Stamm immer den Ursprungssatz — ``status_id 1``,
``status_code POL``, datiert auf den Versicherungsbeginn. Jeder spaetere
Zustand steht in der Statushistorie ab ``status_id 2``, datiert NACH
dem Beginn; ``POL`` ist dort gar nicht zulaessig
(``PRODUKT_STATUS['klv']``). P-B1 prueft beides.

Fuer einen uebernommenen Vertrag heisst das: Der gelieferte
Vertragsstatus ist kein Stammfeld, sondern das Ergebnis seiner
Geschichte. Ein beitragsfrei gestellter Vertrag ist ein Vertrag, der als
``POL`` begann und irgendwann eine ``PEX``-Zeile bekam. Genau dafuer
liefert das abgebende Unternehmen die Metadatenliste der
Geschaeftsvorfaelle — Police, Art, Datum, ohne Betraege
(Grundsatzdokumentation 9.14). Ohne sie ist der Zustand am Stichtag
nicht rekonstruierbar, und das Kommando sagt es.

Ebenso das Geburtsdatum: Der Stamm verlangt den Monatsersten UND die
exakte Monatsidentitaet ``insurance_start - date_of_birth ==
12 * entry_age`` (``models/bestand.py:374``). Ein geliefertes
Geburtsdatum erfuellt das selten. Das Kommando KONSTRUIERT es deshalb
aus Beginn und Eintrittsalter und weist aus, wie viele Lieferwerte davon
abweichen — die Abweichung ist eine Aussage ueber die Alterskonvention
der Quelle und gehoert in den Befund, nicht unter den Teppich.

Knoten: klv
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from rechner_pipeline import fall as fall_mod
from rechner_pipeline.bestand.parquet_io import write_portfolio
from rechner_pipeline.models.bestand import (
    STATUS_HISTORIE_NAMES,
    LEDGER_NAMES,
    STAMM_NAMES,
)

#: Welcher Geschaeftsvorfall welchen Zustand herstellt. ERH und RED
#: fehlen mit Absicht: Sie aendern Summe und Beitrag, nicht den Zustand
#: — der Vertrag bleibt beitragspflichtig und bekommt keine
#: Historienzeile.
GEVO_STATUS = {"PEX": "PEX", "STO": "STO", "TOD": "TOD", "ABL": "ABL"}


def _monatserster_vor(beginn: dt.date, monate: int) -> dt.date:
    """Monatserster, der ``monate`` volle Monate vor ``beginn`` liegt.

    Der Stamm verlangt beides: Tag 1 und die exakte Monatsdifferenz zum
    Eintrittsalter. Ein aus der Quelle uebernommenes Geburtsdatum
    erfuellt das nur zufaellig.
    """
    gesamt = (beginn.year * 12 + beginn.month - 1) - monate
    return dt.date(gesamt // 12, gesamt % 12 + 1, 1)


def _jahrestag(beginn: dt.date, jahre: int) -> dt.date:
    try:
        return beginn.replace(year=beginn.year + jahre)
    except ValueError:      # 29. Februar
        return beginn.replace(year=beginn.year + jahre, day=28)


def _lies_zeilen(pfad: Path) -> List[Dict[str, Any]]:
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    if not isinstance(daten, list):
        raise SystemExit(
            f"{pfad}: erwartet wird die Zeilenliste aus "
            "gates.transformation_anwenden --zeilen"
        )
    return daten


def _vorgeschichte(fall: Path, name: Optional[str]) -> Dict[str, List[Tuple[str, dt.date]]]:
    """Die Geschaeftsvorfaelle vor dem Stichtag, je Police.

    Aus der REGISTRIERTEN Metadatenliste des abgebenden Unternehmens —
    Police, Art, Datum, ohne Betraege (Grundsatzdokumentation 9.14).
    Freie Dateipfade sind kein Eingang: Was in den Fall gelangt, ist
    registriert und integritaetsgeprueft (ADR-002).
    """
    if not name:
        return {}
    import csv

    pfad = fall_mod.eingang_datei(fall, name)
    aus: Dict[str, List[Tuple[str, dt.date]]] = {}
    with pfad.open(encoding="utf-8") as datei:
        for z in csv.DictReader(datei, delimiter=";"):
            police = z.get("POLNR") or z.get("police_id")
            art = z.get("GEVO") or z.get("ereignis")
            datum = z.get("DATUM") or z.get("status_date")
            if not (police and art and datum):
                raise SystemExit(
                    f"{name}: erwartet werden die Spalten POLNR;GEVO;DATUM "
                    f"(gefunden: {sorted(z)})"
                )
            aus.setdefault(str(police), []).append((art, _parse(datum)))
    return aus


def baue(
    zeilen: List[Dict[str, Any]],
    *,
    tarif_generation: str,
    produkt: str,
    stichtag: dt.date,
    vorgeschichte: Dict[str, List[Tuple[str, dt.date]]],
    generationsfelder: Optional[Dict[str, Any]] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, List[str]]:
    """Stamm, Historie und Ledger aus den transformierten Zeilen."""
    stamm: List[Dict[str, Any]] = []
    historie: List[Dict[str, Any]] = []
    ledger: List[Dict[str, Any]] = []
    hinweise: List[str] = []
    abweichende_geburtsdaten = 0

    for z in zeilen:
        police = str(z["police_id"])
        beginn = _parse(z["beginn"])
        alter = int(z["entry_age"])
        n, t = int(z["duration"]), int(z["premium_duration"])
        gebdat = _monatserster_vor(beginn, 12 * alter)
        if z.get("geburtsdatum"):
            geliefert = _parse(z["geburtsdatum"])
            if geliefert != gebdat:
                abweichende_geburtsdaten += 1

        stamm.append({
            "police_id": int(police),
            "tarif_generation": tarif_generation,
            "produkt": produkt,
            # Der Ursprungssatz ist IMMER POL: Jeder Vertrag begann
            # beitragspflichtig. Was danach kam, steht in der Historie.
            "status_id": 1,
            "status_code": "POL",
            "status_date": pd.Timestamp(beginn),
            "sex": str(z["sex"]),
            "date_of_birth": pd.Timestamp(gebdat),
            "entry_age": alter,
            "duration": n,
            "premium_duration": t,
            "sum_insured": float(z["sum_insured"]),
            "bu_rente": 0.0,
            "zahlweise": int(z["zahlweise"]),
            "insurance_start": pd.Timestamp(beginn),
            "insurance_end": pd.Timestamp(_jahrestag(beginn, n)),
            "payment_end": pd.Timestamp(_jahrestag(beginn, t)),
        })
        # Die Statuswechsel der Vorgeschichte, fortlaufend ab id 2. ERH
        # und RED erzeugen keine Zeile: Sie aendern Summe und Beitrag,
        # nicht den Zustand.
        wechsel = [
            (art, datum)
            for art, datum in sorted(vorgeschichte.get(police, []),
                                     key=lambda e: e[1])
            if art in GEVO_STATUS
        ]
        for nr, (art, datum) in enumerate(wechsel, start=2):
            historie.append({
                "police_id": int(police),
                "status_id": nr,
                "status_code": GEVO_STATUS[art],
                "status_date": pd.Timestamp(datum),
            })
        # Der Stamm traegt den JUENGSTEN Journalstand, nicht den
        # Ursprung — P-B1 haelt beide gegeneinander. Der Ursprungssatz
        # (id 1, POL) bleibt implizit; er steht nie in der Historie,
        # weil POL dort fuer die KLV gar nicht zulaessig ist.
        if wechsel:
            letzte = stamm[-1]
            letzte["status_id"] = len(wechsel) + 1
            letzte["status_code"] = GEVO_STATUS[wechsel[-1][0]]
            letzte["status_date"] = pd.Timestamp(wechsel[-1][1])
        ledger.append({
            "police_id": int(police),
            "tarif_generation": tarif_generation,
            "ereignis": "ZUG",
            "vertragsjahr": 0,
            "status_date": pd.Timestamp(beginn),
            "betrag_art": "VS",
            "betrag": float(z["sum_insured"]),
        })
        # Der mitgebrachte Zustand braucht seine Buchung: Ein Vertrag,
        # der beitragsfrei ankommt, traegt in der Historie eine
        # PEX-Zeile, und die Bewegungsrechnung des aufnehmenden
        # Unternehmens verlangt die zugehoerige Summe. Sie kommt NICHT
        # aus der Lieferung — die Vorgeschichte fuehrt keine Betraege
        # (Grundsatzdokumentation 9.14) —, sondern wird gerechnet: Das
        # ist derselbe konstruktive Weg wie fuer jede andere Groesse des
        # uebernommenen Vertrags.
        for art, datum in wechsel:
            if art != "PEX" or generationsfelder is None:
                continue
            pex_jahr = (datum.year - beginn.year) * 12 + (
                datum.month - beginn.month) - (
                1 if datum.day < beginn.day else 0)
            pex_jahr //= 12
            ledger.append({
                "police_id": int(police),
                "tarif_generation": tarif_generation,
                "ereignis": "PEX",
                "vertragsjahr": pex_jahr,
                "status_date": pd.Timestamp(datum),
                "betrag_art": "VS_bfr",
                "betrag": _beitragsfreie_summe(
                    z,
                    generationsfelder.get(police, generationsfelder)
                    if isinstance(next(iter(generationsfelder.values()), None),
                                  dict) else generationsfelder,
                    pex_jahr),
            })

    if abweichende_geburtsdaten:
        hinweise.append(
            f"{abweichende_geburtsdaten} von {len(zeilen)} gelieferten "
            "Geburtsdaten weichen vom konstruierten ab. Der Stamm verlangt "
            "den Monatsersten und die exakte Monatsidentitaet zum "
            "Eintrittsalter; die Abweichung ist eine Aussage ueber die "
            "Alterskonvention der Quelle und gehoert geklaert."
        )
    if not vorgeschichte:
        hinweise.append(
            "Keine Vorgeschichte uebergeben: alle Vertraege stehen als "
            "POL im Ursprungszustand. Ein beitragsfrei gestellter Vertrag "
            "ohne PEX-Zeile in der Historie waere bewertungsrelevant "
            "falsch (beitragsfreier Track, gamma3, VS_bfr)."
        )

    return (
        pd.DataFrame(stamm, columns=list(STAMM_NAMES)),
        pd.DataFrame(historie, columns=list(STATUS_HISTORIE_NAMES)),
        pd.DataFrame(ledger, columns=list(LEDGER_NAMES)),
        hinweise,
    )


def _beitragsfreie_summe(
    zeile: Dict[str, Any], generationsfelder: Dict[str, Any], pex_jahr: int
) -> float:
    """Die beitragsfreie Summe eines uebernommenen Vertrags — gerechnet.

    Das Zielsystem bildet sie aus den Ursprungsparametern; die Lieferung
    traegt sie nicht. Ist die gelieferte Summe bereits die beitragsfreie
    (so fuehren Abzuege beitragsfrei gestellte Vertraege), ist sie
    zugleich das Ergebnis — der Kern rechnet dann auf der
    Ursprungssumme, die diese Summe erzeugt.
    """
    from rechner_pipeline.kern import ModelPoint, Rechenkern

    felder = {
        "x": int(zeile["entry_age"]), "sex": str(zeile["sex"]),
        "n": int(zeile["duration"]), "t": int(zeile["premium_duration"]),
        "sum_insured": float(zeile["sum_insured"]),
        "zw": int(zeile["zahlweise"]),
        **{k: v for k, v in generationsfelder.items()},
    }
    return float(Rechenkern(ModelPoint(**felder)).beitragsfreie_summe(pex_jahr))


def _parse(wert: Any) -> dt.date:
    if isinstance(wert, dt.date):
        return wert
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return dt.datetime.strptime(str(wert).strip(), fmt).date()
        except ValueError:
            continue
    raise SystemExit(f"kein bekanntes Datumsformat: {wert!r}")


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.gates.bestand_uebernehmen",
        description="Transformierte Lieferzeilen zum gefuehrten Bestand "
                    "(Produzent, kein Gate).")
    p.add_argument("--fall", required=True, help="Fall-Arbeitsbereich")
    p.add_argument("--zeilen", required=True,
                   help="Zeilenliste aus gates.transformation_anwenden")
    p.add_argument("--tarif-generation", dest="generation", required=True,
                   help="Wert der Stammspalte tarif_generation, z. B. TG2015")
    p.add_argument("--produkt", default="klv", choices=("klv", "bu"))
    p.add_argument("--stichtag", required=True, help="Migrationsstichtag (ISO)")
    p.add_argument("--vorgeschichte", default=None,
                   help="REGISTRIERTE Metadatenliste der Geschaeftsvorfaelle "
                        "vor dem Stichtag (POLNR;GEVO;DATUM)")
    p.add_argument("--generation-spez", dest="generation_spez", default=None,
                   help="Knoten-Id der Tarif-Spez des Falls (z. B. "
                        "klv/tg2015). Mit ihr rechnet die Uebernahme die "
                        "beitragsfreie Summe mitgebrachter PEX-Zustaende — "
                        "ohne sie fehlt der Bewegungsrechnung ihre Buchung.")
    p.add_argument("--out-dir", dest="out_dir", required=True,
                   help="Zielverzeichnis im Fall")
    args = p.parse_args(argv)

    fall = Path(args.fall).resolve()
    if not (fall / "fall.json").is_file():
        print(f"Kein Fall-Arbeitsbereich: {fall}", file=sys.stderr)
        return 2
    ziel = Path(args.out_dir).resolve()
    try:
        ziel.relative_to(fall)
    except ValueError:
        print(f"--out-dir muss im Fall liegen: {ziel}", file=sys.stderr)
        return 2

    generationsfelder = None
    if args.generation_spez:
        from rechner_pipeline.spez.validierung import lade_spez

        spez = lade_spez(fall, args.generation_spez)
        if len(spez.zellen) != 1:
            # Mehrzellige Spez: die Zellwahl je Vertrag traegt die
            # transformierte Zeile; hier genuegt die Zelle, deren
            # Auspraegungen die Zeile nennt.
            generationsfelder = None
        else:
            generationsfelder = dict(spez.zellen[0].model_point)

    zeilen = _lies_zeilen(Path(args.zeilen))
    if args.generation_spez and generationsfelder is None:
        from rechner_pipeline.spez.validierung import lade_spez

        spez = lade_spez(fall, args.generation_spez)
        zellen = {tuple(sorted(z.auspraegungen.items())): dict(z.model_point)
                  for z in spez.zellen}
        dimensionen = sorted({k for z in spez.zellen for k in z.auspraegungen})
        generationsfelder = {}
        for z in zeilen:
            schluessel = tuple(sorted(
                (d, str(z[d])) for d in dimensionen if d in z))
            if schluessel in zellen:
                generationsfelder[str(z["police_id"])] = zellen[schluessel]

    stamm, historie, ledger, hinweise = baue(
        zeilen,
        tarif_generation=args.generation,
        produkt=args.produkt,
        stichtag=_parse(args.stichtag),
        vorgeschichte=_vorgeschichte(fall, args.vorgeschichte),
        generationsfelder=generationsfelder,
    )

    write_portfolio(stamm, ziel / "bestand.parquet")
    write_portfolio(historie, ziel / "historie.parquet")
    write_portfolio(ledger, ziel / "ledger.parquet")

    print(f"{len(stamm)} Vertraege uebernommen nach {ziel}")
    print(f"  bestand.parquet   {len(stamm)} Zeilen")
    print(f"  historie.parquet  {len(historie)} Zeilen")
    print(f"  ledger.parquet    {len(ledger)} Zeilen")
    if len(historie):
        verteilung = historie["status_code"].value_counts().to_dict()
        print(f"  Statuswechsel     {verteilung}")
    for h in hinweise:
        print(f"\nHINWEIS: {h}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
