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
        --fall <faelle/name> --stichtag 2026-01-01 [--snapshot <sha256>] \\
        [--zugangsabnahme <sha256>]

Seit ADR-022 (Entscheid des Maintainers 2026-09-30) hat der Zugang drei
Schritte: die Zugangsprobe (``betrieb.zugangsprobe``) auf einer Kopie der
Ablage, die Zugangsabnahme A-B2 und erst dann die Registrierung. Sie
verlangt den angenommenen A-B2-Snapshot, der GENAU den Eingang bindet, den
sie schreibt, und den gefuehrten Stand der Ablage, auf dem sie ihn
schreibt; der Tageslauf haelt ihn beim Eintritt noch einmal dagegen.

Knoten: klv, bu
"""

from __future__ import annotations

from typing import Mapping

import contextlib
import dataclasses
import sys as _sys
import datetime as _dt
import io
import json

try:  # Referenzumgebung ist Linux; ohne fcntl gibt es keine Prozess-Sperre.
    import fcntl
except ImportError:  # pragma: no cover - fremde Plattform
    fcntl = None  # type: ignore[assignment]
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import pandas as pd

from rechner_pipeline.betrieb._loeschen import LoeschFehler, entferne_verzeichnis
from rechner_pipeline.models.zeichnung import ZEICHNENDE_KLASSEN
from rechner_pipeline.models.schemas import P9Snapshot, p9_semantik_fehler, p9_snapshot_sha256
from rechner_pipeline.bestand.config import BestandConfig
from rechner_pipeline.bestand.manifest import sha256_bytes
from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
from rechner_pipeline.models.bestand import (
    LEDGER_NAMES,
    MERKMALE_NAMES,
    POLICENNUMMERN_NAMES,
    SCHEIBEN_NAMES,
    SCHICHTEN_NAMES,
    STAMM_NAMES,
    STATUS_HISTORIE_NAMES,
    VERANKERUNG_NAMES,
    validate_scheiben,
    validate_schichten,
    validate_verankerung,
)

#: Wurzel der VEROEFFENTLICHTEN Eingaenge in der Laufzeitablage.
UEBERNAHME_DIR = "uebernahme"
#: Wurzel der Eingaenge IM BAU — daneben, nicht darin (Befund T26-01).
#:
#: Vorher entstand ein Eingang als ``<fallname>.neu`` NEBEN seinem
#: spaeteren Namen, im selben Verzeichnis. Das Suffix war die einzige
#: Unterscheidung zwischen "Arbeitsrest" und "Eingang" — und ``fall.neu``
#: ist ein gueltiger Fallname. Wer danach den Fall ``fall`` registrierte,
#: loeschte den fremden, regulaer registrierten Eingang ``fall.neu``.
#:
#: Zwei getrennte Wurzeln machen die Ueberschneidung unmoeglich, statt
#: sie zu verbieten: Kein Fallname kann einen Pfad unter der einen Wurzel
#: auf einen Pfad unter der anderen abbilden. Derselbe Schnitt schliesst
#: Befund T26-15 mit — der Leser sieht unter ``uebernahme/`` nur noch
#: Veroeffentlichtes, und ein abgebrochenes Anlegen blockiert den
#: Tagesbetrieb nicht mehr.
STAGING_DIR = "uebernahme.neu"
EINGANG_DATEI = "eingang.json"
#: Schema 2 (Review T24-08): Der Eingang nennt sein Nummernband und
#: registriert die Uebersetzungstabelle Quell- auf Zielnummer.
#: Schema 3 (Pruefrunde nach T27, Runde C; Entscheid des Maintainers
#: 2026-09-30): Die Registrierung ZEICHNET eingang.json mit dem
#: Betriebsschluessel (``betriebszeichnung``, Verfahren hmac-sha256-v2 nach
#: ``models.anker``) — ueber alle Felder: Datei-Hashes, Snapshot-Hash und
#: den A-M4-Zeichnungsblock mit ``signatur_verifiziert``. Vorher war dieses
#: Flag nur eine Angabe der Datei: Wer die Ablage beschreiben konnte,
#: schrieb einen Eingang stimmig um oder legte einen neuen hin (RC14, RC15).
#: Ein Eingang nach Schema 2 bleibt lesbar, tritt im Betrieb aber nur ein,
#: wenn eine gezeichnete Protokollzeile ihn schon bezeugt (Aufschaltung).
EINGANG_SCHEMA_VERSION = 3
EINGANG_SCHEMA_ALT = 2
#: Pflichttabellen eines Zugangsstands und ihre Spaltenvertraege.
PFLICHT = {
    "bestand": STAMM_NAMES,
    "historie": STATUS_HISTORIE_NAMES,
    "ledger": LEDGER_NAMES,
}
OPTIONAL = {
    "merkmale": MERKMALE_NAMES,
    "verankerung": VERANKERUNG_NAMES,
    # Freischaltung (Schritt 9): die Alt-Erhoehungen als Bausteine und die
    # Korrekturschicht wandern mit in den Betrieb — sonst fuehrt der
    # Tagesbetrieb eine andere Welt als die Abnahmen.
    "scheiben": SCHEIBEN_NAMES,
    "schichten": SCHICHTEN_NAMES,
}
#: Belegdateien der Uebernahme, die der Eingang mit registriert (Hash) und
#: der Betrieb liest: der Uebernahmebeleg traegt Modus und Tarifwerk-
#: Schalter, gegen die die Config der Laufzeit gehalten wird.
BELEGE = ("uebernahme.json",)

#: Die Uebersetzungstabelle Quellnummer -> Zielnummer eines Eingangs.
POLICENNUMMERN_DATEI = "policennummern.parquet"

#: Der Zahlenraum, den kein Erzeuger der PLV erreichen kann. Ein
#: Nummernkreis ``k`` belegt ``k*10 Mio + 1 .. (k+1)*10 Mio - 1``, und
#: ``k >= 1`` ist erzwungen (``config._pruefe_nummernkreise``; auch der
#: Positions-Rueckfall zaehlt ab 1). Alles bis einschliesslich zehn
#: Millionen ist damit konstruktiv frei und der Heimatraum uebernommener
#: Bestaende.
NAMENSRAUM_UEBERNAHME_BIS = 10_000_000

#: Ein Band bekommt, was seine Lieferung braucht, aufgerundet auf volle
#: Tausend. BEWUSST kein festes Raster (Review T24-08, Entscheid des
#: Maintainers 2026-09-15): Eine feste Bandgroesse ist immer eine
#: willkuerliche Obergrenze — entweder fuer die Zahl der Faelle oder fuer
#: ihre Groesse. Bedarfsgerecht traegt derselbe Raum hundert kleine
#: Migrationstranchen genauso wie wenige grosse Bestaende.
BAND_SCHRITT = 1_000


class UebernahmeError(ValueError):
    """Ein Uebernahme-Eingang ist unvollstaendig, veraendert oder unpassend."""


def nebentabellen_fehler(
    bestand: pd.DataFrame,
    historie: Optional[pd.DataFrame],
    scheiben: Optional[pd.DataFrame],
    verankerung: Optional[pd.DataFrame],
    schichten: Optional[pd.DataFrame],
) -> List[str]:
    """Die Nebentabellen eines Zugangsstands gegen dieselbe Pruefung halten wie das Gate.

    Was der Betrieb an Nebentabellen liest, wird gegen dieselbe Vokabel und
    dieselben Invarianten gehalten wie in Gate P-B1 (Betriebsbefund N-01,
    2026-09-08): Vorher las der Betriebsweg ``zustand_ta = "POL"`` und einen
    ``verankerungszustand``, den kein Zustandsmodell kennt, anstandslos ein
    — das Gate haette beides abgewiesen, der Kern brach vier Schichten
    tiefer ohne Bezug zum Eingang ab. Leer = in Ordnung.
    """
    fehler: List[str] = []
    if scheiben is not None and len(scheiben):
        fehler += validate_scheiben(bestand, scheiben, historie=historie)
    if verankerung is not None and len(verankerung):
        fehler += validate_verankerung(bestand, verankerung, historie=historie)
    if schichten is not None and len(schichten):
        fehler += validate_schichten(bestand, schichten, verankerung)
    return fehler


def _nebentabellen_fehler_im(verzeichnis: Path) -> List[str]:
    """Dasselbe fuer die Dateien eines (halb) angelegten Eingangs."""
    tabellen: Dict[str, Optional[pd.DataFrame]] = {}
    for name, spalten in {**PFLICHT, **OPTIONAL}.items():
        pfad = verzeichnis / f"{name}.parquet"
        tabellen[name] = read_portfolio(pfad, expected_columns=spalten) if pfad.is_file() else None
    if tabellen["bestand"] is None:
        return ["bestand.parquet fehlt"]
    return nebentabellen_fehler(
        tabellen["bestand"], tabellen["historie"], tabellen["scheiben"],
        tabellen["verankerung"], tabellen["schichten"],
    )


def _eingang_pb1_fehler(verzeichnis: Path, stichtag: _dt.date, config_pfad: Path) -> List[str]:
    """Die P-B1-Pruefung ueber die Tabellen eines (halb) angelegten Eingangs.

    Dieselbe Funktion wie die Wache des Tageslaufs, mit dem Stichtag als
    Horizont. Liegt in der Ablage schon eine Config, werden die Betraege
    auch hergeleitet; ohne sie (Einrichtung, Config folgt) wird die Form
    geprueft und ausdruecklich nicht hergeleitet.
    """
    from rechner_pipeline.bestand.vorbedingungen import PB1_ROLLEN_DATEIEN, lies_und_pruefe_pb1

    # Die Rollen aus der Tabelle der Engine, nicht abgetippt (N-01); der
    # Eingang fuehrt den Stamm nur unter seinem eigenen Namen.
    eingaben: Dict[str, Path] = {}
    for rolle, datei in PB1_ROLLEN_DATEIEN.items():
        pfad = verzeichnis / ("bestand.parquet" if rolle == "portfolio" else datei)
        if pfad.is_file():
            eingaben[rolle] = pfad
    mit_config = config_pfad.is_file()
    if mit_config:
        eingaben["config"] = config_pfad
    _tab, _geprueft, fehler, usage = lies_und_pruefe_pb1(
        eingaben, bis=stichtag)
    return [f"{b.get('code')}: {b.get('message')}" for b in usage + fehler]


#: Was ueber die Zeichnung einer A-M4-Annahme NICHT bekannt ist, heisst so —
#: nicht leer, nicht None. Aeltere Snapshots (Schema 6) fuehren keine
#: Schluesselklasse; die Seite sagt dann "nicht ausgewiesen", wie die
#: Fall-Seite.
NICHT_AUSGEWIESEN = "nicht ausgewiesen"

#: Der Schluesselring, mit dem ``eingang_anlegen`` eine Freigabesignatur
#: prueft, wenn der Aufrufer keinen uebergibt. Produktiv bleibt er None —
#: der Ring kommt aus ``--freigabe-schluessel`` der CLI und wird
#: ausdruecklich uebergeben. Die Naht ist fuer Tests da (conftest setzt
#: den Testschluessel), damit jede Registrierung im Testlauf verifiziert
#: ist, ohne dass jede Aufrufstelle einen Ring tragen muss. Ohne Ring
#: wird registriert mit ``signatur_verifiziert: False`` als benanntem
#: Zustand — und ``lies_uebernahme`` nimmt so einen Eingang NICHT in die
#: Fuehrung (zwei Zeugen, Entscheid 2026-09-22).
_STANDARD_SCHLUESSELRING: Optional[Mapping[str, bytes]] = None

#: Die Zugangsabnahme eines Eingangs (ADR-022): ein Satz neben
#: ``eingang.json``, den die Registrierung schreibt, nachdem sie den
#: A-B2-Snapshot samt Freigabesignatur geprueft und seine Bindungen gegen
#: IHREN Eingang und den Stand der Ablage gehalten hat — gezeichnet mit dem
#: Betriebsschluessel, wie eingang.json selbst. Der Tageslauf kennt den Fall
#: nicht; er liest die Abnahme hier und haelt sie beim Eintritt gegen den
#: Stand, auf dem er laeuft. Er steht NICHT in ``dateien`` von eingang.json:
#: Die Abnahme bindet den Hash von eingang.json, und eingang.json kann den
#: Hash der Abnahme nicht zugleich tragen.
ZUGANGSABNAHME_DATEI = "zugangsabnahme.json"
#: Schema 2 (Block F, Nachbesserung): die Bindung an Config, Kern und
#: Code-Stand der Probe (``bindung``), die der Tageslauf beim
#: tatsaechlichen Eintritt haelt, und die Soll-Bindung der Abnahmen.
ZUGANGSABNAHME_SCHEMA_VERSION = 2

#: Die Naht der Zugangsabnahme fuer Tests (Muster: die Naht des
#: Betriebsschluessels, ``tageslauf._STANDARD_BETRIEBSZEICHNUNG``).
#: Produktiv bleibt sie None: Ohne A-B2 wird nichts registriert. Die Tests
#: setzen sessionweit einen Helfer (tests/zugangsabnahme_testhelfer.py), der
#: fuer eine Registrierung ohne ausdrueckliche Abnahme den Beleg der Probe
#: und einen gezeichneten A-B2-Snapshot im Fall anlegt und dessen Hash
#: liefert. Geprueft wird der Snapshot danach auf demselben Weg wie jeder
#: andere — die Naht ersetzt die Abnahme, nicht ihre Pruefung.
#: Aufruf: ``naht(fall, ablage_stand=..., eingang_roh=..., am4_snapshot_sha256=...,
#: zeichner=..., schluesselring=...)``.
_STANDARD_ZUGANGSABNAHME: Optional[Callable[..., str]] = None


def _umnummeriert(tabelle: pd.DataFrame, abbildung: Dict[int, int], name: str) -> pd.DataFrame:
    """Eine Tabelle des Zugangsstands auf die Zielnummern heben.

    Die Zeilenreihenfolge bleibt, wie sie war: Die Abbildung ist monoton
    (aufsteigende Quellnummern auf aufsteigende Zielnummern), eine nach
    ``police_id`` sortierte Tabelle bleibt also sortiert, und eine nach
    etwas anderem sortierte behaelt ihre fachliche Ordnung.
    """
    fremd = sorted({int(p) for p in tabelle["police_id"]} - set(abbildung))
    if fremd:
        raise UebernahmeError(
            f"{name}: nennt Policen, die der Bestand nicht fuehrt ({fremd[:5]}"
            f"{' …' if len(fremd) > 5 else ''}) — eine Nebentabelle ohne Vertrag "
            "ist kein Zugangsstand, und ohne Vertrag gibt es keine Zielnummer"
        )
    neu = tabelle.copy()
    neu["police_id"] = pd.Series(
        [abbildung[int(p)] for p in tabelle["police_id"]], dtype="int64", index=tabelle.index)
    return neu


def zielnummern(eingang: Path) -> Dict[int, int]:
    """Quellnummer -> Zielnummer eines Eingangs.

    Die Antwort auf "Was ist aus eurer Police 7000487 geworden?". Der
    Betrieb fuehrt eigene Policennummern (Review T24-08); die Belege des
    Falls sprechen weiter in Quellnummern. Diese Tabelle ist die Bruecke,
    und sie ist registriert wie jede andere Datei des Eingangs — wer sie
    aendert, bricht den Hash.
    """
    import io

    eingang = Path(eingang)
    pfad = eingang / POLICENNUMMERN_DATEI
    if not pfad.is_file():
        raise UebernahmeError(
            f"{pfad}: die Uebersetzungstabelle fehlt — ohne sie ist der Bezug "
            "zwischen gelieferten und gefuehrten Policennummern verloren"
        )
    # Der Satz oben stand schon da, geprueft hat ihn niemand (Befund
    # T26-13): Die Tabelle war im Manifest gehasht, wurde aber unabhaengig
    # davon gelesen. Eine Mutation nur an der Map — Manifest unveraendert
    # — lieferte eine falsche Zielidentitaet, und bei vollstaendigem
    # Verlust der Bruecke blieb die Tagesfuehrung gruen.
    daten = pfad.read_bytes()
    registriert = (_lies_eingang(eingang).get("dateien") or {}).get(
        POLICENNUMMERN_DATEI)
    if registriert is None:
        raise UebernahmeError(
            f"{eingang / EINGANG_DATEI}: nennt {POLICENNUMMERN_DATEI} nicht — "
            "eine Bruecke, die das Manifest nicht fuehrt, ist keine"
        )
    if sha256_bytes(daten) != registriert:
        raise UebernahmeError(
            f"{pfad}: SHA-256 weicht von der registrierten Summe ab — die "
            "Uebersetzung ist unantastbar wie jede andere Datei des Eingangs"
        )
    tabelle = read_portfolio(io.BytesIO(daten),
                             expected_columns=POLICENNUMMERN_NAMES)
    # Eindeutigkeit auf der ROHTABELLE, bevor sie zur Abbildung wird
    # (Pruefrunde T27, Befund 16): Ein Dict kollabiert doppelte
    # Quellnummern still — die letzte Zeile gewinnt —, und die
    # Bijektionspruefung dahinter sah nur noch eindeutige Schluessel.
    # Zwei widerspruechliche Zuordnungen vertauschten so die Quellen
    # zweier Zielpolicen, und der Reader nahm die Bruecke an.
    doppelt_q = sorted(int(q) for q in tabelle["quelle_police_id"][
        tabelle["quelle_police_id"].duplicated()].unique())
    doppelt_z = sorted(int(z) for z in tabelle["ziel_police_id"][
        tabelle["ziel_police_id"].duplicated()].unique())
    if doppelt_q or doppelt_z:
        raise UebernahmeError(
            f"{pfad}: die Uebersetzung ist keine Abbildung — Quellnummern "
            f"mehrfach: {doppelt_q[:5]}, Zielnummern mehrfach: {doppelt_z[:5]}; "
            "eine widerspruechliche Bruecke wird nicht wegreduziert, sondern "
            "abgewiesen")
    return {int(q): int(z)
            for q, z in zip(tabelle["quelle_police_id"], tabelle["ziel_police_id"])}


def uebersetzung_fehler(
    abbildung: Dict[int, int], bestand: "pd.DataFrame",
    band: Optional[Dict[str, int]] = None,
) -> List[str]:
    """Ist die Uebersetzung eine Bijektion auf den gefuehrten Bestand? Leer = ja.

    Ein gehashter Beleg sagt nur, dass die Datei nicht veraendert wurde —
    nicht, dass sie stimmt. Die Bruecke muss ausserdem VOLLSTAENDIG sein
    (jede gefuehrte Police hat genau eine Quellnummer), EINDEUTIG in
    beiden Richtungen und innerhalb des Nummernbands dieses Eingangs
    (Befund T26-13).
    """
    fehler: List[str] = []
    quellen, ziele = list(abbildung), list(abbildung.values())
    if len(set(ziele)) != len(ziele):
        fehler.append("Zielnummern sind nicht eindeutig — zwei Quellpolicen "
                      "zeigen auf dieselbe gefuehrte Police")
    gefuehrt = {int(p) for p in bestand["police_id"]}
    ohne_quelle = sorted(gefuehrt - set(ziele))
    ohne_ziel = sorted(set(ziele) - gefuehrt)
    if ohne_quelle:
        fehler.append(
            f"gefuehrte Policen ohne Quellnummer: {ohne_quelle[:5]} — die "
            "Rueckfrage nach ihrer Herkunft waere nicht beantwortbar")
    if ohne_ziel:
        fehler.append(
            f"Uebersetzung nennt Policen, die der Eingang nicht fuehrt: "
            f"{ohne_ziel[:5]}")
    if band and {"von", "bis"} <= set(band):
        von, bis = int(band["von"]), int(band["bis"])
        daneben = sorted(z for z in ziele if not von <= z <= bis)
        if daneben:
            fehler.append(
                f"Zielnummern ausserhalb des Bands {von}..{bis}: {daneben[:5]}")
        # Die Vergaberegel des Schreibers (eingang_anlegen): die i-te
        # kleinste Quellnummer bekommt von + i. Aus eingang.json ist die
        # Sollabbildung damit vollstaendig rekonstruierbar; eine
        # vertauschte oder verschobene Bruecke ist in sich stimmig und
        # trotzdem falsch (Angriffsrunde Betrieb) — sie beantwortet die
        # Rueckfrage "was ist aus eurer Police geworden?" falsch.
        soll = {q: von + i for i, q in enumerate(sorted(abbildung))}
        abweichend = sorted(q for q in abbildung if abbildung[q] != soll[q])
        if abweichend:
            fehler.append(
                f"Uebersetzung folgt nicht der Vergaberegel des Eingangs "
                f"(i-te Quellnummer -> {von} + i) fuer Quellpolicen "
                f"{abweichend[:5]}")
    if len(set(quellen)) != len(quellen):  # pragma: no cover - dict-Schluessel
        fehler.append("Quellnummern sind nicht eindeutig")
    return fehler


def quellnummern(eingang: Path) -> Dict[int, int]:
    """Zielnummer -> Quellnummer, die Gegenrichtung von :func:`zielnummern`.

    Die haeufigere Frage im Betrieb: "Diese Police fuehren wir unter 42 —
    wie hiess sie beim abgebenden Unternehmen?"
    """
    return {z: q for q, z in zielnummern(eingang).items()}


def vergebene_baender(uebernahme: Path) -> List[Dict[str, Any]]:
    """Die Nummernbaender der bereits registrierten Eingaenge, aufsteigend.

    Das Register ist kein eigenes Verzeichnis, das jemand pflegen muesste,
    sondern die Summe der Eingaenge selbst: Jeder nennt sein Band in
    ``eingang.json``. Eine gepflegte Liste veraltet genau dann, wenn sie
    gebraucht wird; eine abgeleitete kann es nicht.
    """
    uebernahme = Path(uebernahme)
    if not uebernahme.is_dir():
        return []
    baender: List[Dict[str, Any]] = []
    for kind in sorted(p for p in uebernahme.iterdir() if p.is_dir()):
        pfad = kind / EINGANG_DATEI
        if not pfad.is_file():
            continue
        try:
            daten = json.loads(pfad.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise UebernahmeError(
                f"{pfad}: nicht lesbar ({exc}) — ohne diesen Eingang ist nicht "
                "bestimmbar, welches Nummernband schon vergeben ist"
            ) from exc
        band = daten.get("band")
        if not isinstance(band, dict) or not isinstance(band.get("bis"), int):
            raise UebernahmeError(
                f"{pfad}: nennt kein Nummernband — ein Eingang ohne Band laesst "
                "sich nicht gegen den naechsten abgrenzen; Eingang neu anlegen"
            )
        baender.append({"fall": daten.get("fall"), "von": int(band["von"]), "bis": int(band["bis"])})
    return sorted(baender, key=lambda b: b["von"])


#: Sperrdatei des Eingangsschreibers, neben der Eingangswurzel.
EINGANG_SPERRE = "uebernahme.lock"


@contextlib.contextmanager
def eingang_sperre(stand: Path):
    """Exklusive Sperre fuer das Registrieren eines Eingangs (nicht blockierend).

    Das Register der Nummernbaender ist die Summe der Eingaenge selbst
    (:func:`vergebene_baender`) — es wird gelesen, um das naechste Band zu
    bestimmen, und durch die Publikation fortgeschrieben. Lesen und
    Fortschreiben muessen deshalb EIN Schritt sein.

    Ohne die Sperre bekamen zwei gleichzeitige Registrierungen dasselbe
    Band und veroeffentlichten beide erfolgreich; auffallen konnte das
    erst Tage spaeter im Tagesbetrieb, als "police_id-Kollision zwischen
    eigenem und uebernommenem Bestand" (Befund T26-14). Die Trennung der
    Zahlenraeume war damit nur behauptet.

    Nicht blockierend und mit Meldung, wie die Laufsperre: Ein zweiter
    Schreiber soll wissen, dass er wartet, statt es zu tun.
    """
    stand = Path(stand)
    stand.mkdir(parents=True, exist_ok=True)
    pfad = stand / EINGANG_SPERRE
    datei = open(pfad, "a+", encoding="utf-8")
    try:
        if fcntl is not None:
            try:
                fcntl.flock(datei.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (BlockingIOError, OSError) as exc:
                raise UebernahmeError(
                    f"{stand}: ein anderer Eingang wird gerade registriert "
                    f"({pfad.name}) — zwei Registrierungen zugleich teilen sich "
                    "sonst ein Nummernband; den laufenden Vorgang enden lassen"
                ) from exc
        yield
    finally:
        datei.close()


def baender_fehler(eintraege: List[Dict[str, Any]]) -> List[str]:
    """Ueberschneiden sich die Nummernbaender der Eingaenge? Leer = nein.

    Die Leseseite derselben Aussage. Eine Sperre schuetzt nur Prozesse,
    die sie nehmen; ob die Baender tatsaechlich disjunkt sind, steht in
    den Eingaengen und laesst sich jederzeit nachrechnen. Der Gutachter
    verlangt ausdruecklich beides (T26-14): gemeinsame Sperre UND
    Readersicherung gegen ueberlappende Baender.

    ``eintraege`` sind Paare aus Fallname und Band, aufsteigend nach
    ``von`` geprueft.
    """
    fehler: List[str] = []
    sortiert = sorted(eintraege, key=lambda e: (int(e["von"]), int(e["bis"])))
    for vorher, jetzt in zip(sortiert, sortiert[1:]):
        if int(jetzt["von"]) <= int(vorher["bis"]):
            fehler.append(
                f"Nummernbaender ueberschneiden sich: {vorher['fall']} "
                f"{vorher['von']}..{vorher['bis']} und {jetzt['fall']} "
                f"{jetzt['von']}..{jetzt['bis']} — zwei Faelle sprechen ueber "
                "dieselben Policennummern"
            )
    return fehler


def naechstes_band(uebernahme: Path, anzahl: int) -> Tuple[int, int]:
    """Das naechste freie Nummernband fuer ``anzahl`` Vertraege.

    Vergeben wird monoton hinter dem hoechsten belegten Band, in der
    Groesse, die die Lieferung braucht (aufgerundet auf
    :data:`BAND_SCHRITT`). Luecken entstehen nicht, weil Eingaenge nie
    geloescht werden; ein freigewordenes Band wieder zu vergeben hiesse,
    zwei Faelle ueber dieselben Nummern sprechen zu lassen.
    """
    if anzahl <= 0:
        raise UebernahmeError("Nummernband fuer null Vertraege — der Zugangsstand ist leer")
    belegt = vergebene_baender(uebernahme)
    von = (belegt[-1]["bis"] + 1) if belegt else 1
    breite = -(-int(anzahl) // BAND_SCHRITT) * BAND_SCHRITT
    bis = von + breite - 1
    if bis > NAMENSRAUM_UEBERNAHME_BIS:
        raise UebernahmeError(
            f"Nummernraum erschoepft: {anzahl} Vertraege brauchen das Band "
            f"{von}..{bis}, frei ist nur bis {NAMENSRAUM_UEBERNAHME_BIS} "
            f"({len(belegt)} Eingaenge bereits registriert). Der Ausweg ist ein "
            "eigener Nummernkreis fuer Uebernahmen (configs, [[generation]] "
            "nummernkreis) — nicht das stille Ueberlaufen in den Zahlenraum "
            "des Eigengeschaefts"
        )
    return von, bis


def pruefe_am4_snapshot(
    fall: Path, snapshot_sha256: Optional[str], *, ordnung: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Die Zeichnungsangaben des geprueften Snapshots (siehe
    :func:`lies_am4_snapshot`)."""
    daten, name, verifiziert = lies_am4_snapshot(fall, snapshot_sha256, ordnung=ordnung)
    return _zeichnung_aus_daten(daten, name, verifiziert=verifiziert)


#: Was ein Snapshot je Gate fuer die Uebernahme bedeutet — fuer die
#: Meldungen, die dem Bediener den Ausweg nennen. A-M4 begruendet die
#: Uebernahme, A-B2 den Eintritt in die Ablage (ADR-022).
_ABNAHME = {
    # A-M1 liest die Registrierung nicht fuer sich, sondern als Grundlage
    # der Zugangsprobe: Ihr Soll ist das Testergebnis, das der A-M1-Snapshot
    # pinnt, den A-M4 pinnt (Block F, Nachbesserung, Pruefer-Befund 1).
    "A-M1": ("aktuarielle Abnahme A-M1",
             "den Stichtagstest abnehmen (python -m rechner_pipeline.gates.gate_entscheid "
             "--gate A-M1), dann A-M4, Zugangsprobe und A-B2 auf ihm"),
    "A-M4": ("Migrationsabnahme",
             "--snapshot <sha256> oder ein gruenes A-M4-Gate-Ledger unter "
             "abgeleitet/diagnostics/"),
    "A-B2": ("Zugangsabnahme",
             "Zugangsprobe fahren (python -m rechner_pipeline.betrieb.zugangsprobe), "
             "A-B2 zeichnen (python -m rechner_pipeline.gates.gate_entscheid --gate "
             "A-B2), dann registrieren mit --zugangsabnahme <sha256> oder dem "
             "gruenen A-B2-Gate-Ledger unter abgeleitet/diagnostics/"),
}


def lies_am4_snapshot(
    fall: Path, snapshot_sha256: Optional[str], *,
    schluesselring: Optional[Mapping[str, bytes]] = None,
    ordnung: Optional[Mapping[str, Any]],
) -> Tuple[Dict[str, Any], str, bool]:
    """Den A-M4-Snapshot einer Uebernahme pruefen (siehe :func:`lies_abnahme_snapshot`)."""
    return lies_abnahme_snapshot(fall, "A-M4", snapshot_sha256, schluesselring=schluesselring,
                                 ordnung=ordnung)


def zeichnende_rolle(
    daten: Mapping[str, Any], gate: str, ordnung: Optional[Mapping[str, Any]], name: str,
) -> str:
    """Die Rolle, die einen Abnahme-Snapshot gezeichnet hat — oder Verweigerung.

    Der Betriebsweg der EINEN Regel ``models.zeichnung.zeichnende_rolle_fehler``
    (Entscheid des Maintainers 2026-10-01; dieselbe Funktion haelt das Gate
    fuer seine Vorbedingungen): Die Rolle kommt aus dem Fingerabdruck der
    Freigabe ueber die Zeichnungsordnung des Betriebs, sie muss ``gate``
    zeichnen duerfen, und der Snapshot muss genau sie als Rolle tragen. Bis
    zum Entscheid hielt der Betrieb nur die A-B2-Freigabe gegen die Ordnung;
    ein gueltig signierter A-M4-Snapshot eines Schluessels ohne A-M4
    begruendete eine Uebernahme. Die Signatur sagt, WELCHER Schluessel
    gezeichnet hat; erst die Ordnung sagt, wer das ist und ob er es darf.
    """
    from rechner_pipeline.models.zeichnung import zeichnende_rolle_fehler

    rolle, fehler = zeichnende_rolle_fehler(
        dict(daten), gate, dict(ordnung) if isinstance(ordnung, Mapping) else None)
    if fehler is not None or rolle is None:
        raise UebernahmeError(f"{name}: {_ABNAHME[gate][0]}: {fehler}")
    return rolle


def lies_abnahme_snapshot(
    fall: Path, gate: str, snapshot_sha256: Optional[str], *,
    schluesselring: Optional[Mapping[str, bytes]] = None,
    ordnung: Optional[Mapping[str, Any]],
) -> Tuple[Dict[str, Any], str, bool]:
    """Den Abnahme-Snapshot (A-M1, A-M4 oder A-B2) einer Uebernahme pruefen.

    Eine Pruefung fuer alle Abnahmen, auf denen ein Zugang steht
    (ADR-022): Schema, Selbstadressierung, Gate, Entscheid, Fall, exakte
    Belegrollenmenge (``models.belegrollen``: welche Pflichtbelege der
    Snapshot pinnt), geltende Spitze der Kette dieses Gates,
    Freigabesignatur — und die zeichnende Rolle gegen die Zeichnungsordnung
    des Betriebs (:func:`zeichnende_rolle`). ``ordnung`` ist deshalb
    Pflicht: Ein Leser ohne Ordnung waere ein Leseweg ohne Rollenpruefung.
    Die Zugangsabnahme wird nicht schwaecher gelesen als die
    Migrationsabnahme, und umgekehrt — zwei Lesewege waeren zwei Regeln.

    Review T22-06: ``eingang_anlegen`` las irgendeinen 64-stelligen Wert aus
    der editierbaren Gate-Summary, der Snapshot war optional, und
    :func:`zeichnung_aus_snapshot` uebernahm Felder ohne jede Pruefung — eine
    frei erfundene Datei ergab eine Uebernahme mit "Zeichnung". Jetzt gilt:
    ohne A-M4-Snapshot keine Uebernahme (eine Migration ohne
    Migrationsabnahme gibt es nicht); der Snapshot muss strukturell
    unversehrt sein (Schema, Selbstadressierung, Dateiname — dieselbe
    Pruefung wie in gates.gate_entscheid, hier ueber models.schemas), das
    Gate A-M4, der Entscheid angenommen und der Fall der Fall sein. Die
    SIGNATUR prueft auch das nicht (kein Schluesselring, T19-02) — deshalb
    heisst es weiter "Angaben der Snapshot-Datei", nie "gezeichnet".
    """
    from rechner_pipeline.models.schemas import P9Snapshot, p9_snapshot_sha256

    abnahme, ausweg = _ABNAHME[gate]
    if not snapshot_sha256:
        raise UebernahmeError(
            f"{fall}: kein {gate}-Snapshot — eine Uebernahme ohne {abnahme} "
            f"gibt es nicht ({ausweg})"
        )
    if not _ist_sha256(snapshot_sha256):
        raise UebernahmeError(f"snapshot_sha256 {snapshot_sha256!r} ist keine SHA-256")
    pfad = Path(fall) / "entscheide" / f"{gate}-{snapshot_sha256}.json"
    if not pfad.is_file():
        raise UebernahmeError(f"{pfad}: der {gate}-Snapshot liegt nicht im Fall")
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UebernahmeError(f"{pfad}: nicht lesbar: {exc}") from exc
    fehler = P9Snapshot.validate_payload(daten)
    if fehler:
        raise UebernahmeError(f"{pfad.name}: Snapshot verletzt sein Schema: " + "; ".join(fehler[:3]))
    if daten.get("snapshot_sha256") != p9_snapshot_sha256(daten) or daten["snapshot_sha256"] != snapshot_sha256:
        raise UebernahmeError(
            f"{pfad.name}: Selbstadressierung verletzt — Inhalt, behaupteter Hash und "
            "Dateiname stimmen nicht ueberein; die Datei ist kein Snapshot des Gates"
        )
    if daten.get("gate") != gate:
        raise UebernahmeError(f"{pfad.name}: Gate {daten.get('gate')!r} ist nicht {gate}")
    if daten.get("entscheid") != "angenommen":
        raise UebernahmeError(
            f"{pfad.name}: Entscheid {daten.get('entscheid')!r} — nur eine ANGENOMMENE "
            f"{abnahme} begruendet eine Uebernahme"
        )
    try:
        fallname = json.loads((Path(fall) / "fall.json").read_text(encoding="utf-8"))["name"]
    except (OSError, json.JSONDecodeError, KeyError):
        fallname = Path(fall).name
    if daten.get("fall") != fallname:
        raise UebernahmeError(
            f"{pfad.name}: der Snapshot gehoert zum Fall {daten.get('fall')!r}, "
            f"uebernommen wird {fallname!r}"
        )
    # Der aus dem Inhalt ableitbare Teil der Semantik (Befund T26-03).
    # Die FORM prueft das Schema; dass pflichtbelege['pk1_belege'] die
    # Generationen-Belegmenge ist, prueft niemand ausser dieser Stelle
    # und dem Gate — und beide ueber dieselbe Funktion in models.
    # Der Rollenvertrag (models.belegrollen, T26-03 Weg 2): Ein Snapshot,
    # der nicht EXAKT die Pflichtrollen seines Scopes traegt — DoRAs
    # Fall: eine einzige Rolle pb1_ledger — ist keine Abnahme. Bis zum
    # Entscheid vom 2026-09-22 konnte der Betriebseingang das nicht
    # pruefen; jetzt liest er denselben Vertrag wie das Gate.
    from rechner_pipeline.models.belegrollen import BelegrollenFehler, belegrollen
    try:
        erwartete_rollen = belegrollen(gate, str(daten.get("fall_scope")))
    except BelegrollenFehler as exc:
        raise UebernahmeError(f"{pfad.name}: {exc}") from exc
    semantik = p9_semantik_fehler(daten, erwartete_rollen=erwartete_rollen)
    if semantik:
        raise UebernahmeError(
            f"{pfad.name}: Snapshot ist in sich nicht stimmig: "
            + "; ".join(semantik[:3]))
    # Gueltigkeit, nicht nur Echtheit (Pruefrunde T27, Befund 05): Der
    # Snapshot muss die GELTENDE SPITZE der A-M4-Kette des Falls sein.
    # Eine spaetere Ablehnung mit Vorgaengerbezug ueberholt eine alte
    # Annahme — das Gate liest die Kette so (ADR-008, ADR-010), der
    # Eingang liest sie ueber denselben Vertrag (models.snapshot_kette).
    _pruefe_geltende_spitze(Path(fall) / "entscheide", snapshot_sha256, pfad.name, daten,
                            fallname=fallname, schluesselring=schluesselring, gate=gate)
    # Der zweite Zeuge: die Freigabesignatur (models.freigabe, dieselbe
    # Pruefung wie im Gate). Ohne Ring bleibt "nicht verifiziert" ein
    # benannter Zustand; mit Ring ist eine falsche Signatur ein Abbruch.
    verifiziert = False
    if schluesselring:
        from rechner_pipeline.models.freigabe import pruefe_freigabe
        sig_fehler = pruefe_freigabe(daten, schluesselring)
        if sig_fehler:
            raise UebernahmeError(f"{pfad.name}: " + "; ".join(sig_fehler))
        verifiziert = True
    # Der dritte Zeuge: Wer gezeichnet hat, muss das Gate zeichnen duerfen
    # (Entscheid 2026-10-01). Nach der Signatur — eine Rolle aus einem
    # Fingerabdruck, dessen Signatur nicht stimmt, sagte nichts.
    zeichnende_rolle(daten, gate, ordnung, pfad.name)
    return daten, pfad.name, verifiziert


def _pruefe_geltende_spitze(
    verzeichnis: Path, snapshot_sha256: str, name: str, daten: Dict[str, Any],
    *, fallname: Optional[str] = None,
    schluesselring: Optional[Mapping[str, bytes]] = None,
    gate: str = "A-M4",
) -> None:
    """Die Kette des Gates (A-M4 bzw. A-B2) im Fall lesen und verlangen, dass
    ``snapshot_sha256`` ihre eindeutige Spitze ist.

    Jede ``<gate>-*.json`` unter ``entscheide/`` zaehlt — auch eine, die
    nicht das Schema erfuellt: Sie ist ein Fehler der Kette, kein Grund,
    sie zu ueberlesen. Der geprueft Snapshot selbst wird NICHT ein
    zweites Mal gelesen (T24-06: geprueft wird, was verwendet wird) —
    seine ``daten`` kommen vom Aufrufer. Belegt ist damit die
    Neuregistrierung NACH einer Ablehnung; ob ein frueher rechtmaessig
    uebernommener Bestand rueckwirkend zu loeschen waere, entscheidet
    nicht dieser Eingang.
    """
    from rechner_pipeline.models.snapshot_kette import (
        nachfolger_von,
        pruefe_snapshot_graph,
    )

    kette: Dict[str, Dict[str, Any]] = {}
    namen: Dict[str, str] = {}
    for eintrag in sorted(verzeichnis.glob(f"{gate}-*.json")):
        if eintrag.name == f"{gate}-{snapshot_sha256}.json":
            kette[snapshot_sha256] = daten
            namen[snapshot_sha256] = eintrag.name
            continue
        try:
            glied = json.loads(eintrag.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise UebernahmeError(
                f"{eintrag.name}: Glied der {gate}-Kette nicht lesbar ({exc}) — "
                "die geltende Spitze ist damit unbekannt") from exc
        if not isinstance(glied, dict):
            raise UebernahmeError(
                f"{eintrag.name}: Glied der {gate}-Kette ist kein Objekt — die "
                "geltende Spitze ist damit unbekannt")
        sha = str(glied.get("snapshot_sha256") or "")
        if not _ist_sha256(sha) or eintrag.name != f"{gate}-{sha}.json" \
                or not isinstance(glied.get("vorgaenger"), list):
            raise UebernahmeError(
                f"{eintrag.name}: Glied der {gate}-Kette ohne gueltige "
                "Selbstadressierung oder Vorgaengerliste — die geltende Spitze "
                "ist damit unbekannt")
        # Dieselbe Aufnahmeregel wie das Gate (_lade_snapshot_kette), nicht
        # nur dieselbe Graphregel (Angriffsrunde Betrieb: ein ungezeichnetes
        # oder fallfremdes Glied galt als gueltiger Nachfolger und meldete
        # "ueberholt", wo das Gate "Kette verletzt" sagt).
        glied_fehler = list(P9Snapshot.validate_payload(glied))
        if glied.get("snapshot_sha256") != p9_snapshot_sha256(glied):
            glied_fehler.append("Selbstadressierung verletzt")
        if glied.get("gate") != gate:
            glied_fehler.append(f"Gate {glied.get('gate')!r} statt {gate!r}")
        if fallname is not None and glied.get("fall") != fallname:
            glied_fehler.append(f"Fallbindung {glied.get('fall')!r} statt {fallname!r}")
        if schluesselring:
            from rechner_pipeline.models.freigabe import pruefe_freigabe
            glied_fehler.extend(pruefe_freigabe(glied, schluesselring))
        if glied_fehler:
            raise UebernahmeError(
                f"{eintrag.name}: Glied der {gate}-Kette ist kein gueltiger "
                "Snapshot — die Kette ist verletzt, die geltende Spitze "
                "unbekannt: " + "; ".join(glied_fehler[:3]))
        kette[sha] = glied
        namen[sha] = eintrag.name
    spitzen, fehler = pruefe_snapshot_graph(kette, namen)
    if fehler:
        raise UebernahmeError(
            f"{name}: die {gate}-Kette des Falls ist verletzt — " + "; ".join(fehler[:3]))
    if snapshot_sha256 not in spitzen:
        folgen = nachfolger_von(kette, snapshot_sha256)
        beschreibung = ", ".join(
            f"{namen[s]} (entscheid={kette[s].get('entscheid')!r})" for s in folgen)
        raise UebernahmeError(
            f"{name}: nicht die geltende Spitze der {gate}-Kette — ueberholt "
            f"durch {beschreibung or spitzen}. Uebernommen wird nur, was "
            "heute gilt; eine alte Annahme ist echt, aber nicht gueltig")


#: Die Verzeichnisse eines Falls, in denen Belege des Snapshot-Graphen
#: liegen. Der Eingang selbst wird NICHT gelesen (ADR-002: unantastbar,
#: und ein Beleg liegt dort ohnehin nicht).
BELEGORTE = ("abgeleitet", "entscheide")


def belegte_tabellen(fall: Path, snapshot: Dict[str, Any]) -> Dict[str, str]:
    """Welche Quelltabellen bezeugt der Beleggraph dieses Snapshots?

    Befund T26-03: Der Laufzeiteingang las die drei Quelltabellen, nummerierte
    sie um und registrierte sie — ohne jeden Bezug zu dem, was die
    Migrationsabnahme eigentlich abgenommen hat. "Kein Quelltabellenhash steht
    in den behaupteten Snapshot-Artefakten." Die Abnahme galt damit einem
    Stand, und uebernommen wurde ein anderer.

    Der Snapshot nennt seine Pflichtbelege als Hashes. Diese Funktion sucht
    die zugehoerigen Dateien IM FALL, liest ihre Eingabenbloecke
    (``input_hashes`` der Gate-Ledger, ``provenienz.eingaben`` der
    Producer-Belege) und sammelt daraus die Hashes der Quelltabellen.

    Geschluesselt wird nach dem PFAD, nicht nach dem Dateinamen. Ein Fall
    traegt denselben Tabellennamen an mehreren Orten, und alle sind
    richtig: ``abgeleitet/bestand/historie.parquet`` ist der uebernommene
    Stand, ``abgeleitet/bestand-nach/historie.parquet`` der
    fortgeschriebene. Auf den Namen verkuerzt sahen zwei Zeugen, die sich
    einig sind, wie ein Widerspruch aus — gemessen an einem echten Fall
    mit vier Verzeichnissen dieses Namens.

    Benannte Grenze: Gebunden wird, was der Graph NENNT. Ein aelterer
    P-B1-Ledger fuehrt etwa Bestand und Historie, aber nicht den Ledger.
    Der Eingang haelt fest, welche Tabellen belegt waren und welche nicht —
    eine Luecke, die im Eingang steht, ist etwas anderes als eine, die
    niemand sieht.
    """
    gesucht = {
        str(h)
        for hashes in (snapshot.get("pflichtbelege") or {}).values()
        if isinstance(hashes, list)
        for h in hashes
        if _ist_sha256(str(h))
    }
    if not gesucht:
        return {}
    # Auch der Uebernahmebeleg (Angriffsrunde nach T27): Er traegt die
    # Tarifwerk-Schalter der Abnahme; die Fuehrungsprobe bindet ihn.
    tabellen = {f"{n}.parquet" for n in list(PFLICHT) + list(OPTIONAL)} | set(BELEGE)
    gefunden: Dict[str, str] = {}
    for ort in BELEGORTE:
        wurzel = Path(fall) / ort
        if not wurzel.is_dir():
            continue
        for pfad in sorted(wurzel.rglob("*.json")):
            try:
                roh = pfad.read_bytes()
            except OSError:
                continue
            if sha256_bytes(roh) not in gesucht:
                continue
            try:
                daten = json.loads(roh.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError):
                continue
            if not isinstance(daten, dict):
                continue
            bloecke = [daten.get("input_hashes")]
            prov = daten.get("provenienz")
            if isinstance(prov, dict):
                bloecke.append(prov.get("eingaben"))
            for block in bloecke:
                if not isinstance(block, dict):
                    continue
                for rel, sha in block.items():
                    schluessel = _fallpfad(fall, rel)
                    if (Path(schluessel).name not in tabellen
                            or not _ist_sha256(str(sha))):
                        continue
                    vorher = gefunden.get(schluessel)
                    if vorher is not None and vorher != str(sha):
                        raise UebernahmeError(
                            f"{fall}: der Beleggraph widerspricht sich ueber "
                            f"{schluessel} ({vorher[:16]}… und "
                            f"{str(sha)[:16]}…) — zwei Belege sagen "
                            "Verschiedenes ueber DIESELBE Tabelle"
                        )
                    gefunden[schluessel] = str(sha)
    return gefunden


def _fallpfad(fall: Path, rel: object) -> str:
    """Einen Belegpfad auf den Fall beziehen, soweit er dazugehoert."""
    pfad = Path(str(rel))
    try:
        return str(pfad.resolve().relative_to(Path(fall).resolve()))
    except (ValueError, OSError):
        return str(pfad)


def bezeugter_hash(
    belegt: Dict[str, str], fall: Path, quell_pfad: Path, datei: str
) -> Optional[str]:
    """Welchen Hash bezeugt der Graph fuer GENAU diese Datei?

    Erst der Pfad, dann — wenn der Graph diesen Ort nicht kennt — der
    Name, aber nur wenn er eindeutig ist. Mehrere gleichnamige Tabellen
    an verschiedenen Orten sind der Normalfall eines Falls; welche davon
    uebernommen wird, entscheidet der Pfad und nicht die Hoffnung.
    """
    schluessel = _fallpfad(fall, quell_pfad)
    if schluessel in belegt:
        return belegt[schluessel]
    treffer = {sha for pfad, sha in belegt.items() if Path(pfad).name == datei}
    return treffer.pop() if len(treffer) == 1 else None


def _zeichnung_aus_daten(
    daten: Dict[str, Any], quelle: str, *, verifiziert: bool = False,
) -> Dict[str, Any]:
    """Die Zeichnungsangaben aus einem BEREITS GELESENEN Snapshot.

    Der Weg, auf dem Pruefung und Auswertung dieselben Bytes benutzen.
    Wer erst prueft und dann neu liest, prueft eine andere Datei als die,
    die er auswertet.
    """
    freigabe = daten.get("freigabe") or {}
    zeichnung = daten.get("zeichnung") or {}
    schluessel = str(freigabe.get("schluessel_sha256") or "")
    return {
        "gate": str(daten.get("gate") or "A-M4"),
        "entscheid": str(daten.get("entscheid") or NICHT_AUSGEWIESEN),
        "rolle": str(daten.get("rolle") or NICHT_AUSGEWIESEN),
        "entscheider": str(daten.get("entscheider") or zeichnung.get("rolle") or NICHT_AUSGEWIESEN),
        # Die Schluesselklasse fuehren erst Snapshots ab dem Vier-Rollen-
        # Modell; ein Altsnapshot (Schema 6) traegt sie nicht.
        "schluesselklasse": str(
            zeichnung.get("schluesselklasse") or freigabe.get("schluesselklasse")
            or NICHT_AUSGEWIESEN),
        "schluessel_sha256": schluessel[:16] if schluessel else NICHT_AUSGEWIESEN,
        # Das Mandat einer simulierten Rolle wandert mit (Review T23-06):
        # eine Simulation ohne Mandat ist auch im Betriebseingang keine
        # Besetzung, sondern eine Luecke.
        "mandat_sha256": str(zeichnung.get("mandat_sha256") or NICHT_AUSGEWIESEN),
        "schema_version": daten.get("schema_version"),
        "signatur_verifiziert": bool(verifiziert),
        "quelle": quelle,
    }


def zeichnung_aus_snapshot(fall: Path, snapshot_sha256: Optional[str]) -> Dict[str, Any]:
    """Rolle, Entscheider und Schluesselklasse der A-M4-Annahme aus dem Snapshot.

    Gelesen wird ``entscheide/A-M4-<sha256>.json`` des Falls — die Datei,
    die das Gate P9 geschrieben hat. Dieses Kommando prueft ihre Signatur
    NICHT (kein Schluesselring, T19-02); es uebernimmt die Angaben der
    Datei und benennt sie so. Fehlt der Snapshot, ist jede Angabe
    ``nicht ausgewiesen``.
    """
    leer = {
        "gate": "A-M4", "entscheid": NICHT_AUSGEWIESEN, "rolle": NICHT_AUSGEWIESEN,
        "entscheider": NICHT_AUSGEWIESEN, "schluesselklasse": NICHT_AUSGEWIESEN,
        "schluessel_sha256": NICHT_AUSGEWIESEN, "schema_version": None,
        "signatur_verifiziert": False,
        "quelle": "kein A-M4-Snapshot im Fall gefunden",
    }
    if not snapshot_sha256:
        return leer
    pfad = Path(fall) / "entscheide" / f"A-M4-{snapshot_sha256}.json"
    if not pfad.is_file():
        return leer
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {**leer, "quelle": f"{pfad.name} nicht lesbar"}
    return _zeichnung_aus_daten(daten, pfad.name)


@dataclasses.dataclass
class Uebernahme:
    fall: str
    stichtag: _dt.date
    snapshot_sha256: Optional[str]
    zeichnung: Dict[str, Any]
    verzeichnis: Path
    manifest_pfad: Path
    bestand: pd.DataFrame
    historie: pd.DataFrame
    ledger: pd.DataFrame
    merkmale: Optional[pd.DataFrame]
    verankerung: Optional[pd.DataFrame]
    scheiben: Optional[pd.DataFrame]
    schichten: Optional[pd.DataFrame]
    #: Der Uebernahmebeleg (uebernahme.json) — Modus und Tarifwerk-Schalter,
    #: gegen die die Config der Laufzeit gehalten wird; leer, wenn der
    #: Eingang keinen traegt (Zugaenge vor der Freischaltung).
    beleg: Dict[str, Any]
    #: Das Nummernband dieses Eingangs (``von``/``bis``). Es steht hier,
    #: damit der Leser die Disjunktheit nachrechnen kann, ohne eingang.json
    #: ein zweites Mal zu oeffnen (T26-14).
    band: Dict[str, int] = dataclasses.field(default_factory=dict)
    #: Quellnummer -> Zielnummer. Geprueft gelesen (T26-13), damit eine
    #: Rueckfrage nach der Herkunft einer Police beantwortbar bleibt.
    uebersetzung: Dict[int, int] = dataclasses.field(default_factory=dict)
    #: SHA-256 der eingang.json, wie sie gelesen wurde. Die Protokollzeile
    #: nennt ihn; ein spaeterer Lauf haelt den Eingang dagegen (Angriffsrunde
    #: nach T27: ein nach dem Eintritt stimmig umgeschriebener Eingang
    #: rechnete die Geschichte seit Betriebsbeginn neu).
    eingang_sha256: str = ""


def _zugangsabnahme_satz(daten: Dict[str, Any]) -> Dict[str, Any]:
    """Was die Betriebszeichnung einer zugangsabnahme.json deckt (alle Felder)."""
    rest = {k: v for k, v in daten.items() if k != "betriebszeichnung"}
    return {"zugangsabnahme": rest, "zeichnung": daten.get("betriebszeichnung")}


def _eingang_bytes(eingang: Dict[str, Any]) -> bytes:
    """Die Bytes einer eingang.json — EINE Serialisierung fuer Registrierung
    und Zugangsprobe, sonst bindet A-B2 einen Eingang, den niemand schreibt."""
    return (json.dumps(eingang, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n").encode("utf-8")


def _felder_verschieden(soll: Any, ist: Any) -> List[str]:
    """Die obersten Felder zweier Eingaenge, die sich unterscheiden."""
    if not isinstance(soll, dict) or not isinstance(ist, dict):
        return ["(ganzer Eingang)"]
    return sorted(k for k in set(soll) | set(ist) if soll.get(k) != ist.get(k))


def _zugangsabnahme_binden(
    fall: Path, fallname: str, ab2: Dict[str, Any], ab2_name: str, *,
    stand_sha256: str, eingang: Dict[str, Any], am4_sha256: str,
    zeichner: Any, am4: Dict[str, Any],
    schluesselring: Optional[Mapping[str, bytes]] = None,
    ab2_verifiziert: bool = True,
) -> Dict[str, Any]:
    """Den A-B2-Snapshot an DIESEN Eingang und DIESEN Stand binden (ADR-022).

    Der Snapshot (Schema, Kette, Freigabesignatur: :func:`lies_abnahme_snapshot`)
    pinnt drei Belege. Jeder wird hier gegen das gehalten, was die
    Registrierung gerade schreibt:

    * ``am4_snapshot`` — der A-M4-Snapshot, den die Registrierung prueft;
    * ``eingang`` — der Hash GENAU der eingang.json, die sie schreibt
      (abweichende Felder werden genannt: meist ein anderes Nummernband,
      weil inzwischen ein anderer Eingang registriert wurde, oder eine
      anders geschriebene ``--fall``-Angabe);
    * ``zugangsprobe`` — der Beleg der Probe am festen Ort im Fall, mit
      Betriebszeichnung (nachgerechnet mit dem Betriebsschluessel), dem
      nachgerechneten Urteil und dem Stand der Ablage, auf dem die Probe
      lief: Er muss der gefuehrte Stand JETZT sein. Lief die Ablage nach
      der Probe weiter, ist die Abnahme eine ueber einen anderen Stand.

    Block F, Nachbesserung: Das Soll der Probe muss das der GELTENDEN
    Abnahmen sein (``models.zugangsprobe.soll_bindung_fehler`` gegen den
    A-M4-Snapshot ``am4`` und den A-M1-Snapshot, den er pinnt — geltende
    Spitze, angenommen, Freigabesignatur), und die Freigabe der A-B2 muss
    von einem Schluessel stammen, dessen Rolle die Zeichnungsordnung des
    Betriebs fuer A-B2 berechtigt (Pruefer-Befunde 1 und 9).

    Rueckgabe: der ungezeichnete Satz der zugangsabnahme.json, samt der
    Bindung an Config, Kern und Code-Stand der Probe (``bindung``), die
    der Tageslauf beim tatsaechlichen Eintritt haelt.
    """
    from rechner_pipeline.betrieb._zeichnung import betriebszeichnung_fehler
    from rechner_pipeline.models import zugangsprobe as zp

    ausweg = ("Ausweg: Zugangsprobe auf dem heutigen Stand neu fahren, A-B2 neu "
              "zeichnen, dann registrieren")
    # Wer A-B2 gezeichnet hat — zuerst, vor jedem Inhalt, mit derselben Regel
    # wie fuer A-M4 und A-M1 (zeichnende_rolle). Der Leser hat sie schon
    # angewandt; hier wird die Rolle fuer die zugangsabnahme.json gebraucht,
    # und wer _zugangsabnahme_binden mit anders gelesenen Daten ruft,
    # bekommt dieselbe Pruefung.
    ordnung = zeichner.ordnung if isinstance(getattr(zeichner, "ordnung", None), dict) else None
    rolle = zeichnende_rolle(ab2, "A-B2", ordnung, ab2_name)
    eingang_sha = sha256_bytes(_eingang_bytes(eingang))
    belege = ab2.get("pflichtbelege") or {}
    if belege.get("am4_snapshot") != [am4_sha256]:
        raise UebernahmeError(
            f"{ab2_name}: A-B2 pinnt den A-M4-Snapshot {belege.get('am4_snapshot')}, "
            f"registriert wird auf {am4_sha256[:16]}… — die Zugangsabnahme gilt einer "
            f"anderen Migrationsabnahme. {ausweg}")
    beleg_pfad = Path(fall) / zp.BELEG_RELATIV
    try:
        roh = beleg_pfad.read_bytes()
    except OSError as exc:
        raise UebernahmeError(
            f"{beleg_pfad}: der Beleg der Zugangsprobe fehlt ({exc}) — A-B2 stuetzt "
            f"sich auf ihn. {ausweg}") from exc
    if belege.get("zugangsprobe") != [sha256_bytes(roh)]:
        raise UebernahmeError(
            f"{beleg_pfad}: nicht der Beleg, den A-B2 pinnt ({sha256_bytes(roh)[:16]}… "
            f"statt {belege.get('zugangsprobe')}) — die Probe wurde nach der Abnahme "
            f"neu gefahren oder der Beleg ersetzt. {ausweg}")
    try:
        beleg = json.loads(roh.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UebernahmeError(f"{beleg_pfad}: nicht lesbar: {exc}") from exc
    fehler = zp.beleg_fehler(beleg, ordnung=zeichner.ordnung)
    zeichnung = (betriebszeichnung_fehler(
        zp.signierter_satz(beleg), zeichner.ring, zeichner.ordnung, was="zugangsprobe.json")
        if isinstance(beleg, dict) else None)
    if fehler or zeichnung:
        raise UebernahmeError(
            f"{beleg_pfad}: der Beleg der Zugangsprobe verletzt seinen Vertrag — "
            + "; ".join((fehler + ([zeichnung] if zeichnung else []))[:4]))
    if beleg.get("bestanden") is not True:
        raise UebernahmeError(
            f"{beleg_pfad}: die Zugangsprobe ist nicht bestanden — eine Abnahme ohne "
            "gruene Probe hat keine Grundlage")
    if beleg.get("fall") != fallname or beleg.get("am4_snapshot_sha256") != am4_sha256:
        raise UebernahmeError(
            f"{beleg_pfad}: die Probe lief fuer {beleg.get('fall')!r} auf dem A-M4-Snapshot "
            f"{str(beleg.get('am4_snapshot_sha256'))[:16]}… — registriert wird {fallname!r} "
            f"auf {am4_sha256[:16]}…. {ausweg}")
    if belege.get("eingang") != [beleg["eingang"]["sha256"]]:
        raise UebernahmeError(
            f"{ab2_name}: A-B2 pinnt einen anderen Eingang als die Probe, auf die es "
            "sich stuetzt — Snapshot und Beleg gehoeren nicht zusammen")
    if beleg["eingang"]["sha256"] != eingang_sha:
        raise UebernahmeError(
            f"{fallname}: der Eingang, den diese Registrierung schriebe, ist nicht der, "
            f"den A-B2 abgenommen hat ({eingang_sha[:16]}… statt "
            f"{beleg['eingang']['sha256'][:16]}…); verschieden: "
            f"{', '.join(_felder_verschieden(beleg['eingang']['inhalt'], eingang))}. "
            "Die Registrierung braucht dieselben Angaben wie die Probe (--fall, "
            f"--quelle, Stichtag, Betriebsschluessel) und dieselbe Ablage. {ausweg}")
    if beleg["ablage_stand"]["sha256"] != stand_sha256:
        raise UebernahmeError(
            f"{fallname}: A-B2 bindet den Stand der Ablage "
            f"{beleg['ablage_stand']['sha256'][:16]}… (gefuehrt bis "
            f"{beleg['ablage_stand']['inhalt'].get('gefuehrter_tag')}), die Ablage steht "
            f"jetzt auf {stand_sha256[:16]}… — sie lief nach der Probe weiter, oder ihre "
            f"Config wurde getauscht (ADR-022). {ausweg}")
    # Das Soll der Probe: die Bytes, die die geltenden Abnahmen pinnen.
    am1_pin = (am4.get("pflichtbelege") or {}).get("am1_snapshot") or [None]
    am1: Optional[Dict[str, Any]] = None
    if _ist_sha256(am1_pin[0]):
        am1, _, _ = lies_abnahme_snapshot(fall, "A-M1", am1_pin[0], schluesselring=schluesselring,
                                          ordnung=ordnung)
    soll_fehler = zp.soll_bindung_fehler(beleg.get("abnahmen"), am4=am4, am1=am1)
    if soll_fehler:
        raise UebernahmeError(
            f"{beleg_pfad}: das Soll der Probe ist nicht das der geltenden Abnahmen — "
            + "; ".join(soll_fehler[:3]) + f". {ausweg}")
    system = beleg.get("system") if isinstance(beleg.get("system"), dict) else {}
    return {
        "schema_version": ZUGANGSABNAHME_SCHEMA_VERSION,
        "fall": fallname,
        "eingang_sha256": eingang_sha,
        "ablage_stand_sha256": stand_sha256,
        "am4_snapshot_sha256": am4_sha256,
        "zugangsprobe_sha256": sha256_bytes(roh),
        "abnahmen": beleg["abnahmen"],
        # Was sich durch den Betrieb nicht aendert: Der Tageslauf haelt es
        # beim tatsaechlichen Eintritt gegen den Lauf (pruefe_eintritt).
        "bindung": {
            "config_sha256": beleg.get("config_sha256"),
            "kern_version": beleg.get("kern_version"),
            "code": {f: system.get(f) for f in zp.CODE_STAND_FELDER},
        },
        "a_b2": {**_zeichnung_aus_daten(ab2, ab2_name, verifiziert=ab2_verifiziert),
                 "snapshot_sha256": str(ab2.get("snapshot_sha256")),
                 "freigabe_rolle": rolle},
    }


def _lies_zugangsabnahme(
    ueb: "Uebernahme", *, schluesselring: Optional[Mapping[str, bytes]],
    ordnung: Optional[Dict[str, Any]], ausweg: str,
) -> Tuple[Path, Dict[str, Any]]:
    """zugangsabnahme.json eines Eingangs lesen und ihre Zeichnung und
    Grundbindungen pruefen — EIN Leseweg fuer Aufnahme und Eintritt."""
    from rechner_pipeline.betrieb._zeichnung import betriebszeichnung_fehler

    pfad = ueb.verzeichnis / ZUGANGSABNAHME_DATEI
    if not pfad.is_file():
        raise UebernahmeError(
            f"{ueb.verzeichnis}: Eingang ohne Zugangsabnahme A-B2 ({pfad.name} fehlt) — "
            f"ohne A-B2 kein Eintritt (ADR-022). {ausweg}")
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UebernahmeError(f"{pfad}: nicht lesbar: {exc}") from exc
    if not isinstance(daten, dict):
        raise UebernahmeError(f"{pfad}: kein JSON-Objekt")
    zeichnung = betriebszeichnung_fehler(
        _zugangsabnahme_satz(daten),
        dict(schluesselring) if schluesselring is not None else None, ordnung,
        was=pfad.name)
    if zeichnung:
        raise UebernahmeError(f"{pfad}: {zeichnung} — die Zugangsabnahme ist unantastbar. {ausweg}")
    a_b2 = daten.get("a_b2") or {}
    fehler: List[str] = []
    if daten.get("schema_version") != ZUGANGSABNAHME_SCHEMA_VERSION:
        fehler.append(f"schema_version {daten.get('schema_version')!r}")
    if daten.get("fall") != ueb.fall:
        fehler.append(f"gehoert zum Fall {daten.get('fall')!r}, nicht {ueb.fall!r}")
    if not (a_b2.get("gate") == "A-B2" and a_b2.get("entscheid") == "angenommen"
            and a_b2.get("signatur_verifiziert") is True):
        fehler.append("keine angenommene A-B2 mit verifizierter Freigabesignatur")
    if daten.get("am4_snapshot_sha256") != ueb.snapshot_sha256:
        fehler.append("bindet einen anderen A-M4-Snapshot als der Eingang")
    if daten.get("eingang_sha256") != ueb.eingang_sha256:
        fehler.append(
            f"bindet den Eingang {str(daten.get('eingang_sha256'))[:16]}…, eingetreten "
            f"waere {ueb.eingang_sha256[:16]}… — ein fremder oder veraenderter Eingang")
    if fehler:
        raise UebernahmeError(f"{pfad}: " + "; ".join(fehler) + f". {ausweg}")
    return pfad, daten


_AUSWEG_EINTRITT = (
    "Ausweg: Zugangsprobe auf dem heutigen Stand fahren, A-B2 zeichnen; der "
    "Eingang ist nie eingetreten — ihn aus uebernahme/ entfernen (sichern) und "
    "mit der neuen Abnahme registrieren")


def pruefe_zugangsabnahme(
    ueb: "Uebernahme", stand_sha256: str, *,
    schluesselring: Optional[Mapping[str, bytes]],
    ordnung: Optional[Dict[str, Any]],
) -> None:
    """Die Aufnahme eines Eingangs verlangt seine Zugangsabnahme (ADR-022).

    Gelesen wird ``zugangsabnahme.json`` des Eingangs: von der Registrierung
    mit dem Betriebsschluessel gezeichnet, nachdem sie A-B2 samt
    Freigabesignatur geprueft hat. Sie muss DIESEN Eingang binden (Hash der
    eingang.json, wie der Leser sie gelesen hat) und den gefuehrten Stand,
    auf dem der Eingang jetzt aufgenommen wird — ``stand_sha256`` rechnet
    der Tageslauf vor seinem Lauf. Ohne sie, mit fremdem Eingang oder mit
    einem anderen Stand wird er nicht aufgenommen; der Lauf ist rot, der
    Stand bleibt. Den tatsaechlichen Eintritt fragt :func:`pruefe_eintritt`.
    """
    pfad, daten = _lies_zugangsabnahme(
        ueb, schluesselring=schluesselring, ordnung=ordnung, ausweg=_AUSWEG_EINTRITT)
    if daten.get("ablage_stand_sha256") != stand_sha256:
        raise UebernahmeError(
            f"{pfad}: A-B2 bindet den Stand der Ablage "
            f"{str(daten.get('ablage_stand_sha256'))[:16]}…, eintreten wuerde der Eingang "
            f"auf {stand_sha256[:16]}… — die Ablage lief nach der Probe weiter oder ihre "
            f"Config wurde getauscht, die Abnahme gilt einem anderen Stand. {_AUSWEG_EINTRITT}")


def pruefe_eintritt(
    ueb: "Uebernahme", *, config_sha256: Optional[str], kern_version: Optional[str],
    code: Mapping[str, Any],
    schluesselring: Optional[Mapping[str, bytes]],
    ordnung: Optional[Dict[str, Any]],
) -> None:
    """Der TATSAECHLICHE Eintritt eines Eingangs in die Buecher (Block F,
    Nachbesserung, Pruefer-Befund 2).

    Ein vorausdatierter Eingang wird wartend aufgenommen — dort haelt
    :func:`pruefe_zugangsabnahme` den Stand — und tritt erst an seinem
    Stichtag ein. Dazwischen laeuft die Ablage weiter; das aendert den Stand,
    aber nicht, WOMIT gerechnet wird. Config, Kern-Version und Code-Stand
    (Image-Digest und Revision, soweit die Probe sie erfasst hat, und der
    Hash des Pakets) muessen am Eintritt die sein, auf denen die Probe lief.
    Sonst tritt der Zugang auf einem Stand ein, den niemand geprobt hat.
    """
    from rechner_pipeline.betrieb.tageslauf import NICHT_ERFASST
    from rechner_pipeline.models import zugangsprobe as zp

    ausweg = (
        "Ausweg: Zugangsprobe und A-B2 auf dem heutigen Stand neu (der Eingang ist "
        "nie eingetreten — ihn aus uebernahme/ sichern und entfernen, dann mit der "
        "neuen Abnahme registrieren), oder Config, Kern und Image der Probe "
        "wiederherstellen")
    pfad, daten = _lies_zugangsabnahme(
        ueb, schluesselring=schluesselring, ordnung=ordnung, ausweg=ausweg)
    bindung = daten.get("bindung")
    if not isinstance(bindung, dict) or not isinstance(bindung.get("code"), dict):
        raise UebernahmeError(f"{pfad}: ohne Bindung an Config, Kern und Code-Stand. {ausweg}")
    abweichend: List[str] = []
    if bindung.get("config_sha256") != config_sha256:
        abweichend.append(
            f"Config {str(config_sha256)[:16]}… statt {str(bindung.get('config_sha256'))[:16]}…")
    if bindung.get("kern_version") != kern_version:
        abweichend.append(f"Kern {kern_version!r} statt {bindung.get('kern_version')!r}")
    abweichend += zp.code_stand_abweichungen(bindung["code"], code, nicht_erfasst=NICHT_ERFASST)
    if not zp.code_stand_belegt(bindung["code"], nicht_erfasst=NICHT_ERFASST):
        abweichend.append("die Abnahme belegt keinen Code-Stand")
    if abweichend:
        raise UebernahmeError(
            f"{pfad}: der Eingang traete am {ueb.stichtag.isoformat()} auf einem anderen "
            "Stand ein, als die Zugangsprobe geprobt hat — " + "; ".join(abweichend)
            + f". {ausweg}")


def tarifwerk_fehler(config: BestandConfig, generationen: Iterable[str], beleg: Dict[str, Any]) -> List[str]:
    """Die Config der Laufzeit muss fuer die uebernommenen Generationen die
    Tarifwerk-Schalter tragen, mit denen ihre Abnahmen bestanden wurden
    (Freischaltung, Schritt 2 und 9). Leer = in Ordnung."""
    soll = beleg.get("tarifwerk")
    if not isinstance(soll, dict):
        # Ein Beleg ohne Tarifwerk ist keine Erlaubnis, sondern eine Luecke
        # (Angriffsrunde nach T27): Vorher war er "in Ordnung", und ein
        # entfernter oder geleerter Beleg umging die Pruefung ganz.
        return ["der Uebernahmebeleg nennt kein Tarifwerk — gegen welche Schalter "
                "die Abnahmen bestanden wurden, ist nicht ablesbar"]
    fehler: List[str] = []
    for name in sorted(set(generationen)):
        gen = next((g for g in config.generationen if g.name == name), None)
        if gen is None:
            continue
        ist = gen.tarifwerk()
        abweichend = {k: (ist.get(k), v) for k, v in soll.items() if ist.get(k) != v}
        if abweichend:
            fehler.append(
                f"Generation {name}: Tarifwerk der Config weicht vom Uebernahmebeleg ab — "
                + ", ".join(f"{k}: Config {i!r}, Beleg {s!r}" for k, (i, s) in sorted(abweichend.items()))
                + " — den Config-Abschnitt aus abgeleitet/bestand/generation-zellen.toml "
                "des Falls uebernehmen, nicht abtippen"
            )
    return fehler


def _lies_eingang(verzeichnis: Path) -> Dict[str, Any]:
    return _lies_eingang_roh(verzeichnis)[0]


def _lies_eingang_roh(verzeichnis: Path) -> Tuple[Dict[str, Any], str]:
    """Die Eingangsdatei EINMAL lesen: Inhalt und Hash derselben Bytes."""
    pfad = verzeichnis / EINGANG_DATEI
    if not pfad.is_file():
        raise UebernahmeError(
            f"{verzeichnis}: keine {EINGANG_DATEI} — ein Uebernahme-Eingang wird "
            "mit python -m rechner_pipeline.betrieb.uebernahme angelegt, nicht "
            "von Hand kopiert"
        )
    try:
        roh = pfad.read_bytes()
        daten = json.loads(roh.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UebernahmeError(f"{pfad}: nicht lesbar: {exc}") from exc
    fehler = validate_eingang(daten)
    if fehler:
        raise UebernahmeError(f"{pfad}: " + "; ".join(fehler))
    return daten, sha256_bytes(roh)


def validate_eingang(daten: Any) -> List[str]:
    """Struktur-Contract der Eingangsdatei (Fehlerlisten-Idiom)."""
    fehler: List[str] = []
    if not isinstance(daten, dict):
        return ["Eingang ist kein JSON-Objekt"]
    if daten.get("schema_version") not in (EINGANG_SCHEMA_ALT, EINGANG_SCHEMA_VERSION):
        # Den AUSWEG nennen, nicht nur den Befund (Betriebsbefund
        # 2026-09-16): Eine Ablage, deren Eingang aus einem aelteren
        # Codestand stammt, bricht den Tageslauf hart ab — und die
        # naheliegende Reaktion ist die falsche. Wer hier nur
        # "erwartet 2" liest, schreibt die 2 in die Datei und hat dann
        # einen Eingang, der Schema 2 BEHAUPTET, ohne Nummernband und
        # ohne Uebersetzungstabelle. Ein Eingang wird nie umgeschrieben;
        # der Weg ist die Neuaufsetzung der Ablage aus dem Fall.
        fehler.append(
            f"schema_version {daten.get('schema_version')!r}, erwartet "
            f"{EINGANG_SCHEMA_VERSION} — ein Eingang wird nie umgeschrieben "
            "(eine neue Lieferung ist ein neuer Eingang). Der Weg ist "
            "'python -m rechner_pipeline.betrieb.neuaufsetzen --stand "
            "<ablage> --fall faelle/<fall> --stichtag <ISO>': Die "
            "Umnummerierung geschieht beim Registrieren, die Gates werden "
            "NICHT neu gezeichnet"
        )
    if daten.get("schema_version") == EINGANG_SCHEMA_VERSION and not isinstance(
            daten.get("betriebszeichnung"), dict):
        fehler.append(
            "betriebszeichnung fehlt — ein Eingang nach Schema 3 ist von der "
            "Registrierung mit dem Betriebsschluessel gezeichnet")
    if not isinstance(daten.get("fall"), str) or not daten["fall"].strip():
        fehler.append("fall fehlt")
    try:
        _dt.date.fromisoformat(str(daten.get("stichtag")))
    except ValueError:
        fehler.append(f"stichtag {daten.get('stichtag')!r} ist kein ISO-Datum")
    # Der Eingang MUSS seine Abnahme nennen (Review T24-06, Teil B): Der
    # Schreibpfad (eingang_anlegen -> pruefe_am4_snapshot) laesst keine
    # Uebernahme ohne angenommenes A-M4 zu, der Leser nahm bisher aber
    # jede Tabelle an, die er vorfand — snapshot_sha256 = None war
    # fehlerfrei, und eine Zeichnung mit gate "KEIN-GATE" ebenso.
    # Nachgemessen: ein von Hand editierter Eingang (0644, Feld getauscht,
    # 0444) kam durch. Eine Regel, die nur der Schreiber kennt, schuetzt
    # den nicht, der die Bytes spaeter liest — und gelesen wird der
    # Eingang bei JEDEM Tageslauf.
    snapshot = daten.get("snapshot_sha256")
    if not _ist_sha256(snapshot):
        fehler.append(
            f"snapshot_sha256 {snapshot!r} ist keine SHA-256 — eine Uebernahme "
            "ohne Migrationsabnahme gibt es nicht (A-M4)"
        )
    zeichnung = daten.get("zeichnung")
    if not isinstance(zeichnung, dict):
        fehler.append(
            "zeichnung fehlt oder ist keine Tabelle — der Eingang berichtet die "
            "Rollenbindung seines A-M4-Snapshots"
        )
    else:
        if zeichnung.get("gate") != "A-M4":
            fehler.append(
                f"zeichnung.gate {zeichnung.get('gate')!r} ist nicht A-M4 — nur die "
                "Migrationsabnahme begruendet eine Uebernahme"
            )
        if zeichnung.get("entscheid") != "angenommen":
            fehler.append(
                f"zeichnung.entscheid {zeichnung.get('entscheid')!r} — nur eine "
                "ANGENOMMENE Migrationsabnahme begruendet eine Uebernahme"
            )
        # Der Eingang berichtet die Rollenbindung des A-M4-Snapshots; er
        # darf keine Schluesselklasse behaupten, die es nicht gibt, und
        # eine Simulation nicht ohne Mandat (Review T23-06, ADR-018). Die
        # Signatur selbst prueft dieses Kommando weiterhin nicht (T19-02).
        klasse = zeichnung.get("schluesselklasse", NICHT_AUSGEWIESEN)
        if klasse not in ZEICHNENDE_KLASSEN + (NICHT_AUSGEWIESEN,):
            fehler.append(
                f"zeichnung.schluesselklasse {klasse!r} ist keine zeichnende "
                f"Schluesselklasse ({', '.join(ZEICHNENDE_KLASSEN)}; ein Agent "
                "zeichnet nicht, ADR-018)"
            )
        if klasse == "simulation" and not _ist_sha256(zeichnung.get("mandat_sha256")):
            fehler.append(
                "zeichnung: Schluesselklasse simulation ohne mandat_sha256 — "
                "eine simulierte Rolle handelt unter einem Mandat (ADR-018); "
                "der A-M4-Snapshot muss das Mandat tragen"
            )
    # Das Nummernband (Review T24-08): Ohne Band laesst sich dieser Eingang
    # nicht gegen den naechsten abgrenzen, und zwei Faelle koennten
    # dieselben Nummern fuehren. Die Kollision zweier UEBERNOMMENER
    # Bestaende faellt spaeter auf als die mit dem Eigengeschaeft, weil
    # beide Seiten fremd sind und keine Zusicherung sie trennt.
    band = daten.get("band")
    if not isinstance(band, dict):
        fehler.append("band fehlt — ein Eingang ohne Nummernband grenzt sich gegen keinen anderen ab")
    else:
        von, bis = band.get("von"), band.get("bis")
        if not isinstance(von, int) or not isinstance(bis, int) or von < 1 or bis < von:
            fehler.append(f"band {von!r}..{bis!r} ist kein Nummernband")
        elif bis > NAMENSRAUM_UEBERNAHME_BIS:
            fehler.append(
                f"band endet bei {bis}, der freie Raum reicht bis "
                f"{NAMENSRAUM_UEBERNAHME_BIS} — darueber beginnt das Eigengeschaeft")
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
        if POLICENNUMMERN_DATEI not in dateien:
            fehler.append(
                f"dateien: {POLICENNUMMERN_DATEI} fehlt — der Betrieb fuehrt eigene "
                "Policennummern, und ohne die Uebersetzung ist eine Rueckfrage an "
                "die Quelle nicht beantwortbar")
    return fehler


def _ist_sha256(wert: Any) -> bool:
    return isinstance(wert, str) and len(wert) == 64 and all(c in "0123456789abcdef" for c in wert)


def betriebszeichnung_des_eingangs_fehler(
    eingang: Dict[str, Any],
    schluesselring: Optional[Mapping[str, bytes]],
    ordnung: Optional[Dict[str, Any]],
) -> Optional[str]:
    """Die Betriebszeichnung einer eingang.json pruefen (None = in Ordnung).

    Gezeichnet ist ``{"eingang": <alle Felder ausser der Zeichnung>}`` — der
    Eingang traegt unter ``zeichnung`` schon den Block seiner A-M4-Annahme,
    und die Betriebszeichnung darf ihn nicht verdecken, sondern muss ihn
    mit abdecken.
    """
    from rechner_pipeline.betrieb._zeichnung import betriebszeichnung_fehler

    rest = {k: v for k, v in eingang.items() if k != "betriebszeichnung"}
    return betriebszeichnung_fehler(
        {"eingang": rest, "zeichnung": eingang.get("betriebszeichnung")},
        dict(schluesselring) if schluesselring is not None else None, ordnung,
        was="eingang.json")


def lies_uebernahme(
    verzeichnis: Path,
    config: BestandConfig,
    *,
    schluesselring: Optional[Mapping[str, bytes]] = None,
    ordnung: Optional[Dict[str, Any]] = None,
    bezeugt: Optional[set] = None,
) -> Uebernahme:
    """Einen Eingang lesen — jede Datei gegen ihre registrierte Summe.

    Mit ``schluesselring`` (der Betriebsschluessel des Tageslaufs) wird die
    Zeichnung der eingang.json geprueft; ein ungezeichneter Eingang nach
    Schema 2 tritt dann nur ein, wenn sein Hash in ``bezeugt`` steht — eine
    gruene, gezeichnete Protokollzeile oder eine Zeile des gepinnten
    Vorlaufs hat ihn schon gefuehrt (``tageslauf.bezeugte_eingaenge``).
    Ohne Ring wird die Form geprueft und die Zeichnung nicht behauptet.
    """
    verzeichnis = Path(verzeichnis)
    eingang, eingang_sha256 = _lies_eingang_roh(verzeichnis)
    if eingang.get("schema_version") == EINGANG_SCHEMA_VERSION:
        fehler = betriebszeichnung_des_eingangs_fehler(eingang, schluesselring, ordnung)
        if fehler:
            raise UebernahmeError(
                f"{verzeichnis}: {fehler} — ein Eingang ist unantastbar; den "
                "urspruenglichen Eingang wiederherstellen oder neu registrieren")
    elif schluesselring is not None and eingang_sha256 not in (bezeugt or set()):
        raise UebernahmeError(
            f"{verzeichnis}: Eingang nach Schema {eingang.get('schema_version')} ohne "
            "Betriebszeichnung, und weder eine gezeichnete Protokollzeile noch der "
            "gepinnte Vorlauf bezeugt ihn — "
            "ein ungezeichneter Eingang tritt nicht neu in die Fuehrung. Ausweg: den "
            "Eingang mit Betriebsschluessel neu registrieren (betrieb.neuaufsetzen)")
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
    # Die Bruecke gehoert zum Eingang wie jede Pflichttabelle: gelesen,
    # gegen ihre registrierte Summe gehalten und auf Bijektivitaet
    # geprueft (T26-13). Vorher las sie niemand — sie fehlte sogar in
    # dieser Schleife, obwohl das Manifest sie fuehrt.
    uebersetzung = zielnummern(verzeichnis)
    stichtag = _dt.date.fromisoformat(str(eingang["stichtag"]))
    if len(bestand) == 0:
        raise UebernahmeError(f"{verzeichnis}: leerer Zugangsstand")
    bruecke = uebersetzung_fehler(uebersetzung, bestand, eingang.get("band"))
    if bruecke:
        raise UebernahmeError(
            f"{verzeichnis}: die Uebersetzung Quell- zu Zielpolicen traegt "
            "nicht — " + "; ".join(bruecke[:3]))
    zugang = pd.to_datetime(bestand["bestandszugang"])
    if not (zugang == pd.Timestamp(stichtag)).all():
        raise UebernahmeError(
            f"{verzeichnis}: bestandszugang weicht vom Stichtag "
            f"{stichtag.isoformat()} ab — ein Zugang hat genau einen Stichtag"
        )
    # Dieselbe Pruefung wie das Gate, bevor irgendetwas davon in die
    # Fortschreibung geht (N-01) — der Eingang ist unantastbar, aber nicht
    # ungeprueft.
    nt_fehler = nebentabellen_fehler(
        bestand, tabellen["historie"], tabellen["scheiben"],
        tabellen["verankerung"], tabellen["schichten"],
    )
    if nt_fehler:
        raise UebernahmeError(
            f"{verzeichnis}: Nebentabellen des Eingangs bestehen die Pruefung "
            "des Gates nicht — " + "; ".join(nt_fehler[:5])
        )
    bekannt = {g.name for g in config.generationen}
    fremd = sorted(set(bestand["tarif_generation"]) - bekannt)
    if fremd:
        raise UebernahmeError(
            f"{verzeichnis}: Tarifgenerationen {fremd} nicht in der Config der "
            "PLV — die uebernommene Generation gehoert in configs/ (ohne Neuzugang)"
        )
    mit_zellen = {g.name for g in config.generationen if g.zellen}
    if (set(bestand["tarif_generation"]) & mit_zellen) and tabellen["merkmale"] is None:
        raise UebernahmeError(
            f"{verzeichnis}: die Generation ist in Tarifzellen aufgeteilt, der "
            "Eingang traegt aber keine merkmale.parquet — ohne sie waere jede "
            "Zelle geraten"
        )
    beleg: Dict[str, Any] = {}
    if "uebernahme.json" in eingang["dateien"]:
        pfad = verzeichnis / "uebernahme.json"
        if not pfad.is_file():
            raise UebernahmeError(f"{verzeichnis}: uebernahme.json ist registriert, fehlt aber")
        daten = pfad.read_bytes()
        if sha256_bytes(daten) != eingang["dateien"]["uebernahme.json"]:
            raise UebernahmeError(f"{pfad}: SHA-256 weicht von der registrierten Summe ab")
        try:
            beleg = json.loads(daten.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UebernahmeError(f"{pfad}: Uebernahmebeleg nicht lesbar: {exc}") from exc
        if not isinstance(beleg, dict):
            raise UebernahmeError(f"{pfad}: Uebernahmebeleg ist kein JSON-Objekt")
    # Die Fuehrung rechnet nach dem Tarifwerk der Generation (Freischaltung,
    # Schritt 4); die Config der Laufzeit muss dasselbe sagen wie der Beleg
    # der Uebernahme — sonst fuehrt der Betrieb eine andere Welt als die
    # Abnahmen, und genau das war der Befund T22-11.
    # Zwei Zeugen (Entscheid 2026-09-22): Ohne verifizierte Freigabesignatur
    # tritt kein Bestand in die Fuehrung — der Eingang traegt den Zustand,
    # den seine Registrierung hinterliess.
    if (eingang.get("zeichnung") or {}).get("signatur_verifiziert") is not True:
        raise UebernahmeError(
            f"{verzeichnis}: Eingang ohne verifizierte Freigabesignatur — "
            "mit --freigabe-schluessel registrieren (betrieb.uebernahme), "
            "sonst fuehrt der Betrieb eine unbezeugte Abnahme"
        )
    tw_fehler = tarifwerk_fehler(config, bestand["tarif_generation"], beleg)
    if tw_fehler:
        raise UebernahmeError(f"{verzeichnis}: " + "; ".join(tw_fehler))
    # Ratsche (Befund T26-12, Entscheid des Maintainers 2026-09-22): Was der
    # Betrieb fuehrt, muss er auch KOENNEN. Bekannt und uebertragen waren
    # die Schalter schon geprueft; die dritte Menge — produktiv
    # ausfuehrbar — pruefte niemand, und die Teilkuendigung der TG2015
    # (ihr Bedingungswerk, Ziffer 6) fiel im Lauf um. Hier beginnt die
    # Fuehrung: Eine uebernommene Generation, deren Tarifwerk der
    # produktive Pfad nicht rechnet, tritt nicht ein — Migration blockiert,
    # mit benanntem Bauauftrag, nie mit einem Config-Rat.
    from rechner_pipeline.bestand.config import bauauftrag_text, tarifwerk_luecken

    uebernommen = {str(g) for g in bestand["tarif_generation"]}
    luecken = tarifwerk_luecken(g for g in config.generationen if g.name in uebernommen)
    if luecken:
        raise UebernahmeError(
            f"{verzeichnis}: Migration blockiert — "
            + "; ".join(bauauftrag_text(*l) for l in luecken)
        )
    return Uebernahme(
        fall=str(eingang["fall"]),
        stichtag=stichtag,
        snapshot_sha256=eingang.get("snapshot_sha256"),
        zeichnung=dict(eingang.get("zeichnung") or zeichnung_aus_snapshot(Path("."), None)),
        verzeichnis=verzeichnis,
        manifest_pfad=verzeichnis / EINGANG_DATEI,
        bestand=bestand,
        historie=tabellen["historie"],
        ledger=tabellen["ledger"],
        merkmale=tabellen["merkmale"],
        verankerung=tabellen["verankerung"],
        scheiben=tabellen["scheiben"],
        schichten=tabellen["schichten"],
        beleg=beleg,
        band={k: int(v) for k, v in (eingang.get("band") or {}).items()},
        uebersetzung=uebersetzung,
        eingang_sha256=eingang_sha256,
    )


def lies_uebernahmen(
    wurzel: Path,
    config: BestandConfig,
    *,
    schluesselring: Optional[Mapping[str, bytes]] = None,
    ordnung: Optional[Dict[str, Any]] = None,
    bezeugt: Optional[set] = None,
) -> List[Uebernahme]:
    """Alle Eingaenge unter ``uebernahme/`` (sortiert nach Fallname); leer ohne
    Verzeichnis. Ring, Ordnung und bezeugte Hashes wie :func:`lies_uebernahme`."""
    wurzel = Path(wurzel)
    if not wurzel.is_dir():
        return []
    eingaenge = [
        lies_uebernahme(p, config, schluesselring=schluesselring, ordnung=ordnung,
                        bezeugt=bezeugt)
        for p in sorted(wurzel.iterdir()) if p.is_dir()]
    faelle = [u.fall for u in eingaenge]
    if len(faelle) != len(set(faelle)):
        raise UebernahmeError(f"uebernahme: Fallname doppelt: {faelle}")
    # Die Baender muessen disjunkt sein — geprueft beim LESEN, nicht nur
    # verhindert beim Schreiben (T26-14). Eine Sperre schuetzt nur
    # Prozesse, die sie nehmen; ob die Trennung der Zahlenraeume
    # tatsaechlich gilt, steht in den Eingaengen und wird hier
    # nachgerechnet. Vorher fiel eine Ueberschneidung erst Tage spaeter im
    # Tagesbetrieb auf, als Policennummern-Kollision.
    fehler = baender_fehler([
        {"fall": u.fall, "von": u.band["von"], "bis": u.band["bis"]}
        for u in eingaenge if {"von", "bis"} <= set(u.band)
    ])
    if fehler:
        raise UebernahmeError("; ".join(fehler))
    return eingaenge


# --------------------------------------------------------------------------- #
# Eingang anlegen (Kommando)
# --------------------------------------------------------------------------- #


def _pruefe_stichtag_gegen_ablage(ablage, stichtag: _dt.date, fallname: str) -> None:
    """Einen Stichtag, den der Tagesbetrieb nie annehmen wird, nicht erst
    registrieren (Angriffsrunde Betrieb: ein unwiderruflich registrierter
    Eingang legte den Betrieb danach still). Die Regeln sind die des
    Laufs: nicht vor dem Betriebsbeginn, und kein festgeschriebener
    Abschluss am oder nach dem Stichtag — der kennte den Bestand nie
    (ADR-011)."""
    from rechner_pipeline.betrieb.tageslauf import _festgeschriebene_abschluesse

    if ablage.config_pfad.is_file():
        from rechner_pipeline.bestand.config import load_config

        beginn = load_config(ablage.config_pfad).tagesbetrieb.betriebsbeginn
        if beginn is not None and stichtag < beginn:
            raise UebernahmeError(
                f"{fallname}: Stichtag {stichtag.isoformat()} liegt vor dem "
                f"Betriebsbeginn {beginn.isoformat()} dieser Ablage — der "
                "Tagesbetrieb nimmt ihn nie an; die Ablage aus dem Fall neu "
                "aufsetzen (betrieb.neuaufsetzen)")
    spaetere = [t for t in _festgeschriebene_abschluesse(ablage) if t >= stichtag]
    if spaetere:
        raise UebernahmeError(
            f"{fallname}: Stichtag {stichtag.isoformat()} liegt nicht nach dem "
            f"festgeschriebenen Monatsabschluss {spaetere[0].isoformat()} — der "
            "Abschluss kennt den Bestand nie (ADR-011), der Tagesbetrieb nimmt "
            "den Eingang nicht an. Den Zugang in die offene Zeit legen oder die "
            "Ablage aus dem Fall neu aufsetzen (betrieb.neuaufsetzen)")


def _pruefe_tarifwerk_gegen_ablage(stand: Path, roh: Dict[str, bytes], quelle: Path) -> None:
    """Registriert wird nur, was die Wache des Tageslaufs annimmt (RC16).

    Die Registrierung fuhr P-B1, Stichtag und Abschluss, aber nicht den
    Tarifwerk-Abgleich — der stand nur in ``lies_uebernahme``, das erst der
    Tageslauf ruft. Ein Eingang mit abweichendem Tarifwerk wurde registriert
    und legte danach jede Nacht den ganzen Betrieb still, und
    ueberschreiben laesst sich ein Eingang nie. Dieselben zwei Pruefungen
    wie der Leser, vor dem ersten Seiteneffekt, mit dem Config-Abschnitt als
    Ausweg (wie ``betrieb.neuaufsetzen``).

    Ohne Config in der Ablage wird NICHT registriert (Nachbesserung Runde
    C): Die erste Fassung liess die Pruefung dann aus ("Einrichtung, Config
    folgt") — und registrierte damit genau den Eingang, den der Tageslauf
    danach mit der nachgereichten Config jede Nacht verweigerte. Die
    Reihenfolge ist Config, dann Eingang.
    """
    from rechner_pipeline.bestand.config import bauauftrag_text, load_config, tarifwerk_luecken
    from rechner_pipeline.betrieb.tageslauf import Ablage as _Ablage

    config_pfad = _Ablage(stand).config_pfad
    if not config_pfad.is_file():
        raise UebernahmeError(
            f"{quelle}: nichts registriert — die Ablage traegt keine Config "
            f"({config_pfad}), gegen die das Tarifwerk der Uebernahme geprueft "
            "werden koennte; ohne diesen Abgleich entstuende ein Eingang, den der "
            "Tageslauf womoeglich nie annimmt. Ausweg: erst die Config nach "
            "deploy/plv/README.md ablegen, dann registrieren")
    config = load_config(config_pfad)
    generationen = {str(g) for g in read_portfolio(
        io.BytesIO(roh["bestand.parquet"]), expected_columns=STAMM_NAMES)["tarif_generation"]}
    try:
        beleg = json.loads(roh["uebernahme.json"].decode("utf-8")) if "uebernahme.json" in roh else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UebernahmeError(f"{quelle}/uebernahme.json: Uebernahmebeleg nicht lesbar: {exc}") from exc
    fehler = tarifwerk_fehler(config, generationen, beleg if isinstance(beleg, dict) else {})
    luecken = tarifwerk_luecken(g for g in config.generationen if g.name in generationen)
    if fehler or luecken:
        raise UebernahmeError(
            f"{quelle}: nichts registriert — die Config der Ablage ({config_pfad}) "
            "passt nicht zur Uebernahme, und der Tageslauf naehme den Eingang nie an: "
            + "; ".join(fehler + [bauauftrag_text(*l) for l in luecken]))


@dataclasses.dataclass
class Vorbedingungen:
    """Was die Registrierung vor jedem Seiteneffekt geprueft und gelesen hat."""
    fall: Path
    fallname: str
    quelle: Path
    ring: Mapping[str, bytes]
    snapshot_sha256: str
    snapshot: Dict[str, Any]
    zeichnung: Dict[str, Any]
    ab2: Optional[Tuple[Dict[str, Any], str]]
    ab2_verifiziert: bool
    roh: Dict[str, bytes]


def registrierung_vorbedingungen(
    fall: Path,
    *,
    ordnung: Optional[Mapping[str, Any]],
    schluesselring: Optional[Mapping[str, bytes]] = None,
    snapshot_sha256: Optional[str] = None,
    zugangsabnahme_sha256: Optional[str] = None,
    quelle: Optional[Path] = None,
    probe_kopie: bool = False,
) -> Vorbedingungen:
    """Die Vorbedingungen der Registrierung, die KEINEN Ort brauchen: Fall,
    Zugangsstand, A-M4 (Rollenregel, Schema), A-B2 (Rollenregel; seine
    Bindung an Eingang und Stand erst unter der Sperre), Tabellen und
    Belege gegen den Beleggraphen der Abnahme.

    EINE Funktion, zwei Aufrufer (Angriffsrunde 2026-10-01):
    :func:`eingang_anlegen` vor ihrem ersten Seiteneffekt und
    ``betrieb.neuaufsetzen`` bevor es die neue Ablage anlegt. Vorher liefen
    diese Pruefungen erst in der Registrierung — nachdem das Neuaufsetzen
    ``<stand>.neu-<stempel>`` angelegt hatte, und eine Verweigerung liess
    den Rest liegen.
    """
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
    # Kein Steuer-, Format- oder Trennzeichen (Angriffsrunde nach T27): Der
    # Name steht roh in jeder Protokollzeile; ein U+2028 darin machte das
    # Protokoll fuer jeden Leser mit anderer Zeilengrenze unlesbar.
    import unicodedata

    if any(unicodedata.category(z) in ("Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp") for z in fallname):
        raise UebernahmeError(
            f"{fall_json}: name {fallname!r} traegt ein Steuer- oder Trennzeichen — "
            "als Fallname im Protokoll nicht zulaessig")
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
    # Der Snapshot ist Pflicht und wird geprueft (T22-06), BEVOR irgendetwas
    # angelegt wird.
    ring = schluesselring if schluesselring is not None else _STANDARD_SCHLUESSELRING
    if not ring:
        # Registriert wird nur, was der Tagesbetrieb annimmt (Angriffsrunde
        # nach T27): Ohne Schluessel entstand ein Eingang mit
        # signatur_verifiziert = false, den jeder Tageslauf verweigerte —
        # und neu registrieren ging nicht, weil ein Eingang nie
        # ueberschrieben wird. Der Betrieb stand.
        raise UebernahmeError(
            "ohne Freigabeschluessel wird nichts registriert — der Tagesbetrieb "
            "nimmt nur einen Eingang mit verifizierter Signatur an; "
            "--freigabe-schluessel angeben")
    snapshot, snapshot_name, verifiziert = lies_am4_snapshot(
        fall, snapshot_sha256, schluesselring=ring, ordnung=ordnung)
    # Zeichnungsschicht zu Ende (Entscheid 2026-09-22): Registriert wird
    # nur ein Snapshot des aktuellen Schemas — mit Schluesselklasse und
    # Rolle aus der Zeichnungsordnung. Ein Altsnapshot (Schema 6) traegt
    # beides nicht; lesen laesst er sich weiter (Seite), eintreten nicht.
    from rechner_pipeline.models.schemas import P9_SNAPSHOT_SCHEMA_VERSION
    if snapshot.get("schema_version") != P9_SNAPSHOT_SCHEMA_VERSION:
        raise UebernahmeError(
            f"{snapshot_name}: Schema {snapshot.get('schema_version')!r} — ein "
            f"Eingang braucht eine Zeichnung mit Schluesselklasse (Schema "
            f"{P9_SNAPSHOT_SCHEMA_VERSION}); den Fall neu zeichnen"
        )
    zeichnung = _zeichnung_aus_daten(snapshot, snapshot_name, verifiziert=verifiziert)
    # Die Zugangsabnahme A-B2 (ADR-022, Entscheid des Maintainers
    # 2026-09-30): Ohne sie wird nichts registriert. Geprueft wird der
    # Snapshot HIER, vor dem ersten Seiteneffekt (Schema, Kette, Signatur);
    # seine Bindung an den Eingang und den Stand der Ablage erst unter der
    # Sperre, wenn beide feststehen. Die Probe selbst registriert in ihrer
    # Kopie ohne — sie erzeugt erst, was A-B2 abnimmt.
    ab2: Optional[Tuple[Dict[str, Any], str]] = None
    ab2_verifiziert = False
    if not probe_kopie:
        if zugangsabnahme_sha256 is None:
            ledger_ab2 = fall / "abgeleitet" / "diagnostics" / "gate_entscheid_ab2.gate.json"
            if ledger_ab2.is_file():
                try:
                    zugangsabnahme_sha256 = json.loads(ledger_ab2.read_text(
                        encoding="utf-8"))["summary"]["snapshot_sha256"]
                except (OSError, json.JSONDecodeError, KeyError, TypeError):
                    zugangsabnahme_sha256 = None
        if zugangsabnahme_sha256 is not None:
            ab2_daten, ab2_name, ab2_verifiziert = lies_abnahme_snapshot(
                fall, "A-B2", zugangsabnahme_sha256, schluesselring=ring,
                ordnung=ordnung)
            ab2 = (ab2_daten, ab2_name)
        elif _STANDARD_ZUGANGSABNAHME is None:
            raise UebernahmeError(
                f"{fall}: kein A-B2-Snapshot — ohne Zugangsabnahme wird nichts "
                "registriert, ohne A-B2 kein Eintritt (ADR-022). Ausweg: "
                + _ABNAHME["A-B2"][1])
    # Was uebernommen wird, muss das sein, was die Abnahme gesehen hat
    # (Befund T26-03). Geprueft VOR dem ersten Seiteneffekt: Ein Eingang,
    # dessen Tabellen die Migrationsabnahme nicht bezeugt, entsteht nicht.
    belegt = belegte_tabellen(fall, snapshot)
    unbelegt: List[str] = []
    # EINMAL lesen, dann nur noch diese Bytes verwenden (Pruefrunde T27,
    # Befund 04): Die erste Fassung hashte die Quelldateien hier und las
    # sie nach dem Eintritt in die Sperre ein zweites Mal von der Platte.
    # Wer die Quelle dazwischen tauschte, bekam andere Tabellen in den
    # Eingang als die, die die Abnahme bezeugt — mit gruener Hashpruefung
    # und verifizierter Signatur. Die Sperre schuetzt konkurrierende
    # Eingangsschreiber, nicht den Produzenten der Quelle; nur die Bytes
    # selbst tun das.
    roh: Dict[str, bytes] = {}
    for datei in [f"{n}.parquet" for n in list(PFLICHT) + list(OPTIONAL)] + list(BELEGE):
        if (quelle / datei).is_file():
            roh[datei] = (quelle / datei).read_bytes()
    # Gebunden wird JEDE Tabelle, die der Graph bezeugt — auch Scheiben,
    # Schichten, Verankerung und Merkmale (Angriffsrunde 2 Betrieb, Fund
    # N21: die Schleife lief nur ueber die Pflichttabellen, obwohl
    # belegte_tabellen die Hashes der Nebentabellen laengst gesammelt
    # hatte; eine getauschte Scheibentabelle ging ungeprueft ein). Und eine
    # mitgebrachte Nebentabelle, die der Graph NICHT nennt, ist ebenso eine
    # Luecke wie eine Pflichttabelle (Angriffsrunde nach T27: eine nach der
    # Abnahme hinzugelegte Korrekturschicht hob den Rueckkaufswert auf das
    # Zwanzigfache). Die Fuehrungsprobe bindet jede Tabelle, die sie liest.
    for datei in (f"{name}.parquet" for name in list(PFLICHT) + list(OPTIONAL)):
        quell_pfad = quelle / datei
        if datei not in roh:
            continue
        ist = sha256_bytes(roh[datei])
        soll = bezeugter_hash(belegt, fall, quell_pfad, datei)
        if soll is None:
            # JEDE mitgebrachte Tabelle, nicht nur die drei Pflichttabellen
            # (Angriffsrunde nach T27): Eine nach der Abnahme hinzugelegte
            # Korrekturschicht ging ungeprueft in Storno und Bewertung ein.
            unbelegt.append(datei)
        elif soll != ist:
            raise UebernahmeError(
                f"{quell_pfad}: die Tabelle ist nicht die, die der "
                f"A-M4-Snapshot bezeugt ({ist[:16]}… statt {soll[:16]}…) — "
                "die Abnahme galt einem anderen Stand. Entweder die "
                "abgenommenen Tabellen uebernehmen oder den Fall neu "
                "abnehmen"
            )
    if unbelegt:
        # Annahme 5, ENTSCHIEDEN STRENG (Maintainer 2026-09-22): Jede der drei
        # Pflichttabellen muss vom Beleggraphen der Abnahme bezeugt sein — ein
        # unbezeugter Ledger ist eine Luecke, keine Warnung. Vorher wurde nur
        # bestand.parquet verlangt und der Rest auf stderr benannt; ein
        # aelterer P-B1-Ledger reicht damit nicht mehr, der Fall ist neu
        # abzunehmen (Befund T26-03).
        raise UebernahmeError(
            f"{fall}: der Beleggraph des A-M4-Snapshots nennt keinen Hash "
            f"fuer {', '.join(sorted(unbelegt))} — die Abnahme bezeugt diese "
            "Tabelle(n) nicht. Ohne diesen Bezug ist der Eingang eine "
            "Behauptung (Befund T26-03; Annahme 5 streng)"
        )
    # Der Uebernahmebeleg ist Pflicht und muss der bezeugte sein
    # (Angriffsrunde nach T27): Er traegt die Tarifwerk-Schalter, gegen die
    # der Tageslauf die Config haelt. Nur die Tabellen wurden gegen den
    # Graphen gehalten; ein geaenderter oder entfernter Beleg liess den
    # Betrieb mit anderen Schaltern fuehren, als abgenommen war.
    for datei in BELEGE:
        if datei not in roh:
            raise UebernahmeError(
                f"{quelle / datei}: der Uebernahmebeleg fehlt — ohne ihn ist nicht "
                "ablesbar, unter welchem Tarifwerk die Abnahmen bestanden wurden")
        soll = bezeugter_hash(belegt, fall, quelle / datei, datei)
        ist = sha256_bytes(roh[datei])
        if soll != ist:
            raise UebernahmeError(
                f"{quelle / datei}: der Uebernahmebeleg ist nicht der, den der "
                "A-M4-Snapshot bezeugt"
                + (" (der Beleggraph nennt ihn nicht)" if soll is None
                   else f" ({ist[:16]}… statt {soll[:16]}…)")
                + " — den abgenommenen Beleg uebernehmen oder den Fall neu abnehmen")
    return Vorbedingungen(
        fall=fall, fallname=fallname, quelle=quelle, ring=ring,
        snapshot_sha256=str(snapshot_sha256), snapshot=snapshot, zeichnung=zeichnung,
        ab2=ab2, ab2_verifiziert=ab2_verifiziert, roh=roh)


def eingang_anlegen(
    stand: Path,
    fall: Path,
    stichtag: _dt.date,
    *,
    quelle: Optional[Path] = None,
    snapshot_sha256: Optional[str] = None,
    schluesselring: Optional[Mapping[str, bytes]] = None,
    betriebsschluessel: Optional[Path] = None,
    zeichnungsordnung: Optional[Path] = None,
    zugangsabnahme_sha256: Optional[str] = None,
    probe_kopie: bool = False,
) -> Path:
    """Den Zugangsstand eines Falls als Eingang der Laufzeitumgebung registrieren.

    ``zugangsabnahme_sha256``: der Snapshot der angenommenen Zugangsabnahme
    A-B2 (ADR-022; Default: das A-B2-Gate-Ledger des Falls). Ohne sie wird
    nichts registriert; sie muss GENAU den Eingang binden, den diese
    Registrierung schreibt, und den gefuehrten Stand der Ablage, auf dem sie
    ihn schreibt. Die Registrierung legt die gepruefte Abnahme als
    ``zugangsabnahme.json`` neben eingang.json, gezeichnet mit dem
    Betriebsschluessel; der Tageslauf haelt sie beim Eintritt noch einmal
    gegen den Stand.

    ``probe_kopie``: NUR fuer ``betrieb.zugangsprobe`` auf ihrer
    gekennzeichneten Kopie der Ablage — dort entsteht der Eingang, den A-B2
    danach abnimmt, und eine Abnahme gibt es dort noch nicht. Auf einer
    Ablage ohne das Kennzeichen verweigert der Schalter.

    ``betriebsschluessel``/``zeichnungsordnung``: der Betriebsschluessel,
    mit dem eingang.json gezeichnet wird (Schema 3; Aufloesung wie im
    Tageslauf: ausdruecklich > Naht > Fehler). Ohne ihn wird nichts
    registriert — der Tageslauf nimmt keinen ungezeichneten neuen Eingang an.

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

    from rechner_pipeline.betrieb.tageslauf import Ablage as _Ablage
    from rechner_pipeline.betrieb.tageslauf import TageslaufError as _TageslaufError
    from rechner_pipeline.betrieb.tageslauf import betriebszeichner

    # Kopie oder Ablage — VOR jedem Seiteneffekt (ADR-022): Die Probe
    # registriert nur in ihrer gekennzeichneten Kopie ohne Abnahme, und in
    # eine Probenkopie registriert niemand sonst.
    from rechner_pipeline.betrieb.tageslauf import ZUGANGSPROBE_KOPIE_DATEI

    kennzeichen = Path(stand) / ZUGANGSPROBE_KOPIE_DATEI
    if probe_kopie and not kennzeichen.is_file():
        raise UebernahmeError(
            f"{stand}: eine Registrierung ohne Zugangsabnahme nur in der "
            f"gekennzeichneten Kopie einer Zugangsprobe ({kennzeichen.name} fehlt) — in "
            "eine echte Ablage tritt kein Eingang ohne A-B2 ein (ADR-022)")
    if not probe_kopie and kennzeichen.exists():
        raise UebernahmeError(
            f"{stand}: die Ablage ist die Kopie einer Zugangsprobe ({kennzeichen.name}) — "
            "registriert wird in die produktive Ablage")
    if not probe_kopie:
        # Auch ohne Kennzeichen (Runde F, F9): Eine Probezeile im Protokoll
        # macht die Ablage zur Probenkopie — das Kennzeichen ist ungezeichnet.
        from rechner_pipeline.betrieb.tageslauf import probenkopie_fehler

        fehler = probenkopie_fehler(_Ablage(Path(stand)))
        if fehler:
            raise UebernahmeError(f"{fehler} — registriert wird in die produktive Ablage")
    # Der Betriebsschluessel VOR jedem Seiteneffekt: Ohne ihn entstuende ein
    # Eingang, den der Tageslauf nie annimmt.
    try:
        zeichner = betriebszeichner(
            _Ablage(Path(stand)), betriebsschluessel, zeichnungsordnung,
            wofuer="die Registrierung", ohne="keine Registrierung",
            flag="--betriebsschluessel")
    except _TageslaufError as exc:
        raise UebernahmeError(str(exc)) from exc
    vor = registrierung_vorbedingungen(
        fall, ordnung=zeichner.ordnung, schluesselring=schluesselring,
        snapshot_sha256=snapshot_sha256, zugangsabnahme_sha256=zugangsabnahme_sha256,
        quelle=quelle, probe_kopie=probe_kopie)
    fall, fallname, quelle, ring = vor.fall, vor.fallname, vor.quelle, vor.ring
    snapshot_sha256, snapshot, zeichnung = vor.snapshot_sha256, vor.snapshot, vor.zeichnung
    ab2, ab2_verifiziert, roh = vor.ab2, vor.ab2_verifiziert, vor.roh
    _pruefe_tarifwerk_gegen_ablage(Path(stand), roh, quelle)
    ziel = Path(stand) / UEBERNAHME_DIR / fallname
    if ziel.exists():
        raise UebernahmeError(
            f"{ziel} existiert bereits — ein Eingang wird nie ueberschrieben; "
            "eine neue Lieferung ist ein neuer Eingang unter neuem Namen"
        )
    # Bandvergabe UND Publikation unter einer Sperre (T26-14): Das
    # Register der Baender ist die Summe der Eingaenge selbst — es wird
    # gelesen, um das naechste Band zu bestimmen, und durch die
    # Publikation fortgeschrieben. Zwei gleichzeitige Registrierungen
    # bekamen sonst dasselbe Band und veroeffentlichten beide.
    # Dazu die LAUF-Sperre der Ablage (Angriffsrunde Betrieb): Registrierung
    # und Tageslauf nahmen verschiedene Sperren; ein Lauf, der zwischen
    # Pruefung und Publikation einen Abschluss schrieb, machte den frisch
    # registrierten Eingang dauerhaft unannehmbar — beide Kommandos meldeten
    # Erfolg. Unter der Lauf-Sperre gibt es kein Dazwischen, und die
    # Registrierung kann pruefen, was der Lauf verlangen wird.
    from contextlib import ExitStack

    from rechner_pipeline.betrieb.tageslauf import (
        Ablage,
        TageslaufError,
        _festgeschriebene_abschluesse,
        lauf_sperre,
    )

    ablage_ziel = Ablage(Path(stand))
    with ExitStack() as sperren:
        try:
            sperren.enter_context(lauf_sperre(ablage_ziel))
            # Der gefuehrte Stand, auf dem registriert wird — unter der
            # Sperre, also derselbe, auf dem der naechste Lauf den Eingang
            # aufnimmt (ADR-022).
            from rechner_pipeline.betrieb.tageslauf import ablage_stand
            from rechner_pipeline.models.zugangsprobe import stand_sha256 as _stand_sha

            stand_inhalt = ablage_stand(ablage_ziel)
            stand_sha = _stand_sha(stand_inhalt)
        except TageslaufError as exc:
            raise UebernahmeError(str(exc)) from exc
        _pruefe_stichtag_gegen_ablage(ablage_ziel, stichtag, fallname)
        sperren.enter_context(eingang_sperre(stand))
        # Der Eingang entsteht VOLLSTAENDIG neben seinem Namen und wird dann in
        # einem Zug umbenannt (Review T22-03): Ein halb geschriebener Eingang
        # blockierte sonst dauerhaft, weil das Verzeichnis als "nie
        # ueberschreiben" galt. Ein Rest eines abgebrochenen Anlegens wird
        # entfernt — er war nie ein Eingang.
        # Die Staging-Wurzel liegt NEBEN der Eingangswurzel (T26-01). Der
        # ``ohne_marker`` darunter ist die zweite Sicherung derselben Aussage:
        # Selbst wenn jemand die Wurzeln wieder zusammenlegte, verbietet er
        # die Loeschung eines Verzeichnisses, das eine eingang.json traegt.
        staging = Path(stand) / STAGING_DIR
        arbeit = staging / fallname
        if arbeit.exists():
            # Publikationszustand und Arbeitswurzel GEMEINSAM: ``ziel``
            # existiert nicht (oben geprueft), also ist nichts unter diesem
            # Namen veroeffentlicht — auch ein vollstaendig geschriebenes
            # Staging mit eingang.json ist dann ein Rest, dessen finaler
            # Rename scheiterte. Die erste Fassung hielt den Marker fuer
            # den Beweis einer Publikation und verweigerte; die Wiederholung
            # derselben Registrierung scheiterte dauerhaft (Pruefrunde T27,
            # Befund 03). Der Marker sperrt, sobald das Ziel steht.
            try:
                entferne_verzeichnis(
                    arbeit, innerhalb=staging,
                    name_ok=lambda n: n == fallname,
                    ohne_marker=EINGANG_DATEI if ziel.exists() else None,
                    grund="Rest eines abgebrochenen Anlegens",
                )
            except LoeschFehler as exc:
                raise UebernahmeError(str(exc)) from exc
        arbeit.mkdir(parents=True)
        # Die Eingangswurzel muss es geben, bevor umbenannt wird — frueher
        # entstand sie beilaeufig, weil das Arbeitsverzeichnis darin lag.
        ziel.parent.mkdir(parents=True, exist_ok=True)
        # Das Zielsystem vergibt seine eigenen Policennummern (Review T24-08,
        # Entscheid des Maintainers 2026-09-15). Niemand schreibt uns in einer
        # Migration einen Datensatz um; die Transformation ist unsere Arbeit
        # auf der Zielseite, und es ist unsere Aufgabe, sie kollisionsfrei zu
        # machen. Vorher lief eine gelieferte Nummer ungeprueft durch und
        # kollidierte Jahre spaeter mit dem eigenen, deterministisch
        # vorausberechenbaren Neugeschaeft — als harter Abbruch eines
        # Nachtlaufs, zu einem Zeitpunkt, den niemand gewaehlt hat.
        #
        # Umnummeriert wird IMMER, nicht nur bei Kollision: Sonst haengt unsere
        # Nummernvergabe davon ab, was die Quelle zufaellig geliefert hat, und
        # die Uebersetzungstabelle waere mal die Identitaet und mal nicht — ein
        # Leser baut sich dann zwei Lesewege.
        stamm_quelle = read_portfolio(io.BytesIO(roh["bestand.parquet"]), expected_columns=STAMM_NAMES)
        quelle_ids = sorted(int(p) for p in stamm_quelle["police_id"])
        if len(quelle_ids) != len(set(quelle_ids)):
            raise UebernahmeError(
                f"{quelle}/bestand.parquet: police_id nicht eindeutig — ohne "
                "eindeutige Quellnummern gibt es keine Uebersetzung"
            )
        band_von, band_bis = naechstes_band(Path(stand) / UEBERNAHME_DIR, len(quelle_ids))
        abbildung = {q: band_von + i for i, q in enumerate(quelle_ids)}

        dateien: Dict[str, str] = {}
        spalten_je_tabelle = {**PFLICHT, **OPTIONAL}
        kandidaten = [f"{name}.parquet" for name in list(PFLICHT) + list(OPTIONAL)] + list(BELEGE)
        for datei in kandidaten:
            if datei not in roh:
                continue
            if datei in BELEGE:
                # Belege sprechen die Sprache des FALLS und bleiben bei den
                # Quellnummern: uebernahme.json dokumentiert, was die Migration
                # getan hat, und seine Freitexte nennen Policen. Ein Beleg, den
                # der Betrieb umschreibt, bezeugt nicht mehr den Fall. Die
                # Uebersetzungstabelle ist die Bruecke zwischen beiden Welten.
                daten = roh[datei]
                (arbeit / datei).write_bytes(daten)
            else:
                tabelle = read_portfolio(
                    io.BytesIO(roh[datei]),
                    expected_columns=spalten_je_tabelle[datei[:-len(".parquet")]])
                write_portfolio(_umnummeriert(tabelle, abbildung, datei), arbeit / datei)
                daten = (arbeit / datei).read_bytes()
            if os.name != "nt":
                (arbeit / datei).chmod(0o444)
            dateien[datei] = sha256_bytes(daten)

        uebersetzung = pd.DataFrame({
            "quelle_police_id": pd.Series(quelle_ids, dtype="int64"),
            "ziel_police_id": pd.Series([abbildung[q] for q in quelle_ids], dtype="int64"),
        })
        write_portfolio(uebersetzung, arbeit / POLICENNUMMERN_DATEI)
        if os.name != "nt":
            (arbeit / POLICENNUMMERN_DATEI).chmod(0o444)
        dateien[POLICENNUMMERN_DATEI] = sha256_bytes((arbeit / POLICENNUMMERN_DATEI).read_bytes())
        # Erst die Pruefung am Eingang des Betriebs, dann die Registrierung:
        # Ein Zugangsstand, dessen Nebentabellen das Gate nicht annehmen
        # wuerde, wird nicht Eingang (N-01). Der Rest in der Staging-Wurzel
        # ist kein Eingang und wird beim naechsten Anlegen desselben Falls
        # entfernt. Er blockiert niemanden: Der Leser sieht ihn nicht, weil
        # er ausserhalb der Eingangswurzel liegt (T26-15).
        nt_fehler = _nebentabellen_fehler_im(arbeit)
        if nt_fehler:
            raise UebernahmeError(
                f"{quelle}: der Zugangsstand traegt Nebentabellen, die das Gate "
                "nicht annehmen wuerde — nichts registriert: " + "; ".join(nt_fehler[:5])
            )
        # Und dieselbe Pruefung, mit der die Wache des Tageslaufs den Stand
        # abnimmt (Angriffsrunde Betrieb): Ein Zugangsstand, dessen Vertraege
        # am Stichtag schon abgelaufen sind, wurde registriert, und der
        # Tagesbetrieb stand danach an jedem Tag still. Der Snapshot bezeugt
        # die Bytes; ob der Betrieb sie fuehren kann, sagt erst die
        # Pruefung selbst — sie wird hier nicht geglaubt, sondern gefahren.
        pb1_fehler = _eingang_pb1_fehler(arbeit, stichtag, ablage_ziel.config_pfad)
        if pb1_fehler:
            raise UebernahmeError(
                f"{quelle}: der Zugangsstand ist nicht, was die Wache des "
                "Tageslaufs (P-B1) annimmt — nichts registriert: "
                + "; ".join(pb1_fehler[:5]))
        eingang = {
            "schema_version": EINGANG_SCHEMA_VERSION,
            "fall": fallname,
            "stichtag": stichtag.isoformat(),
            "snapshot_sha256": snapshot_sha256,
            # Rolle und Schluesselklasse der Zeichnung, wie die Fall-Seite sie
            # ausweist — Angaben der strukturell geprueften Snapshot-Datei, die
            # Signatur hier nicht verifiziert (T22-06).
            "zeichnung": zeichnung,
            "quelle": str(quelle),
            # Das Nummernband dieses Eingangs. Es steht hier und nicht in einem
            # gepflegten Register: Die Summe der Eingaenge IST das Register.
            "band": {"von": band_von, "bis": band_bis},
            "dateien": dict(sorted(dateien.items())),
        }
        # Gezeichnet ueber ALLE Felder (Schema 3): Datei-Hashes, Snapshot-Hash
        # und der A-M4-Block mit signatur_verifiziert. Die Registrierung ist
        # der Moment, in dem die Freigabesignatur geprueft wurde; danach
        # bezeugt nur noch diese Zeichnung, dass es so war.
        eingang["betriebszeichnung"] = zeichner.zeichne({"eingang": eingang})
        if not probe_kopie:
            # Die Zugangsabnahme gegen GENAU diesen Eingang und diesen Stand
            # (ADR-022). Ohne ausdrueckliche Abnahme liefert sie nur die
            # Test-Naht; produktiv hat der Weg oben schon verweigert.
            if ab2 is None:
                sha = _STANDARD_ZUGANGSABNAHME(  # type: ignore[misc]
                    fall, ablage_stand=stand_inhalt, eingang_roh=_eingang_bytes(eingang),
                    am4_snapshot_sha256=snapshot_sha256, zeichner=zeichner,
                    schluesselring=ring)
                ab2_daten, ab2_name, ab2_verifiziert = lies_abnahme_snapshot(
                    fall, "A-B2", sha, schluesselring=ring, ordnung=zeichner.ordnung)
                ab2 = (ab2_daten, ab2_name)
            abnahme = _zugangsabnahme_binden(
                fall, fallname, ab2[0], ab2[1], stand_sha256=stand_sha,
                eingang=eingang, am4_sha256=str(snapshot_sha256), zeichner=zeichner,
                am4=snapshot, schluesselring=ring, ab2_verifiziert=ab2_verifiziert)
            abnahme["betriebszeichnung"] = zeichner.zeichne({"zugangsabnahme": abnahme})
            abnahme_pfad = arbeit / ZUGANGSABNAHME_DATEI
            abnahme_pfad.write_text(
                json.dumps(abnahme, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8", newline="\n")
            if os.name != "nt":
                abnahme_pfad.chmod(0o444)
        pfad = arbeit / EINGANG_DATEI
        pfad.write_bytes(_eingang_bytes(eingang))
        if os.name != "nt":
            pfad.chmod(0o444)
        os.rename(arbeit, ziel)
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
    parser.add_argument("--freigabe-schluessel", action="append", default=None,
                        help="Pfad eines Freigabeschluessels (mehrfach moeglich), ausserhalb des "
                             "Falls; prueft die Signatur des A-M4-Snapshots. Pflicht: ohne ihn "
                             "wird nichts registriert, denn der Tageslauf nimmt nur einen "
                             "verifizierten Eingang an.")
    parser.add_argument("--snapshot", default=None,
                        help="Snapshot-Hash der A-M4-Annahme (Default: aus dem Gate-Beleg des Falls).")
    parser.add_argument("--zugangsabnahme", default=None,
                        help="Snapshot-Hash der angenommenen Zugangsabnahme A-B2 (ADR-022; "
                             "Default: aus dem A-B2-Gate-Beleg des Falls). Pflicht: ohne A-B2 "
                             "wird nichts registriert.")
    parser.add_argument("--betriebsschluessel", required=True,
                        help="Betriebsschluessel (Rolle betrieb/<name>, Klasse betrieb), mit dem "
                             "eingang.json gezeichnet wird; ausserhalb der Ablage.")
    parser.add_argument("--zeichnungsordnung", required=True,
                        help="Zeichnungsordnung, die dem Betriebsschluessel seine Rolle gibt.")
    ns = parser.parse_args(argv)
    ring: Optional[Mapping[str, bytes]] = None
    if ns.freigabe_schluessel:
        from rechner_pipeline.models.freigabe import lade_schluesselring
        ring, ring_fehler, _aktiv = lade_schluesselring(
            list(ns.freigabe_schluessel), ausserhalb=Path(ns.fall))
        if ring_fehler:
            print("uebernahme: " + "; ".join(ring_fehler), file=sys.stderr)
            return 2
    try:
        stichtag = _dt.date.fromisoformat(ns.stichtag)
    except ValueError as exc:
        print(f"uebernahme: --stichtag: {exc}", file=sys.stderr)
        return 2
    try:
        ziel = eingang_anlegen(
            Path(ns.stand), Path(ns.fall), stichtag,
            quelle=Path(ns.quelle) if ns.quelle else None, snapshot_sha256=ns.snapshot,
            schluesselring=ring, betriebsschluessel=Path(ns.betriebsschluessel),
            zeichnungsordnung=Path(ns.zeichnungsordnung),
            zugangsabnahme_sha256=ns.zugangsabnahme,
        )
    except UebernahmeError as exc:
        print(f"uebernahme: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        # Eine unlesbare Eingabe (etwa eine halb kopierte Config der
        # Ablage) ist ein Eingangsfehler mit Meldung (Angriffsrunde nach T27).
        print(f"uebernahme: Eingabe nicht lesbar: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        # Meldung statt Traceback und Exit 1, wie tageslauf und seite
        # (Angriffsrunde nach T27).
        print(f"uebernahme: Ein-/Ausgabefehler: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(f"uebernahme: Eingang angelegt -> {ziel}", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
