#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rückwärtskompatibler Wrapper.

Echte Logik liegt in ``rechner_pipeline.cli.main`` — auch als Console-Script
``rechner-pipeline`` über ``pip install -e .`` verfügbar.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_src_on_path() -> None:
    src = Path(__file__).resolve().parent / "src"
    if src.is_dir() and str(src) not in sys.path:
        sys.path.insert(0, str(src))


if __name__ == "__main__":
    _ensure_src_on_path()
    from rechner_pipeline.cli import main

    main(repo_root=Path(__file__).resolve().parent)
