"""Externes Review T22-01 (= T21-02): A-M4 nahm ein P-B1-Minimalprofil an.

Nachweis des Reviews: P-B1 nur mit ``--portfolio`` auf dem Bestandsfall,
``amounts_derived None``, ``am4_exit 0``. Die unter T21 geschlossene
Betragspruefung liess sich am A-M4-Uebergang durch Weglassen der
Eingaben abschalten. Jetzt verlangt A-M4 im Bestands-Scope das
Vollprofil: Stamm, Journal, Ledger, Config, Horizont, Betragsbindung.

Knoten: klv
"""

from __future__ import annotations

from pathlib import Path

from rechner_pipeline.gates import bestand_validate
from tests.test_pk1_am4_beweisvertrag import (
    einpolicen_config,
    HORIZONT_BESTANDSFALL,
    pb1_vollprofil_argv,
    REPO_ROOT,
    _abnahmebericht,
    _bereite_bestandsfall,
)


def _pb1(fall: Path, argv: list):
    return bestand_validate.main(argv + [
        "--repo-root", str(REPO_ROOT),
        "--diagnostics-dir", str(fall / "abgeleitet" / "diagnostics"),
    ])


def test_minimalprofil_ist_kein_am4_beleg(tmp_path: Path):
    """Der Repro des Reviews. Mutationsprobe: PB1_VOLLPROFIL leeren -> rot."""
    fall = _bereite_bestandsfall(tmp_path)
    lauf = fall / "abgeleitet" / "bestand"
    # Das kleinste Profil, das P-B1 fuer einen gefuehrten Bestand annimmt:
    # Stamm und Journal (ein Folgezustand verlangt sein Journal). Kein
    # Ledger, keine Config, kein Horizont.
    pb1 = _pb1(fall, ["--portfolio", str(lauf / "bestand_gesamt.parquet"),
                      "--historie", str(lauf / "historie.parquet")])
    assert pb1.exit_code == 0, pb1.errors          # P-B1 selbst ist gruen ...
    assert "betraege_hergeleitet" not in pb1.summary
    bericht = _abnahmebericht(fall)                # ... aber kein A-M4-Beleg
    assert bericht.exit_code == 20
    assert bericht.errors[0]["code"] == "pb1_contract"
    meldung = " ".join(e["message"] for e in bericht.errors)
    assert "Vollprofil" in meldung and "'ledger'" in meldung and "'config'" in meldung
    assert "betraege_hergeleitet" in meldung


def test_ohne_config_fehlt_die_betragsbindung(tmp_path: Path):
    """Journal und Ledger allein reichen nicht: Ohne Config lief die
    Kern-Herleitung nicht, und der Beleg sagt es nicht."""
    fall = _bereite_bestandsfall(tmp_path)
    lauf = fall / "abgeleitet" / "bestand"
    pb1 = _pb1(fall, [
        "--portfolio", str(lauf / "bestand_gesamt.parquet"),
        "--historie", str(lauf / "historie.parquet"),
        "--ledger", str(lauf / "ledger.parquet"),
        "--scheiben", str(lauf / "scheiben.parquet"),
        "--bis", "2020-01-01",
    ])
    assert pb1.exit_code == 0
    bericht = _abnahmebericht(fall)
    assert bericht.exit_code == 20
    meldung = " ".join(e["message"] for e in bericht.errors)
    assert "'config'" in meldung and "betraege_hergeleitet" in meldung


def test_vollprofil_ist_ein_am4_beleg(tmp_path: Path):
    fall = _bereite_bestandsfall(tmp_path)
    lauf = fall / "abgeleitet" / "bestand"
    # Seit Review T23-04 liegt jede P-B1-Rolle im Fall — auch die Config.
    pb1 = _pb1(fall, pb1_vollprofil_argv(lauf, einpolicen_config(fall / "abgeleitet"), bis=HORIZONT_BESTANDSFALL))
    assert pb1.exit_code == 0, pb1.errors
    assert isinstance(pb1.summary.get("betraege_hergeleitet"), int)
    assert _abnahmebericht(fall).exit_code == 0


def test_mit_korrekturschicht_verlangt_das_vollprofil_schicht_und_verankerung(tmp_path: Path):
    """Review T25-03, Entscheid des Maintainers 2026-09-15: Fuehrt der Fall
    eine materialisierte schichten.parquet, sind schichten und verankerung
    Pflichtrollen des A-M4-Vollprofils.

    Vorher nahm A-M4 einen Bestand ab, dessen Korrekturschicht P-B1 nie
    gelesen hatte — die Abnahme rechnete eine andere Welt als die Fuehrung.
    Bei N-01 gemessen: rund 13.700 EUR Deckungskapital je Vertrag.

    Mutationsprobe: PB1_VOLLPROFIL_SCHICHT leeren -> gruen, also rot hier.
    """
    from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
    from rechner_pipeline.models.bestand import STAMM_NAMES
    from tests.test_betrieb_neuaufsetzen import _schichten, _verankerung

    fall = _bereite_bestandsfall(tmp_path)
    lauf = fall / "abgeleitet" / "bestand"
    # Der Minimalfall dieses Moduls fuehrt keine Schicht — der Test stellt
    # seinen Gegenstand selbst her: eine materialisierte Korrekturschicht
    # im Uebernahme-Verzeichnis, fuer die Police, die der Fall fuehrt.
    police = int(read_portfolio(lauf / "bestand.parquet",
                                expected_columns=STAMM_NAMES)["police_id"].iloc[0])
    ueber = fall / "abgeleitet" / "uebernahme"
    write_portfolio(_schichten(police), ueber / "schichten.parquet")
    write_portfolio(_verankerung(police), ueber / "verankerung.parquet")
    assert any((fall / "abgeleitet").rglob("schichten.parquet"))

    # Ein sonst VOLLSTAENDIGES Profil, nur ohne Schicht und Verankerung.
    ohne = _pb1(fall, ["--portfolio", str(lauf / "bestand_gesamt.parquet"),
                       "--historie", str(lauf / "historie.parquet"),
                       "--ledger", str(lauf / "ledger.parquet"),
                       "--scheiben", str(lauf / "scheiben.parquet"),
                       "--config", str(fall / "abgeleitet" / "einpolice.toml"),
                       "--bis", "2026-01-01"])
    assert ohne.exit_code == 0, ohne.errors        # P-B1 selbst ist gruen ...
    bericht = _abnahmebericht(fall)                # ... aber kein A-M4-Beleg
    assert bericht.exit_code != 0
    meldung = " ".join(e["message"] for e in bericht.errors)
    assert "Vollprofil" in meldung
    assert "'schichten'" in meldung and "'verankerung'" in meldung
