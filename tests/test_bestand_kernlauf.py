"""Kernel coupling: ModelPoint mapping, inputs.py rendering, confined kernel run.

The end-to-end tests need a generated kernel (``runs/generated``, transient) and
skip honestly when none is present.

Knoten: klv
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from rechner_pipeline.bestand.kernlauf import (
    KernlaufError,
    berechne_vertrag,
    fortschreibungswerte,
)
from rechner_pipeline.models.bestand import (
    MODEL_POINT_FIELDS,
    model_point_kwargs,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

_ROW = {
    "entry_age": 45,
    "sex": "M",
    "duration": 30,
    "premium_duration": 20,
    "sum_insured": 100000.0,
    "zahlweise": 12,
}
_GENERATION = {
    "zins": 0.0175,
    "tafel": "DAV1994_T",
    "alpha": 0.025,
    "beta1": 0.025,
    "gamma1": 0.0008,
    "gamma2": 0.00125,
    "gamma3": 0.0025,
    "policy_fee": 24.0,
    "min_alter_flex": 60,
    "min_rlz_flex": 5,
}


def test_model_point_kwargs_covers_contract():
    kwargs = model_point_kwargs(_ROW, _GENERATION)
    assert set(kwargs) == {name for name, _ in MODEL_POINT_FIELDS}
    assert kwargs["x"] == 45 and kwargs["n"] == 30 and kwargs["t"] == 20
    assert kwargs["sum_insured"] == 100000.0 and kwargs["zw"] == 12
    assert kwargs["tafel"] == "DAV1994_T"
    # Tarif-Stellschrauben fehlen in _GENERATION -> Kernel-Defaults (Blattwerte):
    assert kwargs["stoab_max"] == 150.0 and kwargs["zillmer_dauer"] == 5
    # Explizit gesetzte Stellschraube gewinnt gegen den Default:
    kwargs2 = model_point_kwargs(_ROW, dict(_GENERATION, stoab_max=200.0))
    assert kwargs2["stoab_max"] == 200.0


def test_berechne_vertrag_in_process_ueber_stabilen_kern():
    outputs = berechne_vertrag(_ROW, _GENERATION)
    assert set(outputs) == {"scalars", "tables"}
    scalars = outputs["scalars"]["Kalkulation"]
    assert {"Bxt", "BJB", "BZB", "Pxt", "ratzu"} <= set(scalars)
    assert len(outputs["tables"]["Kalkulation"]) == 51
    werte = fortschreibungswerte(outputs, months_exp=61)
    assert werte["jahr"] == 5 and werte["skalare"]["BJB"] == scalars["BJB"]






def test_fortschreibungswerte_picks_contract_year():
    outputs = {
        "scalars": {"Kalkulation": {"BJB": 1.0}},
        "tables": {"Kalkulation": [{"k": 0.0}, {"k": 1.0}, {"k": 2.0}]},
    }
    werte = fortschreibungswerte(outputs, months_exp=25)  # Jahr 2
    assert werte["jahr"] == 2
    assert werte["zeile"] == {"k": 2.0}
    assert werte["skalare"] == {"BJB": 1.0}
    with pytest.raises(Exception):
        fortschreibungswerte(outputs, months_exp=12 * 99)


def test_fortschreibungswerte_mehrdeutiger_prefix_ist_fehler():
    outputs = {
        "scalars": {"A": {"s": 1.0}, "B": {"s": 2.0}},
        "tables": {"A": [{"k": 0.0}], "B": [{"k": 0.0}]},
    }
    with pytest.raises(KernlaufError, match="Mehrdeutig"):
        fortschreibungswerte(outputs, months_exp=0)
    werte = fortschreibungswerte(outputs, months_exp=0, prefix="B")
    assert werte["skalare"] == {"s": 2.0}
