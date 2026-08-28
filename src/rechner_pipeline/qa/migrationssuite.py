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
ihr niemand gegeben hat. Dasselbe gilt für den Erwartungsbetrag jedes
betragsführenden GeVos (STO, TOD, ABL und PEX). Seine Zustandswirkung
wird weiterhin geprüft, der ausgelassene Betragsvergleich aber als
konkrete Größe ``gevo_<art>_monat_<n>`` ausgewiesen.

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

ABGRENZUNG (ADR-010): Diese Suite ist das MIGRATIONSCONTROLLING am
Migrationsstichtag — jeder Vertrag des Bestands, aggregierend, Vorlage
fuer Gate A-M4. ``vollstaendig_geprueft`` traegt genau diese Bedeutung:
jeder Vertrag wurde geprueft, ein ungeprueter ist eine Prueflücke. Der
AKTUARIELLE TEST (``qa.aktuarieller_test``, Gate A-M1) ist die andere
Pruefebene: je Vertrag am eigenen Verankerungszeitpunkt, auf einer
Stichprobe — dort heisst Vollstaendigkeit ``stichprobe_vollstaendig``
(die Stichprobe wurde abgearbeitet). Die Scope-Bindungen dieser Suite
(``bestand_sha256``, ``system``) sind Transport- und
Provenienzsicherung des Controllings, kein aktuarielles Urteil.

Knoten: klv
"""

from __future__ import annotations

import datetime as _dt
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from rechner_pipeline.kern import (
    MissingMortalityTableError,
    ModelPoint,
    Rechenkern,
    erhoehungs_scheibe,
    vertrags_monatsreserve,
)
from rechner_pipeline.kern.beitragsreduktion import (
    PROSPEKTIV,
    ReduzierterVertrag,
)
from rechner_pipeline.qa.abzugsabgleich import ABS_TOL, REL_TOL

GEVO_ARTEN = ("ERH", "STO", "TOD", "PEX", "ABL", "RED")
#: Diese Arten tragen einen eigenständig zu vergleichenden Leistungs-
#: beziehungsweise Statuswechselbetrag. Fehlt er, darf ein zusätzlich
#: erkannter Lieferungsbefund die konkrete Prüflücke nicht verdecken.
BETRAGSPRUEFUNG_ARTEN = ("STO", "TOD", "ABL", "PEX")
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
    ERH: Versicherungssumme der neuen Scheibe). Fehlt er bei STO, TOD,
    ABL oder PEX, bleibt die Zustandsprüfung möglich, aber der
    Betragsvergleich ist eine ausgewiesene Prüflücke. Eine ERH kann ohne
    Erhöhungssumme nicht konstruiert werden und bleibt deshalb wie bisher
    ein Lieferungsbefund.
    """

    art: str
    monate: int
    betrag_erwartet: Optional[float] = None
    #: Nur bei RED: der fortgeführte Bruchteil des Beitrags. Er steht im
    #: Vorfall und nicht im Vertrag; ohne ihn ist die Herabsetzung nicht
    #: bestimmt.
    anteil: Optional[float] = None


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

    ``scheiben`` und ``reduktion`` sind die beiden anderen
    Anfangszustaende eines uebernommenen Vertrags: dynamische
    Erhoehungen der VORGESCHICHTE als ``(vertragsjahr,
    erhoehungssumme)`` je Scheibe, bzw. eine Herabsetzung der
    Vorgeschichte als ``(vertragsjahr, fortgefuehrter_anteil)`` —
    bewertet als geteilter Vertrag (Kern 3.1.0, Zielverfahren
    prospektiv). Die Anfangszustaende sind EXKLUSIV: eine Vorgeschichte
    mit mehreren Welten (beitragsfrei UND reduziert, ...) ist kein
    abgebildeter Fall und faellt als Auftragsfehler, nicht als stiller
    Track.
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
    scheiben: Tuple[Tuple[int, float], ...] = field(default_factory=tuple)
    reduktion: Optional[Tuple[int, float]] = None


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
    kern: Rechenkern,
    monate: int,
    pex_jahr: Optional[int],
    *,
    scheiben: Sequence[Tuple[int, Rechenkern]] = (),
    reduziert: Optional["ReduzierterVertrag"] = None,
) -> float:
    """Bruttojahresbeitrag des Vertrags am Monats-Stichtag.

    Nach dem Ende der Beitragszahlungsdauer (``monate >= 12 * t``) und
    ab einer Beitragsfreistellung wird kein Beitrag mehr gezahlt: der
    Systemwert ist dann ``0.0``, so wie die Bestandsabzüge das Feld
    führen. Sonst der Jahresbeitrag des Grundvertrags (``VS * Bxt``) —
    nach einer Herabsetzung der fortgeführte Anteil davon. Jede
    Erhöhungsscheibe der Vorgeschichte ist ein eigener Modellpunkt mit
    eigenem Beitrag bis zu IHRER Beitragszahlungsdauer (dieselbe Regel
    wie ``bestand.auswertung.beitraege``): ohne sie wäre das
    Beitragsvolumen so zu niedrig wie das Deckungskapital ohne
    Scheiben.
    """
    if pex_jahr is not None:
        return 0.0
    if reduziert is not None:
        gesamt = reduziert.bjb(monate)
    elif monate >= 12 * kern.mp.t:
        gesamt = 0.0
    else:
        gesamt = kern.gross_annual_premium()
    for erh_jahr, k in scheiben:
        if monate - 12 * erh_jahr < 12 * k.mp.t:
            gesamt += k.gross_annual_premium()
    return gesamt


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

    HERABGESETZTE VERTRÄGE — seit Kern 3.1.0 werden sie FORTGEFÜHRT
    (geteilter Vertrag, Zielverfahren prospektiv): eine Herabsetzung der
    Vorgeschichte ist der Anfangszustand ``reduktion``, eine im
    Prüfzeitraum ein RED-GeVo mit geliefertem Anteil. Nur ohne Anteil
    bleibt der Folgestichtag eine ausgewiesene Prüflücke — nicht weil
    die Rechnung fehlte, sondern weil die Herabsetzung unbestimmt ist.
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

    # Anfangszustaende sind EXKLUSIV: je Vertrag hoechstens EINE
    # Vorgeschichts-Welt (beitragsfrei, Alt-Scheiben, herabgesetzt).
    welten = [name for name, gesetzt in (
        ("beitragsfrei_seit_jahr", v.beitragsfrei_seit_jahr is not None),
        ("scheiben", bool(v.scheiben)),
        ("reduktion", v.reduktion is not None),
    ) if gesetzt]
    if len(welten) > 1:
        raise ValueError(
            f"{v.police_id}: mehrere Anfangszustaende zugleich "
            f"({', '.join(welten)}) — die Kombination ist nicht abgebildet"
        )

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

    # Anfangszustand: Herabsetzung der Vorgeschichte (geteilter Vertrag).
    alt_rv: Optional[ReduzierterVertrag] = None
    if v.reduktion is not None:
        red_jahr, red_anteil = v.reduktion
        if 12 * red_jahr > v.monate_stichtag_1:
            raise ValueError(
                f"{v.police_id}: Herabsetzung in Jahr {red_jahr} liegt nach "
                "dem Migrationsstichtag — als RED-GeVo liefern, nicht als "
                "Anfangszustand"
            )
        # Jahr- und Anteilsgrenzen prueft der Kern (fail-fast).
        alt_rv = ReduzierterVertrag.nach(
            kern, red_jahr, red_anteil, verfahren=PROSPEKTIV)

    # Anfangszustand: dynamische Erhoehungen der Vorgeschichte.
    scheiben: List[Tuple[int, Rechenkern]] = []
    for erh_jahr, erh_summe in v.scheiben:
        if 12 * erh_jahr > v.monate_stichtag_1:
            raise ValueError(
                f"{v.police_id}: Erhoehungsscheibe aus Jahr {erh_jahr} liegt "
                "nach dem Migrationsstichtag — als ERH-GeVo liefern, nicht "
                "als Anfangszustand"
            )
        scheiben.append(
            (erh_jahr, Rechenkern(erhoehungs_scheibe(
                grund_mp, erh_jahr, erh_summe))))

    if alt_rv is not None:
        dk_1 = alt_rv.monatsreserve(v.monate_stichtag_1).vx_mrv
    elif pex_jahr is not None:
        dk_1 = kern.monatsreserve_beitragsfrei(pex_jahr, v.monate_stichtag_1)
    elif scheiben:
        dk_1 = vertrags_monatsreserve(
            kern, scheiben, v.monate_stichtag_1).vx_mrv
    else:
        dk_1 = kern.monatsreserve(v.monate_stichtag_1).vx_mrv
    pruefungen.append(_vergleich("dk_stichtag_1", dk_1, v.dk_erwartet_1))

    if v.bjb_erwartet_1 is not None:
        pruefungen.append(_vergleich(
            "bjb_stichtag_1",
            _bjb_system(kern, v.monate_stichtag_1, pex_jahr,
                        scheiben=scheiben, reduziert=alt_rv),
            v.bjb_erwartet_1,
        ))
    else:
        nicht_geprueft.append("bjb_stichtag_1")

    terminal_monat: Optional[int] = None
    red_monat: Optional[int] = None
    reduziert: Optional[ReduzierterVertrag] = None
    for g in sorted(v.gevos, key=lambda g: g.monate):
        if g.art not in GEVO_ARTEN:
            befunde.append(f"unbekannte GeVo-Art {g.art!r}")
            continue
        if g.art in BETRAGSPRUEFUNG_ARTEN and g.betrag_erwartet is None:
            luecke = f"gevo_{g.art.lower()}_monat_{g.monate}"
            if luecke not in nicht_geprueft:
                nicht_geprueft.append(luecke)
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
        if red_monat is not None:
            # Ein weiterer Vorfall NACH einer Herabsetzung im
            # Prüfzeitraum: der geteilte Vertrag kann Folge-GeVos
            # (zweites PEX-Fixieren, Erhöhung, Rückkauf) rechnen, aber
            # keiner der Zweige unten tut es — sie rechnen auf dem
            # UNGETEILTEN Kern. Ein stiller falscher Wert wäre schlimmer
            # als ein Befund.
            befunde.append(
                f"GeVo {g.art} bei Monat {g.monate} nach Herabsetzung "
                f"(Monat {red_monat}) — Folge-Geschäftsvorfälle eines im "
                "Prüfzeitraum herabgesetzten Vertrags sind in der Suite "
                "noch nicht abgebildet"
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
            if alt_rv is not None and scheiben:
                befunde.append(
                    f"STO bei Monat {g.monate}: Rückkauf eines "
                    "herabgesetzten Vertrags MIT Erhöhungsscheiben ist "
                    "nicht abgebildet"
                )
                continue
            if g.betrag_erwartet is not None:
                rkw = (alt_rv.monatsreserve(g.monate).rkw
                       if alt_rv is not None else
                       vertrags_monatsreserve(kern, scheiben, g.monate).rkw)
                pruefungen.append(_vergleich(
                    f"gevo_sto_monat_{g.monate}", rkw, g.betrag_erwartet,
                ))
        elif g.art == "TOD":
            if alt_rv is not None and scheiben:
                befunde.append(
                    f"TOD bei Monat {g.monate}: Leistung eines "
                    "herabgesetzten Vertrags MIT Erhöhungsscheiben ist "
                    "nicht abgebildet"
                )
                continue
            if g.betrag_erwartet is not None:
                leistung = (alt_rv.terminale_leistung(pex_jahr)
                            if alt_rv is not None else
                            _terminale_leistung(kern, scheiben, pex_jahr))
                pruefungen.append(_vergleich(
                    f"gevo_tod_monat_{g.monate}", leistung,
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
            if alt_rv is not None and scheiben:
                befunde.append(
                    f"ABL bei Monat {g.monate}: Leistung eines "
                    "herabgesetzten Vertrags MIT Erhöhungsscheiben ist "
                    "nicht abgebildet"
                )
                continue
            if g.betrag_erwartet is not None:
                leistung = (alt_rv.terminale_leistung(pex_jahr)
                            if alt_rv is not None else
                            _terminale_leistung(kern, scheiben, pex_jahr))
                pruefungen.append(_vergleich(
                    f"gevo_abl_monat_{g.monate}", leistung,
                    g.betrag_erwartet,
                ))
        elif g.art == "RED":
            # Der herabgesetzte Vertrag wird seit Kern 3.1.0 FORTGEFÜHRT
            # (kern.beitragsreduktion.ReduzierterVertrag, Zweiteilung in
            # fortgeführten Anteil und fixierte beitragsfreie Summe). Die
            # Suite rechnet mit dem ZIELVERFAHREN (prospektiv,
            # verlustfrei); rechnet das Quellsystem mit Abzug, zeigt der
            # Vergleich am Folgestichtag genau die Verfahrensdifferenz —
            # je Vertrag sichtbar, statt einer Prüflücke oder eines
            # stillen Vergleichs auf der ursprünglichen Summe.
            #
            # Ohne gelieferten Anteil bleibt die Herabsetzung
            # unbestimmt: Anteils-Vergleich UND Folgewert sind dann
            # ausgewiesene Prüflücken.
            #
            # Die Wertänderung IM Moment der Herabsetzung prüft der
            # Geschäftsvorfalltest A-M3 über kern.beitragsreduktion.
            if pex_jahr is not None:
                befunde.append(
                    f"RED bei Monat {g.monate}: der Vertrag ist seit Jahr "
                    f"{pex_jahr} beitragsfrei — es gibt keinen Beitrag, "
                    "der sich herabsetzen ließe"
                )
                continue
            if alt_rv is not None:
                befunde.append(
                    f"RED bei Monat {g.monate}: zweite Herabsetzung eines "
                    "bereits herabgesetzten Vertrags ist nicht abgebildet"
                )
                continue
            if scheiben:
                befunde.append(
                    f"RED bei Monat {g.monate} nach dynamischer Erhöhung — "
                    "die Herabsetzung eines Vertrags mit Erhöhungsscheiben "
                    "ist im Zielsystem noch nicht abgebildet (Tarifplan-"
                    "Ausgestaltung offen); Wert nicht gerechnet"
                )
                continue
            if g.monate % 12:
                befunde.append(
                    f"RED bei Monat {g.monate}: die Herabsetzung wirkt am "
                    "Vertragsjahrestag (Vielfaches von 12)"
                )
                continue
            if g.anteil is None:
                nicht_geprueft.append(f"gevo_red_monat_{g.monate}_anteil")
            elif not 0.0 <= g.anteil <= 1.0:
                befunde.append(
                    f"RED bei Monat {g.monate}: Anteil {g.anteil} liegt "
                    "nicht in [0, 1] — er ist der fortgeführte Bruchteil "
                    "des Beitrags"
                )
                continue
            else:
                reduziert = ReduzierterVertrag.nach(
                    kern, g.monate // 12, g.anteil, verfahren=PROSPEKTIV)
            red_monat = g.monate
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
            if alt_rv is not None and scheiben:
                befunde.append(
                    f"PEX bei Monat {g.monate}: Beitragsfreistellung eines "
                    "herabgesetzten Vertrags MIT Erhöhungsscheiben ist "
                    "nicht abgebildet"
                )
                continue
            pex_jahr = g.monate // 12
            if g.betrag_erwartet is not None:
                summe = (alt_rv.beitragsfreie_summe(pex_jahr)
                         if alt_rv is not None else
                         _bfr_gesamtsumme(kern, scheiben, pex_jahr))
                pruefungen.append(_vergleich(
                    f"gevo_pex_monat_{g.monate}", summe,
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
    elif red_monat is not None:
        if reduziert is not None:
            # Der geteilte Vertrag wird fortgeführt (Kern 3.1.0): der
            # fortgeführte Anteil auf dem beitragspflichtigen Track, die
            # fixierte beitragsfreie Summe auf dem bfr-Satz. Gerechnet
            # wird das ZIELVERFAHREN; eine Verfahrensdifferenz der
            # Quelle erscheint als Residuum dieses Vergleichs.
            pruefungen.append(_vergleich(
                "dk_stichtag_2",
                reduziert.monatsreserve(v.monate_stichtag_2).vx_mrv,
                v.dk_erwartet_2,
            ))
        else:
            # Ohne gelieferten Anteil ist die Herabsetzung unbestimmt —
            # eine ausgewiesene Prüflücke ist ehrlicher als eine Zahl,
            # die aussieht, als sei sie geprüft.
            nicht_geprueft.append(
                f"dk_stichtag_2_nach_red_monat_{red_monat}")
    else:
        if alt_rv is not None:
            if pex_jahr is not None:
                dk2 = alt_rv.reserve_beitragsfrei(
                    pex_jahr, v.monate_stichtag_2)
            else:
                # Geteilter Vertrag plus etwaige Scheiben aus
                # Prüfzeitraums-ERH — jede an ihrem versetzten Stichtag.
                dk2 = alt_rv.monatsreserve(v.monate_stichtag_2).vx_mrv + sum(
                    k.monatsreserve(
                        v.monate_stichtag_2 - 12 * erh_jahr).vx_mrv
                    for erh_jahr, k in scheiben)
        elif pex_jahr is not None:
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
    stichtag_1: Optional[str] = None,
    stichtag_2: Optional[str] = None,
    bestand_sha256: Optional[str] = None,
    system: Optional[Dict[str, str]] = None,
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
    GeVo-Beträge oder erwartete Vertragszahl);
    ``vollstaendig_geprueft`` ist nur ohne jede Lücke wahr. Eine Lücke
    ist kein Fehlschlag — aber auch kein Bestehen, und sie steht deshalb
    neben dem Urteil.

    SCOPE-BINDUNG: Für einen Bestandsfall werden ``stichtag_1``,
    ``stichtag_2`` und ``bestand_sha256`` gemeinsam übergeben. Fuer einen
    A-M4-Beleg kommt der vom Aufrufer berechnete ``system``-Stand hinzu. Die
    Suite validiert und spiegelt diese Angaben in ihr Ergebnis. Ohne sie bleibt
    die Funktion fallunabhängig, ihr Ergebnis ist aber kein A-M4-Beleg eines
    Bestandsfalls.

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
    scope_werte = (stichtag_1, stichtag_2, bestand_sha256)
    if any(wert is not None for wert in scope_werte):
        if not all(isinstance(wert, str) and wert for wert in scope_werte):
            raise ValueError(
                "Suite-Scope-Bindung verlangt gemeinsam stichtag_1, "
                "stichtag_2 und bestand_sha256"
            )
        try:
            erster = _dt.date.fromisoformat(stichtag_1)
            zweiter = _dt.date.fromisoformat(stichtag_2)
        except ValueError as exc:
            raise ValueError(f"Suite-Scope-Stichtag ist ungueltig: {exc}") from exc
        if zweiter <= erster:
            raise ValueError("Suite-Scope-Stichtag 2 muss nach Stichtag 1 liegen")
        if (
            len(bestand_sha256) != 64
            or any(zeichen not in "0123456789abcdef" for zeichen in bestand_sha256)
        ):
            raise ValueError("Suite-Scope-bestand_sha256 ist kein SHA-256")
    if system is not None:
        system_felder = {"commit", "branch", "dirty", "quellcode_sha256"}
        if not isinstance(system, dict) or set(system) != system_felder:
            raise ValueError(
                "Suite-Scope-system muss exakt " + str(sorted(system_felder))
                + " enthalten"
            )
        if any(not isinstance(wert, str) or not wert for wert in system.values()):
            raise ValueError("Suite-Scope-system-Werte muessen nichtleer sein")
        quellcode_hash = system["quellcode_sha256"]
        if (
            len(quellcode_hash) != 64
            or any(zeichen not in "0123456789abcdef" for zeichen in quellcode_hash)
        ):
            raise ValueError("Suite-Scope-system.quellcode_sha256 ist kein SHA-256")

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

    ergebnis = {
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
    if all(wert is not None for wert in scope_werte):
        ergebnis.update({
            "stichtag_1": stichtag_1,
            "stichtag_2": stichtag_2,
            "bestand_sha256": bestand_sha256,
        })
    if system is not None:
        ergebnis["system"] = dict(system)
    return ergebnis
