"""Blattnamen einer Vorverdichtung ERMITTELN statt annehmen.

Die deterministische Vorverdichtung eines Quell-Workbooks legt je Blatt
eine CSV im Schema ``Blatt;Adresse;Formel;Wert`` ab und verdichtet die
formeltragenden Blaetter zusaetzlich zu ``<stamm>_compressed.csv``
(daraus wiederum ``<stamm>_scalar.json`` und
``<stamm>_table_values.csv``). WIE das Kalkulationsblatt heisst,
entscheidet das Quellsystem: der Vorlauf-Fall nannte es
``Kalkulation``, die Baldrian-Uebernahme nennt es ``Tarifrechnung``.

Wer diesen Namen hart verdrahtet, prueft still nichts, sobald ein
Quellsystem anders benennt — genau so fiel der Formel-Rueck-Check in
Gate P-Q3 aus, ohne dass das Gate rot wurde (Review-Befund). Dieses Modul
liest den Namen deshalb aus den Artefakten selbst:

* ``export_manifest.json`` sagt, WELCHE Blaetter exportiert wurden und
  welche davon formeltragend sind (die Schluessel von ``replacements``
  sind genau die Blatt-CSVs, fuer die eine ``_compressed.csv``
  entstanden ist),
* die Blatt-CSV sagt in ihrer Spalte ``Blatt``, wie das Blatt im
  Workbook HEISST — der Dateiname ist nur dessen dateisystemsichere
  Fassung (``safe_filename``) und taugt nicht als Fundstellen-Praefix.

Fail-fast statt Default: ein mehrdeutiger Fall (mehrere formeltragende
Blaetter) ist ein benannter Fehler mit Ausweg, keine stille Auswahl.
Unterschieden wird ausserdem hart zwischen "es gibt hier keine
Vorverdichtung" (:class:`VorverdichtungFehlt`) und "sie ist da, aber
nicht auswertbar" (:class:`VorverdichtungFehler`) — die erste Lage ist
ehrlich nicht pruefbar, die zweite ist ein Befund.

Knoten: system/assurance
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from rechner_pipeline.models.manifest import ExportManifest

#: Name des Manifests, das die Vorverdichtung eines Workbooks indiziert.
MANIFEST_DATEI = "export_manifest.json"

#: Pflicht-Kopfzeile jeder Blatt-CSV (Contract des Exporteurs).
CSV_KOPF: Tuple[str, ...] = ("Blatt", "Adresse", "Formel", "Wert")


class VorverdichtungFehlt(FileNotFoundError):
    """Zu dieser Generation liegt keine Vorverdichtung vor.

    Ehrlich nicht pruefbar (z. B. synthetische A-Box ohne Quellrechner)
    — kein Befund, aber auch kein stilles Gruen.
    """


class VorverdichtungFehler(ValueError):
    """Vorverdichtung vorhanden, aber nicht auswertbar (Befund)."""


@dataclass(frozen=True)
class Blatt:
    """Ein exportiertes Arbeitsblatt der Vorverdichtung.

    ``name`` ist der Blattname des Quell-Workbooks (Praefix der
    Fundstellen: ``<name>!$G$12``), ``stamm`` der Dateistamm und damit
    das Praefix der abgeleiteten Artefakte (``<stamm>_scalar.json``).
    Beide fallen meist zusammen, muessen es aber nicht.
    """

    name: str
    stamm: str
    csv: Path
    formeltragend: bool


@dataclass(frozen=True)
class Vorverdichtung:
    """Die Blatt-Sicht auf ein Vorverdichtungs-Verzeichnis."""

    verzeichnis: Path
    blaetter: Tuple[Blatt, ...]

    def blatt(self, name: str) -> Optional[Blatt]:
        """Blatt nach seinem Workbook-Namen (None = nicht vorhanden)."""
        for blatt in self.blaetter:
            if blatt.name == name:
                return blatt
        return None

    @property
    def blattnamen(self) -> Tuple[str, ...]:
        return tuple(blatt.name for blatt in self.blaetter)

    @property
    def kalkulationsblatt(self) -> Blatt:
        """Das eine formeltragende Blatt (fail-fast, wenn uneindeutig)."""
        kandidaten = [b for b in self.blaetter if b.formeltragend]
        if len(kandidaten) == 1:
            return kandidaten[0]
        if not kandidaten:
            raise VorverdichtungFehler(
                f"kein formeltragendes Blatt in {self.verzeichnis} "
                f"(exportierte Blaetter: {list(self.blattnamen) or 'keine'}) "
                "— ohne verdichtete Formeln gibt es nichts nachzurechnen; "
                "extract fuer diese Generation erneut laufen lassen"
            )
        raise VorverdichtungFehler(
            f"mehrere formeltragende Blaetter in {self.verzeichnis}: "
            f"{[b.name for b in kandidaten]} — welches davon das "
            "Kalkulationsblatt ist, ist eine fachliche Entscheidung; das "
            "Blatt explizit waehlen (Vorverdichtung.blatt(<name>))"
        )


def verzeichnis_der_generation(fall: Path, generation: str) -> Path:
    """Vorverdichtungs-Verzeichnis einer Generation im Fall-Arbeitsbereich.

    ``klv/tg2015`` -> ``<fall>/abgeleitet/vorverdichtung/xlsm-TG2015``.
    Eine Stelle statt drei — die Namenskonvention der Ablage soll nicht
    in jedem Gate erneut buchstabiert werden.
    """
    gen_name = generation.rsplit("/", 1)[-1].upper()
    return fall / "abgeleitet" / "vorverdichtung" / f"xlsm-{gen_name}"


def _blattname(csv_pfad: Path) -> str:
    """Blattname aus der ersten Datenzeile der Blatt-CSV.

    Die Spalte ``Blatt`` traegt den Namen des Quell-Workbooks; der
    Dateistamm ist nur seine dateisystemsichere Fassung. Ein leeres
    Blatt (nur Kopfzeile) hat keinen belegten Namen — dann bleibt der
    Dateistamm die beste verfuegbare Aussage, und das steht hier
    ausdruecklich statt es zu verschweigen.
    """
    with csv_pfad.open(encoding="utf-8", newline="") as f:
        leser = csv.reader(f, delimiter=";")
        kopf = next(leser, None)
        if kopf is None or tuple(kopf[: len(CSV_KOPF)]) != CSV_KOPF:
            raise VorverdichtungFehler(
                f"{csv_pfad} ist keine Blatt-CSV der Vorverdichtung "
                f"(erwartete Kopfzeile {';'.join(CSV_KOPF)}, gelesen "
                f"{kopf!r})"
            )
        for zeile in leser:
            if zeile and zeile[0]:
                return zeile[0]
    return csv_pfad.stem


def lies_vorverdichtung(verzeichnis: Path) -> Vorverdichtung:
    """Blatt-Sicht eines Vorverdichtungs-Verzeichnisses aufbauen.

    Fehlt das Verzeichnis, ist die Vorverdichtung schlicht nicht da
    (:class:`VorverdichtungFehlt`). Ist sie da, aber ohne Manifest oder
    ohne die im Manifest genannten CSVs, ist das ein Befund
    (:class:`VorverdichtungFehler`) — ein halb vorhandener Export darf
    nicht wie "nicht vorhanden" aussehen.
    """
    if not verzeichnis.is_dir():
        raise VorverdichtungFehlt(
            f"keine Vorverdichtung unter {verzeichnis}"
        )
    manifest_pfad = verzeichnis / MANIFEST_DATEI
    if not manifest_pfad.is_file():
        raise VorverdichtungFehler(
            f"Vorverdichtung {verzeichnis} ohne {MANIFEST_DATEI} — welche "
            "Blaetter sie enthaelt, ist damit nicht ableitbar; extract "
            "erneut laufen lassen"
        )
    try:
        roh = json.loads(manifest_pfad.read_text(encoding="utf-8"))
        manifest = ExportManifest.from_dict(roh)
    except (ValueError, KeyError) as exc:
        raise VorverdichtungFehler(
            f"{manifest_pfad} ist kein lesbares Export-Manifest: {exc}"
        ) from exc

    # Die Manifest-Pfade sind relativ zum Repo-Stand der Extraktion; der
    # Arbeitsbereich kann seither verschoben oder kopiert worden sein.
    # Verbindlich ist deshalb der Dateiname im uebergebenen Verzeichnis.
    formeltragend = {Path(p).name for p in manifest.replacements}
    blaetter = []
    for eintrag in manifest.sheet_csvs:
        csv_pfad = verzeichnis / Path(eintrag).name
        if not csv_pfad.is_file():
            raise VorverdichtungFehler(
                f"Manifest nennt die Blatt-CSV {Path(eintrag).name}, sie "
                f"fehlt aber in {verzeichnis} — unvollstaendige "
                "Vorverdichtung"
            )
        blaetter.append(
            Blatt(
                name=_blattname(csv_pfad),
                stamm=csv_pfad.stem,
                csv=csv_pfad,
                formeltragend=csv_pfad.name in formeltragend,
            )
        )
    if not blaetter:
        raise VorverdichtungFehler(
            f"Vorverdichtung {verzeichnis} nennt kein einziges Blatt "
            "(sheet_csvs leer) — extract erneut laufen lassen"
        )
    return Vorverdichtung(
        verzeichnis=verzeichnis,
        blaetter=tuple(sorted(blaetter, key=lambda b: b.stamm)),
    )
