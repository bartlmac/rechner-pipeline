"""Regressionen zur externen Reviewrunde T16 (PR #10).

Jeder Test haelt genau einen bestaetigten Befund fest. Die Faelle sind so
gebaut, dass sie VOR der Korrektur durchgelaufen waeren -- ein Test, der
auch ohne Korrektur gruen ist, sichert nichts.

Die Befunde T16-01 und T16-02 stehen nicht hier, sondern in
``test_bestand_abschluss.py``: sie gehoeren an die produktive Verdrahtung
der CLI, nicht in eine eigene Reviewdatei.

Knoten: system/bestand
"""

from __future__ import annotations

import datetime as _dt
import math
import os
import stat
import threading
from pathlib import Path

import pandas as pd
import pytest

from rechner_pipeline.bestand import abschluss as abschluss_modul
from rechner_pipeline.bestand.abschluss import (
    AbschlussError,
    abschluss_pfad,
    pruefe_abschluss,
    schreibe_abschluss,
)
from rechner_pipeline.bestand.config import load_config
from rechner_pipeline.bestand.ereignisse import fortschreiben, mit_zugaengen
from rechner_pipeline.bestand.fuehrung import fuehre_fort
from rechner_pipeline.bestand.generator import generate
from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
from rechner_pipeline.models.bestand import validate_portfolio

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = REPO_ROOT / "configs" / "bestand_klv.toml"
STICHTAG = _dt.date(2016, 1, 1)
HORIZONT = _dt.date(2020, 1, 1)


@pytest.fixture(scope="module")
def _config():
    return load_config(CONFIG)


@pytest.fixture(scope="module")
def lauf_klv(_config):
    basis = generate(_config)
    ergebnis = fortschreiben(basis, _config, HORIZONT)
    stamm = fuehre_fort(mit_zugaengen(basis, ergebnis.zugaenge), ergebnis.historie)
    return stamm, ergebnis.historie, ergebnis.scheiben, _config


# --------------------------------------------------------------------------- #
# T16-03: Bilanzwerte sind endlich
# --------------------------------------------------------------------------- #


def test_unendlicher_stammwert_wird_abgelehnt(lauf_klv) -> None:
    """+inf ist kein fehlender Wert und faellt durch jede Bandpruefung.

    Vorher: validate_portfolio meldete [], der Abschluss schrieb leistung,
    deckungskapital und jahresbeitrag als inf fest.
    """
    stamm, _historie, _scheiben, _config = lauf_klv
    kaputt = stamm.copy()
    kaputt.loc[kaputt.index[0], "sum_insured"] = float("inf")

    befunde = validate_portfolio(kaputt)
    assert any("nichtendlich" in b for b in befunde), befunde
    # Der Ursprungsbestand selbst bleibt sauber -- die Pruefung ist nicht
    # einfach immer rot.
    assert not any("nichtendlich" in b for b in validate_portfolio(stamm))


def test_kontrolle_deckt_keinen_unendlichen_abschluss(tmp_path, lauf_klv) -> None:
    """math.isclose(inf, inf) ist wahr: der Stand haette sich selbst gedeckt."""
    stamm, historie, scheiben, config = lauf_klv
    ziel = tmp_path / "abschluesse"
    pfad = schreibe_abschluss(stamm, historie, config, STICHTAG, ziel,
                              scheiben=scheiben)

    fest = read_portfolio(pfad)
    fest.loc[fest.index[0], "deckungskapital"] = float("inf")
    pfad.unlink()
    write_portfolio(fest, pfad)

    # Vorbedingung des Tests: ohne Endlichkeitspruefung waeren die Werte
    # per isclose deckungsgleich gewesen.
    assert math.isclose(float("inf"), float("inf"), rel_tol=0.0, abs_tol=0.0)

    befunde = pruefe_abschluss(pfad, stamm, historie, config, scheiben=scheiben)
    assert any("nichtendlich" in b for b in befunde), befunde


# --------------------------------------------------------------------------- #
# T16-04: Festgeschrieben heisst genau einmal
# --------------------------------------------------------------------------- #


def test_genau_ein_schreiber_gewinnt(tmp_path, lauf_klv) -> None:
    """Zwei parallele Aufrufe, die BEIDE durch exists() gekommen sind.

    Vorher meldeten beide Erfolg und os.replace ersetzte den zuerst
    veroeffentlichten Stand -- der Genau-einmal-Vertrag aus ADR-011 war
    unter Konkurrenz nicht erfuellt.
    """
    stamm, historie, scheiben, config = lauf_klv
    ziel = tmp_path / "abschluesse"
    barriere = threading.Barrier(2, timeout=60)
    echt = abschluss_modul._rechne

    def _synchronisiert(*args, **kwargs):
        df = echt(*args, **kwargs)
        barriere.wait()          # beide sind an exists() vorbei
        return df

    abschluss_modul._rechne = _synchronisiert
    try:
        ergebnis: list = []
        def _lauf():
            try:
                schreibe_abschluss(stamm, historie, config, STICHTAG, ziel,
                                   scheiben=scheiben)
                ergebnis.append("ok")
            except AbschlussError:
                ergebnis.append("abgewiesen")

        faeden = [threading.Thread(target=_lauf) for _ in range(2)]
        for f in faeden:
            f.start()
        for f in faeden:
            f.join(timeout=90)
    finally:
        abschluss_modul._rechne = echt

    assert ergebnis.count("ok") == 1, ergebnis
    assert ergebnis.count("abgewiesen") == 1, ergebnis
    assert len(list(ziel.glob("abschluss_*.parquet"))) == 1


def test_exklusiver_publish_ueberschreibt_nicht(tmp_path) -> None:
    """write_portfolio(exklusiv=True) legt an oder scheitert -- nie beides."""
    tabelle = pd.DataFrame({
        "police_id": pd.Series([1], dtype="int64"),
        "tarif_generation": pd.Series(["klv-2015"], dtype="object"),
        "ereignis": pd.Series(["ERH"], dtype="object"),
        "vertragsjahr": pd.Series([1], dtype="int64"),
        "status_date": pd.Series([pd.Timestamp("2016-01-01")], dtype="datetime64[ns]"),
        "betrag_art": pd.Series(["VS_erhoehung"], dtype="object"),
        "betrag": pd.Series([1.0], dtype="float64"),
    })
    pfad = tmp_path / "einmal.parquet"
    write_portfolio(tabelle, pfad, exklusiv=True)
    with pytest.raises(FileExistsError):
        write_portfolio(tabelle, pfad, exklusiv=True)
    # Ohne exklusiv bleibt der bisherige Weg erhalten: die sechs Ausgaben
    # eines Laufs sind bewusst ueberschreibbar.
    write_portfolio(tabelle, pfad)
    # Keine Temp-Reste.
    assert [p.name for p in tmp_path.iterdir()] == ["einmal.parquet"]


# --------------------------------------------------------------------------- #
# T16-05: Der Bericht traegt den Wachposten an der CLI-Grenze
# --------------------------------------------------------------------------- #


def test_bericht_ohne_journal_blockiert(tmp_path, lauf_klv, capsys) -> None:
    """Ohne --historie wird einzelwerte_am nie gerufen, der Wachposten dort
    griff also nie.

    Gemessen zum Stichtag 2016: 464 statt 1.213 Vertraege und 37,5 statt
    95,1 Mio Versicherungssumme -- bei Exit 0 und ohne Vorbehalt.
    """
    from rechner_pipeline.bestand import cli_report

    stamm, _historie, _scheiben, _config = lauf_klv
    pfad = tmp_path / "bestand_gesamt.parquet"
    write_portfolio(stamm, pfad)
    assert (stamm["status_id"] > 1).any(), "Vorbedingung: gefuehrter Bestand"

    ziel = tmp_path / "bericht.html"
    exit_code = cli_report.main([
        "--portfolio", str(pfad), "--out", str(ziel),
        "--stichtag", STICHTAG.isoformat(),
    ])
    assert exit_code == 2
    assert not ziel.exists()
    # Seit T18-05 urteilt die P-B1-Engine, nicht mehr ein eigener
    # Wachposten der CLI — die Meldung ist ihre.
    assert "--historie ist erforderlich" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# T16-06a: Der atomare Writer aendert den Berechtigungsvertrag nicht
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(os.name == "nt", reason="POSIX-Dateirechte")
def test_lauf_ausgaben_folgen_der_umask(tmp_path, lauf_klv) -> None:
    """tempfile.mkstemp legt 0600 an, os.replace nimmt DIESEN Modus mit.

    Vorher endete jede der sechs Lauf-Ausgaben als 0600 -- gegenueber dem
    direkten Writer eine stille Rechteaenderung.
    """
    maske = os.umask(0)
    os.umask(maske)
    erwartet = 0o666 & ~maske

    stamm, _historie, _scheiben, _config = lauf_klv
    pfad = tmp_path / "bestand_gesamt.parquet"
    write_portfolio(stamm, pfad)

    modus = stat.S_IMODE(pfad.stat().st_mode)
    assert modus == erwartet, oct(modus)
