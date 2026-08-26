"""Stichprobenprofile des aktuariellen Tests (ADR-010, FK 6.1).

Der aktuarielle Test misst am Verankerungszeitpunkt gegen die Methode und
laeuft dafuer auf einer STICHPROBE, nicht auf dem ganzen Bestand. Die
Stichprobe ist damit selbst Teil des Beleges: Wer nur einen Teil prueft,
muss zeigen, welchen Teil und warum — sonst hat das Ergebnis keine
Aussagekraft ueber den Rest.

Ein Profil ist deshalb benannt, parametriert und deterministisch: Derselbe
Bestand und dieselben Parameter ergeben dieselbe Stichprobe, und
:meth:`Stichprobe.als_beleg` beschreibt sie vollstaendig genug, um sie
anderswo nachzuziehen.

Umfang v0 — bewusst genau ein Profil:

``vollbestand``
    Die Stichprobe ist der ganze Bestand. Fuer Bestaende in der
    Groessenordnung des Showcase-Falls ist das die fachlich richtige Wahl
    und zugleich der Randfall der Parametrisierung.

Weitere Profile sind eine offene Teilaufgabe und werden hier NICHT auf
Vorrat erfunden: Schichtung nach Historientyp-Cluster (FK 5.4
Lieferobjekt 2), Mindestabdeckung je Cluster, Zufallsziehung mit
dokumentiertem Startwert. Die Erweiterungsstelle ist :data:`PROFILE` —
eine neue Funktion mit derselben Signatur eintragen, mehr braucht es
nicht.

Knoten: klv
"""

from __future__ import annotations

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


#: Erweiterungsstelle: Profilname -> Ziehfunktion.
PROFILE: Dict[str, Callable[..., Stichprobe]] = {
    "vollbestand": _vollbestand,
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
