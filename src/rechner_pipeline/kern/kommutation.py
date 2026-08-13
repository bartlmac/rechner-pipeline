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
from types import MappingProxyType
from typing import Dict, List, Mapping, Tuple

from rechner_pipeline.kern.konventionen import MAX_ALTER, RADIX, excel_round


class MissingMortalityTableError(NotImplementedError):
    """Die angeforderte Sterbetafel fehlt in ``tafeln.xml``."""


class TafelBereichError(ValueError):
    """Eine Rechnung erreicht Alter mit D_x = 0 (Tafel erschöpft).

    Sprechender Domänenfehler statt ``ZeroDivisionError``: betrifft nur
    Modellpunkte, deren Verlaufshorizont über das letzte Alter mit lebenden
    Beständen hinausläuft (z. B. DAV1994_T: l_x = 0 ab Alter 101).
    """


def _load_tables():
    """``tafeln.xml`` (Paket-Daten) parsen.

    Rückgabe: (Alterstafeln ``{name: {alter: qx}}``, Select-Tafeln
    ``{name: {(alter, dauer): wert}}``). Select-Tafeln (Einträge mit
    ``dauer``-Attribut, Tabellen-Attribut ``select_max``) tragen
    dauerabhängige Ausscheidewahrscheinlichkeiten — das
    Select-Perioden-Prinzip der DAV-Tafeln (z. B. Reaktivierung/
    Invalidensterblichkeit nach BU-Dauer).
    """
    text = (resources.files("rechner_pipeline.kern") / "tafeln.xml").read_text(
        encoding="utf-8"
    )
    root = ET.fromstring(text)
    tables: Dict[str, Dict[int, float]] = {}
    select_tables: Dict[str, Dict[Tuple[int, int], float]] = {}
    for table in root.findall("table"):
        name = table.get("name")
        if table.get("select_max") is not None:
            select_max = int(table.get("select_max"))
            by_key: Dict[Tuple[int, int], float] = {}
            for entry in table.findall("entry"):
                if entry.get("dauer") is None:
                    raise ValueError(
                        f"Select-Tafel {name!r}: Eintrag ohne dauer-Attribut"
                    )
                key = (int(entry.get("age")), int(entry.get("dauer")))
                if key in by_key:
                    raise ValueError(f"Select-Tafel {name!r}: Duplikat {key}")
                by_key[key] = float(entry.get("qx"))
            # Vollstaendiges Gitter + Attribut-Konsistenz fail-fast beim Laden
            # (nicht erst mitten in der Thiele-Rekursion):
            daten_max = max(d for _, d in by_key)
            if daten_max != select_max:
                raise ValueError(
                    f"Select-Tafel {name!r}: select_max={select_max} passt "
                    f"nicht zu den Daten (max. Dauer {daten_max})"
                )
            fehlend = [
                (a, d)
                for a in range(0, MAX_ALTER + 1)
                for d in range(0, select_max + 1)
                if (a, d) not in by_key
            ]
            if fehlend:
                raise ValueError(
                    f"Select-Tafel {name!r}: Gitterluecken, z. B. {fehlend[:3]}"
                )
            select_tables[name] = by_key
        else:
            by_age: Dict[int, float] = {}
            for entry in table.findall("entry"):
                if entry.get("dauer") is not None:
                    raise ValueError(
                        f"Tafel {name!r}: dauer-Eintrag ohne select_max-Attribut "
                        "— Select-Tafeln muessen als solche deklariert sein"
                    )
                age = int(entry.get("age"))
                if age in by_age:
                    raise ValueError(f"Tafel {name!r}: Duplikat Alter {age}")
                by_age[age] = float(entry.get("qx"))
            tables[name] = by_age
    return tables, select_tables


_TABLES, _SELECT_TABLES = _load_tables()


def select_tafel(name: str) -> Mapping[Tuple[int, int], float]:
    """Select-Tafel ``{(alter, dauer): wert}`` — fail-fast wenn unbekannt.

    Rückgabe ist eine unveränderliche Sicht (MappingProxy) auf die
    Prozess-globalen Tafeldaten — Aufrufer können sie nicht mutieren
    (Anker-Bit-Exaktheit).
    """
    tafel = _SELECT_TABLES.get(name)
    if tafel is None:
        raise MissingMortalityTableError(
            f"Select-Tafel {name!r} fehlt in tafeln.xml; es wird keine "
            "Ausscheideordnung erfunden"
        )
    return MappingProxyType(tafel)


def select_max_dauer(name: str) -> int:
    """Höchste tabulierte Dauer einer Select-Tafel (Select-Periode)."""
    return max(dauer for _, dauer in select_tafel(name))


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
