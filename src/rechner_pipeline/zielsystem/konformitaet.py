"""Konformitaet: was jede Implementierung des Zielvertrags bestehen muss.

``pruefe`` liefert Befunde (leer = konform), die Tests fahren sie gegen
den Anbieter (``tests/test_zielsystem.py``). Jede Regel hat dort eine
Positivkontrolle mit einer absichtlich falschen Implementierung.

Knoten: system/zielsystem
"""

from __future__ import annotations

import re
from typing import List

from rechner_pipeline.zielsystem.version import VERTRAG_VERSION, vertraeglich, zerlege
from rechner_pipeline.zielsystem.vertrag import FAEHIGKEITEN, PROTOKOLL_JE_FAEHIGKEIT, Zielsystem

__all__ = ["pruefe"]

_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


def pruefe(zielsystem: object) -> List[str]:
    """Befunde zur Konformitaet einer Implementierung mit dem Vertrag
    ``VERTRAG_VERSION``; leer heisst konform."""
    befunde: List[str] = []
    if not isinstance(zielsystem, Zielsystem):
        return [
            f"{type(zielsystem).__name__} erfuellt das Wurzelprotokoll Zielsystem nicht "
            "(name, vertragsversion, faehigkeiten, faehigkeit)"
        ]
    name = zielsystem.name
    if not isinstance(name, str) or not _NAME.match(name):
        befunde.append(f"name {name!r} ist keine Kennung ([a-z][a-z0-9_]*)")
    version = zielsystem.vertragsversion
    try:
        zerlege(version)
    except (ValueError, AttributeError, TypeError):
        befunde.append(f"vertragsversion {version!r} ist keine Vertragsversion")
    else:
        if not vertraeglich(version, VERTRAG_VERSION):
            befunde.append(
                f"vertragsversion {version} ist mit dem Vertrag {VERTRAG_VERSION} nicht "
                "vertraeglich (gleiche Haupt- und Nebenversion verlangt)"
            )
    angeboten = zielsystem.faehigkeiten()
    if not isinstance(angeboten, frozenset):
        befunde.append(f"faehigkeiten() liefert {type(angeboten).__name__}, erwartet frozenset")
        angeboten = frozenset(angeboten)
    for unbekannt in sorted(angeboten - set(FAEHIGKEITEN)):
        befunde.append(f"bietet die unbekannte Faehigkeit {unbekannt!r} an")
    for ohne in sorted((angeboten & set(FAEHIGKEITEN)) - set(PROTOKOLL_JE_FAEHIGKEIT)):
        befunde.append(
            f"bietet {ohne!r} an, der Vertrag {VERTRAG_VERSION} beschreibt dafuer kein Protokoll"
        )
    for faehigkeit in sorted(angeboten & set(PROTOKOLL_JE_FAEHIGKEIT)):
        try:
            umsetzung = zielsystem.faehigkeit(faehigkeit)
        except KeyError:
            befunde.append(f"bietet {faehigkeit!r} an, liefert dafuer aber KeyError")
            continue
        protokoll = PROTOKOLL_JE_FAEHIGKEIT[faehigkeit]
        if not isinstance(umsetzung, protokoll):
            befunde.append(
                f"die Umsetzung von {faehigkeit!r} erfuellt das Protokoll "
                f"{protokoll.__name__} nicht"
            )
    for nicht in sorted(set(FAEHIGKEITEN) - angeboten):
        try:
            zielsystem.faehigkeit(nicht)
        except KeyError:
            continue
        befunde.append(f"liefert {nicht!r}, obwohl es die Faehigkeit nicht anbietet")
    return befunde
