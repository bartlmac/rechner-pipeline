"""Die Bestandsfuehrung der Quelle: Verkauf, Vorfaelle, Journal.

Das Quellsystem VERKAUFT Policen (Neugeschaeft ueber das
Vertriebsfenster der Generation) und fuehrt sie danach ueber die Jahre:
Dynamik-Erhoehungen, Beitragsfreistellungen, Herabsetzungen, Storni,
Tode, Ablaeufe — MEHRERE Vorfaelle je Vertrag, mit Datum im Journal.
Der Bestand zu einem Stichtag ist damit das ERGEBNIS der Fuehrung, keine
gesetzte Zahl.

Konventionen der Quelle (bewusst anders als das Zielsystem; genehmigt
2026-08-31, praezisiert am Golden Master):

* **Kalenderjahres-Logik**: Vorfaelle werden am 1. Januar geprueft und
  gebucht — nicht am Vertragsjahrestag. Bewertet wird am letzten
  VOLLEN Vertragsjahr davor (dem letzten Rechenpunkt des Blatts):
  genau daraus entstehen spaeter die t_a der Lieferung.
* **Stornoabzug JE SCHEIBE**: Jede Dynamikscheibe ist im Blattmodell der
  Quelle ein eigener kleiner Vertrag; beim Rueckkauf gelten die
  StoAb-Grenzen je Scheibe — die Untergrenze greift also mehrfach.
  (Das Zielsystem rechnet vertragsweit; die Differenz ist eine der
  Konventionsdifferenzen, die R_conv sichtbar machen soll.)
* **Herabsetzung = TEILKUENDIGUNG MIT AUSZAHLUNG**, nur auf der
  GRUNDSCHEIBE: Der freiwerdende Reserveanteil wird nach anteiligem
  Stornoabzug AUSGEZAHLT, die Grundsumme sinkt auf f, die
  Dynamikscheiben bleiben unberuehrt. Verbreitete Altpraxis — und
  maximal weit weg von der verlustfreien Umwandlung des Zielsystems
  (PLV: anteilig ueber alle Schichten). Der Vertrag bleibt AKT; RED ist
  ein Geschaeftsvorfall, kein Zustand — danach sind weitere Dynamiken,
  PEX oder eine zweite Herabsetzung moeglich.
* **Cent beim Buchen**: gebuchte Betraege sind centgerundet
  (Excel-Rundung); die Rechenkette bleibt ungerundet (rechnung.py).
* **VS_bfr am letzten Rechenpunkt**: fixiert wird die beitragsfreie
  Summe des letzten vollen Vertragsjahres — die Quelle interpoliert
  nicht.

Determinismus: ``random.Random(seed)`` (stdlib), ein Strom je Lauf, feste
Zieh-Reihenfolge. KEIN Import aus rechner_pipeline.
"""

from __future__ import annotations

import datetime as dt
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from quellsystem.konventionen import excel_round
from quellsystem.rechnung import Rechnung, Vertrag
from quellsystem.tarifwerk import Tarifzelle, zelle


def _cent(betrag: float) -> float:
    return excel_round(betrag, 2)


def _monatserster(jahr: int, monat: int) -> dt.date:
    return dt.date(jahr + (monat - 1) // 12, (monat - 1) % 12 + 1, 1)


def _volle_jahre(beginn: dt.date, datum: dt.date) -> int:
    """Volle Vertragsjahre am ``datum`` (Monatserster-Arithmetik)."""
    monate = (datum.year - beginn.year) * 12 + (datum.month - beginn.month)
    return max(0, monate // 12)


@dataclass
class Scheibe:
    """Eine Schicht des Vertrags — Grundscheibe oder Dynamik-Erhoehung."""

    nr: int
    beginn: dt.date
    x: int
    n: int
    t: int
    vs: float

    def rechnung(self, zw: int, tarif: Tarifzelle) -> Rechnung:
        return Rechnung(tarif, Vertrag(self.x, self.n, self.t, self.vs, zw))


@dataclass
class Police:
    """Ein gefuehrter Vertrag der Quelle."""

    polnr: int
    status: str            # Nichtraucher | Raucher
    tarifart: str          # Einzel | Kollektiv | Haus
    zw: int
    beginn: dt.date
    scheiben: List[Scheibe]
    vtg_status: str = "AKT"          # AKT | BFR | STO | TOD | ABL
    vtg_status_seit: Optional[dt.date] = None
    vs_bfr_fix: float = 0.0          # bei BFR: fixierte Gesamtsumme
    #: Herabsetzungen (Datum, fortgefuehrter Anteil f) — mehrfach moeglich.
    herabsetzungen: List[Tuple[dt.date, float]] = field(default_factory=list)

    @property
    def tarif(self) -> Tarifzelle:
        return zelle(self.status, self.tarifart)

    @property
    def grund(self) -> Scheibe:
        return self.scheiben[0]

    @property
    def gesamt_vs(self) -> float:
        return sum(s.vs for s in self.scheiben)

    def aktiv(self) -> bool:
        return self.vtg_status in ("AKT", "BFR")

    def beitragspflichtig_am(self, datum: dt.date) -> bool:
        if self.vtg_status != "AKT":
            return False
        return _volle_jahre(self.grund.beginn, datum) < self.grund.t


@dataclass(frozen=True)
class Buchung:
    """Eine Journalzeile der Quelle."""

    polnr: int
    datum: dt.date
    art: str               # ZUG | ERH | PEX | RED | STO | TOD | ABL
    betrag: float
    scheibe: Optional[int] = None


@dataclass(frozen=True)
class Annahmen:
    """Vorfallraten der Fuehrung (je Kalenderjahr und aktivem Vertrag)."""

    tod: float = 0.002
    storno: float = 0.02
    beitragsfreistellung: float = 0.02
    herabsetzung: float = 0.01
    dynamik_annahme: float = 0.7
    dynamik_satz: float = 0.05
    herabsetzungs_anteile: Tuple[float, ...] = (0.5, 0.6, 0.75)


@dataclass(frozen=True)
class Vertriebsplan:
    """Wie die Generation verkauft wird — Ziel sind ~1000 Policen.

    Der Verkauf ist stochastisch je Monat (Poisson-artig ueber eine feste
    Monatsrate); wie viele Vertraege am Ende im Bestand stehen, ergibt
    sich aus Verkauf UND Vorfaellen — keine gesetzte Zahl.
    """

    von: dt.date = dt.date(2015, 1, 1)
    bis: dt.date = dt.date(2016, 12, 1)
    policen_ziel: int = 1000
    erste_polnr: int = 7000001


class Bestandsfuehrung:
    """Das gefuehrte Buch der Quelle: Policen + Journal."""

    def __init__(
        self,
        seed: int,
        *,
        plan: Vertriebsplan = Vertriebsplan(),
        annahmen: Annahmen = Annahmen(),
    ) -> None:
        self.rng = random.Random(seed)
        self.plan = plan
        self.annahmen = annahmen
        self.policen: Dict[int, Police] = {}
        self.journal: List[Buchung] = []

    # -- Verkauf ------------------------------------------------------------ #

    def _neue_police(self, polnr: int, beginn: dt.date) -> Police:
        r = self.rng
        status = "Raucher" if r.random() < 0.25 else "Nichtraucher"
        tarifart = r.choices(
            ("Einzel", "Kollektiv", "Haus"), weights=(40, 35, 25))[0]
        x = r.randint(25, 60)
        n = r.choice((12, 15, 20, 25, 30))
        n = min(n, 70 - x) if 70 - x >= 12 else 12
        t = n if r.random() < 0.6 else max(5, n - r.choice((3, 5, 8)))
        vs = float(round(r.lognormvariate(11.0, 0.45), -3))
        vs = max(10_000.0, min(vs, 500_000.0))
        zw = r.choices((12, 1, 4, 2), weights=(85, 7, 5, 3))[0]
        return Police(
            polnr=polnr, status=status, tarifart=tarifart, zw=zw,
            beginn=beginn,
            scheiben=[Scheibe(nr=0, beginn=beginn, x=x, n=n, t=t, vs=vs)],
        )

    def verkaufe(self) -> None:
        """Das Vertriebsfenster einmal besiedeln (ZUG-Buchungen)."""
        p = self.plan
        monate = ((p.bis.year - p.von.year) * 12
                  + (p.bis.month - p.von.month) + 1)
        rate = p.policen_ziel / monate
        polnr = p.erste_polnr
        for m in range(monate):
            beginn = _monatserster(p.von.year, p.von.month + m)
            # Poisson ueber Bernoulli-Summe (stdlib, deterministisch).
            anzahl = sum(
                1 for _ in range(int(rate * 4) + 8)
                if self.rng.random() < rate / (int(rate * 4) + 8)
            )
            for _ in range(anzahl):
                police = self._neue_police(polnr, beginn)
                self.policen[polnr] = police
                self.journal.append(Buchung(
                    polnr, beginn, "ZUG", _cent(police.gesamt_vs), scheibe=0))
                polnr += 1

    # -- Fuehrung je Kalenderjahr ------------------------------------------- #

    def _bewertung(self, police: Police, datum: dt.date) -> Dict[str, float]:
        """Gesamtwerte am letzten Rechenpunkt VOR ``datum`` (je Scheibe)."""
        werte = {"mrv": 0.0, "rkw_je_scheibe": 0.0, "vs_bfr": 0.0}
        for s in police.scheiben:
            k = _volle_jahre(s.beginn, datum)
            zeile = s.rechnung(police.zw, police.tarif).verlaufszeile(
                min(k, s.n))
            werte["mrv"] += zeile["kVx_MRV_H"]
            # KONVENTION DER QUELLE: StoAb-Grenzen je SCHEIBE.
            werte["rkw_je_scheibe"] += zeile["RKW_K"]
            werte["vs_bfr"] += zeile["VS_bfr_L"]
        return werte

    def fuehre(self, bis: dt.date) -> None:
        """Vorfaelle je Kalenderjahr am 1. Januar pruefen und buchen."""
        a = self.annahmen
        jahr = self.plan.von.year + 1
        while dt.date(jahr, 1, 1) <= bis:
            stichtag = dt.date(jahr, 1, 1)
            for polnr in sorted(self.policen):
                police = self.policen[polnr]
                if not police.aktiv() or police.beginn >= stichtag:
                    continue
                self._fuehre_police(police, stichtag)
            jahr += 1

    def _beende(self, police: Police, datum: dt.date, art: str,
                betrag: float) -> None:
        police.vtg_status = art
        police.vtg_status_seit = datum
        self.journal.append(Buchung(police.polnr, datum, art, _cent(betrag)))

    def _fuehre_police(self, police: Police, stichtag: dt.date) -> None:
        a = self.annahmen
        grund = police.grund
        volle = _volle_jahre(grund.beginn, stichtag)

        # Common Random Numbers: IMMER alle fuenf Draws ziehen, in fester
        # Reihenfolge — dann entscheiden. So bleiben Laeufe mit
        # verschiedenen Annahmen pfadweise vergleichbar, und kein
        # Rueckgabezweig verschiebt den Strom der uebrigen Policen.
        u_tod, u_sto, u_pex, u_red, u_dyn = (
            self.rng.random() for _ in range(5))

        # Ablauf zuerst: mit dem Ende der Grundscheibe endet der Vertrag.
        if volle >= grund.n:
            betrag = (police.vs_bfr_fix if police.vtg_status == "BFR"
                      else police.gesamt_vs)
            self._beende(police, stichtag, "ABL", betrag)
            return

        if u_tod < a.tod:
            betrag = (police.vs_bfr_fix if police.vtg_status == "BFR"
                      else police.gesamt_vs)
            self._beende(police, stichtag, "TOD", betrag)
            return

        bpfl = police.beitragspflichtig_am(stichtag)
        if not bpfl:
            return

        if u_sto < a.storno:
            bewertung = self._bewertung(police, stichtag)
            self._beende(police, stichtag, "STO", bewertung["rkw_je_scheibe"])
            return

        if u_pex < a.beitragsfreistellung:
            bewertung = self._bewertung(police, stichtag)
            police.vtg_status = "BFR"
            police.vtg_status_seit = stichtag
            police.vs_bfr_fix = _cent(bewertung["vs_bfr"])
            self.journal.append(Buchung(
                police.polnr, stichtag, "PEX", police.vs_bfr_fix))
            return

        if u_red < a.herabsetzung:
            self._herabsetzen(police, stichtag)
            return

        if u_dyn < a.dynamik_annahme:
            self._erhoehe(police, stichtag)

    def _erhoehe(self, police: Police, stichtag: dt.date) -> None:
        """Dynamik: neue Scheibe ueber dynamik_satz der Gesamtsumme."""
        grund = police.grund
        a = _volle_jahre(grund.beginn, stichtag)
        rest_n, rest_t = grund.n - a, grund.t - a
        if rest_n < 2 or rest_t < 1:
            return
        betrag = _cent(self.annahmen.dynamik_satz * police.gesamt_vs)
        scheibe = Scheibe(
            nr=len(police.scheiben), beginn=stichtag,
            x=grund.x + a, n=rest_n, t=rest_t, vs=betrag,
        )
        police.scheiben.append(scheibe)
        self.journal.append(Buchung(
            police.polnr, stichtag, "ERH", betrag, scheibe=scheibe.nr))

    def _herabsetzen(self, police: Police, stichtag: dt.date) -> None:
        """RED = Teilkuendigung mit AUSZAHLUNG, nur auf der Grundscheibe.

        Der freiwerdende Reserveanteil der Grundscheibe wird nach
        anteiligem Stornoabzug ausgezahlt; die Grundsumme sinkt auf f,
        die Dynamikscheiben bleiben unberuehrt. Der Vertrag bleibt AKT —
        RED ist ein Geschaeftsvorfall, kein Zustand; danach sind weitere
        Dynamiken, PEX oder eine zweite Herabsetzung moeglich. Gebucht
        wird der AUSZAHLUNGSBETRAG.
        """
        grund = police.grund
        k = _volle_jahre(grund.beginn, stichtag)
        zeile = grund.rechnung(police.zw, police.tarif).verlaufszeile(k)
        f = self.rng.choice(self.annahmen.herabsetzungs_anteile)
        auszahlung = _cent(
            max(0.0, (zeile["kVx_MRV_H"] - zeile["StoAb_J"]) * (1.0 - f)))
        grund.vs = _cent(grund.vs * f)
        police.herabsetzungen.append((stichtag, f))
        self.journal.append(Buchung(
            police.polnr, stichtag, "RED", auszahlung, scheibe=0))


def lauf(seed: int, bis: dt.date, **argumente) -> Bestandsfuehrung:
    """Verkauf plus Fuehrung bis ``bis`` — der eine Einstieg."""
    buch = Bestandsfuehrung(seed, **argumente)
    buch.verkaufe()
    buch.fuehre(bis)
    return buch
