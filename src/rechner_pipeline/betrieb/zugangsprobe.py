"""``betrieb.zugangsprobe`` — der Zugang in die produktive Ablage, vorab gerechnet (ADR-022).

Producer, kein Gate (Muster ``gates.fuehrungsprobe``): schreibt den Beleg
``zugangsprobe.json``, den die Zugangsabnahme ``A-B2.zugangsabnahme``
(``gates.gate_entscheid --gate A-B2``) als Pflichtbeleg pinnt und die
Registrierung (``betrieb.uebernahme``) gegen ihren Eingang und den Stand
der Ablage haelt::

    python -m rechner_pipeline.betrieb.zugangsprobe --stand <daten> \\
        --fall faelle/<fall> --stichtag 2026-01-01 [--bis <iso>] \\
        --schluessel <betriebsschluessel> --zeichnungsordnung <ordnung> \\
        --freigabe-schluessel <freigabeschluessel> [--arbeit <dir>] [--out <beleg>]

**Die Frage, die sie beantwortet** (Entscheid des Maintainers
2026-09-30). A-M1 bis A-M4 und die Fuehrungsprobe urteilen im Fall, mit
der Config des Falls. Was die Registrierung in der PRODUKTIVEN Ablage
bewirkt — mit ihrer Config, ihrem Bestand, ihrem Kern — sah bis hierher
niemand; der erste Monatsabschluss danach war die erste Gelegenheit, und
dann stand er schon fest. Der zweite Baldrian-Lauf hat gezeigt, dass beide
Welten auseinanderlaufen koennen.

**Wie.** Unter der Lauf-Sperre der Ablage zieht die Probe zwei Kopien
(das Original wird nie beschrieben; die Kopien liegen ausserhalb der
Ablage und tragen ein Kennzeichen, auf dem kein echter Lauf faehrt). In
die eine registriert sie den Eingang des Falls, genau wie die
Registrierung es spaeter tun wird; dann faehrt sie beide vom gefuehrten
Tag ueber den Zugangsstichtag bis zum naechsten Monatsabschluss (oder bis
``--bis``). Beide Laeufe sind deterministisch (ADR-020), ihre Differenz
ist eine Rechnung, keine Messung mit Rauschen: Sie muss exakt der
abgenommene Bestand sein.

**Was verglichen wird** (``models.zugangsprobe.GROESSEN``): je
Monatsabschluss Anzahl in Kraft, Versicherungssumme und Jahresbeitrag der
Zeilen, die nur der Lauf "mit" traegt — am Zugangsstichtag gegen die
Uebernahme (``bestand.parquet``) und die Migrationssuite
(``bjb_stichtag_1`` je Vertrag des ganzen Zugangs), am Folgetermin die
Anzahl in Kraft gegen die Migrationssuite, soweit der Termin ein Abschluss
des Fensters ist; die Zugaenge gegen die Zahl der uebernommenen Vertraege,
ihre Buchungen bis zum Stichtag gegen den Ledger der Uebernahme, das
Bewegungskonto der Differenz je Periode, und alles, was nicht den Zugang
betrifft, gegen Gleichheit. Summen UND Einzelvertraege: Zwei gegenlaeufige
Fehler heben sich in einer Summe auf, in der Einzelliste nicht. Das
Deckungskapital steht bis zum Entscheid seiner Konvention mit Grund im
Beleg, nicht verglichen (``models.zugangsprobe.NICHT_VERGLICHEN``).

**Woher das Soll kommt** (Block F, Nachbesserung): aus den Bytes, die die
geltenden Abnahmen pinnen — ``aktuartest.json`` ueber A-M1,
``migrationssuite.json`` ueber A-M4. Liegt am festen Ort etwas anderes,
verweigert die Probe; sie rechnet nicht gegen ein Soll, das jeder ohne
Schluessel ersetzen kann.

**Was sie NICHT ist.** Keine zweite Abnahme und keine Entscheidung: Ein
Unterschied zwischen der Welt der Abnahme und der des Betriebs ist ein
Befund fuer den Menschen, der A-B2 zeichnet oder ablehnt. Der Beleg traegt
die Betriebszeichnung (Urheberschaft, ``models.anker.zeichne``), nicht die
Abnahme.

**Benannte Grenzen.** Der Zugangsstichtag muss ein Monatserster sein —
nur dort gibt es einen Abschluss, an dem die Differenz gegen die Uebernahme
gehalten werden kann. Die Probe laeuft mit dem Code, mit dem sie
aufgerufen wird; weicht ihr Code-Stand (Image-Digest und Revision, soweit
die Ablage sie erfasst hat, Hash des Pakets, Kern-Version) von dem der
letzten gruenen Protokollzeile ab, ist das ein Befund (dann rechnete die
Probe eine andere Welt als der Betrieb).

Knoten: klv, bu
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as _dt
import io
import json
import os
import shutil  # copytree; geloescht wird nur ueber betrieb._loeschen
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

import pandas as pd

from rechner_pipeline.bestand.abschluss import abschluss_pfad
from rechner_pipeline.bestand.manifest import sha256_bytes
from rechner_pipeline.bestand.parquet_io import read_portfolio
from rechner_pipeline.betrieb import tageslauf as tl
from rechner_pipeline.betrieb import uebernahme as ueb
from rechner_pipeline.models import zugangsprobe as zp
from rechner_pipeline.models.bestand import (
    LEDGER_NAMES,
    LEISTUNGSSPALTE,
    SCHEIBEN_NAMES,
    STAMM_NAMES,
    TAGESJOURNAL_NAMES,
    TERMINALE_STATUS,
)


class ZugangsprobeError(ValueError):
    """Die Probe kann nicht gefahren werden — mit Ausweg, ohne Beleg."""


#: Die Unterverzeichnisse der Arbeitskopie.
KOPIE_OHNE = "ohne"
KOPIE_MIT = "mit"


@dataclasses.dataclass
class Soll:
    """Was die Abnahmen des Falls ueber den Zugang sagen — in Zielnummern.

    ``jb`` und ``dk`` je Vertrag des GANZEN Zugangs aus der Migrationssuite
    (``bjb_stichtag_1``, ``dk_stichtag_1``), ``vs`` aus der Uebernahme;
    ``dk`` und ``dk_folge`` verglichen erst nach dem Entscheid der
    DK-Konvention (``models.zugangsprobe.NICHT_VERGLICHEN``). ``abnahmen``
    ist die Soll-Bindung des Belegs: je Rolle Datei, Hash der gelesenen
    Bytes und der Snapshot, der sie pinnt.
    """

    anzahl: int
    uebersetzung: Dict[int, int]
    vs: Dict[int, float]
    dk: Dict[int, float]
    jb: Dict[int, float]
    ledger: pd.DataFrame
    folgetermin: Optional[_dt.date]
    dk_folge: Dict[int, float]
    in_kraft_folge: Optional[int]
    eingaben: Dict[str, str]
    abnahmen: Dict[str, Dict[str, str]] = dataclasses.field(default_factory=dict)


def naechster_monatserster(tag: _dt.date) -> _dt.date:
    """Der erste Monatserster NACH ``tag`` — der naechste Monatsabschluss."""
    return (tag.replace(day=28) + _dt.timedelta(days=4)).replace(day=1)


def _ziel(uebersetzung: Mapping[int, int], police: Any, quelle: str) -> int:
    try:
        return uebersetzung[int(str(police))]
    except (KeyError, ValueError) as exc:
        raise ZugangsprobeError(
            f"{quelle}: Police {police!r} ist keine Police des Eingangs — der Beleg "
            "gehoert nicht zu diesem Zugangsstand") from exc


def lies_soll(
    fall: Path, stichtag: _dt.date, uebersetzung: Mapping[int, int], *,
    am4_snapshot_sha256: str,
    quelle: Optional[Path] = None,
    schluesselring: Optional[Mapping[str, bytes]] = None,
) -> Soll:
    """Das Soll aus dem Fall: Uebernahme, aktuarieller Test, Migrationssuite.

    Jede Datei wird EINMAL gelesen und ihr Hash in ``eingaben`` gebunden —
    der Beleg nennt die Bytes, gegen die gerechnet wurde. Gelesen werden die
    SYSTEMWERTE der Abnahmen: Die Probe fragt, ob der Betrieb rechnet, was
    das Zielsystem in der Abnahme gerechnet hat; die Toleranz gegen die
    Lieferung hat die Abnahme schon beurteilt.

    Block F, Nachbesserung (Pruefer-Befund 1): Die Belege der Abnahmen
    liegen am festen Ort im Fall und sind ohne Schluessel beschreibbar. Ihr
    Soll ist nur dann das der Abnahme, wenn ihre Bytes die sind, die der
    geltende, angenommene Snapshot pinnt — ``migrationssuite`` im
    A-M4-Snapshot ``am4_snapshot_sha256``, ``aktuartest`` im A-M1-Snapshot,
    den dieser als ``am1_snapshot`` pinnt (Kette, Entscheid und
    Freigabesignatur wie bei der Registrierung). Abweichung ist
    Verweigerung, kein Befund: Gegen ein fremdes Soll gibt es nichts zu
    rechnen. (Pruefer-Befunde 3 und 4): Jahresbeitrag und Deckungskapital
    je Vertrag ueber den GANZEN Zugang aus der Migrationssuite, nicht auf
    der Stichprobe des aktuariellen Tests.
    """
    from rechner_pipeline.models.zugangsprobe import SOLL_BELEGE, soll_bindung_fehler

    fall = Path(fall)
    quelle = Path(quelle) if quelle is not None else fall / "abgeleitet" / "bestand"
    ring = schluesselring if schluesselring is not None else ueb._STANDARD_SCHLUESSELRING
    eingaben: Dict[str, str] = {}

    def lies(pfad: Path, pflicht: bool = True) -> Optional[bytes]:
        if not pfad.is_file():
            if pflicht:
                raise ZugangsprobeError(
                    f"{pfad}: fehlt — ohne sie gibt es kein Soll, gegen das die Differenz "
                    "der Laeufe gehalten wird. Ausweg: den Fall bis A-M4 abnehmen "
                    "(aktuarieller Test und Migrationssuite im Bestands-Scope)")
            return None
        roh = pfad.read_bytes()
        try:
            schluessel = str(pfad.resolve().relative_to(fall.resolve()))
        except ValueError:
            schluessel = str(pfad)
        eingaben[schluessel] = sha256_bytes(roh)
        return roh

    bestand = read_portfolio(io.BytesIO(lies(quelle / "bestand.parquet")),
                             expected_columns=STAMM_NAMES)
    ledger = read_portfolio(io.BytesIO(lies(quelle / "ledger.parquet")),
                            expected_columns=LEDGER_NAMES)
    scheiben_roh = lies(quelle / "scheiben.parquet", pflicht=False)
    scheiben = (read_portfolio(io.BytesIO(scheiben_roh), expected_columns=SCHEIBEN_NAMES)
                if scheiben_roh is not None else None)
    # Versicherungssumme am Stichtag: die fuehrende Leistung des Stamms und
    # jede Erhoehungsscheibe, die am Stichtag besteht — dieselbe Definition
    # wie die Spalte ``leistung`` des Abschlusses (models.bestand).
    vs: Dict[int, float] = {}
    for pid, produkt, zeile in zip(bestand["police_id"], bestand["produkt"],
                                   bestand.to_dict("records")):
        vs[_ziel(uebersetzung, pid, "bestand.parquet")] = float(
            zeile[LEISTUNGSSPALTE[str(produkt)]])
    if scheiben is not None and len(scheiben):
        aktiv = scheiben[scheiben["erhoehung_datum"] <= pd.Timestamp(stichtag)]
        for pid, summe in zip(aktiv["police_id"], aktiv["sum_insured"]):
            vs[_ziel(uebersetzung, pid, "scheiben.parquet")] += float(summe)
    ledger = ledger.copy()
    ledger["police_id"] = [_ziel(uebersetzung, p, "ledger.parquet") for p in ledger["police_id"]]

    # Die Belege der Abnahmen — gelesen, gehasht und gegen die Pins gehalten.
    roh: Dict[str, bytes] = {rolle: lies(fall / datei) for rolle, (_, datei) in SOLL_BELEGE.items()}
    try:
        am4, _, _ = ueb.lies_am4_snapshot(fall, am4_snapshot_sha256, schluesselring=ring)
        am1_pin = (am4.get("pflichtbelege") or {}).get("am1_snapshot") or [None]
        am1: Optional[Dict[str, Any]] = None
        am1_verifiziert = False
        if isinstance(am1_pin[0], str):
            am1, _, am1_verifiziert = ueb.lies_abnahme_snapshot(
                fall, "A-M1", am1_pin[0], schluesselring=ring)
    except ueb.UebernahmeError as exc:
        raise ZugangsprobeError(
            f"die Abnahmen, auf denen das Soll steht, sind nicht lesbar oder nicht "
            f"geltend: {exc}") from exc
    abnahmen = {
        rolle: {"datei": datei, "gate": gate, "sha256": sha256_bytes(roh[rolle]),
                "snapshot_sha256": str(am4.get("snapshot_sha256") if gate == "A-M4" else am1_pin[0])}
        for rolle, (gate, datei) in SOLL_BELEGE.items()
    }
    bindung = soll_bindung_fehler(abnahmen, am4=am4, am1=am1)
    if am1 is not None and not am1_verifiziert:
        bindung.append("die Freigabesignatur des A-M1-Snapshots ist nicht verifiziert")
    if bindung:
        raise ZugangsprobeError(
            "das Soll der Probe ist nicht das der geltenden Abnahmen — "
            + "; ".join(bindung[:4])
            + ". Ausweg: die abgenommenen Belege wiederherstellen (aktuartest.json und "
            "migrationssuite.json in der Fassung, die A-M1 und A-M4 pinnen) oder die "
            "Abnahmen auf den heutigen Belegen neu entscheiden, dann die Probe fahren")
    try:
        aktuartest = json.loads(roh["aktuartest"].decode("utf-8"))
        suite = json.loads(roh["migrationssuite"].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ZugangsprobeError(f"Beleg der Abnahme nicht lesbar: {exc}") from exc
    if not isinstance(aktuartest, dict) or not isinstance(suite, dict):
        raise ZugangsprobeError("aktuartest.json und migrationssuite.json muessen JSON-Objekte sein")
    folgetermin = None
    if suite.get("stichtag_2"):
        try:
            folgetermin = _dt.date.fromisoformat(str(suite["stichtag_2"]))
        except ValueError as exc:
            raise ZugangsprobeError(f"migrationssuite.json: stichtag_2 unlesbar: {exc}") from exc
    dk: Dict[int, float] = {}
    jb: Dict[int, float] = {}
    dk_folge: Dict[int, float] = {}
    lebend_ungeprueft = 0
    abgebrochen = 0
    for vertrag in suite.get("vertraege") or []:
        ziel = _ziel(uebersetzung, vertrag.get("police_id"), "migrationssuite.json")
        pruefungen = vertrag.get("pruefungen") or []
        for groesse, ablage in (("dk_stichtag_1", dk), ("bjb_stichtag_1", jb),
                                ("dk_stichtag_2", dk_folge)):
            treffer = [p for p in pruefungen if p.get("groesse") == groesse]
            if len(treffer) > 1:
                raise ZugangsprobeError(
                    f"migrationssuite.json: Police {vertrag.get('police_id')!r} traegt "
                    f"{groesse} mehrfach — der Wert ist mehrdeutig")
            if treffer:
                ablage[ziel] = float(treffer[0]["system"])
        luecken = [g for g in vertrag.get("nicht_geprueft") or []
                   if str(g).startswith("dk_stichtag_2")]
        if ziel not in dk_folge:
            if "dk_stichtag_1" in (vertrag.get("nicht_geprueft") or []):
                # Nur eine ABGEBROCHENE Pruefung fuehrt dk_stichtag_1 als
                # Luecke (qa.migrationssuite.pruefe_bestand): Ueber den
                # Vertrag ist nichts bekannt, nicht einmal, ob er lebt.
                abgebrochen += 1
            elif luecken:
                lebend_ungeprueft += 1    # lebt, aber ohne Vergleichswert
    # Die Zahl in Kraft am Folgetermin ist nur belegt, wenn von jedem Vertrag
    # bekannt ist, ob er lebt.
    in_kraft_folge = None if abgebrochen else len(dk_folge) + lebend_ungeprueft
    return Soll(
        anzahl=int(len(bestand)), uebersetzung=dict(uebersetzung), vs=vs, dk=dk, jb=jb,
        ledger=ledger, folgetermin=folgetermin, dk_folge=dk_folge,
        in_kraft_folge=in_kraft_folge, eingaben=dict(sorted(eingaben.items())),
        abnahmen=abnahmen)


# --------------------------------------------------------------------------- #
# Vergleich
# --------------------------------------------------------------------------- #


def _abschluesse(ablage: tl.Ablage) -> Dict[_dt.date, Path]:
    return {t: abschluss_pfad(ablage.abschluesse, t) for t in tl._festgeschriebene_abschluesse(ablage)}


def _zeilen_je_police(tabelle: pd.DataFrame) -> Dict[int, Dict[str, Any]]:
    return {int(z["police_id"]): z for z in tabelle.to_dict("records")}


def _gleich(a: Any, b: Any) -> bool:
    if isinstance(a, float) and isinstance(b, float):
        return a == b or (a != a and b != b)
    return a == b


def _je_vertrag(
    ist: Mapping[int, float], soll: Mapping[int, float],
) -> List[Dict[str, Any]]:
    """Die Vertraege, deren Einzelwert nicht stimmt (auch: fehlt auf einer Seite)."""
    abweichend = []
    for pid in sorted(set(soll) | set(ist)):
        s, i = soll.get(pid), ist.get(pid)
        if s is None or i is None or abs(float(i) - float(s)) > zp.TOLERANZ:
            abweichend.append({"police_id": pid, "soll": s, "ist": i})
    return abweichend


def _vorfaelle(zeilen: pd.DataFrame) -> pd.DataFrame:
    return zeilen[["police_id", "ereignis", "status_date"]].drop_duplicates()


def vergleiche(
    ohne: Path, mit: Path, soll: Soll, *, stichtag: _dt.date,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Die Differenz der beiden Laeufe gegen das Soll — aus den Bytes der Kopien.

    Liest die Abschluesse und Tagesjournale beider Kopien, wie die Laeufe sie
    hinterlassen haben, und liefert ``(vergleiche, befunde)`` im Vertrag von
    ``models.zugangsprobe``. Eine eigene Funktion, damit ein Test die
    Ausgabe eines Laufs verstuemmeln und die Probe denselben Weg noch einmal
    fragen kann (Zaehltest je Groesse).
    """
    a_ohne, a_mit = tl.Ablage(Path(ohne)), tl.Ablage(Path(mit))
    befunde: List[str] = []
    vergleiche_: List[Dict[str, Any]] = []
    ausserhalb: List[Dict[str, Any]] = []
    p_ids = set(soll.uebersetzung.values())
    p_liste = sorted(p_ids)

    stichtage_ohne, stichtage_mit = _abschluesse(a_ohne), _abschluesse(a_mit)
    if set(stichtage_ohne) != set(stichtage_mit):
        befunde.append(
            f"die Laeufe schrieben verschiedene Abschluesse: ohne "
            f"{sorted(t.isoformat() for t in stichtage_ohne)}, mit "
            f"{sorted(t.isoformat() for t in stichtage_mit)}")
    # Ein Soll ohne einen einzigen Wert ist kein Soll: Eine Summe ueber
    # nichts ist 0, ihr Ist auch — der Vergleich waere gruen, ohne etwas
    # geprueft zu haben (Detektor ohne Treffer). Dann ist die Groesse "nicht
    # belegt", und die Probe besteht nicht.
    pflicht = [("Jahresbeitrag (bjb_stichtag_1)", soll.jb)]
    if "deckungskapital" not in zp.NICHT_VERGLICHEN:
        pflicht.append(("Deckungskapital (dk_stichtag_1)", soll.dk))
    for name, werte in pflicht:
        if not werte:
            befunde.append(
                f"die Migrationssuite belegt am Zugangsstichtag kein {name} — die "
                "Differenz ist dort nicht gegen die Abnahme zu halten")
    if not len(soll.ledger):
        befunde.append(
            "der Ledger der Uebernahme ist leer — die Zugangsbuchungen sind nicht "
            "gegen ihn zu halten")
    if stichtag not in stichtage_mit:
        befunde.append(
            f"kein Abschluss am Zugangsstichtag {stichtag.isoformat()} — die Differenz "
            "ist dort nicht gegen die Uebernahme zu halten")
    diff_anzahl: Dict[_dt.date, int] = {}
    for s in sorted(set(stichtage_ohne) & set(stichtage_mit)):
        ao = read_portfolio(stichtage_ohne[s])
        am = read_portfolio(stichtage_mit[s])
        zo, zm = _zeilen_je_police(ao), _zeilen_je_police(am)
        for pid in sorted(set(zo) - set(zm)):
            ausserhalb.append({"stichtag": s.isoformat(), "police_id": pid,
                               "art": "nur ohne den Eingang im Abschluss"})
        for pid in sorted(set(zo) & set(zm)):
            if pid in p_ids:
                ausserhalb.append({"stichtag": s.isoformat(), "police_id": pid,
                                   "art": "Vertrag des Eingangs im Lauf ohne ihn"})
            spalten = [k for k in zo[pid] if not _gleich(zo[pid][k], zm[pid].get(k))]
            if spalten:
                ausserhalb.append({"stichtag": s.isoformat(), "police_id": pid,
                                   "art": f"Abschlusszeile verschieden: {spalten}"})
        diff = {pid: zm[pid] for pid in set(zm) - set(zo)}
        if s < stichtag:
            for pid in sorted(diff):
                ausserhalb.append({"stichtag": s.isoformat(), "police_id": pid,
                                   "art": "Zeile vor dem Zugangsstichtag"})
            diff_anzahl[s] = 0
            continue
        for pid in sorted(set(diff) - p_ids):
            ausserhalb.append({"stichtag": s.isoformat(), "police_id": pid,
                               "art": "nur mit dem Eingang, aber kein Vertrag des Eingangs"})
        diff_anzahl[s] = len(diff)
        leistung = {pid: float(z["leistung"]) for pid, z in diff.items()}
        dk = {pid: float(z["deckungskapital"]) for pid, z in diff.items()}
        jb = {pid: float(z["jahresbeitrag"]) for pid, z in diff.items()}
        iso = s.isoformat()

        def deckungskapital(termin: str, soll_dk: Mapping[int, float]) -> Dict[str, Any]:
            # Die vorbereitete Stelle (Pruefer-Befund 3): Bis der Maintainer
            # die Konvention entscheidet, steht das Deckungskapital mit
            # seinem Grund im Beleg und wird NICHT verglichen — kein
            # stiller Verzicht, kein gruener Vergleich ungleicher Groessen.
            # Danach je Vertrag ueber den ganzen Zugang.
            if "deckungskapital" in zp.NICHT_VERGLICHEN:
                return zp.vergleich("deckungskapital", termin, iso, None, sum(dk.values()),
                                    umfang=len(diff), grund=zp.NICHT_VERGLICHEN["deckungskapital"])
            return zp.vergleich("deckungskapital", termin, iso,
                                sum(soll_dk.values()) if soll_dk else None, sum(dk.values()),
                                umfang=len(soll_dk), abweichend=_je_vertrag(dk, soll_dk))

        if s == stichtag:
            ids_soll = {pid: 1.0 for pid in p_ids}
            vergleiche_ += [
                zp.vergleich("in_kraft", "zugangsstichtag", iso, soll.anzahl, len(diff),
                             umfang=soll.anzahl,
                             abweichend=_je_vertrag({p: 1.0 for p in diff}, ids_soll)),
                zp.vergleich("versicherungssumme", "zugangsstichtag", iso,
                             sum(soll.vs.values()), sum(leistung.values()),
                             umfang=len(soll.vs), abweichend=_je_vertrag(leistung, soll.vs)),
                deckungskapital("zugangsstichtag", soll.dk),
                # Je Vertrag ueber den GANZEN Zugang (Pruefer-Befund 4): die
                # Migrationssuite belegt jeden Vertrag, der aktuarielle
                # Test nur seine Stichprobe.
                zp.vergleich("jahresbeitrag", "zugangsstichtag", iso,
                             sum(soll.jb.values()) if soll.jb else None, sum(jb.values()),
                             umfang=len(soll.jb), abweichend=_je_vertrag(jb, soll.jb)),
            ]
        elif s == soll.folgetermin:
            ohne_soll = ("nicht belegt: die Migrationssuite belegt am Folgestichtag nur "
                         "Deckungskapital und Bestand")
            vergleiche_ += [
                zp.vergleich("in_kraft", "folgetermin", iso, soll.in_kraft_folge, len(diff),
                             umfang=len(diff)),
                deckungskapital("folgetermin", soll.dk_folge),
                zp.vergleich("versicherungssumme", "folgetermin", iso, None,
                             sum(leistung.values()), umfang=len(diff), grund=ohne_soll),
                zp.vergleich("jahresbeitrag", "folgetermin", iso, None,
                             sum(jb.values()), umfang=len(diff), grund=ohne_soll),
            ]
        else:
            vergleiche_ += [
                zp.vergleich(g, "zwischen", iso, None, wert, umfang=len(diff))
                for g, wert in (("in_kraft", len(diff)),
                                ("versicherungssumme", sum(leistung.values())),
                                ("jahresbeitrag", sum(jb.values())))]
            vergleiche_.append(deckungskapital("zwischen", {}) if "deckungskapital" in zp.NICHT_VERGLICHEN
                               else zp.vergleich("deckungskapital", "zwischen", iso, None,
                                                 sum(dk.values()), umfang=len(diff)))

    # Die Buchungen: Tagesjournale beider Laeufe.
    jo = read_portfolio(a_ohne.tagesjournal_pfad, expected_columns=TAGESJOURNAL_NAMES)
    jm = read_portfolio(a_mit.tagesjournal_pfad, expected_columns=TAGESJOURNAL_NAMES)
    for zeile in jo[jo["police_id"].isin(p_liste)].to_dict("records"):
        ausserhalb.append({"police_id": int(zeile["police_id"]),
                           "art": f"Buchung eines Vertrags des Eingangs im Lauf ohne ihn: {zeile['ereignis']}"})
    spalten = list(TAGESJOURNAL_NAMES)
    fremd_mit = jm[~jm["police_id"].isin(p_liste)].sort_values(spalten, kind="stable").reset_index(drop=True)
    fremd_ohne = jo[~jo["police_id"].isin(p_liste)].sort_values(spalten, kind="stable").reset_index(drop=True)
    if not fremd_mit.equals(fremd_ohne):
        schluessel = ["police_id", "ereignis", "status_date", "betrag_art", "betrag", "buchungsdatum"]
        a = set(map(tuple, fremd_ohne[schluessel].astype(str).values.tolist()))
        b = set(map(tuple, fremd_mit[schluessel].astype(str).values.tolist()))
        for z in sorted(a ^ b):
            ausserhalb.append({"police_id": int(z[0]),
                               "art": f"Buchung verschieden ({'nur ohne' if z in a else 'nur mit'}): {z[1]} {z[2]} {z[3]} {z[4]}"})
        if not a ^ b:
            ausserhalb.append({"police_id": None, "art": "Journal der fremden Vertraege verschieden"})
    eigene = jm[jm["police_id"].isin(p_liste)]

    # Zugang: je uebernommenem Vertrag genau ein Zugangsvorfall.
    zug = _vorfaelle(eigene[eigene["ereignis"] == "ZUG"])
    zug_je = zug.groupby("police_id").size().to_dict() if len(zug) else {}
    vergleiche_.append(zp.vergleich(
        "zugang", "fenster", None, soll.anzahl, int(len(zug)), umfang=soll.anzahl,
        abweichend=[{"police_id": p, "soll": 1, "ist": int(zug_je.get(p, 0))}
                    for p in sorted(p_ids | set(zug_je)) if zug_je.get(p, 0) != 1]))

    # Die Buchungen der Uebernahme bis zum Stichtag: dieselben wie ihr Ledger.
    bis_stichtag = eigene[eigene["status_date"] <= pd.Timestamp(stichtag)]
    schl = ["police_id", "ereignis", "status_date", "betrag_art"]

    def je_schluessel(t: pd.DataFrame) -> Dict[Tuple, float]:
        werte: Dict[Tuple, float] = {}
        for z in t[schl + ["betrag"]].to_dict("records"):
            k = (int(z["police_id"]), str(z["ereignis"]), pd.Timestamp(z["status_date"]).date().isoformat(),
                 str(z["betrag_art"]))
            werte[k] = werte.get(k, 0.0) + float(z["betrag"])
        return werte

    ist_b, soll_b = je_schluessel(bis_stichtag), je_schluessel(soll.ledger)
    vergleiche_.append(zp.vergleich(
        "zugangsbuchungen", "zugangsstichtag", stichtag.isoformat(),
        sum(soll_b.values()) if soll_b else None, sum(ist_b.values()), umfang=len(soll_b),
        abweichend=[{"buchung": "/".join(map(str, k)), "soll": s_, "ist": i_}
                    for k in sorted(set(ist_b) | set(soll_b))
                    for s_, i_ in [(soll_b.get(k), ist_b.get(k))]
                    if s_ is None or i_ is None or abs(i_ - s_) > zp.TOLERANZ]))

    # Das Bewegungskonto der Differenz: Anfang + Zugang - Abgang = Ende, je
    # Periode (Vormonatserster, Stichtag] auf dem Sichtbarkeitstag
    # (max(Wirkungstag, Buchungstag)), wie die Monatskennzahlen zaehlen.
    sichtbar = eigene[["status_date", "buchungsdatum"]].max(axis=1)
    vorher = 0
    for s in sorted(diff_anzahl):
        if s < stichtag:
            vorher = diff_anzahl[s]
            continue
        vormonat = (s.replace(day=1) - _dt.timedelta(days=1)).replace(day=1)
        periode = eigene[(sichtbar > pd.Timestamp(vormonat)) & (sichtbar <= pd.Timestamp(s))]
        zugang = int(len(_vorfaelle(periode[periode["ereignis"] == "ZUG"])))
        abgang = int(periode[periode["ereignis"].isin(TERMINALE_STATUS)]["police_id"].nunique())
        rest = vorher + zugang - abgang - diff_anzahl[s]
        vergleiche_.append(zp.vergleich(
            "bewegungskonto", "zugangsstichtag" if s == stichtag else (
                "folgetermin" if s == soll.folgetermin else "zwischen"),
            s.isoformat(), 0, rest, umfang=diff_anzahl[s],
            abweichend=([{"anfang": vorher, "zugang": zugang, "abgang": abgang,
                          "ende": diff_anzahl[s]}] if rest else [])))
        vorher = diff_anzahl[s]

    vergleiche_.append(zp.vergleich(
        "ausserhalb_des_zugangs", "fenster", None, 0, len(ausserhalb),
        umfang=len(ausserhalb), abweichend=ausserhalb))
    return vergleiche_, befunde


# --------------------------------------------------------------------------- #
# Die Laeufe
# --------------------------------------------------------------------------- #


def _lauf_beleg(ablage: tl.Ablage, code: int, zeile: Mapping[str, Any]) -> Dict[str, Any]:
    from rechner_pipeline.models.anker import jsonl_zeilen

    rohe = (jsonl_zeilen(ablage.protokoll_pfad.read_text(encoding="utf-8"))
            if ablage.protokoll_pfad.is_file() else [])
    return {
        "exit": int(code),
        "heute": zeile.get("heute"),
        "uebernommen": bool(zeile.get("uebernommen")),
        "fehler": zeile.get("fehler"),
        "manifest_sha256": zeile.get("manifest_sha256"),
        "journal_sha256": tl._datei_hash(ablage.tagesjournal_pfad),
        "protokollzeile_sha256": tl._zeilen_hash(rohe[-1]) if rohe else None,
        "abschluesse": {t.isoformat(): tl._datei_hash(p) for t, p in sorted(_abschluesse(ablage).items())},
    }


def _kopiere(stand: Path, ziel: Path, kennzeichen: Dict[str, Any]) -> tl.Ablage:
    """Eine Kopie der Ablage — gekennzeichnet VOR dem ersten kopierten Byte.

    Runde F, F6: Erst kopieren, dann kennzeichnen liess bei einem
    Prozessende dazwischen eine ungekennzeichnete Vollkopie zurueck, auf der
    der Tageslauf gruen fuhr. Jetzt entsteht das Zielverzeichnis leer, das
    Kennzeichen hinein, dann die Ablage dazu: Jeder Zwischenstand traegt das
    Kennzeichen (auch ein halb geschriebenes verweigert, denn gefragt wird,
    ob die Datei DA ist). Das Original traegt nie eines
    (:func:`tl.probenkopie_fehler` vorher), also ueberschreibt die Kopie es
    nicht.
    """
    ziel.mkdir(parents=True)
    (ziel / tl.ZUGANGSPROBE_KOPIE_DATEI).write_text(
        json.dumps({**kennzeichen, "kopie": ziel.name}, ensure_ascii=False, indent=2,
                   sort_keys=True) + "\n",
        encoding="utf-8")
    shutil.copytree(stand, ziel, symlinks=True, dirs_exist_ok=True)
    return tl.Ablage(ziel)


def zugangsprobe(
    stand: Path,
    fall: Path,
    stichtag: _dt.date,
    *,
    bis: Optional[_dt.date] = None,
    arbeit: Optional[Path] = None,
    schluessel: Optional[Path] = None,
    zeichnungsordnung: Optional[Path] = None,
    schluesselring: Optional[Mapping[str, bytes]] = None,
    snapshot_sha256: Optional[str] = None,
    quelle: Optional[Path] = None,
    image_digest: Optional[str] = None,
    jetzt: Optional[_dt.datetime] = None,
) -> Dict[str, Any]:
    """Die Probe fahren und den gezeichneten Beleg liefern (geschrieben wird er
    von :func:`main`; das Original wird nie beschrieben).

    ``arbeit``: das Verzeichnis der zwei Kopien, ausserhalb der Ablage; es
    darf nicht existieren (oder muss leer sein) und bleibt stehen, damit ein
    Mensch die Laeufe ansehen kann. Ohne Angabe ein temporaeres
    Verzeichnis, das danach entfernt wird. Schluessel, Ordnung und
    Freigabe-Schluesselring wie bei ``betrieb.uebernahme``: Die Probe
    registriert in ihrer Kopie genau so, wie die Registrierung es spaeter tut.

    ``jetzt``: der Zeitpunkt der Probe (Default: jetzt, UTC). Er steht mit
    der Kennung der Probe im Kennzeichen jeder Kopie und gezeichnet in jeder
    Protokollzeile, die die Probe auf ihr schreibt (Runde F, F9) — der
    Tageslauf zieht dafuer keine Uhr.
    """
    from rechner_pipeline.kern import __version__ as kern_version
    from rechner_pipeline.models.zeichnung import ausserhalb_von

    stand, fall = Path(stand), Path(fall)
    original = tl.Ablage(stand)
    if not stand.is_dir():
        raise ZugangsprobeError(f"{stand}: keine Ablage")
    # Keine Probe auf einer Probenkopie (Runde F, F6/F9): Ihre Kopie truege
    # das Kennzeichen des Originals mit, und ihre Zeilen sind Probezeilen.
    kopie_fehler = tl.probenkopie_fehler(original)
    if kopie_fehler:
        raise ZugangsprobeError(
            f"{kopie_fehler} — die Probe laeuft auf der produktiven Ablage")
    if stichtag.day != 1:
        raise ZugangsprobeError(
            f"Zugangsstichtag {stichtag.isoformat()} ist kein Monatserster — nur an einem "
            "Monatsersten gibt es einen Abschluss, an dem die Differenz gegen die "
            "Uebernahme gehalten werden kann (benannte Grenze der Probe, ADR-022)")
    ziel = naechster_monatserster(stichtag)
    if bis is not None and bis < ziel:
        raise ZugangsprobeError(
            f"--bis {bis.isoformat()} liegt vor dem naechsten Monatsabschluss "
            f"{ziel.isoformat()} — die Probe laeuft mindestens bis zu ihm")
    bis = bis or ziel
    try:
        zeichner = tl.betriebszeichner(
            original, schluessel, zeichnungsordnung, wofuer="die Zugangsprobe",
            ohne="keine Zugangsprobe", flag="--schluessel")
    except tl.TageslaufError as exc:
        raise ZugangsprobeError(str(exc)) from exc
    try:
        fallname = str(json.loads((fall / "fall.json").read_text(encoding="utf-8"))["name"])
    except (OSError, ValueError, KeyError) as exc:
        raise ZugangsprobeError(f"{fall}: kein Fall-Arbeitsbereich ({exc})") from exc
    if (original.uebernahme / fallname).exists():
        raise ZugangsprobeError(
            f"{original.uebernahme / fallname}: der Fall ist in dieser Ablage schon "
            "registriert — die Probe rechnet einen Zugang, der noch nicht geschehen ist")

    temporaer = arbeit is None
    arbeit = Path(tempfile.mkdtemp(prefix="zugangsprobe-")) if arbeit is None else Path(arbeit)
    if not ausserhalb_von(arbeit, stand, muss_existieren=False) or not ausserhalb_von(
            stand, arbeit, muss_existieren=False):
        raise ZugangsprobeError(
            f"--arbeit {arbeit}: die Kopien liegen ausserhalb der Ablage (und die Ablage "
            "nicht in ihnen) — sonst saehe der naechste Lauf sie als Teil der Ablage")
    if arbeit.exists() and any(arbeit.iterdir()):
        raise ZugangsprobeError(
            f"--arbeit {arbeit}: nicht leer — eine Probe ueberschreibt keine alten Kopien")
    try:
        # 1. Unter der Lauf-Sperre: Stand bestimmen und zweimal kopieren.
        #    Das Original wird dabei nur gelesen.
        try:
            with tl.lauf_sperre(original):
                gefuehrt = tl.gefuehrter_tag(original, zeichner)
                stand_inhalt = tl.ablage_stand(original)
                zeitpunkt = (jetzt or _dt.datetime.now(_dt.timezone.utc)).isoformat()
                kennzeichen = {"fall": fallname, "original": str(stand),
                               "ablage_stand_sha256": zp.stand_sha256(stand_inhalt),
                               "zeitpunkt": zeitpunkt}
                # Die Kennung der Probe: beide Kopien tragen dieselbe, jede
                # Probezeile nennt sie (Runde F, F9).
                kennzeichen["kennung"] = sha256_bytes(json.dumps(
                    kennzeichen, ensure_ascii=False, sort_keys=True).encode("utf-8"))
                ohne = _kopiere(stand, arbeit / KOPIE_OHNE, kennzeichen)
                mit = _kopiere(stand, arbeit / KOPIE_MIT, kennzeichen)
                if tl.ablage_stand(original) != stand_inhalt:  # pragma: no cover - Sperre haelt
                    raise ZugangsprobeError("die Ablage aenderte sich waehrend der Kopie")
        except tl.TageslaufError as exc:
            raise ZugangsprobeError(str(exc)) from exc
        if gefuehrt is not None and gefuehrt >= stichtag:
            raise ZugangsprobeError(
                f"die Ablage fuehrt bereits {gefuehrt.isoformat()}, der Zugangsstichtag "
                f"{stichtag.isoformat()} liegt nicht danach — sein Abschluss steht fest "
                "(ADR-011); der Zugang gehoert in die offene Zeit")
        for kopie in (ohne, mit):
            if zp.stand_sha256(tl.ablage_stand(kopie)) != kennzeichen["ablage_stand_sha256"]:
                raise ZugangsprobeError(f"{kopie.wurzel}: die Kopie traegt nicht den Stand des Originals")

        # 2. In die Kopie "mit" registrieren — wie die Registrierung spaeter.
        try:
            eingang_dir = ueb.eingang_anlegen(
                mit.wurzel, fall, stichtag, quelle=quelle, snapshot_sha256=snapshot_sha256,
                schluesselring=schluesselring, betriebsschluessel=schluessel,
                zeichnungsordnung=zeichnungsordnung, probe_kopie=True)
        except ueb.UebernahmeError as exc:
            raise ZugangsprobeError(f"die Registrierung in der Kopie verweigert: {exc}") from exc
        eingang_roh = (eingang_dir / ueb.EINGANG_DATEI).read_bytes()
        eingang = json.loads(eingang_roh.decode("utf-8"))
        uebersetzung = ueb.zielnummern(eingang_dir)
        soll = lies_soll(fall, stichtag, uebersetzung, quelle=quelle,
                         am4_snapshot_sha256=str(eingang.get("snapshot_sha256")),
                         schluesselring=schluesselring)

        # 3. Beide Laeufe bis zum Ziel (verpasste Tage holt der Lauf nach;
        #    der Stand ist derselbe, als liefe er jede Nacht).
        befunde: List[str] = []
        laeufe: Dict[str, Dict[str, Any]] = {}
        for name, kopie in ((KOPIE_OHNE, ohne), (KOPIE_MIT, mit)):
            try:
                code, zeile = tl.tageslauf(
                    kopie, bis, schluessel=schluessel, zeichnungsordnung=zeichnungsordnung,
                    image_digest=image_digest, zugangsprobe_fall=fallname)
            except tl.TageslaufError as exc:
                raise ZugangsprobeError(f"Lauf {name!r}: {exc}") from exc
            laeufe[name] = _lauf_beleg(kopie, code, zeile)
            if code != tl.EXIT_OK:
                meldung = zeile.get("fehler") or "; ".join((zeile.get("pb1") or {}).get("befunde", [])[:3])
                if name == KOPIE_OHNE:
                    raise ZugangsprobeError(
                        f"der Lauf OHNE den Eingang ist rot (Exit {code}: {meldung}) — die "
                        "Ablage selbst laeuft nicht; erst den Tageslauf klaeren")
                befunde.append(
                    f"der Lauf MIT dem Eingang ist rot (Exit {code}: {meldung}) — der Zugang "
                    "bricht den Betrieb")

        vergleiche_: List[Dict[str, Any]] = []
        if not befunde:
            vergleiche_, v_befunde = vergleiche(ohne.wurzel, mit.wurzel, soll, stichtag=stichtag)
            befunde += v_befunde
        # Rechnete die Probe mit dem Code, mit dem der Betrieb fuehrt? Die
        # Kern-Version allein ist keine Identitaet (Block F, Nachbesserung,
        # Pruefer-Befund 6): gehalten werden Image-Digest und Revision,
        # soweit die Ablage sie erfasst hat, und der Hash des Pakets gegen
        # die letzte gruene Protokollzeile.
        system = tl.code_stand(image_digest)
        letzte = _letzte_gruene_zeile(original)
        kern_betrieb = None if letzte is None else (
            str(letzte["kern_version"]) if letzte.get("kern_version") is not None else None)
        if kern_betrieb is not None and kern_betrieb != kern_version:
            befunde.append(
                f"die Probe rechnet mit Kern {kern_version}, die Ablage wurde zuletzt mit "
                f"Kern {kern_betrieb} gefuehrt — sie rechnete eine andere Welt als der Betrieb. "
                "Ausweg: die Probe mit dem Stand des produktiven Images fahren")
        if letzte is not None:
            abweichend = zp.code_stand_abweichungen(letzte, system, nicht_erfasst=tl.NICHT_ERFASST)
            if abweichend:
                befunde.append(
                    "die Probe rechnet mit einem anderen Code-Stand als die letzte gruene "
                    f"Zeile der Ablage ({'; '.join(abweichend)}) — sie rechnete eine andere "
                    "Welt als der Betrieb. Ausweg: die Probe im produktiven Image fahren "
                    "(--image-digest bzw. PLV_IMAGE_DIGEST wie im Tageslauf)")
            elif not zp.code_stand_belegt(letzte, nicht_erfasst=tl.NICHT_ERFASST):
                befunde.append(
                    "die letzte gruene Zeile der Ablage belegt keinen Code-Stand (weder "
                    "Image noch quellcode_sha256) — ob die Probe dieselbe Welt rechnete, "
                    "ist nicht zu zeigen. Ausweg: einen Tageslauf mit dem heutigen Stand "
                    "fahren, dann die Probe")
        folgetermin = soll.folgetermin
        beleg: Dict[str, Any] = {
            "schema_version": zp.SCHEMA_VERSION,
            "art": zp.ART,
            "fall": fallname,
            "stichtag": stichtag.isoformat(),
            "bis": bis.isoformat(),
            "gefuehrt_vorher": gefuehrt.isoformat() if gefuehrt else None,
            "ablage_stand": {"sha256": kennzeichen["ablage_stand_sha256"], "inhalt": stand_inhalt},
            "eingang": {"sha256": sha256_bytes(eingang_roh), "inhalt": eingang},
            "am4_snapshot_sha256": eingang.get("snapshot_sha256"),
            "laeufe": laeufe,
            "config_sha256": stand_inhalt.get("config_sha256"),
            "kern_version": kern_version,
            "kern_version_betrieb": kern_betrieb,
            "system": system,
            "eingaben": soll.eingaben,
            # Die Soll-Bindung: je Beleg der Abnahmen Datei, Hash und der
            # Snapshot, der sie pinnt (Pruefer-Befund 1).
            "abnahmen": soll.abnahmen,
            # Was je Abschlussspalte gehalten wird, und was mit welchem
            # Grund nicht (Pruefer-Befunde 3 und 8).
            "abdeckung": zp.abdeckung(),
            "nicht_verglichen": dict(zp.NICHT_VERGLICHEN),
            "folgetermin": {
                "stichtag": folgetermin.isoformat() if folgetermin else None,
                "gedeckt": bool(folgetermin and stichtag < folgetermin <= bis
                                and folgetermin.day == 1),
                "grund": ("im Fenster der Probe" if folgetermin and stichtag < folgetermin <= bis
                          and folgetermin.day == 1 else
                          "kein Monatsabschluss im Fenster der Probe — mit --bis verlaengern"
                          if folgetermin else "die Migrationssuite nennt keinen Folgestichtag"),
            },
            "groessen": list(zp.GROESSEN),
            "vergleiche": vergleiche_,
            "befunde": befunde,
            "bestanden": zp.bestanden_aus(vergleiche_, befunde),
        }
        beleg["betriebszeichnung"] = zeichner.zeichne({"zugangsprobe": beleg})
        return beleg
    finally:
        if temporaer:
            # Durch die eine Loeschfunktion des Betriebs (T24-07): nur das
            # eigene Temp-Verzeichnis dieses Aufrufs, an seinem Namen erkannt.
            # Ein Rest ist kein Grund, die Probe scheitern zu lassen — er wird
            # genannt, nicht verschwiegen.
            from rechner_pipeline.betrieb._loeschen import LoeschFehler, entferne_verzeichnis

            try:
                entferne_verzeichnis(
                    arbeit, innerhalb=arbeit.parent,
                    name_ok=lambda n: n.startswith("zugangsprobe-"),
                    grund="Kopien einer Zugangsprobe")
            except (LoeschFehler, OSError) as exc:
                print(f"zugangsprobe: Warnung: Kopien nicht entfernt ({exc}) — {arbeit}",
                      file=sys.stderr)


def _letzte_gruene_zeile(ablage: tl.Ablage) -> Optional[Dict[str, Any]]:
    """Die letzte gruene Protokollzeile (None: nie gefuehrt)."""
    from rechner_pipeline.models.anker import jsonl_zeilen

    if not ablage.protokoll_pfad.is_file():
        return None
    letzte = None
    for roh in jsonl_zeilen(ablage.protokoll_pfad.read_text(encoding="utf-8")):
        zeile = json.loads(roh)
        if isinstance(zeile, dict) and zeile.get("uebernommen"):
            letzte = zeile
    return letzte


def _schreibe_beleg(out: Path, beleg: Mapping[str, Any]) -> None:
    """Den Beleg vollstaendig daneben schreiben, dann in einem Zug an ``out``.

    Die Tempdatei entsteht mit den Rechten, die der Beleg vorher hatte
    (0666 vor der umask, wie ``write_text``) — der Beleg liegt im Fall und
    wird von anderen gelesen; ein mkstemp gaebe ihm still 0600.
    """
    inhalt = (json.dumps(beleg, ensure_ascii=False, indent=2, sort_keys=True)
              + "\n").encode("utf-8")
    out.parent.mkdir(parents=True, exist_ok=True)
    temp = out.with_name(f".{out.name}.{os.getpid()}.tmp")
    try:
        temp.unlink(missing_ok=True)
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
        with os.fdopen(fd, "wb") as datei:
            datei.write(inhalt)
            datei.flush()
            os.fsync(datei.fileno())
        os.replace(temp, out)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.betrieb.zugangsprobe",
        description="Den Zugang eines abgenommenen Bestands auf einer Kopie der produktiven "
        "Ablage vorab fahren (mit und ohne Eingang) und die Differenz gegen die Abnahme "
        "belegen — der Beleg der Zugangsabnahme A-B2 (ADR-022).")
    parser.add_argument("--stand", required=True, help="Datenverzeichnis der Laufzeitumgebung.")
    parser.add_argument("--fall", required=True, help="Fall-Arbeitsbereich (faelle/<name>).")
    parser.add_argument("--stichtag", required=True, help="Zugangsstichtag (ISO, ein Monatserster).")
    parser.add_argument("--bis", default=None,
                        help="Letzter gefuehrter Tag der Probe (Default: der naechste Monatsabschluss; "
                             "weiter z. B. bis zum Folgestichtag der Migrationssuite).")
    parser.add_argument("--schluessel", required=True,
                        help="Betriebsschluessel (Rolle betrieb/<name>), ausserhalb der Ablage.")
    parser.add_argument("--zeichnungsordnung", required=True,
                        help="Zeichnungsordnung, die dem Betriebsschluessel seine Rolle gibt.")
    parser.add_argument("--freigabe-schluessel", action="append", default=None,
                        help="Freigabeschluessel (mehrfach moeglich), ausserhalb des Falls; prueft "
                             "die Signatur des A-M4-Snapshots wie die Registrierung. Pflicht.")
    parser.add_argument("--snapshot", default=None,
                        help="Snapshot-Hash der A-M4-Annahme (Default: aus dem Gate-Beleg des Falls).")
    parser.add_argument("--quelle", default=None,
                        help="Verzeichnis des Zugangsstands (Default: <fall>/abgeleitet/bestand); "
                             "dieselbe Angabe wie spaeter bei der Registrierung.")
    parser.add_argument("--arbeit", default=None,
                        help="Verzeichnis fuer die zwei Kopien, ausserhalb der Ablage, leer; bleibt "
                             "stehen (Default: temporaer, danach entfernt).")
    parser.add_argument("--out", default=None,
                        help=f"Beleg (Default: <fall>/{zp.BELEG_RELATIV} — dort liest ihn A-B2).")
    parser.add_argument("--image-digest", dest="image_digest", default=None,
                        help="Digest des produktiven Images fuer den Beleg (Default: PLV_IMAGE_DIGEST).")
    ns = parser.parse_args(argv)
    try:
        stichtag = _dt.date.fromisoformat(ns.stichtag)
        bis = _dt.date.fromisoformat(ns.bis) if ns.bis else None
    except ValueError as exc:
        print(f"zugangsprobe: Datum: {exc}", file=sys.stderr)
        return 2
    ring = None
    if ns.freigabe_schluessel:
        from rechner_pipeline.models.freigabe import lade_schluesselring

        ring, ring_fehler, _aktiv = lade_schluesselring(
            list(ns.freigabe_schluessel), ausserhalb=Path(ns.fall))
        if ring_fehler:
            print("zugangsprobe: " + "; ".join(ring_fehler), file=sys.stderr)
            return 2
    try:
        beleg = zugangsprobe(
            Path(ns.stand), Path(ns.fall), stichtag, bis=bis,
            arbeit=Path(ns.arbeit) if ns.arbeit else None,
            schluessel=Path(ns.schluessel), zeichnungsordnung=Path(ns.zeichnungsordnung),
            schluesselring=ring, snapshot_sha256=ns.snapshot,
            quelle=Path(ns.quelle) if ns.quelle else None,
            image_digest=ns.image_digest or os.environ.get("PLV_IMAGE_DIGEST") or None)
    except (ZugangsprobeError, ValueError) as exc:
        print(f"zugangsprobe: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"zugangsprobe: Ein-/Ausgabefehler: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    out = Path(ns.out) if ns.out else Path(ns.fall) / zp.BELEG_RELATIV
    # Der Beleg vollstaendig daneben, dann in einem Zug an den festen Ort
    # (Runde F, F7): Ein Fehler beim Schreiben stand hinter dem try-Block und
    # endete als Traceback mit Exit 1 — fuer einen Aufrufer "nicht
    # bestanden" — und liess einen abgeschnittenen Beleg dort, wo A-B2 ihn
    # liest. Jetzt Exit 2 mit Meldung, und am festen Ort liegt unveraendert,
    # was vorher dort lag.
    try:
        _schreibe_beleg(out, beleg)
    except OSError as exc:
        print(f"zugangsprobe: Ein-/Ausgabefehler beim Beleg {out}: {type(exc).__name__}: "
              f"{exc} — die Probe ist gelaufen, ihr Beleg nicht geschrieben; am festen Ort "
              "liegt unveraendert, was vorher dort lag. Ausweg: Platz bzw. Rechte am Ort "
              "des Belegs herstellen und die Probe erneut fahren", file=sys.stderr)
        return 2
    rot = [v for v in beleg["vergleiche"] if v.get("ok") is False]
    print(f"zugangsprobe: {'BESTANDEN' if beleg['bestanden'] else 'NICHT BESTANDEN'} — "
          f"{len(beleg['vergleiche'])} Vergleiche, {len(rot)} rot, {len(beleg['befunde'])} "
          f"Befunde -> {out}", file=sys.stderr)
    for v in rot[:10]:
        print(f"  ROT {v['groesse']} {v['termin']} {v.get('stichtag') or ''}: soll {v['soll']}, "
              f"ist {v['ist']}, abweichend {v['abweichend_anzahl']}", file=sys.stderr)
    for b in beleg["befunde"][:10]:
        print(f"  BEFUND {b}", file=sys.stderr)
    return 0 if beleg["bestanden"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
