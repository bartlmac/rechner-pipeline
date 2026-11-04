"""Lesende Bestandsdaten-Faehigkeit des Zielvertrags (ADR-030).

Die erste Teilfaehigkeit meldet allein, ob die gebundenen Bytes eines
Migrationsbestands eine Verankerung tragen. Sie liest keine Pfade und
liefert keine Schichtwerte oder Abnahmeentscheidung.

Knoten: system/zielsystem
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

__all__ = ["Bestandsdaten", "BestandsdatenFehler", "Verankerungsrolle"]


class BestandsdatenFehler(ValueError):
    """Die gebundenen Bestandsdaten belegen ihre Verankerungsrolle nicht."""


@dataclass(frozen=True)
class Verankerungsrolle:
    vorhanden: bool
    bestand_sha256: str
    verankerung_sha256: str | None


@runtime_checkable
class Bestandsdaten(Protocol):
    """Die vorgezogene, rein lesende Bestandsdaten-Faehigkeit."""

    def verankerungsrolle(
        self, *, manifest_bytes: bytes | None, bestand_bytes: bytes,
        verankerung_bytes: bytes | None,
    ) -> Verankerungsrolle:
        """Rolle aus Manifest und genau den verarbeiteten Datei-Bytes lesen.

        ``BestandsdatenFehler`` bei fehlender Rolle/Datei, abweichenden
        Hashes, unlesbarer Verankerungsdatei oder falschem Erzeuger.
        Fehlen Manifest und Verankerungsdatei beide, ist die Rolle leer.
        """
        ...
