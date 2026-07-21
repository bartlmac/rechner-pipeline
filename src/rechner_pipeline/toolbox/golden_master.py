"""``golden_master`` toolbox command — gate **G5** (golden-master) + **G4**
(runtime confinement). §3.3 row line 1689; §3.5 G4+G5; §4.1 disposition.

Imports the generated ``generated/test_run.py`` kernel, calls
``golden_master_outputs()``, and compares the computed scalars/tables against the
deterministically extracted Excel expectations (``info_from_excel/*_scalar.json``
and ``*_table_values.csv``) with the fixed-harness semantics from
:mod:`rechner_pipeline.qa.golden_master` (4-decimal rounding, prefix-based,
separator-insensitive/case-sensitive column matching).

**Layered safety: G2 static security gate ORDERS execution (self-contained).**
Before the generated kernel is executed at all, this command runs the static AST
security scanner (:func:`rechner_pipeline.qa.security.scan_python_paths`) over the
generated dir. If the scan finds any violation (network/subprocess/dynamic-exec/
write-I/O/unsafe-filesystem/nondeterminism/...), execution is REFUSED and a
blocking security result (exit ``21`` = :attr:`Exit.SECURITY`,
``code="precondition_failed"``) is returned — the unsafe kernel is never imported.
This makes G5 robust regardless of external orchestration order: even if an
orchestrator forgot to run G2 first, ``golden_master`` will not execute code that
fails the reviewed static rules.

**Runtime confinement (G4).** Once the static gate passes, the generated kernel is
*executed* — so it runs under :mod:`rechner_pipeline.qa.fs_confine`: read-only
within the repo root, no writes, no reads outside the repo root, and no
socket/subprocess at runtime. Confinement is installed in a child process
(``fs_confine.main``) whose working directory is ``generated/`` exactly as the
AS-IS ``run_compare`` contract requires; the child emits the structured
comparison result as one JSON object on its stdout, which the parent reads.
fs_confine is defense-in-depth, NOT a formal OS sandbox (§2.6): the real trust
model is G2 (static) + G4 (runtime confine) + subprocess isolation combined.

**Gate ledger (§6.8.2).** On BOTH the pass and fail paths, when a
``--diagnostics-dir`` is given, a ``golden_master.gate.json`` ledger entry is
written via :func:`rechner_pipeline.toolbox._common.write_gate_ledger` so the
``dossier`` gate (G8) can aggregate the run. The ledger is a side artifact — it is
never leaked to stdout (stdout stays exactly one JSON result object).

**False-acceptance fix (§2.6 / §4.2 step 6).** Two AS-IS false-green paths are
closed here:

1. **Unmatched expected columns fail.** An expected scalar/table column with data
   that the generated output does not provide is a blocking deviation. The fixed
   :pyattr:`Report.ok` already folds ``unmatched_columns`` into the verdict, so a
   non-empty ``unmatched_columns`` yields exit ``30``.
2. **Zero-comparison runs are not full-acceptance.** A run that compared *zero*
   scalars and *zero* table cells performed no numeric validation. Per §2.6 it is
   sparse/none coverage, never full golden equivalence, so it is routed to a
   human-review terminal state via ``human_review_result(reason="coverage")``
   (exit ``31``), not a pass.

JSON stdout summary: scalars tested/skipped, table cells tested, deviation count
(and first deviations), unmatched columns, and the computed-output hash.
Blocking exit code on mismatch is ``30`` (:attr:`Exit.GOLDEN_MASTER`).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, List, Optional

from rechner_pipeline.qa import fs_confine
from rechner_pipeline.qa.security import scan_python_paths, security_report
from rechner_pipeline.toolbox._common import (
    Exit,
    add_request_json_arg,
    build_result,
    hash_files,
    human_review_result,
    log,
    merge_request_into_args,
    read_request_json,
    run_command,
    write_gate_ledger,
    ToolboxResult,
)

GATE_VERSION = "1.0.0"
COMMAND = "golden_master"
GATE = "G5.golden-master"

# Marker the confined child wraps its JSON payload in, so unrelated chatter on the
# child's stdout (which run_command of *this* parent does not control inside the
# subprocess) cannot be confused with the result envelope.
_BEGIN = "@@GM_JSON_BEGIN@@"
_END = "@@GM_JSON_END@@"


# --------------------------------------------------------------------------- #
# Confined child program
# --------------------------------------------------------------------------- #
# This source is written to a temp script and executed via
# ``fs_confine.main([repo_root, script, info_dir])`` with cwd == generated/.
# Under confinement it imports the generated ``test_run`` kernel, calls
# ``golden_master_outputs()``, loads the expected files, runs the fixed compare
# engine, and prints the structured Report between the begin/end markers.
#
# NOTE: ``info_from_excel`` MUST be under the confinement root (the repo root),
# which it is by the AS-IS layout (``repo_root/info_from_excel``); reads of it are
# therefore allowed by fs_confine. The child reads ``sys.argv[1]`` for info_dir.
_CHILD_SOURCE = r'''
import json
import sys
from pathlib import Path

from rechner_pipeline.qa.golden_master import compare, load_expected

_BEGIN = "{begin}"
_END = "{end}"


def _emit(payload):
    sys.stdout.write(_BEGIN)
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.write(_END)
    sys.stdout.write("\n")
    sys.stdout.flush()


def _run():
    info_dir = Path(sys.argv[1])
    generated = Path.cwd()
    sys.path.insert(0, str(generated))
    try:
        import test_run
    except Exception as exc:  # noqa: BLE001
        _emit({{"error": "import", "message": "test_run import failed: %s" % exc}})
        raise SystemExit(0)
    if not hasattr(test_run, "golden_master_outputs"):
        _emit({{"error": "contract", "message": "test_run.golden_master_outputs() missing"}})
        raise SystemExit(0)
    try:
        computed = test_run.golden_master_outputs()
    except Exception as exc:  # noqa: BLE001
        _emit({{"error": "runtime", "message": "golden_master_outputs() raised: %s" % exc}})
        raise SystemExit(0)
    if not isinstance(computed, dict) or "scalars" not in computed or "tables" not in computed:
        _emit({{"error": "schema", "message": "golden_master_outputs() did not return {{scalars, tables}}"}})
        raise SystemExit(0)

    expected = load_expected(info_dir)
    report = compare(expected, computed)
    payload = {{
        "scalars_tested": report.scalars_tested,
        "scalars_skipped": report.scalars_skipped,
        "table_cells_tested": report.table_cells_tested,
        "unmatched_columns": list(report.unmatched_columns),
        "deviations": list(report.deviations),
        "compared_anything": report.compared_anything,
        "ok": report.ok,
        "computed": computed,
    }}
    _emit(payload)


_run()
'''


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=COMMAND,
        description="Golden-master value gate (G5) executed under runtime confinement (G4).",
    )
    parser.add_argument("--repo-root", dest="repo_root", default=None)
    parser.add_argument("--generated-dir", dest="generated_dir", default=None)
    parser.add_argument("--info-dir", dest="info_dir", default=None)
    parser.add_argument("--diagnostics-dir", dest="diagnostics_dir", default=None)
    add_request_json_arg(parser)
    return parser


def _resolve_args(argv: Optional[List[str]]) -> argparse.Namespace:
    parser = _build_parser()
    args = parser.parse_args(argv)
    request = read_request_json(args.request_json)
    merge_request_into_args(args, request)
    return args


def _extract_payload(stdout: str) -> Optional[Dict[str, Any]]:
    start = stdout.find(_BEGIN)
    end = stdout.find(_END)
    if start == -1 or end == -1 or end < start:
        return None
    blob = stdout[start + len(_BEGIN) : end]
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        return None


def _output_hash(computed: Any) -> str:
    """Stable SHA-256 of the computed golden-master output (sorted keys)."""
    canonical = json.dumps(computed, ensure_ascii=False, sort_keys=True)
    return sha256(canonical.encode("utf-8")).hexdigest()


def _err(code: str, message: str) -> Dict[str, str]:
    return {"code": code, "message": message}


def _run(argv: Optional[List[str]] = None) -> ToolboxResult:
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
            repair_hints=["Provide --repo-root, --generated-dir and --info-dir."],
        )

    repo_root = Path(args.repo_root).resolve()
    generated_dir = Path(args.generated_dir).resolve()
    info_dir = Path(args.info_dir).resolve()
    diagnostics_dir = (
        Path(args.diagnostics_dir).resolve() if args.diagnostics_dir else None
    )

    paths = {
        "repo_root": str(repo_root),
        "generated_dir": str(generated_dir),
        "info_dir": str(info_dir),
    }
    if diagnostics_dir is not None:
        paths["diagnostics_dir"] = str(diagnostics_dir)

    test_run_py = generated_dir / "test_run.py"
    if not test_run_py.is_file():
        return build_result(
            command=COMMAND,
            gate=GATE,
            gate_version=GATE_VERSION,
            exit_code=Exit.GOLDEN_MASTER,
            paths=paths,
            errors=[_err("missing_kernel", f"generated kernel not found: {test_run_py}")],
            repair_hints=["Generate test_run.py with a golden_master_outputs() callable."],
        )

    # Hash the kernel + expectation inputs for the provenance trail.
    input_files = [test_run_py]
    input_files += sorted(info_dir.glob("*_scalar.json"))
    input_files += sorted(info_dir.glob("*_table_values.csv"))
    input_hashes = hash_files(input_files, base=repo_root, missing_ok=True)

    # --- G2 PRECONDITION: refuse to execute code that fails static security. ---
    # Layered design (§3.5): the static AST scanner (G2) runs BEFORE the kernel is
    # imported/executed. fs_confine (G4) is defense-in-depth, not the first line of
    # defense — so even if an orchestrator skipped G2, we never execute unsafe code.
    generated_py = sorted(generated_dir.glob("*.py"))
    security_violations = scan_python_paths(generated_py)
    if security_violations:
        report = security_report(
            checked_files=generated_py, violations=security_violations
        )
        sec_errors = [
            _err(
                "precondition_failed",
                "static security gate (G2) found a violation; refusing to execute "
                f"the generated kernel: {Path(v.path).name}:{v.line}:{v.column} "
                f"{v.category}/{v.symbol} — {v.message}",
            )
            for v in security_violations[:50]
        ]
        return build_result(
            command=COMMAND,
            gate=GATE,
            gate_version=GATE_VERSION,
            exit_code=Exit.SECURITY,  # 21 — static security failure, blocking
            paths=paths,
            input_hashes=input_hashes,
            summary={
                "security_precondition": "failed",
                "security_violation_count": len(security_violations),
                "security_violations": report["violations"][:20],
            },
            errors=sec_errors,
            repair_hints=[
                "Generated code must pass the static security gate (no network, "
                "subprocess, dynamic exec/import, write I/O, unsafe filesystem APIs, "
                "or nondeterministic/time/random/env calculation paths) before it can "
                "be executed under golden-master. Fix the flagged constructs and retry.",
            ],
        )

    # --- Execute the compare under fs_confine in a child process (G4). ---
    with tempfile.TemporaryDirectory(prefix="gm_confine_") as tmp:
        child_script = Path(tmp) / "_gm_child.py"
        child_script.write_text(
            _CHILD_SOURCE.format(begin=_BEGIN, end=_END), encoding="utf-8"
        )
        cmd = [
            sys.executable,
            fs_confine.__file__,
            str(repo_root),
            str(child_script),
            str(info_dir),
        ]
        log(f"running confined golden-master child: cwd={generated_dir}")
        proc = subprocess.run(
            cmd,
            cwd=str(generated_dir),
            capture_output=True,
            text=True,
            check=False,
        )

    if diagnostics_dir is not None:
        try:
            diagnostics_dir.mkdir(parents=True, exist_ok=True)
            (diagnostics_dir / "golden_master_child.log").write_text(
                f"returncode={proc.returncode}\n--- stdout ---\n{proc.stdout}\n"
                f"--- stderr ---\n{proc.stderr}\n",
                encoding="utf-8",
            )
        except OSError as exc:  # diagnostics are best-effort
            log(f"could not write diagnostics: {exc}")

    payload = _extract_payload(proc.stdout)

    # Confinement / launcher failure: the child did not produce a result envelope.
    if payload is None:
        return build_result(
            command=COMMAND,
            gate=GATE,
            gate_version=GATE_VERSION,
            exit_code=Exit.GOLDEN_MASTER,
            paths=paths,
            input_hashes=input_hashes,
            summary={"returncode": proc.returncode},
            errors=[
                _err(
                    "confinement_failure",
                    "confined golden-master child produced no result envelope "
                    f"(returncode={proc.returncode})",
                )
            ],
            repair_hints=[
                "Inspect stderr; the generated kernel may have attempted a blocked "
                "write/outside-read, crashed, or fs_confine could not import the kernel."
            ],
            diagnostics_path=(
                str(diagnostics_dir / "golden_master_child.log")
                if diagnostics_dir is not None
                else None
            ),
        )

    # Child-reported import/contract/schema errors map to the golden-master gate.
    if payload.get("error"):
        return build_result(
            command=COMMAND,
            gate=GATE,
            gate_version=GATE_VERSION,
            exit_code=Exit.GOLDEN_MASTER,
            paths=paths,
            input_hashes=input_hashes,
            errors=[_err(payload["error"], payload.get("message", ""))],
            repair_hints=[
                "test_run.py must import cleanly and expose "
                "golden_master_outputs() -> {'scalars': ..., 'tables': ...}."
            ],
        )

    scalars_tested = int(payload.get("scalars_tested", 0))
    scalars_skipped = int(payload.get("scalars_skipped", 0))
    table_cells_tested = int(payload.get("table_cells_tested", 0))
    unmatched_columns = list(payload.get("unmatched_columns", []))
    deviations = list(payload.get("deviations", []))
    compared_anything = bool(payload.get("compared_anything", False))
    computed = payload.get("computed")

    output_hash = _output_hash(computed)
    output_hashes = {"golden_master_outputs": output_hash}

    summary: Dict[str, Any] = {
        "scalars_tested": scalars_tested,
        "scalars_skipped": scalars_skipped,
        "table_cells_tested": table_cells_tested,
        "deviation_count": len(deviations),
        "deviations": deviations[:20],
        "unmatched_columns": unmatched_columns,
        "compared_anything": compared_anything,
        "computed_output_hash": output_hash,
    }
    diagnostics_path = (
        str(diagnostics_dir / "golden_master_child.log")
        if diagnostics_dir is not None
        else None
    )

    # --- FIX part 1: unmatched columns and/or numeric deviations -> blocking. ---
    if deviations or unmatched_columns:
        errors: List[Dict[str, str]] = []
        for d in deviations[:50]:
            errors.append(_err("deviation", d))
        for col in unmatched_columns:
            errors.append(
                _err(
                    "unmatched_expected_column",
                    f"expected column has data but is absent from generated output: {col}",
                )
            )
        return build_result(
            command=COMMAND,
            gate=GATE,
            gate_version=GATE_VERSION,
            exit_code=Exit.GOLDEN_MASTER,
            paths=paths,
            input_hashes=input_hashes,
            output_hashes=output_hashes,
            summary=summary,
            errors=errors,
            repair_hints=[
                "Fix the generated kernel so every expected scalar/column is "
                "produced under the matching prefix/name and all values agree to "
                "4 decimals.",
            ],
            diagnostics_path=diagnostics_path,
        )

    # --- FIX part 2: zero-comparison run is NOT full golden-master acceptance. ---
    if not compared_anything:
        return human_review_result(
            command=COMMAND,
            gate=GATE,
            gate_version=GATE_VERSION,
            reason="coverage",  # -> exit 31 (Exit.ALGEBRAIC), blocking, non-zero
            paths=paths,
            input_hashes=input_hashes,
            output_hashes=output_hashes,
            summary=summary,
            errors=[
                _err(
                    "zero_comparison",
                    "no scalar or table cell was compared; expectation coverage is "
                    "sparse/none and cannot be accepted as full golden-master.",
                )
            ],
            repair_hints=[
                "Provide *_scalar.json / *_table_values.csv expectations in --info-dir, "
                "or declare this input adapter's coverage as sparse/none for human review.",
            ],
            diagnostics_path=diagnostics_path,
        )

    # --- Pass: at least one comparison, no deviations, no unmatched columns. ---
    return build_result(
        command=COMMAND,
        gate=GATE,
        gate_version=GATE_VERSION,
        exit_code=Exit.OK,
        paths=paths,
        input_hashes=input_hashes,
        output_hashes=output_hashes,
        summary=summary,
        diagnostics_path=diagnostics_path,
    )


def main(argv: Optional[List[str]] = None) -> ToolboxResult:
    """Run the golden-master gate and, on BOTH the pass and fail paths, emit the
    §6.8.2 gate-result ledger entry (``golden_master.gate.json``) into the
    ``--diagnostics-dir`` when one is given.

    The ledger write is a side artifact: it goes to disk only and is NEVER written
    to stdout (stdout stays exactly one JSON result object via :func:`run_command`).
    A ledger-write failure must never mask the gate verdict, so it is best-effort
    and logged to stderr.
    """
    result = _run(argv)

    diagnostics_dir = result.paths.get("diagnostics_dir")
    if diagnostics_dir:
        repo_root_path = result.paths.get("repo_root")
        try:
            write_gate_ledger(
                result,
                diagnostics_dir,
                repo_root=Path(repo_root_path) if repo_root_path else None,
                command_line=["python", "-m", f"rechner_pipeline.toolbox.{COMMAND}"]
                + list(argv or []),
            )
        except Exception as exc:  # noqa: BLE001 — ledger is a side artifact
            log(f"could not write golden_master gate ledger: {exc}")

    return result


if __name__ == "__main__":
    raise SystemExit(run_command(main))
