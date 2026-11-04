"""Die Faehigkeiten des Zielvertrags und sein Wurzelprotokoll (ADR-030).

Der Katalog nennt die fuenf Faehigkeiten, die das Tool von einem
Zielsystem braucht, so wie die Messung der Kanten sie ergeben hat. Ein
Protokoll je Faehigkeit kommt mit der Stufe, die sie an den Vertrag
bindet (``PROTOKOLL_JE_FAEHIGKEIT``); bis dahin darf ein Zielsystem die
Faehigkeit nicht anbieten, weil der Vertrag nicht sagt, was sie ist.

Das Wurzelprotokoll ``Zielsystem`` ist strukturell (``typing.Protocol``),
wie ``InputAdapter`` fuer die Quellen: Die Implementierung importiert
nichts aus dem Tool, sie hat nur die verlangte Form.

Knoten: system/zielsystem
"""

from __future__ import annotations

from types import MappingProxyType
from typing import FrozenSet, Mapping, Protocol, runtime_checkable

from rechner_pipeline.zielsystem.bestandsdaten import Bestandsdaten
from rechner_pipeline.zielsystem.bewertung import Bewertung
from rechner_pipeline.zielsystem.rechnungsgrundlagen import Rechnungsgrundlagen

__all__ = ["FAEHIGKEITEN", "PROTOKOLL_JE_FAEHIGKEIT", "Zielsystem"]

#: Die fuenf Faehigkeiten (ADR-030, Messung vom 22.10.2026): Name -> was
#: das Tool vom Zielsystem braucht.
FAEHIGKEITEN: Mapping[str, str] = MappingProxyType({
    "rechnungsgrundlagen": "den wirksamen Parametersatz je Vertrag, Tafeln, Produkte",
    "bestandsdaten": "Bestand lesen und schreiben, Manifest",
    "bewertung": "Werte und Verlauf je Vertrag, Vorgaenge, Korrekturschicht",
    "zugang": "aus gelieferten Werten den Anfangszustand im Zielsystem ableiten",
    "bestandspruefung": "P-B1 auf einem Bestand fahren",
})

#: Faehigkeit -> Protokoll, das der Vertrag in dieser Version dafuer
#: beschreibt. Stufe 1: ``rechnungsgrundlagen``; Stufe 2: ``bewertung``;
#: vorgezogenes Stueck von Stufe 3: ``bestandsdaten``.
#: Eine Faehigkeit ohne Protokoll darf kein Zielsystem anbieten
#: (Konformitaet).
PROTOKOLL_JE_FAEHIGKEIT: Mapping[str, type] = MappingProxyType({
    "rechnungsgrundlagen": Rechnungsgrundlagen,
    "bewertung": Bewertung,
    "bestandsdaten": Bestandsdaten,
})


@runtime_checkable
class Zielsystem(Protocol):
    """Was jedes Zielsystem hat: einen Namen, die Vertragsversion, die es
    erfuellt, und die Faehigkeiten, die es anbietet."""

    #: Kurze Kennung, ``[a-z][a-z0-9_]*`` (z. B. ``"plv"``).
    name: str
    #: Die Vertragsversion, die die Implementierung erfuellt (eigene
    #: Aussage, siehe ``version``).
    vertragsversion: str

    def faehigkeiten(self) -> FrozenSet[str]:
        """Die angebotenen Faehigkeiten, Namen aus ``FAEHIGKEITEN``."""
        ...

    def faehigkeit(self, name: str) -> object:
        """Die Implementierung einer angebotenen Faehigkeit; ``KeyError``
        fuer jede nicht angebotene."""
        ...
