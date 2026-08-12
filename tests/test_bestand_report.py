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
def config():
    return load_config(EXAMPLE)


@pytest.fixture(scope="module")
def portfolio(config):
    return generate(config)


@pytest.fixture(scope="module")
def fortschreibung(portfolio, config):
    from rechner_pipeline.bestand.ereignisse import fortschreiben

    return fortschreiben(portfolio, config, dt.date(2035, 1, 1))


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
# Ereignis-/Abgangs-Sichten
# --------------------------------------------------------------------------- #


def test_ereignis_kennzahlen_summen_und_jahresreihe(fortschreibung):
    from rechner_pipeline.bestand.kennzahlen import (
        EREIGNIS_REIHENFOLGE,
        ereignis_summen,
        ereignisse_je_jahr,
    )

    _, ledger, *_ = fortschreibung
    summen = ereignis_summen(ledger)
    assert [s["ereignis"] for s in summen] == [
        c for c in EREIGNIS_REIHENFOLGE if (ledger["ereignis"] == c).any()
    ]
    for s in summen:
        rows = ledger[ledger["ereignis"] == s["ereignis"]]
        assert s["anzahl"] == len(rows)
        assert s["summe_betrag"] == pytest.approx(float(rows["betrag"].sum()))
    reihe = ereignisse_je_jahr(ledger)
    jahre = [r["jahr"] for r in reihe]
    assert jahre == list(range(jahre[0], jahre[-1] + 1))  # lueckenlos
    assert sum(sum(r[c] for c in EREIGNIS_REIHENFOLGE) for r in reihe) == len(ledger)


def test_status_verlauf_zaehlt_pol_und_pex(portfolio, fortschreibung):
    from rechner_pipeline.bestand.ereignisse import bestand_mit_historie
    from rechner_pipeline.bestand.kennzahlen import status_verlauf
    from rechner_pipeline.bestand.zeitscheibe import zeitscheibe

    historie, _, *_ = fortschreibung
    sicht = bestand_mit_historie(portfolio, historie)
    stichtag = dt.date(2020, 1, 1)
    reihe = status_verlauf(sicht, [stichtag])
    scheibe = zeitscheibe(sicht, stichtag)
    assert reihe[0]["POL"] + reihe[0]["PEX"] == len(scheibe)
    assert reihe[0]["PEX"] > 0  # Beispielraten erzeugen Beitragsfreistellungen


def test_render_mit_historie_zeigt_abgangssichten(portfolio, fortschreibung):
    historie, ledger, *_ = fortschreibung
    stichtage = [dt.date(j, 1, 1) for j in range(2005, 2031, 5)]
    ohne = report.render_html(portfolio, stichtage=stichtage)
    mit = report.render_html(
        portfolio, stichtage=stichtage, historie=historie, ledger=ledger
    )
    assert "Fortschreibung und Abgänge" in mit
    assert "Beitragsfreistellung (PEX)" in mit
    assert "Storno (STO)" in mit
    assert "abgangsbereinigt" in mit
    assert "Fortschreibung und Abgänge" not in ohne  # Default unverändert
    assert mit.count("<svg") == ohne.count("<svg") + 2
    # Determinismus auch mit Historie:
    nochmal = report.render_html(
        portfolio, stichtage=stichtage, historie=historie, ledger=ledger
    )
    assert mit == nochmal


def test_render_historie_ohne_ledger_ist_fehler(portfolio, fortschreibung):
    historie, ledger, *_ = fortschreibung
    with pytest.raises(ValueError, match="gehoeren zusammen"):
        report.render_html(portfolio, historie=historie)
    with pytest.raises(ValueError, match="gehoeren zusammen"):
        report.render_html(portfolio, ledger=ledger)


def test_render_mit_config_zeigt_aktuarielle_kennzahlen(portfolio, config, fortschreibung):
    historie, ledger, *_ = fortschreibung
    stichtage = [dt.date(j, 1, 1) for j in range(2010, 2031, 10)]
    mit = report.render_html(
        portfolio, stichtage=stichtage, historie=historie, ledger=ledger, config=config
    )
    assert "Aktuarielle Kennzahlen je Stichtag" in mit
    assert "Deckungskapital" in mit and "Rückkaufswert" in mit
    ohne = report.render_html(
        portfolio, stichtage=stichtage, historie=historie, ledger=ledger
    )
    assert "Aktuarielle Kennzahlen" not in ohne
    # Auch ohne Historie (reiner Basisbestand) rendert die Sektion:
    basis = report.render_html(portfolio, stichtage=stichtage, config=config)
    assert "Aktuarielle Kennzahlen je Stichtag" in basis
    # Determinismus:
    nochmal = report.render_html(
        portfolio, stichtage=stichtage, historie=historie, ledger=ledger, config=config
    )
    assert mit == nochmal


def test_render_ohne_ereignisse_im_horizont(portfolio, config):
    from rechner_pipeline.bestand.ereignisse import fortschreiben

    frueh = portfolio["insurance_start"].min().date()
    historie, ledger, *_ = fortschreiben(portfolio, config, frueh)
    assert len(ledger) == 0
    html = report.render_html(
        portfolio,
        stichtage=[dt.date(2010, 1, 1)],
        historie=historie,
        ledger=ledger,
    )
    assert "Keine Ereignisse im Berichtszeitraum" in html


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


def test_cli_mit_historie_und_ledger(portfolio, fortschreibung, tmp_path):
    historie, ledger, scheiben = fortschreibung
    parquet = write_portfolio(portfolio, tmp_path / "b.parquet")
    h = write_portfolio(historie, tmp_path / "h.parquet")
    l = write_portfolio(ledger, tmp_path / "l.parquet")
    s = write_portfolio(scheiben, tmp_path / "s.parquet")
    out = tmp_path / "bericht.html"
    code = cli.main(
        ["--portfolio", str(parquet), "--out", str(out),
         "--historie", str(h), "--ledger", str(l), "--scheiben", str(s),
         "--config", str(EXAMPLE),
         "--stichtage", "2010-01-01,2020-01-01,2030-01-01"]
    )
    assert code == 0
    text = out.read_text(encoding="utf-8")
    assert "Fortschreibung und Abgänge" in text
    assert "Aktuarielle Kennzahlen je Stichtag" in text
    assert "Dynamische Erhöhung (ERH)" in text
    # Nur eines von beiden ist ein Fehler:
    assert cli.main(
        ["--portfolio", str(parquet), "--historie", str(h)]
    ) == 2
    # Scheiben ohne Historie ist ein Fehler:
    assert cli.main(
        ["--portfolio", str(parquet), "--scheiben", str(s)]
    ) == 2
    # Fehlende Config-Datei ist ein Fehler:
    assert cli.main(
        ["--portfolio", str(parquet), "--config", str(tmp_path / "fehlt.toml")]
    ) == 2
