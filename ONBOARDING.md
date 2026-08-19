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
source workbooks for the extraction tests; `lieferungen/` ships the
showcase deliveries of fictitious ceding insurers. There is no
implicit input channel — sources enter a case only through explicit
registration (below).

## 2. Setup
Python **3.11+**. No LLM key needed.
```
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"      # Windows: .venv\Scripts\python
```
Runtime (pinned): `openpyxl`, `oletools`, `pandas`, `pyarrow`, `matplotlib`,
`pydantic` — see `pyproject.toml`. Dev: `pytest`, `hypothesis`.

## 3. Run it
**Create a case and register its sources.** Registration is the ONLY
way into a case — never copy files into `eingang/` by hand. The command
takes the delivery wherever it landed (download folder, scp target),
copies it into `eingang/` (optionally renamed via `--als`), records
SHA-256, origin path and size in the `eingang.json` register, and sets
the copy read-only. Every later statement in the case traces back to
these hashes — the provenance chain starts here:
```
python -m rechner_pipeline.fall anlegen --fall faelle/klv-tg2012
python -m rechner_pipeline.fall registrieren --fall faelle/klv-tg2012 \
    --datei tests/fixtures/Tarifrechner_KLV_TG2012.xlsm
python -m rechner_pipeline.fall status --fall faelle/klv-tg2012
```
`status` (and every pipeline run) checks the register against the file
system in both directions: a registered file that is missing or whose
content deviates from its hash is a hard error, and so is any
hand-copied file without a register entry. Re-registering the same
content reports `bereits_registriert`; a lost copy is restored from
the source without touching the register; the same name with different
content is a hard conflict showing both hashes — there is no silent
overwrite. If a delivery genuinely replaces an earlier one, set up a
fresh case (or archive the old one under `faelle/archiv/`).

**Run the showcase migration.** `lieferungen/baldrian/` ships the
delivery of the fictitious insurer Baldrian Leben — the three inputs of
a real portfolio migration (faulty tariff calculator, tariff
notification, portfolio data delivery with two reporting dates and a
GeVo protocol). Register it into a fresh case:
```
python -m rechner_pipeline.fall anlegen --fall faelle/baldrian
for f in lieferungen/baldrian/*.xlsm lieferungen/baldrian/*.docx lieferungen/baldrian/*.csv; do
  python -m rechner_pipeline.fall registrieren --fall faelle/baldrian --datei "$f"
done
python -m rechner_pipeline.fall status --fall faelle/baldrian
```
From here the pipeline stages run through the agent skills
(`migrationsfall-durchfuehren` orchestrates; see the role catalog in
`docs/architektur/skill-architektur.md`): pre-digestion and extraction
per source, merge into the A-Box, discrepancies to the human gate G-1,
transformation of the portfolio extract, Spez, acceptance gates, and
the two-reporting-date migration suite with its HTML acceptance report
for gate G-2. The deliveries may contain deliberate errors and
source-system quirks — finding them IS the demonstration.

**Pre-digest a source (gate G0):**
```
python -m rechner_pipeline.gates.extract --repo-root . \
    --input faelle/klv-tg2012/eingang/Tarifrechner_KLV_TG2012.xlsm \
    --out-dir faelle/klv-tg2012/abgeleitet/vorverdichtung/xlsm-TG2012 --adapter excel
```
The ontology gates cannot follow directly on a fresh case: O1
(`gates.abox_validate`) validates an A-Box, and O3
(`gates.generation_golden`) validates a Tarif-Spez — neither exists
yet. The A-Box is produced by the Stage-1 extraction agents plus the
deterministic merge (`gates.abox_merge`), and the Spez is projected
from the accepted A-Box. Calling O1 or O3 on a bare case fails with
exit 2 **by design**: no silent default, the error names what is
missing. Run them the way `migrationsfall-durchfuehren` does — after
the stage that produces their input, and with the same `--generation`
the case actually carries.

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
| P9 | `gates.gate_entscheid` | immutable snapshots of the human gates (G-1, G-2, G-T); `--rolle mensch\|agent` is mandatory (exit 2 without it) and agents may only reject |
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
  tool is informational — it never narrows what has to run. CI
  (`.github/workflows/tests.yml`) runs the full suite on every push and
  pull request; case-bound tests skip honestly there, because the
  runner has no `faelle/` workspace. In a fresh clone expect the same:
  the suite is green with those tests skipped; locally, with a case
  workspace present, they run for real and must stay green.
- Dependencies pinned exactly, new ones only via ADR. Push is the human's job.
