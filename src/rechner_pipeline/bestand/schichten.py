"""Die Korrekturschicht als Vertragsattribut der Fuehrung (Freischaltung, Schritt 5).

``schichten.parquet`` traegt je uebernommenem Vertrag die persistierten
Parameter der Schicht (Grundsatzdokumentation 9.11), ``verankerung.parquet``
ihren Verankerungszeitpunkt. Hier werden beide zu dem, was Ereignis-Engine,
Bewertung und Ledger-Herleitung brauchen: ``Schichtparameter`` des Kerns
plus ``monate_ta`` und der Verankerungszustand je Police. Die Form der
Tabelle prueft ``models.bestand.validate_schichten`` ohne den Kern; die
Konstruktion lebt hier, weil sie den Kern braucht.

Knoten: klv
"""

from __future__ import annotations

import json
from typing import Any, Dict, Mapping, Tuple

from rechner_pipeline.kern.korrekturschicht import Schichtparameter
from rechner_pipeline.models.bestand import validate_schichten


def schichtparameter_aus_zeile(zeile: Mapping[str, Any]) -> Schichtparameter:
    """Eine Zeile von ``schichten.parquet`` als ``Schichtparameter``."""
    return Schichtparameter(
        schichttyp=str(zeile["schichttyp"]),
        verankerungszustand=str(zeile["verankerungszustand"]),
        verweildauer=int(zeile["verweildauer"]),
        rho=float(zeile["rho"]),
        formfunktion=str(zeile["formfunktion"]),
        formparameter=dict(json.loads(zeile["formparameter"])),
        vererbend=tuple(tuple(p) for p in json.loads(zeile["vererbend"])),
        kohorte=str(zeile["kohorte"]),
        in_ueberschuss=bool(zeile["in_ueberschuss"]),
        in_zzr=bool(zeile["in_zzr"]),
        rumpfmonate=int(zeile["rumpfmonate"]),
    )


def schichten_je_police(
    stamm: Any, schichten: Any, verankerung: Any
) -> Dict[int, Tuple[Schichtparameter, int, str]]:
    """police_id -> (Schichtparameter, monate_ta, zustand_ta) fuer die Fuehrung.

    Faellt hart, wenn die Tabellen nicht zusammenpassen — derselbe
    Befund wie in ``validate_schichten``, nur als Ausnahme fuer
    Engines, die keine Fehlerliste zurueckgeben.
    """
    if schichten is None or len(schichten) == 0:
        return {}
    befunde = validate_schichten(stamm, schichten, verankerung)
    if befunde:
        raise ValueError("; ".join(befunde))
    anker = verankerung.set_index("police_id")
    aus: Dict[int, Tuple[Schichtparameter, int, str]] = {}
    for zeile in schichten.to_dict("records"):
        pid = int(zeile["police_id"])
        aus[pid] = (
            schichtparameter_aus_zeile(zeile),
            int(anker.loc[pid, "monate_ta"]),
            str(anker.loc[pid, "zustand_ta"]),
        )
    return aus
