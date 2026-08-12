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

import dataclasses as _dc
import datetime as _dt
from typing import Any, Dict, List, Mapping, Tuple

from rechner_pipeline.kern.model_point import ModelPoint as _KernModelPoint

# --------------------------------------------------------------------------- #
# Kernel ModelPoint contract
# --------------------------------------------------------------------------- #

#: The kernel's ``ModelPoint`` field surface (name -> python type name).
#: Contract fields per the KLV kernel generated 2026-07-22; provenance: the
#: workbook's defined names (x=B4, Sex=B5, n=B6, t=B7, VS=B8, zw=B9, Zins=E4,
#: Tafel=E5, alpha=E6, beta1=E7, gamma1=E8, gamma2=E9, gamma3=E10, k=E11,
#: MinAlterFlex=H4, MinRLZFlex=H5) plus the tariff knobs lifted from the
#: sheet's formula literals (Stornoabschlag, Zillmer-Dauer, ratzu-Staffel E12).
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
    ("stoab_satz", "float"),
    ("stoab_min", "float"),
    ("stoab_max", "float"),
    ("zillmer_dauer", "int"),
    ("ratzu_zw2", "float"),
    ("ratzu_zw4", "float"),
    ("ratzu_zw12", "float"),
)

#: Kernel fields that vary per contract (come from the portfolio row).
CONTRACT_FIELDS: Tuple[str, ...] = ("x", "sex", "n", "t", "sum_insured", "zw")

#: Kernel fields that come from the tariff generation (config), not the row.
GENERATION_FIELDS: Tuple[str, ...] = (
    "zins", "tafel", "alpha", "beta1", "gamma1", "gamma2", "gamma3",
    "policy_fee", "min_alter_flex", "min_rlz_flex",
    "stoab_satz", "stoab_min", "stoab_max", "zillmer_dauer",
    "ratzu_zw2", "ratzu_zw4", "ratzu_zw12",
)

#: Defaults of the kernel's defaulted (tariff-knob) fields — sourced from the
#: ModelPoint SSOT so a generation config may omit them (sheet behaviour).
GENERATION_FIELD_DEFAULTS: Dict[str, Any] = {
    f.name: f.default
    for f in _dc.fields(_KernModelPoint)
    if f.default is not _dc.MISSING
}

#: Allowed values for enum-like columns (module tuples, repo idiom).
SEX_VALUES: Tuple[str, ...] = ("M", "F")
#: Full status enum of the Fortschreibung (Ereignis-Engine): POL = active
#: premium-paying, PEX = active paid-up, STO/TOD/ABL = terminal.
STATUS_CODE_VALUES: Tuple[str, ...] = ("POL", "PEX", "STO", "TOD", "ABL")
#: The generator's base portfolio carries only active POL rows.
BASIS_STATUS: Tuple[str, ...] = ("POL",)
#: Statuses that count as in-force at a reporting date.
AKTIVE_STATUS: Tuple[str, ...] = ("POL", "PEX")
#: Terminal statuses: nothing may follow them in a Statushistorie.
TERMINALE_STATUS: Tuple[str, ...] = ("STO", "TOD", "ABL")
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

#: Statushistorie of the Fortschreibung: follow-up status rows per contract
#: (the base POL row lives in the Stamm; history rows start at status_id 2).
STATUS_HISTORIE_SPALTEN: Tuple[Tuple[str, str], ...] = (
    ("police_id", "int64"),
    ("status_id", "int64"),
    ("status_code", "object"),
    ("status_date", "datetime64[ns]"),
)

#: Ereignis-Ledger: one row per booked event with its kernel-computed amount.
LEDGER_SPALTEN: Tuple[Tuple[str, str], ...] = (
    ("police_id", "int64"),
    ("tarif_generation", "object"),
    ("ereignis", "object"),          # status_code of the event, or ERH (GeVo)
    ("vertragsjahr", "int64"),       # booked anniversary (completed years)
    ("status_date", "datetime64[ns]"),
    ("betrag_art", "object"),        # RKW | VS_bfr | Todesfallleistung | Ablaufleistung | VS_erhoehung
    ("betrag", "float64"),
)

#: Erhoehungsscheiben (dynamische Erhoehung): each row is an own layer of a
#: contract, actuarially an own model point (Schichtungsprinzip). The base
#: layer (Grundscheibe) is the Stamm row itself; Scheiben start at id 1.
#: Column names deliberately mirror the Stamm contract fields so the kernel
#: coupling (:func:`model_point_kwargs`) works on a Scheibe row directly
#: (sex/zahlweise/tarif_generation come from the Stamm, contract level).
SCHEIBEN_SPALTEN: Tuple[Tuple[str, str], ...] = (
    ("police_id", "int64"),
    ("scheiben_id", "int64"),          # 1, 2, ... je Police (0 = Grundscheibe im Stamm)
    ("erhoehung_jahr", "int64"),       # Vertragsjahr der Erhoehung (Jahrestag)
    ("erhoehung_datum", "datetime64[ns]"),
    ("entry_age", "int64"),            # Alter bei Erhoehung -> ModelPoint.x
    ("duration", "int64"),             # Restlaufzeit -> ModelPoint.n
    ("premium_duration", "int64"),     # Rest-Beitragsdauer -> ModelPoint.t
    ("sum_insured", "float64"),        # Erhoehungssumme -> ModelPoint.sum_insured
)

STAMM_NAMES: Tuple[str, ...] = tuple(n for n, _ in STAMM_SPALTEN)
ZEITSCHEIBEN_NAMES: Tuple[str, ...] = tuple(n for n, _ in ZEITSCHEIBEN_SPALTEN)
STATUS_HISTORIE_NAMES: Tuple[str, ...] = tuple(n for n, _ in STATUS_HISTORIE_SPALTEN)
LEDGER_NAMES: Tuple[str, ...] = tuple(n for n, _ in LEDGER_SPALTEN)
SCHEIBEN_NAMES: Tuple[str, ...] = tuple(n for n, _ in SCHEIBEN_SPALTEN)


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
    if not df["status_code"].isin(BASIS_STATUS).all():
        errors.append(f"status_code ausserhalb {BASIS_STATUS} (Basisbestand: nur POL)")
    if not df["zahlweise"].isin(ZAHLWEISE_VALUES).all():
        errors.append(f"zahlweise ausserhalb {ZAHLWEISE_VALUES}")

    num = df[["entry_age", "duration", "premium_duration", "sum_insured"]]
    # NaN-Vergleiche sind immer False — fehlende Werte muessen explizit
    # geprueft werden, sonst passieren sie jede Bandpruefung.
    nan_spalten = [c for c in num.columns if num[c].isna().any()]
    if nan_spalten:
        errors.append(f"fehlende Werte (NaN) in {nan_spalten}")
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


def validate_statushistorie(stamm: Any, historie: Any) -> List[str]:
    """Validate a Statushistorie against its base portfolio (error-list idiom).

    A history holds only follow-up statuses (the POL row lives in the Stamm):
    per police consecutive ``status_id`` starting at 2 in ``status_date``
    order, at most one PEX, at most one terminal status — and the terminal
    one is last. An empty history is valid.
    """
    errors: List[str] = []
    cols = list(historie.columns)
    if cols != list(STATUS_HISTORIE_NAMES):
        errors.append(
            f"historie: Spalten {cols} != erwartet {list(STATUS_HISTORIE_NAMES)}"
        )
        return errors
    for name, dtype in STATUS_HISTORIE_SPALTEN:
        actual = str(historie[name].dtype)
        if actual != dtype:
            errors.append(f"historie {name}: dtype {actual}, erwartet {dtype}")
    if len(historie) == 0:
        return errors

    folge_status = tuple(s for s in STATUS_CODE_VALUES if s not in BASIS_STATUS)
    if not historie["status_code"].isin(folge_status).all():
        errors.append(f"historie: status_code ausserhalb {folge_status}")
    unbekannt = set(historie["police_id"]) - set(stamm["police_id"])
    if unbekannt:
        errors.append(f"historie: police_id unbekannt: {sorted(unbekannt)[:5]}")
    if not (historie["status_date"].dt.day == 1).all():
        errors.append("historie: status_date nicht auf Monatsersten normalisiert")

    grenzen = stamm.set_index("police_id")[["insurance_start", "insurance_end"]]
    for police_id, gruppe in historie.groupby("police_id", sort=False):
        g = gruppe.sort_values("status_date", kind="stable")
        prefix = f"historie police {police_id}"
        if list(g["status_id"]) != list(range(2, 2 + len(g))):
            errors.append(f"{prefix}: status_id nicht fortlaufend ab 2")
        codes = list(g["status_code"])
        terminal = [c for c in codes if c in TERMINALE_STATUS]
        if len(terminal) > 1:
            errors.append(f"{prefix}: mehr als ein terminaler Status")
        elif terminal and codes[-1] not in TERMINALE_STATUS:
            errors.append(f"{prefix}: Status nach terminalem Status")
        if codes.count("PEX") > 1:
            errors.append(f"{prefix}: PEX mehrfach")
        if police_id in grenzen.index:
            start = grenzen.loc[police_id, "insurance_start"]
            ende = grenzen.loc[police_id, "insurance_end"]
            if (g["status_date"] <= start).any():
                errors.append(f"{prefix}: status_date vor/auf insurance_start")
            if (g["status_date"] > ende).any():
                errors.append(f"{prefix}: status_date nach insurance_end")
    return errors


def validate_scheiben(stamm: Any, scheiben: Any) -> List[str]:
    """Validate Erhoehungsscheiben against their base contracts (error list).

    Per police: consecutive ``scheiben_id`` starting at 1 in
    ``erhoehung_jahr`` order; each Scheibe must be arithmetically consistent
    with its Hauptvertrag (age at increase, remaining terms, anniversary
    date) and carry a positive Erhoehungssumme. Empty Scheiben are valid.
    """
    errors: List[str] = []
    cols = list(scheiben.columns)
    if cols != list(SCHEIBEN_NAMES):
        errors.append(f"scheiben: Spalten {cols} != erwartet {list(SCHEIBEN_NAMES)}")
        return errors
    for name, dtype in SCHEIBEN_SPALTEN:
        actual = str(scheiben[name].dtype)
        if actual != dtype:
            errors.append(f"scheiben {name}: dtype {actual}, erwartet {dtype}")
    if len(scheiben) == 0:
        return errors

    unbekannt = set(scheiben["police_id"]) - set(stamm["police_id"])
    if unbekannt:
        errors.append(f"scheiben: police_id unbekannt: {sorted(unbekannt)[:5]}")
        return errors
    if (scheiben["sum_insured"] <= 0).any():
        errors.append("scheiben: sum_insured <= 0")
    if not (scheiben["erhoehung_datum"].dt.day == 1).all():
        errors.append("scheiben: erhoehung_datum nicht auf Monatsersten normalisiert")

    haupt = stamm.set_index("police_id")
    for police_id, gruppe in scheiben.groupby("police_id", sort=False):
        g = gruppe.sort_values("erhoehung_jahr", kind="stable")
        prefix = f"scheiben police {police_id}"
        if list(g["scheiben_id"]) != list(range(1, 1 + len(g))):
            errors.append(f"{prefix}: scheiben_id nicht fortlaufend ab 1")
        h = haupt.loc[police_id]
        x, n, t = int(h["entry_age"]), int(h["duration"]), int(h["premium_duration"])
        start = h["insurance_start"]
        for _, s in g.iterrows():
            j = int(s["erhoehung_jahr"])
            if not 0 < j < t:
                errors.append(f"{prefix}: erhoehung_jahr {j} ausserhalb (0, t)")
                continue
            if int(s["entry_age"]) != x + j:
                errors.append(f"{prefix}: entry_age != Hauptvertrag-Alter + {j}")
            if int(s["duration"]) != n - j:
                errors.append(f"{prefix}: duration != Restlaufzeit {n - j}")
            if int(s["premium_duration"]) != t - j:
                errors.append(f"{prefix}: premium_duration != Rest-Beitragsdauer {t - j}")
            erwartet = _dt.date(start.year + j, start.month, 1)
            if s["erhoehung_datum"].date() != erwartet:
                errors.append(f"{prefix}: erhoehung_datum != Jahrestag {erwartet}")
    return errors


# --------------------------------------------------------------------------- #
# Kernel coupling: portfolio row + generation -> ModelPoint
# --------------------------------------------------------------------------- #


def model_point_kwargs(row: Mapping[str, Any], generation: Mapping[str, Any]) -> Dict[str, Any]:
    """Join one portfolio row with its tariff generation into ModelPoint kwargs.

    ``generation`` must provide the :data:`GENERATION_FIELDS`; the row provides
    the :data:`CONTRACT_FIELDS` (with portfolio column names). Tariff knobs
    absent from ``generation`` fall back to the kernel defaults
    (:data:`GENERATION_FIELD_DEFAULTS`) — the result always covers the full
    contract.
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
        if name in generation:
            kwargs[name] = generation[name]
        elif name in GENERATION_FIELD_DEFAULTS:
            kwargs[name] = GENERATION_FIELD_DEFAULTS[name]
        else:
            raise KeyError(f"Generation-Feld fehlt ohne Default: {name}")
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
