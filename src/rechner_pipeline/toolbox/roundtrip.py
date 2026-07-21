"""``roundtrip`` toolbox command — gate **G7** (XML / extraction / recomputation
stability). §3.3 row line 1691; §3.5 G7 line 1749; roundtrip paragraph line 1763;
§6.7 ``tafeln.xml`` rules lines 2595-2610.

Thin CLI wrapper over :mod:`rechner_pipeline.qa.roundtrip`. It wires flags,
hashes, the §6.8.2 gate ledger, and the single-JSON-stdout result; all logic
lives in the engine. Three blocking checks (any failure -> exit ``32`` =
:attr:`Exit.ROUNDTRIP`):

1. ``tafeln.xml`` is a canonical fixed point of parse -> serialize -> parse
   (same canonical object AND same SHA-256); duplicate ages / ``qx`` outside
   ``[0, 1]`` / non-finite ``qx`` fail (§6.7).
2. Re-running extraction (read-only import of
   :class:`rechner_pipeline.adapters.excel.ExcelAdapter`) twice into a
   deterministic staging location under ``--repo-root`` yields stable MATERIAL
   artifact hashes; material drift fails.
3. Repeated ``test_run.golden_master_outputs()`` in FRESH processes (reusing the
   golden_master / :mod:`rechner_pipeline.qa.fs_confine` execution pattern) yields
   an identical canonical output hash; non-determinism fails.

Flags: ``--repo-root --generated-dir --info-dir --diagnostics-dir`` (the §3.3
required set) plus ``--input`` (the extraction source document needed for check 2)
and the standard ``--request-json``. Every mergeable flag uses ``default=None`` so
``--request-json`` can supply it.

The JSON stdout summary emits the ``tafeln.xml`` canonical hash, the re-extraction
hash comparison, and the repeated-output hash comparison. The ledger
(``roundtrip.gate.json``) is written on BOTH the pass and fail paths and is a
disk-only side artifact — stdout stays exactly one JSON object.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from rechner_pipeline.qa import roundtrip as engine
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

GATE_VERSION = "1.0.0"
COMMAND = "roundtrip"
GATE = "G7.roundtrips"


def _err(code: str, message: str) -> Dict[str, str]:
    return {"code": code, "message": message}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.toolbox.roundtrip",
        description="Roundtrip / hash-stability gate (G7).",
    )
    # Every mergeable flag uses default=None so --request-json can supply it.
    parser.add_argument("--repo-root", dest="repo_root", default=None)
    parser.add_argument("--generated-dir", dest="generated_dir", default=None)
    parser.add_argument("--info-dir", dest="info_dir", default=None)
    parser.add_argument("--diagnostics-dir", dest="diagnostics_dir", default=None)
    parser.add_argument(
        "--input",
        dest="input",
        default=None,
        help="Extraction source document (Excel workbook) for the re-extraction "
        "stability check. Required for check 2.",
    )
    add_request_json_arg(parser)
    return parser


def _resolve_args(argv: Optional[List[str]]) -> argparse.Namespace:
    parser = _build_parser()
    args = parser.parse_args(argv)
    request = read_request_json(args.request_json)
    merge_request_into_args(args, request)
    return args


def _is_under(root: Path, child: Path) -> bool:
    try:
        child.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _run(argv: Optional[List[str]]) -> ToolboxResult:
    args = _resolve_args(argv)

    missing = [
        name
        for name, val in (
            ("--repo-root", args.repo_root),
            ("--generated-dir", args.generated_dir),
            ("--info-dir", args.info_dir),
        )
        if not val
    ]
    if missing:
        return build_result(
            command=COMMAND,
            gate=GATE,
            gate_version=GATE_VERSION,
            exit_code=Exit.USAGE,
            errors=[_err("usage", f"missing required flags: {', '.join(missing)}")],
            repair_hints=[
                "Provide --repo-root, --generated-dir, --info-dir "
                "(and --input for the re-extraction check)."
            ],
        )

    repo_root = Path(args.repo_root).resolve()
    generated_dir = Path(args.generated_dir).resolve()
    info_dir = Path(args.info_dir).resolve()
    diagnostics_dir = (
        Path(args.diagnostics_dir).resolve() if args.diagnostics_dir else None
    )
    source_path = Path(args.input).resolve() if args.input else None

    paths: Dict[str, Any] = {
        "repo_root": str(repo_root),
        "generated_dir": str(generated_dir),
        "info_dir": str(info_dir),
    }
    if diagnostics_dir is not None:
        paths["diagnostics_dir"] = str(diagnostics_dir)
    if source_path is not None:
        paths["source_path"] = str(source_path)

    # --info-dir MUST live under --repo-root, else the confined recompute child's
    # expectation reads are blocked (skill gotcha). Surface as a clear usage error.
    if not _is_under(repo_root, info_dir):
        return build_result(
            command=COMMAND,
            gate=GATE,
            gate_version=GATE_VERSION,
            exit_code=Exit.USAGE,
            paths=paths,
            errors=[
                _err(
                    "usage",
                    f"--info-dir ({info_dir}) must live under --repo-root ({repo_root}); "
                    "otherwise the fs-confined recompute child cannot read it.",
                )
            ],
            repair_hints=["Place the info dir inside the repo root."],
        )

    if source_path is None:
        return build_result(
            command=COMMAND,
            gate=GATE,
            gate_version=GATE_VERSION,
            exit_code=Exit.USAGE,
            paths=paths,
            errors=[
                _err(
                    "usage",
                    "--input (extraction source document) is required for the "
                    "re-extraction stability check (G7 check 2).",
                )
            ],
            repair_hints=["Pass --input <path-to-source-workbook>."],
        )

    tafeln_path = generated_dir / "tafeln.xml"

    # --- Check 1: tafeln.xml canonical roundtrip ----------------------------- #
    if not tafeln_path.is_file():
        return build_result(
            command=COMMAND,
            gate=GATE,
            gate_version=GATE_VERSION,
            exit_code=Exit.ROUNDTRIP,
            paths=paths,
            errors=[_err("missing_tafeln", f"tafeln.xml not found: {tafeln_path}")],
            repair_hints=[
                "The generated kernel must emit tafeln.xml with the extracted "
                "mortality tables (no fabricated/placeholder qx data)."
            ],
        )
    tafeln = engine.check_tafeln_canonical(tafeln_path)

    # --- Input hashes (provenance): tafeln.xml + kernel + source workbook ---- #
    input_files = [tafeln_path]
    kernel = generated_dir / "test_run.py"
    if kernel.is_file():
        input_files.append(kernel)
    if source_path.is_file():
        input_files.append(source_path)
    input_hashes = hash_files(input_files, base=repo_root, missing_ok=True)

    # --- Check 2: re-extraction material-hash stability ---------------------- #
    reextract = engine.check_reextraction_stable(source_path, repo_root, generated_dir)

    # --- Check 3: recomputation (fresh-process) hash stability --------------- #
    recompute = engine.check_recompute_stable(repo_root, generated_dir, info_dir)

    summary: Dict[str, Any] = {
        "tafeln": {
            "ok": tafeln.ok,
            "canonical_sha256": tafeln.canonical_sha256,
            "table_count": tafeln.table_count,
            "entry_count": tafeln.entry_count,
        },
        "reextraction": {
            "ok": reextract.ok,
            "artifact_count": reextract.artifact_count,
            "drifted": reextract.drifted[:20],
            "missing_in_b": reextract.missing_in_b[:20],
            "extra_in_b": reextract.extra_in_b[:20],
        },
        "recomputation": {
            "ok": recompute.ok,
            "repeats": recompute.repeats,
            "output_hash": recompute.output_hash,
            "hashes": recompute.hashes,
            "security_violations": recompute.security_violations[:20],
        },
    }

    output_hashes: Dict[str, str] = {}
    if tafeln.canonical_sha256:
        output_hashes["tafeln_xml_canonical"] = tafeln.canonical_sha256
    if recompute.output_hash:
        output_hashes["golden_master_outputs"] = recompute.output_hash

    errors: List[Dict[str, str]] = []
    repair_hints: List[str] = []

    if not tafeln.ok:
        errors.append(_err(tafeln.error_code or "tafeln", tafeln.error_message or "tafeln.xml roundtrip failed"))
        repair_hints.append(
            "tafeln.xml must parse to a canonical mortality-table object with "
            "unique ascending ages and every qx finite in [0, 1]; serialize "
            "deterministically so it is a fixed point of parse->serialize."
        )
    if not reextract.ok:
        errors.append(
            _err(
                reextract.error_code or "reextraction",
                reextract.error_message or "re-extraction is not stable",
            )
        )
        for name in reextract.drifted[:20]:
            errors.append(_err("material_drift_artifact", f"hash drifted across runs: {name}"))
        repair_hints.append(
            "Re-extraction from the same source must be byte-stable for material "
            "artifacts; remove any time/random/iteration-order nondeterminism."
        )
    if not recompute.ok:
        errors.append(
            _err(
                recompute.error_code or "recomputation",
                recompute.error_message or "recomputation is not deterministic",
            )
        )
        repair_hints.append(
            "golden_master_outputs() must be a pure deterministic function: no "
            "time/random/environment input and a stable canonical output ordering."
        )

    if errors:
        # A G2 static-security violation in a gate that EXECUTES code is exit 21
        # (SECURITY), exactly like golden_master — even though it surfaced here.
        # A corrupt/unreadable --input (openpyxl can't open the workbook at all)
        # or a missing extraction dependency is an extraction / InputBundle
        # failure (exit 10, Exit.EXTRACTION): it is not an actuarial hash-
        # stability mismatch, so it must NOT crash to exit 50 nor be reported as
        # a roundtrip failure. Every other failure is a roundtrip / hash-
        # stability failure (exit 32).
        if recompute.error_code == "security_precondition":
            exit_code = Exit.SECURITY
        elif (not reextract.ok) and reextract.error_code in (
            "extraction_failed",
            "dependency_unavailable",
        ):
            exit_code = Exit.EXTRACTION
        else:
            exit_code = Exit.ROUNDTRIP
        return build_result(
            command=COMMAND,
            gate=GATE,
            gate_version=GATE_VERSION,
            exit_code=exit_code,
            paths=paths,
            input_hashes=input_hashes,
            output_hashes=output_hashes,
            summary=summary,
            errors=errors,
            repair_hints=repair_hints,
        )

    return build_result(
        command=COMMAND,
        gate=GATE,
        gate_version=GATE_VERSION,
        exit_code=Exit.OK,
        paths=paths,
        input_hashes=input_hashes,
        output_hashes=output_hashes,
        summary=summary,
    )


def main(argv: Optional[List[str]] = None) -> ToolboxResult:
    """Run the roundtrip gate and emit the §6.8.2 ledger on BOTH paths.

    The ledger write is a disk-only side artifact (never stdout) and is
    best-effort: a write failure is logged to stderr and never masks the verdict.
    """
    started_at = utc_now()
    result = _run(argv)

    diagnostics_dir = result.paths.get("diagnostics_dir")
    if diagnostics_dir:
        repo_root_path = result.paths.get("repo_root")
        try:
            write_gate_ledger(
                result,
                diagnostics_dir,
                repo_root=Path(repo_root_path) if repo_root_path else None,
                started_at=started_at,
                ended_at=utc_now(),
                command_line=["python", "-m", f"rechner_pipeline.toolbox.{COMMAND}"]
                + list(argv or []),
            )
        except Exception as exc:  # noqa: BLE001 — ledger is a side artifact
            log(f"{COMMAND}: gate-ledger write failed: {exc}")

    return result


if __name__ == "__main__":
    raise SystemExit(run_command(main))
