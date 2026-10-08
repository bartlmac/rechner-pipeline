"""Betrieb neu aufsetzen — der Betriebsweg der Freischaltung (Schritt 9).

Die Laufzeitumgebung der PLV fuehrte den uebernommenen Bestand in einer
anderen Welt als die Abnahmen (Review T22-11). Der Entwicklerweg hat den
Fall korrigiert (Schritt 8); der Betriebsweg setzt die Laufzeit daraus neu
auf::

    python -m rechner_pipeline.betrieb.neuaufsetzen --stand ~/apps/plv/daten \\
        --fall faelle/<fall> --stichtag 2026-01-01 [--config configs/bestand_gesamt.toml] \\
        --freigabe-schluessel <freigabeschluessel> \\
        --betriebsschluessel <betriebsschluessel> --zeichnungsordnung <ordnung> \\
        [--zugangsabnahme <sha256>] [--aufschalten]

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
   Produzent loescht nur, was er selbst erzeugt hat; hier nur die eigene,
   nie veroeffentlichte Vorbereitung aus Schritt 2, wenn er verweigert —
   Angriffsrunde 2026-10-01). Ehrlich benannt: Zwischen den zwei Umbenennungen gibt es einen
   Moment OHNE Ablage — die Wurzel ist ein echtes Verzeichnis, kein
   Symlink wie ``stand`` (T22-03), ein atomarer Tausch zweier Verzeichnisse
   ist mit Bordmitteln nicht moeglich. Endet der Prozess in diesem Moment,
   vollendet der naechste, der die Ablage oeffnet (``lauf_sperre``), den
   Tausch: Die neue Ablage ist fertig, sobald ihre Provenienzdatei liegt —
   sie wird als Letztes geschrieben und nennt das Archiv. Eine leere Wurzel
   wird neben einem Aufbau nie angelegt.
   Endet der Prozess FRUEHER — nach dem Anlegen der Vorbereitung, vor der
   ersten Umbenennung —, steht die alte Ablage an ihrem Ort und daneben eine
   nie veroeffentlichte Vorbereitung (Pruefrunde H, H18). Sie ist nie still:
   Jeder Aufruf, der die Ablage betritt, erkennt sie in ``lauf_sperre`` und
   haelt benannt an; der naechste Aufruf dieser Routine raeumt sie ab, bevor
   er neu aufbaut. Was veroeffentlicht gewesen sein koennte (die Provenienz
   nennt ein Archiv, das es gibt, oder ein Journal liegt darin), bleibt
   liegen und wird genannt.
   Die Registrierung verlangt die Zugangsabnahme A-B2 (ADR-022) — fuer
   die NEUE Ablage: Ihr gefuehrter Stand ist der einer leeren Ablage mit
   dieser Config, also laeuft die Zugangsprobe auf einer leeren Ablage,
   die nur diese Config traegt (plv/betrieb/README.md).
   Vor dem Tausch liest die Routine den neuen Eingang einmal vollstaendig
   (``lies_uebernahme``): unbekannte Generation, falscher Stichtag, fehlende
   Merkmale oder abweichendes Tarifwerk fallen auf, BEVOR etwas bewegt ist.
4. Den Stand faehrt sie NICHT: Der naechste Tageslauf baut ihn vom
   Betriebsbeginn bis heute in einem Lauf (Erstbefuellung, der Aufbaulauf),
   danach nimmt der Betrieb den Anfangsbestand ab (A-B3, ADR-025: belegen,
   zeichnen, binden — ohne sie laeuft kein weiterer Tag), dann das
   Stands-Paket. Die Routine nennt die Kommandos.

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
    Ablage, TageslaufError, VorbereitungLiegtError, aufschaltung_fehler, betriebszeichner,
    lauf_sperre,
)
from rechner_pipeline.betrieb.uebernahme import (
    UEBERNAHME_DIR, UebernahmeError, eingang_anlegen, lies_uebernahme,
    registrierung_vorbedingungen, tarifwerk_fehler,
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
    zugangsabnahme_sha256: Optional[str] = None,
    linie: Optional[Path] = None,
) -> Dict[str, Any]:
    """Die Laufzeitumgebung ``stand`` aus dem Fall ``fall`` neu aufsetzen.

    ``zugangsabnahme_sha256``: die angenommene Zugangsabnahme A-B2 fuer den
    Eingang der NEUEN Ablage (ADR-022; Default: das A-B2-Gate-Ledger des
    Falls). Ohne sie wird nichts aufgebaut.

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
    wurde, wann immer das moeglich ist — und hinterlaesst dann auch keine
    vorbereitete Ablage (Angriffsrunde 2026-10-01): Was keinen Ort braucht,
    wird vor dem Anlegen geprueft, was nur gegen die neue Ablage pruefbar
    ist, raeumt seine Vorbereitung bei Verweigerung selbst ab.
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
            wofuer="das Neuaufsetzen", ohne="kein Aufbau", flag="--betriebsschluessel",
            linie=linie,
            # Die Linie mit dem Ring, der die Abnahmen prueft (Pruefrunde G, G09).
            ring=schluesselring if schluesselring is not None else _ueb._STANDARD_SCHLUESSELRING)
    except TageslaufError as exc:
        raise NeuaufsetzenError(str(exc)) from exc
    # Die Zugangsabnahme VOR jedem Aufbau (ADR-022): Ohne sie verweigert die
    # Registrierung erst, wenn die neue Ablage schon angelegt ist.
    ab2_ledger = fall / "abgeleitet" / "diagnostics" / "gate_entscheid_ab2.gate.json"
    if (zugangsabnahme_sha256 is None and not ab2_ledger.is_file()
            and _ueb._STANDARD_ZUGANGSABNAHME is None):
        raise NeuaufsetzenError(
            "ohne Zugangsabnahme A-B2 wird nichts aufgebaut — der Eingang der neuen "
            "Ablage braucht sie (ADR-022). Ausweg: die Zugangsprobe auf einer leeren "
            "Ablage mit der neuen Config fahren (python -m "
            "rechner_pipeline.betrieb.zugangsprobe), A-B2 zeichnen, dann "
            "--zugangsabnahme <sha256>")
    if stand.is_symlink() or not stand.is_dir():
        raise NeuaufsetzenError(
            f"{stand}: keine Ablage (kein echtes Verzeichnis) — fuer die erste "
            "Einrichtung siehe plv/betrieb/README.md, neu aufgesetzt wird nur eine "
            "bestehende Ablage"
        )
    alt = Ablage(stand)
    # Dieselbe Prozess-Sperre wie der Tageslauf (Review T22-03): Haelt ein
    # Lauf sie, wird nichts bewegt. Die Sperrdatei bleibt bestehen; gehalten
    # wird sie per flock, und genau das prueft lauf_sperre.
    try:
        # Eine liegengebliebene, nie veroeffentlichte Vorbereitung eines
        # frueheren, abgebrochenen Aufrufs raeumt die Sperre ab, BEVOR etwas
        # Neues entsteht (Pruefrunde H, H18): Ein Prozessende zwischen dem
        # Anlegen der Vorbereitung und der ersten Umbenennung liess sie
        # ungenannt liegen. Was veroeffentlicht gewesen sein koennte, bleibt
        # liegen und wird genannt (VorbereitungLiegtError).
        with lauf_sperre(alt, vorbereitung_abraeumen=True) as geraeumt:
            for satz in geraeumt:
                print(f"neuaufsetzen: {satz}", file=sys.stderr)
            return _neu_aufsetzen_unter_sperre(
                stand, fall, stichtag, alt, config=config, archiv=archiv, jetzt=jetzt,
                schluesselring=schluesselring, betriebsschluessel=betriebsschluessel,
                zeichnungsordnung=zeichnungsordnung, zeichner=zeichner,
                aufschalten=aufschalten, zugangsabnahme_sha256=zugangsabnahme_sha256,
                linie=linie,
            )
    except VorbereitungLiegtError as exc:
        raise NeuaufsetzenError(str(exc)) from exc
    except TageslaufError as exc:
        raise NeuaufsetzenError(
            f"Sperre: {exc} — Timer anhalten, laufenden Prozess enden lassen, dann "
            "neu aufsetzen"
        ) from exc


def _verwirf_vorbereitung(neu_pfad: Path, stand: Path, *,
                          mit_provenienz: bool = False) -> Optional[str]:
    """Die eigene, nie veroeffentlichte Vorbereitung entfernen (ueber
    ``betrieb._loeschen``: nur dieses Verzeichnis, neben der Ablage, ohne
    Provenienz). Scheitert das Entfernen, bleibt der Rest benannt liegen —
    die urspruengliche Verweigerung geht vor. Rueckgabe: None, oder der
    Satz, der den Rest nennt.

    ``mit_provenienz``: nur fuer einen Ausfall BEIM Schreiben der Provenienz
    oder bei der ersten Umbenennung (Runde G, G28). Dann traegt die
    Vorbereitung ihre Provenienz (ganz oder halb), ist aber nie
    veroeffentlicht: Ihre Identitaet steht fest, weil DIESER Aufruf sie unter
    seinem Namen angelegt hat (der Name existierte vorher nicht) und die
    alte Ablage an ihrem Ort liegt."""
    from rechner_pipeline.betrieb._loeschen import LoeschFehler, entferne_verzeichnis

    if not neu_pfad.exists():
        return None
    try:
        entferne_verzeichnis(
            neu_pfad, innerhalb=stand.parent, name_ok=lambda n: n == neu_pfad.name,
            ohne_marker=None if mit_provenienz else PROVENIENZ_DATEI,
            grund="Vorbereitung eines verweigerten Neuaufsetzens")
    except (LoeschFehler, OSError) as exc:  # pragma: no cover - benannter Rest
        rest = f"Vorbereitung {neu_pfad} nicht entfernt ({exc}) — von Hand entfernen"
        print(f"neuaufsetzen: {rest}", file=sys.stderr)
        return rest
    return None


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
    zugangsabnahme_sha256: Optional[str] = None,
    linie: Optional[Path] = None,
) -> Dict[str, Any]:
    # Das alte Protokoll ohne gezeichnete Zeile nur ausdruecklich
    # (Nachbesserung Runde C). Gelesen wird nur, WELCHE Zeilen gezeichnet
    # sind, nicht die Kette: Ob sie haelt, ist Sache des Tageslaufs; das
    # Archiv bewahrt sie, wie sie ist. Die Signatur wird hier nicht
    # nachgerechnet — neu aufgesetzt wird auch nach einem Schluesselwechsel.
    # Eine Probenkopie wird nicht neu aufgesetzt (Runde F, F9): Sie gehoert
    # der Probe, und ihr Archiv waere die Geschichte einer Ablage, die es nie
    # gab. Gefragt wird VOR jedem Aufbau, mit Kennzeichen ODER Probezeile.
    from rechner_pipeline.betrieb.tageslauf import probenkopie_fehler

    fehler = probenkopie_fehler(alt)
    if fehler:
        raise NeuaufsetzenError(
            f"{fehler} — neu aufgesetzt wird die produktive Ablage; nichts bewegt")
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
    # Die Vorbedingungen der Registrierung, die keinen Ort brauchen, VOR dem
    # Anlegen (Angriffsrunde 2026-10-01): A-M4 und A-B2 samt Rollenregel,
    # Tabellen und Belege gegen den Beleggraphen — dieselbe Funktion, die
    # eingang_anlegen ruft. Vorher verweigerte erst die Registrierung, und
    # die angelegte neue Ablage blieb liegen.
    registrierung_vorbedingungen(
        fall, ordnung=zeichner.ordnung if zeichner is not None else None,
        schluesselring=schluesselring, zugangsabnahme_sha256=zugangsabnahme_sha256,
        ordnungslinie=zeichner.ordnungslinie if zeichner is not None else None)

    # 2. Neue Ablage vollstaendig NEBEN der alten aufbauen. Was nur gegen
    # sie pruefbar ist (Bindung der A-B2 an Eingang und Stand, A-M1 der
    # Soll-Bindung, Nebentabellen, P-B1, Lesbarkeit), scheitert danach; dann
    # wird die eigene, nie veroeffentlichte Vorbereitung entfernt — ihre
    # Identitaet steht fest: Name dieses Aufrufs, noch ohne Provenienz.
    #
    # EIN Schutz um den ganzen Abschnitt vom Anlegen der Vorbereitung bis zur
    # ersten Umbenennung (Pruefrunde I, I21): Faellt irgendeine Schreibstelle
    # darin aus, ist nichts bewegt, solange die alte Ablage an ihrem Ort liegt
    # und das Archiv nicht; dann wird die eigene Vorbereitung abgeraeumt und
    # die Meldung sagt das (oder nennt den Rest). Vorher schuetzten drei
    # Faenge je eine Stelle; das Anlegen von configs lag vor dem ersten — ein
    # Ausfall dort liess die schon angelegte Vorbereitung ungenannt liegen,
    # und jeder weitere Aufruf, auch der Timer, hielt an. Die Identitaet der
    # Vorbereitung steht fest: Ihr Name existierte vor diesem Aufruf nicht
    # (oben geprueft), dieser Aufruf haelt die Sperre der Ablage.
    def _abbruch_vor_dem_tausch() -> Optional[str]:
        """Abraeumen, wenn nichts bewegt ist; Rueckgabe der Satz fuer die
        Meldung, oder None, wenn schon bewegt wurde."""
        if not (stand.exists() and not archiv_ziel.exists()):
            return None
        rest = _verwirf_vorbereitung(neu_pfad, stand, mit_provenienz=True)
        return "nichts bewegt, " + (rest if rest else f"die Vorbereitung {neu_pfad} ist entfernt")

    neu = Ablage(neu_pfad)
    try:
        neu.configs.mkdir(parents=True)
        neu.config_pfad.write_bytes(config_bytes)
        eingang = eingang_anlegen(
            neu_pfad, fall, stichtag, schluesselring=schluesselring,
            betriebsschluessel=betriebsschluessel, zeichnungsordnung=zeichnungsordnung,
            zugangsabnahme_sha256=zugangsabnahme_sha256, linie=linie)
        # Der neue Eingang muss lesbar sein, BEVOR die alte Ablage bewegt
        # wird: dieselbe Pruefung, die der Tageslauf bei der Erstbefuellung
        # macht — samt der Betriebszeichnung, die er gerade bekommen hat.
        try:
            lies_uebernahme(eingang, cfg, schluesselring=zeichner.ring, ordnung=zeichner.ordnung)
        except UebernahmeError as exc:
            raise NeuaufsetzenError(f"Eingang nicht lesbar, nichts bewegt: {exc}") from exc
        provenienz = _provenienz(stand, archiv_ziel, config_quelle, config_bytes, eingang,
                                 stichtag, jetzt)
        # Provenienz und erste Umbenennung gehoeren noch zur Vorbereitung
        # (Runde G, G28).
        (neu_pfad / PROVENIENZ_DATEI).write_text(
            json.dumps(provenienz, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8", newline="\n",
        )
        # 3. Archivieren und tauschen: zwei Umbenennungen, keine Loeschung.
        os.rename(stand, archiv_ziel)
    except OSError as exc:
        satz = _abbruch_vor_dem_tausch()
        if satz is not None:
            raise NeuaufsetzenError(
                f"Ein-/Ausgabefehler vor dem Tausch ({type(exc).__name__}: {exc}); {satz}"
                " — Ausweg: die Ursache beheben und denselben Aufruf wiederholen") from exc
        raise NeuaufsetzenError(
            f"Ein-/Ausgabefehler beim Archivieren ({type(exc).__name__}: {exc}); alte Ablage: "
            f"{archiv_ziel if archiv_ziel.exists() else stand}, vorbereitete neue Ablage: "
            f"{neu_pfad} — Ausweg: Timer anhalten, Lage pruefen, dann von Hand: mv {neu_pfad} "
            f"{stand}") from exc
    except Exception:
        # Eine Verweigerung (A-B2, Eingang, Lesbarkeit): abraeumen wie oben,
        # die Verweigerung geht vor.
        _abbruch_vor_dem_tausch()
        raise
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


def _provenienz(stand: Path, archiv_ziel: Path, config_quelle: Path, config_bytes: bytes,
                eingang: Path, stichtag: _dt.date,
                jetzt: Optional[_dt.datetime]) -> Dict[str, Any]:
    return {
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
            # Nach dem Aufbaulauf die Abnahme des Anfangsbestands (ADR-025):
            # ohne sie laeuft kein weiterer Tag.
            f"python -m rechner_pipeline.betrieb.anfangsbestand belegen --stand {stand} "
            "--linie <linie> --schluessel <betriebsschluessel> --zeichnungsordnung <ordnung>",
            "python -m rechner_pipeline.gates.gate_entscheid --linie <linie> --gate A-B3 "
            "--entscheid angenommen ... (mensch/betrieb)",
            f"python -m rechner_pipeline.betrieb.anfangsbestand binden --stand {stand} "
            "--linie <linie> --freigabe-schluessel <schluessel mensch/betrieb> "
            "--schluessel <betriebsschluessel> --zeichnungsordnung <ordnung>",
            f"python -m rechner_pipeline.betrieb.seite --stand {stand} --paket <paketverzeichnis> "
            "--anker <ankerverzeichnis> --betriebsschluessel <betriebsschluessel> "
            "--zeichnungsordnung <ordnung>",
        ],
    }


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
    parser.add_argument("--zugangsabnahme", default=None,
                        help="Snapshot-Hash der Zugangsabnahme A-B2 fuer den Eingang der neuen "
                             "Ablage (ADR-022; Default: aus dem A-B2-Gate-Beleg des Falls).")
    parser.add_argument("--linie", required=True,
                        help="Linienbereich (ADR-025; Pflicht seit dem Nachtrag 2026-10-01): "
                             "die Abnahmen werden gegen die Ordnung gehalten, unter der sie "
                             "gezeichnet wurden (Ordnungslinie). Kein Default, keine "
                             "Umgebungsvorgabe: der Ort wird bei jedem Aufruf genannt.")
    parser.add_argument("--aufschalten", action="store_true",
                        help="Einmalig: die alte Ablage traegt ein Protokoll ohne gezeichnete "
                             "Zeile (Altbestand vor dem Betriebsschluessel) und wird trotzdem "
                             "archiviert (plv/betrieb/README.md).")
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
            zugangsabnahme_sha256=ns.zugangsabnahme,
            linie=Path(ns.linie),
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
