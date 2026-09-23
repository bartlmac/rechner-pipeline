"""Der Zugangsstrom als Bestand: Determinismus, Schema, Korrelation, Parquet.

Bis ADR-020 prueften diese Tests den Batch-Erzeuger (``generate``): einen
auf einmal gezogenen Bestand ohne Geschichte. Den gibt es nicht mehr. Was
bleibt, ist der Zugangsstrom (``neuzugaenge``), und die Aussagen, die
schon fuer den Batch galten, muessen fuer ihn genauso gelten — nur die
Bestandsgroesse ist keine Vorgabe (``sample_size``) mehr, sondern folgt
aus den Jahreszielen der Generationen.

Knoten: klv
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rechner_pipeline.bestand.config import load_config
from rechner_pipeline.bestand.parquet_io import (
    portfolio_hash,
    read_portfolio,
    write_portfolio,
)
from rechner_pipeline.bestand.stochastik import empirical_spearman
from rechner_pipeline.models.bestand import validate_portfolio
from rechner_pipeline.qa.bestand import sanity_check
from tests.zugangsstrom import bestand_aus_zugangsstrom

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = REPO_ROOT / "configs" / "bestand_klv.toml"


@pytest.fixture(scope="module")
def config():
    return load_config(EXAMPLE)


@pytest.fixture(scope="module")
def portfolio(config):
    return bestand_aus_zugangsstrom(config)


def test_zugangsstrom_ist_seed_deterministisch(config, portfolio):
    again = bestand_aus_zugangsstrom(config)
    assert portfolio.equals(again)


def test_portfolio_passes_schema_validation(portfolio):
    assert validate_portfolio(portfolio) == []


def test_bestandsgroesse_folgt_aus_den_jahreszielen(config, portfolio):
    """Keine Vorgabe mehr, sondern eine Folge: je Generation und
    Kalenderjahr ``round(jahresziel)`` Vertraege, soweit der Jahrgang das
    Verkaufsfenster schneidet. Das ist die Aussage, die ``sample_size``
    frueher als Zahl vorwegnahm."""
    counts = portfolio["tarif_generation"].value_counts()
    for gen in config.generationen:
        erwartet = 0
        for jahr in range(gen.gueltig_von.year, gen.gueltig_bis.year + 1):
            # Rand-Jahrgaenge tragen anteilig: gezogen wird ueber alle zwoelf
            # Monatsersten, behalten nur, was im Fenster liegt.
            erwartet_jahr = int(round(gen.jahresziel(jahr)))
            rows = portfolio[(portfolio["tarif_generation"] == gen.name)
                             & (portfolio["insurance_start"].dt.year == jahr)]
            assert len(rows) <= erwartet_jahr, (gen.name, jahr)
            erwartet += erwartet_jahr
        if gen.neuzugang_pro_jahr == 0:
            assert counts.get(gen.name, 0) == 0, gen.name
        else:
            # Mindestens die vollen Jahrgaenge, hoechstens die Summe.
            assert 0 < counts[gen.name] <= erwartet, (gen.name, counts[gen.name], erwartet)
    assert len(portfolio) == int(counts.sum())


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
        if not len(rows):
            continue
        assert rows["insurance_start"].dt.date.min() >= gen.gueltig_von
        assert rows["insurance_start"].dt.date.max() <= gen.gueltig_bis


def test_beschnittener_strom_ist_exakte_teilmenge(config, portfolio):
    """``bis`` schneidet wie ein Referenzstichtag — und weil der Erzeuger
    draw-then-filter arbeitet, ist der beschnittene Bestand die exakte
    Teilmenge des vollen, nicht eine andere Ziehung."""
    import datetime as dt

    import pandas as pd

    ref = dt.date(2010, 1, 1)
    beschnitten = bestand_aus_zugangsstrom(config, bis=ref)
    erwartet = portfolio[portfolio["insurance_start"] < pd.Timestamp(ref)].reset_index(drop=True)
    pd.testing.assert_frame_equal(beschnitten, erwartet)
    assert 0 < len(beschnitten) < len(portfolio)


def test_sanity_bands_from_example_config(config, portfolio):
    assert sanity_check(portfolio, config.plausibilitaet) == []


def test_sanity_detects_violation(portfolio):
    errors = sanity_check(portfolio, {"entry_age": (30, 40)})
    assert errors  # Beispielbestand hat Alter ausserhalb dieses engen Bandes


def test_date_consistency_validated(portfolio):
    """Review-Fix: validate_portfolio erkennt Datumsfelder, die nicht zu den
    Jahresfeldern passen."""
    import pandas as pd

    kaputt = portfolio.copy()
    kaputt.loc[kaputt.index[0], "insurance_end"] = (
        kaputt.loc[kaputt.index[0], "insurance_end"] + pd.DateOffset(years=1)
    )
    errors = validate_portfolio(kaputt)
    assert any("insurance_end != insurance_start + duration" in e for e in errors)


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
    changed = bestand_aus_zugangsstrom(other)
    assert not changed.equals(portfolio)
