"""Check engine for the Bestandsdaten gates (Stufe 1: driven via pytest).

Three check families, all returning error lists (repo idiom; empty = pass):

* :func:`sanity_check` — distribution plausibility: configured value bands.
* :func:`zeitscheiben_invarianten` — a Zeitscheibe may select rows and add
  derived columns, but every Stamm value must pass through unchanged.
* Golden-master anchoring is byte-level and lives in
  :func:`rechner_pipeline.bestand.parquet_io.portfolio_hash`; schema
  validation lives in :func:`rechner_pipeline.models.bestand.validate_portfolio`.

Formalization as toolbox gate CLIs (ledger entries, exit codes) is the
planned Stufe-2 step, following the toolbox/_common pattern.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import pandas as pd

from rechner_pipeline.models.bestand import STAMM_NAMES, ZEITSCHEIBEN_NAMES


def sanity_check(
    df: pd.DataFrame, baender: Dict[str, Tuple[float, float]]
) -> List[str]:
    """Check numeric columns against configured (min, max) plausibility bands."""
    errors: List[str] = []
    for merkmal, (lo, hi) in sorted(baender.items()):
        if merkmal not in df.columns:
            errors.append(f"sanity {merkmal}: Spalte fehlt")
            continue
        col = df[merkmal]
        actual_min, actual_max = float(col.min()), float(col.max())
        if actual_min < lo:
            errors.append(f"sanity {merkmal}: min {actual_min} < Band-Minimum {lo}")
        if actual_max > hi:
            errors.append(f"sanity {merkmal}: max {actual_max} > Band-Maximum {hi}")
    return errors


def zeitscheiben_invarianten(
    basis: pd.DataFrame, scheibe: pd.DataFrame
) -> List[str]:
    """A Zeitscheibe must be a pure selection + derivation of the base.

    Checks: column contract (Stamm + Zeitscheiben columns, exact order), no
    invented policies, no duplicated policies, and byte-equal Stamm values for
    every selected row.
    """
    errors: List[str] = []
    expected_cols = list(STAMM_NAMES) + list(ZEITSCHEIBEN_NAMES)
    if list(scheibe.columns) != expected_cols:
        errors.append(
            f"zeitscheibe: Spalten {list(scheibe.columns)} != erwartet {expected_cols}"
        )
        return errors
    if scheibe["police_id"].duplicated().any():
        errors.append("zeitscheibe: police_id doppelt")

    unbekannt = set(scheibe["police_id"]) - set(basis["police_id"])
    if unbekannt:
        errors.append(f"zeitscheibe: erfundene police_ids {sorted(unbekannt)[:5]}")
        return errors

    stamm = list(STAMM_NAMES)
    basis_idx = basis.set_index("police_id")
    scheibe_idx = scheibe.set_index("police_id")
    basis_sel = basis_idx.loc[scheibe_idx.index, [c for c in stamm if c != "police_id"]]
    scheibe_sel = scheibe_idx[[c for c in stamm if c != "police_id"]]
    if not basis_sel.equals(scheibe_sel):
        diff_cols = [
            c for c in basis_sel.columns if not basis_sel[c].equals(scheibe_sel[c])
        ]
        errors.append(f"zeitscheibe: Stammfelder veraendert: {diff_cols}")
    return errors
