"""Check engine for the Bestandsdaten gates (Stufe 1: driven via pytest).

Three check families, all returning error lists (repo idiom; empty = pass):

* :func:`sanity_check` — distribution plausibility: configured value bands.
* :func:`auskunfts_invarianten` — ein Auskunfts-Schnitt (ADR-011) darf
  Zeilen auswaehlen und Stichtagsgroessen ableiten, aber jeden Stammwert
  nur unveraendert durchreichen.
* Golden-master anchoring is byte-level and lives in
  :func:`rechner_pipeline.bestand.parquet_io.portfolio_hash`; schema
  validation lives in :func:`rechner_pipeline.models.bestand.validate_portfolio`.

Formalization as toolbox gate CLIs (ledger entries, exit codes) is the
planned Stufe-2 step, following the toolbox/_common pattern.

Knoten: klv, bu
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import pandas as pd

from rechner_pipeline.models.bestand import STAMM_NAMES, ZEITSCHEIBEN_NAMES


def sanity_check(
    df: pd.DataFrame, baender: Dict[str, Tuple[float, float]]
) -> List[str]:
    """Check numeric columns against configured (min, max) plausibility bands.

    Die produktfuehrenden Leistungsspalten (``sum_insured`` bei KLV,
    ``bu_rente`` bei BU) werden nur auf den Vertraegen ihres Produkts
    geprueft: die jeweils andere Spalte ist per Schema-Invariante strikt 0
    und wuerde in einem gemischten Bestand jedes Untergrenzen-Band reissen.
    """
    from rechner_pipeline.models.bestand import LEISTUNGSSPALTE

    produkt_je_spalte = {spalte: produkt for produkt, spalte in LEISTUNGSSPALTE.items()}
    errors: List[str] = []
    for merkmal, (lo, hi) in sorted(baender.items()):
        if merkmal not in df.columns:
            errors.append(f"sanity {merkmal}: Spalte fehlt")
            continue
        teil = df
        produkt = produkt_je_spalte.get(merkmal)
        if produkt is not None and "produkt" in df.columns:
            teil = df[df["produkt"] == produkt]
            if len(teil) == 0:
                continue   # Produkt im Bestand nicht vertreten
        col = teil[merkmal]
        actual_min, actual_max = float(col.min()), float(col.max())
        if actual_min < lo:
            errors.append(f"sanity {merkmal}: min {actual_min} < Band-Minimum {lo}")
        if actual_max > hi:
            errors.append(f"sanity {merkmal}: max {actual_max} > Band-Maximum {hi}")
    return errors


def auskunfts_invarianten(
    basis: pd.DataFrame, scheibe: pd.DataFrame
) -> List[str]:
    """Ein Auskunfts-Schnitt ist reine Auswahl + Ableitung der Journalsicht.

    Checks: column contract (Stamm + Zeitscheiben columns, exact order), no
    invented policies, no duplicated policies, and byte-equal Stamm values for
    every selected row.
    """
    errors: List[str] = []
    expected_cols = list(STAMM_NAMES) + list(ZEITSCHEIBEN_NAMES)
    if list(scheibe.columns) != expected_cols:
        errors.append(
            f"auskunft: Spalten {list(scheibe.columns)} != erwartet {expected_cols}"
        )
        return errors
    if scheibe["police_id"].duplicated().any():
        errors.append("auskunft: police_id doppelt")

    unbekannt = set(scheibe["police_id"]) - set(basis["police_id"])
    if unbekannt:
        errors.append(f"auskunft: erfundene police_ids {sorted(unbekannt)[:5]}")
        return errors

    # Vergleichsschluessel ist die Statuszeile (police_id, status_id): die
    # Basis darf mehrere Statuszeilen je Police tragen (Statushistorie der
    # Fortschreibung); die Scheibe waehlt genau eine davon aus.
    stamm = list(STAMM_NAMES)
    key = ["police_id", "status_id"]
    if basis.duplicated(subset=key).any():
        errors.append("auskunft: Basis hat doppelte (police_id, status_id)")
        return errors
    merged = scheibe[stamm].merge(
        basis[stamm], on=key, how="left", suffixes=("", "_basis"), indicator=True
    )
    if (merged["_merge"] != "both").any():
        errors.append("auskunft: Statuszeile (police_id, status_id) nicht in Basis")
        return errors
    diff_cols = [
        c for c in stamm
        if c not in key and not merged[c].equals(merged[f"{c}_basis"])
    ]
    if diff_cols:
        errors.append(f"auskunft: Stammfelder veraendert: {diff_cols}")
    return errors
