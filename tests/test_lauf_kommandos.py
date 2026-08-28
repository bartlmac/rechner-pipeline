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
