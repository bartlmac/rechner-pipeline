"""KLV-Produkt: Zielgrößen des Kalkulations-Blatts (gemischte Versicherung).

Alle KLV-spezifische Logik des promoteten Kerns an einem Ort: Beitragssätze
(Bxt/BJB/BZB/Pxt), Verlaufswerte (Reserven, Rückkauf, flexible Phase) und die
darauf aufbauenden Ereignis-Anschlüsse (Stichtags-Zustand, Beitragsfreistellung).
Formeltreu zum Quell-Workbook — die Formeln sind unverändert aus
``rechenkern.py`` hierher gezogen (Code-Motion); Tarifwerk-Stellschrauben
(Stornoabschlag, Zillmer-Dauer, Ratenzuschlag-Staffel) kommen aus dem
:class:`~rechner_pipeline.kern.model_point.ModelPoint` statt als Literale im
Formelblock zu stehen.

Zwei Sichten auf eine Verlaufszeile:

* :class:`Verlaufszeile` — typisierte fachliche API (Ereignis-Engine,
  Fortschreibung); Feldnamen sind Python-Namen.
* :meth:`Verlaufszeile.als_blattzeile` — die Golden-Master-View mit den
  Blatt-Keys (inkl. ``"flex. Phase"``); Wert-für-Wert identisch.

Knoten: klv
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from rechner_pipeline.kern import tafeln
from rechner_pipeline.kern.tafeln import TafelBereichError
from rechner_pipeline.kern.konventionen import installment_surcharge
from rechner_pipeline.kern.model_point import ModelPoint
from rechner_pipeline.kern.zustandsmodell import ZustandsBarwerte

#: Default-Verlaufshorizont: bis Vertragsende (Vertragsjahre 0..n).
#: Jenseits von n sind die Zeilen ueber die Blattregeln definiert
#: (Reserven/RKW 0, flexible Phase) — der Kern rechnet sie auf Anfrage
#: bis zur Tafel-Erschoepfung (fail-fast), ein blattfester 0..50-Deckel
#: existiert seit 3.0.0 nicht mehr (Beschluss Bartek 2026-08-16).

#: Golden-Master-View-Spalten (Blatt-Keys) — einzige Definitionsstelle.
VERLAUFSWERTE_SPALTEN = (
    "k", "Axn", "axn", "axt", "kVx_bpfl", "kDRx_bpfl", "kVx_bfr",
    "kVx_MRV", "flex. Phase", "StoAb", "RKW", "VS_bfr",
)


@dataclass(frozen=True)
class Verlaufszeile:
    """Eine Verlaufswerte-Zeile, typisiert (Blatt-Key in Klammern).

    ``vx_bpfl``/``vx_bfr`` sind Sätze je VS-Einheit, ``drx_bpfl``/``vx_mrv``
    absolute Beträge — die Blatt-Keys (``kVx_*``) unterscheiden das nicht.
    """

    jahr: int                 # "k" (im Blatt als float)
    leistungsbarwert: float   # "Axn"
    axn: float                # "axn"
    axt: float                # "axt"
    vx_bpfl: float            # "kVx_bpfl"  Satz je VS-Einheit
    drx_bpfl: float           # "kDRx_bpfl" Betrag
    vx_bfr: float             # "kVx_bfr"   Satz je VS-Einheit
    vx_mrv: float             # "kVx_MRV"   Betrag (inkl. Zillmer-Tilgung)
    flex_phase: bool          # "flex. Phase" (im Blatt 0.0/1.0)
    stoab: float              # "StoAb"
    rkw: float                # "RKW"
    vs_bfr: float             # "VS_bfr"    beitragsfreie Summe (Betrag)

    def als_blattzeile(self) -> Dict[str, float]:
        """Golden-Master-View: exakt die Blatt-Keys und -Werte."""
        return {
            "k": float(self.jahr),
            "Axn": self.leistungsbarwert,
            "axn": self.axn,
            "axt": self.axt,
            "kVx_bpfl": self.vx_bpfl,
            "kDRx_bpfl": self.drx_bpfl,
            "kVx_bfr": self.vx_bfr,
            "kVx_MRV": self.vx_mrv,
            "flex. Phase": 1.0 if self.flex_phase else 0.0,
            "StoAb": self.stoab,
            "RKW": self.rkw,
            "VS_bfr": self.vs_bfr,
        }


@dataclass(frozen=True)
class Monatsreserve:
    """Reserven an einem Monats-Stichtag zwischen zwei Vertragsjahrestagen.

    Bilanzierungskonvention: die Betragsgrößen der Jahrestage ``a`` und
    ``a+1`` werden mit dem Monatsanteil ``u = restmonate/12`` linear
    gemischt (unterjährige Interpolation). Stornoabschlag und
    Rückkaufswert werden aus den INTERPOLIERTEN Beträgen neu gerechnet;
    das Regelwerk (flexible Phase, Ablauf) folgt dem angebrochenen
    Vertragsjahr ``a``. Bei ``restmonate == 0`` sind alle Werte
    bit-identisch zur Jahrestagszeile.
    """

    monate: int          # volle Monate seit Versicherungsbeginn
    jahr: int            # angebrochenes Vertragsjahr a = monate // 12
    monatsanteil: float  # u = (monate % 12) / 12
    drx_bpfl: float      # Betrag (Deckungsrückstellung, beitragspfl. Track)
    vx_mrv: float        # Betrag (inkl. Zillmer-Tilgung) — Bilanzgröße
    stoab: float         # Stornoabschlag auf Basis der interpolierten DR
    # Vertragsweit: max(0, vx_mrv - stoab). Mit stoab_je_baustein wird
    # JE Baustein auf null geklemmt und dann summiert; stoab bleibt die
    # ungeklemmte Summe der Abzuege — rkw ist dann NICHT aus
    # vx_mrv - stoab rueckrechenbar (Kern 3.3.0, Ziffer 4).
    rkw: float


class KLV:
    """KLV-Zielgrößen für genau einen Modellpunkt (Kalkulations-Blatt)."""

    kennung = "klv"
    contract_prefix = "Kalkulation"  # Blattname des Quell-Workbooks
    # Vergleichsfenster des historischen Sechs-Datei-Contracts (Zeilen
    # 0..50 des Quell-Verlaufsblatts) — Eigenschaft der Vergleichs-View
    # in ``berechne``, KEIN Referenzwert des Kerns.
    contract_verlauf_bis: int | None = 50
    model_point_cls = ModelPoint

    def __init__(self, mp: ModelPoint) -> None:
        """Das Rechenrückgrat ist das Zustandsmodell — ohne Alternative.

        Bis ADR-013 nahm dieser Konstruktor ein austauschbares
        ``Barwerte``-Rückgrat, damit die Toleranz-Überleitung denselben
        Produktcode einmal mit der Kommutation und einmal mit dem
        Zustandsmodell rechnen konnte. Diese Überleitung war der
        Übersetzungsbeleg des Backbone-Wechsels (kern 2.0.0, 2026-08-12;
        6170 Werte, 0 abweichend, max. 4e-13 relativ) und ist erbracht.

        Die Einhängestelle fällt mit ihr. Sie war der Anspruch, den der
        Zweitkern an den Zielkern hatte — und über ihn kam die Grenze
        des Kommutationsmodells herein: Ein austauschbares
        ``Barwerte``-Rückgrat kann nur Einheitsbarwerte liefern, also
        konstante Summe und konstanten Beitrag."""
        self.mp = mp
        self.basis = tafeln.basis(mp.sex, mp.tafel)
        self.bw = ZustandsBarwerte(self.basis, mp.zins)
        self._scalar_cache: Dict[str, float] = {}
        self._zeilen_cache: Dict[int, Verlaufszeile] = {}

    # ----------------------------------------------------------------- #
    # Beitragssätze (Skalare K5..K9).
    # ----------------------------------------------------------------- #

    def _cached(self, name: str, rechne) -> float:
        if name not in self._scalar_cache:
            self._scalar_cache[name] = rechne()
        return self._scalar_cache[name]

    def ratzu(self) -> float:
        """Ratenzuschlag (E12) aus der Tarif-Staffel des Modellpunkts."""
        mp = self.mp
        staffel = {2: mp.ratzu_zw2, 4: mp.ratzu_zw4, 12: mp.ratzu_zw12}
        return installment_surcharge(mp.zw, staffel)

    def gross_premium_rate(self) -> float:
        """Bxt (K5): Bruttobeitragssatz je Einheit Versicherungssumme."""
        return self._cached("Bxt", self._gross_premium_rate)

    def _gross_premium_rate(self) -> float:
        mp = self.mp
        x, n, t = mp.x, mp.n, mp.t
        axt = self.bw.axn_k(x, t, 1)
        axn = self.bw.axn_k(x, n, 1)
        numerator = (
            self.bw.endowment_benefit_pv(x, n)
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
        return (1.0 + self.ratzu()) / mp.zw * (
            self.gross_annual_premium() + mp.policy_fee
        )

    def net_premium_rate(self) -> float:
        """Pxt (K9): Nettobeitragssatz je Einheit Versicherungssumme."""
        return self._cached("Pxt", self._net_premium_rate)

    def _net_premium_rate(self) -> float:
        mp = self.mp
        x, n, t = mp.x, mp.n, mp.t
        return (
            self.bw.endowment_benefit_pv(x, n) + t * mp.alpha * self.gross_premium_rate()
        ) / self.bw.axn_k(x, t, 1)

    def scalars(self) -> Dict[str, float]:
        """Die Golden-Master-Skalare des Kalkulations-Blatts."""
        return {
            "Bxt": self.gross_premium_rate(),
            "BJB": self.gross_annual_premium(),
            "BZB": self.gross_payable_premium(),
            "Pxt": self.net_premium_rate(),
            "ratzu": self.ratzu(),
        }

    # ----------------------------------------------------------------- #
    # Verlaufswerte (Blattzeilen 16..66) — benannte fachliche Seams.
    # ----------------------------------------------------------------- #

    def ist_flex_phase(self, a: int) -> bool:
        """Flexible Phase: Mindestalter erreicht UND Restlaufzeit klein genug."""
        mp = self.mp
        return mp.x + a >= mp.min_alter_flex and a >= mp.n - mp.min_rlz_flex

    def stornoabzug(self, a: int, kdrx_bpfl: float) -> float:
        """StoAb: satz*(VS-DRx), begrenzt auf [min, max]; 0 nach Ablauf/flex."""
        mp = self.mp
        if a > mp.n or self.ist_flex_phase(a):
            return 0.0
        return min(
            mp.stoab_max,
            max(mp.stoab_min, mp.stoab_satz * (mp.sum_insured - kdrx_bpfl)),
        )

    def verlaufszeile(self, a: int) -> Verlaufszeile:
        """Verlaufswerte-Zeile für Vertragsjahr ``a`` — typisiert, gecacht.

        Definiert fuer a >= 0 bis zur Tafel-Erschoepfung; jenseits von n
        greifen die Ablaufregeln (Reserven/RKW 0, flexible Phase).
        """
        if a < 0:
            raise ValueError(f"Vertragsjahr {a} negativ")
        if a in self._zeilen_cache:
            return self._zeilen_cache[a]
        mp = self.mp
        x, n, t, vs = mp.x, mp.n, mp.t, mp.sum_insured
        xa = x + a
        # Tafel-Domaene fail-fast (Erschoepfung, MAX_ALTER):
        self.basis.pruefe_alter(min(xa, x + min(a, n)), xa)

        pxt = self.net_premium_rate()
        bjb = self.gross_annual_premium()
        axn_full = self.bw.axn_k(x, n, 1)
        axt_full = self.bw.axn_k(x, t, 1)
        zd = mp.zillmer_dauer
        azd_full = self.bw.axn_k(x, zd, 1)

        if a <= n:
            axn_benefit = self.bw.endowment_benefit_pv(xa, n - a)
        else:
            axn_benefit = 0.0

        axn = self.bw.axn_k(xa, max(0, n - a), 1)
        axt = self.bw.axn_k(xa, max(0, t - a), 1)

        kvx_bpfl = (
            axn_benefit
            - pxt * axt
            + mp.gamma2 * (axn - (axn_full / axt_full) * axt)
        )
        kdrx_bpfl = vs * kvx_bpfl
        kvx_bfr = axn_benefit + mp.gamma3 * axn
        kvx_mrv = kdrx_bpfl + mp.alpha * t * bjb * self.bw.axn_k(
            xa, max(zd - a, 0), 1
        ) / azd_full

        flex = self.ist_flex_phase(a)
        stoab = self.stornoabzug(a, kdrx_bpfl)
        rkw = max(0.0, kvx_mrv - stoab)

        if a > n:
            vs_bfr = 0.0
        elif a < t:
            vs_bfr = kvx_mrv / kvx_bfr if kvx_bfr else 0.0
        else:
            vs_bfr = float(vs)

        zeile = Verlaufszeile(
            jahr=a,
            leistungsbarwert=axn_benefit,
            axn=axn,
            axt=axt,
            vx_bpfl=kvx_bpfl,
            drx_bpfl=kdrx_bpfl,
            vx_bfr=kvx_bfr,
            vx_mrv=kvx_mrv,
            flex_phase=flex,
            stoab=stoab,
            rkw=rkw,
            vs_bfr=vs_bfr,
        )
        self._zeilen_cache[a] = zeile
        return zeile

    def reserve_row(self, a: int) -> Dict[str, float]:
        """Verlaufswerte-Zeile als Golden-Master-View (Blatt-Keys)."""
        return self.verlaufszeile(a).als_blattzeile()

    def verlaufswerte(self, bis: int | None = None) -> List[Dict[str, float]]:
        """Verlaufswerte-Zeilen (Default: Vertragsjahre 0..n).

        ``bis`` erlaubt laengere Sichten (z. B. den 51-Zeilen-Contract des
        Sechs-Datei-Vergleichskerns) — der Horizont ist Sache des
        Aufrufers, nicht des Kerns.
        """
        horizont = self.mp.n if bis is None else bis
        return [self.reserve_row(jahr) for jahr in range(0, horizont + 1)]

    # ----------------------------------------------------------------- #
    # Ereignis-Anschlüsse (Stichtag, Beitragsfreistellung) — additiv, die
    # Golden-Master-Ausgaben bleiben unberührt.
    # ----------------------------------------------------------------- #

    def zustand_am(self, months_exp: int) -> Verlaufszeile:
        """Zustand am Stichtag nach ``months_exp`` vollen Monaten.

        Konvention: Zeile des angebrochenen Vertragsjahres
        (``months_exp // 12``), identisch zur Bestand-Fortschreibung.
        """
        return self.verlaufszeile(int(months_exp) // 12)

    def beitragsfreie_summe(self, a0: int) -> float:
        """VS_bfr bei Beitragsfreistellung am Ende von Vertragsjahr ``a0``."""
        return self.verlaufszeile(a0).vs_bfr

    def monatsreserve(self, monate: int) -> Monatsreserve:
        """Reserven nach ``monate`` vollen Monaten — unterjährig interpoliert.

        Linear zwischen den Vertragsjahrestagen ``a = monate // 12`` und
        ``a+1`` (Monatsanteil ``u = restmonate/12``); StoAb/RKW werden aus
        der interpolierten DR neu gerechnet (Regeln des Jahres ``a``).
        Definiert für ``0 <= monate <= 12*n`` — nach Ablauf gibt es keine
        Reserve mehr (fail fast statt stiller Null).
        """
        monate = int(monate)
        if monate < 0:
            raise ValueError(f"Monats-Stichtag {monate} negativ")
        if monate > 12 * self.mp.n:
            raise ValueError(
                f"Monats-Stichtag {monate} liegt nach dem Ablauf "
                f"(n = {self.mp.n} Jahre)"
            )
        a, rest = divmod(monate, 12)
        u = rest / 12.0
        za = self.verlaufszeile(a)
        if rest == 0:
            dr, mrv = za.drx_bpfl, za.vx_mrv
        else:
            zb = self.verlaufszeile(a + 1)
            dr = (1.0 - u) * za.drx_bpfl + u * zb.drx_bpfl
            mrv = (1.0 - u) * za.vx_mrv + u * zb.vx_mrv
        stoab = self.stornoabzug(a, dr)
        return Monatsreserve(
            monate=monate, jahr=a, monatsanteil=u,
            drx_bpfl=dr, vx_mrv=mrv, stoab=stoab,
            rkw=max(0.0, mrv - stoab),
        )

    def monatsreserve_beitragsfrei(self, a0: int, monate: int) -> float:
        """Beitragsfreie Reserve am Monats-Stichtag (PEX in Jahr ``a0``).

        Die bei Beitragsfreistellung fixierte Summe ``VS_bfr(a0)`` läuft
        auf dem beitragsfreien Reservesatz weiter; der Satz wird wie in
        :meth:`monatsreserve` linear zwischen den Jahrestagen gemischt.
        """
        monate = int(monate)
        if monate < 12 * a0:
            raise ValueError(
                f"Monats-Stichtag {monate} vor der Beitragsfreistellung "
                f"(a0 = {a0})"
            )
        if monate > 12 * self.mp.n:
            raise ValueError(
                f"Monats-Stichtag {monate} liegt nach dem Ablauf "
                f"(n = {self.mp.n} Jahre)"
            )
        a, rest = divmod(monate, 12)
        u = rest / 12.0
        satz = self.verlaufszeile(a).vx_bfr
        if rest:
            satz = (1.0 - u) * satz + u * self.verlaufszeile(a + 1).vx_bfr
        return self.beitragsfreie_summe(a0) * satz

    def reserve_beitragsfrei(self, a0: int, a: int) -> float:
        """Reserve im Jahr ``a`` eines ab ``a0`` beitragsfreien Vertrags.

        Deckungskapital-Umwandlung des Blatts: die beitragsfreie Summe
        (``VS_bfr`` in ``a0``) läuft auf dem beitragsfreien Reservesatz
        (``kVx_bfr``) weiter; in ``a = a0`` entspricht das der mit dem
        Rückkaufs-Track konsistenten Reserve ``kVx_MRV``.
        """
        if a < a0:
            raise ValueError(f"a={a} vor Beitragsfreistellung a0={a0}")
        return self.beitragsfreie_summe(a0) * self.verlaufszeile(a).vx_bfr
