"""Probe des Landeplatzes der Cashflow-Modelle (ADR-007, Nachtrag vom 10.11.2026).

Kein Rechenwerk: Die Funktion summiert eine Beitragsspalte je Jahr, ohne
Zins und ohne Sterblichkeit. Sie liest ihre Eingabe nur und importiert
nichts aus dem Paket des Systems (tests/test_landeplatz_cashflow.py).
"""

from pathlib import Path
from typing import Dict

import pandas as pd


def _ganzes_jahr(wert, spalte: str) -> int:
    """Ein Jahr als int; Wahrheitswerte und Bruchjahre brechen ab."""
    bruch = pd.api.types.is_float(wert) and not float(wert).is_integer()
    if pd.api.types.is_bool(wert) or bruch:
        raise ValueError(f"Spalte {spalte!r} hat einen Wert, der kein ganzes Jahr ist: {wert!r}")
    return int(wert)


def beitragsreihe(pfad: Path, *, jahr: str, beitrag: str) -> Dict[int, float]:
    """Summe der Spalte ``beitrag`` je vorkommendem Jahr, aufsteigend.

    Die Spaltennamen nennt der Aufrufer; die Probe legt kein Format fest.
    Eine fehlende Spalte bricht beim Lesen ab. Leere Werte in einer der beiden
    Spalten, eine nicht numerische Beitragsspalte und ein Jahr, das keine ganze
    Zahl ist, brechen hier ab. Das Jahr wird vor der Gruppierung in int
    umgewandelt, der Beitrag nicht.
    """
    tabelle = pd.read_parquet(pfad, columns=[jahr, beitrag])
    for spalte in (jahr, beitrag):
        if tabelle[spalte].isna().any():
            raise ValueError(f"Spalte {spalte!r} hat leere Werte")
    werte = tabelle[beitrag]
    if not pd.api.types.is_numeric_dtype(werte) or pd.api.types.is_bool_dtype(werte):
        raise ValueError(f"Spalte {beitrag!r} ist nicht numerisch ({werte.dtype})")
    jahre = pd.Series([_ganzes_jahr(j, jahr) for j in tabelle[jahr]], index=tabelle.index)
    summen = werte.groupby(jahre, sort=True).sum()
    return {int(j): float(s) for j, s in summen.items()}
