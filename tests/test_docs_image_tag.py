"""Die Doku-Engine bekommt ihr Versions-Tag aus der FROM-Zeile.

Steht die Quarto-Version in ``docs-image.yml`` fest, landet nach einem
Versionssprung im Dockerfile das neue Image unter dem Tag der alten
Version. Der Workflow liest die Version deshalb aus der FROM-Zeile von
``werkzeuge/engine/Dockerfile``. Die Tests fahren genau das Skript des
Workflow-Schritts, damit Workflow und Dockerfile nicht auseinanderlaufen.

Knoten: system/architektur
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "docs-image.yml"
DOCKERFILE = ROOT / "werkzeuge" / "engine" / "Dockerfile"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash fehlt")


def _skript_des_schritts() -> str:
    """Der ``run``-Block des Schritts mit ``id: version``, ausgerueckt."""
    zeilen = WORKFLOW.read_text(encoding="utf-8").splitlines()
    start = zeilen.index("        id: version")
    run = start + 1
    assert zeilen[run].strip() == "run: |", zeilen[run]
    block = []
    for zeile in zeilen[run + 1:]:
        if zeile and not zeile.startswith(" " * 10):
            break
        block.append(zeile[10:])
    return "\n".join(block) + "\n"


def _fahre(wurzel: Path, tmp_path: Path) -> tuple[int, str]:
    ausgabe = tmp_path / "github_output"
    ausgabe.write_text("", encoding="utf-8")
    lauf = subprocess.run(
        ["bash", "-c", _skript_des_schritts()],
        cwd=wurzel, env={"PATH": "/usr/bin:/bin", "GITHUB_OUTPUT": str(ausgabe)},
        capture_output=True, text=True, timeout=30,
    )
    return lauf.returncode, ausgabe.read_text(encoding="utf-8")


def test_workflow_schreibt_keine_quarto_version_fest():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert not re.search(r"quarto-\d", text), "Versions-Tag fest im Workflow"
    assert "rechner-pipeline-docs:quarto-${{ steps.version.outputs.quarto }}" in text


def test_schritt_liest_die_version_aus_der_from_zeile(tmp_path):
    from_zeilen = [z for z in DOCKERFILE.read_text(encoding="utf-8").splitlines()
                   if z.startswith("FROM ")]
    assert len(from_zeilen) == 1, from_zeilen
    erwartet = from_zeilen[0].rsplit(":", 1)[1]
    code, ausgabe = _fahre(ROOT, tmp_path)
    assert code == 0
    assert ausgabe == f"quarto={erwartet}\n"


@pytest.mark.parametrize("from_zeile", [
    "FROM ghcr.io/quarto-dev/quarto:latest",
    "FROM ghcr.io/quarto-dev/quarto@sha256:" + "0" * 64,
    "FROM ghcr.io/quarto-dev/quarto:1.6.42\nFROM ghcr.io/quarto-dev/quarto:1.10.20",
])
def test_schritt_haelt_ohne_eindeutige_version(tmp_path, from_zeile):
    wurzel = tmp_path / "baum"
    engine = wurzel / "werkzeuge" / "engine"
    engine.mkdir(parents=True)
    (engine / "Dockerfile").write_text(from_zeile + "\nENTRYPOINT [\"quarto\"]\n", encoding="utf-8")
    code, ausgabe = _fahre(wurzel, tmp_path)
    assert code != 0
    assert ausgabe == ""
