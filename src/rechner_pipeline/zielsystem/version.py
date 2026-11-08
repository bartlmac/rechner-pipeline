"""Versionskennung des Zielvertrags (ADR-030).

Drei Zahlen wie beim Gate-Vertrag (ADR-012): Die Hauptversion wechselt,
wenn eine Implementierung, die bisher konform war, es nicht mehr ist; die
Nebenversion, wenn der Vertrag etwas Neues verlangt oder beschreibt; die
dritte Zahl bei Berichtigungen ohne Folgen fuer Implementierungen.
Die Unterscheidung von Haupt- und Nebenversion erklaert heute nur den
Anlass eines Sprungs; ``vertraeglich`` verlangt beide gleich, weil in
den Stufen 0 bis 2 jede Erweiterung des Vertrags die PLV nachziehen
muss. Ob eine aeltere Nebenversion einmal als vertraeglich gelten soll,
entscheidet erst ein zweites Zielsystem.

Eine Implementierung nennt die Vertragsversion, die sie erfuellt, als
eigene Aussage (kein Import dieser Konstante): Erst dann ist die
Vertraeglichkeitspruefung eine Pruefung.

Knoten: system/zielsystem
"""

from __future__ import annotations

from typing import Tuple

#: Die Version des Vertrags, den dieses Paket beschreibt. 0.1.0 war das
#: Geruest (Stufe 0), 0.2.0 beschrieb die Rechnungsgrundlagen (Stufe 1),
#: 0.3.0 beschreibt die Bewertung (Stufe 2), 0.4.0 die lesende
#: Verankerungsrolle als vorgezogenes Stueck von Stufe 3; 0.5.0 die
#: Bestandsdateien und Laufmanifeste der Stufe 3.
VERTRAG_VERSION = "0.5.0"


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
