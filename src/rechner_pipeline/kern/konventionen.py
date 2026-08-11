"""Konventionen und Basis-Helfer des Kerns (unterste Rechenschicht).

Numerische Konventionen 1:1 aus dem VBA-Modul ``mConstants`` des
Quell-Workbooks (Radix, Rundungsordnung, Endalter), die Excel-treue Rundung
``excel_round`` (``WorksheetFunction.Round`` — half away from zero) und der
Ratenzuschlag ``installment_surcharge`` (Zelle E12). Modellpunkt-abhängige
Größen (Zins, Diskont) leben NICHT hier — sie werden je Rechnung aus dem
:class:`~rechner_pipeline.kern.model_point.ModelPoint` abgeleitet
(parametrisierte API statt Modul-Konstanten).
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, localcontext

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


def installment_surcharge(zw: int) -> float:
    """``ratzu`` (Kalkulation!E12): =IF(zw=2,2%,IF(zw=4,3%,IF(zw=12,5%,0)))."""
    if zw == 2:
        return 0.02
    if zw == 4:
        return 0.03
    if zw == 12:
        return 0.05
    return 0.0
