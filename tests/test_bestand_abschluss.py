"""Abschluss: festgeschriebene Bewertungsstaende (ADR-011).

Knoten: klv, bu
"""

from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path

import pandas as pd
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
from tests.nebentabellen import aus_fortschreibung, mit_neben
from tests.zugangsstrom import bestand_aus_zugangsstrom
from rechner_pipeline.bestand.manifest import schreibe_manifest
from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
from rechner_pipeline.kern import __version__ as KERN_VERSION
from rechner_pipeline.models.bestand import (
    ABSCHLUSS_NAMES,
    ABSCHLUSS_SPALTEN,
    ABSCHLUSS_ZAHLEN,
    SCHEIBEN_SPALTEN,
    STATUS_HISTORIE_SPALTEN,
    validate_abschluss,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = REPO_ROOT / "plv" / "configs" / "bestand_klv.toml"
STICHTAG = dt.date(2016, 1, 1)
#: Fortschreibungs-Horizont des Fixture-Laufs. Der Abschluss
#: braucht ihn, weil die Bewegungs-Identitaet nur fuer
#: vollstaendig simulierte Kalenderjahre gilt.
HORIZONT = dt.date(2020, 1, 1)


@pytest.fixture(scope="module")
def config():
    return load_config(CONFIG)


@pytest.fixture(scope="module")
def _fortschreibung(config):
    basis = bestand_aus_zugangsstrom(config)
    return basis, fortschreiben(basis, config, HORIZONT)


@pytest.fixture(scope="module")
def lauf(_fortschreibung):
    basis, ergebnis = _fortschreibung
    stamm = fuehre_fort(
        mit_zugaengen(basis, ergebnis.zugaenge), ergebnis.historie
    )
    # ``neben``: ALLE Nebentabellen des Laufs, wie der Produzent sie an den
    # Abschluss gibt (Befund aus dem Raten-Block 2026-10-01: nur die
    # Scheiben, und herabgesetzte wie teilgekuendigte Vertraege standen hier
    # ungekuerzt im Abschluss, ohne dass ein Test es sah).
    return mit_neben((stamm, ergebnis.historie, ergebnis.scheiben),
                     aus_fortschreibung(ergebnis))


@pytest.fixture(scope="module")
def bundle(tmp_path_factory, lauf, _fortschreibung):
    """Ein VOLLSTAENDIGES Lauf-Bundle auf Platte.

    So hinterlaesst cli_fortschreibung einen Lauf, und genau so verlangt
    ihn der Abschluss: Stamm, Historie, Ledger und Scheiben gehoeren
    zusammen. Die Negativtests unten kopieren dieses Verzeichnis und
    nehmen ihm gezielt ein Stueck weg.
    """
    stamm, historie, scheiben = lauf
    _basis, ergebnis = _fortschreibung
    ziel = tmp_path_factory.mktemp("lauf")
    write_portfolio(stamm, ziel / "bestand_gesamt.parquet")
    write_portfolio(historie, ziel / "historie.parquet")
    write_portfolio(scheiben, ziel / "scheiben.parquet")
    write_portfolio(ergebnis.ledger, ziel / "ledger.parquet")
    # Bedingte Ausgabe wie in cli_fortschreibung: nur wenn der Lauf
    # Herabsetzungen oder Teilkuendigungen gebucht hat — mit der Config der
    # PLV seit 2026-10-01 der Fall.
    if len(ergebnis.reduktionen):
        write_portfolio(ergebnis.reduktionen, ziel / "reduktionen.parquet")
    _manifest(ziel)
    return ziel


def _manifest(lauf_dir):
    """Der Lieferschein, wie cli_fortschreibung ihn schreibt (T18-02).

    Die Negativtests unten mutieren Tabellen und schreiben das Manifest
    danach NEU: Sie pruefen die semantischen Wachen (leere Scheiben,
    gamma1, ...), nicht die Manifest-Bindung — ein Angreifer, der auch
    das Manifest nachzieht, muss an der Semantik scheitern. Die
    Manifest-Bindung selbst prueft tests/test_bestand_manifest.py.
    """
    schreibe_manifest(
        lauf_dir, horizont=HORIZONT, neuzugang_ab=None, config_pfad=CONFIG,
        ausgaben=sorted(lauf_dir.glob("*.parquet")),
    )


def _leere_tabelle(spalten):
    """Schema-korrekt, aber ohne Zeilen — der Fall, der bisher durchkam."""
    return pd.DataFrame({n: pd.Series(dtype=d) for n, d in spalten})


def _bundle_kopie(bundle, tmp_path, entfernen=(), **ersatz):
    ziel = tmp_path / "lauf"
    shutil.copytree(bundle, ziel)
    for name in entfernen:
        (ziel / f"{name}.parquet").unlink()
    for name, tabelle in ersatz.items():
        write_portfolio(tabelle, ziel / f"{name}.parquet")
    _manifest(ziel)
    return ziel


def _argv(lauf_dir, out_dir, *extra):
    return [
        "--config", str(CONFIG),
        "--lauf", str(lauf_dir),
        "--stichtag", STICHTAG.isoformat(),
        "--bis", HORIZONT.isoformat(),
        "--out-dir", str(out_dir),
        *extra,
    ]


def test_abschluss_friert_die_eine_bewertungsstrecke_ein(lauf, config, tmp_path):
    stamm, historie, scheiben = lauf
    pfad = schreibe_abschluss(
        stamm, historie, config, STICHTAG, tmp_path, **lauf.neben
    )

    fest = read_portfolio(pfad)
    assert list(fest.columns) == list(ABSCHLUSS_NAMES)
    assert (fest["kern_version"] == KERN_VERSION).all()
    assert fest["police_id"].is_unique

    # Der Abschluss ist die einzelvertragliche Form derselben Rechnung,
    # die auch die Aggregation traegt: die Summen muessen exakt decken.
    agg = auswertungs_verlauf(
        stamm, historie, config, [STICHTAG], **lauf.neben
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
        stamm, historie, config, STICHTAG, tmp_path, **lauf.neben
    )
    davor = pfad.read_bytes()

    with pytest.raises(AbschlussError, match="nie ueberschrieben"):
        schreibe_abschluss(
            stamm, historie, config, STICHTAG, tmp_path, **lauf.neben
        )

    assert pfad.read_bytes() == davor


def test_abschluss_ist_byte_deterministisch(lauf, config, tmp_path):
    stamm, historie, scheiben = lauf
    a = schreibe_abschluss(
        stamm, historie, config, STICHTAG, tmp_path / "a", **lauf.neben
    )
    b = schreibe_abschluss(
        stamm, historie, config, STICHTAG, tmp_path / "b", **lauf.neben
    )
    assert a.read_bytes() == b.read_bytes()


def test_pruefung_deckt_unveraenderten_stand(lauf, config, tmp_path):
    stamm, historie, scheiben = lauf
    pfad = schreibe_abschluss(
        stamm, historie, config, STICHTAG, tmp_path, **lauf.neben
    )
    assert pruefe_abschluss(pfad, stamm, historie, config, **lauf.neben) == []


def test_pruefung_weist_wertabweichung_aus_und_laesst_den_abschluss_stehen(
    lauf, config, tmp_path
):
    """Der Kernfall des Bausteins: Aendert sich die Rechnung nach der
    Festschreibung (hier simuliert durch einen manipulierten Bestand),
    wird die Abweichung je Police und Groesse AUSGEWIESEN — der
    festgeschriebene Stand bewegt sich nicht."""
    stamm, historie, scheiben = lauf
    pfad = schreibe_abschluss(
        stamm, historie, config, STICHTAG, tmp_path, **lauf.neben
    )
    davor = pfad.read_bytes()

    anders = stamm.copy()
    ziel = anders.index[anders["status_id"] == 1][0]
    pid = int(anders.loc[ziel, "police_id"])
    anders.loc[ziel, "sum_insured"] = float(anders.loc[ziel, "sum_insured"]) * 2

    befunde = pruefe_abschluss(pfad, anders, historie, config, **lauf.neben)

    assert any(f"police {pid}" in b and "deckungskapital" in b for b in befunde)
    assert pfad.read_bytes() == davor


def test_pruefung_benennt_geaenderten_kernstand(lauf, config, tmp_path, monkeypatch):
    stamm, historie, scheiben = lauf
    pfad = schreibe_abschluss(
        stamm, historie, config, STICHTAG, tmp_path, **lauf.neben
    )
    import rechner_pipeline.bestand.abschluss as modul

    monkeypatch.setattr(modul, "KERN_VERSION", "99.0.0")
    befunde = pruefe_abschluss(pfad, stamm, historie, config, **lauf.neben)

    assert any("Kern" in b and "99.0.0" in b for b in befunde)
    assert any("bleibt stehen" in b for b in befunde)


def test_leerer_stichtag_ist_eine_gueltige_leere_bilanz(lauf, config, tmp_path):
    """ADR-020: Ein Unternehmen beginnt leer. Ein Stichtag ohne
    in-force-Vertrag (vor dem ersten Beginn) traegt eine gueltige, leere
    Eroeffnungsbilanz — kein Aufruffehler mehr. Der festgeschriebene Stand
    hat die Abschlussspalten und null Zeilen."""
    from rechner_pipeline.models.bestand import ABSCHLUSS_NAMES, validate_abschluss

    stamm, historie, scheiben = lauf
    pfad = schreibe_abschluss(
        stamm, historie, config, dt.date(1980, 1, 1), tmp_path,
        **lauf.neben,
    )
    fest = pd.read_parquet(pfad)
    assert len(fest) == 0 and list(fest.columns) == list(ABSCHLUSS_NAMES)
    assert validate_abschluss(fest) == []


def test_vorhandene_abschluesse_listet_sortiert(lauf, config, tmp_path):
    stamm, historie, scheiben = lauf
    schreibe_abschluss(
        stamm, historie, config, dt.date(2017, 1, 1), tmp_path, **lauf.neben
    )
    schreibe_abschluss(
        stamm, historie, config, STICHTAG, tmp_path, **lauf.neben
    )

    gefunden = vorhandene_abschluesse(tmp_path)

    assert list(gefunden) == [STICHTAG, dt.date(2017, 1, 1)]
    assert gefunden[STICHTAG] == abschluss_pfad(tmp_path, STICHTAG)


def test_cli_schreibt_und_prueft(bundle, tmp_path, capsys):
    out = tmp_path / "abschluesse"
    argv = _argv(bundle, out)

    assert cli_abschluss.main(argv) == 0
    assert (out / f"abschluss_{STICHTAG}.parquet").is_file()
    # Doppel-Festschreibung: harter Fehler.
    assert cli_abschluss.main(argv) == 2
    # Pruefung deckt.
    assert cli_abschluss.main(argv + ["--pruefen"]) == 0
    meldungen = capsys.readouterr().err
    assert "nie ueberschrieben" in meldungen
    assert "deckt den Abschluss" in meldungen


# --- T16-01/T16-02: der Abschluss verlangt das ganze Bundle ----------------
#
# Alle folgenden Faelle lieferten vor der Korrektur Exit 0 und einen
# festgeschriebenen, materiell falschen Stand — den die eigene Kontrolle
# anschliessend bestaetigte. Sie pruefen die VERDRAHTUNG in der CLI, nicht
# nur die Engine: genau dort war die Luecke.


def test_leere_scheiben_blockieren_den_abschluss(bundle, tmp_path, capsys):
    """T16-01: schema-korrekt, aber ohne Zeilen — und das Ledger traegt ERH.

    Gemessen am regulaeren KLV-Lauf lag das Deckungskapital dadurch um
    3.795.035,38 zu niedrig, bei Exit 0 und in einem unumkehrbaren Stand.
    """
    lauf_dir = _bundle_kopie(
        bundle, tmp_path, scheiben=_leere_tabelle(SCHEIBEN_SPALTEN)
    )
    out = tmp_path / "abschluesse"

    assert cli_abschluss.main(_argv(lauf_dir, out)) == 2
    assert not (out / f"abschluss_{STICHTAG}.parquet").exists()
    assert "Vorbedingung" in capsys.readouterr().err


def test_leere_historie_blockiert_den_abschluss(bundle, tmp_path, capsys):
    """T16-02: eine leere Historie ist ein DataFrame und kam bisher durch.

    Der gefuehrte Zustand ginge verloren; gemessen 55,7 statt 35,5 Mio
    Deckungskapital.
    """
    lauf_dir = _bundle_kopie(
        bundle, tmp_path, historie=_leere_tabelle(STATUS_HISTORIE_SPALTEN)
    )
    out = tmp_path / "abschluesse"

    assert cli_abschluss.main(_argv(lauf_dir, out)) == 2
    assert not (out / f"abschluss_{STICHTAG}.parquet").exists()
    assert "Journalzeilen" in capsys.readouterr().err


def test_fehlendes_ledger_blockiert_den_abschluss(bundle, tmp_path, capsys):
    """Ohne Ledger laeuft die Bewegungspruefung nicht — dann sind fehlende
    Scheiben wieder unsichtbar. Der Abschluss verlangt das Bundle ganz."""
    lauf_dir = _bundle_kopie(bundle, tmp_path, entfernen=("ledger",))
    out = tmp_path / "abschluesse"

    assert cli_abschluss.main(_argv(lauf_dir, out)) == 2
    assert not (out / f"abschluss_{STICHTAG}.parquet").exists()
    assert "unvollstaendiges Lauf-Bundle" in capsys.readouterr().err


def test_stichtag_hinter_dem_horizont_blockiert(bundle, tmp_path, capsys):
    """Ein Abschluss auf Jahre, die der Lauf nie simuliert hat, ist keine
    Bewertung. Frueher lief er durch und die Bewegungspruefung htte ihn
    mit irrefuehrenden Meldungen quittiert."""
    out = tmp_path / "abschluesse"
    argv = [
        "--config", str(CONFIG),
        "--lauf", str(bundle),
        "--stichtag", "2026-01-01",
        "--bis", HORIZONT.isoformat(),
        "--out-dir", str(out),
    ]

    assert cli_abschluss.main(argv) == 2
    assert "Horizont" in capsys.readouterr().err


def test_pruefen_faellt_nicht_mit_dem_defekt_mit(bundle, tmp_path, capsys):
    """Die gemeinsame-Eingabe-Closure: Produzent UND Kontrolle rechneten mit
    demselben unvollstaendigen Bundle und bestaetigten einander.

    Ein korrekt festgeschriebener Abschluss, danach --pruefen auf einem
    Bundle mit leeren Scheiben: die Kontrolle muss blockieren, statt
    "Neuberechnung deckt den Abschluss" zu melden.
    """
    out = tmp_path / "abschluesse"
    assert cli_abschluss.main(_argv(bundle, out)) == 0
    capsys.readouterr()

    kaputt = _bundle_kopie(
        bundle, tmp_path, scheiben=_leere_tabelle(SCHEIBEN_SPALTEN)
    )
    assert cli_abschluss.main(_argv(kaputt, out, "--pruefen")) == 2
    meldungen = capsys.readouterr().err
    assert "deckt den Abschluss" not in meldungen


def test_gamma1_abweichung_blockiert_den_abschluss(bundle, tmp_path, capsys):
    """Der gamma1-Waechter, end-to-end durch die produktive Verdrahtung.

    Der bisherige Test rief validate_scheiben direkt auf; die Verdrahtung
    des Validators in pruefe_pb1_eingaenge liess sich entfernen, ohne dass
    ein Test rot wurde. Dieser Fall geht ueber physisches Parquet und die
    CLI: gamma1 != 0 rechnet still falsch (gemessen -5.0 -> Jahresbeitrag
    -7.202,87 EUR), und der Stand waere danach festgeschrieben.
    """
    scheiben = read_portfolio(bundle / "scheiben.parquet")
    scheiben.loc[scheiben.index[0], "gamma1"] = -5.0
    lauf_dir = _bundle_kopie(bundle, tmp_path, scheiben=scheiben)
    out = tmp_path / "abschluesse"

    assert cli_abschluss.main(_argv(lauf_dir, out)) == 2
    assert not (out / f"abschluss_{STICHTAG}.parquet").exists()
    assert "gamma1" in capsys.readouterr().err


def test_leere_historie_ist_wie_keine(lauf, config):
    """T16-02 eine Ebene tiefer: auch der Bibliotheksaufruf muss sie
    ablehnen, nicht nur die CLI."""
    from rechner_pipeline.bestand.auswertung import einzelwerte_am

    stamm, _historie, scheiben = lauf
    with pytest.raises(ValueError, match="keine Historie"):
        einzelwerte_am(
            stamm, _leere_tabelle(STATUS_HISTORIE_SPALTEN), config,
            STICHTAG, scheiben=scheiben,
        )


# --------------------------------------------------------------------------- #
# T18-03: Zwischen Pruefung und Verarbeitung darf nichts mehr passieren
# --------------------------------------------------------------------------- #

def test_tausch_nach_bestandener_pruefung_wirkt_nicht_mehr(
    bundle, tmp_path, monkeypatch
):
    """Externes Review T18-03, als Regression festgeschrieben.

    Im Nachweis wurde ``scheiben.parquet`` DIREKT NACH der bestandenen
    P-B1-Pruefung atomar gegen eine gueltige leere Tabelle getauscht;
    die CLI las erneut, endete mit Exit 0 und publizierte einen um
    3.795.035,38 EUR zu niedrigen Stand. Der Fix beseitigt den zweiten
    Lesevorgang: Was geprueft wurde, wird verarbeitet.

    Der Test stellt den Angriff exakt nach — er tauscht die Datei im
    Moment zwischen Pruefung und Rechnung — und verlangt, dass der
    Abschluss die VOLLEN Scheiben traegt, nicht die leeren.
    """
    from rechner_pipeline.bestand import cli_abschluss, vorbedingungen
    from rechner_pipeline.models.bestand import SCHEIBEN_SPALTEN

    lauf_dir = _bundle_kopie(bundle, tmp_path)
    out_dir = tmp_path / "abschluesse"
    echt = vorbedingungen.lies_und_pruefe_pb1

    def _pruefen_dann_tauschen(eingaben, **kwargs):
        ergebnis = echt(eingaben, **kwargs)
        # Der Angriff: nach dem Urteil, vor der Verarbeitung.
        write_portfolio(_leere_tabelle(SCHEIBEN_SPALTEN),
                        lauf_dir / "scheiben.parquet")
        return ergebnis

    monkeypatch.setattr(vorbedingungen, "lies_und_pruefe_pb1",
                        _pruefen_dann_tauschen)
    monkeypatch.setattr(cli_abschluss, "lies_und_pruefe_pb1",
                        _pruefen_dann_tauschen)

    assert cli_abschluss.main(_argv(lauf_dir, out_dir)) == 0

    # Der festgeschriebene Stand muss die GEPRUEFTEN Scheiben tragen.
    # Mit dem alten Verhalten (erneutes Lesen) waere er um die
    # Erhoehungsscheiben zu niedrig.
    geschrieben = read_portfolio(abschluss_pfad(out_dir, STICHTAG))
    referenz_dir = _bundle_kopie(bundle, tmp_path / "referenz")
    assert cli_abschluss.main(
        _argv(referenz_dir, tmp_path / "referenz-abschluss")) == 0
    referenz = read_portfolio(
        abschluss_pfad(tmp_path / "referenz-abschluss", STICHTAG))

    spalte = "deckungskapital" if "deckungskapital" in geschrieben.columns \
        else [c for c in geschrieben.columns if "kapital" in c.lower()][0]
    assert float(geschrieben[spalte].sum()) == pytest.approx(
        float(referenz[spalte].sum())), (
        "der getauschte Stand ist in den Abschluss gelangt")


# --- T25-09: die geprueften Bewertungsgroessen kommen aus einer Quelle ----
#
# Zwei Pruefungen fuehrten dieselbe Spaltenmenge als Literal, und beiden
# fehlte ``korrekturschicht``. Die Proben unten mutieren genau diese eine
# Spalte: ohne die Ableitung bleiben beide still.


def test_geprueft_werden_alle_bewertungsgroessen_des_abschlusses():
    """Die Menge wird aus dem Spaltentyp abgeleitet, nicht gepflegt."""
    assert ABSCHLUSS_ZAHLEN == tuple(
        n for n, dtype in ABSCHLUSS_SPALTEN if dtype == "float64"
    )
    # Positivkontrolle: die Spalte, an der die Luecke haftete, ist drin —
    # und jede abgeleitete Groesse ist wirklich eine Spalte des Abschlusses.
    assert "korrekturschicht" in ABSCHLUSS_ZAHLEN
    assert set(ABSCHLUSS_ZAHLEN) <= set(ABSCHLUSS_NAMES)


def _mit_geaenderter_spalte(pfad, spalte, wert):
    """Genau eine Zahl einer Police im festgeschriebenen Stand bewegen."""
    tabelle = read_portfolio(pfad)
    pid = int(tabelle.iloc[0]["police_id"])
    tabelle.loc[tabelle.index[0], spalte] = wert
    pfad.chmod(0o644)
    write_portfolio(tabelle, pfad)
    return pid


def test_nachrechnung_faellt_auf_eine_bewegte_korrekturschicht(
    lauf, config, tmp_path
):
    """Die Schicht ist ein eigener Bilanzposten (9.11) — bewegt sie sich,
    ist der Stand ein anderer, auch wenn die Summe zufaellig stimmt."""
    stamm, historie, scheiben = lauf
    pfad = schreibe_abschluss(
        stamm, historie, config, STICHTAG, tmp_path, **lauf.neben
    )
    pid = _mit_geaenderter_spalte(pfad, "korrekturschicht", 5.0)

    befunde = pruefe_abschluss(pfad, stamm, historie, config, **lauf.neben)

    assert any(f"police {pid}" in b and "korrekturschicht" in b for b in befunde)


def test_unendliche_korrekturschicht_ist_kein_bilanzstand(
    lauf, config, tmp_path
):
    stamm, historie, scheiben = lauf
    pfad = schreibe_abschluss(
        stamm, historie, config, STICHTAG, tmp_path, **lauf.neben
    )
    _mit_geaenderter_spalte(pfad, "korrekturschicht", float("inf"))

    fehler = validate_abschluss(read_portfolio(pfad))

    assert any("korrekturschicht" in f and "nichtendlich" in f for f in fehler)


# --------------------------------------------------------------------------- #
# Befund aus dem Raten-Block (2026-10-01): Herabsetzung und Teilkuendigung im
# Abschluss — die Klasse "der Test baut seine Eingaben selbst"
# --------------------------------------------------------------------------- #


def _monat_plus(tag, monate: int) -> dt.date:
    j, m = divmod(tag.month - 1 + monate, 12)
    return dt.date(tag.year + j, m + 1, 1)


def test_herabgesetzte_und_teilgekuendigte_vertraege_stehen_gekuerzt_und_monatsgenau_im_abschluss(
        lauf, _fortschreibung, config, tmp_path):
    """Der Lauf der KLV-Config erzeugt beide Vorgaenge (Raten seit dem
    Raten-Block). Je ein herabgesetzter und ein teilgekuendigter Vertrag,
    sieben Monate nach dem Vorgang: Die Abschlusszeile ist die unabhaengige
    Kontrollrechnung —

    * Teilkuendigung: der gewoehnliche Kern mit der Summe f x S, die
      Deckungsrueckstellung seiner beiden Jahreszeilen im Test gemischt;
    * Herabsetzung: der geknickte Verlauf des Kerns an den beiden
      Jahrestagen (``vertrags_monatsreserve_reduziert``), im Test gemischt.

    Und ohne die Reduktionstabelle stuende der Vertrag ungekuerzt da — die
    Blindheit, die der Befund benannte (Detektor mit Treffer).

    Mutationsprobe: in ``einzelwerte_am`` die Reduktionen nicht anwenden ->
    rot; ``monat`` in ``werte_reduziert`` auf den Jahrestag -> rot."""
    import dataclasses

    from rechner_pipeline.bestand.auswertung import grundlagen_je_police
    from rechner_pipeline.kern import ModelPoint, Rechenkern
    from rechner_pipeline.kern.beitragsreduktion import (
        TEILKUENDIGUNG,
        reduzierte_teile,
        vertrags_monatsreserve_reduziert,
    )
    from rechner_pipeline.models.bestand import model_point_kwargs

    stamm, historie, _scheiben = lauf
    _basis, ergebnis = _fortschreibung
    red = ergebnis.reduktionen
    mit_scheiben = set(ergebnis.scheiben["police_id"]) if len(ergebnis.scheiben) else set()
    grundlagen = grundlagen_je_police(config)
    tarifwerk = {g.name: g.tarifwerk() for g in config.generationen}
    zeile_je = stamm.set_index("police_id")
    geprueft = {"herabsetzung": 0, "teilkuendigung": 0}
    for r in red.sort_values(["reduktion_datum", "police_id"]).to_dict("records"):
        pid = int(r["police_id"])
        art = "teilkuendigung" if r["verfahren"] == TEILKUENDIGUNG else "herabsetzung"
        if geprueft[art] or pid in mit_scheiben:
            continue
        stichtag = _monat_plus(pd.Timestamp(r["reduktion_datum"]).date(), 7)
        if stichtag > HORIZONT:
            continue
        pfad = schreibe_abschluss(stamm, historie, config, stichtag, tmp_path / f"{art}-{pid}",
                                  **lauf.neben)
        fest = read_portfolio(pfad).set_index("police_id")
        if pid not in fest.index or fest.loc[pid, "status_code"] != "POL":
            continue
        z = zeile_je.loc[pid]
        mp = ModelPoint(**model_point_kwargs(z, grundlagen(pid, str(z["tarif_generation"]))))
        jahr, u = int(r["reduktion_jahr"]), 7 / 12.0
        if art == "teilkuendigung":
            folge = Rechenkern(dataclasses.replace(
                mp, sum_insured=float(r["anteil"]) * mp.sum_insured))
            unten = folge.verlaufszeile(jahr).drx_bpfl
            oben = folge.verlaufszeile(jahr + 1).drx_bpfl
        else:
            sj = bool(tarifwerk[str(z["tarif_generation"])]["stoab_je_baustein"])
            teile = reduzierte_teile(Rechenkern(mp), [], jahr, float(r["anteil"]),
                                     str(r["verfahren"]), stoab_je_baustein=sj)
            unten = vertrags_monatsreserve_reduziert(
                teile, 12 * jahr, stoab_je_baustein=sj).drx_bpfl
            oben = vertrags_monatsreserve_reduziert(
                teile, 12 * (jahr + 1), stoab_je_baustein=sj).drx_bpfl
        ist = float(fest.loc[pid, "deckungskapital"])
        assert ist == pytest.approx((1 - u) * unten + u * oben, rel=1e-10), (art, pid)
        assert ist != pytest.approx(unten, rel=1e-9), (art, pid)
        # Ohne die Reduktionstabelle: ungekuerzt — genau die Blindheit.
        blind = read_portfolio(schreibe_abschluss(
            stamm, historie, config, stichtag, tmp_path / f"{art}-{pid}-blind",
            **dict(lauf.neben, reduktionen=None))).set_index("police_id")
        assert float(blind.loc[pid, "leistung"]) > float(fest.loc[pid, "leistung"]), (art, pid)
        assert float(blind.loc[pid, "deckungskapital"]) > ist, (art, pid)
        geprueft[art] += 1
    assert geprueft == {"herabsetzung": 1, "teilkuendigung": 1}, (
        "die Welt traegt nicht beide Vorgaenge in Kraft — der Test prueft dann nichts",
        red["verfahren"].value_counts().to_dict())


def test_ratsche_jeder_aufrufer_des_abschlusses_nennt_jede_nebentabelle():
    """Die Klasse geschlossen: ``schreibe_abschluss`` und ``pruefe_abschluss``
    haben fuer die Nebentabellen KEINEN Vorgabewert (Python verweigert den
    Aufruf ohne sie), und jeder Aufruf in ``src`` von ``einzelwerte_am``,
    ``auswertungs_verlauf`` und ``_rechne`` nennt alle fuenf. Positivkontrolle:
    ein Aufruf ohne ``reduktionen`` wird gefunden."""
    import ast
    import inspect

    from rechner_pipeline.bestand import abschluss as modul
    from tests.nebentabellen import NAMEN

    for f in (modul.schreibe_abschluss, modul.pruefe_abschluss):
        parameter = inspect.signature(f).parameters
        for n in NAMEN:
            assert parameter[n].default is inspect.Parameter.empty, (f.__name__, n)
            assert parameter[n].kind is inspect.Parameter.KEYWORD_ONLY, (f.__name__, n)

    def fehlend(text: str, mit_rechne: bool = False) -> list:
        # ``_rechne`` heisst auch eine fremde Funktion (qa.abzugsabgleich);
        # gemeint ist nur die des Abschlusses.
        aus = []
        for k in ast.walk(ast.parse(text)):
            if not isinstance(k, ast.Call):
                continue
            name = k.func.id if isinstance(k.func, ast.Name) else getattr(k.func, "attr", None)
            if name not in ("einzelwerte_am", "auswertungs_verlauf",
                            "schreibe_abschluss", "pruefe_abschluss") and not (
                                mit_rechne and name == "_rechne"):
                continue
            genannt = {kw.arg for kw in k.keywords}
            if None in genannt or len(k.args) >= 9:
                continue      # **kwargs durchgereicht bzw. _rechne positionsweise
            luecke = set(NAMEN) - genannt
            if luecke:
                aus.append((name, k.lineno, sorted(luecke)))
        return aus

    src = REPO_ROOT / "src" / "rechner_pipeline"
    befunde = {str(p.relative_to(src)): fehlend(
        p.read_text("utf-8"), mit_rechne=p.name == "abschluss.py") for p in src.rglob("*.py")}
    assert {k: v for k, v in befunde.items() if v} == {}
    assert fehlend("einzelwerte_am(s, h, c, t, scheiben=x, merkmale=None, "
                   "schichten=None, verankerung=None)") == [
        ("einzelwerte_am", 1, ["reduktionen"])]
