"""Regressionen zur externen Reviewrunde T14 (PR #10).

Jeder Test haelt genau einen bestaetigten Befund fest. Die Faelle sind so
gebaut, dass sie VOR der Korrektur durchgelaufen waeren — ein Test, der
auch ohne Korrektur gruen ist, sichert nichts.

Knoten: system/bestand
"""

from __future__ import annotations

import datetime as _dt
import threading
from pathlib import Path

import pandas as pd
import pytest

from rechner_pipeline.bestand.abschluss import (
    abschluss_pfad,
    pruefe_abschluss,
    schreibe_abschluss,
)
from rechner_pipeline.bestand.auswertung import einzelwerte_am
from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
from rechner_pipeline.models.bestand import validate_scheiben

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = REPO_ROOT / "configs" / "bestand_klv.toml"
STICHTAG = _dt.date(2016, 1, 1)


@pytest.fixture(scope="module")
def _config():
    from rechner_pipeline.bestand.config import load_config

    return load_config(CONFIG)


@pytest.fixture(scope="module")
def lauf_klv_ursprung(_config):
    """Der erzeugte Basisbestand: lauter Ursprungszustaende, kein Journal."""
    from rechner_pipeline.bestand.generator import generate

    return generate(_config), _config


@pytest.fixture(scope="module")
def lauf_klv(lauf_klv_ursprung):
    """Ein gefuehrter Bestand mit Journal und Scheiben (stamm, historie, scheiben, config)."""
    from rechner_pipeline.bestand.ereignisse import fortschreiben, mit_zugaengen
    from rechner_pipeline.bestand.fuehrung import fuehre_fort

    basis, config = lauf_klv_ursprung
    historie, _ledger, scheiben, zugaenge = fortschreiben(
        basis, config, _dt.date(2035, 1, 1)
    )[:4]
    gesamt = mit_zugaengen(basis, zugaenge)
    return fuehre_fort(gesamt, historie), historie, scheiben, config


@pytest.fixture(scope="module")
def lauf_verzeichnis(tmp_path_factory, lauf_klv_ursprung):
    """Ein vollstaendiges Laufverzeichnis wie cli_fortschreibung es schreibt."""
    from rechner_pipeline.bestand.ereignisse import fortschreiben, mit_zugaengen
    from rechner_pipeline.bestand.fuehrung import fuehre_fort

    basis, config = lauf_klv_ursprung
    historie, ledger, scheiben, zugaenge = fortschreiben(
        basis, config, _dt.date(2035, 1, 1)
    )[:4]
    ziel = tmp_path_factory.mktemp("lauf")
    write_portfolio(fuehre_fort(mit_zugaengen(basis, zugaenge), historie),
                    ziel / "bestand_gesamt.parquet")
    write_portfolio(historie, ziel / "historie.parquet")
    write_portfolio(ledger, ziel / "ledger.parquet")
    write_portfolio(scheiben, ziel / "scheiben.parquet")
    # Der Lieferschein des Laufs (T18-02) — ohne ihn nimmt der Abschluss
    # das Bundle nicht an.
    from rechner_pipeline.bestand.manifest import schreibe_manifest

    schreibe_manifest(
        ziel, horizont=_dt.date(2035, 1, 1), neuzugang_ab=None,
        config_pfad=CONFIG, ausgaben=sorted(ziel.glob("*.parquet")),
    )
    return ziel


# --------------------------------------------------------------------------- #
# T14-05: gamma1 ist eine Rechnungsgrundlage und wird geprueft
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "wert, erwartet",
    [
        (float("nan"), "fehlende Werte (NaN) in gamma1"),
        (float("inf"), "gamma1 != 0"),
        (-5.0, "gamma1 != 0"),
        (0.0008, "gamma1 != 0"),
    ],
)
def test_b1_lehnt_fremdes_gamma1_der_scheibe_ab(
    lauf_klv, wert: float, erwartet: str
) -> None:
    """Ein Fremdwert rechnet still falsch, nicht laut.

    NaN laesst den Rueckkaufswert auf 0,00 fallen statt auf NaN, ein
    negatives gamma1 erzeugt einen negativen Jahresbeitrag. Beides sind
    plausibel aussehende Zahlen — deshalb muss das Gate sie fangen und
    nicht der Leser.
    """
    stamm, _, scheiben, _ = lauf_klv
    assert validate_scheiben(stamm, scheiben) == [], "regulaer erzeugt: gruen"

    manipuliert = scheiben.copy()
    manipuliert.loc[manipuliert.index[0], "gamma1"] = wert
    fehler = [e for e in validate_scheiben(stamm, manipuliert) if "gamma1" in e]
    assert fehler, f"gamma1={wert} wurde durchgelassen"
    assert erwartet in fehler[0]


def test_regulaer_erzeugte_scheiben_tragen_gamma1_null(lauf_klv) -> None:
    """Die Tarifwerk-Regel, gegen die geprueft wird (erhoehungs_scheibe)."""
    _, _, scheiben, _ = lauf_klv
    assert set(scheiben["gamma1"]) == {0.0}


# --------------------------------------------------------------------------- #
# T14-01: Bewertung ohne Journal verwirft den gefuehrten Zustand
# --------------------------------------------------------------------------- #


def test_bewertung_verlangt_das_journal_zum_gefuehrten_stamm(lauf_klv) -> None:
    """Ohne Journal kaemen terminierte Vertraege als beitragspflichtig zurueck.

    journalsicht synthetisiert den Ursprung unbedingt als POL am
    Versicherungsbeginn; bei leerem Journal bleibt nur diese Zeile. Der
    Bericht wies so 51 Prozent zu viele Vertraege und 70 Prozent zu viel
    Deckungskapital aus — bei Exit 0 und ohne Warnung.
    """
    stamm, historie, scheiben, config = lauf_klv
    assert (stamm["status_id"] > 1).any(), "Vorbedingung: gefuehrter Stamm"

    with pytest.raises(ValueError, match="Folgezustand"):
        einzelwerte_am(stamm, None, config, STICHTAG)

    # Mit Journal laeuft dieselbe Bewertung.
    zeilen = einzelwerte_am(stamm, historie, config, STICHTAG, scheiben=scheiben)
    assert zeilen


def test_ursprungsbestand_ohne_journal_bleibt_erlaubt(lauf_klv_ursprung) -> None:
    """Der Wachposten trifft NUR den gefuehrten Fall.

    Ein Bestand aus lauter Ursprungszustaenden hat kein Journal noetig —
    ihn abzulehnen waere eine Verschaerfung ohne Anlass.
    """
    stamm, config = lauf_klv_ursprung
    assert set(stamm["status_id"]) == {1}
    assert einzelwerte_am(stamm, None, config, STICHTAG)


# --------------------------------------------------------------------------- #
# T14-02: Der Abschluss traegt dieselben Vorbedingungen wie der Bericht
# --------------------------------------------------------------------------- #


def test_abschluss_ohne_scheiben_bei_erh_im_ledger_blockiert(
    tmp_path: Path, lauf_verzeichnis: Path
) -> None:
    """Ein festgeschriebener Stand ohne Scheiben ist unumkehrbar falsch.

    Gemessen lag das Deckungskapital 3.795.035,38 zu niedrig (-10,68 %),
    bei Exit 0 — und die eigene Kontrolle meldete "Neuberechnung deckt den
    Abschluss".
    """
    from rechner_pipeline.bestand import cli_abschluss

    unvollstaendig = tmp_path / "ohne_scheiben"
    unvollstaendig.mkdir()
    for name in ("bestand_gesamt.parquet", "historie.parquet", "ledger.parquet"):
        (unvollstaendig / name).write_bytes((lauf_verzeichnis / name).read_bytes())
    ledger = read_portfolio(unvollstaendig / "ledger.parquet")
    assert (ledger["ereignis"] == "ERH").any(), "Vorbedingung: ERH im Ledger"

    exit_code = cli_abschluss.main([
        "--config", "configs/bestand_klv.toml",
        "--lauf", str(unvollstaendig),
        "--stichtag", STICHTAG.isoformat(),
        "--bis", "2035-01-01",   # Horizont des Fixture-Laufs
        "--out-dir", str(tmp_path / "ziel"),
    ])
    assert exit_code == 2
    assert not (tmp_path / "ziel").exists() or not list((tmp_path / "ziel").iterdir())


# --------------------------------------------------------------------------- #
# T14-04: Der Dateiname ist eine Aussage und wird gebunden
# --------------------------------------------------------------------------- #


def test_abschluss_unter_falschem_dateinamen_ist_ein_befund(
    tmp_path: Path, lauf_klv, lauf_verzeichnis: Path
) -> None:
    """Vorher meldete --pruefen Exit 0 und "Neuberechnung deckt den Abschluss".

    Die Kontrolle rechnete gegen den INHALTS-Stichtag und war deshalb
    blind dafuer, dass die Datei etwas anderes behauptet.
    """
    stamm, historie, scheiben, config = lauf_klv
    ziel = tmp_path / "abschluesse"
    echt = schreibe_abschluss(stamm, historie, config, STICHTAG, ziel, scheiben=scheiben)
    assert pruefe_abschluss(echt, stamm, historie, config, scheiben=scheiben) == []

    falsch = ziel / abschluss_pfad(ziel, _dt.date(2099, 1, 1)).name
    falsch.write_bytes(echt.read_bytes())
    befunde = pruefe_abschluss(falsch, stamm, historie, config, scheiben=scheiben)
    assert befunde and "enthaelt aber den Stichtag" in befunde[0]


def test_abschluss_vergleicht_auch_produkt_und_generation(
    tmp_path: Path, lauf_klv
) -> None:
    """Beide werden aus dem Stamm neu abgeleitet — also auch verglichen."""
    stamm, historie, scheiben, config = lauf_klv
    ziel = tmp_path / "abschluesse"
    pfad = schreibe_abschluss(stamm, historie, config, STICHTAG, ziel, scheiben=scheiben)

    fest = read_portfolio(pfad)
    fest.loc[fest.index[0], "tarif_generation"] = "MANIPULIERT"
    write_portfolio(fest, pfad)
    befunde = pruefe_abschluss(pfad, stamm, historie, config, scheiben=scheiben)
    assert any("tarif_generation" in b for b in befunde)

    # Und produkt ebenso: der Testname behauptete beide, mutierte aber nur
    # die Generation — der Produktvergleich liess sich entfernen, ohne dass
    # ein Test rot wurde.
    fest = read_portfolio(pfad)
    fest.loc[fest.index[0], "produkt"] = "bu"
    write_portfolio(fest, pfad)
    befunde = pruefe_abschluss(pfad, stamm, historie, config, scheiben=scheiben)
    assert any("produkt" in b for b in befunde)


# --------------------------------------------------------------------------- #
# T14-03: Geschrieben wird atomar
# --------------------------------------------------------------------------- #


def test_gleichzeitiges_schreiben_hinterlaesst_keine_kaputte_datei(
    tmp_path: Path, lauf_klv
) -> None:
    """Zwei Schreiber verschraenkten ihre Parquet-Fuesse (b'AR11' statt b'PAR1').

    Der Stumpf war eine Sackgasse: pfad.exists() liefert auch dafuer True,
    also verweigerte schreibe_abschluss jede Reparatur, waehrend die
    Kontrolle an der Parquet-Fehlermeldung scheiterte.
    """
    stamm, _, _, _ = lauf_klv
    ziel = tmp_path / "z.parquet"
    zweit = stamm.copy()
    zweit.loc[zweit.index[0], "sum_insured"] = 999_999.0

    for _ in range(4):
        ziel.unlink(missing_ok=True)
        barriere = threading.Barrier(2)
        fehler: list = []

        def schreib(df: pd.DataFrame) -> None:
            barriere.wait()
            try:
                write_portfolio(df, ziel)
            except Exception as exc:  # noqa: BLE001 — Testbeobachtung
                fehler.append(exc)

        faeden = [threading.Thread(target=schreib, args=(d,)) for d in (stamm, zweit)]
        for f in faeden:
            f.start()
        for f in faeden:
            f.join()
        assert not fehler, f"Schreiber gescheitert: {fehler}"
        # Lesbar und vollstaendig — egal welcher der beiden gewonnen hat.
        assert len(read_portfolio(ziel)) == len(stamm)

    rest = [p.name for p in tmp_path.iterdir() if p.name != "z.parquet"]
    assert rest == [], f"temporaere Dateien geblieben: {rest}"
