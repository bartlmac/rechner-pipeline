"""Aktuarieller Test: Wertvergleich je Vertrag am eigenen Verankerungszeitpunkt.

Umsetzung von ADR-010 (Trennung aktuarieller Test / Migrationscontrolling;
normative Referenz Fachkonzept "Konstruktive Neuberechnung und
Korrekturschicht" v0.2, Kap. 5.1 und 6.1-6.3). Drei Invarianten gelten im
Code, nicht nur in der Doku:

* **Der Vergleichszeitpunkt ist ein Vertragsattribut** (``monate_ta``),
  kein Suite-Parameter. Jeder Vertrag wird an SEINEM Verankerungszeitpunkt
  gemessen.
* **Keine Interpolation.** Verglichen wird am Rechenpunkt: ``monate_ta``
  muss ein voller Jahrestag des Vertrags sein (Vielfaches von 12); die
  Engine rechnet ausschliesslich ueber Jahres-Verlaufszeilen bzw. deren
  bit-identische Monats-Randlage. Ein unterjaehriges ``monate_ta`` ist ein
  harter Konstruktionsfehler des Aufrufs, kein Befund.
* **Keine Summation der Vergleichsgroessen.** Die Engine bildet keine
  Deckungskapital-Summe. Sie kennt ausschliesslich Verteilungsgroessen des
  Residuums (Maximum, hohe Perzentile, Betragssumme der Abweichungen je
  Gruppe), geclustert nach Historientyp.

Das Residuum ``system - erwartet`` ist der Wertvergleich, den wir heute
haben: Solange es keine Korrekturschicht gibt (FK Kap. 3-5, bewusst nicht
Bestandteil von ADR-010), traegt der Test diesen Vergleich — am richtigen
Zeitpunkt und ohne Summen. Der Platz fuer das methodische Residuum R
bleibt benannt und leer.

Vollstaendigkeit heisst hier: die **Stichprobe** (``qa.stichprobe``) wurde
vollstaendig abgearbeitet. Die Nichtpruefung der Nicht-Stichprobe ist kein
Befund, sondern die Definition. Mitgelieferte Pruefsummen sind
Transportsicherung: Sie werden getrennt ausgewiesen
(``transportsicherung``) und fliessen nie in das fachliche Urteil ein.

Toleranzen kommen aus ``qa.abzugsabgleich`` (eine Quelle, nie aufgeweicht).

Knoten: klv
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

from rechner_pipeline.kern import ModelPoint
from rechner_pipeline.kern.rechenkern import (
    Rechenkern,
    erhoehungs_scheibe,
    vertrags_monatsreserve,
)
from rechner_pipeline.qa.abzugsabgleich import ABS_TOL, REL_TOL
from rechner_pipeline.qa.migrationssuite import DATEN_AUSNAHMEN
from rechner_pipeline.qa.stichprobe import Stichprobe

#: Groessen, die die Engine rechnen kann. Ein unbekannter Erwartungs-Key
#: ist ein harter Fehler — stiller Verzicht waere ein falscher Nachweis.
GEPRUEFTE_GROESSEN = ("kVx_MRV", "RKW", "BJB", "VS_bfr")

#: Hohe Perzentile der |Residuum|-Verteilung (FK 6.2: Toleranzen auf
#: Maximum und hohen Perzentilen, nie auf Mittelwert oder Median).
PERZENTILE = (95, 99)


class AktuartestFehler(ValueError):
    """Testauftrag verletzt den Engine-Vertrag — fail-fast."""


@dataclass(frozen=True)
class VerankerungsPruefung:
    """Pruefauftrag eines Vertrags an seinem Verankerungszeitpunkt.

    ``monate_ta`` sind die vollen Vertragsmonate am Verankerungszeitpunkt
    t_a (FK 5.1: der letzte exakte Rechenpunkt) — ein Vielfaches von 12.
    ``historientyp`` clustert die Verteilungsauswertung (z. B. nach der
    Uebergangsklasse der Historie); die Engine schreibt ihm keine
    Semantik vor. ``erwartet`` traegt die gelieferten Vergleichswerte mit
    Kern-Groessennamen als Schluesseln.
    """

    police_id: str
    model_point: Dict[str, Any]
    monate_ta: int
    historientyp: str
    erwartet: Dict[str, float]
    scheiben: Tuple[Tuple[int, float], ...] = field(default_factory=tuple)
    beitragsfrei_seit_jahr: Optional[int] = None


def _pruefe_auftrag(v: VerankerungsPruefung) -> None:
    """Engine-Vertrag des Auftrags — Verletzungen sind harte Fehler."""
    if v.monate_ta < 0 or v.monate_ta % 12 != 0:
        raise AktuartestFehler(
            f"police {v.police_id}: monate_ta={v.monate_ta} ist kein "
            "Rechenpunkt — t_a ist der letzte exakte Rechenpunkt des "
            "Vertrags (volle Jahre, FK 5.1); unterjaehrige Mischwerte "
            "sind im aktuariellen Test unzulaessig (ADR-010)"
        )
    if not v.erwartet:
        raise AktuartestFehler(
            f"police {v.police_id}: keine Erwartungswerte — ein Vertrag "
            "ohne Vergleichsgroessen ist kein Testauftrag"
        )
    unbekannt = sorted(set(v.erwartet) - set(GEPRUEFTE_GROESSEN))
    if unbekannt:
        raise AktuartestFehler(
            f"police {v.police_id}: unbekannte Groessen {unbekannt} "
            f"(gerechnet werden: {list(GEPRUEFTE_GROESSEN)})"
        )
    if v.scheiben and set(v.erwartet) - {"kVx_MRV", "RKW"}:
        raise AktuartestFehler(
            f"police {v.police_id}: mit Erhoehungsscheiben rechnet die "
            "Engine nur kVx_MRV und RKW vertragsweit — andere Groessen "
            "sind nicht definiert statt still falsch"
        )
    if v.beitragsfrei_seit_jahr is not None and "RKW" in v.erwartet:
        raise AktuartestFehler(
            f"police {v.police_id}: RKW im beitragsfreien Zustand ist in "
            "v0 nicht definiert — Groesse weglassen oder Engine erweitern"
        )


def _system_werte(v: VerankerungsPruefung) -> Dict[str, float]:
    """Die angeforderten Groessen am Rechenpunkt — ohne Interpolation."""
    grund_mp = ModelPoint(**v.model_point)
    kern = Rechenkern(grund_mp)
    jahr = v.monate_ta // 12
    if v.monate_ta > 12 * grund_mp.n:
        raise AktuartestFehler(
            f"police {v.police_id}: monate_ta={v.monate_ta} liegt hinter "
            f"dem Vertragsende (n={grund_mp.n} Jahre)"
        )
    werte: Dict[str, float] = {}
    if v.scheiben:
        kerne = [
            (jahr_s, Rechenkern(erhoehungs_scheibe(grund_mp, jahr_s, vs)))
            for jahr_s, vs in v.scheiben
        ]
        m = vertrags_monatsreserve(kern, kerne, v.monate_ta)
        if "kVx_MRV" in v.erwartet:
            werte["kVx_MRV"] = m.vx_mrv
        if "RKW" in v.erwartet:
            werte["RKW"] = m.rkw
        return werte
    if v.beitragsfrei_seit_jahr is not None:
        a0 = v.beitragsfrei_seit_jahr
        if "kVx_MRV" in v.erwartet:
            werte["kVx_MRV"] = kern.reserve_beitragsfrei(a0, jahr)
        if "VS_bfr" in v.erwartet:
            werte["VS_bfr"] = kern.beitragsfreie_summe(a0)
        if "BJB" in v.erwartet:
            werte["BJB"] = 0.0
        return werte
    zeile = kern.zustand_am(v.monate_ta)
    if "kVx_MRV" in v.erwartet:
        werte["kVx_MRV"] = zeile.vx_mrv
    if "RKW" in v.erwartet:
        werte["RKW"] = zeile.rkw
    if "VS_bfr" in v.erwartet:
        werte["VS_bfr"] = zeile.vs_bfr
    if "BJB" in v.erwartet:
        werte["BJB"] = (
            0.0 if jahr >= grund_mp.t else kern.gross_annual_premium()
        )
    return werte


def _ok(ist: float, soll: float) -> bool:
    return math.isclose(ist, soll, rel_tol=REL_TOL, abs_tol=ABS_TOL)


def pruefe_verankerung(v: VerankerungsPruefung) -> Dict[str, Any]:
    """Einen Vertrag an seinem t_a pruefen (deterministisch).

    Auftrags-Verletzungen (falscher Rechenpunkt, unbekannte Groessen)
    sind harte Fehler; kranke LIEFERDATEN (kaputter Modellpunkt,
    unzulaessige Scheibe) werden je Vertrag isoliert und als Befund
    ausgewiesen — das entscheidet ``pruefe_stichprobe``.
    """
    _pruefe_auftrag(v)
    werte = _system_werte(v)
    pruefungen: List[Dict[str, Any]] = []
    befunde: List[str] = []
    for groesse in sorted(v.erwartet):
        system = float(werte[groesse])
        erwartet = float(v.erwartet[groesse])
        residuum = system - erwartet
        ok = _ok(system, erwartet)
        pruefungen.append(
            {
                "groesse": groesse,
                "system": system,
                "erwartet": erwartet,
                "residuum": residuum,
                "ok": ok,
            }
        )
        if not ok:
            befunde.append(
                f"{groesse}: system {system!r} vs. erwartet {erwartet!r} "
                f"(residuum {residuum!r})"
            )
    return {
        "police_id": v.police_id,
        "historientyp": v.historientyp,
        "monate_ta": v.monate_ta,
        "bestanden": not befunde,
        "pruefungen": pruefungen,
        "befunde": befunde,
    }


def _perzentil(sortierte_betraege: List[float], p: int) -> float:
    """Empirisches Perzentil (deterministisch, ohne Interpolation)."""
    idx = max(0, math.ceil(p / 100.0 * len(sortierte_betraege)) - 1)
    return sortierte_betraege[idx]


def _verteilung(residuen: List[float]) -> Dict[str, Any]:
    """Verteilungsgroessen der |Residuen| — die EINZIGEN Aggregate.

    Keine Summe der Vergleichswerte, kein Mittelwert, kein Median
    (ADR-010 / FK 6.2). Die Betragssumme der ABWEICHUNGEN ist eine
    Groesse der Residuum-Verteilung, keine Bestandssumme.
    """
    betraege = sorted(abs(r) for r in residuen)
    if not betraege:
        return {"anzahl_werte": 0}
    verteilung: Dict[str, Any] = {
        "anzahl_werte": len(betraege),
        "max_abs_residuum": betraege[-1],
        "summe_abs_residuum": math.fsum(betraege),
    }
    for p in PERZENTILE:
        verteilung[f"p{p}_abs_residuum"] = _perzentil(betraege, p)
    return verteilung


def pruefe_stichprobe(
    vertraege: List[VerankerungsPruefung],
    stichprobe: Stichprobe,
    *,
    transportsicherung: Optional[Mapping[str, Any]] = None,
    system: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Den aktuariellen Test ueber eine belegte Stichprobe fahren.

    ``vertraege`` muessen die Stichprobe exakt abdecken: Jeder gezogene
    Vertrag wird geprueft, kein anderer. Fehlende oder ueberzaehlige
    Auftraege sind Mengenbefunde und schlagen den Test fehl — die
    Nichtpruefung der Nicht-Stichprobe dagegen ist per Definition kein
    Befund. ``transportsicherung`` (z. B. Datei-Hashes oder gelieferte
    Kontrollsummen) wird unveraendert und GETRENNT ausgewiesen; sie ist
    nie Teil des fachlichen Urteils.
    """
    if not vertraege:
        raise AktuartestFehler(
            "leere Auftragsliste — ein Test ohne Vertraege ist kein "
            "bestandener Test, sondern ein Aufruffehler"
        )
    ids = [v.police_id for v in vertraege]
    if len(ids) != len(set(ids)):
        doppelt = sorted({i for i in ids if ids.count(i) > 1})
        raise AktuartestFehler(
            f"doppelte Pruefauftraege fuer {doppelt[:5]} — die Verteilung "
            "des Residuums waere verzerrt"
        )

    gezogen = set(stichprobe.police_ids)
    geliefert = set(ids)
    mengenbefunde: List[str] = []
    fehlend = sorted(gezogen - geliefert)
    if fehlend:
        mengenbefunde.append(
            f"stichprobe nicht abgearbeitet: {len(fehlend)} Vertraege "
            f"ohne Pruefauftrag (z. B. {fehlend[:5]})"
        )
    ueberzaehlig = sorted(geliefert - gezogen)
    if ueberzaehlig:
        mengenbefunde.append(
            f"{len(ueberzaehlig)} Pruefauftraege ausserhalb der "
            f"Stichprobe (z. B. {ueberzaehlig[:5]}) — der Beleg deckt "
            "sie nicht"
        )
    stichprobe_vollstaendig = not mengenbefunde

    ergebnisse: List[Dict[str, Any]] = []
    for v in vertraege:
        try:
            ergebnisse.append(pruefe_verankerung(v))
        except DATEN_AUSNAHMEN as exc:
            ergebnisse.append(
                {
                    "police_id": v.police_id,
                    "historientyp": v.historientyp,
                    "monate_ta": v.monate_ta,
                    "bestanden": False,
                    "pruefungen": [],
                    "befunde": [
                        "daten: Vertrag nicht rechenbar "
                        f"({type(exc).__name__}: {exc})"
                    ],
                }
            )

    gruppen: Dict[str, Dict[str, Any]] = {}
    for typ in sorted({e["historientyp"] for e in ergebnisse}):
        im_typ = [e for e in ergebnisse if e["historientyp"] == typ]
        residuen = [
            p["residuum"] for e in im_typ for p in e["pruefungen"]
        ]
        gruppen[typ] = {
            "anzahl": len(im_typ),
            "bestanden": sum(1 for e in im_typ if e["bestanden"]),
            **_verteilung(residuen),
        }

    alle_residuen = [
        p["residuum"] for e in ergebnisse for p in e["pruefungen"]
    ]
    fehlgeschlagen = sum(1 for e in ergebnisse if not e["bestanden"])
    ergebnis: Dict[str, Any] = {
        "stichprobe": stichprobe.als_beleg(),
        "anzahl": len(ergebnisse),
        "bestanden": len(ergebnisse) - fehlgeschlagen,
        "fehlgeschlagen": fehlgeschlagen,
        "mengenbefunde": mengenbefunde,
        "stichprobe_vollstaendig": stichprobe_vollstaendig,
        "verteilung": _verteilung(alle_residuen),
        "gruppen": gruppen,
        "vertraege": ergebnisse,
        "test_bestanden": stichprobe_vollstaendig and fehlgeschlagen == 0,
    }
    if transportsicherung is not None:
        ergebnis["transportsicherung"] = dict(transportsicherung)
    if system is not None:
        ergebnis["system"] = dict(system)
    return ergebnis
