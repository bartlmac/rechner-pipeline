"""Die PLV erfuellt das Wurzelprotokoll des Zielvertrags (ADR-030).

Die Vertragsversion steht hier als eigene Aussage, nicht als Import aus
dem Vertrag: Wechselt der Vertrag, muss die PLV ausdruecklich nachziehen,
und bis dahin ist sie nicht konform (``zielsystem.konformitaet``).

Stufe 1: die PLV bietet die Rechnungsgrundlagen an
(``plv.rechnungsgrundlagen``).

Knoten: system/zielsystem
"""

from __future__ import annotations

from typing import FrozenSet

from rechner_pipeline.plv.rechnungsgrundlagen import PLVRechnungsgrundlagen

__all__ = ["PLV"]

_FAEHIGKEITEN = {
    "rechnungsgrundlagen": PLVRechnungsgrundlagen,
}


class PLV:
    """Die PLV als Zielsystem."""

    name = "plv"
    vertragsversion = "0.2.0"

    def faehigkeiten(self) -> FrozenSet[str]:
        return frozenset(_FAEHIGKEITEN)

    def faehigkeit(self, name: str) -> object:
        try:
            return _FAEHIGKEITEN[name]()
        except KeyError:
            raise KeyError(f"die PLV bietet die Faehigkeit {name!r} nicht an") from None
