# AGENTS.md

## Working Agreements

- Do not reinvent established mechanisms; prefer the existing toolbox, gate, and skill patterns.
- Do not use RPC calls. The portable baseline is local files plus plain shell commands.
- Keep generated code deterministic; do not add network, subprocess, dynamic execution, or credential-reading paths.

## Repo Workflow

- The Python package is deterministic and SDK-free. Do not add OpenAI, Anthropic, LangGraph, provider, token, or hosted-agent runtime paths to `src/`.
- Generation and repair are owned by the outer CLI agent. Acceptance is owned by `python -m rechner_pipeline.cli assurance` and the toolbox gates.
- Use the repo-scoped Codex skills in `.agents/skills/` when running Codex. Keep them behaviorally identical to the corresponding `.claude/skills/` files unless a deliberate cross-CLI difference is documented and tested.
- Keep Claude CLI support intact. Do not move, rename, or weaken `.claude/skills/`.
- Do not document or depend on `rechner_pipeline.gates.mcp_stdio`; no such module exists. Do not add MCP/RPC workflow paths for this pipeline.

## Common Commands

- Install for development: `python -m pip install -e ".[dev]"`.
- Run tests: `python -m pytest`.
- Create a case workspace and register sources (the pipeline operates on a case, not on repo dirs; `examples/` is demo material, not an input channel):
  `python -m rechner_pipeline.fall anlegen --fall faelle/demo-klv`
  `python -m rechner_pipeline.fall registrieren --fall faelle/demo-klv --datei examples/Tarifrechner_KLV_TG2012.xlsm`
- Migration pipeline (ontology as the only stage interface; see docs/architektur/migrations-pipeline-v01.md): `python -m rechner_pipeline.gates.abox_validate --fall <fall>` (O1), `python -m rechner_pipeline.gates.generation_golden --fall <fall> --generation <id>` (O3), `python -m rechner_pipeline.quellen.tafel_import`, `python -m rechner_pipeline.ontologie.entscheide` and `python -m rechner_pipeline.gates.gate_entscheid` (human gates, P9 snapshots). Agents never resolve discrepancies as final; provisional resolutions carry `vorlaeufig=true` and block human acceptance.
- Navigate and scope changes via the ontology index (ADR-005; fundstellen are derived, not searched): `python -m rechner_pipeline.ontologie.code_index --tests tests` (node <-> module/test, drift), `python -m rechner_pipeline.ontologie.code_karte` (import graph vs. layer allowlist, ADR-004 rule, SDK ban), `git diff --name-only | python -m rechner_pipeline.ontologie.impact` (which tests and which case gates a change touches). The impact tool is informational — CI and the pre-commit rule still run the FULL suite. `python -m rechner_pipeline.ontologie.landkarte --out landkarte.html` renders the same data as one self-contained HTML page (deterministic, no new dependency) for review and demonstration.
- Run full deterministic acceptance after generated files exist:
  `python -m rechner_pipeline.cli assurance --repo-root . --fall faelle/demo-klv --quelle Tarifrechner_KLV_TG2012.xlsm --qa-contract qa_contract.json --adapter excel`.
  Direct-dir flags (`--input --generated-dir --info-dir --diagnostics-dir`) remain available and override case defaults.

## Codex Entry Points

- Interactive repo work: start Codex from the repository root so this `AGENTS.md` and `.agents/skills/` are discovered.
- Headless repo work: `codex exec --cd . --sandbox workspace-write --ask-for-approval on-request "..."`.
- For kernel generation, invoke `$build-vergleichsrechenkern` or ask for `build-vergleichsrechenkern`.
- For new toolbox gates, invoke `$author-rechner-toolbox-gate`.
- For a full migration case through the ontology pipeline, invoke `$migrationsfall-durchfuehren`; its Stage-1 extraction agents follow `$extrahiere-quellfragment`.
- For implementation work in `src/`/`tests/`, follow `$entwickle-im-zielsystem` (the architecture rules there are non-negotiable). Quality-assure finished blocks with `$teste-adversarial`; documentation follows `$dokumentiere-system`; fachliche Konflikte are PREPARED with `$bereite-fachkonflikt-auf` and DECIDED by humans. Role catalog: `docs/architektur/skill-architektur.md`.
