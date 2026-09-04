# AGENTS.md

Shared, CLI-neutral instructions for coding agents working in this
repository. Deep-dive: `ONBOARDING.md`, architecture and ADRs in
`docs/architektur/`, role catalog in
`docs/architektur/skill-architektur.md`.

## Working Agreements

- LLM agents propose (one pre-digested source each); deterministic code
  decides (merge, coverage, comparison, transformation, acceptance);
  humans decide contradictions between sources and every acceptance
  gate (A-Q1/A-M1/A-M4/A-K1). No LLM path inside any gate.
- The Python package is deterministic and SDK-free. Do not add OpenAI,
  Anthropic, LangGraph, provider, token, or hosted-agent runtime paths
  to `src/`; do not add network, subprocess, dynamic execution, or
  credential-reading paths to generated code.
- Do not use RPC calls. The portable baseline is local files plus plain
  shell commands; do not add MCP/RPC workflow paths.
- Do not reinvent established mechanisms; prefer the existing toolbox,
  gate, and skill patterns.
- Tests before every commit (full suite), named staging (never
  `git add -A`), pushes are done by the human maintainer only.
- No real names of team members, clients, or suppliers in tracked files
  or commit messages — use roles instead. Enforced by
  `tests/test_klarnamen.py` (hash-based, so the check itself carries no
  names); authorship fields (`pyproject.toml`, `LICENSE`) are the
  documented exception — a role would be wrong there. Commit messages
  written before the check existed are a documented exception too: the
  maintainer decided against rewriting a pushed branch's history
  (2026-09-04, external review finding T19-06), because a rebase would
  break the merge plan's "additive only" rule for every branch built on
  it. New commits follow the rule.
- Use the repo-scoped skills in `.agents/skills/` when running Codex and
  `.claude/skills/` when running Claude. The two trees are mirrored and
  their parity is test-enforced (`tests/test_agent_workflow_docs.py`);
  do not move, rename, or weaken either side.

## Repo Map (what an agent needs to know first)

- **Layer map** (import allowlist enforced by
  `python -m rechner_pipeline.ontologie.code_karte`):
  `quellen -> ontologie -> spez -> kern -> bestand -> qa -> gates`,
  plus `kommutationskern` as a separate second kernel consumed only by
  `qa` (cross-check rail).
- **Node annotation is mandatory:** every module and test file declares
  its ontology node in the docstring (`Knoten: klv/tg2015`); a building
  block without a node is a hard drift error
  (`python -m rechner_pipeline.ontologie.code_index --tests tests`).
- **Cases** live in `faelle/<name>/` (gitignored): `eingang/` holds
  registered sources under a SHA-256 register (never silently
  overwritten — the provenance chain starts here), `abgeleitet/` holds
  everything regenerable, `entscheide/` holds append-only human
  decisions. The system is demonstrated on the fictitious insurer
  Pfefferminzia LV (PLV); `configs/` holds its portfolio configurations
  (TOML, suite-loaded), `tests/fixtures/` holds synthetic source
  workbooks for extraction tests, and `lieferungen/` ships the showcase
  deliveries of fictitious ceding insurers (freight to register into a
  case, possibly with deliberate errors — finding them is the
  demonstration). There is no implicit input channel: nothing reads
  `lieferungen/` automatically; sources enter a case only through
  explicit registration.
- **Docs have one home each:** architecture and ADRs in
  `docs/architektur/`; the normative maths and numerics of the kernel in
  `docs/mathematik/grundsatzdokumentation.md` — maintained here, with
  the kernel following it, including the migration entry and the
  correction layer in its section 9; Tarifplaene in
  `docs/tarifplaene/` carry the per-product elaboration and never
  repeat the shared backbone (guarded by
  `tests/test_tarifplan_struktur.py`); how the showcase portfolios are
  GENERATED — third-order experience assumptions, simulation tooling —
  in `docs/simulation/`, never in the actuarial documents, because in a
  real company reality drives the portfolio, not a model; the
  project-side migration procedure in `docs/migrationskonzept/`
  (template; the filled instance lives in the case workspace); planned
  work that is recognised but not built in `dev-docs/`; team
  agent instructions here; private notes in `docs-local/` (never read
  those or `simulation/` unless the human explicitly points you there —
  they are the maintainer's staging areas). Commands and flags belong
  in the skills, not in the concept documents.
- **Parallel migrations share one kernel trunk** (ADR-007): code
  changes during a migration are small node-bound increments; landing
  requires the full suite green including every case's frozen reference values.

## Common Commands

- Install for development: `python -m pip install -e ".[dev]"`.
- Run tests: `python -m pytest`.
- Case workspace:
  `python -m rechner_pipeline.fall anlegen --fall faelle/<name>`,
  `... registrieren --fall faelle/<name> --datei <quelle>`,
  `... status --fall faelle/<name>`.
- Migration pipeline (ontology as the only stage interface; see
  `docs/architektur/migrations-pipeline-v01.md`):
  `python -m rechner_pipeline.gates.extract` (P-Q1, pre-digest a
  workbook), `python -m rechner_pipeline.quellen.bestand_profil`
  (column profile of a delivered portfolio extract — transformation
  agents read this, never the raw CSV),
  `python -m rechner_pipeline.gates.abox_validate` (P-Q3),
  `python -m rechner_pipeline.quellen.tafel_import`,
  `python -m rechner_pipeline.gates.generation_golden` (P-K1),
  `python -m rechner_pipeline.ontologie.entscheide` and
  `python -m rechner_pipeline.gates.gate_entscheid` (human gates, P9
  snapshots). Agents never resolve discrepancies as final; provisional
  resolutions carry `vorlaeufig=true` and block human acceptance.
- Migration controlling: the two-reporting-date suite
  (`rechner_pipeline.qa.migrationssuite`) and the HTML acceptance
  report (`rechner_pipeline.gates.abnahmebericht`) are libraries driven
  by the `pruefe-migrationscontrolling` skill (gate A-M4).
- Actuarial test (precedes A-M4): THREE separately signed acceptances —
  `A-M1` Stichtagstest, `A-M2` Verlaufstest, `A-M3`
  Geschaeftsvorfalltest. Per contract a LIST of check points
  (`rechner_pipeline.qa.aktuarieller_test`), each with its own sample and
  criteria (`rechner_pipeline.qa.testprofil`); no interpolated
  comparison, no summation. Sub-annual points are admissible only with a
  business event as the occasion — there the mixing convention IS the
  subject of the check. Rendered by
  `python -m rechner_pipeline.gates.aktuartest --abnahme A-M1|A-M2|A-M3`,
  driven by the `aktuartest-durchfuehren` skill.
- Migration entry (ADR-012, Grundsatzdokumentation section 9): the
  correction layer computes in `rechner_pipeline.kern.korrekturschicht`.
  It is NOT a second engine — the collapse form arises from the existing
  Thiele recursion by dropping the value-continuous transitions, which is
  why lapse assumptions cannot influence the calibration factor.
- Portfolio module: `python -m rechner_pipeline.bestand.cli_fortschreibung`
  (GeVo stream to Parquet), `python -m rechner_pipeline.bestand.cli_report`
  (self-contained HTML report; `--bis` is the simulation horizon,
  `--stichtag` splits history from projection — default:
  `meta.referenzstichtag` from the config),
  `python -m rechner_pipeline.gates.bestand_validate` (P-B1).
- Navigate and scope changes via the ontology index (ADR-005;
  fundstellen are derived, not searched):
  `python -m rechner_pipeline.ontologie.code_index --tests tests`,
  `python -m rechner_pipeline.ontologie.code_karte`,
  `git diff --name-only | python -m rechner_pipeline.ontologie.impact`
  (informational — CI and the pre-commit rule still run the FULL
  suite), `python -m rechner_pipeline.ontologie.landkarte
  --format mermaid|dot|graphml --umfang schichten|knoten|modul`.

## Codex Entry Points

- Interactive repo work: start Codex from the repository root so this
  `AGENTS.md` and `.agents/skills/` are discovered.
- Headless repo work:
  `codex exec --cd . --sandbox workspace-write --ask-for-approval on-request "..."`.
- For a full migration case through the ontology pipeline, invoke
  `$migrationsfall-durchfuehren`; its Stage-1 extraction agents follow
  `$extrahiere-quellfragment`; portfolio-extract mappings follow
  `$transformiere-quellbestand`.
- Fachliche Konflikte are PREPARED with `$bereite-fachkonflikt-auf` and
  DECIDED by humans; the actuarial test is prepared with
  `$aktuartest-durchfuehren` (decision: human gate A-M1) and migration
  controlling with `$pruefe-migrationscontrolling` (decision: human
  gate A-M4; A-M1 precedes A-M4).
- For implementation work in `src/`/`tests/`, follow
  `$entwickle-im-zielsystem` (the architecture rules there are
  non-negotiable); code changes during a running migration additionally
  follow `$integriere-migrationsinkrement` (ADR-007). Quality-assure
  finished blocks with `$teste-adversarial`; documentation follows
  `$dokumentiere-system`; new toolbox gates follow
  `$author-rechner-toolbox-gate`. Role catalog:
  `docs/architektur/skill-architektur.md`.
