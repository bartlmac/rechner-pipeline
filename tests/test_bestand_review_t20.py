"""Regressionen zur externen Reviewrunde T20 (DORA ToDo 20, 2026-09-05).

Acht Befunde auf Stand 6e239dc. Die Runde bestaetigte, dass die konkret
demonstrierten Mutationen aus T18/T19 gefangen sind, und zeigte an drei
tieferen Gegenbeispielen, dass die KLASSE noch nicht geschlossen war:
Beleg und Urteil ueber verschiedene Bytes (T20-01), Betragsidentitaet
statt Jahressumme (T20-04), Endlichkeit bis in die Verteilungsparameter
(T20-05). Jeder Test hier stellt den Nachweis des Reviews nach und waere
vor der Korrektur gruen gewesen.

Knoten: system/bestand
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
from pathlib import Path

import pytest

from rechner_pipeline.bestand import cli_fortschreibung
from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
from rechner_pipeline.gates import abnahmebericht, bestand_validate

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = REPO_ROOT / "configs" / "bestand_klv.toml"
HORIZONT = _dt.date(2020, 1, 1)


def _sha(pfad: Path) -> str:
    return hashlib.sha256(pfad.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def lauf(tmp_path_factory) -> Path:
    ziel = tmp_path_factory.mktemp("lauf")
    assert cli_fortschreibung.main([
        "--config", str(CONFIG), "--bis", HORIZONT.isoformat(),
        "--out-dir", str(ziel),
    ]) == 0
    return ziel


def _kopie(lauf: Path, tmp_path: Path) -> Path:
    ziel = tmp_path / "lauf"
    ziel.mkdir()
    for p in lauf.iterdir():
        (ziel / p.name).write_bytes(p.read_bytes())
    return ziel


def _gate_argv(lauf_dir: Path, diag: Path) -> list:
    return [
        "--portfolio", str(lauf_dir / "bestand_gesamt.parquet"),
        "--historie", str(lauf_dir / "historie.parquet"),
        "--ledger", str(lauf_dir / "ledger.parquet"),
        "--scheiben", str(lauf_dir / "scheiben.parquet"),
        "--bis", HORIZONT.isoformat(),
        "--repo-root", str(REPO_ROOT),
        "--diagnostics-dir", str(diag),
    ]


# --------------------------------------------------------------------------- #
# T20-01: Beleg und Urteil ueber DIESELBEN Bytes
# --------------------------------------------------------------------------- #

def test_pb1_beleg_nennt_die_bytes_die_geprueft_wurden(lauf, tmp_path, monkeypatch):
    """Der Nachweis des Reviews: Auf der Platte liegt ein ungueltiger Ledger
    (STO mit betrag = inf). Zwischen dem Hashen des Gates und dem Lesen der
    Engine wird er atomar durch die gueltige Fassung ersetzt. Vorher: Exit 0,
    all_passed, und der Beleg trug den Hash der ungueltigen Bytes.

    Jetzt gibt es kein 'zwischen': Die Engine liest einmal, hasht und prueft
    dieselben Bytes, das Gate uebernimmt ihre Hashes. Der Tausch geschieht im
    Test VOR dem Engine-Aufruf — und der Beleg muss die Bytes nennen, die
    danach geprueft wurden.
    """
    lauf_dir = _kopie(lauf, tmp_path)
    ledger_pfad = lauf_dir / "ledger.parquet"
    gueltig = ledger_pfad.read_bytes()
    ledger = read_portfolio(ledger_pfad)
    ledger.loc[ledger.index[ledger["ereignis"] == "STO"][0], "betrag"] = float("inf")
    write_portfolio(ledger, ledger_pfad)
    ungueltig = ledger_pfad.read_bytes()
    assert ungueltig != gueltig

    echt = bestand_validate.lies_und_pruefe_pb1

    def _tausch_dann_pruefen(eingaben, **kwargs):
        # Der atomare Publish zwischen "Gate hat gehasht" und "Engine liest".
        ledger_pfad.write_bytes(gueltig)
        return echt(eingaben, **kwargs)

    monkeypatch.setattr(bestand_validate, "lies_und_pruefe_pb1", _tausch_dann_pruefen)
    ergebnis = bestand_validate.main(_gate_argv(lauf_dir, tmp_path / "diag"))

    assert ergebnis.exit_code == 0, "die Engine sah die gueltigen Bytes"
    ledger_schluessel = ergebnis.summary["eingangsrollen"]["ledger"]
    assert ergebnis.input_hashes[ledger_schluessel] == hashlib.sha256(gueltig).hexdigest(), (
        "der Beleg nennt andere Bytes, als die Engine geprueft hat")
    assert ergebnis.input_hashes[ledger_schluessel] != hashlib.sha256(ungueltig).hexdigest()
    # Und der Portfolio-Hash im Summary ist derselbe wie im Beleg.
    assert ergebnis.summary["portfolio_sha256"] == ergebnis.input_hashes[
        ergebnis.summary["eingangsrollen"]["portfolio"]]


def test_pb1_beleg_hashes_sind_die_der_engine(lauf, tmp_path):
    """Positivkontrolle ohne Tausch: Beleg-Hashes == Engine-Hashes == Platte."""
    ergebnis = bestand_validate.main(_gate_argv(lauf, tmp_path / "diag"))
    assert ergebnis.exit_code == 0
    for rolle, datei in (("portfolio", "bestand_gesamt.parquet"), ("historie", "historie.parquet"),
                         ("ledger", "ledger.parquet"), ("scheiben", "scheiben.parquet")):
        schluessel = ergebnis.summary["eingangsrollen"][rolle]
        assert ergebnis.input_hashes[schluessel] == _sha(lauf / datei)
    assert set(ergebnis.input_hashes) == set(ergebnis.summary["eingangsrollen"].values())


def _pb1_ledger(lauf_dir: Path, diag: Path) -> tuple:
    ergebnis = bestand_validate.main(_gate_argv(lauf_dir, diag))
    assert ergebnis.exit_code == 0
    ledger_pfad = diag / "bestand_validate.gate.json"
    eintrag = json.loads(ledger_pfad.read_text(encoding="utf-8"))
    suite = {
        "bestand_sha256": eintrag["summary"]["portfolio_sha256"],
        "anzahl": eintrag["summary"]["portfolio_zeilen"],
        "erwartete_anzahl": eintrag["summary"]["portfolio_zeilen"],
    }
    return ledger_pfad, eintrag, suite


def test_am4_neupruefung_vergleicht_die_gepruefen_bytes(lauf, tmp_path, monkeypatch):
    """Dieselbe Klasse in der A-M4-Neupruefung des P-B1-Belegs: Vorher wurde
    jede Datei zum Vergleich mit dem Beleg gehasht und DANACH fuer die
    Neupruefung erneut gelesen. Ein Tausch dazwischen (hier: ein anderes,
    fuer sich gueltiges Portfolio) blieb unbemerkt — Hash passte, Pruefung
    passte, nur nicht auf dieselben Bytes."""
    lauf_dir = _kopie(lauf, tmp_path)
    ledger_pfad, eintrag, suite = _pb1_ledger(lauf_dir, tmp_path / "diag")
    system = eintrag["summary"]["system"]

    # Positivkontrolle: unveraendert ist die Neupruefung befundfrei.
    assert abnahmebericht._b1_fehler(
        ledger_pfad=ledger_pfad, fall=lauf_dir, repo_root=REPO_ROOT,
        suite=suite, erwartetes_system=system) == []

    # Ein anderes, fuer sich gueltiges Portfolio: zwei Geschlechter getauscht.
    portfolio_pfad = lauf_dir / "bestand_gesamt.parquet"
    anderes = read_portfolio(portfolio_pfad)
    m, f = anderes.index[anderes["sex"] == "M"][0], anderes.index[anderes["sex"] == "F"][0]
    anderes.loc[m, "sex"], anderes.loc[f, "sex"] = "F", "M"
    original = portfolio_pfad.read_bytes()
    echt = abnahmebericht.lies_und_pruefe_pb1

    def _tausch_dann_pruefen(eingaben, **kwargs):
        write_portfolio(anderes, portfolio_pfad)
        return echt(eingaben, **kwargs)

    monkeypatch.setattr(abnahmebericht, "lies_und_pruefe_pb1", _tausch_dann_pruefen)
    fehler = abnahmebericht._b1_fehler(
        ledger_pfad=ledger_pfad, fall=lauf_dir, repo_root=REPO_ROOT,
        suite=suite, erwartetes_system=system)
    assert portfolio_pfad.read_bytes() != original, "Vorbedingung: der Tausch fand statt"
    assert any("anderen SHA-256" in x for x in fehler), fehler


# --------------------------------------------------------------------------- #
# T20-05: Endlichkeit bis in die Verteilungsparameter
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("alt, neu", [
    ("sdlog = 0.55", "sdlog = nan"),
    ("sdlog = 0.55", "sdlog = inf"),
])
def test_nichtendlicher_verteilungsparameter_stoppt_den_produzenten(tmp_path, alt, neu):
    """Der Nachweis des Reviews: sdlog = nan passierte config.validate()
    (nan <= 0 ist falsch), die Fortschreibung schrieb 600 Vertraege mit
    sum_insured = NaN samt Manifest und endete mit Exit 0."""
    from rechner_pipeline.bestand.config import load_config

    text = CONFIG.read_text(encoding="utf-8")
    assert text.count(alt) >= 1
    config = tmp_path / "c.toml"
    config.write_text(text.replace(alt, neu, 1), encoding="utf-8")

    fehler = load_config(config).validate()
    assert any("nicht endlich" in f for f in fehler), fehler

    out = tmp_path / "lauf"
    assert cli_fortschreibung.main([
        "--config", str(config), "--bis", HORIZONT.isoformat(), "--out-dir", str(out),
    ]) == 2
    assert not out.exists() or not list(out.iterdir()), "nichts darf publiziert sein"


# --------------------------------------------------------------------------- #
# T20-04: Der Betrag jeder Buchung folgt aus dem Kern fuer DIESE Police
# --------------------------------------------------------------------------- #

def _engine(lauf_dir: Path):
    from rechner_pipeline.bestand.vorbedingungen import lies_und_pruefe_pb1

    return lies_und_pruefe_pb1({
        "portfolio": lauf_dir / "bestand_gesamt.parquet",
        "historie": lauf_dir / "historie.parquet",
        "ledger": lauf_dir / "ledger.parquet",
        "scheiben": lauf_dir / "scheiben.parquet",
        "config": CONFIG,
    }, bis=HORIZONT)


def test_vertauschte_stornobetraege_fallen_auf(lauf, tmp_path):
    """Der Nachweis des Reviews: Die Betraege zweier STO-Ereignisse desselben
    Kalenderjahrs zwischen zwei Policen vertauscht — Code, Betragsart,
    Datum, Generation, Zeilenzahl und Jahressumme unveraendert. Vorher:
    validate_ledger 0, P-B1 0 Befunde, 26 Bewegungsjahre gruen."""
    _, geprueft, fehler, _ = _engine(lauf)
    assert fehler == [], "Positivkontrolle: der echte Lauf ist herleitbar"
    assert geprueft["betraege_hergeleitet"] > 1000

    lauf_dir = _kopie(lauf, tmp_path)
    ledger = read_portfolio(lauf_dir / "ledger.parquet")
    sto = ledger[ledger["ereignis"] == "STO"]
    jahr = next(j for j, g in sto.groupby(sto["status_date"].dt.year)
                if g["police_id"].nunique() >= 2 and g["betrag"].nunique() >= 2)
    a, b = sto.index[sto["status_date"].dt.year == jahr][:2]
    assert ledger.loc[a, "betrag"] != ledger.loc[b, "betrag"]
    ledger.loc[a, "betrag"], ledger.loc[b, "betrag"] = ledger.loc[b, "betrag"], ledger.loc[a, "betrag"]
    write_portfolio(ledger, lauf_dir / "ledger.parquet")

    _, _, fehler, _ = _engine(lauf_dir)
    assert any("nicht aus dem Kern fuer diese Police folgt" in f["message"]
               for f in fehler), fehler

    # Und im Gate: rot, mit Config.
    ergebnis = bestand_validate.main(
        _gate_argv(lauf_dir, tmp_path / "diag") + ["--config", str(CONFIG)])
    assert ergebnis.exit_code == 20
    assert any(e["code"] == "ledger" for e in ergebnis.errors)


@pytest.mark.parametrize("art", ["STO", "PEX", "TOD", "ABL"])
def test_jede_hergeleitete_buchungsart_ist_gebunden(lauf, tmp_path, art):
    """Nicht nur STO: Ein um einen Euro veraenderter Betrag jeder
    hergeleiteten Art faellt auf — die Herleitung ist policenweise."""
    lauf_dir = _kopie(lauf, tmp_path)
    ledger = read_portfolio(lauf_dir / "ledger.parquet")
    zeilen = ledger.index[ledger["ereignis"] == art]
    if len(zeilen) == 0:
        pytest.skip(f"der Fixture-Lauf bucht kein {art}")
    ledger.loc[zeilen[0], "betrag"] = float(ledger.loc[zeilen[0], "betrag"]) + 1.0
    write_portfolio(ledger, lauf_dir / "ledger.parquet")

    _, _, fehler, _ = _engine(lauf_dir)
    assert any(f"{art} Jahr" in f["message"] for f in fehler), fehler
