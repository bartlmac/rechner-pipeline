"""Die eine Stelle, an der das Tool die Implementierung des Zielsystems
kennt (ADR-030).

Statischer Import, damit die Schichtenkarte die Kante sieht: Sie ist die
einzige Kante aus dem Tool in die Vorzeige, die der Vertrag vorsieht; die
uebrigen 36 sind die Altlast, die je Stufe schrumpft
(``ontologie.code_karte.TOOL_NACH_VORZEIGE_ERLAUBT``). Dynamisches Laden
faellt aus, weil die Karte einen berechneten Importnamen als Befund
zaehlt.

Knoten: system/zielsystem
"""

from __future__ import annotations

from rechner_pipeline.plv.zielsystem import PLV
from rechner_pipeline.zielsystem.vertrag import Zielsystem

__all__ = ["zielsystem"]


def zielsystem() -> Zielsystem:
    """Das Zielsystem, das dieses Tool anspricht: die PLV."""
    return PLV()
