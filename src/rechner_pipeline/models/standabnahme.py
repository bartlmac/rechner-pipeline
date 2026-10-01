"""Die Abnahme des Stands, auf dem ein Fall laeuft — EINE Regel, zwei Gegenstaende.

Entscheid des Maintainers 2026-10-01 (ADR-018, Nachtrag 2026-10-01): Der
Stand, auf dem ein Migrationsfall rechnet, ist abgenommen — fuer den
KERNSTAND (A-K2, ``mensch/rechenkern``) und den T-BOX-STAND (A-O1,
``mensch/architektur``) nach derselben Regel. A-M4 verlangt sie je
Gegenstand. Erfuellt ist sie auf genau einem von drei Wegen:

(a) ``abnahme_im_fall`` — ein geltender, angenommener Snapshot des Gates
    im Fall fuer genau diesen Stand (Rollenregel, Belegvertrag,
    Stand-Bindung);
(b) ``keine_aenderung`` — der Stand ist identisch zu dem, den ein FRUEHER
    angenommener Snapshot abgenommen hat. Belegt durch den Verweis an
    festem Ort im Fall (:data:`VERWEIS_RELATIV`), der eine vollstaendige
    Kopie dieses Snapshots traegt; Signatur, Rolle und Klasse prueft die
    Rollenregel, sein Feld ``stand`` wird per ``==`` gegen den lebenden
    Stand gehalten. Durchgewunken heisst belegt unveraendert, nicht
    ungeprueft.
(c) ``basislinie`` — NUR fuer die T-Box: Solange ihre Versionslinie
    (``ontologie.tbox.TBOX_VERSIONEN``) ein Element hat, gab es keinen
    Uebergang. Fuer den Kern gibt es keine Basislinie; seine erste Abnahme
    ist zu zeichnen.

Hat der Fall eine Kette des Gates, gilt (a) und nur (a): Eine Ablehnung im
Fall laesst sich nicht durch einen Verweis umgehen.

Lesen tun das Gate (``gates.gate_entscheid``), der Produzent des Verweises
(``gates.stand_belegen``) und die Darstellung (``werkzeuge/``) — deshalb
wohnt der Vertrag hier.

Knoten: system/entscheid
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class Gegenstand:
    """Ein Gegenstand der Standabnahme."""

    rolle: str             # Pflichtrolle von A-M4
    gate: str              # das Gate, das den Stand abnimmt
    titel: str             # Unternehmenssprache
    verweis_relativ: str   # fester Ort des Verweises (Weg b)
    basislinie: bool       # gibt es Weg (c)?


#: Die Gegenstaende — abschliessend. Eine Ratsche haelt sie gegen
#: ``models.belegrollen.BELEGROLLEN["A-M4"]``.
GEGENSTAENDE: Tuple[Gegenstand, ...] = (
    Gegenstand("kernstand", "A-K2", "Kernstand", "abgeleitet/kern/verweis.json", False),
    Gegenstand("tboxstand", "A-O1", "T-Box-Stand", "abgeleitet/tbox/verweis.json", True),
)

#: Die drei Wege.
ABNAHME_IM_FALL = "abnahme_im_fall"
KEINE_AENDERUNG = "keine_aenderung"
BASISLINIE = "basislinie"
WEGE = (ABNAHME_IM_FALL, KEINE_AENDERUNG, BASISLINIE)

#: Schema und Art des Verweis-Belegs (Weg b).
VERWEIS_SCHEMA_VERSION = 1
VERWEIS_ART = "standverweis"
VERWEIS_FELDER = frozenset({"schema_version", "art", "gate", "herkunft", "snapshot"})


def gegenstand_fuer(gate: str) -> Optional[Gegenstand]:
    for g in GEGENSTAENDE:
        if g.gate == gate:
            return g
    return None


def herkunft(snapshot: dict) -> str:
    """Woher der fruehere Snapshot kommt — ABGELEITET aus seinen signierten
    Feldern (Fallname, Gate, Hash), nicht angegeben."""
    return (f"Fall {snapshot.get('fall')}, entscheide/"
            f"{snapshot.get('gate')}-{snapshot.get('snapshot_sha256')}.json")


def anzeige_im_fall(gate: str, snapshot_sha256: str) -> str:
    return f"abgenommen im Fall ({gate}-Snapshot {snapshot_sha256[:16]})"


def anzeige_keine_aenderung(snapshot_sha256: str, herkunft_text: str) -> str:
    """Woertlich nach dem Entscheid: "keine Aenderung seit Abnahme
    <snapshot> (<Herkunft>)"."""
    return f"keine Aenderung seit Abnahme {snapshot_sha256[:16]} ({herkunft_text})"


def anzeige_basislinie(version: str) -> str:
    return (f"keine Aenderung: die Versionslinie der T-Box hat ein Element "
            f"({version}), es gab keinen Uebergang")
