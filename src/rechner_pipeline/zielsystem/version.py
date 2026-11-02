"""Versionskennung des Zielvertrags (ADR-030).

Drei Zahlen wie beim Gate-Vertrag (ADR-012): Die Hauptversion wechselt,
wenn eine Implementierung, die bisher konform war, es nicht mehr ist; die
Nebenversion, wenn der Vertrag etwas Neues verlangt oder beschreibt; die
dritte Zahl bei Berichtigungen ohne Folgen fuer Implementierungen.

Eine Implementierung nennt die Vertragsversion, die sie erfuellt, als
eigene Aussage (kein Import dieser Konstante): Erst dann ist die
Vertraeglichkeitspruefung eine Pruefung.

Knoten: system/zielsystem
"""

from __future__ import annotations

from typing import Tuple

#: Die Version des Vertrags, den dieses Paket beschreibt. Stufe 0: Geruest.
VERTRAG_VERSION = "0.1.0"


def zerlege(version: str) -> Tuple[int, int, int]:
    """``"1.2.3"`` -> ``(1, 2, 3)``; alles andere ist ein ValueError."""
    teile = version.split(".")
    if len(teile) != 3 or not all(t.isdigit() for t in teile):
        raise ValueError(f"keine Vertragsversion: {version!r} (erwartet HAUPT.NEBEN.PATCH)")
    return int(teile[0]), int(teile[1]), int(teile[2])


def vertraeglich(angeboten: str, verlangt: str = VERTRAG_VERSION) -> bool:
    """Ob eine Implementierung, die ``angeboten`` erfuellt, den Vertrag
    ``verlangt`` erfuellt: gleiche Haupt- und Nebenversion. Die dritte
    Zahl ist frei."""
    return zerlege(angeboten)[:2] == zerlege(verlangt)[:2]
