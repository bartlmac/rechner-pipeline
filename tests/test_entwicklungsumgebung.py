"""Die Referenzumgebung (deploy/dev) und die CI nehmen dieselbe Eingabe.

Was ein Test hier halten kann, ist Mechanik: dass das Entwicklungs-Image
denselben Interpreter und dieselbe Pin-Datei nimmt wie die CI, dass die
Devcontainer-Definition auf genau dieses Dockerfile zeigt, und dass die
Zeilenende-Regel die byteweise verglichenen Lieferungen und Fixturen
ausnimmt. Ob das Image baut, prueft kein Unit-Test — das tut, wer es
benutzt.

Knoten: system/architektur
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _lies(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


def test_entwicklungs_image_nimmt_interpreter_und_pins_der_ci():
    dockerfile = _lies("deploy/dev/Dockerfile")
    workflow = _lies(".github/workflows/tests.yml")
    ci_python = re.search(r'python-version:\s*"(\d+\.\d+)"', workflow).group(1)
    assert f"FROM python:{ci_python}-slim" in dockerfile
    assert "requirements-dev.txt" in dockerfile
    assert "--no-deps" in _lies("deploy/dev/entrypoint.sh")
    # Kein zweiter Aufloesungsweg: pyproject-Extras werden nicht installiert.
    assert '".[dev]"' not in dockerfile and "[dev]" not in dockerfile


def test_devcontainer_zeigt_auf_das_entwicklungs_image():
    definition = json.loads(_lies(".devcontainer/devcontainer.json"))
    assert definition["build"]["dockerfile"] == "../deploy/dev/Dockerfile"
    assert definition["workspaceFolder"] == "/workspace"
    assert "--no-deps" in definition["postCreateCommand"]


def test_zeilenenden_regel_schont_lieferungen_und_fixturen():
    attribute = _lies(".gitattributes")
    assert "* text=auto eol=lf" in attribute
    for pfad in ("lieferungen/** -text", "tests/fixtures/** -text"):
        assert pfad in attribute, pfad
    # Die Pin-Datei der Laufzeit ist unberuehrt: Laufzeit-Image und
    # Entwicklungs-Image bleiben zwei Dateien mit zwei Zwecken.
    assert "requirements.txt" in _lies("deploy/plv/Dockerfile")
