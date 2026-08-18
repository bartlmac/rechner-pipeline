# ONBOARDING — rechner-pipeline

## 1. What this is
A system for **life-insurance portfolio migration**, with **no LLM SDK in the
codebase** (the CLI agent *is* the model; Python code pre-digests, validates,
computes and accepts):

1. **The target kernel** (`rechner_pipeline.kern`, version 3.0.0): a stable,
   versioned calculation kernel formulated entirely in the state-model world
   (semi-Markov backbone, Thiele recursion on pure decrement probabilities).
   Two products — endowment (KLV) and disability (BU) — are *configurations*
   of that backbone, not separate engines. Commutation values live in a
   **separate second kernel** used only as a cross-check rail (ADR-004).
2. **The portfolio module** (`rechner_pipeline.bestand`): synthetic,
   forward-projectable portfolios that the target kernel can compute directly.
   Every amount comes from the kernel; the module carries no actuarial
   formulas of its own.
3. **The migration pipeline** (the main path): heterogeneous sources
   (Tarifmeldung DOCX, Tarifrechner XLSM) -> ontology (T-Box/A-Box with
   per-statement provenance and discrepancy objects) -> Tarif-Spez ->
   parametrized kernel -> acceptance against the source calculator, with human
   gates (G-1/G-2/G-T) and immutable decision snapshots.

Read `docs/architektur/migrations-pipeline-v01.md` first, then the role catalog
`docs/architektur/skill-architektur.md`, then the seven ADRs in
`docs/architektur/`.

**Historical note:** the project started from a one-time *translation act* — a
coding agent ported an Excel/VBA calculator into a six-file Python kernel,
accepted by a deterministic gate chain (617/617 values, 2026-07-22). That proof
is complete. The porting machinery was retired on 2026-08-17 and is preserved
on branch `parked/portierung-excel` / tag `portierung-excel-2026-08`. New
generations are **parametrization**; new products come through the T-Box
(gate G-T) — not by translating another workbook.

A migration case lives in a **Fall-Arbeitsbereich** (`python -m
rechner_pipeline.fall`, ADR-002). The artifacts of this workspace belong to
**Pfefferminzia Lebensversicherung (PLV)** — the fictitious insurer the
system is demonstrated on. `configs/` holds the PLV portfolio
configurations (TOML, suite-loaded); `tests/fixtures/` holds synthetic
source workbooks for the extraction tests. Case sources come from
outside — there is no repo-level input channel.

## 2. Setup
Python **3.11+**. No LLM key needed.
```
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"      # Windows: .venv\Scripts\python
```
Runtime (pinned): `openpyxl`, `oletools`, `pandas`, `pyarrow`, `matplotlib`,
`pydantic` — see `pyproject.toml`. Dev: `pytest`, `hypothesis`.

## 3. Run it
**Create a case and register its sources** (the input channel; sources are
stored read-only with SHA-256 in `eingang.json` and checked before every run):
```
python -m rechner_pipeline.fall anlegen --fall faelle/klv-tg2012
python -m rechner_pipeline.fall registrieren --fall faelle/klv-tg2012 \
    --datei tests/fixtures/Tarifrechner_KLV_TG2012.xlsm
python -m rechner_pipeline.fall status --fall faelle/klv-tg2012
```

**Pre-digest a source, then run the ontology gates:**
```
python -m rechner_pipeline.gates.extract --repo-root . \
    --input faelle/klv-tg2012/eingang/Tarifrechner_KLV_TG2012.xlsm \
    --out-dir faelle/klv-tg2012/abgeleitet/vorverdichtung/xlsm-TG2012 --adapter excel
python -m rechner_pipeline.gates.abox_validate --fall faelle/klv-tg2012 --repo-root .
python -m rechner_pipeline.gates.generation_golden --fall faelle/klv-tg2012 \
    --generation klv/tg2015 --repo-root .
```

**Generate a portfolio and its report.** Two DIFFERENT dates: `--bis` is
the simulation horizon (how far events are projected), `--stichtag` only
marks the history/projection boundary in the report. Setting `--bis` to
"today" silently kills the projection — everything beyond the reference
date then degenerates to planned new business:
```
python -m rechner_pipeline.bestand.cli_fortschreibung \
    --config configs/bestand_gesamt.toml --bis 2046-01-01 --out-dir runs/bestand
python -m rechner_pipeline.bestand.cli_report --portfolio runs/bestand/bestand_gesamt.parquet \
    --historie runs/bestand/historie.parquet --ledger runs/bestand/ledger.parquet \
    --scheiben runs/bestand/scheiben.parquet --config configs/bestand_gesamt.toml \
    --bis 2046-01-01 --stichtag 2026-01-01 --out runs/berichte/bestandsbericht.html
```

**Navigate the codebase** (fundstellen are derived, not searched — ADR-005):
```
python -m rechner_pipeline.ontologie.code_index --tests tests   # node <-> module/test
python -m rechner_pipeline.ontologie.code_karte                 # layer rules
git diff --name-only | python -m rechner_pipeline.ontologie.impact
python -m rechner_pipeline.ontologie.landkarte --out runs/landkarte.html
```

## 4. The gates
Each gate is one command, writes one JSON to stdout plus a
`<command>.gate.json` ledger into `--diagnostics-dir`. A non-zero exit is
**blocking** and is never softened into a warning.

| Gate | Command | Proves |
|---|---|---|
| G0 | `gates.extract` | deterministic pre-digest of a source workbook (formulas, cached values, defined names via openpyxl; VBA via `oletools.olevba`) |
| O0 | `gates.abox_merge` | fragments merged into the A-Box, with a chain ledger binding it to its sources |
| O1 | `gates.abox_validate` | A-Box against T-Box, coverage, plausibility ranges, formula back-check, chain re-computation |
| O3 | `gates.generation_golden` | the parametrized kernel against the source calculator's expectation values |
| P9 | `gates.gate_entscheid` | immutable snapshots of the human gates (G-1, G-2, G-T); agents may only reject |
| B1 | `gates.bestand_validate` | portfolio schema and movement identities per year, track and measure |

## 5. Non-negotiables
- **Deterministic and SDK-free** in `src/`: no network, no subprocess, no
  dynamic execution; same input -> same output; sorted serialization.
- **Fail-fast, never silent**: no silent overwrite, no silent default. Doubt is
  a named state (`nicht_belegt`/`mehrdeutig`/`widerspruechlich`) or a hard
  error whose message names the way out.
- **Agents never decide** contradictions between sources. Provisional
  resolutions carry `vorlaeufig=true` and block every human acceptance.
- **Nodes** (`Knoten: klv/tg2015`) in every module and test docstring; the same
  IDs as the A-Box and gate O3. `code_index` must stay drift-free,
  `code_karte` finding-free.
- **Full suite before every commit** (`.venv/bin/python -m pytest`). The impact
  tool is informational; CI runs everything.
- Dependencies pinned exactly, new ones only via ADR. Push is the human's job.
