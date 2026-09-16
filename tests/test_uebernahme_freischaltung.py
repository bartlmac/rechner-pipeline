"""Freischaltung, Schritt 3: Die Uebernahme materialisiert den Anfangszustand.

Was die Pruefstrecke rechnet, muss in den Tabellen stehen, die die
Fuehrung liest (dev-docs/freischaltung-uebernommener-bestand.md). Jeder
Test hier haelt einen Befund der Messung aus Abschnitt 1.1 fest und ist
so gebaut, dass er VOR der Korrektur rot gewesen waere: die doppelte
Umwandlung beitragsfrei gelieferter Summen, die Gesamtsumme als ein
Vertrag statt Grundsumme plus Bausteine, der Zugang ohne Bausteine, die
stille Fuehrung eines Herabsetzungs-Zustands.

Knoten: klv
"""

from __future__ import annotations

import datetime as dt
import json

import pandas as pd
import pytest

from rechner_pipeline.gates.bestand_uebernehmen import (
    _zellen_toml,
    baue,
    materialisiere_anfangszustand,
)
from rechner_pipeline.kern import ModelPoint, Rechenkern
from rechner_pipeline.models.bestand import (
    SCHEIBEN_NAMES,
    _ledger_scheiben_bindung,
    validate_scheiben,
)
from tests.test_bestand_uebernehmen import GRUNDLAGEN, ZEILE

STICHTAG = dt.date(2026, 1, 1)


def _baue(vorgeschichte):
    return baue(
        [dict(ZEILE)], tarif_generation="TG2015", produkt="klv",
        stichtag=STICHTAG, vorgeschichte=vorgeschichte,
        generationsfelder=GRUNDLAGEN,
    )


def _modellpunkt(sum_insured: float) -> ModelPoint:
    return ModelPoint(
        x=ZEILE["entry_age"], sex=ZEILE["sex"], n=ZEILE["duration"],
        t=ZEILE["premium_duration"], sum_insured=sum_insured,
        zw=ZEILE["zahlweise"], **GRUNDLAGEN,
    )


def test_beitragsfrei_geliefert_wird_nicht_doppelt_umgewandelt():
    """Der Abzug fuehrt die BEITRAGSFREIE Summe. Der Stamm traegt die
    Ursprungssumme, aus der der Kern sie bildet; die Umbuchung bucht die
    gelieferte Summe. Vorher: gelieferte Summe als Versicherungssumme und
    daraus noch einmal eine beitragsfreie Summe (Faktor 0,3 bis 0,5)."""
    stamm, _historie, ledger, _h = _baue(
        {"7000001": [("PEX", dt.date(2022, 2, 1))]})
    geliefert = float(ZEILE["sum_insured"])
    ursprung = float(stamm.loc[0, "sum_insured"])
    assert ursprung > geliefert, "Ursprungssumme liegt ueber der beitragsfreien"

    zug = ledger[ledger["ereignis"] == "ZUG"]["betrag"].iloc[0]
    pex = ledger[ledger["ereignis"] == "PEX"]["betrag"].iloc[0]
    assert zug == ursprung
    assert abs(pex - geliefert) <= 0.005, (pex, geliefert)
    # Der Kern reproduziert die Lieferung aus der Ursprungssumme exakt —
    # das ist die Bedingung, die die Uebernahme prueft, kein Zufall.
    pex_jahr = 6
    assert abs(Rechenkern(_modellpunkt(ursprung)).beitragsfreie_summe(pex_jahr)
               - geliefert) <= 0.005
    # Die alte Rechnung haette die Summe ein zweites Mal umgewandelt:
    doppelt = Rechenkern(_modellpunkt(geliefert)).beitragsfreie_summe(pex_jahr)
    assert doppelt < 0.9 * geliefert


def test_materialisierung_schreibt_grundsumme_scheiben_und_gesamtzugang():
    """Alt-Erhoehungen werden Bausteine mit derselben Konstruktionsregel
    wie in der Ereignis-Engine; der Stamm traegt die Grundsumme, der
    Zugang die Gesamtsumme. gamma1 der Scheibe folgt dem Schalter."""
    vorgeschichte = {"7000001": [("ERH", dt.date(2018, 2, 1)),
                                 ("ERH", dt.date(2019, 2, 1))]}
    zustaende = {"7000001": {
        "sum_insured": 60000.0, "scheiben": ((2, 3000.0), (3, 3150.0)),
    }}
    for mit_gamma1 in (True, False):
        stamm, _historie, ledger, _h = _baue(vorgeschichte)
        scheiben, zahlen = materialisiere_anfangszustand(
            stamm, ledger, zustaende, GRUNDLAGEN,
            scheiben_mit_gamma1=mit_gamma1)
        assert float(stamm.loc[0, "sum_insured"]) == 60000.0
        assert ledger.loc[ledger["ereignis"] == "ZUG", "betrag"].iloc[0] == 66150.0
        assert list(scheiben.columns) == list(SCHEIBEN_NAMES)
        assert list(scheiben["scheiben_id"]) == [1, 2]
        assert list(scheiben["erhoehung_jahr"]) == [2, 3]
        assert list(scheiben["entry_age"]) == [39, 40]
        assert list(scheiben["duration"]) == [10, 9]
        assert list(scheiben["premium_duration"]) == [5, 4]
        assert [d.date() for d in scheiben["erhoehung_datum"]] == [
            dt.date(2018, 2, 1), dt.date(2019, 2, 1)]
        assert list(scheiben["sum_insured"]) == [3000.0, 3150.0]
        erwartet = GRUNDLAGEN["gamma1"] if mit_gamma1 else 0.0
        assert set(scheiben["gamma1"]) == {erwartet}
        assert validate_scheiben(stamm, scheiben) == []
        assert zahlen == {"mit_anfangszustand": 1, "mit_scheiben": 1,
                          "scheiben": 2, "beitragsfrei": 0}
        # Mitgebrachte Scheiben haben keine ERH-Buchung — sie liegen vor
        # dem Bestandszugang. Ohne den Stamm saehe der Validator sie als
        # Scheiben ohne Buchung.
        assert _ledger_scheiben_bindung(ledger, scheiben, stamm) == []
        ohne_stamm = _ledger_scheiben_bindung(ledger, scheiben)
        assert ohne_stamm and "ohne ERH-Buchung" in ohne_stamm[0]


def test_herabsetzungs_zustand_ist_nicht_freigeschaltet():
    """Ein geteilter Vertrag (Verfahren prospektiv/mit_abzug) wird nicht
    still als Grundvertrag gefuehrt: benannter Halt."""
    stamm, _h, ledger, _hw = _baue(
        {"7000001": [("RED", dt.date(2020, 2, 1))]})
    with pytest.raises(SystemExit, match="nicht freigeschaltet"):
        materialisiere_anfangszustand(
            stamm, ledger,
            {"7000001": {"reduktion": (4, 0.6), "sum_insured": 80000.0}},
            GRUNDLAGEN, scheiben_mit_gamma1=False)


def test_cli_verlangt_die_antwort_sobald_die_vorgeschichte_bausteine_traegt(tmp_path):
    """Kein stiller Default: Mit ERH/RED in der Vorgeschichte muss der
    Aufrufer sagen, ob materialisiert oder als Grundvertrag gefuehrt wird.
    Der Grundvertrag-Weg weist die betroffenen Policen im Beleg aus."""
    from rechner_pipeline.fall import anlegen, registrieren
    from rechner_pipeline.gates import bestand_uebernehmen

    fall = tmp_path / "fall"
    anlegen(fall, scope="bestand")
    metadaten = tmp_path / "gevo_metadaten.csv"
    metadaten.write_text(
        "POLNR;GEVO;DATUM\n7000001;ERH;01.02.2020\n", encoding="utf-8")
    registrieren(fall, metadaten)
    zeilen = tmp_path / "zeilen.json"
    zeilen.write_text(json.dumps([dict(ZEILE)]), encoding="utf-8")
    ziel = fall / "abgeleitet" / "bestand"
    argv = [
        "--fall", str(fall), "--zeilen", str(zeilen),
        "--tarif-generation", "TG2015", "--stichtag", "2026-01-01",
        "--vorgeschichte", "gevo_metadaten.csv",
        "--out-dir", str(ziel),
    ]
    assert bestand_uebernehmen.main(argv) == 2
    assert not (ziel / "bestand.parquet").exists(), "nichts geschrieben"
    assert bestand_uebernehmen.main(
        argv + ["--anfangszustand", "grundvertrag"]) == 0
    beleg = json.loads((ziel / "uebernahme.json").read_text(encoding="utf-8"))
    assert beleg["anfangszustand"] == "grundvertrag"
    assert beleg["nicht_freigeschaltet"] == ["7000001"]
    assert beleg["tarifwerk"] == {
        "scheiben_mit_gamma1": False, "stoab_je_baustein": False,
        "red_verfahren": "prospektiv"}
    assert not (ziel / "scheiben.parquet").exists()
    # Materialisieren ohne Rechnungsgrundlagen ist ein Aufruffehler.
    assert bestand_uebernehmen.main(
        argv + ["--anfangszustand", "materialisieren"]) == 2


class _Zelle:
    def __init__(self, auspraegungen, model_point):
        self.auspraegungen = auspraegungen
        self.model_point = model_point


class _Spez:
    def __init__(self, zellen):
        self.zellen = zellen


def test_zellen_toml_traegt_das_tarifwerk_der_fuehrung():
    """Die Schalter, mit denen uebernommen wurde, stehen im erzeugten
    Config-Abschnitt — sonst tippt sie jemand ab und vergisst einen."""
    tarifwerk = {"scheiben_mit_gamma1": True, "stoab_je_baustein": True,
                 "red_verfahren": "teilkuendigung"}
    zellen = [_Zelle({"status": "raucher"}, dict(GRUNDLAGEN, tafel="A")),
              _Zelle({"status": "nichtraucher"}, dict(GRUNDLAGEN, tafel="B"))]
    abschnitt = _zellen_toml(_Spez(zellen), "TG2015", tarifwerk)
    kopf = abschnitt.partition("[[generation.zelle]]")[0]
    for zeile in ("scheiben_mit_gamma1 = true", "stoab_je_baustein = true",
                  'red_verfahren = "teilkuendigung"'):
        assert zeile in kopf, zeile
    assert "zins = 0.0125" in kopf and 'tafel = "A"' in abschnitt
    # Ohne Zellen: nur das Tarifwerk, ohne Tarifwerk: gar nichts.
    assert "stoab_je_baustein = true" in _zellen_toml(_Spez([]), "TG2015", tarifwerk)
    assert _zellen_toml(_Spez([]), "TG2015") == ""


def test_zugang_und_bewegungskonto_tragen_die_mitgebrachten_bausteine():
    """Ledger-Herleitung (P-B1) und Bewegungskonto sehen den Zugang eines
    uebernommenen Vertrags MIT seinen Alt-Scheiben — sonst stuende dem
    Abgang mit Scheiben ein Zugang ohne gegenueber."""
    from rechner_pipeline.bestand.config import config_aus_text
    from rechner_pipeline.bestand.kennzahlen import bewegungskonto
    from rechner_pipeline.bestand.ledger_bindung import pruefe_ledger_betraege
    from rechner_pipeline.models.bestand import (
        LEDGER_SPALTEN,
        SCHEIBEN_SPALTEN,
        STATUS_HISTORIE_SPALTEN,
    )
    from tests.test_bestand_uebernommen_fortschreiben import _CONFIG_TOML, _stamm

    config = config_aus_text(_CONFIG_TOML)
    stamm = _stamm([{"id": 900_001, "beginn": "2015-01-01", "zugang": "2026-01-01"}])
    scheiben = pd.DataFrame([{
        "police_id": 900_001, "scheiben_id": 1, "erhoehung_jahr": 3,
        "erhoehung_datum": pd.Timestamp("2018-01-01"), "entry_age": 43,
        "duration": 22, "premium_duration": 22, "sum_insured": 5000.0,
        "gamma1": 0.0,
    }])[[n for n, _ in SCHEIBEN_SPALTEN]].astype(dict(SCHEIBEN_SPALTEN))
    historie = pd.DataFrame(columns=[n for n, _ in STATUS_HISTORIE_SPALTEN]).astype(
        dict(STATUS_HISTORIE_SPALTEN))

    def _ledger(zug: float) -> pd.DataFrame:
        return pd.DataFrame([{
            "police_id": 900_001, "tarif_generation": "klv/zellen",
            "ereignis": "ZUG", "vertragsjahr": 11,
            "status_date": pd.Timestamp("2026-01-01"), "betrag_art": "VS",
            "betrag": zug, "betrag_herkunft": "geliefert",
        }])[[n for n, _ in LEDGER_SPALTEN]].astype(dict(LEDGER_SPALTEN))

    assert pruefe_ledger_betraege(
        stamm, _ledger(105_000.0), config, scheiben=scheiben, historie=historie) == []
    fehler = pruefe_ledger_betraege(
        stamm, _ledger(100_000.0), config, scheiben=scheiben, historie=historie)
    assert fehler and "ZUG" in fehler[0]

    konto = bewegungskonto(stamm, historie, _ledger(105_000.0), scheiben,
                           bis=dt.date(2027, 1, 1))
    zeile = next(z for z in konto if z["jahr"] == 2025)
    assert zeile["bpfl"]["zugang_neuzugang"]["summe"] == 105_000.0
    assert all(ok for oks in zeile["identitaet"].values() for ok in oks.values())
