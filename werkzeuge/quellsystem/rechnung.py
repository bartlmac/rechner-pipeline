"""Die KLV-Zielgroessen des Quellsystems — VBA-Formeln auf der Kommutation.

Dieselben Tarifformeln, die das Kalkulations-Blatt des Quell-Workbooks
rechnet (Bxt/BJB/BZB/Pxt als Skalare, die Verlaufszeile mit Reserven,
Stornoabzug, Rueckkaufswert und beitragsfreier Summe) — ausgewertet auf
den Kommutations-Barwerten statt in Excel. Golden Master sind die
Excel-Ergebnisse selbst (siehe README und Test).

Betragskonvention der Quelle, AM GOLDEN MASTER KALIBRIERT: Die
Rechenkette laeuft UNGERUNDET; nur die AUSGABEZELLEN in EUR (BJB, BZB,
kDRx, MRV, StoAb, RKW, VS_bfr) rundet das Blatt auf Cent (Excel-Rundung,
half away from zero). Die Saetze (Bxt, Pxt, kVx) bleiben ungerundet.
Eine Ketten-Rundung (jeden Zwischenwert auf Cent) war die erste
Vermutung und ist am Golden Master WIDERLEGT — sie erzeugte 245
Cent-Kipper statt 33. Gebuchte BETRAEGE der Bestandsfuehrung sind
trotzdem Cent: gerundet wird beim Buchen, nicht beim Rechnen.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from quellsystem.barwerte import Barwerte
from quellsystem.kommutation import fuer
from quellsystem.konventionen import excel_round
from quellsystem.tarifwerk import Tarifzelle


def _cent(betrag: float) -> float:
    return excel_round(betrag, 2)


@dataclass(frozen=True)
class Vertrag:
    """Vertragsfelder der Quelle (Blatt-Eingaben)."""

    x: int
    n: int
    t: int
    vs: float
    zw: int


class Rechnung:
    """Zielgroessen fuer genau einen Vertrag in genau einer Tarifzelle."""

    def __init__(self, zelle: Tarifzelle, vertrag: Vertrag) -> None:
        self.zelle = zelle
        self.vertrag = vertrag
        self.bw = Barwerte(fuer("M", zelle.tafel, zelle.zins), zelle.zins)

    # -- Skalare (Blatt K5..K9) ------------------------------------------- #

    def bxt(self) -> float:
        z, v = self.zelle, self.vertrag
        axt = self.bw.axn_k(v.x, v.t, 1)
        axn = self.bw.axn_k(v.x, v.n, 1)
        zaehler = (
            self.bw.endowment_benefit_pv(v.x, v.n)
            + z.gamma1 * axt
            + z.gamma2 * (axn - axt)
        )
        nenner = (1.0 - z.beta1) * axt - z.alpha * v.t
        return zaehler / nenner

    def _bjb_ungerundet(self) -> float:
        return self.vertrag.vs * self.bxt()

    def bjb(self) -> float:
        return _cent(self._bjb_ungerundet())

    def bzb(self) -> float:
        z, v = self.zelle, self.vertrag
        ratzu = z.ratzu.get(v.zw, 0.0)
        return _cent(
            (1.0 + ratzu) / v.zw * (self._bjb_ungerundet() + z.policy_fee)
        )

    def pxt(self) -> float:
        z, v = self.zelle, self.vertrag
        return (
            self.bw.endowment_benefit_pv(v.x, v.n) + v.t * z.alpha * self.bxt()
        ) / self.bw.axn_k(v.x, v.t, 1)

    # -- Verlaufszeile (Blattzeilen) --------------------------------------- #

    def ist_flex_phase(self, a: int) -> bool:
        z, v = self.zelle, self.vertrag
        return v.x + a >= z.min_alter_flex and a >= v.n - z.min_rlz_flex

    def verlaufszeile(self, a: int) -> Dict[str, float]:
        """Die Blattzeile des Vertragsjahres ``a`` (Spalten wie im Export)."""
        z, v = self.zelle, self.vertrag
        x, n, t, vs = v.x, v.n, v.t, v.vs
        xa = x + a

        pxt = self.pxt()
        axn_full = self.bw.axn_k(x, n, 1)
        axt_full = self.bw.axn_k(x, t, 1)
        azd_full = self.bw.axn_k(x, z.zillmer_dauer, 1)

        axn_benefit = (
            self.bw.endowment_benefit_pv(xa, n - a) if a <= n else 0.0
        )
        axn = self.bw.axn_k(xa, max(0, n - a), 1)
        axt = self.bw.axn_k(xa, max(0, t - a), 1)

        kvx_bpfl = (
            axn_benefit
            - pxt * axt
            + z.gamma2 * (axn - (axn_full / axt_full) * axt)
        )
        # Die KETTE bleibt ungerundet (siehe Modul-Docstring); gerundet
        # werden nur die Ausgabezellen am Ende.
        kdrx_u = vs * kvx_bpfl
        kvx_bfr = axn_benefit + z.gamma3 * axn
        mrv_u = (
            kdrx_u
            + z.alpha * t * self._bjb_ungerundet()
            * self.bw.axn_k(xa, max(z.zillmer_dauer - a, 0), 1) / azd_full
        )

        flex = self.ist_flex_phase(a)
        if a > n or flex:
            stoab_u = 0.0
        else:
            stoab_u = min(
                z.stoab_max,
                max(z.stoab_min, z.stoab_satz * (vs - kdrx_u)),
            )
        rkw_u = max(0.0, mrv_u - stoab_u)

        if a > n:
            vs_bfr_u = 0.0
        elif a < t:
            vs_bfr_u = mrv_u / kvx_bfr if kvx_bfr else 0.0
        else:
            vs_bfr_u = float(vs)
        kdrx_bpfl = _cent(kdrx_u)
        kvx_mrv = _cent(mrv_u)
        stoab = _cent(stoab_u)
        rkw = _cent(rkw_u)
        vs_bfr = _cent(vs_bfr_u)

        return {
            "Axn_B": axn_benefit,
            "axn_C": axn,
            "axt_D": axt,
            "kVx_bpfl_E": kvx_bpfl,
            "kDRx_bpfl_F": kdrx_bpfl,
            "kVx_bfr_G": kvx_bfr,
            "kVx_MRV_H": kvx_mrv,
            "flexPhase_I": 1.0 if flex else 0.0,
            "StoAb_J": stoab,
            "RKW_K": rkw,
            "VS_bfr_L": vs_bfr,
        }
