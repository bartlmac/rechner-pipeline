"""KLV-Bewegungskonto (BaFin-Nachweisungs-Struktur): Handrechnungen + Identitäten.

Diese Datei deckt die KLV-Nachweisung ab: Tracks beitragspflichtig/
beitragsfrei, Bezugsgroesse Versicherungssumme. Die BU-Nachweisung ist
eine EIGENE Groesse (Tracks Anwaerter/Rentner, Bezugsgroesse
Jahresrente) und liegt in ``test_bestand_bu.py`` — der Dateiname hier
sagt das jetzt, statt Produktneutralitaet zu suggerieren.

Die Handrechnungs-Tests treiben einzelne GeVo-Pfade deterministisch (Raten
0 bzw. nahe 1, Muster wie in test_bestand_ereignisse); der End-to-End-Test
prüft die Bestands-Identität Anfang + Zugang - Abgang = Endbestand über den
vollen Beispiel-Lauf, je Jahr, Track (bpfl/bfr) und Maß (Stück/Summe).

Knoten: klv
"""

from __future__ import annotations

import copy
import datetime as dt
from pathlib import Path

import pandas as pd
import pytest

from rechner_pipeline.bestand.config import Annahme, Annahmen, load_config
from rechner_pipeline.bestand.ereignisse import fortschreiben
from rechner_pipeline.bestand.generator import generate
from rechner_pipeline.bestand.kennzahlen import bewegungskonto
from rechner_pipeline.models.bestand import STAMM_SPALTEN

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = REPO_ROOT / "configs" / "bestand_klv.toml"


@pytest.fixture(scope="module")
def config():
    return load_config(EXAMPLE)


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
                # Eigenes Geschaeft: Zugang = Beginn. "zugang"
                # uebersteuert fuer uebernommene Vertraege.
                "bestandszugang": v.get("zugang", start),
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


def _alle_identitaeten_ok(konto) -> bool:
    return all(
        ok
        for zeile in konto
        for oks in zeile["identitaet"].values()
        for ok in oks.values()
    )


def _zeile(konto, jahr):
    return next(z for z in konto if z["jahr"] == jahr)


# --------------------------------------------------------------------------- #
# Handrechnungen (forcierte Einzelpfade)
# --------------------------------------------------------------------------- #


def test_reiner_ablauf_handrechnung(config):
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2005, 4, 1), "x": 40, "n": 10, "t": 10}
    )
    cfg = _mit_raten(config)  # alle Raten 0: nur der deterministische Ablauf
    historie, ledger, *_ = fortschreiben(stamm, cfg, dt.date(2016, 1, 1))
    konto = bewegungskonto(stamm, historie, ledger, bis=dt.date(2016, 1, 1))

    assert [z["jahr"] for z in konto] == list(range(2005, 2016))
    zugang = _zeile(konto, 2005)
    assert zugang["bpfl"]["anfang"] == {"stueck": 0, "summe": 0.0}
    assert zugang["bpfl"]["zugang_neuzugang"] == {"stueck": 1, "summe": 100000.0}
    assert zugang["bpfl"]["ende"] == {"stueck": 1, "summe": 100000.0}
    ruhig = _zeile(konto, 2010)
    assert ruhig["bpfl"]["anfang"] == ruhig["bpfl"]["ende"] == {
        "stueck": 1, "summe": 100000.0,
    }
    ablauf = _zeile(konto, 2015)
    assert ablauf["bpfl"]["abgang_ablauf"] == {"stueck": 1, "summe": 100000.0}
    assert ablauf["bpfl"]["ende"] == {"stueck": 0, "summe": 0.0}
    assert all(z["bfr"]["ende"] == {"stueck": 0, "summe": 0.0} for z in konto)
    assert _alle_identitaeten_ok(konto)


def test_pex_umbuchung_handrechnung(config):
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 6, 1), "x": 45, "n": 20, "t": 15}
    )
    cfg = _mit_raten(config, pex_rate=0.999999)  # PEX am 2011-06-01
    historie, ledger, *_ = fortschreiben(stamm, cfg, dt.date(2045, 1, 1))
    assert list(historie["status_code"]) == ["PEX", "ABL"]
    vs_bfr = float(ledger[ledger["ereignis"] == "PEX"]["betrag"].iloc[0])
    assert 0.0 < vs_bfr < 100000.0

    konto = bewegungskonto(stamm, historie, ledger, bis=dt.date(2045, 1, 1))
    umbuchung = _zeile(konto, 2011)
    # bpfl verliert die volle VS, bfr gewinnt die beitragsfreie Summe:
    assert umbuchung["bpfl"]["umbuchung_beitragsfrei"] == {
        "stueck": 1, "summe": 100000.0,
    }
    assert umbuchung["bpfl"]["ende"] == {"stueck": 0, "summe": 0.0}
    assert umbuchung["bfr"]["zugang_umbuchung"] == {"stueck": 1, "summe": vs_bfr}
    assert umbuchung["bfr"]["ende"] == {"stueck": 1, "summe": vs_bfr}
    ruhig = _zeile(konto, 2020)
    assert ruhig["bfr"]["anfang"] == ruhig["bfr"]["ende"] == {
        "stueck": 1, "summe": vs_bfr,
    }
    # Der beitragsfreie Ablauf geht mit VS_bfr ab, nicht mit der vollen VS:
    ablauf = _zeile(konto, 2030)
    assert ablauf["bfr"]["abgang_ablauf"] == {"stueck": 1, "summe": vs_bfr}
    assert ablauf["bfr"]["ende"] == {"stueck": 0, "summe": 0.0}
    assert ablauf["bpfl"]["abgang_ablauf"] == {"stueck": 0, "summe": 0.0}
    assert _alle_identitaeten_ok(konto)


def test_erhoehung_nur_summe_und_abgang_mit_scheiben(config):
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 6, 1), "x": 45, "n": 20, "t": 15}
    )
    cfg = _mit_raten(config, erh_rate=0.999999, erh_prozent=0.05)
    historie, ledger, scheiben, *_ = fortschreiben(stamm, cfg, dt.date(2045, 1, 1))
    assert len(scheiben) > 0

    konto = bewegungskonto(stamm, historie, ledger, scheiben, bis=dt.date(2045, 1, 1))
    erh_ledger = ledger[ledger["ereignis"] == "ERH"]
    for jahr, betrag in erh_ledger.groupby(erh_ledger["status_date"].dt.year)["betrag"]:
        zeile = _zeile(konto, int(jahr))
        # Erhoehung: Summen-Zugang ohne Stueck-Zugang.
        assert zeile["bpfl"]["zugang_erhoehung"] == {
            "stueck": 0, "summe": pytest.approx(float(betrag.sum())),
        }
    # Der Ablauf geht mit der GESAMT-VS ab (Stamm + alle Scheiben):
    ablauf = _zeile(konto, 2030)
    vs_gesamt = 100000.0 + float(scheiben["sum_insured"].sum())
    assert ablauf["bpfl"]["abgang_ablauf"]["stueck"] == 1
    assert ablauf["bpfl"]["abgang_ablauf"]["summe"] == pytest.approx(vs_gesamt)
    assert _alle_identitaeten_ok(konto)


def test_horizont_begrenzt_die_pruefbaren_jahre(config):
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 6, 1), "x": 45, "n": 20, "t": 15}
    )
    cfg = _mit_raten(config)  # Ablauf 2030 liegt HINTER dem Horizont 2020
    historie, ledger, *_ = fortschreiben(stamm, cfg, dt.date(2020, 1, 1))
    konto = bewegungskonto(stamm, historie, ledger, bis=dt.date(2020, 1, 1))
    # Jahr 2019 ist das letzte vollstaendige (Ende-Stichtag 1.1.2020 <= bis):
    assert [z["jahr"] for z in konto] == list(range(2010, 2020))
    assert _alle_identitaeten_ok(konto)
    # Ohne Horizont-Angabe traegt der Aufrufer die Verantwortung: das
    # Ablaufjahr 2030 ist nicht simuliert und die Identitaet dort
    # (dokumentiert) scheinbar verletzt.
    ungedeckt = bewegungskonto(stamm, historie, ledger)
    assert [z["jahr"] for z in ungedeckt] == list(range(2010, 2031))
    assert not _zeile(ungedeckt, 2030)["identitaet"]["bpfl"]["stueck"]


# --------------------------------------------------------------------------- #
# Voller Lauf: Identitaeten, Verkettung, Ledger-Abgleich
# --------------------------------------------------------------------------- #


def test_voller_lauf_identitaeten_und_verkettung(config):
    portfolio = generate(config)
    bis = dt.date(2035, 1, 1)
    historie, ledger, scheiben, *_ = fortschreiben(portfolio, config, bis)
    konto = bewegungskonto(portfolio, historie, ledger, scheiben, bis=bis)

    assert len(konto) > 30
    assert _alle_identitaeten_ok(konto)
    # Verkettung: Endbestand des Jahres J ist der Anfangsbestand von J+1.
    for a, b in zip(konto, konto[1:]):
        assert a["bpfl"]["ende"] == b["bpfl"]["anfang"]
        assert a["bfr"]["ende"] == b["bfr"]["anfang"]
    # Stueck-Abgleich gegen den Ledger im ausgewiesenen Zeitraum:
    von_ts = pd.Timestamp(dt.date(konto[0]["jahr"], 1, 1))
    bis_ts = pd.Timestamp(dt.date(konto[-1]["jahr"] + 1, 1, 1))
    fenster = ledger[
        (ledger["status_date"] > von_ts) & (ledger["status_date"] <= bis_ts)
    ]
    for code, positionen in (
        ("STO", [("bpfl", "abgang_storno")]),
        ("PEX", [("bpfl", "umbuchung_beitragsfrei")]),
        ("TOD", [("bpfl", "abgang_tod"), ("bfr", "abgang_tod")]),
        ("ABL", [("bpfl", "abgang_ablauf"), ("bfr", "abgang_ablauf")]),
    ):
        soll = int((fenster["ereignis"] == code).sum())
        ist = sum(z[t][p]["stueck"] for z in konto for t, p in positionen)
        assert ist == soll, code


# --------------------------------------------------------------------------- #
# Review-Fixes: Randjahr, Fail-fast, Toleranz-Skalierung, Berichts-Zeilen
# --------------------------------------------------------------------------- #


def test_zugang_am_ersten_januar_wird_ausgewiesen(config):
    """Review-Fix: Beginn genau am 1.1.J gehoert zur Periode J-1 — das
    Raster startet einen Tag frueher, sonst fehlt der Zugang still."""
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 1, 1), "x": 40, "n": 10, "t": 10}
    )
    cfg = _mit_raten(config)
    historie, ledger, *_ = fortschreiben(stamm, cfg, dt.date(2021, 1, 1))
    konto = bewegungskonto(stamm, historie, ledger, bis=dt.date(2021, 1, 1))
    assert konto[0]["jahr"] == 2009
    assert konto[0]["bpfl"]["zugang_neuzugang"] == {"stueck": 1, "summe": 100000.0}
    assert sum(z["bpfl"]["zugang_neuzugang"]["stueck"] for z in konto) == 1
    assert _alle_identitaeten_ok(konto)


def test_fail_fast_bei_inkonsistentem_ledger(config):
    """Review-Fix: inkonsistente Eingaben sind sprechende ValueErrors,
    keine KeyError-Abstuerze (Gate: Contract-Fehler statt Exit 50)."""
    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 6, 1), "x": 45, "n": 20, "t": 15}
    )
    cfg = _mit_raten(config, pex_rate=0.999999)
    historie, ledger, *_ = fortschreiben(stamm, cfg, dt.date(2045, 1, 1))

    fremd = ledger.copy()
    fremd.loc[fremd.index[0], "police_id"] = 99999999
    with pytest.raises(ValueError, match="ausserhalb des Bestands"):
        bewegungskonto(stamm, historie, fremd, bis=dt.date(2045, 1, 1))

    pex = ledger[ledger["ereignis"] == "PEX"]
    doppelt = pd.concat([ledger, pex], ignore_index=True)
    with pytest.raises(ValueError, match="mehrere PEX-Zeilen"):
        bewegungskonto(stamm, historie, doppelt, bis=dt.date(2045, 1, 1))

    ohne_pex = ledger.drop(index=pex.index).reset_index(drop=True)
    with pytest.raises(ValueError, match="ohne PEX-Ledger-Zeile"):
        bewegungskonto(stamm, historie, ohne_pex, bis=dt.date(2045, 1, 1))


def test_summen_toleranz_skaliert_mit_grossbestand():
    """Review-Fix: feste atol 1e-6 brach ab Gesamt-VS ~1e9 an blossem
    Float-Akkumulationsrauschen (andere Summationsreihenfolge Anfang/Ende
    vs. Zu-/Abgaenge). Exakt konsistenter 20k-Bestand muss gruen sein."""
    import numpy as np

    from rechner_pipeline.models.bestand import (
        LEDGER_SPALTEN,
        STATUS_HISTORIE_SPALTEN,
    )

    rng = np.random.default_rng(7)
    n = 20_000
    vs = np.round(rng.uniform(10_000, 500_000, n), 2)
    stamm = _mini_stamm(*[
        {
            "police_id": 10000001 + i,
            "start": dt.date(2000 + i % 20, 1 + i % 12, 1),
            "x": 40,
            "n": 30,
            "t": 25,
            "vs": float(vs[i]),
        }
        for i in range(n)
    ])
    leer_h = pd.DataFrame({
        name: pd.Series(dtype=dtype) for name, dtype in STATUS_HISTORIE_SPALTEN
    })
    leer_l = pd.DataFrame({
        name: pd.Series(dtype=dtype) for name, dtype in LEDGER_SPALTEN
    })
    konto = bewegungskonto(stamm, leer_h, leer_l, bis=dt.date(2025, 1, 1))
    assert float(stamm["sum_insured"].sum()) > 1e9
    assert _alle_identitaeten_ok(konto)


def test_report_zeigt_letztes_bfr_jahr_und_warnung_bei_bruch(config):
    """Review-Fixes: (a) das Jahr des letzten beitragsfreien Abgangs
    erscheint in den Bewegungstabellen (bfr-Anfang im Zeilenfilter);
    (b) der WARNUNG-Pfad ist erreichbar, wenn die Identitaet bricht."""
    from rechner_pipeline.bestand import report

    stamm = _mini_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 6, 1), "x": 45, "n": 20, "t": 15}
    )
    cfg = _mit_raten(config, pex_rate=0.999999)  # PEX 2011, ABL 2030 (bfr)
    historie, ledger, *_ = fortschreiben(stamm, cfg, dt.date(2045, 1, 1))
    stichtage = [dt.date(2015, 1, 1)]
    html = report.render_html(
        stamm, stichtage=stichtage, historie=historie, ledger=ledger,
        bis=dt.date(2045, 1, 1),
    )
    assert "<tr><td>2030</td>" in html
    assert "WARNUNG" not in html

    ohne_abl = ledger[ledger["ereignis"] != "ABL"].reset_index(drop=True)
    kaputt = report.render_html(
        stamm, stichtage=stichtage, historie=historie, ledger=ohne_abl,
        bis=dt.date(2045, 1, 1),
    )
    assert "WARNUNG" in kaputt
