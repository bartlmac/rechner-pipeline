"""Zeitscheiben-Fortschreibung: pure filter + derived fields, never mutation.

Semantics follow the reference's Zeitscheiben step: a reporting date
(Stichtag) SELECTS the portfolio state — contracts active at the date, the
youngest status row before the date — and derives the few time-dependent
quantities anew (age with 6-month rounding, elapsed/remaining months). All
Stamm columns pass through byte-identically; the Zeitscheiben gate enforces
that invariant. Calculated quantities (reserves at the date, ...) are NOT
computed here — they come from the stable kernel (:func:`.kernlauf.berechne_vertrag`).
"""

from __future__ import annotations

import datetime as _dt

import pandas as pd

from rechner_pipeline.models.bestand import STAMM_NAMES, ZEITSCHEIBEN_NAMES


def months_between(d1: _dt.date, d2: _dt.date) -> int:
    """Full months elapsed from ``d1`` to ``d2`` (negative if d2 < d1)."""
    m = (d2.year - d1.year) * 12 + (d2.month - d1.month)
    if d2.day < d1.day:
        m -= 1
    return m


def derived_age(entry_age: int, months_exp: int) -> int:
    """Attained age with the reference's 6-month rounding.

    ``round((months_exp + 1) / 12 - eps)``: five completed months round down,
    six completed months round up (the +1/eps construction puts the boundary
    between five and six months, mirroring the reference implementation).
    """
    return int(entry_age + round((months_exp + 1) / 12 - 1e-12))


def zeitscheibe(df: pd.DataFrame, stichtag: _dt.date) -> pd.DataFrame:
    """Cut the portfolio state at ``stichtag`` (pure function, no mutation).

    Selection: contract already begun (``insurance_start <= stichtag``), not
    yet expired (``insurance_end > stichtag``), and only status rows known at
    the date (``status_date <= stichtag``; youngest per police). Derivation:
    ``age``, ``months_exp``, ``months_rem`` plus the ``stichtag`` column.
    """
    ts = pd.Timestamp(stichtag)
    aktiv = df[
        (df["insurance_start"] <= ts)
        & (df["insurance_end"] > ts)
        & (df["status_date"] <= ts)
    ]
    # Juengster Statussatz je Police vor dem Stichtag (Stufe 1: genau einer).
    aktiv = (
        aktiv.sort_values(["police_id", "status_date"], kind="stable")
        .groupby("police_id", as_index=False, sort=False)
        .tail(1)
        .reset_index(drop=True)
    )

    months_exp = [
        months_between(s.date(), stichtag) for s in aktiv["insurance_start"]
    ]
    # Restmonate als Ceiling: volle Monate + 1 nur bei angebrochenem Monat
    # (Tag-genau; bei Stichtag auf dem Monatsersten — der Datums-Konvention
    # des Moduls — gibt es keinen Teilmonat). Invariante fuer jeden Stichtag:
    # months_exp + months_rem == 12 * duration.
    months_rem = [
        months_between(stichtag, e.date())
        + (0 if e.date().day == stichtag.day else 1)
        for e in aktiv["insurance_end"]
    ]
    age = [
        derived_age(int(a), m) for a, m in zip(aktiv["entry_age"], months_exp)
    ]

    out = aktiv.copy()
    out["stichtag"] = ts
    out["age"] = pd.Series(age, dtype="int64")
    out["months_exp"] = pd.Series(months_exp, dtype="int64")
    out["months_rem"] = pd.Series(months_rem, dtype="int64")
    return out[list(STAMM_NAMES) + list(ZEITSCHEIBEN_NAMES)]
