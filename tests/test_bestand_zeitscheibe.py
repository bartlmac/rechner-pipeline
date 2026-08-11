"""Zeitscheibe: month arithmetic, 6-month age rounding, selection, invariants."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from rechner_pipeline.bestand.config import load_config
from rechner_pipeline.bestand.generator import generate
from rechner_pipeline.bestand.zeitscheibe import derived_age, months_between, zeitscheibe
from rechner_pipeline.qa.bestand import zeitscheiben_invarianten

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = REPO_ROOT / "examples" / "bestand_klv.toml"


@pytest.fixture(scope="module")
def portfolio():
    return generate(load_config(EXAMPLE))


def test_months_between_full_months_only():
    assert months_between(dt.date(2000, 1, 1), dt.date(2000, 3, 1)) == 2
    assert months_between(dt.date(2000, 1, 1), dt.date(2000, 3, 15)) == 2
    assert months_between(dt.date(2000, 1, 15), dt.date(2000, 3, 1)) == 1
    assert months_between(dt.date(2000, 3, 1), dt.date(2000, 1, 1)) == -2


def test_derived_age_six_month_rounding():
    # 5 volle Monate -> (5+1)/12 = 0.5 -> rundet AB (Referenz-Semantik)
    assert derived_age(40, 5) == 40
    # 6 volle Monate -> (6+1)/12 ≈ 0.583 -> rundet AUF
    assert derived_age(40, 6) == 41
    assert derived_age(40, 11) == 41
    assert derived_age(40, 17) == 41  # (17+1)/12 = 1.5 -> ab
    assert derived_age(40, 18) == 42


def test_zeitscheibe_selects_only_active_contracts(portfolio):
    stichtag = dt.date(2010, 6, 30)
    scheibe = zeitscheibe(portfolio, stichtag)
    assert (scheibe["insurance_start"].dt.date <= stichtag).all()
    assert (scheibe["insurance_end"].dt.date > stichtag).all()
    # Vertraege, die erst spaeter beginnen, sind nicht enthalten:
    spaeter = portfolio[portfolio["insurance_start"].dt.date > stichtag]
    assert set(spaeter["police_id"]).isdisjoint(set(scheibe["police_id"]))


def test_zeitscheibe_derives_consistent_fields(portfolio):
    stichtag = dt.date(2010, 6, 30)
    scheibe = zeitscheibe(portfolio, stichtag)
    row = scheibe.iloc[0]
    start = row["insurance_start"].date()
    assert row["months_exp"] == months_between(start, stichtag)
    assert row["age"] == derived_age(int(row["entry_age"]), int(row["months_exp"]))
    assert (scheibe["months_exp"] >= 0).all()
    assert (scheibe["months_rem"] >= 1).all()


def test_zeitscheiben_invarianten_pass_for_real_slice(portfolio):
    scheibe = zeitscheibe(portfolio, dt.date(2012, 1, 1))
    assert zeitscheiben_invarianten(portfolio, scheibe) == []


def test_zeitscheiben_invarianten_catch_mutation(portfolio):
    scheibe = zeitscheibe(portfolio, dt.date(2012, 1, 1))
    kaputt = scheibe.copy()
    kaputt.loc[kaputt.index[0], "sum_insured"] += 1.0
    errors = zeitscheiben_invarianten(portfolio, kaputt)
    assert any("Stammfelder veraendert" in e and "sum_insured" in e for e in errors)


def test_zeitscheiben_invarianten_catch_invented_policy(portfolio):
    scheibe = zeitscheibe(portfolio, dt.date(2012, 1, 1))
    kaputt = scheibe.copy()
    kaputt.loc[kaputt.index[0], "police_id"] = 999_999_999
    errors = zeitscheiben_invarianten(portfolio, kaputt)
    assert any("erfundene police_ids" in e for e in errors)
