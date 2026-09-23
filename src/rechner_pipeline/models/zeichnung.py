"""Zeichnungsordnung — der paketuebergreifende Rollen-Datenvertrag.

Die Ordnung bindet ROLLEN an Schluessel-Fingerabdruecke und GATES an
Rollen. Sie lebt ausserhalb des frei editierbaren Falls (eine Ordnung,
die der Fall selbst umschreiben kann, ordnet nichts) und wird von ZWEI
Konsumenten gelesen: den P9-Gates (``gates.gate_entscheid``) und der
endgueltigen Diskrepanz-Aufloesung (``ontologie.entscheide``) — seit
dem Vier-Rollen-Modell des zweiten Laufs entscheidet dort die fachlich
zeichnende Rolle, nicht mehr nur "der Mensch". Deshalb liegt der
Vertrag in ``models/`` (paketuebergreifend), nicht in einer der beiden
Schichten: ``ontologie -> gates`` waere eine neue Architektur-Kante.

Rollen werden aus dem SCHLUESSEL bestimmt, nie behauptet: Wer eine
Datei besitzt, deren SHA-256 die Ordnung einer Rolle zuordnet, handelt
als diese Rolle. Zwei Rollen mit demselben Fingerabdruck sind ein
Fehler — die Trennung der Operatoren waere sonst nur behauptet.

**Schema 2 (ADR-018): Rollenkennung und Schluesselklasse.** Eine Rolle
heisst ``mensch/<funktion>`` oder ``agent/<name>``; die Ebene steht im
Namen. Jede Rolle traegt eine ``schluesselklasse``: ``mensch`` (eine
natuerliche Person haelt den Schluessel), ``simulation`` (die Vorzeige
ahmt eine menschliche Rolle nach — dieselbe Kennung, andere Klasse,
jeder Beleg sagt es) oder ``agent`` (eine Agentenrolle des KI-Tools; sie
legt vor und zeichnet KEINE ABNAHME, ihre gates-Liste ist leer).

**Nachtrag 2026-09-16 (Entscheid des Maintainers).** Die Regel hiess
bis hierher "zeichnet nie". Das war eine Haelfte zu viel: Schuetzenswert
ist die ABNAHME — die Aussage eines Menschen, dass er fuer etwas
einsteht —, nicht jede Signatur. Ein Agent, der einen Ankersatz
zeichnet, sagt "ich habe dieses Paket erzeugt"; das ist eine Aussage
ueber Urheberschaft, keine Abnahme, und sein Beleg traegt die Klasse
``agent``, sodass niemand es verwechselt. Genau dafuer wurde die Klasse
eingefuehrt (T20/U1: aus keinem Beleg war ablesbar, ob ein Mensch oder
eine KI-Session gezeichnet hatte). Die gates-Liste einer Agentenrolle
bleibt leer — was ein Agent zeichnet, ist kein Gate.

Der praktische Grund: Bei vielen kleinen Migrationstranchen mit
taeglichen Exporten kann kein Mensch jeden Export zeichnen. Ein Agent
kann es, und der Beleg sagt, dass es einer war. Der Mensch zeichnet
dort, wo etwas nach aussen geht — einmal je Auslieferung (``A-B1``). Die Reviews T20
und U1 fanden, dass aus keinem Beleg ablesbar war, ob ein Mensch oder
eine KI-Session gezeichnet hatte; die Klasse wandert deshalb in die
Ordnung und von dort in jeden Snapshot. Ordnungen nach Schema 1 werden
mit Hinweis abgewiesen, nicht still gemappt.

Knoten: system/entscheid
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

#: Die Schluesselklassen (ADR-018).
SCHLUESSELKLASSEN = ("mensch", "simulation", "agent")
#: Klassen, deren Schluessel eine Annahme zeichnen duerfen.
ZEICHNENDE_KLASSEN = ("mensch", "simulation")
#: Rollenkennungen tragen die Ebene: mensch/<funktion> oder agent/<name>.
ROLLEN_MUSTER = re.compile(r"^(mensch|agent)/[a-z][a-z0-9-]*$")
ORDNUNG_SCHEMA_VERSION = 2


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
AUSWEG = (
    " — Ausweg: die Aufloesung bzw. Annahme mit dem Kommando neu zeichnen "
    "(Zeichnungsordnung und Freigabeschluessel, bei Schluesselklasse simulation --mandat)"
)


def validiere_zeichnung(zeichnung: object, *, form: str = "beide") -> List[str]:
    """Die Regel der Rollenbindung (ADR-018) — an EINER Stelle, fuer jeden
    Eintrittspunkt (Review T23-06). Leer = in Ordnung.

    Zwei Formen sind im Bestand: die Altform des Vier-Rollen-Modells
    ``{rolle, ordnung_sha256}`` (P9-Schema 6; A-Box-Aufloesungen bis
    2026-09) und die Form mit Schluesselklasse ``{rolle, ordnung_sha256,
    schluesselklasse[, mandat_sha256]}`` (P9-Schema 7). ``form`` sagt, was
    der Eintrittspunkt zulaesst: ``"alt"``, ``"neu"`` oder ``"beide"``.

    Die zentrale Aussage des Rollenmodells gilt in jeder Form: Eine
    simulierte Rolle handelt unter einem Mandat, und dessen Hash steht in
    der Zeichnung. Vorher galt das nur in der Argumentverarbeitung von
    ``ontologie.entscheide`` und im P9-Schema; wer eine Entscheidung direkt
    konstruierte oder eine A-Box von Hand schrieb, konnte jede
    Schluesselklasse behaupten.
    """
    if not isinstance(zeichnung, dict):
        return ["zeichnung muss eine Tabelle sein" + AUSWEG]
    schluessel = set(zeichnung)
    altform = {"rolle", "ordnung_sha256"}
    ordnung = zeichnung.get("ordnung_sha256")
    ordnung_ok = isinstance(ordnung, str) and bool(_SHA256.match(ordnung))
    if schluessel == altform:
        if form == "neu":
            return [
                "zeichnung muss die Schluesselklasse tragen — {rolle, "
                "ordnung_sha256, schluesselklasse[, mandat_sha256]} (ADR-018)" + AUSWEG
            ]
        # Altform des Vier-Rollen-Modells: die Rolle traegt noch die alte
        # Schreibweise (z. B. "plv-aktuar"), der Ordnungs-Hash ist ein Hash.
        rolle = zeichnung.get("rolle")
        if not (isinstance(rolle, str) and rolle.strip() and ordnung_ok):
            return [
                "zeichnung (Altform) muss {rolle, ordnung_sha256} mit einer "
                "nichtleeren Rolle und einem SHA-256 der Ordnung sein" + AUSWEG
            ]
        return []
    if form == "alt":
        return ["zeichnung muss {rolle, ordnung_sha256} mit Strings sein" + AUSWEG]
    pflicht = {"rolle", "ordnung_sha256", "schluesselklasse"}
    fehler: List[str] = []
    mandat = zeichnung.get("mandat_sha256")
    if not (
        pflicht <= schluessel <= pflicht | {"mandat_sha256"}
        and all(isinstance(zeichnung.get(k), str) and zeichnung[k] for k in pflicht)
        and gueltige_rollenkennung(zeichnung.get("rolle"))
        and ordnung_ok
        and zeichnung.get("schluesselklasse") in ZEICHNENDE_KLASSEN
        and (mandat is None or (isinstance(mandat, str) and _SHA256.match(mandat)))
    ):
        fehler.append(
            "zeichnung muss {rolle (Rollenkennung ebene/name), ordnung_sha256 "
            "(SHA-256), schluesselklasse in (mensch, simulation)[, mandat_sha256 "
            "(SHA-256)]} sein" + AUSWEG
        )
    if zeichnung.get("schluesselklasse") == "simulation" and not (
        isinstance(mandat, str) and _SHA256.match(mandat)
    ):
        fehler.append(
            "zeichnung mit schluesselklasse simulation braucht "
            "mandat_sha256 (ADR-018: eine simulierte Rolle handelt "
            "unter einem Mandat)" + AUSWEG
        )
    return fehler


def gueltige_rollenkennung(rolle: object) -> bool:
    return isinstance(rolle, str) and ROLLEN_MUSTER.match(rolle) is not None

#: Alle zeichenbaren Gates. Massgeblich fuer die gates-Listen der
#: Ordnung: Ein Gate, das man zeichnen, aber keiner Rolle geben kann,
#: waere eine Ordnung mit Loch (so geschehen mit A-O1, gefunden beim
#: Aufsetzen der Vier-Rollen-Regie fuer Fall-Lauf 2).
#:
#: ``A-B1.auslieferung`` (Entscheid des Maintainers 2026-09-16): die
#: Abnahme der AUSLIEFERUNG eines Stands-Pakets — der Moment, in dem ein
#: Stand nach aussen sichtbar wird. Sie gehoert einer FACHLICHEN Rolle
#: (``mensch/betrieb``, Kundenservice-Verantwortung fuer die
#: Bestandsfuehrung), nicht der IT: Was ausgeliefert wird, verantwortet
#: der Betrieb, nicht der, der die Maschine betreibt.
#:
#: Sie ist die erste Abnahme der LINIE statt eines Falls (ADR-018,
#: Nachtrag 2026-09-16): Der Bestand wird taeglich gefuehrt, unabhaengig
#: davon, ob gerade eine Migration laeuft. Wo ihr Snapshot liegt, ist
#: damit eine offene Frage — heute im Fall, weil das Entscheid-Kommando
#: keinen anderen Ort kennt.
#:
#: ``A-K2.kernaenderung`` (Entscheid des Maintainers 2026-09-16): die
#: menschliche Abnahme einer Aenderung an Code oder Dokumentation des
#: RECHENKERNS. Bis dahin war das folgenreichste, was am Zielsystem
#: geschieht, nur durch Commit-Disziplin geregelt (Abnahme-Protokoll in
#: ``kern/__init__``) — keine Zeichnung, kein Schluessel, kein Snapshot.
#: Sie gehoert ``mensch/rechenkern``; deren Agent legt vor.
#:
#: Ausloeser ist die AENDERUNG am Kern, gleich aus welchem Anlass. Eine
#: neue Tarifgeneration loest sie NICHT aus: Sie ist Parametrierung
#: (ADR-006, TG2012 -> TG2015 lief ohne eine einzige Formelaenderung) und
#: wird von ``P-K1`` deterministisch und von ``A-M4`` menschlich
#: abgenommen. Nur wenn sie ausnahmsweise einen neuen Rechenweg erzwingt,
#: ist sie eine Kern-Aenderung — und der Beleg zeigt dann genau das.
#:
#: Sie traegt ``regression`` als PFLICHTbeleg und ist damit ohne den
#: Regressionsproduzenten bewusst nicht zeichenbar. Das ist Absicht: Der
#: geaenderte Kern bewertet nach der Migration den laufenden Bestand
#: weiter, und diese Wirkung sieht sonst niemand.
GUELTIGE_GATES = ("A-Q1", "A-M1", "A-M2", "A-M3", "A-M4", "A-O1", "A-K2", "A-B1")

#: Zeichenbare Gates OHNE Belegvertrag — die begruendete Ausnahme.
#:
#: ``A-Q1`` (Quellenabnahme) stuetzt sich nicht auf Dateirollen im Fall,
#: sondern auf den A-Box-Stand, den der Entscheid selbst pinnt: A-M4
#: verlangt spaeter einen geltenden, signierten A-Q1-Snapshot AUF DIESEM
#: Stand. Die Bindung existiert also, sie laeuft nur nicht ueber
#: ``models.belegrollen.BELEGROLLEN``.
#:
#: Hier stehen NUR begruendete Ausnahmen. Eine Liste, die Ausnahmen und
#: Versehen mischt, verliert ihre Aussage.
GATES_OHNE_BELEGVERTRAG: tuple[str, ...] = ("A-Q1",)

#: Gates, deren Snapshot ``fall_scope`` und ``pflichtbelege`` traegt —
#: ABGELEITET, nicht abgetippt.
#:
#: Das ist die Reparatur einer Klasse, die zweimal zugeschlagen hat. Beim
#: ersten Mal war es die Liste der Gates selbst ("eine vierte Liste
#: derselben Gates war genau der Grund, warum A-M2 zwar entschieden, aber
#: nicht gespeichert werden konnte"). Beim zweiten Mal, mit A-B1, eine
#: Ebene tiefer: die Liste der Gates MIT Pflichtbelegen, gefuehrt als
#: Literal an sechs Stellen. A-B1 stand in keiner — mit der Folge, dass
#: das Entscheid-Kommando den Ankersatz zwar ausrechnete, ihn aber nicht
#: in den signierten Inhalt schrieb. Die Unterschrift bezeugte danach
#: alles ausser dem, was sie bezeugen sollte: WELCHES Paket ausgeliefert
#: wurde.
#:
#: Ein Kommentar, der eine Invariante beschreibt, erzwingt sie nicht.
#: Deshalb steht sie jetzt hier, und eine Ratsche haelt sie gegen
#: ``models.belegrollen.BELEGROLLEN`` (tests/test_gate_vokabel_ab1.py).
GATES_MIT_PFLICHTBELEGEN: tuple[str, ...] = tuple(
    gate for gate in GUELTIGE_GATES if gate not in GATES_OHNE_BELEGVERTRAG
)


def _unter(pfad: Path, wurzel: Path) -> bool:
    try:
        pfad.relative_to(wurzel)
        return True
    except ValueError:
        return False


def ausserhalb_von(
    pfad: Path, bereich: Path, *, muss_existieren: bool = True
) -> bool:
    """Ob ein Pfad lexikalisch UND aufgeloest ausserhalb eines Bereichs liegt.

    Die eine Regel fuer jeden Bezug, der Vertrauen stiften soll: **Was der
    schreibende Prozess selbst umschreiben kann, belegt nichts.** Sie gilt
    fuer alles, was eine Zeichnung autorisiert — Ordnung, Freigabe-
    schluessel, Mandat (ADR-018) — und fuer den Anker eines Stands-Pakets,
    der genau deshalb ausserhalb von Ablage und Paket liegen muss
    (models/anker).

    Zwei Pruefungen, weil eine von beiden umgangen werden kann: lexikalisch
    (``../ordnung.json`` von innen ist aussen) und aufgeloest (ein Symlink
    nach aussen fuehrt nicht hinaus, wenn er drinnen liegt).

    ``muss_existieren`` trennt zwei Faelle, die frueher verschwommen:
    Ein Beleg, den es nicht gibt, autorisiert nichts und gilt deshalb NICHT
    als aussen. Ein VERZEICHNIS dagegen, in das erst geschrieben werden
    soll, existiert bei der Pruefung regelmaessig noch nicht — dort wird
    der vorhandene Anfang des Pfades aufgeloest und der Rest normalisiert.
    """
    absolut = Path(os.path.normpath(pfad if pfad.is_absolute() else Path.cwd() / pfad))
    bereich_resolved = bereich.resolve()
    try:
        resolved = absolut.resolve(strict=True)
    except OSError:
        if muss_existieren:
            return False
        resolved = absolut.resolve()
    return not (
        _unter(absolut.absolute(), bereich_resolved) or _unter(resolved, bereich_resolved)
    )


def ausserhalb_des_falls(pfad: Path, fall: Path) -> bool:
    """Ob ein Belegpfad ausserhalb des Falls liegt (:func:`ausserhalb_von`).

    Eigener Name, weil die Aussage eine andere ist als die Mechanik: Was
    der Fall selbst umschreiben kann, autorisiert nichts. Vorher stand
    dieselbe Mechanik zweimal im Code — hier und in
    :func:`lade_zeichnungsordnung` — und keine der beiden Fassungen deckte
    den Anker ab (Befund T26-08).
    """
    return ausserhalb_von(pfad, fall)


def lade_zeichnungsordnung(
    raw: object, fall: Path
) -> Tuple[Optional[dict], Optional[str], List[str]]:
    """Zeichnungsordnung laden: welche ROLLE darf welches GATE zeichnen.

    Rueckgabe ``(ordnung, sha256, fehler)``; ohne Angabe (None) gilt das
    bisherige Verhalten des jeweiligen Konsumenten. Die Regie eines
    Falls entscheidet, ob sie die Ordnung verlangt.
    """
    if raw is None:
        return None, None, []
    if not isinstance(raw, str):
        return None, None, ["--zeichnungsordnung muss ein Pfad sein"]
    angegeben = Path(raw)
    absolut = Path(os.path.normpath(
        angegeben if angegeben.is_absolute() else Path.cwd() / angegeben))
    try:
        resolved = absolut.resolve(strict=True)
    except OSError as exc:
        return None, None, [f"Zeichnungsordnung nicht lesbar ({raw!r}): {exc}"]
    # Dieselbe Regel wie fuer Schluessel, Mandat und Anker — eine
    # Implementierung, nicht vier (Befund T26-08).
    if not ausserhalb_von(angegeben, fall):
        return None, None, [
            f"Zeichnungsordnung {raw!r} liegt innerhalb des Falls; die "
            "Rollenbindung muss extern verwahrt werden"
        ]
    try:
        # Einmal lesen: ordnung_sha256 in jedem Snapshot ist der Hash GENAU
        # der Bytes, aus denen die Rollenbindung hier geparst wird (Review
        # T23-01) — nicht der einer zweiten Lesung.
        roh = resolved.read_bytes()
        daten = json.loads(roh.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, None, [f"Zeichnungsordnung nicht als JSON lesbar: {exc}"]
    fehler: List[str] = []
    if not isinstance(daten, dict):
        return None, None, ["Zeichnungsordnung: kein JSON-Objekt"]
    if daten.get("schema_version") == 1:
        return None, None, [
            "Zeichnungsordnung nach Schema 1 wird nicht mehr gelesen "
            "(ADR-018): Rollen heissen jetzt mensch/<funktion> oder "
            "agent/<name> und tragen eine schluesselklasse (mensch, "
            "simulation, agent); schema_version 2"
        ]
    if daten.get("schema_version") != ORDNUNG_SCHEMA_VERSION:
        fehler.append(f"Zeichnungsordnung: schema_version {ORDNUNG_SCHEMA_VERSION} erwartet")
        return None, None, fehler
    rollen = daten.get("rollen")
    if not isinstance(rollen, dict) or not rollen:
        return None, None, ["Zeichnungsordnung: 'rollen' fehlt oder leer"]
    gesehen: Dict[str, str] = {}
    for name, eintrag in rollen.items():
        if not isinstance(eintrag, dict):
            fehler.append(f"Zeichnungsordnung: Rolle {name!r} ist kein Objekt")
            continue
        if not gueltige_rollenkennung(name):
            fehler.append(
                f"Zeichnungsordnung: Rolle {name!r} traegt keine Ebene — "
                "erwartet mensch/<funktion> oder agent/<name> (ADR-018)"
            )
            continue
        klasse = eintrag.get("schluesselklasse")
        if klasse not in SCHLUESSELKLASSEN:
            fehler.append(
                f"Zeichnungsordnung: Rolle {name!r} ohne gueltige "
                f"schluesselklasse (erlaubt: {list(SCHLUESSELKLASSEN)})"
            )
            continue
        ebene = name.split("/", 1)[0]
        if ebene == "agent" and klasse != "agent":
            fehler.append(
                f"Zeichnungsordnung: Agentenrolle {name!r} muss die "
                "Schluesselklasse 'agent' tragen"
            )
            continue
        if ebene == "mensch" and klasse == "agent":
            fehler.append(
                f"Zeichnungsordnung: menschliche Rolle {name!r} kann nicht "
                "die Schluesselklasse 'agent' tragen — Agenten zeichnen nicht"
            )
            continue
        if klasse == "agent" and eintrag.get("gates"):
            fehler.append(
                f"Zeichnungsordnung: Agentenrolle {name!r} mit gates "
                f"{eintrag.get('gates')} — Agentenrollen legen vor und "
                "zeichnen nie (ADR-018); die Liste muss leer sein"
            )
            continue
        fp = eintrag.get("schluessel_sha256")
        if not (isinstance(fp, str) and len(fp) == 64
                and all(c in "0123456789abcdef" for c in fp)):
            fehler.append(
                f"Zeichnungsordnung: Rolle {name!r} ohne gueltigen "
                "schluessel_sha256 (64 Hexzeichen)"
            )
            continue
        if fp in gesehen:
            fehler.append(
                f"Zeichnungsordnung: Rollen {gesehen[fp]!r} und {name!r} "
                "teilen denselben Schluessel -- die Trennung der Operatoren "
                "waere nur behauptet"
            )
        gesehen[fp] = name
        gates = eintrag.get("gates")
        if not isinstance(gates, list) or not all(
            isinstance(g, str) and (g == "*" or g in GUELTIGE_GATES)
            for g in gates
        ):
            fehler.append(
                f"Zeichnungsordnung: Rolle {name!r} mit ungueltiger "
                f"gates-Liste (erlaubt: {list(GUELTIGE_GATES)} oder '*')"
            )
    if fehler:
        return None, None, fehler
    sha = hashlib.sha256(roh).hexdigest()
    return daten, sha, []


def zeichnungsrolle(
    ordnung: dict, schluessel_sha256: str
) -> Optional[str]:
    """Die Rolle, der dieser Fingerabdruck gehoert (None = keiner)."""
    for name, eintrag in ordnung["rollen"].items():
        if eintrag.get("schluessel_sha256") == schluessel_sha256:
            return name
    return None


def rolle_darf_gate(ordnung: dict, rolle: str, gate: str) -> bool:
    """Ob die Rolle das Gate zeichnen darf ('*' = alle). Agentenrollen
    haben nie Gates (die Ordnung erzwingt die leere Liste)."""
    gates = ordnung["rollen"].get(rolle, {}).get("gates", [])
    return "*" in gates or gate in gates


def schluesselklasse(ordnung: dict, rolle: str) -> Optional[str]:
    """Die Schluesselklasse einer Rolle der Ordnung (None = unbekannte Rolle)."""
    eintrag = ordnung["rollen"].get(rolle)
    return eintrag.get("schluesselklasse") if isinstance(eintrag, dict) else None


def zeichnung_fuer(
    ordnung: dict, ordnung_sha256: str, schluessel_sha256: str,
    mandat_sha256: Optional[str] = None,
) -> Optional[Dict[str, str]]:
    """Der Zeichnungs-Eintrag eines Belegs: Rolle (aus dem Schluessel
    bestimmt), Ordnungs-Hash, Schluesselklasse, optional das Mandat.

    None, wenn der Schluessel keiner Rolle gehoert. Ein Mandat ist das
    Dokument, unter dem eine simulierte Rolle handelte; sein Hash gehoert
    in den Beleg, damit die Besetzung nachlesbar bleibt (ADR-018).
    """
    rolle = zeichnungsrolle(ordnung, schluessel_sha256)
    if rolle is None:
        return None
    eintrag = {
        "rolle": rolle,
        "ordnung_sha256": ordnung_sha256,
        "schluesselklasse": str(schluesselklasse(ordnung, rolle)),
    }
    if mandat_sha256:
        eintrag["mandat_sha256"] = mandat_sha256
    return eintrag
