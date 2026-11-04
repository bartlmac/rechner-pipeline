"""Vertrag der Ereignisliste zwischen simulierte Welt und Bestandsfuehrung.

Codes, Spalten und Zugangslage enthalten weder eine Ziehung noch einen
Rechenwert. Die Fuehrung kann eine fremde Liste anhand dieses Vertrags
pruefen und buchen (ADR-031).

Knoten: klv, bu
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Mapping, NamedTuple

import pandas as pd

from rechner_pipeline.models.bestand import STAMM_SPALTEN


TOD = "TOD"
STO = "STO"
PEX = "PEX"
ERH = "ERH"
RED = "RED"
TKU = "TKU"
INV = "INV"
REA = "REA"

#: Schema der Ereignisliste (Spalte, dtype).
EREIGNISLISTE_SPALTEN = (
    ("police_id", "int64"),
    ("lfd", "int64"),            # Zugreihenfolge je Police: 1, 2, ...
    ("vertragsjahr", "int64"),  # gebuchter Jahrestag (vollendete Jahre)
    ("ereignis", "object"),
    ("wirkungstag", "datetime64[ns]"),
    ("anteil", "float64"),      # Reduktion: Anteil; Erhoehung: Satz; sonst NaN
    ("verfahren", "object"),   # Reduktion: Verfahren; sonst leer
)
EREIGNISLISTE_NAMES = tuple(name for name, _ in EREIGNISLISTE_SPALTEN)
OHNE_ANTEIL = float("nan")
OHNE_VERFAHREN = ""


class EreignisError(ValueError):
    """Bestand, Config oder Ereignisliste passen nicht zur Simulation."""


class Ereignisliste(NamedTuple):
    """Zugaenge als POL-Basiszeilen und gezogene Ereignisse aller Vertraege."""

    zugaenge: pd.DataFrame
    ereignisse: pd.DataFrame


def leere_ereignisse() -> pd.DataFrame:
    return pd.DataFrame({name: pd.Series(dtype=dtype) for name, dtype in EREIGNISLISTE_SPALTEN})


def leere_zugaenge() -> pd.DataFrame:
    return pd.DataFrame({name: pd.Series(dtype=dtype) for name, dtype in STAMM_SPALTEN})


def _vertragsjahr(beginn: _dt.date, datum: _dt.date) -> int:
    monate = (datum.year - beginn.year) * 12 + (datum.month - beginn.month)
    return max(0, monate // 12)


def zugangslage(row: Mapping[str, Any]) -> tuple:
    """Erstes Vertragsjahr, Zugangszustand und Jahr des Zustandswechsels."""
    beginn = pd.Timestamp(row["insurance_start"]).date()
    zugang = pd.Timestamp(row["bestandszugang"]).date()
    ab_jahr = _vertragsjahr(beginn, zugang)
    zustand = str(row.get("status_code", "POL"))
    seit = _vertragsjahr(beginn, pd.Timestamp(row["status_date"]).date())
    return ab_jahr, zustand, seit
