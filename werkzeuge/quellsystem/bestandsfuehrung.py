"""Die Bestandsfuehrung der Quelle: Verkauf, Vorfaelle, Journal.

Das Quellsystem VERKAUFT Policen (Neugeschaeft ueber das
Vertriebsfenster der Generation) und fuehrt sie danach ueber die Jahre:
Dynamik-Erhoehungen, Beitragsfreistellungen, Herabsetzungen, Storni,
Tode, Ablaeufe — MEHRERE Vorfaelle je Vertrag, mit Datum im Journal.
Der Bestand zu einem Stichtag ist damit das ERGEBNIS der Fuehrung, keine
gesetzte Zahl.

Konventionen der Quelle (bewusst anders als das Zielsystem; genehmigt
2026-08-31, praezisiert am Golden Master):

* **Jahres-Batch**: Die Quelle verarbeitet je KALENDERJAHR einen
  Batchlauf, gebucht wird aber am VERTRAGSJAHRESTAG des jeweiligen
  Vertrags (so belegt es die versionierte Alt-Lieferung: PEX am 01.02.,
  STO am 01.04.). Am Jahrestag ist das Vertragsjahr voll — die
  Bewertung faellt exakt auf einen Rechenpunkt des Blatts, und die
  gelieferten t_a liegen auf dem Jahresgitter. Die KALENDERJAHRES-
  Eigenheit der Quelle steckt woanders: in der Altersermittlung
  (rechnungsmaessiges Alter = Differenz der Kalenderjahre, siehe
  Geburtsdatum).
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


def _jahrestag(beginn: dt.date, jahr: int) -> dt.date:
    return dt.date(beginn.year + jahr, beginn.month, 1)


@dataclass
class Scheibe:
    """Eine Schicht des Vertrags — Grundscheibe oder Dynamik-Erhoehung."""

    nr: int
    beginn: dt.date
    x: int
    n: int
    t: int
    vs: float
    #: Bei Beitragsfreistellung: die je Scheibe fixierte beitragsfreie
    #: Summe (die Quelle fuehrt und bewertet je Baustein, AVB Ziffer 5).
    vs_bfr: Optional[float] = None
    #: Ursprungssumme bei Anlage. ``vs`` mutiert bei Herabsetzungen; fuer
    #: rueckwirkende Stichtage (Export) wird die Summe aus ``vs0`` und der
    #: Herabsetzungskette der Police rekonstruiert — mit derselben
    #: Cent-Rundung je Schritt, also exakt der gebuchte Wert.
    vs0: float = 0.0

    def __post_init__(self) -> None:
        if self.vs0 == 0.0:
            self.vs0 = self.vs

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
    geschlecht: str = "M"          # M | W (Lieferspalte GESCHL)
    #: Kalenderjahres-Konvention der Quelle: das rechnungsmaessige
    #: Eintrittsalter ist die DIFFERENZ DER KALENDERJAHRE von Beginn und
    #: Geburt. Monat und Tag sind frei — beim vollendeten Alter des
    #: Zielsystems weicht dadurch ein Teil der Vertraege um 1 ab. Das
    #: ist die Konvention aus der Zeichenerklaerung der Meldung, keine
    #: Regie-Manipulation der Daten.
    geburtsdatum: Optional[dt.date] = None
    #: Dynamik ist VERTRAGSBESTANDTEIL (Einschluss bei Antrag), kein
    #: Zufall je Jahr: Nur eingeschlossene Vertraege erhalten Angebote,
    #: diese nehmen serienweise an (dynamik_annahme je Jahr). So gibt es
    #: beides — Dynamikserien UND Vertraege ganz ohne Vorgeschichte. Der
    #: Einschluss steht nicht im Bestandsabzug; das aufnehmende
    #: Unternehmen sieht nur die gebuchten Erhoehungen.
    dynamik_einschluss: bool = True
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
    #: Wirkung des Vorfalls auf das Deckungskapital (nachher - vorher),
    #: festgehalten IM MOMENT der Buchung — dort ist der Vor-Zustand noch
    #: greifbar. Terminale Vorfaelle raeumen die Reserve (negativ), eine
    #: Dynamik traegt am Buchungstag noch keine (0.00). Die Erwartungs-
    #: werte der Lieferung (dDK des Geschaeftsvorfalltests) lesen genau
    #: dieses Feld.
    dk_delta: float = 0.0


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
        geburt = dt.date(beginn.year - x, r.randint(1, 12), r.randint(1, 28))
        return Police(
            polnr=polnr, status=status, tarifart=tarifart, zw=zw,
            beginn=beginn,
            scheiben=[Scheibe(nr=0, beginn=beginn, x=x, n=n, t=t, vs=vs)],
            geschlecht="M" if r.random() < 0.5 else "W",
            geburtsdatum=geburt,
            dynamik_einschluss=r.random() < 0.6,
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
        """Gesamtwerte am Rechenpunkt ``datum`` (je Scheibe versetzt).

        Am Vertragsjahrestag ist das Vertragsjahr jeder Scheibe voll —
        die Werte fallen exakt auf Blattzeilen. Bei einem beitragsfrei
        gestellten Vertrag laeuft je Scheibe ihre fixierte beitragsfreie
        Summe auf dem beitragsfreien Reservesatz weiter.
        """
        werte = {"mrv": 0.0, "rkw_je_scheibe": 0.0, "vs_bfr": 0.0,
                 "vs_bfr_je_scheibe": []}
        for s in police.scheiben:
            k = min(_volle_jahre(s.beginn, datum), s.n)
            zeile = s.rechnung(police.zw, police.tarif).verlaufszeile(k)
            if s.vs_bfr is not None:
                werte["mrv"] += _cent(s.vs_bfr * zeile["kVx_bfr_G"])
            else:
                werte["mrv"] += zeile["kVx_MRV_H"]
            # KONVENTION DER QUELLE: StoAb-Grenzen je SCHEIBE.
            werte["rkw_je_scheibe"] += zeile["RKW_K"]
            werte["vs_bfr"] += zeile["VS_bfr_L"]
            werte["vs_bfr_je_scheibe"].append(zeile["VS_bfr_L"])
        return werte

    def fuehre(self, bis: dt.date) -> None:
        """Jahres-Batch: je Kalenderjahr, gebucht am Vertragsjahrestag."""
        jahr = self.plan.von.year + 1
        while dt.date(jahr, 1, 1) <= bis:
            for polnr in sorted(self.policen):
                police = self.policen[polnr]
                volle = jahr - police.beginn.year
                if volle < 1 or not police.aktiv():
                    continue
                jahrestag = _jahrestag(police.beginn, volle)
                if jahrestag > bis:
                    continue
                self._fuehre_police(police, jahrestag, volle)
            jahr += 1

    def _beende(self, police: Police, datum: dt.date, art: str,
                betrag: float) -> None:
        # Ein terminaler Vorfall raeumt die gefuehrte Reserve: dk_delta
        # ist -MRV am Buchungstag (bei TOD/ABL verschieden von der
        # AUSZAHLUNG, die die Versicherungssumme ist).
        mrv = self._bewertung(police, datum)["mrv"]
        police.vtg_status = art
        police.vtg_status_seit = datum
        self.journal.append(Buchung(
            police.polnr, datum, art, _cent(betrag),
            dk_delta=_cent(-mrv)))

    def _fuehre_police(self, police: Police, stichtag: dt.date,
                       volle: int) -> None:
        a = self.annahmen
        grund = police.grund

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
            for s, vs_bfr in zip(police.scheiben,
                                 bewertung["vs_bfr_je_scheibe"]):
                s.vs_bfr = _cent(vs_bfr)
            police.vs_bfr_fix = _cent(bewertung["vs_bfr"])
            # Nach der Umstellung laeuft je Scheibe die fixierte Summe auf
            # dem beitragsfreien Reservesatz; die Differenz zur bisherigen
            # MRV ist die DK-Wirkung der Freistellung (Abzug je Baustein).
            nachher = self._bewertung(police, stichtag)["mrv"]
            self.journal.append(Buchung(
                police.polnr, stichtag, "PEX", police.vs_bfr_fix,
                dk_delta=_cent(nachher - bewertung["mrv"])))
            return

        if u_red < a.herabsetzung:
            self._herabsetzen(police, stichtag)
            return

        if police.dynamik_einschluss and u_dyn < a.dynamik_annahme:
            self._erhoehe(police, stichtag)

    def _erhoehe(self, police: Police, stichtag: dt.date) -> None:
        """Dynamik: neue Scheibe ueber dynamik_satz der Gesamtsumme.

        Restlaufzeiten unter der Zillmerdauer (5 Jahre) sind nach den
        Tarifbestimmungen (Ziffer 3) ausgeschlossen: Die VBA-Formel
        amortisiert die Abschlusskosten stur ueber die Zillmerdauer —
        ein kuerzerer Baustein truege am Ablauf mehr Reserve als Summe.
        Das Blatt wurde nie mit solchen Scheiben betrieben, die Fuehrung
        erzeugt sie deshalb auch nicht.
        """
        grund = police.grund
        a = _volle_jahre(grund.beginn, stichtag)
        rest_n, rest_t = grund.n - a, grund.t - a
        if rest_n < 5 or rest_t < 1:
            return
        betrag = _cent(self.annahmen.dynamik_satz * police.gesamt_vs)
        scheibe = Scheibe(
            nr=len(police.scheiben), beginn=stichtag,
            x=grund.x + a, n=rest_n, t=rest_t, vs=betrag,
        )
        police.scheiben.append(scheibe)
        # Die neue Scheibe steht am Buchungstag im Vertragsjahr 0 ihres
        # eigenen Blatts — dort traegt sie noch keine Reserve.
        delta = scheibe.rechnung(police.zw, police.tarif).verlaufszeile(
            0)["kVx_MRV_H"]
        self.journal.append(Buchung(
            police.polnr, stichtag, "ERH", betrag, scheibe=scheibe.nr,
            dk_delta=_cent(delta)))

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
        # DK-Wirkung: nur die Grundscheibe aendert sich; ihr Blatt wird
        # mit der herabgesetzten Summe neu gelesen (keine Linearitaets-
        # Annahme — der Betrag kommt aus der Rechnung, nicht aus f).
        neu = grund.rechnung(police.zw, police.tarif).verlaufszeile(k)
        self.journal.append(Buchung(
            police.polnr, stichtag, "RED", auszahlung, scheibe=0,
            dk_delta=_cent(neu["kVx_MRV_H"] - zeile["kVx_MRV_H"])))


def lauf(seed: int, bis: dt.date, **argumente) -> Bestandsfuehrung:
    """Verkauf plus Fuehrung bis ``bis`` — der eine Einstieg."""
    buch = Bestandsfuehrung(seed, **argumente)
    buch.verkaufe()
    buch.fuehre(bis)
    return buch
