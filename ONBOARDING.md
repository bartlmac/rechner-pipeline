# ONBOARDING — agentic-rechner-pipeline

## 1. What this is
A **CLI-agnostic, full-agentic** pipeline that migrates an Excel/VBA *Tarifrechner* 1:1 into a
six-file pure-Python *Vergleichsrechenkern*, then proves it with a **deterministic gate suite**.
There is **no LLM SDK in the codebase** — the CLI agent (you, via a skill) *is* the model; the
Python tool only extracts, validates, and accepts. Generation/repair = agent; acceptance = code.

## 2. Setup
- Python **>=3.11**, fresh **`.venv`**, **public pypi.org only** (no Artifactory), pinned deps.
- Install from repo root:
  ```
  python -m pip install -e ".[dev]"
  ```
- Windows venv form:
  ```
  .venv\Scripts\python.exe -m pip install -e ".[dev]"
  ```
- POSIX venv form:
  ```
  .venv/bin/python -m pip install -e ".[dev]"
  ```
  Runtime: `openpyxl==3.1.5`, `oletools==0.60.2`, `pandas==2.3.3`. Dev: `pytest==8.4.2`, `hypothesis==6.155.5`.

## 3. Run it
**Accept an already-generated kernel (one command, the KLV worked example):**
```
python -m rechner_pipeline.cli assurance \
    --repo-root . --input examples/Tarifrechner_KLV.xlsm \
    --generated-dir generated --info-dir info_from_excel \
    --diagnostics-dir diagnostics --qa-contract qa_contract.json --adapter excel
```
Runs the chain `extract → validate → security → conventions → golden_master → algebraic →
roundtrip → dossier` over one shared `--diagnostics-dir`; aggregate exit code = dossier verdict
(**0 = accepted**, 40 = human_review_required). KLV is accepted hands-off & idempotent.

**(Re)generate a kernel:** invoke the **`build-vergleichsrechenkern`** skill (the agent reads the
`info_from_excel/` bundle, writes the six files, drives the gates to acceptance). KLV facts:
interest 1.75%, mortality `DAV1994_T_M`, ω=100; expectations = 5 scalars (`Bxt, BJB, BZB, Pxt, ratzu`)
+ 612 table cells, coverage `full`.

**Agent surfaces:** Claude CLI uses `.claude/skills/build-vergleichsrechenkern/SKILL.md`.
Codex CLI uses the root `AGENTS.md` plus `.agents/skills/build-vergleichsrechenkern/SKILL.md`.
Those skill bodies are intentionally mirrored and covered by tests. Start Codex at repo root
or run `codex exec --cd . --sandbox workspace-write --ask-for-approval on-request "..."`.

## 4. The gates (each: `python -m rechner_pipeline.toolbox.<cmd>`, or run all via `assurance`)
| Gate | Proves | Exit | Command |
|---|---|---|---|
| G0 extract | manifest + bundle, byte-identical extraction, coverage | 10 | `extract` |
| G1 validate | exactly six files, right order, compiles, GM schema | 20 | `validate` |
| G2 security | static AST: no net/subprocess/exec/RNG/time/write-IO | 21 | `security` |
| G3 conventions | allowed import graph only, no cycles/local-import, cache hashable | 22 | `conventions` |
| G4 confinement | kernel runs read-only-under-root (inside G5/G7, not standalone) | 30/32 | (in golden_master/roundtrip) |
| G5 golden_master | computed scalars/tables == extracted expectations (4-dec) | 30 | `golden_master` |
| G6 algebraic | Hypothesis actuarial identities hold (load-bearing for accuracy) | 31 | `algebraic` |
| G7 roundtrip | tafeln canonical fixpoint + re-extract + recompute stable | 32 | `roundtrip` |
| G8 dossier | aggregates all `.gate.json` ledgers → mechanical accept/block | 40 | `dossier` |

Exit 2 = usage, 50 = internal. A non-zero exit is **blocking**, never downgraded to a warning.

## 5. Layout (all relative to `--repo-root .`)
- **`info_from_excel/`** — the extraction *bundle* (CSVs, `*_scalar.json`, `*_table_values.csv`,
  `names_manager.csv`, `vba/*.txt`, `export_manifest.json`, `input_bundle.json`). MUST live **under repo root**.
- **`generated/`** — **EXACTLY six files**: `inputs.py, params.py, tafeln.xml, commutation.py, actuarial.py, test_run.py`. Nothing else.
- **`diagnostics/`** — shared ledger dir: one `<command>.gate.json` per gate + `qa_report.json` + `run_dossier.json`.
- **`qa_contract.json`** — at **repo root**, NOT in `generated/` (a 7th file fails G1). Passed via `--qa-contract`.

## 6. Extend it
- **New gate:** use the **`author-rechner-toolbox-gate`** skill — thin `toolbox/<cmd>.py` wrapper over a
  `qa/<engine>.py`; `main()`+`run_command` skeleton, `default=None` mergeable flags, `write_gate_ledger`
  on BOTH pass & fail, standard exit code + status mirroring. Add it to `REQUIRED_GATES`/`ALL_GATES` in
  `orchestrate/dossier.py` and to the `assurance` chain.
- **New input adapter:** implement the `InputAdapter → InputBundle` seam (`adapters/base.py`; `adapters/excel.py`
  `ExcelAdapter` is the zero-behavior reference). Wire it into `--adapter`. **Word is the future case**; today
  `--adapter` accepts only `auto|excel`.
- **Acceptance requires:** every required gate `passed` under recorded versions/hashes, coverage `full`,
  no blocking (`strict_error`) manifest warning, no unapproved open assumption. `dossier` decides — never self-assessment.

## 7. Gotchas
- **Generated code is constrained** (enforced by G2/G3/G4, so the kernel must obey): no network/subprocess/
  `eval`/`exec`/dynamic-import/write-IO/`random`/`time`/`os.environ`; only edge between compute layers is
  `actuarial.py → commutation.py`; `@lru_cache` only with strictly-hashable args (bare `tuple`/`Tuple` FAILS —
  use `Tuple[int, ...]`); GM scalar keys byte-match `*_scalar.json` (case-sensitive, no normalization);
  `qx` extracted faithfully into `tafeln.xml` (full precision OK), missing table → raise + `human_review_required`.
- **`qa_contract.json` lives at repo root**, never in `generated/`.
- **`--info-dir` must be under `--repo-root`** or the confined golden_master/roundtrip children can't read
  expectations (exit 30 `confinement_failure`).
- **Supply `--qa-contract` for real acceptance** — omitting it skips G6 and `dossier` blocks on `gate.missing`.
- `roundtrip` (G7) needs `--input <original workbook>` for its re-extraction check — keep the source path available.
- fs_confine (G4) is **defense-in-depth, not an OS sandbox**; trust = G2 static + G4 confine + subprocess isolation.

## 8. Status
**COMPLETE & SOUND** (final review verdict). Current verification: **287 passed, 1 skipped**.
KLV kernel **accepted** hands-off & idempotent (assurance exit 0, dossier accepted, coverage
full; green proven real — anti-overfit + 1:1 VBA port).
Explicitly **future**: a Word input adapter (seam exists, not implemented). No MCP/RPC seam exists
today; use the plain Python toolbox commands.
