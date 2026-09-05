"""Tagesjournal: Buchungstag aus Wirkungstag, Meldeverzug, Bijektion zum Ledger.

Fachkonzept docs/simulation/tagesbetrieb.md, Block B3. Der Ledger sagt,
WANN ein Vorfall wirkt; das Tagesjournal sagt, WANN das Unternehmen ihn
bucht. Der Validator haelt beide gegeneinander — und diese Datei haelt
den Validator: Jede Mutation, die er fangen soll, steht hier als Probe
(Zeile entfernt, Datum verschoben, Betrag geaendert, Zeile erfunden,
Zukunft, Dublette, Reihenfolge).

Knoten: system/betrieb
"""

from __future__ import annotations

import copy
import datetime as dt
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from rechner_pipeline.bestand.config import Annahme, load_config
from rechner_pipeline.bestand.ereignisse import fortschreiben
from rechner_pipeline.bestand.generator import generate
from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
from rechner_pipeline.betrieb.neugeschaeft import neugeschaeft_am, neugeschaeft_zwischen, verkaufstag
from rechner_pipeline.betrieb.tagesjournal import (
    TagesjournalError,
    buchungstag,
    faellige_zeilen,
    herkunft,
    meldeverzug_sigma,
    meldeverzug_tage,
    mit_buchungstagen,
    naechster_werktag,
    tagesjournal_ergaenzen,
    validate_tagesjournal,
)
from rechner_pipeline.models.bestand import TAGESJOURNAL_NAMES

REPO_ROOT = Path(__file__).resolve().parents[1]
PLV = REPO_ROOT / "configs" / "bestand_gesamt.toml"

BETRIEBSBEGINN = dt.date(2026, 1, 1)
HEUTE = dt.date(2026, 8, 9)          # ein Sonntag: Verkaeufe der Woche wirken erst am 1.9., ein Tod vom 1.8. ist noch ungemeldet
FRUEHER = dt.date(2026, 3, 31)


@pytest.fixture(scope="module")
def config():
    """Die PLV-Config mit kleinem Bestand und hohen Raten, damit jede
    Ereignisart im Fenster vorkommt."""
    cfg = copy.deepcopy(load_config(PLV))
    for g in cfg.generationen:
        g.sample_size = {"KLV-2004": 40, "KLV-2017": 400, "KLV-2022": 150,
                         "BU-2017": 100}.get(g.name, 0)
    cfg.annahmen.tod = Annahme(a=0.03, b=0.8)
    cfg.annahmen.storno = Annahme(a=0.12, b=0.0)
    cfg.annahmen.beitragsfreistellung = Annahme(a=0.08, b=0.0)
    cfg.annahmen.erhoehung = Annahme(a=0.4, b=0.0)
    cfg.annahmen.invalidisierung = Annahme(a=0.05, b=1.0)
    assert cfg.validate() == []
    return cfg


@pytest.fixture(scope="module")
def lauf(config):
    stamm = generate(config, bis=BETRIEBSBEGINN)
    zugaenge = neugeschaeft_zwischen(config, BETRIEBSBEGINN, HEUTE)
    ergebnis = fortschreiben(stamm, config, HEUTE, zugaenge=zugaenge)
    ledger = ergebnis.ledger
    # Eine gelieferte Buchung, wie sie eine Uebernahme mitbringt:
    police = int(stamm["police_id"].iloc[0])
    zeile = stamm[stamm["police_id"] == police].iloc[0]
    geliefert = pd.DataFrame([{
        "police_id": police, "tarif_generation": zeile["tarif_generation"],
        "ereignis": "ZUG", "vertragsjahr": 0, "status_date": zeile["insurance_start"],
        "betrag_art": "VS", "betrag": float(zeile["sum_insured"]),
        "betrag_herkunft": "geliefert",
    }])
    ledger = pd.concat([geliefert[ledger.columns], ledger], ignore_index=True)
    ledger = ledger.astype(ergebnis.ledger.dtypes.to_dict())
    return stamm, zugaenge, ledger


@pytest.fixture(scope="module")
def sicht(config, lauf):
    return mit_buchungstagen(config, lauf[2])


def test_der_lauf_traegt_alle_ereignisarten(lauf, sicht):
    ereignisse = set(lauf[2]["ereignis"])
    assert {"ZUG", "STO", "PEX", "ERH", "TOD", "ABL", "INV"} <= ereignisse
    im_betrieb = sicht[sicht["buchungsdatum"] >= pd.Timestamp(BETRIEBSBEGINN)]
    assert {"ZUG", "STO", "PEX", "ERH", "TOD"} <= set(im_betrieb["ereignis"])


# --------------------------------------------------------------------------- #
# Buchungstag-Regeln
# --------------------------------------------------------------------------- #


def test_werktagsregel():
    samstag, sonntag, montag = dt.date(2026, 8, 1), dt.date(2026, 8, 2), dt.date(2026, 8, 3)
    assert (samstag.weekday(), montag.weekday()) == (5, 0)
    assert naechster_werktag(samstag) == montag
    assert naechster_werktag(sonntag) == montag
    assert naechster_werktag(montag) == montag
    assert naechster_werktag(dt.date(2026, 5, 1)) == dt.date(2026, 5, 1)   # Freitag


def test_wirkungstag_auf_dem_wochenende_wird_montags_gebucht(sicht):
    """Mutationsprobe: Buchungstag = Wirkungstag ohne Werktagsrundung —
    dann stuenden Samstage im Journal."""
    ohne_verzug = sicht[(sicht["ereignis"] != "TOD") & (sicht["herkunft"] == "fortschreibung")]
    assert len(ohne_verzug) > 0
    wochenende = ohne_verzug[ohne_verzug["status_date"].dt.weekday >= 5]
    assert len(wochenende) > 0, "die Probe braucht Wirkungstage am Wochenende"
    for z in wochenende.itertuples(index=False):
        assert z.buchungsdatum.date() == naechster_werktag(z.status_date.date())
        assert z.buchungsdatum.weekday() == 0
    werktags = ohne_verzug[ohne_verzug["status_date"].dt.weekday < 5]
    assert (werktags["buchungsdatum"] == werktags["status_date"]).all()
    assert (sicht["buchungsdatum"].dt.weekday < 5).all()


def test_tod_wird_mit_meldeverzug_gebucht(config, sicht):
    """Mutationsprobe: Meldeverzug ignoriert — dann laege jeder Tod auf
    dem naechsten Werktag seines Wirkungstags."""
    tode = sicht[sicht["ereignis"] == "TOD"]
    assert len(tode) > 0
    spaeter = 0
    for z in tode.itertuples(index=False):
        wirkung = z.status_date.date()
        verzug = meldeverzug_tage(config, int(z.police_id), wirkung.year)
        assert verzug >= 0
        assert z.buchungsdatum.date() == naechster_werktag(wirkung + dt.timedelta(days=verzug))
        assert z.buchungsdatum.date() >= naechster_werktag(wirkung)
        spaeter += z.buchungsdatum.date() > naechster_werktag(wirkung)
    assert spaeter > 0
    # Deterministisch je Police und Jahr, unabhaengig von der Reihenfolge:
    assert meldeverzug_tage(config, 4711, 2026) == meldeverzug_tage(config, 4711, 2026)
    assert meldeverzug_tage(config, 4711, 2026) != meldeverzug_tage(config, 4712, 2026) or \
        meldeverzug_tage(config, 4711, 2027) != meldeverzug_tage(config, 4711, 2026)


def test_meldeverzug_folgt_der_konfigurierten_verteilung(config):
    verzug = config.tagesbetrieb.meldeverzug_tod
    sigma = meldeverzug_sigma(verzug)
    assert verzug.median_tage * math.exp(sigma * 1.6448536269514722) == pytest.approx(verzug.p95_tage)
    probe = np.array([meldeverzug_tage(config, pid, 2026) for pid in range(1, 2001)])
    assert 11 <= np.median(probe) <= 17
    assert (probe > verzug.p95_tage).mean() < 0.08
    assert probe.min() >= 0
    # Die Config bestimmt die Verteilung, nicht der Code:
    anders = copy.deepcopy(config)
    anders.tagesbetrieb.meldeverzug_tod = type(verzug)("lognormal", 40.0, 120.0)
    probe_anders = np.array([meldeverzug_tage(anders, pid, 2026) for pid in range(1, 2001)])
    assert np.median(probe_anders) > np.median(probe) + 15


def test_neugeschaeft_wird_am_verkaufstag_gebucht(config, lauf, sicht):
    """Mutationsprobe: ZUG des Tagesneugeschaefts nach der Werktagsregel
    gebucht — dann laege der Buchungstag auf dem Beginn statt davor."""
    _, zugaenge, _ = lauf
    neu = sicht[sicht["herkunft"] == "neugeschaeft"]
    assert set(neu["police_id"]) == set(zugaenge["police_id"])
    assert (neu["ereignis"] == "ZUG").all()
    assert (neu["buchungsdatum"] < neu["status_date"]).all()
    index = {g.name: (i, g) for i, g in enumerate(config.generationen)}
    for z in neu.head(15).itertuples(index=False):
        gen_name = str(zugaenge.set_index("police_id").loc[int(z.police_id), "tarif_generation"])
        i, gen = index[gen_name]
        tag = verkaufstag(gen, i, int(z.police_id))
        assert z.buchungsdatum.date() == tag
        assert int(z.police_id) in set(neugeschaeft_am(config, tag)["police_id"])


def test_gelieferte_buchung_stammt_aus_der_uebernahme(sicht):
    ueb = sicht[sicht["herkunft"] == "uebernahme"]
    assert len(ueb) == 1
    z = ueb.iloc[0]
    assert z["ereignis"] == "ZUG"
    assert z["buchungsdatum"].date() == naechster_werktag(z["status_date"].date())
    assert herkunft(load_config(PLV), 1, "PEX", "geliefert", "KLV-2017") == "uebernahme"
    assert herkunft(load_config(PLV), 1, "STO", "gerechnet", "KLV-2017") == "fortschreibung"


def test_ledger_schluessel_muss_eindeutig_sein(config, lauf):
    ledger = lauf[2]
    doppelt = pd.concat([ledger, ledger.iloc[[5]]], ignore_index=True)
    with pytest.raises(TagesjournalError, match="nicht eindeutig"):
        mit_buchungstagen(config, doppelt)


# --------------------------------------------------------------------------- #
# Anfuegen und Bijektion
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def journale(config, lauf):
    ledger = lauf[2]
    leer = pd.DataFrame({n: pd.Series(dtype=d) for n, d in zip(
        TAGESJOURNAL_NAMES, ["datetime64[ns]", "int64", "object", "datetime64[ns]",
                             "float64", "object", "object"])})
    j1, neu1 = tagesjournal_ergaenzen(leer, ledger, config, FRUEHER, ab_tag=BETRIEBSBEGINN)
    j2, neu2 = tagesjournal_ergaenzen(j1, ledger, config, HEUTE, ab_tag=BETRIEBSBEGINN)
    return j1, neu1, j2, neu2


def _pruefe(journal, ledger, config, bis_tag=HEUTE):
    return validate_tagesjournal(journal, ledger, config, bis_tag, ab_tag=BETRIEBSBEGINN)


def test_journal_ist_bijektiv_bis_zum_gefuehrten_tag(config, lauf, sicht, journale):
    ledger = lauf[2]
    j1, neu1, j2, neu2 = journale
    assert len(j1) == len(neu1) > 0
    assert _pruefe(j1, ledger, config, FRUEHER) == []
    assert _pruefe(j2, ledger, config) == []
    assert len(j2) == len(faellige_zeilen(sicht, HEUTE, BETRIEBSBEGINN)) == len(j1) + len(neu2)
    assert (j2["buchungsdatum"] >= pd.Timestamp(BETRIEBSBEGINN)).all()
    # Nur angefuegt: das fruehere Journal ist das Praefix des spaeteren.
    pd.testing.assert_frame_equal(j2.iloc[: len(j1)].reset_index(drop=True), j1)
    assert (neu2["buchungsdatum"] > pd.Timestamp(FRUEHER)).all()
    # Ein drittes Anfuegen ohne neue Faelligkeit aendert nichts:
    j3, neu3 = tagesjournal_ergaenzen(j2, ledger, config, HEUTE, ab_tag=BETRIEBSBEGINN)
    assert len(neu3) == 0
    pd.testing.assert_frame_equal(j3, j2)


def test_vorgeschichte_bleibt_ausserhalb(sicht, journale):
    """Buchungen vor dem Betriebsbeginn stehen im Ledger (die Engine
    simuliert jeden Vertrag ab seinem Beginn), aber nicht im Journal."""
    vorher = sicht[sicht["buchungsdatum"] < pd.Timestamp(BETRIEBSBEGINN)]
    assert len(vorher) > 0 and "ABL" in set(vorher["ereignis"])
    j2 = journale[2]
    assert not set(zip(vorher["police_id"], vorher["ereignis"], vorher["status_date"])) & set(
        zip(j2["police_id"], j2["ereignis"], j2["status_date"]))


def test_das_unternehmen_weiss_noch_nicht_alles(sicht, journale):
    """Wirkung vor Buchung: Am gefuehrten Tag gibt es Ledger-Zeilen, die
    schon wirken, aber noch nicht gebucht sind (Meldeverzug, Wochenende) —
    und Neugeschaeft, das gebucht ist, aber noch nicht wirkt."""
    j2 = journale[2]
    gewirkt = sicht[sicht["status_date"] <= pd.Timestamp(HEUTE)]
    noch_nicht = gewirkt[gewirkt["buchungsdatum"] > pd.Timestamp(HEUTE)]
    assert len(noch_nicht) > 0
    assert not set(zip(noch_nicht["police_id"], noch_nicht["ereignis"])) & set(
        zip(j2["police_id"], j2["ereignis"]))
    gebucht_vor_wirkung = j2[j2["status_date"] > pd.Timestamp(HEUTE)]
    assert len(gebucht_vor_wirkung) > 0
    assert set(gebucht_vor_wirkung["herkunft"]) == {"neugeschaeft"}


def _ohne(journal: pd.DataFrame, pos: int) -> pd.DataFrame:
    return journal.drop(index=journal.index[pos]).reset_index(drop=True)


def test_validator_faengt_die_mutationen(config, lauf, journale):
    """Zeile entfernt, Datum verschoben, Betrag geaendert, Zeile erfunden,
    Zukunft, Dublette, Reihenfolge, Herkunft — jede einzeln."""
    ledger = lauf[2]
    j2 = journale[2]
    mitte = len(j2) // 2

    entfernt = _ohne(j2, mitte)
    assert any("faellige Buchung(en) fehlen" in f
               for f in _pruefe(entfernt, ledger, config))

    verschoben = j2.copy()
    # ein Werktag, dessen Verschiebung um einen Tag im gefuehrten Fenster bleibt:
    pos = next(i for i in range(len(j2)) if j2["buchungsdatum"].iloc[i].weekday() < 3)
    verschoben.loc[verschoben.index[pos], "buchungsdatum"] += pd.Timedelta(days=1)
    fehler = _pruefe(verschoben, ledger, config)
    assert any("statt abgeleitet" in f for f in fehler), fehler

    betrag = j2.copy()
    betrag.loc[betrag.index[mitte], "betrag"] += 1.0
    assert any("Betrag" in f for f in _pruefe(betrag, ledger, config))

    erfunden = pd.concat([j2, j2.iloc[[mitte]].assign(ereignis="STO", status_date=pd.Timestamp("2026-04-01"))],
                         ignore_index=True)
    assert any("ohne Ledger-Zeile" in f
               for f in _pruefe(erfunden, ledger, config))

    zukunft = j2.copy()
    zukunft.loc[zukunft.index[-1], "buchungsdatum"] = pd.Timestamp(HEUTE) + pd.Timedelta(days=3)
    assert any("nach dem gefuehrten Tag" in f
               for f in _pruefe(zukunft, ledger, config))

    dublette = pd.concat([j2, j2.iloc[[mitte]]], ignore_index=True)
    assert any("doppelt" in f for f in _pruefe(dublette, ledger, config))

    vertauscht = pd.concat([j2.iloc[[-1]], j2.iloc[:-1]], ignore_index=True)
    assert any("nicht nur angefuegt" in f
               for f in _pruefe(vertauscht, ledger, config))

    fremd = j2.copy()
    fremd.loc[fremd.index[mitte], "herkunft"] = "neugeschaeft" if fremd["herkunft"].iloc[mitte] != "neugeschaeft" else "fortschreibung"
    assert any("herkunft" in f for f in _pruefe(fremd, ledger, config))

    falsch = j2.copy()
    falsch.loc[falsch.index[mitte], "herkunft"] = "erfunden"
    assert any("ausserhalb" in f for f in _pruefe(falsch, ledger, config))

    assert any("Spalten" in f for f in _pruefe(j2.drop(columns="betrag_art"), ledger, config))
    # Ein leeres Journal ist nur dann in Ordnung, wenn nichts faellig ist:
    leer = j2.iloc[0:0]
    assert any("leer" in f for f in _pruefe(leer, ledger, config))
    assert validate_tagesjournal(leer, ledger, config, dt.date(2026, 1, 1), ab_tag=dt.date(2026, 1, 1)) == [] \
        or any("faellig" in f for f in validate_tagesjournal(leer, ledger, config, dt.date(2026, 1, 1), ab_tag=dt.date(2026, 1, 1)))
    # Eine Buchung vor dem Betriebsbeginn gehoert nicht ins Journal:
    vorher = j2.copy()
    vorher.loc[vorher.index[0], "buchungsdatum"] = pd.Timestamp("2025-12-30")
    assert any("vor dem Betriebsbeginn" in f for f in _pruefe(vorher, ledger, config))


def test_ergaenzen_verweigert_rueckwaerts_und_kaputte_journale(config, lauf, journale):
    ledger = lauf[2]
    j2 = journale[2]
    with pytest.raises(TagesjournalError, match="rueckwaerts"):
        tagesjournal_ergaenzen(j2, ledger, config, FRUEHER, ab_tag=BETRIEBSBEGINN)
    with pytest.raises(TagesjournalError, match="passt nicht zum Ledger"):
        tagesjournal_ergaenzen(_ohne(j2, 3), ledger, config, HEUTE, ab_tag=BETRIEBSBEGINN)
    with pytest.raises(TagesjournalError, match="vor dem Betriebsbeginn"):
        tagesjournal_ergaenzen(j2, ledger, config, HEUTE, ab_tag=HEUTE + dt.timedelta(days=1))
    # Ein Ledger, der eine gebuchte Zeile verloren hat, ist ein Befund:
    schluessel = list(zip(j2["police_id"], j2["ereignis"], j2["status_date"]))
    treffer = next(i for i, z in enumerate(ledger.itertuples(index=False))
                   if (int(z.police_id), z.ereignis, z.status_date) in set(schluessel))
    verlust = ledger.drop(index=ledger.index[[treffer]]).reset_index(drop=True)
    fehler = _pruefe(j2, verlust, config)
    assert fehler and any("ohne Ledger-Zeile" in f for f in fehler)


def test_journal_ist_parquet_deterministisch(journale, tmp_path):
    j2 = journale[2]
    a = write_portfolio(j2, tmp_path / "a.parquet")
    b = write_portfolio(j2, tmp_path / "b.parquet")
    assert a.read_bytes() == b.read_bytes()
    zurueck = read_portfolio(a)
    assert list(zurueck.columns) == list(TAGESJOURNAL_NAMES)
    pd.testing.assert_frame_equal(zurueck, j2)


def test_buchungstag_der_einzelnen_regeln(config, lauf):
    stamm = lauf[0]
    gen = next(g for g in config.generationen if g.name == "KLV-2017")
    assert buchungstag(config, 1, "STO", dt.date(2026, 8, 1), "fortschreibung", gen.name) == dt.date(2026, 8, 3)
    assert buchungstag(config, 1, "ERH", dt.date(2026, 5, 1), "fortschreibung", gen.name) == dt.date(2026, 5, 1)
    tod = buchungstag(config, 1, "TOD", dt.date(2026, 8, 1), "fortschreibung", gen.name)
    assert tod >= dt.date(2026, 8, 3) and tod.weekday() < 5
    with pytest.raises(TagesjournalError, match="nicht in der Config"):
        buchungstag(config, 1, "ZUG", dt.date(2026, 9, 1), "neugeschaeft", "FREMD")
    with pytest.raises(TagesjournalError, match="Nummernkreis"):
        buchungstag(config, int(stamm["police_id"].iloc[0]), "ZUG", dt.date(2026, 9, 1),
                    "neugeschaeft", gen.name)
