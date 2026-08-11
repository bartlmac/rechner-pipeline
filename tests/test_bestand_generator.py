"""Generator: determinism, schema conformance, correlations, Parquet golden."""

from __future__ import annotations

from pathlib import Path

import pytest

from rechner_pipeline.bestand.config import load_config
from rechner_pipeline.bestand.generator import generate
from rechner_pipeline.bestand.parquet_io import (
    portfolio_hash,
    read_portfolio,
    write_portfolio,
)
from rechner_pipeline.bestand.stochastik import empirical_spearman
from rechner_pipeline.models.bestand import validate_portfolio
from rechner_pipeline.qa.bestand import sanity_check

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = REPO_ROOT / "examples" / "bestand_klv.toml"


@pytest.fixture(scope="module")
def config():
    return load_config(EXAMPLE)


@pytest.fixture(scope="module")
def portfolio(config):
    return generate(config)


def test_generate_is_seed_deterministic(config, portfolio):
    again = generate(config)
    assert portfolio.equals(again)


def test_portfolio_passes_schema_validation(portfolio):
    assert validate_portfolio(portfolio) == []


def test_portfolio_sizes_and_generations(config, portfolio):
    assert len(portfolio) == sum(g.sample_size for g in config.generationen)
    counts = portfolio["tarif_generation"].value_counts()
    assert counts["KLV-1994"] == 600
    assert counts["KLV-2008"] == 400


def test_configured_correlation_shows_in_data(portfolio):
    gen1 = portfolio[portfolio["tarif_generation"] == "KLV-1994"]
    rho = empirical_spearman(
        gen1["entry_age"].to_numpy(float), gen1["duration"].to_numpy(float)
    )
    assert rho < -0.25  # konfiguriert: Spearman -0.45 (Klippung schwaecht ab)


def test_contract_constraints_hold(portfolio):
    assert (portfolio["premium_duration"] <= portfolio["duration"]).all()
    endalter = portfolio["entry_age"] + portfolio["duration"]
    assert (endalter <= 85).all()
    starts = portfolio["insurance_start"]
    assert (starts.dt.day == 1).all()


def test_generation_windows_respected(config, portfolio):
    for gen in config.generationen:
        rows = portfolio[portfolio["tarif_generation"] == gen.name]
        assert rows["insurance_start"].dt.date.min() >= gen.gueltig_von
        assert rows["insurance_start"].dt.date.max() <= gen.gueltig_bis


def test_sanity_bands_from_example_config(config, portfolio):
    assert sanity_check(portfolio, config.plausibilitaet) == []


def test_sanity_detects_violation(portfolio):
    errors = sanity_check(portfolio, {"entry_age": (30, 40)})
    assert errors  # Beispielbestand hat Alter ausserhalb dieses engen Bandes


def test_parquet_write_is_byte_deterministic(portfolio, tmp_path):
    p1 = write_portfolio(portfolio, tmp_path / "a.parquet")
    p2 = write_portfolio(portfolio, tmp_path / "b.parquet")
    assert portfolio_hash(p1) == portfolio_hash(p2)


def test_parquet_roundtrip_preserves_data(portfolio, tmp_path):
    p = write_portfolio(portfolio, tmp_path / "r.parquet")
    back = read_portfolio(p)
    assert back.equals(portfolio)


def test_different_seed_changes_portfolio(config, portfolio, tmp_path):
    import dataclasses

    other = dataclasses.replace(config, seed=config.seed + 1)
    changed = generate(other)
    assert not changed.equals(portfolio)
