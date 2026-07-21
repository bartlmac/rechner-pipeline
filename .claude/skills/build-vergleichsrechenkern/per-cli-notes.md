# Per-CLI notes — build-vergleichsrechenkern

The behavioral contract in `SKILL.md` is the install-neutral §6.7 body. It contains no
SDK call, API key, or CLI-specific front-matter; each CLI wraps it with its own delivery
mechanism but the contract does not change (§3.6).

## Claude CLI / Claude Code — VERIFIED target

This is the verified target. The body ships as a native Agent Skill at
`.claude\skills\build-vergleichsrechenkern\SKILL.md` (or `~\.claude\skills\...`) and is
invoked with `/build-vergleichsrechenkern` or by the trigger phrasing in the description.
No toolbox MCP adapter exists in this repo today; run the plain Python toolbox commands.
Headless: `claude -p "..."` with appropriate permission flags. If a common `AGENTS.md` is
used by the active Claude surface, treat it as repo guidance, but the `.claude` skill stays
the Claude entry point.

## GitHub Copilot CLI — VERIFY stub (not built)

No verified native `SKILL.md`. Install the procedure as `AGENTS.md` and/or
`.github\copilot-instructions.md`, with an optional custom agent/prompt when supported.
No toolbox MCP adapter exists in this repo today; run the plain Python toolbox commands.
Headless: `copilot -p "..."` with `--allow-tool` / `--allow-all-tools` as policy permits.
Custom-command authoring beyond instructions/plugins and custom-agent config path/precedence:
VERIFY.

## Codex CLI — VERIFIED repo-skill target

Codex reads repo instructions from `AGENTS.md` and repo skills from `.agents\skills\`.
This repo ships Codex-visible copies at `.agents\skills\build-vergleichsrechenkern\SKILL.md`
and `.agents\skills\author-rechner-toolbox-gate\SKILL.md`; tests enforce parity with the
Claude skills. Headless: `codex exec --cd . --sandbox workspace-write --ask-for-approval
on-request "..."`. Do not configure MCP/RPC for this pipeline; use plain Python toolbox
commands.

## OpenCode CLI — VERIFY stub (not built)

Use `.opencode\commands\build-vergleichsrechenkern.md` or `command` in `opencode.json`;
include/reference the same §6.7 body. Invoked `/build-vergleichsrechenkern`. Primary and
subagents via `opencode.json` or Markdown (`@agent`). No toolbox MCP adapter exists today;
use plain Python toolbox commands. Headless: `opencode run "..."`.
Exact headless subcommand/options: VERIFY.
