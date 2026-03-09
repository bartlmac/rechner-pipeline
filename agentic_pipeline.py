#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agentic_pipeline.py

LangGraph-based orchestration wrapper for the existing tariff pipeline.
This keeps the current business logic in PipelineRunner and adds:
- explicit state transitions
- quality gates
- bounded retries
- human review handoff
"""

from __future__ import annotations

import argparse
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, TypedDict

from manifest_model import ExportManifest
from pipeline_core import PipelineOptions, PipelineRunner

try:
    from langgraph.graph import END, START, StateGraph
except Exception as exc:  # pragma: no cover
    raise RuntimeError(
        "LangGraph is required for agentic_pipeline.py. "
        "Install it first, e.g. `pip install langgraph`."
    ) from exc


StepStatus = Literal["pending", "ok", "skipped", "error"]
Decision = Literal["continue", "retry", "human_review", "finish"]


class AgenticState(TypedDict, total=False):
    script_dir: str
    options: PipelineOptions
    manifest: ExportManifest
    step_status: Dict[str, StepStatus]
    failed_step: str | None
    errors: List[str]
    retries: Dict[str, int]
    gate_decision: Decision
    human_review_required: bool


@dataclass(frozen=True)
class AgenticOptions:
    pipeline: PipelineOptions
    max_retries_main: int
    max_retries_test: int
    fail_on_human_review: bool


def _runner_from_state(state: AgenticState) -> PipelineRunner:
    script_dir = Path(state["script_dir"])
    options = state["options"]
    return PipelineRunner(script_dir=script_dir, options=options)


def _set_step_status(state: AgenticState, step: str, status: StepStatus) -> Dict[str, Any]:
    step_status = dict(state.get("step_status", {}))
    step_status[step] = status
    return {"step_status": step_status}


def _append_error(state: AgenticState, step: str, exc: Exception) -> Dict[str, Any]:
    errors = list(state.get("errors", []))
    summary = f"{step}: {exc.__class__.__name__}: {exc}"
    errors.append(summary)
    errors.append(traceback.format_exc())
    return {"errors": errors, "failed_step": step}


def prepare_node(state: AgenticState) -> Dict[str, Any]:
    runner = _runner_from_state(state)
    try:
        runner._assert_required_files()
        manifest = runner._load_or_export_manifest()
        update: Dict[str, Any] = {"manifest": manifest, "failed_step": None}
        update.update(_set_step_status(state, "prepare", "ok"))
        return update
    except Exception as exc:
        update = _append_error(state, "prepare", exc)
        update.update(_set_step_status(state, "prepare", "error"))
        return update


def main_llm_node(state: AgenticState) -> Dict[str, Any]:
    options = state["options"]
    if options.skip_main_llm:
        return _set_step_status(state, "main_llm", "skipped")

    runner = _runner_from_state(state)
    manifest = state["manifest"]
    try:
        runner._run_main_llm(manifest)
        update: Dict[str, Any] = {"failed_step": None}
        update.update(_set_step_status(state, "main_llm", "ok"))
        return update
    except Exception as exc:
        update = _append_error(state, "main_llm", exc)
        update.update(_set_step_status(state, "main_llm", "error"))
        return update


def test_llm_node(state: AgenticState) -> Dict[str, Any]:
    options = state["options"]
    if options.skip_test_llm:
        return _set_step_status(state, "test_llm", "skipped")

    runner = _runner_from_state(state)
    manifest = state["manifest"]
    try:
        runner._run_test_llm(manifest)
        update: Dict[str, Any] = {"failed_step": None}
        update.update(_set_step_status(state, "test_llm", "ok"))
        return update
    except Exception as exc:
        update = _append_error(state, "test_llm", exc)
        update.update(_set_step_status(state, "test_llm", "error"))
        return update


def compare_node(state: AgenticState) -> Dict[str, Any]:
    options = state["options"]
    if options.skip_compare_run:
        return _set_step_status(state, "compare", "skipped")

    runner = _runner_from_state(state)
    try:
        runner._run_compare()
        update: Dict[str, Any] = {"failed_step": None}
        update.update(_set_step_status(state, "compare", "ok"))
        return update
    except Exception as exc:
        update = _append_error(state, "compare", exc)
        update.update(_set_step_status(state, "compare", "error"))
        return update


def _gate_step(
    state: AgenticState,
    step: str,
    max_retries: int,
) -> Dict[str, Any]:
    status = state.get("step_status", {}).get(step, "pending")
    if status != "error":
        return {"gate_decision": "continue"}

    retries = dict(state.get("retries", {}))
    current = retries.get(step, 0)
    if current < max_retries:
        retries[step] = current + 1
        return {
            "gate_decision": "retry",
            "retries": retries,
            "errors": [],
        }
    return {"gate_decision": "human_review", "human_review_required": True}


def gate_after_prepare_node(state: AgenticState) -> Dict[str, Any]:
    return _gate_step(state, "prepare", max_retries=0)


def gate_after_main_node(state: AgenticState) -> Dict[str, Any]:
    max_retries = state.get("retries", {}).get("_max_main", 0)
    return _gate_step(state, "main_llm", max_retries=max_retries)


def gate_after_test_node(state: AgenticState) -> Dict[str, Any]:
    max_retries = state.get("retries", {}).get("_max_test", 0)
    return _gate_step(state, "test_llm", max_retries=max_retries)


def gate_after_compare_node(state: AgenticState) -> Dict[str, Any]:
    status = state.get("step_status", {}).get("compare", "pending")
    if status == "error":
        return {"gate_decision": "human_review", "human_review_required": True}
    return {"gate_decision": "finish"}


def human_review_node(state: AgenticState) -> Dict[str, Any]:
    print("\n[HUMAN_REVIEW_REQUIRED]")
    for err in state.get("errors", []):
        print(err)
    print()
    return {}


def route_from_gate(state: AgenticState) -> str:
    return state.get("gate_decision", "continue")


def build_graph() -> Any:
    graph = StateGraph(AgenticState)

    graph.add_node("prepare", prepare_node)
    graph.add_node("gate_prepare", gate_after_prepare_node)
    graph.add_node("main_llm", main_llm_node)
    graph.add_node("gate_main", gate_after_main_node)
    graph.add_node("test_llm", test_llm_node)
    graph.add_node("gate_test", gate_after_test_node)
    graph.add_node("compare", compare_node)
    graph.add_node("gate_compare", gate_after_compare_node)
    graph.add_node("human_review", human_review_node)

    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "gate_prepare")

    graph.add_conditional_edges(
        "gate_prepare",
        route_from_gate,
        {
            "continue": "main_llm",
            "human_review": "human_review",
        },
    )

    graph.add_edge("main_llm", "gate_main")
    graph.add_conditional_edges(
        "gate_main",
        route_from_gate,
        {
            "continue": "test_llm",
            "retry": "main_llm",
            "human_review": "human_review",
        },
    )

    graph.add_edge("test_llm", "gate_test")
    graph.add_conditional_edges(
        "gate_test",
        route_from_gate,
        {
            "continue": "compare",
            "retry": "test_llm",
            "human_review": "human_review",
        },
    )

    graph.add_edge("compare", "gate_compare")
    graph.add_conditional_edges(
        "gate_compare",
        route_from_gate,
        {
            "finish": END,
            "human_review": "human_review",
        },
    )

    graph.add_edge("human_review", END)
    return graph.compile()


def parse_args() -> AgenticOptions:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gpt-5.2")
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
    ap.add_argument("--max_retries_main", type=int, default=1)
    ap.add_argument("--max_retries_test", type=int, default=1)
    ap.add_argument("--fail_on_human_review", action="store_true")
    ns = ap.parse_args()

    pipeline_options = PipelineOptions(
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
    return AgenticOptions(
        pipeline=pipeline_options,
        max_retries_main=max(0, ns.max_retries_main),
        max_retries_test=max(0, ns.max_retries_test),
        fail_on_human_review=ns.fail_on_human_review,
    )


def main() -> None:
    args = parse_args()
    app = build_graph()

    script_dir = Path(__file__).resolve().parent
    initial_state: AgenticState = {
        "script_dir": str(script_dir),
        "options": args.pipeline,
        "step_status": {},
        "errors": [],
        # Internal control values for gates.
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


if __name__ == "__main__":
    main()
