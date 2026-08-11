"""Portfolio-Kennzahlen für den Bestandsbericht (reine Berechnung, testbar).

Alle Funktionen sind deterministisch und frei von I/O und Darstellung; der
Renderer (:mod:`rechner_pipeline.bestand.report`) konsumiert nur die hier
berechneten Strukturen. Sortierungen sind überall explizit, damit das
Rendering byte-reproduzierbar bleibt.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List

import pandas as pd

from rechner_pipeline.bestand.zeitscheibe import zeitscheibe


def jahresraster(df: pd.DataFrame) -> List[_dt.date]:
    """Jährliche Stichtage (1.1.) vom ersten Vertragsbeginn bis zum letzten Ablauf."""
    von = int(df["insurance_start"].dt.year.min())
    bis = int(df["insurance_end"].dt.year.max())
    return [_dt.date(jahr, 1, 1) for jahr in range(von, bis + 1)]


def stichtags_kennzahlen(scheibe: pd.DataFrame, stichtag: _dt.date) -> Dict[str, Any]:
    """Kennzahlen einer Zeitscheibe (leere Scheibe ergibt Nullwerte)."""
    n = int(len(scheibe))
    generationen = {
        str(name): int(anzahl)
        for name, anzahl in sorted(
            scheibe["tarif_generation"].value_counts().items()
        )
    } if n else {}
    return {
        "stichtag": stichtag.isoformat(),
        "vertraege": n,
        "summe_vs": float(scheibe["sum_insured"].sum()) if n else 0.0,
        "mittel_alter": float(scheibe["age"].mean()) if n else 0.0,
        "mittel_restlaufzeit_jahre": float(scheibe["months_rem"].mean() / 12.0) if n else 0.0,
        "generationen": generationen,
    }


def verlauf(df: pd.DataFrame, stichtage: List[_dt.date]) -> List[Dict[str, Any]]:
    """Kennzahlen-Reihe über eine Stichtagsliste (Bestandsverlauf)."""
    return [stichtags_kennzahlen(zeitscheibe(df, s), s) for s in stichtage]


def generationsnamen(df: pd.DataFrame) -> List[str]:
    """Alle Tarifgenerationen im Bestand, stabil sortiert."""
    return sorted(str(v) for v in df["tarif_generation"].unique())
