# STATE.md — Agentic Rechner-Pipeline Migration

> Live "what is true today" document. Maintained by the project lead only.
> Conclusions, not aspirations: nothing is marked done until a gate is verified by running it.

_Last updated: 2026-06-25 — Codex-centric repo workflow added without removing the Claude CLI workflow. Claude skills remain in `.claude/skills/`; Codex-visible mirrored skills live in `.agents/skills/`; root `AGENTS.md` is now the durable repo instruction surface. No MCP/RPC path is supported._

## Mission

Execute the SDK→full-agentic migration specified in `MIGRATION.md` (self-contained).
Source-of-truth to migrate (READ-ONLY reference, never modified): `C:\AG-Bestandsmigration\rechner-pipeline`.
We build into: `C:\AG-Bestandsmigration\agentic-rechner-pipeline`.

## Locked decisions (user-confirmed 2026-06-18)

| # | Decision | Choice |
|---|---|---|
| 1 | CLI target | **Claude CLI + Codex CLI.** Claude remains supported through `.claude/skills/`. Codex is supported through root `AGENTS.md` plus mirrored repo skills under `.agents/skills/`. Other CLIs remain documented VERIFY stubs. |
| 2 | Gate scope | **All gates G0–G8** (extract, validate, security, conventions, golden_master, algebraic[Hypothesis], roundtrip, dossier). |
| 3 | Definition of done | **End-to-end on KLV:** build toolbox+skill AND actually generate the six `generated/` files for KLV, driving them to acceptance (or honest `human_review_required`). |
| 4 | Dependencies | **PUBLIC repo — public pypi.org only, pinned versions. NO corporate Artifactory / no corporate resources.** Fresh `.venv` on scoop Python 3.12.4. |

## Environment facts

- Python: package declares `>=3.11`. Use a repo-local `.venv` and install pinned deps from public pypi.org with `python -m pip install -e ".[dev]"`.
- Latest local verification in this repo: `.venv` on Python 3.13.5, `pytest==8.4.2`, `hypothesis==6.155.5`; full suite `287 passed, 1 skipped`.
- Test workbooks live under this repo's `examples/`: `Tarifrechner_KLV.xlsm`, `Tarifrechner_FLV_v1.xlsm`.
- Six generated files (order fixed): `inputs.py, params.py, tafeln.xml, commutation.py, actuarial.py, test_run.py`.

## Current package layout

```
src/rechner_pipeline/
  toolbox/      _common.py (JSON contract, exit codes, logging) + extract/validate/security/conventions/golden_master/algebraic/roundtrip/dossier.py
  extract/      excel.py, openpyxl_backend.py, scalar_table.py   (MIGRATE from source)
  adapters/     base.py, excel.py (ExcelAdapter zero-behavior wrapper)
  qa/           golden_master.py, fs_confine.py, security.py      (MIGRATE)
  models/       manifest.py (ExportManifest), bundle.py (InputBundle), schemas.py (§6.8)
  cli.py        source-neutral (--input/--adapter)
.claude/skills/build-vergleichsrechenkern/SKILL.md   (Claude skill entry point)
.agents/skills/build-vergleichsrechenkern/SKILL.md   (Codex repo skill mirror)
qa_contract.json (algebraic gate contract, §6.8.6)
```

## Exit codes (toolbox contract, MIGRATION §3.3)

2 usage/config · 10 extraction · 20 file-contract/compile · 21 security · 22 conventions ·
30 golden-master · 31 algebraic · 32 roundtrip · 40 dossier · 50 internal.

## Wave plan

| Wave | Content | Agents | Status |
|---|---|---|---|
| 0 | Foundation: scaffolding, `.venv`, pyproject, `toolbox/_common.py` (+stdout-purity `run_command`, `human_review_result`), `models/` schemas, copy workbooks | 1 (sequential) | **CLOSED — 34 tests green, review PASS, guardrails applied & verified** |
| 1 | MIGRATE deterministic ports: extract+ExcelAdapter, validate, security, golden_master(fix false-accept), dossier | 5 parallel | **CLOSED** build-green; review BLOCK→1b |
| 1b | Reconciliation: `write_gate_ledger`+UTF-8 stdout; wire ledger+`--diagnostics-dir` into extract/validate/security; harden fs_confine + order golden_master behind G2 | 1 seq + 2 parallel | **CLOSED** — 162 tests green; cross-process extract→dossier aggregation proven (G0 present, honest block on missing gates); both Criticals fixed |
| 1d | Distill Wave 0/1/1b feedback → reusable gate-authoring skill | 1 (product-dev) | **launching** |
| 1d | Distill Wave 0/1/1b feedback → `.claude/skills/author-rechner-toolbox-gate/SKILL.md` (84 lines) | 1 (product-dev) | **CLOSED** |
| 2 | NEW gates: conventions(AST G3), algebraic(Hypothesis+contract G6), roundtrip(G7) | 3 parallel | **built green (236 tests); review: G3/G6 PASS-WITH-FIXES, G7 BLOCK → 2b** |
| 2b | Fixes: G7 qx>12-dec false-fail + BadZipFile→exit10; G6 wired `D_x=v^x·l_x` (was dead) + terminal policy; G3 dynamic-import + conservative tuple lru_cache | 3 parallel | **CLOSED** — all verified; 271 tests green |
| 3 | (A) `build-vergleichsrechenkern` SKILL (§6.7, 213ln); (B) source-neutral `cli.py` + `assurance` orchestrator + SDK/LangGraph absence (grep clean) | 2 parallel | **CLOSED** — assurance chain runs e2e; 271 tests green; tree litter cleaned |
| 3d | Distill wave2/2b/3 feedback → complete the build-vergleichsrechenkern skill with final qa_contract schema + assurance invocation + dir layout | 1 (product-dev) | **launching** |
| 3d | Distill → complete build-vergleichsrechenkern skill (246 ln: assurance driver, dir layout, final qa_contract schema, gotchas) | 1 (product-dev) | **CLOSED** |
| 4 | E2E: generate KLV six files + author KLV `qa_contract.json`, drive `assurance` | 1 (skill exec) | **kernel CLOSED** — G0–G7 ALL pass (lead-verified: golden_master 5 scalars+612 cells 0 dev; algebraic 1501 cases 0 ce; roundtrip ok). Dossier blocked only by 4 toolbox wiring bugs → 4b |
| 4b | Fix 4 wiring bugs (extract input_hashes; dossier output→diagnostics-dir; assurance routes --diagnostics-dir; coverage via persisted input_bundle.json) + skill qa_contract location | 1 focused | **CLOSED** — assurance exit 0, dossier ACCEPTED (lead-verified hands-off + idempotent); 271 tests green |
| 5 | Final brutal review: KLV kernel faithfulness/overfit + migration completeness vs §4.1/§4.2 | 1 review | **CLOSED — verdict: COMPLETE & SOUND; green proven REAL; no Critical/High** |
| 6 | Operator handoff distillation (ONBOARDING.md, 96 ln) | 1 (product-dev) | **CLOSED** |

**Post-W4 skill bug fixed:** build-vergleichsrechenkern now keeps `qa_contract.json` outside
`generated/` and writes dossier artifacts under `diagnostics/`. Codex mirrors are tested against
the Claude skills.

Each wave → independent review gate (code-review-architect) before close. After each wave → an agentic-product-development expert distills feedback into reusable skills/agents.

## Open items / risks being tracked

- Baseline capture must write ONLY into this repo's tmp; never into the source repo.
- Keep `.claude/skills/` and `.agents/skills/` in parity unless a deliberate cross-CLI
  difference is documented and tested.
- Do not add or document MCP/RPC workflow paths.

## Gate status ledger (KLV)

| Gate | Status | Evidence |
|---|---|---|
| G0 extraction-manifest | command built, KLV pass (coverage=full, byte-identical) | extract.py; 13 tests |
| G1 file-contract | command built + ledger wired | validate.py; 27 tests |
| G2 static-security | command built (v2.0.0) + ledger wired | security.py; 26 tests |
| G3 conventions | command built + HARDENED (dynamic-import, conservative tuple cache) | conventions.py; 35 tests |
| G4 runtime-confinement | built + HARDENED (io.open/os.*/socket/subprocess blocked); golden_master ordered behind G2 | fs_confine; tests |
| G5 golden-master | command built, false-green FIXED, ledger wired | golden_master.py; tests |
| G6 algebraic | command built + FIXED (`D_x=v^x·l_x` now live; terminal policy required); Hypothesis 6.155.5 pinned | algebraic.py; 36 tests |
| G7 roundtrips | command built + FIXED (full-precision canonical; corrupt input→10) | roundtrip.py; 31 tests |
| G8 dossier-completeness | command built + wiring fixed (outputs→diagnostics); KLV run ACCEPTED | dossier.py; 13 tests |

**KLV kernel (Wave 4):** six files in `generated/` + `qa_contract.json` (repo root). Interest 1.75%, mortality DAV1994_T_M, ω=100. assurance ACCEPTED hands-off & idempotent (lead-verified 2026-06-19).

**Resolved historical gaps:** gate ledgers, shared `--diagnostics-dir`, G2-before-execute,
dossier aggregation, and KLV acceptance wiring are complete. Historical notes in older wave
logs are not current truth unless corroborated by code and tests.
