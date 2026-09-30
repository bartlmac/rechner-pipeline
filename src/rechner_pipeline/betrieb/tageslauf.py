"""``betrieb.tageslauf`` — der naechtliche Lauf der PLV (Fachkonzept Tagesbetrieb, Abschnitt 7).

Ein Kommando, idempotent und deterministisch::

    python -m rechner_pipeline.betrieb.tageslauf --stand <daten> --heute <datum> \
        --schluessel <betriebsschluessel> --zeichnungsordnung <ordnung>

``--stand`` ist das Datenverzeichnis der Laufzeitumgebung
(``~/apps/plv/daten``, Abschnitt 7 des Konzepts); ``--heute`` der
Kalendertag, der gefuehrt werden soll — ohne Angabe der Kalendertag des
Aufrufs (die einzige Stelle, an der der Tagesbetrieb eine Uhr liest, und
sie steht ausserhalb der Simulation: alles Weitere ist eine Funktion von
Config, Eingaengen und Kalendertag).

Was ein Lauf tut, in dieser Reihenfolge:

1. **Nachholen.** Liegt der letzte gefuehrte Tag vor ``heute - 1``, gilt
   der Lauf fuer alle fehlenden Tage. Weil der Stand eines Tages die
   deterministische Fortschreibung bis zu diesem Tag ist und das
   Tagesjournal seine Buchungstage aus dem Wirkungstag ableitet, ist der
   Stand nach dem Nachholen derselbe, als haette der Lauf jede Nacht
   stattgefunden — nur das Protokoll hat eine Zeile statt vieler, und
   die nennt die nachgeholten Tage.
2. **Neugeschaeft.** Alle Verkaufstage vom Betriebsbeginn bis heute
   (:mod:`rechner_pipeline.betrieb.neugeschaeft`) — je Tag fuer sich
   reproduzierbar.
3. **Fortschreibung bis heute.** Basisbestand (die uebernommenen Vertraege; eigenes Geschaeft entsteht Werktag fuer Werktag)
   plus Uebernahme-Eingaenge plus Neugeschaeft, EIN Lauf der bestehenden
   Engine (``bestand.ereignisse.fortschreiben``); die Buchungen der
   Uebernahmen stehen dem Journal voran wie in ``cli_fortschreibung``.
4. **Tagesjournal.** Die bis heute faelligen, noch nicht gebuchten
   Buchungen anfuegen (:mod:`rechner_pipeline.betrieb.tagesjournal`).
5. **Wache.** Die P-B1-Engine (``bestand.vorbedingungen.lies_und_pruefe_pb1``)
   auf dem NEUEN Stand mit Config, Manifest und JEDER Nebentabelle, die
   der Stand traegt (``bestand.manifest.lauf_eingaben``) — dieselbe
   Pruefung, die Gate P-B1 faehrt, ueber die Bytes, die geschrieben
   wurden. Rot heisst: Der Stand wird nicht uebernommen, der gestrige
   bleibt der gefuehrte, der Befund steht im Protokoll, Exit 3. Ein
   Bestandsfuehrungssystem, das einen roten Stand still uebernimmt, waere
   die schlechteste Variante.
6. **Monatsabschluss** fuer jeden Monatsersten in ``(letzter Tag,
   heute]``: ``bestand.abschluss.schreibe_abschluss`` mit Stichtag
   Monatserster (Konvention Monatserster; Bewertung ueber dieselbe eine
   Strecke wie jeder Abschluss, festgeschrieben 0444, genau einmal —
   ADR-011) und der Bestandsbericht des Monats. Der Horizont eines Laufs
   ist der gefuehrte Tag selbst; der Stand des Ersten enthaelt dessen
   Buchungen, deshalb entsteht der Abschluss zum Ersten im Lauf des
   Ersten — der Ultimo-Lauf koennte ihn noch nicht bewerten
   (``stichtag <= bis``). Ein Monat ohne in-force-Vertrag bekommt einen
   LEEREN Abschluss (ADR-020): Ein Unternehmen beginnt leer, der erste
   Versicherungsbeginn liegt am Monatsersten nach dem ersten Verkaufstag,
   und die leere Bilanz ist eine gueltige Bilanz. Sie wird geschrieben und
   belegt wie jede andere; ihre Nachrechnung (Wiederanlauf) weist sie nur
   aus, wenn die Neuberechnung dort Vertraege findet.
   Kandidat der naechsten Runde: Ein vorab gepflanzter Abschluss fuer den
   naechsten Stichtag gilt im nachgerechnet-Zweig mit Exit 0 als
   festgeschrieben (der Befund steht in der Zeile, blockiert aber nicht).
7. **Tagesprotokoll**: eine JSON-Zeile je Lauf, gezeichnet mit dem
   Betriebsschluessel (Rolle ``betrieb/tageslauf``, Schluesselklasse
   ``betrieb``; ADR-018, Nachtrag 2026-09-30). Schluessel und
   Zeichnungsordnung liegen ausserhalb der Ablage beim Menschen, wie die
   Rollenschluessel der Abnahmen: Was der schreibende Prozess selbst
   umschreiben kann, belegt nichts.

Der Stand wird erst uebernommen, wenn die Wache gruen ist: Der Lauf
schreibt in ein Arbeitsverzeichnis neben ``stand/``, prueft dort, und
tauscht dann atomar. Ein Absturz mitten im Lauf hinterlaesst den alten
Stand und ein Arbeitsverzeichnis, das der naechste Lauf verwirft.

Ablage unter ``--stand`` (Konzept, Abschnitt 7)::

    stand/          sechs Ausgaben + laufmanifest.json (+ merkmale.parquet)
    journal/        tagesjournal.parquet, protokoll.jsonl (nur-anfuegbar)
    seite/          index.html "Bestand heute" (betrieb.seite), nach jedem gruenen Lauf
    seite.neu/      Vorbereitung der Seite (nur Tempdatei, Reste raeumt der naechste Render)
    abschluesse/    abschluss_<stichtag>.parquet (0444, genau einmal)
    berichte/       bestandsbericht_<stichtag>.html je Monatsabschluss
    uebernahme/     je Migrationsfall ein Eingang (Block B5)
    configs/        die Config der PLV (Kopie; Hash im Protokoll)

Knoten: klv, bu
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as _dt
import hashlib
import json
import os
import sys
import tempfile

try:  # Referenzumgebung ist Linux; ohne fcntl gibt es keine Prozess-Sperre.
    import fcntl
except ImportError:  # pragma: no cover - fremde Plattform
    fcntl = None  # type: ignore[assignment]
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from rechner_pipeline.betrieb._loeschen import LoeschFehler, entferne_verzeichnis
from rechner_pipeline.bestand.abschluss import (
    AbschlussError,
    abschluss_pfad,
    pruefe_abschluss,
    schreibe_abschluss,
)
from rechner_pipeline.bestand.config import BestandConfig, load_config
from rechner_pipeline.bestand.ereignisse import EreignisError, fortschreiben, mit_zugaengen
from rechner_pipeline.bestand.fuehrung import fuehre_fort
from rechner_pipeline.bestand.manifest import (
    MANIFEST_DATEI,
    ERZEUGER,
    ROLLEN_DATEIEN,
    ManifestError,
    lauf_eingaben,
    lies_manifest,
    pruefe_erzeuger,
    schreibe_manifest,
    sha256_bytes,
)
from rechner_pipeline.bestand.kennzahlen import monatskennzahlen
from rechner_pipeline.bestand.parquet_io import neue_datei, read_portfolio, write_portfolio
from rechner_pipeline.bestand.report import render_html
from rechner_pipeline.bestand.vorbedingungen import lies_und_pruefe_pb1
from rechner_pipeline.betrieb._zeichnung import (
    Zeichner,
    ZeichnungFehler,
    betriebszeichnung_fehler,
    lade_zeichner,
    verlange_betrieb,
)
from rechner_pipeline.betrieb.neugeschaeft import NeugeschaeftError, neugeschaeft_zwischen
from rechner_pipeline.betrieb.tagesjournal import (
    TagesjournalError,
    gebuchte_sicht,
    leeres_tagesjournal,
    tagesjournal_ergaenzen,
    validate_tagesjournal,
)
from rechner_pipeline.betrieb.uebernahme import (
    UEBERNAHME_DIR, UebernahmeError, lies_uebernahmen,
)
from rechner_pipeline.models.anker import jsonl_zeilen
from rechner_pipeline.models.bestand import (
    BASIS_STATUS,
    LEDGER_NAMES,
    MERKMALE_NAMES,
    STAMM_NAMES,
    STATUS_HISTORIE_NAMES,
    TAGESJOURNAL_NAMES,
    leerer_stamm,
)

#: Schema 2 (Review T22-05): jede Zeile traegt ``vorgaenger_sha256``, den
#: SHA-256 der vorangehenden Zeile (Bytes ohne Zeilenende; "" fuer die
#: erste). Zeilen der Erstfassung (Schema 1) bleiben lesbar; sobald eine
#: Zeile Schema 2 traegt, ist die Kette ab dort Pflicht.
#:
#: Schema 3 (Pruefrunde nach T27, Runde C; Entscheid des Maintainers
#: 2026-09-30): jede Zeile ist mit dem Betriebsschluessel GEZEICHNET
#: (``zeichnung`` nach ``models.anker``, Verfahren hmac-sha256-v2, Klasse
#: ``betrieb``). Die Kette allein schuetzte nichts gegen einen Schreiber,
#: der sie mitrechnet: Eine angefuegte zweite gruene Zeile, eine
#: umgeschriebene letzte Zeile oder eine auf Schema 1 herabgestufte Zeile
#: gingen durch (RC10, RC11). Das Schema steigt nur: Hinter einer Zeile
#: mit Schema n steht keine mit einem kleineren — eine Herabstufung ist
#: ein Kettenbruch. Die erste gezeichnete Zeile einer Ablage mit
#: ungezeichnetem Vorlauf pinnt ihn (``vorlauf``: Zahl und Hash der rohen
#: Zeilen) — Aufschaltung ohne Neuaufsetzen.
PROTOKOLL_SCHEMA_VERSION = 3
#: Die Naht fuer den Betriebsschluessel, wenn der Aufrufer keinen nennt:
#: ``(schluessel, zeichnungsordnung)`` als Pfade. Produktiv bleibt sie
#: None — der Schluessel kommt aus ``--schluessel``/``--zeichnungsordnung``
#: und ohne ihn laeuft kein Tag. Tests setzen sie sessionweit
#: (``tests/conftest.py``), wie ``uebernahme._STANDARD_SCHLUESSELRING``;
#: geladen und geprueft wird auch dann bei jedem Aufruf, mit denselben
#: Regeln wie ein expliziter Schluessel.
_STANDARD_BETRIEBSZEICHNUNG: Optional[Tuple[Path, Path]] = None
#: Benannter Zustand einer Protokollangabe, die die Umgebung nicht liefert.
NICHT_ERFASST = "nicht erfasst"
STAND_DIR = "stand"
JOURNAL_DIR = "journal"
ABSCHLUSS_DIR = "abschluesse"
BERICHT_DIR = "berichte"
CONFIG_DIR = "configs"
# UEBERNAHME_DIR kommt aus betrieb.uebernahme — der Schreiber der
# Eingaenge besitzt den Namen. Zweimal gepflegt waere es dieselbe
# Menge an zwei Orten, und die Staging-Wurzel daneben (STAGING_DIR)
# liefe beim naechsten Umbau still auseinander.
TAGESJOURNAL_DATEI = "tagesjournal.parquet"
#: Kopie des Journals waehrend eines Publish (Review T24-01, Schritt b):
#: die einzige Veroeffentlichung, die sich nicht aus dem Stand
#: wiederherstellen laesst, also wird sie zurueckgelegt.
TAGESJOURNAL_VORHER_DATEI = "tagesjournal.vorher.parquet"
PROTOKOLL_DATEI = "protokoll.jsonl"
CONFIG_DATEI = "bestand.toml"
#: Arbeitsverzeichnis eines laufenden Tageslaufs (wird beim naechsten Lauf verworfen).
ARBEIT_DIR = "stand.neu"
#: Name der Sperrdatei (fcntl.flock, exklusiv, nicht blockierend).
SPERRE_DATEI = "lauf.lock"
#: Write-Ahead-Marker der Veroeffentlichung: liegt zwischen dem ersten
#: und dem letzten irreversiblen Schritt eines Laufs.
PUBLISH_MARKER_DATEI = "publish.json"
#: Uebergangsname des Symlinks beim atomaren Tausch.
STAND_LINK_TMP = "stand.link"

#: Exit-Codes: 0 gruen und uebernommen, 2 Aufruf-, Eingangs- oder Ein-/
#: Ausgabefehler vor der Wache (Stand nicht uebernommen), 3 Wache rot
#: (Stand nicht uebernommen), 4 Journal- oder Abschlussfehler nach gruener
#: Wache (Stand nicht uebernommen).
EXIT_OK, EXIT_USAGE, EXIT_WACHE_ROT, EXIT_NACHLAUF = 0, 2, 3, 4


class TageslaufError(ValueError):
    """Eingang oder Ablage passen nicht zum Tagesbetrieb — fail-fast."""


# --------------------------------------------------------------------------- #
# Ablage
# --------------------------------------------------------------------------- #


class Ablage:
    """Die Verzeichnisse der Laufzeitumgebung (Konzept, Abschnitt 7)."""

    def __init__(self, wurzel: Path) -> None:
        self.wurzel = Path(wurzel)
        self.stand = self.wurzel / STAND_DIR
        self.arbeit = self.wurzel / ARBEIT_DIR
        self.journal = self.wurzel / JOURNAL_DIR
        self.abschluesse = self.wurzel / ABSCHLUSS_DIR
        self.berichte = self.wurzel / BERICHT_DIR
        self.configs = self.wurzel / CONFIG_DIR
        self.uebernahme = self.wurzel / UEBERNAHME_DIR
        #: Prozess-Sperre des Laufs (Review T22-03): zwei gleichzeitige
        #: Laeufe teilten sich Arbeitsverzeichnis, Journal und Protokoll.
        self.sperre = self.wurzel / SPERRE_DATEI
        #: Write-Ahead-Marker der Veroeffentlichung (Review T24-01,
        #: Schritt b): Er liegt genau zwischen dem ersten und dem letzten
        #: irreversiblen Schritt eines Laufs und sagt dem naechsten, dass
        #: ein Publish unterwegs war.
        self.publish_marker = self.wurzel / PUBLISH_MARKER_DATEI

    @property
    def config_pfad(self) -> Path:
        return self.configs / CONFIG_DATEI

    @property
    def tagesjournal_pfad(self) -> Path:
        return self.journal / TAGESJOURNAL_DATEI

    @property
    def tagesjournal_vorher_pfad(self) -> Path:
        """Die Kopie des Journals VOR dem Publish — die Ruecknahme.

        Das Journal ist die einzige Veroeffentlichung eines Laufs, die
        sich nicht aus dem Stand wiederherstellen laesst: Es wird ganz
        geschrieben, und die alten Bytes waeren weg. Ein Absturz nach
        dem Journal und vor dem Standwechsel liess den Lauf DAUERHAFT
        blockiert zurueck — jeder Retry fiel ueber den Nachweisvertrag
        (Review T24-01, Reproduktion 1).
        """
        return self.journal / TAGESJOURNAL_VORHER_DATEI

    @property
    def protokoll_pfad(self) -> Path:
        return self.journal / PROTOKOLL_DATEI


def betriebszeichner(
    ablage: "Ablage",
    schluessel: Optional[Path] = None,
    zeichnungsordnung: Optional[Path] = None,
    *,
    wofuer: str = "der Tageslauf",
    ohne: str = "kein Tageslauf",
    flag: str = "--schluessel",
) -> Zeichner:
    """Den Betriebsschluessel aufloesen: ausdruecklich > Naht > Fehler.

    Ohne Schluessel gibt es keinen Tag (Entscheid des Maintainers
    2026-09-30): Eine Protokollzeile, die niemand zeichnet, bezeugt
    nur, dass jemand Schreibrecht auf die Ablage hatte. Und nur die Klasse
    ``betrieb`` zeichnet — ein Menschen- oder Agentenschluessel wird mit
    Ausweg abgewiesen (:func:`betrieb._zeichnung.verlange_betrieb`).
    """
    if schluessel is None and zeichnungsordnung is None:
        if _STANDARD_BETRIEBSZEICHNUNG is None:
            raise TageslaufError(
                f"ohne Betriebsschluessel {ohne} — {wofuer} zeichnet bzw. prueft "
                "Protokollzeilen und Eingaenge mit dem Schluessel des Betriebs. "
                f"Ausweg: {flag} <betriebsschluessel> --zeichnungsordnung <ordnung> "
                "(beide ausserhalb der Ablage, deploy/plv/README.md)")
        schluessel, zeichnungsordnung = _STANDARD_BETRIEBSZEICHNUNG
    if schluessel is None or zeichnungsordnung is None:
        raise TageslaufError(
            f"{flag} und --zeichnungsordnung gehoeren zusammen: Die Rolle "
            "wird aus dem Schluessel BESTIMMT, und die Ordnung sagt, welche")
    try:
        return verlange_betrieb(
            lade_zeichner(Path(schluessel), Path(zeichnungsordnung),
                          ausserhalb=ablage.wurzel),
            wofuer)
    except ZeichnungFehler as exc:
        raise TageslaufError(str(exc)) from exc


def _schreibe_json_atomar(pfad: Path, daten: Dict[str, Any]) -> None:
    """Vollstaendig daneben, dann in einem Zug an den Zielpfad.

    Ein halb geschriebener Marker waere genau der unklare Zustand, gegen
    den er schuetzt (dieselbe Figur wie ``ontologie.abox.speichere``,
    Review T25-11).
    """
    inhalt = (json.dumps(daten, ensure_ascii=False, indent=2, sort_keys=True)
              + "\n").encode("utf-8")
    pfad.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=pfad.parent, prefix=f".{pfad.name}.",
                                     suffix=".tmp")
    temp_pfad = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as datei:
            datei.write(inhalt)
            datei.flush()
            os.fsync(datei.fileno())
        os.replace(temp_pfad, pfad)
    except BaseException:
        temp_pfad.unlink(missing_ok=True)
        raise


def schreibe_publish_marker(
    ablage: "Ablage", heute: _dt.date, generation: str,
) -> None:
    """Den Write-Ahead-Marker setzen — VOR dem ersten irreversiblen Schritt.

    Ein Tageslauf veroeffentlicht mehrere extern sichtbare Artefakte
    nacheinander: Monatsabschluesse, Tagesjournal, Stand-Symlink,
    Protokollzeile. Jedes ist fuer sich atomar geschuetzt; ZUSAMMEN waren
    sie es nicht. Ein gewoehnlicher I/O-Fehler dazwischen liess vier
    Endzustaende zu, und einer davon — Journal geschrieben, Stand nicht
    getauscht — blockierte den Betrieb dauerhaft: Jeder saubere Retry
    fiel ueber den Nachweisvertrag, ohne Ausweg im Code.

    Der Marker macht daraus einen benannten Zwischenzustand. Er nennt
    den Tag, die Generation, auf die getauscht werden soll, und den
    Stand, auf den ``stand`` vorher zeigte. Zusammen mit der Kopie des
    Journals reicht das, um den Lauf ZURUECKZUNEHMEN — der naechste Lauf
    findet die Ablage so vor, wie sie vor dem Publish war, und fuehrt den
    Tag erneut. Die Alternative waere ein Vorwaerts-Wiederaufnehmen; sie
    braeuchte die ganze Protokollzeile im Marker und damit eine zweite
    Quelle fuer denselben Inhalt.
    """
    vorher = None
    if ablage.stand.is_symlink():
        vorher = ablage.stand.resolve().name
    elif ablage.stand.is_dir():
        vorher = STAND_DIR
    ablage.journal.mkdir(parents=True, exist_ok=True)
    if ablage.tagesjournal_pfad.is_file():
        ablage.tagesjournal_vorher_pfad.write_bytes(
            ablage.tagesjournal_pfad.read_bytes())
    _schreibe_json_atomar(ablage.publish_marker, {
        "schema_version": 1,
        "heute": heute.isoformat(),
        "generation": generation,
        "stand_vorher": vorher,
        "journal_vorher": (
            _datei_hash(ablage.tagesjournal_vorher_pfad)
            if ablage.tagesjournal_vorher_pfad.is_file() else None),
    })


def entferne_publish_marker(ablage: "Ablage") -> None:
    """Der Publish ist durch — der Zwischenzustand endet hier."""
    ablage.publish_marker.unlink(missing_ok=True)
    ablage.tagesjournal_vorher_pfad.unlink(missing_ok=True)


def _schneide_teilzeile(pfad: Path) -> bool:
    """Eine angefangene, nie abgeschlossene Protokollzeile entfernen.

    Eine Zeile des Protokolls gilt als geschrieben, wenn sie mit einem
    Zeilenumbruch endet — das ist die Commitgrenze eines anfuegbaren
    Journals. Bricht der Schreibvorgang mittendrin ab, steht ein Fragment
    ohne Umbruch am Ende der Datei. Es ist nie eine Zeile geworden, und es
    wegzuschneiden nimmt nichts zurueck, was jemals galt.

    Ohne diesen Schnitt endete JEDER Wiederanlauf im JSON-Fehler von
    ``lies_protokoll``: Die Ruecknahme liest das Protokoll, bevor sie
    irgendetwas zuruecksetzen kann, und blieb damit dauerhaft haengen
    (Befund T26-02, Szenario 3).

    Bewusst eng: Endet die Datei mit einem Umbruch, wird nichts angefasst.
    Eine vollstaendige Zeile, die kein JSON ist, ist echte Beschaedigung
    und bleibt ein Fehler — dafuer gibt es keinen Ausweg, der nicht
    Beweismaterial vernichtet. Gerufen wird am Anfang JEDES Laufs unter
    der Sperre und noch einmal aus der Ruecknahme: Ein Fragment ohne
    Umbruch ist nie eine Zeile geworden — ob ein Marker daneben liegt oder
    nicht. Die erste Fassung schnitt nur unter dem Publish-Marker; die
    angefangene Zeile eines ROTEN Laufs (der keinen Marker setzt) sperrte
    die Ablage dauerhaft (Kalibrierungsfund N7 der Pruefrunde T27).

    Abgeschnitten wird IN DER DATEI (``os.truncate``), nie durch
    Neuschreiben: Die erste Fassung schrieb ``roh[:schnitt]`` mit
    ``write_bytes`` — sie leerte die Datei und schrieb die belegten Zeilen
    zurueck. Ein zweiter Ausfall zwischen beidem liess ein Protokoll mit
    null Bytes zurueck, und jeder Wiederanlauf verweigerte dauerhaft, weil
    der belegte Vortag darin nicht mehr vorkam (Pruefrunde T27, Befund 01).
    Belegte Bytes gehen durch keinen Schreibpfad; scheitert der Schnitt,
    bleibt die Datei, wie sie war, und der naechste Lauf schneidet.

    Geschnitten wird nur ein FRAGMENT — was kein vollstaendiges JSON-Objekt
    ist. Eine vollstaendige Endzeile ohne Umbruch wird mit ``\n``
    abgeschlossen, nicht geloescht (Nachbesserung Runde C, Probe des
    Pruefers Fall C): Die erste Fassung schnitt jede Endzeile ohne Umbruch,
    und wer ohne Schluessel nur das letzte Byte einer ROTEN, gezeichneten
    Zeile entfernte, liess das Programm selbst den roten Lauf ungeschehen
    machen. Ob die abgeschlossene Zeile etwas bezeugt, entscheidet danach
    der Leser (Kette, Zeichnung) — ein Befund bleibt ein Befund, statt
    Beweismaterial zu vernichten. Rueckgabe True, wenn die Datei angefasst
    wurde (geschnitten oder abgeschlossen).
    """
    if not pfad.is_file():
        return False
    roh = pfad.read_bytes()
    if not roh or roh.endswith(b"\n"):
        return False
    schnitt = roh.rfind(b"\n") + 1
    if _ist_vollstaendige_zeile(roh[schnitt:]):
        # Anfuegen, nie neu schreiben: belegte Bytes gehen durch keinen
        # Schreibpfad (derselbe Grund wie os.truncate unten).
        with open(pfad, "ab") as f:
            f.write(b"\n")
            f.flush()
            os.fsync(f.fileno())
        print(
            f"tageslauf: {pfad} endete mit einer vollstaendigen Zeile ohne "
            "Zeilenumbruch — sie wurde abgeschlossen, nicht entfernt; ob sie "
            "etwas bezeugt, prueft der Leser.",
            file=sys.stderr,
        )
        return True
    os.truncate(pfad, schnitt)
    print(
        f"tageslauf: {pfad} endete mit einer angefangenen Zeile "
        f"({len(roh) - schnitt} Bytes ohne Zeilenumbruch) — sie ist nie "
        "geschrieben worden und wurde entfernt; der Tag wird erneut gefuehrt.",
        file=sys.stderr,
    )
    return True


def _ist_vollstaendige_zeile(rest: bytes) -> bool:
    """Ob ``rest`` (die Bytes nach dem letzten Umbruch) ein vollstaendiges
    JSON-Objekt ist — dann ist es eine Zeile, der nur das Zeilenende fehlt.
    Ein abgebrochenes ``json.dumps`` eines Objekts ist nie gueltiges JSON."""
    try:
        return isinstance(json.loads(rest.decode("utf-8")), dict)
    except (UnicodeDecodeError, ValueError):
        return False


def nimm_publish_zurueck(
    ablage: "Ablage", zeichner: Optional[Zeichner] = None,
) -> Optional[Dict[str, Any]]:
    """Einen unterbrochenen Publish zuruecknehmen; liefert den Marker.

    Der Lauf ist idempotent und deterministisch — der sauberste Weg aus
    einem halben Publish ist deshalb nicht, ihn fortzusetzen, sondern ihn
    zurueckzunehmen und den Tag erneut zu fuehren.

    Zurueckgenommen wird, was sich zuruecknehmen LAESST: das Journal aus
    seiner Kopie, der Symlink auf die vorherige Generation. Die
    Monatsabschluesse bleiben — sie sind unwiderruflich (0444, ADR-011),
    und der erneute Lauf rechnet sie nach, statt sie zu glauben (Schritt
    a desselben Reviews). Ist der Publish bereits vollstaendig gewesen
    (die Protokollzeile steht), wird nur aufgeraeumt.
    """
    if not ablage.publish_marker.is_file():
        return None
    try:
        marker = json.loads(ablage.publish_marker.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise TageslaufError(
            f"{ablage.publish_marker} liegt vor, laesst sich aber nicht lesen "
            f"({exc}) — ob ein Publish unterwegs war, ist damit unbekannt, und "
            "eine Ruecknahme auf Verdacht waere schlimmer als keine. Datei "
            "pruefen und von Hand entfernen, wenn die Ablage stimmig ist"
        ) from exc
    tag = str(marker.get("heute"))
    # Erst die angefangene Zeile wegschneiden, dann lesen: Sonst stirbt die
    # Ruecknahme an dem Zustand, den sie zuruecknehmen soll (T26-02).
    _schneide_teilzeile(ablage.protokoll_pfad)
    gruene = [z for z in _protokoll(ablage, zeichner) if z.get("uebernommen")]
    if gruene and str(gruene[-1].get("heute")) == tag:
        # Der Publish war durch, nur das Aufraeumen fehlte.
        entferne_publish_marker(ablage)
        return marker
    if ablage.tagesjournal_vorher_pfad.is_file():
        ablage.tagesjournal_pfad.write_bytes(
            ablage.tagesjournal_vorher_pfad.read_bytes())
    elif marker.get("journal_vorher") is None:
        # Vor dem Publish gab es kein Journal — dann gehoert auch keines
        # in die zurueckgenommene Ablage.
        ablage.tagesjournal_pfad.unlink(missing_ok=True)
    vorher = marker.get("stand_vorher")
    if (vorher and vorher != STAND_DIR
            and ablage.stand.is_symlink()
            and ablage.stand.resolve().name != vorher
            and (ablage.wurzel / str(vorher)).is_dir()):
        tmp = ablage.wurzel / STAND_LINK_TMP
        tmp.unlink(missing_ok=True)
        os.symlink(str(vorher), tmp)
        os.replace(tmp, ablage.stand)
    elif vorher == STAND_DIR and (
            ablage.stand.is_symlink() or not ablage.stand.exists()):
        # Vor dem Publish war ``stand`` ein echtes VERZEICHNIS (Legacy).
        # Der Erstuebergang schiebt es nach stand-erstfassung und setzt den
        # Symlink; zurueckgenommen ist das erst, wenn beides wieder steht.
        #
        # Die einzige Ruecksetzbedingung schloss diesen Zustand
        # ausdruecklich aus (``vorher != STAND_DIR``). Danach fuehrte der
        # Symlink den neuen Tag, das Protokoll den alten, und jeder
        # weitere Lauf meldete "Stand und Nachweis passen nicht zusammen"
        # — dauerhaft (Befund T26-02, Szenario 2).
        #
        # Zwei Abbruchstellen fallen darunter, und sie sehen verschieden
        # aus: Bricht der Tausch NACH dem Beiseiteschieben ab, gibt es
        # ``stand`` gar nicht mehr; bricht er danach ab, ist es ein
        # Symlink auf die neue Generation. Gefragt wird deshalb, ob
        # ``stand`` noch das echte Verzeichnis von vorher ist — nicht,
        # welche der beiden Formen gerade vorliegt.
        erstfassung = ablage.wurzel / f"{STAND_DIR}-erstfassung"
        if erstfassung.is_dir():
            if ablage.stand.is_symlink():
                ablage.stand.unlink()
            os.rename(erstfassung, ablage.stand)
    elif vorher is None:
        # Vor dem Publish gab es KEINEN Stand (Erstbefuellung). Die einzige
        # Ruecksetzbedingung darueber verlangte einen vorherigen Stand, und
        # ohne einen blieb der neue stehen, waehrend Journal und Marker
        # zurueckgenommen wurden: Danach meldete jeder Lauf dauerhaft
        # "Protokoll kennt keinen uebernommenen Lauf" (Befund T26-02,
        # Szenario 1). Zurueckgenommen ist die Ablage erst, wenn auch der
        # neue Stand wieder weg ist.
        #
        # Geloescht wird hier mit FESTSTEHENDER Identitaet, nicht nach
        # Gestalt: Der Marker nennt die Generation, die veroeffentlicht
        # werden sollte, und der Symlink zeigt genau auf sie.
        generation = str(marker.get("generation") or "")
        if (generation and ablage.stand.is_symlink()
                and ablage.stand.resolve().name == generation):
            ablage.stand.unlink()
            neu = ablage.wurzel / generation
            if neu.is_dir():
                _entferne_ablageverzeichnis(ablage, neu)
    entferne_publish_marker(ablage)
    print(
        f"tageslauf: unterbrochener Publish vom {tag} zurueckgenommen — die "
        "Ablage steht wieder auf dem Stand davor; der Tag wird erneut "
        "gefuehrt. Festgeschriebene Monatsabschluesse bleiben stehen und "
        "werden nachgerechnet.",
        file=sys.stderr,
    )
    return marker


def _zeilen_hash(roh: str) -> str:
    return hashlib.sha256(roh.encode("utf-8")).hexdigest()


def _protokoll(ablage: "Ablage", zeichner: Optional[Zeichner]) -> List[Dict[str, Any]]:
    """Das Protokoll der Ablage, gegen den Betriebsschluessel geprueft.

    Ohne ausdruecklichen Zeichner gilt die Aufloesung des Tageslaufs
    (:func:`betriebszeichner`) — im Betrieb wird nie ungeprueft gelesen.
    """
    z = zeichner if zeichner is not None else betriebszeichner(ablage)
    return lies_protokoll(ablage.protokoll_pfad, schluesselring=z.ring, ordnung=z.ordnung)


def lies_protokoll(
    pfad: Path,
    *,
    schluesselring: Optional[Dict[str, bytes]] = None,
    ordnung: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Alle Zeilen des Tagesprotokolls (leer, wenn es noch keines gibt) —
    mit Pruefung der Kette und, mit ``schluesselring``, der Zeichnung.

    Review T22-05: Das Protokoll war editierbar, ohne dass es jemand
    merkte — eine entfernte mittlere Zeile liess den letzten Tag weiter
    gelten. Jede Zeile ab Schema 2 nennt den Hash ihrer Vorgaengerin; eine
    Luecke, eine Aenderung oder eine Umsortierung bricht die Kette, und
    ein gebrochenes Protokoll ist ein Befund, kein Nachweis. Seit Schema 3
    ist jede Zeile gezeichnet (siehe :func:`lies_protokoll_text`).
    """
    if not Path(pfad).is_file():
        return []
    return lies_protokoll_text(
        Path(pfad).read_text(encoding="utf-8"), str(pfad),
        schluesselring=schluesselring, ordnung=ordnung)


def aufschaltung_fehler(
    zeilen: List[Dict[str, Any]], *, aufschalten: bool = False, wer: str = "der Tageslauf",
) -> Optional[str]:
    """Was gegen das Weiterschreiben auf diesem Protokoll spricht (None = nichts).

    Nachbesserung Runde C (Probe des Pruefers, Fall A): Ein Protokoll ohne
    gezeichnete Zeile sieht in der Ablage genau so aus wie ein Altbestand
    vor dem Betriebsschluessel — auch dann, wenn ein Schreiber ohne
    Schluessel ein gezeichnetes Protokoll herabgestuft hat (Zeichnungen und
    Pin entfernt, Zahlen gefaelscht, Kette neu verkettet). Die erste
    Fassung pinnte einen solchen Vorlauf stillschweigend und ZEICHNETE ihn
    damit. Aus der Ablage allein sind beide Lesarten nicht zu
    unterscheiden; darum entscheidet der Mensch, AUSDRUECKLICH und einmal:

    - Protokoll mit Zeilen, keine gezeichnet: nur mit ``aufschalten``
      (erster Lauf nach dem Umstieg, deploy/plv/README.md).
    - Protokoll mit gezeichneter Zeile und ``aufschalten``: verweigert — die
      Aufschaltung ist geschehen, und ein Schalter, der dauerhaft im Timer
      stuende, oeffnete die Herabstufung wieder.
    - Leeres Protokoll (Erstbefuellung): kein Schalter noetig; mit ihm
      verweigert, denn er ist nie ein stilles No-op.

    Ist ein schon gezeichnetes Protokoll spaeter wieder ohne gezeichnete
    Zeile, ist das ein Kettenbruch, kein zweiter Aufschaltfall. Die Ablage
    sieht das nicht; den Bezug nach aussen liefert der Anker: Die Zeile,
    die der letzte Export verankert hat, steht dann nicht mehr im
    Protokoll, und der naechste Export verweigert (``models.anker.pruefe_reihe``).
    """
    gezeichnet = [i for i, z in enumerate(zeilen, 1) if z.get("schema_version", 1) >= 3]
    if gezeichnet and aufschalten:
        return (
            f"--aufschalten, aber das Protokoll ist schon gezeichnet (Zeile "
            f"{gezeichnet[0]} ist die erste gezeichnete) — die Aufschaltung ist der "
            "einmalige Schritt beim ersten Lauf nach dem Umstieg und ist geschehen. "
            "Ausweg: ohne --aufschalten fahren (und den Schalter aus dem Timer nehmen)")
    if gezeichnet:
        return None
    if not zeilen:
        if aufschalten:
            return ("--aufschalten, aber das Protokoll ist leer — nichts aufzuschalten; "
                    "die Erstbefuellung laeuft ohne den Schalter")
        return None
    if aufschalten:
        return None
    return (
        f"das Protokoll traegt {len(zeilen)} Zeile(n), aber keine gezeichnete Zeile — "
        f"{wer} zeichnet oder veroeffentlicht darauf nichts. Das ist entweder ein "
        "Altbestand vor dem Betriebsschluessel oder ein ohne Schluessel "
        "herabgestuftes Protokoll; die Ablage allein unterscheidet das nicht. "
        "Ausweg: ist es der erste Lauf nach dem Umstieg, den Tageslauf EINMAL mit "
        "--aufschalten fahren (deploy/plv/README.md; die erste gezeichnete Zeile "
        "pinnt dann den Vorlauf). War das Protokoll schon gezeichnet, ist es ein "
        "Kettenbruch: das Protokoll aus der Sicherung wiederherstellen, NICHT "
        "aufschalten")


def _vorlauf_pin(rohe: List[str]) -> Dict[str, Any]:
    """Zahl und Hash der ungezeichneten Zeilen vor der ersten gezeichneten.

    Gehasht wird, was auf der Platte steht: jede rohe Zeile mit ihrem
    Zeilenende, in der Reihenfolge der Datei. Die Kette allein deckt den
    Vorlauf nicht ab — Zeilen nach Schema 1 tragen keinen Vorgaenger-Hash.
    """
    return {
        "zeilen": len(rohe),
        "sha256": hashlib.sha256("".join(r + "\n" for r in rohe).encode("utf-8")).hexdigest(),
    }


def lies_protokoll_text(
    text: str,
    pfad: str,
    *,
    schluesselring: Optional[Dict[str, bytes]] = None,
    ordnung: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Wie :func:`lies_protokoll`, auf schon gelesenen Bytes — fuer einen
    Konsumenten, der Hash, Kette und Anker auf EINER Lesung prueft.

    Geprueft wird je Zeile: JSON-Objekt, Schema bekannt und nicht kleiner
    als das der Zeilen davor (RC10: eine auf Schema 1 herabgestufte Zeile
    schaltete Kette und Nachweis ab), die Kette ab Schema 2, ab Schema 3 die
    Zeichnung (Form immer; Rolle gegen ``ordnung``, Signatur gegen
    ``schluesselring``, wenn gegeben) und der Vorlauf-Pin der ersten
    gezeichneten Zeile.
    """
    zeilen: List[Dict[str, Any]] = []
    rohe: List[str] = []
    vorgaenger_roh: Optional[str] = None
    hoechstes = 0
    gezeichnet = False
    for nummer, roh in enumerate(jsonl_zeilen(text), 1):
        try:
            zeile = json.loads(roh)
        except json.JSONDecodeError as exc:
            raise TageslaufError(
                f"{pfad}: Zeile {nummer} ist kein JSON ({exc}) — das Protokoll "
                "ist nur-anfuegbar; eine kaputte Zeile ist ein Befund, kein "
                "Grund zum Ueberschreiben"
            ) from exc
        if not isinstance(zeile, dict):
            raise TageslaufError(f"{pfad}: Zeile {nummer} ist kein JSON-Objekt")
        schema = zeile.get("schema_version", 1)
        if (isinstance(schema, bool) or not isinstance(schema, int)
                or not 1 <= schema <= PROTOKOLL_SCHEMA_VERSION):
            raise TageslaufError(
                f"{pfad}: Zeile {nummer} traegt schema_version {schema!r} — bekannt "
                f"sind 1 bis {PROTOKOLL_SCHEMA_VERSION}; ein neueres Protokoll liest "
                "nur ein neueres Image")
        if schema < hoechstes:
            # RC10: Die Kette galt nur fuer Zeilen, die sich selbst Schema 2
            # zuschrieben. Eine herabgestufte Zeile hinter gezeichneten ist
            # keine alte Zeile, sondern eine umgeschriebene.
            raise TageslaufError(
                f"{pfad}: Zeile {nummer} bricht die Protokollkette — Schema "
                f"{schema} hinter einer Zeile mit Schema {hoechstes}; das Schema "
                "steigt nur, eine Herabstufung ist eine umgeschriebene Zeile")
        hoechstes = schema
        if schema >= 2:
            erwartet = _zeilen_hash(vorgaenger_roh) if vorgaenger_roh is not None else ""
            if zeile.get("vorgaenger_sha256") != erwartet:
                raise TageslaufError(
                    f"{pfad}: Zeile {nummer} bricht die Protokollkette (vorgaenger_sha256 "
                    f"passt nicht zur Zeile davor) — das Protokoll wurde veraendert, "
                    "gekuerzt oder umsortiert; es ist damit kein Nachweis mehr"
                )
        if schema >= 3:
            fehler = betriebszeichnung_fehler(zeile, schluesselring, ordnung)
            if fehler:
                raise TageslaufError(f"{pfad}: Zeile {nummer}: {fehler}")
            if not gezeichnet:
                soll = _vorlauf_pin(rohe) if rohe else None
                if zeile.get("vorlauf") != soll:
                    raise TageslaufError(
                        f"{pfad}: Zeile {nummer} ist die erste gezeichnete und pinnt "
                        f"den ungezeichneten Vorlauf nicht ({zeile.get('vorlauf')!r} "
                        f"statt {soll!r}) — der Vorlauf wurde nach der Aufschaltung "
                        "veraendert")
                gezeichnet = True
            elif "vorlauf" in zeile:
                raise TageslaufError(
                    f"{pfad}: Zeile {nummer} pinnt einen Vorlauf, obwohl vor ihr schon "
                    "gezeichnet wurde — nur die erste gezeichnete Zeile tut das")
        zeilen.append(zeile)
        rohe.append(roh)
        vorgaenger_roh = roh
    return zeilen


def pruefe_nachweis(
    ablage: Ablage, gruene: List[Dict[str, Any]]
) -> Dict[str, Optional[bytes]]:
    """Der Nachweisvertrag zwischen Protokoll, Stand und Journal (T22-05).

    Oeffentlich seit Review T24-03: Der Vertrag galt nur fuer den, der ihn
    durchlief. ``gefuehrter_tag`` lehnte ein veraendertes Journal ab, die
    Seite und das Stands-Paket lasen dieselben Bytes ohne jede Pruefung
    erneut und zeigten den manipulierten Betrag — waehrend die Provenienz
    daneben weiter den alten Journal-Hash nannte. Wer Protokoll, Stand
    oder Journal auswertet, ruft das hier ZUERST.

    Gruene Zeilen sind lueckenlos verkettet (jede nennt den vorigen Tag,
    ihre nachgeholten Tage fuellen genau die Luecke), die letzte gruene
    Zeile nennt den Manifest-Hash des Stands und den Hash des Journals —
    was auf der Platte liegt, muss dem entsprechen, sonst ist das
    Protokoll eine Behauptung ueber einen anderen Stand.

    ZURUECKGEGEBEN werden die geprueften BYTES (Befund T26-10). Vorher
    hat diese Funktion gehasht und die Bytes weggeworfen; der Aufrufer
    las dieselben Dateien danach erneut. An der Naht dazwischen passt ein
    ganzer Tageslauf: Die Gegenprobe des Gutachters hat unmittelbar nach
    dem Lesen des alten Manifests einen zweiten, voellig regulaeren Lauf
    gestartet. Die Seite nannte danach den 03.02. und P-B1 gruen, zeigte
    Buchungen bis zum 10.02. und einen Journal-Hash, der nicht zum
    ausgewerteten Journal passte — zwei autonom gueltige Generationen zu
    einem Stand vermischt, den es nie gab.

    Eine Sperre haette den einen Weg geschuetzt, den sie umschliesst.
    Wer die geprueften Bytes weiterreicht, schuetzt jeden.
    """
    for vorher, jetzt in zip(gruene, gruene[1:]):
        tag_vorher = _dt.date.fromisoformat(str(vorher["heute"]))
        tag_jetzt = _dt.date.fromisoformat(str(jetzt["heute"]))
        if tag_jetzt <= tag_vorher:
            # RC11: Eine zweite gruene Zeile fuer denselben Tag, kettenrichtig
            # angefuegt, wurde angenommen — und mit ihr jede Zahl, die nicht
            # nachgerechnet wird. Je gefuehrtem Tag gibt es genau eine gruene
            # Zeile: Ein Lauf auf den gefuehrten Tag ist ein No-op ohne Zeile,
            # und rueckwaerts wird nicht gefuehrt. Das gilt fuer JEDES Schema.
            raise TageslaufError(
                f"Protokoll: zwei gruene Zeilen fuer {tag_jetzt.isoformat()} "
                f"(nach {tag_vorher.isoformat()}) — je gefuehrtem Tag gibt es genau "
                "eine gruene Zeile; die spaetere wurde angefuegt, nicht gelaufen")
        if jetzt.get("schema_version", 1) < 2:
            continue
        if jetzt.get("gefuehrt_vorher") != vorher["heute"]:
            raise TageslaufError(
                f"Protokoll: der Lauf {tag_jetzt.isoformat()} nennt als vorherigen Tag "
                f"{jetzt.get('gefuehrt_vorher')!r}, der letzte gruene Lauf davor fuehrte "
                f"{tag_vorher.isoformat()} — Tagesluecke oder fehlende Zeile"
            )
        erwartet = [
            (tag_vorher + _dt.timedelta(days=k)).isoformat()
            for k in range(1, (tag_jetzt - tag_vorher).days)
        ]
        if list(jetzt.get("nachgeholt") or []) != erwartet:
            raise TageslaufError(
                f"Protokoll: die nachgeholten Tage des Laufs {tag_jetzt.isoformat()} "
                "fuellen die Luecke zum vorigen Tag nicht"
            )
    letzte = gruene[-1]
    gelesen: Dict[str, Optional[bytes]] = {"manifest": None, "journal": None}
    if letzte.get("schema_version", 1) >= 2:
        manifest_pfad = ablage.stand / MANIFEST_DATEI
        gelesen["manifest"] = (
            manifest_pfad.read_bytes() if manifest_pfad.is_file() else None)
        manifest_hash = (
            sha256_bytes(gelesen["manifest"])
            if gelesen["manifest"] is not None else None)
        if letzte.get("manifest_sha256") != manifest_hash:
            raise TageslaufError(
                "Protokoll und Stand passen nicht zusammen: die letzte gruene Zeile "
                f"nennt Manifest {str(letzte.get('manifest_sha256'))[:16]}…, der Stand "
                f"traegt {str(manifest_hash)[:16]}…"
            )
        journal_hash = (letzte.get("tagesjournal") or {}).get("sha256")
        gelesen["journal"] = (
            ablage.tagesjournal_pfad.read_bytes()
            if ablage.tagesjournal_pfad.is_file() else None)
        ist = (sha256_bytes(gelesen["journal"])
               if gelesen["journal"] is not None else None)
        if journal_hash != ist:
            raise TageslaufError(
                "Protokoll und Journal passen nicht zusammen: das Tagesjournal hat "
                "nicht den Hash, den die letzte gruene Zeile nennt — das Journal "
                "wurde veraendert oder gehoert zu einem anderen Stand"
            )
        if gelesen["manifest"] is not None and isinstance(letzte.get("bestand"), dict):
            _pruefe_zahlen_der_zeile(ablage, letzte, gelesen["manifest"], gelesen["journal"])
    _pruefe_festgeschriebene_abschluesse(ablage, gruene)
    return gelesen


def _pruefe_festgeschriebene_abschluesse(ablage: Ablage, gruene: List[Dict[str, Any]]) -> None:
    """Jeder Abschluss, den eine gruene Zeile mit Hash bezeugt, liegt noch so da.

    RC12: Ein festgeschriebener Abschluss wurde nach seinem Lauf nie wieder
    geprueft. Ersetzt (drei statt sechzehn Vertraege) und in der Zeile
    nachgezogen, war er dauerhaft als festgeschrieben belegt, und jeder
    spaetere Lauf nannte ihn wieder. Ein Abschluss wird genau einmal
    geschrieben (ADR-011); was eine Zeile ueber ihn bezeugt, gilt fuer
    immer, und jede Zeile muss dasselbe bezeugen.
    """
    bezeugt: Dict[str, str] = {}
    for zeile in gruene:
        for a in zeile.get("abschluesse") or []:
            if not (a.get("sha256") and a.get("datei")):
                continue
            datei = str(a["datei"])
            if bezeugt.setdefault(datei, str(a["sha256"])) != str(a["sha256"]):
                raise TageslaufError(
                    f"Protokoll: der Abschluss {datei} wird mit zwei verschiedenen "
                    "Hashes bezeugt — ein festgeschriebener Abschluss aendert sich nie "
                    "(ADR-011)")
    for datei, soll in sorted(bezeugt.items()):
        pfad = ablage.abschluesse / datei
        if not pfad.is_file():
            raise TageslaufError(
                f"{pfad}: der Abschluss ist im Protokoll bezeugt, liegt aber nicht mehr "
                "in der Ablage — ein festgeschriebener Abschluss wird nie entfernt "
                "(ADR-011); die Datei aus der Sicherung wiederherstellen")
        if sha256_bytes(pfad.read_bytes()) != soll:
            raise TageslaufError(
                f"{pfad}: nicht der Abschluss, den das Protokoll bezeugt "
                f"({soll[:16]}…) — ein festgeschriebener Abschluss wird nie "
                "ueberschrieben (ADR-011); die Datei aus der Sicherung wiederherstellen")


def verankerung_angabe(registriert: Optional[int], mit_schicht: bool) -> Dict[str, Any]:
    """Die Verankerungsangabe einer Protokollzeile — EINE Formulierung.

    Der Lauf schreibt sie, der Nachweis rechnet sie aus dem Stand nach
    (RC13: ``{angewandt: true, registriert: 999}`` stand frei behauptet in
    der Zeile und ging veroeffentlicht durch). ``registriert`` None heisst:
    der Stand traegt keine Verankerung.
    """
    return {
        "registriert": int(registriert or 0),
        # Seit Schritt 9 gehen Verankerung und Korrekturschicht in die
        # Fortschreibung ein (Schritte 4 und 5): angewandt heisst, die
        # Schicht lag vor und wurde der Engine uebergeben.
        "angewandt": bool(registriert is not None and mit_schicht),
        "hinweis": (
            "Verankerung und Korrekturschicht der uebernommenen Vertraege gehen "
            "in Storno und Bewertung der Fortschreibung ein (Freischaltung, "
            "Schritte 4/5/9)"
            if registriert is not None and mit_schicht
            else "Verankerung registriert, aber ohne Korrekturschicht (schichten.parquet) "
            "nicht angewandt — der Eingang traegt keinen Schichtbeleg"
            if registriert is not None
            else "keine Verankerung uebernommen"
        ),
    }


def zeile_gegen_manifest(letzte: Dict[str, Any], manifest: Dict[str, Any]) -> List[str]:
    """Was die letzte gruene Zeile ueber Herkunft und Eingaenge sagt, gegen
    das Manifest des Stands, das sie ueber ``manifest_sha256`` bindet.

    Ohne Ablage und ohne Schluessel rechenbar — der Konsument eines
    Stands-Pakets traegt das Manifest mit (RC13, RC14): Config-Hash und
    Kern-Version schreibt der Lauf aus derselben Config und demselben Code
    in Zeile und Manifest; die Eingaenge, die der Stand fuehrt, nennt das
    Manifest mit dem Hash ihrer eingang.json. Eine Zeile, die andere
    Eingaenge nennt oder keine, spricht von einem anderen Stand.
    """
    abweichend: List[str] = []
    if letzte.get("config_sha256") != (manifest.get("config") or {}).get("sha256"):
        abweichend.append("config_sha256")
    if letzte.get("kern_version") != manifest.get("kern_version"):
        abweichend.append("kern_version")
    im_manifest = {
        rolle.split(":", 1)[1]: (eintrag or {}).get("sha256")
        for rolle, eintrag in (manifest.get("eingaben") or {}).items()
        if str(rolle).startswith("uebernahme:")
    }
    in_zeile = {str(u.get("fall")): u.get("eingang_sha256")
                for u in letzte.get("uebernahmen") or []}
    if im_manifest != in_zeile:
        abweichend.append("uebernahmen (Faelle und eingang_sha256 gegen das Manifest)")
    ausgaben = manifest.get("ausgaben") or {}
    verankerung = letzte.get("verankerung")
    if isinstance(verankerung, dict):
        if "verankerung.parquet" not in ausgaben and verankerung != verankerung_angabe(None, False):
            abweichend.append("verankerung")
        elif "verankerung.parquet" in ausgaben and (
                bool(verankerung.get("angewandt")) != ("schichten.parquet" in ausgaben)):
            abweichend.append("verankerung.angewandt")
    return abweichend


def _pruefe_zahlen_der_zeile(
    ablage: Ablage, letzte: Dict[str, Any], manifest_roh: bytes,
    journal_roh: Optional[bytes] = None,
) -> None:
    """Die Bestandszahlen der letzten gruenen Zeile, aus dem Stand nachgerechnet.

    Angriffsrunde nach T27: Die letzte Zeile hat keinen Nachfolger, der sie
    bindet, und vor ihrer ersten Verankerung auch keinen Anker. Stimmig
    umgeschrieben (1003 statt 3 Vertraege in Kraft, 5000 Neugeschaeft)
    verankerte der Export die Faelschung, der Konsument nahm sie an, und
    der naechste Lauf kettete an. Die Zahlen sind aber keine eigene Aussage
    der Zeile: Sie folgen aus dem Stand, den ihr Manifest-Hash bindet, und
    aus den registrierten Eingaengen — und werden hier daraus gerechnet.

    Pruefrunde nach T27, Runde C: Geprueft waren nur Zaehlungen. Die
    Monatskennzahlen der Abschluesse (RC12), Stichtag, Snapshot und
    Zeichnung der Uebernahmen, die Verankerung und die Provenienz (RC13)
    standen frei behauptet in der Zeile. Jetzt gilt fuer jedes Feld, das
    aus Stand, Abschlussdatei, Eingang oder Config folgt: gerechnet oder
    gleich, nie geglaubt.
    """
    import io

    from rechner_pipeline.bestand.fuehrung import bestand_am
    from rechner_pipeline.betrieb.uebernahme import zielnummern

    manifest = json.loads(manifest_roh.decode("utf-8"))
    ausgaben = (manifest.get("ausgaben") or {})

    def lies(name: str) -> pd.DataFrame:
        roh = (ablage.stand / name).read_bytes()
        if sha256_bytes(roh) != ausgaben.get(name):
            raise TageslaufError(
                f"{ablage.stand / name}: nicht die Datei, die das Manifest des Stands bindet")
        return read_portfolio(io.BytesIO(roh))

    portfolio = lies("bestand_gesamt.parquet")
    historie = lies("historie.parquet")
    basis = lies("bestand.parquet") if "bestand.parquet" in ausgaben else None
    heute = _dt.date.fromisoformat(str(letzte["heute"]))
    schnitt = bestand_am(portfolio, historie, heute)
    uebernommene: set = set()
    je_eingang: Dict[str, int] = {}
    from rechner_pipeline.betrieb.uebernahme import UebernahmeError

    for u in letzte.get("uebernahmen") or []:
        verzeichnis = ablage.uebernahme / str(u.get("fall"))
        if not verzeichnis.is_dir():
            raise TageslaufError(
                f"Eingang {u.get('fall')!r}: gefuehrt und im Protokoll bezeugt, aber "
                "nicht mehr in der Ablage (entfernt oder umbenannt) — ein Eingang ist "
                "unantastbar; den urspruenglichen Eingang wiederherstellen")
        try:
            ziele = set(int(z) for z in zielnummern(verzeichnis).values())
        except UebernahmeError as exc:
            raise TageslaufError(f"Eingang {u.get('fall')!r}: {exc}") from exc
        je_eingang[str(u.get("fall"))] = len(ziele)
        uebernommene |= ziele
    soll = {
        "in_force": int(len(schnitt)),
        "je_produkt": {str(k): int(v) for k, v in sorted(schnitt["produkt"].value_counts().items())},
        "uebernommen_in_force": int(schnitt["police_id"].isin(uebernommene).sum()),
        "policiert_beginn_folgt": int((portfolio["insurance_start"] > pd.Timestamp(heute)).sum()),
    }
    abweichend = [k for k, v in soll.items() if letzte["bestand"].get(k) != v]
    for u in letzte.get("uebernahmen") or []:
        if u.get("vertraege") != je_eingang.get(str(u.get("fall"))):
            abweichend.append(f"uebernahmen[{u.get('fall')}].vertraege")
        # RC13: Stichtag, Snapshot und Zeichnung der A-M4-Annahme stehen in
        # der eingang.json, deren Hash dieselbe Zeile nennt — aus ihr, nicht
        # aus der Zeile.
        eingang_pfad = ablage.uebernahme / str(u.get("fall")) / "eingang.json"
        try:
            eingang_roh = eingang_pfad.read_bytes()
            eingang = json.loads(eingang_roh.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TageslaufError(f"{eingang_pfad}: nicht lesbar ({exc})") from exc
        if sha256_bytes(eingang_roh) != u.get("eingang_sha256"):
            abweichend.append(f"uebernahmen[{u.get('fall')}].eingang_sha256")
        for feld in ("stichtag", "snapshot_sha256", "zeichnung"):
            if u.get(feld) != eingang.get(feld):
                abweichend.append(f"uebernahmen[{u.get('fall')}].{feld}")
    abweichend.extend(zeile_gegen_manifest(letzte, manifest))
    if "verankerung.parquet" in ausgaben and isinstance(letzte.get("verankerung"), dict):
        soll_v = verankerung_angabe(
            int(len(lies("verankerung.parquet"))), "schichten.parquet" in ausgaben)
        if letzte["verankerung"] != soll_v:
            abweichend.append("verankerung")
    # RC12: Die Monatskennzahlen folgen aus der festgeschriebenen
    # Abschlussdatei (in_kraft) und dem Tagesjournal (zugaenge, leistungen)
    # — mit derselben Funktion, die der Lauf beim Schreiben ruft.
    journal = (read_portfolio(io.BytesIO(journal_roh), expected_columns=TAGESJOURNAL_NAMES)
               if journal_roh is not None else None)
    for a in letzte.get("abschluesse") or []:
        if not a.get("datei"):
            continue
        pfad = ablage.abschluesse / str(a["datei"])
        if not pfad.is_file():
            continue  # _pruefe_festgeschriebene_abschluesse nennt es mit Ausweg
        roh = pfad.read_bytes()
        if a.get("sha256") and sha256_bytes(roh) != a["sha256"]:
            continue  # dort ebenso
        soll_k = {"in_kraft": int(len(read_portfolio(io.BytesIO(roh))))}
        if journal is not None:
            from rechner_pipeline.bestand.kennzahlen import bewegungskennzahlen

            soll_k.update(bewegungskennzahlen(journal, _dt.date.fromisoformat(str(a["stichtag"]))))
        for feld, wert in soll_k.items():
            if feld in a and a[feld] != wert:
                abweichend.append(f"abschluesse[{a.get('stichtag')}].{feld}")
    if basis is not None and "basisvertraege" in letzte:
        # Die Basis des Laufs ist der eigene Anfangsbestand (bestand.parquet)
        # plus jeder uebernommene Vertrag; alles darueber ist Neugeschaeft.
        basis_soll = int(len(basis)) + sum(je_eingang.values())
        if letzte["basisvertraege"] != basis_soll:
            abweichend.append("basisvertraege")
        if "neugeschaeft_seit_betriebsbeginn" in letzte and letzte[
                "neugeschaeft_seit_betriebsbeginn"] != int(len(portfolio)) - basis_soll:
            abweichend.append("neugeschaeft_seit_betriebsbeginn")
    if abweichend:
        raise TageslaufError(
            f"Protokoll und Stand passen nicht zusammen: die letzte gruene Zeile "
            f"({letzte.get('heute')}) nennt Zahlen, die nicht aus dem Stand folgen: "
            f"{abweichend} — die Zeile wurde veraendert oder gehoert zu einem anderen Stand")


def gefuehrter_tag(ablage: Ablage, zeichner: Optional[Zeichner] = None) -> Optional[_dt.date]:
    """Der letzte gruen gefuehrte Tag — aus dem Manifest des Stands.

    Das Manifest ist die Aussage des Stands ueber sich selbst (Horizont);
    das Protokoll muss dieselbe Aussage machen, sonst passen Stand und
    Nachweis nicht zusammen, und der Lauf bricht ab statt einen der
    beiden zu glauben. Dazu der Nachweisvertrag (:func:`pruefe_nachweis`).
    """
    if not ablage.stand.is_dir():
        # Kein Stand ist nur dann "noch nie gefuehrt", wenn auch das
        # Protokoll keinen uebernommenen Lauf kennt. Sonst ist es derselbe
        # Widerspruch wie ein Stand ohne Protokollzeile — der Lauf fing
        # still von vorn an und zerstoerte die Protokollkette (Angriffsrunde
        # Betrieb). Abbrechen und den Ausweg nennen.
        gruene_ohne_stand = [
            z for z in _protokoll(ablage, zeichner) if z.get("uebernommen")]
        if gruene_ohne_stand:
            letzter = gruene_ohne_stand[-1]
            raise TageslaufError(
                f"{ablage.stand} fehlt (oder ist kein Verzeichnis), das Protokoll "
                f"kennt aber einen gefuehrten Tag ({letzter.get('heute')}, Stand "
                f"{letzter.get('stand')!r}) — Stand und Nachweis passen nicht "
                "zusammen. Ausweg: den Symlink 'stand' auf die im Protokoll "
                "genannte Generation setzen; ein Neuanfang waere ein neuer "
                "Betrieb (betrieb.neuaufsetzen)")
        return None
    try:
        manifest = lies_manifest(ablage.stand)
        # Seit es zwei Manifest-Erzeuger gibt, ist "wohlgeformt" nicht
        # mehr "passend": Der Stand einer Fuehrung ist ein
        # Fortschreibungslauf. Ein Migrationszugang traegt nur die
        # uebernommenen Vertraege — wer ihn als Stand fuehrte, verlore
        # das eigene Geschaeft still.
        pruefe_erzeuger(manifest, ERZEUGER)
    except ManifestError as exc:
        raise TageslaufError(
            f"{ablage.stand}: {exc} — ein Stand ohne gueltiges Manifest ist "
            "kein gefuehrter Stand; Verzeichnis pruefen oder entfernen und "
            "die Erstbefuellung wiederholen"
        ) from exc
    tag = _dt.date.fromisoformat(str(manifest["horizont"]))
    gruene = [z for z in _protokoll(ablage, zeichner) if z.get("uebernommen")]
    if not gruene:
        raise TageslaufError(
            f"{ablage.stand} fuehrt {tag.isoformat()}, aber das Protokoll "
            f"{ablage.protokoll_pfad} kennt keinen uebernommenen Lauf — Stand "
            "und Nachweis passen nicht zusammen"
        )
    letzte = _dt.date.fromisoformat(str(gruene[-1]["heute"]))
    if letzte != tag:
        raise TageslaufError(
            f"Stand fuehrt {tag.isoformat()}, das Protokoll {letzte.isoformat()} "
            "— Stand und Nachweis passen nicht zusammen"
        )
    pruefe_nachweis(ablage, gruene)
    return tag


def monatserste_in(von_exklusiv: _dt.date, bis_inklusiv: _dt.date) -> List[_dt.date]:
    """Alle Monatsersten in ``(von, bis]`` — die Abschluss-Stichtage eines Laufs."""
    tage: List[_dt.date] = []
    jahr, monat = von_exklusiv.year, von_exklusiv.month
    while True:
        monat += 1
        if monat == 13:
            jahr, monat = jahr + 1, 1
        kandidat = _dt.date(jahr, monat, 1)
        if kandidat > bis_inklusiv:
            break
        if kandidat > von_exklusiv:
            tage.append(kandidat)
    return tage


# --------------------------------------------------------------------------- #
# Der Lauf
# --------------------------------------------------------------------------- #


def _festgeschriebene_abschluesse(ablage: Ablage) -> List[_dt.date]:
    """Die Stichtage der bereits festgeschriebenen Monatsabschluesse."""
    if not ablage.abschluesse.is_dir():
        return []
    tage: List[_dt.date] = []
    for pfad in ablage.abschluesse.glob("abschluss_*.parquet"):
        try:
            tage.append(_dt.date.fromisoformat(pfad.stem[len("abschluss_"):]))
        except ValueError:
            continue
    return sorted(tage)


def bezeugte_eingaenge(
    zeilen: List[Dict[str, Any]], *, aufschalten: bool = False,
) -> Dict[str, str]:
    """Fall -> Hash der eingang.json, wie ihn die gruenen Zeilen bezeugen.

    Jede gruene Zeile, die einen Eingang fuehrt, nennt denselben Hash — ein
    Eingang aendert sich nach dem Eintritt nie. Zwei verschiedene Hashes
    fuer denselben Fall sind ein Befund, kein Wahlrecht.

    Zeuge ist nur, was gebunden ist (Nachbesserung Runde C): eine
    GEZEICHNETE Zeile (Schema 3) oder eine Zeile des GEPINNTEN Vorlaufs —
    die ungezeichneten Zeilen vor der ersten gezeichneten, deren Zahl und
    Hash diese festhaelt. Ein Protokoll ohne gezeichnete Zeile bezeugt
    nichts; ausser im Lauf, der es mit ``aufschalten`` ausdruecklich
    uebernimmt — dessen erste Zeile pinnt genau diesen Vorlauf.
    """
    gebunden = aufschalten or any(z.get("schema_version", 1) >= 3 for z in zeilen)
    bezeugt: Dict[str, str] = {}
    for zeile in zeilen:
        if not zeile.get("uebernommen"):
            continue
        if zeile.get("schema_version", 1) < 3 and not gebunden:
            continue
        for u in zeile.get("uebernahmen") or []:
            if not u.get("eingang_sha256"):
                continue
            fall, soll = str(u.get("fall")), str(u["eingang_sha256"])
            if bezeugt.setdefault(fall, soll) != soll:
                raise TageslaufError(
                    f"Protokoll: der Eingang {fall!r} wird mit zwei verschiedenen "
                    "Hashes bezeugt — ein Eingang aendert sich nach dem Eintritt nie")
    return bezeugt


def _pruefe_bezeugte_eingaenge(
    ablage: Ablage, zeilen: List[Dict[str, Any]], *, aufschalten: bool = False,
) -> None:
    """JEDER Eingang, den irgendeine gruene Zeile bezeugt, liegt unveraendert da.

    Angriffsrunde nach T27 und Runde C (RC14, RC15): Gegen die bezeugten
    Hashes wurden nur die VORHANDENEN Eingaenge gehalten, und das
    Verschwinden nur fuer die Eingaenge der letzten Zeile — wer die letzte
    Zeile leerte, liess einen alten Eingang verschwinden; wer die
    Eintrittszeile nachzog, schrieb einen Eingang stimmig um
    (Versicherungssummen mal zehn). Jetzt gilt fuer jeden jemals bezeugten
    Eingang: Verzeichnis da, eingang.json byte-gleich zum bezeugten Hash,
    und jede Tabelle traegt den Hash, den eingang.json nennt.
    """
    for fall, soll in sorted(bezeugte_eingaenge(zeilen, aufschalten=aufschalten).items()):
        verzeichnis = ablage.uebernahme / fall
        ausweg = ("ein Eingang ist unantastbar; den urspruenglichen Eingang aus der "
                  "Sicherung wiederherstellen — eine neue Lieferung ist ein neuer Eingang")
        if not verzeichnis.is_dir():
            raise TageslaufError(
                f"Eingang {fall!r}: gefuehrt und im Protokoll bezeugt, aber nicht mehr "
                f"in der Ablage (entfernt oder umbenannt) — {ausweg}")
        pfad = verzeichnis / "eingang.json"
        try:
            roh = pfad.read_bytes()
        except OSError as exc:
            raise TageslaufError(f"Eingang {fall!r}: {pfad} nicht lesbar ({exc}) — {ausweg}") from exc
        if sha256_bytes(roh) != soll:
            raise TageslaufError(
                f"Eingang {fall!r}: eingang.json ist nicht mehr die, mit der er in die "
                f"Fuehrung trat ({sha256_bytes(roh)[:16]}… statt {soll[:16]}…) — {ausweg}")
        try:
            dateien = json.loads(roh.decode("utf-8")).get("dateien") or {}
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError) as exc:
            raise TageslaufError(f"Eingang {fall!r}: eingang.json nicht lesbar ({exc})") from exc
        for datei, summe in sorted(dateien.items()):
            tabelle = verzeichnis / str(datei)
            if not tabelle.is_file() or sha256_bytes(tabelle.read_bytes()) != summe:
                raise TageslaufError(
                    f"Eingang {fall!r}: {datei} fehlt oder traegt nicht den Hash, den "
                    f"eingang.json nennt — {ausweg}")


def _bereits_gefuehrte_eingaenge(zeilen: List[Dict[str, Any]]) -> set:
    """Die Faelle, die der letzte gruene Lauf schon gefuehrt hat."""
    gruene = [z for z in zeilen if z.get("uebernommen")]
    if not gruene:
        return set()
    return {str(u.get("fall")) for u in gruene[-1].get("uebernahmen", [])}


def _abschluss_kennt_eingang(ablage: Ablage, stichtag: _dt.date, police_ids) -> bool:
    """Ob der festgeschriebene Abschluss diesen Eingang bereits traegt.

    Die Frage "ist dieser Eingang schon eingerechnet" wurde bisher an das
    PROTOKOLL gestellt: Welche Faelle hat der letzte gruene Lauf gefuehrt?
    Das ist ein Stellvertreter, und er faellt aus, sobald ein Lauf den
    Abschluss schreibt und danach scheitert — der Abschluss kennt den
    Bestand, die Protokollzeile sagt "nicht uebernommen", und der Retry
    haelt den Eingang fuer neu. Genau so blieb ein Betrieb dauerhaft
    stehen (Befund T26-02, Szenario 4): "Abschluss kennt den Bestand
    nicht", obwohl er ihn kannte.

    Gefragt wird deshalb die Tabelle selbst. Ein Abschluss, der die
    Zielnummern des Eingangs traegt, hat ihn eingerechnet — das ist keine
    Ableitung ueber einen Stellvertreter, sondern die Sache.

    Benannte Grenze: Ein Eingang, dessen Vertraege am Stichtag des
    Abschlusses ALLE schon beendet waeren, hinterliesse keine Zeile und
    zaehlte hier als unbekannt. Fuer einen Zugang zum eigenen Stichtag
    kann das nicht eintreten — er tritt an diesem Tag in die Buecher ein.
    """
    pfad = abschluss_pfad(ablage.abschluesse, stichtag)
    if not pfad.is_file():
        return False
    tabelle = read_portfolio(pfad)
    return bool(set(int(p) for p in tabelle["police_id"]) & {int(p) for p in police_ids})


def _erster_abschluss_ab(ablage: Ablage, stichtag: _dt.date) -> Optional[_dt.date]:
    """Der erste festgeschriebene Abschluss am oder nach ``stichtag`` — der
    Abschluss, in dem ein Zugang zu diesem Stichtag in die Buecher trat."""
    return next((t for t in _festgeschriebene_abschluesse(ablage) if t >= stichtag), None)


def _eingang_eingerechnet(ablage: Ablage, stichtag: _dt.date, police_ids) -> Optional[bool]:
    """Ob ein Eingang mit diesem Stichtag schon eingerechnet ist — gefragt
    am RICHTIGEN Zeitpunkt.

    Die Frage geht an den Abschluss, in dem der Zugang in die Buecher trat:
    den ersten festgeschriebenen am oder nach seinem Stichtag. Traegt der
    seine Zielnummern, ist er eingerechnet — auch wenn jeder spaetere
    Abschluss sie nicht mehr traegt, weil die Vertraege inzwischen
    abgelaufen sind. Genau daran scheiterte der Wiederanlauf eines
    Nachhollaufs ueber Vertragsablaeufe hinweg (Pruefrunde T27, Befund 02):
    Die Frage wurde dem JUENGSTEN Abschluss gestellt, Monate spaeter, und
    der kannte die abgelaufenen Vertraege nicht mehr — "kennt den Bestand
    nicht", dauerhaft.

    Rueckgabe: ``None`` — es gibt noch keinen Abschluss ab dem Stichtag
    (offen, kein Widerspruch); ``True`` — eingerechnet; ``False`` — der
    Abschluss seines Stichtags kennt ihn nicht (ADR-011: der wird nie neu
    gerechnet, der Zugang gehoert in die offene Zeit).
    """
    erster = _erster_abschluss_ab(ablage, stichtag)
    if erster is None:
        return None
    return _abschluss_kennt_eingang(ablage, erster, police_ids)


def _stand_bauen(
    config: BestandConfig, config_pfad: Path, ablage: Ablage, heute: _dt.date,
    zeichner: Zeichner, *, aufschalten: bool = False,
) -> Tuple[Path, Dict[str, Any]]:
    """Den Stand fuer ``heute`` im Arbeitsverzeichnis erzeugen (noch nicht uebernommen)."""
    betriebsbeginn = config.tagesbetrieb.betriebsbeginn
    assert betriebsbeginn is not None
    # Kein gezogener Anfangsbestand mehr (ADR-020): Der Stand beginnt leer,
    # das eigene Geschaeft entsteht Werktag fuer Werktag ab dem
    # Betriebsbeginn — jeder Vertrag mit seinem Zugang im Journal.
    basis = leerer_stamm()
    ausgaben: List[Path] = []
    eingaben: Dict[str, Path] = {}
    if ablage.arbeit.exists():
        _entferne_ablageverzeichnis(ablage, ablage.arbeit)
    ablage.arbeit.mkdir(parents=True)
    ausgaben.append(write_portfolio(basis, ablage.arbeit / "bestand.parquet"))

    zeilen = _protokoll(ablage, zeichner)
    _pruefe_bezeugte_eingaenge(ablage, zeilen, aufschalten=aufschalten)
    uebernahmen = lies_uebernahmen(
        ablage.uebernahme, config, schluesselring=zeichner.ring,
        ordnung=zeichner.ordnung,
        bezeugt=set(bezeugte_eingaenge(zeilen, aufschalten=aufschalten).values()))
    # Ein vorausdatierter Eingang RUHT bis zu seinem Stichtag (Angriffsrunde
    # nach T27): Gebucht wird, was geschehen ist. Vorher brach jeder Lauf
    # davor rot ab, und der ganze Betrieb stand bis zum Stichtag still —
    # ohne Buchung und ohne fristgerechten Monatsabschluss.
    wartend = [u for u in uebernahmen if u.stichtag > heute]
    uebernahmen = [u for u in uebernahmen if u.stichtag <= heute]
    merkmale = None
    verankerung: Optional[pd.DataFrame] = None
    scheiben_ueb: Optional[pd.DataFrame] = None
    schichten: Optional[pd.DataFrame] = None
    historie_voran: List[pd.DataFrame] = []
    ledger_voran: List[pd.DataFrame] = []
    # Ein NEUER Eingang darf nicht hinter einen festgeschriebenen Abschluss
    # zurueckreichen (ADR-011: genau einmal, nie ueberschrieben). Sonst
    # traegt die Gegenwart den uebernommenen Bestand und die eingefrorene
    # Vergangenheit nicht — ein Bilanzwert, der sich rueckwirkend bewegt
    # haette, wenn er duerfte. Schon gefuehrte Eingaenge sind davon nicht
    # betroffen: Ihre Abschluesse kennen sie.
    #
    # "Schon gefuehrt" wird an ZWEI Quellen gefragt (T26-02, Szenario 4):
    # am Protokoll, das den letzten gruenen Lauf nennt, und am Abschluss
    # selbst. Die zweite ist die belastbare — ein Lauf, der den Abschluss
    # schreibt und danach scheitert, hinterlaesst keine gruene Zeile, und
    # der Stellvertreter "Protokoll" hielt den Eingang dann fuer neu.
    schon_gefuehrt = _bereits_gefuehrte_eingaenge(zeilen)
    for ueb in uebernahmen:
        # Ein Zugang gehoert in die GEFUEHRTE ZEIT: nicht vor den ersten Tag,
        # den das Unternehmen fuehrt (davor gibt es keine Buecher, in die er
        # eintreten koennte), und nicht in die Zukunft (gebucht wird, was
        # geschehen ist). Dazwischen ist er frei — auch mitten im Betrieb.
        # Vorher stand hier "hoechstens am Betriebsbeginn". Das war eine
        # Regel der Ablauforganisation, keine des Modells: Die Engine
        # simuliert einen uebernommenen Vertrag ohnehin erst ab seinem
        # Bestandszugang (ereignisse._zugangslage), weil alles davor beim
        # abgebenden Unternehmen geschah — ein Zugang mitten im Betrieb
        # rechnet damit richtig, er war nur verboten.
        if ueb.stichtag < betriebsbeginn:
            raise TageslaufError(
                f"uebernahme {ueb.fall}: Stichtag {ueb.stichtag.isoformat()} "
                f"liegt vor dem Betriebsbeginn {betriebsbeginn.isoformat()} — "
                "davor gibt es keine Buecher, in die der Bestand eintreten koennte"
            )
        if (
            ueb.fall not in schon_gefuehrt
            and _eingang_eingerechnet(
                ablage, ueb.stichtag, ueb.bestand["police_id"]) is False
        ):
            erster = _erster_abschluss_ab(ablage, ueb.stichtag)
            raise TageslaufError(
                f"uebernahme {ueb.fall}: Stichtag {ueb.stichtag.isoformat()} "
                f"liegt nicht nach dem festgeschriebenen Monatsabschluss "
                f"{erster.isoformat()}, in dem er in die Buecher getreten "
                "waere — dieser "
                "Abschluss kennt den Bestand nicht und wird nie neu gerechnet "
                "(ADR-011). Der Zugang gehoert in die noch offene Zeit; soll "
                "er weiter zurueckreichen, wird die Ablage aus dem Fall neu "
                "aufgesetzt (betrieb.neuaufsetzen)"
            )
        basis = _zusammen(basis, ueb.bestand)
        historie_voran.append(ueb.historie)
        ledger_voran.append(ueb.ledger)
        if ueb.merkmale is not None and len(ueb.merkmale):
            merkmale = (
                ueb.merkmale if merkmale is None
                else pd.concat([merkmale, ueb.merkmale], ignore_index=True)
            )
        # Verankerung, Bausteine und Korrekturschicht (Freischaltung,
        # Schritte 3-5, im Tagesbetrieb seit Schritt 9): Die Fuehrung liest
        # den Anfangszustand der Abnahmen — Alt-Erhoehungen als Scheiben,
        # die Korrekturschicht in Storno und Bewertung, die Verankerung als
        # Grundlage der Schicht. Vorher (Review T22-11, Stufe 1) wurde die
        # Verankerung nur registriert und als NICHT angewandt ausgewiesen.
        if ueb.verankerung is not None and len(ueb.verankerung):
            verankerung = (
                ueb.verankerung if verankerung is None
                else pd.concat([verankerung, ueb.verankerung], ignore_index=True)
            )
        if ueb.scheiben is not None and len(ueb.scheiben):
            scheiben_ueb = (
                ueb.scheiben if scheiben_ueb is None
                else pd.concat([scheiben_ueb, ueb.scheiben], ignore_index=True)
            )
        if ueb.schichten is not None and len(ueb.schichten):
            schichten = (
                ueb.schichten if schichten is None
                else pd.concat([schichten, ueb.schichten], ignore_index=True)
            )
        eingaben[f"uebernahme:{ueb.fall}"] = ueb.manifest_pfad

    zugaenge = neugeschaeft_zwischen(config, betriebsbeginn, heute)
    ergebnis = fortschreiben(
        basis, config, heute, zugaenge=zugaenge, merkmale=merkmale,
        scheiben=scheiben_ueb, schichten=schichten, verankerung=verankerung,
    )
    historie, ledger = ergebnis.historie, ergebnis.ledger
    scheiben_fort = ergebnis.scheiben
    if historie_voran:
        historie = _voran(pd.concat(historie_voran, ignore_index=True), historie,
                          ["police_id", "status_id"])
        ledger = _voran(pd.concat(ledger_voran, ignore_index=True), ledger,
                        ["police_id", "status_date"])
    if scheiben_ueb is not None and len(scheiben_ueb):
        scheiben_fort = _voran(scheiben_ueb, scheiben_fort, ["police_id", "scheiben_id"])
    # Tag = Sicht (Review T22-04): Der Stand von heute ist, was heute gebucht
    # ist. Buchungen mit Buchungstag nach heute (Meldeverzug, Werktagsregel)
    # bleiben mit ihren Zustandszeilen und Scheiben draussen und kommen an
    # ihrem Buchungstag — Seite, Stand und Journal sagen dasselbe.
    historie, ledger, scheiben = gebuchte_sicht(
        config, historie, ledger, scheiben_fort, heute, ab_tag=betriebsbeginn)
    gesamt = fuehre_fort(mit_zugaengen(basis, ergebnis.zugaenge), historie)

    ausgaben.append(write_portfolio(historie, ablage.arbeit / "historie.parquet"))
    ausgaben.append(write_portfolio(ledger, ablage.arbeit / "ledger.parquet"))
    ausgaben.append(write_portfolio(scheiben, ablage.arbeit / "scheiben.parquet"))
    ausgaben.append(write_portfolio(ergebnis.zugaenge, ablage.arbeit / "zugaenge.parquet"))
    ausgaben.append(write_portfolio(gesamt, ablage.arbeit / "bestand_gesamt.parquet"))
    if merkmale is not None:
        ausgaben.append(write_portfolio(
            merkmale[list(MERKMALE_NAMES)].reset_index(drop=True),
            ablage.arbeit / "merkmale.parquet"))
    if verankerung is not None:
        ausgaben.append(write_portfolio(
            verankerung.reset_index(drop=True), ablage.arbeit / "verankerung.parquet"))
    if schichten is not None:
        ausgaben.append(write_portfolio(
            schichten.reset_index(drop=True), ablage.arbeit / "schichten.parquet"))
    reduktionen = _gebuchte_reduktionen(ergebnis.reduktionen, ledger)
    if reduktionen is not None and len(reduktionen):
        ausgaben.append(write_portfolio(
            reduktionen, ablage.arbeit / "reduktionen.parquet"))
    schreibe_manifest(
        ablage.arbeit, horizont=heute, neuzugang_ab=None, config_pfad=config_pfad,
        ausgaben=ausgaben, eingaben=eingaben,
    )
    zahlen = {
        "basisvertraege": int(len(basis)),
        "uebernommene_vertraege": int(sum(len(u.bestand) for u in uebernahmen)),
        "neugeschaeft_seit_betriebsbeginn": int(len(zugaenge)),
        # GeVo heisst Geschaeftsvorfall, und die Zahl steht zwischen lauter
        # Stueckzahlen — also werden Vorfaelle gezaehlt, nicht Buchungszeilen.
        # Ueber len(ledger) gemeldet, ueberzeichnete sie den Lauf um jede
        # zweite Zugangs- und Erhoehungszeile (auf dem Messstand um 85 %).
        # Was Zeilen meint, heisst im Protokoll gebucht und zeilen_gesamt.
        "gevos": int(ledger[["police_id", "ereignis", "status_date"]]
                     .drop_duplicates().shape[0]),
        "erhoehungsscheiben": int(len(scheiben)),
        # Stufe 1 von T22-11: ausgewiesen; seit Schritt 9 angewandt, wenn die
        # Korrekturschicht vorliegt. Die Formulierung teilt sich der Lauf mit
        # dem Nachweis, der sie aus dem Stand nachrechnet (RC13).
        "verankerung": verankerung_angabe(
            int(len(verankerung)) if verankerung is not None else None,
            schichten is not None),
        # Fall-Bezug jeder Uebernahme (Konzept, Abschnitt 6): Der Zugang
        # ist als datierter Eingang nachweisbar, nicht als anonyme Zeile.
        "wartende_uebernahmen": [
            {"fall": u.fall, "stichtag": u.stichtag.isoformat()} for u in wartend],
        "uebernahmen": [
            {"fall": u.fall, "stichtag": u.stichtag.isoformat(),
             "vertraege": int(len(u.bestand)), "snapshot_sha256": u.snapshot_sha256,
             "zeichnung": dict(u.zeichnung), "eingang_sha256": u.eingang_sha256}
            for u in uebernahmen
        ],
        "_uebernommene_policen": sorted(
            int(p) for u in uebernahmen for p in u.bestand["police_id"]),
        "_teilbestaende": {
            u.fall: sorted(int(p) for p in u.bestand["police_id"]) for u in uebernahmen
        },
    }
    return ablage.arbeit, zahlen


def _zusammen(eigen: pd.DataFrame, uebernommen: pd.DataFrame) -> pd.DataFrame:
    beide = pd.concat([eigen, uebernommen], ignore_index=True)
    doppelt = beide["police_id"][beide["police_id"].duplicated()]
    if len(doppelt):
        raise TageslaufError(
            f"police_id-Kollision zwischen eigenem und uebernommenem Bestand: "
            f"{sorted(set(doppelt))[:5]} — die Nummernkreise muessen getrennt sein"
        )
    return beide.sort_values("police_id", kind="stable").reset_index(drop=True)[list(STAMM_NAMES)]


def _voran(vorne: pd.DataFrame, hinten: pd.DataFrame, sortierung: List[str]) -> pd.DataFrame:
    beide = pd.concat([vorne, hinten], ignore_index=True)
    return beide.sort_values(sortierung, kind="stable").reset_index(drop=True)


def _wache(arbeit: Path, config_pfad: Path, heute: _dt.date) -> Tuple[Dict[str, Any], Dict[str, Any], List[dict]]:
    """P-B1-Engine ueber die geschriebenen Bytes des neuen Stands.

    Die Rollen kommen aus der Tabelle des Erzeugers (``lauf_eingaben``),
    nicht aus einer abgetippten Liste: Die Wache las Bausteine und
    Korrekturschicht des uebernommenen Bestands nicht zurueck, obwohl
    ``_stand_bauen`` beide schreibt und in die Fortschreibung reicht — die
    Herleitung rechnete den Storno ohne Schicht und meldete das korrekt
    gebuchte Ledger als falsch (Betriebsbefund N-01, 2026-09-08: zwei
    Rueckkaeufe im zehnten Jahr, je ein Cent).
    """
    eingaben = lauf_eingaben(arbeit, config_pfad)
    manifest = lies_manifest(arbeit)
    pruefe_erzeuger(manifest, ERZEUGER)
    tabellen, geprueft, fehler, usage = lies_und_pruefe_pb1(eingaben, bis=heute, manifest=manifest)
    return tabellen, geprueft, usage + fehler


def _entferne_ablageverzeichnis(ablage: Ablage, pfad: Path) -> None:
    """Ein Verzeichnis der Ablage entfernen — und NUR eines der Ablage.

    Review T24-07, als Klasse: ``shutil.rmtree`` loescht, was am Pfad LIEGT,
    nicht was der Name verspricht. ``stand`` ist ein Symlink; zeigt er —
    von Hand umgesetzt — auf ein Backup ausserhalb der Wurzel, haette der
    Tausch das Backup geloescht. Erlaubt ist nur ein echtes Verzeichnis
    UNMITTELBAR in der Wurzel, dessen Name ein Stand- (``stand-<kennung>``)
    oder das Arbeitsverzeichnis ist. Alles andere bleibt stehen und ist
    ein benannter Fehler.
    """
    fehler = _ablageverzeichnis_fehler(ablage, pfad)
    if fehler:
        raise TageslaufError(fehler)
    try:
        entferne_verzeichnis(
            Path(pfad), innerhalb=ablage.wurzel,
            name_ok=lambda n: n == ARBEIT_DIR or n.startswith(f"{STAND_DIR}-"),
            grund="Stand- oder Arbeitsverzeichnis der Ablage",
        )
    except LoeschFehler as exc:
        raise TageslaufError(str(exc)) from exc


def _ablageverzeichnis_fehler(ablage: Ablage, pfad: Path) -> Optional[str]:
    """Darf ``pfad`` als Verzeichnis der Ablage entfernt werden? Leer = ja.
    Getrennt von der Loeschung, damit ``_uebernehmen`` VOR dem atomaren
    Tausch weiss, ob es den alten Stand danach entfernen darf."""
    ziel = Path(pfad)
    wurzel = ablage.wurzel.resolve()
    aufgeloest = ziel.resolve()
    if ziel.is_symlink() or aufgeloest.parent != wurzel or not (
        aufgeloest.name == ARBEIT_DIR or aufgeloest.name.startswith(f"{STAND_DIR}-")
    ):
        return (
            f"verweigert: {ziel} ist kein Stand- oder Arbeitsverzeichnis unmittelbar "
            f"in der Ablage {ablage.wurzel} — nicht geloescht (Review T24-07). Ausweg: "
            f"den Symlink {ablage.stand} von Hand auf das richtige stand-<kennung>-"
            "Verzeichnis in der Ablage setzen bzw. das fremde Verzeichnis selbst "
            "entfernen, dann den Lauf erneut starten"
        )
    return None


def _uebernehmen(ablage: Ablage, kennung: str) -> None:
    """Das Arbeitsverzeichnis atomar zum gefuehrten Stand machen.

    Review T22-03: Zwei Renames (stand -> stand.alt, stand.neu -> stand)
    hatten dazwischen einen Moment OHNE Stand — ein Absturz dort liess die
    Laufzeit ohne gefuehrten Tag zurueck, und die Zusage "der gestrige
    bleibt" war falsch. Jetzt ist ``stand`` ein Symlink auf ein
    versioniertes Verzeichnis ``stand-<manifest-kennung>``; der Tausch ist
    EIN ``os.replace`` des Symlinks und damit atomar: Vorher zeigt er auf
    den alten Stand, nachher auf den neuen, nie auf nichts. Das alte
    Verzeichnis wird erst danach entfernt.

    Ein Stand aus der Erstfassung (echtes Verzeichnis) wird einmalig in die
    Symlink-Form ueberfuehrt; nur dieser eine Uebergang hat noch das alte
    Fenster.
    """
    ziel = ablage.wurzel / f"{STAND_DIR}-{kennung}"
    # Review T24-07 (adversarialer Review): Ob der ALTE Stand nach dem Tausch
    # entfernt werden darf, wird VOR dem ersten irreversiblen Schritt
    # entschieden. Faellt die Pruefung erst nach dem Tausch, zeigt ``stand``
    # schon auf den neuen Tag, das Protokoll bucht "nicht uebernommen", und
    # Stand und Nachweis passen dauerhaft nicht mehr zusammen.
    if ablage.stand.is_symlink():
        bisher = ablage.stand.resolve()
        if bisher.exists() and bisher != ziel.resolve():
            fehler = _ablageverzeichnis_fehler(ablage, bisher)
            if fehler:
                raise TageslaufError(f"Standwechsel nicht begonnen — alter Stand: {fehler}")
    if ziel.exists():
        _entferne_ablageverzeichnis(ablage, ziel)
    os.rename(ablage.arbeit, ziel)
    alt_ziel: Optional[Path] = None
    if ablage.stand.is_symlink():
        alt_ziel = ablage.stand.resolve()
    elif ablage.stand.exists():
        alt_ziel = ablage.wurzel / f"{STAND_DIR}-erstfassung"
        if alt_ziel.exists():
            _entferne_ablageverzeichnis(ablage, alt_ziel)
        os.rename(ablage.stand, alt_ziel)
    tmp = ablage.wurzel / STAND_LINK_TMP
    if tmp.is_symlink() or tmp.exists():
        tmp.unlink()
    os.symlink(ziel.name, tmp)
    os.replace(tmp, ablage.stand)
    # Der alte Stand bleibt LIEGEN, bis der Publish vollstaendig ist
    # (Review T24-01, Schritt b). Vorher wurde er hier sofort entfernt —
    # und damit war der Standwechsel unumkehrbar: Ein Absturz zwischen
    # Tausch und Protokollzeile hinterliess einen Stand, auf den kein
    # Nachweis zeigt, und nichts, worauf man zurueckzeigen koennte.
    #
    # Aufgeraeumt wird er vom naechsten Lauf (_verwaiste_staende_entfernen),
    # sobald der Symlink steht und die Praemisse wieder klar ist. Das ist
    # dieselbe Regel wie dort: aufgeraeumt wird nur, wo man weiss, was man
    # wegraeumt.
    _ = alt_ziel


def _verwaiste_staende_entfernen(ablage: Ablage) -> None:
    """Versionierte Standverzeichnisse, auf die der Symlink nicht zeigt
    (Reste eines abgebrochenen Tauschs), aufraeumen — vor dem Lauf.

    Die Praemisse dieser Aufraeumung ist, dass ``stand`` ein SYMLINK auf
    ein Standverzeichnis unmittelbar in der Wurzel ist. Nur dann steht
    fest, welche Generation gefuehrt wird und welche Waisen sind.

    Gilt die Praemisse nicht, waere JEDES ``stand-*`` in der Wurzel eine
    "Waise", und die Aufraeumung loeschte den einzigen Stand der Ablage.
    Zwei Auspraegungen davon sind belegt: der von Hand nach aussen
    gesetzte oder haengende Symlink (Nachmessung T24-07) und der
    Legacy-Zustand, in dem ``stand`` ein echtes Verzeichnis ist — dort
    verschwand ``stand-erstfassung`` (Befund T26-02).

    Deshalb fragt der Code nach der Praemisse und nicht nach den
    bekannten Ausnahmen. Ein haengender Symlink ist ein Abbruch mit
    Ausweg; jeder andere unklare Zustand raeumt NICHTS auf und sagt es.
    """
    aktuell: Optional[Path] = None
    if ablage.stand.is_symlink():
        if not ablage.stand.exists():
            raise TageslaufError(
                f"verweigert: {ablage.stand} zeigt auf ein nicht vorhandenes "
                f"Verzeichnis ({os.readlink(ablage.stand)}) — nichts aufgeraeumt. "
                f"Ausweg: den Symlink von Hand auf ein vorhandenes "
                f"{STAND_DIR}-<kennung>-Verzeichnis in der Ablage setzen, dann den "
                "Lauf erneut starten"
            )
        aktuell = ablage.stand.resolve()
        fehler = _ablageverzeichnis_fehler(ablage, aktuell)
        if fehler:
            raise TageslaufError(f"Aufraeumen nicht begonnen — gefuehrter Stand: {fehler}")
    kandidaten = [k for k in ablage.wurzel.glob(f"{STAND_DIR}-*") if k.is_dir()]
    if aktuell is None and kandidaten:
        # Die Praemisse dieser Aufraeumung ist ein SYMLINK ``stand`` auf
        # eine Generation in der Wurzel. Gilt sie nicht, sagt hier nichts,
        # welcher Kandidat gefuehrt war — dann wird NICHTS entfernt.
        #
        # Drei Zustaende fallen darunter, und zwei davon haben bereits
        # Daten gekostet:
        # * ``stand`` fehlt — unter anderem der Zustand nach einem Absturz
        #   zwischen den zwei Umbenennungen des Erstuebergangs. Vorher
        #   hielt die Aufraeumung jeden Kandidaten fuer eine Waise und
        #   raeumte den alten Stand UND die fertig geschriebene neue
        #   Generation ab (Review T24-01, Reproduktion 3).
        # * ``stand`` ist ein echtes Verzeichnis — der unterstuetzte
        #   Legacy-Zustand vor dem Erstuebergang. Hier fiel der Code bis
        #   zur Schleife durch, und weil ``aktuell`` None blieb, galt
        #   JEDER Kandidat als Waise: geloescht wurde unter anderem
        #   ``stand-erstfassung``, der letzte belegte alte Stand (Befund
        #   T26-02, Szenario 2).
        # * ``stand`` ist etwas anderes, etwa eine Datei — nie beobachtet,
        #   aber von derselben Bauart.
        #
        # Gefragt wird deshalb nach der PRAEMISSE und nicht nach den
        # bekannten Ausnahmen: Eine Aufzaehlung haette den dritten Fall
        # wieder durchgelassen, so wie die Aufzaehlung nach T24-07 den
        # zweiten durchliess. Dieselbe Klasse wie T26-01 — wer aus der
        # Form eines Pfades auf seinen Lebenszyklus schliesst, loescht
        # frueher oder spaeter etwas Gueltiges.
        #
        # Abbrechen waere zu scharf: Eine Ablage ohne ``stand`` ist ein
        # legitimer Ausgangspunkt (Neuaufbau aus dem Eingang), und der
        # Legacy-Zustand ist ausdruecklich unterstuetzt. Der Lauf baut
        # einen neuen Stand, setzt den Symlink, und der NAECHSTE Lauf
        # raeumt auf — dann ist die Praemisse wieder klar.
        zustand = (
            "fehlt" if not ablage.stand.exists()
            else "ein echtes Verzeichnis (Legacy-Zustand vor dem Erstuebergang)"
            if ablage.stand.is_dir()
            else "weder Symlink noch Verzeichnis"
        )
        print(
            f"tageslauf: {ablage.stand} ist kein Symlink auf eine Generation "
            f"({zustand}), aber die Ablage traegt {len(kandidaten)} "
            f"versionierte(n) Stand "
            f"({', '.join(sorted(k.name for k in kandidaten)[:3])}) — nichts "
            "aufgeraeumt, weil unklar ist, welcher gefuehrt war. Der Lauf "
            "baut einen neuen Stand; der naechste raeumt die Reste ab. Wer "
            "einen der Staende weiterfuehren will, setzt den Symlink von "
            "Hand darauf (das Protokoll nennt den zuletzt uebernommenen).",
            file=sys.stderr,
        )
        return
    for kandidat in kandidaten:
        if kandidat.resolve() != aktuell:
            _entferne_ablageverzeichnis(ablage, kandidat)
    tmp = ablage.wurzel / STAND_LINK_TMP
    if tmp.is_symlink():
        tmp.unlink()


def _vollende_unterbrochenes_neuaufsetzen(wurzel: Path) -> None:
    """Fehlt die Wurzel, weil ``neuaufsetzen`` zwischen seinen zwei
    Umbenennungen endete, den Tausch vollenden — statt leer neu anzulegen.

    Angriffsrunde Betrieb: Die alte Ablage lag im Archiv, die neue unter
    ``<wurzel>.neu-<zeit>``, und der naechste Tageslauf legte eine LEERE
    Wurzel an und fuehrte von vorn. Die neue Ablage ist die Absicht, wenn
    sie fertig ist: ihre Provenienzdatei wird als Letztes geschrieben und
    nennt das Archiv, in das die alte gegangen ist. Genau dann wird sie
    eingesetzt. Ein Aufbau ohne Provenienz, oder mehr als ein fertiger,
    ist keine Absicht, die sich lesen laesst — dann wird nichts angelegt.
    """
    from rechner_pipeline.betrieb.neuaufsetzen import PROVENIENZ_DATEI

    reste = sorted(p for p in wurzel.parent.glob(f"{wurzel.name}.neu-*") if p.is_dir())
    if not reste:
        return
    fertig = []
    for rest in reste:
        try:
            prov = json.loads((rest / PROVENIENZ_DATEI).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(prov, dict) and prov.get("archiv") and Path(prov["archiv"]).is_dir():
            fertig.append(rest)
    if len(fertig) != 1:
        raise TageslaufError(
            f"{wurzel} fehlt, daneben liegt ein Aufbau von neuaufsetzen "
            f"({', '.join(r.name for r in reste)}), "
            + ("aber keiner ist fertig (ohne Provenienz oder ohne Archiv)"
               if not fertig else "und mehr als einer ist fertig")
            + " — keine leere Ablage anlegen; von Hand klaeren, welche "
            "Ablage gilt, und sie an diese Stelle setzen")
    try:
        os.rename(fertig[0], wurzel)
    except FileNotFoundError:
        # Ein anderer Prozess (neuaufsetzen selbst) hat den Tausch eben vollendet.
        if not wurzel.is_dir():
            raise


@contextlib.contextmanager
def lauf_sperre(ablage: Ablage):
    """Exklusive Prozess-Sperre der Laufzeitumgebung (nicht blockierend).

    Zwei gleichzeitige Laeufe (Timer und Hand, zwei Timer nach einer
    Haengepartie) teilten sich stand.neu, Journal und Protokoll (Review
    T22-03). Der zweite bricht jetzt sofort ab, mit Meldung.
    """
    if not ablage.wurzel.exists() and not ablage.wurzel.is_symlink():
        _vollende_unterbrochenes_neuaufsetzen(ablage.wurzel)
    ablage.wurzel.mkdir(parents=True, exist_ok=True)
    datei = open(ablage.sperre, "a+", encoding="utf-8")
    try:
        if fcntl is not None:
            try:
                fcntl.flock(datei.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (BlockingIOError, OSError) as exc:
                raise TageslaufError(
                    f"{ablage.wurzel}: ein anderer Lauf haelt die Sperre "
                    f"{ablage.sperre.name} — zwei Laeufe auf derselben Ablage "
                    "gibt es nicht; den laufenden Prozess enden lassen"
                ) from exc
        yield
    finally:
        datei.close()


def _teilbestand(tabellen: Dict[str, Any], policen: List[int]) -> Dict[str, Any]:
    """Die Tabellen eines uebernommenen Teilbestands — dieselben Zeilen, gefiltert.

    Kein zweiter Datenraum: Stamm, Journal, Ledger, Scheiben, Merkmale,
    Korrekturschicht und Verankerung des Teilbestands sind die Zeilen des
    Gesamtstands, deren Police zum Eingang gehoert — JEDE Rolle der
    Tabelle, nicht eine abgetippte Auswahl (N-01: ohne Schicht und
    Verankerung wich der Teilbestandsbericht um rund 13.700 EUR
    Deckungskapital je Vertrag vom Fallbericht ab). Der Bericht rendert sie
    mit denselben Renderern wie den Gesamtbestand (Konzept, Abschnitt 6).
    """
    auswahl = set(policen)
    teil: Dict[str, Any] = {}
    for rolle in ROLLEN_DATEIEN:
        tabelle = tabellen.get(rolle)
        teil[rolle] = (
            tabelle[tabelle["police_id"].isin(auswahl)].reset_index(drop=True)
            if tabelle is not None else None
        )
    return teil


def _gebuchte_reduktionen(reduktionen, ledger):
    """Die Herabsetzungen, deren Buchung in dieser Sicht steht.

    Kein zweiter Buchungsschnitt, sondern DERSELBE, abgeleitet: Eine
    Herabsetzung gehoert in den Stand, wenn ihre RED-Zeile darin steht.
    Ein eigener Filter auf ``reduktion_datum`` waere eine zweite Regel
    fuer dieselbe Frage — und damit die naechste Stelle, an der zwei
    Antworten auseinanderlaufen (Review T25-06).
    """
    if reduktionen is None or not len(reduktionen):
        return reduktionen
    gebucht = set(ledger.loc[ledger["ereignis"] == "RED", "police_id"])
    return reduktionen[
        reduktionen["police_id"].isin(gebucht)].reset_index(drop=True)


def _stichtagssicht(
    tabellen: Dict[str, Any], config: BestandConfig, stichtag: _dt.date,
    betriebsbeginn: _dt.date,
) -> Dict[str, Any]:
    """Die Tabellen des Laufs auf den Buchungsstand des STICHTAGS zurueckschneiden.

    Ein Monatsabschluss ist der Stand, den das Unternehmen an seinem
    Stichtag hatte — nicht der Stand, den es heute rueckblickend fuer
    diesen Stichtag ausrechnet (Review T24-02, Entscheid des Maintainers
    2026-09-14: "wir simulieren das Innere eines Unternehmens").

    Der Lauf baut seine Tabellen einmal mit der gebuchten Sicht von
    ``heute``. Die Abschluss-Schleife schrieb damit JEDEN Stichtag — der
    Wirkungsfilter sass auf dem Stichtag, der Buchungsschnitt aber auf dem
    Lauftag. Ein Todesfall mit Wirkung zum 1.1. und Buchung am 13.3. fehlte
    dadurch schon im Januar-Abschluss, obwohl das Unternehmen im Januar
    nichts von ihm wusste; ein Nachtlauf am 1.2. haette den Vertrag als in
    Kraft ausgewiesen. Beide Laeufe waren gruen und schrieben dieselbe
    0444-Datei mit verschiedenem Inhalt — ein Abschluss war damit keine
    Funktion seines Stichtags, sondern auch des Zufalls, wann gerechnet
    wurde. Damit war er auch nicht festschreibbar (ADR-011).

    Auf der Laufzeit der Vorzeige betraf das 192 der 387 Abschluesse: die
    Erstbefuellung holte 1994 bis 2026 in EINEM Lauf nach und rechnete
    jeden Monatsabschluss mit dem Wissen von 2026. Die Zahl ist nach dem
    Bau gemessen worden (Bytevergleich gegen den Lauf davor) und liegt
    weit ueber der ersten Schaetzung von 29 — die fragte, ob eine Buchung
    eine MONATSGRENZE ueberschreitet, und uebersah damit den Regelfall:
    Ereignisse wirken zum Monatsersten, gebucht wird am naechsten
    Werktag, und faellt der Erste auf ein Wochenende, liegt genau der
    Stichtag zwischen Wirkung und Buchung. Von 4625 verspaetet gebuchten
    Zeilen wirken ALLE 4625 zum Monatsersten.

    Der Schnitt darf auf den bereits nach ``heute`` gefilterten Tabellen
    aufsetzen, statt die ungefilterte Wirkungshistorie mitzufuehren:
    ``buchungstag`` ist eine reine Funktion der einzelnen Ledger-Zeile
    (Police, Ereignis, Wirkungstag, Herkunft, Generation) und damit
    unabhaengig davon, welche anderen Zeilen die Tabelle traegt. Fuer
    ``stichtag <= heute`` entfernt erst der eine, dann der andere Schnitt
    genau die Zeilen, die ein einziger Schnitt auf ``stichtag`` entfernt
    haette.

    ``portfolio`` bleibt unveraendert: die Bewertung leitet den Zustand am
    Stichtag aus dem Journal her (``journalsicht``), der Stamm steuert
    Stammdaten bei. Gemessen an zwei Stichtagen des echten Bestands ist ein
    auf den Stichtag fortgeschriebener Stamm zeilengleich; ein Test haelt
    die Annahme fest, damit sie nicht still wegbricht.
    """
    historie, ledger, scheiben = gebuchte_sicht(
        config, tabellen["historie"], tabellen["ledger"], tabellen["scheiben"],
        stichtag, ab_tag=betriebsbeginn,
    )
    sicht = dict(tabellen)
    sicht["historie"], sicht["ledger"], sicht["scheiben"] = historie, ledger, scheiben
    if "portfolio" in tabellen:
        sicht["portfolio"] = _stamm_am_stichtag(tabellen["portfolio"], historie)
    sicht["reduktionen"] = _gebuchte_reduktionen(
        tabellen.get("reduktionen"), ledger)
    return sicht


def _stamm_am_stichtag(stamm: pd.DataFrame, historie: pd.DataFrame) -> pd.DataFrame:
    """Den Zustand des Stammes auf die zurueckgeschnittene Historie setzen.

    Der Stamm des Laufs traegt den Zustand von HEUTE. Fuer einen Abschluss
    zu einem frueheren Stichtag wird die Historie auf den Buchungsstand
    dieses Stichtags geschnitten — der Stamm blieb stehen. Ist ein Vertrag
    seither abgelaufen oder gestorben und war das sein einziges Ereignis,
    ist die geschnittene Historie leer, waehrend der Stamm den terminalen
    Zustand traegt; die Bewertung verweigert diese Kombination zu Recht
    ("Folgezustand ohne Historie", ADR-011), und der Lauf endete mit Exit 4,
    dauerhaft (Pruefrunde T27, Altdefekt A27-01). Stamm und Historie
    gehoeren gemeinsam auf den Stichtag: Zustand = letzte Historienzeile bis
    zum Stichtag, sonst der Ursprung (POL am Versicherungsbeginn) — dieselbe
    Regel, nach der ``journalsicht`` den Zustand herleitet.
    """
    aus = stamm.copy()
    aus["status_id"] = pd.Series(1, index=aus.index, dtype="int64")
    aus["status_code"] = BASIS_STATUS[0]
    aus["status_date"] = aus["insurance_start"]
    if historie is not None and len(historie):
        letzte = (historie.sort_values(["police_id", "status_id"], kind="stable")
                  .drop_duplicates("police_id", keep="last").set_index("police_id"))
        treffer = aus["police_id"].isin(letzte.index)
        pids = aus.loc[treffer, "police_id"]
        aus.loc[treffer, "status_id"] = letzte.loc[pids, "status_id"].to_numpy()
        aus.loc[treffer, "status_code"] = letzte.loc[pids, "status_code"].to_numpy()
        aus.loc[treffer, "status_date"] = letzte.loc[pids, "status_date"].to_numpy()
    return aus.astype({"status_id": "int64"})


def _bericht(
    tabellen: Dict[str, Any], config: BestandConfig, stichtag: _dt.date, heute: _dt.date,
    ziel: Path, quelle_hash: str, titel: Optional[str] = None,
) -> Path:
    html = render_html(
        tabellen["portfolio"],
        titel=titel or f"Bestandsbericht PLV zum {stichtag.isoformat()}",
        quelle_hash=quelle_hash,
        historie=tabellen["historie"],
        ledger=tabellen["ledger"],
        config=config,
        scheiben=tabellen["scheiben"],
        merkmale=tabellen.get("merkmale"),
        bis=heute,
        # Betriebsbericht: Stand der Fuehrung bis zum Stichtag, keine
        # Projektion. Der Betrieb kennt die Zukunft nicht — er entdeckt sie
        # taeglich; eine Prognosekurve waere hier eine Behauptung ueber Tage,
        # die noch nicht stattgefunden haben. Der Fallbericht behaelt seine
        # Projektion (dort ist sie der Gegenstand).
        berichtsstichtag=stichtag,
        schichten=tabellen.get("schichten"),
        verankerung=tabellen.get("verankerung"),
        reduktionen=tabellen.get("reduktionen"),
    )
    ziel.parent.mkdir(parents=True, exist_ok=True)
    tmp = neue_datei(ziel.parent, ziel.name)
    try:
        tmp.write_text(html, encoding="utf-8", newline="\n")
        os.replace(tmp, ziel)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return ziel


def _anfuegen(
    pfad: Path, zeile: Dict[str, Any], zeichner: Optional[Zeichner] = None,
    *, aufschalten: bool = False,
) -> None:
    """Eine Protokollzeile anfuegen (nur-anfuegbar, sortierte Schluessel),
    verkettet mit der Zeile davor (T22-05) und GEZEICHNET (Schema 3).

    Vor JEDEM Anfuegen wird die ganze Kette mit Schluessel und Ordnung
    geprueft: An eine gebrochene oder fremd gezeichnete Kette wird nicht
    angehaengt — die eigene Zeichnung waere sonst eine Bestaetigung dessen,
    was davor steht. Traegt die Ablage einen ungezeichneten Vorlauf, pinnt
    die erste gezeichnete Zeile ihn (Aufschaltung ohne Neuaufsetzen) — aber
    nur mit ``aufschalten``: Der Schreiber prueft die Regel selbst
    (:func:`aufschaltung_fehler`), nicht nur sein Aufrufer.
    """
    pfad = Path(pfad)
    if zeichner is None:
        zeichner = betriebszeichner(Ablage(pfad.parent.parent))
    pfad.parent.mkdir(parents=True, exist_ok=True)
    text = pfad.read_text(encoding="utf-8") if pfad.is_file() else ""
    zeilen = lies_protokoll_text(
        text, str(pfad), schluesselring=zeichner.ring, ordnung=zeichner.ordnung)
    rohe = jsonl_zeilen(text)
    if rohe and not any(z.get("schema_version", 1) >= 3 for z in zeilen) and not aufschalten:
        raise TageslaufError(f"{pfad}: {aufschaltung_fehler(zeilen)}")
    zeile.pop("zeichnung", None)
    zeile.pop("vorlauf", None)
    zeile["schema_version"] = PROTOKOLL_SCHEMA_VERSION
    zeile["vorgaenger_sha256"] = _zeilen_hash(rohe[-1]) if rohe else ""
    if rohe and not any(z.get("schema_version", 1) >= 3 for z in zeilen):
        zeile["vorlauf"] = _vorlauf_pin(rohe)
        print(
            f"tageslauf: {pfad} traegt {len(rohe)} ungezeichnete Zeile(n) — die "
            "erste gezeichnete Zeile pinnt sie (Aufschaltung); ab hier ist jede "
            "Zeile mit dem Betriebsschluessel gezeichnet.",
            file=sys.stderr,
        )
    zeile["zeichnung"] = zeichner.zeichne(zeile)
    text = json.dumps(zeile, ensure_ascii=False, sort_keys=True) + "\n"
    with open(pfad, "a", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _datei_hash(pfad: Path) -> Optional[str]:
    return sha256_bytes(Path(pfad).read_bytes()) if Path(pfad).is_file() else None


def tageslauf(
    ablage: Ablage,
    heute: _dt.date,
    *,
    schluessel: Optional[Path] = None,
    zeichnungsordnung: Optional[Path] = None,
    image_digest: Optional[str] = None,
    aufschalten: bool = False,
) -> Tuple[int, Dict[str, Any]]:
    """Den Tag ``heute`` fuehren — unter der Prozess-Sperre der Ablage
    (Review T22-03); siehe :func:`_tageslauf`.

    ``schluessel``/``zeichnungsordnung``: der Betriebsschluessel, mit dem
    jede Protokollzeile gezeichnet und die Kette geprueft wird
    (:func:`betriebszeichner`: ausdruecklich > Naht > Fehler). Er wird
    VOR allem anderen geladen: Ohne ihn fasst der Lauf die Ablage nicht an.

    ``aufschalten``: der einmalige Schritt beim ersten Lauf nach dem
    Umstieg auf den Betriebsschluessel — nur damit wird ein Protokoll ohne
    gezeichnete Zeile weitergefuehrt und sein Vorlauf gepinnt
    (:func:`aufschaltung_fehler`). Geprueft wird unter der Sperre, VOR
    Ruecknahme und Aufraeumen: Ein verweigerter Lauf fasst die Ablage
    nicht an.
    """
    zeichner = betriebszeichner(ablage, schluessel, zeichnungsordnung)
    with lauf_sperre(ablage):
        # Eine angefangene Protokollzeile ist nie eine Zeile geworden —
        # sie faellt VOR allem anderen, sonst stirbt jeder Leser des
        # Protokolls an ihr (auch ohne Publish-Marker: die Zeile eines
        # roten Laufs).
        _schneide_teilzeile(ablage.protokoll_pfad)
        fehler = aufschaltung_fehler(_protokoll(ablage, zeichner), aufschalten=aufschalten)
        if fehler:
            raise TageslaufError(f"{ablage.protokoll_pfad}: {fehler}")
        # ZUERST einen unterbrochenen Publish zuruecknehmen (Review
        # T24-01, Schritt b): Danach ist die Ablage wieder in einem
        # Zustand, ueber den Nachweisvertrag und Aufraeumung urteilen
        # koennen. Vorher fiel jeder Retry ueber genau diesen
        # Zwischenzustand — und zwar dauerhaft.
        nimm_publish_zurueck(ablage, zeichner)
        _verwaiste_staende_entfernen(ablage)
        return _tageslauf(ablage, heute, zeichner, image_digest=image_digest,
                          aufschalten=aufschalten)


def _tageslauf(
    ablage: Ablage,
    heute: _dt.date,
    zeichner: Zeichner,
    *,
    image_digest: Optional[str] = None,
    aufschalten: bool = False,
) -> Tuple[int, Dict[str, Any]]:
    """Den Tag ``heute`` fuehren (Bibliotheksform des Kommandos).

    Rueckgabe ``(exit_code, protokollzeile)``. Die Protokollzeile ist in
    jedem Fall angefuegt worden, auch bei roter Wache — das Protokoll ist
    der Nachweis, dass gelaufen wurde, nicht nur, dass es gut ging.

    Ausnahme: Ist ``heute`` der bereits gefuehrte Tag, laeuft nichts —
    Rueckgabe ``(EXIT_OK, {"heute": ..., "bereits_gefuehrt": True})``, ohne
    Protokollzeile, Stand unveraendert. Der Lauf ist idempotent; eine
    Erstbefuellung am Tag des ersten Timers darf die erste Nacht nicht rot
    faerben. Rueckwaerts (``heute`` vor dem gefuehrten Tag) bleibt ein Fehler.
    """
    from rechner_pipeline.kern import __version__ as kern_version

    config_pfad = ablage.config_pfad
    if not config_pfad.is_file():
        raise TageslaufError(
            f"keine Config unter {config_pfad} — die Laufzeitumgebung traegt "
            "die Config der PLV als Kopie unter configs/ (deploy/plv/README.md)"
        )
    # Genau EINMAL gelesen (Angriffsrunde Betrieb, dieselbe Naht wie N9):
    # Rechnung, Hash der Protokollzeile, Manifest und P-B1 lasen die Config
    # je fuer sich von der Platte, und ein Tausch dazwischen gab einen
    # Stand, der mit der einen Config gerechnet und mit einer anderen
    # bezeugt war. Alle vier lesen jetzt dieselbe eingefrorene Kopie — mit
    # demselben Dateinamen, denn das Manifest nennt ihn.
    # Ein Fehler beim Aufraeumen der Kopie macht den gefuehrten Tag nicht
    # ungeschehen (Angriffsrunde nach T27: Exit 4 "im Vorlauf" nach gruenem Tag).
    with tempfile.TemporaryDirectory(prefix="lauf-config-", ignore_cleanup_errors=True) as tmp:
        eingefroren = Path(tmp) / config_pfad.name
        eingefroren.write_bytes(config_pfad.read_bytes())
        return _tageslauf_mit_config(
            ablage, heute, eingefroren, zeichner, image_digest=image_digest,
            aufschalten=aufschalten)


def _tageslauf_mit_config(
    ablage: Ablage,
    heute: _dt.date,
    config_pfad: Path,
    zeichner: Zeichner,
    *,
    image_digest: Optional[str],
    aufschalten: bool = False,
) -> Tuple[int, Dict[str, Any]]:
    """Der Lauf auf der eingefrorenen Config (siehe :func:`_tageslauf`)."""
    from rechner_pipeline.kern import __version__ as kern_version

    config = load_config(config_pfad)
    fehler = config.validate()
    if fehler:
        raise TageslaufError("Config ungueltig: " + "; ".join(fehler))
    betriebsbeginn = config.tagesbetrieb.betriebsbeginn
    if betriebsbeginn is None:
        raise TageslaufError(
            "die Config traegt keinen [tagesbetrieb] betriebsbeginn — ohne ihn "
            "gibt es keinen ersten Tag, ab dem verkauft wird"
        )
    if heute < betriebsbeginn:
        raise TageslaufError(
            f"heute {heute.isoformat()} liegt vor dem Betriebsbeginn "
            f"{betriebsbeginn.isoformat()}"
        )
    letzter = gefuehrter_tag(ablage, zeichner)
    if letzter is not None and heute == letzter:
        return EXIT_OK, {"heute": heute.isoformat(), "bereits_gefuehrt": True}
    if letzter is not None and heute < letzter:
        raise TageslaufError(
            f"der Stand fuehrt bereits {letzter.isoformat()}; heute "
            f"{heute.isoformat()} liegt davor — ein Tag wird nicht "
            "rueckwaerts gefuehrt"
        )
    nachgeholt = []
    if letzter is not None:
        tag = letzter + _dt.timedelta(days=1)
        while tag < heute:
            nachgeholt.append(tag.isoformat())
            tag += _dt.timedelta(days=1)
    elif heute > betriebsbeginn:
        tag = betriebsbeginn
        while tag < heute:
            nachgeholt.append(tag.isoformat())
            tag += _dt.timedelta(days=1)

    zeile: Dict[str, Any] = {
        "schema_version": PROTOKOLL_SCHEMA_VERSION,
        "heute": heute.isoformat(),
        "gefuehrt_vorher": letzter.isoformat() if letzter else None,
        "nachgeholt": nachgeholt,
        "config_sha256": _datei_hash(config_pfad),
        "kern_version": kern_version,
        # Drei Angaben zum Image, jede mit dem benannten Zustand NICHT_ERFASST
        # statt eines leeren Felds (ein leeres Feld liest sich wie ein
        # Fehler): der Digest kommt aus .env, vom Menschen nach dem Pull
        # eingetragen — der Container kennt ihn selbst nicht (kein Netz,
        # kein Docker-Socket); Revision (Commit des Baus) und Tag traegt
        # das Image bzw. compose.yml. Ausserhalb des Containers fehlen alle.
        "image_digest": image_digest or NICHT_ERFASST,
        "image_revision": os.environ.get("PLV_IMAGE_REVISION") or NICHT_ERFASST,
        "image_tag": os.environ.get("PLV_IMAGE_TAG") or NICHT_ERFASST,
        "uebernommen": False,
    }
    exit_code = EXIT_OK
    try:
        arbeit, zahlen = _stand_bauen(
            config, config_pfad, ablage, heute, zeichner, aufschalten=aufschalten)
        zeile.update(zahlen)
        tabellen, geprueft, befunde = _wache(arbeit, config_pfad, heute)
        zeile["pb1"] = {
            "urteil": "gruen" if not befunde else "rot",
            "geprueft": geprueft,
            "befunde": [b["message"] for b in befunde][:20],
        }
        if befunde:
            exit_code = EXIT_WACHE_ROT
            zeile.pop("_uebernommene_policen", None)
            zeile.pop("_teilbestaende", None)
        else:
            # Tagesjournal auf dem geprueften Ledger (dieselben Bytes).
            journal_alt = (
                read_portfolio(ablage.tagesjournal_pfad, expected_columns=TAGESJOURNAL_NAMES)
                if ablage.tagesjournal_pfad.is_file() else leeres_tagesjournal()
            )
            journal, neu = tagesjournal_ergaenzen(
                journal_alt, tabellen["ledger"], config, heute, ab_tag=betriebsbeginn)
            befunde_journal = validate_tagesjournal(
                journal, tabellen["ledger"], config, heute, ab_tag=betriebsbeginn)
            if befunde_journal:
                raise TagesjournalError("; ".join(befunde_journal[:5]))
            # "gebucht" und "zeilen_gesamt" zaehlen BUCHUNGEN (Zeilen) — ein
            # Zugang bucht seit dem gebuchten Beitrag zwei. "je_ereignis" und
            # "neugeschaeft" zaehlen VORFAELLE, denn wer sie liest, fragt
            # nach Vertraegen: Wie viele Zugaenge, wie viele Verkaeufe.
            # Beides ueber Zeilen zu zaehlen hiesse, doppelt so viel Geschaeft
            # zu melden, wie es gab.
            neu_vorfaelle = neu[["police_id", "ereignis", "status_date", "herkunft"]] \
                .drop_duplicates() if len(neu) else neu
            zeile["tagesjournal"] = {
                "gebucht": int(len(neu)),
                "je_ereignis": {
                    str(k): int(v)
                    for k, v in sorted(neu_vorfaelle["ereignis"].value_counts().items())
                } if len(neu) else {},
                "neugeschaeft": int(
                    (neu_vorfaelle["herkunft"] == "neugeschaeft").sum()
                ) if len(neu) else 0,
                "zeilen_gesamt": int(len(journal)),
            }
            # Bestandszahlen am gefuehrten Tag.
            from rechner_pipeline.bestand.fuehrung import bestand_am

            schnitt = bestand_am(tabellen["portfolio"], tabellen["historie"], heute)
            uebernommene = set(zeile.pop("_uebernommene_policen"))
            zeile["bestand"] = {
                "in_force": int(len(schnitt)),
                "je_produkt": {
                    str(k): int(v) for k, v in sorted(schnitt["produkt"].value_counts().items())
                },
                "uebernommen_in_force": int(schnitt["police_id"].isin(uebernommene).sum()),
                "policiert_beginn_folgt": int(
                    (tabellen["portfolio"]["insurance_start"] > pd.Timestamp(heute)).sum()),
            }
            # Monatsabschluesse fuer jeden Monatsersten im gefuehrten Fenster.
            # Festgeschrieben wird jeder; den Bestandsbericht (jederzeit neu
            # renderbar) bekommt nur der juengste — beim Nachholen vieler
            # Monate waere alles andere Rechenzeit fuer Seiten, die niemand
            # liest. Mit teilbestand_getrennt kommt je Uebernahme ein
            # Bericht ueber ihren Teilbestand dazu (Konzept, Abschnitt 6).
            manifest_hash = _datei_hash(arbeit / MANIFEST_DATEI)
            kennung = str(manifest_hash)[:16]
            # Der Marker liegt VOR dem ersten irreversiblen Schritt — und
            # der ist der Monatsabschluss, nicht der Standwechsel. Ein
            # Abschluss wird 0444 geschrieben und nie neu gerechnet
            # (ADR-011); er ist damit unwiderruflicher als der Symlink,
            # den ein Rename zuruecknimmt.
            #
            # Vorher stand der Marker hinter der Abschluss-Schleife und
            # behauptete im Kommentar, er stehe davor. Ein Fehler dazwischen
            # — etwa im Monatsbericht — hinterliess einen festgeschriebenen
            # Abschluss OHNE Marker, und dem naechsten Lauf fehlte jeder
            # Hinweis, dass ein Publish unterwegs war (Befund T26-02,
            # Szenario 4).
            schreibe_publish_marker(ablage, heute, f"{STAND_DIR}-{kennung}")
            teilbestaende: Dict[str, List[int]] = zeile.pop("_teilbestaende")
            abschluesse: List[Dict[str, Any]] = []
            stichtage = monatserste_in(
                letzter or (betriebsbeginn - _dt.timedelta(days=1)), heute)
            for stichtag in stichtage:
                pfad = abschluss_pfad(ablage.abschluesse, stichtag)
                if pfad.exists():
                    # Nachrechnen statt glauben (Review T24-01). Der
                    # Kurzschluss umging den No-clobber-Schutz von
                    # schreibe_abschluss vollstaendig: Ein Abschluss aus
                    # einem technisch GESCHEITERTEN Lauf — die
                    # Fehlerinjektion des Reviews hinterlaesst genau das —
                    # galt beim naechsten Versuch ungeprueft als gueltig.
                    #
                    # Der Befund wird AUSGEWIESEN, nicht geheilt: Ein
                    # festgeschriebener Stand bewegt sich nicht (ADR-011),
                    # und eine Abweichung nach einer Kern-Aenderung ist
                    # erwartbar. Die Protokollzeile nennt sie, damit ein
                    # Mensch sie sieht — vorher sah sie niemand.
                    sicht = _stichtagssicht(
                        tabellen, config, stichtag, betriebsbeginn)
                    befunde = pruefe_abschluss(
                        pfad, sicht["portfolio"], sicht["historie"], config,
                        scheiben=sicht["scheiben"],
                        merkmale=sicht.get("merkmale"),
                        schichten=sicht.get("schichten"),
                        verankerung=sicht.get("verankerung"),
                        reduktionen=sicht.get("reduktionen"),
                    )
                    # Ein nachgerechneter Abschluss wird genauso BELEGT wie
                    # ein neu geschriebener — Datei, sha256, Monatskennzahlen,
                    # und der juengste bekommt seinen Bericht (Angriffsrunde
                    # Betrieb: ein Ausfall im Publish-Fenster nahm jedem
                    # Abschluss dieses Laufs dauerhaft den Beleg). Und der
                    # Schreibschutz wird nachgezogen, falls der Lauf, der
                    # ihn schrieb, vor dem chmod endete.
                    if os.name != "nt":
                        pfad.chmod(0o444)
                    geschrieben = pfad
                    eintrag: Dict[str, Any] = {
                        "stichtag": stichtag.isoformat(), "datei": pfad.name,
                        "sha256": _datei_hash(pfad), "neu": False,
                        "nachgerechnet": True,
                        **monatskennzahlen(read_portfolio(pfad), journal, stichtag),
                    }
                    if befunde:
                        eintrag["befunde"] = befunde[:20]
                else:
                    # Buchungsschnitt am Stichtag, nicht am Lauftag (T24-02):
                    # Der Abschluss ist, was am Stichtag GEBUCHT war. Wache und
                    # Tagesseite bleiben auf der Sicht von heute — dort ist sie
                    # richtig, denn sie berichten ueber heute.
                    sicht = _stichtagssicht(tabellen, config, stichtag, betriebsbeginn)
                    # Der Abschluss bekommt dieselben Nebentabellen wie die Wache
                    # und der Bericht — sonst weist er die Korrekturschicht als
                    # null aus, obwohl die Fuehrung sie traegt (N-01).
                    geschrieben = schreibe_abschluss(
                        sicht["portfolio"], sicht["historie"], config, stichtag,
                        ablage.abschluesse, scheiben=sicht["scheiben"],
                        merkmale=sicht.get("merkmale"),
                        schichten=sicht.get("schichten"),
                        verankerung=sicht.get("verankerung"),
                        reduktionen=sicht.get("reduktionen"),
                    )
                    eintrag = {
                        "stichtag": stichtag.isoformat(), "datei": geschrieben.name,
                        "sha256": _datei_hash(geschrieben), "neu": True,
                        # Das TAGESJOURNAL, nicht sicht["ledger"]: Nur das
                        # Journal traegt das Buchungsdatum, und ohne das
                        # faellt jeder spaet gebuchte Vorfall auf einem
                        # Stichtag aus der Zaehlung. Den Schnitt auf den
                        # Stichtag macht die Periode selbst — ein Vorfall,
                        # der erst heute gebucht wurde, wird erst in seinem
                        # Monat sichtbar.
                        **monatskennzahlen(
                            read_portfolio(geschrieben), journal, stichtag),
                    }
                if stichtag == stichtage[-1]:
                    # Derselbe Schnitt wie der Abschluss: Der Bericht legt
                    # den Abschluss aus, den er begleitet — auf der Sicht
                    # von heute erzaehlte er vom selben Stichtag eine
                    # andere Geschichte als die Zahlen daneben.
                    bericht = _bericht(
                        sicht, config, stichtag, heute,
                        ablage.berichte / f"bestandsbericht_{stichtag.isoformat()}.html",
                        tabellen["sha256"]["portfolio"],
                    )
                    eintrag["bericht"] = bericht.name
                    if config.tagesbetrieb.teilbestand_getrennt and teilbestaende:
                        eintrag["teilbestaende"] = []
                        for fall, policen in sorted(teilbestaende.items()):
                            teil = _bericht(
                                _teilbestand(sicht, policen), config, stichtag, heute,
                                ablage.berichte
                                / f"bestandsbericht_{stichtag.isoformat()}_teilbestand-{fall}.html",
                                tabellen["sha256"]["portfolio"],
                                titel=f"Teilbestand {fall} (uebernommen) zum {stichtag.isoformat()}",
                            )
                            eintrag["teilbestaende"].append({"fall": fall, "bericht": teil.name})
                abschluesse.append(eintrag)
            zeile["abschluesse"] = abschluesse
            # Ab hier veroeffentlicht der Lauf nach aussen. Der Marker
            # liegt seit dem Beginn der Abschluesse (siehe oben) und sagt
            # dem naechsten Lauf, dass ein Publish unterwegs war — samt
            # allem, was er braucht, um ihn zurueckzunehmen (Review T24-01,
            # Schritt b).
            write_portfolio(journal, ablage.tagesjournal_pfad)
            zeile["tagesjournal"]["sha256"] = _datei_hash(ablage.tagesjournal_pfad)
            _uebernehmen(ablage, kennung)
            zeile["manifest_sha256"] = manifest_hash
            zeile["uebernommen"] = True
    except (EreignisError, NeugeschaeftError, TagesjournalError, AbschlussError,
            UebernahmeError, ManifestError, ValueError, OSError) as exc:
        # OSError (Review T22-03): ein gescheiterter Tausch oder Schreibvorgang
        # ist ein roter Lauf mit Protokollzeile — kein Traceback ohne Nachweis.
        zeile.pop("_uebernommene_policen", None)
        zeile.pop("_teilbestaende", None)
        zeile["fehler"] = f"{type(exc).__name__}: {exc}"
        if exit_code == EXIT_OK:
            exit_code = EXIT_NACHLAUF if "pb1" in zeile else EXIT_USAGE
    from rechner_pipeline.betrieb.seite import (
        SeiteError,
        bereite_bestand_heute_vor,
        verwirf_seite,
        veroeffentliche_seite,
    )

    seite_tmp: Optional[Path] = None
    seite_ziel: Optional[Path] = None
    seite_stand: Optional[_dt.date] = None
    if zeile["uebernommen"]:
        # Die interne Sicht (Konzept, Abschnitt 8.3): aus Protokoll und
        # Journal, nach dem uebernommenen Stand und vor der Protokollzeile,
        # damit die Zeile die Seite nennt. Sie wird aber nur NEBEN sich
        # gerendert und erst nach dem Anfuegen der Zeile ersetzt (unten;
        # Angriffsrunde C, RC08): Aus einem unterbrochenen Lauf wird nichts
        # nach aussen sichtbar, die Seite nennt nur einen Tag, den das
        # Protokoll gruen fuehrt. Eine Seite, die nicht gebaut werden kann,
        # macht den gefuehrten Tag nicht ungeschehen — sie fehlt, und die
        # Zeile sagt es.
        try:
            seite_tmp, seite_ziel, seite_stand = bereite_bestand_heute_vor(
                ablage, aktuelle_zeile=zeile, zeichner=zeichner)
            zeile["seite"] = seite_ziel.name
        except (SeiteError, OSError, ValueError) as exc:
            zeile["seite"] = f"nicht gerendert: {type(exc).__name__}: {exc}"
    try:
        _anfuegen(ablage.protokoll_pfad, zeile, zeichner, aufschalten=aufschalten)
    except OSError as exc:
        # Der Stand ist uebernommen, die Zeile fehlt: Stand und Nachweis
        # sagen ab jetzt Verschiedenes, und der naechste gefuehrter_tag()
        # bricht dauerhaft ab. Vorher lief hier ein roher OSError bis zur
        # CLI durch — ohne Nachweis, ohne Ausweg (Review T24-01).
        verwirf_seite(seite_tmp)
        raise TageslaufError(
            f"Protokollzeile fuer {heute.isoformat()} nicht geschrieben "
            f"({type(exc).__name__}: {exc}). Der Stand ist "
            f"{'uebernommen' if zeile.get('uebernommen') else 'nicht uebernommen'}"
            f" — Stand und Nachweis passen damit nicht mehr zusammen. Ausweg: "
            f"{ablage.protokoll_pfad} schreibbar machen und den Lauf erneut "
            "starten; der Lauf ist idempotent; die Seite zeigt weiter den "
            "letzten gefuehrten Tag"
        ) from exc
    except BaseException:
        verwirf_seite(seite_tmp)
        raise
    if seite_tmp is not None:
        # Die Zeile steht: jetzt darf die Seite nach aussen. Die Sperre haelt
        # dieser Lauf; er fuehrt den Stand, auch rueckwaerts (siehe
        # veroeffentliche_seite). Scheitert der Tausch, ist der Tag trotzdem
        # gefuehrt und belegt — die seite-CLI rendert die Seite neu.
        try:
            veroeffentliche_seite(seite_tmp, seite_ziel, seite_stand,
                                  juengere_seite_schuetzen=False)
        except OSError as exc:
            print(f"tageslauf: Warnung: Seite nicht veroeffentlicht "
                  f"({type(exc).__name__}: {exc}) — der Tag ist gefuehrt und "
                  "belegt; Ausweg: python -m rechner_pipeline.betrieb.seite "
                  f"--stand {ablage.wurzel}", file=sys.stderr)
    # NUR wenn der Publish wirklich durch ist: Stand, Journal und Nachweis
    # sagen dasselbe. Ein ROTER Lauf laesst den Marker liegen — sonst naehme
    # der naechste Lauf nichts zurueck, und der halbe Publish bliebe stehen.
    # Das Wegraeumen steht NACH der Zeile und ausserhalb ihres Fehlerpfads
    # (Angriffsrunde nach T27): Scheiterte es, meldete der Lauf "Zeile nicht
    # geschrieben", obwohl der Tag gruen gefuehrt und belegt war.
    if zeile.get("uebernommen"):
        try:
            entferne_publish_marker(ablage)
        except OSError as exc:
            print(f"tageslauf: Warnung: Publish-Marker nicht weggeraeumt "
                  f"({type(exc).__name__}: {exc}) — der Tag ist gefuehrt und "
                  "belegt; der naechste Lauf raeumt ihn", file=sys.stderr)
    return exit_code, zeile
# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.betrieb.tageslauf",
        description="Den heutigen Tag der PLV fuehren: Neugeschaeft, Fortschreibung, "
        "Tagesjournal, Wache P-B1, Monatsabschluss, Protokoll. Idempotent, "
        "deterministisch; verpasste Tage werden nachgeholt.",
    )
    parser.add_argument("--stand", required=True, help="Datenverzeichnis der Laufzeitumgebung.")
    parser.add_argument(
        "--heute", default=None,
        help="Der zu fuehrende Kalendertag (ISO); Default: Kalendertag des Aufrufs.",
    )
    parser.add_argument(
        "--schluessel", required=True,
        help="Betriebsschluessel (Rolle betrieb/<name>, Schluesselklasse betrieb), "
        "mit dem jede Protokollzeile gezeichnet und die Kette geprueft wird. Er "
        "liegt ausserhalb der Ablage beim Menschen (0600, ein Hardlink).")
    parser.add_argument(
        "--zeichnungsordnung", required=True,
        help="Zeichnungsordnung (Schema 2), die dem Schluessel seine Rolle gibt; "
        "ausserhalb der Ablage.")
    parser.add_argument(
        "--aufschalten", action="store_true",
        help="Einmalig beim ersten Lauf nach dem Umstieg auf den Betriebsschluessel: "
        "ein Protokoll ohne gezeichnete Zeile (Altbestand) weiterfuehren; die erste "
        "gezeichnete Zeile pinnt den Vorlauf. Auf ein gezeichnetes oder leeres "
        "Protokoll verweigert (deploy/plv/README.md).")
    parser.add_argument(
        "--image-digest", dest="image_digest", default=None,
        help="Digest des Container-Images fuer das Protokoll (Default: "
        "Umgebungsvariable PLV_IMAGE_DIGEST).",
    )
    ns = parser.parse_args(argv)
    try:
        heute = _dt.date.fromisoformat(ns.heute) if ns.heute else _dt.date.today()
    except ValueError as exc:
        print(f"tageslauf: --heute: {exc}", file=sys.stderr)
        return EXIT_USAGE
    ablage = Ablage(Path(ns.stand))
    digest = ns.image_digest or os.environ.get("PLV_IMAGE_DIGEST") or None
    try:
        code, zeile = tageslauf(
            ablage, heute, schluessel=Path(ns.schluessel),
            zeichnungsordnung=Path(ns.zeichnungsordnung), image_digest=digest,
            aufschalten=ns.aufschalten)
    except TageslaufError as exc:
        print(f"tageslauf: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except ValueError as exc:
        # Eine unlesbare Eingabe (halb kopierte Config: TOML- oder
        # UTF-8-Fehler) ist ein Eingangsfehler mit Meldung, kein Traceback
        # mit Exit 1 (Angriffsrunde nach T27).
        print(f"tageslauf: Eingabe nicht lesbar: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except OSError as exc:
        # Ein Ein-/Ausgabefehler VOR dem eigentlichen Lauf (Ruecknahme,
        # Teilzeilenschnitt, Aufraeumen unter der Sperre) ist ein Fehler
        # vor der Wache — Exit 2 mit Meldung statt Traceback und Exit 1.
        # Der naechste Lauf nimmt denselben Vorlauf wieder auf.
        print(f"tageslauf: Ein-/Ausgabefehler im Vorlauf: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return EXIT_USAGE
    if zeile.get("bereits_gefuehrt"):
        print(f"tageslauf: {heute.isoformat()} bereits gefuehrt, nichts zu tun",
              file=sys.stderr)
        return code
    if code == EXIT_OK:
        print(
            f"tageslauf: {heute.isoformat()} gefuehrt"
            + (f" (nachgeholt: {len(zeile['nachgeholt'])} Tage)" if zeile["nachgeholt"] else "")
            + f", {zeile['tagesjournal']['gebucht']} Buchungen, "
            f"{zeile['bestand']['in_force']} Vertraege in Kraft, "
            f"{len(zeile.get('abschluesse', []))} Monatsabschluesse -> {ablage.stand}",
            file=sys.stderr,
        )
    elif code == EXIT_WACHE_ROT:
        print(
            f"tageslauf: WACHE ROT am {heute.isoformat()} — Stand nicht uebernommen, "
            f"{len(zeile['pb1']['befunde'])} Befund(e): "
            + "; ".join(zeile["pb1"]["befunde"][:3]),
            file=sys.stderr,
        )
    else:
        print(f"tageslauf: {zeile.get('fehler')} — Stand nicht uebernommen", file=sys.stderr)
    return code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
