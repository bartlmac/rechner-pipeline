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
Name ``<nummer:04d>-<glied_sha256>.json``, exklusiv geschrieben):

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
nichts anderes (gates genau ``["A-Z1"]``), und keine andere Rolle zeichnet
``A-Z1``: Wer Zeichnungsrechte vergibt, nimmt nichts fachlich ab. Ein Agent
hat kein Gegenstueck dazu — Zeichnungsrechte vergibt kein Agent.

Grenze der Aussage: Die Zeichnung ist ein HMAC. Wer den Vorstands-Schluessel
nicht haelt, prueft Form und Fingerabdruck (gegen die Spitze davor), nicht die
Signatur; mit dem Schluessel im Ring prueft :func:`lade_linie` auch sie.

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
from typing import Any, Dict, List, Optional, Tuple

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
#: Anzeige der Rolle in Unternehmenssprache.
WURZELROLLE_ANZEIGE = "Vorstand"
ZEICHEN_VERFAHREN = "hmac-sha256-v1"
#: Rollen des ABGEBENDEN Hauses (ADR-018): Die Ordnung der PLV fuehrt nur
#: Rollen der PLV, der Vorstand vergibt nur diese.
ROLLEN_DES_ABGEBENDEN_HAUSES = ("mensch/quell-aktuar",)
ZEICHNUNG_FELDER = frozenset({"gate", "rolle", "schluesselklasse", "schluessel_sha256",
                              "verfahren", "signatur"})
GLIED_SCHEMA_VERSION = 1
GLIED_ART = "ordnungsglied"
GLIED_FELDER = frozenset({
    "schema_version", "art", "nummer", "vorgaenger", "ordnung_sha256",
    "ordnung_text", "aenderungen", "eingetragen_am", "eintrag", "zeichnung",
    "glied_sha256",
})
#: Die Arten einer Aenderung zwischen zwei Staenden der Ordnung — GERECHNET
#: aus beiden Staenden, nie vom Bediener behauptet (ADR-025). Eine stille
#: Verbreiterung einer bestehenden Rolle heisst ``gates_erweitert`` und ist
#: von ``neue_rolle`` unterscheidbar.
AENDERUNGSARTEN = ("neue_rolle", "rolle_entfallen", "gates_erweitert", "gates_entzogen",
                   "schluessel_gewechselt", "klasse_geaendert")
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
    return f"{int(glied['nummer']):04d}-{glied['glied_sha256']}.json"


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
    if not isinstance(vorstand, dict) or vorstand.get("gates") != [ORDNUNGS_GATE] \
            or vorstand.get("schluesselklasse") not in ("mensch", "simulation"):
        return None, [
            f"die Ordnung fuehrt keine Rolle {WURZELROLLE!r} mit gates "
            f"[{ORDNUNGS_GATE!r}] und Schluesselklasse mensch/simulation — ohne sie zeichnet "
            "niemand das naechste Glied, und sie zeichnet nichts anderes (ADR-025)"]
    fremd = sorted(n for n, e in daten["rollen"].items()
                   if n != WURZELROLLE and ORDNUNGS_GATE in (e.get("gates") or []))
    if fremd:
        return None, [f"{ORDNUNGS_GATE} zeichnet nur {WURZELROLLE}, nicht {fremd}"]
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


def zeichnung_fehler(glied: Dict[str, Any], vorher: Dict[str, Any],
                     ring: Optional[Dict[str, bytes]] = None) -> List[str]:
    """Ob ``glied`` von der Wurzelrolle mit dem Schluessel gezeichnet ist,
    den ``vorher`` (die Spitze davor) dieser Rolle gibt."""
    import hmac

    z = glied.get("zeichnung")
    if not isinstance(z, dict) or set(z) != ZEICHNUNG_FELDER:
        return [f"Glied {glied.get('nummer')}: ohne Zeichnung von {WURZELROLLE} "
                f"({ORDNUNGS_GATE}) nicht gueltig — {sorted(ZEICHNUNG_FELDER)}"]
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
    if ring and soll_fp in ring:
        erwartet = hmac.new(ring[soll_fp], _nachricht(glied), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(erwartet, str(z.get("signatur"))):
            fehler.append(f"Glied {glied.get('nummer')}: die Signatur stimmt nicht mit dem "
                          "Inhalt ueberein")
    return fehler


def baue_glied(
    ordnung_roh: bytes, *, nummer: int, vorgaenger: Optional[str], eingetragen_am: str,
    vorstand: Optional[Tuple[bytes, str]] = None, vorher: Optional[dict] = None,
) -> Dict[str, Any]:
    """Ein Glied aus den Bytes einer Ordnungsdatei (ohne es zu schreiben).
    ``vorher``: die Ordnung der Spitze davor (None beim ersten Glied)."""
    text = ordnung_roh.decode("utf-8")
    glied: Dict[str, Any] = {
        "schema_version": GLIED_SCHEMA_VERSION,
        "art": GLIED_ART,
        "nummer": nummer,
        "vorgaenger": vorgaenger,
        "ordnung_sha256": hashlib.sha256(ordnung_roh).hexdigest(),
        "ordnung_text": text,
        "aenderungen": aenderungen(vorher, json.loads(text)),
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
    erwartet = "wurzel" if glied.get("vorgaenger") is None else "anhang"
    if erwartet == "wurzel" and glied.get("zeichnung") is not None:
        fehler.append("das erste Glied ist unsigniert (zeichnung None) — es ist die Wurzel")
    eintrag = glied.get("eintrag")
    if not (isinstance(eintrag, dict) and eintrag.get("art") == erwartet and eintrag.get(
            "vermerk") == (WURZEL_VERMERK if erwartet == "wurzel" else ANHANG_VERMERK)):
        fehler.append(f"eintrag muss {{art: {erwartet!r}, vermerk: <woertlich>}} sein")
    return fehler


def lade_linie(bereich: Path, ring: Optional[Dict[str, bytes]] = None,
               ) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Die Glieder der Linie in ``<bereich>/ordnung/``, geprueft, aelteste zuerst.

    Rueckgabe ``(glieder, fehler)``; bei Fehlern ist die Linie nicht
    verwendbar. Leere Liste ohne Fehler: es gibt (noch) keine Linie.
    """
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
            fehler += zeichnung_fehler(glied, glieder[i - 1], ring)
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


def neues_glied(
    glieder: List[Dict[str, Any]], ordnung_roh: bytes, *, vorgaenger: Optional[str],
    eingetragen_am: str, vorstand_schluessel: Optional[bytes] = None,
) -> Dict[str, Any]:
    """Das naechste Glied — oder :class:`OrdnungslinieFehler` mit Ausweg.

    ``vorgaenger`` nennt der Mensch ausdruecklich (die Spitze, wie er sie
    gesehen hat; ``None`` fuer das erste Glied): Ein Eintrag, der auf einem
    anderen Stand der Linie gedacht war als dem, der liegt, wird nicht
    angehaengt.
    """
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
                      vorher=ordnung_aus(oben) if oben is not None else None)


def damalige_ordnung(
    snapshot: object, glieder: List[Dict[str, Any]],
) -> Tuple[Optional[dict], Optional[str]]:
    """Die Ordnung, unter der ``snapshot`` gezeichnet wurde — aus der Linie.

    ``(ordnung, None)`` oder ``(None, meldung)``. Lokalisiert wird ueber
    das GLIED, das die Zeichnung pinnt (``zeichnung.ordnungsglied_sha256``),
    nicht nur ueber den Hash der Ordnungsdatei: Ein ausgetauschtes Glied
    aendert jeden Glied-Hash danach und faellt hier auf.
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
    return ordnung_aus(glied), None
