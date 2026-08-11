"""Sterbetafel-Zugriff und Kommutationswerte D/N/C/M — parametrisiert.

Baut für eine Kombination (Geschlecht, Tafel, Zins) die klassischen
Kommutationsspalten exakt nach dem VBA-Modul ``mGWerte`` des Quell-Workbooks:

    l_0 = 1_000_000
    l_{x+1} = round(l_x * (1 - q_x), 16)
    t_x     = round(l_x - l_{x+1}, 16)
    D_x     = round(l_x * v^x, 16)
    C_x     = round(t_x * v^{x+1}, 16)
    N_x     = round(N_{x+1} + D_x, 16)   (von omega = MAX_ALTER abwärts)
    M_x     = round(M_{x+1} + C_x, 16)

Anders als der einmalig generierte Migrations-Kern bindet dieses Modul NICHT
an einen festen Modellpunkt: :func:`fuer` liefert (gecacht) ein
:class:`Kommutation`-Objekt je Basis. Fail-fast: fehlt die angeforderte Tafel
in ``tafeln.xml``, wird :class:`MissingMortalityTableError` geworfen — es wird
niemals eine qx-Kurve erfunden.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from importlib import resources
from typing import Dict, List, Tuple

from rechner_pipeline.kern.konventionen import MAX_ALTER, RADIX, excel_round


class MissingMortalityTableError(NotImplementedError):
    """Die angeforderte Sterbetafel fehlt in ``tafeln.xml``."""


class TafelBereichError(ValueError):
    """Eine Rechnung erreicht Alter mit D_x = 0 (Tafel erschöpft).

    Sprechender Domänenfehler statt ``ZeroDivisionError``: betrifft nur
    Modellpunkte, deren Verlaufshorizont über das letzte Alter mit lebenden
    Beständen hinausläuft (z. B. DAV1994_T: l_x = 0 ab Alter 101).
    """


def _load_tables() -> Dict[str, Dict[int, float]]:
    """``tafeln.xml`` (Paket-Daten) nach ``{name: {alter: qx}}`` parsen."""
    text = (resources.files("rechner_pipeline.kern") / "tafeln.xml").read_text(
        encoding="utf-8"
    )
    root = ET.fromstring(text)
    tables: Dict[str, Dict[int, float]] = {}
    for table in root.findall("table"):
        name = table.get("name")
        by_age: Dict[int, float] = {}
        for entry in table.findall("entry"):
            by_age[int(entry.get("age"))] = float(entry.get("qx"))
        tables[name] = by_age
    return tables


_TABLES = _load_tables()


def _tafel_key(sex: str, tafel: str) -> str:
    """Tafel-Id in ``tafeln.xml`` auflösen.

    Exakter Tafelname gewinnt (macht geschlechtsunabhängige Tafeln — Unisex —
    ohne Kern-Änderung möglich, sobald ``tafeln.xml`` eine solche enthält);
    sonst VBA-treues Suffix ``Act_qx``: nicht-"M" -> Frauentafel.
    """
    if tafel in _TABLES:
        return tafel
    return tafel + "_" + ("M" if sex.upper() == "M" else "F")


def qx_vector(sex: str, tafel: str) -> List[float]:
    """qx-Liste für Alter 0..MAX_ALTER (Auflösung siehe :func:`_tafel_key`)."""
    key = _tafel_key(sex, tafel)
    table = _TABLES.get(key)
    if table is None:
        raise MissingMortalityTableError(
            f"Sterbetafel {key!r} fehlt in tafeln.xml; es wird keine qx-Kurve erfunden"
        )
    vector = []
    for age in range(0, MAX_ALTER + 1):
        if age not in table:
            raise MissingMortalityTableError(
                f"Sterbetafel {key!r}: Alter {age} fehlt in tafeln.xml"
            )
        vector.append(table[age])
    return vector


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
