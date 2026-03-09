#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backward-compatible facade for the extractor modules.

This module keeps the previous public API stable while delegating to:
- excel_exporter.py
- llm_output_extractor.py
- scalar_table_extractor.py
"""

from __future__ import annotations

from excel_exporter import EXCEL_PATH, GENERATED_SUBDIR_NAME, export_excel_infos
from llm_output_extractor import (
    extract_files_from_text,
    safe_write,
    write_extracted_files_to_generated_dir,
)
from scalar_table_extractor import (
    extract_all_pairs_in_info_dir,
    extract_one_pair,
    extract_one_pair_from_values,
)

__all__ = [
    "EXCEL_PATH",
    "GENERATED_SUBDIR_NAME",
    "export_excel_infos",
    "extract_files_from_text",
    "safe_write",
    "write_extracted_files_to_generated_dir",
    "extract_all_pairs_in_info_dir",
    "extract_one_pair",
    "extract_one_pair_from_values",
]


def main() -> None:
    export_excel_infos()


if __name__ == "__main__":
    main()
