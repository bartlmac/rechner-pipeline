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
   PEX -> beitragsfreie Summe am Jahrestag, ABL -> Gesamt-VS bzw. nach
   Beitragsfreistellung die Summe der beitragsfreien Summen);
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
    MissingMortalityTableError,
    ModelPoint,
    Rechenkern,
    erhoehungs_scheibe,
    vertrags_monatsreserve,
)
from rechner_pipeline.qa.abzugsabgleich import ABS_TOL, REL_TOL

GEVO_ARTEN = ("ERH", "STO", "TOD", "PEX", "ABL")
#: GeVo-Arten, die den Vertrag beenden (kein Wert am Folgestichtag).
TERMINAL = ("STO", "TOD", "ABL")

#: Ausnahmen, die eine unplausible LIEFERUNG auslösen kann und die
#: deshalb Befund GENAU EINES Vertrags werden (siehe
#: :func:`pruefe_bestand`): Bereichs-/Plausibilitätsfehler des Kerns
#: (``ValueError``, davon abgeleitet ``TafelBereichError``), ein
#: Modellpunkt, der den Feld-Contract des Kerns verletzt (``TypeError``
#: bei unbekanntem/fehlendem Feld, ``KeyError`` bei fehlendem Schlüssel),
#: entartete Parameter (``ArithmeticError``: Division durch Null,
#: Overflow) und eine gelieferte, im Zielsystem nicht hinterlegte
#: Sterbetafel (``MissingMortalityTableError``).
#: NICHT gefangen wird alles Übrige — ``AttributeError``, ``NameError``,
#: ``IndexError``, ``AssertionError``, ``RecursionError``: diese Fehler
#: kann kein Lieferdatum erzeugen, sie sind Defekte der Suite oder des
#: Kerns. Sie müssen den Lauf abbrechen, statt sich als 500 gleich
#: lautende "Befunde" zu tarnen.
DATEN_AUSNAHMEN: Tuple[type, ...] = (
    ValueError,
    TypeError,
    KeyError,
    ArithmeticError,
    MissingMortalityTableError,
)


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


def _vs_gesamt(
    grund_mp: ModelPoint, scheiben: List[Tuple[int, Rechenkern]]
) -> float:
    """Gesamt-Versicherungssumme des Vertrags (Grundvertrag + Scheiben).

    Die Leistung von TOD und ABL des beitragspflichtigen Tracks
    (Tarifplan klv.md, GeVo-Katalog: ``S^ges``).
    """
    return float(grund_mp.sum_insured) + sum(
        k.mp.sum_insured for _, k in scheiben)


def _bfr_gesamtsumme(
    kern: Rechenkern, scheiben: List[Tuple[int, Rechenkern]], pex_jahr: int
) -> float:
    """Summe der beitragsfreien Summen über Grundvertrag und Scheiben.

    Die bei der Beitragsfreistellung im Jahr ``pex_jahr`` fixierte
    Vertragsleistung (Tarifplan klv.md, GeVo-Katalog: ``sum S^bfr_a``);
    jede Erhöhungsscheibe zählt ab ihrem eigenen Jahrestag, daher der
    Versatz ``pex_jahr - erh_jahr``. Sie ist ab der Beitragsfreistellung
    konstant und damit zugleich die Ablauf-/Todesfallleistung des
    beitragsfreien Tracks.
    """
    return kern.beitragsfreie_summe(pex_jahr) + sum(
        k.beitragsfreie_summe(pex_jahr - erh_jahr)
        for erh_jahr, k in scheiben)


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
                pruefungen.append(_vergleich(
                    f"gevo_tod_monat_{g.monate}",
                    _vs_gesamt(grund_mp, scheiben),
                    g.betrag_erwartet,
                ))
        elif g.art == "ABL":
            # Ablauf ist terminal und faellig GENAU am Ende der
            # Versicherungsdauer (Tarifplan klv.md, GeVo-Katalog:
            # "terminal bei a = n"). Ein ABL an einem anderen Monat ist
            # kein Ablauf, sondern eine Lieferungs-Inkonsistenz.
            ablauf_monat = 12 * grund_mp.n
            if g.monate != ablauf_monat:
                befunde.append(
                    f"ABL bei Monat {g.monate}: Ablauf wird am Ende der "
                    f"Versicherungsdauer fällig (Monat {ablauf_monat}, "
                    f"n = {grund_mp.n} Jahre)"
                )
                continue
            terminal_monat = g.monate
            if g.betrag_erwartet is not None:
                betrag = (
                    _bfr_gesamtsumme(kern, scheiben, pex_jahr)
                    if pex_jahr is not None
                    else _vs_gesamt(grund_mp, scheiben)
                )
                pruefungen.append(_vergleich(
                    f"gevo_abl_monat_{g.monate}", betrag, g.betrag_erwartet,
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
                pruefungen.append(_vergleich(
                    f"gevo_pex_monat_{g.monate}",
                    _bfr_gesamtsumme(kern, scheiben, pex_jahr),
                    g.betrag_erwartet,
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

    LEERE PRÜFMENGE: harter Fehler statt eines ausgewiesenen
    Nicht-Bestehens. Ein ``suite_bestanden = False`` wäre die Aussage
    "geprüft und durchgefallen" und würde einen Abnahmebericht über
    null Verträge erzeugen ("0 von 0 fehlgeschlagen") — eine Urkunde
    über nichts, die ein Gremium als Prüfaussage lesen kann. Tatsächlich
    hat hier gar keine Prüfung stattgefunden; die Ursache liegt vor der
    Suite (leere Lieferung, Transformation ohne Ausgabezeilen, falscher
    Filter). Über ein Nichts gibt es kein ehrliches Urteil, nur einen
    Abbruch, der auf die Ursache zeigt (P2: kein stiller Default).
    ``pruefe_vertrag`` bleibt davon unberührt.

    VERTRAGS-ISOLATION: eine Ausnahme aus :func:`pruefe_vertrag`, die
    eine unplausible Lieferung erzeugt haben kann (:data:`DATEN_AUSNAHMEN`),
    wird zum Befund GENAU DIESES Vertrags — der Lauf prüft die übrigen zu
    Ende. Ein einzelner kranker Datensatz darf die Abnahme des ganzen
    Bestands nicht in einen Traceback verwandeln; die Diagnose steht
    dann im Bericht, bei der Police, an der sie hängt. Alle anderen
    Ausnahmen (Defekte der Suite oder des Kerns) laufen ungefangen
    durch — sie sollen sichtbar sein und nicht als Reihe von Befunden
    verschwinden.
    """
    if not vertraege:
        raise ValueError(
            "Migrations-Abnahmesuite ohne einen einzigen Vertrag: eine "
            "leere Prüfmenge ist keine bestandene Abnahme. Prüfe die "
            "Lieferung und die Transformation (wurden 0 Verträge "
            "übernommen?) und rufe die Suite mit mindestens einem "
            "Vertrag auf."
        )
    urteile: List[Dict[str, Any]] = []
    for v in vertraege:
        try:
            urteile.append(pruefe_vertrag(v))
        except DATEN_AUSNAHMEN as exc:
            urteile.append({
                "police_id": v.police_id,
                "bestanden": False,
                "befunde": [
                    "Prüfung abgebrochen "
                    f"({type(exc).__name__}): {exc}"
                ],
                "pruefungen": [],
            })
    n_ok = sum(1 for u in urteile if u["bestanden"])
    return {
        "anzahl": len(urteile),
        "bestanden": n_ok,
        "fehlgeschlagen": len(urteile) - n_ok,
        "suite_bestanden": n_ok == len(urteile),
        "vertraege": urteile,
    }
