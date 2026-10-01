"""``fuehrungsprobe`` — die Fuehrung gegen die Pruefstrecke (Freischaltung, Schritt 6).

Produzent, kein Gate (Muster ``gates.migrationssuite_lauf``): schreibt
einen JSON-Beleg, den der Abnahmebericht im Bestands-Scope bindet und
A-M4 als Pflichtbelegrolle ``fuehrungsprobe`` verlangt.

**Die Frage, die er beantwortet.** Die Abnahmen A-M1 bis A-M4 rechnen
jeden uebernommenen Vertrag auf seinem Anfangszustand mit den Tarifregeln
der Spez (Tarifwerk und Quellverfahren, ADR-024, Nachtrag — vorher
Schalter der Lieferung) und der Korrekturschicht. Ob der gefuehrte Bestand diese
Welt auch benutzt, sah bis zur Freischaltung niemand: Kein Gate stellte
das Ledger der Fuehrung neben die Werte der Pruefstrecke — im zweiten
Baldrian-Fall lagen 550 von 834 Stammsummen in der falschen Welt
(dev-docs/freischaltung-uebernommener-bestand.md, Abschnitt 1.1). Hier
wird der Bestand, den die Uebernahme geschrieben hat, und das Journal,
das die Fortschreibung darauf gebucht hat, gegen die Pruefstrecken-Welt
gehalten:

1. der Uebernahmebeleg (``uebernahme.json``): materialisierter
   Anfangszustand, Tarifwerk gleich dem der Config der Generation und
   dem der Spez, Quellverfahren gleich dem der Spez;
2. je Vertrag: Stammsumme, Bausteine (Scheiben mit ihrem gamma1),
   Beitragsfreistellung, Zugang und Umbuchung gegen den Anfangszustand,
   den DIESELBE Ableitung wie in den Abnahmen liefert
   (``migrationssuite_lauf.anfangszustaende_je_police``); die
   Rechnungsgrundlagen der Config gegen die Spez-Zelle des Vertrags;
3. je Buchung der Fortschreibung nach dem Stichtag (Storno, Umbuchung,
   Tod, Ablauf) den Betrag gegen die Pruefstrecken-Engine am gebuchten
   Vertragsmonat — Kern mit Bausteinen, Stornoabzug je Baustein nach
   Tarifwerk, Korrekturschicht aus dem Schichtbeleg;
4. die Fortschreibung bewegt nur, was nach dem Stichtag geschieht
   (Pruefrunde T27, Runde C): das Ledger bis zum Stichtag ist das der
   Uebernahme, Schichten, Verankerung und Merkmale der Fortschreibung sind
   die der Uebernahme (feldweise, Schichten zusaetzlich gegen den
   Schichtbeleg), und eine Herabsetzung liegt nach dem Bestandszugang, vor
   dem im Laufmanifest belegten Horizont und auf einem beitragspflichtigen
   Vertrag — sonst ist sie keine Buchung dieses Laufs und hat kein Soll.

**Das Buchungsfenster und die Bindung an die Rate** (Runde E, Klasse
geschlossen) gelten fuer JEDE Ereignisart, nicht nur fuer die Herabsetzung:
Eine Buchung der uebernommenen Vertraege liegt echt nach dem Bestandszugang
und nicht hinter dem im Laufmanifest belegten Horizont
(``models.bestand.buchungsfenster_verstoesse``, dieselbe Regel wie in
``validate_ledger``), und sie folgt aus einer Erfahrungsannahme der Config,
deren Rate nicht null ist (``models.bestand.unbelegte_ereignisse``, dieselbe
Regel wie in P-B1); ein (Produkt, Ereignis)-Paar ohne Annahme und ohne
benannte Ausnahme ist ein Befund (``unzugeordnete_ereignisse``), und die
Ausnahme-Ereignisse ZUG, MIG und ABL stehen an ihrem Zeitpunkt
(``models.bestand.ausnahme_ereignis_verstoesse``).

**Paarbuchung, endlicher Betrag, Wirkungstag** (Runde F): Je Vorfall mit
Beitragswirkung steht genau ein Paar aus Summen- und Beitragszeile
(``models.bestand.beitragspaar_verstoesse``, dieselbe Regel wie in
``validate_ledger``); jede Zeile der uebernommenen Vertraege traegt einen
endlichen Betrag (``abs(betrag - erwartet) > TOLERANZ`` ist bei NaN immer
falsch — ein NaN galt als geprueft und uebereinstimmend); die Probe vergleicht
Betraege an ALLEN Stellen nur noch durch ``models.bestand.weicht_ab``, die
nicht endliche Werte auf Ist- wie Soll-Seite als Abweichung meldet (Runde F,
Nachbesserung: Stammsumme, Bausteine, Zugang, PEX-Umbuchung, nachgerechnete
Buchungen); und jede Buchung nach
dem Stichtag steht am Jahrestag ihres Vertragsjahres, der Wirkungstag einer
Herabsetzung am Jahrestag ihres Reduktionsjahres (``reduktion_jahrestag``, die
Regel von ``validate_reduktionen``). Eine solche Zeile wird nicht
nachgerechnet und nicht als geprueft gezaehlt.

**Eindeutigkeit und Vorfall** (Runde F, Nachbesserung): Je (Police, Ereignis,
Wirkungstag, Betragsart) steht genau eine Zeile, fuer JEDE Ereignisart
(``models.bestand.doppelte_buchungen``, dieselbe Regel wie in
``validate_ledger``; sie gilt auch fuer den Ledger der Uebernahme); die
ueberzaehlige Zeile wird nicht nachgerechnet und nicht als geprueft gezaehlt.
Eine Zeile, die eine andere Regel (Fenster, Ausnahme-Ereignis, Wirkungstag)
schon beanstandet, nimmt ihren ganzen Vorfall aus der Paarregel — ein Fehler,
ein Befund —, und ein in der Zeit getrenntes Paar ist ein Befund
(``tag_verschoben``).

**Belege vor dieser Aenderung** (Pruefrunde T27, Runde C) sind nicht mehr
nachrechenbar: Die Probe bindet jetzt die Nebentabellen der
Fortschreibung (Schichten, Verankerung, Merkmale) und das
``laufmanifest.json`` als Eingaben; ein aelterer Beleg traegt diese
Bindung nicht. Sie werden bei der Neuzeichnung des Standes neu gefahren,
nicht nachgefuehrt.

Was die Probe NICHT ist: keine zweite Abnahme. Sie rechnet mit denselben
Kern-Funktionen wie die Pruefstrecke und prueft, ob die Fuehrung sie
ruft — Materialisierung und Verdrahtung, nicht Tarifmathematik.

Knoten: klv
"""

from __future__ import annotations

import argparse
import dataclasses as _dataclasses
import datetime as dt
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from rechner_pipeline.gates._provenienz import lebendes_repo  # --repo-root (G12)
from rechner_pipeline import fall as fall_mod
from rechner_pipeline.bestand.config import BestandConfig, config_aus_text
from rechner_pipeline.bestand.parquet_io import read_portfolio_aus_bytes
from rechner_pipeline.gates._common import Eingangsbindung
from rechner_pipeline.gates._provenienz import systemstand
from rechner_pipeline.gates.bestand_uebernehmen import GRUNDVERTRAG, MATERIALISIEREN
from rechner_pipeline.gates.migrationssuite_lauf import (
    VORGABE,
    _lies_csv,
    anfangszustaende_je_police,
    auspraegungen_je_police,
    lies_auskuenfte,
    tarifregeln_des_falls,
)
from rechner_pipeline.kern import ModelPoint, Rechenkern, erhoehungs_scheibe, vertrags_monatsreserve
from rechner_pipeline.kern.beitragsreduktion import TEILKUENDIGUNG
from rechner_pipeline.kern import (
    VORGANG_RANG as RANG,
    Vertragsstand,
    Vorgangsfolge,
    vorgang,
)
from rechner_pipeline.ontologie.tbox import TARIFWERK_MERKMALE
from rechner_pipeline.spez.tarifregeln import (
    TarifregelnFehler,
    verweigere_entfallene_schalter,
)

#: Die Codes der Reihenfolge eines Jahrestags (kern.vorgangsfolge.RANG).
PEX_CODE = "PEX"
RED_CODE = "RED"
from rechner_pipeline.kern.korrekturschicht import (
    Schichtparameter,
    schicht_traegt,
    schichtwert_bei,
    zuschlag_bei_pex,
)
from rechner_pipeline.models.bestand import (
    EREIGNIS_ZUSTAND,
    GENERATION_FIELDS,
    LEDGER_NAMES,
    SCHEIBEN_NAMES,
    REDUKTIONEN_NAMES,
    SCHICHTEN_NAMES,
    STAMM_NAMES,
    STATUS_CODE_VALUES,
    STATUS_HISTORIE_NAMES,
    VERANKERUNG_NAMES,
    ausnahme_ereignis_verstoesse,
    ausnahme_ereignis_text,
    beitragspaar_text,
    beitragspaar_verstoesse,
    buchungsfenster_verstoesse,
    doppelte_buchung_text,
    doppelte_buchungen,
    jahrestag_verstoesse,
    model_point_kwargs,
    REDUKTION_EREIGNISSE,
    red_bindung_fehler,
    reduktion_ereignis,
    red_sollbuchungen,
    red_vollstaendigkeit_fehler,
    reduktion_jahrestag,
    unbelegte_ereignisse,
    unbelegte_ereignisse_text,
    unzugeordnete_ereignisse,
    weicht_ab,
)

#: Die drei Spalten des Stamms, die die Fortschreibung BEWEGEN darf.
#: Sie zu bewegen IST die Fortschreibung; jede andere Stammspalte ist
#: Identitaet und wird verglichen (Befund T26-05).
ZUSTANDSSPALTEN = ("status_id", "status_code", "status_date")
from rechner_pipeline.models.manifest import GeleseneDatei
from rechner_pipeline.spez.validierung import lade_spez_aus_bytes, spez_pfad

#: Schema des Probe-Belegs. 2 seit Review T25-02/T25-01: Der Beleg fuehrt
#: ``endbestand_geprueft`` als Zahl, und der Abnahmebericht verlangt einen
#: Katalog positiver Zaehler statt nur Flags. 3 seit Pruefrunde T27,
#: Befund 06: Der Beleg nennt seinen vollstaendigen Aufruf
#: (``provenienz.aufruf``), damit der Konsument ihn nachrechnen kann,
#: statt ihm zu glauben. 4 seit dem Pruefer-Befund B1 zur Alt-Absetzung
#: (2026-10-01): Der Beleg fuehrt ``gedeckt`` (die Policen, deren
#: Anfangszustand die Auskunft traegt) und befundet jeden Vertrag ohne
#: ableitbaren Anfangszustand, statt nur die Gleichheit der Listen zu pruefen.
#: 5 seit ADR-024, Nachtrag (2026-10-01): Die Tarifregeln kommen aus der
#: Spez; der Aufruf traegt keine Tarifschalter mehr, die Parameter nennen
#: ``tarifregeln``, und der Beleg prueft das Quellverfahren des
#: Uebernahmebelegs. Ein Beleg der Fassung 4 ist mit seinem Aufruf nicht
#: mehr nachrechenbar (seine Schalter werden verweigert).
SCHEMA_VERSION = 5

#: Die Optionen, deren Wert ein Pfad ist. Im Aufruf des Belegs stehen sie
#: relativ zum Fall (wo sie darin liegen); der Konsument loest sie gegen
#: seinen Fall auf. Die uebrigen Werte sind Namen im Fall oder Zahlen.
PFAD_OPTIONEN = ("--uebernahme", "--fortschreibung", "--config", "--zeilen")

#: Cent-Toleranz wie in der Ledger-Herleitung von P-B1: Fuehrung und
#: Pruefstrecke rufen dieselben Kern-Funktionen; ein vertragsweiter
#: Stornoabzug der Vorgabe darf um Gleitkomma-Rauschen abweichen, eine
#: falsche Welt liegt Groessenordnungen darueber.
TOLERANZ = 0.005

#: RED seit der Angriffsrunde der Nacht: Die Auszahlung der Teilkuendigung
#: ist eine echte Zahlung an den Kunden und hatte keinen zweiten Rechenweg.
GEPRUEFTE_BUCHUNGEN = ("STO", "PEX", "TOD", "ABL", "RED", "TKU")


def _jahre(beginn: pd.Timestamp, datum: pd.Timestamp) -> int:
    return ((datum.year * 12 + datum.month) - (beginn.year * 12 + beginn.month)) // 12


def _zelle(spez, auspraegungen: Dict[str, str]):
    gesucht = {k: str(v).strip().lower() for k, v in auspraegungen.items() if v}
    treffer = [z for z in spez.zellen if z.auspraegungen == gesucht]
    if not treffer:
        raise SystemExit(
            f"keine Spez-Zelle fuer {gesucht!r} — vorhanden sind "
            f"{[z.auspraegungen for z in spez.zellen]}")
    return treffer[0]


#: Die Felder der Korrekturschicht, die Tabelle und Beleg BEIDE fuehren.
#: Verglichen wurde bisher nur ``rho`` — elf weitere Spalten standen
#: unbezeugt daneben (Review T25-03). Aus der Datenklasse abgeleitet, nicht
#: abgetippt: Wer ein Feld ergaenzt, ergaenzt den Vergleich mit.
SCHICHT_FELDER: Tuple[str, ...] = tuple(
    f.name for f in _dataclasses.fields(Schichtparameter))


def _schichtwert(wert: Any) -> Any:
    """Tabellen- und Belegwert vergleichbar machen.

    ``formparameter`` und ``vererbend`` liegen in der Tabelle als
    JSON-Text und im Beleg als Struktur; Tupel und Listen sind dasselbe.
    """
    if isinstance(wert, str) and wert[:1] in ("{", "["):
        try:
            wert = json.loads(wert)
        except ValueError:
            return wert
    if isinstance(wert, (list, tuple)):
        return [_schichtwert(x) for x in wert]
    return wert


def _zellwert(v: Any) -> Any:
    """Ein Tabellenwert vergleichbar: Datum als Timestamp, Zahlen auf sechs
    Stellen, fehlend als None."""
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return None
    if isinstance(v, (pd.Timestamp, dt.date, np.datetime64)):
        return pd.Timestamp(v)
    if isinstance(v, (float, np.floating)):
        return round(float(v), 6)
    if isinstance(v, (int, np.integer)):
        return int(v)
    return str(v)


def _zeilenmenge(df: Optional[pd.DataFrame], spalten: List[str]) -> Counter:
    """Zeilen als Multimenge vergleichbarer Tupel (Datum als Timestamp,
    Zahlen auf sechs Stellen, fehlend als None)."""
    if df is None or not len(df):
        return Counter()
    return Counter(tuple(_zellwert(z[s]) for s in spalten) for z in df.to_dict("records"))


#: Die Nebentabellen, die die Fortschreibung MITFUEHRT und nicht bewegen
#: darf: Sie sind Vertragsidentitaet wie die Stammspalten (T26-05, "die
#: Fortschreibung bewegt Zustaende, nicht Identitaeten"). Rolle -> (Art des
#: Befunds, Schluesselspalten je Zeile). ``cli_fortschreibung`` reicht sie
#: unveraendert aus der Uebernahme in den Lauf.
NEBENTABELLEN_IDENTITAET: Dict[str, Tuple[str, Tuple[str, ...]]] = {
    "schichten": ("schicht", ("police_id",)),
    "verankerung": ("verankerung", ("police_id",)),
    "merkmale": ("merkmale", ("police_id", "dimension")),
}


def _nebentabelle_gleich(befund, rolle: str, art: str, schluessel: Tuple[str, ...],
                         soll: Optional[pd.DataFrame], ist: Optional[pd.DataFrame]) -> None:
    """Eine Nebentabelle der Fortschreibung FELDWEISE gegen die der
    Uebernahme halten (Pruefrunde T27, Runde C, Befund RC04).

    Die Probe las von der Fortschreibung nur Ledger, Scheiben, Historie,
    Endbestand und Reduktionen. ``schichten.parquet`` und
    ``merkmale.parquet`` der Fortschreibung — das, worauf ``einzelwerte_am``
    und der Abschluss bewerten — blieben ungeprueft: Ein rho von 1e-8 auf
    0,05 verschob das Deckungskapital eines Vertrags am Folgestichtag von
    23.106,92 auf 35.900,67 EUR (+55 Prozent), ein Merkmal nichtraucher ->
    raucher um 66,31 EUR, jeweils bei gruener Probe und gruenem
    A-M4-Konsumenten. Fuer die Tabelle der UEBERNAHME tat die Probe den
    Feldvergleich laengst; hier dieselbe Regel, je Zeile und Feld, damit
    die Meldung den Vertrag und das Feld nennt.
    """
    def indiziert(df: Optional[pd.DataFrame]):
        je: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
        doppelt: List[Tuple[Any, ...]] = []
        if df is None:
            return je, doppelt
        for z in df.to_dict("records"):
            k = tuple(_zellwert(z[c]) for c in schluessel)
            if k in je:
                doppelt.append(k)
            je[k] = z
        return je, doppelt

    soll_je, _ = indiziert(soll)
    ist_je, ist_doppelt = indiziert(ist)
    kopf = f"{rolle}.parquet der Fortschreibung"
    if ist_doppelt:
        befund(None, art, f"{kopf}: Schluessel {[list(k) for k in ist_doppelt[:3]]} "
                          "mehrfach — die Fortschreibung fuehrt die Tabelle der Uebernahme")
    fehlt = sorted(set(soll_je) - set(ist_je), key=str)
    if fehlt:
        befund(None, art, f"{kopf}: {len(fehlt)} Zeile(n) der Uebernahme fehlen "
                          f"{[list(k) for k in fehlt[:3]]} — die Fortschreibung fuehrt "
                          "die Tabelle der Uebernahme unveraendert")
    zuviel = sorted(set(ist_je) - set(soll_je), key=str)
    if zuviel:
        befund(None, art, f"{kopf}: {len(zuviel)} Zeile(n) ohne Zeile in der Uebernahme "
                          f"{[list(k) for k in zuviel[:3]]}")
    for k in sorted(set(soll_je) & set(ist_je), key=str):
        for feld in soll_je[k]:
            if _schichtwert(_zellwert(ist_je[k].get(feld))) != _schichtwert(_zellwert(soll_je[k][feld])):
                pid = k[0] if schluessel[0] == "police_id" else None
                befund(pid, art,
                       f"{feld} {ist_je[k].get(feld)!r} in {kopf}, "
                       f"{soll_je[k][feld]!r} in der Uebernahme (Schluessel {list(k)}) — "
                       "die Fortschreibung bewegt Zustaende, nicht Identitaeten",
                       feld=feld)


def _schicht_gegen_beleg(befund, tabelle: pd.DataFrame,
                         schicht_je_police: Dict[int, Tuple[Schichtparameter, int]],
                         herkunft: str) -> None:
    """Jedes Feld jeder Schicht einer Tabelle gegen den Schichtbeleg — fuer
    die Tabelle der Uebernahme und ebenso fuer die der Fortschreibung
    (``herkunft`` benennt sie in der Meldung)."""
    je_police = {int(z["police_id"]): z for z in tabelle.to_dict("records")}
    for pid, (param, _) in sorted(schicht_je_police.items()):
        zeile = je_police.get(pid)
        if zeile is None:
            continue
        for feld in SCHICHT_FELDER:
            if _schichtwert(zeile[feld]) != _schichtwert(getattr(param, feld)):
                befund(pid, "schicht",
                       f"{feld} {zeile[feld]!r} in {herkunft}, "
                       f"{getattr(param, feld)!r} im Schichtbeleg", feld=feld)


def _beispiele(menge: Counter) -> List[Any]:
    return [list(k) for k in sorted(menge, key=str)[:3]]


def _pruefe_endzustand(
    befund, *, stamm: pd.DataFrame, historie: pd.DataFrame,
    scheiben: Optional[pd.DataFrame], f_bestand: Optional[pd.DataFrame],
    f_historie: Optional[pd.DataFrame], f_ledger: pd.DataFrame,
    f_scheiben: Optional[pd.DataFrame], stichtag: dt.date,
    u_ledger: Optional[pd.DataFrame] = None,
) -> None:
    """Den Endzustand der uebernommenen Vertraege HERLEITEN, nicht auf
    Form pruefen (Pruefrunde T27, Befund 07).

    Vorher sah die Probe im Endbestand nur die Identitaetsspalten und in
    der Historie nur die Vokabel. Der Gutachter ersetzte die Endscheiben
    und die Endhistorie durch leere Tabellen und setzte eine aktive Police
    auf den Ablaufzustand einer anderen — dreimal bestanden. Was sich
    bewegen darf, entsteht aus der Uebernahme und den GeVos danach, und
    genau daraus wird es hier gebildet:

    * Historie: die der Uebernahme, dazu je Zustands-GeVo nach dem
      Stichtag eine Zeile (``EREIGNIS_ZUSTAND``, dieselbe Tabelle wie die
      Engine) — als Multimenge, keine Zeile mehr, keine weniger;
    * Zustand im Stamm: die juengste Zeile dieser Historie (ADR-011),
      ohne Zeile der uebernommene Zustand;
    * Scheiben: die der Uebernahme unveraendert, dazu je Erhoehung nach
      dem Stichtag (``ERH`` mit ``VS_erhoehung``) genau eine Scheibe an
      ihrem Datum mit ihrer Summe;
    * Ledger bis zum Stichtag (Runde C, Befund RC02): genau die Buchungen
      der Uebernahme. Was die Fortschreibung buchen darf, liegt NACH dem
      Stichtag; der Stichtag ist der Bestandszugang, davor liegt die Zeit
      der abgebenden Gesellschaft. Die Probe pruefte bisher nur die
      Buchungen danach (``nach``) und sah eine eingetragene Herabsetzung
      vom 2025-01-01 nicht, die die Summe eines Vertrags am Stichtag von
      43.000 auf 25.800 EUR kuerzte. Ohne GeVo nach dem Stichtag bewegt
      sich an einem uebernommenen Vertrag nichts: Summe und Bewertungs-
      grundlage am Stichtag bleiben der abgenommene Anfangszustand.
    """
    uebernommen = set(int(p) for p in stamm["police_id"])
    st = pd.Timestamp(stichtag)
    eigen = f_ledger[f_ledger["police_id"].isin(uebernommen)]
    nach = eigen[pd.to_datetime(eigen["status_date"]) > st]

    # Ledger bis zum Stichtag ---------------------------------------------
    if u_ledger is not None:
        l_spalten = list(LEDGER_NAMES)
        soll_l = _zeilenmenge(u_ledger[u_ledger["police_id"].isin(uebernommen)], l_spalten)
        ist_l = _zeilenmenge(eigen[pd.to_datetime(eigen["status_date"]) <= st], l_spalten)
        if soll_l != ist_l:
            befund(None, "endledger",
                   f"Ledger der Fortschreibung bis zum Stichtag {st.date()} ist nicht die "
                   f"Uebernahme: {sum((soll_l - ist_l).values())} Buchung(en) der Uebernahme "
                   f"fehlen oder sind veraendert {_beispiele(soll_l - ist_l)}, "
                   f"{sum((ist_l - soll_l).values())} Buchung(en) davor ohne Uebernahme "
                   f"{_beispiele(ist_l - soll_l)} — die Zeit vor dem Bestandszugang gehoert "
                   "der abgebenden Gesellschaft und ist keine Buchung dieses Laufs")

    # Historie ------------------------------------------------------------
    h_spalten = ["police_id", "status_code", "status_date"]
    ueb_hist = historie[historie["police_id"].isin(uebernommen)]
    soll = _zeilenmenge(ueb_hist, h_spalten)
    zustands_gevos = {
        (int(z["police_id"]), EREIGNIS_ZUSTAND[str(z["ereignis"])], pd.Timestamp(z["status_date"]))
        for z in nach.to_dict("records") if str(z["ereignis"]) in EREIGNIS_ZUSTAND}
    soll.update(zustands_gevos)
    ist_hist = (f_historie[f_historie["police_id"].isin(uebernommen)]
                if f_historie is not None else ueb_hist.iloc[0:0])
    ist = _zeilenmenge(ist_hist, h_spalten)
    if soll != ist:
        befund(None, "endhistorie",
               f"Endhistorie der uebernommenen Vertraege ist nicht Uebernahme plus "
               f"GeVos: {sum((soll - ist).values())} Zeile(n) fehlen "
               f"{_beispiele(soll - ist)}, {sum((ist - soll).values())} ohne GeVo "
               f"{_beispiele(ist - soll)}")

    # Zustand im Stamm ---------------------------------------------------
    if f_bestand is not None:
        juengste: Dict[int, Tuple[Any, ...]] = {}
        if len(ist_hist):
            for z in ist_hist.sort_values(["police_id", "status_date", "status_id"],
                                          kind="stable").to_dict("records"):
                juengste[int(z["police_id"])] = (
                    int(z["status_id"]), str(z["status_code"]), pd.Timestamp(z["status_date"]))
        ursprung = {int(z["police_id"]): (int(z["status_id"]), str(z["status_code"]),
                                          pd.Timestamp(z["status_date"]))
                    for z in stamm.to_dict("records")}
        for z in f_bestand[f_bestand["police_id"].isin(uebernommen)].to_dict("records"):
            pid = int(z["police_id"])
            erwartet = juengste.get(pid, ursprung[pid])
            ist_z = (int(z["status_id"]), str(z["status_code"]), pd.Timestamp(z["status_date"]))
            if ist_z != erwartet:
                befund(pid, "endzustand",
                       f"Zustand im Endbestand {list(ist_z)}, aus Uebernahme und "
                       f"GeVos folgt {list(erwartet)}")

    # Scheiben -------------------------------------------------------------
    s_spalten = [c for c in SCHEIBEN_NAMES]
    ueb_s = scheiben[scheiben["police_id"].isin(uebernommen)] if scheiben is not None else None
    ist_s = f_scheiben[f_scheiben["police_id"].isin(uebernommen)] if f_scheiben is not None else None
    ist_alt = ist_s[pd.to_datetime(ist_s["erhoehung_datum"]) <= st] if ist_s is not None else None
    ist_neu = ist_s[pd.to_datetime(ist_s["erhoehung_datum"]) > st] if ist_s is not None else None
    soll_alt, ist_alt_m = _zeilenmenge(ueb_s, s_spalten), _zeilenmenge(ist_alt, s_spalten)
    if soll_alt != ist_alt_m:
        befund(None, "endscheiben",
               f"Scheiben der Uebernahme im Endbestand nicht unveraendert: "
               f"{sum((soll_alt - ist_alt_m).values())} fehlen oder sind veraendert "
               f"{_beispiele(soll_alt - ist_alt_m)}, {sum((ist_alt_m - soll_alt).values())} "
               f"unbekannt {_beispiele(ist_alt_m - soll_alt)}")
    erh = nach[(nach["ereignis"] == "ERH") & (nach["betrag_art"] == "VS_erhoehung")]
    soll_neu = _zeilenmenge(erh, ["police_id", "status_date", "betrag"])
    ist_neu_m = _zeilenmenge(ist_neu, ["police_id", "erhoehung_datum", "sum_insured"])
    if soll_neu != ist_neu_m:
        befund(None, "endscheiben",
               f"Erhoehungsscheiben nach dem Stichtag sind nicht die ERH-Buchungen: "
               f"{sum((soll_neu - ist_neu_m).values())} Buchung(en) ohne Scheibe "
               f"{_beispiele(soll_neu - ist_neu_m)}, {sum((ist_neu_m - soll_neu).values())} "
               f"Scheibe(n) ohne Buchung {_beispiele(ist_neu_m - soll_neu)}")


def pruefe_fuehrung(
    *,
    uebernahme: Dict[str, Any],
    fortschreibung: Optional[Dict[str, Any]],
    config: BestandConfig,
    spez,
    zeilen: List[Dict[str, Any]],
    vorgeschichte: List[Dict[str, str]],
    tarifwerk: Dict[str, Any],
    quellverfahren: Dict[str, Any],
    erhoehungssatz: Optional[float],
    red_anteile: Dict[str, float],
    red_anteile_je_datum: Dict[str, Dict[str, float]],
    red_anteil_kandidaten: Tuple[float, ...],
    anker: Dict[str, Tuple[int, float]],
    schichtbeleg: Optional[Dict[str, Any]],
    stichtag: dt.date,
) -> Dict[str, Any]:
    """Der rechnende Kern der Probe (rein, ohne Dateisystem).

    ``uebernahme``: ``bestand``, ``historie``, ``ledger`` (DataFrames),
    optional ``scheiben``, ``verankerung``, ``schichten``, ``merkmale``,
    und ``beleg`` (``uebernahme.json`` als Dict). ``fortschreibung``:
    ``ledger``, ``scheiben``, ``historie`` des Laufs nach dem Stichtag
    oder None. ``schichtbeleg``: ``schichten`` des Schichtbelegs
    (police -> {"hist": Parameter}) oder None. Rueckgabe: der Beleg ohne
    ``system``/``provenienz`` (die setzt ``main``).

    ``tarifwerk`` (alle vier Merkmale) und ``quellverfahren`` sind die
    Tarifregeln der Spez (``spez.tarifregeln``); ``main`` liest sie dort.
    Ein unvollstaendiges Tarifwerk wird nicht ergaenzt — vorher fuellte
    die Probe einen fehlenden Umfang der Teilkuendigung aus dem Verfahren
    und ein fehlendes Verfahren mit der PLV-Vorgabe ``prospektiv``.
    """
    befunde: List[Dict[str, Any]] = []
    if set(tarifwerk) != set(TARIFWERK_MERKMALE) or "red_verfahren" not in quellverfahren:
        raise ValueError(
            f"Fuehrungsprobe: Tarifwerk {sorted(tarifwerk)} / Quellverfahren "
            f"{sorted(quellverfahren)} unvollstaendig — die Regeln kommen ganz "
            "aus der Spez (spez.tarifregeln), keine Vorgabe ergaenzt sie")
    tarifwerk = dict(tarifwerk)
    stamm: pd.DataFrame = uebernahme["bestand"]
    historie: pd.DataFrame = uebernahme["historie"]
    ledger: pd.DataFrame = uebernahme["ledger"]
    scheiben = uebernahme.get("scheiben")
    verankerung = uebernahme.get("verankerung")
    beleg = uebernahme.get("beleg") or {}
    merkmale = uebernahme.get("merkmale")

    def befund(police: Any, art: str, text: str, **rest: Any) -> None:
        befunde.append({"police_id": None if police is None else str(police),
                        "art": art, "text": text, **rest})

    # 1. Beleg und Tarifregeln ---------------------------------------------
    modus = beleg.get("anfangszustand")
    if modus == GRUNDVERTRAG:
        befund(None, "nicht_freigeschaltet",
               f"Uebernahme fuehrt {len(beleg.get('nicht_freigeschaltet') or [])} "
               "Vertraege mit Erhoehungen/Herabsetzungen als Grundvertrag "
               f"(--anfangszustand {GRUNDVERTRAG}) — nicht freigeschaltet",
               policen=list(beleg.get("nicht_freigeschaltet") or []))
    elif modus not in (MATERIALISIEREN, "ohne_bausteine"):
        befund(None, "beleg", f"Uebernahmebeleg ohne gueltigen Modus: {modus!r}")

    generationen = sorted(set(str(g) for g in stamm["tarif_generation"]))
    if len(generationen) != 1:
        befund(None, "generation",
               f"uebernommener Bestand traegt {len(generationen)} Generationen "
               f"{generationen} — eine Uebernahme ist eine Generation")
    gen = next((g for g in config.generationen if g.name in generationen), None)
    if gen is None:
        befund(None, "config",
               f"Generation {generationen} nicht in der Config "
               f"(bekannt: {[g.name for g in config.generationen]})")
        tw_config: Dict[str, Any] = {}
    else:
        tw_config = gen.tarifwerk()
    # Ein Beleg ohne vollstaendiges Tarifwerk (vor dem Merkmal tku_umfang
    # oder vor ADR-024, Nachtrag) wird nicht ergaenzt: Er weicht ab und ist
    # ein Befund — der Bestand wird auf dem neuen Stand neu uebernommen.
    tw_beleg = dict(beleg.get("tarifwerk") or {})
    for name, quelle, werte in (("config", "Config der Generation", tw_config),
                                ("beleg", "Uebernahmebeleg", tw_beleg)):
        if werte != tarifwerk:
            befund(None, "tarifwerk",
                   f"Tarifwerk der {quelle} {werte} weicht vom belegten der "
                   f"Spez {tarifwerk} ab — die Pruefstrecke hat mit anderen "
                   "Regeln abgenommen als die Fuehrung rechnet")
    qv_beleg = beleg.get("quellverfahren")
    if qv_beleg is not None and qv_beleg != dict(quellverfahren):
        befund(None, "quellverfahren",
               f"Quellverfahren des Uebernahmebelegs {qv_beleg} weicht vom "
               f"belegten der Spez {dict(quellverfahren)} ab — die Uebernahme "
               "hat die Lieferung anders gelesen als die Pruefstrecke")

    # Der Stichtag ist eine Eigenschaft des Bestands, keine Angabe des
    # Aufrufs (Pruefrunde T27, Befund 06): Jeder uebernommene Vertrag kam
    # am Migrationsstichtag in die Buecher. Ein Aufruf mit einem anderen
    # Stichtag prueft eine andere Uebernahme.
    zugaenge = sorted({pd.Timestamp(z).date().isoformat()
                       for z in stamm["bestandszugang"].dropna()})
    if zugaenge != [stichtag.isoformat()]:
        befund(None, "stichtag",
               f"Stichtag {stichtag.isoformat()} ist nicht der Bestandszugang "
               f"des uebernommenen Bestands {zugaenge}")

    # 2. Anfangszustand je Vertrag -----------------------------------------
    auspraegungen = auspraegungen_je_police(spez, zeilen) if zeilen else {}
    if vorgeschichte:
        zustaende, warnungen = anfangszustaende_je_police(
            spez, zeilen, vorgeschichte, stamm, spalten=dict(VORGABE),
            # Die Vorgeschichte liest die Probe wie die Pruefstrecke: in der
            # Lesart der QUELLE, nicht nach dem Tarifwerk der Fuehrung.
            red_verfahren=str(quellverfahren["red_verfahren"]), red_anteile=red_anteile,
            auspraegungen=auspraegungen, erhoehungssatz=erhoehungssatz,
            anker=anker, red_anteile_je_datum=red_anteile_je_datum,
            red_anteil_kandidaten=red_anteil_kandidaten,
            scheiben_mit_gamma1=bool(tarifwerk["scheiben_mit_gamma1"]),
            tku_umfang=str(tarifwerk["tku_umfang"]),
            stoab_je_baustein=bool(tarifwerk["stoab_je_baustein"]))
    else:
        zustaende, warnungen = {}, []
    ohne_zustand = set()
    for w in warnungen:
        teile = w.split()
        if len(teile) >= 2 and teile[0] == "Police":
            ohne_zustand.add(teile[1].strip(":(),"))
    ausgewiesen = {str(e.get("police_id")) for e in beleg.get("ohne_anfangszustand") or []}
    if modus == MATERIALISIEREN and ohne_zustand != ausgewiesen:
        befund(None, "ausnahmen",
               "Vertraege ohne ableitbaren Anfangszustand: Pruefstrecke "
               f"{sorted(ohne_zustand)} vs. Uebernahmebeleg {sorted(ausgewiesen)}")
    # Pruefer-Befund B1: Nicht die Gleichheit der Listen ist die Aussage,
    # sondern dass sie LEER sind — ein Vertrag ohne ableitbaren
    # Anfangszustand ist nicht freigeschaltet, auch wenn Uebernahme und
    # Probe ihn uebereinstimmend so nennen.
    if modus == MATERIALISIEREN and (ohne_zustand or ausgewiesen):
        befund(None, "ausnahmen",
               "Vertraege ohne ableitbaren Anfangszustand "
               f"{sorted(ohne_zustand | ausgewiesen)[:5]} — nicht still als "
               "Grundvertrag fuehrbar; Ausweg: Anteile je Ereignis als registrierte "
               "Auskunft (--red-anteile-datei) nennen")
    # Und die gedeckten Policen sind dieselben wie in der Uebernahme
    # (Pflichtschicht, A-M4 haelt sie gegen die Abnahmen).
    gedeckt_probe = sorted(p for p, z in zustaende.items() if z.get("gedeckt_durch"))
    gedeckt_beleg = sorted(str(p) for p in (beleg.get("gedeckt") or {}))
    if modus == MATERIALISIEREN and gedeckt_probe != gedeckt_beleg:
        befund(None, "ausnahmen",
               f"durch die Auskunft gedeckte Anfangszustaende: Pruefstrecke "
               f"{gedeckt_probe[:5]} vs. Uebernahmebeleg {gedeckt_beleg[:5]}")

    geliefert = {str(z["police_id"]): float(z["sum_insured"]) for z in zeilen}
    haupt = stamm.set_index("police_id")
    # Eindeutigkeit im Ledger der Uebernahme (Runde F, Nachbesserung): Eine
    # verdoppelte Zugangs- oder Umbuchungszeile war eine Reihe mit zwei
    # Eintraegen, die der Vergleich nicht in eine Zahl wandeln konnte. Der
    # Vergleich laeuft gegen die erste Zeile; die Wiederholung ist ein Befund.
    # Die Paarregel sieht diesen Ledger nicht an: keine Art ist ausgenommen.
    ueb_doppelt = doppelte_buchungen(ledger, ohne_arten=())
    for art_d in sorted(set(ledger["ereignis"].to_numpy()[ueb_doppelt])):
        policen_d = sorted(set(int(p) for p in ledger["police_id"].to_numpy()[
            ueb_doppelt & (ledger["ereignis"].to_numpy() == art_d)]))
        befund(None, "doppelte_buchung", doppelte_buchung_text(art_d, policen_d),
               ereignis=art_d, policen=policen_d)
    ledger_eindeutig = ledger[~ueb_doppelt]
    ledger_zug = ledger_eindeutig[ledger_eindeutig["ereignis"] == "ZUG"].set_index(
        "police_id")["betrag"]
    ledger_pex = ledger_eindeutig[ledger_eindeutig["ereignis"] == "PEX"].set_index(
        "police_id")["betrag"]
    pex_historie: Dict[int, pd.Timestamp] = {}
    if len(historie):
        for pid, datum in historie[historie["status_code"] == "PEX"][
                ["police_id", "status_date"]].itertuples(index=False):
            pex_historie[int(pid)] = min(pd.Timestamp(datum), pex_historie.get(int(pid), pd.Timestamp(datum)))
    scheiben_je_police: Dict[int, List[Dict[str, Any]]] = {}
    if scheiben is not None and len(scheiben):
        for s in scheiben.to_dict("records"):
            scheiben_je_police.setdefault(int(s["police_id"]), []).append(s)

    from rechner_pipeline.bestand.auswertung import grundlagen_je_police
    grundlagen = grundlagen_je_police(config, merkmale)

    welten: Dict[int, Dict[str, Any]] = {}
    zahlen = {"vertraege": int(len(stamm)), "mit_anfangszustand": 0,
              "scheiben": 0, "beitragsfrei": 0}
    for row in stamm.to_dict("records"):
        pid = int(row["police_id"]); police = str(pid)
        zelle_felder = dict(_zelle(spez, auspraegungen.get(police, {})).model_point)
        # Rechnungsgrundlagen der Fuehrung = die der Spez-Zelle.
        try:
            felder_config = grundlagen(pid, str(row["tarif_generation"]))
        except ValueError as exc:
            befund(pid, "grundlagen", str(exc)); continue
        abweichend = sorted(
            f for f in GENERATION_FIELDS
            if f in zelle_felder and felder_config.get(f) != zelle_felder[f])
        if abweichend:
            befund(pid, "grundlagen",
                   f"Rechnungsgrundlagen der Config weichen von der Spez-Zelle "
                   f"ab: {abweichend}")
        z = zustaende.get(police, {})
        if z:
            zahlen["mit_anfangszustand"] += 1
        if z.get("reduktion") is not None:
            befund(pid, "nicht_freigeschaltet",
                   "Herabsetzungs-Zustand der Pruefstrecke — die Fuehrung traegt "
                   "keinen geteilten Vertrag")
        erwartete_summe = float(z["sum_insured"]) if "sum_insured" in z else geliefert.get(police)
        if erwartete_summe is None:
            befund(pid, "zeilen", "keine transformierte Zeile — Summe nicht pruefbar")
            erwartete_summe = float(row["sum_insured"])
        if weicht_ab(row["sum_insured"], erwartete_summe, TOLERANZ):
            befund(pid, "stammsumme",
                   f"Stammsumme {float(row['sum_insured']):.2f} statt "
                   f"{erwartete_summe:.2f} (Grund-/Ursprungssumme der Pruefstrecke)")
        kw = model_point_kwargs(row, zelle_felder)
        kw["sum_insured"] = erwartete_summe
        grund_mp = ModelPoint(**kw)
        # Bausteine
        erwartet_scheiben = sorted((int(j), float(s)) for j, s in z.get("scheiben", ()))
        vorhanden = sorted(
            (int(s["erhoehung_jahr"]), float(s["sum_insured"]))
            for s in scheiben_je_police.get(pid, []))
        if len(erwartet_scheiben) != len(vorhanden) or any(
                a[0] != b[0] or weicht_ab(a[1], b[1], TOLERANZ)
                for a, b in zip(erwartet_scheiben, vorhanden)):
            befund(pid, "scheiben",
                   f"Bausteine der Fuehrung {vorhanden} statt "
                   f"{erwartet_scheiben} (Alt-Erhoehungen der Pruefstrecke)")
        gamma1_soll = float(zelle_felder["gamma1"]) if tarifwerk["scheiben_mit_gamma1"] else 0.0
        for s in scheiben_je_police.get(pid, []):
            if float(s["gamma1"]) != gamma1_soll:
                befund(pid, "scheiben",
                       f"Scheibe {int(s['scheiben_id'])} traegt gamma1 "
                       f"{float(s['gamma1'])!r} statt {gamma1_soll!r}")
        zahlen["scheiben"] += len(erwartet_scheiben)
        teile = [(j, Rechenkern(erhoehungs_scheibe(
            grund_mp, j, s, gamma1_uebernehmen=bool(tarifwerk["scheiben_mit_gamma1"]))))
            for j, s in erwartet_scheiben]
        grund = Rechenkern(grund_mp)
        # Beitragsfreistellung
        pex_jahr = z.get("beitragsfrei_seit_jahr")
        beginn = pd.Timestamp(row["insurance_start"])
        if pex_jahr is None and pid in pex_historie and police not in ohne_zustand:
            # Eine Beitragsfreistellung in der Historie, die die Pruefstrecke
            # aus der Vorgeschichte DIESES Laufs nicht kennt: Uebernahme und
            # Probe haben verschiedene Lieferungen gesehen — Befund, kein
            # stiller Rueckgriff auf die Tabelle, die geprueft werden soll.
            befund(pid, "beitragsfrei",
                   "PEX in der Historie der Uebernahme, aber keine "
                   "Beitragsfreistellung im Anfangszustand der Pruefstrecke "
                   "(Vorgeschichte dieses Laufs)")
        if pex_jahr is not None:
            zahlen["beitragsfrei"] += 1
            if pid not in pex_historie:
                befund(pid, "beitragsfrei", "beitragsfrei nach Pruefstrecke, aber "
                       "ohne PEX-Zeile in der Historie")
            elif _jahre(beginn, pex_historie[pid]) != int(pex_jahr):
                befund(pid, "beitragsfrei",
                       f"PEX-Jahr {_jahre(beginn, pex_historie[pid])} in der "
                       f"Historie, {int(pex_jahr)} in der Pruefstrecke")
            if pid not in ledger_pex.index:
                befund(pid, "umbuchung", "keine PEX-Umbuchung im Uebernahme-Ledger")
            # Der BETRAG wird erst nach Abschnitt 3 geprueft: Er traegt
            # die Korrekturschicht, und die steht hier noch nicht.
        gesamt = grund_mp.sum_insured + sum(k.mp.sum_insured for _, k in teile)
        if pid not in ledger_zug.index:
            befund(pid, "zugang", "keine Zugangsbuchung im Uebernahme-Ledger")
        elif weicht_ab(ledger_zug.loc[pid], gesamt, TOLERANZ):
            befund(pid, "zugang",
                   f"Zugang {float(ledger_zug.loc[pid]):.2f} statt {gesamt:.2f} "
                   "(Gesamtsumme der Bausteine)")
        welten[pid] = {"grund": grund, "grund_mp": grund_mp, "teile": teile,
                       "pex_jahr": pex_jahr, "gesamt": gesamt, "beginn": beginn}

    # 3. Schicht ------------------------------------------------------------
    schicht_je_police: Dict[int, Tuple[Schichtparameter, int]] = {}
    if schichtbeleg:
        if verankerung is None or len(verankerung) == 0:
            befund(None, "schicht", "Schichtbeleg ohne verankerung.parquet")
        else:
            anker_ta = verankerung.set_index("police_id")["monate_ta"]
            for police, eintrag in schichtbeleg.items():
                pid = int(police)
                if "conv" in eintrag:
                    befund(pid, "nicht_freigeschaltet",
                           "Zweitschicht R_conv ist in der Fuehrung nicht freigeschaltet")
                if pid not in anker_ta.index:
                    befund(pid, "schicht", "Schicht ohne Verankerungszeitpunkt")
                    continue
                schicht_je_police[pid] = (
                    Schichtparameter(**{
                        **eintrag["hist"],
                        "vererbend": tuple(tuple(p) for p in eintrag["hist"]["vererbend"]),
                    }),
                    int(anker_ta.loc[pid]),
                )
    # Die Tabelle wird IMMER angesehen, nicht nur wenn ein Beleg vorliegt
    # (Review T25-03): ``if schichtbeleg:`` machte die ganze Schichtpruefung
    # optional — eine schichten.parquet ohne Beleg lief ungeprueft durch die
    # Fuehrung, und niemand sagte es.
    tabelle = uebernahme.get("schichten")
    if tabelle is not None and len(tabelle) and not schichtbeleg:
        befund(None, "schicht",
               f"schichten.parquet fuehrt {len(tabelle)} Schichten, aber es gibt "
               "keinen Schichtbeleg — die Fuehrung rechnet mit einer Korrektur, "
               "die keine Abnahme bezeugt")
    if schichtbeleg:
        if tabelle is None or len(tabelle) == 0:
            befund(None, "schicht",
                   "Schichtbeleg vorhanden, aber schichten.parquet fehlt im "
                   "Uebernahme-Verzeichnis — die Fuehrung kennt die Schicht nicht")
        else:
            in_tabelle = {int(p) for p in tabelle["police_id"]}
            fehlend = sorted(set(schicht_je_police) - in_tabelle)
            if fehlend:
                befund(None, "schicht",
                       f"{len(fehlend)} Schichten des Belegs fehlen in "
                       f"schichten.parquet (z. B. {fehlend[:5]})")
            # Die GEGENRICHTUNG: Zeilen der Tabelle, die kein Beleg deckt.
            # Sie wurde nie gebildet — eine Schicht, die die Fuehrung rechnet
            # und keine Abnahme kennt, war unsichtbar (Review T25-03).
            unbelegt = sorted(in_tabelle - set(schicht_je_police))
            if unbelegt:
                befund(None, "schicht",
                       f"{len(unbelegt)} Schichten in schichten.parquet ohne Eintrag "
                       f"im Schichtbeleg (z. B. {unbelegt[:5]}) — die Fuehrung rechnet "
                       "eine Korrektur, die die Pruefstrecke nicht kennt")
            # Und JEDES Feld, nicht nur rho: Ein Vergleich, der eine Spalte
            # prueft und elf uebergeht, bezeugt die elf nicht.
            _schicht_gegen_beleg(befund, tabelle, schicht_je_police,
                                 "schichten.parquet")

    # 3b. Die Umbuchung der Uebernahme, MIT Korrekturschicht ----------------
    # Sie stand vorher in Abschnitt 2 und rechnete die beitragsfreie Summe
    # ohne Zuschlag — dieselbe Luecke, die die Uebernahme selbst hatte
    # (Entscheid des Maintainers 2026-09-20): Die beitragsfreie Summe ist
    # eine garantierte Leistung und traegt den absorbierten Schichtwert.
    # Gerechnet wird durch dieselbe Tuer wie unten in Abschnitt 4
    # (``zuschlag_bei_pex``); zwei Rechenwege waren der Befund T25-06.
    for pid, welt in welten.items():
        pex_jahr = welt["pex_jahr"]
        if pex_jahr is None or pid not in ledger_pex.index:
            continue
        grund, teile = welt["grund"], welt["teile"]
        vs_bfr = (
            grund.beitragsfreie_summe(int(pex_jahr))
            + sum(k.beitragsfreie_summe(int(pex_jahr) - j) for j, k in teile)
            + zuschlag_bei_pex(schicht_je_police.get(pid), grund, int(pex_jahr))
        )
        if weicht_ab(ledger_pex.loc[pid], vs_bfr, TOLERANZ):
            befund(pid, "umbuchung",
                   f"Umbuchung {float(ledger_pex.loc[pid]):.2f} statt "
                   f"{vs_bfr:.2f} (beitragsfreie Summe der Pruefstrecke "
                   "einschliesslich Korrekturschicht)")

    # 4. Buchungen der Fortschreibung nach dem Stichtag ---------------------
    buchungen: Dict[str, int] = {art: 0 for art in GEPRUEFTE_BUCHUNGEN}
    abweichungen = 0
    endbestand_geprueft = 0
    if fortschreibung is not None:
        # Der Endbestand wird jetzt angesehen (Review T25-02). Geprueft wird,
        # was die Fortschreibung NICHT darf: einen uebernommenen Vertrag
        # verlieren oder seine Identitaet aendern. Die Zustandsspalten sind
        # ausgenommen — sie zu bewegen IST die Fortschreibung.
        f_bestand = fortschreibung.get("bestand")
        if f_bestand is not None:
            # Benannt wird, was sich BEWEGEN darf — nicht, was geprueft
            # wird (Befund T26-05). Vorher stand hier eine handverlesene
            # Auswahl von sechs Feldern, und ``sum_insured`` war nicht
            # darin: Eine von 43.000 auf 1.042.999 EUR erhoehte Stammsumme
            # lief durch die echte Probe und durch ihren Consumer, gruen,
            # mit positivem Zaehler. Der Zaehler sagte nur, dass eine
            # Zeile auf sechs Attribute angesehen wurde.
            #
            # Gemessen am gefahrenen Fall (500 Policen) aendert die
            # Fortschreibung GENAU DREI Spalten. Alles andere ist
            # Identitaet — Erhoehungen leben in den Scheiben, die
            # Herabsetzung im Ledger, die beitragsfreie Summe in ihrer
            # eigenen Spalte. Eine neue Stammspalte ist damit von Anfang
            # an geprueft, statt stillschweigend ungeprueft zu bleiben.
            identitaet = [feld for feld in STAMM_NAMES
                          if feld not in ZUSTANDSSPALTEN
                          and feld != "police_id"
                          and feld in f_bestand.columns]
            ende = f_bestand.set_index("police_id")
            for row in stamm.to_dict("records"):
                pid = int(row["police_id"])
                if pid not in ende.index:
                    befund(pid, "endbestand",
                           "im Endbestand der Fortschreibung nicht mehr vorhanden — "
                           "ein uebernommener Vertrag verschwindet nicht")
                    continue
                zeile = ende.loc[pid]
                for feld in identitaet:
                    if pd.isna(row.get(feld)) and pd.isna(zeile[feld]):
                        continue
                    if row[feld] != zeile[feld]:
                        befund(pid, "endbestand",
                               f"{feld} im Endbestand {zeile[feld]!r}, uebernommen "
                               f"wurde {row[feld]!r} — die Fortschreibung bewegt "
                               "Zustaende, nicht Identitaeten", feld=feld)
                endbestand_geprueft += 1
        else:
            befund(None, "endbestand",
                   "Fortschreibung ohne Endbestand — ein Endzustand, den niemand "
                   "vorlegt, ist nicht geprueft")
        f_historie = fortschreibung.get("historie")
        if f_historie is not None and len(f_historie):
            fremd = sorted({str(s) for s in f_historie["status_code"]} - set(STATUS_CODE_VALUES))
            if fremd:
                befund(None, "endhistorie",
                       f"Endhistorie der Fortschreibung: unbekannte Zustaende {fremd} — "
                       f"bekannt sind {sorted(STATUS_CODE_VALUES)}")
        f_ledger: pd.DataFrame = fortschreibung["ledger"].reset_index(drop=True)
        _pruefe_endzustand(
            befund, stamm=stamm, historie=historie, scheiben=scheiben,
            f_bestand=f_bestand, f_historie=f_historie, f_ledger=f_ledger,
            f_scheiben=fortschreibung.get("scheiben"), stichtag=stichtag,
            u_ledger=ledger)
        # Die Nebentabellen, die die Fortschreibung mitfuehrt (RC04): Wer
        # sie nicht in der Fortschreibung modelliert, laesst den Schluessel
        # weg (Werkzeug-Aufrufer); ``fuehre_probe`` setzt ihn immer.
        for rolle, (art_n, schluessel_n) in NEBENTABELLEN_IDENTITAET.items():
            if rolle not in fortschreibung:
                continue
            _nebentabelle_gleich(befund, rolle, art_n, schluessel_n,
                                 uebernahme.get(rolle), fortschreibung[rolle])
        if "schichten" in fortschreibung and schichtbeleg:
            f_tab = fortschreibung["schichten"]
            if f_tab is not None and len(f_tab):
                _schicht_gegen_beleg(befund, f_tab, schicht_je_police,
                                     "schichten.parquet der Fortschreibung")
        f_scheiben = fortschreibung.get("scheiben")
        neue_je_police: Dict[int, List[Dict[str, Any]]] = {}
        if f_scheiben is not None and len(f_scheiben):
            for s in f_scheiben.to_dict("records"):
                if pd.Timestamp(s["erhoehung_datum"]) > pd.Timestamp(stichtag):
                    neue_je_police.setdefault(int(s["police_id"]), []).append(s)
        nach = f_ledger[
            f_ledger["police_id"].isin(set(int(p) for p in stamm["police_id"]))
            & (pd.to_datetime(f_ledger["status_date"]) > pd.Timestamp(stichtag))
            & f_ledger["ereignis"].isin(GEPRUEFTE_BUCHUNGEN)
        ]
        # Policen mit Herabsetzungen und Teilkuendigungen: Ihre Folgebuchungen
        # rechnen auf der VORGANGSFOLGE (beliebig viele je Vertrag, Entscheid
        # des Maintainers 2026-10-01). Anteil und Verfahren stehen in
        # reduktionen.parquet — ohne die Tabelle kann die Probe diese Buchungen
        # NICHT nachrechnen, und sie gegen den ungekuerzten Vertrag zu halten
        # waere schlechter als gar nichts: Das Urteil bezeugte eine
        # Uebereinstimmung, die es nicht gibt.
        f_reduktionen = fortschreibung.get("reduktionen")
        vorgaenge_je_police: Dict[int, List[Tuple[int, float, str, pd.Timestamp]]] = {}
        if f_reduktionen is not None and len(f_reduktionen):
            for z in f_reduktionen.to_dict("records"):
                vorgaenge_je_police.setdefault(int(z["police_id"]), []).append((
                    int(z["reduktion_jahr"]), float(z["anteil"]), str(z["verfahren"]),
                    pd.Timestamp(z["reduktion_datum"])))
        # Verfahren und Anteil gegen das System, dieselbe Regel wie P-B1
        # (Angriffsrunde nach T27: eine als prospektiv eingetragene
        # Teilkuendigung und ein falscher Anteil bestanden die Probe).
        for pid, vorgaenge in sorted(vorgaenge_je_police.items()):
            if pid in welten:
                for r_j, anteil, verfahren, _tag in vorgaenge:
                    # Vorgang, Verfahren und Anteil: dieselbe Regel wie P-B1.
                    for text in red_bindung_fehler(
                            pid, r_j, anteil, verfahren,
                            beitragsdauer=int(haupt.loc[pid, "premium_duration"]),
                            generation_verfahren=tarifwerk.get("red_verfahren"),
                            annahmen=config.annahmen):
                        befund(pid, "herabsetzung", text)
        red_jahr: Dict[int, set] = {}
        for z in f_ledger[f_ledger["ereignis"].isin(REDUKTION_EREIGNISSE)].to_dict("records"):
            red_jahr.setdefault(int(z["police_id"]), set()).add(int(z["vertragsjahr"]))
        ohne_tabelle = sorted(set(red_jahr) - set(vorgaenge_je_police))
        if ohne_tabelle:
            befund(None, "herabsetzung",
                   f"{len(ohne_tabelle)} Police(n) mit RED- oder TKU-Buchung, aber ohne "
                   f"Zeile in reduktionen.parquet (z. B. {ohne_tabelle[:5]}) — "
                   "die Probe kann ihre Folgebuchungen nicht nachrechnen")
        # Jeder Vorgang liegt IM Lauf (RC02); eine BEITRAGSHERABSETZUNG liegt auf
        # einem beitragspflichtigen Vertrag (RC03; klv.md 7.1). Davor, dahinter
        # oder (Herabsetzung) nach der Beitragsfreistellung ist er keine Buchung
        # dieses Laufs: Die Engine simuliert einen uebernommenen Vertrag erst ab
        # seinem Zugangsjahr, nie ueber den Horizont und zieht fuer
        # beitragsfreie Vertraege keine Herabsetzung. Ein Soll wird fuer die
        # Police NICHT hergeleitet (es waere das eines Vertrags, den es nicht
        # gibt) — der Widerspruch ist der Befund. Die Teilkuendigung nach der
        # Beitragsfreistellung ist dagegen ein Vorgang (klv.md 7.2, B3).
        horizont = fortschreibung.get("horizont")
        ausgeschlossen: set = set()
        pex_je_police: Dict[int, Optional[int]] = {}
        for pid, welt in welten.items():
            pex_beitragsfrei = welt["pex_jahr"]
            if pex_beitragsfrei is None:
                eigene_pex = f_ledger[(f_ledger["police_id"] == pid)
                                      & (f_ledger["ereignis"] == "PEX")]
                if len(eigene_pex):
                    pex_beitragsfrei = int(eigene_pex["vertragsjahr"].min())
            pex_je_police[pid] = (None if pex_beitragsfrei is None
                                  else int(pex_beitragsfrei))
        for pid, vorgaenge in sorted(vorgaenge_je_police.items()):
            welt = welten.get(pid)
            if welt is None:
                continue
            for r_jahr, _anteil, r_verfahren, datum in vorgaenge:
                name = "Teilkuendigung" if r_verfahren == TEILKUENDIGUNG else "Herabsetzung"
                zugang = pd.Timestamp(haupt.loc[pid, "bestandszugang"])
                if datum <= zugang:
                    ausgeschlossen.add(pid)
                    befund(pid, "herabsetzung",
                           f"{name} am {datum.date()} liegt nicht nach dem Bestandszugang "
                           f"{zugang.date()} — Vorgeschichte der abgebenden Gesellschaft, "
                           "keine Buchung dieses Laufs")
                if horizont is not None and datum > pd.Timestamp(horizont):
                    ausgeschlossen.add(pid)
                    befund(pid, "herabsetzung",
                           f"{name} am {datum.date()} liegt nach dem belegten Horizont "
                           f"{pd.Timestamp(horizont).date()} — der Lauf hat sie nicht gefahren")
                pex_beitragsfrei = pex_je_police.get(pid)
                if (r_verfahren != TEILKUENDIGUNG and pex_beitragsfrei is not None
                        and pex_beitragsfrei <= r_jahr):
                    ausgeschlossen.add(pid)
                    befund(pid, "herabsetzung",
                           f"Beitragsherabsetzung im Jahr {r_jahr} auf einem beitragsfrei "
                           f"gestellten Vertrag (Beitragsfreistellung im Jahr "
                           f"{pex_beitragsfrei}) — ein beitragsfreier Vertrag hat keinen "
                           "Beitrag, den eine Herabsetzung senken koennte (Ausweg: die "
                           "Teilkuendigung); ein Soll wird nicht hergeleitet")
        # Das Buchungsfenster gilt fuer JEDE Ereignisart (Runde E, Klasse
        # geschlossen): Die Zeilen der uebernommenen Vertraege liegen echt
        # nach dem Bestandszugang (ausser den benannten Zugangsbuchungen) und
        # nicht hinter dem belegten Horizont — dieselbe Regel wie in
        # validate_ledger. Eine Zeile ausserhalb ist keine Buchung dieses
        # Laufs: Sie wird nicht nachgerechnet und nicht als geprueft gezaehlt.
        uebernommen_ids = set(int(p) for p in stamm["police_id"])
        im_lauf = f_ledger[f_ledger["police_id"].isin(uebernommen_ids)]
        vor_zugang, hinter = buchungsfenster_verstoesse(im_lauf, stamm, horizont)
        ausserhalb_idx = set()
        for pos in range(len(im_lauf)):
            if not (vor_zugang[pos] or hinter[pos]):
                continue
            z = im_lauf.iloc[pos]
            pid, art_z = int(z["police_id"]), str(z["ereignis"])
            datum_z = pd.Timestamp(z["status_date"])
            ausserhalb_idx.add(im_lauf.index[pos])
            if hinter[pos]:
                ort = (f"nach dem belegten Horizont {pd.Timestamp(horizont).date()} "
                       f"(am {datum_z.date()})")
                grund = "der Lauf hat sie nicht gefahren"
            else:
                ort = f"nicht nach dem Bestandszugang (am {datum_z.date()})"
                grund = ("Vorgeschichte der abgebenden Gesellschaft, keine Buchung "
                         "dieses Laufs")
            if art_z in REDUKTION_EREIGNISSE:
                ausgeschlossen.add(pid)
            befund(pid, "herabsetzung" if art_z in REDUKTION_EREIGNISSE else "buchungsfenster",
                   f"{art_z}-Buchung {ort} — {grund}")
        # Die Ausnahme-Ereignisse (ZUG, MIG, ABL) stehen an ihrem Zeitpunkt
        # (Runde E, Nachbesserung): dieselbe Regel wie in validate_ledger;
        # Zeilen, die das Fenster schon beanstandet, scheiden aus. Eine Zeile
        # am falschen Platz ist keine Buchung dieses Laufs — sie wird nicht
        # nachgerechnet und nicht als geprueft gezaehlt.
        gemeldet = vor_zugang | hinter
        for regel, maske in ausnahme_ereignis_verstoesse(
                im_lauf, stamm, vor_zugang | hinter).items():
            gemeldet = gemeldet | maske
            for pos in range(len(im_lauf)):
                if not maske[pos]:
                    continue
                z = im_lauf.iloc[pos]
                ausserhalb_idx.add(im_lauf.index[pos])
                befund(int(z["police_id"]), "ausnahme_ereignis",
                       ausnahme_ereignis_text(regel, str(z["ereignis"]), [int(z["police_id"])]))
        # Die Eindeutigkeit (Runde F, Nachbesserung, Klasse): je (Police,
        # Ereignis, Wirkungstag, Betragsart) genau eine Zeile, fuer JEDE Art —
        # dieselbe Regel wie in validate_ledger; die Verdopplung der
        # Beitragsereignisse meldet die Paarregel oben. Die ueberzaehlige Zeile
        # wird nicht nachgerechnet und nicht als geprueft gezaehlt (die erste
        # bleibt die Buchung); die Herabsetzung sieht sie ebenfalls nicht mehr
        # (``doppelt_idx``) — ein Fehler, ein Befund.
        ueberzaehlig = doppelte_buchungen(im_lauf, gemeldet)
        doppelt_idx = set(im_lauf.index[ueberzaehlig])
        for art_d in sorted(set(im_lauf["ereignis"].to_numpy()[ueberzaehlig])):
            policen_d = sorted(set(int(p) for p in im_lauf["police_id"].to_numpy()[
                ueberzaehlig & (im_lauf["ereignis"].to_numpy() == art_d)]))
            befund(None, "doppelte_buchung", doppelte_buchung_text(art_d, policen_d),
                   ereignis=art_d, policen=policen_d)
        ausserhalb_idx |= doppelt_idx
        gemeldet = gemeldet | ueberzaehlig
        # Der Wirkungstag ist der Jahrestag des Vertragsjahres (Runde F, Regel
        # aus validate_reduktionen): Tabelle und Ledger gleich verschoben, und
        # die Probe sah keinen Unterschied. Die RED-Zeilen bindet die Tabelle
        # (unten); jede andere Zeile steht selbst am Jahrestag. Die Maske steht
        # VOR der Paarregel (Nachbesserung): Eine Zeile am falschen Tag meldet
        # der Wirkungstag-Befund unten, die Paarregel nimmt den ganzen Vorfall aus.
        falscher_tag = jahrestag_verstoesse(im_lauf, stamm) & ~gemeldet \
            & ~im_lauf["ereignis"].isin(REDUKTION_EREIGNISSE).to_numpy()
        # Die Paarbuchung (Runde F, Klasse): je Vorfall mit Beitragswirkung
        # genau eine Summenzeile und eine Beitragszeile — dieselbe Regel wie in
        # validate_ledger. Eine Zeile, die eine Regel oben beanstandet, nimmt
        # ihren GANZEN Vorfall aus (Nachbesserung): die Partnerzeile bringt keinen
        # zusaetzlichen Befund, ein Vorfall ist ein Fehler.
        for (art_p, verstoss), policen_p in sorted(
                beitragspaar_verstoesse(im_lauf, stamm, gemeldet | falscher_tag).items()):
            befund(None, "beitragspaar", beitragspaar_text(art_p, verstoss, policen_p),
                   ereignis=art_p, verstoss=verstoss, policen=policen_p)
        # Ein Betrag ist eine endliche Zahl (Runde F): ``abs(betrag - erwartet) >
        # TOLERANZ`` ist bei NaN immer falsch, und ein NaN-Betrag galt als
        # geprueft und uebereinstimmend. Fuer JEDE Ereignisart, nicht nur die
        # nachgerechneten; P-B1 meldet dasselbe als 'fehlende Werte (NaN) in
        # betrag'. Die Zeile wird nicht nachgerechnet und nicht gezaehlt.
        betraege = pd.to_numeric(im_lauf["betrag"], errors="coerce").to_numpy(dtype="float64")
        for pos in np.flatnonzero(~np.isfinite(betraege)):
            z = im_lauf.iloc[int(pos)]
            ausserhalb_idx.add(im_lauf.index[int(pos)])
            befund(int(z["police_id"]), "betrag_nicht_endlich",
                   f"{z['ereignis']}-Buchung {z['betrag_art']} am "
                   f"{pd.Timestamp(z['status_date']).date()}: Betrag {z['betrag']!r} ist "
                   "keine endliche Zahl — ein Buchungsbetrag ist endlich; die Zeile wird "
                   "nicht nachgerechnet und nicht als geprueft gezaehlt")
        # Der Wirkungstag (Maske oben): eine Zeile am falschen Tag wird nicht
        # nachgerechnet und nicht als geprueft gezaehlt.
        for pos in np.flatnonzero(falscher_tag):
            z = im_lauf.iloc[int(pos)]
            jahrestag = reduktion_jahrestag(
                haupt.loc[int(z["police_id"]), "insurance_start"], z["vertragsjahr"])
            ausserhalb_idx.add(im_lauf.index[int(pos)])
            befund(int(z["police_id"]), "wirkungstag",
                   f"{z['ereignis']}-Buchung am {pd.Timestamp(z['status_date']).date()} "
                   f"steht nicht am Jahrestag {jahrestag.date()} ihres Vertragsjahres "
                   f"{int(z['vertragsjahr'])} — die Engine bucht zum Jahreswechsel; die "
                   "Zeile wird nicht nachgerechnet und nicht als geprueft gezaehlt")
        for pid, vorgaenge in sorted(vorgaenge_je_police.items()):
            if pid not in haupt.index:
                continue
            for r_jahr, _anteil, r_verfahren, tag in vorgaenge:
                jahrestag = reduktion_jahrestag(haupt.loc[pid, "insurance_start"], r_jahr)
                if tag != jahrestag:
                    befund(pid, "herabsetzung",
                           f"{'Teilkuendigung' if r_verfahren == TEILKUENDIGUNG else 'Herabsetzung'}: "
                           f"Wirkungstag {tag.date()} ist nicht der Jahrestag "
                           f"{jahrestag.date()} des Reduktionsjahres {r_jahr} — Tabelle und "
                           "Ledger duerfen ihn nicht frei setzen")
        # Die Rate: Jede Buchung nach dem Zugang folgt aus einer Annahme der
        # Config, die sie erzeugen kann (Runde E, Klasse geschlossen).
        for feld, eintraege in sorted(unbelegte_ereignisse(
                stamm, im_lauf, config.annahmen).items()):
            befund(None, "ratebindung", unbelegte_ereignisse_text(feld, eintraege),
                   feld=feld)
        # Und die Art gehoert dem Produkt ueberhaupt zu (Nachbesserung Runde E):
        # weder Ziel einer Annahme noch Ausnahme ist kein stilles "keine Rate".
        for text in unzugeordnete_ereignisse(stamm, im_lauf):
            befund(None, "zuordnung", text)
        nach = nach.drop(index=list(ausserhalb_idx & set(nach.index)))

        def teile_bei(pid: int, welt: Dict[str, Any], jahr: int):
            teile = list(welt["teile"])
            for s in neue_je_police.get(pid, []):
                if int(s["erhoehung_jahr"]) < jahr:
                    row = {"entry_age": s["entry_age"], "sex": haupt.loc[pid, "sex"],
                           "duration": s["duration"], "premium_duration": s["premium_duration"],
                           "sum_insured": s["sum_insured"], "zahlweise": haupt.loc[pid, "zahlweise"]}
                    kw = model_point_kwargs(row, dict(_zelle(
                        spez, auspraegungen.get(str(pid), {})).model_point))
                    kw["gamma1"] = float(s["gamma1"])
                    teile.append((int(s["erhoehung_jahr"]), Rechenkern(ModelPoint(**kw))))
            return [(j, k) for j, k in teile if j < jahr]

        def red_soll(pid: int, welt: Dict[str, Any], jahr: int, code: str) -> Dict[str, float]:
            """Die Soll-Buchungen des Vorgangs ``code`` am Jahrestag ``jahr`` —
            die Regel von P-B1 (red_sollbuchungen), die Betraege aus DERSELBEN
            Vorgangsfolge auf den Grundlagen der Pruefstrecke."""
            folge = folge_fuer(pid, welt)
            ergebnis = None if folge is None else folge.ergebnis(jahr, code)
            if ergebnis is None:
                return {}
            return red_sollbuchungen(ergebnis.vs_neu, ergebnis.absorbiert,
                                     ergebnis.auszahlung)

        folgen: Dict[int, Optional[Vorgangsfolge]] = {}

        def folge_fuer(pid: int, welt: Dict[str, Any]) -> Optional[Vorgangsfolge]:
            """Die Vorgangsfolge der Police auf dem Weg der Pruefstrecke: Grund
            und Bausteine der Pruefstrecke, die neuen Scheiben der Fuehrung, die
            registrierten Vorgaenge, die Beitragsfreistellung, die Schicht — und
            DIESELBE Klasse wie Engine, Bewertung und P-B1 (kern.vorgangsfolge).
            Eine eigene Formel hier waere die vierte Abschrift — und genau die
            hat bei der Beitragsfreistellung den Fehler bestaetigt, statt ihn zu
            widerlegen (Review T25-06)."""
            if pid not in folgen:
                vorgaenge = vorgaenge_je_police.get(pid)
                if not vorgaenge:
                    folgen[pid] = None
                else:
                    try:
                        folgen[pid] = Vorgangsfolge(
                            welt["grund"], teile_bei(pid, welt, 10 ** 6),
                            [vorgang(j, a, v) for j, a, v, _ in vorgaenge],
                            pex_jahr=pex_je_police.get(pid),
                            schicht=schicht_je_police.get(pid),
                            stoab_je_baustein=bool(tarifwerk["stoab_je_baustein"]),
                            tku_umfang=str(tarifwerk["tku_umfang"]))
                    except ValueError as exc:
                        befund(pid, "herabsetzung",
                               f"Vorgangsfolge nicht rechenbar: {exc}")
                        folgen[pid] = None
            return folgen[pid]

        def nach_vorgang(pid: int, jahr: int, art: str) -> bool:
            """Ob vor einer Buchung ``art`` am Jahrestag ``jahr`` schon ein
            registrierter Vorgang liegt (Reihenfolge des Tages)."""
            grenze = (int(jahr), RANG[art if art in RANG else PEX_CODE])
            return any(vorgang(j, a, v).schluessel < grenze
                       for j, a, v, _ in vorgaenge_je_police.get(pid, ()))

        # Jeder registrierte Vorgang traegt seine Soll-Buchungen genau einmal am
        # Wirkungstag der Tabelle (Angriffsrunde nach T27: die Probe pruefte nur
        # die Zeilen, die da waren — 43 gestrichene Auszahlungen bestanden sie;
        # P-B1 hatte die Soll-Menge seit T27-14).
        red_zeilen = f_ledger[f_ledger["ereignis"].isin(REDUKTION_EREIGNISSE)
                              & ~f_ledger.index.isin(list(doppelt_idx))]
        for pid, vorgaenge in sorted(vorgaenge_je_police.items()):
            welt = welten.get(pid)
            if welt is None or pid in ausgeschlossen:
                continue
            for r_jahr, _anteil, r_verfahren, tag in vorgaenge:
                code = reduktion_ereignis(r_verfahren)
                eigene = red_zeilen[(red_zeilen["police_id"] == pid)
                                    & (red_zeilen["vertragsjahr"] == r_jahr)
                                    & (red_zeilen["ereignis"] == code)]
                for text in red_vollstaendigkeit_fehler(
                        pid, r_jahr, eigene, red_soll(pid, welt, r_jahr, code), tag,
                        ereignis=code):
                    befund(pid, "herabsetzung", text)

        for z in nach.to_dict("records"):
            pid, art, jahr = int(z["police_id"]), str(z["ereignis"]), int(z["vertragsjahr"])
            welt = welten.get(pid)
            if welt is None or pid in ausgeschlossen:
                continue                       # oben als Befund gemeldet
            if pid in red_jahr and pid not in vorgaenge_je_police \
                    and jahr >= min(red_jahr[pid]):
                continue                       # oben als Befund gemeldet
            if art in REDUKTION_EREIGNISSE:
                # Jede RED-/TKU-Zeile gehoert zu einem registrierten Vorgang
                # desselben Jahres und derselben Art (Runde D, Fund 3): Eine
                # Zeile, die kein registrierter Vorgang erzeugt, ist unbelegt,
                # wird nicht nachgerechnet und nicht gezaehlt. Ohne
                # Tabellenzeile steht der Befund oben.
                if pid not in vorgaenge_je_police:
                    continue
                registriert = [(j, reduktion_ereignis(v)) for j, _, v, _ in
                               vorgaenge_je_police[pid]]
                if (jahr, art) not in registriert:
                    befund(pid, "herabsetzung",
                           f"{art}-Buchung im Vertragsjahr {jahr} ({z['betrag_art']}), "
                           "registriert sind "
                           + ", ".join(f"{a} im Jahr {j}" for j, a in sorted(registriert))
                           + " — keine Buchung, die die Tabelle erzeugt; sie wird nicht "
                           "nachgerechnet und nicht als geprueft gezaehlt")
                    continue
            teile = teile_bei(pid, welt, jahr)
            grund, grund_mp = welt["grund"], welt["grund_mp"]
            pex_jahr = welt["pex_jahr"]
            folge = folge_fuer(pid, welt) if pid in vorgaenge_je_police else None
            if folge is not None and (art in REDUKTION_EREIGNISSE
                                      or nach_vorgang(pid, jahr, art)):
                # Der Vertrag nach Vorgaengen, ueber DIESELBE Folge wie Engine,
                # Bewertung und Ledger-Herleitung (kern.vorgangsfolge).
                if art in REDUKTION_EREIGNISSE:
                    # Die Buchungen des Vorgangs selbst, auf dem Weg der
                    # Pruefstrecke nachgerechnet; eine Art ausserhalb der
                    # Soll-Menge meldet die Vollstaendigkeit oben.
                    erwartet = red_soll(pid, welt, jahr, art).get(str(z["betrag_art"]))
                    if erwartet is None:
                        buchungen[art] += 1
                        continue
                elif art == "STO":
                    erwartet = folge.stand_vor(jahr, PEX_CODE).rkw(jahr)
                elif art == "PEX":
                    # Unmittelbar nach der Freistellung, vor einer
                    # Teilkuendigung desselben Tages.
                    erwartet = folge.stand_vor(jahr, RED_CODE).vs_bfr()
                else:
                    erwartet = folge.stand_vor(jahr, PEX_CODE).leistung()
                buchungen[art] += 1
                if weicht_ab(z["betrag"], erwartet, TOLERANZ):
                    abweichungen += 1
                    befund(pid, "buchung",
                           f"{art} Jahr {jahr}: Ledger {float(z['betrag']):.2f}, "
                           f"Vertrag nach Vorgaengen {erwartet:.2f}")
                continue
            if art == "STO" and pex_je_police.get(pid) is not None \
                    and pex_je_police[pid] <= jahr:
                # Storno eines beitragsfreien Vertrags: DERSELBE Rueckkaufswert
                # wie bei der Teilkuendigung nach der Beitragsfreistellung
                # (Entscheid B3 vom 2026-10-01; ein Rueckkaufswert, zwei Leser — P-B1 ebenso).
                erwartet = Vertragsstand.anfang(
                    grund, teile, stoab_je_baustein=bool(tarifwerk["stoab_je_baustein"]),
                    tku_umfang=str(tarifwerk["tku_umfang"]),
                    schicht=schicht_je_police.get(pid),
                ).nach_pex(pex_je_police[pid]).rkw(jahr)
            elif art == "STO":
                erwartet = vertrags_monatsreserve(
                    grund, teile, 12 * jahr,
                    stoab_je_baustein=bool(tarifwerk["stoab_je_baustein"])).rkw
                schicht = schicht_je_police.get(pid)
                if schicht_traegt(schicht, 12 * jahr):
                    erwartet += schichtwert_bei(schicht[0], schicht[1], grund_mp, 12 * jahr)
            elif art == "PEX":
                # Liegt die Freistellung nach der Verankerung, hat sie die
                # Korrekturschicht wertstetig in die beitragsfreie Summe
                # ueberfuehrt — die Probe rechnet dieselbe Regel nach, sonst
                # bestaetigt sie den alten, unvollstaendigen Betrag.
                erwartet = (
                    grund.beitragsfreie_summe(jahr)
                    + sum(k.beitragsfreie_summe(jahr - j) for j, k in teile)
                    + zuschlag_bei_pex(schicht_je_police.get(pid), grund, jahr)
                )
            else:
                pex_f = pex_jahr
                if pex_f is None:
                    eigene_pex = f_ledger[(f_ledger["police_id"] == pid)
                                          & (f_ledger["ereignis"] == "PEX")]
                    if len(eigene_pex):
                        pex_f = int(eigene_pex["vertragsjahr"].iloc[0])
                if pex_f is not None:
                    erwartet = (
                        grund.beitragsfreie_summe(int(pex_f))
                        + sum(k.beitragsfreie_summe(int(pex_f) - j)
                              for j, k in teile if int(pex_f) - j > 0)
                        + zuschlag_bei_pex(
                            schicht_je_police.get(pid), grund, int(pex_f))
                    )
                else:
                    erwartet = grund_mp.sum_insured + sum(k.mp.sum_insured for _, k in teile)
            buchungen[art] += 1
            if weicht_ab(z["betrag"], erwartet, TOLERANZ):
                abweichungen += 1
                befund(pid, "buchung",
                       f"{art} im Vertragsjahr {jahr}: Fuehrung {float(z['betrag']):.2f}, "
                       f"Pruefstrecke {erwartet:.2f}", ereignis=art, jahr=jahr,
                       fuehrung=float(z["betrag"]), pruefstrecke=erwartet)

    return {
        "schema_version": SCHEMA_VERSION,
        "stichtag": stichtag.isoformat(),
        "generation": generationen[0] if len(generationen) == 1 else generationen,
        "tarifwerk": tarifwerk,
        "anfangszustand": modus,
        **zahlen,
        "ohne_anfangszustand": sorted(ohne_zustand),
        "gedeckt": sorted(p for p, z in zustaende.items() if z.get("gedeckt_durch")),
        "schichten": len(schicht_je_police),
        "buchungen_geprueft": buchungen,
        "buchungen_abweichend": abweichungen,
        "fortschreibung_geprueft": fortschreibung is not None,
        # Positive Zahl statt Flag (Review T25-01/T25-02): "geprueft: ja"
        # und "nichts angesehen" sahen bisher gleich aus.
        "endbestand_geprueft": endbestand_geprueft,
        "befunde": befunde,
        "bestanden": not befunde,
    }


def parser() -> argparse.ArgumentParser:
    """Die Kommandozeile der Probe — auch fuer den Konsumenten, der den
    Aufruf eines Belegs nachrechnet."""
    p = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.gates.fuehrungsprobe",
        description="Die Fuehrung gegen die Pruefstrecke halten "
                    "(Produzent, kein Gate).")
    p.add_argument("--fall", required=True)
    p.add_argument("--repo-root", type=lebendes_repo, dest="repo_root", required=True)
    p.add_argument("--generation", required=True,
                   help="Knoten-Id der Tarifgeneration, z. B. klv/tg2015")
    p.add_argument("--uebernahme", default=None,
                   help="Uebernahme-Verzeichnis (Vorgabe: <fall>/abgeleitet/bestand)")
    p.add_argument("--fortschreibung", default=None,
                   help="Laufverzeichnis der Fortschreibung des uebernommenen "
                        "Bestands (bestand_fortschreibung --uebernahme); ohne "
                        "es werden nur Uebernahme und Anfangszustand geprueft")
    p.add_argument("--config", required=True, help="Bestand-Config der Fuehrung (TOML)")
    p.add_argument("--zeilen", required=True,
                   help="transformierte Zeilen (gates.transformation_anwenden --zeilen)")
    p.add_argument("--vorgeschichte", default=None,
                   help="REGISTRIERTE Metadatenliste der Geschaeftsvorfaelle")
    p.add_argument("--stichtag", required=True, help="Migrationsstichtag (ISO)")
    p.add_argument("--schicht", default=None,
                   help="ABGELEITETER Schichtbeleg (gates.verankerung_belegen)")
    p.add_argument("--red-anteil-kandidat", dest="red_anteil_kandidaten",
                   action="append", type=float, default=[],
                   help="Arbeitsannahme des Laufs (siehe aktuartest_lauf)")
    p.add_argument("--red-anteile-datei", dest="red_anteile_datei", default=None,
                   help="REGISTRIERTE Auskunft der Quelle zu den fortgefuehrten "
                        "Beitragsanteilen (POLNR;GEVO;DATUM;ANTEIL, optional "
                        "BEZUG) — der einzige Weg, sie zu nennen")
    p.add_argument("--anker-erwartungswerte", dest="anker_quelle", default=None)
    p.add_argument("--out", default=None,
                   help="Zielpfad (Vorgabe: <fall>/abgeleitet/berichte/fuehrungsprobe.json)")
    # Die Tarifregeln stehen in der Spez (ADR-024, Nachtrag). Auch der
    # Konsument, der den Aufruf eines Belegs nachrechnet, geht durch diesen
    # Parser: Ein alter Aufruf mit Schaltern wird sprechend verweigert.
    verweigere_entfallene_schalter(p)
    return p


def _aufruf(args: argparse.Namespace, ueber: Path, schluessel) -> List[str]:
    """Der vollstaendige Aufruf, normalisiert: ohne ``--fall``,
    ``--repo-root`` und ``--out``, Pfade relativ zum Fall."""
    a = ["--generation", str(args.generation), "--stichtag", str(args.stichtag),
         "--uebernahme", schluessel(ueber),
         "--config", schluessel(Path(args.config)),
         "--zeilen", schluessel(Path(args.zeilen))]
    if args.fortschreibung:
        a += ["--fortschreibung", schluessel(Path(args.fortschreibung))]
    for option, wert in (("--vorgeschichte", args.vorgeschichte), ("--schicht", args.schicht),
                         ("--red-anteile-datei", args.red_anteile_datei),
                         ("--anker-erwartungswerte", args.anker_quelle)):
        if wert is not None:
            a += [option, str(wert)]
    for wert in args.red_anteil_kandidaten:
        a += ["--red-anteil-kandidat", repr(float(wert))]
    return a


def main(argv: Optional[List[str]] = None) -> int:
    args = parser().parse_args(argv)
    code, ergebnis = fuehre_probe(args)
    if ergebnis is None:
        return code
    fall = Path(args.fall).resolve()
    out = Path(args.out) if args.out else fall / "abgeleitet" / "berichte" / "fuehrungsprobe.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(f"fuehrungsprobe: {ergebnis['vertraege']} Vertraege, "
          f"{ergebnis['mit_anfangszustand']} mit Anfangszustand, "
          f"{sum(ergebnis['buchungen_geprueft'].values())} Buchungen geprueft, "
          f"{len(ergebnis['befunde'])} Befunde -> {out}")
    for b in ergebnis["befunde"][:20]:
        print(f"  BEFUND {b['police_id'] or '-'} {b['art']}: {b['text']}", file=sys.stderr)
    return code


def fuehre_probe(args: argparse.Namespace) -> Tuple[int, Optional[Dict[str, Any]]]:
    """Die Probe ohne Schreiben: ``(Exit-Code, Beleg)``; bei einem
    Bedienfehler ``(2, None)`` mit Meldung auf stderr. Der Konsument ruft
    genau diese Funktion mit dem Aufruf des Belegs (Pruefrunde T27,
    Befund 06)."""
    fall = Path(args.fall).resolve()
    if not (fall / "fall.json").is_file():
        print(f"Kein Fall-Arbeitsbereich: {fall}", file=sys.stderr)
        return 2, None
    repo_root = Path(args.repo_root).resolve()
    ueber = Path(args.uebernahme).resolve() if args.uebernahme else fall / "abgeleitet" / "bestand"
    # Jede Eingabe GENAU EINMAL lesen (Review T25-05, dieselbe Klasse wie
    # T23-01/T20-01): Der Beleg traegt den Hash DER BYTES, die geprueft
    # wurden. Vorher las die Probe jede Datei fachlich und hashte sie
    # danach ein zweites Mal vom Pfad — dazwischen konnte eine andere
    # Datei stehen, und der Beleg bezeugte einen Zustand, den niemand
    # geprueft hat.
    # EINE Bindung, die gemeinsame (Befund T26-07, Teil b). Die eigene
    # Fassung hier las bei jedem Aufruf neu — wer eine Datei fuer einen
    # zweiten Zweck brauchte, bekam einen zweiten Lesevorgang. Genau
    # daran haengt der nachgewiesene Bruch: Der Schichtbeleg wurde
    # fachlich gelesen und danach ein zweites Mal gehasht; gebunden
    # wurden die Bytes der zweiten Lesung, geprueft die der ersten. Ein
    # Producer band damit unter gruenem Urteil eine Datei, die er nie
    # verarbeitet hatte.
    bindung = Eingangsbindung(fall)
    schluessel = bindung.schluessel
    binde = bindung.binde

    def lies(pfad: Path, spalten, pflicht: bool):
        if not pfad.is_file():
            if pflicht:
                raise SystemExit(f"fuehrungsprobe: Pflichttabelle fehlt: {pfad}")
            return None
        return read_portfolio_aus_bytes(binde(pfad).roh, expected_columns=spalten)

    try:
        uebernahme: Dict[str, Any] = {
            "bestand": lies(ueber / "bestand.parquet", STAMM_NAMES, True),
            "historie": lies(ueber / "historie.parquet", STATUS_HISTORIE_NAMES, True),
            "ledger": lies(ueber / "ledger.parquet", LEDGER_NAMES, True),
            "scheiben": lies(ueber / "scheiben.parquet", SCHEIBEN_NAMES, False),
            "verankerung": lies(ueber / "verankerung.parquet", VERANKERUNG_NAMES, False),
            "schichten": lies(ueber / "schichten.parquet", SCHICHTEN_NAMES, False),
            "merkmale": lies(ueber / "merkmale.parquet", None, False),
        }
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 2, None
    beleg_pfad = ueber / "uebernahme.json"
    if not beleg_pfad.is_file():
        print(f"fuehrungsprobe: Uebernahmebeleg fehlt: {beleg_pfad} — der Bestand "
              "hat keinen benannten Anfangszustand (gates.bestand_uebernehmen "
              "schreibt ihn)", file=sys.stderr)
        return 2, None
    uebernahme["beleg"] = json.loads(binde(beleg_pfad).text())

    fortschreibung = None
    if args.fortschreibung:
        lauf = Path(args.fortschreibung).resolve()
        try:
            fortschreibung = {
                "ledger": lies(lauf / "ledger.parquet", LEDGER_NAMES, True),
                "scheiben": lies(lauf / "scheiben.parquet", SCHEIBEN_NAMES, False),
                "historie": lies(lauf / "historie.parquet", STATUS_HISTORIE_NAMES, False),
                # Der Endbestand wurde bisher GELESEN und weggeworfen: der
                # Aufruf stand als freistehender Ausdruck da, sein
                # Rueckgabewert ging ins Leere (Review T25-02). Die Probe
                # meldete "fortschreibung_geprueft: true" und hatte ihn nie
                # angesehen — am echten Fall bestanden ein Endbestand mit
                # +999999 und eine Endhistorie mit XXX die Probe.
                "bestand": lies(lauf / "bestand_gesamt.parquet", STAMM_NAMES, False),
                "reduktionen": lies(
                    lauf / "reduktionen.parquet", REDUKTIONEN_NAMES, False),
                # Die Nebentabellen, die der Lauf aus der Uebernahme mitfuehrt
                # (Runde C, Befund RC04): Auf ihnen bewertet der Abschluss.
                "schichten": lies(lauf / "schichten.parquet", SCHICHTEN_NAMES, False),
                "verankerung": lies(lauf / "verankerung.parquet", VERANKERUNG_NAMES, False),
                "merkmale": lies(lauf / "merkmale.parquet", None, False),
            }
        except SystemExit as exc:
            print(str(exc), file=sys.stderr)
            return 2, None
        # Der belegte Horizont des Laufs (Runde C, Befund RC02): Eine RED-
        # Buchung dahinter hat der Lauf nicht gefahren. Als Klartext-JSON
        # gelesen, nicht ueber bestand.manifest — dieselbe Schicht-Kante
        # wie die uebrigen Eingaben, keine neue. Ohne Manifest gibt es
        # keinen belegten Horizont; dann prueft ihn P-B1 im Konsumenten.
        manifest_pfad = lauf / "laufmanifest.json"
        fortschreibung["horizont"] = None
        if manifest_pfad.is_file():
            try:
                fortschreibung["horizont"] = dt.date.fromisoformat(
                    str(json.loads(binde(manifest_pfad).text())["horizont"]))
            except (ValueError, KeyError, TypeError) as exc:
                print(f"fuehrungsprobe: Laufmanifest {manifest_pfad} ohne lesbaren "
                      f"Horizont ({type(exc).__name__}: {exc})", file=sys.stderr)
                return 2, None

    config_pfad = Path(args.config).resolve()
    config = config_aus_text(binde(config_pfad).text())
    fehler = config.validate()
    if fehler:
        print("fuehrungsprobe: Config ungueltig: " + "; ".join(fehler), file=sys.stderr)
        return 2, None
    # Die Spez war ueberhaupt nicht gebunden (Review T25-05): Die Probe
    # rechnete gegen die Zellen einer Datei, die ihr Beleg nicht nannte.
    spez_datei = spez_pfad(fall, args.generation)
    spez = lade_spez_aus_bytes(binde(spez_datei).roh)
    try:
        regeln = tarifregeln_des_falls(fall, spez)
    except TarifregelnFehler as exc:
        print(f"fuehrungsprobe: {exc}", file=sys.stderr)
        return 2, None
    zeilen_pfad = Path(args.zeilen).resolve()
    zeilen = json.loads(binde(zeilen_pfad).text())
    if not isinstance(zeilen, list):
        print(f"{args.zeilen}: erwartet wird die Zeilenliste aus "
              "gates.transformation_anwenden --zeilen", file=sys.stderr)
        return 2, None
    vorgeschichte = []
    if args.vorgeschichte:
        # Durch DIESELBE Bindung lesen, nicht daneben (Pruefrunde T27,
        # Befund 08): ``binde`` registrierte die Datei, ``_lies_csv``
        # oeffnete sie danach ein zweites Mal — verarbeitet wurden andere
        # Bytes, als der Beleg nannte.
        vorgeschichte = _lies_csv(fall, args.vorgeschichte, bindung)

    if args.red_anteile_datei is not None and not args.vorgeschichte:
        print("fuehrungsprobe: --red-anteile-datei wirkt nur mit "
              "--vorgeschichte (die Anteile gehoeren zu den Ereignissen der "
              "Vorgeschichte) — ohne sie waere die Auskunft gebunden, aber "
              "ohne Wirkung", file=sys.stderr)
        return 2, None
    red_anteile: Dict[str, float] = {}
    red_anteile_je_datum: Dict[str, Dict[str, float]] = {}
    red_anteile_datei: Optional[Dict[str, Any]] = None
    if args.red_anteile_datei is not None:
        # Auch die Herabsetzungs-Anteile binden (Review T25-05): Sie gehen
        # in jede Bewertung ein und standen nicht im Beleg. Seit dem
        # Entscheid 2026-09-30 ist die registrierte Auskunft der einzige
        # Weg; der Beleg nennt sie mit Name, SHA-256 und Bezug je Police.
        auskuenfte = lies_auskuenfte(
            fall, args.red_anteile_datei, bindung, vorgeschichte,
            dict(VORGABE))
        red_anteile = dict(auskuenfte.anteile)
        red_anteile_je_datum = {
            pol: dict(d) for pol, d in auskuenfte.je_datum.items()}
        red_anteile_datei = auskuenfte.beleg
    anker: Dict[str, Tuple[int, float]] = {}
    if args.anker_quelle is not None:
        quelle_pfad = fall_mod.eingang_datei(fall, args.anker_quelle)
        quelle = json.loads(binde(quelle_pfad).text())
        for eintrag in quelle.get("vertraege", []):
            erster = next(
                (x for x in (eintrag.get("punkte") or [])
                 if x.get("anlass") == "uebernahme"
                 and "kVx_MRV" in (x.get("erwartet") or {})), None)
            if erster:
                anker[str(eintrag["police_id"])] = (
                    int(erster["monate"]), float(erster["erwartet"]["kVx_MRV"]))

    schichtbeleg = None
    if args.schicht:
        from rechner_pipeline.gates.aktuartest_lauf import _schichten

        # Dieselbe Bindung weitergereicht: Der Beleg wird EINMAL gelesen,
        # und genau diese Bytes stehen danach im eigenen Beleg (T26-07 b).
        roh = _schichten(fall, args.schicht, repo_root=repo_root,
                         bindung=bindung, auskunft=red_anteile_datei)
        schichtbeleg = {
            police: {k: (v.als_beleg() if hasattr(v, "als_beleg") else v)
                     for k, v in eintrag.items()}
            for police, eintrag in roh.items()
        }
        # Kein zweiter Lesevorgang mehr: _schichten hat ueber dieselbe
        # Bindung gelesen und dabei registriert.

    # Tarifwerk und Quellverfahren: die belegten der Spez — dieselbe Fassung,
    # mit der Uebernahme und Pruefstrecke gerechnet haben (ADR-024, Nachtrag).
    ergebnis = pruefe_fuehrung(
        uebernahme=uebernahme, fortschreibung=fortschreibung, config=config,
        spez=spez, zeilen=zeilen, vorgeschichte=vorgeschichte,
        tarifwerk=dict(regeln.tarifwerk), quellverfahren=dict(regeln.quellverfahren),
        erhoehungssatz=regeln.erhoehungssatz,
        red_anteile=red_anteile, red_anteile_je_datum=red_anteile_je_datum,
        red_anteil_kandidaten=tuple(args.red_anteil_kandidaten), anker=anker,
        schichtbeleg=schichtbeleg, stichtag=dt.date.fromisoformat(args.stichtag),
    )
    ergebnis["system"] = systemstand(repo_root)
    ergebnis["provenienz"] = {
        "eingaben": bindung.als_beleg(),
        "parameter": {
            "generation": args.generation, "tarifregeln": regeln.als_beleg(),
            "red_anteile_datei": red_anteile_datei,
            "red_anteil_kandidaten": sorted(args.red_anteil_kandidaten),
            "anker_erwartungswerte": args.anker_quelle,
            "vorgeschichte": args.vorgeschichte, "schicht": args.schicht,
            "uebernahme": schluessel(ueber),
            "fortschreibung": (schluessel(Path(args.fortschreibung))
                               if args.fortschreibung else None),
        },
        # Der vollstaendige Aufruf (Pruefrunde T27, Befund 06): Mit ihm
        # rechnet der Konsument die Probe nach, statt ihr zu glauben.
        "aufruf": _aufruf(args, ueber, schluessel),
    }
    return (0 if ergebnis["bestanden"] else 1), ergebnis


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
