"""``validate`` toolbox command — gate G1 (six-file output contract).

Enforces MIGRATION.md §3.5 G1 / §2.3.5: exactly the six expected files, exact
order, no path components, no duplicate blocks, no outer FILE-block text (text
path), every ``*.py`` compiles, and ``test_run.py`` exposes a schema-correct
``golden_master_outputs()`` (static precheck — the code is never executed here;
that is G4/G5's job under confinement).

Two resolution modes (both enforce the same contract):

* **direct-file-edit (primary)** — no ``--file-block-response``: validate the
  six files already on disk in ``--generated-dir``.
* **file-block (secondary)** — ``--file-block-response <path>``: parse the
  ``===FILE_START: <name>===`` / ``===FILE_END: <name>===`` blocks (grammar
  §6.3) from the given text file and validate them.

Blocking failures exit ``20`` (``Exit.FILE_CONTRACT``) with a structured error
list so the agent can repair without parsing prose. Usage/config errors (missing
inputs, unreadable response file) exit ``2`` (``Exit.USAGE``).

Run via::

    python -m rechner_pipeline.toolbox.validate \
        --repo-root . --generated-dir generated --info-dir info_from_excel \
        [--file-block-response response.txt]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from rechner_pipeline.generate.output import (
    EXPECTED_MAIN_OUTPUT_FILES,
    PYTHON_MAIN_OUTPUT_FILES,
    ValidationResult,
    validate_files_on_disk,
    validate_main_output_text,
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

GATE = "G1.file-contract"
GATE_VERSION = "1.0.0"

#: Per-error-code repair hint (agent-actionable, stable strings).
_REPAIR_HINTS = {
    "no_files": "Emit the six required FILE blocks; none were found.",
    "outer_text": "Remove all text outside the FILE_START/FILE_END blocks "
    "(only whitespace is allowed between blocks).",
    "path_components": "Use bare file names only — no directory components, "
    "no '/' or '\\'.",
    "duplicate_blocks": "Emit each of the six files exactly once.",
    "invalid_file_set": "Emit exactly these six files: "
    + ", ".join(EXPECTED_MAIN_OUTPUT_FILES)
    + ".",
    "wrong_order": "Emit the six files in this exact order: "
    + ", ".join(EXPECTED_MAIN_OUTPUT_FILES)
    + ".",
    "syntax_error": "Fix the Python syntax error at the reported file:line:col.",
    "golden_master_schema": "Define test_run.golden_master_outputs() to return a "
    'dict literal with keys {"scalars": ..., "tables": ...}.',
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.toolbox.validate",
        description="Gate G1: validate the six-file generated-output contract.",
    )
    # Mergeable flags use default=None so --request-json can fill them.
    parser.add_argument("--repo-root", dest="repo_root", default=None)
    parser.add_argument("--generated-dir", dest="generated_dir", default=None)
    parser.add_argument("--info-dir", dest="info_dir", default=None)
    parser.add_argument(
        "--file-block-response",
        dest="file_block_response",
        default=None,
        metavar="PATH",
        help="Optional: validate FILE blocks parsed from this text response "
        "instead of the files on disk.",
    )
    parser.add_argument(
        "--diagnostics-dir",
        dest="diagnostics_dir",
        default=None,
        help="Directory to write the <command>.gate.json ledger entry into. "
        "Defaults to <generated-dir>/diagnostics when omitted.",
    )
    add_request_json_arg(parser)
    return parser


def _errors_to_payload(result: ValidationResult):
    errors = []
    hints = []
    seen_hint_codes: set = set()
    for err in result.errors:
        errors.append(err.to_dict())
        hint = _REPAIR_HINTS.get(err.code)
        if hint and err.code not in seen_hint_codes:
            hints.append({"code": err.code, "hint": hint})
            seen_hint_codes.add(err.code)
    return errors, hints


def _summary(result: ValidationResult, mode: str) -> dict:
    return {
        "resolution_mode": mode,
        "expected_files": list(EXPECTED_MAIN_OUTPUT_FILES),
        "extracted_files": list(result.names),
        "order_ok": result.names == list(EXPECTED_MAIN_OUTPUT_FILES),
        "compiled_files": list(result.compiled),
        "python_files_required": list(PYTHON_MAIN_OUTPUT_FILES),
        "golden_master_schema_ok": result.golden_master_ok,
        "all_passed": result.ok,
    }


def main(argv: Optional[List[str]] = None):
    started_at = utc_now()
    parser = _build_parser()
    args = parser.parse_args(argv)
    request = read_request_json(args.request_json)
    args = merge_request_into_args(args, request)

    # Resolve the diagnostics dir for the §6.8.2 gate ledger. Default to
    # <generated-dir>/diagnostics (the other gates' convention); falls back to
    # the cwd diagnostics dir when no generated-dir is available (usage errors).
    if args.diagnostics_dir:
        diagnostics_dir = Path(args.diagnostics_dir)
    elif args.generated_dir:
        diagnostics_dir = Path(args.generated_dir) / "diagnostics"
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
                repo_root=Path(args.repo_root) if args.repo_root else None,
                started_at=started_at,
                ended_at=utc_now(),
                command_line=argv if argv is not None else sys.argv[1:],
            )
        except Exception as exc:  # noqa: BLE001 — never let the ledger break the gate
            log(f"validate: gate-ledger write failed: {exc}")
        return result

    # --- usage / configuration validation (exit 2) -------------------------- #
    usage_errors: List[dict] = []
    if not args.generated_dir:
        usage_errors.append(
            {"code": "missing_arg", "message": "--generated-dir is required"}
        )
    if not args.info_dir:
        usage_errors.append(
            {"code": "missing_arg", "message": "--info-dir is required"}
        )
    if usage_errors:
        return _finalize(build_result(
            command="validate",
            gate=GATE,
            gate_version=GATE_VERSION,
            exit_code=Exit.USAGE,
            errors=usage_errors,
            repair_hints=[
                {"code": "missing_arg", "hint": "Provide --generated-dir and --info-dir."}
            ],
        ))

    repo_root = Path(args.repo_root).resolve() if args.repo_root else None
    generated_dir = Path(args.generated_dir)
    info_dir = Path(args.info_dir)
    file_block_response = (
        Path(args.file_block_response) if args.file_block_response else None
    )

    paths = {
        "generated_dir": str(generated_dir),
        "info_dir": str(info_dir),
    }
    if repo_root is not None:
        paths["repo_root"] = str(repo_root)

    # --- resolution mode ---------------------------------------------------- #
    if file_block_response is not None:
        mode = "file_block"
        paths["file_block_response"] = str(file_block_response)
        if not file_block_response.is_file():
            return _finalize(build_result(
                command="validate",
                gate=GATE,
                gate_version=GATE_VERSION,
                exit_code=Exit.USAGE,
                paths=paths,
                errors=[
                    {
                        "code": "missing_response",
                        "message": f"--file-block-response not found: {file_block_response}",
                    }
                ],
                repair_hints=[
                    {
                        "code": "missing_response",
                        "hint": "Point --file-block-response at an existing text file.",
                    }
                ],
            ))
        log(f"validate: parsing FILE blocks from {file_block_response}")
        text = file_block_response.read_text(encoding="utf-8")
        result = validate_main_output_text(text)
        input_hashes = hash_files(
            [file_block_response], base=repo_root, missing_ok=True
        )
    else:
        mode = "direct_file_edit"
        log(f"validate: validating files on disk in {generated_dir}")
        result = validate_files_on_disk(generated_dir)
        # Hash whichever expected files are present (repo-relative keys).
        candidate_files = [
            generated_dir / name for name in EXPECTED_MAIN_OUTPUT_FILES
        ]
        input_hashes = hash_files(candidate_files, base=repo_root, missing_ok=True)

    summary = _summary(result, mode)

    if result.ok:
        log("validate: G1 PASSED (six-file contract satisfied)")
        return _finalize(build_result(
            command="validate",
            gate=GATE,
            gate_version=GATE_VERSION,
            exit_code=Exit.OK,
            paths=paths,
            summary=summary,
            input_hashes=input_hashes,
        ))

    errors, hints = _errors_to_payload(result)
    log(f"validate: G1 FAILED with {len(errors)} contract violation(s)")
    return _finalize(build_result(
        command="validate",
        gate=GATE,
        gate_version=GATE_VERSION,
        exit_code=Exit.FILE_CONTRACT,
        paths=paths,
        summary=summary,
        input_hashes=input_hashes,
        errors=errors,
        repair_hints=hints,
    ))


if __name__ == "__main__":
    raise SystemExit(run_command(main))
