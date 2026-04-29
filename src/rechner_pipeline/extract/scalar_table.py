from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

RANGE_RE = re.compile(r"^\$?([A-Z]+)\$?(\d+)\s*:\s*\$?([A-Z]+)\$?(\d+)$")
CELL_RE = re.compile(r"^\$?([A-Z]+)\$?(\d+)$")


def _import_pandas() -> Any:
    try:
        import pandas as pd  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "pandas is required for scalar and table extraction. "
            "Install the export dependencies first, e.g. `pip install -e '.[export]'`."
        ) from exc
    return pd


def col_to_num(col: str) -> int:
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return n


def num_to_col(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(ord("A") + r) + s
    return s


def parse_cell(addr: str) -> Tuple[str, int]:
    addr = addr.replace("$", "").strip()
    m = CELL_RE.match(addr)
    if not m:
        raise ValueError(addr)
    return m.group(1), int(m.group(2))


def make_cell(col: str, row: int) -> str:
    return f"${col}${row}"


def parse_range(rng: str) -> Tuple[str, int, str, int]:
    rng = rng.replace("$", "").strip()
    m = RANGE_RE.match(rng)
    if not m:
        raise ValueError(rng)
    return m.group(1), int(m.group(2)), m.group(3), int(m.group(4))


def try_float(x: Any) -> Any:
    try:
        return float(x)
    except Exception:
        return x


def load_address_values(path: Path) -> Dict[str, Any]:
    pd = _import_pandas()

    df = pd.read_csv(path)
    return {str(r["Adresse"]).strip(): try_float(r["Wert"]) for _, r in df.iterrows()}


def load_compressed(path: Path):
    pd = _import_pandas()

    return pd.read_csv(path, sep=";")


def load_sheet_values(path: Path) -> Dict[str, Any]:
    pd = _import_pandas()

    df = pd.read_csv(path, sep=";", dtype=str, keep_default_na=False)
    if "Adresse" not in df.columns or "Wert" not in df.columns:
        raise ValueError(f"Missing required columns in {path.name}: need 'Adresse' and 'Wert'")
    out: Dict[str, Any] = {}
    for _, r in df.iterrows():
        addr = str(r.get("Adresse", "")).strip()
        if not addr:
            continue
        val_raw = r.get("Wert", "")
        out[addr] = try_float(val_raw) if val_raw != "" else None
    return out


def detect_left_index_column(
    fv: Dict[str, Any],
    header_row: int,
    r1: int,
    r2: int,
    col_start_num: int,
) -> Optional[Tuple[str, List[Any]]]:
    col_num = col_start_num - 1
    if col_num < 1:
        return None

    col = num_to_col(col_num)
    header = fv.get(make_cell(col, header_row))
    if not isinstance(header, str):
        return None

    values = [fv.get(make_cell(col, r)) for r in range(r1, r2 + 1)]
    nums = [v for v in values if isinstance(v, (int, float))]
    if len(nums) < 3:
        return None

    step = nums[1] - nums[0]
    if all(nums[i] - nums[i - 1] == step for i in range(2, len(nums))):
        return header, values
    return None


def extract_one_pair_from_values(fv: Dict[str, Any], comp_csv: Path, out_dir: Path, prefix: str) -> None:
    pd = _import_pandas()

    cp = load_compressed(comp_csv)

    scalars: Dict[str, Any] = {}
    scal_df = cp[(cp["Label_Wert"].notna()) & (cp["Anzahl_Zellen"] == 1)]
    for _, r in scal_df.iterrows():
        label = str(r["Label_Wert"]).strip()
        addr = str(r["Adresse"]).strip()
        try:
            c, rr = parse_cell(addr)
            addr = make_cell(c, rr)
        except Exception:
            pass
        scalars[label] = fv.get(addr)

    scalar_out = out_dir / f"{prefix}_scalar.json"
    scalar_out.write_text(json.dumps(scalars, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Scalar exported: {scalar_out}")

    tables: List[pd.DataFrame] = []
    mat_df = cp[(cp["Label_Wert"].notna()) & (cp["Anzahl_Zellen"] > 1)]
    groups: Dict[Tuple[int, int], List[dict]] = {}

    for _, r in mat_df.iterrows():
        try:
            c1, r1, c2, r2 = parse_range(str(r["Adresse"]))
        except Exception:
            continue
        if c1 != c2:
            continue
        groups.setdefault((r1, r2), []).append({"col": c1, "label": str(r["Label_Wert"]).strip()})

    for (r1, r2), cols in groups.items():
        cols = sorted(cols, key=lambda x: col_to_num(x["col"]))
        col_nums = [col_to_num(c["col"]) for c in cols]

        data = {
            c["label"]: [fv.get(make_cell(c["col"], rr)) for rr in range(r1, r2 + 1)]
            for c in cols
        }
        df = pd.DataFrame(data)
        left = detect_left_index_column(fv, r1 - 1, r1, r2, min(col_nums))
        if left:
            df.insert(0, left[0], left[1])
        tables.append(df)

    out_csv = out_dir / f"{prefix}_table_values.csv"
    if tables:
        pd.concat(tables, ignore_index=True).to_csv(out_csv, index=False)
    else:
        pd.DataFrame().to_csv(out_csv, index=False)
    print(f"[OK] Table values exported: {out_csv}")


def extract_one_pair(addr_csv: Path, comp_csv: Path, out_dir: Path, prefix: str) -> None:
    try:
        fv = load_sheet_values(addr_csv)
    except Exception:
        fv = load_address_values(addr_csv)
    extract_one_pair_from_values(fv, comp_csv, out_dir, prefix)


def extract_all_pairs_in_info_dir(info_dir: Path) -> List[Dict[str, Any]]:
    warnings: List[Dict[str, Any]] = []
    compressed = {p.stem.replace("_compressed", ""): p for p in info_dir.glob("*_compressed.csv")}
    address_values = {
        p.stem.replace("_address_values", ""): p for p in info_dir.glob("*_address_values.csv")
    }
    sheet_csv = {
        p.stem: p
        for p in info_dir.glob("*.csv")
        if not p.name.endswith("_compressed.csv") and not p.name.endswith("_address_values.csv")
    }

    for prefix in sorted(compressed.keys()):
        comp_path = compressed[prefix]
        if prefix in address_values:
            addr_path = address_values[prefix]
        elif prefix in sheet_csv:
            addr_path = sheet_csv[prefix]
        else:
            warnings.append(
                {
                    "code": "export.scalar_table_value_source_missing",
                    "stage": "export",
                    "message": (
                        f"No value source for prefix '{prefix}'; scalar/table "
                        "values were not extracted for this sheet."
                    ),
                    "strict_error": True,
                    "path": str(comp_path),
                    "details": {"prefix": prefix},
                }
            )
            print(
                f"[SKIP] No value source for prefix '{prefix}': "
                f"need {prefix}_address_values.csv or {prefix}.csv"
            )
            continue
        try:
            extract_one_pair(addr_path, comp_path, info_dir, prefix)
        except Exception as exc:
            warnings.append(
                {
                    "code": "export.scalar_table_extraction_failed",
                    "stage": "export",
                    "message": (
                        f"Failed extracting scalar/table values for prefix '{prefix}'."
                    ),
                    "strict_error": True,
                    "path": str(comp_path),
                    "details": {"prefix": prefix, "exception": str(exc)},
                }
            )
            print(f"[WARN] Failed extracting for prefix '{prefix}': {exc}")
    return warnings
