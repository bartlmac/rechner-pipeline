"""Rechenkonventionen des Quellsystems — EINGEFRORENE Kopie.

Uebernommen 2026-08-31 aus ``rechner_pipeline.kern.konventionen`` (Stand
f0938c7), auf die drei Bausteine beschnitten, die die Kommutation
braucht. Absichtlich KEIN Import aus ``rechner_pipeline``: Der Quellcode
des Quellsystems ist fuer das Migrationsprojekt unerreichbar, also darf
auch keine spaetere Zielsystem-Aenderung hierher durchsickern.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, localcontext

#: VBA ``radix = 1000000``.
RADIX = 1000000.0
#: Hoechstes tabuliertes Alter (VBA ``max_Alter = 123``).
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
