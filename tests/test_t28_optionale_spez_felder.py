"""T28-04: fehlende Spez-Felder haben wirksame Kern-Defaults.

Die Fuehrung darf eine Config mit anderem Wert weder in der Fuehrungsprobe
noch im engeren Fuehrungswert-Pfad als dieselbe Tarifzelle behandeln.

Knoten: klv
"""

from __future__ import annotations

import datetime as dt
import io
from pathlib import Path

import pandas as pd
import pytest

from rechner_pipeline.bestand.config import config_aus_text
from rechner_pipeline.bestand.migrationszugang import MigrationszugangFehler, fuehrungswerte
from rechner_pipeline.gates.fuehrungsprobe import pruefe_fuehrung
from rechner_pipeline.gates.migrationssuite_lauf import fuehrungswert_rechnen
from rechner_pipeline.kern import ModelPoint, Rechenkern
from rechner_pipeline.models.bestand import (
    GENERATION_FIELDS,
    GENERATION_FIELD_DEFAULTS,
    model_point_kwargs,
)
from rechner_pipeline.spez.schema import StrukturUrteil, TarifSpez, ZellSpez


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_TEXT = (REPO_ROOT / "plv" / "configs" / "bestand_klv.toml").read_text(encoding="utf-8")
STICHTAG = dt.date(2003, 1, 1)
ABWEICHEND = (
    ("stoab_satz", 0.03),
    ("stoab_min", 100.0),
    ("stoab_max", 200.0),
    ("zillmer_dauer", 10),
    ("ratzu_zw2", 0.04),
    ("ratzu_zw4", 0.06),
    ("ratzu_zw12", 0.10),
)


def _welt(feld: str, config_wert=None):
    text = CONFIG_TEXT
    if config_wert is not None:
        anker = "min_rlz_flex = 5"
        assert anker in text
        text = text.replace(anker, f"{anker}\n{feld} = {config_wert}", 1)
    config = config_aus_text(text)
    assert config.validate() == []
    generation = config.generationen[0]
    spez_felder = generation.generation_fields()
    del spez_felder[feld]
    spez = TarifSpez(
        generation=generation.knoten, familie="klv",
        urteil=StrukturUrteil(ergebnis="parametrierung",
                              begruendung=["synthetischer Default-Vergleich"]),
        zellen=[ZellSpez(knoten=generation.knoten + "/gesamt",
                         auspraegungen={}, model_point=spez_felder)],
    )
    zeile = {
        "police_id": 1, "produkt": "klv", "tarif_generation": generation.name,
        "date_of_birth": pd.Timestamp("1965-01-01"),
        "insurance_start": pd.Timestamp("2000-01-01"),
        "bestandszugang": pd.Timestamp(STICHTAG),
        "insurance_end": pd.Timestamp("2030-01-01"),
        "payment_end": pd.Timestamp("2030-01-01"),
        "entry_age": 35, "sex": "M", "duration": 30,
        "premium_duration": 30, "sum_insured": 100000.0,
        "bu_rente": 0.0, "zahlweise": 12,
        "status_id": 1, "status_code": "POL",
        "status_date": pd.Timestamp("2000-01-01"),
    }
    stamm = pd.DataFrame([zeile])
    historie = pd.DataFrame(columns=["police_id", "status_id", "status_code", "status_date"])
    ledger = pd.DataFrame([{
        "police_id": 1, "ereignis": "ZUG", "status_date": pd.Timestamp(STICHTAG),
        "betrag_art": "VS", "betrag": 100000.0, "vertragsjahr": 3,
    }])
    return text, config, spez, zeile, stamm, historie, ledger


def _probe(config, spez, zeile, stamm, historie, ledger):
    tarifwerk = config.generationen[0].tarifwerk()
    return pruefe_fuehrung(
        uebernahme={"bestand": stamm, "historie": historie, "ledger": ledger,
                     "beleg": {"anfangszustand": "ohne_bausteine",
                               "tarifwerk": tarifwerk}},
        fortschreibung=None, config=config, spez=spez, zeilen=[zeile],
        vorgeschichte=[], tarifwerk=tarifwerk,
        quellverfahren={"red_verfahren": "prospektiv"},
        erhoehungssatz=None, red_anteile={}, red_anteile_je_datum={},
        red_anteil_kandidaten=(), anker={}, schichtbeleg=None,
        stichtag=STICHTAG,
    )


@pytest.mark.parametrize("feld,abweichend", ABWEICHEND)
def test_fuehrungsprobe_vergleicht_fehlenden_default(feld, abweichend):
    """Jedes ausgelassene optionale Feld ist im Kern wirksam; die Config
    mit anderem Wert darf nicht an diesem Vergleich vorbeikommen."""
    assert feld in GENERATION_FIELD_DEFAULTS
    _, config, spez, zeile, stamm, historie, ledger = _welt(feld, abweichend)
    result = _probe(config, spez, zeile, stamm, historie, ledger)
    assert any(feld in str(b) and "grundlagen" in str(b)
               for b in result["befunde"]), result["befunde"]


@pytest.mark.parametrize("feld,abweichend", ABWEICHEND)
def test_fuehrungsprobe_nimmt_wirksamen_default_an(feld, abweichend):
    """Der fehlende Spez-Wert ist tatsaechlich der Kern-Default; gleiches
    Verhalten darf nicht durch einen pauschalen Fehlend-Befund fallen."""
    _, config, spez, zeile, stamm, historie, ledger = _welt(feld)
    result = _probe(config, spez, zeile, stamm, historie, ledger)
    assert result["bestanden"] is True, result["befunde"]


def test_zillmer_default_ist_der_wirksame_kernwert():
    """Unabhaengige Kontrollrechnung: der Modellpunkt aus der Spez ohne
    Zillmerfeld rechnet mit 5 Jahren, nicht mit 10 der geaenderten Config."""
    _, _, spez, zeile, _, _, _ = _welt("zillmer_dauer", 10)
    mp = ModelPoint(**model_point_kwargs(zeile, spez.zellen[0].model_point))
    assert mp.zillmer_dauer == 5
    assert Rechenkern(mp).monatsreserve(36).rkw == pytest.approx(4929.418850252759)


@pytest.mark.parametrize("feld,abweichend", ABWEICHEND)
def test_fuehrungswert_verweigert_andere_wirksame_grundlage(feld, abweichend):
    text, config, spez, zeile, stamm, historie, _ = _welt(feld, abweichend)
    mp = model_point_kwargs(zeile, spez.zellen[0].model_point)
    erwartet = {f: mp[f] for f in GENERATION_FIELDS}
    with pytest.raises(MigrationszugangFehler, match=feld):
        fuehrungswerte(
            stamm, historie, text, {"stichtag": STICHTAG},
            tarifwerk_der_spez={spez.generation: config.generationen[0].tarifwerk()},
            grundlagen_der_spez={"1": erwartet})


@pytest.mark.parametrize("feld,abweichend", ABWEICHEND)
def test_fuehrungswert_nimmt_wirksamen_default_an(feld, abweichend):
    text, config, spez, zeile, stamm, historie, _ = _welt(feld)
    mp = model_point_kwargs(zeile, spez.zellen[0].model_point)
    erwartet = {f: mp[f] for f in GENERATION_FIELDS}
    _, werte = fuehrungswerte(
        stamm, historie, text, {"stichtag": STICHTAG},
        tarifwerk_der_spez={spez.generation: config.generationen[0].tarifwerk()},
        grundlagen_der_spez={"1": erwartet})
    assert werte["1"]["stichtag"] is not None


def test_suite_uebergibt_wirksame_spez_grundlagen_an_den_fuehrungswert():
    """Ratsche an der Schichtgrenze: Die Suite darf den engeren Wächter
    nicht nur mit Tarifwerk aufrufen und die ModelPoint-Felder vergessen."""
    text, config, spez, _, stamm, historie, _ = _welt("zillmer_dauer", 10)
    puffer = io.BytesIO()
    historie.to_parquet(puffer)

    def neben(name):
        return puffer.getvalue() if name == "historie.parquet" else None

    with pytest.raises(MigrationszugangFehler, match="zillmer_dauer"):
        fuehrungswert_rechnen(
            stamm, neben, text, {"stichtag": STICHTAG},
            tarifwerk_der_spez={spez.generation: config.generationen[0].tarifwerk()},
            spez=spez)

    text, config, spez, _, stamm, historie, _ = _welt("zillmer_dauer")
    _, werte = fuehrungswert_rechnen(
        stamm, neben, text, {"stichtag": STICHTAG},
        tarifwerk_der_spez={spez.generation: config.generationen[0].tarifwerk()},
        spez=spez)
    assert werte["1"]["stichtag"] is not None
