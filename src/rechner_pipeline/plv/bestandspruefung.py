"""Die PLV erfuellt den Bestandspruefungs-Vertrag (ADR-030, Stufe 4).

Die eine P-B1-Engine bleibt in der Bestandsfuehrung. Ihr Urteil und ihre
gelesenen Tabellen gehen ohne zweiten Lesevorgang an das Tool.

Knoten: system/zielsystem, klv, bu
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from rechner_pipeline.zielsystem.bestandspruefung import (
    Fortschreibungspruefung, ManifestNachrechnung, PB1Pruefung,
    Rollenbeschreibung,
)

__all__ = ["PLVBestandspruefung"]


class PLVBestandspruefung:
    """P-B1-Antworten der bestehenden Bestandsfuehrung."""

    def rollenbeschreibung(self) -> Rollenbeschreibung:
        from rechner_pipeline.bestand.vorbedingungen import PB1_ROLLEN, PB1_ROLLEN_DATEIEN

        return Rollenbeschreibung(PB1_ROLLEN, MappingProxyType(dict(PB1_ROLLEN_DATEIEN)))

    def pruefe_eingaenge(
        self, eingaben: Mapping[str, Path], *, bis: date | None = None,
        manifest: Mapping[str, Any] | None = None,
    ) -> PB1Pruefung:
        from rechner_pipeline.bestand.vorbedingungen import lies_und_pruefe_pb1

        tabellen, geprueft, fehler, bedienfehler = lies_und_pruefe_pb1(
            eingaben, bis=bis, manifest=manifest)
        return PB1Pruefung(tabellen, geprueft, fehler, bedienfehler)

    def pruefe_fortschreibung(
        self, verzeichnis: Path, config: Path,
    ) -> Fortschreibungspruefung:
        from rechner_pipeline.bestand.vorbedingungen import fortschreibung_pruefen

        horizont, fehler = fortschreibung_pruefen(verzeichnis, config)
        return Fortschreibungspruefung(horizont, fehler)

    def manifest_fuer_nachrechnung(
        self, portfolio: Path, erwarteter_sha256: str | None,
    ) -> ManifestNachrechnung:
        from rechner_pipeline.bestand.vorbedingungen import manifest_fuer_nachrechnung

        daten, fehler = manifest_fuer_nachrechnung(portfolio, erwarteter_sha256)
        return ManifestNachrechnung(daten, fehler)

    def bestandszeilen(self, pfad: Path) -> int:
        from rechner_pipeline.bestand.vorbedingungen import bestandszeilen

        return bestandszeilen(pfad)
