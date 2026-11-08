"""Die PLV erfuellt den Bestandsdaten-Vertrag (ADR-030, Stufe 3).

Das Laufmanifest wird nur fuer eine vollstaendige Schicht geschrieben.
Darum ist auch ein Bestand ohne Manifest und ohne Verankerungsdatei ein
ordentlicher Zustand. Sobald eine Seite die Rolle behauptet, prueft die
PLV beide Seiten samt Hash und Tabellenform. Tabellen und Config bleiben
in der PLV-Fuehrung; das Tool sieht nur die neutralen Vertragsformen.

Knoten: system/zielsystem, klv
"""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from rechner_pipeline.zielsystem.bestandsdaten import (
    BestandsdatenFehler, Erfahrungsannahmen, Fuehrungsansicht,
    Fuehrungsgeneration, Laufmanifest, Verankerungsrolle,
)

__all__ = ["PLVBestandsdaten"]


class PLVBestandsdaten:
    """Bestands- und Manifestoperationen der PLV hinter dem Vertrag."""

    def tabelle_aus_bytes(
        self, daten: bytes, *, erwartete_spalten: Sequence[str] | None = None,
    ) -> Any:
        from rechner_pipeline.bestand.parquet_io import read_portfolio_aus_bytes

        return read_portfolio_aus_bytes(daten, expected_columns=erwartete_spalten)

    def schreibe_tabelle(self, tabelle: Any, pfad: Path, *, exklusiv: bool = False) -> Path:
        from rechner_pipeline.bestand.parquet_io import write_portfolio

        return write_portfolio(tabelle, pfad, exklusiv=exklusiv)

    def rollen_dateien(self) -> Mapping[str, str]:
        from rechner_pipeline.bestand.manifest import ROLLEN_DATEIEN

        return MappingProxyType(dict(ROLLEN_DATEIEN))

    def laufmanifest_lesen(self, pfad: Path) -> Laufmanifest:
        from rechner_pipeline.bestand.manifest import (
            ManifestError, lies_manifest_bytes, manifest_aus_bytes,
        )

        try:
            roh = lies_manifest_bytes(pfad)
            return Laufmanifest(manifest_aus_bytes(roh), hashlib.sha256(roh).hexdigest())
        except ManifestError as exc:
            raise BestandsdatenFehler(str(exc)) from exc

    def laufmanifest_schreiben(
        self, lauf: Path, *, horizont: date, neuzugang_ab: date | None,
        config_pfad: Path, ausgaben: Sequence[Path],
        eingaben: Mapping[str, Path] | None = None, laufart: str,
    ) -> Path:
        from rechner_pipeline.bestand.manifest import (
            ERZEUGER, ERZEUGER_MIGRATIONSZUGANG, schreibe_manifest,
        )

        erzeuger = {
            "fortschreibung": ERZEUGER,
            "migrationszugang": ERZEUGER_MIGRATIONSZUGANG,
        }.get(laufart)
        if erzeuger is None:
            raise BestandsdatenFehler(f"unbekannte Laufart {laufart!r}")
        return schreibe_manifest(
            lauf, horizont=horizont, neuzugang_ab=neuzugang_ab,
            config_pfad=config_pfad, ausgaben=ausgaben, eingaben=eingaben,
            erzeuger=erzeuger,
        )

    def fuehrungsansicht_aus_text(self, text: str) -> Fuehrungsansicht:
        from rechner_pipeline.bestand.config import config_aus_text

        config = config_aus_text(text)
        fehler = config.validate()
        if fehler:
            raise BestandsdatenFehler("Config ungueltig: " + "; ".join(fehler))
        a = config.annahmen
        return Fuehrungsansicht(
            generationen=tuple(
                Fuehrungsgeneration(g.name, MappingProxyType(g.tarifwerk()))
                for g in config.generationen),
            annahmen=Erfahrungsannahmen(
                tod=a.tod, storno=a.storno, beitragsfreistellung=a.beitragsfreistellung,
                erhoehung=a.erhoehung, herabsetzung=a.herabsetzung,
                teilkuendigung=a.teilkuendigung, invalidisierung=a.invalidisierung,
                reaktivierung=a.reaktivierung,
                aktivensterblichkeit=a.aktivensterblichkeit,
                invalidensterblichkeit=a.invalidensterblichkeit,
                erh_prozent=a.erh_prozent, red_anteil=a.red_anteil, tk_anteil=a.tk_anteil,
            ),
            config_text=text,
        )

    def verankerungsrolle(
        self, *, manifest_bytes: bytes | None, bestand_bytes: bytes,
        verankerung_bytes: bytes | None,
    ) -> Verankerungsrolle:
        # Die Bestandsmodule importieren den Anbieter selbst. Erst nach der
        # Konstruktion des Zielsystems laden, sonst schliesst sich ein
        # Importkreis PLV -> Bestand -> Anbieter -> PLV.
        from rechner_pipeline.bestand.manifest import (
            ERZEUGER_MIGRATIONSZUGANG, ManifestError, manifest_aus_bytes, pruefe_erzeuger,
        )
        from rechner_pipeline.bestand.parquet_io import read_portfolio_aus_bytes
        from rechner_pipeline.models.bestand import VERANKERUNG_NAMES

        bestand_sha = hashlib.sha256(bestand_bytes).hexdigest()
        if manifest_bytes is None:
            if verankerung_bytes is not None:
                raise BestandsdatenFehler(
                    "Verankerung liegt vor, aber das Laufmanifest fehlt")
            return Verankerungsrolle(False, bestand_sha, None)
        try:
            manifest = manifest_aus_bytes(manifest_bytes)
            pruefe_erzeuger(manifest, ERZEUGER_MIGRATIONSZUGANG)
        except ManifestError as exc:
            raise BestandsdatenFehler(f"Laufmanifest ungueltig: {exc}") from exc
        ausgaben = manifest["ausgaben"]
        if ausgaben.get("bestand.parquet") != bestand_sha:
            raise BestandsdatenFehler(
                "bestand.parquet weicht von den im Laufmanifest gebundenen Bytes ab")
        soll = ausgaben.get("verankerung.parquet")
        if soll is None:
            if verankerung_bytes is not None:
                raise BestandsdatenFehler(
                    "Verankerung liegt vor, aber das Laufmanifest nennt ihre Ausgabe nicht")
            return Verankerungsrolle(False, bestand_sha, None)
        if verankerung_bytes is None:
            raise BestandsdatenFehler(
                "Laufmanifest nennt verankerung.parquet, aber die Datei fehlt")
        verankerung_sha = hashlib.sha256(verankerung_bytes).hexdigest()
        if verankerung_sha != soll:
            raise BestandsdatenFehler(
                "verankerung.parquet weicht von den im Laufmanifest gebundenen Bytes ab")
        try:
            tabelle = read_portfolio_aus_bytes(
                verankerung_bytes, expected_columns=VERANKERUNG_NAMES)
            if tuple(tabelle.columns) != VERANKERUNG_NAMES:
                raise ValueError("Verankerung hat nicht alle Pflichtspalten")
        except Exception as exc:  # noqa: BLE001 - Parquet-Lader kennt mehrere Formatfehler
            raise BestandsdatenFehler(
                f"Verankerung hat kein gueltiges Parquet-Format: {exc}") from exc
        return Verankerungsrolle(True, bestand_sha, verankerung_sha)
