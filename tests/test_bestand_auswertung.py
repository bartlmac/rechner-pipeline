"""Aktuarielle Auswertungen: Kern-Treue der Werte, Aggregation, PEX-Pfad.

Knoten: klv
"""

from __future__ import annotations

import copy
import datetime as dt
from pathlib import Path

import pandas as pd
import pytest

from rechner_pipeline.bestand.auswertung import (
    auswertungs_verlauf,
    vertragswerte,
)
from rechner_pipeline.bestand.config import Annahme, Annahmen, load_config
from rechner_pipeline.bestand.ereignisse import fortschreiben
from rechner_pipeline.bestand.generator import generate
from rechner_pipeline.bestand.fuehrung import schnitt_am
from rechner_pipeline.kern import ModelPoint, Rechenkern
from rechner_pipeline.models.bestand import STAMM_SPALTEN, model_point_kwargs

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = REPO_ROOT / "configs" / "bestand_klv.toml"


@pytest.fixture(scope="module")
def config():
    return load_config(EXAMPLE)


@pytest.fixture(scope="module")
def portfolio(config):
    return generate(config)


@pytest.fixture(scope="module")
def fortschreibung(portfolio, config):
    return fortschreiben(portfolio, config, dt.date(2035, 1, 1))


def _mini_stamm(*vertraege: dict) -> pd.DataFrame:
    rows = []
    for v in vertraege:
        start = v["start"]
        rows.append(
            {
                "police_id": v["police_id"],
                "tarif_generation": v.get("tarif_generation", "KLV-1994"),
                "status_id": 1,
                "status_code": "POL",
                "status_date": start,
                "sex": v.get("sex", "M"),
                "date_of_birth": dt.date(start.year - v["x"], start.month, 1),
                "entry_age": v["x"],
                "duration": v["n"],
                "premium_duration": v["t"],
                "produkt": v.get("produkt", "klv"),
                "sum_insured": v.get("vs", 100000.0),
                "bu_rente": v.get("bu_rente", 0.0),
                "zahlweise": v.get("zw", 12),
                "insurance_start": start,
                "insurance_end": dt.date(start.year + v["n"], start.month, 1),
                "payment_end": dt.date(start.year + v["t"], start.month, 1),
                # Eigenes Geschaeft: Zugang = Beginn. "zugang"
                # uebersteuert fuer uebernommene Vertraege.
                "bestandszugang": v.get("zugang", start),
            }
        )
    df = pd.DataFrame(rows)
    for name, dtype in STAMM_SPALTEN:
        if dtype == "datetime64[ns]":
            df[name] = pd.to_datetime(df[name])
        else:
            df[name] = df[name].astype(dtype)
    return df[[n for n, _ in STAMM_SPALTEN]]


def _kern(stamm_row: pd.Series, config) -> Rechenkern:
    generation = {
        g.name: g.generation_fields() for g in config.generationen
    }[stamm_row["tarif_generation"]]
    return Rechenkern(ModelPoint(**model_point_kwargs(stamm_row, generation)))


def test_vertragswerte_pol_entsprechen_kernzeile(config):
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 6, 1), "x": 45, "n": 30, "t": 20}
    )
    kern = _kern(stamm.iloc[0], config)
    werte = vertragswerte(kern, months_exp=125)  # Vertragsjahr 10
    zeile = kern.verlaufszeile(10)
    assert werte["jahr"] == 10 and werte["status"] == "POL"
    assert werte["deckungskapital"] == zeile.drx_bpfl
    assert werte["rueckkaufswert"] == zeile.rkw
    assert werte["vs_bfr"] == 0.0


def test_vertragswerte_pex_nutzen_beitragsfreie_reserve(config):
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 6, 1), "x": 45, "n": 30, "t": 20}
    )
    kern = _kern(stamm.iloc[0], config)
    werte = vertragswerte(kern, months_exp=125, pex_jahr=4)
    assert werte["status"] == "PEX"
    assert werte["deckungskapital"] == kern.reserve_beitragsfrei(4, 10)
    assert werte["vs_bfr"] == kern.beitragsfreie_summe(4)
    assert werte["rueckkaufswert"] == 0.0


def test_auswertungs_verlauf_ohne_historie_summiert_kernwerte(config):
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 6, 1), "x": 45, "n": 30, "t": 20},
        {"police_id": 10000002, "start": dt.date(2012, 3, 1), "x": 40, "n": 25,
         "t": 20, "vs": 50000.0, "sex": "F"},
    )
    stichtag = dt.date(2020, 1, 1)
    reihe = auswertungs_verlauf(stamm, None, config, [stichtag])
    scheibe = schnitt_am(stamm, stichtag)
    erwartet_dk = sum(
        _kern(stamm.iloc[i], config).zustand_am(int(m)).drx_bpfl
        for i, m in enumerate(scheibe["months_exp"])
    )
    assert reihe[0]["vertraege"] == 2
    assert reihe[0]["deckungskapital"] == pytest.approx(erwartet_dk, rel=1e-12)
    assert reihe[0]["deckungskapital_bfr"] == 0.0
    assert reihe[0]["vs_bfr"] == 0.0


def test_auswertungs_verlauf_pex_pfad_deterministisch(config):
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 6, 1), "x": 45, "n": 20, "t": 15}
    )
    import copy

    cfg = copy.copy(config)
    cfg.annahmen = Annahmen(beitragsfreistellung=Annahme(a=0.999999, b=0.0))  # PEX im Vertragsjahr 1
    historie, _, *_ = fortschreiben(stamm, cfg, dt.date(2035, 1, 1))
    stichtag = dt.date(2020, 1, 1)  # Vertragsjahr 9, beitragsfrei seit Jahr 1
    reihe = auswertungs_verlauf(stamm, historie, cfg, [stichtag])
    kern = _kern(stamm.iloc[0], config)
    assert reihe[0]["vertraege"] == 1
    assert reihe[0]["deckungskapital"] == pytest.approx(
        kern.reserve_beitragsfrei(1, 9), rel=1e-12
    )
    assert reihe[0]["deckungskapital_bfr"] == reihe[0]["deckungskapital"]
    assert reihe[0]["vs_bfr"] == pytest.approx(kern.beitragsfreie_summe(1), rel=1e-12)
    assert reihe[0]["rueckkaufswert"] == 0.0


def test_auswertungs_verlauf_beispielbestand(portfolio, config, fortschreibung):
    historie, _, *_ = fortschreibung
    stichtage = [dt.date(2015, 1, 1), dt.date(2025, 1, 1)]
    reihe = auswertungs_verlauf(portfolio, historie, config, stichtage)
    assert [r["stichtag"] for r in reihe] == [s.isoformat() for s in stichtage]
    for r in reihe:
        assert r["deckungskapital"] > 0
        assert 0 <= r["deckungskapital_bfr"] <= r["deckungskapital"]
        assert r["rueckkaufswert"] > 0
    # Beispielraten erzeugen beitragsfreie Vertraege bis 2015:
    assert reihe[0]["vs_bfr"] > 0
    # Determinismus:
    nochmal = auswertungs_verlauf(portfolio, historie, config, stichtage)
    assert nochmal == reihe


def test_auswertung_pex_versatz_der_scheiben(config):
    """Review-Fix, maschinell gesichert: Scheiben laufen nach PEX mit ihrem eigenen
    Jahresversatz beitragsfrei weiter (hand-konstruiertes, validiertes Paar)."""
    import dataclasses

    from rechner_pipeline.models.bestand import validate_scheiben, validate_statushistorie

    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 6, 1), "x": 45, "n": 20, "t": 15}
    )
    scheiben = pd.DataFrame(
        {
            "police_id": pd.Series([10000001], dtype="int64"),
            "scheiben_id": pd.Series([1], dtype="int64"),
            "erhoehung_jahr": pd.Series([2], dtype="int64"),
            "erhoehung_datum": pd.to_datetime([dt.date(2012, 6, 1)]),
            "entry_age": pd.Series([47], dtype="int64"),
            "duration": pd.Series([18], dtype="int64"),
            "premium_duration": pd.Series([13], dtype="int64"),
            "sum_insured": pd.Series([5000.0], dtype="float64"),
            # Schicht-eigene Rechnungsgrundlage (ADR-011): Tarifwerk-Regel
            # der Scheibe ist gamma1 = 0 (Bezugsgroesse bleibt die GrundVS).
            "gamma1": pd.Series([0.0], dtype="float64"),
        }
    )
    historie = pd.DataFrame(
        {
            "police_id": pd.Series([10000001], dtype="int64"),
            "status_id": pd.Series([2], dtype="int64"),
            "status_code": pd.Series(["PEX"], dtype=object),
            "status_date": pd.to_datetime([dt.date(2013, 6, 1)]),  # PEX Jahr 3
        }
    )
    assert validate_scheiben(stamm, scheiben, historie=historie) == []
    assert validate_statushistorie(stamm, historie) == []

    stichtag = dt.date(2016, 1, 1)  # Vertragsjahr 5, Scheibenjahr 3
    reihe = auswertungs_verlauf(stamm, historie, config, [stichtag], scheiben=scheiben)
    grund = _kern(stamm.iloc[0], config)
    scheiben_kern = Rechenkern(
        dataclasses.replace(
            grund.mp, x=47, n=18, t=13, sum_insured=5000.0, gamma1=0.0
        )
    )
    erwartet_dk = grund.reserve_beitragsfrei(3, 5) + scheiben_kern.reserve_beitragsfrei(1, 3)
    erwartet_vs = grund.beitragsfreie_summe(3) + scheiben_kern.beitragsfreie_summe(1)
    assert reihe[0]["deckungskapital"] == pytest.approx(erwartet_dk, rel=1e-12)
    assert reihe[0]["vs_bfr"] == pytest.approx(erwartet_vs, rel=1e-12)
    assert reihe[0]["rueckkaufswert"] == 0.0

    # Scheibe im/nach dem PEX-Jahr: fail-fast statt stiller Unsinn.
    kaputt = scheiben.copy()
    kaputt.loc[0, "erhoehung_jahr"] = 3
    kaputt.loc[0, "erhoehung_datum"] = pd.Timestamp(dt.date(2013, 6, 1))
    kaputt.loc[0, "entry_age"] = 48
    kaputt.loc[0, "duration"] = 17
    kaputt.loc[0, "premium_duration"] = 12
    with pytest.raises(ValueError, match="nicht vor der Beitragsfreistellung"):
        auswertungs_verlauf(stamm, historie, config, [stichtag], scheiben=kaputt)


def test_scheiben_fremder_polizzen_sind_fehler(config):
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 6, 1), "x": 45, "n": 20, "t": 15}
    )
    fremd = pd.DataFrame(
        {
            "police_id": pd.Series([99999999], dtype="int64"),
            "scheiben_id": pd.Series([1], dtype="int64"),
            "erhoehung_jahr": pd.Series([1], dtype="int64"),
            "erhoehung_datum": pd.to_datetime([dt.date(2011, 6, 1)]),
            "entry_age": pd.Series([46], dtype="int64"),
            "duration": pd.Series([19], dtype="int64"),
            "premium_duration": pd.Series([14], dtype="int64"),
            "sum_insured": pd.Series([5000.0], dtype="float64"),
            "gamma1": pd.Series([0.0], dtype="float64"),
        }
    )
    with pytest.raises(ValueError, match="99999999"):
        auswertungs_verlauf(stamm, None, config, [dt.date(2016, 1, 1)], scheiben=fremd)


def test_unbekannte_generation_ist_fehler(config):
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 6, 1), "x": 45, "n": 30,
         "t": 20, "tarif_generation": "GIBTS-NICHT"}
    )
    with pytest.raises(ValueError, match="GIBTS-NICHT"):
        auswertungs_verlauf(stamm, None, config, [dt.date(2020, 1, 1)])
