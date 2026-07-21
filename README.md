# rechner-pipeline

Full-agentic, CLI-driven Excel-to-Python actuarial migration pipeline.

This repository contains the deterministic acceptance layer for migrating an
Excel/VBA actuarial *Tarifrechner* into a six-file pure-Python comparison
kernel. The agent writes and repairs the kernel; this package extracts inputs,
runs gates, and produces the mechanical acceptance dossier. See `MIGRATION.md`
for the full architecture history and specification.

## Usage

`rechner-pipeline` is a **deterministic, SDK-free** acceptance CLI. It runs the
gate suite that decides whether an already-generated comparison kernel is
acceptable. Code generation and self-repair are owned by the migration *agent*
(a CLI skill — see `build-vergleichsrechenkern`), **not** by this tool: there is
no model / provider / token / reasoning surface and no LLM acceptance path.

## Setup

Use a local virtual environment and install the pinned development dependencies:

```
python -m pip install -e ".[dev]"
```

On Windows, use the venv interpreter path where appropriate:

```
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

On POSIX shells:

```
.venv/bin/python -m pip install -e ".[dev]"
```

### Source-neutral options

```
rechner-pipeline --input <path> [--adapter auto|excel]
                 [--export-backend openpyxl|com] [--strict-manifest-warnings]
```

* `--input <path>` — the source document to migrate (source-neutral; Excel
  today, with an adapter seam for future sources). `--excel <path>` is retained
  as a backward-compatible **alias** for `--input`.
* `--adapter auto|excel` — input adapter (default `auto`).
* `--export-backend openpyxl|com` — extraction backend; `openpyxl` is the
  deterministic, platform-neutral default. `com` needs Windows + Excel.
* `--strict-manifest-warnings` — treat `strict_error` manifest warnings as
  blocking failures.

Strict validation: every gate fails fast with a standard non-zero exit code
(§3.3). A non-zero exit is **blocking** and is never downgraded to a warning.

### `assurance` — the gate orchestrator

`assurance` runs the full deterministic gate suite **in order** over an
already-generated kernel and ends with a `dossier` acceptance verdict. It does
not contain gate logic and does not generate the six deliverables — it invokes
the existing `python -m rechner_pipeline.toolbox.<command>` gates and aggregates
their results.

```
rechner-pipeline assurance --repo-root . --input <wb> \
    --generated-dir <gen> --info-dir <info> --diagnostics-dir <diag> \
    [--qa-contract <path>] [--max-attempts N] [--adapter auto|excel] \
    [--export-backend openpyxl|com] [--strict-manifest-warnings]
```

Chain: `extract → validate → security → conventions → golden_master →
algebraic → roundtrip → dossier`. All gates share one `--diagnostics-dir`; each
writes its single JSON result to stdout and a `<command>.gate.json` ledger entry
into that dir, which `dossier` aggregates into the final verdict.

Stop/continue policy:

* `extract` and `validate` are **prerequisites**; if either fails the QA gates
  are skipped, but `dossier` still runs to record an honest blocked verdict.
* `security`..`roundtrip` are **continue-on-fail** so one run yields the full
  gate picture.
* `algebraic` is **skipped** when no `--qa-contract` is supplied
  (unknown-applicability without a product contract); `dossier` then reports
  `G6` as missing.
* the aggregate exit code is the `dossier` exit code (else the first blocking
  prerequisite failure).

### Deterministic toolbox (direct)

Each gate is also runnable directly:

```
python -m rechner_pipeline.toolbox.<command> [flags]
```

### Agent workflow surfaces

Claude CLI remains supported through `.claude/skills/`. Codex CLI is supported
through the repository `AGENTS.md` plus mirrored repo skills in `.agents/skills/`.
The Codex skill copies are tested for byte-for-byte parity with the Claude skill
bodies so one workflow does not silently drift from the other.

The portable baseline is local files plus plain Python commands. There is no
`rechner_pipeline.toolbox.mcp_stdio` module and no supported MCP/RPC path in the
current codebase.

### No SDK / LangGraph in the target execution path

The target carries **no** Python LLM SDK or LangGraph orchestration in `src/`.
Verify with:

```
rg -n -i "anthropic|openai|OPENAI_API_KEY|ANTHROPIC_API_KEY|langgraph|StateGraph|rechner-pipeline-agentic" src pyproject.toml
```

This should return **no matches** for active target code/config. The CLI exposes
only the deterministic gate suite; generation/repair is the agent's
responsibility.
