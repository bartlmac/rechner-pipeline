"""BU-Produkt (selbständige Berufsunfähigkeitsversicherung, Beispielprodukt).

Das zweite Produkt des Kerns — und das erste, das AUSSCHLIESSLICH als
Konfiguration des Zustandsmodell-Rückgrats existiert (keine eigene Engine,
keine Kommutations-Spalten): drei Zustände (aktiv / bu / tot), Übergänge aus
vier Ausscheideordnungen, Bewertung über die Thiele-Rekursion.

Fachliches Modell (bewusst einfach gehaltenes Beispielprodukt):

* Leistungen: jährliche BU-Rente (vorschüssig, solange ``bu``, längstens bis
  Ablauf) mit impliziter Beitragsbefreiung (Beiträge nur im Zustand
  ``aktiv``). Keine Karenz, keine Leistungsdynamik, keine Kosten außer einem
  proportionalen Zuschlag (Brutto = Netto * (1 + zuschlag)).
* Übergänge: aktiv->bu Invalidisierung ``i_x`` (Alterstafel), aktiv->tot
  Aktivensterblichkeit ``q^a_x`` (Sterbetafel), bu->aktiv Reaktivierung
  ``r(x, d)`` und bu->tot Invalidensterblichkeit ``q^i(x, d)`` — beide
  SELECT-Tafeln (dauerabhängig, Semi-Markov über die
  Zustandsraum-Erweiterung der Engine).
* Nettobeitrag über das Äquivalenzprinzip: ``p * Prämienbarwert ==
  Rente * Leistungsbarwert`` (beide ab Zustand ``aktiv`` gerechnet); per
  Konstruktion ist die Anfangsreserve V_aktiv(0) = 0.

WICHTIG (Tafel-Provenienz): Die mitgelieferten ``SYNTH_BU_*``-Tafeln sind
SYNTHETISCHE Platzhalter (glatte, plausible Verläufe) für das
Beispielprodukt — KEINE DAV-Tafeln. Für den produktiven Einsatz sind die
DAV-BU-Ausscheideordnungen (DAV 1997 I/RI/TI bzw. aktuellere) zu beschaffen
und mit Provenienz in ``tafeln.xml`` einzupflegen; das Tafelformat
(Select-Tafeln mit ``dauer``-Attribut) ist dafür vorbereitet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from rechner_pipeline.kern import kommutation
from rechner_pipeline.kern.kommutation import (
    MissingMortalityTableError,
    select_max_dauer,
    select_tafel,
)
from rechner_pipeline.kern.zustandsmodell import Zustandsmodell


@dataclass(frozen=True)
class BUModelPoint:
    """Ein BU-Vertrag als Kern-Input (Beispielprodukt)."""

    x: int                 # Eintrittsalter
    sex: str               # "M" oder "F" (wirkt auf die Aktivensterblichkeit)
    n: int                 # Versicherungs- = Beitragsdauer in Jahren
    bu_rente: float        # jaehrliche BU-Rente
    zins: float            # Rechnungszins
    tafel_aktiv: str = "DAV2008_T"     # Aktivensterblichkeit
    tafel_i: str = "SYNTH_BU_I"        # Invalidisierung (Alterstafel)
    tafel_ri: str = "SYNTH_BU_RI"      # Reaktivierung (Select-Tafel)
    tafel_ti: str = "SYNTH_BU_TI"      # Invalidensterblichkeit (Select-Tafel)
    zuschlag: float = 0.05             # Brutto = Netto * (1 + zuschlag)


#: Beispiel-Modellpunkt des BU-Beispielprodukts (synthetische Tafeln!).
BU_BEISPIEL = BUModelPoint(x=35, sex="M", n=30, bu_rente=12000.0, zins=0.0175)

AKTIV = "aktiv"
BU_ZUSTAND = "bu"
TOT = "tot"


class BU:
    """BU-Zielgrößen für genau einen Modellpunkt (Zustandsmodell-Konfiguration)."""

    kennung = "bu"
    contract_prefix = "BU"
    model_point_cls = BUModelPoint

    def __init__(self, mp: BUModelPoint) -> None:
        if mp.bu_rente <= 0.0:
            raise ValueError(f"bu_rente {mp.bu_rente} <= 0")
        if mp.zuschlag < 0.0:
            raise ValueError(f"zuschlag {mp.zuschlag} < 0")
        if mp.n < 1:
            raise ValueError(f"n {mp.n} < 1")
        self.mp = mp
        # Ausscheideordnungen (fail-fast bei fehlenden Tafeln):
        self._qa = kommutation.fuer(mp.sex, mp.tafel_aktiv, mp.zins)
        self._i = {
            alter: wert
            for alter, wert in enumerate(kommutation.qx_vector(mp.sex, mp.tafel_i))
        }
        self._ri = select_tafel(mp.tafel_ri)
        self._ti = select_tafel(mp.tafel_ti)
        # Ungleiche Select-Perioden waeren still verworfene Tafeldaten
        # (Ultimate-Bereich der laengeren Tafel bliebe unerreichbar) —
        # fail-fast statt stiller min()-Kappung (Review-Fix). Ein
        # DAV-Import mit ungleichen Perioden braucht eine bewusste
        # Produkt-Erweiterung.
        ri_dauer = select_max_dauer(mp.tafel_ri)
        ti_dauer = select_max_dauer(mp.tafel_ti)
        if ri_dauer != ti_dauer:
            raise ValueError(
                f"Select-Perioden ungleich: {mp.tafel_ri} = {ri_dauer}, "
                f"{mp.tafel_ti} = {ti_dauer} — Tafeln auf eine gemeinsame "
                "Periode bringen"
            )
        self.modell = Zustandsmodell(
            (AKTIV, BU_ZUSTAND, TOT), mp.zins, self._uebergang,
            max_dauer=ri_dauer,
        )
        self._scalar_cache: Dict[str, float] = {}
        self._verlauf_cache: Dict[str, list] = {}

    def _select(self, tafel: Dict, name: str, alter: int, dauer: int) -> float:
        wert = tafel.get((alter, dauer))
        if wert is None:
            raise MissingMortalityTableError(
                f"Select-Tafel {name!r}: Alter {alter}, Dauer {dauer} fehlt"
            )
        return wert

    def _uebergang(self, von: str, nach: str, alter: int, dauer: int) -> float:
        if von == AKTIV and nach == BU_ZUSTAND:
            wert = self._i.get(alter)
            if wert is None:
                raise IndexError(
                    f"Alter {alter} ausserhalb des Tafelbereichs [0, 123]"
                )
            return wert
        if von == AKTIV and nach == TOT:
            return self._qa.qx_at(alter)
        if von == BU_ZUSTAND and nach == AKTIV:
            return self._select(self._ri, self.mp.tafel_ri, alter, dauer)
        if von == BU_ZUSTAND and nach == TOT:
            return self._select(self._ti, self.mp.tafel_ti, alter, dauer)
        return 0.0

    # ----------------------------------------------------------------- #
    # Zahlungsprofile (je Einheit Jahresrente bzw. Jahresbeitrag).
    # ----------------------------------------------------------------- #

    @staticmethod
    def _bu_rente_zahlung(zustand: str, jahr: int) -> float:
        return 1.0 if zustand == BU_ZUSTAND else 0.0

    @staticmethod
    def _praemien_zahlung(zustand: str, jahr: int) -> float:
        return 1.0 if zustand == AKTIV else 0.0

    def _verlauf(self, art: str, startzustand: str, start_dauer: int = 0) -> list:
        """Wertespalte je (Zahlungsart, Startzustand, Startdauer), gecacht."""
        key = f"{art}:{startzustand}:{start_dauer}"
        werte = self._verlauf_cache.get(key)
        if werte is None:
            zahlung = (
                self._bu_rente_zahlung if art == "leistung" else self._praemien_zahlung
            )
            werte = self.modell.barwert_verlauf(
                startzustand, self.mp.x, self.mp.n,
                zahlung_zustand=zahlung, start_dauer=start_dauer,
            )
            self._verlauf_cache[key] = werte
        return werte

    # ----------------------------------------------------------------- #
    # Zielgrößen.
    # ----------------------------------------------------------------- #

    def leistungsbarwert(self) -> float:
        """Barwert der BU-Rente von 1 p. a. ab Zustand ``aktiv`` (Jahr 0)."""
        return self._verlauf("leistung", AKTIV)[0]

    def praemienbarwert(self) -> float:
        """Barwert einer Beitragszahlung von 1 p. a. solange ``aktiv``."""
        return self._verlauf("praemie", AKTIV)[0]

    def netto_rate(self) -> float:
        """Nettobeitragssatz je Einheit Jahresrente (Äquivalenzprinzip)."""
        praemienbarwert = self.praemienbarwert()
        if praemienbarwert <= 0.0:
            raise ValueError(
                f"Prämienbarwert {praemienbarwert} <= 0 — Modellpunkt nicht tarifierbar"
            )
        leistungsbarwert = self.leistungsbarwert()
        if leistungsbarwert <= 0.0:
            raise ValueError(
                "Leistungsbarwert <= 0 — im Jahresmodell beginnt die BU-Rente "
                f"fruehestens am Jahrestag 1; n = {self.mp.n} bietet keine "
                "Leistungsmoeglichkeit (nicht tarifierbar)"
            )
        return leistungsbarwert / praemienbarwert

    def nettobeitrag(self) -> float:
        return self._cached("Nettobeitrag", lambda: self.mp.bu_rente * self.netto_rate())

    def bruttobeitrag(self) -> float:
        return self.nettobeitrag() * (1.0 + self.mp.zuschlag)

    def _cached(self, name: str, rechne) -> float:
        if name not in self._scalar_cache:
            self._scalar_cache[name] = rechne()
        return self._scalar_cache[name]

    def reserve_aktiv(self, a: int) -> float:
        """Deckungsrückstellung im Vertragsjahr ``a``, Zustand ``aktiv``.

        Prospektiv (Thiele): Leistungsbarwert minus Barwert künftiger
        Nettobeiträge; per Äquivalenzprinzip ist ``reserve_aktiv(0) == 0``
        (bis auf Float-Epsilon).
        """
        self._pruefe_jahr(a)
        return (
            self.mp.bu_rente * self._verlauf("leistung", AKTIV)[a]
            - self.nettobeitrag() * self._verlauf("praemie", AKTIV)[a]
        )

    def reserve_bu(self, a: int, dauer: int = 0) -> float:
        """Deckungsrückstellung im Vertragsjahr ``a``, Zustand ``bu``.

        ``dauer`` = volle Jahre in BU. Fachliche Grenze (Review-Fix):
        frühester BU-Eintritt ist das Jahresende von Jahr 0, also gilt
        ``dauer <= a - 1`` (``a = 0`` nur als hypothetischer Eintrittswert
        mit ``dauer = 0``); unmögliche Kombinationen sind fail-fast statt
        still plausibler Werte. Oberhalb der Select-Periode wird auf deren
        Ultimate-Stufe gekappt — der Anschlusspunkt der Ereignis-Engine
        für BU-Bestände.
        """
        self._pruefe_jahr(a)
        if dauer < 0 or dauer > max(0, a - 1):
            raise ValueError(
                f"BU-Dauer {dauer} im Vertragsjahr {a} fachlich unmoeglich "
                "(fruehester BU-Eintritt: Jahresende von Jahr 0 -> "
                "dauer <= a - 1)"
            )
        dauer = min(dauer, self.modell.max_dauer)
        leistung = self._verlauf("leistung", BU_ZUSTAND, dauer)[a]
        praemie = self._verlauf("praemie", BU_ZUSTAND, dauer)[a]
        return self.mp.bu_rente * leistung - self.nettobeitrag() * praemie

    def _pruefe_jahr(self, a: int) -> None:
        if not 0 <= a <= self.mp.n:
            raise ValueError(f"Vertragsjahr {a} ausserhalb 0..{self.mp.n}")

    # ----------------------------------------------------------------- #
    # Golden-Contract (Registry-Schnittstelle wie KLV).
    # ----------------------------------------------------------------- #

    def scalars(self) -> Dict[str, float]:
        return {
            "Nettobeitrag": self.nettobeitrag(),
            "Bruttobeitrag": self.bruttobeitrag(),
            "Leistungsbarwert": self.mp.bu_rente * self.leistungsbarwert(),
            "Praemienbarwert": self.praemienbarwert(),
        }

    def verlaufswerte(self) -> List[Dict[str, float]]:
        return [
            {
                "jahr": float(a),
                "V_aktiv": self.reserve_aktiv(a),
                "V_bu": self.reserve_bu(a, 0),
            }
            for a in range(0, self.mp.n + 1)
        ]
