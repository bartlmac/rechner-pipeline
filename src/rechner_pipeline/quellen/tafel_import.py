"""Deterministischer Tafel-Import: Vorverdichtung -> kern/tafeln.xml.

Traegt die von einer Tarif-Spez angeforderten Sterbetafel-Vektoren aus
der Tafeln-CSV einer Vorverdichtung in die Rechnungsgrundlagen des
Kerns ein und rechnet die Unisex-Ableitungen der Spez aus — die
VBA-Mischformel als einmalige DATEN-Ableitung::

    qx_U = min(1, f * qx_M + (1 - f) * qx_F)    je Alter

Regeln:

* Kein stiller Overwrite (P2): fuehrt der Kern eine angeforderte Tafel
  bereits, muss sie WERTGLEICH sein — sonst harter Konflikt mit beiden
  Quellen in der Meldung. Gleiches gilt fuer Kontrollvektoren, die in
  Quelle und Kern liegen (Provenienz-Kreuzprobe).
* Provenienz je Tafel (P1): vollstaendige SHA-256-Werte der registrierten
  XLSM, des Exportmanifests und der konkreten Blatt-CSV plus
  Fundstellen-Bereich bzw. Ableitungsregel als XML-Kommentar direkt an
  der Tafel. Fehlende oder nachtraeglich veraenderte Kettenglieder
  blockieren auch im ``--dry-run``.
* Fachliche Integritaet: jede Alterstafel traegt genau die eindeutigen,
  ganzzahligen Alter 0..MAX_ALTER; qx ist endlich und liegt in [0, 1].
  Derselbe Vertrag gilt beim Laden des vorhandenen Kern-XML.
* Deterministisch: gleiche Eingaben ergeben byte-gleiches XML (neue
  Tafeln alphabetisch sortiert vor ``</tafeln>`` eingefuegt).

Producer-CLI (kein Gate)::

    python -m rechner_pipeline.quellen.tafel_import \\
        --fall faelle/baldrian-klv-tg2015 --generation klv/tg2015 \\
        [--tafeln-xml src/rechner_pipeline/kern/tafeln.xml] [--dry-run]

Knoten: klv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import stat
import sys
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import StringIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rechner_pipeline.kern.tafeln import _parse_tables, validiere_alterstafel
from rechner_pipeline.models.manifest import ExportManifest, file_sha256


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class TafelImportFehler(ValueError):
    """Fachlicher Fehler beim Import (fail-fast, kein stiller Zustand)."""


def _lese_regulaere_datei_no_follow(path: Path) -> bytes:
    """Lies genau ein regulaeres Dateiobjekt, ohne einem Symlink zu folgen."""
    if path.is_symlink():
        raise TafelImportFehler(f"Blatt-CSV darf kein Symlink sein: {path}")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise TafelImportFehler(
            f"Blatt-CSV {path} ist nicht sicher lesbar: {exc}"
        ) from exc
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode):
            raise TafelImportFehler(
                f"Blatt-CSV muss eine regulaere Datei sein: {path}"
            )
        with os.fdopen(fd, "rb") as f:
            fd = -1
            return f.read()
    finally:
        if fd >= 0:
            os.close(fd)


def _csv_zeilen(inhalt: bytes, path: Path) -> List[List[str]]:
    try:
        text = inhalt.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TafelImportFehler(
            f"Blatt-CSV {path} ist nicht als UTF-8 lesbar: {exc}"
        ) from exc
    return list(csv.reader(StringIO(text), delimiter=";"))


def _lade_exportmanifest(verzeichnis: Path) -> Tuple[Path, ExportManifest]:
    manifest_pfad = verzeichnis / "export_manifest.json"
    if not manifest_pfad.is_file():
        raise TafelImportFehler(
            f"Vorverdichtung ohne Exportmanifest: {manifest_pfad} — extract "
            "fuer die registrierte XLSM erneut laufen lassen"
        )
    try:
        roh = json.loads(manifest_pfad.read_text(encoding="utf-8"))
        if not isinstance(roh, dict):
            raise ValueError("Wurzel ist kein JSON-Objekt")
        return manifest_pfad, ExportManifest.from_dict(roh)
    except (OSError, TypeError, ValueError, KeyError) as exc:
        raise TafelImportFehler(
            f"Exportmanifest {manifest_pfad} ist nicht lesbar: {exc}"
        ) from exc


def _tafeln_csv_aus_manifest(verzeichnis: Path) -> Path:
    """Loese das Originalblatt ``Tafeln`` auf sein gebundenes Artefakt auf."""
    _manifest_pfad, manifest = _lade_exportmanifest(verzeichnis)
    if not manifest.sheet_artifacts:
        # Kompatibilitaet mit Vorverdichtungen vor dem 10.14-Manifestvertrag.
        return verzeichnis / "Tafeln.csv"

    bindungen = [
        eintrag
        for eintrag in manifest.sheet_artifacts
        if eintrag.original_name == "Tafeln"
    ]
    if len(bindungen) != 1:
        raise TafelImportFehler(
            "Exportmanifest muss den Originalblattnamen 'Tafeln' genau einmal "
            f"an einen Dateinamen binden, gefunden: {len(bindungen)}"
        )
    dateiname = bindungen[0].file_name
    if not dateiname or Path(dateiname).name != dateiname:
        raise TafelImportFehler(
            f"Exportmanifest bindet fuer Blatt 'Tafeln' keinen sicheren "
            f"Dateinamen: {dateiname!r}"
        )
    sheet_csv_eintraege = [
        eintrag
        for eintrag in manifest.sheet_csvs
        if Path(eintrag).name == dateiname
    ]
    if len(sheet_csv_eintraege) != 1:
        raise TafelImportFehler(
            f"Exportmanifest muss den fuer Blatt 'Tafeln' gebundenen Dateinamen "
            f"{dateiname!r} genau einmal in sheet_csvs nennen, gefunden: "
            f"{len(sheet_csv_eintraege)}"
        )
    return verzeichnis / dateiname


def _pruefe_alterstafel(
    name: str, werte: Dict[int, float], quelle: Optional[str] = None
) -> None:
    try:
        validiere_alterstafel(name, werte)
    except ValueError as exc:
        praefix = f"{quelle}: " if quelle else ""
        raise TafelImportFehler(f"{praefix}{exc}") from exc


def _pruefe_exportkette(
    fall: Path,
    quelle_datei: str,
    registrierter_sha256: object,
    tafeln_csv: Path,
    tafeln_csv_bytes: bytes,
) -> Dict[str, str]:
    """Registrierte XLSM, Exportmanifest und konkrete Blatt-CSV binden.

    Das Manifest ist der deterministische Uebersetzungsbeleg zwischen den
    registrierten Workbook-Bytes und den exportierten Blatt-Bytes. Ein bloss
    passender Dateiname beweist diese Uebersetzung nicht: Quelle und Blatt
    muessen deshalb mit ihren vollstaendigen SHA-256-Werten im Manifest stehen
    und beim Import noch bytegleich vorhanden sein.
    """
    if not isinstance(registrierter_sha256, str) or not _SHA256_RE.fullmatch(
        registrierter_sha256
    ):
        raise TafelImportFehler(
            f"Eingang-Register: {quelle_datei!r} hat keinen vollstaendigen "
            "SHA-256-Wert"
        )

    registrierte_xlsm = fall / "eingang" / quelle_datei
    if not registrierte_xlsm.is_file():
        raise TafelImportFehler(
            f"Registrierte XLSM fehlt: {registrierte_xlsm} — Fall-Eingang "
            "pruefen und Vorverdichtung erneut erzeugen"
        )
    aktueller_xlsm_sha256 = file_sha256(registrierte_xlsm)
    if aktueller_xlsm_sha256 != registrierter_sha256:
        raise TafelImportFehler(
            f"Registrierte XLSM {quelle_datei!r} wurde veraendert: Register "
            f"{registrierter_sha256}, Datei {aktueller_xlsm_sha256}"
        )

    manifest_pfad, manifest = _lade_exportmanifest(tafeln_csv.parent)

    source = manifest.source
    if source is None:
        raise TafelImportFehler(
            f"Exportmanifest {manifest_pfad.name} bindet keine Quell-XLSM — "
            "extract erneut laufen lassen"
        )
    if Path(source.path).name != quelle_datei:
        raise TafelImportFehler(
            f"Exportmanifest bindet Quelle {Path(source.path).name!r}, "
            f"erwartet ist die registrierte XLSM {quelle_datei!r}"
        )
    if not _SHA256_RE.fullmatch(source.sha256):
        raise TafelImportFehler(
            "Exportmanifest.source.sha256 ist kein vollstaendiger SHA-256-Wert"
        )
    if source.sha256 != registrierter_sha256:
        raise TafelImportFehler(
            f"Exportmanifest bindet fuer {quelle_datei!r} SHA-256 "
            f"{source.sha256}, das Eingang-Register {registrierter_sha256}"
        )
    if source.bytes != registrierte_xlsm.stat().st_size:
        raise TafelImportFehler(
            f"Exportmanifest bindet fuer {quelle_datei!r} {source.bytes} Bytes, "
            f"die registrierte XLSM hat {registrierte_xlsm.stat().st_size}"
        )

    if manifest.sheet_artifacts:
        bindungen = [
            eintrag
            for eintrag in manifest.sheet_artifacts
            if eintrag.original_name == "Tafeln"
            and eintrag.file_name == tafeln_csv.name
        ]
        if len(bindungen) != 1:
            raise TafelImportFehler(
                f"Exportmanifest muss Originalblatt 'Tafeln' genau einmal an "
                f"{tafeln_csv.name!r} binden, gefunden: {len(bindungen)}"
            )

    blatt_eintraege = [
        eintrag
        for eintrag in manifest.sheet_csvs
        if Path(eintrag).name == tafeln_csv.name
    ]
    if len(blatt_eintraege) != 1:
        raise TafelImportFehler(
            f"Exportmanifest muss die konkrete Blatt-CSV {tafeln_csv.name!r} "
            f"genau einmal nennen, gefunden: {len(blatt_eintraege)}"
        )
    blatt_manifest_pfad = str(blatt_eintraege[0])
    hash_eintraege = [
        eintrag
        for eintrag in manifest.output_hashes
        if eintrag.path == blatt_manifest_pfad
    ]
    if len(hash_eintraege) != 1:
        raise TafelImportFehler(
            f"Exportmanifest muss genau einen SHA-256-Beleg fuer Blatt-CSV "
            f"{blatt_manifest_pfad!r} tragen, gefunden: {len(hash_eintraege)}"
        )
    blatt_hash = hash_eintraege[0]
    if not _SHA256_RE.fullmatch(blatt_hash.sha256):
        raise TafelImportFehler(
            f"Exportmanifest-Hash fuer {tafeln_csv.name!r} ist kein "
            "vollstaendiger SHA-256-Wert"
        )
    aktueller_csv_sha256 = sha256(tafeln_csv_bytes).hexdigest()
    if blatt_hash.sha256 != aktueller_csv_sha256:
        raise TafelImportFehler(
            f"Blatt-CSV {tafeln_csv.name!r} wurde nach dem Export veraendert: "
            f"Manifest {blatt_hash.sha256}, Datei {aktueller_csv_sha256}"
        )
    if blatt_hash.bytes != len(tafeln_csv_bytes):
        raise TafelImportFehler(
            f"Exportmanifest bindet fuer {tafeln_csv.name!r} "
            f"{blatt_hash.bytes} Bytes, gelesen wurden {len(tafeln_csv_bytes)}"
        )

    zeilen = _csv_zeilen(tafeln_csv_bytes, tafeln_csv)
    kopf = zeilen[0] if zeilen else None
    blattnamen = {
        zeile[0] for zeile in zeilen[1:] if zeile and zeile[0]
    }
    if not manifest.sheet_artifacts and kopf and kopf[0] == "Tafeln":
        # Historische synthetische Manifeste konnten noch ohne Kopfzeile
        # geschrieben werden; ihre erste Datenzeile zaehlt zur Blattbindung.
        blattnamen.add(kopf[0])
    falscher_kopf = (
        bool(manifest.sheet_artifacts)
        and kopf != ["Blatt", "Adresse", "Formel", "Wert"]
    )
    if falscher_kopf or blattnamen != {"Tafeln"}:
        raise TafelImportFehler(
            f"Blatt-CSV {tafeln_csv.name!r} bindet intern nicht eindeutig den "
            f"Originalblattnamen 'Tafeln' (Kopf {kopf!r}, Blattnamen "
            f"{sorted(blattnamen)!r})"
        )

    return {
        "xlsm_sha256": registrierter_sha256,
        "exportmanifest_sha256": file_sha256(manifest_pfad),
        "blatt_csv_sha256": aktueller_csv_sha256,
    }


def lese_tafel_vektoren(
    tafeln_csv: Path,
    inhalt: bytes | None = None,
) -> Dict[str, Dict[int, float]]:
    """Alle benannten qx-Vektoren einer Tafeln-CSV (Blatt;Adresse;Formel;Wert).

    Kopfzeile ist Zeile 3 (Vektornamen je Spalte), die Alter stehen in
    Spalte A ab Zeile 4. Luecken sind fail-fast — ein Vektor mit Loch
    ist keine Tafel.
    """
    zellen: Dict[Tuple[str, int], str] = {}
    if inhalt is None:
        inhalt = _lese_regulaere_datei_no_follow(tafeln_csv)
    for zeile in _csv_zeilen(inhalt, tafeln_csv):
        if len(zeile) < 4 or zeile[0] != "Tafeln":
            continue
        m = re.match(r"^\$([A-Z]+)\$(\d+)$", zeile[1])
        if m:
            schluessel = (m.group(1), int(m.group(2)))
            if schluessel in zellen:
                raise TafelImportFehler(
                    f"{tafeln_csv.name}: Zelladresse "
                    f"{m.group(0)} doppelt — Export ist nicht eindeutig"
                )
            zellen[schluessel] = zeile[3]

    spalten = sorted({s for (s, z) in zellen if z == 3 and s != "A"})
    kopfnamen = [zellen[(s, 3)] for s in spalten]
    if len(set(kopfnamen)) != len(kopfnamen):
        doppelt = sorted({n for n in kopfnamen if kopfnamen.count(n) > 1})
        raise TafelImportFehler(
            f"{tafeln_csv.name}: doppelte Vektornamen {doppelt} — der "
            "Gewinner hinge an der Spaltenreihenfolge"
        )
    alter_zeilen = sorted(z for (s, z) in zellen if s == "A" and z >= 4)
    alter_nach_zeile: Dict[int, int] = {}
    zeile_nach_alter: Dict[int, int] = {}
    for z in alter_zeilen:
        roh_alter = zellen[("A", z)].strip()
        try:
            dezimal = Decimal(roh_alter)
        except InvalidOperation as exc:
            raise TafelImportFehler(
                f"{tafeln_csv.name}: Alter {roh_alter!r} in Zeile {z} "
                "ist nicht ganzzahlig"
            ) from exc
        if not dezimal.is_finite() or dezimal != dezimal.to_integral_value():
            raise TafelImportFehler(
                f"{tafeln_csv.name}: Alter {roh_alter!r} in Zeile {z} "
                "ist nicht ganzzahlig"
            )
        alter = int(dezimal)
        if alter in zeile_nach_alter:
            raise TafelImportFehler(
                f"{tafeln_csv.name}: Alter {alter} ist in den Zeilen "
                f"{zeile_nach_alter[alter]} und {z} doppelt"
            )
        alter_nach_zeile[z] = alter
        zeile_nach_alter[alter] = z

    vektoren: Dict[str, Dict[int, float]] = {}
    for spalte in spalten:
        name = zellen[(spalte, 3)]
        werte: Dict[int, float] = {}
        for z in alter_zeilen:
            alter = alter_nach_zeile[z]
            roh = zellen.get((spalte, z))
            if roh is None or roh == "":
                raise TafelImportFehler(
                    f"Vektor {name!r}: Alter {alter} (Zeile {z}) ohne Wert — "
                    "eine Tafel mit Loch wird nicht importiert"
                )
            try:
                werte[alter] = float(roh)
            except ValueError as exc:
                raise TafelImportFehler(
                    f"Vektor {name!r}: qx {roh!r} bei Alter {alter} "
                    "ist keine Zahl"
                ) from exc
        _pruefe_alterstafel(name, werte, tafeln_csv.name)
        vektoren[name] = werte
    return vektoren


def leite_unisex_ab(
    qx_m: Dict[int, float], qx_f: Dict[int, float], maenneranteil: float
) -> Dict[int, float]:
    """Die VBA-Mischformel, einmal ausgerechnet (bit-treu: gleiche Doubles)."""
    if set(qx_m) != set(qx_f):
        raise TafelImportFehler("Unisex-Ableitung: M/F-Altersbereiche ungleich")
    return {
        alter: min(1.0, maenneranteil * qx_m[alter]
                   + (1.0 - maenneranteil) * qx_f[alter])
        for alter in sorted(qx_m)
    }


def _lade_bestehende(
    tafeln_xml: Path,
) -> Tuple[Dict[str, Dict[int, float]], set]:
    """Alterstafeln (mit Werten) und ALLE vergebenen Tafelnamen.

    Die Namensmenge enthaelt auch Select-Tafeln: eine neue Alterstafel
    unter dem Namen einer bestehenden Select-Tafel waere sonst ein
    unbemerktes Namens-Duplikat im XML.
    """
    try:
        bestehende, select_tafeln = _parse_tables(
            tafeln_xml.read_text(encoding="utf-8")
        )
    except (OSError, ValueError) as exc:
        raise TafelImportFehler(
            f"Kern-XML {tafeln_xml} ist ungueltig: {exc}"
        ) from exc
    return bestehende, set(bestehende) | set(select_tafeln)


def _pruefe_wertgleich(
    name: str, neu: Dict[int, float], vorhanden: Dict[int, float]
) -> List[str]:
    fehler = []
    gemeinsame = sorted(set(neu) & set(vorhanden))
    for alter in gemeinsame:
        if neu[alter] != vorhanden[alter]:
            fehler.append(
                f"Tafel {name!r}, Alter {alter}: Quelle {neu[alter]!r} != "
                f"Kern {vorhanden[alter]!r} — kein stiller Overwrite; erst "
                "die Provenienz klaeren"
            )
    return fehler


def _qx_repr(wert: float) -> str:
    return repr(wert)


def _setze_provenienzkommentar(
    text: str, name: str, provenienz: str
) -> Tuple[str, bool]:
    """Provenienz direkt vor einer bestehenden Tafel setzen.

    Wertgleiche Tafeln werden nicht neu geschrieben, ihr Herkunftsbeleg muss
    aber den aktuell validierten Importvertrag tragen. Sonst konserviert ein
    idempotenter Reimport gerade die veraltete oder gekuerzte Provenienz, die
    er korrigieren soll. Andere Kommentare bleiben erhalten; nur ein direkt
    vorangestellter Provenienz-/Ableitungskommentar wird ersetzt.
    """
    marker = f'<table name="{name}">'
    if text.count(marker) != 1:
        raise TafelImportFehler(
            f"Tafel {name!r}: XML-Element fuer Provenienzaktualisierung "
            f"nicht eindeutig, gefunden: {text.count(marker)}"
        )
    table_start = text.index(marker)
    zeilenanfang = text.rfind("\n", 0, table_start) + 1
    einzug = text[zeilenanfang:table_start]
    kommentar = f"{einzug}<!-- {provenienz} -->"

    vorheriges_ende = zeilenanfang - 1
    if vorheriges_ende >= 0:
        vorheriger_anfang = text.rfind("\n", 0, vorheriges_ende) + 1
        vorherige_zeile = text[vorheriger_anfang:vorheriges_ende]
        vorheriger_kommentar = vorherige_zeile.strip()
        if (
            vorheriger_kommentar.startswith("<!-- Provenienz")
            or vorheriger_kommentar.startswith("<!-- Abgeleitet")
        ) and vorheriger_kommentar.endswith("-->"):
            if vorherige_zeile == kommentar:
                return text, False
            return (
                text[:vorheriger_anfang]
                + kommentar
                + text[vorheriges_ende:],
                True,
            )

    return text[:zeilenanfang] + kommentar + "\n" + text[zeilenanfang:], True


def fuege_tafeln_ein(
    tafeln_xml: Path,
    neue: Dict[str, Dict[int, float]],
    provenienz: Dict[str, str],
) -> List[str]:
    """Tafeln/Provenienz deterministisch schreiben; Rueckgabe = neue Namen.

    Textbasiertes Einfuegen vor ``</tafeln>`` (kein Re-Serialisieren des
    Bestands). Bei wertgleichen vorhandenen Tafeln wird ausschliesslich der
    direkt vorangestellte Herkunftskommentar auf die validierte Exportkette
    aktualisiert; die Tafelwerte bleiben byte-identisch.
    """
    bestehende, alle_namen = _lade_bestehende(tafeln_xml)
    konflikte: List[str] = []
    einzufuegen: Dict[str, Dict[int, float]] = {}
    for name in sorted(neue):
        # Defensive zweite Grenze fuer programatische Aufrufer neben dem
        # CSV-Import: direkte Einfuegeaufrufe duerfen keine ungueltige
        # Rechnungsgrundlage akzeptieren.
        _pruefe_alterstafel(name, neue[name])
        if name in bestehende:
            konflikte.extend(_pruefe_wertgleich(name, neue[name], bestehende[name]))
            mehr = sorted(set(neue[name]) - set(bestehende[name]))
            if mehr:
                konflikte.append(
                    f"Tafel {name!r}: Quelle traegt zusaetzliche Alter "
                    f"{mehr[:5]}{'…' if len(mehr) > 5 else ''} — eine "
                    "Tafel-Erweiterung ist ein eigener Vorgang, kein Import"
                )
            continue  # wertgleich vorhanden: nichts zu tun
        if name in alle_namen:
            konflikte.append(
                f"Tafel {name!r}: Name ist im XML bereits vergeben "
                "(Select-Tafel) — Namens-Duplikat"
            )
            continue
        einzufuegen[name] = neue[name]
    if konflikte:
        raise TafelImportFehler("; ".join(konflikte[:5]))

    text = tafeln_xml.read_text(encoding="utf-8")
    geaendert = False
    for name in sorted(set(neue) & set(bestehende)):
        text, kommentar_geaendert = _setze_provenienzkommentar(
            text, name, provenienz[name]
        )
        geaendert = geaendert or kommentar_geaendert

    if not einzufuegen:
        if geaendert:
            tafeln_xml.write_text(text, encoding="utf-8")
        return []
    schluss = "</tafeln>"
    if schluss not in text:
        raise TafelImportFehler(f"{tafeln_xml}: kein {schluss}-Schluss gefunden")
    bloecke: List[str] = []
    for name in sorted(einzufuegen):
        zeilen = [f"  <!-- {provenienz[name]} -->", f'  <table name="{name}">']
        for alter in sorted(einzufuegen[name]):
            zeilen.append(
                f'    <entry age="{alter}" qx="{_qx_repr(einzufuegen[name][alter])}" />'
            )
        zeilen.append("  </table>")
        bloecke.append("\n".join(zeilen))
    text = text.replace(schluss, "\n".join(bloecke) + "\n" + schluss, 1)
    tafeln_xml.write_text(text, encoding="utf-8")
    return sorted(einzufuegen)


def importiere_fuer_spez(
    fall: Path,
    generation: str,
    tafeln_xml: Path,
    dry_run: bool = False,
) -> Dict[str, object]:
    """Tafel-Importe und -Ableitungen einer Spez anwenden."""
    from rechner_pipeline.spez.validierung import lade_spez

    spez = lade_spez(fall, generation)
    gen_name = generation.rsplit("/", 1)[-1].upper()
    quelle_datei = f"Tarifrechner_KLV_{gen_name}.xlsm"
    vorverdichtung = (
        fall / "abgeleitet" / "vorverdichtung" / f"xlsm-{gen_name}"
    )
    tafeln_csv = _tafeln_csv_aus_manifest(vorverdichtung)
    if not tafeln_csv.is_file():
        raise TafelImportFehler(f"Vorverdichtung fehlt: {tafeln_csv}")
    tafeln_csv_bytes = _lese_regulaere_datei_no_follow(tafeln_csv)
    register = json.loads((fall / "eingang.json").read_text(encoding="utf-8"))
    register_eintraege = [
        q for q in register.get("quellen", [])
        if isinstance(q, dict) and q.get("datei") == quelle_datei
    ]
    if len(register_eintraege) != 1:
        raise TafelImportFehler(
            f"{quelle_datei!r} muss genau einmal im Eingang-Register stehen, "
            f"gefunden: {len(register_eintraege)} — Import nur aus eindeutig "
            "registrierten Quellen (P1)"
        )
    beleg = _pruefe_exportkette(
        fall,
        quelle_datei,
        register_eintraege[0].get("sha256"),
        tafeln_csv,
        tafeln_csv_bytes,
    )

    vektoren = lese_tafel_vektoren(tafeln_csv, tafeln_csv_bytes)
    neue: Dict[str, Dict[int, float]] = {}
    provenienz: Dict[str, str] = {}
    for name in spez.tafel_importe:
        if name not in vektoren:
            raise TafelImportFehler(
                f"Spez verlangt Tafel {name!r}, die Vorverdichtung "
                f"({tafeln_csv.name}) kennt sie nicht "
                f"(vorhanden: {sorted(vektoren)})"
            )
        neue[name] = vektoren[name]
        provenienz[name] = (
            f"Provenienz: XLSM {quelle_datei} "
            f"(sha256 {beleg['xlsm_sha256']}), Exportmanifest "
            f"(sha256 {beleg['exportmanifest_sha256']}), Blatt-CSV "
            f"{tafeln_csv.name} (sha256 {beleg['blatt_csv_sha256']}), "
            f"Blatt Tafeln, Vektor {name}; importiert via quellen.tafel_import"
        )
    for ableitung in spez.tafel_ableitungen:
        qx_m = neue.get(ableitung.basis_m) or vektoren.get(ableitung.basis_m)
        qx_f = neue.get(ableitung.basis_f) or vektoren.get(ableitung.basis_f)
        if qx_m is None or qx_f is None:
            raise TafelImportFehler(
                f"Ableitung {ableitung.name!r}: Basis {ableitung.basis_m!r}/"
                f"{ableitung.basis_f!r} nicht verfuegbar"
            )
        neue[ableitung.name] = leite_unisex_ab(
            qx_m, qx_f, ableitung.maenneranteil
        )
        provenienz[ableitung.name] = (
            f"Abgeleitet: min(1, {ableitung.maenneranteil}*qx[{ableitung.basis_m}] "
            f"+ {1.0 - ableitung.maenneranteil}*qx[{ableitung.basis_f}]) je Alter "
            f"(VBA-Mischformel {spez.unisex}); Basen aus {quelle_datei} "
            f"(sha256 {beleg['xlsm_sha256']}) via Exportmanifest "
            f"(sha256 {beleg['exportmanifest_sha256']}) und Blatt-CSV "
            f"{tafeln_csv.name} (sha256 {beleg['blatt_csv_sha256']}); "
            "abgeleitet via quellen.tafel_import"
        )

    # Auch im --dry-run gilt der Schreibvertrag fuer alle importierten und
    # abgeleiteten Vektoren. Die zweite Pruefung neben dem CSV-Parser faengt
    # insbesondere eine ungueltige Ableitung oder einen programatischen
    # Aufrufer ab, bevor Bestand und Quelle verglichen werden.
    for name in sorted(neue):
        _pruefe_alterstafel(name, neue[name])

    # Kreuzprobe: Vektoren, die Quelle UND Kern fuehren, muessen wertgleich
    # sein — auch wenn die Spez sie nicht anfordert (stiller Drift der
    # Rechnungsgrundlagen zwischen Generationen waere sonst unsichtbar).
    bestehende, _ = _lade_bestehende(tafeln_xml)
    kreuzprobe = sorted(set(vektoren) & set(bestehende))
    konflikte: List[str] = []
    for name in kreuzprobe:
        konflikte.extend(_pruefe_wertgleich(name, vektoren[name], bestehende[name]))
    # Auch die ABLEITUNGEN gegen einen etwaigen Bestand pruefen — im
    # dry-run genauso wie scharf (sonst meldet der Trockenlauf
    # "wertgleich vorhanden", ohne je verglichen zu haben).
    vorhanden_wertgleich: List[str] = []
    for name in sorted(set(neue) & set(bestehende)):
        abweichungen = _pruefe_wertgleich(name, neue[name], bestehende[name])
        if abweichungen:
            konflikte.extend(abweichungen)
        else:
            vorhanden_wertgleich.append(name)
    if konflikte:
        raise TafelImportFehler("; ".join(konflikte[:5]))

    if dry_run:
        eingefuegt: List[str] = []
    else:
        eingefuegt = fuege_tafeln_ein(tafeln_xml, neue, provenienz)
    return {
        "generation": generation,
        "quelle": quelle_datei,
        "quellbeleg": beleg,
        "angefordert": sorted(neue),
        "eingefuegt": eingefuegt,
        "bereits_vorhanden_wertgleich": vorhanden_wertgleich,
        "kreuzprobe_wertgleich": kreuzprobe,
        "tafeln_xml": str(tafeln_xml),
        "dry_run": dry_run,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.quellen.tafel_import",
        description="Tafel-Vektoren einer Spez in kern/tafeln.xml eintragen.",
    )
    parser.add_argument("--fall", required=True)
    parser.add_argument("--generation", required=True, help="z. B. klv/tg2015")
    parser.add_argument(
        "--tafeln-xml",
        default="src/rechner_pipeline/kern/tafeln.xml",
        help="Ziel-XML (Default: die Paket-Rechnungsgrundlagen).",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        ergebnis = importiere_fuer_spez(
            Path(args.fall), args.generation, Path(args.tafeln_xml),
            dry_run=args.dry_run,
        )
    except TafelImportFehler as exc:
        print(f"tafel_import: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(ergebnis, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
