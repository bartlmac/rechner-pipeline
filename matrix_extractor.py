#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deprecated.

Diese Top-Level-Fassade existiert nur noch als rückwärtskompatible Brücke
auf die kanonischen Module unter ``rechner_pipeline``. Bitte direkt importieren:

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

from rechner_pipeline.extract.excel import (  # noqa: E402
    GENERATED_SUBDIR_NAME,
    export_excel_infos,
)
from rechner_pipeline.extract.scalar_table import (  # noqa: E402
    extract_all_pairs_in_info_dir,
    extract_one_pair,
    extract_one_pair_from_values,
)
from rechner_pipeline.generate.output import (  # noqa: E402
    extract_files_from_text,
    safe_write,
    write_extracted_files_to_generated_dir,
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
