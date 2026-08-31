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
    GENERATION_FIELDS,
    MERKMALE_SPALTEN,
    VERANKERUNG_SPALTEN,
    STATUS_HISTORIE_NAMES,
    LEDGER_NAMES,
    STAMM_NAMES,
)

#: Welcher Geschaeftsvorfall welchen Zustand herstellt. ERH und RED
#: fehlen mit Absicht: Sie aendern Summe und Beitrag, nicht den Zustand
#: — der Vertrag bleibt beitragspflichtig und bekommt keine
#: Historienzeile.
GEVO_STATUS = {"PEX": "PEX", "STO": "STO", "TOD": "TOD", "ABL": "ABL"}


def _zellen_toml(spez, generation: str) -> str:
    """Die Tarifzellen der Spez als Config-Abschnitt fuer den Bestand.

    Die Merkmalstabelle sagt, WELCHE Zelle ein Vertrag hat; welche
    Grundlagen in der Zelle gelten, muss die Bestand-Config sagen. Ohne
    diesen Abschnitt bewertet der Bericht sechs Zellen mit einem Satz --
    und wer ihn von Hand schreibt, uebertraegt bei sechs Zellen und
    siebzehn Feldern gut hundert Zahlen.

    Aufgeteilt in gemeinsam und abweichend: Felder mit gleichem Wert in
    allen Zellen gehoeren zur Generation, nur der Rest in die Zelle. So
    liest man am Abschnitt ab, was die Zellen ueberhaupt unterscheidet.
    """
    zellen = [z for z in getattr(spez, "zellen", []) if z.auspraegungen]
    if not zellen:
        return ""

    def _wert(v) -> str:
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, str):
            return f'"{v}"'
        return repr(v)

    # model_point ist ein Pydantic-Modell: erst in ein Dict, sonst
    # iteriert "in" Paare statt Feldnamen und alles waere "nicht da".
    saetze = [dict(z.model_point) for z in zellen]
    felder = [f for f in GENERATION_FIELDS if all(f in s for s in saetze)]
    gemeinsam = [f for f in felder if len({s[f] for s in saetze}) == 1]
    abweichend = [f for f in felder if f not in gemeinsam]

    aus = [
        f"# Tarifzellen der Generation {generation}, erzeugt aus der Spez.",
        "# Die Zuweisungen unter diesem Kommentar gehoeren in den",
        "# Generationsblock der Bestand-Config; die Zellbloecke darunter",
        "# folgen unveraendert. (Kein Marker im Kommentar: der Abschnitt",
        "# wird an seinem ersten Zellblock geteilt.)",
        "",
    ]
    aus += [f"{f} = {_wert(saetze[0][f])}" for f in gemeinsam]
    for z, satz in sorted(zip(zellen, saetze),
                          key=lambda p: sorted(p[0].auspraegungen.items())):
        paare = ", ".join(
            f'{k} = "{z.auspraegungen[k]}"' for k in sorted(z.auspraegungen)
        )
        aus += ["", "[[generation.zelle]]", f"auspraegungen = {{ {paare} }}"]
        aus += [f"{f} = {_wert(satz[f])}" for f in abweichend]
    return "\n".join(aus) + "\n"


def _merkmalstabelle(zeilen, spez) -> "pd.DataFrame":
    """Je Vertrag und Dimension die gewaehlte Auspraegung.

    WELCHE Dimensionen es gibt, sagt die Spez der Generation -- nicht
    dieses Kommando. Traegt sie nur eine Zelle ohne Auspraegungen, gibt
    es keine Dimensionen und damit keine Tabelle.

    Die Transformation liefert die Auspraegungen laengst mit (sie waehlt
    damit die Spez-Zelle je Vertrag); sie fielen bisher nur weg, weil der
    Stamm sie nicht kennt. Damit bewertete der Bestandsbericht einen
    Bestand mit sechs Zellen mit einer einzigen.
    """
    dimensionen = sorted({
        name
        for zelle in getattr(spez, "zellen", [])
        for name in (zelle.auspraegungen or {})
    })
    if not dimensionen:
        return pd.DataFrame(columns=[n for n, _ in MERKMALE_SPALTEN])

    saetze = []
    for z in zeilen:
        for dim in dimensionen:
            wert = z.get(dim)
            if wert in (None, ""):
                continue
            saetze.append({
                "police_id": int(z["police_id"]),
                "dimension": str(dim),
                "auspraegung": str(wert).strip().lower(),
            })
    rahmen = pd.DataFrame(saetze, columns=[n for n, _ in MERKMALE_SPALTEN])
    for name, dtype in MERKMALE_SPALTEN:
        rahmen[name] = rahmen[name].astype(dtype)
    return rahmen.sort_values(["police_id", "dimension"]).reset_index(drop=True)


def _verankerungstabelle(
    zeilen: List[Dict[str, Any]],
    vorgeschichte: Dict[str, List[Tuple[str, dt.date]]],
) -> "pd.DataFrame":
    """Verankerungsattribute je Vertrag — wenn die Lieferung sie traegt.

    ``monate_ta`` und ``dk_ta`` kommen aus der transformierten Zeile
    (Korrekturschicht-Umsetzung K3: die Ableitungslast liegt quellseitig
    oder in der Uebernahmestrecke). Zustand und Verweildauer am t_a
    werden aus der REGISTRIERTEN Vorgeschichte abgeleitet — dieselbe
    Quelle, aus der die Statushistorie entsteht, kein zweiter Kanal.

    Alle oder keine: Eine halbe Verankerungstabelle waere schlimmer als
    keine, denn die Korrekturschicht faende einen Teil der Vertraege und
    hielte den Rest fuer verankerungsfrei. Ein TERMINALER Vorfall vor
    t_a ist ein Lieferungswiderspruch — ein beendeter Vertrag hat keinen
    spaeteren Rechenpunkt.
    """
    mit = [z for z in zeilen if z.get("monate_ta") is not None]
    if not mit:
        return pd.DataFrame(columns=[n for n, _ in VERANKERUNG_SPALTEN])
    if len(mit) != len(zeilen):
        ohne = [str(z["police_id"]) for z in zeilen
                if z.get("monate_ta") is None][:5]
        raise SystemExit(
            f"{len(zeilen) - len(mit)} von {len(zeilen)} Zeilen ohne "
            f"monate_ta (z. B. {ohne}) — Verankerungsattribute werden fuer "
            "ALLE Vertraege geliefert oder fuer keinen; eine halbe Tabelle "
            "liesse die Korrekturschicht den Rest fuer verankerungsfrei "
            "halten"
        )
    saetze = []
    for z in mit:
        police = str(z["police_id"])
        beginn = _parse(z["beginn"])
        monate_ta = int(z["monate_ta"])
        if z.get("dk_ta") is None:
            raise SystemExit(
                f"Police {police}: monate_ta ohne dk_ta — eine Verankerung "
                "ohne Wert ist keine"
            )
        gesamt = beginn.year * 12 + (beginn.month - 1) + monate_ta
        datum_ta = dt.date(gesamt // 12, gesamt % 12 + 1, 1)
        zustand, seit = "beitragspflichtig", beginn
        for art, datum in sorted(vorgeschichte.get(police, []),
                                 key=lambda e: e[1]):
            if art not in GEVO_STATUS or datum > datum_ta:
                continue
            if GEVO_STATUS[art] in ("STO", "TOD", "ABL"):
                raise SystemExit(
                    f"Police {police}: terminaler Vorfall {art} am "
                    f"{datum.isoformat()} VOR dem Verankerungszeitpunkt "
                    f"{datum_ta.isoformat()} — ein beendeter Vertrag hat "
                    "keinen spaeteren Rechenpunkt"
                )
            zustand, seit = "beitragsfrei", datum
        saetze.append({
            "police_id": int(police),
            "monate_ta": monate_ta,
            "zustand_ta": zustand,
            "verweildauer_ta": _vertragsjahre(seit, datum_ta),
            "dk_ta": float(z["dk_ta"]),
        })
    rahmen = pd.DataFrame(saetze, columns=[n for n, _ in VERANKERUNG_SPALTEN])
    return rahmen.astype(dict(VERANKERUNG_SPALTEN)).sort_values(
        "police_id").reset_index(drop=True)


def _vertragsjahre(beginn, stichtag) -> int:
    """Volle Vertragsjahre zwischen Beginn und Stichtag.

    Der Zugang eines uebernommenen Vertrags faellt nicht in sein erstes
    Vertragsjahr: Er tritt mit seinem Alter in die Buecher ein, und das
    Bewegungsjournal soll das zeigen.
    """
    monate = ((stichtag.year - beginn.year) * 12
              + (stichtag.month - beginn.month)
              - (1 if stichtag.day < beginn.day else 0))
    return max(0, monate // 12)


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
            # HIER trennen sich Vertragsbeginn und Bestandszugang: Der
            # Vertrag wurde beim abgebenden Unternehmen geschlossen und
            # kommt erst zum Migrationsstichtag in unsere Buecher. Ohne
            # diese Zeile fuehrte der Bestandsbericht ihn ab seinem
            # Beginn — also Jahre, bevor es die Uebernahme gab.
            "bestandszugang": pd.Timestamp(stichtag),
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
        # Der Vertrag tritt am UEBERNAHMESTICHTAG in die Buecher des
        # aufnehmenden Unternehmens ein, nicht an seinem Beginn.
        #
        # Zuvor wurde er auf den Vertragsbeginn gebucht und die
        # Vorgeschichte als eigene Bewegungen nachgefahren -- 540 von 540
        # Buchungen lagen damit VOR dem Stichtag. In den Buechern der
        # PLV hat 2017 aber keine Beitragsfreistellung stattgefunden; der
        # Vertrag war da noch gar nicht da. Was Baldrian gebucht hat,
        # steht in Baldrians Journal.
        #
        # Die Vorgeschichte ERKLAERT den Zustand, sie ist keine Bewegung
        # des aufnehmenden Unternehmens. Sie bleibt deshalb in der
        # Statushistorie (dort beschreibt sie den Vertrag und traegt die
        # Bewertung) und faellt aus dem Bewegungsjournal heraus. Genau so
        # beschreibt es der Migrationszugang: "Die Historie des
        # Quellsystems wird nicht nachgefahren"
        # (bestand/migrationszugang.py, Grundsatzdokumentation 9.14).
        #
        # Der Zugang bucht die VERSICHERUNGSSUMME des Vertrags -- auch
        # bei einem beitragsfrei uebernommenen. Er tritt mit seiner
        # vollen Summe in den beitragspflichtigen Bestand ein und wird
        # im selben Augenblick in den beitragsfreien umgebucht; genau
        # so weist es die Nachweisung aus.
        ledger.append({
            "police_id": int(police),
            "tarif_generation": tarif_generation,
            "ereignis": "ZUG",
            "vertragsjahr": _vertragsjahre(beginn, stichtag),
            "status_date": pd.Timestamp(stichtag),
            "betrag_art": "VS",
            "betrag": float(z["sum_insured"]),
            # Die Zugangssumme steht im Abzug der abgebenden Gesellschaft.
            "betrag_herkunft": "geliefert",
        })
        # Kommt der Vertrag bereits beitragsfrei an, gehoert dazu die
        # Umbuchung -- ebenfalls zum ZUGANGSDATUM, nicht zum historischen
        # Datum der Beitragsfreistellung. Bei Baldrian ist die 2022
        # geschehen; in den Buechern der PLV gab es den Vertrag da nicht.
        # Die Umbuchung IST der Eintritt in den beitragsfreien Bestand.
        #
        # Ohne diese Zeile fuehrt die Nachweisung den Vertrag dauerhaft
        # als beitragspflichtig: Der Zugang bucht ihn dorthin und nichts
        # holt ihn heraus -- die Identitaet Anfang + Zugang - Abgang -
        # Umbuchung = Ende bricht, und der beitragsfreie Bestand faende
        # keine Summe (kennzahlen.stand_am liest sie aus dieser Zeile).
        #
        # Der Betrag ist die beitragsfreie Summe und damit KLEINER als
        # die Zugangssumme -- kein Widerspruch, sondern die Umwandlung
        # selbst: Der beitragspflichtige Bestand gibt die volle Summe ab,
        # der beitragsfreie nimmt die herabgesetzte auf. Die Lieferung
        # traegt sie nicht, das Zielsystem rechnet sie aus den
        # Ursprungsparametern -- deshalb "gerechnet".
        pex_datum = next(
            (datum for art, datum in wechsel if art == "PEX"), None)
        if pex_datum is not None:
            felder = generationsfelder or {}
            if felder and police in felder:
                felder = felder[police]
            if not felder:
                # Kein stiller Verzicht: Ohne Rechnungsgrundlagen laesst
                # sich die beitragsfreie Summe nicht bilden, und ein
                # Bestand mit beitragsfreien Vertraegen ohne diese Buchung
                # ist unvollstaendig -- die Nachweisung fuehrte sie
                # dauerhaft als beitragspflichtig.
                raise SystemExit(
                    f"Police {police} ist beitragsfrei uebernommen "
                    f"({pex_datum}), aber es liegen keine "
                    "Rechnungsgrundlagen vor -- die beitragsfreie Summe "
                    "ist nicht berechenbar. --generation-spez mitgeben "
                    "(oder generationsfelder uebergeben)."
                )
            ledger.append({
                "police_id": int(police),
                "tarif_generation": tarif_generation,
                "ereignis": "PEX",
                "vertragsjahr": _vertragsjahre(beginn, stichtag),
                "status_date": pd.Timestamp(stichtag),
                "betrag_art": "VS",
                "betrag": _beitragsfreie_summe(
                    z, felder, _vertragsjahre(beginn, pex_datum)),
                "betrag_herkunft": "gerechnet",
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

    # Explizit auf die Vertrags-Dtypes: Ein LEERES Frame hat sonst
    # object-Spalten, und der Parquet-Schreiber scheitert am ersten
    # Datumsfeld. Der Fall ist real -- eine Vorgeschichte, die nur ERH
    # oder RED enthaelt, erzeugt keine einzige Historienzeile.
    from rechner_pipeline.models.bestand import (
        LEDGER_SPALTEN,
        STAMM_SPALTEN,
        STATUS_HISTORIE_SPALTEN,
    )

    return (
        pd.DataFrame(stamm, columns=list(STAMM_NAMES))
        .astype(dict(STAMM_SPALTEN)),
        pd.DataFrame(historie, columns=list(STATUS_HISTORIE_NAMES))
        .astype(dict(STATUS_HISTORIE_SPALTEN)),
        pd.DataFrame(ledger, columns=list(LEDGER_NAMES))
        .astype(dict(LEDGER_SPALTEN)),
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

    # Die Merkmalsauspraegungen als NEBENTABELLE, wie Scheiben und
    # Historie: Sie entsteht nur, wenn die Tarifgeneration Dimensionen
    # fuehrt. Ohne Datei hat der Bestand keine Zellen -- das ist etwas
    # anderes als leere Stammspalten, in denen "trifft nicht zu" und
    # "unbekannt" gleich aussehen.
    merkmale = _merkmalstabelle(zeilen, spez) if args.generation_spez else None
    if merkmale is not None and len(merkmale):
        write_portfolio(merkmale, ziel / "merkmale.parquet")
        print(f"  merkmale.parquet: {len(merkmale)} Zeilen "
              f"({merkmale['dimension'].nunique()} Dimensionen)")
        # Und die Grundlagen zu den Zellen -- sonst laege die Zuordnung
        # vor, aber nichts, worauf sie zeigt.
        abschnitt = _zellen_toml(spez, args.generation)
        if abschnitt:
            pfad = ziel / "generation-zellen.toml"
            pfad.write_text(abschnitt, encoding="utf-8")
            print(f"  generation-zellen.toml: {len(spez.zellen)} Zellen "
                  "(in die Bestand-Config uebernehmen)")

    # Verankerungsattribute als NEBENTABELLE (K3): Bisher lebten t_a und
    # der dort gelieferte Wert nur im Pruefauftrag, je Lauf aus den
    # Erwartungswerten rekonstruiert. Traegt die Lieferung sie je Zeile,
    # werden sie hier Vertragsmerkmale des Bestands.
    verankerung = _verankerungstabelle(
        zeilen, _vorgeschichte(fall, args.vorgeschichte))
    if len(verankerung):
        write_portfolio(verankerung, ziel / "verankerung.parquet")
        print(f"  verankerung.parquet: {len(verankerung)} Zeilen "
              f"(t_a in Vertragsmonaten, Zustand aus der Vorgeschichte)")

    # E1 (Migrationskonzept Kap. 11, Entscheidung 2026-08-31): Die
    # gelieferte GeVo-Metadatenliste gehoert DAUERHAFT zum Zielbestand --
    # das Quellsystem wird stillgelegt und als Archiv genutzt, also
    # archiviert die PLV die Liste bei der Uebernahme. Byte-identische
    # Kopie der REGISTRIERTEN Datei, kein Umformat: Ein Archiv, das beim
    # Archivieren umschreibt, archiviert nicht.
    if args.vorgeschichte:
        quelle = fall_mod.eingang_datei(fall, args.vorgeschichte)
        archiv = ziel / "quellarchiv"
        archiv.mkdir(parents=True, exist_ok=True)
        (archiv / quelle.name).write_bytes(quelle.read_bytes())
        print(f"  quellarchiv/{quelle.name}: GeVo-Metadatenliste archiviert "
              "(E1: Archiv der PLV)")

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
