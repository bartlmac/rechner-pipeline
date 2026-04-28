"""
LangGraph-basierter Wrapper um den klassischen ``PipelineRunner``.

Verwendet die öffentliche API des Runners (``assert_required_files``,
``prepare_manifest``, ``run_main_llm``, ``run_test_llm``, ``run_compare``)
statt private Underscore-Methoden.

Ergänzt:
- explizite State-Übergänge,
- Quality-Gates,
- begrenzte Retries,
- Human-Review-Handoff.
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, TypedDict

from rechner_pipeline.models.manifest import ExportManifest
from rechner_pipeline.orchestrate.runner import PipelineOptions, PipelineRunner

try:
    from langgraph.graph import END, START, StateGraph
except Exception as exc:  # pragma: no cover
    raise RuntimeError(
        "LangGraph is required for the agentic pipeline. "
        "Install it first, e.g. `pip install langgraph`."
    ) from exc


StepStatus = Literal["pending", "ok", "skipped", "error"]
Decision = Literal["continue", "retry", "human_review", "finish"]


class AgenticState(TypedDict, total=False):
    repo_root: str
    excel_path: str
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
    repo_root = Path(state["repo_root"])
    options = state["options"]
    excel_path_str = state.get("excel_path")
    excel_path = Path(excel_path_str) if excel_path_str else None
    return PipelineRunner(repo_root=repo_root, options=options, excel_path=excel_path)


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
        runner.assert_required_files()
        manifest = runner.prepare_manifest()
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
        runner.run_main_llm(manifest)
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
        runner.run_test_llm(manifest)
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
        runner.run_compare()
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
