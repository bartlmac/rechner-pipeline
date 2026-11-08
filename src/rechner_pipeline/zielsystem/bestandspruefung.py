"""Bestandspruefung als Faehigkeit des Zielvertrags (ADR-030, Stufe 4).

P-B1 bleibt die eine Engine der Fuehrung. Das Tool erhaelt deren gepruefte
Tabellen und Befunde, damit zwischen Pruefung und Verwendung kein zweiter
Lesevorgang entsteht.

Knoten: system/zielsystem, klv, bu
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, FrozenSet, List, Mapping, Protocol, runtime_checkable

__all__ = [
    "Bestandspruefung", "Fortschreibungspruefung", "ManifestNachrechnung",
    "PB1Pruefung", "Rollenbeschreibung",
]


@dataclass(frozen=True)
class Rollenbeschreibung:
    """Alle von P-B1 angenommenen Rollen und ihre Laufdateien."""

    rollen: FrozenSet[str]
    dateien: Mapping[str, str]


@dataclass(frozen=True)
class PB1Pruefung:
    """Pruefurteil und exakt die Tabellen, ueber deren Bytes es erging."""

    tabellen: Mapping[str, Any]
    geprueft: Mapping[str, int]
    fehler: List[dict]
    bedienfehler: List[dict]


@dataclass(frozen=True)
class Fortschreibungspruefung:
    horizont: date | None
    fehler: List[str]


@dataclass(frozen=True)
class ManifestNachrechnung:
    daten: Mapping[str, Any] | None
    fehler: List[str]


@runtime_checkable
class Bestandspruefung(Protocol):
    """Fachliche P-B1-Antworten ohne Implementierungstyp im Gate."""

    def rollenbeschreibung(self) -> Rollenbeschreibung:
        """Die Rollen aus derselben Engine wie die Pruefung liefern."""
        ...

    def pruefe_eingaenge(
        self, eingaben: Mapping[str, Path], *, bis: date | None = None,
        manifest: Mapping[str, Any] | None = None,
    ) -> PB1Pruefung:
        """Benannte Eingaben einmal lesen, pruefen und die Tabellen zurueckgeben."""
        ...

    def pruefe_fortschreibung(
        self, verzeichnis: Path, config: Path,
    ) -> Fortschreibungspruefung:
        """Lauf, Config und belegten Horizont gemeinsam pruefen."""
        ...

    def manifest_fuer_nachrechnung(
        self, portfolio: Path, erwarteter_sha256: str | None,
    ) -> ManifestNachrechnung:
        """Das benachbarte Manifest an den Hash des P-B1-Belegs halten."""
        ...

    def bestandszeilen(self, pfad: Path) -> int:
        """Zeilen der Bestandstabelle unabhaengig vom behaupteten Zaehler lesen."""
        ...
