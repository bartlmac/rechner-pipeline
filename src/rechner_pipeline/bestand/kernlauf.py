"""Kernel-based evaluation of portfolio contracts (Fortschreibung support).

Project decision (Projektleitung/Aktuariat 2026-08-11): every calculated
quantity — premium, present values, reserve at a reporting date — comes
EXCLUSIVELY from the kernel; the Bestandsdaten module carries no actuarial
formulas of its own.

:func:`berechne_vertrag` evaluates one contract against the stable, promoted
kernel (:mod:`rechner_pipeline.kern`) in-process: no subprocess, no
confinement — the kernel is reviewed, version-anchored repo code.

Bis zur Ausserbetriebnahme des Portierungspfads gab es daneben einen zweiten
Weg fuer TRANSIENTE, frisch generierte Kerne (ein abgeschotteter Kindprozess
je Vertrag). Er ist entfallen: es werden keine Fremdkerne mehr erzeugt, also
gibt es auch nichts mehr abzuschotten.

Knoten: klv
"""

from __future__ import annotations

import sys
from typing import Any, Dict, Mapping, Optional

from rechner_pipeline.kern import ModelPoint, berechne
from rechner_pipeline.models.bestand import model_point_kwargs



class KernlaufError(RuntimeError):
    """Der Kern liefert kein verwertbares Ergebnis fuer diesen Vertrag."""


def berechne_vertrag(
    row: Mapping[str, Any], generation_fields: Mapping[str, Any]
) -> Dict[str, Any]:
    """Evaluate one portfolio contract through the stable kernel, in-process.

    Joins the portfolio row with its tariff generation into a
    :class:`~rechner_pipeline.kern.model_point.ModelPoint` and returns
    ``berechne(mp)`` in the golden-master contract shape — same format as
    :func:`run_kernel_for_contract`, without subprocess or scratch files.

    The output is reporting-date independent (a pure function of the model
    point): a Fortschreibung over several Stichtage calls this ONCE per
    contract and indexes per Stichtag via :func:`fortschreibungswerte`.
    """
    mp = ModelPoint(**model_point_kwargs(row, generation_fields))
    return berechne(mp)




def fortschreibungswerte(
    outputs: Mapping[str, Any], months_exp: int, *, prefix: Optional[str] = None
) -> Dict[str, Any]:
    """Pick the reporting-date values from kernel outputs (no own formulas).

    The kernel's table rows are per completed contract year; the row for
    ``months_exp // 12`` is the state at the reporting date. Scalars pass
    through unchanged. Without an explicit ``prefix`` the output must contain
    exactly one table prefix — ambiguity (a future multi-product kernel) is
    an error, never a silent first-key pick.
    """
    jahr = int(months_exp) // 12
    tables = outputs.get("tables", {})
    if prefix is None:
        if len(tables) != 1:
            raise KernlaufError(
                f"Mehrdeutiger Kernel-Output: {len(tables)} Tabellen-Prefixe "
                f"({sorted(tables)}) — prefix explizit angeben"
            )
        prefix = next(iter(tables))
    rows = tables.get(prefix, [])
    if not 0 <= jahr < len(rows):
        raise KernlaufError(
            f"Kein Tabellenjahr {jahr} in Kernel-Output (Zeilen: {len(rows)})"
        )
    scalars = outputs.get("scalars", {})
    return {
        "jahr": jahr,
        "zeile": dict(rows[jahr]),
        "skalare": dict(scalars.get(prefix, {})),
    }
