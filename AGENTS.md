# AGENTS.md

Shared, CLI-neutral instructions for coding agents working in this
repository. Deep-dive: `ONBOARDING.md`, architecture and ADRs in
`docs/architektur/`, role catalog in
`docs/architektur/skill-architektur.md`.

## Working Agreements

- LLM agents propose (one pre-digested source each); deterministic code
  decides (merge, coverage, comparison, transformation, acceptance);
  humans decide contradictions between sources and every acceptance
  gate (G-1/G-A/G-2/G-T). No LLM path inside any gate.
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
  or commit messages — use roles instead.
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
  `docs/architektur/`; the product-side method in `docs/fachkonzept/` —
  `konstruktive-neuberechnung.md` is the Fachkonzept and is NEVER
  edited here (changes come from its author), while
  `grundsatzdokumentation.md` is this repo's own normative maths and
  numerics (FK ch. 8.1) and IS maintained here, with the kernel
  following it; Tarifplaene in `docs/tarifplaene/` carry the
  per-product elaboration (FK ch. 8.2) and never repeat the shared
  backbone (guarded by `tests/test_tarifplan_struktur.py`); the
  project-side migration procedure in `docs/migrationskonzept/`
  (template; the filled instance lives in the case workspace); team
  agent instructions here; private notes in `docs-local/` (never read
  those or `simulation/` unless the human explicitly points you there —
  they are the maintainer's staging areas). Commands and flags belong
  in the skills, not in the concept documents.
- **Parallel migrations share one kernel trunk** (ADR-007): code
  changes during a migration are small node-bound increments; landing
  requires the full suite green including every case's anchors.

## Common Commands

- Install for development: `python -m pip install -e ".[dev]"`.
- Run tests: `python -m pytest`.
- Case workspace:
  `python -m rechner_pipeline.fall anlegen --fall faelle/<name>`,
  `... registrieren --fall faelle/<name> --datei <quelle>`,
  `... status --fall faelle/<name>`.
- Migration pipeline (ontology as the only stage interface; see
  `docs/architektur/migrations-pipeline-v01.md`):
  `python -m rechner_pipeline.gates.extract` (G0, pre-digest a
  workbook), `python -m rechner_pipeline.quellen.bestand_profil`
  (column profile of a delivered portfolio extract — transformation
  agents read this, never the raw CSV),
  `python -m rechner_pipeline.gates.abox_validate` (O1),
  `python -m rechner_pipeline.quellen.tafel_import`,
  `python -m rechner_pipeline.gates.generation_golden` (O3),
  `python -m rechner_pipeline.ontologie.entscheide` and
  `python -m rechner_pipeline.gates.gate_entscheid` (human gates, P9
  snapshots). Agents never resolve discrepancies as final; provisional
  resolutions carry `vorlaeufig=true` and block human acceptance.
- Migration controlling: the two-reporting-date suite
  (`rechner_pipeline.qa.migrationssuite`) and the HTML acceptance
  report (`rechner_pipeline.gates.abnahmebericht`) are libraries driven
  by the `pruefe-migrationscontrolling` skill (gate G-2).
- Actuarial test (precedes G-2): per-contract comparison at each
  contract's own anchor date (`rechner_pipeline.qa.aktuarieller_test`,
  no interpolation, no summation) with the G-A template gate
  `python -m rechner_pipeline.gates.aktuartest`, driven by the
  `aktuartest-durchfuehren` skill.
- Portfolio module: `python -m rechner_pipeline.bestand.cli_fortschreibung`
  (GeVo stream to Parquet), `python -m rechner_pipeline.bestand.cli_report`
  (self-contained HTML report; `--bis` is the simulation horizon,
  `--stichtag` splits history from projection — default:
  `meta.referenzstichtag` from the config),
  `python -m rechner_pipeline.gates.bestand_validate` (B1).
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
  `$aktuartest-durchfuehren` (decision: human gate G-A) and migration
  controlling with `$pruefe-migrationscontrolling` (decision: human
  gate G-2; G-A precedes G-2).
- For implementation work in `src/`/`tests/`, follow
  `$entwickle-im-zielsystem` (the architecture rules there are
  non-negotiable); code changes during a running migration additionally
  follow `$integriere-migrationsinkrement` (ADR-007). Quality-assure
  finished blocks with `$teste-adversarial`; documentation follows
  `$dokumentiere-system`; new toolbox gates follow
  `$author-rechner-toolbox-gate`. Role catalog:
  `docs/architektur/skill-architektur.md`.
