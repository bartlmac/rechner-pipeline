"""Deterministic Parquet persistence for portfolios.

Byte-determinism is part of the golden-master contract: the same DataFrame
must always serialize to the identical file. Therefore the table is built
from explicit arrays with an explicit Arrow schema (no pandas metadata blob,
which would embed library versions), a fixed compression codec, and pyarrow
is pinned exactly in ``pyproject.toml``. Date columns are stored as
``date32``, the natural Parquet type for calendar dates.

Knoten: klv, bu
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import List, Optional, Sequence

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from rechner_pipeline.models.bestand import (
    ABSCHLUSS_NAMES,
    ABSCHLUSS_SPALTEN,
    LEDGER_NAMES,
    LEDGER_SPALTEN,
    MERKMALE_NAMES,
    MERKMALE_SPALTEN,
    VERANKERUNG_NAMES,
    VERANKERUNG_SPALTEN,
    SCHEIBEN_NAMES,
    SCHEIBEN_SPALTEN,
    STAMM_NAMES,
    STAMM_SPALTEN,
    ZEITSCHEIBEN_SPALTEN,
)

#: All persistable table families share one name->dtype map (Statushistorie
#: columns are a subset of the Stamm columns, dtypes are consistent).
_DTYPE_MAP = (
    dict(ABSCHLUSS_SPALTEN)
    | dict(STAMM_SPALTEN)
    | dict(ZEITSCHEIBEN_SPALTEN)
    | dict(LEDGER_SPALTEN)
    | dict(SCHEIBEN_SPALTEN)
    | dict(MERKMALE_SPALTEN)
    | dict(VERANKERUNG_SPALTEN)
)

_ARROW_TYPES = {
    "int64": pa.int64(),
    "float64": pa.float64(),
    "object": pa.string(),
    "datetime64[ns]": pa.date32(),
}


def _schema_for(columns: List[str]) -> pa.schema:
    fields = []
    for name in columns:
        if name not in _DTYPE_MAP:
            raise ValueError(f"Unbekannte Portfolio-Spalte: {name}")
        fields.append(pa.field(name, _ARROW_TYPES[_DTYPE_MAP[name]], nullable=False))
    return pa.schema(fields)


def write_portfolio(df: pd.DataFrame, path: Path) -> Path:
    """Write a table deterministically to Parquet.

    Supports the portfolio families (base portfolio, Auskunfts-Schnitt,
    Statushistorie — column subsets of the Stamm) and the Ereignis-Ledger.
    """
    columns = list(df.columns)
    schema = _schema_for(columns)
    arrays = []
    for name in columns:
        typ = schema.field(name).type
        if typ == pa.date32():
            arrays.append(pa.array(df[name].dt.date, type=typ))
        elif typ == pa.string():
            arrays.append(pa.array([str(v) for v in df[name]], type=typ))
        else:
            arrays.append(pa.array(df[name].to_numpy(), type=typ))
    table = pa.Table.from_arrays(arrays, schema=schema)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Erst vollstaendig daneben schreiben, dann in einem Zug an den Zielpfad
    # umhaengen. os.replace ist auf einem Dateisystem atomar: Es gibt die
    # Zieldatei entweder alt oder neu, nie halb. Direkt auf den Zielpfad
    # geschrieben hinterlaesst ein Abbruch — oder ein zweiter Schreiber —
    # einen Stumpf mit kaputtem Parquet-Fuss, und der ist eine Sackgasse:
    # Fuer schreibe_abschluss existiert der Stichtag dann bereits, waehrend
    # ihn niemand mehr lesen kann.
    # Der temporaere Name muss je AUFRUF eindeutig sein, nicht je Prozess:
    # zwei Threads teilen sich die PID und wuerden sonst dieselbe Datei
    # beschreiben und einander wegziehen.
    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        pq.write_table(table, tmp, compression="zstd")
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return path


def read_portfolio(
    path: Path,
    *,
    expected_columns: Optional[Sequence[str]] = None,
) -> pd.DataFrame:
    """Read a table back with canonical pandas dtypes and column order.

    If ``expected_columns`` is supplied by a gate, the physical Parquet
    columns *and their Arrow types* are checked before conversion and
    canonical selection.  This must happen before ``astype``: otherwise an
    integral-looking ``double`` column such as ``status_id = 1.0`` would be
    silently normalised to ``int64`` and the gate would validate data against
    a schema the file itself never satisfied.  Without ``expected_columns``,
    columns unknown to every persistable portfolio family are still rejected.
    """
    table = pq.read_table(path)
    erlaubt = (
        set(expected_columns) if expected_columns is not None else set(_DTYPE_MAP)
    )
    unbekannt = [name for name in table.column_names if name not in erlaubt]
    if unbekannt:
        raise ValueError(
            f"Unbekannte physische Parquet-Spalten: {unbekannt}"
        )
    if expected_columns is not None:
        typfehler = []
        for name in expected_columns:
            if name not in table.column_names:
                continue
            erwartet = _ARROW_TYPES[_DTYPE_MAP[name]]
            vorhanden = table.schema.field(name).type
            if vorhanden != erwartet:
                typfehler.append(
                    f"{name}: Typ {vorhanden}, erwartet {erwartet}"
                )
        if typfehler:
            raise ValueError(
                "Physisches Parquet-Schema weicht ab: " + "; ".join(typfehler)
            )
    df = table.to_pandas()
    for name in df.columns:
        if _DTYPE_MAP.get(name) == "datetime64[ns]":
            df[name] = pd.to_datetime(df[name])
        elif _DTYPE_MAP.get(name) is not None:
            df[name] = df[name].astype(_DTYPE_MAP[name])
    if set(df.columns) == set(ABSCHLUSS_NAMES):
        return df[list(ABSCHLUSS_NAMES)]
    if set(df.columns) == set(LEDGER_NAMES):
        return df[list(LEDGER_NAMES)]
    if set(df.columns) == set(SCHEIBEN_NAMES):
        return df[list(SCHEIBEN_NAMES)]
    if set(df.columns) == set(MERKMALE_NAMES):
        return df[list(MERKMALE_NAMES)]
    if set(df.columns) == set(VERANKERUNG_NAMES):
        return df[list(VERANKERUNG_NAMES)]
    ordered = [c for c in list(STAMM_NAMES) + [n for n, _ in ZEITSCHEIBEN_SPALTEN] if c in df.columns]
    return df[ordered]


def portfolio_hash(path: Path) -> str:
    """SHA-256 of the Parquet file bytes (golden-master reference value)."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
