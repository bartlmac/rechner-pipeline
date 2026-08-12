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


# --------------------------------------------------------------------------- #
# Ereignis-Kennzahlen (Fortschreibung: Statushistorie + Ledger)
# --------------------------------------------------------------------------- #

#: Feste fachliche Reihenfolge der Ereignisse in Tabellen und Grafiken.
EREIGNIS_REIHENFOLGE = ("PEX", "STO", "TOD", "ABL")

#: Klartext je Ereignis-Code (Berichts-Beschriftung).
EREIGNIS_LABELS = {
    "PEX": "Beitragsfreistellung",
    "STO": "Storno",
    "TOD": "Tod",
    "ABL": "Ablauf",
}


def ereignis_summen(ledger: pd.DataFrame) -> List[Dict[str, Any]]:
    """Anzahl und Betragssumme je Ereignisart (feste Reihenfolge).

    ``betrag_art`` ist je Ereignis einheitlich (RKW, VS_bfr, ...); Ereignisse
    ohne Vorkommen werden ausgelassen.
    """
    summen: List[Dict[str, Any]] = []
    for code in EREIGNIS_REIHENFOLGE:
        rows = ledger[ledger["ereignis"] == code]
        if len(rows) == 0:
            continue
        summen.append(
            {
                "ereignis": code,
                "label": EREIGNIS_LABELS[code],
                "anzahl": int(len(rows)),
                "betrag_art": str(rows["betrag_art"].iloc[0]),
                "summe_betrag": float(rows["betrag"].sum()),
            }
        )
    return summen


def ereignisse_je_jahr(ledger: pd.DataFrame) -> List[Dict[str, Any]]:
    """Ereigniszählung je Kalenderjahr (aufsteigend, lückenlos)."""
    if len(ledger) == 0:
        return []
    jahre = ledger["status_date"].dt.year
    von, bis = int(jahre.min()), int(jahre.max())
    reihe: List[Dict[str, Any]] = []
    for jahr in range(von, bis + 1):
        im_jahr = ledger[jahre == jahr]
        eintrag: Dict[str, Any] = {"jahr": jahr}
        for code in EREIGNIS_REIHENFOLGE:
            eintrag[code] = int((im_jahr["ereignis"] == code).sum())
        reihe.append(eintrag)
    return reihe


def status_verlauf(
    sicht: pd.DataFrame, stichtage: List[_dt.date]
) -> List[Dict[str, Any]]:
    """In-force-Bestand je Stichtag, aufgeteilt nach Status (POL/PEX).

    ``sicht`` ist die Mehrzeilen-Sicht aus
    :func:`rechner_pipeline.bestand.ereignisse.bestand_mit_historie`; die
    Zeitscheibe wählt je Police den jüngsten in-force-Status.
    """
    reihe: List[Dict[str, Any]] = []
    for stichtag in stichtage:
        scheibe = zeitscheibe(sicht, stichtag)
        counts = scheibe["status_code"].value_counts()
        reihe.append(
            {
                "stichtag": stichtag.isoformat(),
                "POL": int(counts.get("POL", 0)),
                "PEX": int(counts.get("PEX", 0)),
            }
        )
    return reihe
