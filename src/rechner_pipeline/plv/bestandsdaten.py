"""Die PLV liest die Verankerungsrolle aus gebundenen Bestandsbytes.

Das Laufmanifest wird nur fuer eine vollstaendige Schicht geschrieben.
Darum ist auch ein Bestand ohne Manifest und ohne Verankerungsdatei ein
ordentlicher Zustand. Sobald eine Seite die Rolle behauptet, prueft die
PLV beide Seiten samt Hash und Tabellenform (ADR-030).

Knoten: system/zielsystem, klv
"""

from __future__ import annotations

import hashlib

from rechner_pipeline.zielsystem.bestandsdaten import BestandsdatenFehler, Verankerungsrolle

__all__ = ["PLVBestandsdaten"]


class PLVBestandsdaten:
    """Lesende Implementierung der Verankerungsrolle fuer die PLV."""

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
            read_portfolio_aus_bytes(
                verankerung_bytes, expected_columns=VERANKERUNG_NAMES)
        except Exception as exc:  # noqa: BLE001 - Parquet-Lader kennt mehrere Formatfehler
            raise BestandsdatenFehler(
                f"Verankerung hat kein gueltiges Parquet-Format: {exc}") from exc
        return Verankerungsrolle(True, bestand_sha, verankerung_sha)
