"""Knoten-Identitaeten der Ontologie.

Jeder Fachknoten traegt eine stabile, global eindeutige ID — nie
Python-Objektidentitaet, nie Listenposition (D1-Auflage der
Architektur-Fragerunde). Die IDs sind der Join-Schluessel fuer
Provenance, Diskrepanzen, Testfaelle, den Code-Index und einen
etwaigen spaeteren Graph-Export; deshalb sind sie hier zentral
definiert und validiert statt ad hoc gebaut.

Form: Pfadsegmente mit ``/``, z. B. ``klv/tg2015`` (Tarifgeneration)
oder ``klv/tg2015/zelle:einzel,nichtraucher`` (Parametrierungszelle).
Segmente sind klein geschrieben; Zellen-IDs sortieren ihre
Auspraegungen nach Dimensions-ID, damit dieselbe Zelle immer dieselbe
ID traegt.
"""

from __future__ import annotations

import re
from typing import Dict

#: Ein Segment: Kleinbuchstaben, Ziffern, ``_``; Zellen-Segmente
#: zusaetzlich ``:`` und ``,`` (z. B. ``zelle:einzel,nichtraucher``).
_SEGMENT = re.compile(r"^[a-z0-9_]+(:[a-z0-9_]+(,[a-z0-9_]+)*)?$")

ZELLE_OHNE_DIMENSION = "zelle:-"


class KnotenIdFehler(ValueError):
    """Ungueltige Knoten-ID — fail-fast statt stiller Schreibfehler."""


def pruefe_segment(segment: str) -> str:
    if segment == ZELLE_OHNE_DIMENSION:
        return segment
    if not _SEGMENT.match(segment):
        raise KnotenIdFehler(
            f"ungueltiges ID-Segment: {segment!r} — erlaubt sind "
            "Kleinbuchstaben, Ziffern und '_' (Zellen: 'zelle:a,b')"
        )
    return segment


def knoten_id(*segmente: str) -> str:
    """Knoten-ID aus Segmenten bauen (validiert)."""
    if not segmente:
        raise KnotenIdFehler("Knoten-ID ohne Segmente")
    return "/".join(pruefe_segment(s) for s in segmente)


def zellen_segment(auspraegungen: Dict[str, str]) -> str:
    """Zellen-Segment aus Merkmals-Auspraegungen — deterministisch.

    Sortiert nach Dimensions-ID, damit ``{tarifart: einzel,
    status: nichtraucher}`` und die umgekehrte Reihenfolge dieselbe
    Zelle benennen. Ohne Dimensionen (TG2012) traegt die eine Zelle
    das feste Segment ``zelle:-``.
    """
    if not auspraegungen:
        return ZELLE_OHNE_DIMENSION
    werte = [auspraegungen[dim] for dim in sorted(auspraegungen)]
    return pruefe_segment("zelle:" + ",".join(werte))
