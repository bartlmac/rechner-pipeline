"""Ereignis-Engine: Determinismus, Kern-Betraege, Statushistorie, Zeitscheibe.

Die forcierten Tests treiben einzelne Ereignispfade deterministisch (Raten
0 bzw. nahe 1 / tod_faktor extrem); der End-to-End-Test laeuft mit den
Beispiel-Raten ueber den generierten Bestand.

Knoten: klv
"""

from __future__ import annotations

import copy
import dataclasses
import datetime as dt
from pathlib import Path

import pandas as pd
import pytest

from rechner_pipeline.bestand.config import (
    ANNAHME_FELDER,
    Annahme,
    Annahmen,
    load_config,
)
from rechner_pipeline.bestand.ereignisse import (
    EreignisError,
    fortschreiben,
)
from rechner_pipeline.bestand.generator import generate
from rechner_pipeline.bestand.fuehrung import journalsicht, schnitt_am
from rechner_pipeline.kern import ModelPoint, Rechenkern
from rechner_pipeline.models.bestand import (
    STAMM_SPALTEN,
    STATUS_HISTORIE_NAMES,
    model_point_kwargs,
    validate_statushistorie,
)
from rechner_pipeline.qa.bestand import auskunfts_invarianten

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = REPO_ROOT / "configs" / "bestand_klv.toml"


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
                "produkt": v.get("produkt", "klv"),
                "sum_insured": v.get("vs", 100000.0),
                "bu_rente": v.get("bu_rente", 0.0),
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
    """Forcierte Erfahrungsannahmen (3. Ordnung) fuer einzelne Pfade.

    Kurzform fuer die Tests: ``storno_rate=0.99`` setzt die Annahme
    ``storno = a 0.99, b 0``; ``tod_faktor=2`` setzt ``tod = a 0, b 2``
    (Marge auf der Tafel erster Ordnung). Nicht genannte Ereignisse
    bleiben auf 0.
    """
    angepasst = copy.copy(config)
    felder = {}
    for name, wert in raten.items():
        if name == "erh_prozent":
            felder["erh_prozent"] = wert
        elif name == "tod_faktor":
            felder["tod"] = Annahme(a=0.0, b=wert)
        else:
            ziel = {"storno_rate": "storno", "pex_rate": "beitragsfreistellung",
                    "erh_rate": "erhoehung"}[name]
            felder[ziel] = Annahme(a=wert, b=0.0)
    angepasst.annahmen = Annahmen(**felder)
    return angepasst


# --------------------------------------------------------------------------- #
# Determinismus
# --------------------------------------------------------------------------- #


def test_fortschreiben_ist_deterministisch(portfolio, config):
    bis = dt.date(2035, 1, 1)
    h1, l1, *_ = fortschreiben(portfolio, config, bis)
    h2, l2, *_ = fortschreiben(portfolio, config, bis)
    pd.testing.assert_frame_equal(h1, h2)
    pd.testing.assert_frame_equal(l1, l2)
    assert len(h1) > 0
    assert set(h1["status_code"]) <= {"PEX", "STO", "TOD", "ABL"}
    assert (h1["status_date"] <= pd.Timestamp(bis)).all()


def test_horizont_erweiterung_haelt_praefix_konstant(portfolio, config):
    frueh = dt.date(2015, 1, 1)
    h_frueh, l_frueh, *_ = fortschreiben(portfolio, config, frueh)
    h_spaet, l_spaet, *_ = fortschreiben(portfolio, config, dt.date(2030, 1, 1))
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
    _, ledger_allein, *_ = fortschreiben(_mini_stamm(a), cfg, bis)
    _, ledger_beide, *_ = fortschreiben(_mini_stamm(a, b), cfg, bis)
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
    historie, ledger, *_ = fortschreiben(stamm, cfg, dt.date(2045, 1, 1))
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
    historie, ledger, *_ = fortschreiben(stamm, cfg, dt.date(2045, 1, 1))
    assert list(historie["status_code"]) == ["STO"]
    kern = _kern_fuer(stamm.iloc[0], config)
    assert ledger["betrag"].iloc[0] == kern.verlaufszeile(1).rkw
    assert ledger["betrag_art"].iloc[0] == "RKW"


def test_pex_fixiert_vs_bfr_und_ablauf_zahlt_sie_aus(config):
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 6, 1), "x": 45, "n": 20, "t": 15}
    )
    cfg = _mit_raten(config, pex_rate=0.999999)
    historie, ledger, *_ = fortschreiben(stamm, cfg, dt.date(2045, 1, 1))
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
    historie, ledger, *_ = fortschreiben(stamm, cfg, dt.date(2045, 1, 1))
    assert list(historie["status_code"]) == ["TOD"]
    assert ledger["betrag"].iloc[0] == 100000.0  # beitragspflichtig: volle VS


def test_ohne_raten_nur_deterministischer_ablauf(config):
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2000, 3, 1), "x": 40, "n": 30, "t": 25},
        {"police_id": 10000002, "start": dt.date(2000, 3, 1), "x": 40, "n": 40, "t": 30},
    )
    cfg = _mit_raten(config)  # alle Raten 0
    historie, ledger, *_ = fortschreiben(stamm, cfg, dt.date(2035, 1, 1))
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
    historie, _, *_ = fortschreiben(portfolio, config, dt.date(2035, 1, 1))
    assert list(historie.columns) == list(STATUS_HISTORIE_NAMES)
    assert validate_statushistorie(portfolio, historie) == []


def test_tod_nach_pex_zahlt_beitragsfreie_summe(portfolio, config):
    """Statistische Abdeckung im Beispielbestand: jeder Tod nach PEX zahlt
    exakt die bei PEX fixierte beitragsfreie Summe."""
    _, ledger, *_ = fortschreiben(portfolio, config, dt.date(2045, 1, 1))
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
    historie, _, *_ = fortschreiben(stamm, cfg, dt.date(2045, 1, 1))
    sicht = journalsicht(stamm, historie)
    davor = schnitt_am(sicht, dt.date(2011, 5, 1))
    danach = schnitt_am(sicht, dt.date(2011, 6, 1))
    assert list(davor["police_id"]) == [10000001]
    assert davor["status_code"].iloc[0] == "POL"
    assert len(danach) == 0


def test_zeitscheibe_behaelt_beitragsfreie_vertraege(config):
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 6, 1), "x": 45, "n": 20, "t": 15}
    )
    cfg = _mit_raten(config, pex_rate=0.999999)  # PEX am 2011-06-01
    historie, _, *_ = fortschreiben(stamm, cfg, dt.date(2045, 1, 1))
    sicht = journalsicht(stamm, historie)
    scheibe = schnitt_am(sicht, dt.date(2015, 1, 1))
    assert list(scheibe["police_id"]) == [10000001]
    assert scheibe["status_code"].iloc[0] == "PEX"
    assert scheibe["status_id"].iloc[0] == 2
    # Zeitachse bleibt die des Vertrags, nicht des Status:
    assert scheibe["months_exp"].iloc[0] == 55  # 2010-06 -> 2015-01


def test_zeitscheiben_invarianten_gelten_auch_mit_historie(portfolio, config):
    historie, _, *_ = fortschreiben(portfolio, config, dt.date(2035, 1, 1))
    sicht = journalsicht(portfolio, historie)
    scheibe = schnitt_am(sicht, dt.date(2020, 7, 1))
    assert auskunfts_invarianten(sicht, scheibe) == []


def test_bestand_mit_historie_wiederholt_stammdaten_bytegleich(config):
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 6, 1), "x": 45, "n": 20, "t": 15}
    )
    cfg = _mit_raten(config, pex_rate=0.999999)
    historie, _, *_ = fortschreiben(stamm, cfg, dt.date(2045, 1, 1))
    sicht = journalsicht(stamm, historie)
    assert len(sicht) == 3  # POL + PEX + ABL
    stammfelder = [
        c for c in sicht.columns
        if c not in ("status_id", "status_code", "status_date")
    ]
    for spalte in stammfelder:
        assert sicht[spalte].nunique() == 1, spalte


# --------------------------------------------------------------------------- #
# Dynamische Erhoehungen (Scheiben)
# --------------------------------------------------------------------------- #


def test_sichere_erhoehung_erzeugt_scheiben_mit_zinseszins(config):
    from rechner_pipeline.models.bestand import validate_scheiben

    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 6, 1), "x": 45, "n": 20, "t": 15}
    )
    cfg = _mit_raten(config, erh_rate=0.999999, erh_prozent=0.05)
    historie, ledger, scheiben, *_ = fortschreiben(stamm, cfg, dt.date(2045, 1, 1))
    # Jede Annahme erhoeht um 5% der aktuellen Gesamt-VS (Zinseszins),
    # solange Beitraege laufen (j+1 < t): Scheiben in den Jahren 1..14.
    assert list(scheiben["erhoehung_jahr"]) == list(range(1, 15))
    assert list(scheiben["scheiben_id"]) == list(range(1, 15))
    for k, betrag in enumerate(scheiben["sum_insured"]):
        assert betrag == pytest.approx(100000.0 * 0.05 * 1.05 ** k, rel=1e-12)
    # Scheiben-Konsistenz gegen den Hauptvertrag:
    assert validate_scheiben(stamm, scheiben) == []
    # ERH ist GeVo, kein Statuswechsel — Historie kennt nur den Ablauf:
    assert list(historie["status_code"]) == ["ABL"]
    # Ablauf zahlt die Gesamt-VS ueber alle Scheiben:
    abl = ledger[ledger["ereignis"] == "ABL"]["betrag"].iloc[0]
    assert abl == pytest.approx(100000.0 * 1.05 ** 14, rel=1e-12)
    # Ledger fuehrt die ERH-GeVos:
    assert (ledger["ereignis"] == "ERH").sum() == 14
    assert set(ledger[ledger["ereignis"] == "ERH"]["betrag_art"]) == {"VS_erhoehung"}


@pytest.fixture(scope="module")
def beispiel_lauf(portfolio, config):
    return fortschreiben(portfolio, config, dt.date(2045, 1, 1))


def test_abgangsbetraege_summieren_ueber_scheiben(portfolio, config, beispiel_lauf):
    """Statistische Abdeckung im Beispielbestand: STO/PEX nach Erhoehungen
    zahlen exakt die Summe der Kern-Betraege ueber alle Scheiben."""
    _, ledger, scheiben, _ = beispiel_lauf
    haupt = portfolio.set_index("police_id")
    generationen = {g.name: g.generation_fields() for g in config.generationen}

    def kerne(pid):
        h = haupt.loc[pid]
        gen = generationen[str(h["tarif_generation"])]
        grund = Rechenkern(ModelPoint(**model_point_kwargs(h, gen)))
        eigene = scheiben[scheiben["police_id"] == pid]
        s_kerne = []
        for s in eigene.to_dict("records"):
            row = {
                "entry_age": s["entry_age"], "sex": h["sex"],
                "duration": s["duration"], "premium_duration": s["premium_duration"],
                "sum_insured": s["sum_insured"], "zahlweise": h["zahlweise"],
            }
            # Scheiben-Regel des Tarifwerks: gamma1-Bezugsgroesse ist die
            # GrundVS — die Erhoehungsscheibe traegt kein gamma1.
            mp = dataclasses.replace(
                ModelPoint(**model_point_kwargs(row, gen)), gamma1=0.0)
            s_kerne.append((int(s["erhoehung_jahr"]), Rechenkern(mp)))
        return grund, s_kerne

    mit_scheiben = set(scheiben["police_id"])
    geprueft = {"STO": 0, "PEX": 0}
    for zeile in ledger[ledger["ereignis"].isin(["STO", "PEX"])].to_dict("records"):
        pid = int(zeile["police_id"])
        if pid not in mit_scheiben or geprueft[zeile["ereignis"]] >= 3:
            continue
        a = int(zeile["vertragsjahr"])
        grund, s_kerne = kerne(pid)
        relevante = [(j, k) for j, k in s_kerne if j < a]
        if not relevante:
            continue
        if zeile["ereignis"] == "STO":
            from rechner_pipeline.bestand.ereignisse import vertrags_rkw

            erwartet = vertrags_rkw(grund, relevante, a)
        else:
            erwartet = grund.beitragsfreie_summe(a) + sum(
                k.beitragsfreie_summe(a - j) for j, k in relevante
            )
        assert zeile["betrag"] == erwartet, (pid, zeile["ereignis"])
        geprueft[zeile["ereignis"]] += 1
    assert geprueft["STO"] >= 1 and geprueft["PEX"] >= 1  # Pfade sind abgedeckt


def test_auswertung_beruecksichtigt_scheiben(config):
    from rechner_pipeline.bestand.auswertung import auswertungs_verlauf

    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 6, 1), "x": 45, "n": 20, "t": 15}
    )
    cfg = _mit_raten(config, erh_rate=0.999999, erh_prozent=0.05)
    historie, _, scheiben, _ = fortschreiben(stamm, cfg, dt.date(2045, 1, 1))
    stichtag = dt.date(2020, 1, 1)
    ohne = auswertungs_verlauf(stamm, historie, cfg, [stichtag])
    mit = auswertungs_verlauf(stamm, historie, cfg, [stichtag], scheiben=scheiben)
    assert mit[0]["deckungskapital"] > ohne[0]["deckungskapital"]
    assert mit[0]["rueckkaufswert"] > ohne[0]["rueckkaufswert"]


def test_scheiben_parquet_roundtrip(tmp_path, beispiel_lauf):
    from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio

    _, _, scheiben, _ = beispiel_lauf
    assert len(scheiben) > 0
    pfad = write_portfolio(scheiben, tmp_path / "scheiben.parquet")
    pd.testing.assert_frame_equal(read_portfolio(pfad), scheiben)


def test_validate_scheiben_findet_inkonsistenzen(config):
    from rechner_pipeline.models.bestand import validate_scheiben

    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 6, 1), "x": 45, "n": 20, "t": 15}
    )
    cfg = _mit_raten(config, erh_rate=0.999999, erh_prozent=0.05)
    _, _, scheiben, _ = fortschreiben(stamm, cfg, dt.date(2045, 1, 1))
    kaputt = scheiben.copy()
    kaputt.loc[kaputt.index[0], "entry_age"] = 99
    fehler = validate_scheiben(stamm, kaputt)
    assert any("entry_age" in f for f in fehler)
    # NaN in der Erhoehungssumme wird explizit gefangen:
    nan_scheiben = scheiben.copy()
    nan_scheiben.loc[nan_scheiben.index[0], "sum_insured"] = float("nan")
    assert any("NaN" in f for f in validate_scheiben(stamm, nan_scheiben))


def test_validate_scheiben_cross_check_gegen_historie(config):
    """Review-Fix: Scheiben nach PEX/terminalem Status (Tabellen-Mismatch)
    werden mit uebergebener Historie erkannt."""
    from rechner_pipeline.models.bestand import validate_scheiben

    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 6, 1), "x": 45, "n": 20, "t": 15}
    )
    cfg = _mit_raten(config, erh_rate=0.999999, erh_prozent=0.05)
    _, _, scheiben, _ = fortschreiben(stamm, cfg, dt.date(2045, 1, 1))
    # Fremde Historie: PEX am zweiten Jahrestag — Scheiben ab Jahr 2 liegen
    # nicht mehr strikt davor:
    fremde_historie = pd.DataFrame(
        {
            "police_id": pd.Series([10000001], dtype="int64"),
            "status_id": pd.Series([2], dtype="int64"),
            "status_code": pd.Series(["PEX"], dtype=object),
            "status_date": pd.to_datetime([dt.date(2012, 6, 1)]),
        }
    )
    fehler = validate_scheiben(stamm, scheiben, historie=fremde_historie)
    assert any("nicht strikt vor" in f for f in fehler)
    # Mit der eigenen (leeren bzw. konsistenten) Historie: kein Fehler.
    assert validate_scheiben(stamm, scheiben, historie=None) == []


def test_erh_rate_null_und_winzig_ziehen_gleiche_draws(config):
    """Review-Fix: auch der vierte (ERH-)Draw wird bei Rate 0 verbraucht —
    die Null-Baseline bleibt pfadweise vergleichbar."""
    a = {"police_id": 10000001, "start": dt.date(2005, 4, 1), "x": 40, "n": 30, "t": 25}
    b = {"police_id": 10000002, "start": dt.date(2007, 9, 1), "x": 35, "n": 30, "t": 25}
    stamm = _mini_stamm(a, b)
    bis = dt.date(2040, 1, 1)
    basis = _mit_raten(config, storno_rate=0.02, pex_rate=0.01, tod_faktor=1.0,
                       erh_rate=0.0, erh_prozent=0.0)
    winzig = _mit_raten(config, storno_rate=0.02, pex_rate=0.01, tod_faktor=1.0,
                        erh_rate=1e-300, erh_prozent=0.05)
    _, ledger_basis, *_ = fortschreiben(stamm, basis, bis)
    _, ledger_winzig, *_ = fortschreiben(stamm, winzig, bis)
    pd.testing.assert_frame_equal(ledger_basis, ledger_winzig)


def test_scheiben_praefix_bei_horizont_erweiterung(portfolio, config):
    """Review-Fix: auch die Scheiben-Tabelle ist bei bis-Erweiterung ein
    Praefix (fruehere Erhoehungen aendern sich nicht)."""
    frueh = dt.date(2015, 1, 1)
    _, _, s_frueh, _ = fortschreiben(portfolio, config, frueh)
    _, _, s_spaet, _ = fortschreiben(portfolio, config, dt.date(2030, 1, 1))
    praefix = s_spaet[s_spaet["erhoehung_datum"] <= pd.Timestamp(frueh)].reset_index(
        drop=True
    )
    pd.testing.assert_frame_equal(praefix, s_frueh)


def test_annahmen_validierung():
    """Erfahrungsannahmen (3. Ordnung): affine Parameter muessen
    plausibel sein."""
    assert Annahmen().validate() == []
    fehler = Annahmen(
        storno=Annahme(a=1.0, b=0.0),
        beitragsfreistellung=Annahme(a=-0.1, b=0.0),
        tod=Annahme(a=0.0, b=-1.0),
    ).validate()
    assert len(fehler) == 3
    assert Annahmen(erhoehung=Annahme(a=0.3, b=0.0)).validate() == [
        "annahmen: erhoehung mit Rate > 0 verlangt erh_prozent > 0"
    ]


def test_annahme_ist_affine_transformation():
    """annahme = a + b * erste_ordnung, geklemmt auf [0, 1]."""
    # Ereignis MIT Rechnungsgrundlage: b rechnet die Marge heraus.
    assert Annahme(a=0.0, b=0.8)(0.05) == pytest.approx(0.04)
    # Entlastende Ausscheideordnung: b > 1 hebt die erste Ordnung an.
    assert Annahme(a=0.0, b=1.25)(0.06) == pytest.approx(0.075)
    # Ereignis OHNE Rechnungsgrundlage: b = 0, die Rate steht in a.
    assert Annahme(a=0.03, b=0.0)(0.0) == 0.03
    assert Annahme(a=0.03, b=0.0)(0.9) == 0.03   # erste Ordnung wirkt nicht
    # Identitaet und Klemmung:
    assert Annahme()(0.0123) == 0.0123
    assert Annahme(a=0.0, b=2.0)(0.7) == 1.0
    assert Annahme(a=0.0, b=1.0)(0.0) == 0.0


def test_beispiel_config_laedt_annahmen(config):
    """Die Beispiel-Config traegt die Erfahrungsannahmen in affiner Form."""
    a = config.annahmen
    assert a.storno == Annahme(a=0.03, b=0.0)
    assert a.beitragsfreistellung == Annahme(a=0.01, b=0.0)
    # Tod: Marge auf der Tafel erster Ordnung.
    assert a.tod.a == 0.0 and 0.0 < a.tod.b <= 1.0
    assert config.validate() == []


def test_fehlende_annahmen_sektion_liefert_nur_ablauf(tmp_path):
    """Ohne [annahmen] findet kein stochastisches Ereignis statt — eine
    fehlende Annahme ist keine Annahme (insbesondere nicht: erste
    Ordnung unveraendert)."""
    quelle = EXAMPLE.read_text(encoding="utf-8")
    ohne = quelle[: quelle.index("[annahmen]")]
    p = tmp_path / "ohne_annahmen.toml"
    p.write_text(ohne, encoding="utf-8")
    cfg = load_config(p)
    assert cfg.annahmen == Annahmen()
    assert cfg.validate() == []
    for name, _zweck in ANNAHME_FELDER:
        assert getattr(cfg.annahmen, name)(0.5) == 0.0


def test_alte_ereignisse_sektion_wird_sprechend_abgewiesen(tmp_path):
    """Eine Config im alten Format darf nicht still mit Null-Annahmen
    durchlaufen."""
    quelle = EXAMPLE.read_text(encoding="utf-8")
    alt = quelle[: quelle.index("[annahmen]")] + "[ereignisse]\nstorno_rate = 0.03\n"
    p = tmp_path / "alt.toml"
    p.write_text(alt, encoding="utf-8")
    with pytest.raises(ValueError, match=r"\[ereignisse\] wird nicht mehr gelesen"):
        load_config(p)


def test_unbekannte_annahme_ist_ladefehler(tmp_path):
    quelle = EXAMPLE.read_text(encoding="utf-8")
    kaputt = quelle + '\nfantasie = { a = 0.1 }\n'
    p = tmp_path / "kaputt.toml"
    p.write_text(kaputt, encoding="utf-8")
    with pytest.raises(ValueError, match="unbekannte Ereignisarten"):
        load_config(p)


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
    historie, _, *_ = fortschreiben(stamm, cfg, dt.date(2045, 1, 1))
    sicht = journalsicht(stamm, historie)
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
    with pytest.raises(EreignisError, match="annahmen storno"):
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
    _, ledger_date, *_ = fortschreiben(stamm, cfg, dt.date(2035, 1, 1))
    _, ledger_ts, *_ = fortschreiben(stamm, cfg, pd.Timestamp("2035-01-01"))
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
    historie, ledger, *_ = fortschreiben(stamm, ohne_tod, dt.date(2045, 1, 1))
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
    _, ledger_basis, *_ = fortschreiben(stamm, basis, bis)
    _, ledger_winzig, *_ = fortschreiben(stamm, winzig, bis)
    pd.testing.assert_frame_equal(ledger_basis, ledger_winzig)


def test_ledger_und_historie_sind_parquet_persistierbar(tmp_path, portfolio, config):
    from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio

    historie, ledger, *_ = fortschreiben(portfolio, config, dt.date(2035, 1, 1))
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


def test_kern_verlaufszeile_kennt_keinen_blattdeckel_mehr():
    """Kern 3.0.0: der Verlauf endet an Modellpunkt bzw. Tafel-
    Erschoepfung, nicht mehr an Zeile 50 des historischen Excel-Blatts."""
    from rechner_pipeline.kern import KLV_DEFAULT

    kern = Rechenkern(KLV_DEFAULT)
    zeile = kern.verlaufszeile(51)  # vor 3.0.0: ValueError "0..50"
    assert zeile.jahr == 51
    with pytest.raises(ValueError, match="negativ"):
        kern.verlaufszeile(-1)
