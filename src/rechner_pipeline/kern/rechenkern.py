"""Rechenkern-Fassade: generische Barwerte + Produkt-Zielgrößen je Modellpunkt.

Formeltreu zum Quell-Workbook (VBA ``mBarwerte`` + Kalkulations-Blatt), aber
ohne Bindung an einen festen Modellpunkt. Die Schichten:

* :class:`~rechner_pipeline.kern.barwerte.Barwerte` — produktunabhängige
  Barwert-Bausteine auf der (gecachten) Kommutationsbasis;
* :mod:`rechner_pipeline.kern.produkte` — Produkt-Registry; die KLV-Zielgrößen
  leben in :class:`~rechner_pipeline.kern.produkte.klv.KLV`;
* :class:`Rechenkern` — die stabile öffentliche Fassade über beiden (bisherige
  Methodensignaturen unverändert);
* :func:`berechne` — Golden-Master-Contract-Ergebnis über die Registry.

Knoten: klv, bu
"""

from __future__ import annotations

from typing import Dict, List

from rechner_pipeline.kern.model_point import KLV_DEFAULT, ModelPoint
from rechner_pipeline.kern.produkte import hole
from rechner_pipeline.kern.produkte.klv import (
    KLV,
    VERLAUFSWERTE_SPALTEN,
    Monatsreserve,
    Verlaufszeile,
)

__all__ = [
    "Rechenkern",
    "berechne",
    "VERLAUFSWERTE_SPALTEN",
    "Monatsreserve",
    "Verlaufszeile",
]


class Rechenkern:
    """Alle Kern-Rechnungen für genau einen (KLV-)Modellpunkt — Fassade."""

    def __init__(self, mp: ModelPoint) -> None:
        self.mp = mp
        self.produkt = KLV(mp)
        self.bw = self.produkt.bw
        self.basis = self.produkt.basis

    # -- Barwerte (generische Schicht) --------------------------------- #

    def abzugsglied(self, k: int) -> float:
        return self.bw.abzugsglied(k)

    def axn_k(self, age: int, term: int, k: int = 1) -> float:
        return self.bw.axn_k(age, term, k)

    def ax_k(self, age: int, k: int = 1) -> float:
        return self.bw.ax_k(age, k)

    def nGrAx(self, age: int, term: int) -> float:
        return self.bw.nGrAx(age, term)

    def nGrEx(self, age: int, term: int) -> float:
        return self.bw.nGrEx(age, term)

    def endowment_benefit_pv(self, age: int, term: int) -> float:
        return self.bw.endowment_benefit_pv(age, term)

    def Ax(self, age: int) -> float:
        return self.bw.Ax(age)

    def aex(self, age: int) -> float:
        return self.bw.aex(age)

    def pv_benefits(self, age: int) -> float:
        return self.bw.pv_benefits(age)

    def pv_premiums(self, age: int) -> float:
        return self.bw.pv_premiums(age)

    def net_premium(self, age: int) -> float:
        return self.bw.net_premium(age)

    # -- KLV-Zielgrößen (Produkt-Schicht) ------------------------------ #

    def gross_premium_rate(self) -> float:
        return self.produkt.gross_premium_rate()

    def gross_annual_premium(self) -> float:
        return self.produkt.gross_annual_premium()

    def gross_payable_premium(self) -> float:
        return self.produkt.gross_payable_premium()

    def net_premium_rate(self) -> float:
        return self.produkt.net_premium_rate()

    def reserve_row(self, a: int) -> Dict[str, float]:
        return self.produkt.reserve_row(a)

    def verlaufswerte(self) -> List[Dict[str, float]]:
        return self.produkt.verlaufswerte()

    # -- Ereignis-Anschlüsse ------------------------------------------- #

    def verlaufszeile(self, a: int) -> Verlaufszeile:
        return self.produkt.verlaufszeile(a)

    def zustand_am(self, months_exp: int) -> Verlaufszeile:
        return self.produkt.zustand_am(months_exp)

    def beitragsfreie_summe(self, a0: int) -> float:
        return self.produkt.beitragsfreie_summe(a0)

    def reserve_beitragsfrei(self, a0: int, a: int) -> float:
        return self.produkt.reserve_beitragsfrei(a0, a)

    def monatsreserve(self, monate: int) -> Monatsreserve:
        return self.produkt.monatsreserve(monate)

    def monatsreserve_beitragsfrei(self, a0: int, monate: int) -> float:
        return self.produkt.monatsreserve_beitragsfrei(a0, monate)


def berechne(mp: ModelPoint = KLV_DEFAULT, produkt: str = "klv") -> Dict[str, Dict]:
    """Golden-Master-Contract-Ergebnis für einen Modellpunkt.

    Gleiches Format wie ``test_run.golden_master_outputs()`` des einmalig
    migrierten Kerns: ``{"scalars": {<prefix>: ...}, "tables": {<prefix>: ...}}``.
    Der Prefix ist Produktattribut (KLV: ``"Kalkulation"``, der Blattname des
    Quell-Workbooks), kein Literal mehr.
    """
    cls = hole(produkt)
    instanz = cls(mp)
    return {
        "scalars": {cls.contract_prefix: instanz.scalars()},
        # Das Verlaufsfenster ist Produkt-Contract (KLV: 0..50 aus dem
        # historischen Sechs-Datei-Vergleichskern, BU: 0..n) — Eigenschaft
        # dieser Vergleichs-View, KEIN Kern-Anker (Kern 3.0.0: der Verlauf
        # selbst ist modellpunktgetrieben).
        "tables": {
            cls.contract_prefix: instanz.verlaufswerte(
                bis=cls.contract_verlauf_bis
            )
        },
    }
