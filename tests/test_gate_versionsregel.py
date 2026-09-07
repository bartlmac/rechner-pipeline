"""Versionierungsregel der Gates (ADR-012, Nachtrag 2026-09-05).

Die Regel selbst (Major bei geaenderter Akzeptanzmenge) kann kein Test
pruefen — er sieht die Akzeptanzmenge nicht. Was er halten kann: dass
Version und README-Zeile nicht auseinanderlaufen (T21-09: P-B1 trug in
Code und README 2.1.0, waehrend die Akzeptanzmenge laengst eine andere
war — die Zeile muss den Sprung erzaehlen, und dazu muss sie stimmen),
und dass die Regel dort steht, wo Gate-Autoren lesen.

Knoten: system/gates
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ZEILE = re.compile(r"^\| ([PA]-[A-Z0-9]+) \(Version `([^`]+)`\) \| `gates\.([a-z_]+)` \|")


def _readme_versionen():
    treffer = []
    for zeile in (REPO_ROOT / "README.md").read_text(encoding="utf-8").splitlines():
        m = ZEILE.match(zeile)
        if m:
            treffer.append(m.groups())
    return treffer


def test_readme_zeile_und_gate_version_stimmen_ueberein():
    treffer = _readme_versionen()
    assert treffer, "keine versionierte Gate-Zeile im README gefunden — Muster geaendert?"
    for gate, version, modul in treffer:
        m = importlib.import_module(f"rechner_pipeline.gates.{modul}")
        assert m.GATE_VERSION == version, (gate, modul, m.GATE_VERSION, version)


def test_jede_gate_version_ist_semver():
    for pfad in (REPO_ROOT / "src" / "rechner_pipeline" / "gates").glob("*.py"):
        for m in re.finditer(r'^GATE_VERSION = "([^"]+)"', pfad.read_text(encoding="utf-8"), re.M):
            assert re.fullmatch(r"\d+\.\d+\.\d+", m.group(1)), (pfad.name, m.group(1))


def test_die_regel_steht_bei_adr_skill_und_readme():
    adr = (REPO_ROOT / "docs/architektur/adr-012-gate-namensordnung.md").read_text(encoding="utf-8")
    skill = (REPO_ROOT / ".claude/skills/author-rechner-toolbox-gate/SKILL.md").read_text(encoding="utf-8")
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    for text in (adr, skill, readme):
        assert "Akzeptanzmenge" in text and "Major" in text
