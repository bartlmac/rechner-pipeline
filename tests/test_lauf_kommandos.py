"""Laeufer-Kommandos: Zellwahl je Police und Anfangszustand der Vorgeschichte.

Die zweite Lieferung traegt eine mehrzellige Spez (tarifart x status)
und Vertraege, die beitragsfrei UEBERNOMMEN werden. Beides konnte der
Suite-/Aktuartest-Laeufer vorher nicht: Er waehlte die Zelle nur bei
einzelliger Spez richtig und kannte keinen Anfangszustand. Diese Tests
halten die neuen Wege fest — inklusive der harten Ausgaenge, die ein
stilles Zurueckfallen auf eine falsche Zelle verhindern.

Knoten: klv
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Dict, List

import pandas as pd
import pytest

from rechner_pipeline.gates.migrationssuite_lauf import (
    auspraegungen_je_police,
    baue_auftraege,
    beitragsfrei_seit_jahr_je_police,
    VORGABE,
)


@dataclass
class _Wert:
    wert: object


@dataclass
class _Zelle:
    auspraegungen: Dict[str, str] = field(default_factory=dict)
    model_point: Dict[str, _Wert] = field(default_factory=dict)


@dataclass
class _Spez:
    zellen: List[_Zelle] = field(default_factory=list)


def _generationsfelder(zins: float) -> Dict[str, _Wert]:
    return {
        "zins": _Wert(zins), "tafel": _Wert("DAV2008_T_NR_U70"),
        "alpha": _Wert(0.025), "beta1": _Wert(0.03),
        "gamma1": _Wert(0.001), "gamma2": _Wert(0.00125),
        "gamma3": _Wert(0.0025), "policy_fee": _Wert(12.0),
        "min_alter_flex": _Wert(60), "min_rlz_flex": _Wert(5),
        "stoab_satz": _Wert(0.005), "stoab_min": _Wert(50.0),
        "stoab_max": _Wert(200.0), "zillmer_dauer": _Wert(5),
        "ratzu_zw2": _Wert(0.02), "ratzu_zw4": _Wert(0.03),
        "ratzu_zw12": _Wert(0.05),
    }


MEHRZELLIG = _Spez(zellen=[
    _Zelle({"status": "nichtraucher", "tarifart": "einzel"},
           _generationsfelder(0.0175)),
    _Zelle({"status": "raucher", "tarifart": "einzel"},
           _generationsfelder(0.0125)),
])

EINZELLIG = _Spez(zellen=[_Zelle({}, _generationsfelder(0.0175))])

SPALTEN = dict(VORGABE)


def _bestand(*policen: int) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "police_id": p, "sex": "F", "entry_age": 45, "duration": 30,
            "premium_duration": 20, "sum_insured": 100000.0, "zahlweise": 12,
            "insurance_start": pd.Timestamp("2016-01-01"),
        }
        for p in policen
    ])


def _abzug(*policen: int) -> List[Dict[str, str]]:
    return [
        {"POLNR": str(p), "DECKKAP": "1234.56", "JBRUTTO": "4150.51"}
        for p in policen
    ]


def test_auspraegungen_je_police_liest_die_dimensionsfelder():
    zeilen = [
        {"police_id": "7000001", "status": "raucher", "tarifart": "einzel"},
        {"police_id": "7000002", "status": "nichtraucher",
         "tarifart": "einzel"},
    ]
    aus = auspraegungen_je_police(MEHRZELLIG, zeilen)
    assert aus["7000001"] == {"status": "raucher", "tarifart": "einzel"}
    assert aus["7000002"]["status"] == "nichtraucher"


def test_fehlende_dimension_in_der_zeile_faellt_hart():
    with pytest.raises(SystemExit, match="7000001.*status"):
        auspraegungen_je_police(
            MEHRZELLIG, [{"police_id": "7000001", "tarifart": "einzel"}])


def test_zeile_ohne_police_id_faellt_hart():
    with pytest.raises(SystemExit, match="police_id"):
        auspraegungen_je_police(MEHRZELLIG, [{"status": "raucher"}])


def test_mehrzellige_spez_ohne_zeilen_faellt_hart():
    with pytest.raises(SystemExit, match="Zellwahl"):
        baue_auftraege(
            _bestand(7000001), MEHRZELLIG, _abzug(7000001), [], [],
            stichtag_1=dt.date(2026, 1, 1), stichtag_2=dt.date(2027, 1, 1),
            spalten=SPALTEN,
        )


def test_zellwahl_je_police_parametriert_je_zelle():
    auftraege = baue_auftraege(
        _bestand(7000001, 7000002), MEHRZELLIG,
        _abzug(7000001, 7000002), [], [],
        stichtag_1=dt.date(2026, 1, 1), stichtag_2=dt.date(2027, 1, 1),
        spalten=SPALTEN,
        auspraegungen={
            "7000001": {"status": "raucher", "tarifart": "einzel"},
            "7000002": {"status": "nichtraucher", "tarifart": "einzel"},
        },
    )
    je_police = {a.police_id: a for a in auftraege}
    assert je_police["7000001"].model_point["zins"] == 0.0125
    assert je_police["7000002"].model_point["zins"] == 0.0175


def test_anfangszustand_fliesst_in_den_pruefauftrag():
    auftraege = baue_auftraege(
        _bestand(7000001), EINZELLIG, _abzug(7000001), [], [],
        stichtag_1=dt.date(2026, 1, 1), stichtag_2=dt.date(2027, 1, 1),
        spalten=SPALTEN,
        beitragsfrei_seit={"7000001": 7},
    )
    assert auftraege[0].beitragsfrei_seit_jahr == 7


def test_pex_der_vorgeschichte_wird_zum_vertragsjahr():
    vorgeschichte = [
        {"POLNR": "7000001", "GEVO": "PEX", "DATUM": "01.01.2023"},
        {"POLNR": "7000001", "GEVO": "ERH", "DATUM": "01.01.2020"},
        {"POLNR": "9999999", "GEVO": "PEX", "DATUM": "01.01.2023"},
    ]
    seit = beitragsfrei_seit_jahr_je_police(
        vorgeschichte, _bestand(7000001), spalten=SPALTEN)
    # Beginn 2016-01-01, PEX 2023-01-01 -> Vertragsjahr 7; fremde Police
    # ohne Bestandszeile bleibt draussen, ERH setzt keinen Zustand.
    assert seit == {"7000001": 7}


def test_pex_abseits_des_jahrestags_faellt_hart():
    vorgeschichte = [{"POLNR": "7000001", "GEVO": "PEX",
                      "DATUM": "01.07.2023"}]
    with pytest.raises(SystemExit, match="Jahrestag"):
        beitragsfrei_seit_jahr_je_police(
            vorgeschichte, _bestand(7000001), spalten=SPALTEN)


def test_zweites_pex_derselben_police_faellt_hart():
    vorgeschichte = [
        {"POLNR": "7000001", "GEVO": "PEX", "DATUM": "01.01.2022"},
        {"POLNR": "7000001", "GEVO": "PEX", "DATUM": "01.01.2023"},
    ]
    with pytest.raises(SystemExit, match="zwei PEX"):
        beitragsfrei_seit_jahr_je_police(
            vorgeschichte, _bestand(7000001), spalten=SPALTEN)


# --------------------------------------------------------------------------- #
# Anfangszustaende ERH/RED je Police (Ableitung im Laeufer)
# --------------------------------------------------------------------------- #

from rechner_pipeline.gates.migrationssuite_lauf import (
    anfangszustaende_je_police,
)
from rechner_pipeline.kern import KLV_DEFAULT
from rechner_pipeline.kern.beitragsreduktion import reduziere
from rechner_pipeline.kern.rechenkern import Rechenkern, erhoehungs_scheibe


def _tg_default_spez():
    """Einzellige Spez mit den Feldern des Referenz-Modellpunkts."""
    import dataclasses as dc
    from rechner_pipeline.models.bestand import GENERATION_FIELDS

    felder = dc.asdict(KLV_DEFAULT)
    return _Spez(zellen=[_Zelle({}, {
        f: _Wert(felder[f]) for f in GENERATION_FIELDS
    })])


def _bestand_mit(*policen: int, beginn="2016-01-01") -> pd.DataFrame:
    rahmen = _bestand(*policen)
    rahmen["insurance_start"] = pd.Timestamp(beginn)
    # Die Referenz-Vorwaertsrechnung laeuft auf KLV_DEFAULT (sex M,
    # geschlechtsabhaengige Tafel) — die Ableitung muss denselben
    # Modellpunkt sehen, sonst vergleicht der Test zwei Vertraege.
    rahmen["sex"] = KLV_DEFAULT.sex
    rahmen["entry_age"] = KLV_DEFAULT.x
    rahmen["duration"] = KLV_DEFAULT.n
    rahmen["premium_duration"] = KLV_DEFAULT.t
    rahmen["zahlweise"] = KLV_DEFAULT.zw
    return rahmen


def test_anfangszustand_erh_leitet_scheibe_und_grundsumme_ab():
    s_grund, s_scheibe, jahr = 80000.0, 12000.0, 6
    grund = Rechenkern(type(KLV_DEFAULT)(**{
        **KLV_DEFAULT.__dict__, "sum_insured": s_grund}))
    scheibe = Rechenkern(erhoehungs_scheibe(grund.mp, jahr, s_scheibe))
    zeilen = [{"police_id": "7000001",
               "sum_insured": round(s_grund + s_scheibe, 2),
               "brutto_jahresbeitrag": round(
                   grund.gross_annual_premium()
                   + scheibe.gross_annual_premium(), 2)}]
    vorgeschichte = [{"POLNR": "7000001", "GEVO": "ERH",
                      "DATUM": "01.01.2022"}]
    zustaende, warnungen = anfangszustaende_je_police(
        _tg_default_spez(), zeilen, vorgeschichte,
        _bestand_mit(7000001), spalten=SPALTEN,
        red_verfahren="mit_abzug")
    assert not warnungen
    (jahr_s, summe), = zustaende["7000001"]["scheiben"]
    assert jahr_s == 6
    assert summe == pytest.approx(s_scheibe, rel=5e-5)
    assert zustaende["7000001"]["sum_insured"] == pytest.approx(
        s_grund, rel=5e-5)


def test_anfangszustand_red_leitet_anteil_und_ursprungssumme_ab():
    r = reduziere(Rechenkern(KLV_DEFAULT), 6, 0.6, verfahren="mit_abzug")
    zeilen = [{"police_id": "7000002", "sum_insured": round(r.vs_neu, 2),
               "brutto_jahresbeitrag": round(r.bjb_neu, 2)}]
    vorgeschichte = [{"POLNR": "7000002", "GEVO": "RED",
                      "DATUM": "01.01.2022"}]
    zustaende, warnungen = anfangszustaende_je_police(
        _tg_default_spez(), zeilen, vorgeschichte,
        _bestand_mit(7000002), spalten=SPALTEN,
        red_verfahren="mit_abzug")
    assert not warnungen
    jahr, anteil = zustaende["7000002"]["reduktion"]
    assert jahr == 6
    assert anteil == pytest.approx(0.6, rel=5e-5)
    assert zustaende["7000002"]["sum_insured"] == pytest.approx(
        KLV_DEFAULT.sum_insured, rel=5e-5)


def test_nachgelieferter_anteil_ersetzt_die_beitragsgleichung():
    r = reduziere(Rechenkern(KLV_DEFAULT), 6, 0.75, verfahren="mit_abzug")
    zeilen = [{"police_id": "7000365", "sum_insured": round(r.vs_neu, 2),
               "brutto_jahresbeitrag": 0.0}]
    vorgeschichte = [{"POLNR": "7000365", "GEVO": "RED",
                      "DATUM": "01.01.2022"}]
    zustaende, warnungen = anfangszustaende_je_police(
        _tg_default_spez(), zeilen, vorgeschichte,
        _bestand_mit(7000365), spalten=SPALTEN,
        red_verfahren="mit_abzug", red_anteile={"7000365": 0.75})
    assert not warnungen
    jahr, anteil = zustaende["7000365"]["reduktion"]
    assert (jahr, anteil) == (6, 0.75)
    assert zustaende["7000365"]["sum_insured"] == pytest.approx(
        KLV_DEFAULT.sum_insured, rel=5e-5)


def test_unbestimmbare_erhoehung_wird_warnung_statt_zustand():
    zeilen = [{"police_id": "7000050", "sum_insured": 92000.0,
               "brutto_jahresbeitrag": 0.0}]
    vorgeschichte = [{"POLNR": "7000050", "GEVO": "ERH",
                      "DATUM": "01.01.2022"}]
    zustaende, warnungen = anfangszustaende_je_police(
        _tg_default_spez(), zeilen, vorgeschichte,
        _bestand_mit(7000050), spalten=SPALTEN,
        red_verfahren="mit_abzug")
    assert zustaende == {}
    assert len(warnungen) == 1 and "7000050" in warnungen[0]


def test_auftragsbau_uebernimmt_zustand_und_ursprungssumme():
    auftraege = baue_auftraege(
        _bestand_mit(7000002), EINZELLIG, _abzug(7000002), [], [],
        stichtag_1=dt.date(2026, 1, 1), stichtag_2=dt.date(2027, 1, 1),
        spalten=SPALTEN,
        anfangszustaende={"7000002": {
            "reduktion": (6, 0.6), "sum_insured": 100000.0}},
    )
    a, = auftraege
    assert a.reduktion == (6, 0.6)
    assert a.model_point["sum_insured"] == 100000.0
