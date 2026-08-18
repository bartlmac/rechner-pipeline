"""Migrations-Testsuite: Zwei-Stichtags-Prüfung eines übernommenen Bestands.

Der Beweis einer Bestandsmigration endet nicht beim Stichtags-Foto: Das
Zielsystem muss den übernommenen Bestand auch FORTSCHREIBEN wie das
Quellsystem. Diese Suite prüft deshalb je Vertrag drei Dinge gegen
gelieferte Erwartungswerte (typisch: zweiter Bestandsabzug des
abgebenden Unternehmens plus GeVo-Protokoll des Zwischenzeitraums):

1. Deckungskapital am Migrationsstichtag — die Bilanzgröße, unterjährig
   interpoliert (:class:`rechner_pipeline.kern.Monatsreserve`);
2. die Beträge der Geschäftsvorfälle zwischen den Stichtagen
   (STO -> Rückkaufswert am Ereignismonat, TOD -> Versicherungssumme,
   PEX -> beitragsfreie Summe am Jahrestag);
3. Deckungskapital am Folgestichtag auf dem durch die GeVos bestimmten
   Track (aktiv, beitragsfrei, abgegangen; nach einer dynamischen
   Erhöhung vertragsweit über Grund- und Erhöhungsscheiben —
   :func:`rechner_pipeline.kern.vertrags_monatsreserve`, Scheiben nach
   der Tarifwerk-Regel :func:`rechner_pipeline.kern.erhoehungs_scheibe`).

Inkonsistenzen der Lieferung (GeVo außerhalb der Stichtage, Wert trotz
Abgang, Abgang ohne GeVo, GeVo auf dem falschen Track) sind BEFUNDE je
Vertrag, nie stille Lücken (P2).

Primitive Strukturen, kein Ontologie-Import — die Suite ist
fallunabhängig; die Fall-Bindung (welche Lieferung, welche Lesart der
Rechnungsgrundlagen) macht der Migrationsfall.

Knoten: klv
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from rechner_pipeline.kern import (
    ModelPoint,
    Rechenkern,
    erhoehungs_scheibe,
    vertrags_monatsreserve,
)
from rechner_pipeline.qa.abzugsabgleich import ABS_TOL, REL_TOL

GEVO_ARTEN = ("ERH", "STO", "TOD", "PEX")
#: GeVo-Arten, die den Vertrag beenden (kein Wert am Folgestichtag).
TERMINAL = ("STO", "TOD")


@dataclass(frozen=True)
class GeVoErwartung:
    """Ein Geschäftsvorfall zwischen den Stichtagen, wie geliefert.

    ``monate`` sind die vollen Vertragsmonate am Wirkungszeitpunkt;
    ``betrag_erwartet`` ist der gelieferte GeVo-Betrag (STO: gezahlter
    Rückkaufswert, TOD: Todesfallleistung, PEX: beitragsfreie Summe,
    ERH: Versicherungssumme der neuen Scheibe).
    """

    art: str
    monate: int
    betrag_erwartet: Optional[float] = None


@dataclass(frozen=True)
class VertragsPruefung:
    """Prüfauftrag für einen Vertrag: Modellpunkt-Lesart + Erwartungen.

    ``dk_erwartet_2`` ist ``None``, wenn der Vertrag laut Lieferung bis
    zum Folgestichtag abgegangen ist (STO/TOD).
    """

    police_id: str
    model_point: Dict[str, Any]
    monate_stichtag_1: int
    monate_stichtag_2: int
    dk_erwartet_1: float
    dk_erwartet_2: Optional[float]
    gevos: Tuple[GeVoErwartung, ...] = field(default_factory=tuple)


def _vergleich(groesse: str, system: float, erwartet: float) -> Dict[str, Any]:
    ok = math.isclose(system, erwartet, rel_tol=REL_TOL, abs_tol=ABS_TOL)
    return {
        "groesse": groesse,
        "system": system,
        "erwartet": erwartet,
        "residuum": system - erwartet,
        "ok": ok,
    }


def pruefe_vertrag(v: VertragsPruefung) -> Dict[str, Any]:
    """Zwei-Stichtags-Urteil für einen Vertrag.

    Rückgabe: ``bestanden`` (alle Vergleiche innerhalb der Toleranz und
    kein Befund), ``befunde`` (Texte zu Lieferungs-Inkonsistenzen),
    ``pruefungen`` (je Größe System-/Erwartungswert und Residuum).
    """
    if v.monate_stichtag_2 <= v.monate_stichtag_1:
        raise ValueError(
            f"{v.police_id}: Folgestichtag ({v.monate_stichtag_2}) liegt "
            f"nicht nach dem Migrationsstichtag ({v.monate_stichtag_1})"
        )
    grund_mp = ModelPoint(**v.model_point)
    kern = Rechenkern(grund_mp)
    befunde: List[str] = []
    pruefungen: List[Dict[str, Any]] = []

    pruefungen.append(_vergleich(
        "dk_stichtag_1", kern.monatsreserve(v.monate_stichtag_1).vx_mrv,
        v.dk_erwartet_1,
    ))

    terminal_monat: Optional[int] = None
    pex_jahr: Optional[int] = None
    scheiben: List[Tuple[int, Rechenkern]] = []
    for g in sorted(v.gevos, key=lambda g: g.monate):
        if g.art not in GEVO_ARTEN:
            befunde.append(f"unbekannte GeVo-Art {g.art!r}")
            continue
        if not v.monate_stichtag_1 < g.monate <= v.monate_stichtag_2:
            befunde.append(
                f"GeVo {g.art} bei Monat {g.monate} liegt nicht zwischen "
                f"den Stichtagen ({v.monate_stichtag_1}, "
                f"{v.monate_stichtag_2}]"
            )
            continue
        if terminal_monat is not None:
            befunde.append(
                f"GeVo {g.art} bei Monat {g.monate} nach terminalem GeVo "
                f"(Monat {terminal_monat}) — Lieferung inkonsistent"
            )
            continue
        if g.art == "ERH":
            if pex_jahr is not None:
                befunde.append(
                    f"ERH bei Monat {g.monate} nach Beitragsfreistellung — "
                    "Erhöhungen nur auf dem beitragspflichtigen Track"
                )
                continue
            if g.monate % 12:
                befunde.append(
                    f"ERH bei Monat {g.monate}: dynamische Erhöhung wirkt "
                    "am Vertragsjahrestag (Vielfaches von 12)"
                )
                continue
            if g.betrag_erwartet is None:
                befunde.append(
                    f"ERH bei Monat {g.monate} ohne Erhöhungssumme — "
                    "Lieferung unvollständig"
                )
                continue
            try:
                scheiben_mp = erhoehungs_scheibe(
                    grund_mp, g.monate // 12, g.betrag_erwartet)
            except ValueError as exc:
                befunde.append(f"ERH bei Monat {g.monate}: {exc}")
                continue
            scheiben.append((g.monate // 12, Rechenkern(scheiben_mp)))
        elif g.art == "STO":
            if pex_jahr is not None:
                befunde.append(
                    f"STO bei Monat {g.monate} nach Beitragsfreistellung — "
                    "im Tarifwerk nicht definiert (kein RKW beitragsfreier "
                    "Verträge)"
                )
                continue
            terminal_monat = g.monate
            if g.betrag_erwartet is not None:
                pruefungen.append(_vergleich(
                    f"gevo_sto_monat_{g.monate}",
                    vertrags_monatsreserve(kern, scheiben, g.monate).rkw,
                    g.betrag_erwartet,
                ))
        elif g.art == "TOD":
            terminal_monat = g.monate
            if g.betrag_erwartet is not None:
                vs_gesamt = float(grund_mp.sum_insured) + sum(
                    k.mp.sum_insured for _, k in scheiben)
                pruefungen.append(_vergleich(
                    f"gevo_tod_monat_{g.monate}", vs_gesamt,
                    g.betrag_erwartet,
                ))
        else:  # PEX
            if g.monate % 12:
                befunde.append(
                    f"PEX bei Monat {g.monate}: Beitragsfreistellung wirkt "
                    "am Vertragsjahrestag (Vielfaches von 12)"
                )
                continue
            pex_jahr = g.monate // 12
            if g.betrag_erwartet is not None:
                summe = kern.beitragsfreie_summe(pex_jahr) + sum(
                    k.beitragsfreie_summe(pex_jahr - erh_jahr)
                    for erh_jahr, k in scheiben)
                pruefungen.append(_vergleich(
                    f"gevo_pex_monat_{g.monate}", summe, g.betrag_erwartet,
                ))

    if terminal_monat is not None:
        if v.dk_erwartet_2 is not None:
            befunde.append(
                "Lieferung trägt ein Deckungskapital am Folgestichtag, "
                f"obwohl der Vertrag bei Monat {terminal_monat} abgegangen "
                "ist"
            )
    elif v.dk_erwartet_2 is None:
        befunde.append(
            "Vertrag fehlt am Folgestichtag, aber die GeVos nennen keinen "
            "Abgang — Lieferung inkonsistent"
        )
    else:
        if pex_jahr is not None:
            dk2 = kern.monatsreserve_beitragsfrei(
                pex_jahr, v.monate_stichtag_2) + sum(
                k.monatsreserve_beitragsfrei(
                    pex_jahr - erh_jahr,
                    v.monate_stichtag_2 - 12 * erh_jahr)
                for erh_jahr, k in scheiben)
        else:
            dk2 = vertrags_monatsreserve(
                kern, scheiben, v.monate_stichtag_2).vx_mrv
        pruefungen.append(_vergleich("dk_stichtag_2", dk2, v.dk_erwartet_2))

    return {
        "police_id": v.police_id,
        "bestanden": not befunde and all(p["ok"] for p in pruefungen),
        "befunde": befunde,
        "pruefungen": pruefungen,
    }


def pruefe_bestand(vertraege: List[VertragsPruefung]) -> Dict[str, Any]:
    """Suite über den ganzen Bestand: Urteile + Zusammenfassung.

    ``fehlgeschlagen`` zählt Verträge mit Toleranzverletzung oder
    Lieferungs-Befund; bestanden ist die Suite nur ohne jeden Fehlschlag.
    """
    urteile = [pruefe_vertrag(v) for v in vertraege]
    n_ok = sum(1 for u in urteile if u["bestanden"])
    return {
        "anzahl": len(urteile),
        "bestanden": n_ok,
        "fehlgeschlagen": len(urteile) - n_ok,
        "suite_bestanden": n_ok == len(urteile),
        "vertraege": urteile,
    }
