"""Regression tests for checked-in agent workflow instructions.

Knoten: system/skills
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def test_codex_repo_skills_match_claude_skills() -> None:
    """Codex support must not drift from the verified Claude skill bodies.

    Verglichen werden die VERZEICHNISSE, nicht eine gepflegte Liste. Die
    Liste hier zaehlte neun Paare auf und vergass das vorhandene
    ``transformiere-quellbestand``: eine einseitige Aenderung daran blieb
    gruen, waehrend AGENTS.md die Paritaet als test-erzwungen ausweist.
    Eine Handliste ist genau so lange vollstaendig, bis jemand einen Skill
    hinzufuegt -- und dann sagt sie nichts mehr, ohne rot zu werden.
    """
    claude_wurzel = REPO_ROOT / ".claude" / "skills"
    codex_wurzel = REPO_ROOT / ".agents" / "skills"

    def _dateien(wurzel: Path) -> set:
        return {p.relative_to(wurzel) for p in wurzel.rglob("*") if p.is_file()}

    claude_dateien, codex_dateien = _dateien(claude_wurzel), _dateien(codex_wurzel)
    assert claude_dateien, "keine Skills gefunden — Pfad falsch?"
    nur_claude = sorted(str(p) for p in claude_dateien - codex_dateien)
    nur_codex = sorted(str(p) for p in codex_dateien - claude_dateien)
    assert not nur_claude, f"nur unter .claude/skills/: {nur_claude}"
    assert not nur_codex, f"nur unter .agents/skills/: {nur_codex}"

    unterschiedlich = sorted(
        str(rel) for rel in claude_dateien
        if (claude_wurzel / rel).read_bytes() != (codex_wurzel / rel).read_bytes()
    )
    assert not unterschiedlich, f"Inhalt weicht ab: {unterschiedlich}"


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
    Grenze; die nicht verhandelbaren Kerne sind verankert."""
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
    abnahme = _read(".claude/skills/pruefe-migrationsabnahme/SKILL.md")
    assert "du rechnest NIE selbst" in abnahme
    assert "G-2" in abnahme
    assert "NIE" in abnahme and "aufgeweicht" in abnahme   # Toleranzen
    assert "Golden-Master-Tests" in abnahme                # Ausbau-Anker
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
                 "author-rechner-toolbox-gate", "pruefe-migrationsabnahme",
                 "integriere-migrationsinkrement"):
        assert name in katalog, name
        assert Path(f".claude/skills/{name}/SKILL.md").is_file(), name
