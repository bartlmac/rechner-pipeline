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

import contextlib
import dataclasses
import sys as _sys
import datetime as _dt
import json

try:  # Referenzumgebung ist Linux; ohne fcntl gibt es keine Prozess-Sperre.
    import fcntl
except ImportError:  # pragma: no cover - fremde Plattform
    fcntl = None  # type: ignore[assignment]
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

from rechner_pipeline.betrieb._loeschen import LoeschFehler, entferne_verzeichnis
from rechner_pipeline.models.zeichnung import ZEICHNENDE_KLASSEN
from rechner_pipeline.models.schemas import p9_semantik_fehler
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
EINGANG_SCHEMA_VERSION = 2
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


#: Was ueber die Zeichnung einer A-M4-Annahme NICHT bekannt ist, heisst so —
#: nicht leer, nicht None. Aeltere Snapshots (Schema 6) fuehren keine
#: Schluesselklasse; die Seite sagt dann "nicht ausgewiesen", wie die
#: Fall-Seite.
NICHT_AUSGEWIESEN = "nicht ausgewiesen"


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


def pruefe_am4_snapshot(fall: Path, snapshot_sha256: Optional[str]) -> Dict[str, Any]:
    """Die Zeichnungsangaben des geprueften Snapshots (siehe
    :func:`lies_am4_snapshot`)."""
    return _zeichnung_aus_daten(*lies_am4_snapshot(fall, snapshot_sha256))


def lies_am4_snapshot(
    fall: Path, snapshot_sha256: Optional[str]
) -> Tuple[Dict[str, Any], str]:
    """Den A-M4-Snapshot einer Uebernahme pruefen, soweit es ohne Schluessel geht.

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

    if not snapshot_sha256:
        raise UebernahmeError(
            f"{fall}: kein A-M4-Snapshot — eine Uebernahme ohne Migrationsabnahme "
            "gibt es nicht (--snapshot <sha256> oder ein gruenes A-M4-Gate-Ledger "
            "unter abgeleitet/diagnostics/)"
        )
    if not _ist_sha256(snapshot_sha256):
        raise UebernahmeError(f"snapshot_sha256 {snapshot_sha256!r} ist keine SHA-256")
    pfad = Path(fall) / "entscheide" / f"A-M4-{snapshot_sha256}.json"
    if not pfad.is_file():
        raise UebernahmeError(f"{pfad}: der A-M4-Snapshot liegt nicht im Fall")
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
    if daten.get("gate") != "A-M4":
        raise UebernahmeError(f"{pfad.name}: Gate {daten.get('gate')!r} ist nicht A-M4")
    if daten.get("entscheid") != "angenommen":
        raise UebernahmeError(
            f"{pfad.name}: Entscheid {daten.get('entscheid')!r} — nur eine ANGENOMMENE "
            "Migrationsabnahme begruendet eine Uebernahme"
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
    semantik = p9_semantik_fehler(daten)
    if semantik:
        raise UebernahmeError(
            f"{pfad.name}: Snapshot ist in sich nicht stimmig: "
            + "; ".join(semantik[:3]))
    # Aus DIESEN Bytes, nicht aus einem zweiten Lesevorgang (Review
    # T24-06): Die Pruefung oben lief auf dem gelesenen Inhalt; ein
    # erneutes Lesen gaebe die Zeichnung einer Datei zurueck, die
    # inzwischen eine andere sein kann. Nachgemessen mit einem Tausch
    # zwischen beiden Lesevorgaengen: geprueft wurde "angenommen",
    # registriert wurde "abgelehnt" — beides ohne Abbruch.
    return daten, pfad.name


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
    tabellen = {f"{n}.parquet" for n in list(PFLICHT) + list(OPTIONAL)}
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


def _zeichnung_aus_daten(daten: Dict[str, Any], quelle: str) -> Dict[str, Any]:
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
        "signatur_verifiziert": False,
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


def tarifwerk_fehler(config: BestandConfig, generationen: Iterable[str], beleg: Dict[str, Any]) -> List[str]:
    """Die Config der Laufzeit muss fuer die uebernommenen Generationen die
    Tarifwerk-Schalter tragen, mit denen ihre Abnahmen bestanden wurden
    (Freischaltung, Schritt 2 und 9). Leer = in Ordnung."""
    soll = beleg.get("tarifwerk")
    if not isinstance(soll, dict):
        return []
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
    tw_fehler = tarifwerk_fehler(config, bestand["tarif_generation"], beleg)
    if tw_fehler:
        raise UebernahmeError(f"{verzeichnis}: " + "; ".join(tw_fehler))
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
    # Der Snapshot ist Pflicht und wird geprueft (T22-06), BEVOR irgendetwas
    # angelegt wird.
    snapshot, snapshot_name = lies_am4_snapshot(fall, snapshot_sha256)
    zeichnung = _zeichnung_aus_daten(snapshot, snapshot_name)
    # Was uebernommen wird, muss das sein, was die Abnahme gesehen hat
    # (Befund T26-03). Geprueft VOR dem ersten Seiteneffekt: Ein Eingang,
    # dessen Tabellen die Migrationsabnahme nicht bezeugt, entsteht nicht.
    belegt = belegte_tabellen(fall, snapshot)
    unbelegt: List[str] = []
    for datei in (f"{name}.parquet" for name in PFLICHT):
        quell_pfad = quelle / datei
        if not quell_pfad.is_file():
            continue
        ist = sha256_bytes(quell_pfad.read_bytes())
        soll = bezeugter_hash(belegt, fall, quell_pfad, datei)
        if soll is None:
            unbelegt.append(datei)
        elif soll != ist:
            raise UebernahmeError(
                f"{quell_pfad}: die Tabelle ist nicht die, die der "
                f"A-M4-Snapshot bezeugt ({ist[:16]}… statt {soll[:16]}…) — "
                "die Abnahme galt einem anderen Stand. Entweder die "
                "abgenommenen Tabellen uebernehmen oder den Fall neu "
                "abnehmen"
            )
    if "bestand.parquet" in unbelegt:
        raise UebernahmeError(
            f"{fall}: der Beleggraph des A-M4-Snapshots nennt keinen Hash "
            "fuer bestand.parquet — die Abnahme bezeugt die Tabelle nicht, "
            "die uebernommen werden soll. Ohne diesen Bezug ist der Eingang "
            "eine Behauptung (Befund T26-03)"
        )
    if unbelegt:
        # Benannte Luecke statt stiller: Ein aelterer P-B1-Ledger fuehrt
        # Bestand und Historie, aber nicht jeden Nebenstand.
        print(
            f"uebernahme: der Beleggraph nennt keine Hashes fuer "
            f"{', '.join(sorted(unbelegt))} — diese Tabellen sind von der "
            "Migrationsabnahme nicht bezeugt und werden ungeprueft "
            "uebernommen",
            file=_sys.stderr,
        )
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
    with eingang_sperre(stand):
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
            try:
                entferne_verzeichnis(
                    arbeit, innerhalb=staging,
                    name_ok=lambda n: n == fallname,
                    ohne_marker=EINGANG_DATEI,
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
        stamm_quelle = read_portfolio(quelle / "bestand.parquet", expected_columns=STAMM_NAMES)
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
            if not (quelle / datei).is_file():
                continue
            if datei in BELEGE:
                # Belege sprechen die Sprache des FALLS und bleiben bei den
                # Quellnummern: uebernahme.json dokumentiert, was die Migration
                # getan hat, und seine Freitexte nennen Policen. Ein Beleg, den
                # der Betrieb umschreibt, bezeugt nicht mehr den Fall. Die
                # Uebersetzungstabelle ist die Bruecke zwischen beiden Welten.
                daten = (quelle / datei).read_bytes()
                (arbeit / datei).write_bytes(daten)
            else:
                tabelle = read_portfolio(
                    quelle / datei, expected_columns=spalten_je_tabelle[datei[:-len(".parquet")]])
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
        pfad = arbeit / EINGANG_DATEI
        pfad.write_text(json.dumps(eingang, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8", newline="\n")
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
