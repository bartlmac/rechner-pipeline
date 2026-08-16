"""Kommutationsspalten D/N/C/M — die klassische Kreuz-Rechenschiene.

Baut fuer eine Basis (Geschlecht, Tafel, Zins) die Kommutationsspalten
exakt nach dem VBA-Modul ``mGWerte`` des historischen Quell-Workbooks
(gerundete l_x-Kette). Dieses Paket ist NICHT Teil des Zielkerns: es
existiert als unabhaengiger zweiter Rechenweg fuer die
Toleranz-Ueberleitung (qa/ueberleitung). Tafeldaten kommen aus
:mod:`rechner_pipeline.kern.tafeln` — fail-fast, keine erfundenen qx.

Knoten: klv
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from importlib import resources
from types import MappingProxyType
from typing import Dict, List, Mapping, Tuple

from rechner_pipeline.kern.konventionen import MAX_ALTER, RADIX, excel_round
from rechner_pipeline.kern.tafeln import (  # noqa: F401 — Re-Export-Kompat
    MissingMortalityTableError,
    TafelBereichError,
    _tafel_key,
    qx_vector,
    select_max_dauer,
    select_tafel,
)


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
    # Kreuz-Modell-Gates (qa/ueberleitung).
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
