from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


GENERATED_SUBDIR_NAME = "info_from_excel"

_INVALID_FS_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1F]+')
_XL_A1 = 1
_A1_RE = re.compile(r"(\$?)([A-Z]{1,3})(\$?)(\d+)$")
_SHEET_A1_RE = re.compile(r"((?:'[^']+'|[A-Za-z0-9_]+)!)?(\$?[A-Z]{1,3}\$?\d+)")


def _manifest_warning(
    *,
    code: str,
    stage: str,
    message: str,
    strict_error: bool,
    path: Path | str = "",
    details: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "code": code,
        "stage": stage,
        "message": message,
        "strict_error": strict_error,
    }
    if path:
        out["path"] = str(path)
    if details:
        out["details"] = details
    return out


def _import_pandas() -> Any:
    try:
        import pandas as pd  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "pandas is required for Excel metadata compression. "
            "Install the export dependencies first, e.g. `pip install -e '.[export]'`."
        ) from exc
    return pd


def _dispatch_excel_application() -> Any:
    try:
        import win32com.client  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "pywin32 is required for Excel COM export and is only available on Windows. "
            "Install the Windows export dependencies first, e.g. "
            "`pip install -e '.[export]'`."
        ) from exc
    return win32com.client.DispatchEx("Excel.Application")


def safe_filename(name: str, max_len: int = 180) -> str:
    cleaned = _INVALID_FS_CHARS.sub("_", name).strip(" .")
    return (cleaned or "unnamed")[:max_len]


def excel_value_to_text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    return str(v)


def is_empty_text(s: str) -> bool:
    return s.strip() == ""


def usedrange_bounds(ws) -> Optional[Tuple[int, int, int, int]]:
    used = ws.UsedRange
    sr = int(used.Row)
    sc = int(used.Column)
    rc = int(used.Rows.Count)
    cc = int(used.Columns.Count)

    if rc == 1 and cc == 1 and sr == 1 and sc == 1:
        cell = ws.Cells(1, 1)
        try:
            v = cell.Value
        except Exception:
            v = None
        try:
            f = cell.Formula
        except Exception:
            f = ""
        if (v is None or str(v) == "") and (f is None or str(f).strip() in ("", "=")):
            return None
    return (sr, sc, rc, cc)


def get_a1_address(cell) -> str:
    try:
        return str(cell.Address(False, False, _XL_A1))
    except Exception:
        return str(cell.Address)


def export_one_sheet(ws, out_dir: Path) -> Optional[Path]:
    sheet_name = str(ws.Name)
    out_path = out_dir / f"{safe_filename(sheet_name)}.csv"
    bounds = usedrange_bounds(ws)
    wrote_any = False

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Blatt", "Adresse", "Formel", "Wert"])

        if bounds is not None:
            start_row, start_col, row_count, col_count = bounds
            for r in range(start_row, start_row + row_count):
                for c in range(start_col, start_col + col_count):
                    cell = ws.Cells(r, c)
                    try:
                        formula = cell.Formula
                    except Exception:
                        formula = ""
                    try:
                        value = cell.Value
                    except Exception:
                        value = None

                    formula_txt = excel_value_to_text(formula)
                    value_txt = excel_value_to_text(value)
                    if is_empty_text(formula_txt) and is_empty_text(value_txt):
                        continue

                    writer.writerow([sheet_name, get_a1_address(cell), formula_txt, value_txt])
                    wrote_any = True

    if not wrote_any:
        try:
            out_path.unlink()
            print(f"[OK] Sheet had no Formel/Wert anywhere -> CSV removed: {sheet_name}")
        except Exception:
            print(f"[OK] Sheet had no Formel/Wert anywhere -> CSV kept (could not delete): {out_path}")
            return out_path
        return None

    print(f"[OK] Sheet exported: {sheet_name} -> {out_path}")
    return out_path


def export_all_sheets(wb, out_dir: Path) -> List[Path]:
    exported: List[Path] = []
    for ws in wb.Worksheets:
        p = export_one_sheet(ws, out_dir)
        if p is not None and p.exists():
            exported.append(p)
    return exported


def export_vba_modules_to_txt(
    wb,
    out_dir: Path,
    warnings: List[Dict[str, Any]] | None = None,
) -> List[Path]:
    vba_dir = out_dir / "vba"
    vba_dir.mkdir(parents=True, exist_ok=True)

    try:
        vbproj = wb.VBProject
    except Exception as exc:
        if warnings is not None:
            warnings.append(
                _manifest_warning(
                    code="export.vba_access_unavailable",
                    stage="export",
                    message="Cannot access VBProject; VBA modules were not exported.",
                    strict_error=True,
                    details={"exception": str(exc)},
                )
            )
        print(
            "[WARN] Cannot access VBProject.\n"
            "Enable in Excel:\n"
            "  File -> Options -> Trust Center -> Trust Center Settings -> Macro Settings\n"
            '  -> "Trust access to the VBA project object model"\n'
            f"Details: {exc}"
        )
        try:
            vba_dir.rmdir()
        except Exception:
            pass
        return []

    exported: List[Path] = []
    for comp in vbproj.VBComponents:
        comp_name = str(comp.Name)
        try:
            code_module = comp.CodeModule
            line_count = int(code_module.CountOfLines)
            code = code_module.Lines(1, line_count) if line_count > 0 else ""
        except Exception as exc:
            if warnings is not None:
                warnings.append(
                    _manifest_warning(
                        code="export.vba_module_read_failed",
                        stage="export",
                        message=f"Could not read VBA module '{comp_name}' completely.",
                        strict_error=True,
                        path=vba_dir / f"{safe_filename(comp_name)}.txt",
                        details={"module": comp_name, "exception": str(exc)},
                    )
                )
            code = f"' [ERROR reading code for {comp_name}] {exc}\n"

        if code is None or str(code).strip() == "":
            continue
        out_path = vba_dir / f"{safe_filename(comp_name)}.txt"
        out_path.write_text(str(code), encoding="utf-8", newline="\n")
        exported.append(out_path)
        print(f"[OK] VBA exported: {comp_name} -> {out_path}")

    if not exported:
        try:
            vba_dir.rmdir()
        except Exception:
            pass
    return exported


def export_name_manager_to_csv(wb, out_dir: Path) -> Optional[Path]:
    out_path = out_dir / "names_manager.csv"

    def try_get_name_scope(nm) -> str:
        try:
            p = nm.Parent
            if hasattr(p, "Name"):
                return f"Worksheet:{p.Name}"
            return "Workbook"
        except Exception:
            return ""

    def try_get_refers_to_range_address(nm) -> str:
        try:
            rng = nm.RefersToRange
            try:
                return str(rng.Address(False, False, _XL_A1, True))
            except Exception:
                return str(rng.Address)
        except Exception:
            return ""

    def try_get_value(nm) -> str:
        try:
            v = wb.Application.Evaluate(nm.Name)
            return excel_value_to_text(v)
        except Exception:
            return ""

    rows: List[List[str]] = []
    try:
        for nm in wb.Names:
            rows.append(
                [
                    str(getattr(nm, "Name", "")),
                    try_get_name_scope(nm),
                    str(getattr(nm, "Visible", "")),
                    excel_value_to_text(getattr(nm, "RefersTo", "")),
                    excel_value_to_text(getattr(nm, "RefersToLocal", "")),
                    try_get_refers_to_range_address(nm),
                    try_get_value(nm),
                    excel_value_to_text(getattr(nm, "Comment", "")),
                ]
            )
    except Exception:
        pass

    for ws in wb.Worksheets:
        try:
            names = ws.Names
        except Exception:
            continue
        for nm in names:
            rows.append(
                [
                    str(getattr(nm, "Name", "")),
                    try_get_name_scope(nm),
                    str(getattr(nm, "Visible", "")),
                    excel_value_to_text(getattr(nm, "RefersTo", "")),
                    excel_value_to_text(getattr(nm, "RefersToLocal", "")),
                    try_get_refers_to_range_address(nm),
                    try_get_value(nm),
                    excel_value_to_text(getattr(nm, "Comment", "")),
                ]
            )

    if not rows:
        print("[OK] Name Manager is empty -> no names_manager.csv generated")
        return None

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(
            [
                "Name",
                "Scope",
                "Visible",
                "RefersTo",
                "RefersToLocal",
                "RefersToRangeAddress",
                "ValueEvaluated",
                "Comment",
            ]
        )
        for row in rows:
            writer.writerow(row)

    print(f"[OK] Name Manager exported -> {out_path}")
    return out_path


def a1_to_rc(a1: str) -> Optional[Tuple[int, int, bool, bool]]:
    m = _A1_RE.match(a1)
    if not m:
        return None
    abs_col = bool(m.group(1))
    col_letters = m.group(2)
    abs_row = bool(m.group(3))
    row = int(m.group(4))
    col = 0
    for ch in col_letters:
        col = col * 26 + (ord(ch) - 64)
    return row, col, abs_row, abs_col


def addr_to_rc(addr: str) -> Optional[Tuple[int, int]]:
    parsed = a1_to_rc(addr.replace("$", ""))
    if not parsed:
        return None
    r, c, *_ = parsed
    return r, c


def rc_to_a1(r: int, c: int) -> str:
    letters = ""
    n = c
    while n:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return f"{letters}{r}"


def rc_to_r1c1(ref_row: int, ref_col: int, cur_row: int, cur_col: int, abs_row: bool, abs_col: bool) -> str:
    r = f"R{ref_row}" if abs_row else f"R[{ref_row - cur_row}]"
    c = f"C{ref_col}" if abs_col else f"C[{ref_col - cur_col}]"
    return r + c


def normalize_formula_to_pattern(formula: str, cur_addr: str) -> str:
    if not formula or not str(formula).startswith("="):
        return str(formula)

    cur = a1_to_rc(str(cur_addr).replace("$", ""))
    if not cur:
        return str(formula).strip()
    cur_row, cur_col, *_ = cur

    def repl(m: re.Match) -> str:
        prefix = m.group(1) or ""
        a1 = m.group(2)
        parsed = a1_to_rc(a1)
        if not parsed:
            return prefix + a1
        r, c, abs_row, abs_col = parsed
        return prefix + rc_to_r1c1(r, c, cur_row, cur_col, abs_row, abs_col)

    norm = _SHEET_A1_RE.sub(repl, str(formula))
    norm = re.sub(r"\s+", "", norm).upper()
    return norm


@dataclass(frozen=True)
class CellKey:
    sheet: str
    row: int
    col: int


@dataclass
class CellInfo:
    addr: str
    formula: str
    value: str

    def is_meaningful_label(self) -> bool:
        return bool(self.value.strip()) and not self.formula.startswith("=")


def build_cell_index(df: pd.DataFrame) -> Dict[CellKey, CellInfo]:
    idx: Dict[CellKey, CellInfo] = {}
    for _, r in df.iterrows():
        rc = addr_to_rc(str(r["Adresse"]))
        if not rc:
            continue
        row, col = rc
        idx[CellKey(str(r["Blatt"]), row, col)] = CellInfo(
            addr=str(r["Adresse"]),
            formula=str(r.get("Formel", "")),
            value=str(r.get("Wert", "")),
        )
    return idx


def split_into_contiguous_blocks(sub: pd.DataFrame) -> List[pd.DataFrame]:
    sub = sub.sort_values("_row").copy()
    blocks: List[List[int]] = []
    current: List[int] = []
    prev_row: Optional[int] = None
    for idx, r in sub.iterrows():
        row = int(r["_row"])
        if prev_row is None or row == prev_row + 1:
            current.append(idx)
        else:
            blocks.append(current)
            current = [idx]
        prev_row = row
    if current:
        blocks.append(current)
    return [sub.loc[b].copy() for b in blocks]


def choose_label(
    cell_index: Dict[CellKey, CellInfo],
    sheet: str,
    start_row: int,
    col: int,
    block_size: int,
) -> Tuple[str, str, str, str]:
    if block_size == 1:
        left = cell_index.get(CellKey(sheet, start_row, col - 1))
        if left and left.is_meaningful_label():
            return left.addr, left.value, left.formula, "left"
        above = cell_index.get(CellKey(sheet, start_row - 1, col))
        if above and above.is_meaningful_label():
            return above.addr, above.value, above.formula, "above"
        return "", "", "", ""

    above = cell_index.get(CellKey(sheet, start_row - 1, col))
    if above and above.is_meaningful_label():
        return above.addr, above.value, above.formula, "above"
    return "", "", "", ""


def compress_sheet_csv_with_labels(in_path: Path, out_path: Path, sep: str = ";") -> bool:
    pd = _import_pandas()

    df = pd.read_csv(in_path, sep=sep, dtype=str, keep_default_na=False)
    required = ["Blatt", "Adresse", "Formel", "Wert"]
    for c in required:
        if c not in df.columns:
            raise ValueError(f"Input CSV missing required column '{c}'. Found columns: {list(df.columns)}")

    is_formula = df["Formel"].astype(str).str.startswith("=")
    if not bool(is_formula.any()):
        return False

    df_values = df.loc[~is_formula].copy()
    df_formulas = df.loc[is_formula].copy()
    cell_index = build_cell_index(df)

    rc = df_formulas["Adresse"].astype(str).apply(addr_to_rc)
    df_formulas["_row"] = rc.apply(lambda x: int(x[0]) if x else -1)
    df_formulas["_col"] = rc.apply(lambda x: int(x[1]) if x else -1)
    df_formulas["Normalisierte_Formel_R1C1"] = [
        normalize_formula_to_pattern(f, a) for f, a in zip(df_formulas["Formel"], df_formulas["Adresse"])
    ]

    out_rows: List[Dict[str, Any]] = []
    for (sheet, col, norm), sub in df_formulas.groupby(["Blatt", "_col", "Normalisierte_Formel_R1C1"], sort=False):
        blocks = split_into_contiguous_blocks(sub)
        for b in blocks:
            start_row = int(b["_row"].min())
            end_row = int(b["_row"].max())
            block_size = len(b)
            col_i = int(col)
            label_addr, label_val, label_for, label_src = choose_label(
                cell_index=cell_index,
                sheet=str(sheet),
                start_row=start_row,
                col=col_i,
                block_size=block_size,
            )

            block_addr = (
                f"{rc_to_a1(start_row, col_i)}:{rc_to_a1(end_row, col_i)}"
                if start_row != end_row
                else rc_to_a1(start_row, col_i)
            )
            example_formula = b["Formel"].iloc[0]
            out_rows.append(
                {
                    "Section": "formulas_unique_block",
                    "Blatt": str(sheet),
                    "Adresse": block_addr,
                    "Formel": example_formula,
                    "Wert": "",
                    "Anzahl_Zellen": block_size,
                    "Normalisierte_Formel_R1C1": norm,
                    "Label_Adresse": label_addr,
                    "Label_Wert": label_val,
                    "Label_Formel": label_for,
                    "Label_Source": label_src,
                    "LLM_Hint": (
                        f"Label({label_src}:{label_addr})={label_val} | "
                        f"Formula={example_formula} | Pattern={norm}"
                    ),
                }
            )

    df_blocks = pd.DataFrame(out_rows)
    df_values.insert(0, "Section", "values")

    out_cols = [
        "Section",
        "Blatt",
        "Adresse",
        "Formel",
        "Wert",
        "Anzahl_Zellen",
        "Normalisierte_Formel_R1C1",
        "Label_Adresse",
        "Label_Wert",
        "Label_Formel",
        "Label_Source",
        "LLM_Hint",
    ]
    for c in out_cols:
        if c not in df_values.columns:
            df_values[c] = ""
        if c not in df_blocks.columns:
            df_blocks[c] = ""

    final = pd.concat([df_values[out_cols], df_blocks[out_cols]], ignore_index=True)
    final.to_csv(out_path, sep=sep, index=False)
    return True


def compress_exported_csvs(
    sheet_csv_paths: List[Path],
    out_dir: Path,
    warnings: List[Dict[str, Any]] | None = None,
) -> Dict[str, str]:
    del out_dir
    replacements: Dict[str, str] = {}
    for csv_path in sheet_csv_paths:
        name = csv_path.name
        if name == "names_manager.csv" or name.endswith("_compressed.csv"):
            continue

        out_path = csv_path.with_name(csv_path.stem + "_compressed.csv")
        if out_path.exists():
            replacements[str(csv_path)] = str(out_path)
            print(f"[OK] Compressed already exists: {csv_path.name} -> {out_path.name} (reuse)")
            continue

        try:
            written = compress_sheet_csv_with_labels(csv_path, out_path, sep=";")
            if written and out_path.exists():
                replacements[str(csv_path)] = str(out_path)
                print(f"[OK] Compressed: {csv_path.name} -> {out_path.name}")
            else:
                print(f"[SKIP] No formulas in: {csv_path.name} -> no compressed CSV generated")
        except Exception as exc:
            if warnings is not None:
                warnings.append(
                    _manifest_warning(
                        code="export.compression_failed",
                        stage="export",
                        message=f"Compression failed for {csv_path.name}; uncompressed CSV remains available.",
                        strict_error=True,
                        path=csv_path,
                        details={"exception": str(exc)},
                    )
                )
            print(f"[WARN] Compression failed for {csv_path.name}: {exc}")
    return replacements


def export_excel_infos(
    excel_path: Path,
    out_dir: Path,
    save_manifest_json: bool = True,
) -> Dict[str, Any]:
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel file not found: {excel_path}")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    excel = _dispatch_excel_application()
    excel.Visible = False
    excel.DisplayAlerts = False
    excel.AskToUpdateLinks = False

    wb = None
    try:
        wb = excel.Workbooks.Open(
            str(excel_path),
            ReadOnly=True,
            UpdateLinks=0,
            AddToMru=False,
        )

        warnings: List[Dict[str, Any]] = []

        sheet_csvs = export_all_sheets(wb, out_dir)
        vba_txts = export_vba_modules_to_txt(wb, out_dir, warnings=warnings)
        nm_csv = export_name_manager_to_csv(wb, out_dir)
        replacements = compress_exported_csvs(sheet_csvs, out_dir, warnings=warnings)

        llm_sheet_csvs: List[Path] = []
        for p in sheet_csvs:
            rep = replacements.get(str(p))
            llm_sheet_csvs.append(Path(rep) if rep else p)

        llm_inputs: List[Path] = []
        llm_inputs.extend(llm_sheet_csvs)
        if nm_csv is not None:
            llm_inputs.append(nm_csv)
        llm_inputs.extend(vba_txts)

        all_outputs_set = set()
        all_outputs_set.update(sheet_csvs)
        all_outputs_set.update(Path(v) for v in replacements.values())
        all_outputs_set.update(vba_txts)
        if nm_csv is not None:
            all_outputs_set.add(nm_csv)

        manifest: Dict[str, Any] = {
            "out_dir": str(out_dir),
            "sheet_csvs": [str(p) for p in sheet_csvs],
            "vba_txts": [str(p) for p in vba_txts],
            "names_manager_csv": str(nm_csv) if nm_csv is not None else "",
            "replacements": replacements,
            "llm_inputs": [str(p) for p in llm_inputs],
            "all_outputs": [str(p) for p in sorted(all_outputs_set, key=lambda x: str(x))],
            "warnings": warnings,
            "prompt_runs": [],
            "output_hashes": [],
        }

        print("\n[INFO] Extracting scalars and table values from compressed metadata...")
        from rechner_pipeline.extract.scalar_table import extract_all_pairs_in_info_dir

        scalar_warnings = extract_all_pairs_in_info_dir(out_dir)
        warnings.extend(scalar_warnings)
        scalar_files = sorted(out_dir.glob("*_scalar.json"), key=lambda p: p.name)
        table_files = sorted(out_dir.glob("*_table_values.csv"), key=lambda p: p.name)
        for p in scalar_files + table_files:
            manifest["all_outputs"].append(str(p))
        print(f"[OK] Scalars generated: {len(scalar_files)}")
        print(f"[OK] Table values generated: {len(table_files)}")
        print(f"\n[DONE] Output written to: {out_dir}")

        if save_manifest_json:
            manifest_path = out_dir / "export_manifest.json"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
                newline="\n",
            )
            manifest["all_outputs"].append(str(manifest_path))

        return manifest
    finally:
        if wb is not None:
            try:
                wb.Close(SaveChanges=False)
            except Exception:
                pass
        try:
            excel.Quit()
        except Exception:
            pass
