"""Portfolio schema for the Bestandsdaten module — tightly coupled to the kernel.

Defines the portfolio (Bestand) schema whose per-contract fields map 1:1 onto
the stable kernel's :class:`rechner_pipeline.kern.ModelPoint` contract, plus
portfolio identity and time axis (coupling decided 2026-08-11: Bestand is real
kernel input). Since the kernel promotion (stable, versioned software in
``rechner_pipeline.kern``), the kernel's ``ModelPoint`` is the contract SSOT;
:data:`MODEL_POINT_FIELDS` is the Bestand-side mirror, kept identical by a
consistency test (``tests/test_kern.py``). Transient, agent-generated kernels
(``generated/``, migration path) must satisfy the same field list.

Design rules (project decisions):

* Schema style follows the repo idiom — plain dataclass/constant definitions
  with ``validate``-style functions returning error lists; no external schema
  library.
* Column names are snake_case after the kernel contract; the DAV reference
  toolchain's UPPER_CASE columns are semantic reference only.
* Per-contract fields carry only what varies per contract. Tariff-generation
  parameters (zins, tafel, cost loadings ...) live in the TOML config and are
  joined into a full ``ModelPoint`` only when the kernel is invoked
  (:func:`model_point_kwargs`).
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List, Mapping, Tuple

# --------------------------------------------------------------------------- #
# Kernel ModelPoint contract
# --------------------------------------------------------------------------- #

#: The kernel's ``inputs.ModelPoint`` field surface (name -> python type name).
#: Contract fields per the KLV kernel generated 2026-07-22; provenance: the
#: workbook's defined names (x=B4, Sex=B5, n=B6, t=B7, VS=B8, zw=B9, Zins=E4,
#: Tafel=E5, alpha=E6, beta1=E7, gamma1=E8, gamma2=E9, gamma3=E10, k=E11,
#: MinAlterFlex=H4, MinRLZFlex=H5).
MODEL_POINT_FIELDS: Tuple[Tuple[str, str], ...] = (
    ("x", "int"),
    ("sex", "str"),
    ("n", "int"),
    ("t", "int"),
    ("sum_insured", "float"),
    ("zw", "int"),
    ("zins", "float"),
    ("tafel", "str"),
    ("alpha", "float"),
    ("beta1", "float"),
    ("gamma1", "float"),
    ("gamma2", "float"),
    ("gamma3", "float"),
    ("policy_fee", "float"),
    ("min_alter_flex", "int"),
    ("min_rlz_flex", "int"),
)

#: Kernel fields that vary per contract (come from the portfolio row).
CONTRACT_FIELDS: Tuple[str, ...] = ("x", "sex", "n", "t", "sum_insured", "zw")

#: Kernel fields that come from the tariff generation (config), not the row.
GENERATION_FIELDS: Tuple[str, ...] = (
    "zins", "tafel", "alpha", "beta1", "gamma1", "gamma2", "gamma3",
    "policy_fee", "min_alter_flex", "min_rlz_flex",
)

#: Allowed values for enum-like columns (module tuples, repo idiom).
SEX_VALUES: Tuple[str, ...] = ("M", "F")
STATUS_CODE_VALUES: Tuple[str, ...] = ("POL",)  # Stufe 1: aktive Vertraege
ZAHLWEISE_VALUES: Tuple[int, ...] = (1, 2, 4, 12)

# --------------------------------------------------------------------------- #
# Portfolio columns
# --------------------------------------------------------------------------- #

#: Base (Stamm) portfolio columns in canonical order: (name, pandas dtype).
#: Dates are timezone-naive datetime64 in pandas and date32 in Parquet.
STAMM_SPALTEN: Tuple[Tuple[str, str], ...] = (
    ("police_id", "int64"),
    ("tarif_generation", "object"),
    ("status_id", "int64"),
    ("status_code", "object"),
    ("status_date", "datetime64[ns]"),
    ("sex", "object"),
    ("date_of_birth", "datetime64[ns]"),
    ("entry_age", "int64"),          # -> ModelPoint.x
    ("duration", "int64"),           # -> ModelPoint.n
    ("premium_duration", "int64"),   # -> ModelPoint.t
    ("sum_insured", "float64"),      # -> ModelPoint.sum_insured
    ("zahlweise", "int64"),          # -> ModelPoint.zw
    ("insurance_start", "datetime64[ns]"),
    ("insurance_end", "datetime64[ns]"),
    ("payment_end", "datetime64[ns]"),
)

#: Columns derived per Zeitscheibe (never part of the generated base portfolio).
ZEITSCHEIBEN_SPALTEN: Tuple[Tuple[str, str], ...] = (
    ("stichtag", "datetime64[ns]"),
    ("age", "int64"),
    ("months_exp", "int64"),
    ("months_rem", "int64"),
)

STAMM_NAMES: Tuple[str, ...] = tuple(n for n, _ in STAMM_SPALTEN)
ZEITSCHEIBEN_NAMES: Tuple[str, ...] = tuple(n for n, _ in ZEITSCHEIBEN_SPALTEN)


def stamm_dtypes() -> Dict[str, str]:
    return dict(STAMM_SPALTEN)


# --------------------------------------------------------------------------- #
# Validation (error-list idiom)
# --------------------------------------------------------------------------- #


def validate_portfolio(df: Any) -> List[str]:
    """Validate a base portfolio DataFrame against the Stamm schema.

    Returns a list of error strings; empty list means valid. Checks column
    set/order, dtypes, enum values, and hard row-level invariants.
    """
    errors: List[str] = []
    cols = list(df.columns)
    if cols != list(STAMM_NAMES):
        errors.append(
            f"Spalten weichen ab: erwartet {list(STAMM_NAMES)}, vorhanden {cols}"
        )
        return errors  # ohne korrekte Spalten sind Detailchecks sinnlos

    for name, dtype in STAMM_SPALTEN:
        actual = str(df[name].dtype)
        if actual != dtype:
            errors.append(f"Spalte {name}: dtype {actual}, erwartet {dtype}")

    if df["police_id"].duplicated().any():
        errors.append("police_id nicht eindeutig")
    if not df["sex"].isin(SEX_VALUES).all():
        errors.append(f"sex ausserhalb {SEX_VALUES}")
    if not df["status_code"].isin(STATUS_CODE_VALUES).all():
        errors.append(f"status_code ausserhalb {STATUS_CODE_VALUES}")
    if not df["zahlweise"].isin(ZAHLWEISE_VALUES).all():
        errors.append(f"zahlweise ausserhalb {ZAHLWEISE_VALUES}")

    num = df[["entry_age", "duration", "premium_duration", "sum_insured"]]
    if (num["entry_age"] < 0).any():
        errors.append("entry_age negativ")
    if (num["duration"] <= 0).any():
        errors.append("duration <= 0")
    if (num["premium_duration"] <= 0).any():
        errors.append("premium_duration <= 0")
    if (df["premium_duration"] > df["duration"]).any():
        errors.append("premium_duration > duration")
    if (num["sum_insured"] <= 0).any():
        errors.append("sum_insured <= 0")

    start = df["insurance_start"]
    if (df["insurance_end"] <= start).any():
        errors.append("insurance_end <= insurance_start")
    if (df["payment_end"] <= start).any():
        errors.append("payment_end <= insurance_start")
    if (df["status_date"] < start).any():
        errors.append("status_date vor insurance_start")
    # Monatserster-Konvention (deterministische Jahres-/Monatsarithmetik).
    for col in ("date_of_birth", "insurance_start", "insurance_end", "payment_end"):
        if not (df[col].dt.day == 1).all():
            errors.append(f"{col}: nicht auf Monatsersten normalisiert")

    # Datumsfelder muessen zu den Jahresfeldern konsistent sein (Monatszaehlung,
    # da alle Daten auf dem Monatsersten liegen).
    def _monat(col: str):
        return df[col].dt.year * 12 + df[col].dt.month

    if not (_monat("insurance_end") - _monat("insurance_start") == 12 * df["duration"]).all():
        errors.append("insurance_end != insurance_start + duration Jahre")
    if not (_monat("payment_end") - _monat("insurance_start") == 12 * df["premium_duration"]).all():
        errors.append("payment_end != insurance_start + premium_duration Jahre")
    if not (_monat("insurance_start") - _monat("date_of_birth") == 12 * df["entry_age"]).all():
        errors.append("date_of_birth passt nicht zu entry_age (Monatszaehlung)")

    return errors


# --------------------------------------------------------------------------- #
# Kernel coupling: portfolio row + generation -> ModelPoint
# --------------------------------------------------------------------------- #


def model_point_kwargs(row: Mapping[str, Any], generation: Mapping[str, Any]) -> Dict[str, Any]:
    """Join one portfolio row with its tariff generation into ModelPoint kwargs.

    ``generation`` must provide the :data:`GENERATION_FIELDS`; the row provides
    the :data:`CONTRACT_FIELDS` (with portfolio column names).
    """
    kwargs: Dict[str, Any] = {
        "x": int(row["entry_age"]),
        "sex": str(row["sex"]),
        "n": int(row["duration"]),
        "t": int(row["premium_duration"]),
        "sum_insured": float(row["sum_insured"]),
        "zw": int(row["zahlweise"]),
    }
    for name in GENERATION_FIELDS:
        kwargs[name] = generation[name]
    return kwargs


def render_inputs_py(kwargs: Mapping[str, Any]) -> str:
    """Render a kernel-compatible ``inputs.py`` for one contract.

    Used by the kernel-based Fortschreibung: the (transient) kernel binds to
    ``inputs.DEFAULT`` at import time, so per-contract evaluation runs in a
    fresh child process whose ``inputs.py`` is generated from the portfolio
    row. This function IS the executable form of the schema coupling.
    """
    missing = [n for n, _ in MODEL_POINT_FIELDS if n not in kwargs]
    if missing:
        raise ValueError(f"ModelPoint-Felder fehlen: {missing}")
    lines = [
        '"""Auto-generated kernel inputs for one portfolio contract."""',
        "",
        "from dataclasses import dataclass",
        "",
        "",
        "@dataclass(frozen=True)",
        "class ModelPoint:",
    ]
    for name, typ in MODEL_POINT_FIELDS:
        lines.append(f"    {name}: {typ}")
    lines.append("")
    lines.append("")
    args = []
    for name, typ in MODEL_POINT_FIELDS:
        value = kwargs[name]
        rendered = repr(str(value)) if typ == "str" else repr(
            int(value) if typ == "int" else float(value)
        )
        args.append(f"    {name}={rendered},")
    lines.append("DEFAULT = ModelPoint(")
    lines.extend(args)
    lines.append(")")
    lines.append("")
    return "\n".join(lines)
