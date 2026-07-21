"""``dossier`` toolbox command — gate G8 (dossier-completeness, §3.5).

    python -m rechner_pipeline.toolbox.dossier \
        --repo-root . --generated-dir generated --info-dir info_from_excel \
        --diagnostics-dir runs/<run-id> --status completed

This is the mechanical-acceptance gate. It reads the §6.8.2 gate-result ledger
entries that the other gate commands wrote into ``--diagnostics-dir``
(``<command>.gate.json`` files), aggregates them into:

* ``<diagnostics-dir>/qa_report.json`` (§6.8.3) — the computed acceptance
  record, and
* ``<diagnostics-dir>/run_dossier.json`` (§6.8.4) — the upgraded
  ``schema_version=2`` provenance dossier,

and decides mechanical acceptance. Acceptance is computed by
:meth:`schemas.QaReport.compute_accepted` (every ``required`` gate ``passed`` AND
no blocking warning AND no unapproved open assumption). G8 is **blocking
(exit 40)** when a gate result is missing, a required hash is missing, an open
assumption is unapproved, or a required gate did not pass (§3.3 dossier row).

stdout is exactly one JSON object (the §6.8.1 common result); all logs go to
stderr. The two acceptance artifacts are written to ``--diagnostics-dir`` (never
into ``--generated-dir``, whose six-file contract G1 validate re-checks) and
referenced from the result ``paths``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rechner_pipeline.models import schemas
from rechner_pipeline.orchestrate import dossier as provenance
from rechner_pipeline.toolbox._common import (
    Exit,
    ToolboxResult,
    add_request_json_arg,
    build_result,
    hash_files,
    human_review_result,
    log,
    merge_request_into_args,
    read_request_json,
    run_command,
)

GATE = "G8.dossier-completeness"
COMMAND = "dossier"
GATE_VERSION = "1.0.0"

#: Acceptance-artifact filenames written under ``--diagnostics-dir`` (never into
#: ``--generated-dir``; the six-file G1 contract forbids extra siblings there).
QA_REPORT_NAME = "qa_report.json"
RUN_DOSSIER_NAME = "run_dossier.json"
QA_CONTRACT_NAME = "qa_contract.json"
INPUT_BUNDLE_NAME = "input_bundle.json"
DOSSIER_INPUT_NAME = "dossier_input.json"


# --------------------------------------------------------------------------- #
# argparse
# --------------------------------------------------------------------------- #


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.toolbox.dossier",
        description="Aggregate gate-result ledger entries into qa_report.json + "
        "run_dossier.json and decide mechanical acceptance (G8).",
    )
    parser.add_argument("--repo-root", dest="repo_root", default=None)
    parser.add_argument("--generated-dir", dest="generated_dir", default=None)
    parser.add_argument("--info-dir", dest="info_dir", default=None)
    parser.add_argument("--diagnostics-dir", dest="diagnostics_dir", default=None)
    parser.add_argument(
        "--status",
        dest="status",
        default=None,
        help="Caller-supplied run status (e.g. completed/failed/human_review_required).",
    )
    add_request_json_arg(parser)
    return parser


def _resolve_paths(args: argparse.Namespace) -> Tuple[Path, Path, Path, Path]:
    repo_root = Path(args.repo_root or ".").resolve()
    generated_dir = (
        Path(args.generated_dir) if args.generated_dir else repo_root / "generated"
    )
    info_dir = (
        Path(args.info_dir) if args.info_dir else repo_root / "info_from_excel"
    )
    diagnostics_dir = (
        Path(args.diagnostics_dir)
        if args.diagnostics_dir
        else repo_root / "runs"
    )
    return repo_root, generated_dir, info_dir, diagnostics_dir


# --------------------------------------------------------------------------- #
# Optional auxiliary inputs (read-only): coverage / assumptions / attempts /
# CLI identity / extra options. These may be supplied by the orchestrating agent
# as ``generated/dossier_input.json`` and/or ``generated/input_bundle.json``; all
# are optional and degrade honestly to conservative defaults.
# --------------------------------------------------------------------------- #


def _read_json_object(path: Path) -> Optional[Dict[str, Any]]:
    if not path.is_file():
        return None
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — treated as absent; never crashes the gate
        return None
    return obj if isinstance(obj, dict) else None


def _load_aux_inputs(
    generated_dir: Path, info_dir: Path
) -> Dict[str, Any]:
    """Best-effort load of orchestrator-supplied dossier context."""
    aux: Dict[str, Any] = {}
    for candidate in (
        generated_dir / DOSSIER_INPUT_NAME,
        info_dir / DOSSIER_INPUT_NAME,
    ):
        obj = _read_json_object(candidate)
        if obj is not None:
            aux.update(obj)
            break
    return aux


def _load_input_bundle(generated_dir: Path, info_dir: Path) -> Dict[str, Any]:
    for candidate in (
        info_dir / INPUT_BUNDLE_NAME,
        generated_dir / INPUT_BUNDLE_NAME,
    ):
        obj = _read_json_object(candidate)
        if obj is not None:
            # Keep only the coverage-block subset (§6.8.5) if a full bundle.
            return obj
    return {}


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #


def main(argv: Optional[List[str]] = None) -> ToolboxResult:
    parser = _build_parser()
    args = parser.parse_args(argv)
    request = read_request_json(args.request_json)
    merge_request_into_args(args, request)

    repo_root, generated_dir, info_dir, diagnostics_dir = _resolve_paths(args)
    run_status = args.status or "completed"

    log(f"dossier: repo_root={repo_root}")
    log(f"dossier: diagnostics_dir={diagnostics_dir} generated_dir={generated_dir}")

    # ----- gate-result ledger (§6.8.2) -------------------------------------- #
    entries, read_errors = provenance.load_gate_ledger(diagnostics_dir)
    log(f"dossier: loaded {len(entries)} ledger entries, {len(read_errors)} unreadable")

    # ----- auxiliary orchestrator context (all optional) -------------------- #
    aux = _load_aux_inputs(generated_dir, info_dir)
    input_bundle = aux.get("input_bundle") or _load_input_bundle(generated_dir, info_dir)
    expectation_coverage = (
        aux.get("expectation_coverage")
        or input_bundle.get("expectation_coverage")
        or "none"
    )
    open_assumptions: List[Dict[str, Any]] = list(aux.get("open_assumptions") or [])
    attempts: List[Dict[str, Any]] = list(aux.get("attempts") or [])
    attempts_used = int(aux.get("attempts_used", len(attempts)))
    max_attempts = int(aux.get("max_attempts", 4))
    run_id = str(aux.get("run_id") or diagnostics_dir.name or "run")
    run_cli = dict(aux.get("cli") or {"name": "unknown", "headless": True})
    options_extra = dict(aux.get("options") or {})
    tafeln_hash = aux.get("tafeln_xml_canonical_sha256")
    # qa_contract.json lives OUTSIDE --generated-dir (at repo root) so it does
    # not trip G1's six-file validate; record that path for provenance.
    qa_contract_path_rel = aux.get("qa_contract_path") or _repo_rel(
        repo_root / QA_CONTRACT_NAME, repo_root
    )

    # Coverage that is not "full" is itself an unapproved open assumption (§6.8.5,
    # §3.4): a zero-comparison run can never masquerade as validated.
    if expectation_coverage != "full" and not any(
        a.get("code") == "coverage.not_full" for a in open_assumptions
    ):
        open_assumptions.append(
            {
                "code": "coverage.not_full",
                "message": (
                    f"expectation_coverage is {expectation_coverage!r}; a non-full "
                    "coverage run requires a recorded human-review or QA-contract "
                    "policy approval (§3.4/§6.7)."
                ),
                "approved": False,
                "human_review_required": True,
            }
        )

    # ----- provenance facts -------------------------------------------------- #
    generated_file_hashes = provenance.hash_generated_files(
        generated_dir, repo_root=repo_root
    )
    dep_versions = provenance.dependency_versions()
    blocking_warnings = provenance._blocking_warnings_from_ledger(entries)

    # ----- qa_report.json (§6.8.3) ------------------------------------------ #
    qa_report = provenance.build_qa_report(
        run_id=run_id,
        entries=entries,
        open_assumptions=open_assumptions,
        blocking_warnings=blocking_warnings,
        generated_file_hashes=generated_file_hashes,
        dependency_versions_map=dep_versions,
        expectation_coverage=expectation_coverage,
        attempts_used=attempts_used,
        max_attempts=max_attempts,
        qa_contract_path=qa_contract_path_rel,
        tafeln_xml_canonical_sha256=tafeln_hash,
    )

    qa_report_errors = qa_report.validate()
    if qa_report_errors:
        log(f"dossier: qa_report schema invalid: {qa_report_errors}")
        return build_result(
            command=COMMAND,
            gate=GATE,
            gate_version=GATE_VERSION,
            exit_code=Exit.DOSSIER,
            summary={"run_id": run_id, "phase": "qa_report_validate"},
            errors=[{"code": "qa_report.invalid", "message": e} for e in qa_report_errors],
            repair_hints=["Fix the qa_report fields then re-run dossier."],
        )

    # The two acceptance artifacts are written to --diagnostics-dir, NEVER into
    # --generated-dir: a 7th/8th file in the six-file generated dir makes the
    # NEXT G1 validate fail ("unexpected files"). The diagnostics dir is the
    # shared, non-validated location every gate already writes its ledger into.
    qa_report_path = diagnostics_dir / QA_REPORT_NAME
    provenance.write_json(qa_report_path, qa_report.to_dict())

    # ----- run_dossier.json v2 (§6.8.4) ------------------------------------- #
    qa_report_record = provenance.path_record(qa_report_path, base=repo_root)
    full_dossier, delta = provenance.build_run_dossier_v2(
        qa_report=qa_report,
        qa_report_record=qa_report_record,
        entries=entries,
        run_status=run_status,
        repo_root=repo_root,
        run_cli=run_cli,
        options_extra=options_extra,
        input_bundle=input_bundle,
        attempts=attempts,
        generated_files=generated_file_hashes,
    )

    delta_errors = delta.validate()
    if delta_errors:
        log(f"dossier: run_dossier v2 delta invalid: {delta_errors}")
        return build_result(
            command=COMMAND,
            gate=GATE,
            gate_version=GATE_VERSION,
            exit_code=Exit.DOSSIER,
            summary={"run_id": run_id, "phase": "run_dossier_validate"},
            errors=[{"code": "run_dossier.invalid", "message": e} for e in delta_errors],
            repair_hints=["Provide run.cli.name and a valid provider/options set."],
        )

    run_dossier_path = diagnostics_dir / RUN_DOSSIER_NAME
    provenance.write_json(run_dossier_path, full_dossier)

    # ----- input_hashes: the ledger files + the artifacts we just wrote ------ #
    ledger_paths = sorted(
        diagnostics_dir.glob(f"*{provenance.GATE_LEDGER_SUFFIX}"), key=str
    )
    input_hashes = hash_files(ledger_paths, missing_ok=True)
    output_hashes = hash_files(
        [qa_report_path, run_dossier_path], missing_ok=True
    )

    paths = {
        "repo_root": str(repo_root),
        "generated_dir": str(generated_dir),
        "diagnostics_dir": str(diagnostics_dir),
        "qa_report": _repo_rel(qa_report_path, repo_root),
        "run_dossier": _repo_rel(run_dossier_path, repo_root),
    }
    summary = {
        "run_id": run_id,
        "decision": qa_report.decision,
        "accepted": qa_report.accepted,
        "expectation_coverage": expectation_coverage,
        "attempts_used": attempts_used,
        "max_attempts": max_attempts,
        "gates_present": sorted({e.gate for e in entries}),
        "required_gates": list(provenance.REQUIRED_GATES),
        "dependency_versions": dep_versions,
    }

    # ----- G8 blocking checks (§3.5) ---------------------------------------- #
    blockers = provenance.evaluate_blockers(
        entries=entries,
        read_errors=read_errors,
        open_assumptions=open_assumptions,
        generated_file_hashes=generated_file_hashes,
    )

    if qa_report.accepted and not blockers:
        log("dossier: ACCEPTED")
        return build_result(
            command=COMMAND,
            gate=GATE,
            gate_version=GATE_VERSION,
            exit_code=Exit.OK,
            paths=paths,
            summary=summary,
            input_hashes=input_hashes,
            output_hashes=output_hashes,
        )

    # Not accepted. A human-review handoff (max-attempts exhausted, or a
    # human-review open assumption / non-full coverage) is a terminal state with
    # status=human_review_required (exit 40). Otherwise it is a plain dossier
    # failure (exit 40, status=failed).
    exhausted = max_attempts > 0 and attempts_used >= max_attempts
    wants_human_review = (
        qa_report.decision == "human_review_required" or exhausted
    )

    summary["blockers"] = blockers
    repair_hints = _repair_hints(blockers)

    if wants_human_review:
        log(f"dossier: HUMAN_REVIEW_REQUIRED (exhausted={exhausted})")
        return human_review_result(
            command=COMMAND,
            gate=GATE,
            gate_version=GATE_VERSION,
            reason="dossier",
            paths=paths,
            summary=summary,
            input_hashes=input_hashes,
            output_hashes=output_hashes,
            errors=blockers,
            repair_hints=repair_hints,
        )

    log(f"dossier: NOT ACCEPTED ({len(blockers)} blockers)")
    return build_result(
        command=COMMAND,
        gate=GATE,
        gate_version=GATE_VERSION,
        exit_code=Exit.DOSSIER,
        paths=paths,
        summary=summary,
        input_hashes=input_hashes,
        output_hashes=output_hashes,
        errors=blockers,
        repair_hints=repair_hints,
    )


def _repo_rel(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except (ValueError, OSError):
        return str(path)


def _repair_hints(blockers: List[Dict[str, Any]]) -> List[str]:
    hints: List[str] = []
    codes = {b.get("code") for b in blockers}
    if "gate.missing" in codes:
        hints.append(
            "Run every required gate so each writes its <command>.gate.json "
            "ledger entry into --diagnostics-dir."
        )
    if "gate.not_passed" in codes:
        hints.append("Repair the failing gate(s) and re-run until each is 'passed'.")
    if "hashes.missing" in codes:
        hints.append("Ensure each gate records input_hashes and generated files exist.")
    if "open_assumption.unapproved" in codes:
        hints.append("Approve or resolve every open assumption before acceptance.")
    if "ledger.read_error" in codes:
        hints.append("Re-emit the unreadable ledger entry as valid UTF-8 JSON.")
    return hints


if __name__ == "__main__":
    raise SystemExit(run_command(main))
