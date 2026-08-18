"""Abzugsabgleich: Diskrepanz-Lesarten gegen den Bestandsabzug (Plan P6).

Die Beweisfuehrung, die eine Diskrepanz OHNE Menschen aufloesen darf —
und die Regel, wann sie es NICHT darf:

Fuer eine strittige Groesse (z. B. Rechnungszins 1,25 % Meldung gegen
1,75 % Rechner) rechnet der Zielkern die Vertraege des transformierten
Bestandsabzugs unter BEIDEN Lesarten und haelt die Ergebnisse gegen
die gelieferten Werte (Jahresbeitrag, Deckungskapital am Stichtag).
Passt GENAU EINE Lesart und wird die andere klar verworfen, ist das
ein deterministischer Beleg — keine LLM-Entscheidung, P2/P4 bleiben
intakt: Code entscheidet auf Evidenz, beide Residuen stehen im
Protokoll.

DIE HARTE REGEL (Bartek, 18.08.): Wird die MELDUNGS-Lesart verworfen,
ist der Fehler in der Tarifmeldung — aufsichtsrechtlich relevant, ein
Meldungsfehler wird IMMER von einem Menschen bestaetigt und berichtet.
Automatisch aufloesbar ist ausschliesslich der Fall "Rechner-Lesart
verworfen, Meldungs-Lesart belegt".

Dieses Modul ist eine reine Vergleichs-Engine auf primitiven
Strukturen (die Schichtenkarte laesst qa -> ontologie nicht zu): die
A-Box-Anbindung — Diskrepanzen einsammeln, Aufloesungen schreiben —
gehoert dem aufrufenden Gate (P7).

Knoten: klv
"""

from __future__ import annotations

import dataclasses
import math
from typing import Any, Dict, List, Optional, Tuple

#: Relative Toleranz des Wertvergleichs. Die Abzugswerte kommen aus dem
#: Excel-Rechner auf 2 Nachkommastellen gerundet — 5e-4 relativ traegt
#: diese Rundung auch bei kleinen Betraegen, trennt aber Lesarten, deren
#: Zins sich um 50 Basispunkte unterscheidet (Wirkung im Prozentbereich).
REL_TOL = 5e-4
#: Absolute Untergrenze (EUR) gegen Ausloeschung bei Kleinstwerten.
ABS_TOL = 0.02


@dataclasses.dataclass(frozen=True)
class Lesart:
    wert: Any
    quelle_art: str            # "tarifmeldung" | "tarifrechner" | "bestand"


@dataclasses.dataclass(frozen=True)
class VertragsBeleg:
    """Ein Vertrag des Abzugs, soweit der Abgleich ihn braucht."""

    police_id: str
    model_point: Dict[str, Any]      # kompletter kwargs-Satz fuer den Kern
    vertragsjahr: int                # k: Bewertungsjahr des Deckungskapitals
    erwartet: Dict[str, float]       # z. B. {"BJB": ..., "kVx_MRV": ...}


def _nah(ist: float, soll: float) -> bool:
    return math.isclose(ist, soll, rel_tol=REL_TOL, abs_tol=ABS_TOL)


def _rechne(model_point: Dict[str, Any], vertragsjahr: int) -> Dict[str, float]:
    from rechner_pipeline.kern import berechne
    from rechner_pipeline.kern.produkte import hole

    mp = hole("klv").model_point_cls(**model_point)
    ergebnis = berechne(mp)
    werte: Dict[str, float] = dict(ergebnis["scalars"]["Kalkulation"])
    zeilen = ergebnis["tables"]["Kalkulation"]
    if 0 <= vertragsjahr < len(zeilen):
        werte.update({k: v for k, v in zeilen[vertragsjahr].items()})
    return werte


def pruefe_lesart(
    feld: str,
    lesart: Lesart,
    vertraege: List[VertragsBeleg],
) -> Dict[str, Any]:
    """Eine Lesart gegen alle Belege rechnen (deterministisch)."""
    max_rel = 0.0
    verletzt = 0
    geprueft = 0
    schlechtester: Optional[str] = None
    for v in vertraege:
        params = dict(v.model_point)
        params[feld] = lesart.wert
        werte = _rechne(params, v.vertragsjahr)
        for name, soll in v.erwartet.items():
            if name not in werte:
                raise KeyError(
                    f"Abzugswert {name!r} ist keine Kern-Groesse — "
                    "Transformations-Spec und Kern-Contract abgleichen"
                )
            geprueft += 1
            ist = float(werte[name])
            rel = abs(ist - soll) / max(abs(soll), 1.0)
            if not _nah(ist, soll):
                verletzt += 1
                if rel > max_rel:
                    schlechtester = f"{v.police_id}/{name}"
            max_rel = max(max_rel, rel)
    return {
        "wert": lesart.wert,
        "quelle_art": lesart.quelle_art,
        "geprueft": geprueft,
        "verletzt": verletzt,
        "passt": verletzt == 0 and geprueft > 0,
        "max_relative_abweichung": max_rel,
        "schlechtester_beleg": schlechtester,
    }


def gleiche_ab(
    feld: str,
    lesarten: List[Lesart],
    vertraege: List[VertragsBeleg],
) -> Dict[str, Any]:
    """Beide Lesarten pruefen und das Urteil mit Begruendung liefern.

    ``automatisch_aufloesbar`` ist NUR wahr, wenn genau eine Lesart
    passt, die verworfene die RECHNER-Lesart ist und Belege vorliegen.
    Ein verworfener Meldungs-Wert liefert stattdessen ein
    Mensch-Dossier (``menschlich_erforderlich``).
    """
    if len(lesarten) != 2:
        raise ValueError(
            f"Abgleich erwartet genau zwei Lesarten, bekam {len(lesarten)}"
        )
    urteile = [pruefe_lesart(feld, l, vertraege) for l in lesarten]
    passende = [u for u in urteile if u["passt"]]
    ergebnis: Dict[str, Any] = {
        "feld": feld,
        "urteile": urteile,
        "vertraege": len(vertraege),
        "automatisch_aufloesbar": False,
        "menschlich_erforderlich": False,
        "gewaehlter_wert": None,
        "begruendung": "",
    }
    if len(vertraege) == 0:
        ergebnis["begruendung"] = "keine Belege im Abzug — kein Urteil"
        return ergebnis
    if len(passende) != 1:
        ergebnis["begruendung"] = (
            f"{len(passende)} von 2 Lesarten passen — kein eindeutiger "
            "Beleg, Diskrepanz bleibt beim Menschen"
        )
        ergebnis["menschlich_erforderlich"] = True
        return ergebnis
    gewinner = passende[0]
    verlierer = next(u for u in urteile if u is not gewinner)
    ergebnis["gewaehlter_wert"] = gewinner["wert"]
    if verlierer["quelle_art"] == "tarifmeldung":
        ergebnis["menschlich_erforderlich"] = True
        ergebnis["begruendung"] = (
            "Der Bestandsabzug verwirft die MELDUNGS-Lesart "
            f"({verlierer['wert']!r}, max. rel. Abweichung "
            f"{verlierer['max_relative_abweichung']:.2e}) — Fehler in der "
            "Tarifmeldung sind aufsichtsrechtlich relevant und werden "
            "IMMER menschlich bestaetigt und berichtet (Regel Bartek "
            "2026-08-18). Beleg liegt bei, Aufloesung bleibt beim Menschen."
        )
        return ergebnis
    ergebnis["automatisch_aufloesbar"] = True
    ergebnis["begruendung"] = (
        f"Beleg ueber {len(vertraege)} Vertraege ({gewinner['geprueft']} "
        f"Werte): Lesart {gewinner['wert']!r} ({gewinner['quelle_art']}) "
        f"max. rel. Abweichung {gewinner['max_relative_abweichung']:.2e}; "
        f"Lesart {verlierer['wert']!r} ({verlierer['quelle_art']}) in "
        f"{verlierer['verletzt']} von {verlierer['geprueft']} Werten "
        f"verworfen (max. rel. Abweichung "
        f"{verlierer['max_relative_abweichung']:.2e}, z. B. "
        f"{verlierer['schlechtester_beleg']}). Der Fehler liegt im "
        "Rechner — deterministisch belegt, automatisch aufloesbar."
    )
    return ergebnis
