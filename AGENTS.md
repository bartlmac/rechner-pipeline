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
- Run full deterministic acceptance after generated files exist:
  `python -m rechner_pipeline.cli assurance --repo-root . --input examples/Tarifrechner_KLV.xlsm --generated-dir runs/generated --info-dir runs/info_from_excel --diagnostics-dir runs/diagnostics --qa-contract qa_contract.json --adapter excel`.

## Codex Entry Points

- Interactive repo work: start Codex from the repository root so this `AGENTS.md` and `.agents/skills/` are discovered.
- Headless repo work: `codex exec --cd . --sandbox workspace-write --ask-for-approval on-request "..."`.
- For kernel generation, invoke `$build-vergleichsrechenkern` or ask for `build-vergleichsrechenkern`.
- For new toolbox gates, invoke `$author-rechner-toolbox-gate`.
