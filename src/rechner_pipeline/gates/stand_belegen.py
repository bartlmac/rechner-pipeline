"""``stand_belegen`` — Belege der Standabnahme: Linienbereich, Ordnungslinie, Verweis, T-Box.

Entscheid des Maintainers 2026-10-01 (ADR-018, Nachtrag 2026-10-01; ADR-025):
Das Zielsystem wird einmal ausserhalb jedes Falls abgenommen (Erstabnahme),
ein Fall zeichnet danach nur, was sich durch ihn aendert, und verweist sonst
auf die geltende Abnahme. Dieses Modul haelt, was die Gegenstaende gemeinsam
brauchen (``models.standabnahme``):

* ``linie`` — den LINIENBEREICH anlegen: ein Arbeitsbereich, der sich wie ein
  Fall verhaelt (``entscheide/``, ``abgeleitet/``), aber keinen Eingang einer
  Migration hat; gekennzeichnet durch ``linie.json``.
* ``ordnung`` — einen Stand der Zeichnungsordnung an ihre Versionslinie
  anhaengen (``models.ordnungslinie``): das erste Glied unsigniert und
  menschlich angelegt, jedes weitere gezeichnet von der Wurzelrolle, dem Vorstand
  (Ordnungsaenderung A-Z1) mit dem Schluessel, den die Spitze ihr gibt; mit
  lesbarer Sicht, was sich zwischen den Staenden aendert.
* :func:`lebender_stand` — der Stand, den der Code JETZT traegt (Kern,
  T-Box, Tarifwerk) bzw. den der Beleg des Anfangsbestands bezeugt. Das Gate
  schreibt ihn beim Zeichnen als Feld ``stand`` in den Snapshot und haelt ihn
  bei A-M4 per ``==`` gegen jeden abgenommenen Stand.
* ``verweisen`` — der Weg "keine Aenderung": Ein Fall, dessen Stand die
  GELTENDE Abnahme der Linie schon abgenommen hat (``--linie``: die Spitze
  der Kette des Gates), legt eine vollstaendige Kopie dieses Snapshots an den
  festen Ort. Die Kopie ist selbstadressiert und signiert; A-M4 prueft
  Signatur, Rolle, Klasse und Stand UND haelt nach, dass sie noch die
  geltende, angenommene Spitze der Linie ist (Gueltigkeit, nicht nur
  Echtheit; Pruefrunde G, G11). Kein neuer Entscheid. ``--snapshot`` (ein
  beliebiger frueherer Snapshot, auch eines anderen Falls) ist entfallen.
* ``tbox`` — der Aenderungsbeleg eines T-Box-Uebergangs aus der
  Versionslinie des Codes, mit dem ganzen Vokabular und der lesbaren Sicht
  (``abgeleitet/tbox/aenderung.md``: Vokabular-Diff gegen das zuletzt
  abgenommene Vokabular, bei der Erstabnahme das ganze Vokabular). Die
  aktuarielle Stellungnahme bleibt fachliche Arbeit des Aktuariats.

Run via::

    python -m rechner_pipeline.gates.stand_belegen linie --linie linie
    python -m rechner_pipeline.gates.stand_belegen ordnung --linie linie \\
        --ordnung <ordnung.json> --vorgaenger keiner|<glied> [--vorstand-schluessel <datei>] \\
        [--fruehere-zeichnungen <rolle>=gueltig|verfallen ...] [--vorschau]
    python -m rechner_pipeline.gates.stand_belegen verweisen --fall faelle/<fall> \\
        --gate A-K2|A-O1|A-T1 --linie linie --repo-root .
    python -m rechner_pipeline.gates.stand_belegen tbox \\
        (--fall faelle/<fall> --vorher-linie linie | --linie linie) \\
        --artefakt <adr-oder-vermerk> --begruendung "<text>" --repo-root .

Knoten: system/entscheid
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from rechner_pipeline.gates._provenienz import lebendes_repo  # --repo-root (G12)
from rechner_pipeline.gates import kernstand_belegen as _kern
from rechner_pipeline.gates._common import (
    Exit,
    ToolboxResult,
    build_result,
    ein_ausgabe_benannt,
    ist_schreibrest,
    raeume_schreibreste,
    raeume_zwillinge,
    run_command,
    schreibe_exklusiv,
    utc_now,
)
from rechner_pipeline.models import kernabnahme as ka
from rechner_pipeline.models import ordnungslinie as ol
from rechner_pipeline.models import standabnahme as sa
from rechner_pipeline.models.schemas import P9Snapshot

COMMAND = "stand_belegen"
#: 4.0.0 (2026-10-01, Runde G, ADR-025 Nachtrag "Beleg und Sicht"; Major: ein
#: vorher gruener Aufruf wird rot): ``tbox`` verweigert, wenn eine geltende
#: A-O1-Annahme ihren gepinnten Beleg nicht im Archiv findet (statt still
#: "Erstabnahme"); das Archiv wird VOR Beleg und Sicht geschrieben; ``ordnung``
#: zieht fuer ein schon liegendes Glied die Sicht nach; ``linie`` zaehlt den
#: eigenen Schreibrest nicht als Inhalt; ein Ein-/Ausgabefehler ist benannt.
#: 3.0.0 (2026-10-01, ADR-024 dritter Nachtrag; Major: ein vorher gruener
#: Aufruf wird rot): ``tbox --fall`` verlangt ``--vorher-linie``, ein zweites
#: Vokabular unter einer abgenommenen Version wird verweigert, der lebende
#: Stand von A-O1 traegt ``vokabular_sha256``.
#: 4.0.0 (2026-10-01, Pruefrunde G; Major: ein vorher gruener Aufruf wird
#: rot): ``verweisen --snapshot`` entfaellt (G11), ``--repo-root`` muss das
#: ausgefuehrte Paket tragen (G12), ``ordnung`` liest die Linie mit dem Ring
#: des Vorstands (G09; ``--vorstand-schluessel`` wiederholbar). ``tbox`` schreibt das Archiv zuerst und
#: verweigert eine nicht belegbare fruehere Abnahme benannt (G24);
#: ``ordnung`` zieht die Sicht eines liegenden Glieds nach (G26).
#: 5.0.0 (2026-10-01, Pruefrunde H; Major: ein vorher gruener Aufruf wird
#: rot): ``ordnung`` verlangt je geminderter Rolle ``--fruehere-zeichnungen
#: <rolle>=gueltig|verfallen`` (Glied Schema 2) und ein ``--eingetragen-am``,
#: das nicht vor dem der Spitze liegt; Ausgabe und Sicht nennen die Folge
#: einer Erklaerung. ``linie`` liefert bei der Wiederholung nach einem
#: Ausfall das Ergebnis des ungestoerten Laufs; ``linie``, ``ordnung`` und
#: ``tbox`` raeumen die Hardlink-Zwillinge ihrer Belege (H16).
#: 6.0.0 (2026-10-01, Pruefrunde I; Major: ein vorher gruener Aufruf wird
#: rot): ``ordnung`` verweigert ein ``--eingetragen-am`` nach der Uhr des
#: Aufrufs (I04); liest Spitze, prueft Vorgaenger und haengt an unter EINER
#: Sperre (``sperre_der_ordnung``), ein Glied heisst ``<nummer>.json`` (I18);
#: ``--vorschau`` rechnet die Folge jeder Erklaerung, ohne zu schreiben
#: (I03); die Folge kommt aus derselben Bestimmung wie die Wirkung beim
#: Lesen (``ordnungslinie.getroffene_abnahmen``, I01/I02/I05).
GATE_VERSION = "6.0.0"

#: Fester Ort des T-Box-Aenderungsbelegs (wie bisher von A-O1 gelesen).
TBOX_AENDERUNG_RELATIV = "abgeleitet/tbox/aenderung.json"
TBOX_STELLUNGNAHME_RELATIV = "abgeleitet/tbox/stellungnahme.json"
TBOX_SICHT_RELATIV = "abgeleitet/tbox/aenderung.md"
#: Inhaltsadressiertes Archiv der T-Box-Belege: Die Sicht der naechsten
#: Abnahme findet dort das zuletzt abgenommene Vokabular (der Beleg am
#: festen Ort wird ersetzt, das Archiv nie).
TBOX_ARCHIV_RELATIV = "abgeleitet/tbox/archiv"
#: Schema des T-Box-Aenderungsbelegs (gates.gate_entscheid.pruefe_tbox_aenderung).
#: 2 (2026-10-01, ADR-025): das ganze Vokabular (``vokabular``,
#: ``vokabular_sha256``) und das zuletzt abgenommene (``vorher``) — die
#: Grundlage der lesbaren Sicht.
TBOX_AENDERUNG_SCHEMA_VERSION = 2


class StandFehler(RuntimeError):
    """Der Stand oder ein Beleg dazu ist nicht bestimmbar — mit dem Grund."""


#: Was ``verweisen --snapshot`` jetzt sagt (Pruefrunde G, G11).
SNAPSHOT_ENTFALLEN = (
    "--snapshot ist entfallen (Pruefrunde G, ADR-018/ADR-025): Ein Verweis zeigt nur noch "
    "auf die GELTENDE Abnahme der Linie — ein frueherer Snapshot (auch der eines anderen "
    "Falls) kann inzwischen abgeloest oder abgelehnt sein, und seine Herkunftskette ist vom "
    "Gate aus nicht pruefbar. Ausweg: den Stand in der Linie abnehmen (gate_entscheid "
    "--linie <linie> --gate <gate>) und mit --linie <linie> verweisen; aendert der Fall den "
    "Stand, im Fall zeichnen")


class _SnapshotEntfallen(argparse.Action):
    """Verweigert ``--snapshot`` sprechend statt mit "unrecognized arguments" —
    das Muster der entfallenen Tarifschalter (spez.tarifregeln)."""

    def __call__(self, parser, namespace, values, option_string=None):
        parser.error(SNAPSHOT_ENTFALLEN)


def _tbox_modul():
    from rechner_pipeline.ontologie import tbox

    return tbox


def tbox_modul_sha256() -> str:
    return hashlib.sha256(Path(_tbox_modul().__file__).read_bytes()).hexdigest()


def lebender_stand(gate: str, repo_root: Optional[Path],
                   bereich: Optional[Path] = None) -> Optional[Dict[str, str]]:
    """Der Stand, den der Code JETZT traegt (None = nicht bestimmbar).

    Fuer A-B3 der Stand, den der Beleg des Anfangsbestands im ``bereich``
    bezeugt (``models.anfangsbestand.stand_aus_beleg``): Das Gate sieht die
    Ablage nicht; gegen sie haelt der Betrieb den Stand beim Binden.
    """
    if gate == "A-K2":
        if repo_root is None:
            return None
        init = repo_root / ka.KERN_PAKET / "__init__.py"
        stand = {
            "version": _kern.kern_version(init.read_text(encoding="utf-8")
                                          if init.is_file() else None),
            "kern_sha256": _kern.kern_modul_hash(repo_root),
            "referenzwerte_sha256": _kern.referenzwerte_hash(repo_root),
            "kernstand_sha256": _kern.kernstand_hash(repo_root),
        }
    elif gate == "A-O1":
        # Drei Felder (ADR-024, dritter Nachtrag): die Bytes des Moduls — es
        # traegt auch die Pruefregeln, die P-Q3 und P-K1 ausfuehren — UND der
        # Abdruck des Vokabulars. Der Verweis (Weg b) haelt alle drei mit ==;
        # der Abdruck im Stand macht die Regel "eine Version, ein Vokabular"
        # (:func:`tbox_vokabular_fehler`) aus signierten Snapshots pruefbar.
        tbox = _tbox_modul()
        stand = {"version": tbox.TBOX_VERSION, "tbox_sha256": tbox_modul_sha256(),
                 "vokabular_sha256": tbox.vokabular_sha256()}
    elif gate == "A-T1":
        if repo_root is None:
            return None
        from rechner_pipeline.gates.tarifwerk_belegen import lebender_stand as tw_stand

        stand = tw_stand(repo_root)
    elif gate == "A-B3":
        from rechner_pipeline.models import anfangsbestand as ab

        if bereich is None or not (bereich / ab.BELEG_RELATIV).is_file():
            return None
        try:
            stand = ab.stand_aus_beleg(json.loads(
                (bereich / ab.BELEG_RELATIV).read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return None
    else:
        raise ValueError(f"{gate!r} ist kein Gegenstand der Standabnahme")
    return stand if all(isinstance(v, str) and v and v != "None"
                        for v in stand.values()) else None


def verweis_fehler(daten: object, gegenstand: sa.Gegenstand,
                   stand: Optional[Dict[str, str]]) -> List[str]:
    """Was sich an einem Verweis OHNE Schluessel pruefen laesst: Form,
    Schema und Selbstadressierung der Kopie, Gate, Annahme, Herkunft und —
    der Kern des Wegs — der abgenommene Stand gleich dem lebenden.
    Signatur und Rollenregel prueft das Gate (es haelt den Ring)."""
    if not isinstance(daten, dict):
        return ["kein JSON-Objekt"]
    fehler: List[str] = []
    if set(daten) != sa.VERWEIS_FELDER:
        fehler.append(f"der Verweis traegt genau die Felder {sorted(sa.VERWEIS_FELDER)}")
    if daten.get("schema_version") != sa.VERWEIS_SCHEMA_VERSION:
        fehler.append(f"schema_version muss {sa.VERWEIS_SCHEMA_VERSION} sein")
    if daten.get("art") != sa.VERWEIS_ART:
        fehler.append(f"art muss {sa.VERWEIS_ART!r} sein")
    if daten.get("gate") != gegenstand.gate:
        fehler.append(f"gate muss {gegenstand.gate!r} sein")
    snap = daten.get("snapshot")
    if not isinstance(snap, dict):
        return fehler + ["snapshot fehlt oder ist kein Objekt"]
    fehler += [f"snapshot: {f}" for f in P9Snapshot.validate_payload(snap)]
    if snap.get("gate") != gegenstand.gate:
        fehler.append(f"der Snapshot gehoert zu {snap.get('gate')!r}, nicht {gegenstand.gate!r}")
    if snap.get("entscheid") != "angenommen":
        fehler.append("der Snapshot ist keine Annahme — eine Ablehnung nimmt keinen Stand ab")
    if daten.get("herkunft") != sa.herkunft(snap):
        fehler.append(f"herkunft muss {sa.herkunft(snap)!r} sein (abgeleitet, nicht angegeben)")
    if stand is None:
        fehler.append("der lebende Stand ist nicht bestimmbar (--repo-root fehlt?)")
    elif snap.get("stand") != stand:
        fehler.append(
            f"der abgenommene Stand {snap.get('stand')!r} ist nicht der lebende {stand!r} "
            "— es gab eine Aenderung; sie braucht eine Abnahme (im Fall, oder in der Linie "
            "und dann ein neuer Verweis)")
    return fehler


def baue_verweis(snapshot: dict) -> Dict[str, Any]:
    return {
        "schema_version": sa.VERWEIS_SCHEMA_VERSION,
        "art": sa.VERWEIS_ART,
        "gate": snapshot.get("gate"),
        "herkunft": sa.herkunft(snapshot),
        "snapshot": snapshot,
    }


def geltende_spitze(bereich: Path, gate: str) -> Tuple[Optional[dict], List[str]]:
    """Die geltende Spitze der Kette eines Gates in einem Bereich — strukturell
    (Schema, Selbstadressierung, Graph), OHNE Signatur: Die prueft A-M4 an der
    Kopie im Verweis mit dem Ring. Fuer Produzenten und Sichten."""
    from rechner_pipeline.models.snapshot_kette import pruefe_snapshot_graph

    kette, fehler = _lade_kette(bereich, gate)
    if fehler:
        return None, fehler
    if not kette:
        return None, [f"keine {gate}-Abnahme in {bereich}"]
    spitzen, gf = pruefe_snapshot_graph(kette)
    if gf or len(spitzen) != 1:
        return None, gf or [f"keine eindeutige Spitze der {gate}-Kette"]
    return kette[spitzen[0]], []


def _lade_kette(bereich: Path, gate: str) -> Tuple[Dict[str, dict], List[str]]:
    """Alle Snapshots eines Gates in einem Bereich, strukturell gelesen
    (Schema, Selbstadressierung), OHNE Signatur."""
    kette: Dict[str, dict] = {}
    fehler: List[str] = []
    verzeichnis = Path(bereich) / "entscheide"
    for pfad in sorted(verzeichnis.glob(f"{gate}-*.json")) if verzeichnis.is_dir() else []:
        try:
            daten = json.loads(pfad.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            fehler.append(f"{pfad.name}: nicht lesbar ({exc})")
            continue
        sf = P9Snapshot.validate_payload(daten)
        if sf or pfad.name != f"{gate}-{daten.get('snapshot_sha256')}.json":
            fehler.append(f"{pfad.name}: kein gueltiger Snapshot ({'; '.join(sf[:2])})")
            continue
        kette[daten["snapshot_sha256"]] = daten
    return kette, fehler


def tbox_vokabular_fehler(bereiche: List[Path]) -> List[str]:
    """EINE Regel fuer Produzent und Gate (ADR-024, dritter Nachtrag):
    Innerhalb einer ABGENOMMENEN Version der T-Box gibt es genau ein Vokabular.

    Vor der ersten Zeichnung ist eine Version ein Entwurf: Ihr Vokabular darf
    sich bewegen, der Abdruck im Test wird nachgezogen. Nach der ersten
    Zeichnung ist sie ein Vertrag: Eine A-Box oder Spez, die diese Version
    erklaert, meint das gezeichnete Vokabular. Ein zweites Vokabular unter
    derselben Nummer liesse P-Q3 und P-K1 beim Versionsvergleich beide
    durch. Deshalb: Fuehrt IRGENDEINE Annahme in der A-O1-Kette eines der
    Bereiche (Fall, Linie) die Version des Codes mit einem anderen Abdruck,
    wird verweigert — Ausweg ist die naechste Version. Derselbe Abdruck
    bleibt zulaessig (das Modul hat sich bewegt, das Vokabular nicht).

    Jede Annahme zaehlt, nicht nur die geltende Spitze: Auch eine spaeter
    abgeloeste Annahme war eine Zeichnung, auf der gearbeitet worden sein
    kann. Gelesen wird strukturell, ohne Signatur — ein untergeschobener
    Snapshot kann hier nur verweigern, nichts erlauben; die Signatur der
    geltenden Abnahme prueft A-M4 (Standabnahme). Eine unlesbare Kette
    verweigert (nicht entscheidbar), ebenso eine Annahme dieser Version, die
    keinen Abdruck im Stand fuehrt.
    """
    tbox = _tbox_modul()
    version, abdruck = tbox.TBOX_VERSION, tbox.vokabular_sha256()
    fehler: List[str] = []
    for bereich in bereiche:
        kette, kf = _lade_kette(bereich, "A-O1")
        if kf:
            fehler.append(
                f"die A-O1-Kette in {bereich} ist nicht lesbar ({kf[0]}) — ob die T-Box "
                f"{version} dort schon abgenommen ist, laesst sich nicht entscheiden")
            continue
        for sha, snap in sorted(kette.items()):
            stand = snap.get("stand") or {}
            if snap.get("entscheid") != "angenommen" or stand.get("version") != version:
                continue
            alt = stand.get("vokabular_sha256")
            if alt == abdruck:
                continue
            fehler.append(
                f"die T-Box {version} ist in {bereich} bereits abgenommen (A-O1-Snapshot "
                f"{sha[:16]}), "
                + (f"mit dem Vokabular {str(alt)[:16]}; der Code traegt {abdruck[:16]}"
                   if alt else "ohne Abdruck des Vokabulars im Stand")
                + " — innerhalb einer abgenommenen Version gibt es genau ein Vokabular: "
                "TBOX_VERSION heben und TBOX_VERSIONEN anhaengen (ontologie/tbox.py), die "
                "Hebungsregel ergaenzen (ontologie.abox.HEBUNGEN), dann den Uebergang vorlegen")
    return fehler


def _vokabular_sha256(vokabular: Any) -> str:
    roh = json.dumps(vokabular, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(roh.encode("ascii")).hexdigest()


def tbox_archiv_fehler(bereich: Path, pin: object) -> Optional[str]:
    """Liegt der Beleg ``pin`` im Archiv des Bereichs, byte-gleich zum Pin?
    (None = ja). EINE Pruefung fuer den Produzenten (das zuletzt abgenommene
    Vokabular) und das Gate (A-O1 wird nur gezeichnet, wenn die Archivkopie
    des Belegs liegt, den es pinnt — ``gates.sichten``)."""
    if not (isinstance(pin, str) and len(pin) == 64):
        return f"kein Pin auf einen T-Box-Beleg ({pin!r})"
    datei = Path(bereich) / TBOX_ARCHIV_RELATIV / f"{pin}.json"
    try:
        roh = datei.read_bytes()
    except FileNotFoundError:
        return f"der Beleg {pin[:16]}… fehlt im Archiv ({datei})"
    except OSError as exc:
        return f"der Beleg {pin[:16]}… im Archiv ist nicht lesbar ({exc})"
    if hashlib.sha256(roh).hexdigest() != pin:
        return f"{datei} passt nicht zum Pin (SHA-256 {hashlib.sha256(roh).hexdigest()[:16]}…)"
    return None


def _zuletzt_angenommen(bereich: Path, *, ohne_beleg: Optional[str] = None) -> Optional[dict]:
    """Die zuletzt gezeichnete A-O1-ANNAHME des Bereichs (None = es gibt
    keine). Jeder Snapshot pinnt alle frueheren als Vorgaenger: Die juengste
    Annahme ist die mit den meisten. Eine Ablehnung als Spitze aendert nichts
    daran, welches Vokabular zuletzt abgenommen ist.

    ``ohne_beleg``: Annahmen, die genau diesen T-Box-Beleg pinnen, zaehlen
    nicht (Pruefrunde H, H09) — die Vergleichsgrundlage eines Belegs ist die
    Abnahme VOR ihm; liegt seine eigene Annahme schon in der Kette (erneuter
    Aufruf), bleibt die Grundlage dieselbe."""
    from rechner_pipeline.models.snapshot_kette import pruefe_snapshot_graph

    kette, fehler = _lade_kette(bereich, "A-O1")
    if not fehler and kette:
        _, fehler = pruefe_snapshot_graph(kette)
    if fehler:
        raise StandFehler(
            f"die A-O1-Kette in {bereich} ist nicht lesbar ({fehler[0]}) — welches Vokabular "
            "zuletzt abgenommen ist, laesst sich nicht bestimmen")
    annahmen = [s for s in kette.values() if s.get("entscheid") == "angenommen"
                and (ohne_beleg is None or ((s.get("pflichtbelege") or {}).get(
                    "tbox_aenderung") or [None])[0] != ohne_beleg)]
    return max(annahmen, key=lambda s: len(s.get("vorgaenger") or [])) if annahmen else None


def tbox_vorher_fehler(bereiche: List[Path], pin: object, beleg: object) -> Optional[str]:
    """Ist ``vorher`` des T-Box-Belegs (Pin ``pin``) die zuletzt angenommene
    T-Box in den Bereichen DES GATES? (None = ja.)

    Pruefrunde H (H09): Der Produzent bestimmte ``vorher`` aus Fall und
    ``--vorher-linie``, das Gate bekommt seine Linie ueber ``--linie``; beide
    Eingaben waren getrennt, und mit einem leeren Linienbereich wurde eine
    belegte fruehere Abnahme still zur "Erstabnahme". Das Gate rechnet
    ``vorher`` deshalb beim Zeichnen von A-O1 selbst — dieselbe Funktion wie
    der Produzent (:func:`_vorher_tbox`), ohne die Annahmen dieses Belegs —
    und haelt es mit ``==`` gegen den Beleg. Fall: Fall und Linie des Gates;
    Linienbereich: die Linie."""
    vorher = beleg.get("vorher") if isinstance(beleg, dict) else None
    try:
        soll = _vorher_tbox(list(bereiche), ohne_beleg=str(pin) if pin else None)
    except StandFehler as exc:
        return f"die Vergleichsgrundlage der Sicht ist nicht bestimmbar: {exc}"
    if soll == vorher:
        return None
    nennt = (f"A-O1-Snapshot {str(vorher.get('snapshot_sha256'))[:16]}" if isinstance(vorher, dict)
             else "keine fruehere Abnahme (Erstabnahme)")
    ist = (f"A-O1-Snapshot {str(soll.get('snapshot_sha256'))[:16]}" if soll is not None
           else "keine fruehere Abnahme (Erstabnahme)")
    return (f"die Vergleichsgrundlage der Sicht ist nicht die zuletzt angenommene T-Box in Fall "
            f"und Linie dieses Aufrufs: der Beleg nennt {nennt}, in {[str(b) for b in bereiche]} "
            f"ist es {ist} — eine fruehere Abnahme wird nie still zur Erstabnahme. Ausweg: die "
            "Vorlage mit der Linie des Falls neu erzeugen (python -m "
            "rechner_pipeline.gates.stand_belegen tbox --fall <fall> --vorher-linie <die Linie, "
            "die dieses Gate bekommt> ...), ansehen, dann zeichnen")


def _vorher_tbox(bereiche: List[Path], *, ohne_beleg: Optional[str] = None
                 ) -> Optional[Dict[str, Any]]:
    """Das zuletzt abgenommene Vokabular: der Beleg, den die juengste
    A-O1-Annahme pinnt, aus dem Archiv ihres Bereichs.

    None heisst genau eines: In keinem der Bereiche gibt es eine A-O1-Annahme
    (Erstabnahme). Gibt es eine, deren gepinnter Beleg im Archiv fehlt, nicht
    zum Pin passt oder kein Vokabular fuehrt, ist das ein benannter Fehler mit
    Ausweg (Runde G, G24): Vorher ging die Suche per ``continue`` weiter, und
    die Sicht behauptete "Erstabnahme", obwohl die Linie die T-Box schon
    abgenommen hatte."""
    for bereich in bereiche:
        annahme = _zuletzt_angenommen(bereich, ohne_beleg=ohne_beleg)
        if annahme is None:
            continue
        pin = ((annahme.get("pflichtbelege") or {}).get("tbox_aenderung") or [None])[0]
        fehler = tbox_archiv_fehler(bereich, pin)
        alt: Any = None
        if fehler is None:
            alt = json.loads((Path(bereich) / TBOX_ARCHIV_RELATIV / f"{pin}.json").read_bytes())
            if not (isinstance(alt, dict) and isinstance(alt.get("vokabular"), dict)):
                fehler = f"der Beleg {str(pin)[:16]}… im Archiv fuehrt kein Vokabular"
        if fehler is not None:
            am_ort = Path(bereich) / TBOX_AENDERUNG_RELATIV
            noch_da = (am_ort.is_file()
                       and hashlib.sha256(am_ort.read_bytes()).hexdigest() == pin)
            raise StandFehler(
                f"die T-Box ist in {bereich} abgenommen (A-O1-Snapshot "
                f"{str(annahme.get('snapshot_sha256'))[:16]}…), aber {fehler} — das zuletzt "
                "abgenommene Vokabular ist nicht bestimmbar, und 'Erstabnahme' waere eine "
                "Behauptung. Ausweg: die gepinnte Fassung als "
                f"{TBOX_ARCHIV_RELATIV}/{pin}.json wiederherstellen"
                + (f" (sie liegt noch am festen Ort {TBOX_AENDERUNG_RELATIV}: dorthin kopieren)"
                   if noch_da else " (aus der Sicherung des Bereichs)")
                + ", dann die Vorlage neu erzeugen")
        return {"beleg_sha256": pin, "snapshot_sha256": annahme["snapshot_sha256"],
                "version": alt.get("nach_version"),
                "vokabular_sha256": _vokabular_sha256(alt["vokabular"]),
                "vokabular": alt["vokabular"]}
    return None


def tbox_aenderungsbeleg(fall: Path, repo_root: Optional[Path], artefakt: str,
                         begruendung: str, *,
                         vorher_bereiche: Optional[List[Path]] = None) -> Dict[str, Any]:
    """Der Aenderungsbeleg des letzten Uebergangs der T-Box-Versionslinie."""
    tbox = _tbox_modul()
    linie = tuple(tbox.TBOX_VERSIONEN)
    if len(linie) < 2:
        raise StandFehler(
            f"die Versionslinie {linie!r} hat ein Element — kein Uebergang; die erste "
            "Abnahme der T-Box braucht einen (ADR-025)")
    if linie[-1] != tbox.TBOX_VERSION:
        raise StandFehler(f"die Linie endet nicht bei der Version des Codes ({tbox.TBOX_VERSION})")
    if Path(artefakt).is_absolute() or ".." in Path(artefakt).parts:
        raise StandFehler(f"artefakt {artefakt!r} ist kein relativer, kanonischer Pfad")
    for wurzel in [fall] + ([repo_root] if repo_root is not None else []):
        ort = wurzel / artefakt
        if ort.is_file():
            sha = hashlib.sha256(ort.read_bytes()).hexdigest()
            break
    else:
        raise StandFehler(f"artefakt {artefakt!r} liegt weder im Bereich noch im Repo")
    bereiche = list(vorher_bereiche or [fall])
    regel = tbox_vokabular_fehler(bereiche)
    if regel:
        raise StandFehler("; ".join(regel[:3]))
    vokabular = json.loads(json.dumps(tbox.vokabular(), sort_keys=True))
    return {
        "schema_version": TBOX_AENDERUNG_SCHEMA_VERSION,
        "von_version": linie[-2],
        "nach_version": linie[-1],
        "tbox_sha256": tbox_modul_sha256(),
        "artefakt": {"pfad": artefakt, "sha256": sha},
        "begruendung": begruendung,
        "vokabular_sha256": _vokabular_sha256(vokabular),
        "vokabular": vokabular,
        "vorher": _vorher_tbox(bereiche),
    }


def _flach(wert: Any, praefix: str = "") -> Dict[str, Any]:
    """Ein Vokabular als Pfad -> Blattwert (Listen als Ganzes)."""
    if isinstance(wert, dict):
        aus: Dict[str, Any] = {}
        for k in sorted(wert):
            aus.update(_flach(wert[k], f"{praefix}.{k}" if praefix else str(k)))
        return aus
    return {praefix: wert}


def vokabular_diff(alt: Dict[str, Any], neu: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Was sich zwischen zwei Vokabularen aendert — je Pfad, deterministisch."""
    a, n = _flach(alt), _flach(neu)
    zeilen = []
    for pfad in sorted(set(a) | set(n)):
        if a.get(pfad) == n.get(pfad):
            continue
        zustand = "neu" if pfad not in a else "entfallen" if pfad not in n else "geaendert"
        zeilen.append({"pfad": pfad, "zustand": zustand, "vorher": a.get(pfad),
                       "nachher": n.get(pfad)})
    return zeilen


def rendere_tbox_sicht(beleg: Dict[str, Any]) -> str:
    """Die Sicht des Pruefers fuer A-O1 (Markdown), deterministisch aus dem Beleg."""
    from rechner_pipeline.gates.kernstand_belegen import _c, _md

    def w(x: Any) -> str:
        return _c(json.dumps(x, ensure_ascii=False, sort_keys=True))

    z = ["# T-Box-Abnahme A-O1 — Vokabular des Zielsystems", "",
         f"Uebergang der Versionslinie: {_md(beleg.get('von_version'))} -> "
         f"{_md(beleg.get('nach_version'))}; Modul {_c(str(beleg.get('tbox_sha256'))[:16])}, "
         f"Vokabular {_c(str(beleg.get('vokabular_sha256'))[:16])}.  ",
         f"Begruendung der Vorlage: {_md(beleg.get('begruendung'))}; Artefakt "
         f"{_c((beleg.get('artefakt') or {}).get('pfad'))}.", ""]
    vorher = beleg.get("vorher")
    neu = beleg.get("vokabular") or {}
    if vorher:
        diff = vokabular_diff(vorher.get("vokabular") or {}, neu)
        z += [f"## Aenderungen gegenueber dem zuletzt abgenommenen Vokabular "
              f"(Version {_md(vorher.get('version'))}, A-O1-Snapshot "
              f"{_c(str(vorher.get('snapshot_sha256'))[:16])})", ""]
        if not diff:
            z += ["Keine Aenderung am Vokabular. Weicht der Modul-Hash vom abgenommenen "
                  "ab, haben sich allein Pruefregeln oder Kommentare des Moduls bewegt — zu "
                  "pruefen ist dann der Code-Diff von ontologie/tbox.py.", ""]
        for d in diff:
            z.append(f"- {_c(d['pfad'])} ({_md(d['zustand'])}): {w(d['vorher'])} -> "
                     f"{w(d['nachher'])}")
        z.append("")
    else:
        z += ["## Erstabnahme: das ganze Vokabular", "",
              "Es gibt kein zuletzt abgenommenes Vokabular, gegen das sich eine "
              "Differenz bilden liesse — fruehere Versionen der Linie sind nicht als "
              "Vokabular belegt. Gezeigt wird deshalb das ganze Vokabular dieser Version; "
              "jede spaetere Abnahme zeigt die Differenz dagegen.", ""]
        for abschnitt in sorted(neu):
            eintraege = _flach(neu[abschnitt])
            z += [f"### {_md(abschnitt)} ({len(eintraege)} Eintraege)", ""]
            for pfad, wert in eintraege.items():
                z.append(f"- {_c(pfad)}: {w(wert)}")
            z.append("")
    z += ["Aus dem Aenderungsbeleg erzeugt (`gates.stand_belegen tbox`); massgeblich ist "
          "der Beleg, nicht diese Sicht. Die aktuarielle Stellungnahme legt das Aktuariat "
          "vor.", ""]
    return "\n".join(z)


def _ersetze(ziel: Path, daten: bytes) -> None:
    ziel.parent.mkdir(parents=True, exist_ok=True)
    raeume_schreibreste(ziel)
    tmp = ziel.parent / f".{ziel.name}.{secrets.token_hex(8)}.tmp"
    try:
        with open(tmp, "wb") as datei:
            datei.write(daten)
            datei.flush()
            os.fsync(datei.fileno())
        os.replace(tmp, ziel)
    finally:
        tmp.unlink(missing_ok=True)


def _json_bytes(daten: Dict[str, Any]) -> bytes:
    return (json.dumps(daten, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def ordnung_sicht(alt: Optional[dict], neu: dict) -> List[str]:
    """Was sich zwischen zwei Staenden der Ordnung aendert, lesbar — aus
    ``models.ordnungslinie.aenderungen`` (gerechnet, nicht behauptet)."""
    zeilen = [f"- {ol.aenderung_text(e)}" for e in ol.aenderungen(alt, neu)]
    return zeilen or ["- keine Aenderung an Rollen, Schluesseln oder Gates"]


def rendere_ordnungslinie(glieder: List[Dict[str, Any]]) -> str:
    """Die Sicht der ganzen Ordnungslinie — je Glied, was es aendert, und je
    geminderter Rolle die Erklaerung des Vorstands mit ihrer Folge."""
    z = ["# Versionslinie der Zeichnungsordnung", ""]
    alt: Optional[dict] = None
    for j, g in enumerate(glieder):
        neu = ol.ordnung_aus(g)
        z += [f"## Glied {g['nummer']} — `{g['glied_sha256'][:16]}`", "",
              f"Ordnung `{g['ordnung_sha256'][:16]}`, eingetragen am {g['eingetragen_am']}.  ",
              f"{g['eintrag']['vermerk']}", ""]
        if g.get("zeichnung"):
            z += [f"Gezeichnet: {g['zeichnung']['rolle']} ({g['zeichnung']['gate']}), Schluessel "
                  f"`{g['zeichnung']['schluessel_sha256'][:16]}`.", ""]
        z += ordnung_sicht(alt, neu) + [""]
        folgen = ol.folge_der_erklaerung(glieder, j)
        if folgen:
            z += ["Fruehere Zeichnungen der geminderten Rollen (Erklaerung des Vorstands):", ""]
            z += [f"- {rolle}: {text}" for rolle, text in folgen.items()] + [""]
        alt = neu
    return "\n".join(z)


#: Die Sperre der Ordnungslinie (Pruefrunde I, I18): Lesen der Spitze, Pruefen
#: des Vorgaengers und Anhaengen geschehen unter EINER Sperre; neben
#: ``ordnung/`` im Linienbereich, kein Glied und kein Beleg.
ORDNUNG_SPERRE = ".ordnung.sperre"


@contextmanager
def sperre_der_ordnung(linie: Path) -> Iterator[None]:
    """Die Sperre, unter der ``stand_belegen ordnung`` die Spitze liest, den
    Vorgaenger prueft und anhaengt — von zwei gleichzeitigen Eintraegen auf
    derselben Spitze sieht der zweite die neue Spitze und wird benannt
    verweigert ("der genannte Vorgaenger ... ist nicht die Spitze").

    Dasselbe Sperrmittel wie der Eingang eines Falls
    (``fall._sperre_datei``: ``flock`` auf einem stabilen Deskriptor,
    blockierend; die Sperrdatei bleibt liegen, die Sperre ist ein Kernel-Lock
    auf ihrem Inode, kein Sentinel) — keine zweite Bauform. Zusaetzlich traegt
    jedes Glied seine Nummer als Dateinamen (``ordnungslinie.dateiname``):
    Auch ein Weg ohne diese Sperre legt kein zweites Glied derselben Nummer ab.
    """
    from rechner_pipeline.fall import _entsperre_datei, _sperre_datei

    pfad = Path(linie) / ORDNUNG_SPERRE
    if pfad.is_symlink():
        raise OSError(f"die Sperre der Ordnungslinie ist ein Symlink ({pfad})")
    fd = os.open(pfad, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        if os.fstat(fd).st_size == 0:
            os.write(fd, b"0")
        _sperre_datei(fd)
        try:
            yield
        finally:
            _entsperre_datei(fd)
    finally:
        os.close(fd)


def _ordnung_vorschau(linie: Path, ordnung_roh: bytes, *, vorgaenger: Optional[str],
                      eingetragen_am: str, uhr: str, erklaerung: Dict[str, str]) -> ToolboxResult:
    """``ordnung --vorschau`` (Pruefrunde I, I03/I15/I19): die Folge VOR der Wahl.

    Rechnet fuer die genannte Ordnung und den genannten Vorgaenger dieselben
    Pruefungen wie das Anhaengen (``ordnungslinie.pruefe_anhang``), die
    Aenderungen, die geminderten Rollen, die noch fehlenden Erklaerungen und
    je Rolle die Folge — fuer die genannte Erklaerung, sonst fuer BEIDE —, aus
    derselben Funktion, die der echte Aufruf ausgibt
    (``ordnungslinie.folge_der_erklaerung`` auf dem noch nicht gezeichneten
    Glied). Schreibt nichts: kein Glied, keine Sicht, keine Tempdatei, keine
    Sperrdatei; zeichnet nichts und braucht keinen Schluessel. Die Linie liest
    sie strukturell — sie zeigt, sie gruendet nichts; der echte Aufruf liest
    mit dem Ring des Vorstands und verweigert eine verletzte Linie.
    """
    def fehler(text: str) -> ToolboxResult:
        return build_result(command=COMMAND, gate_version=GATE_VERSION,
                            exit_code=Exit.FILE_CONTRACT,
                            errors=[{"code": "stand", "message": text}])

    glieder, lf = ol.lade_linie_strukturell_zur_anzeige(linie)
    if lf:
        return fehler("die Linie ist verletzt: " + "; ".join(lf[:3]))
    try:
        aliste = ol.pruefe_anhang(glieder, ordnung_roh, vorgaenger=vorgaenger,
                                  eingetragen_am=eingetragen_am, uhr=uhr)
    except ol.OrdnungslinieFehler as exc:
        return fehler(str(exc))
    geminderte = ol.geminderte_rollen(aliste)
    fremd = sorted(r for r in erklaerung if r not in geminderte)
    if fremd:
        return fehler(f"fruehere_zeichnungen nennt {fremd}, die das Glied nicht mindert — "
                      "erklaert wird nur, was gemindert wird")
    vorher = ol.ordnung_aus(glieder[-1]) if glieder else None

    def folge_bei(wahl: str) -> Dict[str, str]:
        werte = {r: erklaerung.get(r, wahl) for r in geminderte}
        kuenftig = ol.baue_glied(ordnung_roh, nummer=len(glieder) + 1, vorgaenger=vorgaenger,
                                 eingetragen_am=eingetragen_am, vorher=vorher,
                                 fruehere_zeichnungen=werte)
        return ol.folge_der_erklaerung([*glieder, kuenftig], len(glieder))

    folgen: Dict[str, Dict[str, str]] = {r: {} for r in geminderte}
    for wahl in ol.ERKLAERUNGEN:
        je_rolle = folge_bei(wahl)
        for r in geminderte:
            if erklaerung.get(r, wahl) == wahl:
                folgen[r][wahl] = je_rolle[r]
    fehlt = [r for r in geminderte if r not in erklaerung]
    summary: Dict[str, Any] = {
        "vorschau": True, "geschrieben": False, "nummer": len(glieder) + 1,
        "aenderung": ordnung_sicht(vorher, json.loads(ordnung_roh.decode("utf-8"))),
        "geminderte_rollen": geminderte, "erklaerung_fehlt": fehlt, "folgen": folgen,
        "linie_gelesen": "strukturell, ohne die Signaturen der Glieder — eine Vorschau "
                         "gruendet nichts; das Anhaengen liest mit dem Ring des Vorstands"}
    if not fehlt:
        # Genau das, was der echte Aufruf mit dieser Erklaerung ausgibt.
        summary["fruehere_zeichnungen"] = folge_bei(ol.ERKLAERUNGEN[0])
    return build_result(command=COMMAND, gate=ol.ORDNUNGS_GATE, gate_version=GATE_VERSION,
                        exit_code=Exit.OK, summary=summary)


def _erklaerungen(werte: Optional[List[str]]) -> Tuple[Dict[str, str], List[str]]:
    """``--fruehere-zeichnungen <rolle>=gueltig|verfallen`` (wiederholbar)."""
    aus: Dict[str, str] = {}
    fehler: List[str] = []
    for wert in werte or []:
        rolle, gleich, erklaerung = str(wert).partition("=")
        if not gleich or not rolle or erklaerung not in ol.ERKLAERUNGEN:
            fehler.append(f"--fruehere-zeichnungen {wert!r}: erwartet <rolle>="
                          f"{'|'.join(ol.ERKLAERUNGEN)}")
        elif rolle in aus:
            fehler.append(f"--fruehere-zeichnungen nennt {rolle} zweimal — je Rolle eine Aussage")
        else:
            aus[rolle] = erklaerung
    return aus, fehler


@ein_ausgabe_benannt(command=COMMAND, gate_version=GATE_VERSION)
def main(argv: Optional[List[str]] = None) -> ToolboxResult:
    p = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.gates.stand_belegen",
        description="Belege der Abnahme des Zielsystems: Linienbereich, Ordnungslinie, "
                    "Verweis 'keine Aenderung', T-Box-Uebergang. Producer, kein Gate.")
    unter = p.add_subparsers(dest="aktion", required=True)
    li = unter.add_parser("linie", help="den Linienbereich anlegen (ADR-025)")
    li.add_argument("--linie", required=True)
    o = unter.add_parser("ordnung", help="einen Stand der Zeichnungsordnung an die Linie haengen")
    o.add_argument("--linie", required=True)
    o.add_argument("--ordnung", required=True, help="die Ordnungsdatei (ausserhalb der Linie)")
    o.add_argument("--vorgaenger", required=True,
                   help="die Spitze, wie der Mensch sie gesehen hat (glied_sha256), oder 'keiner'")
    o.add_argument("--vorstand-schluessel", dest="vorstand_schluessel", action="append",
                   default=None,
                   help="Schluessel der Wurzelrolle (Vorstand) laut Spitze (ab dem zweiten Glied); "
                        "wiederholbar: nach einem Schluesselwechsel auch die frueheren, mit "
                        "denen die Glieder der Linie gezeichnet sind — der zuletzt genannte "
                        "zeichnet")
    o.add_argument("--eingetragen-am", dest="eingetragen_am", default=None,
                   help="Zeitpunkt mit Zeitzone; ohne Angabe die Uhr des Aufrufs. Nie vor dem "
                        "der Spitze")
    o.add_argument("--fruehere-zeichnungen", dest="fruehere_zeichnungen", action="append",
                   default=None, metavar="ROLLE=gueltig|verfallen",
                   help="Pflicht je Rolle, die das Glied MINDERT (Rolle entfaellt, Schluessel- "
                        "oder Klassenwechsel, Gate entzogen): was mit ihren frueheren "
                        "Zeichnungen geschieht — gueltig (tragen weiter, wenn vor diesem Glied "
                        "gezeichnet) oder verfallen (tragen nichts mehr, neu zu zeichnen); "
                        "wiederholbar, keine Vorgabe")
    o.add_argument("--vorschau", action="store_true",
                   help="nur rechnen, nichts schreiben und nichts zeichnen: Aenderungen, "
                        "geminderte Rollen, noetige Erklaerungen und je Rolle die Folge von "
                        "gueltig UND verfallen (bzw. der genannten Erklaerung) — vor der Wahl "
                        "lesen; braucht keinen Schluessel")
    v = unter.add_parser("verweisen", help="Verweis auf die geltende Abnahme der Linie")
    v.add_argument("--fall", required=True)
    v.add_argument("--repo-root", type=lebendes_repo, dest="repo_root", required=True)
    v.add_argument("--gate", required=True, choices=[g.gate for g in sa.AM4_GEGENSTAENDE])
    v.add_argument("--linie", required=True,
                   help="Linienbereich: seine geltende Abnahme des Gates — die einzige Quelle "
                        "eines Verweises (Pruefrunde G, G11)")
    v.add_argument("--snapshot", action=_SnapshotEntfallen,
                   default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    t = unter.add_parser("tbox", help="Aenderungsbeleg des letzten T-Box-Uebergangs")
    ziel = t.add_mutually_exclusive_group(required=True)
    ziel.add_argument("--fall", default=None)
    ziel.add_argument("--linie", default=None)
    t.add_argument("--vorher-linie", dest="vorher_linie", default=None,
                   help="Linienbereich mit der zuletzt abgenommenen T-Box; mit --fall Pflicht: "
                        "Sicht und Regel 'eine Version, ein Vokabular' halten Fall UND Linie")
    t.add_argument("--repo-root", type=lebendes_repo, dest="repo_root", required=True)
    t.add_argument("--artefakt", required=True,
                   help="ADR oder Aenderungsvermerk, relativ zu Bereich oder Repo")
    t.add_argument("--begruendung", required=True)
    args = p.parse_args(argv)

    def _fehler(code: int, text: str) -> ToolboxResult:
        return build_result(command=COMMAND, gate_version=GATE_VERSION, exit_code=code,
                            errors=[{"code": "stand", "message": text}])

    if args.aktion == "linie":
        linie = Path(args.linie)
        daten = _json_bytes(sa.linie_kennung(linie.resolve().name))
        # Ein Ausfall NACH dem Einhaengen von linie.json (Pruefrunde H, H16):
        # Der Hardlink-Zwilling wird geraeumt, und liegt danach genau die
        # Kennzeichnung, die dieser Aufruf schriebe, ist das das Ergebnis des
        # ungestoerten Laufs — nicht "schon ein Linienbereich".
        if linie.is_dir():
            raeume_zwillinge(linie)
            inhalt = [p.name for p in linie.iterdir()
                      if not (ist_schreibrest(p.name) and p.name.startswith(f".{sa.LINIE_MARKER}."))]
            marker = linie / sa.LINIE_MARKER
            if inhalt == [sa.LINIE_MARKER] and marker.is_file() and not marker.is_symlink() \
                    and marker.read_bytes() == daten:
                return build_result(
                    command=COMMAND, gate_version=GATE_VERSION, exit_code=Exit.OK,
                    paths={"linie": str(linie)},
                    summary={"linie": linie.resolve().name, "bereits_vorhanden": True},
                    output_hashes={sa.LINIE_MARKER: hashlib.sha256(daten).hexdigest()})
        if sa.bereich_art(linie) is not None:
            return _fehler(Exit.USAGE, f"{linie} ist schon ein Fall- oder Linienbereich")
        # Ein Schreibrest von linie.json ist kein Inhalt (gates._common.
        # ist_schreibrest; Runde G, G27): Er bleibt nach einem Prozessende
        # zwischen Tempdatei und Einhaengen, und schreibe_exklusiv raeumt ihn
        # beim naechsten Aufruf weg — vorher verweigerte "nicht leer" diesen
        # Aufruf fuer immer.
        if linie.exists() and any(
                not (ist_schreibrest(p.name) and p.name.startswith(f".{sa.LINIE_MARKER}."))
                for p in linie.iterdir()):
            return _fehler(Exit.USAGE, f"{linie} ist nicht leer — ein Linienbereich entsteht leer")
        linie.mkdir(parents=True, exist_ok=True)
        schreibe_exklusiv(linie / sa.LINIE_MARKER, daten)
        return build_result(command=COMMAND, gate_version=GATE_VERSION, exit_code=Exit.OK,
                            paths={"linie": str(linie)}, summary={"linie": linie.resolve().name},
                            output_hashes={sa.LINIE_MARKER: hashlib.sha256(daten).hexdigest()})
    if args.aktion == "ordnung":
        linie = Path(args.linie)
        if sa.bereich_art(linie) != "linie":
            return _fehler(Exit.USAGE, f"kein Linienbereich: {linie}")
        from rechner_pipeline.models.zeichnung import ausserhalb_von

        quelle_pfad = Path(args.ordnung)
        if not ausserhalb_von(quelle_pfad, linie):
            return _fehler(Exit.USAGE, "die Ordnung liegt innerhalb der Linie — sie wird extern "
                                       "verwahrt; die Linie traegt ihre Kopie im Glied")
        erklaerung, ef = _erklaerungen(args.fruehere_zeichnungen)
        if ef:
            return _fehler(Exit.USAGE, "; ".join(ef))
        # Die Uhr des Aufrufs, EINMAL gelesen (Naht der Tests: ``utc_now``):
        # Vorgabe von eingetragen_am und dessen Obergrenze (Pruefrunde I, I04).
        uhr = utc_now()
        vorgaenger = None if args.vorgaenger == "keiner" else args.vorgaenger
        try:
            ordnung_roh = quelle_pfad.read_bytes()
        except OSError as exc:
            return _fehler(Exit.FILE_CONTRACT, str(exc))
        if args.vorschau:
            return _ordnung_vorschau(linie, ordnung_roh, vorgaenger=vorgaenger,
                                     eingetragen_am=args.eingetragen_am or uhr, uhr=uhr,
                                     erklaerung=erklaerung)
        # Wer den Bereich der Glieder betritt, raeumt die Hardlink-Zwillinge
        # eingehaengter Glieder (H16) — auch der Pfad "liegt schon" unten, der
        # nichts schreibt, und jedes spaetere Anhaengen.
        raeume_zwillinge(linie / ol.VERZEICHNIS)
        schluessel = None
        # Der Ring des Vorstands (Pruefrunde G, G09): Wer anhaengt, gruendet auf
        # der Linie — er liest sie mit dem Ring; jeder Schluessel, den die Linie
        # dem Vorstand je gab, darf genannt werden (nach einem Wechsel der alte
        # UND der neue), der zuletzt genannte zeichnet.
        ring: Dict[str, bytes] = {}
        if args.vorstand_schluessel:
            from rechner_pipeline.models.freigabe import lade_schluesselring

            ring, rf, aktiv = lade_schluesselring(list(args.vorstand_schluessel),
                                                  ausserhalb=linie)
            if rf or aktiv is None:
                return _fehler(Exit.USAGE, "; ".join(rf) or "Schluessel des Vorstands nicht geladen")
            schluessel = ring[aktiv]
        sicht_ziel = linie / "abgeleitet" / "ordnung" / "linie.md"
        # Lesen der Spitze, Pruefen des Vorgaengers und Anhaengen unter EINER
        # Sperre (Pruefrunde I, I18): Zwei gleichzeitige Eintraege auf derselben
        # Spitze legten zwei Glieder derselben Nummer ab, beide mit Exit 0.
        with sperre_der_ordnung(linie):
            glieder, lf = ol.lade_linie(linie, ring=ring)
            if lf:
                return _fehler(Exit.FILE_CONTRACT, "die Linie ist verletzt: " + "; ".join(lf[:3]))
            oben = glieder[-1] if glieder else None
            if oben is not None and oben["vorgaenger"] == vorgaenger \
                    and oben["ordnung_sha256"] == hashlib.sha256(ordnung_roh).hexdigest():
                # Derselbe Aufruf fuer das Glied, das schon die Spitze ist (Runde
                # G, G26): Fiel nach dem Glied die Sicht aus, zieht die
                # Wiederholung sie nach, statt mit "Vorgaenger ist nicht die
                # Spitze" zu enden — ohne zweites Glied und ohne neue Zeichnung.
                # Derselbe Aufruf heisst auch: dieselbe Erklaerung (Pruefrunde H).
                if erklaerung != oben.get("fruehere_zeichnungen"):
                    return _fehler(Exit.FILE_CONTRACT, (
                        f"das Glied {oben['nummer']} liegt schon mit der Erklaerung "
                        f"{oben.get('fruehere_zeichnungen')}, dieser Aufruf nennt {erklaerung} — "
                        "ein Glied wird nie umgeschrieben. Ausweg: die Erklaerung des liegenden "
                        "Glieds nennen; soll sie sich aendern, ist das ein neues Glied mit einer "
                        "neuen Ordnung"))
                _ersetze(sicht_ziel, rendere_ordnungslinie(glieder).encode("utf-8"))
                return build_result(
                    command=COMMAND, gate=ol.ORDNUNGS_GATE, gate_version=GATE_VERSION,
                    exit_code=Exit.OK,
                    paths={"glied": str(linie / ol.VERZEICHNIS / ol.dateiname(oben))},
                    summary={"nummer": oben["nummer"], "glied_sha256": oben["glied_sha256"],
                             "ordnung_sha256": oben["ordnung_sha256"],
                             "gezeichnet": oben["zeichnung"] is not None,
                             "bereits_vorhanden": True,
                             "aenderung": ordnung_sicht(
                                 ol.ordnung_aus(glieder[-2]) if len(glieder) > 1 else None,
                                 ol.ordnung_aus(oben)),
                             "fruehere_zeichnungen": ol.folge_der_erklaerung(
                                 glieder, len(glieder) - 1)})
            try:
                glied = ol.neues_glied(
                    glieder, ordnung_roh, vorgaenger=vorgaenger,
                    eingetragen_am=args.eingetragen_am or uhr, uhr=uhr,
                    fruehere_zeichnungen=erklaerung,
                    vorstand_schluessel=schluessel)
            except ol.OrdnungslinieFehler as exc:
                return _fehler(Exit.FILE_CONTRACT, str(exc))
            ziel = linie / ol.VERZEICHNIS / ol.dateiname(glied)
            ziel.parent.mkdir(parents=True, exist_ok=True)
            daten = _json_bytes(glied)
            try:
                schreibe_exklusiv(ziel, daten)
            except FileExistsError:
                # Nur ein Weg OHNE diese Sperre kommt hierher: Die Nummer ist
                # schon vergeben. Kein zweites Glied derselben Nummer.
                return _fehler(Exit.FILE_CONTRACT, (
                    f"Glied {glied['nummer']} liegt schon ({ziel.name}) — ein gleichzeitiger "
                    "Eintrag ausserhalb der Sperre war schneller; dieses Glied ist nicht "
                    "angehaengt. Ausweg: die Linie ansehen und, wenn noetig, an die neue Spitze "
                    "anhaengen (ADR-025, Nachtrag Pruefrunde I)"))
            neu, _ = ol.lade_linie(linie, ring=ring)
            _ersetze(sicht_ziel, rendere_ordnungslinie(neu).encode("utf-8"))
        return build_result(
            command=COMMAND, gate=ol.ORDNUNGS_GATE, gate_version=GATE_VERSION, exit_code=Exit.OK,
            paths={"glied": str(ziel)},
            summary={"nummer": glied["nummer"], "glied_sha256": glied["glied_sha256"],
                     "ordnung_sha256": glied["ordnung_sha256"],
                     "gezeichnet": glied["zeichnung"] is not None,
                     "bereits_vorhanden": False,
                     "aenderung": ordnung_sicht(
                         ol.ordnung_aus(glieder[-1]) if glieder else None, ol.ordnung_aus(glied)),
                     # Je geminderter Rolle die Folge der Erklaerung, woertlich —
                     # aus derselben Bestimmung wie die Wirkung beim Lesen
                     # (Pruefrunde I; ``ordnungslinie.getroffene_abnahmen``).
                     "fruehere_zeichnungen": ol.folge_der_erklaerung(
                         [*glieder, glied], len(glieder))},
            output_hashes={str(ziel): hashlib.sha256(daten).hexdigest()})

    fall = Path(args.fall or getattr(args, "linie", None) or "")
    if args.aktion == "verweisen":
        if sa.bereich_art(fall) != "fall":
            return _fehler(Exit.USAGE, f"kein Fall-Arbeitsbereich: {fall}")
        repo = Path(args.repo_root).resolve()
        gegenstand = sa.gegenstand_fuer(args.gate)
        if sa.bereich_art(Path(args.linie)) != "linie":
            return _fehler(Exit.USAGE, f"kein Linienbereich: {args.linie}")
        snapshot, sf = geltende_spitze(Path(args.linie), args.gate)
        if snapshot is None:
            return _fehler(Exit.FILE_CONTRACT, "; ".join(sf[:3]))
        verweis = baue_verweis(snapshot)
        fehler = verweis_fehler(verweis, gegenstand, lebender_stand(args.gate, repo, fall))
        if fehler:
            return _fehler(Exit.FILE_CONTRACT, "; ".join(fehler[:5]))
        ziel, daten = fall / gegenstand.verweis_relativ, _json_bytes(verweis)
        _ersetze(ziel, daten)
        return build_result(
            command=COMMAND, gate_version=GATE_VERSION, exit_code=Exit.OK,
            paths={"beleg": str(ziel)},
            summary={"gate": args.gate, "anzeige": sa.anzeige_keine_aenderung(
                snapshot["snapshot_sha256"], verweis["herkunft"])},
            output_hashes={str(ziel): hashlib.sha256(daten).hexdigest()})
    # tbox
    if sa.bereich_art(fall) is None:
        return _fehler(Exit.USAGE, f"kein Fall- oder Linienbereich: {fall}")
    repo = Path(args.repo_root).resolve()
    if args.fall and not args.vorher_linie:
        # Was eine Aussage traegt, ist nicht weglassbar (ADR-024, dritter
        # Nachtrag): Ohne die Linie zeigte die Sicht im Fall "Erstabnahme",
        # obwohl die Linie die T-Box schon abgenommen hat, und die Regel
        # saehe die Abnahme der Linie nicht.
        return _fehler(Exit.USAGE, "tbox --fall braucht --vorher-linie <linie>: die Sicht zeigt "
                       "die Differenz zur zuletzt abgenommenen T-Box, und die liegt im Fall "
                       "oder in der Linie")
    if args.vorher_linie and sa.bereich_art(Path(args.vorher_linie)) != "linie":
        return _fehler(Exit.USAGE, f"--vorher-linie {args.vorher_linie}: kein Linienbereich")
    vorher = [fall] + ([Path(args.vorher_linie)] if args.vorher_linie else [])
    try:
        beleg = tbox_aenderungsbeleg(fall, repo, args.artefakt, args.begruendung.strip(),
                                     vorher_bereiche=vorher)
    except StandFehler as exc:
        return _fehler(Exit.FILE_CONTRACT, str(exc))
    daten = _json_bytes(beleg)
    sha = hashlib.sha256(daten).hexdigest()
    # Das Archiv ZUERST (Runde G, G24): Was am festen Ort liegt und gezeichnet
    # werden kann, hat damit immer seine Archivkopie; faellt das Archiv aus,
    # ist am festen Ort nichts bewegt, und derselbe Aufruf liefert danach den
    # Zustand des ungestoerten Laufs. Eine Kopie unter dem Namen, die nicht zum
    # Namen passt, wird nicht stillschweigend stehen gelassen.
    archiv = fall / TBOX_ARCHIV_RELATIV / f"{sha}.json"
    archiv.parent.mkdir(parents=True, exist_ok=True)
    # Der Pfad "liegt schon" schreibt nicht: Den Hardlink-Zwilling eines nach
    # dem Einhaengen ausgefallenen Laufs raeumt der Eintritt ins Archiv (H16).
    raeume_zwillinge(archiv.parent)
    if archiv.exists() or archiv.is_symlink():
        archiv_fehler = tbox_archiv_fehler(fall, sha)
        if archiv_fehler is not None:
            return _fehler(Exit.FILE_CONTRACT, f"{archiv_fehler} — die Archivkopie ist "
                           "verfaelscht; sie wird nie ueberschrieben. Ausweg: den Bereich "
                           "aus der Sicherung wiederherstellen")
    else:
        schreibe_exklusiv(archiv, daten)
    # Die Sicht aus genau den Bytes des Belegs, wie das Gate sie beim Zeichnen
    # neu erzeugt (gates.sichten).
    _ersetze(fall / TBOX_AENDERUNG_RELATIV, daten)
    _ersetze(fall / TBOX_SICHT_RELATIV, rendere_tbox_sicht(json.loads(daten)).encode("utf-8"))
    return build_result(
        command=COMMAND, gate_version=GATE_VERSION, exit_code=Exit.OK,
        paths={"beleg": str(fall / TBOX_AENDERUNG_RELATIV),
               "sicht": str(fall / TBOX_SICHT_RELATIV)},
        summary={"von_version": beleg["von_version"], "nach_version": beleg["nach_version"],
                 "vorher": (beleg["vorher"] or {}).get("snapshot_sha256"),
                 "stellungnahme": f"{TBOX_STELLUNGNAHME_RELATIV} legt das Aktuariat vor"},
        output_hashes={str(fall / TBOX_AENDERUNG_RELATIV): sha})


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_command(main))
