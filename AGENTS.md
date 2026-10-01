# AGENTS.md

Shared, CLI-neutral instructions for coding agents working in this
repository. Deep-dive: `ONBOARDING.md`, architecture and ADRs in
`docs/architektur/`, role catalog in
`docs/architektur/skill-architektur.md`.

## Working Agreements

- LLM agents propose (one pre-digested source each); deterministic code
  decides (merge, coverage, comparison, transformation, acceptance);
  humans decide contradictions between sources and every acceptance
  gate (A-Q1/A-O1/A-K2/A-M1 to A-M4). No LLM path inside any gate.
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
- The four agent roles of the KI-Tool (ADR-018: `agent/aktuariat`,
  `agent/architektur`, `agent/rechenkern`, `agent/programmleitung`) are
  defined under `.claude/agents/` and mirrored in `.agents/agents/`
  (parity test-enforced). They prepare and hand over; they never sign a
  human gate.
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

- Install for development (the same pinned way CI uses; `pip install -e
  ".[dev]"` alone resolves the transitive set freshly and is NOT the
  documented way): `python -m pip install -r requirements-dev.txt`
  followed by `python -m pip install -e . --no-deps`. Reference
  environment is Linux + CPython 3.11; off Linux, run the suite in the
  development container (`deploy/dev/Dockerfile`, `.devcontainer/`) —
  the code is not hardened for other operating systems.
- Run tests: `python -m pytest -n 12 --dist loadfile` (ADR-019). The
  full suite is still the pre-commit condition, but it now takes about
  seven minutes instead of twenty; `-n 12 --dist loadfile` gives one
  test FILE to one worker, so the module-scoped fixtures stay intact.
  Plain `python -m pytest` still works and is what CI uses.
  Do not touch the working tree while a suite runs in it, and never let
  a test write inside the repository (use `tmp_path`): every run is
  watched (`tests/baumwaechter.py`), and a tree that changes during the
  run turns the run red even if every test passed — read the
  `Baumwaechter` line above the result line.
  Partial runs while building (never as a substitute for the full suite
  before a commit):
  `python -m pytest -m "not langsam"` — everything except the measured
  heavyweights; `python -m pytest -m system_betrieb` — one NODE line
  (markers are derived from the `Knoten:` annotations, so the vocabulary
  is klv, bu, system_betrieb, system_bestand, system_assurance,
  system_entscheid, system_architektur, system_gates, system_fall,
  system_skills, klv_tg2015, klv_tg2012 — a LAYER name such as `kern`
  selects nothing and says so only by running empty; see
  `tests/conftest.py`);
  `python -m pytest $(git diff --name-only | python -m
  rechner_pipeline.ontologie.impact | python -c "import json,sys;
  print(' '.join(json.load(sys.stdin)['pytest_args']))")` — exactly the
  test modules the changed files can reach.
  Only ONE suite per working tree at a time, and wrap concurrent runs in
  `flock /tmp/suite.lock` (bundle several modules into ONE call — many
  short calls starve a long one).
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
  resolutions carry `vorlaeufig=true` and block human acceptance. Who
  signs is determined from the key via the Zeichnungsordnung (ADR-018:
  roles `mensch/<funktion>` sign, `agent/<name>` roles only prepare and
  may reject; the key class `mensch`/`simulation`/`agent` is recorded
  in every snapshot).
- Migration controlling: the two-reporting-date suite engine
  (`rechner_pipeline.qa.migrationssuite`) runs only through
  `python -m rechner_pipeline.gates.migrationssuite_lauf`, which takes the
  tariff rules from the case's Spez (ADR-024 addendum; the engines of the
  suite and of the actuarial test carry no default for any tariff rule);
  the HTML acceptance report is `rechner_pipeline.gates.abnahmebericht`;
  both are driven by the `pruefe-migrationscontrolling` skill (gate A-M4).
- Actuarial test (precedes A-M4): THREE separately signed acceptances —
  `A-M1` Stichtagstest, `A-M2` Verlaufstest, `A-M3`
  Geschaeftsvorfalltest. Per contract a LIST of check points
  (`rechner_pipeline.qa.aktuarieller_test`), each with its own sample and
  criteria (`rechner_pipeline.qa.testprofil`); no interpolated
  comparison, no summation. Sub-annual points are admissible only with a
  business event as the occasion — there the mixing convention IS the
  subject of the check. Run by `rechner_pipeline.gates.aktuartest_lauf`
  (rules from the Spez), rendered by
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
- Daily operations of the showcase insurer (concept
  `docs/simulation/tagesbetrieb.md`; package `rechner_pipeline.betrieb`,
  layer `betrieb/`): `python -m rechner_pipeline.betrieb.tageslauf --stand
  <daten> [--heute <ISO>] --schluessel <key> --zeichnungsordnung <ordnung>`
  runs one day (catch-up of missed days, daily new business, roll-forward,
  day journal, P-B1 guard via the engine, month-end close, protocol line
  signed with the operations key, role `betrieb/tageslauf`, key class
  `betrieb`, ADR-018 addendum 2026-09-30); `python -m
  rechner_pipeline.betrieb.uebernahme --stand <daten> --fall <faelle/name>
  --stichtag <ISO> --freigabe-schluessel <vorstand-key>
  --freigabe-schluessel <aktuariat-key> --freigabe-schluessel <betrieb-key>
  --betriebsschluessel <key> --zeichnungsordnung <ordnung> --linie <linie>`
  registers a migrated portfolio as a
  dated, signed intake — only with an accepted intake acceptance A-B2
  (ADR-022; the key ring holds the board's key for the links of the line,
  that of `mensch/aktuariat` for A-M1/A-M4 and that of `mensch/betrieb` for
  A-B2): the intake has three steps, `python -m
  rechner_pipeline.betrieb.zugangsprobe --stand <daten> --fall
  <faelle/name> --stichtag <ISO> [--bis <ISO>] --schluessel <key>
  --zeichnungsordnung <ordnung> --freigabe-schluessel <vorstand-key>
  --freigabe-schluessel <aktuariat-key> --linie <linie>` (two
  deterministic runs on a copy of the store, with and without the intake;
  their difference against the accepted portfolio is the evidence
  `abgeleitet/berichte/zugangsprobe.json`), then `gates.gate_entscheid
  --gate A-B2` (signed by `mensch/betrieb`; `agent/betrieb` can only
  reject), then the registration; the day run checks the acceptance
  against the store state when the intake is taken up, and config, kernel
  and code state when it actually enters; `python -m rechner_pipeline.betrieb.seite --stand
  <daten> [--paket <dir> --anker <dir> --betriebsschluessel <key>
  --zeichnungsordnung <ordnung>]` renders "Bestand heute" and exports the
  stand package that `werkzeuge/falldaten.py --stands-paket` consumes.
  Tests get the operations key via the session seam
  `tageslauf._STANDARD_BETRIEBSZEICHNUNG` and an intake acceptance via
  `uebernahme._STANDARD_ZUGANGSABNAHME` (tests/conftest.py,
  tests/zugangsabnahme_testhelfer.py). Runtime
  environment and image: `deploy/plv/`.
- Navigate and scope changes via the ontology index (ADR-005;
  fundstellen are derived, not searched):
  `python -m rechner_pipeline.ontologie.code_index --tests tests`,
  `python -m rechner_pipeline.ontologie.code_karte`,
  `git diff --name-only | python -m rechner_pipeline.ontologie.impact`
  (informational — CI and the pre-commit rule still run the FULL
  suite), `python -m rechner_pipeline.ontologie.landkarte
  --format mermaid|dot|graphml --umfang schichten|knoten|modul --out <datei>`.

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
  gate A-M4; A-M1 precedes A-M4). A-M4 also requires that the state the
  case runs on is accepted: kernel state A-K2 (presented by
  `agent/rechenkern` with `gates.kernstand_belegen`, signed by
  `mensch/rechenkern`), T-Box state A-O1 (presented by
  `agent/architektur` with `gates.stand_belegen tbox`, signed by
  `mensch/architektur`) and the PLV tariff work A-T1 (presented by
  `agent/aktuariat` with `gates.tarifwerk_belegen`, signed by
  `mensch/aktuariat`). Each is accepted ONCE outside any case in the
  line area (`linie/`, gitignored; `gate_entscheid --linie`, ADR-025);
  a case signs only what it changes and otherwise refers to the current
  acceptance via `gates.stand_belegen verweisen --linie` ("keine
  Aenderung"). The opening portfolio of a store (A-B3, presented by
  `agent/betrieb` with `betrieb.anfangsbestand belegen`, signed by
  `mensch/betrieb`, bound with `betrieb.anfangsbestand binden`) is
  required by the daily run after the build run. The line is MANDATORY
  (ADR-025, addendum 2026-10-01): every decision names `--linie`, signing
  happens only under the tip of the signing-order version line, and every
  reader that relies on an acceptance holds it against the order it was
  signed under, and against every later link of ITS line that reduces the
  signing role: such a link carries the board's signed declaration per
  reduced role (`stand_belegen ordnung --fruehere-zeichnungen
  <role>=gueltig|verfallen`, mandatory, no default) — `verfallen` voids
  every earlier signature in the LINE of that role (its earlier names and
  keys, continued over the same name or the same key, also after an earlier
  `gueltig`), whenever it was made (for the board: every case mandate A-M6
  and everything resting on it), `gueltig` keeps those signed before the
  link; read the consequence of both answers first with `stand_belegen
  ordnung ... --vorschau` (writes and signs nothing, ADR-025 addendum
  Pruefrunde I). Every `--repo-root` must be the tree of
  the package that is executing, and is refused if a bytecode file the
  interpreter would load under that package is not the code of its source
  (remedy: delete the package's `__pycache__`). Without a line nothing is
  signed and nothing relied on
  (the nightly run, which relies on no snapshot, excepted)
  (`models.ordnungslinie`; its root role is the board, `mensch/vorstand`,
  which signs order changes A-Z1 and case mandates A-M6, never a
  technical acceptance). A case starts with the signed CASE MANDATE
  A-M6 (presented with `gates.fall_belegen auftrag`, signed by the
  board): it binds the delivery (`eingang.json`), names the case's
  programme lead (`mensch/programmleitung`, role and key fingerprint)
  and the mandates of simulated roles; every other acceptance in the
  case requires it, and `agent/programmleitung` does not start a case
  without it. A failing case ends with the signed CASE ABORT A-M5
  (presented with `gates.fall_belegen abbruch`, signed by the programme
  lead with the right the mandate gives it); afterwards nothing in the
  case can be signed (ADR-026). Until the
  regression tool exists, the A-K2 regression record is the named
  EXCEPTION "nicht gefahren, Werkzeug noch nicht erstellt", never a pass.
  During a running migration no agent writes to the T-Box or the kernel:
  it presents the change, the human role reviews the diffs and signs
  (ADR-018, addendum 2026-10-01).
- For implementation work in `src/`/`tests/`, follow
  `$entwickle-im-zielsystem` (the architecture rules there are
  non-negotiable); code changes during a running migration additionally
  follow `$integriere-migrationsinkrement` (ADR-007). Quality-assure
  finished blocks with `$teste-adversarial`. Every external review round
  runs its full pattern: calibrate the attacker blind on the pre-fix
  state, a red test before each fix, a ratchet and a mutation probe per
  fix, a blind attack on the fixed state; "closed" is said only after a
  round without a confirmed finding, never under a deadline. Documentation follows
  `$dokumentiere-system`; new toolbox gates follow
  `$author-rechner-toolbox-gate`. Role catalog:
  `docs/architektur/skill-architektur.md`.
