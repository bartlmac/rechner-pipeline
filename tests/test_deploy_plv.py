"""deploy/plv: Image, Compose, Timer und Workflow tragen den Vertrag des Konzepts.

Fachkonzept docs/simulation/tagesbetrieb.md, Abschnitt 8. Die Dateien
sind Text, kein Code — was sie zusichern (Installation wie die CI, kein
Netz, unprivilegiert, 23:00 mit Persistent, zwei Tags), laesst sich
trotzdem pruefen, und eine Abweichung faellt hier auf statt beim
naechsten Deployment.

Knoten: system/betrieb
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEPLOY = REPO / "deploy" / "plv"


def _text(name: str) -> str:
    return (DEPLOY / name).read_text(encoding="utf-8")


def test_dockerfile_installiert_wie_die_ci_und_laeuft_unprivilegiert():
    ci = (REPO / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    docker = _text("Dockerfile")
    assert "pip install -r requirements-dev.txt" in ci
    assert "requirements.txt" in docker and "requirements-dev.txt" not in docker
    assert re.search(r"pip install[^\n]* -e \. --no-deps", docker)
    assert re.search(r"^FROM python:3\.11-slim", docker, re.M)
    assert re.search(r"^USER plv", docker, re.M)
    assert '"rechner_pipeline.betrieb.tageslauf"' in docker
    for verboten in ("pytest", "hypothesis", "SECRET", "TOKEN", "KEY="):
        assert verboten not in docker


def test_compose_ohne_netz_mit_datenvolume():
    compose = _text("compose.yml")
    assert "network_mode: none" in compose
    assert "./daten:/daten" in compose
    assert "rechner-pipeline-plv:${IMAGE_TAG" in compose
    assert "PLV_IMAGE_DIGEST" in compose and "PLV_IMAGE_TAG" in compose
    beispiel = _text("env.beispiel")
    for schluessel in ("GHCR_OWNER", "IMAGE_TAG", "IMAGE_DIGEST", "ZEITZONE"):
        assert re.search(rf"^{schluessel}=", beispiel, re.M), schluessel


def test_timer_um_23_uhr_persistent():
    timer = _text("tageslauf.timer")
    assert re.search(r"^OnCalendar=\*-\*-\* 23:00:00", timer, re.M)
    assert re.search(r"^Persistent=true", timer, re.M)
    service = _text("tageslauf.service")
    assert "docker compose run --rm tageslauf" in service
    assert re.search(r"^Type=oneshot", service, re.M)


def test_workflow_baut_bei_push_auf_main_mit_zwei_tags():
    workflow = (REPO / ".github" / "workflows" / "plv-image.yml").read_text(encoding="utf-8")
    assert "branches: [main]" in workflow
    assert "file: deploy/plv/Dockerfile" in workflow
    assert "rechner-pipeline-plv:latest" in workflow
    assert "rechner-pipeline-plv:${{ steps.kurz.outputs.sha }}" in workflow
    assert "GIT_SHA=${{ github.sha }}" in workflow


def test_readme_beschreibt_die_erstbefuellung_und_die_ablage():
    readme = _text("README.md")
    for pflicht in ("Erstbefuellung", "uebernahme/", "stand/", "journal/protokoll.jsonl",
                    "von AUSSEN ins Volume", "nicht erfasst",
                    "abschluesse/", "betrieb.tageslauf", "betrieb.uebernahme",
                    "systemctl --user enable --now tageslauf.timer", "Exit 3"):
        assert pflicht in readme, pflicht
