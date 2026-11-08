"""Bestandsdaten-Faehigkeit des Zielvertrags (ADR-030).

Sie bindet Tabellen, Laufmanifeste und den bereits gebundenen Config-Text.
Die Verankerungsrolle bleibt eine Aussage ueber uebergebene Bytes; die
Fuehrungsansicht enthaelt keine PLV-Config und trifft keine Abnahmeentscheidung.

Knoten: system/zielsystem
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence, Tuple, runtime_checkable

__all__ = [
    "Bestandsdaten", "BestandsdatenFehler", "Erfahrungsannahmen",
    "Erfahrungsrate", "Fuehrungsansicht", "Fuehrungsgeneration", "Laufmanifest",
    "Verankerungsrolle",
]


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


class Erfahrungsrate(Protocol):
    """Die affine Rate einer Ereignisart, ohne ihren Zielsystemtyp."""

    a: float
    b: float

    def __call__(self, erste_ordnung: float) -> float:
        ...


@dataclass(frozen=True)
class Erfahrungsannahmen:
    """Die fuer die Ereignisbindung benoetigten Annahmen dritter Ordnung."""

    tod: Erfahrungsrate
    storno: Erfahrungsrate
    beitragsfreistellung: Erfahrungsrate
    erhoehung: Erfahrungsrate
    herabsetzung: Erfahrungsrate
    teilkuendigung: Erfahrungsrate
    invalidisierung: Erfahrungsrate
    reaktivierung: Erfahrungsrate
    aktivensterblichkeit: Erfahrungsrate
    invalidensterblichkeit: Erfahrungsrate
    erh_prozent: float
    red_anteil: float
    tk_anteil: float


@dataclass(frozen=True)
class Fuehrungsgeneration:
    name: str
    tarifwerk_daten: Mapping[str, Any]

    def tarifwerk(self) -> Mapping[str, Any]:
        """Den belegten Satz liefern, wie ihn die Fuehrung vergleicht."""
        return self.tarifwerk_daten


@dataclass(frozen=True)
class Fuehrungsansicht:
    """Validierte Config als neutrale Fuehrungswerte und gebundener Text.

    Der Text dient der PLV-internen Tarifzellenaufloesung; er ist der
    bereits eingangsgebundene Inhalt und kein erneut zu lesender Pfad.
    """

    generationen: Tuple[Fuehrungsgeneration, ...]
    annahmen: Erfahrungsannahmen
    config_text: str = field(repr=False)


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

    def fuehrungsansicht_aus_text(self, text: str) -> Fuehrungsansicht:
        """Gebundenen Config-Text validieren und Fuehrungswerte liefern.

        Ungueltige Config: ``BestandsdatenFehler`` mit dem Befund.
        """
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
