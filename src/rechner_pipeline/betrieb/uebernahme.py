"""Uebernahme-Eingaenge des Tagesbetriebs (Fachkonzept Tagesbetrieb, Abschnitt 6).

Ein migrierter Bestand tritt als **datierter Zugang** in den
Tagesbetrieb ein: Die Laufzeitumgebung erhaelt ihn einmal als Eingang
unter ``daten/uebernahme/<fall>/`` — den Zugangsstand, wie ihn
``gates.bestand_uebernehmen`` hinterlaesst (Stamm, Historie, Ledger mit
den ZUG-/PEX-Buchungen zum Stichtag, Merkmale, Verankerung), dazu eine
Eingangsdatei ``eingang.json`` mit dem Fall-Bezug (Fallname, Stichtag,
Snapshot-Hash der A-M4-Annahme) und der SHA-256 jeder Datei. Ab dem
Stichtag wird der Bestand im SELBEN Strom fortgeschrieben wie das
eigene Geschaeft (ADR-015); der Tagesbetrieb kennt keine
Sonderbehandlung je Fall — ein weiterer Migrationsfall ist ein weiterer
Eingang.

Der Eingang ist unantastbar wie ein Fall-Eingang (ADR-002): Beim Lesen
wird jede Datei gegen ihre registrierte Summe gehalten; eine Abweichung
ist ein harter Fehler, kein Vorbehalt. Angelegt wird ein Eingang mit
diesem Modul als Kommando (Block B5)::

    python -m rechner_pipeline.betrieb.uebernahme --stand <daten> \\
        --fall <faelle/name> --stichtag 2026-01-01 [--snapshot <sha256>]

Knoten: klv, bu
"""

from __future__ import annotations

import dataclasses
import datetime as _dt
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from rechner_pipeline.bestand.config import BestandConfig
from rechner_pipeline.bestand.manifest import sha256_bytes
from rechner_pipeline.bestand.parquet_io import read_portfolio
from rechner_pipeline.models.bestand import (
    LEDGER_NAMES,
    MERKMALE_NAMES,
    STAMM_NAMES,
    STATUS_HISTORIE_NAMES,
    VERANKERUNG_NAMES,
)

EINGANG_DATEI = "eingang.json"
EINGANG_SCHEMA_VERSION = 1
#: Pflichttabellen eines Zugangsstands und ihre Spaltenvertraege.
PFLICHT = {
    "bestand": STAMM_NAMES,
    "historie": STATUS_HISTORIE_NAMES,
    "ledger": LEDGER_NAMES,
}
OPTIONAL = {
    "merkmale": MERKMALE_NAMES,
    "verankerung": VERANKERUNG_NAMES,
}


class UebernahmeError(ValueError):
    """Ein Uebernahme-Eingang ist unvollstaendig, veraendert oder unpassend."""


@dataclasses.dataclass
class Uebernahme:
    fall: str
    stichtag: _dt.date
    snapshot_sha256: Optional[str]
    verzeichnis: Path
    manifest_pfad: Path
    bestand: pd.DataFrame
    historie: pd.DataFrame
    ledger: pd.DataFrame
    merkmale: Optional[pd.DataFrame]
    verankerung: Optional[pd.DataFrame]


def _lies_eingang(verzeichnis: Path) -> Dict[str, Any]:
    pfad = verzeichnis / EINGANG_DATEI
    if not pfad.is_file():
        raise UebernahmeError(
            f"{verzeichnis}: keine {EINGANG_DATEI} — ein Uebernahme-Eingang wird "
            "mit python -m rechner_pipeline.betrieb.uebernahme angelegt, nicht "
            "von Hand kopiert"
        )
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UebernahmeError(f"{pfad}: nicht lesbar: {exc}") from exc
    fehler = validate_eingang(daten)
    if fehler:
        raise UebernahmeError(f"{pfad}: " + "; ".join(fehler))
    return daten


def validate_eingang(daten: Any) -> List[str]:
    """Struktur-Contract der Eingangsdatei (Fehlerlisten-Idiom)."""
    fehler: List[str] = []
    if not isinstance(daten, dict):
        return ["Eingang ist kein JSON-Objekt"]
    if daten.get("schema_version") != EINGANG_SCHEMA_VERSION:
        fehler.append(f"schema_version {daten.get('schema_version')!r}, erwartet {EINGANG_SCHEMA_VERSION}")
    if not isinstance(daten.get("fall"), str) or not daten["fall"].strip():
        fehler.append("fall fehlt")
    try:
        _dt.date.fromisoformat(str(daten.get("stichtag")))
    except ValueError:
        fehler.append(f"stichtag {daten.get('stichtag')!r} ist kein ISO-Datum")
    snapshot = daten.get("snapshot_sha256")
    if snapshot is not None and not _ist_sha256(snapshot):
        fehler.append("snapshot_sha256 ist keine SHA-256")
    dateien = daten.get("dateien")
    if not isinstance(dateien, dict) or not dateien:
        fehler.append("dateien fehlen")
    else:
        for name, summe in dateien.items():
            if not _ist_sha256(summe):
                fehler.append(f"dateien[{name}] ist keine SHA-256")
        for pflicht in PFLICHT:
            if f"{pflicht}.parquet" not in dateien:
                fehler.append(f"dateien: {pflicht}.parquet fehlt")
    return fehler


def _ist_sha256(wert: Any) -> bool:
    return isinstance(wert, str) and len(wert) == 64 and all(c in "0123456789abcdef" for c in wert)


def lies_uebernahme(verzeichnis: Path, config: BestandConfig) -> Uebernahme:
    """Einen Eingang lesen — jede Datei gegen ihre registrierte Summe."""
    verzeichnis = Path(verzeichnis)
    eingang = _lies_eingang(verzeichnis)
    tabellen: Dict[str, Optional[pd.DataFrame]] = {}
    for name, spalten in {**PFLICHT, **OPTIONAL}.items():
        datei = f"{name}.parquet"
        if datei not in eingang["dateien"]:
            tabellen[name] = None
            continue
        pfad = verzeichnis / datei
        if not pfad.is_file():
            raise UebernahmeError(
                f"{verzeichnis}: {datei} ist registriert, fehlt aber — der Eingang "
                "ist unvollstaendig"
            )
        daten = pfad.read_bytes()
        if sha256_bytes(daten) != eingang["dateien"][datei]:
            raise UebernahmeError(
                f"{pfad}: SHA-256 weicht von der registrierten Summe ab — der "
                "Eingang ist unantastbar; eine neue Lieferung ist ein neuer Eingang"
            )
        import io

        tabellen[name] = read_portfolio(io.BytesIO(daten), expected_columns=spalten)
    bestand = tabellen["bestand"]
    stichtag = _dt.date.fromisoformat(str(eingang["stichtag"]))
    if len(bestand) == 0:
        raise UebernahmeError(f"{verzeichnis}: leerer Zugangsstand")
    zugang = pd.to_datetime(bestand["bestandszugang"])
    if not (zugang == pd.Timestamp(stichtag)).all():
        raise UebernahmeError(
            f"{verzeichnis}: bestandszugang weicht vom Stichtag "
            f"{stichtag.isoformat()} ab — ein Zugang hat genau einen Stichtag"
        )
    bekannt = {g.name for g in config.generationen}
    fremd = sorted(set(bestand["tarif_generation"]) - bekannt)
    if fremd:
        raise UebernahmeError(
            f"{verzeichnis}: Tarifgenerationen {fremd} nicht in der Config der "
            "PLV — die uebernommene Generation gehoert in configs/ (sample_size 0)"
        )
    mit_zellen = {g.name for g in config.generationen if g.zellen}
    if (set(bestand["tarif_generation"]) & mit_zellen) and tabellen["merkmale"] is None:
        raise UebernahmeError(
            f"{verzeichnis}: die Generation ist in Tarifzellen aufgeteilt, der "
            "Eingang traegt aber keine merkmale.parquet — ohne sie waere jede "
            "Zelle geraten"
        )
    return Uebernahme(
        fall=str(eingang["fall"]),
        stichtag=stichtag,
        snapshot_sha256=eingang.get("snapshot_sha256"),
        verzeichnis=verzeichnis,
        manifest_pfad=verzeichnis / EINGANG_DATEI,
        bestand=bestand,
        historie=tabellen["historie"],
        ledger=tabellen["ledger"],
        merkmale=tabellen["merkmale"],
        verankerung=tabellen["verankerung"],
    )


def lies_uebernahmen(wurzel: Path, config: BestandConfig) -> List[Uebernahme]:
    """Alle Eingaenge unter ``uebernahme/`` (sortiert nach Fallname); leer ohne Verzeichnis."""
    wurzel = Path(wurzel)
    if not wurzel.is_dir():
        return []
    eingaenge = [lies_uebernahme(p, config) for p in sorted(wurzel.iterdir()) if p.is_dir()]
    faelle = [u.fall for u in eingaenge]
    if len(faelle) != len(set(faelle)):
        raise UebernahmeError(f"uebernahme: Fallname doppelt: {faelle}")
    return eingaenge


# --------------------------------------------------------------------------- #
# Eingang anlegen (Kommando)
# --------------------------------------------------------------------------- #


def eingang_anlegen(
    stand: Path,
    fall: Path,
    stichtag: _dt.date,
    *,
    quelle: Optional[Path] = None,
    snapshot_sha256: Optional[str] = None,
) -> Path:
    """Den Zugangsstand eines Falls als Eingang der Laufzeitumgebung registrieren.

    Kopiert die Tabellen aus ``<fall>/abgeleitet/bestand/`` (dem Erzeugnis
    von ``gates.bestand_uebernehmen``; ``quelle`` uebersteuert) nach
    ``<stand>/uebernahme/<fallname>/``, schreibt ``eingang.json`` mit
    Fallname, Stichtag, Snapshot-Hash der A-M4-Annahme und der SHA-256
    jeder Datei, und setzt die Kopien schreibgeschuetzt. Ein vorhandener
    Eingang wird nie ueberschrieben — eine neue Lieferung ist ein neuer
    Eingang unter neuem Namen.

    Den Snapshot-Hash liest das Kommando aus dem Gate-Beleg der
    A-M4-Entscheidung (``abgeleitet/diagnostics/gate_entscheid_am4.gate.json``,
    ``summary.snapshot_sha256``), wenn er nicht uebergeben wird; fehlt
    beides, ist das kein Fehler, sondern ein leeres Feld — der
    Fall-Bezug ist Provenienz, nicht Voraussetzung des Betriebs.
    """
    import os
    import shutil

    fall = Path(fall)
    fall_json = fall / "fall.json"
    if not fall_json.is_file():
        raise UebernahmeError(
            f"{fall}: kein Fall-Arbeitsbereich (fall.json fehlt) — der Eingang "
            "kommt aus einem Fall, nicht aus einem beliebigen Verzeichnis"
        )
    try:
        fall_daten = json.loads(fall_json.read_text(encoding="utf-8"))
        fallname = str(fall_daten["name"])
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        raise UebernahmeError(f"{fall_json}: nicht lesbar oder ohne name: {exc}") from exc
    if not fallname or "/" in fallname or fallname in (".", ".."):
        raise UebernahmeError(f"{fall_json}: name {fallname!r} taugt nicht als Verzeichnisname")
    quelle = Path(quelle) if quelle is not None else fall / "abgeleitet" / "bestand"
    fehlend = [f"{n}.parquet" for n in PFLICHT if not (quelle / f"{n}.parquet").is_file()]
    if fehlend:
        raise UebernahmeError(
            f"{quelle}: {fehlend} fehlen — erwartet wird das Erzeugnis von "
            "gates.bestand_uebernehmen (bestand/historie/ledger.parquet)"
        )
    if snapshot_sha256 is None:
        beleg = fall / "abgeleitet" / "diagnostics" / "gate_entscheid_am4.gate.json"
        if beleg.is_file():
            try:
                snapshot_sha256 = json.loads(beleg.read_text(encoding="utf-8"))["summary"]["snapshot_sha256"]
            except (OSError, json.JSONDecodeError, KeyError, TypeError):
                snapshot_sha256 = None
    if snapshot_sha256 is not None and not _ist_sha256(snapshot_sha256):
        raise UebernahmeError(f"snapshot_sha256 {snapshot_sha256!r} ist keine SHA-256")
    ziel = Path(stand) / "uebernahme" / fallname
    if ziel.exists():
        raise UebernahmeError(
            f"{ziel} existiert bereits — ein Eingang wird nie ueberschrieben; "
            "eine neue Lieferung ist ein neuer Eingang unter neuem Namen"
        )
    ziel.mkdir(parents=True)
    dateien: Dict[str, str] = {}
    for name in list(PFLICHT) + list(OPTIONAL):
        datei = f"{name}.parquet"
        if not (quelle / datei).is_file():
            continue
        daten = (quelle / datei).read_bytes()
        (ziel / datei).write_bytes(daten)
        if os.name != "nt":
            (ziel / datei).chmod(0o444)
        dateien[datei] = sha256_bytes(daten)
    eingang = {
        "schema_version": EINGANG_SCHEMA_VERSION,
        "fall": fallname,
        "stichtag": stichtag.isoformat(),
        "snapshot_sha256": snapshot_sha256,
        "quelle": str(quelle),
        "dateien": dict(sorted(dateien.items())),
    }
    pfad = ziel / EINGANG_DATEI
    pfad.write_text(json.dumps(eingang, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")
    if os.name != "nt":
        pfad.chmod(0o444)
    return ziel


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.betrieb.uebernahme",
        description="Den Zugangsstand eines Migrationsfalls als Eingang des "
        "Tagesbetriebs registrieren (unantastbar, mit Fall-Bezug).",
    )
    parser.add_argument("--stand", required=True, help="Datenverzeichnis der Laufzeitumgebung.")
    parser.add_argument("--fall", required=True, help="Fall-Arbeitsbereich (faelle/<name>).")
    parser.add_argument("--stichtag", required=True, help="Zugangsstichtag (ISO-Datum).")
    parser.add_argument("--quelle", default=None,
                        help="Verzeichnis des Zugangsstands (Default: <fall>/abgeleitet/bestand).")
    parser.add_argument("--snapshot", default=None,
                        help="Snapshot-Hash der A-M4-Annahme (Default: aus dem Gate-Beleg des Falls).")
    ns = parser.parse_args(argv)
    try:
        stichtag = _dt.date.fromisoformat(ns.stichtag)
    except ValueError as exc:
        print(f"uebernahme: --stichtag: {exc}", file=sys.stderr)
        return 2
    try:
        ziel = eingang_anlegen(
            Path(ns.stand), Path(ns.fall), stichtag,
            quelle=Path(ns.quelle) if ns.quelle else None, snapshot_sha256=ns.snapshot,
        )
    except UebernahmeError as exc:
        print(f"uebernahme: {exc}", file=sys.stderr)
        return 2
    print(f"uebernahme: Eingang angelegt -> {ziel}", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
