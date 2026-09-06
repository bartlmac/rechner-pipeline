"""Regressionen zur externen Reviewrunde T18 (Bestandsfuehrung, 2026-09-01).

Der Kernbefund der Runde war ein MUSTER: Ueber drei Runden wanderte
dieselbe Fehlerklasse eine Ebene tiefer, weil Praedikate ueber FORMEN
geprueft wurden (None? leer?) statt der IDENTITAET, die gelten muss —
die Teile eines Bundles stammen aus demselben Lauf (T18-02,
tests/test_bestand_manifest.py), was geprueft wurde, wird verarbeitet
(T18-03, tests/test_bestand_abschluss.py), und jede Zeile folgt aus
ihrer Buchung (hier: T18-01, -04, -05, -06, -07).

Jeder Test stellt den Nachweis des Reviews nach und waere VOR der
Korrektur gruen gewesen.

Knoten: system/bestand
"""

from __future__ import annotations

import datetime as _dt
import os
import stat
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from rechner_pipeline.bestand import cli_abschluss, cli_fortschreibung, cli_report
from rechner_pipeline.bestand.abschluss import AbschlussError, schreibe_abschluss
from rechner_pipeline.bestand.config import load_config
from rechner_pipeline.bestand.manifest import MANIFEST_DATEI, schreibe_manifest
from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
from rechner_pipeline.gates import bestand_validate
from rechner_pipeline.models.bestand import (
    ABSCHLUSS_NAMES,
    EREIGNIS_VALUES,
    validate_abschluss,
    validate_ledger,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = REPO_ROOT / "configs" / "bestand_klv.toml"
HORIZONT = _dt.date(2020, 1, 1)
STICHTAG = _dt.date(2016, 1, 1)


@pytest.fixture(scope="module")
def lauf(tmp_path_factory) -> Path:
    ziel = tmp_path_factory.mktemp("lauf")
    assert cli_fortschreibung.main([
        "--config", str(CONFIG), "--bis", HORIZONT.isoformat(),
        "--out-dir", str(ziel),
    ]) == 0
    return ziel


@pytest.fixture(scope="module")
def tabellen(lauf):
    return {
        name: read_portfolio(lauf / f"{name}.parquet")
        for name in ("bestand_gesamt", "historie", "ledger", "scheiben")
    }


def _lauf_kopie(lauf: Path, tmp_path: Path, **ersatz: pd.DataFrame) -> Path:
    """Ein Lauf mit gezielt getauschten Tabellen — und NEU geschriebenem
    Manifest: Die Tests hier pruefen die Semantik, nicht die Bindung."""
    ziel = tmp_path / "lauf"
    ziel.mkdir()
    for pfad in lauf.glob("*.parquet"):
        (ziel / pfad.name).write_bytes(pfad.read_bytes())
    for name, tabelle in ersatz.items():
        write_portfolio(tabelle, ziel / f"{name}.parquet")
    schreibe_manifest(ziel, horizont=HORIZONT, neuzugang_ab=None,
                      config_pfad=CONFIG, ausgaben=sorted(ziel.glob("*.parquet")))
    return ziel


def _abschluss_argv(lauf_dir: Path, out: Path) -> list:
    return ["--config", str(CONFIG), "--lauf", str(lauf_dir),
            "--stichtag", STICHTAG.isoformat(), "--bis", HORIZONT.isoformat(),
            "--out-dir", str(out)]


def _gate(lauf_dir: Path, tmp_path: Path, **rollen: Path):
    argv = ["--portfolio", str(lauf_dir / "bestand_gesamt.parquet"),
            "--historie", str(lauf_dir / "historie.parquet"),
            "--ledger", str(lauf_dir / "ledger.parquet"),
            "--scheiben", str(lauf_dir / "scheiben.parquet"),
            "--bis", HORIZONT.isoformat(),
            "--diagnostics-dir", str(tmp_path / "diag")]
    for rolle, pfad in rollen.items():
        argv[argv.index(f"--{rolle}") + 1] = str(pfad)
    return bestand_validate.main(argv)


# --------------------------------------------------------------------------- #
# T18-01: ERH-Ledger und Scheiben sind ZEILENWEISE gebunden, nicht ueber Summen
# --------------------------------------------------------------------------- #

def test_vertauschte_scheibenbetraege_fallen_auf(tabellen, tmp_path, lauf):
    """Der Nachweis des Reviews: zwei Scheibenbetraege verschiedener
    Policen vertauscht — Jahressummen unveraendert, P-B1 meldete 0
    Fehler, der Abschluss verschob sich um 63,70 EUR."""
    stamm, historie, ledger = tabellen["bestand_gesamt"], tabellen["historie"], tabellen["ledger"]
    scheiben = tabellen["scheiben"].copy()
    # Zwei Scheiben am selben Datum, verschiedene Policen, verschiedene Betraege.
    gruppen = scheiben.groupby("erhoehung_datum")
    datum = next(d for d, g in gruppen
                 if g["police_id"].nunique() >= 2 and g["sum_insured"].nunique() >= 2)
    kandidaten = scheiben[scheiben["erhoehung_datum"] == datum]
    a, b = kandidaten.index[0], kandidaten.index[1]
    assert scheiben.loc[a, "sum_insured"] != scheiben.loc[b, "sum_insured"]
    assert validate_ledger(stamm, ledger, historie=historie, scheiben=tabellen["scheiben"]) == []

    scheiben.loc[a, "sum_insured"], scheiben.loc[b, "sum_insured"] = (
        scheiben.loc[b, "sum_insured"], scheiben.loc[a, "sum_insured"])

    befunde = validate_ledger(stamm, ledger, historie=historie, scheiben=scheiben)
    assert any("anderem Betrag als ihre Scheibe" in b for b in befunde), befunde

    # Und end-to-end: das Gate wird rot, der Abschluss schreibt nichts.
    lauf_dir = _lauf_kopie(lauf, tmp_path, scheiben=scheiben)
    assert _gate(lauf_dir, tmp_path).exit_code == 20
    assert cli_abschluss.main(_abschluss_argv(lauf_dir, tmp_path / "ab")) == 2
    assert not (tmp_path / "ab").exists() or not list((tmp_path / "ab").iterdir())


def test_scheibe_ohne_buchung_und_buchung_ohne_scheibe(tabellen):
    stamm, historie, ledger, scheiben = (
        tabellen["bestand_gesamt"], tabellen["historie"], tabellen["ledger"], tabellen["scheiben"])
    erh = ledger.index[ledger["ereignis"] == "ERH"][0]

    ohne_buchung = ledger.drop(index=erh).reset_index(drop=True)
    befunde = validate_ledger(stamm, ohne_buchung, historie=historie, scheiben=scheiben)
    assert any("Scheibe(n) ohne ERH-Buchung" in b for b in befunde), befunde

    pid, datum = ledger.loc[erh, "police_id"], ledger.loc[erh, "status_date"]
    ohne_scheibe = scheiben[~((scheiben["police_id"] == pid)
                              & (scheiben["erhoehung_datum"] == datum))].reset_index(drop=True)
    befunde = validate_ledger(stamm, ledger, historie=historie, scheiben=ohne_scheibe)
    assert any("ERH-Buchung(en) ohne Scheibe" in b for b in befunde), befunde


# --------------------------------------------------------------------------- #
# T18-06: Der Ledger hat eine Semantik, und sie wird geprueft
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("spalte, wert, erwartet", [
    ("betrag", float("inf"), "nichtendliche Werte (inf) in betrag"),
    ("betrag", float("nan"), "fehlende Werte (NaN) in betrag"),
    ("betrag", -1.0, "betrag < 0"),
    ("betrag_art", "MANIPULIERT", "betrag_art passt nicht zum GeVo"),
    ("ereignis", "MANIPULIERT", "ereignis ausserhalb"),
    ("tarif_generation", "MANIPULIERT", "tarif_generation weicht vom Stammsatz ab"),
    ("vertragsjahr", 999, "vertragsjahr ausserhalb [0, duration]"),
    ("betrag_herkunft", "geraten", "betrag_herkunft ausserhalb"),
])
def test_manipulierte_stornozeile_faellt_auf(tabellen, spalte, wert, erwartet):
    """Der Nachweis des Reviews: in einer echten STO-Zeile passierten
    betrag=inf, betrag_art=MANIPULIERT, fremde tarif_generation und
    vertragsjahr=999 mit je 0 P-B1-Fehlern."""
    stamm, historie, scheiben = tabellen["bestand_gesamt"], tabellen["historie"], tabellen["scheiben"]
    ledger = tabellen["ledger"].copy()
    sto = ledger.index[ledger["ereignis"] == "STO"][0]
    ledger.loc[sto, spalte] = wert

    befunde = validate_ledger(stamm, ledger, historie=historie, scheiben=scheiben)
    assert any(erwartet in b for b in befunde), befunde


def test_vertragsjahr_muss_zum_datum_passen(tabellen):
    """vertragsjahr = 3 am zehnten Jahrestag ist keine andere Sicht, sondern
    eine Buchung, die etwas anderes behauptet als ihr Datum."""
    ledger = tabellen["ledger"].copy()
    sto = ledger.index[(ledger["ereignis"] == "STO") & (ledger["vertragsjahr"] > 3)][0]
    ledger.loc[sto, "vertragsjahr"] = 3
    befunde = validate_ledger(tabellen["bestand_gesamt"], ledger, historie=tabellen["historie"])
    assert any("vollendeten Vertragsjahre" in b for b in befunde), befunde


def test_zustandsaendernder_gevo_braucht_seine_journalzeile(tabellen):
    stamm, historie, ledger = tabellen["bestand_gesamt"], tabellen["historie"], tabellen["ledger"]
    sto = ledger[ledger["ereignis"] == "STO"].iloc[0]
    ohne = historie[~((historie["police_id"] == sto["police_id"])
                      & (historie["status_date"] == sto["status_date"]))]
    befunde = validate_ledger(stamm, ledger, historie=ohne.reset_index(drop=True))
    assert any("ohne passende Journalzeile" in b for b in befunde), befunde


def test_uebernommener_vertrag_darf_seine_vorgeschichte_tragen():
    """Die Gegenrichtung ist bewusst NICHT verlangt: Ein beitragsfrei
    uebernommener Vertrag traegt die Beitragsfreistellung der Quelle in
    der Historie (2022) und die Umbuchung zum Zugangsstichtag im Ledger
    (2026) — so bucht gates.bestand_uebernehmen."""
    from rechner_pipeline.models.bestand import LEDGER_SPALTEN, STAMM_SPALTEN, STATUS_HISTORIE_SPALTEN

    stamm = pd.DataFrame([{
        "police_id": 7, "tarif_generation": "klv/x", "produkt": "klv",
        "status_id": 2, "status_code": "PEX", "status_date": pd.Timestamp("2022-01-01"),
        "sex": "M", "date_of_birth": pd.Timestamp("1980-01-01"), "entry_age": 35,
        "duration": 30, "premium_duration": 30, "sum_insured": 100000.0, "bu_rente": 0.0,
        "zahlweise": 12, "insurance_start": pd.Timestamp("2015-01-01"),
        "insurance_end": pd.Timestamp("2045-01-01"), "payment_end": pd.Timestamp("2045-01-01"),
        "bestandszugang": pd.Timestamp("2026-01-01"),
    }])[[n for n, _ in STAMM_SPALTEN]].astype(dict(STAMM_SPALTEN))
    historie = pd.DataFrame([{
        "police_id": 7, "status_id": 2, "status_code": "PEX",
        "status_date": pd.Timestamp("2022-01-01"),
    }])[[n for n, _ in STATUS_HISTORIE_SPALTEN]].astype(dict(STATUS_HISTORIE_SPALTEN))
    ledger = pd.DataFrame([
        {"police_id": 7, "tarif_generation": "klv/x", "ereignis": ev, "vertragsjahr": 11,
         "status_date": pd.Timestamp("2026-01-01"), "betrag_art": "VS", "betrag": betrag,
         "betrag_herkunft": herkunft}
        for ev, betrag, herkunft in (("ZUG", 100000.0, "geliefert"), ("PEX", 61000.0, "gerechnet"))
    ])[[n for n, _ in LEDGER_SPALTEN]].astype(dict(LEDGER_SPALTEN))

    assert validate_ledger(stamm, ledger, historie=historie) == []


def test_ereignis_vokabular_ist_eines():
    from rechner_pipeline.bestand.kennzahlen import EREIGNIS_REIHENFOLGE

    assert set(EREIGNIS_REIHENFOLGE) == set(EREIGNIS_VALUES)


def test_gate_wird_bei_manipuliertem_ledger_rot(tabellen, lauf, tmp_path):
    ledger = tabellen["ledger"].copy()
    sto = ledger.index[ledger["ereignis"] == "STO"][0]
    ledger.loc[sto, "betrag"] = float("inf")
    lauf_dir = _lauf_kopie(lauf, tmp_path, ledger=ledger)

    ergebnis = _gate(lauf_dir, tmp_path)
    assert ergebnis.exit_code == 20
    assert any(e["code"] == "ledger" and "inf" in e["message"] for e in ergebnis.errors)


# --------------------------------------------------------------------------- #
# T18-04: Endlichkeit dort, wo Zahlen eintreten — Config und Abschluss
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("zeile", ["gamma2 = nan", "zins = inf", "alpha = -inf"])
def test_config_mit_nichtendlicher_rechnungsgrundlage_ist_ungueltig(tmp_path, zeile):
    """TOML laesst nan/inf zu; config.validate() liess sie durch, und der
    Abschluss publizierte 394 nichtendliche Zahlfelder."""
    text = CONFIG.read_text(encoding="utf-8")
    feld = zeile.split(" = ")[0]
    erste = text.index(f"\n{feld} = ")
    ende = text.index("\n", erste + 1)
    text = text[:erste + 1] + zeile + text[ende:]
    pfad = tmp_path / "c.toml"
    pfad.write_text(text, encoding="utf-8")

    fehler = load_config(pfad).validate()
    assert any("nicht endlich" in f for f in fehler), fehler


def test_annahme_mit_nan_ist_ungueltig():
    from rechner_pipeline.bestand.config import Annahme

    assert any("nicht endlich" in f for f in Annahme(a=float("nan"), b=1.0).validate("storno"))


def test_nichtendlicher_abschluss_wird_nicht_festgeschrieben(tabellen, tmp_path, monkeypatch):
    """Am Ausgang: Was der Kern nicht endlich rechnet, darf nicht
    unumkehrbar auf die Platte."""
    from rechner_pipeline.bestand import abschluss as modul

    config = load_config(CONFIG)
    echt = modul.einzelwerte_am

    def _mit_inf(*args, **kwargs):
        zeilen = echt(*args, **kwargs)
        zeilen[0]["deckungskapital"] = float("inf")
        return zeilen

    monkeypatch.setattr(modul, "einzelwerte_am", _mit_inf)
    with pytest.raises(AbschlussError, match="nichtendliche Werte"):
        schreibe_abschluss(tabellen["bestand_gesamt"], tabellen["historie"], config,
                           STICHTAG, tmp_path / "ab", scheiben=tabellen["scheiben"])
    assert not (tmp_path / "ab").exists() or not list((tmp_path / "ab").iterdir())


def test_validate_abschluss_prueft_den_stand_als_ganzes():
    df = pd.DataFrame([{
        "police_id": 1, "stichtag": pd.Timestamp("2016-01-01"), "produkt": "klv",
        "tarif_generation": "klv/x", "status_code": "POL", "leistung": 1.0,
        "deckungskapital": 1.0, "rueckkaufswert": 1.0, "vs_bfr": 1.0,
        "jahresbeitrag": 1.0, "kern_version": "3.4.0",
    }])[list(ABSCHLUSS_NAMES)]
    assert validate_abschluss(df) == []
    kaputt = pd.concat([df, df], ignore_index=True)
    kaputt.loc[1, "rueckkaufswert"] = np.nan
    kaputt.loc[1, "status_code"] = "STO"
    befunde = validate_abschluss(kaputt)
    assert any("nicht eindeutig" in b for b in befunde)
    assert any("nichtendliche" in b for b in befunde)
    assert any("status_code" in b for b in befunde)


# --------------------------------------------------------------------------- #
# T18-05: Der Bericht prueft die Fuehrung, nicht die Form der Historie
# --------------------------------------------------------------------------- #

def test_teilhistorie_blockiert_den_bericht(tabellen, tmp_path, capsys):
    """Der Nachweis des Reviews: eine nichtleere Ein-Zeilen-Historie mit
    1.075 Stamm/Journal-Widerspruechen passierte den Wachposten
    (None-oder-leer) mit Exit 0 und einem 977-KB-Bericht."""
    stamm, historie, ledger = tabellen["bestand_gesamt"], tabellen["historie"], tabellen["ledger"]
    p = write_portfolio(stamm, tmp_path / "b.parquet")
    h = write_portfolio(historie.iloc[:1], tmp_path / "h.parquet")
    l = write_portfolio(ledger, tmp_path / "l.parquet")
    s = write_portfolio(tabellen["scheiben"], tmp_path / "s.parquet")
    out = tmp_path / "bericht.html"

    assert cli_report.main([
        "--portfolio", str(p), "--historie", str(h), "--ledger", str(l),
        "--scheiben", str(s), "--bis", HORIZONT.isoformat(), "--out", str(out),
    ]) == 2
    assert not out.exists()
    assert "Folgezustand braucht seine Buchung" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# T18-07: Der Writer folgt der umask zum SCHREIBzeitpunkt
# --------------------------------------------------------------------------- #

@pytest.mark.skipif(os.name == "nt", reason="POSIX-Dateirechte")
def test_writer_folgt_der_aktuellen_umask(tabellen, tmp_path):
    """Nach dem Import auf umask 077 verschaerft: Der Writer schrieb
    weiter 0644, weil er die umask beim Import gelesen hatte."""
    alt = os.umask(0o077)
    try:
        pfad = write_portfolio(tabellen["historie"], tmp_path / "h.parquet")
        manifest = schreibe_manifest(tmp_path, horizont=HORIZONT, neuzugang_ab=None,
                                     config_pfad=CONFIG, ausgaben=[pfad])
        assert stat.S_IMODE(pfad.stat().st_mode) == 0o600
        assert stat.S_IMODE(manifest.stat().st_mode) == 0o600
        os.umask(0o022)
        pfad = write_portfolio(tabellen["historie"], tmp_path / "h.parquet")
        assert stat.S_IMODE(pfad.stat().st_mode) == 0o644
    finally:
        os.umask(alt)
    assert manifest.name == MANIFEST_DATEI
