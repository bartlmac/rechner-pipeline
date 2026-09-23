"""Laufmanifest — der Lieferschein eines Fortschreibungslaufs.

``cli_fortschreibung`` schreibt neben seine Parquet-Ausgaben eine Datei
``laufmanifest.json``: den tatsaechlich simulierten Horizont, den
Neuzugangs-Stichtag, den Kern-Stand und je Ausgabe die SHA-256-Summe
der geschriebenen Bytes, dazu die Summe der Config, aus der der Lauf
entstand.

Warum es das braucht (externes Review T18-02): Die Konsumenten eines
Laufs — Gate P-B1 und der Abschluss-Produzent — nehmen ``--bis`` als
Fortschreibungs-Horizont entgegen. Ohne Manifest ist das eine
BEHAUPTUNG des Aufrufers ueber den Lauf, die niemand prueft: Ein bis
2020-01-01 erzeugter Lauf, festgeschrieben mit behauptetem
``--bis 2020-12-01``, lief mit Exit 0 durch und ueberzeichnete das
Bewegungskonto im selben Kalenderjahr um 1,37 Mio EUR. Dieselbe Klasse
(T16) sind Bundle-Teile aus verschiedenen Laeufen: Stamm aus dem einen,
Scheiben aus dem anderen — jeder fuer sich wohlgeformt.

Die Invariante, die das Manifest erzwingt: Die Teile eines Bundles
stammen nachweislich aus DEMSELBEN Lauf, und der Horizont ist der, den
der Erzeuger simuliert hat — nicht der, den der Aufrufer nennt.

Das Manifest ist deterministisch (kein Zeitstempel, sortierte
Schluessel): Zweimal derselbe Lauf ergibt bytegleiche Manifeste, wie
bei den Parquet-Ausgaben.

Knoten: klv, bu
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

#: Dateiname des Manifests im Laufverzeichnis.
MANIFEST_DATEI = "laufmanifest.json"
MANIFEST_SCHEMA_VERSION = 1
ERZEUGER = "bestand_fortschreibung"

#: Der zweite Lauftyp, der ein Manifest schreibt: der Migrationszugang.
#: Ein Migrationsfall hat ZWEI Produzenten — ``gates.bestand_uebernehmen``
#: schreibt die Tabellen, ``gates.verankerung_belegen`` die
#: Korrekturschicht — und erst der zweite kennt die Config, mit der die
#: Fuehrung rechnet (sie entsteht aus dem ``generation-zellen.toml`` des
#: ersten). Deshalb schreibt der ZWEITE das Manifest, fuer beide.
#: Ohne diesen Erzeuger war die Migrationsabnahme A-M4 seit dem
#: Manifest-Entscheid (2026-09-16) unerfuellbar: Sie verlangt ein
#: Laufmanifest im P-B1-Beleg, und den Bestand, den sie abnimmt, erzeugt
#: kein Fortschreibungslauf.
ERZEUGER_MIGRATIONSZUGANG = "bestand_migrationszugang"

#: Welche Erzeuger ein gueltiges Manifest schreiben duerfen. Die Liste
#: ist kein Freibrief: Wer ein Manifest LIEST, sagt mit
#: :func:`pruefe_erzeuger`, welche Sorte Lauf er erwartet — ein
#: Betriebskommando nimmt kein Migrationsmanifest an und umgekehrt.
ERZEUGER_ERLAUBT: Tuple[str, ...] = (ERZEUGER, ERZEUGER_MIGRATIONSZUGANG)

#: Die Portfolio-Rolle traegt je Erzeuger eine andere Datei: Die
#: Fortschreibung fuehrt Uebernahme UND eigenes Geschaeft zusammen
#: (``bestand_gesamt.parquet``), der Migrationszugang nur die
#: uebernommenen Vertraege (``bestand.parquet``). Das ist kein
#: Namensschoenheitsfehler, sondern der Unterschied zwischen zwei
#: Mengen: A-M4 prueft, dass genau die uebernommene Menge abgenommen
#: wurde, und vergleicht sie mit der Pruefmenge der Migrationssuite.
PORTFOLIO_JE_ERZEUGER: Mapping[str, str] = {
    ERZEUGER: "bestand_gesamt.parquet",
    ERZEUGER_MIGRATIONSZUGANG: "bestand.parquet",
}

#: Welche Datei des Laufs eine P-B1-Eingangsrolle traegt. Die Engine
#: vergleicht die gelesenen Bytes einer Rolle mit dem Manifest-Eintrag
#: dieser Datei.
ROLLEN_DATEIEN: Mapping[str, str] = {
    "portfolio": "bestand_gesamt.parquet",
    "historie": "historie.parquet",
    "ledger": "ledger.parquet",
    "scheiben": "scheiben.parquet",
    "merkmale": "merkmale.parquet",
    "schichten": "schichten.parquet",
    "verankerung": "verankerung.parquet",
    "reduktionen": "reduktionen.parquet",
}
#: Rollen, die JEDER Fortschreibungslauf traegt — ohne sie ist es kein Lauf.
PFLICHT_ROLLEN: Tuple[str, ...] = ("portfolio", "historie", "ledger", "scheiben")
#: Nebentabellen: nur Laeufe mit Tarifzellen (merkmale), uebernommenen
#: Vertraegen (schichten, verankerung) oder Herabsetzungen (reduktionen)
#: tragen sie — abgeleitet, nicht abgetippt.
NEBENTABELLEN: Tuple[str, ...] = tuple(r for r in ROLLEN_DATEIEN if r not in PFLICHT_ROLLEN)


def rollen_dateien(erzeuger: str = ERZEUGER) -> Mapping[str, str]:
    """Die Rollentabelle DIESES Erzeugers (Rolle -> Dateiname).

    Nur die Portfolio-Rolle unterscheidet sich; alles andere heisst in
    beiden Lauftypen gleich. Wer ein Manifest liest, schlaegt hier nach
    statt in :data:`ROLLEN_DATEIEN`, sonst sucht er im Migrationslauf
    nach einer ``bestand_gesamt.parquet``, die es dort nicht gibt — und
    meldete "stammt nicht aus diesem Lauf" fuer eine Datei, die sehr
    wohl daraus stammt.
    """
    if erzeuger not in PORTFOLIO_JE_ERZEUGER:
        raise ManifestError(
            f"unbekannter Erzeuger {erzeuger!r} — bekannt: "
            f"{list(PORTFOLIO_JE_ERZEUGER)}"
        )
    return {**ROLLEN_DATEIEN, "portfolio": PORTFOLIO_JE_ERZEUGER[erzeuger]}


def pruefe_erzeuger(daten: Mapping[str, Any], erwartet: str) -> None:
    """Sagen, welche Sorte Lauf man erwartet — und sonst hart anhalten.

    Seit es zwei Erzeuger gibt, ist ``validate_manifest`` allein keine
    Zusicherung mehr: Es sagt nur, dass das Manifest WOHLGEFORMT ist,
    nicht, dass es zum Kommando passt. Ein Betriebskommando, das den
    Stand eines Migrationszugangs als Tageslauf-Stand nimmt, rechnete
    auf der halben Wahrheit weiter (die uebernommenen Vertraege ohne das
    eigene Geschaeft). Deshalb nennt jeder Leser seine Erwartung.
    """
    tatsaechlich = daten.get("erzeuger")
    if tatsaechlich != erwartet:
        raise ManifestError(
            f"Laufmanifest von {tatsaechlich!r}, erwartet {erwartet!r} — "
            "dieses Kommando arbeitet auf einem anderen Lauftyp"
        )


def nebentabellen_in(verzeichnis: Path) -> Dict[str, Path]:
    """Die Nebentabellen, die in einem Verzeichnis tatsaechlich liegen (Rolle -> Pfad)."""
    verzeichnis = Path(verzeichnis)
    return {
        rolle: verzeichnis / ROLLEN_DATEIEN[rolle]
        for rolle in NEBENTABELLEN
        if (verzeichnis / ROLLEN_DATEIEN[rolle]).is_file()
    }


def lauf_eingaben(lauf: Path, config_pfad: Optional[Path] = None) -> Dict[str, Path]:
    """Das Eingaben-Mapping der P-B1-Engine fuer ein Laufverzeichnis.

    Wer die Engine (``bestand.vorbedingungen.lies_und_pruefe_pb1``) ruft,
    baut ihre Eingaben nicht selbst, sondern hier — aus ``ROLLEN_DATEIEN``
    (Betriebsbefund N-01, 2026-09-08): Vier Aufrufer tippten die Rollen ab,
    drei vollstaendig, die Wache des Tageslaufs ohne ``schichten`` und
    ``verankerung``. Die Engine leitete den Storno eines uebernommenen
    Vertrags dann ohne Korrekturschicht her und meldete das korrekt
    gebuchte Ledger als falsch. Pflichtrollen werden immer genannt (fehlen
    sie, meldet es der Aufrufer oder die Engine), Nebentabellen nur, wenn
    sie im Verzeichnis liegen; ``config`` kommt vom Aufrufer.
    """
    lauf = Path(lauf)
    eingaben: Dict[str, Path] = {rolle: lauf / ROLLEN_DATEIEN[rolle] for rolle in PFLICHT_ROLLEN}
    eingaben.update(nebentabellen_in(lauf))
    if config_pfad is not None:
        eingaben["config"] = Path(config_pfad)
    return eingaben


class ManifestError(ValueError):
    """Das Manifest fehlt oder ist nicht das Erzeugnis von cli_fortschreibung."""


def sha256_bytes(daten: bytes) -> str:
    return hashlib.sha256(daten).hexdigest()


def manifest_pfad(lauf: Path) -> Path:
    return Path(lauf) / MANIFEST_DATEI


def schreibe_manifest(
    lauf: Path,
    *,
    horizont: _dt.date,
    neuzugang_ab: Optional[_dt.date],
    config_pfad: Path,
    ausgaben: Sequence[Path],
    eingaben: Optional[Mapping[str, Path]] = None,
    erzeuger: str = ERZEUGER,
) -> Path:
    """Das Manifest NACH den Ausgaben schreiben — ueber deren Bytes.

    ``ausgaben`` sind die Dateien, die der Lauf tatsaechlich geschrieben
    hat (nur die: ``bestand.parquet`` gibt es nur ohne ``--portfolio``).
    ``eingaben`` sind mitgebrachte Dateien (Portfolio, Merkmale), deren
    Herkunft der Lauf ebenfalls festhaelt.
    """
    from rechner_pipeline.kern import __version__ as kern_version

    lauf = Path(lauf)
    inhalt: Dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "erzeuger": erzeuger,
        "kern_version": kern_version,
        "horizont": horizont.isoformat(),
        "neuzugang_ab": neuzugang_ab.isoformat() if neuzugang_ab else None,
        "config": {
            "datei": Path(config_pfad).name,
            "sha256": sha256_bytes(Path(config_pfad).read_bytes()),
        },
        "eingaben": {
            rolle: {"datei": Path(p).name, "sha256": sha256_bytes(Path(p).read_bytes())}
            for rolle, p in sorted((eingaben or {}).items())
        },
        "ausgaben": {
            Path(p).name: sha256_bytes(Path(p).read_bytes())
            for p in sorted(ausgaben, key=lambda p: Path(p).name)
        },
    }
    from rechner_pipeline.bestand.parquet_io import neue_datei

    text = json.dumps(inhalt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ziel = manifest_pfad(lauf)
    # Atomar wie die Parquet-Ausgaben (nie ein halbes Manifest) und mit
    # dem Modus der umask zum Schreibzeitpunkt (T18-07).
    tmp = neue_datei(lauf, ziel.name)
    try:
        tmp.write_text(text, encoding="utf-8", newline="\n")
        os.replace(tmp, ziel)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return ziel


def lies_manifest(lauf: Path) -> Dict[str, Any]:
    """Das Manifest eines Laufs lesen — fail-fast, mit Ausweg in der Meldung.

    ``lauf`` ist das Laufverzeichnis oder die Manifest-Datei selbst. Ein
    Lauf ohne Manifest ist ein Lauf, dessen Horizont niemand belegt; er
    wird nicht 'mit Vorbehalt' angenommen, sondern abgewiesen.
    """
    return manifest_aus_bytes(lies_manifest_bytes(lauf))


def lies_manifest_bytes(lauf: Path) -> bytes:
    """Die Manifest-Bytes lesen (fuer Konsumenten, die sie auch hashen)."""
    lauf = Path(lauf)
    pfad = lauf if lauf.is_file() else manifest_pfad(lauf)
    if not pfad.is_file():
        raise ManifestError(
            f"kein Laufmanifest unter {pfad} — der Lauf belegt seinen Horizont "
            "nicht. Erzeugt wird es von bestand.cli_fortschreibung (ab dem "
            "Stand mit Laufmanifest); einen aelteren Lauf neu fortschreiben, "
            "nicht das Manifest von Hand anlegen"
        )
    try:
        return pfad.read_bytes()
    except OSError as exc:
        raise ManifestError(f"Laufmanifest {pfad} nicht lesbar: {exc}") from exc


def manifest_aus_bytes(daten: bytes) -> Dict[str, Any]:
    try:
        manifest = json.loads(daten.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestError(f"Laufmanifest nicht lesbar: {exc}") from exc
    fehler = validate_manifest(manifest)
    if fehler:
        raise ManifestError("Laufmanifest ungueltig: " + "; ".join(fehler))
    return manifest


def validate_manifest(daten: Any) -> List[str]:
    """Struktur-Contract des Manifests (Fehlerlisten-Idiom)."""
    fehler: List[str] = []
    if not isinstance(daten, dict):
        return ["Manifest ist kein JSON-Objekt"]
    if daten.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        fehler.append(
            f"schema_version {daten.get('schema_version')!r}, "
            f"erwartet {MANIFEST_SCHEMA_VERSION}"
        )
    if daten.get("erzeuger") not in ERZEUGER_ERLAUBT:
        fehler.append(
            f"erzeuger {daten.get('erzeuger')!r}, erwartet einen von "
            f"{list(ERZEUGER_ERLAUBT)}"
        )
    try:
        _dt.date.fromisoformat(str(daten.get("horizont")))
    except ValueError:
        fehler.append(f"horizont {daten.get('horizont')!r} ist kein ISO-Datum")
    if daten.get("neuzugang_ab") is not None:
        try:
            _dt.date.fromisoformat(str(daten["neuzugang_ab"]))
        except ValueError:
            fehler.append(f"neuzugang_ab {daten['neuzugang_ab']!r} ist kein ISO-Datum")
    config = daten.get("config")
    if not isinstance(config, dict) or not _ist_sha256(config.get("sha256")):
        fehler.append("config.sha256 fehlt oder ist keine SHA-256")
    ausgaben = daten.get("ausgaben")
    if not isinstance(ausgaben, dict) or not ausgaben:
        fehler.append("ausgaben fehlen")
    else:
        for name, summe in ausgaben.items():
            if not _ist_sha256(summe):
                fehler.append(f"ausgaben[{name}] ist keine SHA-256")
    return fehler


def _ist_sha256(wert: Any) -> bool:
    return isinstance(wert, str) and len(wert) == 64 and all(
        c in "0123456789abcdef" for c in wert
    )


def horizont(daten: Mapping[str, Any]) -> _dt.date:
    return _dt.date.fromisoformat(str(daten["horizont"]))
