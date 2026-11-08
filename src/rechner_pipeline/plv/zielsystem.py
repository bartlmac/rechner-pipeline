"""Die PLV erfuellt das Wurzelprotokoll des Zielvertrags (ADR-030).

Die Vertragsversion steht hier als eigene Aussage, nicht als Import aus
dem Vertrag: Wechselt der Vertrag, muss die PLV ausdruecklich nachziehen,
und bis dahin ist sie nicht konform (``zielsystem.konformitaet``).

Stufe 1: Rechnungsgrundlagen; Stufe 2: Bewertung; Stufe 3: Bestandsdaten;
Stufe 4: Bestandspruefung.

Knoten: system/zielsystem
"""

from __future__ import annotations

from typing import FrozenSet

from rechner_pipeline.plv.bestandsdaten import PLVBestandsdaten
from rechner_pipeline.plv.bestandspruefung import PLVBestandspruefung
from rechner_pipeline.plv.bewertung import PLVBewertung
from rechner_pipeline.plv.rechnungsgrundlagen import PLVRechnungsgrundlagen

__all__ = ["PLV"]

_FAEHIGKEITEN = {
    "rechnungsgrundlagen": PLVRechnungsgrundlagen,
    "bewertung": PLVBewertung,
    "bestandsdaten": PLVBestandsdaten,
    "bestandspruefung": PLVBestandspruefung,
}


class PLV:
    """Die PLV als Zielsystem."""

    name = "plv"
    vertragsversion = "0.6.0"

    def faehigkeiten(self) -> FrozenSet[str]:
        return frozenset(_FAEHIGKEITEN)

    def faehigkeit(self, name: str) -> object:
        try:
            return _FAEHIGKEITEN[name]()
        except KeyError:
            raise KeyError(f"die PLV bietet die Faehigkeit {name!r} nicht an") from None
