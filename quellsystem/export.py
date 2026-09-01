"""Der Export der Quelle: das Lieferpaket im etablierten Format.

Erzeugt die Artefakte, die das Quellsystem an das aufnehmende
Unternehmen liefert — spalten- und formatgleich zur versionierten
Alt-Lieferung (``lieferungen/baldrian/``), denn auf diesem Vertrag
stehen die Parser der Zielseite:

* ``bestandsabzug`` je Stichtag: eine Zeile je aktiver Police
  (AKT/BFR), Betraege mit Punkt-Dezimal, Daten als TT.MM.JJJJ.
  ``DECKKAP`` ist die letzte Standmitteilung — der Wert am letzten
  Vertragsjahrestag (t_a), dem letzten exakten Rechenpunkt des Blatts;
  die Quelle interpoliert nicht.
* ``gevo_metadaten``: die Vorgeschichte der Abzugs-Policen bis zum
  Stichtag (PEX/ERH/RED — Police, Art, Datum, ohne Betraege).
* ``gevo_protokoll``: die Vorfaelle des Folgejahres MIT Betraegen
  (inklusive der terminalen STO/TOD/ABL); PARAM traegt bei RED den
  fortgefuehrten Anteil.
* die Dokumente der Quelle als PDF: AVB und Tarifplan/Mitteilung 143
  (Doku-Engine, siehe dokumente.py).

Der Bestand eines Stichtags ist eine REKONSTRUKTION aus dem Journal
(:func:`stand_am`): Das Buch wird ueber den Stichtag hinaus gefuehrt,
also muessen spaetere Vorfaelle rueckwirkend unsichtbar sein —
Erhoehungsscheiben nach dem Stichtag zaehlen nicht, Herabsetzungen
danach werden ueber die Ursprungssumme und die Herabsetzungskette bis
zum Stichtag zurueckgerechnet (mit derselben Cent-Rundung je Schritt,
also exakt der damals gebuchte Wert), eine spaetere Beitragsfreistellung
laesst den Vertrag am Stichtag beitragspflichtig.

``STORNO_KZ`` bleibt hier LEER: Das undokumentierte R/S-Kennzeichen der
Baldrian-Lieferung ist eine Regie-Manipulation (M2) und wird von der
Spielleitung eingespielt — der Export erzeugt die saubere Lieferung der
Quelle, die Regie macht daraus den Vorfuehrfall.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from quellsystem.bestandsfuehrung import (
    Bestandsfuehrung,
    Police,
    Scheibe,
    _volle_jahre,
)
from quellsystem.konventionen import excel_round
from quellsystem.rechnung import Rechnung, Vertrag

TARIF = "KLV15"
RK = {"Nichtraucher": "NR", "Raucher": "R"}
BGRP = {"Einzel": "E", "Kollektiv": "K", "Haus": "H"}
ZAHLW = {1: "jaehrlich", 2: "halbjaehrlich", 4: "vierteljaehrlich",
         12: "monatlich"}


def _dt_de(datum: dt.date) -> str:
    return datum.strftime("%d.%m.%Y")


def _betrag(wert: float) -> str:
    return f"{excel_round(wert, 2):.2f}"


@dataclass(frozen=True)
class ScheibenStand:
    """Eine Scheibe, wie sie AM Stichtag im Buch stand."""

    scheibe: Scheibe
    vs: float
    vs_bfr: Optional[float]


@dataclass(frozen=True)
class Stand:
    """Der rekonstruierte Zustand einer Police an einem Stichtag."""

    police: Police
    stichtag: dt.date
    scheiben: List[ScheibenStand]
    beitragsfrei_seit: Optional[dt.date]

    @property
    def beitragsfrei(self) -> bool:
        return self.beitragsfrei_seit is not None


def stand_am(police: Police, stichtag: dt.date,
             pex_datum: Optional[dt.date]) -> Stand:
    """Police-Zustand am Stichtag aus Ursprungswerten und Vorfallketten.

    ``pex_datum`` ist das Datum der Beitragsfreistellung aus dem Journal
    (None, wenn nie) — der Statusverlauf einer Police laesst sich nicht
    aus ihrem Endzustand ablesen, wohl aber aus ihren Buchungen.
    """
    beitragsfrei_seit = (pex_datum
                         if pex_datum is not None and pex_datum <= stichtag
                         else None)
    staende: List[ScheibenStand] = []
    for s in police.scheiben:
        if s.beginn > stichtag:
            continue
        vs = s.vs0
        if s.nr == 0:
            # Nur die Grundscheibe wird herabgesetzt; die Kette bis zum
            # Stichtag reproduziert den gebuchten Wert exakt (gleiche
            # Reihenfolge, gleiche Cent-Rundung je Schritt).
            for datum, f in police.herabsetzungen:
                if datum <= stichtag:
                    vs = excel_round(vs * f, 2)
        staende.append(ScheibenStand(
            scheibe=s, vs=vs,
            vs_bfr=s.vs_bfr if beitragsfrei_seit is not None else None,
        ))
    return Stand(police=police, stichtag=stichtag, scheiben=staende,
                 beitragsfrei_seit=beitragsfrei_seit)


def werte_am(stand: Stand, monate: int) -> Dict[str, float]:
    """Vertragswerte am Vertragsmonat ``monate`` (Jahresgitter).

    Der Zustand ist der des Stichtags — die Punkte in der Zukunft sind
    die Erwartung OHNE weitere Vorfaelle (genau das prueft die
    Fortschreibungsregel des aufnehmenden Systems). Je Scheibe faellt
    der Punkt auf ihr eigenes Blattjahr (Beginnversatz); beitragsfrei
    laeuft die fixierte Summe auf dem beitragsfreien Reservesatz, und
    ``BJB`` zaehlt nur Scheiben, deren Beitragszeit am Punkt noch
    laeuft.
    """
    police = stand.police
    grund = police.grund
    werte = {"kVx_MRV": 0.0, "RKW": 0.0, "BJB": 0.0, "VS_bfr": 0.0}
    for st in stand.scheiben:
        s = st.scheibe
        offset = _volle_jahre(grund.beginn, s.beginn)
        k = min(max(0, monate // 12 - offset), s.n)
        rechnung = Rechnung(
            police.tarif, Vertrag(s.x, s.n, s.t, st.vs, police.zw))
        zeile = rechnung.verlaufszeile(k)
        if stand.beitragsfrei:
            werte["kVx_MRV"] += excel_round(
                st.vs_bfr * zeile["kVx_bfr_G"], 2)
            werte["VS_bfr"] += st.vs_bfr
        else:
            werte["kVx_MRV"] += zeile["kVx_MRV_H"]
            # KONVENTION DER QUELLE: StoAb-Grenzen je SCHEIBE.
            werte["RKW"] += zeile["RKW_K"]
            if k < s.t:
                werte["BJB"] += rechnung.bjb()
    return {g: excel_round(w, 2) for g, w in werte.items()}


class Export:
    """Das Lieferpaket eines Stichtags aus dem gefuehrten Buch."""

    def __init__(self, buch: Bestandsfuehrung) -> None:
        self.buch = buch
        # Statusverlauf aus dem Journal: der Endzustand einer Police
        # (vtg_status/seit) traegt nur den LETZTEN Wechsel — nach
        # PEX + spaeterem TOD waere die Beitragsfreiheit am Stichtag
        # sonst unsichtbar.
        self._pex: Dict[int, dt.date] = {}
        self._terminal: Dict[int, dt.date] = {}
        for b in buch.journal:
            if b.art == "PEX":
                self._pex.setdefault(b.polnr, b.datum)
            elif b.art in ("STO", "TOD", "ABL"):
                self._terminal.setdefault(b.polnr, b.datum)

    def stand_am(self, police: Police, stichtag: dt.date) -> Stand:
        return stand_am(police, stichtag, self._pex.get(police.polnr))

    def verankerung(self, police: Police,
                    stichtag: dt.date) -> Dict[str, float]:
        """t_a und der dort gefuehrte Wert — die letzte Standmitteilung.

        t_a ist der letzte Vertragsjahrestag am oder vor dem Stichtag,
        in vollen Vertragsmonaten (der letzte exakte Rechenpunkt).
        """
        monate_ta = 12 * _volle_jahre(police.grund.beginn, stichtag)
        stand = self.stand_am(police, stichtag)
        return {"monate_ta": monate_ta,
                "dk_ta": werte_am(stand, monate_ta)["kVx_MRV"]}

    def _im_abzug(self, stichtag: dt.date) -> List[Police]:
        return [
            p for p in (self.buch.policen[n]
                        for n in sorted(self.buch.policen))
            if p.beginn <= stichtag
            and self._terminal.get(p.polnr, dt.date.max) > stichtag
        ]

    def bestandsabzug(self, pfad: Path, stichtag: dt.date) -> Path:
        zeilen = [
            "POLNR;TARIF;VTG_STATUS;GESCHL;RK;BGRP;GEBDAT;BEGINN;ABLAUF;"
            "BZDAUER;ERLSUMME;ZAHLW;JBRUTTO;DECKKAP;STORNO_KZ"
        ]
        for p in self._im_abzug(stichtag):
            grund = p.grund
            stand = self.stand_am(p, stichtag)
            monate_ta = 12 * _volle_jahre(grund.beginn, stichtag)
            werte = werte_am(stand, monate_ta)
            if stand.beitragsfrei:
                erlsumme = werte["VS_bfr"]
            else:
                erlsumme = sum(st.vs for st in stand.scheiben)
            zeilen.append(";".join([
                str(p.polnr), TARIF,
                "BFR" if stand.beitragsfrei else "AKT",
                p.geschlecht, RK[p.status], BGRP[p.tarifart],
                _dt_de(p.geburtsdatum), _dt_de(grund.beginn),
                _dt_de(dt.date(grund.beginn.year + grund.n,
                               grund.beginn.month, 1)),
                str(grund.t),
                _betrag(erlsumme), ZAHLW[p.zw], _betrag(werte["BJB"]),
                _betrag(werte["kVx_MRV"]),
                "",
            ]))
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
        return pfad

    def gevo_metadaten(self, pfad: Path, stichtag: dt.date) -> Path:
        """Die Vorgeschichte der Abzugs-Policen — Art und Datum, ohne Betrag."""
        im_abzug = {p.polnr for p in self._im_abzug(stichtag)}
        zeilen = ["POLNR;GEVO;DATUM"]
        for b in self.buch.journal:
            if (b.art in ("PEX", "ERH", "RED")
                    and b.polnr in im_abzug and b.datum <= stichtag):
                zeilen.append(f"{b.polnr};{b.art};{_dt_de(b.datum)}")
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
        return pfad

    def gevo_protokoll(
        self, pfad: Path, von: dt.date, bis: dt.date
    ) -> Path:
        """Die Vorfaelle des Zeitraums (von, bis] — mit Betraegen.

        PARAM traegt bei RED den fortgefuehrten Anteil; die uebrigen
        Arten lassen das Feld leer (Format der Alt-Lieferung).
        """
        anteile = {
            (p.polnr, datum): f
            for p in self.buch.policen.values()
            for datum, f in p.herabsetzungen
        }
        zeilen = ["POLNR;GEVO;DATUM;BETRAG;PARAM"]
        for b in self.buch.journal:
            if b.art == "ZUG" or not (von < b.datum <= bis):
                continue
            param = ""
            if b.art == "RED":
                f = anteile.get((b.polnr, b.datum))
                param = f"{f:g}" if f is not None else ""
            zeilen.append(
                f"{b.polnr};{b.art};{_dt_de(b.datum)};{_betrag(b.betrag)};"
                f"{param}")
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
        return pfad

    def lieferung(
        self,
        ziel: Path,
        stichtag: dt.date,
        stichtag2: Optional[dt.date] = None,
        *,
        mit_pdf: bool = True,
    ) -> List[Path]:
        """Das Paket eines Stichtags: Abzug, Vorgeschichte, Erwartungs-
        werte — plus Folgejahr (zweiter Abzug, Protokoll) und AVB-PDF."""
        ziel = Path(ziel)
        iso = stichtag.isoformat()
        aus = [
            self.bestandsabzug(
                ziel / f"baldrian_bestandsabzug_{iso}.csv", stichtag),
            self.gevo_metadaten(
                ziel / "baldrian_gevo_metadaten.csv", stichtag),
        ]
        if stichtag2 is not None:
            aus.append(self.bestandsabzug(
                ziel / f"baldrian_bestandsabzug_{stichtag2.isoformat()}.csv",
                stichtag2))
            aus.append(self.gevo_protokoll(
                ziel / f"baldrian_gevo_protokoll_{stichtag2.year - 1}.csv",
                stichtag, stichtag2))
            from quellsystem.erwartungswerte import Erwartungswerte

            aus.extend(Erwartungswerte(self, stichtag, stichtag2)
                       .schreibe(ziel))
        if mit_pdf:
            from quellsystem.dokumente import AVB, TARIFPLAN, als_pdf

            aus.append(als_pdf(AVB, ziel / "AVB_KLV_TG2015.pdf"))
            aus.append(als_pdf(
                TARIFPLAN, ziel / "Mitteilung_143_KLV_TG2015.pdf"))
        return aus
