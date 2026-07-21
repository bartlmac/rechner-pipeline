# PROJECT-LEAD.md — Feedback & Coordination Log

> Feedback ledger. The project lead and every subagent append here.
> Format per entry: `### [wave/agent] — short title` then **What happened / What worked / What hurt / Recommendation**.
> The lead distills these into reusable skills/agents after each wave.

## Lead notes

### [lead/setup] — Scoping & environment discovery
- **What worked:** Asking 4 batched scoping questions up front (CLI target, gate scope, DoD, deps) resolved ambiguity cheaply. Probing the env BEFORE spawning agents caught that the "Artifactory" assumption was wrong (public repo, pypi.org). Spawning a wave against a wrong dep source would have wasted a full wave.
- **What hurt:** MIGRATION.md is 198KB; reading it fully as lead is expensive. Mitigation: section line-map (via grep on headings) lets me brief subagents with exact `§N.N` + line ranges instead of dumping the file.
- **Recommendation:** Subagents must read only their assigned MIGRATION.md sections (cited by line range) + their specific source files (read-only). Never "read the whole plan."

### [lead/closeout] — Migration delivered & accepted (2026-06-19)
- **Outcome:** Full SDK→agentic migration complete. Toolbox G0–G8 + `assurance` orchestrator + source-neutral CLI + 2 reusable skills + an accepted KLV kernel. `assurance` exits 0 / dossier `accepted` hands-off & idempotent; 271 tests green; SDK/LangGraph absent; final review verdict COMPLETE & SOUND with the green proven real (anti-overfit + 1:1 VBA port).
- **What worked (orchestration):** (1) Probing the environment BEFORE spawning caught the wrong-deps assumption (public repo, not Artifactory) — saved a wasted wave. (2) Building a hardened shared `_common` layer FIRST, with its own review+guardrail pass, paid off across 8 downstream gate authors. (3) Strict disjoint file ownership per wave → zero merge conflicts across ~20 agents. (4) Distilling the gate-authoring pattern into a skill after wave 1 made wave 2's three gates first-try authorable (dogfooded successfully). (5) Independent review gates caught REAL defects that unit-green hid: fs_confine bypass, golden-master false-green, the ledger-wiring gap, the algebraic `D_x` dead-code (false coverage), and the 4 e2e wiring bugs. (6) The end-to-end run was essential — every integration bug only surfaced when a real kernel flowed through the whole chain.
- **What hurt / would change:** (1) Concurrent appends to PROJECT-LEAD.md from parallel agents occasionally raced; a per-agent feedback file collated by the lead would be cleaner. (2) An invented inter-gate contract (the `.gate.json` ledger) emerged mid-stream from the dossier author AFTER the other gates were built → a reconciliation wave. Defining cross-gate contracts in the shared layer up front would have avoided it. (3) Transient full-suite failures from agents running pytest mid-edit of peers' files — instruct agents to scope their in-flight check to their own test file; lead runs the authoritative full suite only on a quiescent tree.
- **Verification discipline that mattered:** never trusted an agent's "green" — re-ran the build on the quiescent tree after every wave; the most important check (final acceptance) I ran myself hands-off and idempotently.

---

## Subagent feedback

### [wave0/foundation] — Shared toolbox contract, models, scaffolding
- **What worked:** The exact §-line-range briefing let me read only ~600 lines of the 198KB spec; no waste. Porting `manifest.py` verbatim from the source repo (rather than re-deriving) guarantees the §6.4 byte-shape. `_common.py` and `models/schemas.py` share status/exit constants but I kept `ToolboxResult` (live emitter) separate from `schemas.CommonResult` (round-trip schema view) so command authors are not forced through dataclass plumbing on the hot path. Install + 24 tests went green from public pypi.org with no Artifactory leakage.
- **What hurt:** `ExportManifest` declares `Path` fields but `from_dict`/constructor accept raw strings without coercion, so `to_dict()` only normalizes OS separators for values that actually went through `Path` (sheet_csvs, vba_txts, names_manager, llm_inputs, all_outputs) — NOT for `replacements` (plain `Dict[str,str]`) nor for strings handed directly to the constructor. On Windows this means a single `to_dict()` of a string-built manifest can mix `/` and `\\`. It is idempotent only AFTER one `from_dict` round-trip. This is AS-IS behavior preserved intentionally; do not "fix" it or the byte-compatibility contract breaks. Test round-trips from the normalized form.
- **`_common` API surface later agents should rely on (stable):**
  - `build_result(command=, gate_version=, exit_code=, status=?, gate=?, paths=, summary=, input_hashes=, output_hashes=, errors=, repair_hints=, warnings=, metrics=, diagnostics_path=)` → `ToolboxResult`; `emit_result(result)` writes the single stdout JSON and returns the exit code. `status` auto-derives from `exit_code` (0→passed) unless you pass `human_review_required` explicitly.
  - Exit codes: use `Exit.USAGE/EXTRACTION/FILE_CONTRACT/SECURITY/CONVENTIONS/GOLDEN_MASTER/ALGEBRAIC/ROUNDTRIP/DOSSIER/INTERNAL` (or the `EXIT[...]` dict). `errors`/`repair_hints` are ALWAYS serialized (possibly empty) per §6.8.1 — do not strip them.
  - stdin: `add_request_json_arg(parser)` then `merge_request_into_args(args, read_request_json(args.request_json))`. Explicit flags win (a field is "unset" only when its argparse value is `None`, so give flags `default=None`).
  - Logs: `log(msg)` / `get_logger()` → stderr only. NEVER `print()` to stdout except via `emit_*`.
  - Hashing: `hash_files(paths, base=repo_root)` yields repo-relative `{path: sha256}` for `input_hashes`; `file_sha256`/`text_sha256` re-exported.
- **Gotcha for gate authors:** `schemas.CommonResult.validate()` enforces that `status` mirrors `exit_code` and that `exit_code` is in the standard set {0,2,10,20,21,22,30,31,32,40,50}. If a gate wants `human_review_required`, that status maps to a NON-zero exit; keep them consistent or validation fails. `QaReport.compute_accepted()` exists so `dossier` does not hand-roll the acceptance rule.
- **Recommendation:** Later toolbox commands import `from rechner_pipeline.toolbox._common import build_result, emit_result, Exit, log, add_request_json_arg, read_request_json, merge_request_into_args, hash_files`. Gate ledger/qa_report/dossier authors build via `models.schemas` dataclasses and call `.validate()` before emitting. `pandas` pulled a large transitive tree (numpy, pytz, tzdata) and `oletools` pulled `cryptography`/`cffi` (compiled) — first install is slow but cached; budget for it in CI.

### [wave0/review] — PASS (with required follow-ups before Wave 1 ships commands)
- **Verdict:** Foundation is schema-faithful and safe to build on. Manifest port is byte-identical to AS-IS (verified line-by-line). No Critical defects. Resolution was syntactic_only (no shell tool to run the venv; logic traced by hand).
- **High (fix before downstream commands rely on them):**
  - **stdout purity is NOT actually enforced (§3.3/§6.8.1).** `_common` keeps stdout pure *if used correctly*, but nothing prevents a command author's imported lib (`pandas`/`oletools` warnings, banner prints, C-extension chatter) from writing to fd 1. The "hard contract" has no guard. Add an `emit_*`-time stdout-capture/redirect helper (e.g. swap `sys.stdout` to stderr for the gate body, restore only for the single emit) or at minimum a documented `warnings.simplefilter` + a `contextlib.redirect_stdout` wrapper the 8 authors must call. Right now purity is a convention, not a mechanism — it WILL break in a command that imports pandas.
  - **`human_review_required` exit-code mapping is underspecified and a footgun.** `status_for_exit()` only returns passed/failed; any human-review handoff must be hand-set by the author AND paired with a non-zero exit, or `CommonResult.validate()` rejects it. There is no `Exit.HUMAN_REVIEW` constant and no helper like `build_result(human_review=True)`. 8 authors will each re-derive "which non-zero code do I use for human review?" Pick one (spec implies 40/dossier or 31/sparse-coverage per §6.7) and expose a single helper.
- **Medium:**
  - **`merge_request_into_args` only treats `None` as unset.** A flag with a non-None falsy default (`0`, `""`, `False`, `[]`) silently blocks the request-json value — opposite of "flags must remain available." Authors must give every mergeable flag `default=None`; this is documented in the wave0 note but not enforced. Consider a sentinel.
  - **`hash_files(base=)` and `ExportManifest.with_output_hashes` produce different key shapes** (relative-to-base vs raw `str(Path)`), and on Windows `str(Path)` yields `\\` while repo-portable hash maps in the §6.8 examples use `\\` too — but `hash_files` without base leaks absolute OS paths into `input_hashes`. Always pass `base=repo_root`; flag for golden_master/roundtrip authors.
- **Cross-cutting risk for later waves:** the byte-compatibility of `ExportManifest` depends on callers feeding it `Path` objects, not strings, AND never round-tripping through `to_dict()` on a string-built manifest (mixes `/` and `\\`). Wave-1 `extract` must construct the manifest from `Path`s. The §6.8.3 `dependency_versions` example lists `python: "3.11.x"` but the env runs 3.12.4 — acceptable (requires-python>=3.11) but dossier author should record the real interpreter version, not a placeholder.

### [wave0/guardrails] — Final stable `_common` API for the 8 command authors
The four reviewer follow-ups are implemented in `toolbox/_common.py` (+ `models/schemas.py`). API is ADD-only; every prior signature is unchanged. Tests: **34 passed** (24 existing + 10 new). Resolution: **fully_resolved** (ran `.venv\Scripts\python.exe -m pytest tests/ -q`).

- **MANDATORY entry point — `run_command` (stdout purity is now a MECHANISM, not a convention).** Every command's `__main__` MUST be exactly:
  ```python
  from rechner_pipeline.toolbox._common import run_command
  def main(argv=None) -> ToolboxResult:      # or -> (ToolboxResult, exit_code)
      ...                                     # do ALL work here; print()/warnings are fine
      return build_result(...)               # or human_review_result(...)
  if __name__ == "__main__":
      raise SystemExit(run_command(main))
  ```
  `run_command(main_callable, argv=None) -> int` does: `warnings.simplefilter("ignore")` + `PYTHONWARNINGS=ignore` for the body; redirects `sys.stdout -> sys.stderr` for the *whole* body via `contextlib.redirect_stdout` (so pandas/oletools banners and any `print` land on stderr); restores the REAL stdout and emits exactly ONE JSON object on it afterward. Authors no longer need to police imported-library chatter. Do NOT call `emit_result` yourself inside `main` — return the result and let `run_command` emit it once.
  - Unhandled exception in `main` -> auto-converted to INTERNAL result (`exit_code=50`, `status="failed"`, `errors=[{code:"internal_error", type, message}]`). Traceback goes to stderr only, never stdout. `SystemExit` (argparse `--help`/usage) is re-raised untouched.

- **Human-review terminal state — use `human_review_result`, never hand-set the code.** Canonical mapping (confirmed vs §6.7/§6.8.3 and the wave0/review follow-up):
  - `reason="dossier"`  -> exit **40** (`Exit.DOSSIER`): acceptance / dossier handoff, incl. `max_attempts` exhaustion. Used by the `dossier` (G8) author.
  - `reason="coverage"` -> exit **31** (`Exit.ALGEBRAIC`): sparse/none expectation-coverage or missing-mortality-table handoff. Used by `algebraic` (G6) / extract-coverage handoffs.
  ```python
  return human_review_result(command="dossier", gate_version="1.0.0", reason="dossier")
  ```
  Sets `status="human_review_required"` AND the blocking non-zero exit together so authors cannot diverge. Pass `exit_code=` to override (must be a blocking standard code; `0` raises `ValueError`). The mapping lives in `HUMAN_REVIEW_EXIT_CODES`. `schemas.CommonResult.validate()` accepts `human_review_required` with these non-zero codes (already did, now exercised by tests).

- **`hash_files` is repo-relative BY DEFAULT now.** `hash_files(paths)` (no `base=`) keys are relative to the repo root (`_common.REPO_ROOT` / `repo_root()`), e.g. `generated\test_run.py` — portable, never absolute. `base=<Path>` relativizes to that base; `base=None` opts out (raw path string). Authors should just call `hash_files(paths)` for `input_hashes`/`output_hashes`; the old "always pass `base=repo_root`" caveat is obsolete.

- **Constant dedup (Low):** `models/schemas.py` now imports `SCHEMA_VERSION`, `STATUS_VALUES (= _common.STATUSES)`, and `_STANDARD_EXIT_CODES (= _common.STANDARD_EXIT_CODES)` from `_common`. Single source of truth; behavior identical. New `_common` exports: `run_command`, `human_review_result`, `HUMAN_REVIEW_EXIT_CODES`, `STANDARD_EXIT_CODES`, `REPO_ROOT`, `repo_root`. **No deviations.**

### [wave1/validate] — Six-file output validator migrated into `validate` (G1)

**What worked**
- Ported `generate/output.py` semantics into `src/rechner_pipeline/generate/output.py` and the new `toolbox/validate.py`. Both resolution modes enforce the *same* contract: direct-file-edit (six files on disk in `--generated-dir`, the primary path) and file-block (parse `===FILE_START/END===` from `--file-block-response`, secondary). Pass exits 0; every contract violation exits 20 (`Exit.FILE_CONTRACT`) with a structured `errors[]` (`code`, `message`, `file?`, `detail?`) plus per-code `repair_hints`. Usage problems (missing `--generated-dir`/`--info-dir`, missing response file) exit 2.
- Refactored the AS-IS raise-on-first-failure validator into a structured `ValidationResult` while keeping a back-compat `validate_main_output_files(text)` that still raises `OutputValidationError`. Fail-fast category order preserved: outer-text → names/path/dup/set/order → compile → golden-master schema.
- 27 new tests green (`tests/test_validate.py`); full suite 119 passed.

**CANONICAL CONSTANTS — reuse verbatim, do not re-derive (for golden_master & end-to-end-generation authors)**
- Six-file order constant (load-bearing) lives in `rechner_pipeline.generate.output.EXPECTED_MAIN_OUTPUT_FILES`:
  `("inputs.py", "params.py", "tafeln.xml", "commutation.py", "actuarial.py", "test_run.py")`.
  `PYTHON_MAIN_OUTPUT_FILES` = the five `*.py` (everything except `tafeln.xml`); only those are compiled.
- `golden_master_outputs()` SHAPE: defined in `test_run.py`, must return a dict literal whose keys include `{"scalars", "tables"}` — i.e. `{"scalars": {<prefix>: {<name>: float}}, "tables": {<prefix>: [{<col>: float}]}}` (matches `qa/golden_master.py` lines 14–15). G1 checks this **statically via AST** (`golden_master_schema_error`): callable exists + every `return` is a dict literal containing both keys. G1 does **not** execute the code — running `golden_master_outputs()` for real is G4 (confinement) / G5 (golden master). G5 authors should import + call it; the AST precheck only guarantees the signature/shape is present.

**What hurt**
- "no outer text" subtlety: a response with FILE blocks but a non-empty prefix/suffix is reported as `outer_text` (highest priority), and a response with *no* blocks at all is also `outer_text` (the entire string is outside any block) rather than a distinct `no_files`. Matches AS-IS `_validate_no_outer_text` running first; flagging so downstream messaging is not surprised.
- On-disk "extra file" detection lists only top-level files in `--generated-dir` (no recursion). Sufficient for the flat `generated/` layout; if a future layout nests, revisit.

**Recommendation**
- Golden_master (G5) and end-to-end-generation authors: import `EXPECTED_MAIN_OUTPUT_FILES` / `PYTHON_MAIN_OUTPUT_FILES` from `generate.output` instead of hand-coding the list/order. Treat G1's `golden_master_schema_ok` as a *static* precheck only; G5 still owns the runtime contract.
- Deviations: none from the spec. The AS-IS module also had file-*writing* helpers (`write_*_to_generated_dir`); those were intentionally NOT ported into G1 (validation-only gate; writing is the generator's job, out of scope here).

### [wave1/security] — Static security gate (G2): migrated + extended AST scanner
- **What worked:** Ported `qa/security.py` verbatim from the source repo (AS-IS rule families unchanged: dangerous_import / dangerous_call / filesystem_access / syntax_error), then layered the three EXTENSION families on top without touching the existing logic — kept the AS-IS regression tests passing byte-for-byte. The scanner is pure AST (`ast.parse` + `NodeVisitor`); the target code is NEVER imported or executed (§2.6). `_call_name` alias resolution from the original already rewrites import aliases, so `from datetime import datetime as dt; dt.now()` resolves correctly. The toolbox command is a thin wrapper over `qa.security` (no duplicated rule logic), obeys the §3.3 contract exactly (single JSON stdout object via `run_command`, stderr logs, `--request-json` mergeable with `default=None`), and emits structured per-violation errors + per-category repair_hints so the generating agent can self-repair without parsing prose.
- **What hurt:** Two subtleties in the EXTENSION rules. (1) `random.random()` was flagged on the import but NOT the call, because `random` is not in `DANGEROUS_CALL_PREFIXES`; fixed by adding a root-based nondeterministic call check (any call into `random`/`secrets`/`uuid`/`time.*`), placed AFTER the dangerous-prefix block and gated on `"." in name` so a bare `random()` user function is not falsely flagged. (2) `os.getenv`/`os.environ` had to be checked BEFORE the `SAFE_CALL_NAMES`/`os.path` short-circuit, or `os.*` allow-listing would have let them through — the nondeterministic call/attribute check runs first in `_check_call` and in a dedicated `visit_Attribute`. Swallowed-exception detection is conservative: only BROAD handlers (`except:` / `except Exception`/`BaseException`, incl. tuples) whose body is trivial (`pass`/`...`/constant expr/bare continue|break) and contains NO `raise` are flagged — narrow `except ZeroDivisionError: return 0.0` and re-raising handlers are allowed, so legitimate numeric fallbacks are not blocked.
- **FINAL rule set (ids the end-to-end-generation author must make generated KLV code avoid):**
  - `dangerous_import` (exit 21) — `import`/`from-import` of root: `ftplib, http, httpx, importlib, pathlib, requests, runpy, shutil, socket, subprocess, tempfile, urllib`. (`import os` and `import glob` are ALLOWED.)
  - `dangerous_call` (exit 21) — `eval`, `exec`, `__import__`; write/append `open(...,'w'|'a'|'x'|'+')` (non-literal mode = conservatively write); any call prefixed `ftplib. http. httpx. importlib. os. pathlib. requests. runpy. shutil. socket. subprocess. tempfile. urllib.` EXCEPT the SAFE_CALL_NAMES allow-list (`os.path.{join,dirname,basename,abspath,normpath,split,splitext,relpath,commonpath,commonprefix}`, `os.fspath`, `glob.glob`, `glob.iglob`).
  - `filesystem_access` (exit 21) — any call whose final attribute is a filesystem method: `chmod exists glob is_dir is_file iterdir mkdir open read_bytes read_text rename replace resolve rglob rmdir stat touch unlink write_bytes write_text` (e.g. `Path(...).read_text()`).
  - `nondeterministic` (exit 21, EXTENSION) — import of `random, secrets, uuid, time`; any call into those roots; `time.{time,monotonic,perf_counter,process_time,localtime,gmtime}`, `datetime[.datetime|.date].{now,utcnow,today}` (any import/alias form), `os.{getenv,getenvb,urandom}`, `os.environ` access/`os.environ.get(...)`, `os.urandom`. (A fixed `datetime.datetime(2020,1,1)` literal is allowed — it is deterministic.)
  - `swallowed_exception` (exit 21, EXTENSION) — broad handler (`except:` / `except Exception`/`BaseException`) with a trivial body that never re-raises (silent `pass`/`...`).
  - `self_approval` (exit 21, EXTENSION) — a `test*` function that asserts a constant truth (`assert True`), or whose body is vacuous/inert (only `pass`/docstring/constant exprs) — i.e. it compares no computed value.
  - `syntax_error` (exit 21) — file did not parse.
  - Generated KLV calc code must therefore be a PURE function of explicit inputs: math/typing/dataclasses/json(read)/sys only; build paths with `os.path.*`; read inputs with read-only `open(...)`/`glob.glob`; NO time/RNG/env; let real errors propagate; tests must compare to real expected numbers.
- **Recommendation:** `gate_version` bumped to `2.0.0` (AS-IS implicit 1.0.0 + 3 extension families). Added a `snippet` field to `SecurityViolation.to_dict()` (extends the §2.4 shape with one extra key — additive, the 6 AS-IS keys are unchanged); confirm downstream dossier consumers tolerate extra keys (they should — `to_dict` is dict-typed). `RULES` (id->description) is exported from `qa.security` and surfaced in the command `summary.rules` so the generation skill can render the avoid-list directly. No `run_compare`/`runner.py` integration was wired (out of scope — that module is another agent's MIGRATE target); the gate is exercised via the toolbox command and direct `scan_python_*` calls only.

### [wave1/extract] — Excel extraction subsystem migrated, byte-identical, adapter seam + clean-staged toolbox command

**What worked**
- Ported `extract/{excel.py,openpyxl_backend.py,scalar_table.py}` verbatim from the source repo. Package name is identical (`rechner_pipeline`), so the cross-module imports (`from rechner_pipeline.extract.openpyxl_backend import export_raw`, etc.) work unchanged. Verified BYTE-FOR-BYTE: ran the source code (via `PYTHONPATH` to `rechner-pipeline/src`) and the ported code on the same `Tarifrechner_KLV.xlsm`; `diff -rq` over all artifacts (raw CSVs, `_compressed.csv`, `_scalar.json`, `_table_values.csv`, `names_manager.csv`, `vba/*.txt`) is empty. Only `export_manifest.json` differs, and only because it embeds the absolute out-dir path.
- `ExcelAdapter` is a true zero-behavior wrapper: it calls `export_excel_infos(..., backend=selected)` and rebuilds `ExportManifest` from **`Path` objects** (per the wave0 byte-compat caveat — string-built manifests mix `/` and `\`). It validates the manifest (llm_inputs exist, manifest JSON written) WITHOUT touching any Excel artifact.
- Clean/staged extraction (§4.2 step 3) implemented in the command, not the extractor: `_clean_stale_derived()` removes only `*_compressed.csv` / `*_scalar.json` / `*_table_values.csv` before the run, so a re-run cannot reuse a stale `_compressed.csv` (the AS-IS `compress_exported_csvs` reuses an existing one) or glob a stale scalar/table. Raw CSVs / names / VBA are preserved. Covered by 3 tests including an injected-ghost-file test.
- COM backend fails fast (exit 10, `dependency_unavailable`) on this host — no pywin32 — with NO silent openpyxl fallback. Verified live and in a test.

**What hurt**
- `extract/excel.py` line 402 has `build_cell_index(df: pd.DataFrame)` with no module-level `import pandas`. It is harmless only because `from __future__ import annotations` makes it a string annotation. Left as-is for byte-fidelity; future editors must not "fix" it by importing pandas eagerly (would break the no-hard-dep contract).
- The §2.2.11 appendix scalar/table example values were regenerated from COM fixtures and differ in trailing decimals from the live openpyxl cached-value output (e.g. `BJB` = `4465.6547026924` from openpyxl vs `4465.6547` in the appendix). The FILE SHAPE / keys / columns are exact; tests assert shape + key set, not the COM-rounded literals. Golden_master authors: trust the openpyxl-produced `*_scalar.json` / `*_table_values.csv`, not the appendix literals.
- Out-of-scope (NOT fixed, reporting only): `tests/test_validate.py` has 15 failures, all `AttributeError: 'ValidationResult' object has no attribute 'to_dict'`. This is the `validate` command (another owner). My `tests/test_extract.py` (13) and all models/schemas tests pass.

**Recommendation — for golden_master (G5), roundtrip (G7), dossier (G8) authors**
- Consume the bundle from `toolbox.extract`'s result: `paths.manifest_path` -> `<out_dir>/export_manifest.json`; expectation files are `<out_dir>/<prefix>_scalar.json` and `<out_dir>/<prefix>_table_values.csv` (prefix = sheet stem, e.g. `Kalkulation`). Only sheets that have a `_compressed.csv` get scalar/table files. The KLV workbook yields exactly `Kalkulation_scalar.json` (keys: Bxt, BJB, BZB, Pxt, ratzu) and `Kalkulation_table_values.csv`; `Tafeln` has no formulas so no derived files.
- `expectation_coverage` semantics (set explicitly on the bundle, echoed at `summary.expectation_coverage` and `summary.input_bundle`): `full` = at least one numeric scalar expectation present (KLV is `full`, 5/5 numeric, 612 table cells); `sparse` = derived files exist but contain no numeric values; `none` = no numeric scalars and no table cells. The full `CoverageDetail` audit block (`scalar_keys_numeric`, `table_cells_expected`, etc.) is in `summary.input_bundle.coverage_detail`. A `sparse`/`none` adapter result should route to `human_review_result(reason="coverage")` (exit 31) downstream — the extract command itself does not gate on coverage, it only reports it.
- `manifest.llm_inputs` is the source-neutral generation input list (compressed sheet CSV where it exists, else raw sheet CSV; then names_manager; then VBA). `output_hashes` keys are repo-relative.

### [wave1/golden_master] — G5 golden-master + G4 confinement migrated; false-green fixed

**Resolution mode:** Ported `qa/golden_master.py` (engine, fixed) + `qa/fs_confine.py` (byte-identical KEEP) and added the `toolbox.golden_master` command (gates G5+G4). All four mandated fixtures + a write-block fixture pass; `pytest tests/test_golden_master.py tests/test_fs_confine.py -q` = 19 passed.

**What worked**
- The AS-IS compare engine is genuinely idiom-stable — porting it verbatim and only touching the verdict was low-risk. Fix is two lines of intent: `Report.ok = not deviations and not unmatched_columns` (closes unmatched-column false-green) plus a new `Report.compared_anything` property (`scalars_tested + table_cells_tested > 0`) that the command reads to refuse zero-comparison acceptance.
- Running the compare inside fs_confine via a real child process (`[sys.executable, fs_confine.__file__, repo_root, child_script, info_dir]`, `cwd=generated/`, `capture_output`) keeps G4 honest: the *generated kernel actually executes under the guards*, not just a static check. The child prints its structured Report wrapped in `@@GM_JSON_BEGIN@@…@@GM_JSON_END@@` markers; the parent extracts it, so library/oletools chatter on the child stdout can't be mistaken for the result.
- `_common.human_review_result(reason="coverage")` already maps to exit 31 — zero-comparison policy needed no new plumbing.

**What hurt**
- `info_from_excel/` MUST live under the confinement root (repo_root). It does in the AS-IS layout, but the command takes `--info-dir` explicitly: if a future caller points `--info-dir` outside `--repo-root`, the confined child's expectation reads will be blocked and you'll get a `confinement_failure` (exit 30), not a clear usage error. Roundtrip/e2e authors: keep info_dir under repo_root, or the dossier author should validate that invariant.
- The original `golden_master.main()` launcher (cwd-based, exit 0/1) is retained in the qa module for compatibility but is NOT what the gate uses; the toolbox command is the gate surface. Don't wire the old `main()` into acceptance.

**Recommendation / exact contract for roundtrip + e2e authors**
- **Command:** `python -m rechner_pipeline.toolbox.golden_master --repo-root R --generated-dir R/generated --info-dir R/info_from_excel [--diagnostics-dir D]`. Flags are mergeable (`--request-json -`). Exit: 0 pass, 30 mismatch/unmatched-column/missing-callable/confinement failure, 31 human_review (zero-comparison coverage), 2 usage.
- **Kernel contract:** `generated/test_run.py` must expose `golden_master_outputs() -> {"scalars": {prefix: {name: number}}, "tables": {prefix: [ {col: number}, ... ]}}`. Missing import/callable/wrong-schema → exit 30.
- **Scalar file format:** `<prefix>_scalar.json` = flat JSON object `{name: value}`. `None`/""/non-numeric → expected `None` → SKIPPED (`kein-soll`), not tested. Prefix = filename minus `_scalar.json`.
- **Table file format:** `<prefix>_table_values.csv`, UTF-8, `csv.DictReader` (comma delim, header row), `newline=""`. Prefix = filename minus `_table_values.csv`. Empty cells = no expectation for that cell.
- **Compare semantics:** 4-decimal rounding (`round(a,4)==round(b,4)`). Column matching strips `_`, space, `.` and is **case-SENSITIVE** (`A_xn`==`Axn`, `Axn`!=`axn`). Extra computed scalars/columns/rows ignored; missing expected ones recorded. **An expected scalar/column with data absent from output is now a hard failure** (the fix) — exit 30, error code `unmatched_expected_column`. **A run that compared zero scalars AND zero cells is never full-acceptance** (the fix) — exit 31, `status="human_review_required"`, error code `zero_comparison`.
- **summary fields:** `scalars_tested, scalars_skipped, table_cells_tested, deviation_count, deviations[:20], unmatched_columns, compared_anything, computed_output_hash`. `output_hashes["golden_master_outputs"]` = SHA-256 of the canonical (sorted-keys) computed dict — use this for G7 repeated-output stability.
- **fs_confine API:** `install(root)` monkeypatches `builtins.open` (blocks modes w/a/x/+; blocks reads not under `realpath(root)`) and `glob.glob`/`glob.iglob` (filter to root). Launcher: `python <fs_confine.py> <root> <script.py> [args...]` → installs guards, sets `sys.argv=[script,*args]`, runs via `runpy.run_path(run_name="__main__")`, propagates SystemExit. A blocked write surfaces as `PermissionError("fs-confine: write access is blocked: ...")`.

**Deviations:** none — all verification passed first time after porting; no out-of-scope edits (did not touch `qa/__init__.py`, runner.py, STATE.md, MIGRATION.md).

### [wave1/dossier] — G8 dossier-completeness gate + qa_report aggregator
- **What worked:** The wave0 `_common`/`schemas` plumbing carried the whole gate. `dossier` is pure aggregation: `build_result`/`human_review_result` for stdout, `QaReport.compute_accepted()` as the single acceptance rule (never hand-rolled), `RunDossierV2Delta.merge_into()` for the v2 dossier, `GateLedgerEntry.from_dict`/`.validate()` for the ledger. The provenance logic lives in `orchestrate/dossier.py` (pure functions, no I/O); the toolbox command only wires flags + writes files. 13 new tests + full suite 132 passed. Recorded REAL deps via `importlib.metadata` + `platform.python_version()` → `python 3.12.4` (NOT the §6.8 `3.11.x` placeholder), openpyxl 3.1.5 / oletools 0.60.2 / pandas 2.3.3 / hypothesis 6.155.5. **Resolution: fully_resolved** (ran the venv for real: accepted exit 0, failed-gate exit 40, schema-omission failures, pytest green).
- **What hurt:** §6.8.3/§6.8.4 never specify HOW gates hand their ledger entries to `dossier` — there is no defined filename or directory convention in MIGRATION.md. I had to invent one (below). Every gate author + the end-to-end author MUST adopt it or `dossier` sees zero entries and blocks everything as `gate.missing`. Also: §3.5 marks ALL of G0–G7 as required, so until Wave-2 (conventions/algebraic/roundtrip) ships, NO run can be fully `accepted` — that is correct/honest, but the end-to-end author must expect exit 40 on KLV until all seven gates exist.

- **CONTRACT every gate author + end-to-end author MUST follow (so ledger entries are compatible):**
  1. **Each gate writes ONE §6.8.2 `GateLedgerEntry` JSON into `--diagnostics-dir`**, filename = `<command>.gate.json` (e.g. `golden_master.gate.json`, `extract.gate.json`). Constant: `orchestrate.dossier.GATE_LEDGER_SUFFIX == ".gate.json"`. `dossier` globs `*<suffix>`, sorted by filename. This is SEPARATE from a gate's own `diagnostics_path` blob — the `.gate.json` is the acceptance ledger row; `diagnostics_path` inside it points at the gate's detailed diagnostics.
  2. **Exact ledger JSON each gate must write** (all keys required; build it via `schemas.GateLedgerEntry(...).to_dict()` and `.validate()` before writing):
     ```json
     {"gate":"G5.golden-master","command":"golden_master","gate_version":"1.0.0",
      "required":true,"status":"passed","attempt":1,"started_at":"<UTC ISO>",
      "input_hashes":{"generated\test_run.py":"<sha256>"},
      "diagnostics_path":"runs\<run-id>\golden_master.diagnostics.json",
      "summary":{...gate-specific...}}
     ```
     `input_hashes` MUST be non-empty for a passed gate (use `hash_files(paths, base=repo_root)`) — `dossier` BLOCKS (`hashes.missing`) a passed required gate that recorded none. A gate that surfaces a strict-error warning puts it in `summary.warnings:[{...,"strict_error":true}]` → `dossier` promotes it to a blocking warning.
  3. **Required-gate list (gate id → command), the §3.5 acceptance set, exported as `orchestrate.dossier.REQUIRED_GATES` / `ALL_GATES`:**
     `G0.extraction-manifest`→`extract`, `G1.file-contract`→`validate`, `G2.static-security`→`security`, `G3.architecture-conventions`→`conventions`, `G5.golden-master`→`golden_master`, `G6.algebraic-properties`→`algebraic`, `G7.roundtrips`→`roundtrip`. (No `G4` ledger row — runtime-confinement is enforced *inside* golden_master/roundtrip, not a standalone command. G8 is `dossier` itself and never writes its own ledger row.) **A missing required entry → `gate.missing` blocker**, so Wave-2 absence correctly prevents acceptance.
  4. **Orchestrator context** (optional, all degrade safely): the end-to-end/CLI author may drop `generated/dossier_input.json` with `{run_id, expectation_coverage, attempts_used, max_attempts, cli:{name,headless}, options:{provider,max_output_tokens,export_backend,test_mode,adapter_id,max_attempts}, open_assumptions:[], attempts:[], qa_contract_path, tafeln_xml_canonical_sha256}`, and/or `info_from_excel/input_bundle.json` (the §6.8.5 coverage block). `options` flows verbatim into `run_dossier.run.options` — **so `export_backend` is supplied HERE.** Missing context → conservative defaults (coverage `none` → forces a `coverage.not_full` human-review open assumption; `max_attempts=4`).
- **Recommendation:** Lead should pin the `.gate.json` filename convention + the required-gate map into the shared brief BEFORE the Wave-2 gate authors and the end-to-end author start, identical to how the wave0 `_common` API was pinned. The three constants (`GATE_LEDGER_SUFFIX`, `REQUIRED_GATES`, `ALL_GATES`) now live in `orchestrate/dossier.py` as the single source of truth — gate authors should import them rather than hardcode strings. Acceptance handoff (`max_attempts` exhausted, or non-full coverage) returns `human_review_result(reason="dossier")` → exit 40, `status=human_review_required`; a plain unmet blocker returns exit 40 `status=failed`.

**Deviations:** none. Only owned files touched (`orchestrate/__init__.py`, `orchestrate/dossier.py`, `toolbox/dossier.py`, `tests/test_dossier.py`) + this PROJECT-LEAD.md entry. Did not edit STATE.md/MIGRATION.md. Note for lead: §6.8.2's example uses a bare `conventions.diagnostics.json` path — that is the gate's detail blob, NOT the acceptance ledger filename; I made the ledger filename explicit (`<command>.gate.json`) to avoid collision, since the spec left it undefined.

### [wave1/review-core] — PASS-WITH-FIXES
- **resolution_mode:** fully_resolved (ran `.venv\Scripts\python.exe`; extracted KLV with both ported & source extractors; executed fs_confine escape fixtures; probed the compare engine).
- **Byte-identity (verified):** ported `extract` vs source extractor on `examples/Tarifrechner_KLV.xlsm` → `diff -rq` shows the ONLY differing file is `export_manifest.json`, and that difference is exclusively the out_dir absolute-path prefix. All data artifacts (CSVs, scalar JSON, table CSV, VBA, names_manager) are byte-identical. Claim CONFIRMED. (`extract/{excel,openpyxl_backend,scalar_table}.py` are in fact textually identical to the source repo — zero porting drift.)
- **§2.2.11 / point 4 (CLEAN):** `golden_master.load_expected()` reads expectations only from on-disk `info_from_excel/*_scalar.json` + `*_table_values.csv`; no hardcoded literals (grep-verified). With the openpyxl default backend the same cached values feed BOTH extraction and the golden master, so the KLV e2e run is self-consistent. The COM-vs-cache trailing-decimal worry does not apply to the default path.

- **CRITICAL — `qa/fs_confine.py` is bypassable; G4 runtime confinement is porous.** Empirically, under `fs_confine` with root=a subdir, a child script: wrote outside root via `os.open`+`os.write` AND `pathlib.Path.write_text`; deleted an outside file via `os.remove`; READ an outside secret via `os.read` AND `io.open` AND `pathlib.read_text`; opened a network socket; ran `subprocess.run(["whoami"])` — ALL exit 0, all succeeded (commands in `.tmp/`, since cleaned). Root cause (fs_confine.py:65): `install()` rebinds only `builtins.open`. (a) `io.open` is the SAME object as `builtins.open` pre-patch but is NOT rebound, so pathlib/io/most libs that call `io.open` dodge even the read guard (`io.open is builtins.open` → True before, False after; pathlib calls `io.open`). (b) `os.open`/`os.remove`/`os.*` and `socket`/`subprocess` are entirely unguarded. Per spec line 1260 these are "expected to be rejected statically before this subprocess is reached" — i.e. fs_confine is by-design only a secondary `open`/`glob` layer. **The real risk for the e2e author:** `toolbox/golden_master.py` executes the generated `test_run.py` under fs_confine but does NOT itself invoke the static security gate (G2). If `golden_master` is ever run on a kernel that has not already passed `qa.security`, arbitrary code (network/subprocess/os-write/outside-read) runs unconfined. Fix: in `golden_master.main()` require/verify a passing G2 report before execution, OR harden fs_confine (also patch `io.open`; add `os.open`/`os.remove`/`os.rename`/`os.replace`/`os.unlink` guards; block `socket`/`subprocess` at runtime). Do not advertise "read-only within repo root" as enforced — currently it is not (`io.open`/`pathlib` read outside succeeds).

- **High — 4-decimal ABSOLUTE rounding hides unbounded relative drift.** `_eq4` (golden_master.py:65) uses `round(a,4)==round(b,4)`. Verified: expected 0.00001 vs computed 0.00004 PASSES (300% relative error); 100000.00001 vs 100000.00004 PASSES. For small-magnitude actuarial quantities (probabilities, per-mille rates) a materially wrong kernel can pass G5. Spec line 1752 acknowledges "4-decimal comparison can hide internal drift," so this is a documented limitation, not a contract violation — but the e2e author MUST NOT treat a green G5 as proof of relative accuracy; the planned algebraic/property gate (G6) is load-bearing, not optional. Consider a relative-tolerance companion check.

- **Low / note for e2e author — scalar names are matched EXACTLY (case-sensitive, NO separator normalization), unlike table columns.** `_compare_scalars` keys on the raw JSON name; only table columns get `_norm_colname` leniency. A kernel returning `bxt` or `B_xt` instead of `Bxt` fails as "ohne berechneten Wert" (correct fail, not false-green). The generated `golden_master_outputs()["scalars"]` keys must equal the `*_scalar.json` keys byte-for-byte (here: `Bxt, BJB, BZB, Pxt, ratzu`).

- **False-green robustness (mostly ROBUST):** all-empty expectations, header-only tables, all-empty columns, and fully-empty expectation sets correctly yield `compared_anything=False` → toolbox routes to exit 31 (human review), never a pass. Wrong-prefix scalars fail. NaN expected vs NaN computed correctly FAILS (nan!=nan). The only residual: `inf`==`inf` passes `_eq4` (a div-by-zero workbook bug reproduced as inf would pass) — minor, and consistent with "golden master can preserve workbook errors" (line 1752). No path found that reports `passed` (exit 0) while comparing zero cells.

- **Verdict: PASS-WITH-FIXES.** Extraction core and golden-master compare logic are faithful and the documented false-green fix holds at the gate boundary. The blocking item before relying on G4 in the full-agentic loop is the fs_confine bypass: either gate golden_master execution behind a verified G2 pass, or harden fs_confine to cover `io.open`/`os.*`/network/subprocess.

### [wave1/review-integration] — BLOCK
- **resolution_mode:** fully_resolved (ran `.venv\Scripts\python.exe` against `.tmp/` fixtures for all 5 commands + dossier aggregation; evidence below is command output, not inference).
- **Verdict: BLOCK.** The cross-gate ledger contract is entirely unwired: the dossier (G8) can never see any gate result, so the toolbox can NEVER reach `accepted`. Two of the five commands reject `--diagnostics-dir` outright. Plus a real stdout-purity crash on non-cp1252 output. The per-command gate logic is solid; the integration that ties them together does not exist.

#### CRITICAL — The ledger wiring gap (the toolbox cannot produce an accepted run)
- **Evidence (empirical).** Ran on a valid 6-file fixture, all pointing at one shared `.tmp/diag/`:
  - `validate --diagnostics-dir .tmp/diag` -> **exit 2**, `error: unrecognized arguments: --diagnostics-dir` (validate has no such flag; `_build_parser` only declares `--repo-root/--generated-dir/--info-dir/--file-block-response/--request-json`, validate.py:81-92).
  - `extract --diagnostics-dir .tmp/diag` -> **exit 2**, same `unrecognized arguments` error (extract.py:99-125 has no `--diagnostics-dir`).
  - `security --generated-dir .tmp/gen --diagnostics-dir .tmp/diag` -> exit 0, but writes only `static_security_report.json` (security.py:139-144). **No `security.gate.json`.**
  - `golden_master ... --diagnostics-dir .tmp/diag` -> exit 31, writes only `golden_master_child.log` (golden_master.py:262-269). **No `golden_master.gate.json`.**
  - `ls .tmp/diag` after all gates ran: `golden_master_child.log`, `static_security_report.json` — **zero `*.gate.json` files.**
  - `dossier --diagnostics-dir .tmp/diag` -> **exit 40, status human_review_required, `gates_present: []`**, with `gate.missing` for ALL SEVEN required gates (G0,G1,G2,G3,G5,G6,G7) + one `open_assumption.unapproved`.
- **Root cause.** `orchestrate/dossier.load_gate_ledger()` globs `*{GATE_LEDGER_SUFFIX}` = `*.gate.json` (dossier.py:147, GATE_LEDGER_SUFFIX=".gate.json" at line 85). **No gate command writes such a file.** `GateLedgerEntry` exists (schemas.py:180) and is read, but is never produced. The producer side of the §6.8.2 contract was never implemented. `toolbox/dossier.py:8-9` docstring asserts the gates "wrote into `--diagnostics-dir` (`<command>.gate.json` files)" — documentation of a contract that no code fulfills.
- **Compounding:** the three Wave-2 gate commands `conventions`/`algebraic`/`roundtrip` do not exist as toolbox modules at all (`toolbox/` contains only extract, validate, security, golden_master, dossier), yet `REQUIRED_GATES` lists all seven (dossier.py:68-81). So even after wiring the four existing gates, G3/G6/G7 still `gate.missing` and block acceptance — honest, but means the pipeline is non-acceptable until Wave-2 lands too.
- **Impact:** §3.5 G8 / §6.8.2 / §6.8.3 are non-functional end-to-end. `accepted` is unreachable by construction. This is the headline reconciliation item.

##### Recommended ledger-wiring spec (feeds the reconciliation wave)
Prefer **per-gate self-write via a shared `_common` helper** over an stdout-capturing orchestrator (the orchestrator approach re-parses each command's JSON and re-derives `required`/`gate`/`attempt`, duplicating logic and breaking the "scripts are the source of truth" principle; self-write keeps each gate authoritative for its own entry and stays CI/transparent per §3.3).
- **Add to `toolbox/_common.py`:** `write_gate_ledger(diagnostics_dir, *, gate, command, gate_version, status, input_hashes, attempt=1, required=True, summary=None, diagnostics_path=None, started_at=None) -> Path`. It builds a `schemas.GateLedgerEntry`, calls `.validate()` (raise/log on error), and writes `<diagnostics_dir>/<command>.gate.json` as UTF-8 JSON. Capture `started_at = utc_now()` at command entry.
- **Wire each gate** (call it just before `return build_result(...)`, for BOTH pass and fail outcomes so a failing required gate is recorded as `status="failed"`, which `evaluate_blockers` needs):
  - `extract` -> add `--diagnostics-dir` flag; write `extract.gate.json`, `gate="G0.extraction-manifest"`, status from exit (0->passed, 10->failed), `input_hashes` = the manifest/llm_inputs hashes it already computes, `summary` = the coverage/artifact_counts block.
  - `validate` -> add `--diagnostics-dir` flag; write `validate.gate.json`, `gate="G1.file-contract"`, status, `input_hashes` (the on-disk file hashes it already builds), `summary` = its existing summary.
  - `security` -> already has `--diagnostics-dir`; write `security.gate.json`, `gate="G2.static-security"`, status, `input_hashes`, `summary` (existing, optionally minus bulky `violations`/`rules`; keep `warnings` for strict-error surfacing).
  - `golden_master` -> already has `--diagnostics-dir`; write `golden_master.gate.json`, `gate="G5.golden-master"`, status (zero-coverage human-review must record `status="human_review_required"`, a valid `STATUS_VALUES` member, so it blocks as not-passed), `input_hashes`, `summary`.
  - When `conventions`/`algebraic`/`roundtrip` are authored, each self-writes `G3/G6/G7` identically.
- **The exact `<command>.gate.json` shape** is the §6.8.2 `GateLedgerEntry`: `{gate, command, gate_version, required, status, attempt, started_at, input_hashes, [diagnostics_path], summary}` — confirmed tolerated by `GateLedgerEntry.from_dict`/`.validate` (extra keys ignored; `summary` free-form).
- **Dossier-side note:** `evaluate_blockers` blocks `hashes.missing` when a required gate's ledger has empty `input_hashes` (dossier.py:428). `security`/`golden_master` already compute `input_hashes`; ensure the ledger carries them. `validate`'s `direct_file_edit` path hashes only present expected files with `missing_ok=True` — fine when files exist.

#### HIGH — stdout-purity crash on non-cp1252 output (real §3.3 violation)
- **Evidence.** `validate --file-block-response <utf-8-BOM file>`: the BOM lands in the `outer_text` error snippet, then `emit_json` (`_common.py:219`) does `out.write(json.dumps(obj, ensure_ascii=False))` to a Windows cp1252 stdout -> `UnicodeEncodeError: 'charmap' codec can't encode character '﻿'`. Result: **traceback to stderr, ZERO bytes of JSON on stdout, process exit 1** (not a standard toolbox code). Re-running with `PYTHONIOENCODING=utf-8` returns the correct `status=failed code=['outer_text']`, proving the validate logic is right and the fault is the emitter.
- **Root cause + why the guard misses it.** `run_command` redirects stdout->stderr for the body, then calls `emit_result` AFTER the `with` block (`_common.py:317-318`), i.e. OUTSIDE the `try/except BaseException` that converts errors to an INTERNAL result. So an encode error in the single emit is uncaught and breaks the "exactly one JSON object" guarantee — the one thing `run_command` exists to ensure. Realistic trigger: UTF-8-BOM files are ubiquitous on Windows, and any truly-non-cp1252 char in any error `detail`/`snippet`/`message` will do it. (cp1252-encodable chars like ä/ö/ü/ß/smart-quotes do NOT trigger it — tested, no crash — so the blast radius is "non-cp1252 chars in the payload," not all non-ASCII.)
- **Fix.** In `emit_json`, write encoding-safe regardless of console codepage: `out.buffer.write(json.dumps(obj, ensure_ascii=False).encode("utf-8")+b"\n"); out.buffer.flush()` when `out` has a `.buffer`, else fall back; OR `sys.stdout.reconfigure(encoding="utf-8")` at `run_command` entry. Also move the `emit_result` call INSIDE a `try` so an emit failure degrades to an INTERNAL result on a guaranteed-encodable channel rather than a bare traceback.

#### MEDIUM — `golden_master_outputs()` precheck accepts wrong value types
- **Evidence.** `test_run.py` with `return {"scalars": [1,2], "tables": "nope"}` -> validate reports `golden_master_schema_ok=True, status=passed`. The static precheck (`output.py:291-406`) only checks that the returned dict literal's KEYS include `{"scalars","tables"}`, not that the values are dict-shaped.
- **Assessment.** Acceptable-by-design: §2.3.5/§6.3 G1 specify only the static key shape; §3.5 G5 (golden_master, runtime) type-checks values (its confined child requires `isinstance(computed, dict)` and the two keys, golden_master.py:119). A documented precheck limitation, not a contract miss — but `golden_master_schema_ok=True` is mildly misleading; consider renaming to `golden_master_keys_ok`.

#### Things that PASS (verified, not assumed)
- **Exit/status mirroring (§3.3) — all correct.** security fail->21/failed; validate fail->20/failed; extract missing-source->10/failed; golden_master zero-comparison->31/human_review_required; dossier no-ledger->40/human_review_required. Shell exit code matches the JSON `exit_code` in every case.
- **stdout purity under real libraries.** `extract` (imports oletools+pandas, ran a real `examples/Tarifrechner_KLV.xlsm` extract) and `security` each emit EXACTLY one parseable JSON object on one line (`wc -l`=1; piped straight into `json.load` -> OK). The `run_command` redirect mechanism works for library banners — only the post-body emit encoding (HIGH above) breaks.
- **GateLedgerEntry tolerates security's extra `snippet`.** `GateLedgerEntry.from_dict({...summary with violations[].snippet...}).validate()` -> `[]`; the extra key round-trips inside the free-form `summary`. (Moot until security actually writes a ledger, but the tolerance is real.)
- **validate adversarial inputs — all rejected:** 7th valid-named extra file on disk -> `invalid_file_set` (exit 20); out-of-order blocks -> `wrong_order`; duplicate FILE block -> `duplicate_blocks`; non-dict-literal return (`return _mk()`) -> `golden_master_schema`; outer text/BOM prefix -> `outer_text` (correct verdict; only the emit crashes, HIGH above).
- **Wave-2-missing honesty (§6.8.3).** A run missing conventions/algebraic/roundtrip CANNOT be accepted — `evaluate_blockers` emits `gate.missing` for G3/G6/G7 and `compute_accepted` requires all required gates `passed`. Non-full coverage is force-added as an unapproved `coverage.not_full` open assumption (toolbox/dossier.py:190-204), so a zero-comparison run cannot masquerade as validated. Confirmed.

**Bottom line for reconciliation:** implement `_common.write_gate_ledger` + add `--diagnostics-dir` to extract/validate + call the helper from all four existing gates (pass AND fail paths), fix `emit_json` encoding, then the four-gate subset of the dossier becomes exercisable; full acceptance still waits on the Wave-2 gate commands existing.

### [wave1b/common] — write_gate_ledger helper + UTF-8-safe emit (foundation hardened)

Two foundation fixes landed in `src/rechner_pipeline/toolbox/_common.py`; all tests green (**145 passed**, was 132). ADD-only — every existing signature unchanged.

**Resolution mode:** ADD-only on `_common.py`; one re-export edit on `orchestrate/dossier.py`; new test file `tests/test_common.py` (13 tests). No git commit.

#### Fix 1 — `write_gate_ledger` (the call contract the parallel wave MUST use)

```python
write_gate_ledger(
    result,                 # ToolboxResult (any status: pass OR fail path)
    diagnostics_dir,        # str | Path; created if absent
    *,
    repo_root=None,         # accepted for a stable cross-wave contract (reserved)
    attempt=1,              # §6.8.2 attempt index
    started_at=None,        # ISO-8601 UTC; defaults to utc_now()
    ended_at=None,          # ISO-8601 UTC; recorded under summary.ended_at
    command_line=None,      # Iterable[str] argv; recorded under summary.command_line
    gate=None,              # override; else result.gate, else derived from catalogue
    required=None,          # override; else (gate in REQUIRED_GATES)
) -> Path                   # returns the written file path
```

- **Both ledger-wiring and confinement agents call it identically:** `write_gate_ledger(result, diagnostics_dir, repo_root=...)`. Call it on BOTH the pass and the fail path with the same `result` you emit — `status`/`exit_code` are taken verbatim from `result`.
- **Filename / suffix:** writes `<diagnostics_dir>/<result.command>` + `GATE_LEDGER_SUFFIX` (`.gate.json`), e.g. `golden_master.gate.json` — the SAME suffix `orchestrate.dossier.load_gate_ledger` globs.
- **Gate id:** uses `result.gate` if set (gate commands already set e.g. `gate="G5.golden-master"`); otherwise derives it from the dossier `ALL_GATES` catalogue via the command name; last-resort falls back to the command name so the entry always validates.
- **`required`** defaults to `gate in REQUIRED_GATES`.
- **Validation:** builds `schemas.GateLedgerEntry`, calls `.validate()`, and raises `ValueError` if it fails — so a malformed ledger never reaches disk.
- **Schema-fixed extras** that have no first-class field on `GateLedgerEntry` (`exit_code`, `ended_at`, `command_line`, `output_hashes`, `metrics`, `errors`) are tucked under `summary` (free-form), so nothing is lost and §6.8.2 validation still passes.
- **Round-trip confirmed:** `provenance.load_gate_ledger(diagnostics_dir)` reads the file back, `read_errors == []`, and the gate id appears in `sorted({e.gate for e in entries})` — i.e. it counts toward `gates_present`. Verified for a `failed` result too.

#### Circular-import decision (single source of truth)

`GATE_LEDGER_SUFFIX` now lives in `_common` (the lowest module: `orchestrate.dossier → models.schemas → toolbox._common`). `orchestrate.dossier` **imports** it from `_common` and re-exports it, so `provenance.GATE_LEDGER_SUFFIX` is unchanged and `_common.GATE_LEDGER_SUFFIX is dossier.GATE_LEDGER_SUFFIX`. The gate catalogue (`ALL_GATES`/`REQUIRED_GATES`) stays in `dossier`; `write_gate_ledger` reads it via a **lazy import inside the function** (never at module load), keeping the graph acyclic with a safe empty-catalogue fallback (→ `required=True`).

#### Fix 2 — UTF-8 stdout, emit cannot crash

- `run_command` now calls `force_utf8_stream(sys.stdout)` / `force_utf8_stream(sys.stderr)` up front (`reconfigure(encoding="utf-8")`, guarded for streams lacking it).
- The single-JSON emit moved **inside** `run_command`'s protected region: any emit failure becomes an INTERNAL (exit 50) result on a usable stream + traceback to stderr — never empty stdout.
- `emit_json` is hardened in layers: write → on `UnicodeEncodeError` reconfigure+retry → write UTF-8 bytes via `.buffer` → ASCII-escape fallback. `ensure_ascii=False` is kept (real UTF-8) but is now crash-proof. New public helpers: `force_utf8_stream(stream)`, `utc_now()`.
- Proven: a result containing a BOM + `☃` (non-cp1252) emits valid UTF-8 JSON (`json.loads` of the decoded bytes succeeds) with the correct exit code on a simulated cp1252 console.

### [wave1b/ledger-wiring] — Gate commands now emit `<command>.gate.json` ledger entries
- **Resolution mode:** wired the existing `_common.write_gate_ledger` helper into the three wave-1 gate commands so each writes its §6.8.2 ledger entry as a SIDE artifact to `--diagnostics-dir` on BOTH pass and fail. No `emit_result` calls were added — `run_command` still owns the single stdout JSON; the ledger is disk-only.
- **Files:** `src/rechner_pipeline/toolbox/extract.py`, `src/rechner_pipeline/toolbox/validate.py`, `src/rechner_pipeline/toolbox/security.py`, `tests/test_ledger_wiring.py` (NEW).
- **`--diagnostics-dir`:** added to `extract` and `validate` (they previously rejected it → argparse exit 2); `security` already had it. Flag `default=None` (request-json mergeable). Default when omitted: `<out-dir>/diagnostics` (extract), `<generated-dir>/diagnostics` (validate), `<generated-dir>` (security, matching where it already writes `static_security_report.json`); cwd `/diagnostics` fallback for the early usage-error paths.
- **Wiring:** each `main` captures `started_at = utc_now()` at the top, resolves `diagnostics_dir` early, and defines a local `_finalize(result)` that calls `write_gate_ledger(result, diagnostics_dir, repo_root=..., started_at=..., ended_at=utc_now(), command_line=argv or sys.argv[1:])`. Every `return build_result(...)` is wrapped in `_finalize(...)`. A ledger-write failure is logged to stderr and swallowed so it can never mask the real gate result.
- **Gate ids:** extract→`G0.extraction-manifest`, validate→`G1.file-contract`, security→`G2.static-security`. extract sets no `gate=` so the helper derives G0 from the dossier catalogue (verified on both pass and fail); validate/security pass their `GATE` through. All confirmed via `load_gate_ledger`.
- **Verify (run for real, openpyxl backend):**
  - `ls .tmp/diag` → `extract.gate.json`, `validate.gate.json`, `security.gate.json` (+ pre-existing `static_security_report.json`).
  - `dossier.load_gate_ledger(".tmp/diag")` → `read_errors == []`, gates `{G0.extraction-manifest, G1.file-contract, G2.static-security}` all present, all `status=passed`, each `entry.validate() == []`.
  - Fail path proven too: empty generated-dir → `validate.gate.json` with `status=failed`, `summary.exit_code=20`.
  - **stdout purity:** each command's stdout is exactly one parseable JSON object (1 line, `json.load` OK); an in-process `redirect_stdout` test asserts `main()` writes nothing to stdout (ledger goes to disk only).
- **pytest:** `157 passed, 1 failed` (was 145; +12 = 9 new ledger-wiring tests + 3 others already added by the concurrent wave). The lone failure is `tests/test_golden_master.py::test_e2e_confinement_blocks_kernel_write` (`assert 21 == 30` — a runtime fs_confine/golden_master exit-code concern), which is OUTSIDE this task's scope and owned by the concurrent golden_master/fs_confine agent. All in-scope suites (extract, validate, security, ledger_wiring, common, dossier) are 101/101 green.
- **Deviations:** none from the contract. Note the failing golden_master test is a hand-off item for the concurrent agent, not a regression from this change (these commands' exit-code/scan logic was untouched).

### [wave1b/confinement] — fs_confine hardened (real runtime confinement) + golden_master ordered behind G2 static security

**Resolution mode:** edited only the four files in scope. `qa/golden_master.py` (engine) was NOT touched — confinement + G2-gating + ledger all live in the toolbox layer (`toolbox/golden_master.py`).

**Files:** `src/rechner_pipeline/qa/fs_confine.py`, `src/rechner_pipeline/toolbox/golden_master.py`, `tests/test_fs_confine.py`, `tests/test_golden_master.py`.

**FINAL fs_confine (G4) guarantees** — for the e2e author. `install(root)` now patches at the *definition site* (not just `builtins.open`) and returns a `_Restore` whose `.undo()` reverts every patch (use it in-process so guards don't leak; the launcher child needs no undo). Blocked / allowed:
- **Writes blocked everywhere:** `builtins.open` AND `io.open` (pre-patch `builtins.open is io.open`, so io.open was the bypass), any write/append/create mode; `os.open` with any write/create flag; `os.write(fd>2)`; and `os.remove/unlink/rename/renames/replace/rmdir/removedirs/mkdir/makedirs/truncate/ftruncate/link/symlink/chmod/chown/mkfifo/mknod` (hard `PermissionError`). `pathlib.write_text/Path.open('w')` are blocked transitively because they bottom out in the patched `io.open`/`os.*`.
- **Reads allowed ONLY under `realpath(root)` (read-only):** `open`/`io.open`/`os.open(O_RDONLY)` outside the root raise `read outside repo root is blocked`; `glob.glob`/`iglob` filter out-of-root matches.
- **Network blocked:** `socket.socket`, `socket.create_connection/create_server`.
- **Subprocess blocked:** `subprocess.Popen/run/call/check_call/check_output/getoutput/getstatusoutput`, plus `os.system/popen/exec*/spawn*/posix_spawn*/fork/forkpty/startfile`.
- **fd 1/2 (stdout/stderr) writes stay allowed** so the confined child can still emit its JSON result.

**LIMITS (read this).** This is **defense-in-depth, NOT a formal OS sandbox** (per §2.6, documented in the module docstring). It is pure-Python monkeypatching: native code (ctypes, compiled C-extensions, low-level fd tricks via `os.dup`/inherited fds) can defeat it. The real trust model is layered: **G2 static AST scan (the construct never gets through) + G4 runtime confine (this layer) + subprocess isolation (cwd=`generated/`).** Do not treat fs_confine as a hard security boundary in isolation.

**G2 ordering (self-contained).** `toolbox/golden_master.py` now runs `qa.security.scan_python_paths()` over every `*.py` in `--generated-dir` **before** importing/executing the kernel. Any violation → **REFUSE to execute**, return `exit 21` (`Exit.SECURITY`), `code="precondition_failed"`, with `summary.security_precondition="failed"` and violation details. This makes G5 robust regardless of orchestration order — even if an orchestrator skipped G2, unsafe code is never run. (Consequence: a write-`open()` kernel is now caught statically at 21, earlier than the old runtime-30 path; the e2e test was updated to assert the layered behavior.)

**Ledger.** `write_gate_ledger(result, diagnostics_dir, repo_root=...)` is called on BOTH pass and fail paths when `--diagnostics-dir` is set (best-effort, logged to stderr on failure, never masks the verdict). `golden_master.gate.json` is written and round-trips through `orchestrate.dossier.load_gate_ledger` (`read_errors == []`). It is a disk-only side artifact — stdout stays exactly one JSON object.

**Verification (run for real).** All 7 escape vectors blocked via the real `fs_confine` launcher subprocess (io.open write, os.open/os.write outside root, os.remove of an outside secret, pathlib.write_text, read of an outside secret, socket.socket, subprocess.run) — no file created/deleted outside root, secret intact, no network, no subprocess. G2 refusal proven (subprocess-importing kernel → exit 21, not executed). Legit match fixture → exit 0, ledger written + loadable. stdout = 1 JSON object.

**pytest:** `162 passed` (the prior wave's lone failure — `test_e2e_confinement_blocks_kernel_write` `assert 21 == 30`, explicitly handed off to this agent — is resolved: the test now asserts the layered G2 refusal at exit 21).

**Deviations:** none. Did not edit `qa/golden_master.py`, `qa/security.py`, `_common.py`, or other agents' files.

### [wave1d/skill] — Reusable gate-authoring skill distilled
- Distilled wave0/wave1/wave1b feedback into `.claude/skills/author-rechner-toolbox-gate/SKILL.md` (84 lines): mandatory `main()`+`run_command` skeleton, full `_common` import surface + semantics, the `default=None` mergeable-flag rule, the BOTH-paths `.gate.json` ledger contract, the 2/10/20/21/22/30/31/32/40/50 exit map + status mirroring, and the 7 hard gotchas (Path-manifest, info-dir-under-repo-root, fs_confine-not-a-sandbox, G2-before-execute, `_eq4`/G6, clean-stage, case-sensitive scalars).
- A fresh agent can now author a new gate (G3/G6/G7) first-try without re-reading this log.


---

### [wave2/conventions] — G3 architecture / import-convention gate authored
- Created exactly the three owned files: `src/rechner_pipeline/qa/conventions.py` (pure-AST engine), `src/rechner_pipeline/toolbox/conventions.py` (the `conventions` command), `tests/test_conventions.py`. No other `qa/*`, `toolbox/*`, `_common.py`, or `qa/__init__.py` touched. No git commit.
- Engine enforces the full §6.7 allowed import graph: `ALLOWED_IMPORTS` encodes the complete per-module edge set (`inputs`←stdlib only, `params`←`inputs`, `commutation`←`inputs,params`, `actuarial`←`inputs,params,commutation`, `test_run`←all four). Every generated-module edge not in the table is a `disallowed_edge`; the back-edge `commutation→actuarial` fails (and, being a real 2-cycle with `actuarial→commutation`, also surfaces `circular_import` — honest, not a bug). Cycle detection is a deterministic normalized-DFS over the built graph.
- Also enforced: `function_local_import` (depth-tracked imports inside def/async def/lambda), `try_except_importerror` (ImportError + ModuleNotFoundError handlers), `type_checking_trick` (`if TYPE_CHECKING:`), and conservative `unhashable_lru_cache` — unannotated args, mutable-typed args (`dict/list/set/...`), or any non-provably-hashable annotation FAIL; only immutable/`Tuple`/`Optional[hashable]` pass. Unknown hashability = failure, per spec.
- Flags: `--generated-dir`, `--allowlist <path>` (additive-only JSON merge — can widen but never weaken the §6.7 baseline), `--diagnostics-dir`, `--request-json -`; all mergeable flags `default=None`. JSON summary emits `import_graph`, per-edge `layer_edges`, `cache_audit`, `circular_imports`, plus `allowed_imports`/`rules`. Exit 22 = `Exit.CONVENTIONS` on any violation, 2 on usage, 0 clean.
- Verified for real against `.tmp/` fixtures: clean 6-file set → exit 0 (1 JSON line, ledger loadable, non-empty input_hashes); one fixture per rule (back-edge, cycle, function-local, try/except ImportError, TYPE_CHECKING, unhashable lru_cache) → each exit 22 with its specific category in the JSON. `conventions.gate.json` written on BOTH pass and fail paths and loadable via `orchestrate.dossier.load_gate_ledger` (`read_errors == []`). Full suite: **184 passed** (`.venv\Scripts\python.exe -m pytest tests/ -q`).
- Skill assessment: the SKILL.md let me author first-try. The `main()`/`run_command`/`_finalize` ledger skeleton, the `default=None` mergeable-flag rule, the exit/status contract, and `security.py` as the reference command were all sufficient — I followed `toolbox/security.py` + `qa/security.py` as the structural template and needed no extra guidance for the contract layer. The only thing not in the skill (and not expected to be) was the G3-specific rule semantics, which came entirely from MIGRATION.md §6.7. One self-inflicted test bug (asserted `actuarial` imports `inputs` when the clean fixture didn't) — caught immediately by the engine, not a contract gap.

### [wave2/roundtrip] — G7 XML/extraction/recomputation stability gate

- New engine `src/rechner_pipeline/qa/roundtrip.py` + command `src/rechner_pipeline/toolbox/roundtrip.py` + `tests/test_roundtrip.py` (27 tests). No other gates / `_common.py` / `models/schemas.py` touched. Read-only imports only: `qa.fs_confine`, `qa.security.scan_python_paths`, `adapters.excel.ExcelAdapter`.
- **Three blocking checks, exit 32 = `Exit.ROUNDTRIP`** (except a G2 violation in the executed kernel → exit 21, like golden_master):
  1. **`tafeln.xml` canonical fixed point.** Parse → serialize → re-parse must yield the SAME canonical semantic object AND the SAME SHA-256. Emitted as `tafeln_xml_canonical` output hash.
  2. **Re-extraction material-hash stability.** `ExcelAdapter.extract` is run TWICE into deterministic staging (`<generated-dir>/.roundtrip_reextract/run_{a,b}`, cleaned before+after) under `--repo-root`; MATERIAL artifact hashes (sheet/compressed CSVs, scalar JSONs, table CSVs, names_manager, vba txt — **manifest JSON excluded** because it embeds absolute paths) must match. Needs `--input <source-workbook>` (the manifest does NOT record the source path, so it is a required flag for check 2).
  3. **Recomputation stability.** `test_run.golden_master_outputs()` is run in N≥2 FRESH processes via `fs_confine.main(repo_root, child, info_dir)` (cwd=generated/, same pattern as golden_master); canonical output hash must be identical across runs.
- Flags: `--repo-root --generated-dir --info-dir --diagnostics-dir` (+ `--input`, `--request-json`); all mergeable `default=None`. Ledger `roundtrip.gate.json` written on BOTH paths, loadable by `orchestrate.dossier.load_gate_ledger`. stdout = exactly one JSON object.

**`tafeln.xml` canonical-form rules the e2e KLV kernel must satisfy (§6.7):**
- Root `<tafeln>`; each `<table name="...">` holds `<entry age="<int>" qx="<float>"/>` rows. Empty `<tafeln></tafeln>` is valid (zero tables).
- **Validation (hard fail):** duplicate age within a table (`duplicate_age`), `qx` outside `[0,1]` or non-finite/NaN/inf/non-numeric (`invalid_qx`), non-integer age (`invalid_age`), missing `name`/`age`/`qx` attribute, duplicate table name. Fabricated/placeholder/flat `qx` is forbidden — must be faithfully extracted data.
- **Canonical serialization** (so a valid file is a byte-level fixed point): tables sorted by name, entries ascending by age, fixed attribute order, fixed `%.12f`-then-strip float spelling, 2-space indent, LF newlines, single trailing newline, XML decl. Input order/whitespace/attr-order are normalized away — only validated numeric content defines identity.

**Determinism requirements the e2e KLV kernel must satisfy:**
- `golden_master_outputs()` must be a PURE deterministic function — identical canonical (`json.dumps(sort_keys=True)`) output across fresh processes. No wall-clock/`random`/`uuid`/env input (these are also G2 static failures), AND no hash-seed/iteration-order/float-accumulation drift (these pass G2 but are caught here as `nondeterministic`). Output must be JSON-serializable with a stable ordering.
- Extraction itself must be byte-stable run-to-run for all material artifacts (no embedded timestamps/random ordering in the generated CSVs/JSONs).

**Verified for real** against `.tmp/` KLV fixtures (`examples/Tarifrechner_KLV.xlsm`): stable canonical run → exit 0 (9 material artifacts compared, recompute stable across 2 processes, 1-line JSON); duplicate-age / qx>1 / non-finite-qx `tafeln.xml` → exit 32; G2-clean non-deterministic kernel (`hash('x')`) → exit 32 `nondeterministic`; `time`-import kernel → exit 21 `security_precondition`; usage (missing flags / info-dir outside repo-root / missing `--input`) → exit 2. Full suite: **211 passed** (`.venv\Scripts\python.exe -m pytest tests/ -q`).

- Skill assessment: SKILL.md was sufficient to author first-try — the `main()`/`run_command`/ledger skeleton, `default=None` mergeable-flag rule, exit/status contract, and `toolbox/golden_master.py` (the fs_confine child + marker-wrapped JSON envelope pattern) as the reference were directly reusable. Two judgment calls NOT spelled out in the skill: (a) `--input` is needed for check 2 because the manifest omits the source path — made it a required flag; (b) per the skill's "a gate that executes generated code must run G2 first" note, I added a `scan_python_paths` precheck to the recompute check (exit 21 on violation), so a `time`/`random` kernel is refused before execution rather than mislabeled as a hash mismatch. Note: a non-deterministic kernel for the drift test must be G2-CLEAN (hash-seed, not `time`/`random`) or G2 refuses it first.

### [wave2/algebraic] — G6 algebraic/property gate (Hypothesis) + the exact `qa_contract.json` shape Wave-4 KLV must declare

- New engine `src/rechner_pipeline/qa/algebraic.py` + command `src/rechner_pipeline/toolbox/algebraic.py` + `tests/test_algebraic.py` (25 tests) + `qa_contract.example.json` (a schema-valid TEMPLATE, NOT the real KLV contract). No other gates / `_common.py` / `models/schemas.py` touched. Read-only imports: `qa.fs_confine`, `qa.security.scan_python_paths`, `models.schemas.QaContract`.
- **Hypothesis `6.155.5`** (installed from public pypi). Recorded settings in the engine: `max_examples` from the contract (`property_engine.max_examples`, default 200), `deadline=None`, `database=None`, `suppress_health_check=[HealthCheck.too_slow]`, `@seed(0xA1B2C3D4)` so the gate is **rerunnable/deterministic** (a re-run reproduces the same cases + the same report hash). Domain = `st.integers(0, omega-1)` over integer ages (terminal-age check uses `st.just(omega)`).
- **Blocking, exit 31 = `Exit.ALGEBRAIC`** for: engine unavailable / version mismatch; unknown applicability (missing mapping / unsupported timing / unknown product / missing interest / missing omega / unknown tier / unresolvable mapping); any property counterexample. Usage/schema problems exit 2; a G2 static violation in the generated dir exits 21 (refuse to execute, same self-contained precondition as golden_master). **Unknown applicability is ALWAYS a hard fail, never a silent skip** (3.5 line 1761) — that is the whole point of G6, so `--strict` does not relax anything (it only ADDS a guard: a `*net_premium*` product that omits the `product_specific` tier exits 31 `strict_underdeclaration`).
- **Execution model (differs from golden_master/roundtrip on purpose).** The child is launched DIRECTLY (`sys.executable child repo_root qa_contract`), NOT via `fs_confine.main`, because importing Hypothesis transitively imports `unittest.mock` then `asyncio` then `ssl`, and `ssl` module-init introspects `socket.socket` — which `fs_confine` replaces with a guard, so importing Hypothesis AFTER `install()` raises a `TypeError` about a code-object argument. Fix: the child imports the TRUSTED engine (Hypothesis + `qa.algebraic`) FIRST, THEN calls `fs_confine.install(repo_root)` itself, THEN resolves mappings + runs the property tests. Net effect: all *generated-kernel* execution still runs confined (G4); only the reviewed test dependency is imported pre-patch. **If a future gate must run Hypothesis under confinement, reuse this "import engine then install then run" ordering.** The child also reconfigures stdout to UTF-8 (identity strings contain non-ascii math symbols), and the parent reads the child with `subprocess.run(..., encoding="utf-8", errors="replace")` so the cp1252 console cannot mojibake the payload.
- Flags: `--repo-root --generated-dir --info-dir --qa-contract --strict` (+ `--diagnostics-dir --request-json`); all mergeable `default=None` (`--strict` is `store_const const=True default=None`). Ledger `algebraic.gate.json` written on BOTH paths, loadable by `orchestrate.dossier.load_gate_ledger` (`read_errors == []`, gate `G6.algebraic-properties`, required). stdout = exactly one JSON object.

**EXACT `qa_contract.json` shape Wave-4 must author for the real KLV kernel** (validated by `models.schemas.QaContract`; see `qa_contract.example.json` for a full template). Required top-level keys: `schema_version` (must be `1`), `product_type` (non-empty str), `interest_basis` (non-empty obj), `timing_convention` (non-empty str), `function_mappings` (non-empty obj), `tiers_enabled` (non-empty array). Optional: `terminal_age_policy`, `tolerances`, `property_engine`.

- `interest_basis`: MUST contain `annual_effective_rate` (numeric, `> -1`). The engine derives `v = 1/(1+i)`, `d = i/(1+i)` itself; the `"v"`/`"d"` string fields in the example are documentation only and are not parsed.
- `timing_convention`: the universal PV tier is stated for **`"annuity_due"`** ONLY. Any other value while `present_value_identities` is enabled exits 31 `timing_unknown` (applying the wrong identity is worse than skipping it — risk note line 1861). If KLV is not annuity-due, the PV identities must be re-derived in the engine before that timing can be declared.
- `terminal_age_policy`: `omega` (int) is REQUIRED whenever any tier runs (it bounds the sampling/enumeration domain and the `Nx`/`Mx` closed-form sums). `q_omega` is optional; when present the engine asserts `qx(omega) == q_omega` (explicit terminal-age policy).
- `product_type`: to enable the `product_specific` tier the string MUST contain `net_premium` (e.g. `"endowment_net_premium"`); otherwise exits 31 `product_unknown`.
- `tiers_enabled` is a subset of `{mortality_invariants, commutation_identities, present_value_identities, product_specific}`. An unknown tier name exits 31 `unknown_tier`.
- `function_mappings`: each value is `"module.func"` resolved against the generated kernel (`commutation.*` / `actuarial.*`). **Required keys per enabled tier (absence exits 31 `missing_mapping`; an unresolvable target exits `mapping_unresolved`):**
  - `mortality_invariants`: `qx`, `lx` (optional `px` adds `p_x = 1 - q_x`).
  - `commutation_identities`: `lx`, `Dx`, `Nx` (optional `Cx`,`Mx` add `M_x = C_x + M_{x+1}`; optional `vpow` mapping `x -> v**x` adds `D_x = v^x*l_x`).
  - `present_value_identities`: `qx`, `Ax`, `aex`.
  - `product_specific`: `net_premium`, `pv_benefits`, `pv_premiums` (optional `benefit_scaled`,`premium_scaled` taking `(x, sum_insured)` add linear sum-insured scaling).
- `property_engine`: `{ "name": "hypothesis", "version": <pin>, "max_examples": <int> }`. `name` must be `"hypothesis"` (else exit 31 `engine_unknown`). A CONCRETE pinned `version` must equal the installed one (`6.155.5`) or exit 31 `engine_version_mismatch`; a placeholder (`"<...>"`) or empty string means "use the installed reviewed version" and the engine records the actual version in the result/ledger. Engine unimportable exits 31 `engine_unavailable` (NEVER downgrades to a hand-rolled random loop — 3.5 line 1765).

**Identities checked (16 in the full example contract, all 4 tiers):** `0<=qx<=1`, `p_x=1-q_x`, `l_x>=0 & finite`, `d_x=l_x-l_{x+1}>=0`, `l_{x+1}=l_x*(1-q_x)`, `qx(omega)==q_omega`; `N_x=D_x+N_{x+1}`, `N_x=sum_{k=x}^{omega}D_k`, `M_x=C_x+M_{x+1}`; `0<=A_x<=1`, `A_x+d*ae_x=1`, `ae_x=(1-A_x)/d`, `ae_x=1+v*p_x*ae_{x+1}`, `A_x=v*q_x+v*p_x*A_{x+1}`; `P=PV_benefits/PV_premium_annuity`, `PV(benefits)-P*PV(premiums)=0`.

**Verified for real** against synthetic `.tmp/` toy kernels (a self-consistent commutation+actuarial whole-life annuity-due net-premium kernel, omega=10): matching contract exit 0 (16 identities, 151 cases, 1-line JSON, ledger loadable); inflated-`aex` kernel exit 31 with concrete counterexample `A_0 + d*ae_0 = 1.0099 != 1 (example x=0)`; contract dropping `aex` for the PV tier exit 31 `missing_mapping`; `timing_convention="annuity_immediate"` exit 31 `timing_unknown`; injected `import socket` in generated dir exit 21 `precondition_failed`; missing flags exit 2. Full suite: **236 passed** (`.venv\Scripts\python.exe -m pytest tests/ -q`).

- Skill assessment: SKILL.md was sufficient to author the gate first-try — the `main()`/`run_command`/ledger skeleton, the `default=None` mergeable-flag rule, the exit/status contract, and `toolbox/golden_master.py` (the fs_confine child + marker-wrapped JSON envelope + G2-precondition pattern) as the reference were directly reusable. The ONE thing not covered by the skill and worth flagging to other authors: **Hypothesis cannot be imported after `fs_confine.install()`** (the ssl/socket module-init clash above) — so for an engine that pulls in `ssl`/`asyncio` you must import the trusted engine before installing confinement, rather than relying on the `fs_confine.main` launcher that golden_master/roundtrip use.

### [wave3/skill-body] — Canonical `build-vergleichsrechenkern` skill body (install-neutral §6.7)

- Created `.claude/skills/build-vergleichsrechenkern/SKILL.md` (213 lines) — the canonical install-neutral §6.7 instruction body as a Claude Agent Skill, plus `.claude/skills/build-vergleichsrechenkern/per-cli-notes.md` (40 lines) marking Claude as the VERIFIED target and Copilot/Codex/OpenCode as documented `VERIFY` stubs (§3.6). No `src/`, other skills, STATE.md, or MIGRATION.md touched. No git commit.
- Frontmatter `name: build-vergleichsrechenkern`; `description` carries the §3.2 trigger phrasing (`build-vergleichsrechenkern`, `build a Vergleichsrechenkern`, `Vergleichsrechenkern erstellen`, `Excel/VBA Tarifrechner nach Python migrieren`, `build a comparison kernel`, explicit six-file requests) + skip guidance (read/search, gate-authoring → author-rechner-toolbox-gate).
- Body contains all required rules: role/goal (senior actuarial dev, deterministic 1:1, no Excel); read-only `info_from_excel\` bundle sources (prefer `*_compressed.csv`, raw for provenance/expectations); the deterministic loop in REAL command order extract → read manifest → six files → validate → security → conventions → golden_master → algebraic → roundtrip → dossier with ONE shared `--diagnostics-dir`; exact six-file contract + order + `===FILE_START/END===` wrapper rule; complete MANDATORY import graph (only `actuarial.py → commutation.py`; no circular/function-local/`try-except ImportError`/`TYPE_CHECKING`); `lru_cache` hashability rule; no network/subprocess/exec/write-IO/random/time/env; mortality fail-fast with placeholder allowance RETIRED → `NotImplementedError`/`MissingMortalityTableError` + `human_review_required`; `golden_master_outputs() -> dict` with scalars+tables covering every scalar incl. derived rates and preserving order/case; `max_attempts` default 4 / cap 6, attempt-counting + attempt-free fail-fast errors; algebraic `qa_contract.json` note pointing to `qa_contract.example.json` + this file's `### [wave2/algebraic]`.
- **Placeholder grep:** no `{{...}}` template placeholders. The single regex hit is the literal Python dict example `{"scalars": {...}, "tables": {...}}` (the trailing `}}` closes nested dicts), not a template token.
- **Command cross-check (all verified via `--help`):** every cited `python -m rechner_pipeline.toolbox.X` exists — `extract` (`--repo-root --input --out-dir --adapter{auto,excel} --export-backend{openpyxl,com} --strict-manifest-warnings --diagnostics-dir`), `validate` (`--repo-root --generated-dir --info-dir --file-block-response --diagnostics-dir`), `security` (`--generated-dir --diagnostics-dir`), `conventions` (`--generated-dir --allowlist --diagnostics-dir`), `golden_master` (`--repo-root --generated-dir --info-dir --diagnostics-dir`), `algebraic` (`--repo-root --generated-dir --info-dir --qa-contract --strict --diagnostics-dir`), `roundtrip` (`--repo-root --generated-dir --info-dir --input --diagnostics-dir`), `dossier` (`--repo-root --generated-dir --info-dir --status --diagnostics-dir`). The skill's per-gate flag table matches these exactly. Note: `--adapter` only supports `{auto,excel}` today (word/other adapters are future), so the body cites `auto|excel` rather than inventing values.
- **For the Wave-4 e2e author (gaps the skill does not yet cover):**
  1. The skill states the gate ORDER and the `--diagnostics-dir`/`--info-dir`-under-`--repo-root` rules but does not prescribe concrete directory layout (where `<bundle>`, `<generated-dir>`, `<diagnostics-dir>` actually live for the real KLV run) — the e2e harness must pin those paths.
  2. The skill does not author the real KLV `qa_contract.json` (only points at the example template + schema); Wave-4 KLV must produce the real contract with the correct `omega`, `timing_convention`, and resolved `function_mappings` for the actual kernel.
  3. The skill says "re-run all required gates after any source change unless input_hash matches" but does not specify how the agent tracks/compares hashes across attempts — the e2e flow should make hash re-validation concrete.
  4. `roundtrip`'s check-2 needs `--input <original workbook>`; the e2e harness must keep the source path available after extraction so roundtrip can re-extract.
  5. G0/G4 are referenced by name (acceptance set G0–G8) but are not separate toolbox commands the agent invokes — confirm the e2e narrative does not imply a missing CLI step for them.

### [wave2/review] — G3 conventions PASS-WITH-FIXES · G6 algebraic PASS-WITH-FIXES · G7 roundtrip BLOCK
Brutally-critical review of conventions.py / algebraic.py / roundtrip.py (+ toolbox wrappers). Math, evasion, confinement, contract all tested with throwaway kernels.

**HIGH — G7 tafeln false-FAIL on >12-decimal qx (BLOCK).** `qa/roundtrip.py:338` checks `first != second or first_sha != second_sha`, where `first` is parsed from raw input and `second` from `serialize(first)`. `_canon_float` truncates qx to 12 decimals (`_QX_DECIMALS=105`), so any qx with >12 significant decimals makes `first != second` True while the SHAs are EQUAL. Result: `error_code="non_canonical"` with a self-contradictory message `sha X != X` (two identical hashes). Evidence: `qx="0.0123456789012345"` -> ok=False; `qx="0.011687"` (DAV 6-dec) -> ok=True. This blocks any faithfully-extracted higher-precision/select table and contradicts §6.7 line 2602 "serialized faithfully". FIX: compare the fixed point correctly — re-parse `second_bytes` into a `third` and compare `second==third`/`second_sha==third_sha` (i.e. assert serialize is idempotent), OR drop the object `!=` and rely on byte/SHA stability only; and raise `_QX_DECIMALS` or carry full precision so extraction is not silently truncated.

**MEDIUM — G7 crashes to exit 50 (no ledger) on corrupt/non-workbook --input.** `qa/roundtrip.py:447` only catches `ExcelAdapterError`/`RuntimeError`, but openpyxl raises `zipfile.BadZipFile` (subclass of `Exception` only) for a corrupt/non-xlsx source. It propagates unhandled -> `run_command` emits `internal_error` exit 50 and `main()`'s `write_gate_ledger` is bypassed (no roundtrip.gate.json). A malformed `--input` should be a clean exit 32 (or 10), not internal error. FIX: catch `Exception` (or at least `zipfile.BadZipFile`/`OSError`/`ValueError`) in `_extract_into` and map to `extraction_failed`.

**MEDIUM — G6 commutation tier never ties D_x to v^x·l_x; spec identity is dead code.** `qa/algebraic.py:691` only asserts `D_x = v^x·l_x` when a `vpow` mapping is declared, but `vpow` exists NOWHERE in the schema (`models/schemas.py`), the example contract, or §6.8.6. So the spec-mandated identity (§3.5 line 1757) is never exercised. The commutation tier only checks `N_x=D_x+N_{x+1}`, `N_x=ΣD_k`, `M_x=C_x+M_{x+1}` — all of which any *internally-consistent but wrong* Dx satisfies. Evidence: a kernel with `Dx = v^(x+1)·l_x` (off-by-one discount power) PASSES the commutation tier (OK=True, 0 counterexamples). FIX: tie Dx/Cx to the declared interest basis + lx directly inside the tier (the InterestBasis is available), not behind an undeclared `vpow`.

**MEDIUM — G3 forbidden edge via __import__/importlib invisible to AST scan.** `commutation.py` doing `__import__("actuarial")` or `importlib.import_module("actuarial")` produces ZERO conventions violations (the forbidden `commutation->actuarial` edge is absent from the graph). Mitigated only because G2-security flags `__import__`/`importlib` as `dangerous_call` — but G3 is specified as the standalone import-graph gate and the algebraic/roundtrip gates run G2 first while `conventions` does not. Static aliased (`import x as y`), `from a import b`, relative, and top-level conditional imports ARE all caught correctly. FIX/NOTE: document the G2->G3 dependency, or have G3 flag dynamic-import calls itself.

**LOW — G6 q_omega terminal check silently skipped when q_omega absent.** `_q_omega` returns None and the terminal-age identity is dropped; only `omega` is hard-required. §3.5 line 1756 wants an *explicit* terminal-age policy. Consider requiring q_omega (or recording it as an open assumption) rather than silently omitting the check.

**LOW — G3 lru_cache allows bare `tuple`/`Tuple`.** `Tuple`/`tuple` are in `_HASHABLE_ANNOTATIONS`, so `@lru_cache def f(t: Tuple)` passes even though a tuple containing a list is unhashable. Code comments acknowledge this; idiomatic but a theoretical false-negative.

**Verified GOOD (no defect):** correct whole-life annuity-due kernel PASSES all tiers (no false-fail); annuity-immediate-where-due, wrong-interest, and loaded-net-premium kernels are all CAUGHT; all fail-fast applicability paths return exit 31 (timing_unknown, product_unknown, missing_mapping, engine_unknown) — never silent skip; fs_confine BLOCKS writes from a kernel function Hypothesis calls even though Hypothesis is pre-imported (10/10 blocked, no escape file); G2 precondition (exit 21) fires before execution in algebraic AND roundtrip; ledgers written on pass+fail for conventions & algebraic; single-JSON-stdout holds; exit codes 22/31/32 correct; max_examples=200 exhaustively covers omega=121 integer ages.

**Wave-4 KLV-kernel / qa_contract author MUST know:**
- Keep every extracted `qx` at <=12 significant decimals OR the HIGH fix above must land first, else G7 false-fails. Do NOT hand-trim precision to dodge it — that violates "faithfully".
- The real qa_contract should add a `vpow` mapping (once the engine reads it) so `D_x=v^x·l_x` is actually checked; otherwise commutation correctness rests only on golden-master.
- Net-premium product tier only checks P-vs-(pvb/pvp) self-consistency; it does NOT validate pvb/pvp against mortality/interest. Don't treat a G6 pass as proof the PVs are actuarially right.

### [wave3/cli-assurance] — Source-neutral CLI + `assurance` gate orchestrator

Migrated `src/rechner_pipeline/cli.py` from the SDK stub to a **deterministic, SDK-free** CLI and added the `assurance` orchestrator (the Wave-4 e2e driver). The top-level surface advertises only source-neutral options (`--input`, `--adapter auto|excel`, `--export-backend openpyxl|com`, `--strict-manifest-warnings`); `--excel` is a backward-compatible alias for `--input`. No provider/model/token/reasoning/`test_mode=llm` surface remains. Console entry stays `rechner_pipeline.cli:main` (pyproject unchanged). No subcommand → exit 2 (usage).

**`assurance` runs the existing toolbox gates IN ORDER, sharing one `--diagnostics-dir`, via `_common.run_command(<gate>.main, argv)`** — it reuses each gate's `main()` (no second gate implementation, no gate logic in the CLI). Chain: `extract → validate → security → conventions → golden_master → algebraic → roundtrip → dossier`. Stop/continue policy: `extract`+`validate` are prerequisites (failure → skip QA gates but still run `dossier` for an honest blocked verdict); `security..roundtrip` are continue-on-fail; `algebraic` is skipped when no `--qa-contract` (G6 then reported missing by dossier); `dossier` always runs last and the aggregate exit code is the dossier verdict (else first blocking prerequisite). Per-gate argv builders adapt the shared inputs to each command's real flags (e.g. `extract --out-dir <info-dir>`, `security/conventions` take only `--generated-dir`/`--diagnostics-dir`, `roundtrip --input <wb>` for check 2).

**Exact `assurance` invocation for the Wave-4 e2e author** (drop in a real generated-dir + real `--qa-contract`):

```
.venv\Scripts\python.exe -m rechner_pipeline.cli assurance \
    --repo-root . \
    --input examples\Tarifrechner_KLV.xlsm \
    --generated-dir <gen> \
    --info-dir <info> \
    --diagnostics-dir <diag> \
    --qa-contract <generated\qa_contract.json> \
    --adapter excel
```

Notes for the e2e author:
- `--info-dir` is BOTH the extract `--out-dir` and the downstream gates' `--info-dir`; it MUST live under `--repo-root` or the confined golden-master/roundtrip children can't read expectations (exit 30, `confinement_failure`). The KLV example resolves under repo root already.
- Supply `--qa-contract` or `algebraic` (G6) is skipped and dossier blocks on `gate.missing` for G6 — acceptable for a chain demo, NOT for real acceptance.
- A non-`full` expectation coverage (or any required gate not passed) makes dossier emit `human_review_required` (exit 40). With the real kernel + full coverage + all gates passing, dossier returns 0 (accepted).
- Verified real run over a SYNTHETIC six-file generated-dir + real KLV extraction: chain executed end-to-end, `extract/validate/security/conventions/roundtrip` passed, `golden_master` failed 30 (no real kernel — expected/honest), `dossier` → `human_review_required` exit 40, aggregate exit 40. `run_dossier.json` + `qa_report.json` written.

**SDK/LangGraph absence (§4.2 steps 9, 10).** `grep -rEi "anthropic|openai|OPENAI_API_KEY|ANTHROPIC_API_KEY|langgraph|StateGraph|rechner-pipeline-agentic" src pyproject.toml requirements.txt requirements-dev.txt` → **no matches** (exit 1). Confirmed in the target execution path; also asserted by `tests/test_cli.py::test_src_carries_no_sdk_or_langgraph` and `::test_pyproject_and_requirements_carry_no_sdk`.

Tests: added `tests/test_cli.py` (7 tests — help source-neutrality + no-SDK, `--excel` alias, no-subcommand→2, `assurance --help` chain doc, SDK-absence over `src`/pyproject/requirements, full assurance chain ending in dossier verdict). Full suite: **243 passed**. Owned files only: `src/rechner_pipeline/cli.py`, `tests/test_cli.py`, `README.md`.

### [wave2b/roundtrip-fix] — tafeln high-precision canonical check + corrupt-input clean exit

Owned files only: `src/rechner_pipeline/qa/roundtrip.py`, `src/rechner_pipeline/toolbox/roundtrip.py`, `tests/test_roundtrip.py`. No commit.

**Fix 1 (HIGH) — canonical-check redesign.** Root cause: `check_tafeln_canonical` declared `non_canonical` on `first != second` (parsed float-object identity). `_canon_float` truncated qx to 12 decimals, so `first` kept full binary-float precision while the re-parse (`second`) saw the truncated decimal — the objects differed even though BOTH serializations produced byte-identical XML / equal SHA-256 (the reported `sha c74a8e… != c74a8e…` with equal hashes). Redesign:
- The failure test is now `first_bytes != second_bytes` (serialization idempotence = `serialize(parse(serialize(x))) == serialize(x)`). The canonical SHA is the gate's source of truth; byte-equal serializations ARE canonical. Object identity is no longer consulted.
- `_canon_float` now uses Python's shortest-round-tripping `repr(float)` (exact: `float(_canon_float(x)) == x` for every finite x), removing the 12-decimal truncation so faithfully-extracted high-precision DAV tables (§6.7 line 2602) are serialized losslessly and parse→serialize is a TRUE fixpoint at full precision. Scientific notation is defensively expanded via `Decimal` (never reached for qx∈[0,1]).
- §6.7 validation (duplicate age, qx∉[0,1], non-finite, bad age) is untouched and still hard-fails in `parse_tafeln`.

**Fix 2 (MEDIUM) — corrupt `--input` no longer crashes to exit 50.** Root cause: `_extract_into` caught only `ExcelAdapterError`/`RuntimeError`; openpyxl raises `zipfile.BadZipFile` (an `Exception`, not `RuntimeError`) for a corrupt/non-zip workbook → unhandled → exit 50, ledger skipped. Fix:
- Added a broad `except Exception` in `_extract_into` returning a clean `ReextractionResult(error_code="extraction_failed", ...)`.
- Command maps `reextract.error_code in {extraction_failed, dependency_unavailable}` to **exit 10 (`Exit.EXTRACTION`)** — chosen over 32 because a workbook that cannot be opened at all is an extraction/input failure, not an actuarial hash-stability mismatch. Ledger is written on this fail path (unchanged `main()` ledger wiring runs on every path).

**Regression evidence (run for real):**
- Engine: `0.0123456789012345` (16 sig decimals) → `check_tafeln_canonical` ok=true, full precision carried; `_canon_float` exact round-trip verified for several values; genuinely invalid tables (duplicate_age, invalid_qx) still fail.
- CLI end-to-end on a corrupt non-zip `--input`: **exit 10**, `errors=[{code: extraction_failed, message: "BadZipFile: File is not a zip file"}]`, **empty stderr (no traceback)**, stdout = exactly one JSON object, `roundtrip.gate.json` written and loadable via `orchestrate.dossier.load_gate_ledger` (read_errors=[], entry status=failed).

**Test count:** `pytest tests/test_roundtrip.py -q` → **31 passed** (was 27; +4: `test_high_precision_qx_is_canonical`, `test_high_precision_qx_serialization_is_exact_fixpoint`, `test_genuinely_non_canonical_still_fails`, `test_e2e_corrupt_input_clean_exit_with_ledger`). Previously-passing cases still green.

**Deviations:** none from the brief. Removed the now-unused `_QX_DECIMALS` constant (it only fed the truncating `_canon_float`). No other gates/_common/models/skills touched.

### [wave2b/algebraic-fix] — D_x=v^x·l_x now live (false-coverage closed) + explicit terminal-age policy

Owned files only: `src/rechner_pipeline/qa/algebraic.py`, `tests/test_algebraic.py`, `qa_contract.example.json`. No commit. No other gates/_common/models/skills touched.

**Fix 1 (MEDIUM, FALSE COVERAGE) — `D_x = v^x·l_x` was dead code, now checked directly.** Root cause: the commutation tier gated the `D_x=v^x·l_x` identity behind `if kernel.has("vpow")`, but `vpow` exists in NO schema/example/spec → the branch never ran. The tier asserted only the internal recursion/sum identities (`N_x=D_x+N_{x+1}`, `N_x=ΣD_k`), which hold for ANY internally-consistent (even wrong) Dx — so an off-by-one `D_x=v^(x+1)·l_x` kernel PASSED. Redesign:
- Removed the `vpow`-gated dead block entirely. `_check_commutation` now derives `v=1/(1+i)` from `interest_basis.annual_effective_rate` (via the existing `InterestBasis.from_contract`) and asserts `D_x == v^(x-base)·l_x` directly, using the already-required `Dx` and `lx` mappings. No `vpow` mapping is required or referenced anywhere.
- `run_checks` now passes `interest_basis_raw` into `_check_commutation` (the commutation tier genuinely needs the interest basis; it is already required for the PV tier and the contract always declares it).
- **Exponent convention (documented in code):** standard actuarial `D_x = v^x · l_x` with `x` = attained age, i.e. discount exponent = age (base age 0). New helper `_commutation_base_age` reads an OPTIONAL `interest_basis.commutation_base_age` (entry age the table was tabulated from); when declared, exponent = `x - base` → `D_x = v^(x-base)·l_x`. DEFAULT (no declaration) = base 0 = exponent x, and that default identity is now LIVE and checked.

**Fix 2 (LOW) — explicit terminal-age policy required (no silent skip).** Root cause: `q(omega)==q_omega` was skipped when `q_omega` was absent. Now `_q_omega` REQUIRES an explicit policy when the mortality tier runs. Accepted declarations:
- `terminal_age_policy.q_omega` = numeric terminal value, OR
- `terminal_age_policy.mode` = `"q_omega_is_one"` (closes table with certain death, q_omega=1.0) or `"explicit"` (then a `q_omega` value is also required).
- Missing/unknown policy with mortality tier enabled → `ApplicabilityError("terminal_age_unknown")` → exit 31. Resolution is gated on `TIER_MORTALITY in tiers`, so a commutation/PV-only contract is NOT forced to declare a q-policy. `omega` remains unconditionally required (sampling domain).

**Regression evidence (run for real, end-to-end via the CLI):**
- Correct toy kernel, commutation tier → **exit 0**; `identities_checked` = `['D_x = v^x · l_x', 'N_x = D_x + N_{x+1}', 'N_x = Σ_{k=x}^{omega} D_k', 'M_x = C_x + M_{x+1}']` (the Dx definition is now counted, proving it is live). `algebraic.gate.json` written + loadable (`load_gate_ledger`: 1 entry, gate `G6.algebraic-properties`, status passed). stdout = exactly one JSON object.
- Off-by-one `D_x=v^(x+1)·l_x` (Nx kept internally consistent), commutation tier → **exit 31**, 1 counterexample on `D_x = v^x · l_x`: `D_0=97560.98 != v^(0-0)·l_0=100000.0 (v=0.97560…)`, concrete falsifying `example={'x': 0}`. The recursion/sum identities alone did NOT catch it (test `test_commutation_internal_identities_alone_do_not_catch_off_by_one`), confirming the hole was real.
- Mortality tier + no terminal policy (`terminal_age_policy={"omega":6}`) → **exit 31**, `errors=[{code: terminal_age_unknown}]`.

**Updated `qa_contract.example.json`:** `terminal_age_policy` now declares the explicit policy:
```json
"terminal_age_policy": { "omega": 121, "mode": "q_omega_is_one", "q_omega": 1.0 }
```

**FINAL qa_contract schema (for Wave-4 KLV author).** Unchanged top-level keys plus the now-mandatory explicit terminal policy and the optional commutation base:
```json
{
  "schema_version": 1,
  "product_type": "endowment_net_premium",
  "interest_basis": { "annual_effective_rate": 0.025, "commutation_base_age": 0 },
  "timing_convention": "annuity_due",
  "terminal_age_policy": { "omega": 121, "mode": "q_omega_is_one", "q_omega": 1.0 },
  "function_mappings": { "qx": "...", "px": "...", "lx": "...", "Dx": "...", "Nx": "...", "Cx": "...", "Mx": "...", "Ax": "...", "aex": "...", "net_premium": "...", "pv_benefits": "...", "pv_premiums": "..." },
  "tiers_enabled": ["mortality_invariants", "commutation_identities", "present_value_identities", "product_specific"],
  "tolerances": { "rel_tol": 1e-9, "abs_tol": 1e-12 },
  "property_engine": { "name": "hypothesis", "version": "<pinned>", "max_examples": 200 }
}
```
Schema notes for KLV: (a) `terminal_age_policy` MUST declare `q_omega` OR `mode` whenever `mortality_invariants` is enabled — absence = exit 31. `mode: "q_omega_is_one"` is the standard close-the-table choice and needs no separate value. (b) `interest_basis.commutation_base_age` is OPTIONAL (default 0 = `D_x=v^x·l_x` with x=attained age); set it only if the table tabulates Dx from a non-zero entry age. (c) `interest_basis.annual_effective_rate` is now consumed by BOTH the commutation and PV tiers. (d) `vpow` is NOT a mapping — do not declare it.

**Test count:** `pytest tests/test_algebraic.py -q` → **36 passed** (was 26; +10: `test_commutation_dx_definition_is_checked_and_passes`, `test_commutation_off_by_one_dx_now_fails`, `test_commutation_internal_identities_alone_do_not_catch_off_by_one`, `test_commutation_base_age_override`, `test_missing_terminal_policy_fails_when_mortality_runs`, `test_terminal_policy_not_required_without_mortality_tier`, `test_terminal_policy_mode_q_omega_is_one`, `test_terminal_policy_mode_explicit_requires_value`, `test_terminal_policy_unknown_mode_fails`, plus end-to-end `test_cmd_off_by_one_dx_exit_31`, `test_cmd_missing_terminal_policy_exit_31`). All previously-passing cases still green.

**Deviations:** none from the brief. `commutation_base_age` added as the documented optional override the brief invited ("if the contract declares a different commutation base, honor it"); the default identity is live regardless.

### [wave2b/conventions-fix] — G3 dynamic-import detection + conservative tuple lru_cache hashability

**Scope:** Owned `src/rechner_pipeline/qa/conventions.py` + `tests/test_conventions.py` only. No other gates/_common/models/skills touched. No git commit.

**Fix 1 (MEDIUM) — new `dynamic_import` rule.** Dynamic imports were invisible to the AST graph scan, so a forbidden edge (e.g. `commutation→actuarial`) hidden via `__import__("actuarial")` / `importlib.import_module(...)` produced ZERO violations. `conventions` runs standalone (G2 catches dynamic import in the full chain, but G3 must not depend on that). Added a blocking `dynamic_import` category (exit 22) that flags, regardless of argument:
- `__import__(...)` and `importlib.__import__(...)` — final-component call match `__import__`.
- `importlib.import_module(...)` and a re-bound `import_module(...)` (`from importlib import import_module`) — final-component call match `import_module`. (new `visit_Call`)
- `import importlib` / `import importlib.<sub>` (root-module match in `visit_Import`).
- `from importlib import ...` / `from importlib.<sub> import ...` (root-module match in `visit_ImportFrom`).
Generated kernel code has no legitimate dynamic-import need, so any such construct fails. (Toolbox wrapper needed no edit: it surfaces unknown categories via `v.category`/message and skips missing repair hints gracefully.)

**Fix 2 (LOW) — conservative `lru_cache` tuple hashability.** Previously `tuple`/`Tuple` sat unconditionally in `_HASHABLE_ANNOTATIONS`, so a *bare* untyped `tuple` (UNKNOWN element hashability) wrongly PASSED. Removed `tuple`/`Tuple` from the hashable set and made `_is_provably_hashable_annotation` recurse *structurally*: a parameterized tuple is hashable iff every declared (non-`...`) element type is provably hashable; a bare tuple has no declared elements → UNKNOWN → FAIL. Union/Optional/PEP-604/forward-refs recurse per member.

Pass/fail matrix (verified live against the engine):

| annotation | verdict |
|---|---|
| bare `tuple` | FAIL |
| bare `Tuple` | FAIL |
| `Tuple[int, ...]` | PASS |
| `tuple[str, ...]` | PASS |
| `Tuple[int, str]` | PASS |
| `Tuple[list, ...]` | FAIL |
| `Tuple[ModelPoint, ...]` | FAIL |
| `Optional[Tuple[int, ...]]` | PASS |
| `int` | PASS |

**No false-positive confirmed:** legit typed-hashable-tuple caches (`Tuple[int, ...]`, `tuple[str, ...]`, `Tuple[int, str]`, `Optional[Tuple[int, ...]]`) all PASS; the pre-existing `Optional[str]`/`int` clean-cache case still passes.

**Regression evidence:**
- `__import__("...")` / `importlib.import_module(...)` / `import importlib` / `from importlib import import_module` / `importlib.__import__(...)` → exit 22 `dynamic_import`.
- bare `tuple` and bare `Tuple` lru_cache arg → exit 22 `unhashable_lru_cache`; `Tuple[int, ...]` → passes; `Tuple[list, ...]` → exit 22.
- All 6 original violation fixtures (disallowed_edge, circular_import, function_local_import, try_except_importerror, type_checking_trick, unhashable_lru_cache) + the clean-pass case still green.
- Command contract intact: clean run exit 0 / `status=passed`; `conventions.gate.json` + `conventions_report.json` written and loadable; stdout = exactly one JSON object; mutation run exit 22 with the expected category.

**Test count:** `pytest tests/test_conventions.py -q` → **35 passed** (was 22; +13: 6 tuple-hashability + 5 dynamic-import engine fixtures, plus 2 new command-contract parametrize rows `dynimport`/`baretuple`).

**Deviations:** none. `dynamic_import` has no entry in the toolbox `_REPAIR_HINTS` map (that file is out of scope); the violation still surfaces with its full message — acceptable and non-breaking.

### [wave3d/skill-complete] — `build-vergleichsrechenkern` SKILL.md made operationally complete (246 lines): folded in the one-command `cli assurance` driver (+ `--qa-contract` required for real acceptance), the pinned `info_from_excel/` (under repo-root) `generated/` `diagnostics/` layout, the FINAL KLV qa_contract schema (explicit terminal policy, optional `commutation_base_age`, no `vpow`) from wave2b, and a gotchas checklist (no time/random/env/net/subprocess/dynamic-import/write-IO; only `actuarial→commutation`; bare-tuple lru_cache fails G3; scalar keys byte-match; faithful `tafeln.xml` else `NotImplementedError`; deterministic). Owned only this skill file. Remaining Wave-4 gap: the agent still authors the REAL `function_mappings`/`omega`/`timing` for the actual KLV kernel, and the example uses `examples\Tarifrechner_KLV.xlsm` as the source path — confirm that workbook exists before the run. No git commit.

### [wave4/klv-e2e] — KLV Vergleichsrechenkern generated 1:1; all 7 gates PASS but dossier blocks on a structural extract-gate provenance defect (human_review_required)

**Result:** The six-file kernel is correct and every required gate (G0–G8) reports `passed`. The `qa_report.json` computes `decision: accepted, accepted: true, expectation_coverage: full, open_assumptions: [], blocking_warnings: []`. Despite that, `dossier` exits **40** on a SINGLE residual blocker that nothing I own can clear.

**KLV actuarial facts derived (from the bundle, not guessed):**
- Interest (Rechnungszins) `Zins = 0.0175` (cell E4) — the commutation/PV rate. `ratzu` (5% for zw=12) is an instalment *surcharge*, NOT interest.
- Mortality: `DAV1994_T_M` (model point Sex=M, Tafel=DAV1994_T). VBA `Act_qx` recognizes only `DAV1994_T`,`DAV2008_T`; all four sex/table vectors (ages 0..123) serialized faithfully to `tafeln.xml`.
- Terminal age: the DAV1994_T_M table hits `qx=1.0 at age 100` (lx=0, all commutation 0 from 101). True **omega = 100**, NOT the table's padded length 123. Setting omega=123 makes the G6 PV/product tiers divide by Dx=0 (ZeroDivisionError, not AssertionError → would crash the gate). omega=100 keeps every sampled age in the live domain.
- lx radix 1e6; all commutation rounded to 16 decimals (mConstants `rund_*=16`) via Excel round-half-away-from-zero.
- Scalars: `Bxt`=gross premium rate (K5), `BJB`=VS·Bxt (K6), `BZB`=(1+ratzu)/zw·(BJB+k) instalment (K7), `Pxt`=net premium rate (K9), `ratzu`=instalment surcharge (E12). All 5 reproduce to ~13 sig-figs; 612 table cells (Verlaufswerte B16:L66) reproduce 1:1.
- `function_mappings`: qx/lx/Dx/Nx/Cx/Mx → single-arg pinned adapters `commutation.{qx,lx,Dx,Nx,Cx,Mx}_at` (the gate calls each mapping with one int age; the faithful multi-arg migrations stay as `commutation.{qx,Dx,...}`). Ax→`actuarial.Ax`, aex→`actuarial.aex`, net_premium/pv_benefits/pv_premiums→`actuarial.*`. G6 ran 1501 cases across all 4 tiers, 0 counterexamples.

**Repair attempts used: 1** (initial generation + 1 repair).
- Attempt 1 (initial): G0–G6 PASS; G7 roundtrip FAILED — `tafeln.xml` used `<table id=...>`/`<q age>text</q>`, but the G7 canonical parser requires `<table name=...>` with `<entry age=".." qx=".."/>`.
- Repair 1: regenerated `tafeln.xml` via the gate's OWN `serialize_tafeln` (guaranteed byte-level parse→serialize fixpoint) and switched `commutation._load_tables` to the `name`/`entry`/`qx` schema. G7 then PASSED. All G0–G8 gates pass.

**The one irreducible blocker (out of my editable scope — `src/` is off-limits):**
`dossier.evaluate_blockers` raises `hashes.missing` for **every** required gate whose ledger `input_hashes` is empty — including **G0 (extract)**. But `toolbox/extract.py` NEVER assigns `input_hashes` (grep-confirmed: it records source/output only in `output_hashes`). So the extract gate's `extract.gate.json` always has `input_hashes: {}`, and `evaluate_blockers` unconditionally blocks G0. **No change to the six generated files or `qa_contract.json` can populate the extract gate's input_hashes.** Result: `assurance` can never reach exit-0 acceptance for ANY workbook through this toolbox, regardless of kernel quality. The honest fix is a one-line change in `extract.py` (record the source-doc hash under `input_hashes`) or an evaluate_blockers exemption for G0 — both in `src/`, which I was instructed not to touch. I did NOT hand-edit `diagnostics/extract.gate.json` to inject a fake hash; fabricating provenance to pass a gate is exactly what the skill forbids.

**Two further `assurance`-driver gaps I worked around (within my scope):**
1. `cli._argv_validate` omits `--diagnostics-dir`, so G1's ledger lands in `generated/diagnostics/validate.gate.json` (default) instead of the shared dir → dossier reports G1 `gate.missing`. Worked around by running `validate` standalone with `--diagnostics-dir diagnostics`.
2. `assurance` never feeds `expectation_coverage` to `dossier`; the dossier defaults to `none` → `coverage.not_full` open assumption. The extract step writes `export_manifest.json`, but the dossier looks for `input_bundle.json`/`dossier_input.json`. Worked around by writing `info_from_excel/input_bundle.json` (`expectation_coverage: full` + coverage_detail mirrored from the extract manifest). This is the dossier's sanctioned read-only aux channel, not a bundle-artifact mutation.
   Side effect: the dossier writes `qa_report.json`/`run_dossier.json` INTO `generated/`, which then makes the NEXT `validate` run fail G1 with `invalid_file_set` (7th/8th file). Must delete those + `generated/{diagnostics,__pycache__,.roundtrip_reextract}` before each re-run.

**Surprising gate behavior on real generated code:** G5 golden_master compares with `round(x,4)==round(x,4)` (4-decimal absolute), so 16-digit float noise and ~1e-12 near-zeros pass trivially — but a real relative-drift bug at the 5th decimal would also slip through (G6 is the actual numerical-rigor gate). G6's `_eq4`-free `math.isclose(rel_tol=1e-9)` is the binding check and is sound. The expected `scalars`/`tables` are keyed by file-stem PREFIX (`Kalkulation`), and `tables[prefix]` must be a LIST OF ROW-DICTS (not columns) — the example contract doesn't show this shape; I had to read `golden_master.py` to get it right.

**Bottom line:** `resolution_mode = partial`. Kernel + contract are production-correct and mechanically validated by 7/7 gates; acceptance is blocked solely by a `src/`-level toolbox provenance defect (extract gate emits no `input_hashes`). Stopping at `human_review_required` per the skill rather than fabricating a hash. No git commit.

### [wave4b/assurance-wiring] — RESOLVED: true exit 0, dossier `accepted` (7/7 gates, coverage full, 0 assumptions)

All four toolbox WIRING bugs fixed; the already-generated/already-verified KLV kernel now reaches a TRUE mechanical acceptance with NO manual workarounds. `assurance` exits **0**, dossier `decision: accepted` / `accepted: true`. Idempotent (clean on the 2nd run). pytest: **271 passed**. `generated/` holds exactly the six files afterward (the only sibling is `__pycache__/`, a directory — validate ignores non-files).

**Bug 1 — `extract` never set `input_hashes` (G0 ledger empty → dossier `hashes.missing`).**
Fix (`toolbox/extract.py`): hash the genuine extraction input (the source workbook) via `hash_files([source], base=repo_root)` (repo-relative key `examples\Tarifrechner_KLV.xlsm`) and pass it as the result's `input_hashes`. Verified all 7 required gates now carry non-empty `input_hashes` (the other six already hashed generated/info files).

**Bug 2 — `dossier` wrote `qa_report.json`/`run_dossier.json` into `--generated-dir` (broke the next G1 validate as a 7th/8th file).**
Fix (`toolbox/dossier.py`): write both artifacts into `--diagnostics-dir` instead (`diagnostics_dir / QA_REPORT_NAME`, `… / RUN_DOSSIER_NAME`); updated docstring/comments and the `qa_contract_path` provenance default to repo-root. `orchestrate/dossier.py` needed no change (it is pure aggregation; the toolbox command owns I/O).

**Bug 3 — `assurance` did not pass `--diagnostics-dir` to `validate` (G1 ledger landed in `<generated>/diagnostics` → dossier reported G1 `gate.missing` + polluted generated/).**
Fix (`cli.py` `_argv_validate`): added `--diagnostics-dir c.diagnostics_dir`. Confirmed every gate in the chain (extract, validate, security, conventions, golden_master, algebraic, roundtrip, dossier) now receives the shared diagnostics dir; `validate.gate.json` lands in the shared dir and no `generated/diagnostics` appears.

**Bug 4 — coverage not conveyed to dossier (defaulted `none` → false `coverage.not_full` open assumption).**
Fix (spec-aligned, automatic, no manual file): `extract` now PERSISTS the InputBundle coverage block (incl. `expectation_coverage`) as `info_from_excel/input_bundle.json` (`out_dir/input_bundle.json`). The dossier already reads `info_dir/input_bundle.json` first, so coverage is picked up automatically (`full`). It is written to the INFO dir (extract's `--out-dir`), never `--generated-dir`, and is not a gate input, so it pollutes nothing and breaks no gate.

**SKILL.md corrections (`build-vergleichsrechenkern/SKILL.md`):** the dir-layout table now states `generated/` holds EXACTLY the six files and that `qa_contract.json` lives at repo root (added its own row) and that `dossier` writes `qa_report.json`/`run_dossier.json` into `diagnostics/` (never `generated/`); the example `assurance` command and the G6 contract instructions were changed from `generated\qa_contract.json` / "copy it into `generated/qa_contract.json`" to repo-root `qa_contract.json`.

**Tests updated (still 271 passed):** `test_extract.py` asserts non-empty repo-relative `input_hashes` (source workbook) + persisted `input_bundle.json` with `expectation_coverage: full`; `test_dossier.py` reads acceptance artifacts from `--diagnostics-dir` and asserts they do NOT appear in `generated/`; `test_cli.py` asserts artifacts/`validate.gate.json` in diag (none in generated/, no `generated/diagnostics`), and — because the synthetic kernel now extracts at FULL coverage — the blocked verdict is an honest `failed` (`gate.not_passed`, golden master cannot match the fake kernel) rather than a coverage `human_review_required`.

**Final clean `assurance` verdict (G8):** `decision: accepted`, `accepted: true`, `expectation_coverage: full`, `open_assumptions: []`, `blocking_warnings: []`; gates G0,G1,G2,G3,G5,G6,G7 all `passed`; aggregate exit 0. Second consecutive run also `accepted`/exit 0 with no pollution (idempotent).

**Deviations:** none — no manual ledger/hash injection, no faking, no git commit. Pre-existing pollution from the buggy run (`generated/{conventions.gate.json,conventions_report.json,diagnostics/,qa_contract.json}`) was removed before the verification run, per the task's "clean any prior dossier pollution first" instruction.

---

### [wave5/final-review] — MIGRATION COMPLETE & SOUND (acceptance is REAL, not hollow)

`resolution_mode: fully_resolved`. Re-ran the full suite end-to-end (`assurance` exit 0, dossier `accepted`, coverage `full`, 0 open assumptions) and 271/271 tests green, then ran adversarial break-tests in throwaway `.verify/` (cleaned up, no files modified).

**Part A — the green is REAL (no overfit, faithful to source):**
- **Not hardcoded.** `golden_master_outputs()` calls the actuarial functions (no literal expected numbers). Perturbing a *generated* constant (`ALPHA 0.025→0.026`) in an isolated copy produced **100 deviations** vs the unchanged expected values → outputs are COMPUTED from formulas, not echoed. The 612 table cells flow through the commutation/PV functions.
- **Golden-master really compares.** Perturbing an *expected* value (`Bxt +0.01`) → exit 30, 1 deviation. Computed-vs-expected agreement is ~1e-10 (far tighter than the 4-decimal gate), consistent with genuine recomputation, not value-fitting.
- **Faithful to Excel/VBA.** `commutation.py` is a 1:1 port of VBA `mGWerte` (lx/tx/Dx/Cx recurrences, Nx/Mx/Rx backward sums, radix 1e6, `WorksheetFunction.Round`→`ROUND_HALF_UP` at 16 dp, `max_Alter=123`). `actuarial.py` matches `mBarwerte` (`axn_k`, `ax_k`, `nGrAx`, `nGrEx`, `Abzugsglied`) and the sheet formulas K5/K6/K7/K9 + Verlaufswerte B16:L66 byte-for-byte against `Kalkulation_compressed.csv`. Spot-checked Bxt and Pxt end-to-end.
- **Contract honest, gate exercises real functions.** `qa_contract.json` `function_mappings` resolve via `qa.algebraic.resolve_mappings` (real `getattr` on generated modules); a bogus mapping → exit 31 `mapping_unresolved`. 1501 Hypothesis cases over 16 identities passed.
- **omega=100 hides nothing.** The DAV table itself sets `qx(100)=1.0` and `Dx=0` for ages 101–123; the KLV product only reaches age 75 (x=45,n=30). The contract's terminal policy matches the table fact; it is not a fudge.

**Part B — §4.2 checklist completeness:**

| # | Step | Done? | Evidence |
|---|---|---|---|
| 1 | Freeze KLV baseline | ✅ | golden hashes/manifest captured; STATE.md baseline |
| 2 | Lock Excel artifact contract | ✅ | re-extract byte-identical on all 8 artifacts (sha256 match) |
| 3 | Clean/staged extraction | ✅ | `extract.py` `_STALE_DERIVED_SUFFIXES`; `cleaned_stale_derived` in output |
| 4 | Toolbox command surface | ✅ | extract/validate/golden_master + 5 more; JSON stdout, blocking exits |
| 5 | Six-file validator migrated | ✅ | `generate.output`→`toolbox.validate`; G1 passed; order/compile/schema checks |
| 6 | Fix golden-master false-accept | ✅ | unmatched col→30, zero-comparison→31; 18 fixtures pass |
| 7 | Extend QA gates | ✅ | security/conventions/algebraic/roundtrip all present & passing |
| 8 | Prompt rules → instructions | ✅ | SKILL.md, no `{{…}}` placeholders, six-file/golden/fail-fast rules present |
| 9 | Remove SDK generation | ✅ | grep: anthropic/openai/OPENAI/ANTHROPIC/`generate.client` ABSENT |
| 10 | Remove LangGraph | ✅ | grep: langgraph/StateGraph/`agentic_pipeline` ABSENT |
| 11 | Source-neutral CLI | ✅ | `--input`/`--adapter`; `--excel` alias; no provider/model/token surface |
| 12 | Input-adapter seam | ✅ | `adapters/{base,excel}.py`; sparse-coverage→human_review test |
| 13 | Upgrade dossier | ✅ | gate versions/hashes/options/coverage; missing-gate & export_backend tests block |
| 14 | Optional stdio MCP | ✅ (absent) | no MCP wrapper, no HTTP/SSE listener — acceptable per §4.1/§5.3 |
| 15 | Final e2e acceptance | ✅ | `assurance` exit 0, dossier accepted, 271 tests green |

**§4.1 disposition:** all REMOVE targets confirmed absent (greenfield); `generate/` correctly retained only as the MIGRATE'd `output.py` validator; `test_mode`/`provider` appear ONLY as recorded provenance option-keys/comments, not SDK paths. I/O contract (§1) honored: 8 artifacts byte-identical, six files + order intact, `golden_master_outputs()` contract preserved, 4-decimal golden-master preserved. Non-goals respected (no HTTP/SSE MCP).

**Overall verdict: MIGRATION COMPLETE & SOUND.** No Critical/High findings. Minor (non-blocking) observation: the algebraic gate's `Ax/aex` whole-life single-arg interface is a *separate* probe basis from the KLV endowment product formula (Bxt/Pxt use term-assurance + pure-endowment); the identities it checks are real but do not independently re-derive the product's Bxt/Pxt — that cross-check is covered by golden-master + the algebraic `P = PV_benefits/PV_premiums` tier. Acceptance is genuine.

### [wave6/onboarding] — ONBOARDING.md authored (operator handoff, ~96 lines): what-it-is, setup, assurance run + build skill, G0–G8 table, layout, extend (gate/adapter/acceptance), gotchas, status (271 tests, KLV accepted).
