"""``ExcelAdapter`` — zero-behavior-change Excel input adapter (§3.4).

This adapter is a thin wrapper around the current Excel extraction subsystem
(``rechner_pipeline.extract.excel.export_excel_infos``). It:

* runs ``export_excel_infos`` with the selected backend (``openpyxl`` default or
  ``com``), writing the byte-identical ``info_from_excel`` artifacts;
* re-reads the manifest dict the extractor produced and rebuilds it into an
  :class:`~rechner_pipeline.models.manifest.ExportManifest` **from ``Path``
  objects** (never strings), so the byte-compat caveat about ``/`` vs ``\\``
  separator mixing cannot bite;
* validates the manifest structurally **without mutating any Excel artifact**;
* computes an explicit ``expectation_coverage`` (``full|sparse|none``) plus the
  auditable :class:`~rechner_pipeline.models.bundle.CoverageDetail`.

It never rewrites, normalizes, or adds fields to the Excel artifacts themselves —
the extractor remains the byte-for-byte source of truth.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List, Tuple

from rechner_pipeline.adapters.base import InputAdapter
from rechner_pipeline.extract.excel import GENERATED_SUBDIR_NAME, export_excel_infos
from rechner_pipeline.models.bundle import (
    CONTRACT_VERSION,
    CoverageDetail,
    InputBundle,
)
from rechner_pipeline.models.manifest import ExportManifest, ManifestWarning

__all__ = ["ExcelAdapter", "ExcelAdapterError", "GENERATED_SUBDIR_NAME"]

#: Excel source suffixes the adapter recognizes (lowercase).
_EXCEL_SUFFIXES: Tuple[str, ...] = (".xlsm", ".xlsx", ".xlsb", ".xls")


class ExcelAdapterError(RuntimeError):
    """Raised when the Excel adapter cannot produce a valid bundle."""


def _manifest_from_export_dict(data: Dict[str, Any]) -> ExportManifest:
    """Rebuild an :class:`ExportManifest` from the extractor dict using ``Path``.

    The extractor returns path *strings*. ``ExportManifest.from_dict`` would also
    accept strings, but to honour the wave0 byte-compat caveat we construct every
    path field from :class:`pathlib.Path` objects explicitly here. This keeps the
    in-memory manifest's path objects consistent with the OS-native separators
    that the extractor already wrote into the artifacts on disk.
    """
    nm = data.get("names_manager_csv") or ""
    return ExportManifest(
        out_dir=Path(data["out_dir"]),
        sheet_csvs=[Path(p) for p in data.get("sheet_csvs", [])],
        vba_txts=[Path(p) for p in data.get("vba_txts", [])],
        names_manager_csv=Path(nm) if nm else None,
        replacements=dict(data.get("replacements", {})),
        llm_inputs=[Path(p) for p in data.get("llm_inputs", [])],
        all_outputs=[Path(p) for p in data.get("all_outputs", [])],
        warnings=[ManifestWarning.from_dict(w) for w in data.get("warnings", [])],
        prompt_runs=[],
        output_hashes=[],
    )


def _count_scalar_keys(scalar_files: List[Path]) -> Tuple[int, int]:
    """Return ``(total_keys, numeric_keys)`` across every ``*_scalar.json``."""
    import json

    total = 0
    numeric = 0
    for path in scalar_files:
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        for value in obj.values():
            total += 1
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                numeric += 1
    return total, numeric


def _count_table_cells(table_files: List[Path]) -> int:
    """Return the number of data cells across every ``*_table_values.csv``.

    Header row is excluded; an empty (no-column) CSV contributes zero. The files
    are read-only — no mutation of any artifact occurs.
    """
    total = 0
    for path in table_files:
        try:
            with path.open("r", encoding="utf-8", newline="") as f:
                reader = csv.reader(f)
                rows = list(reader)
        except Exception:
            continue
        if len(rows) <= 1:
            continue
        ncols = len(rows[0])
        for row in rows[1:]:
            total += min(len(row), ncols)
    return total


def _build_coverage_detail(out_dir: Path, manifest: ExportManifest) -> CoverageDetail:
    """Compute the §6.8.5 coverage breakdown from on-disk artifacts (read-only)."""
    scalar_files = sorted(out_dir.glob("*_scalar.json"), key=lambda p: p.name)
    table_files = sorted(out_dir.glob("*_table_values.csv"), key=lambda p: p.name)
    scalar_keys_expected, scalar_keys_numeric = _count_scalar_keys(scalar_files)
    table_cells = _count_table_cells(table_files)
    return CoverageDetail(
        scalar_files=len(scalar_files),
        scalar_keys_expected=scalar_keys_expected,
        scalar_keys_numeric=scalar_keys_numeric,
        table_files=len(table_files),
        table_cells_expected=table_cells,
        sheets_with_compressed=len(manifest.replacements),
        names_manager_present=manifest.names_manager_csv is not None,
        source_text_files=len(manifest.vba_txts),
    )


def _classify_coverage(detail: CoverageDetail) -> str:
    """Map a :class:`CoverageDetail` to ``full|sparse|none`` (explicit decision).

    * ``none``   — no numeric scalar expectations and no table cells at all.
    * ``full``   — numeric scalar expectations present (the Excel golden-master
      surface is genuinely populated, as it is for the KLV workbook).
    * ``sparse`` — derived expectation files exist but contain no numeric values
      (e.g. a workbook with formulas but no cached/numeric expected outputs).
    """
    has_numeric_scalars = detail.scalar_keys_numeric > 0
    has_table_cells = detail.table_cells_expected > 0
    if not has_numeric_scalars and not has_table_cells:
        return "none"
    if has_numeric_scalars:
        return "full"
    return "sparse"


class ExcelAdapter(InputAdapter):
    """Zero-behavior wrapper over ``export_excel_infos`` (§3.4)."""

    adapter_id = "excel"

    def __init__(self, *, backend: str = "openpyxl") -> None:
        if backend not in ("openpyxl", "com"):
            raise ExcelAdapterError(
                f"Unknown export backend {backend!r} (expected 'openpyxl' or 'com')."
            )
        self.backend = backend

    @classmethod
    def supports(cls, source_path: Path) -> bool:
        return Path(source_path).suffix.lower() in _EXCEL_SUFFIXES

    def extract(self, source_path: Path, out_dir: Path) -> InputBundle:
        source_path = Path(source_path)
        out_dir = Path(out_dir)

        if not source_path.exists():
            raise ExcelAdapterError(f"Excel source not found: {source_path}")

        # Run the byte-identical extractor with the selected backend. This writes
        # the manifest JSON and all artifacts; we do not touch them afterwards.
        manifest_dict = export_excel_infos(
            source_path,
            out_dir,
            save_manifest_json=True,
            backend=self.backend,
        )

        manifest = _manifest_from_export_dict(manifest_dict)

        # Structural validation without mutating any artifact: every llm_input
        # path must exist, and the manifest JSON file itself must be present.
        errors: List[str] = []
        if not manifest.llm_inputs:
            errors.append("manifest.llm_inputs is empty")
        for path in manifest.llm_inputs:
            if not Path(path).is_file():
                errors.append(f"llm_input path does not exist: {path}")

        manifest_path = out_dir / "export_manifest.json"
        if not manifest_path.is_file():
            errors.append(f"export_manifest.json was not written: {manifest_path}")

        if errors:
            raise ExcelAdapterError("; ".join(errors))

        coverage_detail = _build_coverage_detail(out_dir, manifest)
        coverage = _classify_coverage(coverage_detail)

        return InputBundle(
            source_path=str(source_path),
            adapter_id=self.adapter_id,
            out_dir=str(out_dir),
            manifest_path=str(manifest_path),
            expectation_coverage=coverage,
            contract_version=CONTRACT_VERSION,
            coverage_detail=coverage_detail,
            warnings=list(manifest.warnings),
            manifest=manifest,
        )
