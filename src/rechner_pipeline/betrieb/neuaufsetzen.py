"""Betrieb neu aufsetzen — der Betriebsweg der Freischaltung (Schritt 9).

Die Laufzeitumgebung der PLV fuehrte den uebernommenen Bestand in einer
anderen Welt als die Abnahmen (Review T22-11). Der Entwicklerweg hat den
Fall korrigiert (Schritt 8); der Betriebsweg setzt die Laufzeit daraus neu
auf::

    python -m rechner_pipeline.betrieb.neuaufsetzen --stand ~/apps/plv/daten \\
        --fall faelle/<fall> --stichtag 2026-01-01 [--config configs/bestand_gesamt.toml] \\
        --freigabe-schluessel <freigabeschluessel> \\
        --betriebsschluessel <betriebsschluessel> --zeichnungsordnung <ordnung> \\
        [--aufschalten]

Was die Routine tut, in dieser Reihenfolge — und was sie NICHT tut:

1. Sie prueft, bevor sie etwas bewegt: keine Lauf-Sperre, eine Ablage mit
   Config, der Fall mit Zugangsstand, und die Tarifwerk-Schalter der Config
   stimmen mit dem Uebernahmebeleg des Falls ueberein (Schritt 2).
2. Sie baut die NEUE Ablage vollstaendig neben der alten auf
   (``<daten>.neu-<zeit>``): Config, Uebernahme-Eingang mit allen
   Nebentabellen und Belegen, Provenienzdatei.
3. Sie archiviert die alte Ablage durch eine Umbenennung
   (``<daten>.archiv-<zeit>``) und setzt die neue mit einer zweiten an ihre
   Stelle. Nichts wird geloescht — Journal, Protokollkette, Abschluesse und
   Berichte der alten Ablage bleiben vollstaendig erhalten (T24-07: ein
   Produzent loescht nur, was er selbst erzeugt hat; hier loescht er gar
   nichts). Ehrlich benannt: Zwischen den zwei Umbenennungen gibt es einen
   Moment OHNE Ablage — die Wurzel ist ein echtes Verzeichnis, kein
   Symlink wie ``stand`` (T22-03), ein atomarer Tausch zweier Verzeichnisse
   ist mit Bordmitteln nicht moeglich. Endet der Prozess in diesem Moment,
   vollendet der naechste, der die Ablage oeffnet (``lauf_sperre``), den
   Tausch: Die neue Ablage ist fertig, sobald ihre Provenienzdatei liegt —
   sie wird als Letztes geschrieben und nennt das Archiv. Eine leere Wurzel
   wird neben einem Aufbau nie angelegt.
   Vor dem Tausch liest die Routine den neuen Eingang einmal vollstaendig
   (``lies_uebernahme``): unbekannte Generation, falscher Stichtag, fehlende
   Merkmale oder abweichendes Tarifwerk fallen auf, BEVOR etwas bewegt ist.
4. Den Stand faehrt sie NICHT: Der naechste Tageslauf baut ihn vom
   Betriebsbeginn bis heute in einem Lauf (Erstbefuellung), danach das
   Stands-Paket. Die Routine nennt beide Kommandos.

Knoten: klv, bu
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from rechner_pipeline.bestand.config import config_aus_text, load_config
from rechner_pipeline.bestand.manifest import sha256_bytes
from rechner_pipeline.bestand.parquet_io import read_portfolio
from rechner_pipeline.betrieb.tageslauf import (
    Ablage, TageslaufError, aufschaltung_fehler, betriebszeichner, lauf_sperre,
)
from rechner_pipeline.betrieb.uebernahme import (
    UEBERNAHME_DIR, UebernahmeError, eingang_anlegen, lies_uebernahme,
    tarifwerk_fehler,
)

#: Provenienz des Neuaufbaus in der neuen Ablage.
PROVENIENZ_DATEI = "neuaufsetzen.json"
PROVENIENZ_SCHEMA_VERSION = 1


class NeuaufsetzenError(ValueError):
    """Ein Grund, den Betrieb NICHT neu aufzusetzen — mit Ausweg."""


def _zeitstempel(jetzt: Optional[_dt.datetime]) -> str:
    t = jetzt or _dt.datetime.now(_dt.timezone.utc)
    return t.astimezone(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def neu_aufsetzen(
    stand: Path,
    fall: Path,
    stichtag: _dt.date,
    *,
    config: Optional[Path] = None,
    archiv: Optional[Path] = None,
    jetzt: Optional[_dt.datetime] = None,
    schluesselring: Optional[Mapping[str, bytes]] = None,
    betriebsschluessel: Optional[Path] = None,
    zeichnungsordnung: Optional[Path] = None,
    aufschalten: bool = False,
) -> Dict[str, Any]:
    """Die Laufzeitumgebung ``stand`` aus dem Fall ``fall`` neu aufsetzen.

    ``betriebsschluessel``/``zeichnungsordnung``: der Betriebsschluessel,
    mit dem der neue Eingang gezeichnet und danach geprueft wird
    (Aufloesung wie im Tageslauf). Geladen wird er VOR jedem Aufbau.

    ``aufschalten``: Traegt das Protokoll der alten Ablage Zeilen, aber
    keine gezeichnete, wird nur damit aufgebaut — dieselbe Regel wie im
    Tageslauf (``tageslauf.aufschaltung_fehler``). Das Archiv ist danach
    die Geschichte der Ablage; ein ohne Schluessel herabgestuftes Protokoll
    wuerde sonst still dazu.

    Rueckgabe: die Provenienz (auch als ``neuaufsetzen.json`` in der neuen
    Ablage). Wirft NeuaufsetzenError/UebernahmeError, BEVOR etwas bewegt
    wurde, wann immer das moeglich ist.
    """
    stand = Path(stand)
    fall = Path(fall)
    # Der Schluessel VOR jedem Aufbau (Angriffsrunde nach T27): Die
    # Registrierung verweigert ohne ihn — erst nach dem Anlegen der neuen
    # Ablage, und der halbe Aufbau blieb daneben liegen.
    from rechner_pipeline.betrieb import uebernahme as _ueb

    if not (schluesselring if schluesselring is not None else _ueb._STANDARD_SCHLUESSELRING):
        raise NeuaufsetzenError(
            "ohne Freigabeschluessel wird nichts aufgebaut — die Registrierung des "
            "neuen Eingangs verlangt ihn; --freigabe-schluessel angeben")
    try:
        zeichner = betriebszeichner(
            Ablage(stand), betriebsschluessel, zeichnungsordnung,
            wofuer="das Neuaufsetzen", ohne="kein Aufbau", flag="--betriebsschluessel")
    except TageslaufError as exc:
        raise NeuaufsetzenError(str(exc)) from exc
    if stand.is_symlink() or not stand.is_dir():
        raise NeuaufsetzenError(
            f"{stand}: keine Ablage (kein echtes Verzeichnis) — fuer die erste "
            "Einrichtung siehe deploy/plv/README.md, neu aufgesetzt wird nur eine "
            "bestehende Ablage"
        )
    alt = Ablage(stand)
    # Dieselbe Prozess-Sperre wie der Tageslauf (Review T22-03): Haelt ein
    # Lauf sie, wird nichts bewegt. Die Sperrdatei bleibt bestehen; gehalten
    # wird sie per flock, und genau das prueft lauf_sperre.
    try:
        with lauf_sperre(alt):
            return _neu_aufsetzen_unter_sperre(
                stand, fall, stichtag, alt, config=config, archiv=archiv, jetzt=jetzt,
                schluesselring=schluesselring, betriebsschluessel=betriebsschluessel,
                zeichnungsordnung=zeichnungsordnung, zeichner=zeichner,
                aufschalten=aufschalten,
            )
    except TageslaufError as exc:
        raise NeuaufsetzenError(
            f"Sperre: {exc} — Timer anhalten, laufenden Prozess enden lassen, dann "
            "neu aufsetzen"
        ) from exc


def _protokollzeilen_formlos(pfad: Path) -> List[Dict[str, Any]]:
    """Die Zeilen des alten Protokolls als Objekte — eine unlesbare Zeile als
    leeres Objekt (ungezeichnet). Nur fuer die Frage, ob eine gezeichnet ist."""
    from rechner_pipeline.models.anker import jsonl_zeilen

    if not Path(pfad).is_file():
        return []
    zeilen: List[Dict[str, Any]] = []
    for roh in jsonl_zeilen(Path(pfad).read_text(encoding="utf-8", errors="replace")):
        try:
            zeile = json.loads(roh)
        except ValueError:
            zeile = {}
        zeilen.append(zeile if isinstance(zeile, dict) else {})
    return zeilen


def _neu_aufsetzen_unter_sperre(
    stand: Path,
    fall: Path,
    stichtag: _dt.date,
    alt: Ablage,
    *,
    config: Optional[Path],
    archiv: Optional[Path],
    jetzt: Optional[_dt.datetime],
    schluesselring: Optional[Mapping[str, bytes]] = None,
    betriebsschluessel: Optional[Path] = None,
    zeichnungsordnung: Optional[Path] = None,
    zeichner: Any = None,
    aufschalten: bool = False,
) -> Dict[str, Any]:
    # Das alte Protokoll ohne gezeichnete Zeile nur ausdruecklich
    # (Nachbesserung Runde C). Gelesen wird nur, WELCHE Zeilen gezeichnet
    # sind, nicht die Kette: Ob sie haelt, ist Sache des Tageslaufs; das
    # Archiv bewahrt sie, wie sie ist. Die Signatur wird hier nicht
    # nachgerechnet — neu aufgesetzt wird auch nach einem Schluesselwechsel.
    fehler = aufschaltung_fehler(
        _protokollzeilen_formlos(alt.protokoll_pfad), aufschalten=aufschalten,
        wer="das Neuaufsetzen")
    if fehler:
        raise NeuaufsetzenError(
            f"{alt.protokoll_pfad}: {fehler} (hier: neuaufsetzen --aufschalten); "
            "nichts bewegt")
    config_quelle = Path(config) if config is not None else alt.config_pfad
    if not config_quelle.is_file():
        raise NeuaufsetzenError(
            f"{config_quelle}: keine Config — --config <bestand.toml> angeben oder "
            "die Config der bestehenden Ablage pflegen"
        )
    config_bytes = config_quelle.read_bytes()
    # Geprueft wird, was geschrieben wird (Kalibrierungsfund N9 der
    # Pruefrunde T27, dieselbe Naht wie T27-04): Die erste Fassung las die
    # Config fuer die Pruefung ein zweites Mal von der Platte und schrieb
    # die zuerst gelesenen Bytes in die neue Ablage — geprueft und
    # geschrieben konnten zwei verschiedene Dateien sein.
    cfg = config_aus_text(config_bytes.decode("utf-8"))
    zugangsstand = fall / "abgeleitet" / "bestand"
    if not (zugangsstand / "bestand.parquet").is_file():
        raise NeuaufsetzenError(
            f"{zugangsstand}: kein Zugangsstand (bestand.parquet fehlt) — erwartet "
            "wird das Erzeugnis von gates.bestand_uebernehmen im Fall"
        )
    generationen = read_portfolio(zugangsstand / "bestand.parquet")["tarif_generation"].unique()
    beleg_pfad = zugangsstand / "uebernahme.json"
    beleg: Dict[str, Any] = {}
    if beleg_pfad.is_file():
        try:
            beleg = json.loads(beleg_pfad.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise NeuaufsetzenError(f"{beleg_pfad}: Uebernahmebeleg nicht lesbar: {exc}") from exc
    tw = tarifwerk_fehler(cfg, generationen, beleg)
    if tw:
        raise NeuaufsetzenError(
            "Config der Laufzeit passt nicht zur Uebernahme — " + "; ".join(tw)
        )
    zeit = _zeitstempel(jetzt)
    archiv_ziel = Path(archiv) if archiv is not None else stand.with_name(f"{stand.name}.archiv-{zeit}")
    if archiv_ziel.exists():
        raise NeuaufsetzenError(f"{archiv_ziel} existiert bereits — anderes --archiv waehlen")
    neu_pfad = stand.with_name(f"{stand.name}.neu-{zeit}")
    if neu_pfad.exists():
        raise NeuaufsetzenError(f"{neu_pfad} existiert bereits — Rest eines abgebrochenen Aufbaus, von Hand klaeren")

    # 2. Neue Ablage vollstaendig NEBEN der alten aufbauen.
    neu = Ablage(neu_pfad)
    neu.configs.mkdir(parents=True)
    neu.config_pfad.write_bytes(config_bytes)
    eingang = eingang_anlegen(
        neu_pfad, fall, stichtag, schluesselring=schluesselring,
        betriebsschluessel=betriebsschluessel, zeichnungsordnung=zeichnungsordnung)
    # Der neue Eingang muss lesbar sein, BEVOR die alte Ablage bewegt wird:
    # dieselbe Pruefung, die der Tageslauf bei der Erstbefuellung macht —
    # samt der Betriebszeichnung, die er gerade bekommen hat.
    try:
        lies_uebernahme(eingang, cfg, schluesselring=zeichner.ring, ordnung=zeichner.ordnung)
    except UebernahmeError as exc:
        raise NeuaufsetzenError(
            f"Eingang nicht lesbar, nichts bewegt: {exc} — die vorbereitete Ablage "
            f"liegt unter {neu_pfad} und kann nach der Korrektur von Hand entfernt werden"
        ) from exc
    provenienz: Dict[str, Any] = {
        "schema_version": PROVENIENZ_SCHEMA_VERSION,
        "neu_aufgesetzt_am": (jetzt or _dt.datetime.now(_dt.timezone.utc)).astimezone(_dt.timezone.utc).isoformat(),
        "archiv": str(archiv_ziel),
        "config_quelle": str(config_quelle),
        "config_sha256": sha256_bytes(config_bytes),
        "fall": eingang.name,
        "stichtag": stichtag.isoformat(),
        "eingang": str(stand / UEBERNAHME_DIR / eingang.name),
        "naechste_schritte": [
            f"python -m rechner_pipeline.betrieb.tageslauf --stand {stand} "
            "--schluessel <betriebsschluessel> --zeichnungsordnung <ordnung>",
            f"python -m rechner_pipeline.betrieb.seite --stand {stand} --paket <paketverzeichnis> "
            "--anker <ankerverzeichnis> --betriebsschluessel <betriebsschluessel> "
            "--zeichnungsordnung <ordnung>",
        ],
    }
    (neu_pfad / PROVENIENZ_DATEI).write_text(
        json.dumps(provenienz, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    # 3. Archivieren und tauschen: zwei Umbenennungen, keine Loeschung.
    os.rename(stand, archiv_ziel)
    try:
        os.rename(neu_pfad, stand)
    except OSError as exc:
        if not neu_pfad.exists() and (stand / PROVENIENZ_DATEI).is_file() and json.loads(
                (stand / PROVENIENZ_DATEI).read_text(encoding="utf-8")) == provenienz:
            # Ein anderer Prozess hat genau diesen Tausch vollendet (lauf_sperre).
            return provenienz
        raise NeuaufsetzenError(
            f"zweite Umbenennung fehlgeschlagen ({exc}): {stand} wurde zwischenzeitlich "
            f"neu angelegt (ein Tageslauf gestartet?). Nichts ist verloren — alte Ablage: "
            f"{archiv_ziel}, neue Ablage: {neu_pfad}. Ausweg: Timer anhalten, {stand} "
            f"pruefen (nur lauf.lock?) und beiseitelegen, dann von Hand: mv {neu_pfad} {stand}"
        ) from exc
    return provenienz


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.betrieb.neuaufsetzen",
        description="Die Laufzeitumgebung der PLV aus der Uebernahme eines Falls neu aufsetzen (Betriebsweg, Schritt 9).",
    )
    parser.add_argument("--stand", required=True, help="Datenverzeichnis der Laufzeitumgebung.")
    parser.add_argument("--fall", required=True, help="Fall-Arbeitsbereich (faelle/<name>).")
    parser.add_argument("--stichtag", required=True, help="Zugangsstichtag (ISO-Datum).")
    parser.add_argument("--config", default=None, help="Config der neuen Ablage (Standard: die der bestehenden).")
    parser.add_argument("--archiv", default=None, help="Archivziel der alten Ablage (Standard: <stand>.archiv-<zeit>).")
    parser.add_argument("--freigabe-schluessel", action="append", default=None,
                        help="Pfad eines Freigabeschluessels (mehrfach moeglich), ausserhalb des Falls; "
                             "prueft die Signatur des A-M4-Snapshots beim Anlegen des Eingangs. "
                             "Pflicht: ohne ihn wird nichts aufgebaut.")
    parser.add_argument("--betriebsschluessel", required=True,
                        help="Betriebsschluessel (Rolle betrieb/<name>, Klasse betrieb), mit dem "
                             "der neue Eingang gezeichnet wird; ausserhalb der Ablage.")
    parser.add_argument("--zeichnungsordnung", required=True,
                        help="Zeichnungsordnung, die dem Betriebsschluessel seine Rolle gibt.")
    parser.add_argument("--aufschalten", action="store_true",
                        help="Einmalig: die alte Ablage traegt ein Protokoll ohne gezeichnete "
                             "Zeile (Altbestand vor dem Betriebsschluessel) und wird trotzdem "
                             "archiviert (deploy/plv/README.md).")
    ns = parser.parse_args(argv)
    try:
        stichtag = _dt.date.fromisoformat(ns.stichtag)
    except ValueError as exc:
        print(f"neuaufsetzen: --stichtag: {exc}", file=sys.stderr)
        return 2
    stand = Path(ns.stand)
    if not stand.exists() and not stand.is_symlink():
        # Ein unterbrochenes Neuaufsetzen zuerst vollenden (Angriffsrunde
        # nach T27): Im Container sieht der Tageslauf die Geschwister der
        # Ablage nicht; der dokumentierte Weg ist, neuaufsetzen erneut zu
        # fahren, und das vollendet den Tausch, statt neu zu beginnen.
        from rechner_pipeline.betrieb.tageslauf import _vollende_unterbrochenes_neuaufsetzen

        try:
            _vollende_unterbrochenes_neuaufsetzen(stand)
        except (TageslaufError, OSError) as exc:
            print(f"neuaufsetzen: {exc}", file=sys.stderr)
            return 2
        if stand.is_dir():
            print(f"neuaufsetzen: unterbrochenen Tausch vollendet -> {stand}; "
                  "naechster Schritt: der Tageslauf", file=sys.stderr)
            return 0
    ring: Optional[Mapping[str, bytes]] = None
    if ns.freigabe_schluessel:
        from rechner_pipeline.models.freigabe import lade_schluesselring
        ring, ring_fehler, _aktiv = lade_schluesselring(
            list(ns.freigabe_schluessel), ausserhalb=Path(ns.fall))
        if ring_fehler:
            print("neuaufsetzen: " + "; ".join(ring_fehler), file=sys.stderr)
            return 2
    try:
        provenienz = neu_aufsetzen(
            Path(ns.stand), Path(ns.fall), stichtag,
            config=Path(ns.config) if ns.config else None,
            archiv=Path(ns.archiv) if ns.archiv else None,
            schluesselring=ring, betriebsschluessel=Path(ns.betriebsschluessel),
            zeichnungsordnung=Path(ns.zeichnungsordnung), aufschalten=ns.aufschalten,
        )
    except (NeuaufsetzenError, UebernahmeError, ValueError) as exc:
        print(f"neuaufsetzen: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        # Meldung statt Traceback und Exit 1, wie tageslauf und seite
        # (Angriffsrunde nach T27).
        print(f"neuaufsetzen: Ein-/Ausgabefehler: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(f"neuaufsetzen: alte Ablage archiviert -> {provenienz['archiv']}", file=sys.stderr)
    print(f"neuaufsetzen: Eingang angelegt -> {provenienz['eingang']}", file=sys.stderr)
    print("neuaufsetzen: naechste Schritte:", file=sys.stderr)
    for schritt in provenienz["naechste_schritte"]:
        print(f"  {schritt}", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
