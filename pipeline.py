#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline.py

Thin CLI entrypoint for the tariff pipeline.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from pipeline_core import PipelineOptions, PipelineRunner


def parse_args() -> PipelineOptions:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--model",
        default="gpt-5.2",
        help="OpenAI model name for Responses API",
    )

    ap.add_argument("--skip_export", action="store_true")
    ap.add_argument("--skip_main_llm", action="store_true")
    ap.add_argument("--skip_test_llm", action="store_true")
    ap.add_argument("--skip_compare_run", action="store_true")

    ap.add_argument("--main_max_chars_per_file", type=int, default=500_000)
    ap.add_argument("--main_max_total_chars", type=int, default=2_500_000)
    ap.add_argument("--test_max_chars_per_file", type=int, default=500_000)
    ap.add_argument("--test_max_total_chars", type=int, default=2_500_000)

    ap.add_argument(
        "--reasoning_effort",
        default="medium",
        choices=["low", "medium", "high"],
    )
    ns = ap.parse_args()
    return PipelineOptions(
        model=ns.model,
        skip_export=ns.skip_export,
        skip_main_llm=ns.skip_main_llm,
        skip_test_llm=ns.skip_test_llm,
        skip_compare_run=ns.skip_compare_run,
        main_max_chars_per_file=ns.main_max_chars_per_file,
        main_max_total_chars=ns.main_max_total_chars,
        test_max_chars_per_file=ns.test_max_chars_per_file,
        test_max_total_chars=ns.test_max_total_chars,
        reasoning_effort=ns.reasoning_effort,
    )


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    options = parse_args()
    runner = PipelineRunner(script_dir=script_dir, options=options)
    runner.run()


if __name__ == "__main__":
    main()
