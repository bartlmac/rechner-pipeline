"""``betrieb.tageslauf`` — der naechtliche Lauf der PLV (Fachkonzept Tagesbetrieb, Abschnitt 7).

Ein Kommando, idempotent und deterministisch::

    python -m rechner_pipeline.betrieb.tageslauf --stand <daten> --heute <datum>

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
3. **Fortschreibung bis heute.** Basisbestand (Batch bis Betriebsbeginn)
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
   (``stichtag <= bis``). Die Erstbefuellung schreibt so auch den
   Eroeffnungsstand zum Betriebsbeginn.
7. **Tagesprotokoll**: eine JSON-Zeile je Lauf.

Der Stand wird erst uebernommen, wenn die Wache gruen ist: Der Lauf
schreibt in ein Arbeitsverzeichnis neben ``stand/``, prueft dort, und
tauscht dann atomar. Ein Absturz mitten im Lauf hinterlaesst den alten
Stand und ein Arbeitsverzeichnis, das der naechste Lauf verwirft.

Ablage unter ``--stand`` (Konzept, Abschnitt 7)::

    stand/          sechs Ausgaben + laufmanifest.json (+ merkmale.parquet)
    journal/        tagesjournal.parquet, protokoll.jsonl (nur-anfuegbar)
    seite/          index.html "Bestand heute" (betrieb.seite), nach jedem gruenen Lauf
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
from rechner_pipeline.bestand.generator import generate
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
from rechner_pipeline.models.bestand import (
    LEDGER_NAMES,
    MERKMALE_NAMES,
    STAMM_NAMES,
    STATUS_HISTORIE_NAMES,
    TAGESJOURNAL_NAMES,
)

#: Schema 2 (Review T22-05): jede Zeile traegt ``vorgaenger_sha256``, den
#: SHA-256 der vorangehenden Zeile (Bytes ohne Zeilenende; "" fuer die
#: erste). Zeilen der Erstfassung (Schema 1) bleiben lesbar; sobald eine
#: Zeile Schema 2 traegt, ist die Kette ab dort Pflicht.
PROTOKOLL_SCHEMA_VERSION = 2
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

#: Exit-Codes: 0 gruen und uebernommen, 2 Aufruf-/Eingangsfehler, 3 Wache rot
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
    Beweismaterial vernichtet. Gerufen wird nur aus der Ruecknahme, also
    nur, wenn ein Marker bezeugt, dass ein Publish unterwegs war.
    """
    if not pfad.is_file():
        return False
    roh = pfad.read_bytes()
    if not roh or roh.endswith(b"\n"):
        return False
    schnitt = roh.rfind(b"\n") + 1
    pfad.write_bytes(roh[:schnitt])
    print(
        f"tageslauf: {pfad} endete mit einer angefangenen Zeile "
        f"({len(roh) - schnitt} Bytes ohne Zeilenumbruch) — sie ist nie "
        "geschrieben worden und wurde entfernt; der Tag wird erneut gefuehrt.",
        file=sys.stderr,
    )
    return True


def nimm_publish_zurueck(ablage: "Ablage") -> Optional[Dict[str, Any]]:
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
    gruene = [z for z in lies_protokoll(ablage.protokoll_pfad)
              if z.get("uebernommen")]
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


def lies_protokoll(pfad: Path) -> List[Dict[str, Any]]:
    """Alle Zeilen des Tagesprotokolls (leer, wenn es noch keines gibt) —
    mit Pruefung der Kette.

    Review T22-05: Das Protokoll war editierbar, ohne dass es jemand
    merkte — eine entfernte mittlere Zeile liess den letzten Tag weiter
    gelten. Jede Zeile ab Schema 2 nennt den Hash ihrer Vorgaengerin; eine
    Luecke, eine Aenderung oder eine Umsortierung bricht die Kette, und
    ein gebrochenes Protokoll ist ein Befund, kein Nachweis.
    """
    if not Path(pfad).is_file():
        return []
    zeilen: List[Dict[str, Any]] = []
    vorgaenger_roh: Optional[str] = None
    for nummer, roh in enumerate(Path(pfad).read_text(encoding="utf-8").splitlines(), 1):
        if not roh.strip():
            continue
        try:
            zeile = json.loads(roh)
        except json.JSONDecodeError as exc:
            raise TageslaufError(
                f"{pfad}: Zeile {nummer} ist kein JSON ({exc}) — das Protokoll "
                "ist nur-anfuegbar; eine kaputte Zeile ist ein Befund, kein "
                "Grund zum Ueberschreiben"
            ) from exc
        if isinstance(zeile, dict) and zeile.get("schema_version", 1) >= 2:
            erwartet = _zeilen_hash(vorgaenger_roh) if vorgaenger_roh is not None else ""
            if zeile.get("vorgaenger_sha256") != erwartet:
                raise TageslaufError(
                    f"{pfad}: Zeile {nummer} bricht die Protokollkette (vorgaenger_sha256 "
                    f"passt nicht zur Zeile davor) — das Protokoll wurde veraendert, "
                    "gekuerzt oder umsortiert; es ist damit kein Nachweis mehr"
                )
        zeilen.append(zeile)
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
        if jetzt.get("schema_version", 1) < 2:
            continue
        tag_vorher = _dt.date.fromisoformat(str(vorher["heute"]))
        tag_jetzt = _dt.date.fromisoformat(str(jetzt["heute"]))
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
    return gelesen


def gefuehrter_tag(ablage: Ablage) -> Optional[_dt.date]:
    """Der letzte gruen gefuehrte Tag — aus dem Manifest des Stands.

    Das Manifest ist die Aussage des Stands ueber sich selbst (Horizont);
    das Protokoll muss dieselbe Aussage machen, sonst passen Stand und
    Nachweis nicht zusammen, und der Lauf bricht ab statt einen der
    beiden zu glauben. Dazu der Nachweisvertrag (:func:`pruefe_nachweis`).
    """
    if not ablage.stand.is_dir():
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
    gruene = [z for z in lies_protokoll(ablage.protokoll_pfad) if z.get("uebernommen")]
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


def _bereits_gefuehrte_eingaenge(ablage: Ablage) -> set:
    """Die Faelle, die der letzte gruene Lauf schon gefuehrt hat."""
    gruene = [z for z in lies_protokoll(ablage.protokoll_pfad) if z.get("uebernommen")]
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


def _stand_bauen(
    config: BestandConfig, config_pfad: Path, ablage: Ablage, heute: _dt.date
) -> Tuple[Path, Dict[str, Any]]:
    """Den Stand fuer ``heute`` im Arbeitsverzeichnis erzeugen (noch nicht uebernommen)."""
    betriebsbeginn = config.tagesbetrieb.betriebsbeginn
    assert betriebsbeginn is not None
    basis = generate(config, bis=betriebsbeginn)
    ausgaben: List[Path] = []
    eingaben: Dict[str, Path] = {}
    if ablage.arbeit.exists():
        _entferne_ablageverzeichnis(ablage, ablage.arbeit)
    ablage.arbeit.mkdir(parents=True)
    ausgaben.append(write_portfolio(basis, ablage.arbeit / "bestand.parquet"))

    uebernahmen = lies_uebernahmen(ablage.uebernahme, config)
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
    schon_gefuehrt = _bereits_gefuehrte_eingaenge(ablage)
    abschluesse_bisher = _festgeschriebene_abschluesse(ablage)
    juengster_abschluss = abschluesse_bisher[-1] if abschluesse_bisher else None
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
        if not betriebsbeginn <= ueb.stichtag <= heute:
            raise TageslaufError(
                f"uebernahme {ueb.fall}: Stichtag {ueb.stichtag.isoformat()} "
                "liegt ausserhalb der gefuehrten Zeit "
                f"[{betriebsbeginn.isoformat()}, {heute.isoformat()}] — ein "
                "Bestand tritt in Buecher ein, die es schon gibt, und an "
                "einem Tag, der geschehen ist"
            )
        if (
            ueb.fall not in schon_gefuehrt
            and juengster_abschluss is not None
            and juengster_abschluss >= ueb.stichtag
            and not _abschluss_kennt_eingang(
                ablage, juengster_abschluss, ueb.bestand["police_id"])
        ):
            raise TageslaufError(
                f"uebernahme {ueb.fall}: Stichtag {ueb.stichtag.isoformat()} "
                f"liegt nicht nach dem juengsten festgeschriebenen "
                f"Monatsabschluss {juengster_abschluss.isoformat()} — dieser "
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
    if len(zugaenge) and (zugaenge["insurance_start"] <= pd.Timestamp(betriebsbeginn)).any():
        raise TageslaufError(
            "Neugeschaeft mit Beginn am oder vor dem Betriebsbeginn — der "
            "Batch besiedelt diesen Zeitraum bereits (ein Erzeuger je Zeitfenster)"
        )
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
        # Stufe 1 von T22-11: ausgewiesen, nicht angewandt.
        "verankerung": {
            "registriert": int(len(verankerung)) if verankerung is not None else 0,
            # Seit Schritt 9 gehen Verankerung und Korrekturschicht in die
            # Fortschreibung ein (Schritte 4 und 5): angewandt heisst, die
            # Schicht lag vor und wurde der Engine uebergeben.
            "angewandt": bool(verankerung is not None and schichten is not None),
            "hinweis": (
                "Verankerung und Korrekturschicht der uebernommenen Vertraege gehen "
                "in Storno und Bewertung der Fortschreibung ein (Freischaltung, "
                "Schritte 4/5/9)"
                if verankerung is not None and schichten is not None
                else "Verankerung registriert, aber ohne Korrekturschicht (schichten.parquet) "
                "nicht angewandt — der Eingang traegt keinen Schichtbeleg"
                if verankerung is not None
                else "keine Verankerung uebernommen"
            ),
        },
        # Fall-Bezug jeder Uebernahme (Konzept, Abschnitt 6): Der Zugang
        # ist als datierter Eingang nachweisbar, nicht als anonyme Zeile.
        "uebernahmen": [
            {"fall": u.fall, "stichtag": u.stichtag.isoformat(),
             "vertraege": int(len(u.bestand)), "snapshot_sha256": u.snapshot_sha256,
             "zeichnung": dict(u.zeichnung)}
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


@contextlib.contextmanager
def lauf_sperre(ablage: Ablage):
    """Exklusive Prozess-Sperre der Laufzeitumgebung (nicht blockierend).

    Zwei gleichzeitige Laeufe (Timer und Hand, zwei Timer nach einer
    Haengepartie) teilten sich stand.neu, Journal und Protokoll (Review
    T22-03). Der zweite bricht jetzt sofort ab, mit Meldung.
    """
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
    sicht["reduktionen"] = _gebuchte_reduktionen(
        tabellen.get("reduktionen"), ledger)
    return sicht


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


def _anfuegen(pfad: Path, zeile: Dict[str, Any]) -> None:
    """Eine Protokollzeile anfuegen (nur-anfuegbar, sortierte Schluessel),
    verkettet mit der Zeile davor (T22-05)."""
    pfad.parent.mkdir(parents=True, exist_ok=True)
    vorgaenger = ""
    if pfad.is_file():
        letzte = [z for z in pfad.read_text(encoding="utf-8").splitlines() if z.strip()]
        if letzte:
            vorgaenger = _zeilen_hash(letzte[-1])
    zeile["vorgaenger_sha256"] = vorgaenger
    text = json.dumps(zeile, ensure_ascii=False, sort_keys=True) + "\n"
    with open(pfad, "a", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _datei_hash(pfad: Path) -> Optional[str]:
    return sha256_bytes(Path(pfad).read_bytes()) if Path(pfad).is_file() else None


def tageslauf(
    ablage: Ablage,
    heute: _dt.date,
    *,
    image_digest: Optional[str] = None,
) -> Tuple[int, Dict[str, Any]]:
    """Den Tag ``heute`` fuehren — unter der Prozess-Sperre der Ablage
    (Review T22-03); siehe :func:`_tageslauf`."""
    with lauf_sperre(ablage):
        # ZUERST einen unterbrochenen Publish zuruecknehmen (Review
        # T24-01, Schritt b): Danach ist die Ablage wieder in einem
        # Zustand, ueber den Nachweisvertrag und Aufraeumung urteilen
        # koennen. Vorher fiel jeder Retry ueber genau diesen
        # Zwischenzustand — und zwar dauerhaft.
        nimm_publish_zurueck(ablage)
        _verwaiste_staende_entfernen(ablage)
        return _tageslauf(ablage, heute, image_digest=image_digest)


def _tageslauf(
    ablage: Ablage,
    heute: _dt.date,
    *,
    image_digest: Optional[str] = None,
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
    letzter = gefuehrter_tag(ablage)
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
        arbeit, zahlen = _stand_bauen(config, config_pfad, ablage, heute)
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
                    eintrag_alt: Dict[str, Any] = {
                        "stichtag": stichtag.isoformat(), "datei": pfad.name,
                        "neu": False, "nachgerechnet": True,
                    }
                    if befunde:
                        eintrag_alt["befunde"] = befunde[:20]
                    abschluesse.append(eintrag_alt)
                    continue
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
                eintrag: Dict[str, Any] = {
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
    if zeile["uebernommen"]:
        # Die interne Sicht (Konzept, Abschnitt 8.3): aus Protokoll und
        # Journal, nach dem uebernommenen Stand und vor der Protokollzeile,
        # damit die Zeile die Seite nennt. Eine Seite, die nicht gebaut
        # werden kann, macht den gefuehrten Tag nicht ungeschehen — sie
        # fehlt, und die Zeile sagt es.
        from rechner_pipeline.betrieb.seite import SeiteError, rendere_bestand_heute

        try:
            zeile["seite"] = rendere_bestand_heute(ablage, aktuelle_zeile=zeile).name
        except (SeiteError, OSError, ValueError) as exc:
            zeile["seite"] = f"nicht gerendert: {type(exc).__name__}: {exc}"
    try:
        _anfuegen(ablage.protokoll_pfad, zeile)
        # NUR wenn der Publish wirklich durch ist: Stand, Journal und
        # Nachweis sagen dasselbe. Ein ROTER Lauf laesst den Marker
        # liegen — sonst naehme der naechste Lauf nichts zurueck, und der
        # halbe Publish bliebe stehen.
        if zeile.get("uebernommen"):
            entferne_publish_marker(ablage)
    except OSError as exc:
        # Der Stand ist uebernommen, die Zeile fehlt: Stand und Nachweis
        # sagen ab jetzt Verschiedenes, und der naechste gefuehrter_tag()
        # bricht dauerhaft ab. Vorher lief hier ein roher OSError bis zur
        # CLI durch — ohne Nachweis, ohne Ausweg (Review T24-01).
        raise TageslaufError(
            f"Protokollzeile fuer {heute.isoformat()} nicht geschrieben "
            f"({type(exc).__name__}: {exc}). Der Stand ist "
            f"{'uebernommen' if zeile.get('uebernommen') else 'nicht uebernommen'}"
            f" — Stand und Nachweis passen damit nicht mehr zusammen. Ausweg: "
            f"{ablage.protokoll_pfad} schreibbar machen und den Lauf erneut "
            "starten; der Lauf ist idempotent"
        ) from exc
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
        code, zeile = tageslauf(ablage, heute, image_digest=digest)
    except TageslaufError as exc:
        print(f"tageslauf: {exc}", file=sys.stderr)
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
