"""Jede Buchung folgt aus ihrer Police und dem Kern — policenweise (T20-04).

Der Ledger ist definiert als "one row per booked event with its
kernel-computed amount". ``validate_ledger`` (models.bestand) prueft
Form und Semantik jeder Zeile und bindet ERH-Buchungen zeilenweise an
die Scheiben. Was dort fehlte (externes Review T20-04): Fuer STO, PEX,
TOD, ABL und ZUG wurde nicht geprueft, ob der BETRAG fuer genau diese
Police aus dem Kern folgt. Zwei Stornobetraege desselben Jahres,
zwischen zwei Policen vertauscht — Code, Betragsart, Datum, Generation,
Zeilenzahl und Jahressumme unveraendert — passierten P-B1 mit null
Befunden; das Bewegungskonto sieht nur Jahressummen. Aggregatgleichheit
ersetzt keine Buchungsidentitaet.

Hier wird jede Buchung mit gerechnetem Betrag gegen dieselbe
Kern-Herleitung gestellt, mit der die Ereignis-Engine sie erzeugt hat
(:mod:`rechner_pipeline.bestand.ereignisse`): Rueckkaufswert,
beitragsfreie Summe, Todesfall- und Ablaufleistung des Vertrags im
gebuchten Vertragsjahr, ueber Grundscheibe und die bis dahin bestehenden
Erhoehungsscheiben. Ein Betrag, der zu einer anderen Police gehoert,
faellt daran — unabhaengig davon, ob die Jahressumme aufgeht.

Bewusste Grenzen: ``MIG`` (Residuum der Uebernahme) und ``RED``
(Herabsetzung, von der Engine nicht erzeugt) werden nicht hergeleitet;
``ERH`` ist ueber die Scheiben gebunden. Beim BU-Beispielprodukt folgt der
Betrag eines Todes- oder Ablaufereignisses aus dem ZUSTAND unmittelbar
davor (Review T21-01): im Leistungsbezug die Jahresrente, als Anwaerter
null — hergeleitet aus der geordneten Statushistorie, nicht aus dem zu
pruefenden Betrag. Vorher genuegte "null oder Rente", und zwei
BU-Ablaeufe gleicher Rente liessen sich zwischen einer aktiven und einer
invaliden Police tauschen.

Knoten: klv, bu
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from rechner_pipeline.bestand.auswertung import grundlagen_je_police
from rechner_pipeline.bestand.config import BestandConfig
from rechner_pipeline.bestand.kernlauf import vertrags_rkw
from rechner_pipeline.kern import ModelPoint, Rechenkern, erhoehungs_scheibe
from rechner_pipeline.models.bestand import model_point_kwargs

#: Cent-Toleranz: Der Kern schreibt Buchung und Herleitung aus demselben
#: Wert; eine Lieferung darf auf Cent gerundet haben. Ein vertauschter
#: Betrag liegt Groessenordnungen darueber.
TOLERANZ = 0.005

#: Ereignisse, deren Betrag hier hergeleitet wird (KLV).
HERGELEITET = ("ZUG", "STO", "PEX", "TOD", "ABL")


def _vollendete_jahre(start: pd.Timestamp, datum: pd.Timestamp) -> int:
    return ((datum.year * 12 + datum.month) - (start.year * 12 + start.month)) // 12


class _Herleitung:
    """Grundscheibe und Erhoehungsscheiben einer Police als Rechenkerne."""

    def __init__(self, row: Dict[str, Any], felder: Dict[str, Any],
                 scheiben: List[Tuple[int, float]]) -> None:
        self.grund_mp = ModelPoint(**model_point_kwargs(row, felder))
        self.grund = Rechenkern(self.grund_mp)
        # Dieselbe Scheiben-Regel wie die Engine (erhoehungs_scheibe): Die
        # Scheibe ist aus Grundscheibe, Erhoehungsjahr und Summe
        # reproduzierbar.
        self.scheiben = [
            (jahr, vs, Rechenkern(erhoehungs_scheibe(self.grund_mp, jahr, vs)))
            for jahr, vs in sorted(scheiben)
        ]

    def _bis(self, jahr: int):
        # Die Engine bucht STO/PEX/TOD des Jahres j+1 VOR der Erhoehung
        # desselben Jahres: Es zaehlen die Scheiben mit Erhoehungsjahr < jahr.
        return [(j, vs, k) for j, vs, k in self.scheiben if j < jahr]

    def gesamt_vs(self, jahr: int) -> float:
        return self.grund_mp.sum_insured + sum(vs for _, vs, _ in self._bis(jahr))

    def rkw(self, jahr: int) -> float:
        return vertrags_rkw(self.grund, [(j, k) for j, _, k in self._bis(jahr)], jahr)

    def beitragsfreie_summe(self, jahr: int) -> float:
        return self.grund.beitragsfreie_summe(jahr) + sum(
            k.beitragsfreie_summe(jahr - j) for j, _, k in self._bis(jahr)
        )


#: Zustaende, die eine Police beenden — eine Zeile mit diesem Code am
#: Ereignisdatum IST das Ereignis, nicht sein Vorzustand.
ENDZUSTAENDE = ("TOD", "ABL", "STO")


def zustand_vor(
    historie: Optional[pd.DataFrame], pid: int, datum: pd.Timestamp
) -> str:
    """Der Zustand einer Police unmittelbar VOR ihrem Ereignis an ``datum``.

    Aus der geordneten Statushistorie (status_date, status_id): die
    juengste Zeile bis einschliesslich ``datum``, wobei die Endzustands-
    Zeile desselben Datums (das Ereignis selbst) nicht zaehlt. Der Ledger
    traegt keine status_id, deshalb entscheidet der Code, nicht die
    Reihenfolge. Faellt eine Invalidisierung mit dem Ablauf auf dasselbe
    Datum (letztes Vertragsjahr), ist der Vorzustand des Ablaufs BU.
    Ohne Historie oder Zeile gilt der Ursprungszustand POL. Dieselbe
    Herleitung nutzt das Bewegungskonto (kennzahlen).
    """
    if historie is None or len(historie) == 0:
        return "POL"
    zeilen = historie[(historie["police_id"] == pid) & (historie["status_date"] <= datum)]
    zeilen = zeilen[~((zeilen["status_date"] == datum)
                      & zeilen["status_code"].isin(ENDZUSTAENDE))]
    if len(zeilen) == 0:
        return "POL"
    juengste = zeilen.sort_values(["status_date", "status_id"], kind="stable").iloc[-1]
    return str(juengste["status_code"])


def pruefe_ledger_betraege(
    stamm: pd.DataFrame,
    ledger: pd.DataFrame,
    config: BestandConfig,
    *,
    scheiben: Optional[pd.DataFrame] = None,
    historie: Optional[pd.DataFrame] = None,
    merkmale: Optional[pd.DataFrame] = None,
) -> List[str]:
    """Betrag jeder Buchung gegen die Kern-Herleitung DIESER Police.

    Rueckgabe: Fehlerliste (leer = jede hergeleitete Buchung stimmt).
    Voraussetzung ist ein formal gueltiger Ledger (``validate_ledger``);
    unbekannte Policen oder Generationen werden als Fehler gemeldet, nicht
    als Ausnahme.
    """
    errors: List[str] = []
    if len(ledger) == 0:
        return errors
    grundlagen = grundlagen_je_police(config, merkmale)
    haupt = stamm.set_index("police_id")

    scheiben_je_police: Dict[int, List[Tuple[int, float]]] = {}
    if scheiben is not None:
        for pid, jahr, vs in zip(scheiben["police_id"], scheiben["erhoehung_jahr"],
                                 scheiben["sum_insured"]):
            scheiben_je_police.setdefault(int(pid), []).append((int(jahr), float(vs)))

    # Beitragsfreistellung je Police: das Vertragsjahr, in dem die
    # beitragsfreie Summe fixiert wurde. Aus der Historie (auch die
    # Vorgeschichte eines uebernommenen Vertrags steht dort), sonst aus der
    # eigenen PEX-Buchung.
    pex_jahr: Dict[int, int] = {}
    if historie is not None and len(historie):
        pex = historie[historie["status_code"] == "PEX"]
        for pid, datum in zip(pex["police_id"], pex["status_date"]):
            pid = int(pid)
            if pid in haupt.index:
                j = _vollendete_jahre(haupt.loc[pid, "insurance_start"], datum)
                pex_jahr[pid] = min(j, pex_jahr.get(pid, j))
    for pid, jahr in zip(ledger.loc[ledger["ereignis"] == "PEX", "police_id"],
                         ledger.loc[ledger["ereignis"] == "PEX", "vertragsjahr"]):
        pex_jahr.setdefault(int(pid), int(jahr))

    herleitungen: Dict[int, _Herleitung] = {}
    abweichungen: List[str] = []
    for z in ledger.itertuples(index=False):
        pid = int(z.police_id)
        art = str(z.ereignis)
        if pid not in haupt.index:
            errors.append(f"ledger police {pid}: nicht im Stamm")
            continue
        h = haupt.loc[pid]
        produkt = str(h.get("produkt", "klv"))
        jahr = int(z.vertragsjahr)
        betrag = float(z.betrag)
        erwartet: Optional[float] = None
        if produkt == "bu":
            rente = float(h["bu_rente"])
            if art in ("INV", "REA", "ZUG"):
                erwartet = rente
            elif art in ("TOD", "ABL"):
                # Der Zustand VOR dem Ereignis entscheidet, nicht der Betrag
                # (T21-01): Leistungsbezug -> Rente endet; Anwaerter -> 0.
                im_bezug = zustand_vor(historie, pid, z.status_date) == "BU"
                erwartet = rente if im_bezug else 0.0
            else:
                continue
        else:
            if art not in HERGELEITET:
                continue
            if art == "ZUG":
                erwartet = float(h["sum_insured"])
            else:
                if pid not in herleitungen:
                    try:
                        felder = grundlagen(pid, str(h["tarif_generation"]))
                        herleitungen[pid] = _Herleitung(
                            h.to_dict() | {"police_id": pid}, felder,
                            scheiben_je_police.get(pid, []))
                    except (KeyError, ValueError) as exc:
                        errors.append(f"ledger police {pid}: Kern nicht herleitbar: {exc}")
                        continue
                v = herleitungen[pid]
                bfr_ab = pex_jahr.get(pid)
                if art == "STO":
                    erwartet = v.rkw(jahr)
                elif art == "PEX":
                    # Uebernommene Vertraege buchen die Umbuchung zum
                    # Zugangsstichtag, die Summe wurde im Jahr der
                    # Beitragsfreistellung fixiert (gates.bestand_uebernehmen).
                    erwartet = v.beitragsfreie_summe(
                        bfr_ab if bfr_ab is not None and bfr_ab <= jahr else jahr)
                elif art in ("TOD", "ABL"):
                    if bfr_ab is not None and bfr_ab <= jahr:
                        erwartet = v.beitragsfreie_summe(bfr_ab)
                    else:
                        erwartet = v.gesamt_vs(jahr)
        if erwartet is not None and abs(betrag - erwartet) > TOLERANZ:
            abweichungen.append(
                f"police {pid} {art} Jahr {jahr}: Ledger {betrag:.2f}, "
                f"Kern {erwartet:.2f}")

    if abweichungen:
        errors.append(
            f"ledger: {len(abweichungen)} Buchung(en), deren Betrag nicht aus "
            "dem Kern fuer diese Police folgt — z. B. "
            + "; ".join(abweichungen[:3])
            + (" ..." if len(abweichungen) > 3 else "")
            + ". Ein Betrag, der zu einer anderen Police gehoert, ist keine "
            "Buchung dieser Police, auch wenn die Jahressumme aufgeht"
        )
    return errors
