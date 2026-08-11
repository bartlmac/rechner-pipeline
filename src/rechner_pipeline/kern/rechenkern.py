"""Barwerte, Produktlogik und KLV-Zielgrößen — parametrisiert je Modellpunkt.

Formeltreu zum Quell-Workbook (VBA ``mBarwerte`` + Kalkulations-Blatt), aber
ohne Bindung an einen festen Modellpunkt: :class:`Rechenkern` nimmt einen
:class:`~rechner_pipeline.kern.model_point.ModelPoint` und rechnet auf der
zugehörigen (gecachten) Kommutationsbasis. :func:`berechne` liefert das
Ergebnis im Golden-Master-Contract-Format.
"""

from __future__ import annotations

from typing import Dict, List

from rechner_pipeline.kern import kommutation
from rechner_pipeline.kern.konventionen import installment_surcharge
from rechner_pipeline.kern.model_point import KLV_DEFAULT, ModelPoint

#: Verlaufswerte-Zeilen (Blattzeilen 16..66 -> Vertragsjahre 0..50, blattfest).
VERLAUFSJAHRE = 51


class Rechenkern:
    """Alle Kern-Rechnungen für genau einen Modellpunkt."""

    def __init__(self, mp: ModelPoint) -> None:
        self.mp = mp
        self.kom = kommutation.fuer(mp.sex, mp.tafel, mp.zins)

    # ----------------------------------------------------------------- #
    # Barwerte (VBA mBarwerte); Zahlungsordnung k=1 im Blatt durchgängig.
    # ----------------------------------------------------------------- #

    def abzugsglied(self, k: int) -> float:
        """Unterjähriges Korrekturglied (VBA ``Act_Abzugsglied``); 0 für k=1."""
        if k <= 0:
            return 0.0
        zins = self.mp.zins
        total = 0.0
        for step in range(0, k):
            total += (step / k) / (1.0 + (step / k) * zins)
        return total * (1.0 + zins) / k

    def axn_k(self, age: int, term: int, k: int = 1) -> float:
        """Temporäre vorschüssige Rente (VBA ``Act_axn_k``)."""
        if k <= 0:
            return 0.0
        dx = self.kom.Dx_at(age)
        dxt = self.kom.Dx_at(age + term)
        return (self.kom.Nx_at(age) - self.kom.Nx_at(age + term)) / dx - self.abzugsglied(
            k
        ) * (1.0 - dxt / dx)

    def ax_k(self, age: int, k: int = 1) -> float:
        """Lebenslange vorschüssige Rente (VBA ``Act_ax_k``)."""
        if k <= 0:
            return 0.0
        return self.kom.Nx_at(age) / self.kom.Dx_at(age) - self.abzugsglied(k)

    def nGrAx(self, age: int, term: int) -> float:
        """Temporäre Todesfallversicherung (VBA ``Act_nGrAx``)."""
        return (self.kom.Mx_at(age) - self.kom.Mx_at(age + term)) / self.kom.Dx_at(age)

    def nGrEx(self, age: int, term: int) -> float:
        """Erlebensfallversicherung (VBA ``Act_nGrEx``): D_{x+term}/D_x."""
        return self.kom.Dx_at(age + term) / self.kom.Dx_at(age)

    def endowment_benefit_pv(self, age: int, term: int) -> float:
        """Gemischte Versicherung: Todesfall- plus Erlebensfall-Barwert."""
        return self.nGrAx(age, term) + self.nGrEx(age, term)

    # ----------------------------------------------------------------- #
    # Whole-life-Bausteine (Äquivalenzprinzip-Referenz, algebraische Gates).
    # ----------------------------------------------------------------- #

    def Ax(self, age: int) -> float:
        return self.kom.Mx_at(age) / self.kom.Dx_at(age)

    def aex(self, age: int) -> float:
        return self.kom.Nx_at(age) / self.kom.Dx_at(age)

    def pv_benefits(self, age: int) -> float:
        return self.Ax(age)

    def pv_premiums(self, age: int) -> float:
        return self.aex(age)

    def net_premium(self, age: int) -> float:
        return self.pv_benefits(age) / self.pv_premiums(age)

    # ----------------------------------------------------------------- #
    # KLV-Zielgrößen (Kalkulations-Blatt).
    # ----------------------------------------------------------------- #

    def gross_premium_rate(self) -> float:
        """Bxt (K5): Bruttobeitragssatz je Einheit Versicherungssumme."""
        mp = self.mp
        x, n, t = mp.x, mp.n, mp.t
        axt = self.axn_k(x, t, 1)
        axn = self.axn_k(x, n, 1)
        numerator = (
            self.endowment_benefit_pv(x, n)
            + mp.gamma1 * axt
            + mp.gamma2 * (axn - axt)
        )
        denominator = (1.0 - mp.beta1) * axt - mp.alpha * t
        return numerator / denominator

    def gross_annual_premium(self) -> float:
        """BJB (K6): Jahres-Bruttobeitrag = VS * Bxt."""
        return self.mp.sum_insured * self.gross_premium_rate()

    def gross_payable_premium(self) -> float:
        """BZB (K7): Zahlbeitrag = (1+ratzu)/zw * (BJB + k)."""
        mp = self.mp
        ratzu = installment_surcharge(mp.zw)
        return (1.0 + ratzu) / mp.zw * (self.gross_annual_premium() + mp.policy_fee)

    def net_premium_rate(self) -> float:
        """Pxt (K9): Nettobeitragssatz je Einheit Versicherungssumme."""
        mp = self.mp
        x, n, t = mp.x, mp.n, mp.t
        return (
            self.endowment_benefit_pv(x, n) + t * mp.alpha * self.gross_premium_rate()
        ) / self.axn_k(x, t, 1)

    def reserve_row(self, a: int) -> Dict[str, float]:
        """Verlaufswerte-Zeile für Vertragsjahr ``a`` (Blattzeilen 16..66)."""
        mp = self.mp
        x, n, t, vs = mp.x, mp.n, mp.t, mp.sum_insured
        xa = x + a

        pxt = self.net_premium_rate()
        bjb = self.gross_annual_premium()
        axn_full = self.axn_k(x, n, 1)
        axt_full = self.axn_k(x, t, 1)
        a5_full = self.axn_k(x, 5, 1)

        if a <= n:
            axn_benefit = self.endowment_benefit_pv(xa, n - a)
        else:
            axn_benefit = 0.0

        axn = self.axn_k(xa, max(0, n - a), 1)
        axt = self.axn_k(xa, max(0, t - a), 1)

        kvx_bpfl = (
            axn_benefit
            - pxt * axt
            + mp.gamma2 * (axn - (axn_full / axt_full) * axt)
        )
        kdrx_bpfl = vs * kvx_bpfl
        kvx_bfr = axn_benefit + mp.gamma3 * axn
        kvx_mrv = kdrx_bpfl + mp.alpha * t * bjb * self.axn_k(
            xa, max(5 - a, 0), 1
        ) / a5_full

        flex = 1.0 if (xa >= mp.min_alter_flex and a >= n - mp.min_rlz_flex) else 0.0

        if a > n or flex == 1.0:
            stoab = 0.0
        else:
            stoab = min(150.0, max(50.0, 0.01 * (vs - kdrx_bpfl)))

        rkw = max(0.0, kvx_mrv - stoab)

        if a > n:
            vs_bfr = 0.0
        elif a < t:
            vs_bfr = kvx_mrv / kvx_bfr if kvx_bfr else 0.0
        else:
            vs_bfr = float(vs)

        return {
            "k": float(a),
            "Axn": axn_benefit,
            "axn": axn,
            "axt": axt,
            "kVx_bpfl": kvx_bpfl,
            "kDRx_bpfl": kdrx_bpfl,
            "kVx_bfr": kvx_bfr,
            "kVx_MRV": kvx_mrv,
            "flex. Phase": flex,
            "StoAb": stoab,
            "RKW": rkw,
            "VS_bfr": vs_bfr,
        }

    def verlaufswerte(self) -> List[Dict[str, float]]:
        """Alle Verlaufswerte-Zeilen (Vertragsjahre 0..50, blattfest)."""
        return [self.reserve_row(jahr) for jahr in range(0, VERLAUFSJAHRE)]


def berechne(mp: ModelPoint = KLV_DEFAULT) -> Dict[str, Dict]:
    """Golden-Master-Contract-Ergebnis für einen Modellpunkt.

    Gleiches Format wie ``test_run.golden_master_outputs()`` des einmalig
    migrierten Kerns: ``{"scalars": {"Kalkulation": ...}, "tables": ...}``.
    """
    kern = Rechenkern(mp)
    scalars = {
        "Bxt": kern.gross_premium_rate(),
        "BJB": kern.gross_annual_premium(),
        "BZB": kern.gross_payable_premium(),
        "Pxt": kern.net_premium_rate(),
        "ratzu": installment_surcharge(mp.zw),
    }
    return {
        "scalars": {"Kalkulation": scalars},
        "tables": {"Kalkulation": kern.verlaufswerte()},
    }
