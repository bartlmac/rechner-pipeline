"""Konventionen und Basis-Helfer des Kerns (unterste Rechenschicht).

Numerische Konventionen 1:1 aus dem VBA-Modul ``mConstants`` des
Quell-Workbooks (Radix, Rundungsordnung, Endalter), die Excel-treue Rundung
``excel_round`` (``WorksheetFunction.Round`` — half away from zero) und die
Auswertung der Ratenzuschlag-Staffel ``installment_surcharge`` (Zelle E12).
TARIFWERK lebt nicht hier: Die Staffel selbst steht als Feld am
Modellpunkt und wird uebergeben, nicht hier vorgehalten.
Modellpunkt-abhängige Größen (Zins, Diskont) ebenso — sie werden je
Rechnung aus dem
:class:`~rechner_pipeline.kern.model_point.ModelPoint` abgeleitet
(parametrisierte API statt Modul-Konstanten).

Knoten: klv, bu
"""

from __future__ import annotations

import math
from decimal import Decimal, ROUND_HALF_UP, localcontext
from typing import Mapping

#: Tafel-Radix l_0 (VBA ``vek(0) = 1000000``).
RADIX = 1000000.0
#: Höchstes tabuliertes Alter (VBA ``max_Alter = 123``).
MAX_ALTER = 123
#: Rundungsordnung aller Kommutationswerte (VBA ``rund_lx = ... = 16``).
ROUND_DIGITS = 16


def excel_round(value: float, ndigits: int = ROUND_DIGITS) -> float:
    """Excel ``WorksheetFunction.Round``: half **away from zero** auf *ndigits*.

    Pythons eingebautes :func:`round` rundet kaufmännisch zur geraden Ziffer
    (banker's rounding) und ist daher kein treuer Ersatz für die VBA-Rundung
    der Kommutationsspalten. Decimal mit ``ROUND_HALF_UP`` reproduziert das
    Excel-Verhalten exakt.
    """
    if value == 0:
        return 0.0
    quantum = Decimal(1).scaleb(-ndigits)
    with localcontext() as ctx:
        ctx.prec = 60
        return float(Decimal(repr(value)).quantize(quantum, rounding=ROUND_HALF_UP))


def untergrenze_basissumme(betrag: float) -> float:
    """Keine Summe der Basisschicht wird negativ (Entscheid des Maintainers
    2026-09-30; Runde F, F2) — DIE eine Stelle dieser Regel.

    Die beitragsfreie Summe entsteht aus dem Rueckkaufs-Track,
    ``S_bfr = V^MRV / V^bfr``, und V^MRV ist innerhalb der Zillmerdauer bei
    zulaessigen Parametern negativ (z. B. alpha 0,06, zillmer_dauer 2,
    Vertragsjahr 1; die Config verlangt nur zillmer_dauer > 0). Eine
    negative Summe ist keine Leistung: Sie liess die Engine eine negative
    PEX-Summe buchen, die P-B1 am eigenen Lauf abwies, und machte die
    Herabsetzung mit f -> 0 (auf null begrenzt) zu etwas anderem als die
    Beitragsfreistellung. Beide Wege — PEX
    (``KLVProdukt.beitragsfreie_summe``), spaetere PEX nach einer
    Herabsetzung (``ReduzierterVertrag.beitragsfreie_summe``) und der
    umgewandelte Teil der Herabsetzung (``_reduziere_eine_schicht``) —
    rufen sie hier ab, damit ``f -> 0 == PEX`` nicht von drei Abschriften
    abhaengt.

    Gilt fuer die BASISSCHICHT; die Korrekturschicht ist Migrationsdifferenz
    und wird nicht geklemmt (siehe ``kern.beitragsreduktion``).

    Ein nicht endlicher Wert (NaN, inf) wird NICHT auf null geklemmt,
    sondern unveraendert durchgereicht: ``max(0.0, nan)`` ergibt in Python
    still 0.0, und damit wuerde ein Rechenfehler als gueltige Summe null
    erscheinen — die Fuehrungsprobe meldete dann "0,00 statt 1.169,61"
    statt des NaN, das sie sehen muss (Runde F, Nachbesserung: eine
    Untergrenze ist eine Grenze, kein Reparaturwert).
    """
    if not math.isfinite(betrag):
        return betrag
    return max(0.0, betrag)


def installment_surcharge(zw: int, staffel: Mapping[int, float]) -> float:
    """``ratzu`` (Kalkulation!E12): =IF(zw=2,2%,IF(zw=4,3%,IF(zw=12,5%,0))).

    Die Staffel ist TARIFWERK, keine Kern-Konvention, und wird deshalb
    immer übergeben: Sie steht als Feld am Modellpunkt, wo eine
    Generation sie parametrieren kann. Eine Default-Staffel hier wäre
    eine zweite Kopie derselben Zahlen und damit eine Driftquelle
    (Grundsatzdokumentation, Abweichungsverzeichnis). Unbekannte
    Zahlweise -> 0.0, wie das Blatt.
    """
    return staffel.get(zw, 0.0)
