"""Freischaltung, Schritt 4: Die Fuehrung liest den Anfangszustand und die
Schalter der Generation.

Was die Uebernahme materialisiert (Grundsumme, Alt-Scheiben mit ihrem
gamma1) und was die Config je Generation sagt (Stornoabzug je Baustein,
Scheiben mit voller Beitragsformel), muss die Ereignis-Engine rechnen —
und die Ledger-Herleitung von P-B1 denselben Weg gehen, sonst faende
sie die Buchungen der Engine nicht aus dem Kern. Der Rechenweg des
eigenen Geschaefts (Vorgabe) bleibt der bisherige (Ratsche).

Knoten: klv
"""

from __future__ import annotations

import datetime as _dt
import math

import pandas as pd
import pytest

from rechner_pipeline.bestand.config import config_aus_text
from rechner_pipeline.bestand.ereignisse import EreignisError, fortschreiben
from rechner_pipeline.bestand.kernlauf import vertrags_rkw
from rechner_pipeline.kern import (
    KLV_DEFAULT,
    ModelPoint,
    Rechenkern,
    erhoehungs_scheibe,
    vertrags_monatsreserve,
)
from rechner_pipeline.models.bestand import (
    LEDGER_SPALTEN,
    SCHEIBEN_NAMES,
    SCHEIBEN_SPALTEN,
    model_point_kwargs,
)
from tests.test_bestand_uebernommen_fortschreiben import _CONFIG_TOML, _stamm

BIS = _dt.date(2046, 1, 1)
ZUGANG = pd.Timestamp("2026-01-01")


def _config(*, freigeschaltet: bool):
    text = _CONFIG_TOML
    if freigeschaltet:
        text = text.replace(
            "[[generation]]\n",
            "[[generation]]\nscheiben_mit_gamma1 = true\n"
            "stoab_je_baustein = true\nred_verfahren = \"teilkuendigung\"\n", 1)
    cfg = config_aus_text(text)
    assert cfg.validate() == []
    return cfg


def _alt_scheiben(policen, gamma1: float) -> pd.DataFrame:
    """Je Police eine Alt-Erhoehung im dritten Vertragsjahr (2018-01-01)."""
    rows = [{
        "police_id": pid, "scheiben_id": 1, "erhoehung_jahr": 3,
        "erhoehung_datum": pd.Timestamp("2018-01-01"), "entry_age": 43,
        "duration": 22, "premium_duration": 22, "sum_insured": 5000.0,
        "gamma1": gamma1,
    } for pid in policen]
    return pd.DataFrame(rows)[[n for n, _ in SCHEIBEN_SPALTEN]].astype(
        dict(SCHEIBEN_SPALTEN))


def test_vertrags_rkw_folgt_dem_schalter_der_generation():
    """Vorgabe = bisheriger Weg (je Vertrag), Schalter = der Weg des Kerns
    je Baustein; ohne Scheiben sind beide die Kern-Verlaufszeile."""
    grund = Rechenkern(KLV_DEFAULT)
    scheiben = [
        (3, Rechenkern(erhoehungs_scheibe(KLV_DEFAULT, 3, 5000.0))),
        (5, Rechenkern(erhoehungs_scheibe(KLV_DEFAULT, 5, 6000.0))),
    ]
    jahr = 10
    vertragsweit = vertrags_rkw(grund, scheiben, jahr)
    je_baustein = vertrags_rkw(grund, scheiben, jahr, stoab_je_baustein=True)
    assert je_baustein == vertrags_monatsreserve(
        grund, scheiben, 12 * jahr, stoab_je_baustein=True).rkw
    assert math.isclose(vertragsweit, vertrags_monatsreserve(
        grund, scheiben, 12 * jahr).rkw, rel_tol=0.0, abs_tol=1e-6)
    # Drei Mindestabzuege statt einem: je Baustein zieht mehr ab.
    assert je_baustein < vertragsweit
    ohne = grund.verlaufszeile(jahr).rkw
    assert vertrags_rkw(grund, [], jahr) == ohne
    assert vertrags_rkw(grund, [], jahr, stoab_je_baustein=True) == ohne


@pytest.mark.parametrize("freigeschaltet", [True, False])
def test_engine_rechnet_auf_mitgebrachten_bausteinen(freigeschaltet: bool):
    """Jede Buchung eines uebernommenen Vertrags folgt aus Grundscheibe UND
    mitgebrachten Bausteinen, mit den Schaltern seiner Generation; neue
    Scheiben zaehlen dahinter und tragen das gamma1 des Tarifwerks. Und
    P-B1 leitet genau diese Betraege her."""
    from rechner_pipeline.bestand.fuehrung import fuehre_fort
    from rechner_pipeline.bestand.kennzahlen import bewegungskonto
    from rechner_pipeline.bestand.ledger_bindung import (
        pruefe_ledger_betraege,
        pruefe_scheiben_tarifwerk,
    )

    config = _config(freigeschaltet=freigeschaltet)
    gen = config.generationen[0]
    tw = gen.tarifwerk()
    gamma1_scheibe = gen.gamma1 if tw["scheiben_mit_gamma1"] else 0.0
    policen = list(range(900_001, 900_031))
    stamm = _stamm([{"id": pid, "beginn": "2015-01-01", "zugang": "2026-01-01"}
                    for pid in policen])
    alt = _alt_scheiben(policen, gamma1_scheibe)

    ergebnis = fortschreiben(stamm, config, BIS, scheiben=alt)
    neue = ergebnis.scheiben
    assert len(neue) > 0 and (neue["scheiben_id"] >= 2).all()
    assert set(neue["gamma1"]) == {gamma1_scheibe}

    felder = gen.generation_fields()
    haupt = stamm.set_index("police_id")

    def kerne(pid: int, jahr: int):
        h = haupt.loc[pid]
        grund = Rechenkern(ModelPoint(**model_point_kwargs(h, felder)))
        teile = []
        for s in pd.concat([alt, neue]).query("police_id == @pid").to_dict("records"):
            if int(s["erhoehung_jahr"]) >= jahr:
                continue
            row = {"entry_age": s["entry_age"], "sex": h["sex"],
                   "duration": s["duration"], "premium_duration": s["premium_duration"],
                   "sum_insured": s["sum_insured"], "zahlweise": h["zahlweise"]}
            kw = model_point_kwargs(row, felder)
            kw["gamma1"] = float(s["gamma1"])
            teile.append((int(s["erhoehung_jahr"]), Rechenkern(ModelPoint(**kw))))
        return grund, teile

    geprueft = {"STO": 0, "PEX": 0, "TOD": 0, "ABL": 0, "ERH": 0}
    ledger = ergebnis.ledger
    for z in ledger.to_dict("records"):
        pid, art, jahr = int(z["police_id"]), z["ereignis"], int(z["vertragsjahr"])
        grund, teile = kerne(pid, jahr)
        if art == "STO":
            erwartet = vertrags_rkw(grund, teile, jahr,
                                    stoab_je_baustein=tw["stoab_je_baustein"])
            assert z["betrag"] == erwartet, (pid, jahr)
            # Der mitgebrachte Baustein ist drin: ohne ihn ein anderer Wert.
            assert z["betrag"] != vertrags_rkw(grund, [], jahr)
        elif art == "PEX":
            erwartet = grund.beitragsfreie_summe(jahr) + sum(
                k.beitragsfreie_summe(jahr - j) for j, k in teile)
            assert z["betrag"] == erwartet, (pid, jahr)
        elif art in ("TOD", "ABL"):
            pex = ledger[(ledger["police_id"] == pid) & (ledger["ereignis"] == "PEX")]
            if len(pex):
                assert z["betrag"] == float(pex["betrag"].iloc[0])
            else:
                assert z["betrag"] == grund.mp.sum_insured + sum(
                    k.mp.sum_insured for _, k in teile)
        elif art == "ERH":
            # Bezugsgroesse ist die Gesamtsumme MIT dem Alt-Baustein.
            vorher = grund.mp.sum_insured + sum(k.mp.sum_insured for _, k in teile)
            assert math.isclose(z["betrag"], 0.05 * vorher, rel_tol=0.0, abs_tol=1e-9)
        geprueft[art] = geprueft.get(art, 0) + 1
    assert geprueft["STO"] >= 1 and geprueft["PEX"] >= 1 and geprueft["ERH"] >= 1

    # P-B1: dieselbe Herleitung, Tarifwerk der Scheiben, Bewegungs-Identitaet.
    zug = pd.DataFrame([{
        "police_id": pid, "tarif_generation": gen.name, "ereignis": "ZUG",
        "vertragsjahr": 11, "status_date": ZUGANG, "betrag_art": "VS",
        "betrag": 105_000.0, "betrag_herkunft": "geliefert",
    } for pid in policen])[[n for n, _ in LEDGER_SPALTEN]].astype(dict(LEDGER_SPALTEN))
    voll = pd.concat([zug, ledger], ignore_index=True)
    alle_scheiben = pd.concat([alt, neue], ignore_index=True)
    assert pruefe_scheiben_tarifwerk(stamm, alle_scheiben, config) == []
    assert pruefe_ledger_betraege(
        stamm, voll, config, scheiben=alle_scheiben, historie=ergebnis.historie) == []
    gefuehrt = fuehre_fort(stamm, ergebnis.historie)
    konto = bewegungskonto(gefuehrt, ergebnis.historie, voll, alle_scheiben, bis=BIS)
    verletzt = [(k["jahr"], t, m) for k in konto
                for t, oks in k["identitaet"].items() for m, ok in oks.items() if not ok]
    assert verletzt == []


def test_scheiben_nach_dem_zugang_oder_am_eigenen_vertrag_sind_ein_fehler():
    config = _config(freigeschaltet=True)
    uebernommen = _stamm([{"id": 900_001, "beginn": "2015-01-01", "zugang": "2026-01-01"}])
    spaet = _alt_scheiben([900_001], 0.001)
    spaet.loc[0, "erhoehung_datum"] = pd.Timestamp("2027-01-01")
    spaet.loc[0, "erhoehung_jahr"] = 12
    with pytest.raises(EreignisError, match="NACH dem Bestandszugang"):
        fortschreiben(uebernommen, config, BIS, scheiben=spaet)
    eigen = _stamm([{"id": 900_001, "beginn": "2015-01-01"}])
    with pytest.raises(EreignisError, match="eigenen Vertrag"):
        fortschreiben(eigen, config, BIS, scheiben=_alt_scheiben([900_001], 0.001))
    fremd = _alt_scheiben([900_002], 0.001)
    with pytest.raises(EreignisError, match="unbekannt"):
        fortschreiben(uebernommen, config, BIS, scheiben=fremd)


def test_vorgabe_laesst_das_eigene_geschaeft_unveraendert():
    """Ratsche: Ohne Schalter rechnet die Engine wie bisher — Scheiben ohne
    gamma1, Rueckkaufswert je Vertrag. Der Test haelt den Rechenweg fest,
    nicht nur das Ergebnis."""
    config = _config(freigeschaltet=False)
    assert all(g.tarifwerk() == {"scheiben_mit_gamma1": False,
                                 "stoab_je_baustein": False,
                                 "red_verfahren": "prospektiv"}
               for g in config.generationen)
    stamm = _stamm([{"id": pid, "beginn": "2015-01-01"} for pid in range(1, 21)])
    ergebnis = fortschreiben(stamm, config, BIS)
    assert set(ergebnis.scheiben["gamma1"]) <= {0.0}
    assert list(ergebnis.scheiben.columns) == list(SCHEIBEN_NAMES)
