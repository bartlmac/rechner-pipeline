"""Der stabile KLV-Rechenkern: Golden-Master-Parität, Parametrisierung, Contract.

Der Kern ist die Promotion des am 2026-07-22 agentisch migrierten und
angenommenen Kerns (617/617). Diese Tests verankern:

1. **Parität**: ``berechne(KLV_DEFAULT)`` reproduziert exakt die aus dem
   Quell-Workbook extrahierten Erwartungswerte (Fixtures) — geprüft mit der
   Golden-Master-Engine der Abnahme-Schicht selbst.
2. **Parametrisierung**: andere Modellpunkte (Alter, Geschlecht, Zins, Tafel)
   rechnen ohne Prozess-Substitution — die frühere ``DEFAULT``-Bindung ist weg.
3. **Contract-Konsistenz**: ``ModelPoint`` und die Bestandsschema-Sicht
   ``MODEL_POINT_FIELDS`` bleiben deckungsgleich.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from rechner_pipeline.kern import (
    KLV_DEFAULT,
    MissingMortalityTableError,
    ModelPoint,
    Rechenkern,
    berechne,
)
from rechner_pipeline.kern.kommutation import fuer
from rechner_pipeline.models.bestand import MODEL_POINT_FIELDS, model_point_kwargs
from rechner_pipeline.qa.golden_master import compare, load_expected

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "kern_klv"


# --------------------------------------------------------------------------- #
# 1. Golden-Master-Paritaet (617/617)
# --------------------------------------------------------------------------- #


def test_default_model_point_reproduces_golden_master_exactly():
    expected = load_expected(FIXTURES)
    report = compare(expected, berechne(KLV_DEFAULT))
    assert report.deviations == []
    assert report.unmatched_columns == []
    assert report.ok
    assert report.scalars_tested == 5
    assert report.table_cells_tested == 612  # 5 + 612 = 617/617


def test_scalar_values_known_anchors():
    scalars = berechne(KLV_DEFAULT)["scalars"]["Kalkulation"]
    assert scalars["ratzu"] == 0.05
    assert scalars["BJB"] == pytest.approx(4465.6547026924, abs=1e-8)
    assert scalars["Pxt"] == pytest.approx(0.042392046400377824, abs=1e-12)


# --------------------------------------------------------------------------- #
# 2. Parametrisierung (die fruehere DEFAULT-Bindung ist weg)
# --------------------------------------------------------------------------- #


def test_other_model_points_compute_in_process():
    mp_jung = dataclasses.replace(KLV_DEFAULT, x=30, sum_insured=50000.0)
    mp_frau = dataclasses.replace(KLV_DEFAULT, sex="F")
    bjb_default = berechne(KLV_DEFAULT)["scalars"]["Kalkulation"]["BJB"]
    bjb_jung = berechne(mp_jung)["scalars"]["Kalkulation"]["BJB"]
    bjb_frau = berechne(mp_frau)["scalars"]["Kalkulation"]["BJB"]
    assert bjb_jung != bjb_default  # anderer Vertrag -> anderer Beitrag
    assert bjb_frau != bjb_default  # andere Tafelseite -> anderer Beitrag
    assert bjb_jung < bjb_default   # juenger + kleinere Summe -> kleinerer Beitrag


def test_other_interest_basis_and_table():
    mp_2008 = dataclasses.replace(KLV_DEFAULT, zins=0.0225, tafel="DAV2008_T")
    ergebnis = berechne(mp_2008)
    assert ergebnis["scalars"]["Kalkulation"]["Bxt"] > 0
    assert len(ergebnis["tables"]["Kalkulation"]) == 51


def test_kommutation_cache_reuses_basis():
    a = fuer("M", "DAV1994_T", 0.0175)
    b = fuer("M", "DAV1994_T", 0.0175)
    assert a is b
    c = fuer("F", "DAV1994_T", 0.0175)
    assert c is not a


def test_missing_table_fails_fast():
    with pytest.raises(MissingMortalityTableError, match="DAV9999"):
        berechne(dataclasses.replace(KLV_DEFAULT, tafel="DAV9999_T"))


def test_reserve_row_shape_and_flex_phase():
    kern = Rechenkern(KLV_DEFAULT)
    row0 = kern.reserve_row(0)
    assert set(row0) == {
        "k", "Axn", "axn", "axt", "kVx_bpfl", "kDRx_bpfl", "kVx_bfr",
        "kVx_MRV", "flex. Phase", "StoAb", "RKW", "VS_bfr",
    }
    # Flexible Phase: ab Alter 60 UND Restlaufzeit <= 5 (x=45, n=30 -> a >= 25).
    assert kern.reserve_row(24)["flex. Phase"] == 0.0
    assert kern.reserve_row(25)["flex. Phase"] == 1.0


# --------------------------------------------------------------------------- #
# 3. Contract-Konsistenz mit dem Bestandsschema
# --------------------------------------------------------------------------- #


def test_model_point_matches_bestand_contract_fields():
    fields = [(f.name, f.type) for f in dataclasses.fields(ModelPoint)]
    assert fields == list(MODEL_POINT_FIELDS)


def test_bestand_row_constructs_model_point_directly():
    row = {
        "entry_age": 40, "sex": "F", "duration": 25, "premium_duration": 20,
        "sum_insured": 75000.0, "zahlweise": 12,
    }
    generation = {
        "zins": 0.0225, "tafel": "DAV2008_T", "alpha": 0.025, "beta1": 0.025,
        "gamma1": 0.0008, "gamma2": 0.00125, "gamma3": 0.0025,
        "policy_fee": 30.0, "min_alter_flex": 60, "min_rlz_flex": 5,
    }
    mp = ModelPoint(**model_point_kwargs(row, generation))
    assert mp.x == 40 and mp.sex == "F" and mp.tafel == "DAV2008_T"
    assert berechne(mp)["scalars"]["Kalkulation"]["BJB"] > 0
