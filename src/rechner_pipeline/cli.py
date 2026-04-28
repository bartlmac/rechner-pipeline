"""
Konsolidierte CLI-Eintrittspunkte.

``main()`` startet den klassischen ``PipelineRunner``.
``agentic_main()`` startet die LangGraph-orchestrierte Variante mit
Quality-Gates und Human-Review-Handoff.

Beide werden als Console-Scripts in ``pyproject.toml`` registriert
und sind zusätzlich über die Wrapper ``pipeline.py`` und
``agentic_pipeline.py`` im Repo-Root aufrufbar (rückwärtskompatibel).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from rechner_pipeline.orchestrate.agentic import (
    AgenticOptions,
    AgenticState,
    build_graph,
)
from rechner_pipeline.orchestrate.runner import PipelineOptions, PipelineRunner


def _add_common_options(ap: argparse.ArgumentParser) -> None:
    ap.add_argument(
        "--model",
        default="gpt-5.2",
        help="OpenAI model name for Responses API",
    )
    ap.add_argument(
        "--excel",
        default=None,
        help="Pfad zur Excel-Quelldatei (Default: <repo_root>/Tarifrechner_KLV.xlsm)",
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


def _options_from_namespace(ns: argparse.Namespace) -> PipelineOptions:
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


def _resolve_repo_root(repo_root: Path | None = None) -> Path:
    if repo_root is not None:
        return repo_root
    return Path.cwd()


def main(repo_root: Path | None = None) -> None:
    ap = argparse.ArgumentParser(prog="rechner-pipeline")
    _add_common_options(ap)
    ns = ap.parse_args()

    options = _options_from_namespace(ns)
    excel_path = Path(ns.excel) if ns.excel else None
    runner = PipelineRunner(
        repo_root=_resolve_repo_root(repo_root),
        options=options,
        excel_path=excel_path,
    )
    runner.run()


def agentic_main(repo_root: Path | None = None) -> None:
    ap = argparse.ArgumentParser(prog="rechner-pipeline-agentic")
    _add_common_options(ap)
    ap.add_argument("--max_retries_main", type=int, default=1)
    ap.add_argument("--max_retries_test", type=int, default=1)
    ap.add_argument("--fail_on_human_review", action="store_true")
    ns = ap.parse_args()

    pipeline_options = _options_from_namespace(ns)
    args = AgenticOptions(
        pipeline=pipeline_options,
        max_retries_main=max(0, ns.max_retries_main),
        max_retries_test=max(0, ns.max_retries_test),
        fail_on_human_review=ns.fail_on_human_review,
    )

    app = build_graph()
    initial_state: AgenticState = {
        "repo_root": str(_resolve_repo_root(repo_root)),
        "excel_path": ns.excel or "",
        "options": args.pipeline,
        "step_status": {},
        "errors": [],
        "retries": {
            "_max_main": args.max_retries_main,
            "_max_test": args.max_retries_test,
        },
        "human_review_required": False,
    }

    final_state = app.invoke(initial_state)
    if final_state.get("human_review_required"):
        if args.fail_on_human_review:
            raise RuntimeError("Pipeline ended in HUMAN_REVIEW_REQUIRED.")
        print("[DONE_WITH_HUMAN_REVIEW]")
        return
    print("[DONE]")
