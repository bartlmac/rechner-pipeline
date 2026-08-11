"""Bestandsbericht: Kennzahlen-Korrektheit, Determinismus, CLI."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from rechner_pipeline.bestand import report
from rechner_pipeline.bestand.config import load_config
from rechner_pipeline.bestand.generator import generate
from rechner_pipeline.bestand.kennzahlen import (
    generationsnamen,
    jahresraster,
    stichtags_kennzahlen,
    verlauf,
)
from rechner_pipeline.bestand.parquet_io import write_portfolio
from rechner_pipeline.bestand.zeitscheibe import zeitscheibe
from rechner_pipeline.toolbox import bestand_report as cli

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = REPO_ROOT / "examples" / "bestand_klv.toml"


@pytest.fixture(scope="module")
def portfolio():
    return generate(load_config(EXAMPLE))


# --------------------------------------------------------------------------- #
# Kennzahlen
# --------------------------------------------------------------------------- #


def test_jahresraster_spans_contract_period(portfolio):
    raster = jahresraster(portfolio)
    assert raster[0].year == int(portfolio["insurance_start"].dt.year.min())
    assert raster[-1].year == int(portfolio["insurance_end"].dt.year.max())
    assert all(d.month == 1 and d.day == 1 for d in raster)


def test_stichtags_kennzahlen_match_slice(portfolio):
    stichtag = dt.date(2010, 1, 1)
    scheibe = zeitscheibe(portfolio, stichtag)
    kz = stichtags_kennzahlen(scheibe, stichtag)
    assert kz["vertraege"] == len(scheibe)
    assert kz["summe_vs"] == pytest.approx(float(scheibe["sum_insured"].sum()))
    assert sum(kz["generationen"].values()) == len(scheibe)


def test_stichtags_kennzahlen_empty_slice_is_zero(portfolio):
    stichtag = dt.date(1970, 1, 1)
    kz = stichtags_kennzahlen(zeitscheibe(portfolio, stichtag), stichtag)
    assert kz["vertraege"] == 0 and kz["summe_vs"] == 0.0
    assert kz["generationen"] == {}


def test_verlauf_covers_all_stichtage(portfolio):
    stichtage = [dt.date(2000, 1, 1), dt.date(2010, 1, 1), dt.date(2020, 1, 1)]
    reihe = verlauf(portfolio, stichtage)
    assert [r["stichtag"] for r in reihe] == [s.isoformat() for s in stichtage]
    assert all(r["vertraege"] >= 0 for r in reihe)


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def html(portfolio):
    stichtage = [dt.date(j, 1, 1) for j in range(2000, 2021, 5)]
    return report.render_html(portfolio, stichtage=stichtage, quelle_hash="ab" * 32)


def test_render_is_deterministic(portfolio):
    stichtage = [dt.date(2005, 1, 1), dt.date(2012, 1, 1)]
    a = report.render_html(portfolio, stichtage=stichtage)
    b = report.render_html(portfolio, stichtage=stichtage)
    assert a == b  # byte-identisch — Golden-Master-faehig


def test_html_is_self_contained_with_svg(html, portfolio):
    assert html.startswith("<!doctype html>")
    assert html.count("<svg") >= 6  # Verlauf x2, Struktur x3, Scatter
    assert "http://" not in html.split("xmlns")[0]  # keine externen Ressourcen im Kopf
    for gen in generationsnamen(portfolio):
        assert gen in html
    assert "Kennzahlen je Stichtag" in html
    assert "abababab" in html  # gekuerzter Quelle-Hash


def test_html_has_no_meta_commentary(html):
    lower = html.lower()
    for banned in ("ehrlich", "honest"):
        assert banned not in lower


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def test_cli_writes_report(portfolio, tmp_path):
    parquet = write_portfolio(portfolio, tmp_path / "b.parquet")
    out = tmp_path / "bericht.html"
    code = cli.main(
        ["--portfolio", str(parquet), "--out", str(out),
         "--stichtage", "2005-01-01,2012-01-01", "--titel", "KLV-Testbestand"]
    )
    assert code == 0
    text = out.read_text(encoding="utf-8")
    assert "KLV-Testbestand" in text and "<svg" in text


def test_cli_missing_portfolio_exits_2(tmp_path):
    assert cli.main(["--portfolio", str(tmp_path / "fehlt.parquet")]) == 2


def test_cli_bad_stichtag_exits_2(portfolio, tmp_path):
    parquet = write_portfolio(portfolio, tmp_path / "b.parquet")
    assert cli.main(["--portfolio", str(parquet), "--stichtage", "kein-datum"]) == 2
