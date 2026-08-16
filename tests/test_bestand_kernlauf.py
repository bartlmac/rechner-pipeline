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
    KERNEL_FILES,
    KernlaufError,
    berechne_vertrag,
    fortschreibungswerte,
    run_kernel_for_contract,
)
from rechner_pipeline.models.bestand import (
    MODEL_POINT_FIELDS,
    model_point_kwargs,
    render_inputs_py,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
KERNEL_DIR = REPO_ROOT / "runs" / "generated"

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


def test_render_inputs_py_is_valid_python_with_default():
    source = render_inputs_py(model_point_kwargs(_ROW, _GENERATION))
    namespace: dict = {}
    exec(compile(source, "inputs.py", "exec"), namespace)  # noqa: S102 - Testcode
    default = namespace["DEFAULT"]
    assert default.x == 45 and default.sex == "M" and default.zins == 0.0175
    assert default.policy_fee == 24.0


def test_render_inputs_py_rejects_missing_fields():
    with pytest.raises(ValueError, match="ModelPoint-Felder fehlen"):
        render_inputs_py({"x": 1})


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


_kernel_missing = not all((KERNEL_DIR / f).is_file() for f in KERNEL_FILES)


@pytest.mark.skipif(_kernel_missing, reason="kein generierter Kernel unter runs/generated")
def test_kernel_run_for_default_contract_returns_contract_shape():
    outputs = run_kernel_for_contract(
        _ROW, _GENERATION, repo_root=REPO_ROOT, kernel_dir=KERNEL_DIR
    )
    assert set(outputs) == {"scalars", "tables"}
    scalars = outputs["scalars"]["Kalkulation"]
    assert {"Bxt", "BJB", "BZB", "Pxt", "ratzu"} <= set(scalars)
    rows = outputs["tables"]["Kalkulation"]
    assert len(rows) >= 30  # mind. ein Eintrag je Vertragsjahr
    werte = fortschreibungswerte(outputs, months_exp=61)
    assert werte["jahr"] == 5


@pytest.mark.skipif(_kernel_missing, reason="kein generierter Kernel unter runs/generated")
def test_kernel_run_varies_with_contract():
    outputs_a = run_kernel_for_contract(
        _ROW, _GENERATION, repo_root=REPO_ROOT, kernel_dir=KERNEL_DIR
    )
    row_b = dict(_ROW, entry_age=30, sum_insured=50000.0)
    outputs_b = run_kernel_for_contract(
        row_b, _GENERATION, repo_root=REPO_ROOT, kernel_dir=KERNEL_DIR
    )
    a = outputs_a["scalars"]["Kalkulation"]["BJB"]
    b = outputs_b["scalars"]["Kalkulation"]["BJB"]
    assert a != b  # anderer Vertrag -> andere Beitragswerte


@pytest.mark.skipif(_kernel_missing, reason="kein generierter Kernel unter runs/generated")
def test_in_process_pfad_paritaet_mit_subprozess_kernel():
    """Parity-Gate: stabiler Kern (in-process) vs. transienter Kernel (Subprozess).

    Der transiente Migrations-Kernel rechnet auf der Kommutations-Schiene;
    der stabile Kern seit 2.0.0 produktiv auf dem Zustandsmodell (Wechsel
    per Toleranz-Ueberleitung abgenommen). Der Vergleich laeuft daher in
    der Rundungsklasse der Ueberleitung statt bit-exakt.
    """
    for row in (_ROW, dict(_ROW, entry_age=30, sex="F", sum_insured=50000.0)):
        subprozess = run_kernel_for_contract(
            row, _GENERATION, repo_root=REPO_ROOT, kernel_dir=KERNEL_DIR
        )
        in_process = berechne_vertrag(row, _GENERATION)
        # Symmetrie: gleiche Prefixe, Skalare, Zeilenzahlen und Spalten.
        assert set(in_process["scalars"]) == set(subprozess["scalars"])
        assert set(in_process["tables"]) == set(subprozess["tables"])
        for prefix, scalars in subprozess["scalars"].items():
            assert set(in_process["scalars"][prefix]) == set(scalars)
            for name, wert in scalars.items():
                assert in_process["scalars"][prefix][name] == pytest.approx(
                    wert, rel=1e-12, abs=1e-10
                ), (prefix, name)
        for prefix, rows in subprozess["tables"].items():
            assert len(in_process["tables"][prefix]) == len(rows)
            for j, zeile in enumerate(rows):
                assert set(in_process["tables"][prefix][j]) == set(zeile)
                for spalte, wert in zeile.items():
                    assert in_process["tables"][prefix][j][spalte] == pytest.approx(
                        wert, rel=1e-12, abs=1e-10
                    ), (prefix, j, spalte)
