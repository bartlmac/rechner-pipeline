"""Die Versionslinie der Zeichnungsordnung — wer durfte DAMALS zeichnen.

Entscheid des Maintainers 2026-10-01 (ADR-025): Jeder P9-Snapshot pinnt
``zeichnung.ordnung_sha256``, aber bis hierher stand nirgends, welche
Ordnungsstaende es je gab, in welcher Reihenfolge und was sie enthielten.
Die Rollenregel (``models.zeichnung.zeichnende_rolle_fehler``) hielt einen
frueheren Snapshot deshalb gegen die HEUTIGE Ordnung — und den
``ordnung_sha256`` gegen nichts. Ein Gleichheitsvergleich auf den Hash
waere die falsche Reparatur: Die Ordnung aendert sich oefter, als
gezeichnet wird, und jede Erweiterung entwertete alle bestehenden Belege.

Die Linie macht einen Ordnungsstand in der Geschichte LOKALISIERBAR. Vorbild
ist ``ontologie.tbox.TBOX_VERSIONEN``: angehaengt, nie umgeschrieben; ein
Glied ist nur gueltig, wenn sein Vorgaenger die bisherige Spitze ist.

Gestalt eines Glieds (eine Datei je Glied unter ``<linie>/ordnung/``,
Name ``<nummer:04d>.json`` — je Nummer genau eine Datei, Pruefrunde I —,
exklusiv geschrieben, unter der Sperre des Produzenten):

* ``nummer`` (1, 2, ...), ``vorgaenger`` (``glied_sha256`` des
  Vorgaengers, beim ersten Glied ``None``) — die Kette;
* ``aenderungen`` — was das Glied gegenueber dem Vorgaenger aendert, je
  Rolle und Art (:data:`AENDERUNGSARTEN`), aus beiden Staenden gerechnet und
  beim Lesen nachgerechnet; beim ersten Glied jede Rolle als ``neue_rolle``;
* ``ordnung_sha256`` und ``ordnung_text`` — der SHA-256 der Ordnungsdatei
  und ihr INHALT, Byte fuer Byte (Rollen mit Schluesselklasse,
  Fingerabdruck und Gates; keine Geheimnisse — ein Fingerabdruck ist eine
  Pruefsumme). Der Hash ist aus dem Text nachrechenbar;
* ``eingetragen_am`` — vom Aufrufer gesetzt, kein ``now()`` im Kernpfad;
* ``eintrag`` — wer das Glied verantwortet, woertlich; ``zeichnung`` — beim
  ersten Glied benannt leer (``None``), bei jedem spaeteren die Zeichnung
  der Ordnungsaenderung ``A-Z1`` durch die Wurzelrolle (:data:`WURZELROLLE`);
* ``glied_sha256`` — der kanonische Hash aller uebrigen Felder.

**Die Wurzel ist unsigniert, und das ist benannt** (Entscheid 2026-10-01):
Wer an die Linie anhaengen darf, bestimmt, wer kuenftig zeichnen darf.
Verlangte das ERSTE Glied eine Signatur, kaeme das Recht des Signierenden
aus der Linie selbst — eine Vertrauenswurzel kann sich nicht selbst
begruenden. Das erste Glied legt deshalb ein Mensch ausserhalb jedes Gates
an, und es sagt das woertlich (:data:`WURZEL_VERMERK`); seine Ordnung
benennt die Wurzelrolle (:data:`WURZELROLLE`) mit ihrem Fingerabdruck (out of band
begruendet). Gebunden ist es nicht durch eine Signatur, sondern dadurch, dass
jede Zeichnung das GLIED pinnt, unter dem sie entstand
(``zeichnung.ordnungsglied_sha256``): Die Glied-Hashes sind verkettet, ein
ausgetauschtes erstes Glied aendert jeden Hash danach, und jeder Leser, der
eine Abnahme in der Linie lokalisiert, verweigert.

**Jedes spaetere Glied zeichnet die Wurzelrolle, der Vorstand** (Entscheid
des Maintainers 2026-10-01) — die Ordnungsaenderung :data:`ORDNUNGS_GATE` — mit
dem Schluessel, den die bis dahin geltende SPITZE dieser Rolle gibt; auch ein
Wechsel des Vorstands-Schluessels ist ein solches Glied, gezeichnet vom
alten. Ohne diese Zeichnung ist ein Glied nicht anhaengbar. Die Rolle zeichnet
nur die Gates der Wurzel (:data:`WURZEL_GATES`: ``A-Z1`` und, seit ADR-026, den
Fallauftrag ``A-M6``), und keine andere Rolle zeichnet eines davon: Wer
Zeichnungsrechte vergibt und Faelle beauftragt, nimmt nichts fachlich ab. Ein
Agent hat kein Gegenstueck dazu — Zeichnungsrechte vergibt kein Agent. Die
Rollen des Falls (:data:`ROLLEN_DES_FALLS`) fuehrt die Linie nicht; ihr Recht
kommt aus dem Fallauftrag.

**Gelesen wird mit dem Schluessel des Vorstands** (Pruefrunde G, G09): Wer
auf der Linie GRUENDET (Gate, Betriebskommandos mit ``--linie``, der
Produzent, der ein Glied anhaengt), liest sie mit :func:`lade_linie`, und
deren Ring ist Pflicht: Jedes Glied nach dem ersten wird gegen den Schluessel
geprueft, den die Spitze davor dem Vorstand gibt; fehlt er im Ring, ist die
Linie nicht verwendbar. Eine Linie mit genau einem Glied hat nichts zu
pruefen (die Wurzel ist unsigniert). Wer sie nur ZEIGT, liest sie mit
:func:`lade_linie_strukturell_zur_anzeige` — ohne Signaturen, und darauf
gruendet nichts. Grenze: Die Zeichnung ist ein HMAC; wer pruefen kann,
haelt den Schluessel und kann damit auch zeichnen.

**Der Schnitt** (Entscheid 2026-10-01): Die Linie beginnt mit der Ordnung
der Erstabnahme. Abnahmen unter aelteren, nicht eingetragenen Staenden —
die Snapshots abgeschlossener Faelle — gelten fuer IHREN Fall (er bleibt
auf seinem Stand) und sind als Grundlage eines neuen Falls nicht
verwendbar: Ein Leser mit Linie verweigert sie als "nicht lokalisierbar".
Das ist eine Entscheidung, kein Verlust.

**Kein Allzweck-Zeichner in der Linie.** ADR-018 hat die Rolle mit
``gates: ["*"]`` abgeschafft; der Lader (``lade_zeichnungsordnung``) liest
den Stern weiter, damit alte Ordnungen lesbar bleiben. In die Linie kommt
eine solche Ordnung nicht — und gezeichnet wird mit Linie nur unter ihrer
Spitze, also unter keiner Ordnung mit Stern.

Knoten: system/entscheid
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

#: Das Verzeichnis der Glieder im Linienbereich.
VERZEICHNIS = "ordnung"
#: Die Wurzelrolle — die Rolle, die Zeichnungsrechte vergibt — und ihr Gate
#: (ADR-012: Art A, Gegenstand Z, die Zeichnungsordnung, Nummer 1). Die
#: Kennung steht NUR hier (Entscheid des Maintainers 2026-10-01: "'Vorstand'
#: ist richtig!"): In einem Versicherer vergibt der Vorstand die Vollmachten
#: und beschliesst die Uebernahme eines Bestands. Jeder Leser, Test und Text
#: bezieht sie von hier.
WURZELROLLE = "mensch/vorstand"
ORDNUNGS_GATE = "A-Z1"
#: Die Gates der Wurzel — an EINER Stelle (ADR-026): die Ordnungsaenderung
#: und der Fallauftrag. Der Vorstand vergibt Vollmachten und beauftragt
#: Faelle; er nimmt nichts fachlich ab (ein Auftrag beauftragt, er bezeugt
#: nicht, dass etwas richtig ist). Er traegt ``A-Z1`` immer — ohne sie zeichnet
#: niemand das naechste Glied — und sonst nur Gates dieser Menge; keine andere
#: Rolle traegt eines davon.
WURZEL_GATES: Tuple[str, ...] = (ORDNUNGS_GATE, "A-M6")
#: Anzeige der Rolle in Unternehmenssprache.
WURZELROLLE_ANZEIGE = "Vorstand"
ZEICHEN_VERFAHREN = "hmac-sha256-v1"
#: Rollen des ABGEBENDEN Hauses (ADR-018): Die Ordnung der PLV fuehrt nur
#: Rollen der PLV, der Vorstand vergibt nur diese.
ROLLEN_DES_ABGEBENDEN_HAUSES = ("mensch/quell-aktuar",)
#: Rollen des FALLS (ADR-018: "entsteht mit einem Fall und endet mit ihm"):
#: Die Ordnung der Linie fuehrt sie nicht; der Fallauftrag benennt sie und gibt
#: ihnen ihr Recht (ADR-026).
ROLLEN_DES_FALLS = ("mensch/programmleitung",)
ZEICHNUNG_FELDER = frozenset({"gate", "rolle", "schluesselklasse", "schluessel_sha256",
                              "verfahren", "signatur"})
#: 2 (2026-10-01, Pruefrunde H, H06/H10): das Feld ``fruehere_zeichnungen`` —
#: die gezeichnete Erklaerung des Vorstands je GEMINDERTER Rolle. Glieder nach
#: Schema 1 werden nicht mehr gelesen: Ausserhalb der Tests gibt es noch keine
#: (die Erstabnahme ist nicht gezeichnet, ADR-025 Bedienfolge).
GLIED_SCHEMA_VERSION = 2
GLIED_ART = "ordnungsglied"
GLIED_FELDER = frozenset({
    "schema_version", "art", "nummer", "vorgaenger", "ordnung_sha256",
    "ordnung_text", "aenderungen", "fruehere_zeichnungen", "eingetragen_am", "eintrag",
    "zeichnung", "glied_sha256",
})
#: Die Arten einer Aenderung zwischen zwei Staenden der Ordnung — GERECHNET
#: aus beiden Staenden, nie vom Bediener behauptet (ADR-025). Eine stille
#: Verbreiterung einer bestehenden Rolle heisst ``gates_erweitert`` und ist
#: von ``neue_rolle`` unterscheidbar.
AENDERUNGSARTEN = ("neue_rolle", "rolle_entfallen", "gates_erweitert", "gates_entzogen",
                   "schluessel_gewechselt", "klasse_geaendert")
#: Welche Aenderungen ein Recht MINDERN (Pruefrunde H, H06/H10) — und welche
#: nur erweitern. Die beiden Mengen teilen :data:`AENDERUNGSARTEN` ohne Rest;
#: eine neue Aenderungsart erzwingt die Entscheidung, wohin sie gehoert
#: (Ratsche mit ``==`` in tests/test_ordnungslinie_erklaerung.py).
MINDERUNGSARTEN = ("rolle_entfallen", "gates_entzogen", "schluessel_gewechselt",
                   "klasse_geaendert")
ERWEITERUNGSARTEN = ("neue_rolle", "gates_erweitert")
#: Was der Vorstand je geminderter Rolle ueber ihre FRUEHEREN Zeichnungen
#: erklaert (genau eine der zwei Aussagen, keine Vorgabe): ``gueltig`` — sie
#: tragen weiter, wenn sie vor der Abloesung entstanden (Zeitregel als
#: Plausibilitaet); ``verfallen`` — sie tragen nichts mehr, gleich wann, und
#: zwar jede fruehere Abnahme der LINIE der Rolle (ihre frueheren Namen und
#: Schluessel; Pruefrunde I, :func:`treffer_der_erklaerungen`).
ERKLAERUNGEN = ("gueltig", "verfallen")
#: Der Weg, die Folge einer Erklaerung VOR der Wahl zu lesen (Pruefrunde I,
#: I03): rechnet Aenderungen, geminderte Rollen und je Rolle die Folge beider
#: Erklaerungen, schreibt nichts und zeichnet nichts.
VORSCHAU_KOMMANDO = (
    "python -m rechner_pipeline.gates.stand_belegen ordnung --linie <linie> --ordnung "
    "<ordnung> --vorgaenger <glied_sha256 der Spitze> --vorschau")
#: Was das erste Glied woertlich ueber sich sagt.
WURZEL_VERMERK = (
    "unsigniert: das erste Glied ist die Vertrauenswurzel der Linie; ein Recht, "
    "es zu zeichnen, kaeme aus der Linie selbst. Ein Mensch hat es ausserhalb "
    f"jedes Gates angelegt; seine Ordnung benennt {WURZELROLLE} mit ihrem "
    "Fingerabdruck. Gebunden ist es, weil jede Zeichnung das Glied pinnt, unter "
    "dem sie entstand (ADR-025).")
#: Was ein spaeteres Glied ueber sich sagt.
ANHANG_VERMERK = (
    f"gezeichnet von {WURZELROLLE} ({ORDNUNGS_GATE}) mit dem Schluessel, den die Spitze "
    "davor dieser Rolle gibt (ADR-025).")


class OrdnungslinieFehler(ValueError):
    """Die Linie ist verletzt oder ein Glied laesst sich nicht anhaengen."""


def _kanonisch(daten: Dict[str, Any]) -> bytes:
    return json.dumps(daten, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def glied_sha256(glied: Dict[str, Any]) -> str:
    """Der Hash eines Glieds ueber alle Felder ausser ``glied_sha256``."""
    return hashlib.sha256(_kanonisch(
        {k: v for k, v in glied.items() if k != "glied_sha256"})).hexdigest()


def dateiname(glied: Dict[str, Any]) -> str:
    """Der Name eines Glieds im Bereich der Glieder: seine NUMMER, nichts sonst.

    Pruefrunde I (I18): Der Name trug den Glied-Hash, und das exklusive
    Schreiben wirkte je Name — zwei gleichzeitige Eintraege auf derselben
    Spitze legten zwei Glieder derselben Nummer ab, beide mit Exit 0, und die
    Linie war fuer jeden gruendenden Leser unladbar. Mit der Nummer als Name
    kann ein zweites Glied derselben Nummer nicht entstehen, auf keinem Weg,
    der exklusiv schreibt (auch ohne die Sperre des Produzenten); den Hash
    traegt das Glied in sich, und der Leser rechnet ihn nach."""
    return f"{int(glied['nummer']):04d}.json"


def ordnung_inhalt_fehler(text: str) -> Tuple[Optional[dict], List[str]]:
    """Ob ``text`` eine Ordnung ist, die in die Linie darf.

    Dieselbe Regel wie der Lader (``models.zeichnung.pruefe_ordnung``),
    dazu: keine Rolle mit ``gates: ["*"]``.
    """
    from rechner_pipeline.models.zeichnung import pruefe_ordnung

    try:
        daten = json.loads(text)
    except ValueError as exc:
        return None, [f"die Ordnung ist kein JSON ({exc})"]
    fehler = pruefe_ordnung(daten)
    if fehler:
        return None, fehler
    stern = sorted(name for name, e in daten["rollen"].items() if "*" in (e.get("gates") or []))
    if stern:
        return None, [
            f"die Ordnung fuehrt eine Allzweck-Rolle (gates ['*']): {stern} — ADR-018 hat "
            "sie abgeschafft; eine solche Ordnung kommt nicht in die Linie. Ausweg: die "
            "Gates der Rolle einzeln nennen"]
    vorstand = daten["rollen"].get(WURZELROLLE)
    vgates = vorstand.get("gates") if isinstance(vorstand, dict) else None
    if not isinstance(vorstand, dict) or not isinstance(vgates, list) \
            or ORDNUNGS_GATE not in vgates or not set(vgates) <= set(WURZEL_GATES) \
            or len(vgates) != len(set(vgates)) \
            or vorstand.get("schluesselklasse") not in ("mensch", "simulation"):
        return None, [
            f"die Ordnung fuehrt keine Rolle {WURZELROLLE!r} mit gates aus den Gates der "
            f"Wurzel {list(WURZEL_GATES)} (darunter {ORDNUNGS_GATE!r}) und Schluesselklasse "
            "mensch/simulation — ohne sie zeichnet niemand das naechste Glied, und sie "
            "zeichnet nichts anderes, schon gar keine fachliche Abnahme (ADR-025, ADR-026)"]
    fremd = sorted(n for n, e in daten["rollen"].items()
                   if n != WURZELROLLE and set(e.get("gates") or []) & set(WURZEL_GATES))
    if fremd:
        return None, [f"{list(WURZEL_GATES)} zeichnet nur {WURZELROLLE}, nicht {fremd}"]
    fallrollen = sorted(set(daten["rollen"]) & set(ROLLEN_DES_FALLS))
    if fallrollen:
        return None, [
            f"die Ordnung fuehrt {fallrollen} — eine Rolle des Falls; sie entsteht mit dem "
            "Fall, der Fallauftrag benennt sie und gibt ihr ihr Recht (ADR-026). In die "
            "Ordnung der Linie gehoert sie nicht"]
    abgebend = sorted(set(daten["rollen"]) & set(ROLLEN_DES_ABGEBENDEN_HAUSES))
    if abgebend:
        return None, [
            f"die Ordnung fuehrt {abgebend} — eine Rolle des abgebenden Hauses; ihre "
            "Vollmacht kommt von ihrem eigenen Haus, der Vorstand der PLV verleiht sie "
            "nicht (ADR-025). Benennt das abgebende Haus sie in der Lieferung, haelt der "
            "Fallauftrag die Benennung fest"]
    return daten, []


def aenderungen(alt: Optional[dict], neu: dict) -> List[Dict[str, Any]]:
    """Was sich zwischen zwei Staenden der Ordnung aendert — deterministisch,
    je Rolle (sortiert) und Art (:data:`AENDERUNGSARTEN`)."""
    a = (alt or {}).get("rollen") or {}
    n = neu.get("rollen") or {}
    liste: List[Dict[str, Any]] = []
    for rolle in sorted(set(a) | set(n)):
        ea, en = a.get(rolle), n.get(rolle)
        if ea is None:
            liste.append({"art": "neue_rolle", "rolle": rolle,
                          "gates": sorted(en.get("gates") or []),
                          "schluesselklasse": en.get("schluesselklasse"),
                          "schluessel_sha256": en.get("schluessel_sha256")})
            continue
        if en is None:
            liste.append({"art": "rolle_entfallen", "rolle": rolle,
                          "gates": sorted(ea.get("gates") or [])})
            continue
        dazu = sorted(set(en.get("gates") or []) - set(ea.get("gates") or []))
        weg = sorted(set(ea.get("gates") or []) - set(en.get("gates") or []))
        if dazu:
            liste.append({"art": "gates_erweitert", "rolle": rolle, "gates": dazu})
        if weg:
            liste.append({"art": "gates_entzogen", "rolle": rolle, "gates": weg})
        if ea.get("schluessel_sha256") != en.get("schluessel_sha256"):
            liste.append({"art": "schluessel_gewechselt", "rolle": rolle,
                          "vorher": ea.get("schluessel_sha256"),
                          "nachher": en.get("schluessel_sha256")})
        if ea.get("schluesselklasse") != en.get("schluesselklasse"):
            liste.append({"art": "klasse_geaendert", "rolle": rolle,
                          "vorher": ea.get("schluesselklasse"),
                          "nachher": en.get("schluesselklasse")})
    return liste


def geminderte_rollen(aenderungsliste: object) -> List[str]:
    """Die Rollen, deren Recht eine Aenderungsliste mindert (sortiert)."""
    if not isinstance(aenderungsliste, list):
        return []
    return sorted({e["rolle"] for e in aenderungsliste
                   if isinstance(e, dict) and e.get("art") in MINDERUNGSARTEN})


def erklaerung_fehler(fruehere: object, aenderungsliste: object) -> List[str]:
    """Ob ``fruehere`` (das Feld ``fruehere_zeichnungen``) fuer GENAU die
    geminderten Rollen je eine der Aussagen :data:`ERKLAERUNGEN` traegt.
    Keine Vorgabe: Fehlt eine Rolle, ist das ein Fehler, kein stilles
    ``gueltig``; eine Erklaerung fuer eine nicht geminderte Rolle ebenso."""
    soll = geminderte_rollen(aenderungsliste)
    if not isinstance(fruehere, dict):
        return ["fruehere_zeichnungen muss ein Objekt {rolle: gueltig|verfallen} sein"]
    fehler: List[str] = []
    fehlt = [r for r in soll if r not in fruehere]
    fremd = sorted(r for r in fruehere if r not in soll)
    if fehlt:
        fehler.append(
            f"das Glied mindert {fehlt}, erklaert aber nicht, was mit ihren frueheren "
            f"Zeichnungen geschieht — je geminderter Rolle genau eine Aussage {list(ERKLAERUNGEN)}")
    if fremd:
        fehler.append(f"fruehere_zeichnungen nennt {fremd}, die das Glied nicht mindert — erklaert "
                      "wird nur, was gemindert wird")
    falsch = sorted(r for r, w in fruehere.items() if r in soll and w not in ERKLAERUNGEN)
    if falsch:
        fehler.append(f"fruehere_zeichnungen fuer {falsch}: erlaubt sind nur {list(ERKLAERUNGEN)}")
    return fehler


def _rollen(ordnung: object) -> Dict[str, dict]:
    rollen = ordnung.get("rollen") if isinstance(ordnung, dict) else None
    return {n: e for n, e in rollen.items() if isinstance(e, dict)} \
        if isinstance(rollen, dict) else {}


def entzieht_das_vertrauen(rolle: str, alt: dict, neu: dict) -> bool:
    """Ob die Minderung von ``rolle`` (``alt`` -> ``neu``) den SCHLUESSEL der
    Rolle trifft — die Rolle entfaellt, oder Schluessel oder Klasse wechseln —
    und nicht nur einzelne Gates. Erklaert der Vorstand dazu ``verfallen``, ist
    dem Schluessel nicht mehr getraut: Jede fruehere Abnahme der Rollenlinie
    faellt, gleich fuer welches Gate (auch eines, das der Schluessel unter
    einem frueheren Namen zeichnete — der Vorstandsschluessel, der zu einer
    anderen Rolle wanderte, Pruefrunde I)."""
    ea = _rollen(alt).get(rolle) or {}
    en = _rollen(neu).get(rolle)
    return en is None or en.get("schluessel_sha256") != ea.get("schluessel_sha256") \
        or en.get("schluesselklasse") != ea.get("schluesselklasse")


def entzogene_gates(rolle: str, alt: dict, neu: dict) -> List[str]:
    """Die Gates, die ``neu`` der Rolle gegenueber ``alt`` entzieht."""
    ea = _rollen(alt).get(rolle) or {}
    en = _rollen(neu).get(rolle) or {}
    return sorted(set(ea.get("gates") or []) - set(en.get("gates") or []))


def linie_fortschreiben(namen: set, schluessel: set, ordnung: dict) -> None:
    """Die LINIE einer Rolle ueber ein weiteres Glied fortschreiben (Pruefrunde
    I, I01/I02/I05): Kontinuitaet ueber den Namen ODER ueber den Schluessel.
    Traegt in ``ordnung`` eine Rolle einen Namen der Linie, kommt ihr
    Schluessel hinzu; haelt eine Rolle einen Schluessel der Linie, kommt ihr
    Name hinzu — bis nichts mehr hinzukommt. Die Mengen wachsen nur: Eine
    Umbenennung, ein geordneter Wechsel oder ein Schluessel, der zu einer
    anderen Rolle wandert, fuehrt die Linie fort, statt sie abzureissen."""
    rollen = _rollen(ordnung)
    while True:
        dazu_s = {str(e.get("schluessel_sha256")) for n, e in rollen.items()
                  if n in namen} - schluessel
        dazu_n = {n for n, e in rollen.items()
                  if str(e.get("schluessel_sha256")) in schluessel} - namen
        if not dazu_s and not dazu_n:
            return
        schluessel |= dazu_s
        namen |= dazu_n


#: Was eine Erklaerung an einer Abnahme bewirkt (:func:`treffer_der_erklaerungen`):
#: ``verfallen`` — sie traegt nichts mehr; ``gueltig`` — sie verliert mit dem
#: Glied ihre Grundlage und traegt nur, wenn sie VOR ihm gezeichnet wurde
#: (Zeitregel); ``unlesbar`` — das Glied erklaert fuer die Rolle nichts
#: Lesbares (ein gueltiges Glied kann das nicht; benannt, nie still).
TREFFERARTEN = ("verfallen", "gueltig", "unlesbar")


def treffer_der_erklaerungen(
    glieder: List[Dict[str, Any]], i: int, *, rolle: str, schluessel_sha256: str,
    gate: str, klasse: object,
) -> List[Tuple[int, str, str]]:
    """Welche Erklaerungen der Glieder nach ``glieder[i]`` eine Abnahme treffen
    — die EINE Bestimmung, aus der Wirkung (:func:`abloesung_fehler`) und Folge
    (:func:`getroffene_abnahmen`, :func:`folge_der_erklaerung`) kommen.

    Die Abnahme: gezeichnet unter Glied ``i`` von ``rolle`` mit dem Schluessel
    ``schluessel_sha256`` (Klasse ``klasse``) fuer ``gate``. Rueckgabe je
    Treffer ``(j, rolle_im_glied, art)`` (:data:`TREFFERARTEN`), in der
    Reihenfolge der Glieder.

    Die Regel (Pruefrunde I; ADR-025, Nachtrag Pruefrunde I): Gefuehrt wird die
    LINIE der zeichnenden Rolle als zwei Mengen, Namen und Schluessel
    (:func:`linie_fortschreiben`), vom gepinnten Glied an ueber JEDES spaetere
    Glied. (1) Erklaert Glied j ``verfallen`` fuer eine geminderte Rolle, deren
    Name in Glied j-1 zur Linie gehoert, ist die Abnahme getroffen — gleich wann
    und mit welchem Schluessel der Linie sie gezeichnet wurde, und gleich, ob
    ein frueheres Glied ``gueltig`` erklaert hat; betrifft die Minderung nur
    Gates (:func:`entzieht_das_vertrauen` falsch), nur Abnahmen dieser Gates.
    (2) Verliert die Abnahme mit Glied j ihre Grundlage — ihr Schluessel
    traegt ``gate`` mit ``klasse`` danach unter keinem Namen der Linie mehr —
    und erklaert Glied j fuer den bisherigen Halter ``gueltig``, gilt die
    Zeitregel dieses Glieds. Die Verfolgung endet nicht beim ersten Treffer.
    """
    namen, schluessel = {rolle}, {str(schluessel_sha256)}

    def halter(ordnung: dict) -> Optional[str]:
        for name, e in sorted(_rollen(ordnung).items()):
            if name in namen and e.get("schluessel_sha256") == schluessel_sha256 \
                    and gate in (e.get("gates") or []) and e.get("schluesselklasse") == klasse:
                return name
        return None

    vorher = ordnung_aus(glieder[i])
    halter_vorher = halter(vorher)
    treffer: List[Tuple[int, str, str]] = []
    for j in range(i + 1, len(glieder)):
        jetzt = ordnung_aus(glieder[j])
        erklaerung = glieder[j].get("fruehere_zeichnungen")
        erklaerung = erklaerung if isinstance(erklaerung, dict) else {}
        for r in geminderte_rollen(aenderungen(vorher, jetzt)):
            if r in namen and erklaerung.get(r) == "verfallen" and (
                    entzieht_das_vertrauen(r, vorher, jetzt)
                    or gate in entzogene_gates(r, vorher, jetzt)):
                treffer.append((j, r, "verfallen"))
        linie_fortschreiben(namen, schluessel, jetzt)
        halter_jetzt = halter(jetzt)
        if halter_vorher is not None and halter_jetzt is None:
            wert = erklaerung.get(halter_vorher)
            if wert == "gueltig":
                treffer.append((j, halter_vorher, "gueltig"))
            elif wert != "verfallen":      # "verfallen" steht schon oben
                treffer.append((j, halter_vorher, "unlesbar"))
        vorher, halter_vorher = jetzt, halter_jetzt
    return treffer


def getroffene_abnahmen(glieder: List[Dict[str, Any]], j: int) -> Dict[str, Dict[str, Any]]:
    """Je Rolle, fuer die ``glieder[j]`` eine Erklaerung traegt: welche
    Abnahmen sie trifft — ``{rolle: {erklaerung, gates, rollen, schluessel,
    glieder}}``, sortiert.

    Aus derselben Bestimmung wie der Leser (:func:`treffer_der_erklaerungen`),
    aufgezaehlt ueber jede Stelle, an der vor Glied j eine Abnahme gezeichnet
    sein kann: jedes fruehere Glied, jede Rolle, jedes Gate, das sie dort
    zeichnen durfte (ohne ``A-Z1``: ein Glied ist keine Abnahme). Damit IST die
    Folge, die der Produzent nennt, die Wirkung beim Lesen (Pruefrunde I, I02).

    Eine Abnahme, die ein FRUEHERES Glied schon fuer verfallen erklaert hat,
    zaehlt nicht mehr (Pruefrunde J, J01): Sie traegt nichts, was Glied j ihr
    noch nehmen oder lassen koennte. Vorher nannte die Folge eines ``gueltig``
    sie unter "tragen weiter", waehrend der Leser sie verweigerte."""
    erklaerungen = glieder[j].get("fruehere_zeichnungen") or {}
    aus = {r: {"erklaerung": e, "gates": set(), "rollen": set(), "schluessel": set(),
               "glieder": set()} for r, e in erklaerungen.items()}
    bis = glieder[: j + 1]
    for k in range(j):
        for name, e in sorted(_rollen(ordnung_aus(glieder[k])).items()):
            fp = e.get("schluessel_sha256")
            for gate in sorted({g for g in (e.get("gates") or []) if isinstance(g, str)}):
                if gate in (ORDNUNGS_GATE, "*"):
                    continue
                treffer = treffer_der_erklaerungen(
                    bis, k, rolle=name, schluessel_sha256=fp, gate=gate,
                    klasse=e.get("schluesselklasse"))
                if any(jj < j and art == "verfallen" for jj, _r, art in treffer):
                    continue
                for jj, r, art in treffer:
                    if jj == j and r in aus and art == aus[r]["erklaerung"]:
                        aus[r]["gates"].add(gate)
                        aus[r]["rollen"].add(name)
                        aus[r]["schluessel"].add(str(fp))
                        aus[r]["glieder"].add(glieder[k]["nummer"])
    return {r: {"erklaerung": w["erklaerung"], **{f: sorted(w[f]) for f in
                                                  ("gates", "rollen", "schluessel", "glieder")}}
            for r, w in sorted(aus.items())}


def folge_der_erklaerung(glieder: List[Dict[str, Any]], j: int) -> Dict[str, str]:
    """Je geminderter Rolle von ``glieder[j]`` die Folge seiner Erklaerung,
    woertlich (Ausgabe des Produzenten, seine Vorschau, die Sicht
    ``linie.md``): Was ``verfallen`` kostet, muss lesbar sein, bevor gewaehlt
    wird. Erzeugt aus :func:`getroffene_abnahmen` — dieselbe Bestimmung wie die
    Wirkung beim Lesen."""
    if j <= 0:
        return {}
    folgen: Dict[str, str] = {}
    for rolle, t in getroffene_abnahmen(glieder, j).items():
        wer = (f"gezeichnet unter Glied {t['glieder']} von {t['rollen']} mit den Schluesseln "
               f"{[s[:16] for s in t['schluessel']]}")
        if t["erklaerung"] == "gueltig":
            if not t["gates"]:
                folgen[rolle] = (
                    "gueltig: keine fruehere Abnahme verliert mit diesem Glied ihre Grundlage — "
                    "ihr Schluessel traegt ihre Gates weiter (auch unter einem anderen Namen "
                    "der Linie der Rolle)")
                continue
            folgen[rolle] = (
                f"gueltig: Abnahmen {t['gates']} dieser Rolle, gezeichnet VOR diesem Glied, "
                "tragen weiter, soweit kein frueheres Glied sie fuer verfallen erklaert hat; "
                "eine danach unter einem frueheren Glied gezeichnete traegt "
                f"nicht (Zeitregel) — betroffen: {wer}")
            continue
        if not t["gates"]:
            folgen[rolle] = ("verfallen: es liegt keine fruehere Abnahme der Linie dieser Rolle "
                             "vor, die das trifft — kein Gate, das sie zeichnen durfte")
            continue
        text = (f"verfallen: jede fruehere Abnahme {t['gates']} dieser Rolle traegt nichts "
                "mehr, gleich wann sie gezeichnet wurde — auch unter frueheren Namen und "
                f"Schluesseln ihrer Linie ({wer}), auch wenn ein frueheres Glied sie fuer "
                "gueltig erklaert hat; neu zu zeichnen unter der Spitze, auch die Erstabnahmen "
                "im Linienbereich")
        if "A-M6" in t["gates"]:
            text += (". Darunter der Fallauftrag: jeder so gezeichnete Fallauftrag (A-M6; "
                     "unter den genannten Gliedern, mit einem der genannten Schluessel) und "
                     "alles, was darauf gruendet, faellt — jede Annahme jedes Falls, der unter "
                     "einem dieser Auftraege beauftragt ist, auch beim Betrieb (Registrierung, "
                     "Zugangsprobe, Neuaufsetzen); ein Zugang, der vorher schon registriert "
                     "wurde, bleibt registriert; die Glieder der Linie bleiben gueltig")
        folgen[rolle] = text
    return folgen


def _zeitpunkt(wert: object) -> Optional[Any]:
    """Ein ISO-Zeitpunkt MIT Zeitzone als ``datetime`` (None = nicht lesbar).
    Verglichen wird auf geparsten Zeitpunkten, nie auf Zeichenketten."""
    from datetime import datetime

    if not isinstance(wert, str):
        return None
    try:
        zeit = datetime.fromisoformat(wert)
    except ValueError:
        return None
    return zeit if zeit.tzinfo is not None and zeit.utcoffset() is not None else None


def aenderung_text(eintrag: Dict[str, Any]) -> str:
    """Eine Aenderung in Unternehmenssprache (fuer die Sicht)."""
    art, rolle = eintrag["art"], eintrag["rolle"]
    if art == "neue_rolle":
        return (f"neue Rolle {rolle} (Klasse {eintrag.get('schluesselklasse')}, Schluessel "
                f"{str(eintrag.get('schluessel_sha256'))[:16]}) mit {eintrag['gates']}")
    if art == "rolle_entfallen":
        return f"Rolle {rolle} entfaellt (hatte {eintrag['gates']})"
    if art == "gates_erweitert":
        return f"bestehende Rolle {rolle} um {eintrag['gates']} erweitert"
    if art == "gates_entzogen":
        return f"Rolle {rolle} werden {eintrag['gates']} entzogen"
    if art == "schluessel_gewechselt":
        return (f"Rolle {rolle} wechselt den Schluessel: {str(eintrag['vorher'])[:16]} -> "
                f"{str(eintrag['nachher'])[:16]}")
    return f"Rolle {rolle} wechselt die Klasse: {eintrag['vorher']} -> {eintrag['nachher']}"


def vorstand_schluessel_sha256(ordnung: dict) -> str:
    return str(ordnung["rollen"][WURZELROLLE]["schluessel_sha256"])


def _nachricht(glied: Dict[str, Any]) -> bytes:
    return _kanonisch({k: v for k, v in glied.items()
                       if k not in ("zeichnung", "glied_sha256")})


def zeichne_glied(glied: Dict[str, Any], schluessel: bytes, klasse: str) -> Dict[str, Any]:
    """Die Zeichnung der Ordnungsaenderung (A-Z1) ueber ein Glied."""
    import hmac

    return {
        "gate": ORDNUNGS_GATE, "rolle": WURZELROLLE, "schluesselklasse": klasse,
        "schluessel_sha256": hashlib.sha256(schluessel).hexdigest(),
        "verfahren": ZEICHEN_VERFAHREN,
        "signatur": hmac.new(schluessel, _nachricht(glied), hashlib.sha256).hexdigest(),
    }


def _zeichnung_form_fehler(glied: Dict[str, Any], vorher: Dict[str, Any]
                           ) -> Tuple[List[str], Optional[str]]:
    """Was sich an der Zeichnung eines Glieds OHNE Schluessel pruefen laesst:
    Felder, Gate, Rolle, Verfahren, Fingerabdruck und Klasse gegen die Spitze
    davor. Rueckgabe ``(fehler, fingerabdruck, den die Spitze davor dem
    Vorstand gibt)``."""
    z = glied.get("zeichnung")
    if not isinstance(z, dict) or set(z) != ZEICHNUNG_FELDER:
        return [f"Glied {glied.get('nummer')}: ohne Zeichnung von {WURZELROLLE} "
                f"({ORDNUNGS_GATE}) nicht gueltig — {sorted(ZEICHNUNG_FELDER)}"], None
    alt = ordnung_aus(vorher)
    soll_fp = vorstand_schluessel_sha256(alt)
    fehler = []
    if (z.get("gate"), z.get("rolle"), z.get("verfahren")) != (
            ORDNUNGS_GATE, WURZELROLLE, ZEICHEN_VERFAHREN):
        fehler.append(f"Glied {glied.get('nummer')}: Zeichnung nicht {ORDNUNGS_GATE} von "
                      f"{WURZELROLLE}")
    if z.get("schluessel_sha256") != soll_fp:
        fehler.append(
            f"Glied {glied.get('nummer')}: gezeichnet mit {str(z.get('schluessel_sha256'))[:16]}, "
            f"die Spitze davor (Glied {vorher.get('nummer')}) gibt {WURZELROLLE} den "
            f"Schluessel {soll_fp[:16]}")
    if z.get("schluesselklasse") != alt["rollen"][WURZELROLLE].get("schluesselklasse"):
        fehler.append(f"Glied {glied.get('nummer')}: Schluesselklasse der Zeichnung ist nicht "
                      "die der Spitze davor")
    return fehler, soll_fp


def zeichnung_fehler(glied: Dict[str, Any], vorher: Dict[str, Any],
                     ring: Mapping[str, bytes]) -> List[str]:
    """Ob ``glied`` von der Wurzelrolle mit dem Schluessel gezeichnet ist,
    den ``vorher`` (die Spitze davor) dieser Rolle gibt — Form UND Signatur.

    Pruefrunde G (G09): Die Signatur wurde nur geprueft, wenn der Schluessel
    zufaellig im Ring lag, und kein gruendender Leser reichte einen Ring;
    ein Glied mit geratener Signatur und richtigem Fingerabdruck galt. Jetzt
    ist der Schluessel Pflicht: Fehlt er im Ring, ist das Glied NICHT
    PRUEFBAR, und das ist ein Fehler, kein stiller Verzicht.
    """
    import hmac

    fehler, soll_fp = _zeichnung_form_fehler(glied, vorher)
    if soll_fp is None:
        return fehler
    if soll_fp not in ring:
        fehler.append(
            f"Glied {glied.get('nummer')}: der Schluessel von {WURZELROLLE}, den die Spitze "
            f"davor (Glied {vorher.get('nummer')}) gibt ({soll_fp[:16]}), ist nicht im Ring — "
            "ohne ihn ist die Zeichnung des Glieds nicht pruefbar, und auf einer ungeprueften "
            "Linie gruendet nichts (ADR-025, Nachtrag Pruefrunde G). Ausweg: den Schluessel "
            "des Vorstands in den Ring geben (gate_entscheid und die Kommandos des Betriebs: "
            "als weiteren --freigabe-schluessel; stand_belegen ordnung: --vorstand-schluessel)")
        return fehler
    erwartet = hmac.new(ring[soll_fp], _nachricht(glied), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(erwartet, str(glied["zeichnung"].get("signatur"))):
        fehler.append(f"Glied {glied.get('nummer')}: die Signatur stimmt nicht mit dem "
                      "Inhalt ueberein")
    return fehler


def baue_glied(
    ordnung_roh: bytes, *, nummer: int, vorgaenger: Optional[str], eingetragen_am: str,
    vorstand: Optional[Tuple[bytes, str]] = None, vorher: Optional[dict] = None,
    fruehere_zeichnungen: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Ein Glied aus den Bytes einer Ordnungsdatei (ohne es zu schreiben).
    ``vorher``: die Ordnung der Spitze davor (None beim ersten Glied).
    ``fruehere_zeichnungen``: die Erklaerung je geminderter Rolle; geprueft
    wird sie in :func:`neues_glied` und beim Laden (:func:`glied_fehler`) —
    ein Glied mit Minderung ohne Erklaerung baut dieser Bauer, aber niemand
    haengt es an oder liest es."""
    text = ordnung_roh.decode("utf-8")
    glied: Dict[str, Any] = {
        "schema_version": GLIED_SCHEMA_VERSION,
        "art": GLIED_ART,
        "nummer": nummer,
        "vorgaenger": vorgaenger,
        "ordnung_sha256": hashlib.sha256(ordnung_roh).hexdigest(),
        "ordnung_text": text,
        "aenderungen": aenderungen(vorher, json.loads(text)),
        "fruehere_zeichnungen": dict(fruehere_zeichnungen or {}),
        "eingetragen_am": eingetragen_am,
        "eintrag": {"art": "wurzel" if vorgaenger is None else "anhang",
                    "vermerk": WURZEL_VERMERK if vorgaenger is None else ANHANG_VERMERK},
        "zeichnung": None,
    }
    if vorstand is not None:
        glied["zeichnung"] = zeichne_glied(glied, vorstand[0], vorstand[1])
    glied["glied_sha256"] = glied_sha256(glied)
    return glied


def glied_fehler(glied: object) -> List[str]:
    """Was an einem einzelnen Glied nicht stimmt (ohne die Kette)."""
    if not isinstance(glied, dict):
        return ["kein JSON-Objekt"]
    fehler: List[str] = []
    if set(glied) != GLIED_FELDER:
        fehler.append(f"ein Glied traegt genau die Felder {sorted(GLIED_FELDER)}")
        return fehler
    if glied.get("schema_version") != GLIED_SCHEMA_VERSION or glied.get("art") != GLIED_ART:
        fehler.append(f"schema_version {GLIED_SCHEMA_VERSION} und art {GLIED_ART!r} erwartet")
    if not (type(glied.get("nummer")) is int and glied["nummer"] >= 1):
        fehler.append("nummer muss eine ganze Zahl ab 1 sein")
    if glied.get("glied_sha256") != glied_sha256(glied):
        fehler.append("glied_sha256 stimmt nicht mit dem Inhalt ueberein — das Glied "
                      "wurde nach dem Eintragen veraendert")
    text = glied.get("ordnung_text")
    if not isinstance(text, str) or hashlib.sha256(text.encode("utf-8")).hexdigest() \
            != glied.get("ordnung_sha256"):
        fehler.append("ordnung_sha256 ist nicht der Hash von ordnung_text")
    else:
        fehler += ordnung_inhalt_fehler(text)[1]
    if not (isinstance(glied.get("eingetragen_am"), str) and glied["eingetragen_am"].strip()):
        fehler.append("eingetragen_am fehlt")
    # Die Erklaerung je geminderter Rolle (Pruefrunde H): ueber die
    # GESPEICHERTE Aenderungsliste; dass sie die gerechnete ist, haelt die
    # Kette (_lade). Fehlt sie, ist das Glied kein Glied.
    fehler += erklaerung_fehler(glied.get("fruehere_zeichnungen"), glied.get("aenderungen"))
    erwartet = "wurzel" if glied.get("vorgaenger") is None else "anhang"
    if erwartet == "wurzel" and glied.get("zeichnung") is not None:
        fehler.append("das erste Glied ist unsigniert (zeichnung None) — es ist die Wurzel")
    eintrag = glied.get("eintrag")
    if not (isinstance(eintrag, dict) and eintrag.get("art") == erwartet and eintrag.get(
            "vermerk") == (WURZEL_VERMERK if erwartet == "wurzel" else ANHANG_VERMERK)):
        fehler.append(f"eintrag muss {{art: {erwartet!r}, vermerk: <woertlich>}} sein")
    return fehler


def lade_linie(bereich: Path, *, ring: Mapping[str, bytes],
               ) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Die Glieder der Linie in ``<bereich>/ordnung/``, geprueft, aelteste zuerst
    — der Einstieg fuer jeden Leser, der auf der Linie GRUENDET.

    Rueckgabe ``(glieder, fehler)``; bei Fehlern ist die Linie nicht
    verwendbar. Leere Liste ohne Fehler: es gibt (noch) keine Linie.

    ``ring`` ist Pflicht und hat keinen Default (Pruefrunde G, G09): Jedes
    Glied nach dem ersten wird gegen den Schluessel des Vorstands geprueft,
    den die Spitze davor gibt; liegt er nicht im Ring, ist die Linie nicht
    verwendbar (benannt, mit Ausweg). Eine Linie mit genau einem Glied hat
    nichts zu pruefen: Die Wurzel ist unsigniert (ADR-025, Abschnitt 7).
    Wer die Linie nur ZEIGT, liest sie mit
    :func:`lade_linie_strukturell_zur_anzeige`.
    """
    if ring is None:
        raise TypeError("lade_linie: ring ist Pflicht (kein None) — wer die Linie nur "
                        "zeigt, liest sie mit lade_linie_strukturell_zur_anzeige")
    return _lade(Path(bereich), ring)


def lade_linie_strukturell_zur_anzeige(bereich: Path) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Die Glieder der Linie STRUKTURELL — fuer anzeigende Werkzeuge (Sichten).

    Prueft Form, Kette, Hashes, gerechnete Aenderungslisten und die Form der
    Zeichnungen (Fingerabdruck und Klasse gegen die Spitze davor), NICHT die
    Signaturen der Glieder. Darauf gruendet nichts: keine Annahme, kein
    Verweis, keine Registrierung, keine Bindung (Ratsche in
    ``tests/test_linie_pflicht.py``). Der Name sagt es, damit es kein
    Aufrufer uebersieht.
    """
    return _lade(Path(bereich), None)


def _lade(bereich: Path, ring: Optional[Mapping[str, bytes]]
          ) -> Tuple[List[Dict[str, Any]], List[str]]:
    """``ring`` None: strukturell (nur ueber den benannten Anzeige-Einstieg)."""
    verzeichnis = Path(bereich) / VERZEICHNIS
    if not verzeichnis.is_dir():
        return [], []
    glieder: List[Dict[str, Any]] = []
    fehler: List[str] = []
    for pfad in sorted(verzeichnis.iterdir()):
        if pfad.name.startswith(".") and pfad.name.endswith(".tmp"):
            continue  # Rest eines abgebrochenen exklusiven Schreibens (kein Glied)
        try:
            glied = json.loads(pfad.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            fehler.append(f"{pfad.name}: nicht lesbar ({exc})")
            continue
        gf = glied_fehler(glied)
        if not gf and pfad.name != dateiname(glied):
            gf.append(f"Dateiname passt nicht zum Glied (erwartet {dateiname(glied)})")
        fehler += [f"{pfad.name}: {f}" for f in gf]
        if not gf:
            glieder.append(glied)
    if fehler:
        return [], fehler
    glieder.sort(key=lambda g: g["nummer"])
    gesehen: Dict[str, int] = {}
    for i, glied in enumerate(glieder):
        if glied["nummer"] != i + 1:
            fehler.append(f"Luecke oder Doppel in der Linie: Glied {glied['nummer']} an "
                          f"Stelle {i + 1}")
        soll = None if i == 0 else glieder[i - 1]["glied_sha256"]
        if glied["vorgaenger"] != soll:
            fehler.append(f"Glied {glied['nummer']}: Vorgaenger {str(glied['vorgaenger'])[:16]} "
                          f"ist nicht das Glied davor ({str(soll)[:16]}) — die Linie ist "
                          "umgeschrieben oder unterbrochen")
        vorher = ordnung_aus(glieder[i - 1]) if i > 0 else None
        if glied["aenderungen"] != aenderungen(vorher, ordnung_aus(glied)):
            fehler.append(f"Glied {glied['nummer']}: die Aenderungsliste ist nicht die aus "
                          "beiden Staenden gerechnete — sie wird nicht behauptet")
        if i > 0 and not fehler:
            fehler += (zeichnung_fehler(glied, glieder[i - 1], ring) if ring is not None
                       else _zeichnung_form_fehler(glied, glieder[i - 1])[0])
        if glied["ordnung_sha256"] in gesehen:
            fehler.append(f"Glied {glied['nummer']}: dieselbe Ordnung steht schon als Glied "
                          f"{gesehen[glied['ordnung_sha256']]}")
        gesehen.setdefault(glied["ordnung_sha256"], glied["nummer"])
    return ([], fehler) if fehler else (glieder, [])


def spitze(glieder: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    return glieder[-1] if glieder else None


def glied_fuer(glieder: List[Dict[str, Any]], sha: object) -> Optional[Dict[str, Any]]:
    for glied in glieder:
        if glied["glied_sha256"] == sha:
            return glied
    return None


def ordnung_aus(glied: Dict[str, Any]) -> dict:
    return json.loads(glied["ordnung_text"])


def pruefe_anhang(
    glieder: List[Dict[str, Any]], ordnung_roh: bytes, *, vorgaenger: Optional[str],
    eingetragen_am: str, uhr: str,
) -> List[Dict[str, Any]]:
    """Was vor jedem Anhaengen gilt, OHNE Erklaerung und Zeichnung — fuer das
    Glied (:func:`neues_glied`) und seine Vorschau (``stand_belegen ordnung
    --vorschau``, Pruefrunde I): Vorgaenger ist die Spitze, die Ordnung darf in
    die Linie und steht noch nicht darin, ``eingetragen_am`` ist ein Zeitpunkt
    mit Zeitzone, nicht vor dem der Spitze und nicht nach der Uhr des Aufrufs
    (``uhr``). Rueckgabe: die gerechnete Aenderungsliste; sonst
    :class:`OrdnungslinieFehler` mit Ausweg."""
    oben = spitze(glieder)
    if vorgaenger != (oben["glied_sha256"] if oben else None):
        raise OrdnungslinieFehler(
            f"der genannte Vorgaenger {str(vorgaenger)[:16]} ist nicht die Spitze der Linie "
            f"({str(oben['glied_sha256'])[:16] if oben else 'keine — die Linie ist leer'}) — "
            "angehaengt wird nur an die Spitze. Ausweg: die Linie ansehen und die Spitze "
            "als Vorgaenger nennen")
    try:
        text = ordnung_roh.decode("utf-8")
    except UnicodeError as exc:
        raise OrdnungslinieFehler(f"die Ordnung ist kein UTF-8 ({exc})") from exc
    _, fehler = ordnung_inhalt_fehler(text)
    if fehler:
        raise OrdnungslinieFehler("die Ordnung kann nicht in die Linie: " + "; ".join(fehler[:3]))
    sha = hashlib.sha256(ordnung_roh).hexdigest()
    for glied in glieder:
        if glied["ordnung_sha256"] == sha:
            raise OrdnungslinieFehler(
                f"diese Ordnung steht schon als Glied {glied['nummer']} in der Linie — ein "
                "Stand wird einmal eingetragen")
    if not (isinstance(eingetragen_am, str) and eingetragen_am.strip()):
        raise OrdnungslinieFehler("eingetragen_am fehlt")
    zeit = _zeitpunkt(eingetragen_am)
    if zeit is None:
        raise OrdnungslinieFehler(
            f"eingetragen_am {eingetragen_am!r} ist kein Zeitpunkt mit Zeitzone (ISO-8601) — "
            "die Leser halten Zeichnungen gegen ihn")
    if oben is not None:
        zeit_oben = _zeitpunkt(oben.get("eingetragen_am"))
        if zeit_oben is None or zeit < zeit_oben:
            raise OrdnungslinieFehler(
                f"eingetragen_am {eingetragen_am} liegt vor dem der Spitze (Glied "
                f"{oben['nummer']}, {oben.get('eingetragen_am')}) oder jener ist nicht lesbar — "
                "ein Glied wird nicht frueher datiert als sein Vorgaenger: Die Leser halten "
                "jede Zeichnung gegen den Zeitpunkt, zu dem ihr Glied abgeloest wurde. Ausweg: "
                "--eingetragen-am weglassen (die Uhr des Aufrufs) oder einen spaeteren nennen")
    # Nicht spaeter als die Uhr des Aufrufs (Pruefrunde I, I04): Ein Glied in
    # der Zukunft liesse unter der Zeitregel Zeichnungen des abgeloesten
    # Schluessels gelten, die NACH dem tatsaechlichen Anhaengen entstehen, und
    # machte jedes naechste Glied mit der Uhr unanhaengbar. Keine Toleranz:
    # Wer anhaengt, ist der Prozess, dessen Uhr gilt.
    jetzt = _zeitpunkt(uhr)
    if jetzt is None:
        raise OrdnungslinieFehler(f"die Uhr des Aufrufs {uhr!r} ist kein Zeitpunkt mit Zeitzone")
    if zeit > jetzt:
        raise OrdnungslinieFehler(
            f"eingetragen_am {eingetragen_am} liegt nach der Uhr des Aufrufs ({uhr}) — ein Glied "
            "wird nicht spaeter datiert als sein Anhaengen: Die Leser liessen sonst bis zu "
            "diesem Zeitpunkt Zeichnungen des abgeloesten Schluessels gelten, und jedes naechste "
            "Glied waere mit der Uhr nicht mehr anhaengbar (ADR-025, Nachtrag Pruefrunde I). "
            "Ausweg: --eingetragen-am weglassen (die Uhr des Aufrufs) oder einen Zeitpunkt "
            "nennen, der nicht in der Zukunft liegt")
    return aenderungen(ordnung_aus(oben) if oben is not None else None, json.loads(text))


def neues_glied(
    glieder: List[Dict[str, Any]], ordnung_roh: bytes, *, vorgaenger: Optional[str],
    eingetragen_am: str, uhr: str, fruehere_zeichnungen: Mapping[str, str],
    vorstand_schluessel: Optional[bytes] = None,
) -> Dict[str, Any]:
    """Das naechste Glied — oder :class:`OrdnungslinieFehler` mit Ausweg.

    ``vorgaenger`` nennt der Mensch ausdruecklich (die Spitze, wie er sie
    gesehen hat; ``None`` fuer das erste Glied): Ein Eintrag, der auf einem
    anderen Stand der Linie gedacht war als dem, der liegt, wird nicht
    angehaengt.

    ``fruehere_zeichnungen`` (Pflicht, ohne Vorgabe; Pruefrunde H): je Rolle,
    die das Glied MINDERT (:data:`MINDERUNGSARTEN`), genau eine Aussage
    :data:`ERKLAERUNGEN` — gezeichnet mit dem Glied. ``eingetragen_am`` ist ein
    Zeitpunkt mit Zeitzone, liegt nicht vor dem des Vorgaengers (monoton) und
    nicht nach ``uhr``, der Uhr des Aufrufs (Pflicht, ohne Vorgabe; Pruefrunde
    I): Die Zeitregel der Leser vergleicht Zeichnungen gegen ihn.
    """
    oben = spitze(glieder)
    aliste = pruefe_anhang(glieder, ordnung_roh, vorgaenger=vorgaenger,
                           eingetragen_am=eingetragen_am, uhr=uhr)
    erwartet = geminderte_rollen(aliste)
    efehler = erklaerung_fehler(dict(fruehere_zeichnungen) if isinstance(
        fruehere_zeichnungen, Mapping) else fruehere_zeichnungen, aliste)
    if efehler:
        raise OrdnungslinieFehler(
            "; ".join(efehler) + f" — dieses Glied mindert {erwartet or 'keine Rolle'}. Ausweg: "
            "je geminderter Rolle --fruehere-zeichnungen <rolle>=gueltig (ihre frueheren "
            "Zeichnungen tragen weiter, etwa bei einer Umbenennung oder einem geordneten "
            "Wechsel, der Halter ist derselbe) oder <rolle>=verfallen (sie tragen nichts mehr, "
            "etwa bei einem Schluessel, dem nicht mehr getraut wird; neu zu zeichnen) "
            "(ADR-025, Nachtrag Pruefrunde H). Was jede Erklaerung je Rolle kostet, zeigt "
            f"vorher, ohne etwas zu schreiben: {VORSCHAU_KOMMANDO}")
    vorstand: Optional[Tuple[bytes, str]] = None
    if oben is not None:
        alt = ordnung_aus(oben)
        soll = vorstand_schluessel_sha256(alt)
        if vorstand_schluessel is None or \
                hashlib.sha256(vorstand_schluessel).hexdigest() != soll:
            raise OrdnungslinieFehler(
                f"ein Glied nach dem ersten zeichnet {WURZELROLLE} ({ORDNUNGS_GATE}) mit "
                f"dem Schluessel, den die Spitze (Glied {oben['nummer']}) ihr gibt "
                f"({soll[:16]}) — ohne diese Zeichnung ist es nicht anhaengbar. Ausweg: "
                "--vorstand-schluessel <schluessel der Rolle laut Spitze>")
        vorstand = (vorstand_schluessel,
                      str(alt["rollen"][WURZELROLLE]["schluesselklasse"]))
    return baue_glied(ordnung_roh, nummer=len(glieder) + 1, vorgaenger=vorgaenger,
                      eingetragen_am=eingetragen_am, vorstand=vorstand,
                      vorher=ordnung_aus(oben) if oben is not None else None,
                      fruehere_zeichnungen=dict(fruehere_zeichnungen))


def damalige_ordnung(
    snapshot: object, glieder: List[Dict[str, Any]], *, gate: str,
) -> Tuple[Optional[dict], Optional[str]]:
    """Die Ordnung, unter der ``snapshot`` gezeichnet wurde — aus der Linie.

    ``(ordnung, None)`` oder ``(None, meldung)``. Lokalisiert wird ueber
    das GLIED, das die Zeichnung pinnt (``zeichnung.ordnungsglied_sha256``),
    nicht nur ueber den Hash der Ordnungsdatei: Ein ausgetauschtes Glied
    aendert jeden Glied-Hash danach und faellt hier auf.

    Danach (Pruefrunde H, H06/H10) die spaeteren Glieder der Linie DES
    LESERS: :func:`abloesung_fehler`. Die Stelle, durch die jeder gruendende
    Leser die Rolle eines Abnahme-Snapshots aufloest
    (``models.zeichnung.zeichnende_rolle_fehler``) — die Glieder der Linie
    selbst gehen nicht hier durch, sie prueft :func:`lade_linie` Glied fuer
    Glied gegen den Vorstand des Vorgaengers.
    """
    daten = snapshot if isinstance(snapshot, dict) else {}
    z = daten.get("zeichnung") if isinstance(daten.get("zeichnung"), dict) else {}
    glied_sha = z.get("ordnungsglied_sha256")
    if not glied_sha:
        return None, (
            "der Snapshot pinnt kein Glied der Ordnungslinie — er wurde vor der Linie "
            "oder ohne sie gezeichnet und ist in der Geschichte nicht lokalisierbar; als "
            "Grundlage ist er nicht verwendbar (ADR-025, Schnitt der Linie). Ausweg: die "
            "Abnahme unter der Spitze der Linie neu zeichnen")
    glied = glied_fuer(glieder, glied_sha)
    if glied is None:
        return None, (
            f"das Glied {str(glied_sha)[:16]}, das der Snapshot pinnt, steht nicht in der "
            "Ordnungslinie — die Linie ist eine andere oder ihr Glied wurde ausgetauscht. "
            "Ausweg: die Linie pruefen; eine Abnahme unter einem fremden Glied neu zeichnen")
    if glied["ordnung_sha256"] != z.get("ordnung_sha256"):
        return None, (
            f"das gepinnte Glied {glied['nummer']} traegt die Ordnung "
            f"{glied['ordnung_sha256'][:16]}, der Snapshot nennt "
            f"{str(z.get('ordnung_sha256'))[:16]} — Glied und Ordnung gehoeren nicht zusammen")
    meldung = abloesung_fehler(daten, glieder, glied, gate=gate)
    if meldung is not None:
        return None, meldung
    return ordnung_aus(glied), None


def abloesung_fehler(
    snapshot: Dict[str, Any], glieder: List[Dict[str, Any]], glied: Dict[str, Any], *, gate: str,
) -> Optional[str]:
    """Traegt eine Abnahme noch, deren gepinntes Glied ``glied`` in der Linie
    des Lesers (``glieder``) inzwischen abgeloest ist? (None = ja.)

    Pruefrunde H (H06/H10): Eine AELTERE KOPIE der Linie (vor einem spaeter
    angehaengten Glied) liess einen entzogenen Schluessel unter ihrer alten
    Spitze zeichnen, und der Leser mit der echten Linie nahm die Zeichnung an,
    weil er die Rolle gegen das gepinnte Glied hielt. Die Grundlage ist die
    gezeichnete ERKLAERUNG des Vorstands im abloesenden Glied, die Zeit nur
    eine Plausibilitaet daneben:

    Die Zeichnung (Rolle R des Fingerabdrucks F unter dem gepinnten Glied,
    Gate G, Klasse K) wird ueber JEDES spaetere Glied verfolgt, und mit ihr die
    Linie von R (Namen und Schluessel, Kontinuitaet ueber den Namen oder den
    Schluessel; Pruefrunde I). Die Regel steht an EINER Stelle,
    :func:`treffer_der_erklaerungen`; aus ihr kommt auch die Folge, die der
    Produzent nennt (:func:`folge_der_erklaerung`):

    * ``verfallen`` an einem spaeteren Glied fuer eine geminderte Rolle der
      Linie (fuer G, oder fuer den Schluessel ueberhaupt) — verweigert, gleich
      wann gezeichnet wurde (eine zurueckgestellte Uhr hilft nicht) und gleich,
      ob ein frueheres Glied ``gueltig`` erklaert hat;
    * ``gueltig`` an dem Glied, mit dem F das Gate G unter keinem Namen der
      Linie mehr traegt — die Zeichnung traegt, wenn sie VOR dem
      ``eingetragen_am`` dieses Glieds entstand (``entschieden_am`` im
      signierten Inhalt); sonst verweigert: gezeichnet wird nur unter der
      Spitze. Ein nicht lesbarer Zeitpunkt verweigert.

    Trifft kein spaeteres Glied die Zeichnung, gilt sie (ein spaeteres Glied,
    das die Linie nicht mindert, entwertet nichts). Ein Fingerabdruck, den das
    gepinnte Glied keiner Rolle gibt, ist Sache der Rollenregel danach
    (``zeichnende_rolle_fehler``), ebenso die Fall-Rollen (ihr Recht kommt aus
    dem Fallauftrag, die Linie fuehrt sie nicht).
    """
    i = next((k for k, g in enumerate(glieder) if g is glied
              or g.get("glied_sha256") == glied.get("glied_sha256")), None)
    if i is None or i == len(glieder) - 1:
        return None
    fp = str(((snapshot.get("freigabe") or {}) if isinstance(snapshot.get("freigabe"), dict)
              else {}).get("schluessel_sha256") or "")
    damals = ordnung_aus(glied)
    rolle = next((n for n, e in _rollen(damals).items() if e.get("schluessel_sha256") == fp),
                 None)
    if rolle is None:
        return None
    treffer = treffer_der_erklaerungen(
        glieder, i, rolle=rolle, schluessel_sha256=fp, gate=gate,
        klasse=damals["rollen"][rolle].get("schluesselklasse"))
    ausweg = (f"Ausweg: {gate} unter der Spitze der Linie (Glied {glieder[-1]['nummer']}) "
              "mit einem Schluessel neu zeichnen, dem sie das Gate gibt (ADR-025, "
              "Nachtraege Pruefrunde H und I)")

    def linie_von(r: str) -> str:
        return "" if r == rolle else (
            f" (sie fuehrt die Linie der zeichnenden Rolle {rolle} fort — ueber den Namen oder "
            "den Schluessel)")

    for j, r, art in treffer:
        if art == "verfallen":
            spaeter = glieder[j]
            return (
                f"die Zeichnung pinnt Glied {glied['nummer']}; mit Glied {spaeter['nummer']} "
                f"(eingetragen am {spaeter.get('eingetragen_am')}) hat der Vorstand die "
                f"frueheren Zeichnungen der Rolle {r}{linie_von(r)} fuer verfallen erklaert — "
                f"diese {gate}-Abnahme traegt nichts mehr, gleich wann sie gezeichnet wurde. "
                f"{ausweg}")
    for j, r, art in treffer:
        spaeter = glieder[j]
        if art == "unlesbar":
            return (
                f"die Zeichnung pinnt Glied {glied['nummer']}; mit Glied {spaeter['nummer']} "
                f"(eingetragen am {spaeter.get('eingetragen_am')}) hat der Vorstand die "
                f"frueheren Zeichnungen der Rolle {r} nichts Lesbares erklaert — diese "
                f"{gate}-Abnahme traegt nichts mehr, gleich wann sie gezeichnet wurde. {ausweg}")
        entschieden = _zeitpunkt(snapshot.get("entschieden_am"))
        abgeloest = _zeitpunkt(spaeter.get("eingetragen_am"))
        if entschieden is None or abgeloest is None:
            return (
                f"die Zeichnung pinnt Glied {glied['nummer']}, das Glied "
                f"{spaeter['nummer']} fuer die Rolle {r} abgeloest hat; ob sie vor der "
                "Abloesung entstand, ist nicht entscheidbar (entschieden_am "
                f"{snapshot.get('entschieden_am')!r}, eingetragen_am "
                f"{spaeter.get('eingetragen_am')!r} — kein Zeitpunkt mit Zeitzone). {ausweg}")
        if not entschieden < abgeloest:
            return (
                f"unter einem abgeloesten Glied gezeichnet: Glied {glied['nummer']} wurde fuer "
                f"die Rolle {r} am {spaeter.get('eingetragen_am')} durch Glied "
                f"{spaeter['nummer']} abgeloest, gezeichnet am "
                f"{snapshot.get('entschieden_am')}; gezeichnet wird nur unter der Spitze. "
                f"Glied {spaeter['nummer']} erklaert die frueheren Zeichnungen der Rolle fuer "
                f"gueltig — das traegt Zeichnungen VOR der Abloesung. {ausweg}")
    return None
