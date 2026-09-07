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
(``gates.transformation_anwenden --zeilen``) baut es die Tabellen des
Zielsystems:

* ``bestand.parquet`` — der Stamm nach ``STAMM_SPALTEN``
* ``historie.parquet`` — je Vertrag die erste Statuszeile
* ``ledger.parquet`` — die Zugangsbuchung je Vertrag
* ``scheiben.parquet`` — die Alt-Erhoehungen als Bausteine (Freischaltung)
* ``uebernahme.json`` — der Beleg: Modus, Schalter, Ausnahmen

**Der Anfangszustand ist der der Pruefstrecke** (Freischaltung,
dev-docs/freischaltung-uebernommener-bestand.md, Schritt 3). Die
Abnahmen A-M1 bis A-M4 rechnen jeden Vertrag auf seinem
ANFANGSZUSTAND: Grund- statt Gesamtsumme, die Alt-Erhoehungen als
eigene Bausteine, die beitragsfreie Summe aus der Ursprungssumme. Die
Uebernahme rief bisher nichts davon: Sie nahm die gelieferte Summe als
Versicherungssumme — bei 550 von 834 Vertraegen des zweiten
Baldrian-Falls die falsche Welt — und wandelte eine beitragsfrei
gelieferte Summe ein zweites Mal um. Jetzt ruft sie DIESELBE
Ableitung (``migrationssuite_lauf.anfangszustaende_je_police``) und
materialisiert das Ergebnis in den Tabellen; ``--anfangszustand``
sagt, ob (``materialisieren``) oder ob der Bestand ausdruecklich als
Grundvertrag gefuehrt wird (``grundvertrag``: nicht freigeschaltet,
im Beleg ausgewiesen). Ohne Angabe haelt das Kommando an, sobald die
Vorgeschichte Erhoehungen oder Herabsetzungen traegt.

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
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from rechner_pipeline import fall as fall_mod
from rechner_pipeline.bestand.migrationszugang import (
    MigrationszugangFehler,
    leite_pex_ursprungssumme_ab,
)
from rechner_pipeline.bestand.parquet_io import write_portfolio
from rechner_pipeline.kern import ModelPoint, Rechenkern, erhoehungs_scheibe
from rechner_pipeline.kern.beitragsreduktion import PROSPEKTIV, VERFAHREN
from rechner_pipeline.models.bestand import (
    GENERATION_FIELDS,
    MERKMALE_SPALTEN,
    SCHEIBEN_NAMES,
    SCHEIBEN_SPALTEN,
    VERANKERUNG_SPALTEN,
    STATUS_HISTORIE_NAMES,
    LEDGER_NAMES,
    STAMM_NAMES,
    model_point_kwargs,
)

#: Schema des Uebernahmebelegs ``uebernahme.json``.
BELEG_SCHEMA_VERSION = 1

#: Die beiden Antworten auf ``--anfangszustand``.
MATERIALISIEREN = "materialisieren"
GRUNDVERTRAG = "grundvertrag"

#: Welcher Geschaeftsvorfall welchen Zustand herstellt. ERH und RED
#: fehlen mit Absicht: Sie aendern Summe und Beitrag, nicht den Zustand
#: — der Vertrag bleibt beitragspflichtig und bekommt keine
#: Historienzeile.
GEVO_STATUS = {"PEX": "PEX", "STO": "STO", "TOD": "TOD", "ABL": "ABL"}


def _zellen_toml(spez, generation: str,
                 tarifwerk: Optional[Dict[str, Any]] = None) -> str:
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

    def _wert(v) -> str:
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, str):
            return f'"{v}"'
        return repr(v)

    # Die Tarifwerks-Eigenschaften der Fuehrung gehoeren in denselben
    # Generationsblock wie die Rechnungsgrundlagen: So hat die
    # Pruefstrecke des Falls abgenommen, so muss der Bestand fuehren
    # (Freischaltung, Schritt 2 und 3). Wer sie von Hand in die Config
    # traegt, vergisst einen — und die Fuehrung rechnet still das eigene
    # Tarifwerk.
    tarifwerk_zeilen: List[str] = []
    if tarifwerk:
        tarifwerk_zeilen = [
            "",
            "# Tarifwerks-Eigenschaften der Fuehrung (Freischaltung): mit",
            "# diesen Schaltern hat die Pruefstrecke des Falls abgenommen.",
        ] + [
            f"{name} = {_wert(tarifwerk[name])}"
            for name in ("scheiben_mit_gamma1", "stoab_je_baustein",
                         "red_verfahren")
        ]
    if not zellen:
        if not tarifwerk_zeilen:
            return ""
        return "\n".join(
            [f"# Tarifwerk der Generation {generation}, erzeugt aus der",
             "# Uebernahme. Die Zuweisungen gehoeren in den Generationsblock",
             "# der Bestand-Config."] + tarifwerk_zeilen
        ) + "\n"

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
    aus += tarifwerk_zeilen
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
            felder = _felder_fuer(generationsfelder, police)
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
            # Der Abzug fuehrt bei einem beitragsfreien Vertrag die
            # BEITRAGSFREIE Summe. Der Stamm traegt den Ursprungssatz,
            # also die Summe, aus der der Kern diese beitragsfreie Summe
            # bildet — die Umkehrung ist exakt (leite_pex_ursprungssumme_ab).
            # Vorher wurde die gelieferte Summe als Versicherungssumme
            # genommen und daraus NOCH EINMAL eine beitragsfreie Summe
            # gerechnet: 160 Vertraege des zweiten Baldrian-Falls um den
            # Umwandlungsfaktor zu klein, 1,72 statt 3,71 Mio EUR
            # beitragsfreier Bestand (Freischaltung, Abschnitt 1.1).
            ursprung, vs_bfr = _beitragsfreie_uebernahme(
                z, felder, _vertragsjahre(beginn, pex_datum))
            stamm[-1]["sum_insured"] = ursprung
            ledger[-1]["betrag"] = ursprung
            ledger.append({
                "police_id": int(police),
                "tarif_generation": tarif_generation,
                "ereignis": "PEX",
                "vertragsjahr": _vertragsjahre(beginn, stichtag),
                "status_date": pd.Timestamp(stichtag),
                "betrag_art": "VS",
                "betrag": vs_bfr,
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


def _felder_fuer(generationsfelder: Optional[Dict[str, Any]],
                 police: str) -> Dict[str, Any]:
    """Die Rechnungsgrundlagen einer Police: ein Satz fuer alle (einzellige
    Spez) oder je Police der Satz ihrer Zelle (mehrzellige Spez)."""
    felder = generationsfelder or {}
    if felder and police in felder:
        return dict(felder[police])
    if felder and all(isinstance(v, dict) for v in felder.values()):
        return {}      # je Police, aber diese fehlt
    return dict(felder)


def _beitragsfreie_uebernahme(
    zeile: Dict[str, Any], generationsfelder: Dict[str, Any], pex_jahr: int
) -> Tuple[float, float]:
    """Ursprungssumme und beitragsfreie Summe eines beitragsfrei
    uebernommenen Vertrags — gerechnet, und gegen die Lieferung gehalten.

    Die gelieferte Summe IST die beitragsfreie (so fuehren Abzuege
    beitragsfrei gestellte Vertraege). Der Stamm des Zielmodells traegt
    den Ursprungssatz; die Ursprungssumme ist die, aus der der Kern die
    gelieferte beitragsfreie Summe bildet — dieselbe Umkehrung, die die
    Pruefstrecke fuer ihren Anfangszustand nutzt. Dass der Kern auf der
    Ursprungssumme die gelieferte Summe auf den Cent reproduziert, ist
    hier Bedingung, kein Vertrauen.
    """
    felder = {
        "x": int(zeile["entry_age"]), "sex": str(zeile["sex"]),
        "n": int(zeile["duration"]), "t": int(zeile["premium_duration"]),
        "zw": int(zeile["zahlweise"]),
        **{k: v for k, v in generationsfelder.items()},
    }
    geliefert = float(zeile["sum_insured"])
    police = zeile.get("police_id")
    try:
        ursprung = leite_pex_ursprungssumme_ab(
            {**felder, "sum_insured": geliefert},
            pex_jahr=pex_jahr, vs_bfr=geliefert)
    except MigrationszugangFehler as exc:
        raise SystemExit(
            f"Police {police}: beitragsfrei uebernommen, aber die "
            f"Ursprungssumme ist nicht ableitbar — {exc}"
        ) from exc
    vs_bfr = float(
        Rechenkern(ModelPoint(**felder, sum_insured=ursprung))
        .beitragsfreie_summe(pex_jahr)
    )
    if abs(vs_bfr - geliefert) > 0.005:
        raise SystemExit(
            f"Police {police}: der Kern bildet aus der Ursprungssumme "
            f"{ursprung:.2f} die beitragsfreie Summe {vs_bfr:.2f}, geliefert "
            f"ist {geliefert:.2f} — die Umkehrung reproduziert die Lieferung "
            "nicht; Lieferung oder Rechnungsgrundlagen klaeren"
        )
    return float(ursprung), vs_bfr


def materialisiere_anfangszustand(
    stamm: pd.DataFrame,
    ledger: pd.DataFrame,
    zustaende: Dict[str, Dict[str, Any]],
    generationsfelder: Optional[Dict[str, Any]],
    *,
    scheiben_mit_gamma1: bool,
) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """Den Anfangszustand der Pruefstrecke in die Tabellen schreiben.

    ``zustaende`` ist das Ergebnis von
    ``migrationssuite_lauf.anfangszustaende_je_police`` — je Police die
    Grund- bzw. Ursprungssumme (``sum_insured``), die Alt-Erhoehungen
    (``scheiben``: (Vertragsjahr, Summe)), ein Freistellungsjahr oder
    eine Herabsetzung (``reduktion``). Hier wird daraus, was die
    Fuehrung liest: die Stammsumme, ``scheiben.parquet`` mit derselben
    Konstruktionsregel wie die Ereignis-Engine (``erhoehungs_scheibe``,
    gamma1 nach dem Schalter der Generation) und der Zugang ueber die
    Gesamtsumme aller Bausteine.

    Eine Herabsetzung als ZUSTAND (die PLV-Verfahren prospektiv und
    mit Abzug fuehren den Vertrag geteilt weiter) kann die Fuehrung
    nicht tragen: harter Halt, "nicht freigeschaltet" ist ein benannter
    Zustand. Die Teilkuendigung der Quelle fuehrt zustandslos mit
    kleinerer Grundsumme weiter und erzeugt gar keinen Zustand.
    Mutiert ``stamm`` und ``ledger`` in place; Rueckgabe sind die
    Scheiben und Zaehler fuer den Beleg.
    """
    index_je_police = {int(pid): i for i, pid in enumerate(stamm["police_id"])}
    rows: List[Dict[str, Any]] = []
    gesperrt: List[str] = []
    zahlen = {"mit_anfangszustand": 0, "mit_scheiben": 0, "scheiben": 0,
              "beitragsfrei": 0}
    for police in sorted(zustaende, key=int):
        z = zustaende[police]
        pid = int(police)
        if pid not in index_je_police:
            raise SystemExit(
                f"Police {police}: Anfangszustand fuer eine Police, die "
                "nicht im Stamm steht — Zeilen und Vorgeschichte gehoeren "
                "zur selben Lieferung")
        if z.get("reduktion") is not None:
            gesperrt.append(police)
            continue
        zahlen["mit_anfangszustand"] += 1
        i = index_je_police[pid]
        if "sum_insured" in z:
            stamm.loc[i, "sum_insured"] = float(z["sum_insured"])
        if z.get("beitragsfrei_seit_jahr") is not None:
            zahlen["beitragsfrei"] += 1
        scheiben = tuple(z.get("scheiben", ()))
        if not scheiben:
            continue
        felder = _felder_fuer(generationsfelder, police)
        if not felder:
            raise SystemExit(
                f"Police {police}: Alt-Erhoehungen ohne Rechnungsgrundlagen "
                "— --generation-spez mitgeben")
        row = stamm.loc[i]
        grund_mp = ModelPoint(**model_point_kwargs(row, felder))
        start = pd.Timestamp(row["insurance_start"])
        for nr, (jahr, vs) in enumerate(sorted(scheiben), start=1):
            try:
                sch = erhoehungs_scheibe(
                    grund_mp, int(jahr), float(vs),
                    gamma1_uebernehmen=scheiben_mit_gamma1)
            except ValueError as exc:
                raise SystemExit(
                    f"Police {police}: Alt-Erhoehung im Vertragsjahr {jahr} "
                    f"ist kein Baustein — {exc}") from exc
            rows.append({
                "police_id": pid,
                "scheiben_id": nr,
                "erhoehung_jahr": int(jahr),
                "erhoehung_datum": pd.Timestamp(
                    dt.date(start.year + int(jahr), start.month, 1)),
                "entry_age": sch.x,
                "duration": sch.n,
                "premium_duration": sch.t,
                "sum_insured": sch.sum_insured,
                "gamma1": sch.gamma1,
            })
        zahlen["mit_scheiben"] += 1
        zahlen["scheiben"] += len(scheiben)
        # Der Zugang bucht die VERSICHERUNGSSUMME des Vertrags — mit
        # seinen Bausteinen; die Bewegungsrechnung fuehrt die Gesamtsumme.
        gesamt = grund_mp.sum_insured + sum(float(s) for _, s in scheiben)
        zug = (ledger["police_id"] == pid) & (ledger["ereignis"] == "ZUG")
        ledger.loc[zug, "betrag"] = gesamt
    if gesperrt:
        raise SystemExit(
            f"{len(gesperrt)} Vertraege tragen eine Herabsetzung als "
            f"Zustand (z. B. {gesperrt[:5]}): Die Fuehrung kann einen "
            "geteilten Vertrag (Verfahren prospektiv/mit_abzug) nicht "
            "tragen — nicht freigeschaltet. Nur die Teilkuendigung fuehrt "
            "zustandslos weiter (--red-verfahren teilkuendigung, wenn das "
            "Bedingungswerk der Quelle sie vorsieht)."
        )
    scheiben_df = (
        pd.DataFrame(rows, columns=list(SCHEIBEN_NAMES))
        .astype(dict(SCHEIBEN_SPALTEN))
    )
    if len(scheiben_df):
        scheiben_df = scheiben_df.sort_values(
            ["police_id", "scheiben_id"], kind="stable").reset_index(drop=True)
    return scheiben_df, zahlen


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
    p.add_argument(
        "--anfangszustand", dest="anfangszustand", default=None,
        choices=(MATERIALISIEREN, GRUNDVERTRAG),
        help="Pflicht, sobald die Vorgeschichte ERH oder RED traegt: "
             f"'{MATERIALISIEREN}' schreibt den Anfangszustand der "
             "Pruefstrecke in die Tabellen (Grundsumme, Alt-Scheiben; "
             "Freischaltung), "
             f"'{GRUNDVERTRAG}' fuehrt die Vertraege ausdruecklich als "
             "Grundvertrag mit der gelieferten Summe (nicht "
             "freigeschaltet; im Beleg ausgewiesen).")
    p.add_argument("--erhoehungssatz", dest="erhoehungssatz", type=float,
                   default=None, metavar="SATZ",
                   help="BELEGTER Dynamiksatz der Alt-Erhoehungen — wie in "
                        "aktuartest_lauf/migrationssuite_lauf")
    p.add_argument("--red-verfahren", dest="red_verfahren",
                   default=PROSPEKTIV, choices=sorted(VERFAHREN),
                   help="Verfahren der Beitragsherabsetzung der Quelle — "
                        "wie in der Pruefstrecke; nur 'teilkuendigung' "
                        "ist in der Fuehrung freigeschaltet")
    p.add_argument("--red-anteil", dest="red_anteile", action="append",
                   default=[], metavar="POLNR=ANTEIL",
                   help="nachgelieferter fortgefuehrter Beitragsanteil "
                        "(wiederholbar) — wie in der Pruefstrecke")
    p.add_argument("--red-anteil-kandidat", dest="red_anteil_kandidaten",
                   action="append", type=float, default=[], metavar="ANTEIL",
                   help="BELEGTER Tarif-Kandidat des Herabsetzungsanteils "
                        "(wiederholbar) — wie in der Pruefstrecke")
    p.add_argument("--red-anteile-datei", dest="red_anteile_datei",
                   default=None, metavar="REGISTRIERTE_DATEI",
                   help="REGISTRIERTE Nachlieferung der Anteile "
                        "(POLNR;GEVO;DATUM;ANTEIL)")
    p.add_argument("--anker-erwartungswerte", dest="anker_quelle",
                   default=None, metavar="REGISTRIERTE_DATEI",
                   help="REGISTRIERTE Erwartungswerte am Verankerungs"
                        "zeitpunkt (Ankerwerte fuer die Kalibrierung "
                        "offener Anteile) — wie in der Pruefstrecke")
    p.add_argument("--scheiben-mit-gamma1", dest="scheiben_mit_gamma1",
                   action="store_true",
                   help="Erhoehungsscheiben mit voller Beitragsformel "
                        "(gamma1) — Tarifwerks-Eigenschaft der Lieferung; "
                        "wird Eigenschaft der Generation in der Config")
    p.add_argument("--stoab-je-baustein", dest="stoab_je_baustein",
                   action="store_true",
                   help="Stornoabschlag-Grenzen je Baustein — "
                        "Tarifwerks-Eigenschaft der Lieferung; wird "
                        "Eigenschaft der Generation in der Config")
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

    vorgeschichte = _vorgeschichte(fall, args.vorgeschichte)
    arten = {art for eintraege in vorgeschichte.values() for art, _ in eintraege}
    mit_bausteinen = sorted(
        police for police, eintraege in vorgeschichte.items()
        if any(art in ("ERH", "RED") for art, _ in eintraege)
    )
    if mit_bausteinen and args.anfangszustand is None:
        print(
            f"Die Vorgeschichte traegt Erhoehungen/Herabsetzungen fuer "
            f"{len(mit_bausteinen)} Vertraege ({sorted(arten & {'ERH', 'RED'})}). "
            f"--anfangszustand {MATERIALISIEREN} schreibt den Anfangszustand "
            "der Pruefstrecke in die Tabellen (Freischaltung); "
            f"--anfangszustand {GRUNDVERTRAG} fuehrt die Vertraege "
            "ausdruecklich als Grundvertrag mit der gelieferten Summe "
            "(nicht freigeschaltet). Ohne Angabe wird nichts geschrieben.",
            file=sys.stderr)
        return 2
    if args.anfangszustand == MATERIALISIEREN and not args.generation_spez:
        print(f"--anfangszustand {MATERIALISIEREN} braucht --generation-spez "
              "(Rechnungsgrundlagen der Bausteine)", file=sys.stderr)
        return 2
    tarifwerk = {
        "scheiben_mit_gamma1": bool(args.scheiben_mit_gamma1),
        "stoab_je_baustein": bool(args.stoab_je_baustein),
        "red_verfahren": str(args.red_verfahren),
    }

    stamm, historie, ledger, hinweise = baue(
        zeilen,
        tarif_generation=args.generation,
        produkt=args.produkt,
        stichtag=_parse(args.stichtag),
        vorgeschichte=vorgeschichte,
        generationsfelder=generationsfelder,
    )

    beleg: Dict[str, Any] = {
        "schema_version": BELEG_SCHEMA_VERSION,
        "anfangszustand": args.anfangszustand or "ohne_bausteine",
        "tarifwerk": tarifwerk,
        "erhoehungssatz": args.erhoehungssatz,
        "red_anteile": sorted(args.red_anteile),
        "red_anteil_kandidaten": sorted(args.red_anteil_kandidaten),
        "anker_erwartungswerte": args.anker_quelle,
        "vorgeschichte": args.vorgeschichte,
        "vertraege": int(len(stamm)),
        "vertraege_mit_bausteinen": len(mit_bausteinen),
        "mit_anfangszustand": 0,
        "mit_scheiben": 0,
        "scheiben": 0,
        "beitragsfrei": int((ledger["ereignis"] == "PEX").sum()),
        "ohne_anfangszustand": [],
        "nicht_freigeschaltet": [],
    }
    scheiben = None
    if args.anfangszustand == MATERIALISIEREN:
        from rechner_pipeline.gates.migrationssuite_lauf import (
            VORGABE,
            _lies_csv,
            anfangszustaende_je_police,
            auspraegungen_je_police,
        )

        rohe_vorgeschichte = _lies_csv(fall, args.vorgeschichte)
        auspraegungen = auspraegungen_je_police(spez, zeilen)
        red_anteile: Dict[str, float] = {}
        red_anteile_je_datum: Dict[str, Dict[str, float]] = {}
        if args.red_anteile_datei is not None:
            for zeile in _lies_csv(fall, args.red_anteile_datei):
                if zeile.get("GEVO") == "RED" and zeile.get("ANTEIL"):
                    red_anteile[str(zeile["POLNR"])] = float(zeile["ANTEIL"])
                    if zeile.get("DATUM"):
                        red_anteile_je_datum.setdefault(
                            str(zeile["POLNR"]), {})[str(zeile["DATUM"])] = (
                                float(zeile["ANTEIL"]))
        for eintrag in args.red_anteile:
            police, _, wert = eintrag.partition("=")
            if not police or not wert:
                print(f"--red-anteil {eintrag!r}: erwartet POLNR=ANTEIL",
                      file=sys.stderr)
                return 2
            red_anteile[police.strip()] = float(wert)
        anker: Dict[str, Tuple[int, float]] = {}
        if args.anker_quelle is not None:
            quelle = json.loads(fall_mod.eingang_datei(
                fall, args.anker_quelle).read_text(encoding="utf-8"))
            for eintrag in quelle.get("vertraege", []):
                erster = next(
                    (x for x in (eintrag.get("punkte") or [])
                     if x.get("anlass") == "uebernahme"
                     and "kVx_MRV" in (x.get("erwartet") or {})), None)
                if erster:
                    anker[str(eintrag["police_id"])] = (
                        int(erster["monate"]),
                        float(erster["erwartet"]["kVx_MRV"]))
        # DIESELBE Ableitung wie aktuartest_lauf, verankerung_belegen und
        # migrationssuite_lauf — ein Ort, an dem der Anfangszustand
        # entsteht. Der Stamm dient ihr nur als Traeger der Vertragsdaten;
        # ihre Summen nimmt sie aus den transformierten Zeilen.
        zustaende, warnungen = anfangszustaende_je_police(
            spez, zeilen, rohe_vorgeschichte, stamm, spalten=dict(VORGABE),
            red_verfahren=args.red_verfahren, red_anteile=red_anteile,
            auspraegungen=auspraegungen,
            erhoehungssatz=args.erhoehungssatz, anker=anker,
            red_anteile_je_datum=red_anteile_je_datum,
            red_anteil_kandidaten=tuple(args.red_anteil_kandidaten),
            scheiben_mit_gamma1=args.scheiben_mit_gamma1)
        scheiben, zahlen = materialisiere_anfangszustand(
            stamm, ledger, zustaende, generationsfelder,
            scheiben_mit_gamma1=args.scheiben_mit_gamma1)
        beleg.update(zahlen)
        for w in warnungen:
            # Wie in der Pruefstrecke: kein geratener Zustand, der Vertrag
            # laeuft als Grundvertrag — und steht hier mit Namen und Grund.
            treffer = re.match(r"Police (\S+?)[ :(]", w)
            beleg["ohne_anfangszustand"].append({
                "police_id": treffer.group(1) if treffer else None,
                "grund": w,
            })
            print(f"WARNUNG Anfangszustand nicht ableitbar: {w}",
                  file=sys.stderr)
    elif mit_bausteinen:
        beleg["nicht_freigeschaltet"] = mit_bausteinen
        hinweise.append(
            f"{len(mit_bausteinen)} Vertraege mit Erhoehungen/Herabsetzungen "
            "werden als Grundvertrag mit der gelieferten Summe gefuehrt "
            f"(--anfangszustand {GRUNDVERTRAG}): NICHT freigeschaltet. Die "
            "Fuehrung rechnet diese Vertraege nicht so, wie die "
            "Pruefstrecke sie abgenommen hat."
        )

    write_portfolio(stamm, ziel / "bestand.parquet")
    write_portfolio(historie, ziel / "historie.parquet")
    write_portfolio(ledger, ziel / "ledger.parquet")
    if scheiben is not None and len(scheiben):
        write_portfolio(scheiben, ziel / "scheiben.parquet")
        print(f"  scheiben.parquet  {len(scheiben)} Alt-Erhoehungen "
              f"({beleg['mit_scheiben']} Vertraege; gamma1 "
              f"{'uebernommen' if args.scheiben_mit_gamma1 else '0'})")

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
        abschnitt = _zellen_toml(spez, args.generation, tarifwerk)
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

    # Der Beleg der Uebernahme: Modus, Schalter, Zaehler, die namentlich
    # ausgewiesenen Ausnahmen. Die Fuehrungsprobe liest ihn; ein Bestand
    # ohne Beleg hat keinen benannten Anfangszustand.
    (ziel / "uebernahme.json").write_text(
        json.dumps(beleg, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(f"{len(stamm)} Vertraege uebernommen nach {ziel} "
          f"(Anfangszustand: {beleg['anfangszustand']})")
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
