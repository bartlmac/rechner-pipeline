"""Deterministic Parquet persistence for portfolios.

Byte-determinism is part of the golden-master contract: the same DataFrame
must always serialize to the identical file. Therefore the table is built
from explicit arrays with an explicit Arrow schema (no pandas metadata blob,
which would embed library versions), a fixed compression codec, and pyarrow
is pinned exactly in ``pyproject.toml``. Date columns are stored as
``date32``, the natural Parquet type for calendar dates.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import List

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from rechner_pipeline.models.bestand import (
    STAMM_NAMES,
    STAMM_SPALTEN,
    ZEITSCHEIBEN_SPALTEN,
)

_ARROW_TYPES = {
    "int64": pa.int64(),
    "float64": pa.float64(),
    "object": pa.string(),
    "datetime64[ns]": pa.date32(),
}


def _schema_for(columns: List[str]) -> pa.schema:
    dtype_map = dict(STAMM_SPALTEN) | dict(ZEITSCHEIBEN_SPALTEN)
    fields = []
    for name in columns:
        if name not in dtype_map:
            raise ValueError(f"Unbekannte Portfolio-Spalte: {name}")
        fields.append(pa.field(name, _ARROW_TYPES[dtype_map[name]], nullable=False))
    return pa.schema(fields)


def write_portfolio(df: pd.DataFrame, path: Path) -> Path:
    """Write a portfolio (base or Zeitscheibe) deterministically to Parquet."""
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
    pq.write_table(table, path, compression="zstd")
    return path


def read_portfolio(path: Path) -> pd.DataFrame:
    """Read a portfolio back with canonical pandas dtypes."""
    table = pq.read_table(path)
    df = table.to_pandas()
    dtype_map = dict(STAMM_SPALTEN) | dict(ZEITSCHEIBEN_SPALTEN)
    for name in df.columns:
        if dtype_map.get(name) == "datetime64[ns]":
            df[name] = pd.to_datetime(df[name])
        elif dtype_map.get(name) is not None:
            df[name] = df[name].astype(dtype_map[name])
    ordered = [c for c in list(STAMM_NAMES) + [n for n, _ in ZEITSCHEIBEN_SPALTEN] if c in df.columns]
    return df[ordered]


def portfolio_hash(path: Path) -> str:
    """SHA-256 of the Parquet file bytes (golden-master anchor)."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
