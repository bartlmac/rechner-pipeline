"""Regression tests for checked-in agent workflow instructions."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def test_codex_repo_skills_match_claude_skills() -> None:
    """Codex support must not drift from the verified Claude skill bodies."""
    pairs = (
        (
            ".claude/skills/build-vergleichsrechenkern/SKILL.md",
            ".agents/skills/build-vergleichsrechenkern/SKILL.md",
        ),
        (
            ".claude/skills/author-rechner-toolbox-gate/SKILL.md",
            ".agents/skills/author-rechner-toolbox-gate/SKILL.md",
        ),
    )
    for claude_rel, codex_rel in pairs:
        assert _read(codex_rel) == _read(claude_rel), codex_rel


def test_root_agents_md_documents_codex_without_breaking_claude() -> None:
    text = _read("AGENTS.md")
    assert ".agents/skills/" in text
    assert ".claude/skills/" in text
    assert "codex exec --cd . --sandbox workspace-write" in text
    assert "Do not use RPC calls" in text


def test_per_cli_notes_do_not_advertise_missing_mcp_module() -> None:
    text = _read(".claude/skills/build-vergleichsrechenkern/per-cli-notes.md")
    assert "Codex CLI — VERIFIED repo-skill target" in text
    assert "rechner_pipeline.toolbox.mcp_stdio" not in text
    assert "No toolbox MCP adapter exists" in text
