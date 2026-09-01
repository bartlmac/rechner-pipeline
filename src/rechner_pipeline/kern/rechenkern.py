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

import dataclasses
from typing import Dict, List, Sequence, Tuple

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
    "erhoehungs_scheibe",
    "vertrags_monatsreserve",
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


def erhoehungs_scheibe(
    mp: ModelPoint, jahr: int, vs: float, *, gamma1_uebernehmen: bool = False
) -> ModelPoint:
    """Modellpunkt einer dynamischen Erhöhungsscheibe.

    Eigene Scheibe mit versetzten Dauern (x+jahr, n-jahr, t-jahr) und der
    Erhöhungssumme. Ob die Scheibe ``gamma1`` trägt, ist eine
    TARIFWERKS-EIGENSCHAFT DER JEWEILIGEN LIEFERUNG, keine Konstante —
    das hat der zweite Baldrian-Lauf gezeigt (2026-09-01, bit-stabiler
    BJB-Fehlbetrag über beide Stichtage):

    * Vorgabe ``gamma1_uebernehmen=False`` (Bestandsverhalten): die
      Bezugsgröße für γ1 bleibt die GrundVS — so stand es in der
      Tarifmitteilung der ERSTEN Lieferung, und so rechnet das eigene
      Neugeschäft der PLV.
    * ``gamma1_uebernehmen=True``: die Scheibe rechnet die VOLLE
      Beitragsformel inklusive γ1 — so bestimmt es das Bedingungswerk
      der ZWEITEN Lieferung ("eigenständiger Baustein mit eigener
      Wertermittlung"). Die Prüfstrecke der Migration setzt den
      Parameter nach der dokumentierten Quell-Lage; er wird nie
      geraten.
    """
    if not 0 < jahr < mp.t:
        raise ValueError(
            f"Erhöhung im Jahr {jahr}: nur auf dem beitragspflichtigen "
            f"Track möglich (0 < jahr < t = {mp.t})"
        )
    return dataclasses.replace(
        mp, x=mp.x + jahr, n=mp.n - jahr, t=mp.t - jahr,
        sum_insured=vs, gamma1=mp.gamma1 if gamma1_uebernehmen else 0.0,
    )


def vertrags_monatsreserve(
    grund: Rechenkern,
    scheiben: Sequence[Tuple[int, Rechenkern]],
    monate: int,
    *,
    stoab_je_baustein: bool = False,
) -> Monatsreserve:
    """Vertragsweite Monatsreserve über Grund- und Erhöhungsscheiben.

    Reserven (DR, MRV) sind die Summe der Scheibenwerte, jede Scheibe an
    ihrem versetzten Monats-Stichtag. WO die Stornoabschlag-Grenzen des
    Tarifwerks greifen, ist eine TARIFWERKS-EIGENSCHAFT DER JEWEILIGEN
    LIEFERUNG, keine Konstante — das hat der zweite Baldrian-Lauf
    gezeigt (2026-09-01, RKW-Residuen in Vielfachen der Grenzbeträge):

    * Vorgabe ``stoab_je_baustein=False`` (Bestandsverhalten): die
      Grenzen gelten je VERTRAG, einmal auf die Gesamtwerte gerechnet
      (Tarifplan 6, vgl. den vertragsweiten RKW der Fortschreibung).
    * ``stoab_je_baustein=True``: der Abzug wird je BAUSTEIN gesondert
      erhoben — Grundversicherung und jede Erhöhungsscheibe einzeln,
      jeweils mit Mindest- und Höchstbetrag, jeweils mit der eigenen
      Ablauf-/Flexphasen-Prüfung am versetzten Stichtag — und der
      Rückkaufswert des Vertrags ist die SUMME der auf null begrenzten
      Baustein-Rückkaufswerte (Bedingungswerk der zweiten
      Baldrian-Lieferung, Ziffer 4). ``rkw`` ist dann bewusst NICHT
      ``max(0, vx_mrv - stoab)``: Ein Baustein, dessen Reserve unter
      dem Mindestabzug liegt, klemmt bei null und subventioniert die
      anderen nicht. Die Prüfstrecke der Migration setzt den Parameter
      nach der dokumentierten Quell-Lage; er wird nie geraten.

    Ohne Scheiben und mit Vorgabe ist das Ergebnis identisch zu
    :meth:`Rechenkern.monatsreserve`.
    """
    teile: List[Tuple[int, Rechenkern]] = [(0, grund)] + list(scheiben)
    stuecke: List[Tuple[Rechenkern, int, Monatsreserve]] = []
    dr = mrv = 0.0
    for erh_jahr, kern in teile:
        versetzt = monate - 12 * erh_jahr
        if versetzt < 0:
            raise ValueError(
                f"Erhöhungsscheibe aus Jahr {erh_jahr} existiert am "
                f"Monats-Stichtag {monate} noch nicht"
            )
        reserve = kern.monatsreserve(versetzt)
        dr += reserve.drx_bpfl
        mrv += reserve.vx_mrv
        stuecke.append((kern, versetzt, reserve))
    a = monate // 12
    if stoab_je_baustein:
        stoab = rkw = 0.0
        for kern, versetzt, reserve in stuecke:
            mp_k = kern.mp
            a_k = versetzt // 12
            if a_k > mp_k.n or kern.produkt.ist_flex_phase(a_k):
                teil_stoab = 0.0
            else:
                teil_stoab = min(
                    mp_k.stoab_max,
                    max(mp_k.stoab_min,
                        mp_k.stoab_satz
                        * (mp_k.sum_insured - reserve.drx_bpfl)))
            stoab += teil_stoab
            rkw += max(0.0, reserve.vx_mrv - teil_stoab)
    else:
        mp = grund.mp
        if a > mp.n or grund.produkt.ist_flex_phase(a):
            stoab = 0.0
        else:
            vs = sum(kern.mp.sum_insured for _, kern in teile)
            stoab = min(mp.stoab_max,
                        max(mp.stoab_min, mp.stoab_satz * (vs - dr)))
        rkw = max(0.0, mrv - stoab)
    return Monatsreserve(
        monate=monate, jahr=a, monatsanteil=(monate % 12) / 12.0,
        drx_bpfl=dr, vx_mrv=mrv, stoab=stoab, rkw=rkw,
    )


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
        # dieser Vergleichs-View, KEIN Referenzwert des Kerns (Kern 3.0.0: der Verlauf
        # selbst ist modellpunktgetrieben).
        "tables": {
            cls.contract_prefix: instanz.verlaufswerte(
                bis=cls.contract_verlauf_bis
            )
        },
    }
