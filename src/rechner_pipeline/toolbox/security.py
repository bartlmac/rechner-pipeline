"""`security` toolbox command -- gate **G2** (static security, MIGRATION.md §3.3,
§3.5 G2).

Statically scans every ``*.py`` file under ``--generated-dir`` (AST only, the
target code is never imported or executed) and BLOCKS (exit ``21``) on any
violation. The single JSON stdout object reports the checked Python files and the
full violation list; a human-readable JSON report is also written into
``--diagnostics-dir``.

The actual rule set lives in :mod:`rechner_pipeline.qa.security` -- this command
is a thin CLI wrapper that obeys the §3.3 toolbox contract (single JSON stdout
object, stderr logs, standard exit codes, mergeable ``--request-json``).

Usage::

    python -m rechner_pipeline.toolbox.security \
        --generated-dir generated --diagnostics-dir generated/diagnostics
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from rechner_pipeline.qa.security import (
    GATE_VERSION,
    RULES,
    SecurityViolation,
    scan_python_paths,
    write_security_report,
)
from rechner_pipeline.toolbox._common import (
    Exit,
    ToolboxResult,
    add_request_json_arg,
    build_result,
    hash_files,
    log,
    merge_request_into_args,
    read_request_json,
    run_command,
    utc_now,
    write_gate_ledger,
)

COMMAND = "security"
GATE = "G2.static-security"

#: Per-category repair hint shown to the generating agent.
_REPAIR_HINTS = {
    "dangerous_import": "Remove network/subprocess/dynamic/filesystem imports; "
    "calculation code must be a pure function of its inputs.",
    "dangerous_call": "Remove network/subprocess/dynamic-exec/write-I/O calls; "
    "use read-only open() and os.path string helpers only.",
    "filesystem_access": "Do not touch the filesystem from calculation code; "
    "read inputs via the provided harness instead.",
    "nondeterministic": "Remove time/random/environment reads; a calculation must "
    "depend only on its explicit inputs so the golden master is reproducible.",
    "swallowed_exception": "Do not swallow exceptions; let real errors propagate so "
    "a wrong calculation cannot hide behind a silent fallback.",
    "self_approval": "A generated test must compare computed output to expected "
    "values, not assert a constant truth or write its own expectations.",
    "syntax_error": "Fix the Python syntax error so the file can be parsed.",
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.toolbox.security",
        description="Static security gate (G2) for LLM-generated Python.",
    )
    parser.add_argument(
        "--generated-dir",
        dest="generated_dir",
        default=None,
        help="Directory containing the generated *.py files to scan.",
    )
    parser.add_argument(
        "--diagnostics-dir",
        dest="diagnostics_dir",
        default=None,
        help="Directory to write static_security_report.json into. "
        "Defaults to <generated-dir> when omitted.",
    )
    add_request_json_arg(parser)
    return parser


def _collect_python_files(generated_dir: Path) -> List[Path]:
    """Return the generated ``*.py`` files in a stable, deterministic order."""
    return sorted(
        (p for p in generated_dir.rglob("*.py") if p.is_file()),
        key=lambda p: str(p).lower(),
    )


def main(argv: Optional[List[str]] = None):
    started_at = utc_now()
    parser = _build_parser()
    args = parser.parse_args(argv)
    request = read_request_json(args.request_json)
    merge_request_into_args(args, request)

    # Resolve the diagnostics dir for the §6.8.2 gate ledger. Default to
    # <generated-dir> (this gate already writes its security report there);
    # falls back to the cwd diagnostics dir for the early usage error.
    if args.diagnostics_dir:
        diagnostics_dir = Path(args.diagnostics_dir)
    elif args.generated_dir:
        diagnostics_dir = Path(args.generated_dir)
    else:
        diagnostics_dir = Path.cwd() / "diagnostics"

    def _finalize(result: ToolboxResult) -> ToolboxResult:
        """Write the gate-result ledger entry (side artifact) before returning.

        Called on BOTH pass and fail paths; a ledger-write failure is logged and
        swallowed so it can never mask the real command result.
        """
        try:
            write_gate_ledger(
                result,
                diagnostics_dir,
                started_at=started_at,
                ended_at=utc_now(),
                command_line=argv if argv is not None else sys.argv[1:],
            )
        except Exception as exc:  # noqa: BLE001 — never let the ledger break the gate
            log(f"security: gate-ledger write failed: {exc}")
        return result

    if not args.generated_dir:
        return _finalize(build_result(
            command=COMMAND,
            gate=GATE,
            gate_version=GATE_VERSION,
            exit_code=Exit.USAGE,
            errors=[
                {
                    "code": "missing_argument",
                    "message": "--generated-dir is required.",
                }
            ],
            repair_hints=["Pass --generated-dir pointing at the generated *.py files."],
        ))

    generated_dir = Path(args.generated_dir)

    if not generated_dir.is_dir():
        return _finalize(build_result(
            command=COMMAND,
            gate=GATE,
            gate_version=GATE_VERSION,
            exit_code=Exit.USAGE,
            errors=[
                {
                    "code": "missing_generated_dir",
                    "message": f"--generated-dir does not exist: {generated_dir}",
                }
            ],
            repair_hints=["Create/extract the generated directory before running G2."],
        ))

    python_files = _collect_python_files(generated_dir)
    log(f"security: scanning {len(python_files)} Python file(s) under {generated_dir}")

    violations: List[SecurityViolation] = scan_python_paths(python_files)

    report_path = diagnostics_dir / "static_security_report.json"
    write_security_report(
        report_path,
        checked_files=python_files,
        violations=violations,
    )

    checked = [str(p) for p in python_files]
    violation_dicts = [v.to_dict() for v in violations]
    categories = sorted({v.category for v in violations})

    summary = {
        "checked_files": checked,
        "checked_count": len(checked),
        "violation_count": len(violations),
        "violations": violation_dicts,
        "violation_categories": categories,
        "rules": RULES,
    }
    metrics = {
        "files_scanned": len(checked),
        "violations": len(violations),
        "violations_by_category": {
            cat: sum(1 for v in violations if v.category == cat) for cat in categories
        },
    }

    input_hashes = hash_files(python_files, missing_ok=True)
    output_hashes = hash_files([report_path], missing_ok=True)

    if violations:
        # Build deterministic, structured errors + per-category repair hints.
        errors = [
            {
                "code": v.category,
                "rule": v.category,
                "symbol": v.symbol,
                "path": v.path,
                "line": v.line,
                "column": v.column,
                "message": v.message,
                "snippet": v.snippet,
            }
            for v in violations
        ]
        repair_hints = [
            _REPAIR_HINTS[cat] for cat in categories if cat in _REPAIR_HINTS
        ]
        log(
            f"security: BLOCKED -- {len(violations)} violation(s) "
            f"in categories {categories}"
        )
        return _finalize(build_result(
            command=COMMAND,
            gate=GATE,
            gate_version=GATE_VERSION,
            exit_code=Exit.SECURITY,
            paths={"static_security_report": str(report_path)},
            summary=summary,
            metrics=metrics,
            input_hashes=input_hashes,
            output_hashes=output_hashes,
            diagnostics_path=str(report_path),
            errors=errors,
            repair_hints=repair_hints,
        ))

    log("security: PASSED -- no violations")
    return _finalize(build_result(
        command=COMMAND,
        gate=GATE,
        gate_version=GATE_VERSION,
        exit_code=Exit.OK,
        paths={"static_security_report": str(report_path)},
        summary=summary,
        metrics=metrics,
        input_hashes=input_hashes,
        output_hashes=output_hashes,
        diagnostics_path=str(report_path),
    ))


if __name__ == "__main__":
    raise SystemExit(run_command(main))
