"""Neuzugang: zeitindexierte Zugangs-Draws, Praefix-Konstanz, GeVo-Strom.

Design (Beschluss 2026-08-12): EIN GeVo-Strom und EIN Datenmodell — der
Generator ist die Batch-Auswertung bis zum Referenzstichtag, der Neuzugang
setzt denselben Erzeuger inkrementell fort (Substream je Generation und
Kalenderjahr, jahrgangsstabile police_ids, Filterung statt horizontabhaengiger
Draws).
"""

from __future__ import annotations

import copy
import datetime as dt
from pathlib import Path

import pandas as pd
import pytest

from rechner_pipeline.bestand.config import Annahme, Annahmen, load_config
from rechner_pipeline.bestand.ereignisse import (
    EreignisError,
    fortschreiben,
    mit_zugaengen,
)
from rechner_pipeline.bestand.generator import neuzugaenge
from rechner_pipeline.bestand.zeitscheibe import zeitscheibe
from rechner_pipeline.models.bestand import STAMM_SPALTEN, validate_portfolio

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = REPO_ROOT / "examples" / "bestand_klv.toml"

REF = dt.date(2010, 1, 1)


@pytest.fixture(scope="module")
def config():
    cfg = copy.deepcopy(load_config(EXAMPLE))
    cfg.generationen[1].neuzugang_pro_jahr = 20  # KLV-2008 (2005-2015)
    return cfg


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
            }
        )
    df = pd.DataFrame(rows)
    for name, dtype in STAMM_SPALTEN:
        if dtype == "datetime64[ns]":
            df[name] = pd.to_datetime(df[name])
        else:
            df[name] = df[name].astype(dtype)
    return df[[n for n, _ in STAMM_SPALTEN]]


def test_neuzugaenge_liegen_im_fenster_und_gueltigkeitsraum(config):
    bis = dt.date(2014, 1, 1)
    zugaenge = neuzugaenge(config, REF, bis)
    assert len(zugaenge) > 0
    starts = zugaenge["insurance_start"]
    assert (starts > pd.Timestamp(REF)).all()
    assert (starts <= pd.Timestamp(bis)).all()
    # Nur KLV-2008 hat Neuzugang konfiguriert; Fenster 2005..2015:
    assert set(zugaenge["tarif_generation"]) == {"KLV-2008"}
    # Nummernkreis: Offset 2 Mio im Generations-Block, disjunkt vom Batch:
    assert (zugaenge["police_id"] > 2 * 10_000_000 + 2_000_000).all()
    assert not zugaenge["police_id"].duplicated().any()
    # Volle Jahrgaenge im Fenster tragen den konfigurierten Jahres-Zugang:
    je_jahr = starts.dt.year.value_counts()
    for jahr in (2011, 2012, 2013):
        assert je_jahr.get(jahr, 0) == 20


def test_neuzugang_praefix_konstanz(config):
    frueh = dt.date(2012, 1, 1)
    z_frueh = neuzugaenge(config, REF, frueh)
    z_spaet = neuzugaenge(config, REF, dt.date(2015, 6, 1))
    praefix = z_spaet[z_spaet["insurance_start"] <= pd.Timestamp(frueh)].reset_index(
        drop=True
    )
    pd.testing.assert_frame_equal(praefix, z_frueh)


def test_fortschreiben_mit_neuzugang_liefert_zug_gevos(config):
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2000, 3, 1), "x": 40, "n": 30,
         "t": 25, "tarif_generation": "KLV-1994"}
    )
    ergebnis = fortschreiben(stamm, config, dt.date(2014, 1, 1), neuzugang_ab=REF)
    zugaenge = ergebnis.zugaenge
    assert len(zugaenge) > 0
    zug = ergebnis.ledger[ergebnis.ledger["ereignis"] == "ZUG"]
    assert len(zug) == len(zugaenge)
    assert set(zug["betrag_art"]) == {"VS"}
    assert (zug["vertragsjahr"] == 0).all()
    assert set(zug["tarif_generation"]) == {"KLV-2008"}
    erwartet = zugaenge.set_index("police_id")["sum_insured"]
    for _, zeile in zug.iterrows():
        assert zeile["betrag"] == erwartet.loc[zeile["police_id"]]
    # ZUG ist GeVo, kein Statuswechsel:
    assert "ZUG" not in set(ergebnis.historie["status_code"])
    # Gesamtbestand erfuellt den Basis-Contract:
    assert validate_portfolio(mit_zugaengen(stamm, zugaenge)) == []


def test_neuzugaenge_werden_mitsimuliert(config):
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2000, 3, 1), "x": 40, "n": 30,
         "t": 25, "tarif_generation": "KLV-1994"}
    )
    cfg = copy.copy(config)
    cfg.annahmen = Annahmen(tod=Annahme(a=0.0, b=1e12))  # sicherer Tod im Jahr 1
    ergebnis = fortschreiben(stamm, cfg, dt.date(2020, 1, 1), neuzugang_ab=REF)
    zugang_ids = set(ergebnis.zugaenge["police_id"])
    assert zugang_ids
    tode = ergebnis.historie[ergebnis.historie["status_code"] == "TOD"]
    assert zugang_ids <= set(tode["police_id"])  # jeder Zugang stirbt im Jahr 1
    # Zeitscheibe auf dem Gesamtbestand: nach dem Tod niemand mehr in-force
    # (der Basis-Vertrag stirbt ebenfalls im ersten Jahr nach 2000):
    sicht = mit_zugaengen(stamm, ergebnis.zugaenge)
    from rechner_pipeline.bestand.ereignisse import bestand_mit_historie

    voll = bestand_mit_historie(sicht, ergebnis.historie)
    scheibe = zeitscheibe(voll, dt.date(2019, 1, 1))
    assert len(scheibe) == 0


def test_zeitscheibe_zaehlt_neuzugaenge_nach_referenzstichtag(config):
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2000, 3, 1), "x": 40, "n": 30,
         "t": 25, "tarif_generation": "KLV-1994"}
    )
    ergebnis = fortschreiben(stamm, config, dt.date(2014, 1, 1), neuzugang_ab=REF)
    sicht = mit_zugaengen(stamm, ergebnis.zugaenge)
    davor = zeitscheibe(sicht, REF)
    danach = zeitscheibe(sicht, dt.date(2013, 6, 1))
    assert len(davor) == 1  # nur der Basis-Vertrag
    assert len(danach) > len(davor)


def test_guard_gegen_doppelbesiedelung(config):
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2012, 3, 1), "x": 40, "n": 20,
         "t": 15, "tarif_generation": "KLV-1994"}
    )
    with pytest.raises(EreignisError, match="Referenzstichtag"):
        fortschreiben(stamm, config, dt.date(2014, 1, 1), neuzugang_ab=REF)


def test_ohne_neuzugang_bleibt_alles_beim_alten(config):
    """neuzugang_ab=None ist der bisherige Pfad: leere Zugaenge, kein ZUG."""
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2000, 3, 1), "x": 40, "n": 30,
         "t": 25, "tarif_generation": "KLV-1994"}
    )
    ergebnis = fortschreiben(stamm, config, dt.date(2014, 1, 1))
    assert len(ergebnis.zugaenge) == 0
    assert "ZUG" not in set(ergebnis.ledger["ereignis"])


def test_generate_mit_referenzstichtag_ist_exakte_teilmenge(config):
    """Review-Fix (HOCH): generate(config, bis=REF) = Batch-Auswertung des
    Zugangs-Stroms bis REF — draw-then-filter, exakte Teilmenge des vollen
    Laufs."""
    from rechner_pipeline.bestand.generator import generate

    voll = generate(config)
    beschnitten = generate(config, bis=REF)
    erwartet = voll[voll["insurance_start"] <= pd.Timestamp(REF)].reset_index(
        drop=True
    )
    pd.testing.assert_frame_equal(beschnitten, erwartet)
    assert 0 < len(beschnitten) < len(voll)


def test_ein_config_workflow_funktioniert_ende_zu_ende(config):
    """Der dokumentierte Hauptpfad mit EINER Config: Batch bis REF,
    Fortschreibung mit Neuzugang danach — ohne Guard-Konflikt."""
    from rechner_pipeline.bestand.generator import generate

    basis = generate(config, bis=REF)
    ergebnis = fortschreiben(basis, config, dt.date(2014, 1, 1), neuzugang_ab=REF)
    assert len(ergebnis.zugaenge) > 0
    bestand = mit_zugaengen(basis, ergebnis.zugaenge)
    assert validate_portfolio(bestand) == []
    # Alle Ledger-Policen liegen im Gesamtbestand:
    assert set(ergebnis.ledger["police_id"]) <= set(bestand["police_id"])


def test_neuzugang_ab_ohne_konfigurierten_neuzugang_ist_noop(config):
    """Review-Fix: npj ueberall 0 -> neuzugang_ab wirkt wie None (kein
    irrefuehrender Doppelbesiedelungs-Fehler)."""
    cfg = copy.deepcopy(config)
    for g in cfg.generationen:
        g.neuzugang_pro_jahr = 0
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2012, 3, 1), "x": 40, "n": 20,
         "t": 15, "tarif_generation": "KLV-1994"}
    )
    # Start nach REF, aber Feature aus -> kein Guard, identisch zu None:
    ergebnis = fortschreiben(stamm, cfg, dt.date(2014, 1, 1), neuzugang_ab=REF)
    assert len(ergebnis.zugaenge) == 0


def test_neuzugang_ab_nach_horizont_ist_fehler(config):
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2000, 3, 1), "x": 40, "n": 30,
         "t": 25, "tarif_generation": "KLV-1994"}
    )
    with pytest.raises(EreignisError, match="vertauschte Argumente"):
        fortschreiben(stamm, config, dt.date(2008, 1, 1), neuzugang_ab=REF)


def test_kaputte_config_wird_in_neuzugaenge_validiert(config):
    from rechner_pipeline.bestand.config import TarifGeneration

    cfg = copy.deepcopy(config)
    cfg.generationen.append(
        TarifGeneration(
            name="KAPUTT", gueltig_von=dt.date(2005, 1, 1),
            gueltig_bis=dt.date(2015, 12, 31), sample_size=10,
            max_endalter=85, neuzugang_pro_jahr=5,
        )
    )
    with pytest.raises(ValueError, match="Config ungueltig"):
        neuzugaenge(cfg, REF, dt.date(2014, 1, 1))


def test_randjahrgang_traegt_anteiliges_volumen():
    """Review-Fix: Rand-Jahrgaenge ziehen ueber alle 12 Monate und verwerfen
    ausserfensterige Draws — gleiche Monatsdichte wie volle Jahrgaenge."""
    cfg = copy.deepcopy(load_config(EXAMPLE))
    cfg.generationen[0].neuzugang_pro_jahr = 240  # KLV-1994: ab 1994-07-01
    von = dt.date(1994, 1, 1)
    zugaenge = neuzugaenge(cfg, von, dt.date(1996, 12, 31))
    je_jahr = zugaenge["insurance_start"].dt.year.value_counts()
    # 1994 hat nur 6 waehlbare Monate (Jul-Dez): erwartet ~120 statt 240.
    assert je_jahr.get(1995, 0) > 200
    assert 60 < je_jahr.get(1994, 0) < 180
    # Keine Starts vor dem Gueltigkeitsfenster:
    assert (zugaenge["insurance_start"] >= pd.Timestamp(dt.date(1994, 7, 1))).all()


def test_report_lehnt_ledger_mit_fremden_policen_ab(config):
    from rechner_pipeline.bestand import report
    from rechner_pipeline.bestand.generator import generate

    basis = generate(config, bis=REF)
    ergebnis = fortschreiben(basis, config, dt.date(2014, 1, 1), neuzugang_ab=REF)
    with pytest.raises(ValueError, match="Gesamtbestand"):
        report.render_html(
            basis, historie=ergebnis.historie, ledger=ergebnis.ledger
        )
    # Mit Gesamtbestand rendert der Bericht und weist die Zugaenge aus:
    bestand = mit_zugaengen(basis, ergebnis.zugaenge)
    html = report.render_html(
        bestand,
        stichtage=[dt.date(2012, 1, 1)],
        historie=ergebnis.historie,
        ledger=ergebnis.ledger,
        scheiben=ergebnis.scheiben,
        bis=dt.date(2014, 1, 1),
    )
    assert "Neuzugang (ZUG)" in html
    assert "Bestandsbewegung (Nachweisungs-Struktur)" in html
    assert "WARNUNG" not in html


def test_config_validierung_neuzugang(config):
    kaputt = copy.deepcopy(config)
    kaputt.generationen[0].neuzugang_pro_jahr = -1
    assert any("neuzugang_pro_jahr" in f for f in kaputt.validate())
    kaputt.generationen[0].neuzugang_pro_jahr = 20_000
    assert any("neuzugang_pro_jahr" in f for f in kaputt.validate())
