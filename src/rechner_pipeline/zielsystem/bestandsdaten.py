"""Bestandsdaten-Faehigkeit des Zielvertrags (ADR-030).

Die erste Teilfaehigkeit meldet allein, ob die gebundenen Bytes eines
Migrationsbestands eine Verankerung tragen. Sie liest keine Pfade und
liefert keine Schichtwerte oder Abnahmeentscheidung.

Knoten: system/zielsystem
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable

__all__ = ["Bestandsdaten", "BestandsdatenFehler", "Laufmanifest", "Verankerungsrolle"]


class BestandsdatenFehler(ValueError):
    """Die gebundenen Bestandsdaten belegen ihre Verankerungsrolle nicht."""


@dataclass(frozen=True)
class Verankerungsrolle:
    vorhanden: bool
    bestand_sha256: str
    verankerung_sha256: str | None


@dataclass(frozen=True)
class Laufmanifest:
    """Gepruefter Inhalt und Hash der genau einmal gelesenen Bytes."""

    daten: Mapping[str, Any]
    sha256: str


@runtime_checkable
class Bestandsdaten(Protocol):
    """Bestandsdateien und Laufmanifest ohne Implementierungstypen binden."""

    def tabelle_aus_bytes(
        self, daten: bytes, *, erwartete_spalten: Sequence[str] | None = None,
    ) -> Any:
        """Die bereits gebundenen Bytes mit Spalten- und Typpruefung lesen."""
        ...

    def schreibe_tabelle(self, tabelle: Any, pfad: Path, *, exklusiv: bool = False) -> Path:
        """Eine Tabelle atomar, bei Bedarf nur einmal, veroeffentlichen."""
        ...

    def rollen_dateien(self) -> Mapping[str, str]:
        """Die Zuordnung von Eingangsrollen zu Dateinamen liefern."""
        ...

    def laufmanifest_lesen(self, pfad: Path) -> Laufmanifest:
        """Inhalt und SHA-256 aus denselben Manifestbytes bestimmen."""
        ...

    def laufmanifest_schreiben(
        self, lauf: Path, *, horizont: date, neuzugang_ab: date | None,
        config_pfad: Path, ausgaben: Sequence[Path],
        eingaben: Mapping[str, Path] | None = None, laufart: str,
    ) -> Path:
        """Das Manifest nach den gebundenen Ausgaben schreiben."""
        ...

    def verankerungsrolle(
        self, *, manifest_bytes: bytes | None, bestand_bytes: bytes,
        verankerung_bytes: bytes | None,
    ) -> Verankerungsrolle:
        """Rolle aus Manifest und genau den verarbeiteten Datei-Bytes lesen.

        ``BestandsdatenFehler`` bei fehlender Rolle/Datei, abweichenden
        Hashes, unlesbarer oder nicht vollstaendig spaltengetreuer
        Verankerungsdatei oder falschem Erzeuger.
        Fehlen Manifest und Verankerungsdatei beide, ist die Rolle leer.
        """
        ...
