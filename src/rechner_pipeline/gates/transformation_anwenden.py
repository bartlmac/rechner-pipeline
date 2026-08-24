"""Registrierte Transformationsquelle deterministisch anwenden.

Die Ontologie kennt den Mapping-Vertrag, darf aber architektonisch nicht auf
den Fallarbeitsbereich zugreifen. Diese schmale Orchestrierung verbindet beide
bestehenden Grenzen: Erst loest ``fall.eingang_datei`` den in der Spec
benannten Eingang samt Register- und Integritaetspruefung auf, dann wendet die
Ontologie das Mapping auf exakt diesen neu gelesenen Bytes an. Eine frei
uebergebbare Datei ist deshalb kein Erfolgsweg der Produzenten-API.

Knoten: klv
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

from rechner_pipeline import fall as fall_mod
from rechner_pipeline.ontologie.transformation import (
    TransformationsSpec,
    _wende_registrierte_datei_an,
)


def wende_an(
    spec: TransformationsSpec,
    fall: Path,
    *,
    trenner: str = ";",
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Spec ausschliesslich auf ihrer registrierten Fallquelle anwenden."""
    quelle_pfad = fall_mod.eingang_datei(Path(fall), spec.quelle_datei)
    return _wende_registrierte_datei_an(spec, quelle_pfad, trenner=trenner)
