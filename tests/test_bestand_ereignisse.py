"""Ereignis-Engine: Determinismus, Kern-Betraege, Statushistorie, Zeitscheibe.

Die forcierten Tests treiben einzelne Ereignispfade deterministisch (Raten
0 bzw. nahe 1 / tod_faktor extrem); der End-to-End-Test laeuft mit den
Beispiel-Raten ueber den generierten Bestand.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
import pytest

from rechner_pipeline.bestand.config import EreignisConfig, load_config
from rechner_pipeline.bestand.ereignisse import (
    EreignisError,
    bestand_mit_historie,
    fortschreiben,
)
from rechner_pipeline.bestand.generator import generate
from rechner_pipeline.bestand.zeitscheibe import zeitscheibe
from rechner_pipeline.kern import ModelPoint, Rechenkern
from rechner_pipeline.models.bestand import (
    STAMM_SPALTEN,
    STATUS_HISTORIE_NAMES,
    model_point_kwargs,
    validate_statushistorie,
)
from rechner_pipeline.qa.bestand import zeitscheiben_invarianten

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = REPO_ROOT / "examples" / "bestand_klv.toml"


@pytest.fixture(scope="module")
def config():
    return load_config(EXAMPLE)


@pytest.fixture(scope="module")
def portfolio(config):
    return generate(config)


def _mini_stamm(*vertraege: dict) -> pd.DataFrame:
    """Basisbestand aus Vertrags-Kurzangaben (Monatserster-Konvention)."""
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
                "sum_insured": v.get("vs", 100000.0),
                "zahlweise": v.get("zw", 12),
                "insurance_start": start,
                "insurance_end": dt.date(start.year + v["n"], start.month, 1),
                "payment_end": dt.date(start.year + v["t"], start.month, 1),
            }
        )
    df = pd.DataFrame(rows)
    for name, dtype in STAMM_SPALTEN:
        if dtype == "datetime64[ns]":
            df[name] = pd.to_datetime(df[name])
        else:
            df[name] = df[name].astype(dtype)
    return df[[n for n, _ in STAMM_SPALTEN]]


def _mit_raten(config, **raten):
    import copy

    angepasst = copy.copy(config)
    angepasst.ereignisse = EreignisConfig(**raten)
    return angepasst


# --------------------------------------------------------------------------- #
# Determinismus
# --------------------------------------------------------------------------- #


def test_fortschreiben_ist_deterministisch(portfolio, config):
    bis = dt.date(2035, 1, 1)
    h1, l1 = fortschreiben(portfolio, config, bis)
    h2, l2 = fortschreiben(portfolio, config, bis)
    pd.testing.assert_frame_equal(h1, h2)
    pd.testing.assert_frame_equal(l1, l2)
    assert len(h1) > 0
    assert set(h1["status_code"]) <= {"PEX", "STO", "TOD", "ABL"}
    assert (h1["status_date"] <= pd.Timestamp(bis)).all()


def test_horizont_erweiterung_haelt_praefix_konstant(portfolio, config):
    frueh = dt.date(2015, 1, 1)
    h_frueh, l_frueh = fortschreiben(portfolio, config, frueh)
    h_spaet, l_spaet = fortschreiben(portfolio, config, dt.date(2030, 1, 1))
    praefix_h = h_spaet[h_spaet["status_date"] <= pd.Timestamp(frueh)].reset_index(
        drop=True
    )
    praefix_l = l_spaet[l_spaet["status_date"] <= pd.Timestamp(frueh)].reset_index(
        drop=True
    )
    pd.testing.assert_frame_equal(praefix_h, h_frueh)
    pd.testing.assert_frame_equal(praefix_l, l_frueh)


def test_substream_je_vertrag_unabhaengig_vom_bestand(config):
    a = {"police_id": 10000001, "start": dt.date(2005, 4, 1), "x": 40, "n": 25, "t": 20}
    b = {"police_id": 10000002, "start": dt.date(2007, 9, 1), "x": 35, "n": 30, "t": 25}
    cfg = _mit_raten(config, storno_rate=0.5, pex_rate=0.2, tod_faktor=1.0)
    bis = dt.date(2035, 1, 1)
    _, ledger_allein = fortschreiben(_mini_stamm(a), cfg, bis)
    _, ledger_beide = fortschreiben(_mini_stamm(a, b), cfg, bis)
    nur_a = ledger_beide[ledger_beide["police_id"] == a["police_id"]].reset_index(
        drop=True
    )
    pd.testing.assert_frame_equal(nur_a, ledger_allein)


# --------------------------------------------------------------------------- #
# Forcierte Ereignispfade: Betraege kommen exakt aus dem Kern
# --------------------------------------------------------------------------- #


def _kern_fuer(stamm_row: pd.Series, config) -> Rechenkern:
    generation = {
        g.name: g.generation_fields() for g in config.generationen
    }[stamm_row["tarif_generation"]]
    return Rechenkern(ModelPoint(**model_point_kwargs(stamm_row, generation)))


def test_sicherer_tod_zahlt_versicherungssumme(config):
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 6, 1), "x": 45, "n": 30, "t": 20}
    )
    cfg = _mit_raten(config, tod_faktor=1e12)
    historie, ledger = fortschreiben(stamm, cfg, dt.date(2045, 1, 1))
    assert list(historie["status_code"]) == ["TOD"]
    assert list(historie["status_id"]) == [2]
    assert historie["status_date"].iloc[0] == pd.Timestamp(dt.date(2011, 6, 1))
    assert ledger["betrag_art"].iloc[0] == "Todesfallleistung"
    assert ledger["betrag"].iloc[0] == 100000.0
    assert ledger["vertragsjahr"].iloc[0] == 1


def test_sicheres_storno_zahlt_rkw_aus_dem_kern(config):
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 6, 1), "x": 45, "n": 30, "t": 20}
    )
    cfg = _mit_raten(config, storno_rate=0.999999)
    historie, ledger = fortschreiben(stamm, cfg, dt.date(2045, 1, 1))
    assert list(historie["status_code"]) == ["STO"]
    kern = _kern_fuer(stamm.iloc[0], config)
    assert ledger["betrag"].iloc[0] == kern.verlaufszeile(1).rkw
    assert ledger["betrag_art"].iloc[0] == "RKW"


def test_pex_fixiert_vs_bfr_und_ablauf_zahlt_sie_aus(config):
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 6, 1), "x": 45, "n": 20, "t": 15}
    )
    cfg = _mit_raten(config, pex_rate=0.999999)
    historie, ledger = fortschreiben(stamm, cfg, dt.date(2045, 1, 1))
    assert list(historie["status_code"]) == ["PEX", "ABL"]
    assert list(historie["status_id"]) == [2, 3]
    kern = _kern_fuer(stamm.iloc[0], config)
    vs_bfr = kern.beitragsfreie_summe(1)
    assert ledger.iloc[0]["betrag_art"] == "VS_bfr"
    assert ledger.iloc[0]["betrag"] == vs_bfr
    # Der Ablauf des beitragsfreien Vertrags zahlt VS_bfr, nicht die volle VS:
    assert ledger.iloc[1]["ereignis"] == "ABL"
    assert ledger.iloc[1]["betrag"] == vs_bfr
    assert 0.0 < vs_bfr < 100000.0


def test_tod_schlaegt_storno_und_pex(config):
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 6, 1), "x": 45, "n": 30, "t": 20}
    )
    cfg = _mit_raten(config, storno_rate=0.999999, pex_rate=0.999999, tod_faktor=1e12)
    historie, ledger = fortschreiben(stamm, cfg, dt.date(2045, 1, 1))
    assert list(historie["status_code"]) == ["TOD"]
    assert ledger["betrag"].iloc[0] == 100000.0  # beitragspflichtig: volle VS


def test_ohne_raten_nur_deterministischer_ablauf(config):
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2000, 3, 1), "x": 40, "n": 30, "t": 25},
        {"police_id": 10000002, "start": dt.date(2000, 3, 1), "x": 40, "n": 40, "t": 30},
    )
    cfg = _mit_raten(config)  # alle Raten 0
    historie, ledger = fortschreiben(stamm, cfg, dt.date(2035, 1, 1))
    # Vertrag 1 laeuft 2030 ab (<= bis), Vertrag 2 erst 2040 (> bis: kein Event).
    assert list(historie["police_id"]) == [10000001]
    assert list(historie["status_code"]) == ["ABL"]
    assert historie["status_date"].iloc[0] == pd.Timestamp(dt.date(2030, 3, 1))
    assert ledger["betrag"].iloc[0] == 100000.0


def test_unbekannte_tarifgeneration_ist_fehler(config):
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 6, 1), "x": 45, "n": 30,
         "t": 20, "tarif_generation": "GIBTS-NICHT"}
    )
    with pytest.raises(EreignisError, match="GIBTS-NICHT"):
        fortschreiben(stamm, config, dt.date(2020, 1, 1))


# --------------------------------------------------------------------------- #
# Statushistorie-Contract und Zeitscheiben-Integration
# --------------------------------------------------------------------------- #


def test_statushistorie_validiert_gegen_stamm(portfolio, config):
    historie, _ = fortschreiben(portfolio, config, dt.date(2035, 1, 1))
    assert list(historie.columns) == list(STATUS_HISTORIE_NAMES)
    assert validate_statushistorie(portfolio, historie) == []


def test_tod_nach_pex_zahlt_beitragsfreie_summe(portfolio, config):
    """Statistische Abdeckung im Beispielbestand: jeder Tod nach PEX zahlt
    exakt die bei PEX fixierte beitragsfreie Summe."""
    _, ledger = fortschreiben(portfolio, config, dt.date(2045, 1, 1))
    pex = ledger[ledger["ereignis"] == "PEX"].set_index("police_id")["betrag"]
    tod_nach_pex = ledger[
        (ledger["ereignis"].isin(["TOD", "ABL"]))
        & (ledger["police_id"].isin(pex.index))
    ]
    assert len(tod_nach_pex) > 0  # der Beispielbestand deckt den Pfad ab
    for _, zeile in tod_nach_pex.iterrows():
        assert zeile["betrag"] == pex.loc[zeile["police_id"]]


def test_zeitscheibe_laesst_terminale_vertraege_fallen(config):
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 6, 1), "x": 45, "n": 30, "t": 20}
    )
    cfg = _mit_raten(config, tod_faktor=1e12)  # TOD am 2011-06-01
    historie, _ = fortschreiben(stamm, cfg, dt.date(2045, 1, 1))
    sicht = bestand_mit_historie(stamm, historie)
    davor = zeitscheibe(sicht, dt.date(2011, 5, 1))
    danach = zeitscheibe(sicht, dt.date(2011, 6, 1))
    assert list(davor["police_id"]) == [10000001]
    assert davor["status_code"].iloc[0] == "POL"
    assert len(danach) == 0


def test_zeitscheibe_behaelt_beitragsfreie_vertraege(config):
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 6, 1), "x": 45, "n": 20, "t": 15}
    )
    cfg = _mit_raten(config, pex_rate=0.999999)  # PEX am 2011-06-01
    historie, _ = fortschreiben(stamm, cfg, dt.date(2045, 1, 1))
    sicht = bestand_mit_historie(stamm, historie)
    scheibe = zeitscheibe(sicht, dt.date(2015, 1, 1))
    assert list(scheibe["police_id"]) == [10000001]
    assert scheibe["status_code"].iloc[0] == "PEX"
    assert scheibe["status_id"].iloc[0] == 2
    # Zeitachse bleibt die des Vertrags, nicht des Status:
    assert scheibe["months_exp"].iloc[0] == 55  # 2010-06 -> 2015-01


def test_zeitscheiben_invarianten_gelten_auch_mit_historie(portfolio, config):
    historie, _ = fortschreiben(portfolio, config, dt.date(2035, 1, 1))
    sicht = bestand_mit_historie(portfolio, historie)
    scheibe = zeitscheibe(sicht, dt.date(2020, 7, 1))
    assert zeitscheiben_invarianten(sicht, scheibe) == []


def test_bestand_mit_historie_wiederholt_stammdaten_bytegleich(config):
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 6, 1), "x": 45, "n": 20, "t": 15}
    )
    cfg = _mit_raten(config, pex_rate=0.999999)
    historie, _ = fortschreiben(stamm, cfg, dt.date(2045, 1, 1))
    sicht = bestand_mit_historie(stamm, historie)
    assert len(sicht) == 3  # POL + PEX + ABL
    stammfelder = [
        c for c in sicht.columns
        if c not in ("status_id", "status_code", "status_date")
    ]
    for spalte in stammfelder:
        assert sicht[spalte].nunique() == 1, spalte


def test_ereignis_config_validierung():
    assert EreignisConfig().validate() == []
    fehler = EreignisConfig(storno_rate=1.0, pex_rate=-0.1, tod_faktor=-1.0).validate()
    assert len(fehler) == 3


def test_beispiel_config_laedt_ereignisse(config):
    assert config.ereignisse.storno_rate == 0.03
    assert config.ereignisse.pex_rate == 0.01
    assert config.ereignisse.tod_faktor == 1.0
    assert config.validate() == []


def test_fehlende_ereignisse_sektion_liefert_nur_ablauf_defaults(tmp_path):
    quelle = EXAMPLE.read_text(encoding="utf-8")
    ohne = quelle[: quelle.index("[ereignisse]")]
    p = tmp_path / "ohne_ereignisse.toml"
    p.write_text(ohne, encoding="utf-8")
    cfg = load_config(p)
    assert cfg.ereignisse == EreignisConfig()
    assert cfg.validate() == []


# --------------------------------------------------------------------------- #
# Review-Fixes: Eingangs-Haertung und Draw-Disziplin
# --------------------------------------------------------------------------- #


def test_fortschreiben_lehnt_nicht_basisbestand_ab(config):
    """Review-Fix (HOCH): Scheiben/Historie-Sichten duerfen nicht erneut
    fortgeschrieben werden — die Engine wuerde ab insurance_start neu
    simulieren und z. B. Storno nach PEX buchen."""
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 6, 1), "x": 45, "n": 20, "t": 15}
    )
    cfg = _mit_raten(config, pex_rate=0.999999)
    historie, _ = fortschreiben(stamm, cfg, dt.date(2045, 1, 1))
    sicht = bestand_mit_historie(stamm, historie)
    with pytest.raises(EreignisError, match="Basisbestand"):
        fortschreiben(sicht[sicht["status_code"] == "PEX"], cfg, dt.date(2045, 1, 1))


def test_fortschreiben_lehnt_kaputte_eingaben_ab(config):
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 6, 1), "x": 45, "n": 30, "t": 20}
    )
    with pytest.raises(EreignisError, match="nicht eindeutig"):
        fortschreiben(pd.concat([stamm, stamm]), config, dt.date(2020, 1, 1))
    stamm_null = stamm.assign(police_id=pd.Series([0], dtype="int64"))
    with pytest.raises(EreignisError, match="police_id <= 0"):
        fortschreiben(stamm_null, config, dt.date(2020, 1, 1))
    cfg = _mit_raten(config, storno_rate=1.5)
    with pytest.raises(EreignisError, match="storno_rate"):
        fortschreiben(stamm, cfg, dt.date(2020, 1, 1))
    lang = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 6, 1), "x": 20, "n": 60, "t": 40}
    )
    with pytest.raises(EreignisError, match="duration > 50"):
        fortschreiben(lang, config, dt.date(2020, 1, 1))


def test_fortschreiben_normalisiert_bis_timestamp(config):
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2000, 3, 1), "x": 40, "n": 30, "t": 25}
    )
    cfg = _mit_raten(config)
    _, ledger_date = fortschreiben(stamm, cfg, dt.date(2035, 1, 1))
    _, ledger_ts = fortschreiben(stamm, cfg, pd.Timestamp("2035-01-01"))
    pd.testing.assert_frame_equal(ledger_date, ledger_ts)


def test_kern_fehler_traegt_police_kontext(config):
    """Review-Fix: Kern-Fehler (z. B. Tafel ueber MAX_ALTER hinaus) nennen
    die ausloesende Police."""
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 6, 1), "x": 120, "n": 10, "t": 5}
    )
    # Winziger Faktor: der Vertrag ueberlebt sicher bis zur Tafelgrenze,
    # qx_at(124) wirft dann IndexError — gewrappt mit Police-Kontext.
    cfg = _mit_raten(config, tod_faktor=1e-12)
    with pytest.raises(EreignisError, match="police 10000001"):
        fortschreiben(stamm, cfg, dt.date(2045, 1, 1))
    # Mit abgeschalteter Todes-Simulation wird die Tafel nicht angefasst:
    ohne_tod = _mit_raten(config)
    historie, ledger = fortschreiben(stamm, ohne_tod, dt.date(2045, 1, 1))
    assert list(historie["status_code"]) == ["ABL"]


def test_rate_null_und_winzige_rate_ziehen_gleiche_draws(config):
    """Review-Fix (Common Random Numbers): eine Rate von 0 verbraucht ihren
    Draw trotzdem — die Null-Baseline ist pfadweise vergleichbar."""
    a = {"police_id": 10000001, "start": dt.date(2005, 4, 1), "x": 40, "n": 30, "t": 25}
    b = {"police_id": 10000002, "start": dt.date(2007, 9, 1), "x": 35, "n": 30, "t": 25}
    stamm = _mini_stamm(a, b)
    bis = dt.date(2040, 1, 1)
    basis = _mit_raten(config, storno_rate=0.0, pex_rate=0.01, tod_faktor=1.0)
    winzig = _mit_raten(config, storno_rate=1e-300, pex_rate=0.01, tod_faktor=1.0)
    _, ledger_basis = fortschreiben(stamm, basis, bis)
    _, ledger_winzig = fortschreiben(stamm, winzig, bis)
    pd.testing.assert_frame_equal(ledger_basis, ledger_winzig)


def test_ledger_und_historie_sind_parquet_persistierbar(tmp_path, portfolio, config):
    from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio

    historie, ledger = fortschreiben(portfolio, config, dt.date(2035, 1, 1))
    h_pfad = write_portfolio(historie, tmp_path / "historie.parquet")
    l_pfad = write_portfolio(ledger, tmp_path / "ledger.parquet")
    h_zurueck = read_portfolio(h_pfad)
    l_zurueck = read_portfolio(l_pfad)
    pd.testing.assert_frame_equal(h_zurueck, historie)
    pd.testing.assert_frame_equal(l_zurueck, ledger)


def test_validate_portfolio_faengt_nan(portfolio):
    from rechner_pipeline.models.bestand import validate_portfolio

    kaputt = portfolio.copy()
    kaputt.loc[kaputt.index[0], "sum_insured"] = float("nan")
    fehler = validate_portfolio(kaputt)
    assert any("NaN" in f for f in fehler)


def test_max_endalter_hinter_tafelgrenze_ist_config_fehler(config):
    import copy

    kaputt = copy.deepcopy(config)
    kaputt.generationen[0].max_endalter = 110  # DAV1994_T: Dx = 0 ab Alter 101
    fehler = kaputt.validate()
    assert any("Tafel-Erschoepfung" in f for f in fehler)


def test_kern_verlaufszeile_ausserhalb_blattbereich_faellt_schnell():
    from rechner_pipeline.kern import KLV_DEFAULT

    kern = Rechenkern(KLV_DEFAULT)
    with pytest.raises(ValueError, match="0..50"):
        kern.verlaufszeile(51)
    with pytest.raises(ValueError, match="0..50"):
        kern.verlaufszeile(-1)
