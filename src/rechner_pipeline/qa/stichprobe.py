"""Stichprobenprofile des aktuariellen Tests (ADR-010, Grundsatzdokumentation 9.15).

Der aktuarielle Test misst am Verankerungszeitpunkt gegen die Methode und
laeuft dafuer auf einer STICHPROBE, nicht auf dem ganzen Bestand. Die
Stichprobe ist damit selbst Teil des Beleges: Wer nur einen Teil prueft,
muss zeigen, welchen Teil und warum — sonst hat das Ergebnis keine
Aussagekraft ueber den Rest.

Ein Profil ist deshalb benannt, parametriert und deterministisch: Derselbe
Bestand und dieselben Parameter ergeben dieselbe Stichprobe, und
:meth:`Stichprobe.als_beleg` beschreibt sie vollstaendig genug, um sie
anderswo nachzuziehen.

Zwei Profile, beide aus einem konkreten Bedarf entstanden:

``vollbestand``
    Die Stichprobe ist der ganze Bestand. Fuer Bestaende in der
    Groessenordnung des Showcase-Falls ist das die fachlich richtige Wahl
    und zugleich der Randfall der Parametrisierung.

``geschichtet``
    Je Historientyp-Cluster eine feste Anzahl (Grundsatzdokumentation 9.12,
    Lieferobjekt 2). Notwendig, sobald der Bestand seltene Historientypen
    enthaelt: Eine ungeschichtete Ziehung kann sie vollstaendig verfehlen,
    und der Test bestuende, ohne den Vorgang je gerechnet zu haben. Die
    Ziehreihenfolge folgt einem Hash mit dokumentiertem Startwert, die
    Abdeckung je Cluster steht im Beleg.

Weitere Profile werden hier NICHT auf Vorrat erfunden. Die
Erweiterungsstelle ist :data:`PROFILE` — eine neue Funktion mit derselben
Signatur eintragen, mehr braucht es nicht.

Knoten: klv
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Mapping, Sequence, Tuple


class StichprobenFehler(ValueError):
    """Profil unbekannt oder Parameter unzulaessig — fail-fast."""


@dataclass(frozen=True)
class Stichprobe:
    """Die gezogene Menge samt ihrer vollstaendigen Beschreibung."""

    profil: str
    parameter: Mapping[str, Any]
    police_ids: Tuple[str, ...]
    grundgesamtheit: int

    def __post_init__(self) -> None:
        if len(set(self.police_ids)) != len(self.police_ids):
            raise StichprobenFehler(
                "Stichprobe enthaelt eine Police mehrfach — die Verteilung "
                "des Residuums waere verzerrt"
            )
        if self.grundgesamtheit < len(self.police_ids):
            raise StichprobenFehler(
                f"Stichprobe ({len(self.police_ids)}) ist groesser als die "
                f"Grundgesamtheit ({self.grundgesamtheit})"
            )

    @property
    def umfang(self) -> int:
        return len(self.police_ids)

    @property
    def ist_vollerhebung(self) -> bool:
        return self.umfang == self.grundgesamtheit

    def als_beleg(self) -> Dict[str, Any]:
        """Beschreibung fuer Bericht und Gate-Ledger.

        Die Police-Liste gehoert dazu: Ohne sie liesse sich spaeter nicht
        nachvollziehen, WELCHE Vertraege den aktuariellen Test getragen
        haben.
        """
        return {
            "profil": self.profil,
            "parameter": dict(sorted(self.parameter.items())),
            "umfang": self.umfang,
            "grundgesamtheit": self.grundgesamtheit,
            "vollerhebung": self.ist_vollerhebung,
            "police_ids": list(self.police_ids),
        }


def _vollbestand(police_ids: Sequence[str], **parameter: Any) -> Stichprobe:
    """Alle Vertraege — der Randfall, mit dem v0 startet."""
    if parameter:
        raise StichprobenFehler(
            f"Profil 'vollbestand' kennt keine Parameter, erhalten: "
            f"{sorted(parameter)}"
        )
    ids = tuple(police_ids)
    return Stichprobe(
        profil="vollbestand",
        parameter={},
        police_ids=ids,
        grundgesamtheit=len(ids),
    )


def _schluessel(police_id: str, saat: str) -> str:
    """Stabile Ziehreihenfolge — kein Zufallszustand, kein Startwert-Raten.

    Der Startwert geht in den Hash ein und steht im Beleg. Damit laesst
    sich dieselbe Stichprobe anderswo nachziehen, und ein Wechsel des
    Startwerts ist sichtbar statt still.
    """
    return hashlib.sha256(f"{saat}:{police_id}".encode()).hexdigest()


def _geschichtet(
    police_ids: Sequence[str],
    *,
    schichten: Mapping[str, str],
    je_schicht: int,
    saat: str = "",
) -> Stichprobe:
    """Je Historientyp-Cluster eine feste Anzahl ziehen.

    Der aktuarielle Test wertet das Residuum nach Historientyp getrennt
    aus (Grundsatzdokumentation 9.12, Lieferobjekt 2). Eine ungeschichtete
    Ziehung traefe die seltenen Typen womoeglich gar nicht — ein Bestand
    mit 35 Herabsetzungen unter 500 Vertraegen kann eine Zufallsstichprobe
    von 50 vollstaendig verfehlen, und der Test wuerde bestehen, ohne den
    Vorgang je gerechnet zu haben.

    Ist ein Cluster kleiner als ``je_schicht``, wird er vollstaendig
    gezogen. Das ist kein Fehler, aber es steht im Beleg: Die Abdeckung
    je Cluster wird ausgewiesen, damit der Leser sieht, worauf die Aussage
    fuer diesen Typ beruht.
    """
    if je_schicht < 1:
        raise StichprobenFehler(
            f"je_schicht={je_schicht} — eine leere Schicht ist kein "
            "bestandener Test"
        )
    fehlend = [pid for pid in police_ids if pid not in schichten]
    if fehlend:
        raise StichprobenFehler(
            f"{len(fehlend)} Policen ohne Historientyp (z. B. "
            f"{fehlend[0]!r}) — nach welchem Cluster ausgewertet wird, "
            "muss fuer jeden Vertrag feststehen"
        )

    nach_schicht: Dict[str, list] = {}
    for pid in police_ids:
        nach_schicht.setdefault(schichten[pid], []).append(pid)

    gezogen: list = []
    abdeckung: Dict[str, Any] = {}
    for name in sorted(nach_schicht):
        kandidaten = sorted(nach_schicht[name], key=lambda p: _schluessel(p, saat))
        wahl = kandidaten[:je_schicht]
        gezogen.extend(wahl)
        abdeckung[name] = {"gezogen": len(wahl), "vorhanden": len(kandidaten)}

    return Stichprobe(
        profil="geschichtet",
        parameter={
            "je_schicht": je_schicht,
            "saat": saat,
            "abdeckung": abdeckung,
        },
        police_ids=tuple(gezogen),
        grundgesamtheit=len(police_ids),
    )


#: Erweiterungsstelle: Profilname -> Ziehfunktion.
PROFILE: Dict[str, Callable[..., Stichprobe]] = {
    "vollbestand": _vollbestand,
    "geschichtet": _geschichtet,
}


def ziehe(
    profil: str,
    police_ids: Iterable[str],
    **parameter: Any,
) -> Stichprobe:
    """Stichprobe nach benanntem Profil ziehen.

    Ein unbekanntes Profil ist ein harter Fehler und kein stiller Rueckfall
    auf den Vollbestand: Eine unbeabsichtigte Vollerhebung waere teuer, eine
    unbeabsichtigt kleine Stichprobe waere ein falscher Nachweis.
    """
    if profil not in PROFILE:
        raise StichprobenFehler(
            f"Unbekanntes Stichprobenprofil {profil!r}; verfuegbar: "
            f"{sorted(PROFILE)}"
        )
    ids = list(police_ids)
    if not ids:
        raise StichprobenFehler(
            "Grundgesamtheit ist leer — eine leere Stichprobe ist kein "
            "bestandener Test"
        )
    if len(set(ids)) != len(ids):
        raise StichprobenFehler(
            "Grundgesamtheit enthaelt doppelte Police-IDs; die Stichprobe "
            "waere nicht reproduzierbar"
        )
    return PROFILE[profil](ids, **parameter)
