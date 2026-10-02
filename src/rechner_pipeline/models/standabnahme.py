"""Die Abnahme des Zielsystems — EINE Regel, vier Gegenstaende, ein Ort ausserhalb des Falls.

Entscheid des Maintainers 2026-10-01 (ADR-018, Nachtrag 2026-10-01): Der
Stand, auf dem ein Migrationsfall rechnet, ist abgenommen. Zweiter Entscheid
desselben Tages (ADR-025): "Entweder gibt es eine Initialzeichnung an allen
relevanten Zustaenden oder gar nicht" — auf den Vorschlag "eine Erstabnahme
des Zielsystems, ausserhalb jedes Falls; ein Fall zeichnet danach nur, was
sich durch ihn aendert, und verweist sonst auf die Erstabnahme": "ja, alle".

Vier Gegenstaende, je mit ihrer verantwortlichen Rolle (:data:`GEGENSTAENDE`):

* ``kernstand`` — Code, Referenzwerte, Grundsatzdokumentation des
  Rechenkerns (A-K2, ``mensch/rechenkern``);
* ``tboxstand`` — die T-Box (A-O1, ``mensch/architektur``);
* ``tarifwerkstand`` — Tarifplaene und Parametrierung der eigenen
  Tarifgenerationen der PLV (A-T1, ``mensch/aktuariat``);
* ``anfangsbestand`` — der Bestand, den der Betrieb nach dem Aufsetzen einer
  Ablage fuehrt (A-B3, ``mensch/betrieb``).

**Erstabnahme.** Jede Rolle zeichnet einmal ihren Gegenstand im
LINIENBEREICH (:data:`LINIE_MARKER`; ein Arbeitsbereich der Linie, der sich
wie ein Fall verhaelt, aber keinen Eingang einer Migration hat), spaetere
Aenderungen in der Entwicklung ebenfalls dort — eine Kette je Gegenstand
(Vorgaenger, geltende Spitze), ueber dasselbe Entscheid-Kommando.

**Ein Fall zeichnet nur, was sich DURCH IHN aendert.** Die drei
Gegenstaende des Codes verlangt A-M4 (``verlangt_von == "A-M4"``); die Regel
ist erfuellt auf genau einem von zwei Wegen:

(a) ``abnahme_im_fall`` — ein geltender, angenommener Snapshot des Gates
    im Fall fuer genau diesen Stand (Rollenregel, Belegvertrag,
    Stand-Bindung). Hat der Fall eine Kette des Gates, gilt (a) und nur (a):
    Eine Ablehnung im Fall laesst sich nicht durch einen Verweis umgehen.
(b) ``keine_aenderung`` — der Stand ist identisch zu dem, den ein FRUEHER
    angenommener Snapshot (die Erstabnahme der Linie oder ein frueherer
    Fall) abgenommen hat. Belegt durch den Verweis an festem Ort im Fall,
    der eine vollstaendige Kopie dieses Snapshots traegt; Signatur, Rolle und
    Klasse prueft die Rollenregel, sein Feld ``stand`` wird per ``==`` gegen
    den lebenden Stand gehalten. Durchgewunken heisst belegt unveraendert,
    nicht ungeprueft.

Den Anfangsbestand verlangt der BETRIEB (``verlangt_von == "betrieb"``): Er
gehoert keinem Fall, sondern einer Ablage; die Bindung liegt in der Ablage
(``models.anfangsbestand``), gezeichnet wird er im Linienbereich.

Weg (c) ``basislinie`` (T-Box ohne Uebergang) ist mit der Erstabnahme
entfallen: Er ersetzte die erste Abnahme der T-Box, und die gibt es jetzt.
Lesbar bleibt er fuer Snapshots nach Schema 8 (:data:`WEGE_LESBAR`) — ein
alter A-M4-Snapshot, der ihn fuehrt, bleibt ein gueltiges Glied seiner Kette.

Lesen tun das Gate (``gates.gate_entscheid``), die Produzenten der Belege
(``gates.stand_belegen``, ``gates.kernstand_belegen``,
``gates.tarifwerk_belegen``, ``betrieb.anfangsbestand``) und die
Darstellung (``werkzeuge/``) — deshalb wohnt der Vertrag hier.

Knoten: system/entscheid
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple


@dataclass(frozen=True)
class Gegenstand:
    """Ein Gegenstand der Abnahme des Zielsystems — mit allem, was ihn
    bedienbar macht (Werkzeug, Sicht, Gate, Rolle, vorlegender Agent)."""

    rolle: str             # Pflichtrolle (A-M4) bzw. Name des Gegenstands
    gate: str              # das Gate, das den Stand abnimmt
    titel: str             # Unternehmenssprache
    verantwortung: str     # die zeichnende Rolle (mensch/<funktion>)
    verlangt_von: str      # "A-M4" oder "betrieb"
    verweis_relativ: str   # fester Ort des Verweises (Weg b), "" = keiner
    werkzeug: str          # der Produzent des Belegs (python -m ...)
    sicht_relativ: str     # die lesbare Sicht fuer den Pruefer
    agent: str             # die vorlegende Agentenrolle (.claude/agents)
    im_fall: bool          # in einem Fall zeichenbar (Weg a)?


#: Die Gegenstaende — abschliessend. Ratschen halten sie gegen
#: ``models.belegrollen.BELEGROLLEN`` (A-M4 und Linie), ``P9_GATES_MIT_STAND``
#: und die Agentendefinitionen (``tests/test_erstabnahme_linie.py``).
GEGENSTAENDE: Tuple[Gegenstand, ...] = (
    Gegenstand("kernstand", "A-K2", "Kernstand", "mensch/rechenkern", "A-M4",
               "abgeleitet/kern/verweis.json", "rechner_pipeline.gates.kernstand_belegen",
               "abgeleitet/kern/aenderung.md", "agent/rechenkern", True),
    Gegenstand("tboxstand", "A-O1", "T-Box-Stand", "mensch/architektur", "A-M4",
               "abgeleitet/tbox/verweis.json", "rechner_pipeline.gates.stand_belegen tbox",
               "abgeleitet/tbox/aenderung.md", "agent/architektur", True),
    Gegenstand("tarifwerkstand", "A-T1", "Tarifwerk", "mensch/aktuariat", "A-M4",
               "abgeleitet/tarifwerk/verweis.json", "rechner_pipeline.gates.tarifwerk_belegen",
               "abgeleitet/tarifwerk/aenderung.md", "agent/aktuariat", True),
    Gegenstand("anfangsbestand", "A-B3", "Anfangsbestand", "mensch/betrieb", "betrieb",
               "", "rechner_pipeline.betrieb.anfangsbestand belegen",
               "abgeleitet/anfangsbestand/beleg.md", "agent/betrieb", False),
)

#: Die Gegenstaende, die A-M4 verlangt (Pflichtrollen in beiden Scopes).
AM4_GEGENSTAENDE: Tuple[Gegenstand, ...] = tuple(
    g for g in GEGENSTAENDE if g.verlangt_von == "A-M4")

#: Die Wege. (c) ist entfallen und nur fuer Schema-8-Snapshots lesbar.
ABNAHME_IM_FALL = "abnahme_im_fall"
KEINE_AENDERUNG = "keine_aenderung"
BASISLINIE = "basislinie"
WEGE = (ABNAHME_IM_FALL, KEINE_AENDERUNG)
WEGE_LESBAR = WEGE + (BASISLINIE,)

#: Schema und Art des Verweis-Belegs (Weg b).
VERWEIS_SCHEMA_VERSION = 1
VERWEIS_ART = "standverweis"
VERWEIS_FELDER = frozenset({"schema_version", "art", "gate", "herkunft", "snapshot"})

# --------------------------------------------------------------------------- #
# Der Linienbereich — der Ort der Abnahmen ausserhalb eines Falls (ADR-025)
# --------------------------------------------------------------------------- #

#: Die Kennzeichnung eines Linienbereichs (statt ``eingang.json`` eines Falls).
LINIE_MARKER = "linie.json"
LINIE_SCHEMA_VERSION = 1
LINIE_ART = "linienbereich"
#: Der Scope eines Snapshots im Linienbereich (``fall_scope``, ab P9-Schema 9).
LINIE_SCOPE = "linie"
#: Der vorgeschlagene Ort im Repo (gitignored, wie ``faelle/``).
LINIE_STANDARDORT = "linie"
#: Die Gates, die im Linienbereich zeichenbar sind — genau die vier.
LINIEN_GATES: Tuple[str, ...] = tuple(g.gate for g in GEGENSTAENDE)
#: Die Gates, die NUR im Linienbereich zeichenbar sind.
NUR_LINIE: Tuple[str, ...] = tuple(g.gate for g in GEGENSTAENDE if not g.im_fall)


def gegenstand_fuer(gate: str) -> Optional[Gegenstand]:
    for g in GEGENSTAENDE:
        if g.gate == gate:
            return g
    return None


def ist_linie(snapshot: dict) -> bool:
    return isinstance(snapshot, dict) and snapshot.get("fall_scope") == LINIE_SCOPE


def herkunft(snapshot: dict) -> str:
    """Woher der fruehere Snapshot kommt — ABGELEITET aus seinen signierten
    Feldern (Bereich, Name, Gate, Hash), nicht angegeben."""
    bereich = "Linie" if ist_linie(snapshot) else "Fall"
    return (f"{bereich} {snapshot.get('fall')}, entscheide/"
            f"{snapshot.get('gate')}-{snapshot.get('snapshot_sha256')}.json")


def anzeige_im_fall(gate: str, snapshot_sha256: str) -> str:
    return f"abgenommen im Fall ({gate}-Snapshot {snapshot_sha256[:16]})"


def anzeige_keine_aenderung(snapshot_sha256: str, herkunft_text: str) -> str:
    """Woertlich nach dem Entscheid: "keine Aenderung seit Abnahme
    <snapshot> (<Herkunft>)"."""
    return f"keine Aenderung seit Abnahme {snapshot_sha256[:16]} ({herkunft_text})"


def bereich_art(pfad: Path) -> Optional[str]:
    """``"fall"`` (``eingang.json``), ``"linie"`` (:data:`LINIE_MARKER`) oder
    None — die Arbeitsbereiche, in denen ein Beleg der Abnahme liegen darf."""
    pfad = Path(pfad)
    if (pfad / "eingang.json").is_file():
        return "fall"
    if (pfad / LINIE_MARKER).is_file():
        return "linie"
    return None


def linie_kennung(name: str) -> dict:
    """Der Inhalt von :data:`LINIE_MARKER` — Name, Schema, Art und der Satz,
    was der Bereich ist. Kein Zeitstempel: dieselbe Linie, dieselben Bytes."""
    return {
        "schema_version": LINIE_SCHEMA_VERSION,
        "art": LINIE_ART,
        "name": name,
        "zweck": ("Abnahmen des Zielsystems ausserhalb eines Falls (Erstabnahme und "
                  "spaetere Aenderungen in der Entwicklung): Kernstand A-K2, "
                  "T-Box-Stand A-O1, Tarifwerk A-T1, Anfangsbestand A-B3; dazu die "
                  "Versionslinie der Zeichnungsordnung (ADR-025). entscheide/ und "
                  "ordnung/ sind nur-anfuegbar und werden nie geloescht."),
    }
