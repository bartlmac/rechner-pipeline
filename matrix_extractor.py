#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deprecated.

Diese Top-Level-Fassade existiert nur noch als rückwärtskompatible Brücke
auf die kanonischen Module unter ``rechner_pipeline``. Die Re-Exports werden
lazy geladen, damit ein Import von ``matrix_extractor`` keine Windows- oder
Excel-Exportabhängigkeiten benötigt. Der tatsächliche Excel-Export über
``export_excel_infos`` bleibt an die Exportabhängigkeiten gebunden
(``pandas`` sowie ``pywin32`` auf Windows).

Bitte direkt importieren:

- ``from rechner_pipeline.extract.excel import export_excel_infos, GENERATED_SUBDIR_NAME``
- ``from rechner_pipeline.generate.output import (
    extract_files_from_text, safe_write, write_extracted_files_to_generated_dir,
  )``
- ``from rechner_pipeline.extract.scalar_table import (
    extract_all_pairs_in_info_dir, extract_one_pair, extract_one_pair_from_values,
  )``
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from warnings import warn


def _ensure_src_on_path() -> None:
    src = Path(__file__).resolve().parent / "src"
    if src.is_dir() and str(src) not in sys.path:
        sys.path.insert(0, str(src))


_ensure_src_on_path()

warn(
    "matrix_extractor ist deprecated; importiere direkt aus rechner_pipeline.*",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "GENERATED_SUBDIR_NAME",
    "export_excel_infos",
    "extract_files_from_text",
    "safe_write",
    "write_extracted_files_to_generated_dir",
    "extract_all_pairs_in_info_dir",
    "extract_one_pair",
    "extract_one_pair_from_values",
]

_EXPORTS = {
    "GENERATED_SUBDIR_NAME": ("rechner_pipeline.extract.excel", "GENERATED_SUBDIR_NAME"),
    "export_excel_infos": ("rechner_pipeline.extract.excel", "export_excel_infos"),
    "extract_files_from_text": (
        "rechner_pipeline.generate.output",
        "extract_files_from_text",
    ),
    "safe_write": ("rechner_pipeline.generate.output", "safe_write"),
    "write_extracted_files_to_generated_dir": (
        "rechner_pipeline.generate.output",
        "write_extracted_files_to_generated_dir",
    ),
    "extract_all_pairs_in_info_dir": (
        "rechner_pipeline.extract.scalar_table",
        "extract_all_pairs_in_info_dir",
    ),
    "extract_one_pair": ("rechner_pipeline.extract.scalar_table", "extract_one_pair"),
    "extract_one_pair_from_values": (
        "rechner_pipeline.extract.scalar_table",
        "extract_one_pair_from_values",
    ),
}


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    module = __import__(module_name, fromlist=[attr_name])
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
