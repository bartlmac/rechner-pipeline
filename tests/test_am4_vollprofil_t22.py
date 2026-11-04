"""Externes Review T22-01 (= T21-02): A-M4 nahm ein P-B1-Minimalprofil an.

Nachweis des Reviews: P-B1 nur mit ``--portfolio`` auf dem Bestandsfall,
``amounts_derived None``, ``am4_exit 0``. Die unter T21 geschlossene
Betragspruefung liess sich am A-M4-Uebergang durch Weglassen der
Eingaben abschalten. Jetzt verlangt A-M4 im Bestands-Scope das
Vollprofil: Stamm, Journal, Ledger, Config, Horizont, Betragsbindung.

Knoten: klv
"""

from __future__ import annotations

import json
from pathlib import Path

from rechner_pipeline.gates import bestand_validate
from tests.test_baldrian2_e2e import gefahrener_fall
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
    lauf = fall / "abgeleitet" / "bestand-nach"
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
    lauf = fall / "abgeleitet" / "bestand-nach"
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
    lauf = fall / "abgeleitet" / "bestand-nach"
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

    Der Fall fuehrt materialisierte Schicht und Verankerung, doch die
    bereits gerechnete Suite nennt beide nicht unter ihren Eingaben.
    A-M4 verweigert schon an dieser frueheren Bindungspruefung, bevor
    es das unvollstaendige P-B1-Profil als Abnahmebeleg ansehen kann.
    """
    from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
    from rechner_pipeline.models.bestand import STAMM_NAMES
    from tests.test_betrieb_neuaufsetzen import _schichten, _verankerung

    fall = _bereite_bestandsfall(tmp_path)
    lauf = fall / "abgeleitet" / "bestand-nach"
    # Der Minimalfall dieses Moduls fuehrt keine Schicht — der Test stellt
    # seinen Gegenstand selbst her: materialisierte Tabellen im geprüften
    # Lauf ohne passende Ausgaberollen in dessen Manifest. Die echte
    # Uebernahme bleibt unveraendert, damit ihre Fallrolle weiter stimmt.
    police = int(read_portfolio(lauf / "bestand.parquet",
                                expected_columns=STAMM_NAMES)["police_id"].iloc[0])
    write_portfolio(_schichten(police), lauf / "schichten.parquet")
    write_portfolio(_verankerung(police), lauf / "verankerung.parquet")
    assert any((fall / "abgeleitet").rglob("schichten.parquet"))

    # Ein sonst VOLLSTAENDIGES Profil, nur ohne Schicht und Verankerung.
    ohne = _pb1(fall, ["--portfolio", str(lauf / "bestand_gesamt.parquet"),
                       "--historie", str(lauf / "historie.parquet"),
                       "--ledger", str(lauf / "ledger.parquet"),
                       "--scheiben", str(lauf / "scheiben.parquet"),
                       "--config", str(fall / "abgeleitet" / "einpolice.toml"),
                       "--manifest", str(lauf / "laufmanifest.json"),
                       # Der Horizont ist eine Eigenschaft des LAUFS, nicht
                       # des Aufrufs — das Manifest bindet ihn.
                       "--bis", HORIZONT_BESTANDSFALL])
    assert ohne.exit_code == 0, ohne.errors        # P-B1 selbst ist gruen ...
    bericht = _abnahmebericht(fall)                # ... aber kein A-M4-Beleg
    assert bericht.exit_code != 0
    meldung = " ".join(e["message"] for e in bericht.errors)
    assert "von der Suite nicht gelesen" in meldung, meldung
    assert "schichten.parquet" in meldung and "verankerung.parquet" in meldung


def test_querpruefung_findet_eine_schicht_die_der_belegte_lauf_nicht_nennt(tmp_path: Path):
    """Die Querpruefung von A-M4 (Entscheid 2026-09-16): Fuehrt der Fall
    eine schichten.parquet, die der belegte P-B1-Lauf nicht unter seinen
    Ausgaben nennt, hat die Abnahme an der Korrekturschicht vorbeigerechnet,
    und A-M4 sagt, WAS fehlt.

    Seit der Schichtbeleg-Pflicht (A-058) verweigern die Suite Tabellen
    neben ihrem Bestand und die Pflicht eine Verankerung im festen
    Fallbestand schon vorher; der Test oben endet deshalb an der Suite.
    Damit die Querpruefung selbst geprueft bleibt, liegt die Schicht hier an
    einem dritten Ort unter abgeleitet/: weder neben dem Bestand der Suite
    noch im festen Fallbestand. Mutationsprobe: die Querpruefung in
    abnahmebericht abschalten -> rot (A-061, Befund B1).
    """
    from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
    from rechner_pipeline.models.bestand import STAMM_NAMES
    from tests.test_betrieb_neuaufsetzen import _schichten

    fall = _bereite_bestandsfall(tmp_path)
    lauf = fall / "abgeleitet" / "bestand-nach"
    police = int(read_portfolio(lauf / "bestand.parquet",
                                expected_columns=STAMM_NAMES)["police_id"].iloc[0])
    dritter_ort = fall / "abgeleitet" / "schicht-ohne-lauf"
    dritter_ort.mkdir()
    write_portfolio(_schichten(police), dritter_ort / "schichten.parquet")
    # Weder neben dem Bestand der Suite noch im festen Fallbestand.
    assert not (lauf / "schichten.parquet").exists()
    assert not (fall / "abgeleitet" / "bestand" / "schichten.parquet").exists()
    assert not (fall / "abgeleitet" / "bestand" / "verankerung.parquet").exists()

    # Ein sonst VOLLSTAENDIGES Profil, nur ohne Schicht und Verankerung.
    ohne = _pb1(fall, ["--portfolio", str(lauf / "bestand_gesamt.parquet"),
                       "--historie", str(lauf / "historie.parquet"),
                       "--ledger", str(lauf / "ledger.parquet"),
                       "--scheiben", str(lauf / "scheiben.parquet"),
                       "--config", str(fall / "abgeleitet" / "einpolice.toml"),
                       "--manifest", str(lauf / "laufmanifest.json"),
                       "--bis", HORIZONT_BESTANDSFALL])
    assert ohne.exit_code == 0, ohne.errors
    bericht = _abnahmebericht(fall)
    assert bericht.exit_code != 0
    meldung = " ".join(e["message"] for e in bericht.errors)
    assert "nennt sie aber nicht unter seinen Ausgaben" in meldung, meldung
    assert "'schichten'" in meldung and "'verankerung'" in meldung
    # Die Querpruefung urteilt hier allein, nicht die Suite davor.
    assert "von der Suite nicht gelesen" not in meldung, meldung


def test_echter_verankerter_bestand_hat_abgeleiteten_beleg_und_vollprofil(
        gefahrener_fall: Path):
    """Positivkontrolle: die fehlenden Rollen oben sind kein Verbot einer
    verankerten Uebernahme. Der echte Producer liefert alle Rollen und den
    abgeleiteten Schichtbeleg fuer die Nachrechnung von A-M4."""
    fall = gefahrener_fall
    ueber = fall / "abgeleitet" / "bestand"
    schicht = fall / "abgeleitet" / "schichten" / "verankerung_schichten.json"
    manifest = json.loads((ueber / "laufmanifest.json").read_text("utf-8"))
    assert (ueber / "bestand.parquet").is_file()
    assert (ueber / "verankerung.parquet").is_file()
    assert (ueber / "schichten.parquet").is_file()
    assert schicht.is_file()
    assert {"bestand.parquet", "verankerung.parquet", "schichten.parquet"} <= set(
        manifest["ausgaben"])
    assert json.loads((fall / "abgeleitet" / "diagnostics"
                       / "bestand_validate.gate.json").read_text("utf-8"))["status"] == "passed"
    suite = json.loads((fall / "abgeleitet" / "berichte"
                        / "migrationssuite.json").read_text("utf-8"))
    assert suite["suite_bestanden"] is True
    assert "--schicht" in suite["aufruf"]
