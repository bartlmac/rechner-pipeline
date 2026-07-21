"""`conventions` toolbox command -- gate **G3** (architecture / import
conventions, MIGRATION.md §3.3 ``conventions`` row, §3.5 G3, §6.7 lines
2568-2587).

Statically scans every ``*.py`` file under ``--generated-dir`` (AST only -- the
target code is never imported or executed) and BLOCKS (exit ``22``) on any
architecture / import-convention violation:

* an import edge not in the allowed production graph (the only permitted
  inter-layer edge involving the actuarial layers is ``actuarial -> commutation``;
  ``commutation -> actuarial`` and every other disallowed edge fail),
* a circular import,
* a function-local import,
* a ``try/except ImportError`` optional-import trick,
* an ``if TYPE_CHECKING:`` import trick,
* an ``@lru_cache`` on a function with non-provably-hashable args.

The single JSON stdout object reports the import graph, the per-edge layer
analysis, the cache audit, and the circularity result. A human-readable JSON
report is also written into ``--diagnostics-dir``.

The rule set lives in :mod:`rechner_pipeline.qa.conventions`; this command is a
thin CLI wrapper obeying the §3.3 toolbox contract (single JSON stdout object,
stderr logs, standard exit codes, mergeable ``--request-json``).

Usage::

    python -m rechner_pipeline.toolbox.conventions \
        --generated-dir generated --diagnostics-dir generated/diagnostics
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from rechner_pipeline.qa.conventions import (
    ALLOWED_IMPORTS,
    GATE_VERSION,
    RULES,
    ConventionViolation,
    scan_conventions_paths,
    write_conventions_report,
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

COMMAND = "conventions"
GATE = "G3.architecture-conventions"

#: Per-category repair hint shown to the generating agent.
_REPAIR_HINTS = {
    "disallowed_edge": "Remove the forbidden import; the only allowed inter-layer "
    "edge involving the actuarial layers is actuarial.py -> commutation.py. Move "
    "shared utilities (e.g. excel_round) into a LOWER layer (params/commutation).",
    "circular_import": "Break the import cycle; the generated modules must form a "
    "DAG (inputs <- params <- commutation <- actuarial <- test_run).",
    "function_local_import": "Move the import to module top level; deferred "
    "function-local imports are forbidden.",
    "try_except_importerror": "Remove the try/except ImportError; declare the "
    "dependency directly so the import graph is honest.",
    "type_checking_trick": "Remove the if TYPE_CHECKING: import guard; import "
    "unconditionally so the runtime graph matches the static one.",
    "unhashable_lru_cache": "Only apply @lru_cache when every argument is strictly "
    "hashable; use string IDs / immutable keys, or drop the cache.",
    "syntax_error": "Fix the Python syntax error so the file can be parsed.",
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.toolbox.conventions",
        description="Architecture / import-convention gate (G3) for generated Python.",
    )
    parser.add_argument(
        "--generated-dir",
        dest="generated_dir",
        default=None,
        help="Directory containing the generated *.py files to scan.",
    )
    parser.add_argument(
        "--allowlist",
        dest="allowlist",
        default=None,
        help="Optional JSON file mapping module -> [extra allowed import targets]; "
        "merged ADDITIVELY into the §6.7 allowed import graph.",
    )
    parser.add_argument(
        "--diagnostics-dir",
        dest="diagnostics_dir",
        default=None,
        help="Directory to write conventions_report.json into. "
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


def _apply_allowlist(allowlist_path: Path) -> None:
    """Additively merge an allowlist file into :data:`ALLOWED_IMPORTS` in place.

    The file is ``{module: [extra allowed targets]}``. We only ADD edges (never
    remove the §6.7 baseline) so the gate cannot be weakened below spec; an
    operator can only widen it for a justified exception.
    """
    data = json.loads(allowlist_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("--allowlist must decode to a JSON object {module: [targets]}")
    for module, targets in data.items():
        if not isinstance(targets, list):
            raise ValueError(f"--allowlist['{module}'] must be a list of module names")
        ALLOWED_IMPORTS.setdefault(module, set()).update(str(t) for t in targets)


def main(argv: Optional[List[str]] = None):
    started_at = utc_now()
    parser = _build_parser()
    args = parser.parse_args(argv)
    request = read_request_json(args.request_json)
    merge_request_into_args(args, request)

    if args.diagnostics_dir:
        diagnostics_dir = Path(args.diagnostics_dir)
    elif args.generated_dir:
        diagnostics_dir = Path(args.generated_dir)
    else:
        diagnostics_dir = Path.cwd() / "diagnostics"

    def _finalize(result: ToolboxResult) -> ToolboxResult:
        """Write the §6.8.2 gate ledger (side artifact) before returning.

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
            log(f"conventions: gate-ledger write failed: {exc}")
        return result

    if not args.generated_dir:
        return _finalize(build_result(
            command=COMMAND,
            gate=GATE,
            gate_version=GATE_VERSION,
            exit_code=Exit.USAGE,
            errors=[{"code": "missing_argument", "message": "--generated-dir is required."}],
            repair_hints=["Pass --generated-dir pointing at the generated *.py files."],
        ))

    generated_dir = Path(args.generated_dir)
    if not generated_dir.is_dir():
        return _finalize(build_result(
            command=COMMAND,
            gate=GATE,
            gate_version=GATE_VERSION,
            exit_code=Exit.USAGE,
            errors=[{"code": "missing_generated_dir",
                     "message": f"--generated-dir does not exist: {generated_dir}"}],
            repair_hints=["Create/extract the generated directory before running G3."],
        ))

    if args.allowlist:
        allowlist_path = Path(args.allowlist)
        if not allowlist_path.is_file():
            return _finalize(build_result(
                command=COMMAND,
                gate=GATE,
                gate_version=GATE_VERSION,
                exit_code=Exit.USAGE,
                errors=[{"code": "missing_allowlist",
                         "message": f"--allowlist does not exist: {allowlist_path}"}],
                repair_hints=["Provide a valid allowlist JSON file or omit --allowlist."],
            ))
        try:
            _apply_allowlist(allowlist_path)
        except (ValueError, json.JSONDecodeError) as exc:
            return _finalize(build_result(
                command=COMMAND,
                gate=GATE,
                gate_version=GATE_VERSION,
                exit_code=Exit.USAGE,
                errors=[{"code": "invalid_allowlist", "message": str(exc)}],
                repair_hints=["Fix the allowlist file: {module: [target, ...]}."],
            ))

    python_files = _collect_python_files(generated_dir)
    log(f"conventions: scanning {len(python_files)} Python file(s) under {generated_dir}")

    report = scan_conventions_paths(python_files)
    violations: List[ConventionViolation] = report.violations

    report_path = diagnostics_dir / "conventions_report.json"
    write_conventions_report(report_path, report)

    checked = [str(p) for p in python_files]
    categories = sorted({v.category for v in violations})

    summary = {
        "checked_files": checked,
        "checked_count": len(checked),
        "import_graph": {k: list(v) for k, v in report.import_graph.items()},
        "layer_edges": report.layer_edges,
        "cache_audit": report.cache_audit,
        "circular_imports": [list(c) for c in report.cycles],
        "violation_count": len(violations),
        "violations": [v.to_dict() for v in violations],
        "violation_categories": categories,
        "allowed_imports": {k: sorted(v) for k, v in ALLOWED_IMPORTS.items()},
        "rules": RULES,
    }
    metrics = {
        "files_scanned": len(checked),
        "edges": len(report.layer_edges),
        "disallowed_edges": sum(1 for e in report.layer_edges if not e["allowed"]),
        "cycles": len(report.cycles),
        "violations": len(violations),
        "violations_by_category": {
            cat: sum(1 for v in violations if v.category == cat) for cat in categories
        },
    }

    input_hashes = hash_files(python_files, missing_ok=True)
    output_hashes = hash_files([report_path], missing_ok=True)

    if violations:
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
        repair_hints = [_REPAIR_HINTS[cat] for cat in categories if cat in _REPAIR_HINTS]
        log(f"conventions: BLOCKED -- {len(violations)} violation(s) in categories {categories}")
        return _finalize(build_result(
            command=COMMAND,
            gate=GATE,
            gate_version=GATE_VERSION,
            exit_code=Exit.CONVENTIONS,
            paths={"conventions_report": str(report_path)},
            summary=summary,
            metrics=metrics,
            input_hashes=input_hashes,
            output_hashes=output_hashes,
            diagnostics_path=str(report_path),
            errors=errors,
            repair_hints=repair_hints,
        ))

    log("conventions: PASSED -- no violations")
    return _finalize(build_result(
        command=COMMAND,
        gate=GATE,
        gate_version=GATE_VERSION,
        exit_code=Exit.OK,
        paths={"conventions_report": str(report_path)},
        summary=summary,
        metrics=metrics,
        input_hashes=input_hashes,
        output_hashes=output_hashes,
        diagnostics_path=str(report_path),
    ))


if __name__ == "__main__":
    raise SystemExit(run_command(main))
