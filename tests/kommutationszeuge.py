"""Kommutationszeuge: der unabhaengige zweite Rechenweg der Kern-Tests.

Klassische Kommutationsrechnung ueber die Absterbeordnung l_x — die Spalten
D/N/C/M exakt nach dem VBA-Modul ``mGWerte`` des historischen Quell-Workbooks
(gerundete l_x-Kette) und die Barwert-Bausteine nach ``mBarwerte``. Der
Zielkern rechnet dagegen auf Uebergangswahrscheinlichkeiten (ADR-004). Eine
Gegenrechnung aus diesen Bausteinen ist deshalb keine Umformung des
geprueften Rumpfes: An ihr haengt das Aequivalenzprinzip auf dem produktiven
Beitragspfad (``tests/test_kern_algebraisch.py``, Stufe 3) und der Abgleich
der Whole-Life-Durchreicher.

Kein Teil des Systems. Bis zum 04.10.2026 lag dieser Code als Paket
``rechner_pipeline.kommutationskern`` in ``src``; seit ADR-013 hatte er dort
keinen Konsumenten mehr, und mit ADR-027 ist er aus dem Paket entfernt. Was
bleibt, ist dieser Zeuge der Tests. Die Tafeldaten kommen aus der
Rechnungsgrundlagen-Schicht des Zielkerns
(:mod:`rechner_pipeline.kern.tafeln`) — eine Wahrheit, zwei Rechenwege.

Knoten: klv
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple

from rechner_pipeline.kern.konventionen import MAX_ALTER, RADIX, excel_round
from rechner_pipeline.kern.tafeln import _tafel_key, qx_vector


@dataclass(frozen=True)
class Kommutation:
    """Kommutationsspalten einer Rechnungsbasis (Geschlecht, Tafel, Zins)."""

    sex: str
    tafel: str
    zins: float
    qx: Tuple[float, ...] = field(repr=False)
    lx: Tuple[float, ...] = field(repr=False)
    tx: Tuple[float, ...] = field(repr=False)
    dx: Tuple[float, ...] = field(repr=False)
    cx: Tuple[float, ...] = field(repr=False)
    nx: Tuple[float, ...] = field(repr=False)
    mx: Tuple[float, ...] = field(repr=False)

    @property
    def v(self) -> float:
        """Jährlicher Diskontfaktor v = 1 / (1 + Zins)."""
        return 1.0 / (1.0 + self.zins)

    def _check_age(self, age: int) -> None:
        if age < 0 or age > MAX_ALTER:
            raise IndexError(f"Alter {age} ausserhalb des Tafelbereichs [0, {MAX_ALTER}]")

    def qx_at(self, age: int) -> float:
        self._check_age(age)
        return self.qx[age]

    def lx_at(self, age: int) -> float:
        self._check_age(age)
        return self.lx[age]

    def tx_at(self, age: int) -> float:
        self._check_age(age)
        return self.tx[age]

    def Dx_at(self, age: int) -> float:
        self._check_age(age)
        return self.dx[age]

    def Cx_at(self, age: int) -> float:
        self._check_age(age)
        return self.cx[age]

    def Nx_at(self, age: int) -> float:
        self._check_age(age)
        return self.nx[age]

    def Mx_at(self, age: int) -> float:
        self._check_age(age)
        return self.mx[age]


def _build(sex: str, tafel: str, zins: float) -> Kommutation:
    """(lx, tx, Dx, Cx, Nx, Mx) exakt wie das VBA-Modul mGWerte aufbauen."""
    omega = MAX_ALTER
    qx = qx_vector(sex, tafel)
    v = 1.0 / (1.0 + zins)

    lx = [0.0] * (omega + 1)
    lx[0] = RADIX
    for i in range(1, omega + 1):
        lx[i] = excel_round(lx[i - 1] * (1.0 - qx[i - 1]))

    tx = [0.0] * (omega + 1)
    for i in range(0, omega):
        tx[i] = excel_round(lx[i] - lx[i + 1])

    dx = [0.0] * (omega + 1)
    for i in range(0, omega + 1):
        dx[i] = excel_round(lx[i] * (v ** i))

    # VBA-treu bleiben tx[omega]/cx[omega] unbefuellt (Tote im Endalter 123
    # fehlen strukturell in Mx). Fuer die ausgelieferten Tafeln ist das
    # folgenlos (lx[123] = 0); die Zustandsmodell-Schiene modelliert das
    # Endalter vollstaendig — dokumentierte gemeinsame Blindstelle des
    # algebraische Eigenschaftstests.
    cx = [0.0] * (omega + 1)
    for i in range(0, omega):
        cx[i] = excel_round(tx[i] * (v ** (i + 1)))

    nx = [0.0] * (omega + 1)
    nx[omega] = dx[omega]
    for i in range(omega - 1, -1, -1):
        nx[i] = excel_round(nx[i + 1] + dx[i])

    mx = [0.0] * (omega + 1)
    mx[omega] = cx[omega]
    for i in range(omega - 1, -1, -1):
        mx[i] = excel_round(mx[i + 1] + cx[i])

    return Kommutation(
        sex=sex, tafel=tafel, zins=zins,
        qx=tuple(qx), lx=tuple(lx), tx=tuple(tx),
        dx=tuple(dx), cx=tuple(cx), nx=tuple(nx), mx=tuple(mx),
    )


_CACHE: Dict[Tuple[str, float], Kommutation] = {}


def fuer(sex: str, tafel: str, zins: float) -> Kommutation:
    """Kommutation für eine Rechnungsbasis — deterministisch gecacht.

    Cache-Schlüssel ist die AUFGELÖSTE Tafel (:func:`_tafel_key`): zwei
    Geschlechter auf einer Unisex-Tafel teilen sich dieselbe Basis.
    """
    sex_norm = "M" if sex.upper() == "M" else "F"
    key = (_tafel_key(sex_norm, tafel), float(zins))
    if key not in _CACHE:
        _CACHE[key] = _build(sex_norm, tafel, float(zins))
    return _CACHE[key]


class Barwerte:
    """Barwert-Bausteine auf einer Kommutationsbasis (Zahlungsordnung k)."""

    def __init__(self, kom: Kommutation, zins: float) -> None:
        self.kom = kom
        self.zins = zins
        self._axn_cache: Dict[Tuple[int, int, int], float] = {}

    def abzugsglied(self, k: int) -> float:
        """Unterjähriges Korrekturglied (VBA ``Act_Abzugsglied``); 0 für k=1."""
        if k <= 0:
            return 0.0
        zins = self.zins
        total = 0.0
        for step in range(0, k):
            total += (step / k) / (1.0 + (step / k) * zins)
        return total * (1.0 + zins) / k

    def axn_k(self, age: int, term: int, k: int = 1) -> float:
        """Temporäre vorschüssige Rente (VBA ``Act_axn_k``)."""
        if k <= 0:
            return 0.0
        key = (age, term, k)
        cached = self._axn_cache.get(key)
        if cached is not None:
            return cached
        dx = self.kom.Dx_at(age)
        dxt = self.kom.Dx_at(age + term)
        value = (self.kom.Nx_at(age) - self.kom.Nx_at(age + term)) / dx - self.abzugsglied(
            k
        ) * (1.0 - dxt / dx)
        self._axn_cache[key] = value
        return value

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
