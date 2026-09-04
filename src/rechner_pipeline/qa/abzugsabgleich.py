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

DIE HARTE REGEL (Maintainer, 18.08.): Wird die MELDUNGS-Lesart verworfen,
ist der Fehler in der Tarifmeldung — aufsichtsrechtlich relevant, ein
Meldungsfehler wird IMMER von einem Menschen bestaetigt und berichtet.
Automatisch aufloesbar ist ausschliesslich der Fall "Rechner-Lesart
verworfen, Meldungs-Lesart belegt".

DIE BELEGLAGE ZAEHLT, NICHT DER EINZELFALL: Ein Urteil ueber hunderte
Vertraege darf nicht an einem einzigen Wert kippen — weder zugunsten
noch zulasten der Automatik. Jede Lesart weist deshalb aus, welcher
ANTEIL der Belege sie stuetzt (``quote_stuetzend``), und die Automatik
verlangt zusaetzlich zur bestandenen Lesart eine BREIT verworfene
Gegenlesart (:data:`VERWERFUNGS_QUOTE`) auf hinreichend vielen Belegen
(:data:`MIND_BELEGE`). Beides kann ein Urteil nur zum Menschen
verschieben, nie zur Maschine.

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

#: Relative Toleranz des Wertvergleichs.
#: Die Cent-Rundung der gelieferten Abzugswerte ist ein ABSOLUTER
#: Fehler (hoechstens 0,005 EUR) — dafuer ist ``ABS_TOL`` zustaendig,
#: nicht die relative Toleranz. ``REL_TOL`` traegt allein den Anteil,
#: der mit dem Betrag waechst (Reihenfolge der Gleitkomma-Operationen,
#: unterjaehrige Interpolation). Gemessen am vollstaendigen
#: Referenzabgleich eines gelieferten Bestands liegt das groesste
#: relative Residuum bei rund 1e-6, das groesste absolute unter
#: ``ABS_TOL``; 1e-6 laesst dem groessten Vertrag dieses Bestands
#: (rund 200 TEUR Deckungskapital) noch gut 20 Cent Spielraum.
#: Der frueher hier stehende Wert 5e-4 war rund drei Groessenordnungen
#: lockerer als die Datenqualitaet: er verdeckte Parametrierungsfehler,
#: deren Wirkung auf das Deckungskapital klein ist — etwa ein um ein
#: Jahr versetztes Eintrittsalter bei kurzer Beitragszahlungsdauer.
#: Eine Toleranz wird NIE aufgeweicht, um gruen zu werden; verschaerft
#: werden darf sie, wenn die Beleglage es traegt.
REL_TOL = 1e-6
#: Absolute Untergrenze (EUR) gegen Ausloeschung bei Kleinstwerten;
#: deckt zugleich die Cent-Rundung der Lieferung mit Faktor 2.
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


#: Mindestzahl gepruefter Belegwerte fuer eine AUTOMATISCHE Aufloesung.
#: Ein einzelner Beleg ist kein Bestandsbeweis; unter dieser Grenze
#: bleibt die Aufloesung beim Menschen.
MIND_BELEGE = 3
#: Mindestanteil VERLETZTER Belegwerte, ab dem eine Lesart als
#: verworfen gilt. Ohne diese Schranke genuegte EIN Ausreisser unter
#: hunderten Belegen, um eine Lesart maschinell zu verwerfen und die
#: andere automatisch zu setzen — eine Beleglage, die kein Mensch als
#: Beweis akzeptieren wuerde. Der Schwellwert weicht nichts auf: er
#: verschiebt duenne Beleglagen zum Menschen.
VERWERFUNGS_QUOTE = 0.5


def pruefe_lesart(
    feld: str,
    lesart: Lesart,
    vertraege: List[VertragsBeleg],
) -> Dict[str, Any]:
    """Eine Lesart gegen alle Belege rechnen (deterministisch).

    Neben dem Ja/Nein (``passt``) wird die BELEGLAGE ausgewiesen:
    ``quote_stuetzend``/``quote_verletzt`` sagen, wie breit die Belege
    die Lesart tragen, ``verletzende_belege`` nennt die Ausreisser.
    ``schlechtester_beleg`` ist der Beleg mit der groessten relativen
    Abweichung UNTER DEN VERLETZENDEN — er ist gesetzt, sobald es eine
    Verletzung gibt (frueher konnte ein nicht verletzender Vergleich
    die Schranke hochziehen und den Ausreisser verdecken).
    """
    max_rel = 0.0
    geprueft = 0
    verletzende: List[Tuple[float, str]] = []
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
                verletzende.append((rel, f"{v.police_id}/{name}"))
            max_rel = max(max_rel, rel)
    verletzende.sort(key=lambda e: (-e[0], e[1]))
    verletzt = len(verletzende)
    return {
        "wert": lesart.wert,
        "quelle_art": lesart.quelle_art,
        "geprueft": geprueft,
        "verletzt": verletzt,
        "passt": verletzt == 0 and geprueft > 0,
        "quote_stuetzend": (geprueft - verletzt) / geprueft if geprueft else 0.0,
        "quote_verletzt": verletzt / geprueft if geprueft else 0.0,
        "max_relative_abweichung": max_rel,
        "max_relative_abweichung_verletzt": (
            verletzende[0][0] if verletzende else 0.0),
        "schlechtester_beleg": verletzende[0][1] if verletzende else None,
        "verletzende_belege": [name for _, name in verletzende[:5]],
    }


def _beleglage(urteil: Dict[str, Any]) -> str:
    """Ein Satz ueber die Beleglage einer Lesart (fuer die Begruendung).

    Macht den Unterschied sichtbar, den ein Alles-oder-nichts-Urteil
    verschluckt: ob eine Lesart an EINEM Ausreisser gescheitert ist oder
    an der ganzen Lieferung.
    """
    text = (
        f"Lesart {urteil['wert']!r} ({urteil['quelle_art']}) von "
        f"{urteil['geprueft'] - urteil['verletzt']} von "
        f"{urteil['geprueft']} Werten gestuetzt "
        f"({urteil['quote_stuetzend']:.1%})"
    )
    if urteil["verletzende_belege"]:
        text += f", Ausreisser z. B. {', '.join(urteil['verletzende_belege'])}"
    return text


def gleiche_ab(
    feld: str,
    lesarten: List[Lesart],
    vertraege: List[VertragsBeleg],
) -> Dict[str, Any]:
    """Beide Lesarten pruefen und das Urteil mit Begruendung liefern.

    ``automatisch_aufloesbar`` ist NUR wahr, wenn ALLE vier Bedingungen
    zusammenkommen:

    1. genau EINE Lesart passt (kein einziger Beleg verletzt sie);
    2. die verworfene Lesart ist die RECHNER-Lesart — ein verworfener
       Meldungs-Wert ist aufsichtsrechtlich relevant und geht IMMER an
       den Menschen (harte Regel, s. Modulkopf);
    3. die Beleglage traegt: mindestens :data:`MIND_BELEGE` gepruefte
       Werte;
    4. die verworfene Lesart ist BREIT verworfen — mindestens
       :data:`VERWERFUNGS_QUOTE` der Belege verletzen sie.

    Bedingung 3 und 4 sind die Antwort auf die Asymmetrie eines
    Alles-oder-nichts-Urteils: ohne sie genuegte EIN Ausreisser unter
    hunderten Belegen, um eine Lesart maschinell zu verwerfen. Sie
    weichen nichts auf — sie koennen ein Urteil nur vom Automaten zum
    Menschen verschieben, nie umgekehrt.

    Das Ergebnis fuehrt in jedem Fall die Beleglage BEIDER Lesarten
    (``urteile`` mit ``quote_stuetzend``/``verletzende_belege``), damit
    der Mensch bei einer Verweigerung sieht, ob eine Lesart an einem
    einzigen Ausreisser gescheitert ist oder an der ganzen Lieferung.
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
            "Beleg, Diskrepanz bleibt beim Menschen. Beleglage: "
            + "; ".join(_beleglage(u) for u in urteile)
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
            "IMMER menschlich bestaetigt und berichtet (Regel Maintainer "
            "2026-08-18). Beleg liegt bei, Aufloesung bleibt beim Menschen."
        )
        return ergebnis
    if gewinner["geprueft"] < MIND_BELEGE:
        ergebnis["menschlich_erforderlich"] = True
        ergebnis["begruendung"] = (
            f"Beleglage zu duenn: {gewinner['geprueft']} gepruefte Werte, "
            f"mindestens {MIND_BELEGE} noetig. Genau eine Lesart passt "
            f"({gewinner['wert']!r}, {gewinner['quelle_art']}), aber ein "
            "Bestandsbeweis ist das nicht — Aufloesung beim Menschen. "
            + "Beleglage: " + "; ".join(_beleglage(u) for u in urteile)
        )
        return ergebnis
    if verlierer["quote_verletzt"] < VERWERFUNGS_QUOTE:
        ergebnis["menschlich_erforderlich"] = True
        ergebnis["begruendung"] = (
            f"Lesart {verlierer['wert']!r} ({verlierer['quelle_art']}) ist "
            f"nur in {verlierer['verletzt']} von {verlierer['geprueft']} "
            f"Werten verletzt ({verlierer['quote_verletzt']:.1%}, Schwelle "
            f"{VERWERFUNGS_QUOTE:.0%}) — das sind Ausreisser, keine "
            "Verwerfung der Lesart. Die Diskrepanz und die Ausreisser "
            f"({', '.join(verlierer['verletzende_belege'])}) gehen an den "
            "Menschen. Beleglage: "
            + "; ".join(_beleglage(u) for u in urteile)
        )
        return ergebnis
    ergebnis["automatisch_aufloesbar"] = True
    ergebnis["begruendung"] = (
        f"Beleg ueber {len(vertraege)} Vertraege ({gewinner['geprueft']} "
        f"Werte): Lesart {gewinner['wert']!r} ({gewinner['quelle_art']}) "
        f"von ALLEN Belegen gestuetzt, max. rel. Abweichung "
        f"{gewinner['max_relative_abweichung']:.2e}; "
        f"Lesart {verlierer['wert']!r} ({verlierer['quelle_art']}) in "
        f"{verlierer['verletzt']} von {verlierer['geprueft']} Werten "
        f"verworfen ({verlierer['quote_verletzt']:.1%}, max. rel. "
        f"Abweichung {verlierer['max_relative_abweichung']:.2e}, z. B. "
        f"{verlierer['schlechtester_beleg']}). Der Fehler liegt im "
        "Rechner — deterministisch belegt, automatisch aufloesbar."
    )
    return ergebnis
