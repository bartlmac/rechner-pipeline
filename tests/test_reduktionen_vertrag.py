"""Datenvertrag der Herabsetzung: reduktionen.parquet (Review T25-06).

Eine dynamische Erhoehung legt eine neue Scheibe an; eine Herabsetzung
knickt den Verlauf des bestehenden Vertrags. Der Kern traegt den
herabgesetzten Vertrag als EINEN Vertrag
(``kern.beitragsreduktion.ReduzierterVertrag``) und rekonstruiert ihn aus
genau drei Angaben: Jahr, fortgefuehrter Anteil, Verfahren. Mehr braucht
die Tabelle nicht, und weniger reichte nicht — derselbe Anteil ist je
nach Verfahren ein anderer Vertrag.

Knoten: klv
"""

from __future__ import annotations

import datetime as _dt

import pandas as pd
import pytest

from rechner_pipeline.bestand.parquet_io import (
    FAMILIEN,
    read_portfolio,
    write_portfolio,
)
from rechner_pipeline.kern.beitragsreduktion import VERFAHREN
from rechner_pipeline.models.bestand import (
    REDUKTIONEN_NAMES,
    REDUKTIONEN_SPALTEN,
    STAMM_SPALTEN,
    STATUS_HISTORIE_SPALTEN,
    validate_reduktionen,
)

BEGINN = _dt.date(2015, 1, 1)


def _stamm(police_id: int = 900_001, *, t: int = 20) -> pd.DataFrame:
    zeile = {
        "police_id": police_id, "status_id": 1, "status_code": "POL",
        "status_date": pd.Timestamp(BEGINN), "produkt": "klv",
        "tarif_generation": "TG2015", "sex": "M",
        "date_of_birth": pd.Timestamp("1980-01-01"),
        "insurance_start": pd.Timestamp(BEGINN),
        "insurance_end": pd.Timestamp(_dt.date(BEGINN.year + 25, 1, 1)),
        "payment_end": pd.Timestamp(_dt.date(BEGINN.year + t, 1, 1)),
        "bestandszugang": pd.Timestamp(BEGINN),
        "entry_age": 35, "duration": 25, "premium_duration": t,
        "sum_insured": 60000.0, "bu_rente": 0.0, "zahlweise": 12,
    }
    spalten = [n for n, _ in STAMM_SPALTEN]
    return pd.DataFrame([{k: zeile[k] for k in spalten}]).astype(
        dict(STAMM_SPALTEN))


def _reduktionen(police_id: int = 900_001, *, jahr: int = 8,
                 anteil: float = 0.6, verfahren: str = "prospektiv"):
    zeile = {
        "police_id": police_id,
        "reduktion_jahr": jahr,
        "reduktion_datum": pd.Timestamp(_dt.date(BEGINN.year + jahr, 1, 1)),
        "anteil": anteil,
        "verfahren": verfahren,
    }
    return pd.DataFrame([zeile])[list(REDUKTIONEN_NAMES)].astype(
        dict(REDUKTIONEN_SPALTEN))


def test_die_tabelle_ist_eine_eigene_parquet_familie(tmp_path):
    """Ohne Eintrag in FAMILIEN faellt der Leser in die Rueckfall-Behandlung
    des Stamm-Schnitts — und meldet einen Fehler statt der Tabelle."""
    assert REDUKTIONEN_NAMES in FAMILIEN
    pfad = tmp_path / "reduktionen.parquet"
    write_portfolio(_reduktionen(), pfad)
    zurueck = read_portfolio(pfad)
    assert list(zurueck.columns) == list(REDUKTIONEN_NAMES)
    assert [str(zurueck[n].dtype) for n, _ in REDUKTIONEN_SPALTEN] == \
        [d for _, d in REDUKTIONEN_SPALTEN]


def test_eine_gueltige_herabsetzung_ist_befundfrei():
    assert validate_reduktionen(_stamm(), _reduktionen()) == []


@pytest.mark.parametrize("anteil", [0.0, 1.0, -0.1, 1.5])
def test_anteil_ausserhalb_des_offenen_intervalls_faellt(anteil):
    """1.0 ist keine Herabsetzung, 0.0 ist eine Beitragsfreistellung."""
    befunde = validate_reduktionen(_stamm(), _reduktionen(anteil=anteil))
    assert any("anteil ausserhalb" in b for b in befunde)


def test_nur_bekannte_verfahren():
    befunde = validate_reduktionen(
        _stamm(), _reduktionen(verfahren="nach_gefuehl"))
    assert any("verfahren" in b and "unbekannt" in b for b in befunde)
    # Positivkontrolle: jedes Verfahren des Kerns ist zulaessig.
    for v in VERFAHREN:
        assert validate_reduktionen(_stamm(), _reduktionen(verfahren=v)) == []


def test_zweite_herabsetzung_derselben_police_faellt():
    """Der Kern kennt keinen zweimal herabgesetzten Vertrag."""
    doppelt = pd.concat([_reduktionen(), _reduktionen(jahr=12)],
                        ignore_index=True)
    befunde = validate_reduktionen(_stamm(), doppelt)
    assert any("mehrere Herabsetzungen" in b for b in befunde)


@pytest.mark.parametrize("jahr", [0, 20, 25])
def test_reduktionsjahr_ausserhalb_der_beitragszahlung_faellt(jahr):
    befunde = validate_reduktionen(_stamm(), _reduktionen(jahr=jahr))
    assert any("ausserhalb der Beitragszahlungsdauer" in b for b in befunde)


def test_fremde_police_faellt():
    befunde = validate_reduktionen(_stamm(), _reduktionen(police_id=999))
    assert any("ausserhalb des Bestands" in b for b in befunde)


def test_herabsetzung_nach_dem_zustandswechsel_faellt():
    """Ohne laufenden Beitrag gibt es nichts herabzusetzen."""
    historie = pd.DataFrame([{
        "police_id": 900_001, "status_id": 2, "status_code": "PEX",
        "status_date": pd.Timestamp(_dt.date(2020, 1, 1)),   # Jahr 5
    }])[[n for n, _ in STATUS_HISTORIE_SPALTEN]].astype(
        dict(STATUS_HISTORIE_SPALTEN))
    befunde = validate_reduktionen(
        _stamm(), _reduktionen(jahr=8), historie=historie)
    assert any("nicht vor dem Zustandswechsel" in b for b in befunde)
    # Umgekehrt: eine Herabsetzung VOR der Freistellung ist in Ordnung.
    assert validate_reduktionen(
        _stamm(), _reduktionen(jahr=3), historie=historie) == []
