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


_DEFAULT_MODEL_BY_PROVIDER = {
    "openai": "gpt-5.2",
    "anthropic": "claude-sonnet-4-6",
    "replay": "replay",
}


def _add_common_options(ap: argparse.ArgumentParser) -> None:
    ap.add_argument(
        "--provider",
        default="openai",
        choices=["openai", "anthropic", "replay"],
        help="LLM-Provider (Default: openai; 'replay' = vorbereitete Ausgaben aus RP_REPLAY_DIR)",
    )
    ap.add_argument(
        "--model",
        default=None,
        help=(
            "Modellname. Default je Provider: openai=gpt-5.2, "
            "anthropic=claude-sonnet-4-6"
        ),
    )
    ap.add_argument(
        "--max_output_tokens",
        type=int,
        default=32_000,
        help="Max. Output-Tokens (nur Anthropic; OpenAI Responses ignoriert dies)",
    )
    ap.add_argument(
        "--excel",
        default=None,
        help=(
            "Pfad zur Excel-Quelldatei; relative Pfade werden gegen das "
            "Repo-Root aufgelöst (Default: examples/Tarifrechner_KLV.xlsm)"
        ),
    )

    ap.add_argument(
        "--export-backend",
        dest="export_backend",
        default="openpyxl",
        choices=["openpyxl", "com"],
        help=(
            "Excel-Extraktions-Backend: openpyxl (Default, plattformneutral, "
            "ohne Excel) oder com (Legacy, nur Windows + Excel)"
        ),
    )

    ap.add_argument(
        "--test-mode",
        dest="test_mode",
        default="fixed",
        choices=["fixed", "llm"],
        help=(
            "Validierung: fixed (Default, fester reviewter Golden-Master-Harness; "
            "Rechenkern muss golden_master_outputs() liefern) oder llm (Legacy, "
            "Test pro Lauf vom LLM generiert)"
        ),
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
    ap.add_argument(
        "--strict_manifest_warnings",
        action="store_true",
        help=(
            "Behandle als strict_error markierte Manifest-Warnungen als "
            "Pipeline-Fehler."
        ),
    )


def _options_from_namespace(ns: argparse.Namespace):
    from rechner_pipeline.orchestrate.runner import PipelineOptions

    model = ns.model or _DEFAULT_MODEL_BY_PROVIDER[ns.provider]

    return PipelineOptions(
        model=model,
        skip_export=ns.skip_export,
        skip_main_llm=ns.skip_main_llm,
        skip_test_llm=ns.skip_test_llm,
        skip_compare_run=ns.skip_compare_run,
        main_max_chars_per_file=ns.main_max_chars_per_file,
        main_max_total_chars=ns.main_max_total_chars,
        test_max_chars_per_file=ns.test_max_chars_per_file,
        test_max_total_chars=ns.test_max_total_chars,
        reasoning_effort=ns.reasoning_effort,
        strict_manifest_warnings=ns.strict_manifest_warnings,
        provider=ns.provider,
        max_output_tokens=ns.max_output_tokens,
        export_backend=ns.export_backend,
        test_mode=ns.test_mode,
    )


def _resolve_repo_root(repo_root: Path | None = None) -> Path:
    if repo_root is not None:
        return repo_root
    return Path.cwd()


def _resolve_excel_path(excel_arg: str | None, repo_root: Path) -> Path | None:
    if not excel_arg:
        return None
    excel_path = Path(excel_arg)
    if excel_path.is_absolute():
        return excel_path
    return repo_root / excel_path


def main(repo_root: Path | None = None) -> None:
    ap = argparse.ArgumentParser(prog="rechner-pipeline")
    _add_common_options(ap)
    ns = ap.parse_args()

    from rechner_pipeline.orchestrate.runner import PipelineRunner

    resolved_repo_root = _resolve_repo_root(repo_root)
    options = _options_from_namespace(ns)
    from rechner_pipeline.orchestrate import wflog
    wflog.set_demo(options.provider == "replay")
    excel_path = _resolve_excel_path(ns.excel, resolved_repo_root)
    runner = PipelineRunner(
        repo_root=resolved_repo_root,
        options=options,
        excel_path=excel_path,
    )
    runner.run()


def _print_summary_card(final_state, repo_root: Path) -> None:
    """Kompakte Abschluss-Karte am Lauf-Ende (nur bei RP_WFLOG)."""
    import json

    from rechner_pipeline.orchestrate import wflog

    if not wflog.enabled():
        return

    conv = []
    cpath = wflog.run_dir() / "convergence.csv"
    if cpath.exists():
        for line in cpath.read_text(encoding="utf-8").splitlines():
            parts = line.split(";")
            if len(parts) == 3:
                conv.append(parts)  # (n, Abweichungen, geprüft)

    iters = len(conv)
    seq = " -> ".join(d for _, d, _ in conv) if conv else "-"
    tested = conv[-1][2] if conv else "0"
    manifest = final_state.get("manifest")
    n_sheets = len(manifest.sheet_csvs) if manifest else 0
    n_scalars = 0
    for p in (repo_root / "info_from_excel").glob("*_scalar.json"):
        try:
            n_scalars += len(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    passed = (
        not final_state.get("human_review_required")
        and final_state.get("step_status", {}).get("compare") == "ok"
    )

    wflog.rule("Zusammenfassung")
    wflog.detail(f"Migriert: {n_sheets} Blatt/Blätter, {n_scalars} Skalare, {tested} Werte validiert")
    wflog.detail(f"Iterationen: {iters}  (Abweichungen je Runde: {seq})")
    wflog.detail(f"Laufzeit: {wflog.elapsed():.0f} s")
    if passed:
        wflog.ok("BESTANDEN — Rechenkern reproduziert die Excel-Werte")
    else:
        wflog.fail("nicht bestanden / Human-Review erforderlich")


def agentic_main(repo_root: Path | None = None) -> None:
    ap = argparse.ArgumentParser(prog="rechner-pipeline-agentic")
    _add_common_options(ap)
    ap.add_argument("--max_retries_main", type=int, default=1)
    ap.add_argument("--max_retries_test", type=int, default=1)
    ap.add_argument("--fail_on_human_review", action="store_true")
    ns = ap.parse_args()

    from rechner_pipeline.orchestrate.agentic import AgenticOptions, build_graph
    from rechner_pipeline.orchestrate.dossier import write_run_dossier
    from rechner_pipeline.orchestrate.runner import PipelineRunner

    resolved_repo_root = _resolve_repo_root(repo_root)
    pipeline_options = _options_from_namespace(ns)
    from rechner_pipeline.orchestrate import wflog
    wflog.set_demo(pipeline_options.provider == "replay")
    args = AgenticOptions(
        pipeline=pipeline_options,
        max_retries_main=max(0, ns.max_retries_main),
        max_retries_test=max(0, ns.max_retries_test),
        fail_on_human_review=ns.fail_on_human_review,
    )

    app = build_graph()
    excel_path = _resolve_excel_path(ns.excel, resolved_repo_root)
    initial_state = {
        "repo_root": str(resolved_repo_root),
        "excel_path": str(excel_path) if excel_path else "",
        "options": args.pipeline,
        "step_status": {},
        "errors": [],
        "diagnostics": [],
        "repair_contexts": {},
        "repair_artifacts": {},
        "retries": {
            "_max_main": args.max_retries_main,
            "_max_test": args.max_retries_test,
        },
        "human_review_required": False,
    }

    final_state = app.invoke(initial_state)
    _print_summary_card(final_state, resolved_repo_root)
    runner = PipelineRunner(
        repo_root=resolved_repo_root,
        options=args.pipeline,
        excel_path=excel_path,
    )
    if final_state.get("human_review_required"):
        dossier_path = write_run_dossier(
            runner,
            manifest=final_state.get("manifest"),
            run_status="human_review_required",
            human_review_required=True,
            agentic_state=final_state,
        )
        print(f"[DOSSIER] {dossier_path}")
        if args.fail_on_human_review:
            raise RuntimeError("Pipeline ended in HUMAN_REVIEW_REQUIRED.")
        print("[DONE_WITH_HUMAN_REVIEW]")
        return
    dossier_path = write_run_dossier(
        runner,
        manifest=final_state.get("manifest"),
        run_status="completed",
        human_review_required=False,
        agentic_state=final_state,
    )
    print(f"[DOSSIER] {dossier_path}")
    print("[DONE]")
