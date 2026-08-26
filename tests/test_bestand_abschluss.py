"""Abschluss: festgeschriebene Bewertungsstaende (ADR-011).

Knoten: klv, bu
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from rechner_pipeline.bestand import cli_abschluss
from rechner_pipeline.bestand.abschluss import (
    AbschlussError,
    abschluss_pfad,
    pruefe_abschluss,
    schreibe_abschluss,
    vorhandene_abschluesse,
)
from rechner_pipeline.bestand.auswertung import auswertungs_verlauf
from rechner_pipeline.bestand.config import load_config
from rechner_pipeline.bestand.ereignisse import fortschreiben, mit_zugaengen
from rechner_pipeline.bestand.fuehrung import fuehre_fort
from rechner_pipeline.bestand.generator import generate
from rechner_pipeline.bestand.parquet_io import read_portfolio
from rechner_pipeline.kern import __version__ as KERN_VERSION
from rechner_pipeline.models.bestand import ABSCHLUSS_NAMES

REPO_ROOT = Path(__file__).resolve().parents[1]
STICHTAG = dt.date(2016, 1, 1)


@pytest.fixture(scope="module")
def config():
    return load_config(REPO_ROOT / "configs" / "bestand_klv.toml")


@pytest.fixture(scope="module")
def lauf(config):
    basis = generate(config)
    ergebnis = fortschreiben(basis, config, dt.date(2020, 1, 1))
    stamm = fuehre_fort(
        mit_zugaengen(basis, ergebnis.zugaenge), ergebnis.historie
    )
    return stamm, ergebnis.historie, ergebnis.scheiben


def test_abschluss_friert_die_eine_bewertungsstrecke_ein(lauf, config, tmp_path):
    stamm, historie, scheiben = lauf
    pfad = schreibe_abschluss(
        stamm, historie, config, STICHTAG, tmp_path, scheiben=scheiben
    )

    fest = read_portfolio(pfad)
    assert list(fest.columns) == list(ABSCHLUSS_NAMES)
    assert (fest["kern_version"] == KERN_VERSION).all()
    assert fest["police_id"].is_unique

    # Der Abschluss ist die einzelvertragliche Form derselben Rechnung,
    # die auch die Aggregation traegt: die Summen muessen exakt decken.
    agg = auswertungs_verlauf(
        stamm, historie, config, [STICHTAG], scheiben=scheiben
    )[0]
    assert len(fest) == agg["vertraege"]
    assert float(fest["deckungskapital"].sum()) == pytest.approx(
        agg["deckungskapital"], rel=1e-12
    )
    assert float(fest["jahresbeitrag"].sum()) == pytest.approx(
        agg["bjb"], rel=1e-12
    )


def test_abschluss_wird_nie_ueberschrieben(lauf, config, tmp_path):
    stamm, historie, scheiben = lauf
    pfad = schreibe_abschluss(
        stamm, historie, config, STICHTAG, tmp_path, scheiben=scheiben
    )
    davor = pfad.read_bytes()

    with pytest.raises(AbschlussError, match="nie ueberschrieben"):
        schreibe_abschluss(
            stamm, historie, config, STICHTAG, tmp_path, scheiben=scheiben
        )

    assert pfad.read_bytes() == davor


def test_abschluss_ist_byte_deterministisch(lauf, config, tmp_path):
    stamm, historie, scheiben = lauf
    a = schreibe_abschluss(
        stamm, historie, config, STICHTAG, tmp_path / "a", scheiben=scheiben
    )
    b = schreibe_abschluss(
        stamm, historie, config, STICHTAG, tmp_path / "b", scheiben=scheiben
    )
    assert a.read_bytes() == b.read_bytes()


def test_pruefung_deckt_unveraenderten_stand(lauf, config, tmp_path):
    stamm, historie, scheiben = lauf
    pfad = schreibe_abschluss(
        stamm, historie, config, STICHTAG, tmp_path, scheiben=scheiben
    )
    assert pruefe_abschluss(pfad, stamm, historie, config, scheiben=scheiben) == []


def test_pruefung_weist_wertabweichung_aus_und_laesst_den_abschluss_stehen(
    lauf, config, tmp_path
):
    """Der Kernfall des Bausteins: Aendert sich die Rechnung nach der
    Festschreibung (hier simuliert durch einen manipulierten Bestand),
    wird die Abweichung je Police und Groesse AUSGEWIESEN — der
    festgeschriebene Stand bewegt sich nicht."""
    stamm, historie, scheiben = lauf
    pfad = schreibe_abschluss(
        stamm, historie, config, STICHTAG, tmp_path, scheiben=scheiben
    )
    davor = pfad.read_bytes()

    anders = stamm.copy()
    ziel = anders.index[anders["status_id"] == 1][0]
    pid = int(anders.loc[ziel, "police_id"])
    anders.loc[ziel, "sum_insured"] = float(anders.loc[ziel, "sum_insured"]) * 2

    befunde = pruefe_abschluss(pfad, anders, historie, config, scheiben=scheiben)

    assert any(f"police {pid}" in b and "deckungskapital" in b for b in befunde)
    assert pfad.read_bytes() == davor


def test_pruefung_benennt_geaenderten_kernstand(lauf, config, tmp_path, monkeypatch):
    stamm, historie, scheiben = lauf
    pfad = schreibe_abschluss(
        stamm, historie, config, STICHTAG, tmp_path, scheiben=scheiben
    )
    import rechner_pipeline.bestand.abschluss as modul

    monkeypatch.setattr(modul, "KERN_VERSION", "99.0.0")
    befunde = pruefe_abschluss(pfad, stamm, historie, config, scheiben=scheiben)

    assert any("Kern" in b and "99.0.0" in b for b in befunde)
    assert any("bleibt stehen" in b for b in befunde)


def test_leerer_stichtag_ist_kein_abschluss(lauf, config, tmp_path):
    stamm, historie, scheiben = lauf
    with pytest.raises(AbschlussError, match="kein in-force-Bestand"):
        schreibe_abschluss(
            stamm, historie, config, dt.date(1980, 1, 1), tmp_path,
            scheiben=scheiben,
        )


def test_vorhandene_abschluesse_listet_sortiert(lauf, config, tmp_path):
    stamm, historie, scheiben = lauf
    schreibe_abschluss(
        stamm, historie, config, dt.date(2017, 1, 1), tmp_path, scheiben=scheiben
    )
    schreibe_abschluss(
        stamm, historie, config, STICHTAG, tmp_path, scheiben=scheiben
    )

    gefunden = vorhandene_abschluesse(tmp_path)

    assert list(gefunden) == [STICHTAG, dt.date(2017, 1, 1)]
    assert gefunden[STICHTAG] == abschluss_pfad(tmp_path, STICHTAG)


def test_cli_schreibt_und_prueft(lauf, config, tmp_path, capsys):
    from rechner_pipeline.bestand.parquet_io import write_portfolio

    stamm, historie, scheiben = lauf
    lauf_dir = tmp_path / "lauf"
    lauf_dir.mkdir()
    write_portfolio(stamm, lauf_dir / "bestand_gesamt.parquet")
    write_portfolio(historie, lauf_dir / "historie.parquet")
    write_portfolio(scheiben, lauf_dir / "scheiben.parquet")
    argv = [
        "--config", str(REPO_ROOT / "configs" / "bestand_klv.toml"),
        "--lauf", str(lauf_dir),
        "--stichtag", STICHTAG.isoformat(),
    ]

    assert cli_abschluss.main(argv) == 0
    assert (lauf_dir / "abschluesse" / f"abschluss_{STICHTAG}.parquet").is_file()
    # Doppel-Festschreibung: harter Fehler.
    assert cli_abschluss.main(argv) == 2
    # Pruefung deckt.
    assert cli_abschluss.main(argv + ["--pruefen"]) == 0
    meldungen = capsys.readouterr().err
    assert "nie ueberschrieben" in meldungen
    assert "deckt den Abschluss" in meldungen
