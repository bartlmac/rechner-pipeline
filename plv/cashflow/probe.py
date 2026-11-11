"""Probe des Landeplatzes der Cashflow-Modelle (ADR-007, Nachtrag vom 10.11.2026).

Kein Rechenwerk: Die Funktion summiert eine Beitragsspalte je Jahr, ohne
Zins und ohne Sterblichkeit. Sie liest ihre Eingabe nur und importiert
nichts aus dem Paket des Systems (tests/test_landeplatz_cashflow.py).
"""

from pathlib import Path
from typing import Dict

import pandas as pd


def beitragsreihe(pfad: Path, *, jahr: str, beitrag: str) -> Dict[int, float]:
    """Summe der Spalte ``beitrag`` je Wert der Spalte ``jahr``, aufsteigend.

    Die Spaltennamen nennt der Aufrufer; die Probe legt kein Format fest.
    Eine fehlende Spalte bricht beim Lesen ab, ein leerer Beitrag hier.
    """
    tabelle = pd.read_parquet(pfad, columns=[jahr, beitrag])
    if tabelle[beitrag].isna().any():
        raise ValueError(f"Spalte {beitrag!r} hat leere Werte")
    summen = tabelle.groupby(jahr, sort=True)[beitrag].sum()
    return {int(j): float(s) for j, s in summen.items()}
