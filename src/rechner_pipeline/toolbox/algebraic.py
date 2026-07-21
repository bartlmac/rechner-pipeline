"""``algebraic`` toolbox command — gate **G6** (algebraic / property tests).

§3.3 row line 1690; §3.5 G6 line 1748 + tiers lines 1754-1761; §6.8.6
``qa_contract.json`` lines 2781-2789; risk notes lines 1861-1862.

This command is the thin CLI wrapper over the Hypothesis-driven property-test
engine in :mod:`rechner_pipeline.qa.algebraic`. It:

1. Loads & validates a ``qa_contract.json`` via
   :class:`rechner_pipeline.models.schemas.QaContract` (a schema failure is a
   usage error — exit ``2``).
2. **G2 precondition (self-contained, like golden-master).** Runs the static AST
   security scanner over the generated dir BEFORE the kernel is imported. Any
   violation → refuse to execute, blocking security result (exit ``21``). Even if
   an orchestrator forgot to run G2 first, this gate never executes unsafe code.
3. Executes the engine **inside the fs_confine child** (G4): the generated kernel
   is imported read-only under the repo root, and the tiered Hypothesis property
   tests run there. The child emits a single JSON payload between markers.
4. Maps the outcome:
   * Engine unavailable / version mismatch → exit ``31`` (never downgrade).
   * Unknown applicability (missing mapping / convention / product / interest /
     timing, unknown tier) → exit ``31`` (NEVER a silent skip, §3.5 line 1761).
   * A property counterexample → exit ``31`` with the falsifying example.
   * All enabled tiers pass → exit ``0``.

``--strict`` is accepted per the §3.3 flag list. Because unknown applicability is
*always* a hard failure in this gate (it is the whole point of G6), ``--strict``
does not relax anything; it is recorded and additionally rejects a contract that
enables no product tier for a declared net-premium product type (a likely
under-declaration). The default (non-strict) behaviour is already fail-fast.

JSON stdout summary: selected tiers, identities checked, total cases, and any
counterexamples. Blocking exit code is ``31`` (:attr:`Exit.ALGEBRAIC`). Writes an
``algebraic.gate.json`` ledger on BOTH the pass and fail paths.
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

from rechner_pipeline.models.schemas import QaContract
from rechner_pipeline.qa.security import scan_python_paths, security_report
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
COMMAND = "algebraic"
GATE = "G6.algebraic-properties"

# Markers wrapping the child's JSON payload so unrelated chatter on the child's
# stdout (which this parent's run_command does not control inside the subprocess)
# cannot be confused with the result envelope.
_BEGIN = "@@ALG_JSON_BEGIN@@"
_END = "@@ALG_JSON_END@@"


# --------------------------------------------------------------------------- #
# Confined child program
# --------------------------------------------------------------------------- #
# Launched directly (sys.executable child, cwd == generated/) with argv
# ``[repo_root, qa_contract]``. The child:
#   1. imports the TRUSTED test engine (Hypothesis + the qa.algebraic module)
#      *before* runtime confinement is installed. Hypothesis transitively imports
#      stdlib modules (unittest.mock -> asyncio -> ssl) that introspect
#      ``socket.socket`` at module-init; if fs_confine had already replaced
#      ``socket.socket`` with its guard, that ssl module-init raises. The engine
#      is a reviewed dependency, so importing it before confinement is correct —
#      only the *generated kernel* must execute confined.
#   2. installs fs_confine (G4) for the repo root, so EVERY subsequent
#      generated-code execution (mapping resolution + property evaluation) runs
#      read-only under the repo root, with writes/network/subprocess blocked.
#   3. resolves the contract's function mappings against the generated modules
#      and runs the tiered Hypothesis property checks, emitting one JSON payload
#      between the begin/end markers.
_CHILD_SOURCE = r'''
import json
import sys
from pathlib import Path

_BEGIN = "{begin}"
_END = "{end}"

# Identity strings contain real UTF-8 (Σ, ä, ·). Force stdout/stderr to UTF-8 so
# emitting the JSON payload cannot crash on a Windows cp1252 console. Done at the
# very top, before any confinement, so the reconfigure is unguarded.
for _stream in (sys.stdout, sys.stderr):
    _reconf = getattr(_stream, "reconfigure", None)
    if callable(_reconf):
        try:
            _reconf(encoding="utf-8")
        except Exception:
            pass


def _emit(payload):
    sys.stdout.write(_BEGIN)
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.write(_END)
    sys.stdout.write("\n")
    sys.stdout.flush()


def _run():
    repo_root = sys.argv[1]
    contract_path = Path(sys.argv[2])
    generated = Path.cwd()
    sys.path.insert(0, str(generated))

    # (1) Import the trusted engine + Hypothesis machinery BEFORE confinement so
    #     ssl/asyncio module-init (which introspects socket.socket) is not broken
    #     by the fs_confine socket guard. Force the lazily-imported Hypothesis
    #     pieces the engine uses so no socket-touching import happens post-patch.
    from rechner_pipeline.qa import algebraic as eng

    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    try:
        import hypothesis  # noqa: F401
        from hypothesis import given, settings, HealthCheck, seed  # noqa: F401
        from hypothesis import strategies as st  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        _emit({{"error": "engine", "code": "engine_unavailable",
               "message": "Hypothesis is declared but not importable: %s. The gate "
                          "fails rather than downgrading to a weaker random loop "
                          "(§3.5)." % exc}})
        raise SystemExit(0)

    # (2) Install runtime confinement (G4) — read-only under repo_root, no writes,
    #     no outside reads, no socket/subprocess — around the generated-kernel work.
    from rechner_pipeline.qa import fs_confine
    fs_confine.install(repo_root)

    try:
        report = eng.run_checks(
            product_type=contract.get("product_type", ""),
            interest_basis_raw=contract.get("interest_basis", {{}}),
            timing_convention=contract.get("timing_convention", ""),
            terminal_age_policy=contract.get("terminal_age_policy", {{}}),
            function_mappings=contract.get("function_mappings", {{}}),
            tiers_enabled=contract.get("tiers_enabled", []),
            tolerances_raw=contract.get("tolerances", {{}}),
            property_engine=contract.get("property_engine", {{}}),
        )
    except eng.EngineUnavailableError as exc:
        _emit({{"error": "engine", "code": exc.code, "message": exc.message}})
        raise SystemExit(0)
    except eng.ApplicabilityError as exc:
        _emit({{"error": "applicability", "code": exc.code, "message": exc.message}})
        raise SystemExit(0)
    except Exception as exc:  # noqa: BLE001
        _emit({{"error": "runtime", "code": "engine_runtime", "message": "%s: %s" % (type(exc).__name__, exc)}})
        raise SystemExit(0)

    _emit({{"report": report.to_dict()}})


_run()
'''


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=COMMAND,
        description="Algebraic/property gate (G6): tiered actuarial identity tests "
        "via Hypothesis, executed under runtime confinement (G4).",
    )
    parser.add_argument("--repo-root", dest="repo_root", default=None)
    parser.add_argument("--generated-dir", dest="generated_dir", default=None)
    parser.add_argument("--info-dir", dest="info_dir", default=None)
    parser.add_argument("--qa-contract", dest="qa_contract", default=None)
    parser.add_argument("--diagnostics-dir", dest="diagnostics_dir", default=None)
    # --strict is a flag; default None so a request-json value can set it, but a
    # bare presence on the CLI means True.
    parser.add_argument(
        "--strict", dest="strict", action="store_const", const=True, default=None
    )
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


def _report_hash(report: Any) -> str:
    canonical = json.dumps(report, ensure_ascii=False, sort_keys=True)
    return sha256(canonical.encode("utf-8")).hexdigest()


def _err(code: str, message: str) -> Dict[str, str]:
    return {"code": code, "message": message}


def _run(argv: Optional[List[str]] = None) -> ToolboxResult:
    args = _resolve_args(argv)
    strict = bool(args.strict)

    missing = [
        name
        for name, val in (
            ("--repo-root", args.repo_root),
            ("--generated-dir", args.generated_dir),
            ("--info-dir", args.info_dir),
            ("--qa-contract", args.qa_contract),
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
                "Provide --repo-root, --generated-dir, --info-dir and --qa-contract.",
            ],
        )

    repo_root = Path(args.repo_root).resolve()
    generated_dir = Path(args.generated_dir).resolve()
    info_dir = Path(args.info_dir).resolve()
    qa_contract_path = Path(args.qa_contract).resolve()
    diagnostics_dir = (
        Path(args.diagnostics_dir).resolve() if args.diagnostics_dir else None
    )

    paths = {
        "repo_root": str(repo_root),
        "generated_dir": str(generated_dir),
        "info_dir": str(info_dir),
        "qa_contract": str(qa_contract_path),
    }
    if diagnostics_dir is not None:
        paths["diagnostics_dir"] = str(diagnostics_dir)

    summary_base: Dict[str, Any] = {"strict": strict}

    # --- Load + validate the QA contract (schema failure => usage, exit 2). ---
    if not qa_contract_path.is_file():
        return build_result(
            command=COMMAND,
            gate=GATE,
            gate_version=GATE_VERSION,
            exit_code=Exit.USAGE,
            paths=paths,
            errors=[_err("usage", f"qa_contract not found: {qa_contract_path}")],
            repair_hints=["Provide a readable qa_contract.json (see §6.8.6)."],
        )
    try:
        contract_data = json.loads(qa_contract_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return build_result(
            command=COMMAND,
            gate=GATE,
            gate_version=GATE_VERSION,
            exit_code=Exit.USAGE,
            paths=paths,
            errors=[_err("usage", f"qa_contract is not valid JSON: {exc}")],
            repair_hints=["The qa_contract must be a UTF-8 JSON object (§6.8.6)."],
        )
    contract = QaContract.from_dict(contract_data)
    contract_errors = contract.validate()
    if contract_errors:
        return build_result(
            command=COMMAND,
            gate=GATE,
            gate_version=GATE_VERSION,
            exit_code=Exit.USAGE,
            paths=paths,
            summary=summary_base,
            errors=[_err("contract_invalid", e) for e in contract_errors],
            repair_hints=[
                "Fix the qa_contract.json so it satisfies the §6.8.6 schema "
                "(product_type, interest_basis, timing_convention, "
                "function_mappings, non-empty tiers_enabled).",
            ],
        )

    # --strict extra guard: a net-premium product that does NOT enable the
    # product_specific tier is a likely under-declaration. In strict mode that is
    # a fail-fast applicability problem (exit 31), not a silent pass.
    if strict and "net_premium" in contract.product_type.lower():
        if "product_specific" not in contract.tiers_enabled:
            return build_result(
                command=COMMAND,
                gate=GATE,
                gate_version=GATE_VERSION,
                exit_code=Exit.ALGEBRAIC,
                paths=paths,
                summary={**summary_base, "tiers_enabled": contract.tiers_enabled},
                errors=[
                    _err(
                        "strict_underdeclaration",
                        f"--strict: product_type={contract.product_type!r} is a "
                        "net-premium product but tiers_enabled does not include "
                        "'product_specific'; net-premium identities would go "
                        "unchecked. Declare the product tier or change the product.",
                    )
                ],
                repair_hints=[
                    "Add 'product_specific' to tiers_enabled, or correct product_type.",
                ],
            )

    # Hash the kernel + contract for provenance.
    generated_py = sorted(generated_dir.glob("*.py"))
    input_files = list(generated_py) + [qa_contract_path]
    input_hashes = hash_files(input_files, base=repo_root, missing_ok=True)

    # --- G2 PRECONDITION: refuse to execute code that fails static security. ---
    security_violations = scan_python_paths(generated_py)
    if security_violations:
        report = security_report(
            checked_files=generated_py, violations=security_violations
        )
        return build_result(
            command=COMMAND,
            gate=GATE,
            gate_version=GATE_VERSION,
            exit_code=Exit.SECURITY,  # 21 — static security failure, blocking
            paths=paths,
            input_hashes=input_hashes,
            summary={
                **summary_base,
                "security_precondition": "failed",
                "security_violation_count": len(security_violations),
                "security_violations": report["violations"][:20],
            },
            errors=[
                _err(
                    "precondition_failed",
                    "static security gate (G2) found a violation; refusing to "
                    f"execute the generated kernel: {Path(v.path).name}:{v.line}:"
                    f"{v.column} {v.category}/{v.symbol} — {v.message}",
                )
                for v in security_violations[:50]
            ],
            repair_hints=[
                "Generated code must pass the static security gate before it can be "
                "executed under the algebraic gate. Fix the flagged constructs.",
            ],
        )

    # --- Execute the engine in a child process; the child installs fs_confine
    # (G4) itself AFTER importing the trusted Hypothesis engine, so the generated
    # kernel still runs confined while ssl/asyncio module-init is not broken by
    # the socket guard (see _CHILD_SOURCE). ---
    with tempfile.TemporaryDirectory(prefix="alg_confine_") as tmp:
        child_script = Path(tmp) / "_alg_child.py"
        child_script.write_text(
            _CHILD_SOURCE.format(begin=_BEGIN, end=_END), encoding="utf-8"
        )
        cmd = [
            sys.executable,
            str(child_script),
            str(repo_root),
            str(qa_contract_path),
        ]
        log(f"running confined algebraic child: cwd={generated_dir}")
        proc = subprocess.run(
            cmd,
            cwd=str(generated_dir),
            capture_output=True,
            text=True,
            # The child emits real UTF-8 (Σ, ä, ·) in identity strings; decode as
            # UTF-8 regardless of the parent's console code page (cp1252 would
            # mojibake the payload) and never crash on a stray byte.
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    diagnostics_path: Optional[str] = None
    if diagnostics_dir is not None:
        try:
            diagnostics_dir.mkdir(parents=True, exist_ok=True)
            log_path = diagnostics_dir / "algebraic_child.log"
            log_path.write_text(
                f"returncode={proc.returncode}\n--- stdout ---\n{proc.stdout}\n"
                f"--- stderr ---\n{proc.stderr}\n",
                encoding="utf-8",
            )
            diagnostics_path = str(log_path)
        except OSError as exc:
            log(f"could not write diagnostics: {exc}")

    payload = _extract_payload(proc.stdout)

    # Confinement / launcher failure: no result envelope.
    if payload is None:
        return build_result(
            command=COMMAND,
            gate=GATE,
            gate_version=GATE_VERSION,
            exit_code=Exit.ALGEBRAIC,
            paths=paths,
            input_hashes=input_hashes,
            summary={**summary_base, "returncode": proc.returncode},
            errors=[
                _err(
                    "confinement_failure",
                    "confined algebraic child produced no result envelope "
                    f"(returncode={proc.returncode}); see diagnostics for stderr.",
                )
            ],
            repair_hints=[
                "Inspect stderr: the generated kernel may have failed to import, "
                "attempted a blocked write/outside-read, or Hypothesis could not "
                "be imported under confinement.",
            ],
            diagnostics_path=diagnostics_path,
        )

    # Engine-unavailable / applicability / runtime errors => exit 31 (fail fast).
    err_kind = payload.get("error")
    if err_kind:
        code = payload.get("code", err_kind)
        message = payload.get("message", "")
        repair = {
            "engine": "Install the pinned Hypothesis from corporate Artifactory and "
            "record its version in property_engine; the gate never downgrades to a "
            "weaker random loop.",
            "applicability": "Declare the missing convention/mapping/product/interest/"
            "timing in qa_contract.json. Unknown applicability is a failure, not a "
            "skip (§3.5 line 1761).",
            "runtime": "The generated kernel raised while a property was evaluated; "
            "fix the kernel so the mapped functions are callable over the age domain.",
        }.get(err_kind, "See message and fix the qa_contract or generated kernel.")
        return build_result(
            command=COMMAND,
            gate=GATE,
            gate_version=GATE_VERSION,
            exit_code=Exit.ALGEBRAIC,  # 31
            paths=paths,
            input_hashes=input_hashes,
            summary={**summary_base, "failure_kind": err_kind, "failure_code": code},
            errors=[_err(code, message)],
            repair_hints=[repair],
            diagnostics_path=diagnostics_path,
        )

    report = payload.get("report") or {}
    report_hash = _report_hash(report)
    output_hashes = {"algebraic_report": report_hash}

    counterexamples = list(report.get("counterexamples", []))
    summary: Dict[str, Any] = {
        **summary_base,
        "engine": report.get("engine", ""),
        "engine_version": report.get("engine_version", ""),
        "max_examples": report.get("max_examples", 0),
        "tiers_selected": report.get("tiers_selected", []),
        "identities_checked": report.get("identities_checked", []),
        "total_cases": report.get("total_cases", 0),
        "counterexample_count": len(counterexamples),
        "counterexamples": counterexamples[:20],
        "report_hash": report_hash,
    }

    # A property counterexample => blocking exit 31 with the falsifying example.
    if counterexamples:
        return build_result(
            command=COMMAND,
            gate=GATE,
            gate_version=GATE_VERSION,
            exit_code=Exit.ALGEBRAIC,  # 31
            paths=paths,
            input_hashes=input_hashes,
            output_hashes=output_hashes,
            summary=summary,
            errors=[
                _err(
                    "counterexample",
                    f"[{c.get('tier')}] {c.get('identity')} falsified: "
                    f"{c.get('message')} (example={c.get('example')})",
                )
                for c in counterexamples[:50]
            ],
            repair_hints=[
                "Fix the generated kernel so the falsified actuarial identity holds "
                "over the sampled age domain under the declared conventions.",
            ],
            diagnostics_path=diagnostics_path,
        )

    # Pass: every enabled tier ran and found no counterexample.
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
    """Run the algebraic gate and emit the §6.8.2 ledger on BOTH pass and fail."""
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
            log(f"could not write algebraic gate ledger: {exc}")

    return result


if __name__ == "__main__":
    raise SystemExit(run_command(main))
