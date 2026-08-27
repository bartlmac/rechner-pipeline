"""Regression tests for checked-in agent workflow instructions.

Knoten: system/skills
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def test_codex_repo_skills_match_claude_skills() -> None:
    """Codex support must not drift from the verified Claude skill bodies."""
    pairs = (
        (
            ".claude/skills/author-rechner-toolbox-gate/SKILL.md",
            ".agents/skills/author-rechner-toolbox-gate/SKILL.md",
        ),
        (
            ".claude/skills/migrationsfall-durchfuehren/SKILL.md",
            ".agents/skills/migrationsfall-durchfuehren/SKILL.md",
        ),
        (
            ".claude/skills/extrahiere-quellfragment/SKILL.md",
            ".agents/skills/extrahiere-quellfragment/SKILL.md",
        ),
        (
            ".claude/skills/entwickle-im-zielsystem/SKILL.md",
            ".agents/skills/entwickle-im-zielsystem/SKILL.md",
        ),
        (
            ".claude/skills/teste-adversarial/SKILL.md",
            ".agents/skills/teste-adversarial/SKILL.md",
        ),
        (
            ".claude/skills/dokumentiere-system/SKILL.md",
            ".agents/skills/dokumentiere-system/SKILL.md",
        ),
        (
            ".claude/skills/bereite-fachkonflikt-auf/SKILL.md",
            ".agents/skills/bereite-fachkonflikt-auf/SKILL.md",
        ),
        (
            ".claude/skills/pruefe-migrationscontrolling/SKILL.md",
            ".agents/skills/pruefe-migrationscontrolling/SKILL.md",
        ),
        (
            ".claude/skills/aktuartest-durchfuehren/SKILL.md",
            ".agents/skills/aktuartest-durchfuehren/SKILL.md",
        ),
        (
            ".claude/skills/integriere-migrationsinkrement/SKILL.md",
            ".agents/skills/integriere-migrationsinkrement/SKILL.md",
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




def test_migrations_skills_nennen_die_tragenden_regeln() -> None:
    """Das Stage-1-Know-how ist versioniertes Repo-Artefakt, kein
    Session-Prompt: die Kernregeln muessen im Skill stehen."""
    extraktion = _read(".claude/skills/extrahiere-quellfragment/SKILL.md")
    assert "GENAU EINE Quelle" in extraktion
    assert "nicht_belegt" in extraktion
    assert "model_json_schema" in extraktion          # Schema generiert, nie kopiert
    assert "KEINE Vorschrift" in extraktion           # unisex-Regel
    runbook = _read(".claude/skills/migrationsfall-durchfuehren/SKILL.md")
    assert "vorlaeufig=True" in runbook
    assert "gate_entscheid" in runbook
    assert "faelle/archiv/baldrian-klv-tg2015" in runbook      # Referenzfall (archiviert)
    assert "STOPP" in runbook                         # Abbruchkriterien


def test_rollen_skills_tragen_ihre_haerte_grenzen() -> None:
    """Die Skill-Architektur lebt: jeder Rollen-Skill traegt Auftrag UND
    Grenze; die nicht verhandelbaren Kerne sind festgehalten."""
    entwickler = _read(".claude/skills/entwickle-im-zielsystem/SKILL.md")
    assert "NICHT verhandelbar" in entwickler
    assert "Schichtenkarte" in entwickler
    assert "Knoten-Annotation" in entwickler
    assert "Don't ship without tests" in entwickler
    assert "STOPP-Kriterien" in entwickler
    tester = _read(".claude/skills/teste-adversarial/SKILL.md")
    assert "WIDERLEGT" in tester
    assert "Mutations-Denken" in tester
    assert "f(x)==f(x)" in tester
    doku = _read(".claude/skills/dokumentiere-system/SKILL.md")
    assert "Generiert schlaegt handgeschrieben" in doku
    assert "EIN Zuhause" in doku
    konflikt = _read(".claude/skills/bereite-fachkonflikt-auf/SKILL.md")
    assert "du entscheidest NICHT" in konflikt
    assert "vorlaeufig=True" in konflikt
    assert "Auswirkungsanalyse" in konflikt
    controlling = _read(
        ".claude/skills/pruefe-migrationscontrolling/SKILL.md"
    )
    assert "du rechnest NIE selbst" in controlling
    assert "A-M4" in controlling
    assert "NIE" in controlling and "aufgeweicht" in controlling  # Toleranzen
    aktuartest = _read(".claude/skills/aktuartest-durchfuehren/SKILL.md")
    assert "du rechnest NIE selbst" in aktuartest
    assert "A-M1" in aktuartest
    assert "NIE" in aktuartest and "aufgeweicht" in aktuartest
    assert "Golden-Master-Tests" in aktuartest             # Ausbaustufe festgehalten
    assert "Stichprobe" in aktuartest
    ci = _read(".claude/skills/integriere-migrationsinkrement/SKILL.md")
    assert "ADR-007" in ci
    assert "Branch je INKREMENT" in ci
    assert "Push macht der Mensch" in ci
    assert "git add -A" in ci
    # Rollen-Katalog und Skills bleiben synchron:
    katalog = _read("docs/architektur/skill-architektur.md")
    for name in ("migrationsfall-durchfuehren", "extrahiere-quellfragment",
                 "entwickle-im-zielsystem", "teste-adversarial",
                 "dokumentiere-system", "bereite-fachkonflikt-auf",
                 "author-rechner-toolbox-gate", "pruefe-migrationscontrolling",
                 "aktuartest-durchfuehren",
                 "integriere-migrationsinkrement"):
        assert name in katalog, name
        assert Path(f".claude/skills/{name}/SKILL.md").is_file(), name
