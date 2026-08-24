---
name: author-rechner-toolbox-gate
description: >-
  Author a deterministic toolbox gate command (python -m rechner_pipeline.gates.<cmd>)
  for the agentic-rechner-pipeline. Trigger when adding/editing a gate (e.g. conventions/G3,
  algebraic/G6, roundtrip/G7) or any command that must obey the §3.3 single-JSON-stdout contract,
  emit a §6.8.2 .gate.json ledger, and use standard exit codes. Skip for: non-toolbox code, the
  qa/ engine modules (port those verbatim), pure read/research, or _common.py itself.
---

# Authoring a rechner-pipeline toolbox gate

A gate is a thin CLI wrapper over a `qa/`-engine. Gate logic lives in `qa/*`; the command wires flags, hashes, ledger, and the single JSON result. Model it on `src/rechner_pipeline/gates/generation_golden.py` / `src/rechner_pipeline/gates/bestand_validate.py`.

## Mandatory skeleton (stdout purity is a MECHANISM — never `print`/`emit_result` yourself)
```python
from typing import List, Optional
from rechner_pipeline.gates._common import (
    Exit, ToolboxResult, build_result, human_review_result, log, hash_files,
    add_request_json_arg, read_request_json, merge_request_into_args,
    run_command, write_gate_ledger, utc_now,
)
COMMAND = "conventions"; GATE = "G3.architecture-conventions"; GATE_VERSION = "1.0.0"

def main(argv: Optional[List[str]] = None) -> ToolboxResult:
    started_at = utc_now()
    args = _resolve_args(argv)              # parse + merge_request_into_args
    diagnostics_dir = ...                   # from --diagnostics-dir, else a sensible default

    # Red start marker BEFORE any gate work: a crash must never leave the
    # previous green ledger standing as apparent current evidence.
    fehlstart = begin_gate_ledger_attempt(
        command=COMMAND, gate=GATE, gate_version=GATE_VERSION,
        diagnostics_dir=diagnostics_dir, repo_root=...,
        started_at=started_at,
        command_line=argv if argv is not None else sys.argv[1:])
    if fehlstart is not None:               # marker could not be written -> BLOCKING
        return fehlstart

    def _finalize(result: ToolboxResult) -> ToolboxResult:
        return finalize_gate_ledger(result)  # atomic; write failure -> INTERNAL

    if not args.generated_dir:              # usage problems -> Exit.USAGE (2)
        return _finalize(build_result(command=COMMAND, gate=GATE, gate_version=GATE_VERSION,
                                      exit_code=Exit.USAGE, errors=[{"code":"usage","message":"..."}],
                                      repair_hints=["..."]))
    ...                                     # call qa engine; do ALL work here (print/warnings OK)
    return _finalize(build_result(command=COMMAND, gate=GATE, gate_version=GATE_VERSION,
                                  exit_code=Exit.OK, paths=..., summary=...,
                                  input_hashes=hash_files(py_files, missing_ok=True),
                                  output_hashes=..., diagnostics_path=...))

if __name__ == "__main__":
    raise SystemExit(run_command(main))     # run_command silences warnings, redirects stdout->stderr
                                            # for the body, restores real stdout, emits ONE JSON, returns int
```
`run_command` converts an unhandled exception to an INTERNAL result (exit 50) with traceback on stderr; re-raises `SystemExit` (argparse `--help`). Return `build_result(...)` / `human_review_result(...)` — do NOT call `emit_result`.

## `_common` import surface (semantics, one line each)
- `build_result(*, command, gate_version, exit_code=0, status=?, gate=?, paths, summary, input_hashes, output_hashes, errors, repair_hints, warnings, metrics, diagnostics_path)` → `ToolboxResult`. `status` auto-derives from `exit_code` (0→passed, else failed) unless set.
- `human_review_result(*, command, gate_version, reason=..., gate=?, ...)` → status `human_review_required` + blocking code. `reason="dossier"`→**40**, `reason="coverage"`→**31**. Override via `exit_code=` (must be blocking; 0 raises).
- `Exit`: `OK=0 USAGE=2 EXTRACTION=10 FILE_CONTRACT=20 SECURITY=21 CONVENTIONS=22 GOLDEN_MASTER=30 ALGEBRAIC=31 ROUNDTRIP=32 DOSSIER=40 INTERNAL=50`.
- `log(msg)` → stderr only. NEVER `print` to stdout (only `run_command` writes stdout).
- `add_request_json_arg(parser)`; `read_request_json(args.request_json)`; `merge_request_into_args(args, request)` — request fills only argparse fields whose value is `None`.
- `hash_files(paths, base=REPO_ROOT, missing_ok=False)` → ordered `{repo-relative path: sha256}`. Repo-relative BY DEFAULT (portable; no absolute leak). Use `missing_ok=True` for optional inputs.
- `begin_gate_ledger_attempt(*, command, gate, gate_version, diagnostics_dir, repo_root=None, started_at=None, command_line=None)` → red start marker; returns `None` on success, else the blocking result to return immediately.
- `finalize_gate_ledger(result)` → replaces the marker atomically; a write failure yields an INTERNAL result instead of the (green) input.
- `write_gate_ledger(result, diagnostics_dir, *, repo_root=None, attempt=1, started_at=None, ended_at=None, command_line=None, gate=None, required=None)` → low-level write of `<command>.gate.json`; gates use the two calls above, not this one directly.
- `utc_now()` → ISO-8601 UTC string.

## Standard flags every gate accepts
`--<inputs...>` (e.g. `--repo-root`, `--generated-dir`, `--info-dir`), `--diagnostics-dir`, and `--request-json (- | PATH)` (via `add_request_json_arg`). **RULE: every mergeable flag MUST use `default=None`** — a non-None falsy default (`0/""/False/[]`) silently blocks the request-json value.

## Ledger emission contract (§6.8.2)
Two-step and BLOCKING (ADR-008/ToDo 10.12 — the old best-effort contract is void). First `begin_gate_ledger_attempt(...)` before any gate work: it removes an older `<command>.gate.json` and persists a red start marker, so a crash can never leave a stale green ledger as apparent evidence; if it returns a result, that result is the (blocking) answer. Then wrap every `return` in `_finalize`, which calls `finalize_gate_ledger(result)` — it replaces the marker atomically and turns a write failure into an INTERNAL failure instead of a green verdict. The ledger is a disk-only side artifact — stdout stays exactly one JSON object. A passed gate with empty `input_hashes` is BLOCKED (`hashes.missing`) — always supply hashes. Gate id comes from `result.gate` (set it on every `build_result`); `required` is `True` for every gate (the old opt-in list is gone with ADR-006, and so is the `dossier` aggregation that once consumed these files).

## Exit-code contract + status mirroring
`0` pass | `2` usage | `10` extraction | `20` file/compile/schema | `21` static security | `22` conventions | `30` golden-master | `31` algebraic/coverage | `32` roundtrip | `40` dossier | `50` internal. `status` mirrors `exit_code` (0→passed, non-zero→failed) EXCEPT human-review (`human_review_required`, still non-zero/blocking). Non-zero is BLOCKING — never downgrade to a warning. `schemas.CommonResult.validate()` rejects a status/exit mismatch or an out-of-set code.

## Hard gotchas (one line each)
- `ExportManifest` must be built from `Path`, not `str`, or `to_dict()` mixes `/` and `\` (byte-compat break) — never round-trip a string-built manifest.
- `--info-dir` MUST live under `--repo-root` — else the confined child's expectation reads are blocked (`confinement_failure`, exit 30), not a clear usage error.
- `golden_master` runs G2 (`qa.security.scan_python_paths`) STATICALLY over `*.py` BEFORE executing any kernel; a violation → refuse, exit 21. A new gate that executes generated code must do the same.
- `_eq4` compares to 4 decimals (absolute) — hides relative drift on small actuarial values, so G6 (algebraic) is load-bearing; never treat a green G5 as proof of relative accuracy.
- Clean/stage output dirs before a run (remove stale `*_compressed.csv`/`*_scalar.json`/`*_table_values.csv` derived files) so a re-run can't glob a stale artifact.
- Scalar names match case-sensitive, NO separator normalization; only table columns get leniency (strip `_`/space/`.`, still case-sensitive).

## Verification expectation
Build `.tmp/` fixtures and run the command for real (`.venv\Scripts\python.exe -m rechner_pipeline.gates.<cmd> ...`). Prove the pass path AND each distinct failure mode (usage→2, your gate's blocking code, coverage→31 if applicable). Confirm: stdout is EXACTLY one parseable JSON object (`json.load` OK, 1 line); `<command>.gate.json` written on pass and fail and loadable via `_common.load_gate_ledger` (`read_errors == []`); shell exit code equals the JSON `exit_code`. Keep `pytest tests/` green; add a `tests/test_<command>.py`. Clean up `.tmp/`.
