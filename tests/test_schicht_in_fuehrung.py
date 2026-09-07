"""Freischaltung, Schritt 5: Die Korrekturschicht in der Fuehrung.

Der Rueckkaufswert eines uebernommenen Vertrags ist Basiswert plus
Korrekturschicht (Grundsatzdokumentation 9.7: Storno wertkontinuierlich,
Ausgestaltung des Tarifplans). Die Schicht ist ein Vertragsattribut
(``schichten.parquet`` neben ``verankerung.parquet``), die Engine bucht
sie im Storno mit, der Abschluss weist sie als eigene Position aus, und
P-B1 leitet den Stornobetrag mit ihr her. Ein Rechenweg: dieselbe
Funktion wie in den Pruef-Engines (``kern.korrekturschicht.schichtwert_bei``).

Knoten: klv
"""

from __future__ import annotations

import datetime as _dt
import json

import pandas as pd
import pytest

from rechner_pipeline.bestand.config import config_aus_text
from rechner_pipeline.bestand.ereignisse import EreignisError, fortschreiben
from rechner_pipeline.bestand.kernlauf import vertrags_rkw
from rechner_pipeline.kern import ModelPoint, Rechenkern
from rechner_pipeline.kern.korrekturschicht import Schichtparameter, schichtwert_bei
from rechner_pipeline.bestand.schichten import schichtparameter_aus_zeile
from rechner_pipeline.models.bestand import (
    SCHICHTEN_NAMES,
    SCHICHTEN_SPALTEN,
    VERANKERUNG_SPALTEN,
    model_point_kwargs,
    schichten_zeile,
    validate_schichten,
)
from tests.test_bestand_uebernommen_fortschreiben import _CONFIG_TOML, _stamm

BIS = _dt.date(2046, 1, 1)
MONATE_TA = 132   # elf volle Jahre am Stichtag 2026-01-01 (Beginn 2015-01-01)


def _parameter(rho: float = 0.04) -> Schichtparameter:
    return Schichtparameter(
        schichttyp="hist", verankerungszustand="aktiv", verweildauer=0,
        rho=rho, formfunktion="proportional_zur_basis", formparameter={},
        vererbend=(("aktiv", "tot"),), kohorte="t_a",
    )


def _tabellen(policen, rho: float = 0.04):
    schichten = pd.DataFrame(
        [schichten_zeile(pid, _parameter(rho).als_beleg()) for pid in policen],
        columns=list(SCHICHTEN_NAMES)).astype(dict(SCHICHTEN_SPALTEN))
    verankerung = pd.DataFrame([{
        "police_id": pid, "monate_ta": MONATE_TA, "zustand_ta": "beitragspflichtig",
        "verweildauer_ta": 11, "dk_ta": 1.0,
    } for pid in policen])[[n for n, _ in VERANKERUNG_SPALTEN]].astype(
        dict(VERANKERUNG_SPALTEN))
    return schichten, verankerung


def test_kern_api_ist_dieselbe_funktion_wie_in_der_pruefstrecke():
    from rechner_pipeline.qa import aktuarieller_test

    mp = ModelPoint(**model_point_kwargs(
        _stamm([{"id": 1, "beginn": "2015-01-01"}]).iloc[0],
        config_aus_text(_CONFIG_TOML).generationen[0].generation_fields()))
    for monate in (MONATE_TA, MONATE_TA + 7, MONATE_TA + 60):
        assert aktuarieller_test.schichtwert_bei(_parameter(), MONATE_TA, mp, monate) == \
            schichtwert_bei(_parameter(), MONATE_TA, mp, monate)
    assert schichtwert_bei(_parameter(), MONATE_TA, mp, MONATE_TA) != 0.0


def test_schichten_tabelle_ist_konstruktorkompatibel_und_geprueft():
    policen = [900_001, 900_002]
    schichten, verankerung = _tabellen(policen)
    stamm = _stamm([{"id": pid, "beginn": "2015-01-01", "zugang": "2026-01-01"}
                    for pid in policen])
    assert validate_schichten(stamm, schichten, verankerung) == []
    for zeile in schichten.to_dict("records"):
        assert schichtparameter_aus_zeile(zeile) == _parameter()
    # Fremde Police, fehlender Anker, kaputter Parametersatz.
    fremd = schichten.copy(); fremd.loc[0, "police_id"] = 900_009
    assert any("unbekannt" in b for b in validate_schichten(stamm, fremd, verankerung))
    assert any("ohne Verankerung" in b for b in validate_schichten(
        stamm, schichten, verankerung.iloc[:1]))
    assert any("verankerung" in b for b in validate_schichten(stamm, schichten, None))
    kaputt = schichten.copy(); kaputt.loc[0, "schichttyp"] = "fremd"
    assert any("police 900001" in b for b in validate_schichten(stamm, kaputt, verankerung))


def test_storno_zahlt_basiswert_plus_schicht_und_p_b1_leitet_es_her():
    """Die Buchung der Engine und die Herleitung von P-B1 gehen denselben
    Weg; ohne die Schicht faende P-B1 den Betrag nicht aus dem Kern."""
    from rechner_pipeline.bestand.ledger_bindung import pruefe_ledger_betraege
    from rechner_pipeline.models.bestand import LEDGER_SPALTEN

    config = config_aus_text(_CONFIG_TOML)
    gen = config.generationen[0]
    policen = list(range(900_001, 900_041))
    stamm = _stamm([{"id": pid, "beginn": "2015-01-01", "zugang": "2026-01-01"}
                    for pid in policen])
    schichten, verankerung = _tabellen(policen)
    ergebnis = fortschreiben(stamm, config, BIS, schichten=schichten,
                             verankerung=verankerung)
    ledger = ergebnis.ledger
    sto = ledger[ledger["ereignis"] == "STO"]
    assert len(sto) >= 1
    haupt = stamm.set_index("police_id")
    felder = gen.generation_fields()
    for z in sto.to_dict("records"):
        pid, jahr = int(z["police_id"]), int(z["vertragsjahr"])
        h = haupt.loc[pid]
        grund_mp = ModelPoint(**model_point_kwargs(h, felder))
        teile = []
        for s in ergebnis.scheiben[ergebnis.scheiben["police_id"] == pid].to_dict("records"):
            if int(s["erhoehung_jahr"]) >= jahr:
                continue
            row = {"entry_age": s["entry_age"], "sex": h["sex"],
                   "duration": s["duration"], "premium_duration": s["premium_duration"],
                   "sum_insured": s["sum_insured"], "zahlweise": h["zahlweise"]}
            kw = model_point_kwargs(row, felder); kw["gamma1"] = float(s["gamma1"])
            teile.append((int(s["erhoehung_jahr"]), Rechenkern(ModelPoint(**kw))))
        basis = vertrags_rkw(Rechenkern(grund_mp), teile, jahr)
        schicht = schichtwert_bei(_parameter(), MONATE_TA, grund_mp, 12 * jahr)
        assert schicht != 0.0
        assert z["betrag"] == basis + schicht, (pid, jahr)

    zug = pd.DataFrame([{
        "police_id": pid, "tarif_generation": gen.name, "ereignis": "ZUG",
        "vertragsjahr": 11, "status_date": pd.Timestamp("2026-01-01"),
        "betrag_art": "VS", "betrag": 100_000.0, "betrag_herkunft": "geliefert",
    } for pid in policen])[[n for n, _ in LEDGER_SPALTEN]].astype(dict(LEDGER_SPALTEN))
    voll = pd.concat([zug, ledger], ignore_index=True)
    assert pruefe_ledger_betraege(
        stamm, voll, config, scheiben=ergebnis.scheiben, historie=ergebnis.historie,
        schichten=schichten, verankerung=verankerung) == []
    ohne = pruefe_ledger_betraege(
        stamm, voll, config, scheiben=ergebnis.scheiben, historie=ergebnis.historie)
    assert ohne and "STO" in ohne[0]


def test_abschluss_weist_die_schicht_als_eigene_position_aus(tmp_path):
    from rechner_pipeline.bestand.abschluss import pruefe_abschluss, schreibe_abschluss
    from rechner_pipeline.bestand.auswertung import einzelwerte_am
    from rechner_pipeline.bestand.parquet_io import read_portfolio
    from rechner_pipeline.models.bestand import ABSCHLUSS_NAMES, STATUS_HISTORIE_SPALTEN

    config = config_aus_text(_CONFIG_TOML)
    policen = [900_001, 900_002]
    stamm = _stamm([{"id": pid, "beginn": "2015-01-01", "zugang": "2026-01-01"}
                    for pid in policen])
    schichten, verankerung = _tabellen(policen)
    historie = pd.DataFrame(columns=[n for n, _ in STATUS_HISTORIE_SPALTEN]).astype(
        dict(STATUS_HISTORIE_SPALTEN))
    stichtag = _dt.date(2027, 4, 1)
    mit = einzelwerte_am(stamm, historie, config, stichtag,
                         schichten=schichten, verankerung=verankerung)
    ohne = einzelwerte_am(stamm, historie, config, stichtag)
    felder = config.generationen[0].generation_fields()
    for a, b in zip(mit, ohne):
        mp = ModelPoint(**model_point_kwargs(stamm.set_index("police_id").loc[a["police_id"]], felder))
        monate = (2027 - 2015) * 12 + 3
        korr = schichtwert_bei(_parameter(), MONATE_TA, mp, monate)
        assert a["korrekturschicht"] == korr and korr != 0.0
        assert a["deckungskapital"] == b["deckungskapital"] + korr
        assert a["rueckkaufswert"] == b["rueckkaufswert"] + korr
        assert b["korrekturschicht"] == 0.0

    pfad = schreibe_abschluss(stamm, historie, config, stichtag, tmp_path / "ab",
                              schichten=schichten, verankerung=verankerung)
    fest = read_portfolio(pfad)
    assert list(fest.columns) == list(ABSCHLUSS_NAMES)
    assert (fest["korrekturschicht"] != 0.0).all()
    assert pruefe_abschluss(pfad, stamm, historie, config,
                            schichten=schichten, verankerung=verankerung) == []
    # Ohne die Schicht ist der festgeschriebene Stand nicht reproduzierbar.
    assert pruefe_abschluss(pfad, stamm, historie, config) != []


def test_schicht_ohne_anker_oder_an_eigenem_vertrag_ist_ein_fehler():
    config = config_aus_text(_CONFIG_TOML)
    schichten, verankerung = _tabellen([900_001])
    uebernommen = _stamm([{"id": 900_001, "beginn": "2015-01-01", "zugang": "2026-01-01"}])
    with pytest.raises(EreignisError, match="Verankerung"):
        fortschreiben(uebernommen, config, BIS, schichten=schichten, verankerung=None)
    eigen = _stamm([{"id": 900_001, "beginn": "2015-01-01"}])
    with pytest.raises(EreignisError, match="eigenen Vertrag"):
        fortschreiben(eigen, config, BIS, schichten=schichten, verankerung=verankerung)


def test_der_beleg_und_die_tabelle_tragen_dieselben_parameter(tmp_path):
    """Roundtrip Beleg -> Tabelle -> Parquet -> Schichtparameter."""
    from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio

    schichten, _ = _tabellen([900_001], rho=-0.01)
    write_portfolio(schichten, tmp_path / "schichten.parquet")
    zurueck = read_portfolio(tmp_path / "schichten.parquet", expected_columns=SCHICHTEN_NAMES)
    assert schichtparameter_aus_zeile(zurueck.iloc[0]) == _parameter(-0.01)
    assert json.loads(zurueck.iloc[0]["vererbend"]) == [["aktiv", "tot"]]
