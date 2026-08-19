"""Migrations-Testsuite: Zwei-Stichtags-Prüfung eines übernommenen Bestands.

Der Beweis einer Bestandsmigration endet nicht beim Stichtags-Foto: Das
Zielsystem muss den übernommenen Bestand auch FORTSCHREIBEN wie das
Quellsystem. Diese Suite prüft deshalb je Vertrag vier Dinge gegen
gelieferte Erwartungswerte (typisch: zweiter Bestandsabzug des
abgebenden Unternehmens plus GeVo-Protokoll des Zwischenzeitraums):

1. Deckungskapital am Migrationsstichtag — die Bilanzgröße, unterjährig
   interpoliert (:class:`rechner_pipeline.kern.Monatsreserve`);
2. Bruttojahresbeitrag am Migrationsstichtag, sofern geliefert
   (``bjb_erwartet_1``) — siehe BEITRAG ALS ZWEITE PRÜFACHSE;
3. die Beträge der Geschäftsvorfälle zwischen den Stichtagen
   (STO -> Rückkaufswert am Ereignismonat, PEX -> beitragsfreie Summe am
   Jahrestag, TOD und ABL -> Gesamt-VS bzw. nach einer
   Beitragsfreistellung die Summe der beitragsfreien Summen);
4. Deckungskapital am Folgestichtag auf dem durch die GeVos bestimmten
   Track (aktiv, beitragsfrei, abgegangen; nach einer dynamischen
   Erhöhung vertragsweit über Grund- und Erhöhungsscheiben —
   :func:`rechner_pipeline.kern.vertrags_monatsreserve`, Scheiben nach
   der Tarifwerk-Regel :func:`rechner_pipeline.kern.erhoehungs_scheibe`).

BEITRAG ALS ZWEITE PRÜFACHSE: Das Deckungskapital allein ist ein
stumpfes Instrument gegen Fehler in der PARAMETRIERUNG. Ein um ein Jahr
versetztes Eintrittsalter (Kalenderjahresmethode der Quelle gegen
vollendetes Alter des Ziels) verschiebt bei kurzer
Beitragszahlungsdauer die Reserve oft nur um Bruchteile eines Cents —
der Bruttojahresbeitrag reagiert auf dieselbe Verschiebung deutlich
stärker, weil er direkt an der Beitragsrate ``Bxt(x, n, t)`` hängt.
Deshalb wird der in jedem Bestandsabzug gelieferte Jahresbeitrag mit
geprüft, wenn er im Prüfauftrag steht. Fehlt er, ist das eine
AUSGEWIESENE LÜCKE (``nicht_geprueft`` je Vertrag,
``pruefluecken``/``vollstaendig_geprueft`` in der Zusammenfassung) und
kein stilles Bestehen: die Suite behauptet nie, geprüft zu haben, was
ihr niemand gegeben hat.

Der Systemwert des Beitrags ist ``0.0``, sobald die Beitragszahlung am
Stichtag beendet ist (``monate >= 12 * t``) oder der Vertrag bereits
beitragsfrei ist — genau so führen die Abzüge den Jahresbeitrag.

Inkonsistenzen der Lieferung (GeVo außerhalb der Stichtage, Wert trotz
Abgang, Abgang ohne GeVo, GeVo auf dem falschen Track) sind BEFUNDE je
Vertrag, nie stille Lücken (P2). Fehler der PRÜFMENGE (fehlende
Verträge, doppelte Policennummern) sind Befunde der Menge
(``mengenbefunde``) — eine Abnahme über 400 von 500 Verträgen ist keine
bestandene Abnahme, und ein dreimal gelieferter Vertrag ist kein
dreifacher Beleg.

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
#: :func:`pruefe_vertrag` bucht den Abgang AUSSCHLIESSLICH über diese
#: Tabelle — wer eine Art hier streicht oder aufnimmt, ändert damit das
#: Urteil (und nicht nur eine Beschriftung).
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

    ``bjb_erwartet_1`` ist der gelieferte Bruttojahresbeitrag am
    MIGRATIONSSTICHTAG (Feld ``JBRUTTO`` der üblichen Abzüge; ``0.00``
    für Verträge, deren Beitragszahlung beendet ist). ``None`` heißt
    "nicht geliefert" und wird als Prüflücke ausgewiesen — nicht als
    bestandene Prüfung.

    ``beitragsfrei_seit_jahr`` ist der ANFANGSZUSTAND: das Vertragsjahr
    einer Beitragsfreistellung, die schon VOR dem Migrationsstichtag
    wirksam war. Dann laufen beide Stichtage auf dem beitragsfreien
    Track und der Jahresbeitrag ist 0. Eine Beitragsfreistellung
    ZWISCHEN den Stichtagen ist kein Anfangszustand, sondern ein
    PEX-GeVo.
    """

    police_id: str
    model_point: Dict[str, Any]
    monate_stichtag_1: int
    monate_stichtag_2: int
    dk_erwartet_1: float
    dk_erwartet_2: Optional[float]
    gevos: Tuple[GeVoErwartung, ...] = field(default_factory=tuple)
    bjb_erwartet_1: Optional[float] = None
    beitragsfrei_seit_jahr: Optional[int] = None


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


def _terminale_leistung(
    kern: Rechenkern,
    scheiben: List[Tuple[int, Rechenkern]],
    pex_jahr: Optional[int],
) -> float:
    """Leistung eines terminalen Todes- oder Ablauffalls (TOD, ABL).

    Der Tarifplan (klv.md, GeVo-Katalog) gibt beiden dieselbe Regel:
    ``S^ges`` auf dem beitragspflichtigen Track, nach einer
    Beitragsfreistellung dagegen die dort fixierte Summe der
    beitragsfreien Summen ``sum S^bfr``. Genau so bucht es die
    Bestand-Engine (``bestand/ereignisse``: TOD zahlt ``pex_summe``,
    sobald der Vertrag beitragsfrei ist) — Prüfung und Fortschreibung
    dürfen hier nicht auseinanderlaufen.

    Der beitragsfreie Track kennt die Versicherungssumme des
    beitragspflichtigen nicht mehr; gegen ``S^ges`` zu vergleichen
    machte aus jeder korrekten Lieferung mit Beitragsfreistellung und
    anschließendem Todesfall einen Fehlschlag — ein falsches Rot, das
    wie ein Fund aussieht.
    """
    if pex_jahr is not None:
        return _bfr_gesamtsumme(kern, scheiben, pex_jahr)
    return _vs_gesamt(kern.mp, scheiben)


def _bjb_system(
    kern: Rechenkern, monate: int, pex_jahr: Optional[int]
) -> float:
    """Bruttojahresbeitrag des Vertrags am Monats-Stichtag.

    Nach dem Ende der Beitragszahlungsdauer (``monate >= 12 * t``) und
    ab einer Beitragsfreistellung wird kein Beitrag mehr gezahlt: der
    Systemwert ist dann ``0.0``, so wie die Bestandsabzüge das Feld
    führen. Sonst der Jahresbeitrag des Grundvertrags
    (``VS * Bxt``); Erhöhungsscheiben entstehen erst durch ERH-GeVos
    NACH dem Migrationsstichtag und tragen hier deshalb nichts bei.
    """
    if pex_jahr is not None or monate >= 12 * kern.mp.t:
        return 0.0
    return kern.gross_annual_premium()


def pruefe_vertrag(v: VertragsPruefung) -> Dict[str, Any]:
    """Zwei-Stichtags-Urteil für einen Vertrag.

    Rückgabe: ``bestanden`` (alle Vergleiche innerhalb der Toleranz und
    kein Befund), ``befunde`` (Texte zu Lieferungs-Inkonsistenzen),
    ``pruefungen`` (je Größe System-/Erwartungswert und Residuum) und
    ``nicht_geprueft`` (Größen, zu denen die Lieferung keinen
    Erwartungswert trägt — ausgewiesene Lücke, kein Bestehen).

    ABGEGANGENE VERTRÄGE — warum ``dk_stichtag_2`` dort WEDER verglichen
    noch als Lücke geführt wird: Bei einem terminalen GeVo ist das
    fehlende ``dk_erwartet_2`` kein fehlender Erwartungswert, sondern
    die geprüfte Aussage selbst. Geprüft wird hier die Übereinstimmung
    von Abgang und Folgeabzug, und sie ist bestanden; die beiden
    Gegenfälle (Wert trotz Abgang, Abgang ohne GeVo) sind Befunde.
    Anders im Abbruchpfad von :func:`pruefe_bestand`: dort ist über den
    Vertrag NICHTS bekannt — auch nicht, ob er abgegangen ist — und
    ``dk_stichtag_2`` steht deshalb in ``nicht_geprueft``. Die
    Asymmetrie ist gewollt: einmal ist die Größe geprüft, einmal ist
    sie ungeprüft.
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
    nicht_geprueft: List[str] = []

    # Anfangszustand: schon vor dem Migrationsstichtag beitragsfrei.
    pex_jahr: Optional[int] = v.beitragsfrei_seit_jahr
    if pex_jahr is not None:
        if pex_jahr <= 0:
            raise ValueError(
                f"{v.police_id}: beitragsfrei_seit_jahr = {pex_jahr} ist "
                "kein Vertragsjahr (> 0 erwartet)"
            )
        if 12 * pex_jahr > v.monate_stichtag_1:
            raise ValueError(
                f"{v.police_id}: Beitragsfreistellung in Jahr {pex_jahr} "
                f"(Monat {12 * pex_jahr}) liegt nach dem Migrationsstichtag "
                f"(Monat {v.monate_stichtag_1}) — als PEX-GeVo liefern, "
                "nicht als Anfangszustand"
            )
        dk_1 = kern.monatsreserve_beitragsfrei(pex_jahr, v.monate_stichtag_1)
    else:
        dk_1 = kern.monatsreserve(v.monate_stichtag_1).vx_mrv
    pruefungen.append(_vergleich("dk_stichtag_1", dk_1, v.dk_erwartet_1))

    if v.bjb_erwartet_1 is not None:
        pruefungen.append(_vergleich(
            "bjb_stichtag_1",
            _bjb_system(kern, v.monate_stichtag_1, pex_jahr),
            v.bjb_erwartet_1,
        ))
    else:
        nicht_geprueft.append("bjb_stichtag_1")

    terminal_monat: Optional[int] = None
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
            if g.betrag_erwartet is not None:
                pruefungen.append(_vergleich(
                    f"gevo_sto_monat_{g.monate}",
                    vertrags_monatsreserve(kern, scheiben, g.monate).rkw,
                    g.betrag_erwartet,
                ))
        elif g.art == "TOD":
            if g.betrag_erwartet is not None:
                pruefungen.append(_vergleich(
                    f"gevo_tod_monat_{g.monate}",
                    _terminale_leistung(kern, scheiben, pex_jahr),
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
            if g.betrag_erwartet is not None:
                pruefungen.append(_vergleich(
                    f"gevo_abl_monat_{g.monate}",
                    _terminale_leistung(kern, scheiben, pex_jahr),
                    g.betrag_erwartet,
                ))
        else:  # PEX
            if pex_jahr is not None:
                befunde.append(
                    f"PEX bei Monat {g.monate}: der Vertrag ist bereits seit "
                    f"Jahr {pex_jahr} beitragsfrei — eine zweite "
                    "Beitragsfreistellung gibt es nicht"
                )
                continue
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

        # Der Abgang wird an EINER Stelle gebucht, und zwar aus
        # :data:`TERMINAL`. Bis hierher kommt nur ein GeVo, den die
        # Zweige oben getragen haben (jeder Befund verlässt die Runde
        # per ``continue``) — ein terminaler GeVo mit Befund beendet
        # den Vertrag also nicht.
        if g.art in TERMINAL:
            terminal_monat = g.monate

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
        "nicht_geprueft": nicht_geprueft,
    }


def _mengenbefunde(
    vertraege: List[VertragsPruefung], erwartete_anzahl: Optional[int]
) -> List[str]:
    """Befunde der PRÜFMENGE: Vollständigkeit und Duplikate.

    Beides sind Aussagen über die Menge, nicht über einen Vertrag —
    und beide entwerten die Abnahme vollständig, wenn sie unbemerkt
    bleiben: eine Suite über 400 von 500 Verträgen meldet sonst
    "bestanden", und ein dreimal enthaltener Vertrag zählt dreifach in
    jeder Quote.
    """
    befunde: List[str] = []
    if erwartete_anzahl is not None and erwartete_anzahl != len(vertraege):
        fehlend = erwartete_anzahl - len(vertraege)
        richtung = (f"{fehlend} Verträge fehlen in der Prüfmenge"
                    if fehlend > 0
                    else f"{-fehlend} Verträge zu viel in der Prüfmenge")
        befunde.append(
            f"Vollständigkeit: {len(vertraege)} geprüfte Verträge gegen "
            f"{erwartete_anzahl} erwartete — {richtung}. Prüfe die "
            "Lieferung und die Transformation (verworfene Zeilen, Filter)."
        )
    zaehler: Dict[str, int] = {}
    for v in vertraege:
        zaehler[v.police_id] = zaehler.get(v.police_id, 0) + 1
    for police_id, n in zaehler.items():
        if n > 1:
            befunde.append(
                f"Policennummer {police_id!r} kommt {n}-mal in der "
                "Prüfmenge vor — derselbe Vertrag wird mehrfach gezählt; "
                "die Prüfmenge ist keine Bestandsmenge."
            )
    return befunde


def pruefe_bestand(
    vertraege: List[VertragsPruefung],
    *,
    erwartete_anzahl: Optional[int] = None,
) -> Dict[str, Any]:
    """Suite über den ganzen Bestand: Urteile + Zusammenfassung.

    ``fehlgeschlagen`` zählt Verträge mit Toleranzverletzung oder
    Lieferungs-Befund; bestanden ist die Suite nur ohne jeden Fehlschlag
    UND ohne Befund der Prüfmenge (``mengenbefunde``).

    PRÜFMENGE: ``erwartete_anzahl`` ist die aus der Lieferung bekannte
    Vertragszahl (Zeilen des Bestandsabzugs). Wird sie übergeben, prüft
    die Suite die Vollständigkeit; wird sie nicht übergeben, ist das
    eine ausgewiesene Prüflücke — nicht etwa Vollständigkeit. Doppelte
    Policennummern sind immer ein harter Befund.

    PRÜFLÜCKEN: ``pruefluecken`` benennt, was die Suite MANGELS
    Erwartungswerten nicht geprüft hat (fehlende Jahresbeiträge,
    fehlende erwartete Vertragszahl); ``vollstaendig_geprueft`` ist nur
    ohne jede Lücke wahr. Eine Lücke ist kein Fehlschlag — aber auch
    kein Bestehen, und sie steht deshalb neben dem Urteil.

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
    verschwinden. Ein abgebrochener Vertrag führt ALLE drei Prüfgrößen
    als ``nicht_geprueft``, auch ``dk_stichtag_2``: nach dem Abbruch ist
    über ihn nichts bekannt, nicht einmal ob er abgegangen ist. Der
    regulär abgegangene Vertrag führt ``dk_stichtag_2`` dagegen NICHT
    als Lücke — dort ist der Abgang die Prüfung (siehe
    :func:`pruefe_vertrag`).
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
                # Abgebrochen heisst: NICHTS an diesem Vertrag geprueft.
                "nicht_geprueft": ["dk_stichtag_1", "bjb_stichtag_1",
                                   "dk_stichtag_2"],
            })
    n_ok = sum(1 for u in urteile if u["bestanden"])
    mengenbefunde = _mengenbefunde(vertraege, erwartete_anzahl)

    luecken_zaehler: Dict[str, int] = {}
    for u in urteile:
        for groesse in u["nicht_geprueft"]:
            luecken_zaehler[groesse] = luecken_zaehler.get(groesse, 0) + 1
    pruefluecken = [
        f"{groesse}: bei {n} von {len(urteile)} Verträgen NICHT geprüft "
        "(kein gelieferter Erwartungswert oder abgebrochene Prüfung)."
        for groesse, n in sorted(luecken_zaehler.items())
    ]
    if erwartete_anzahl is None:
        pruefluecken.append(
            "Vollständigkeit: keine erwartete Vertragszahl übergeben "
            "(erwartete_anzahl) — dass die Prüfmenge dem gelieferten "
            "Bestand entspricht, ist NICHT geprüft."
        )

    return {
        "anzahl": len(urteile),
        "bestanden": n_ok,
        "fehlgeschlagen": len(urteile) - n_ok,
        "suite_bestanden": n_ok == len(urteile) and not mengenbefunde,
        "erwartete_anzahl": erwartete_anzahl,
        "mengenbefunde": mengenbefunde,
        "pruefluecken": pruefluecken,
        "vollstaendig_geprueft": not pruefluecken,
        "vertraege": urteile,
    }
