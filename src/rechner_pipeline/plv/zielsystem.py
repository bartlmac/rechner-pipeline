"""Die PLV erfuellt das Wurzelprotokoll des Zielvertrags (ADR-030).

Die Vertragsversion steht hier als eigene Aussage, nicht als Import aus
dem Vertrag: Wechselt der Vertrag, muss die PLV ausdruecklich nachziehen,
und bis dahin ist sie nicht konform (``zielsystem.konformitaet``).

Knoten: system/zielsystem
"""

from __future__ import annotations

from typing import FrozenSet

__all__ = ["PLV"]


class PLV:
    """Die PLV als Zielsystem. Stufe 0: keine Faehigkeit angeboten."""

    name = "plv"
    vertragsversion = "0.1.0"

    def faehigkeiten(self) -> FrozenSet[str]:
        return frozenset()

    def faehigkeit(self, name: str) -> object:
        raise KeyError(f"die PLV bietet die Faehigkeit {name!r} nicht an")
