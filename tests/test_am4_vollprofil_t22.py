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
    REPO_ROOT,
    _abnahmebericht,
    _bereite_bestandsfall,
    einpolicen_config,
    pb1_vollprofil_argv,
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
    pb1 = _pb1(fall, pb1_vollprofil_argv(lauf, einpolicen_config(tmp_path)))
    assert pb1.exit_code == 0, pb1.errors
    assert isinstance(pb1.summary.get("betraege_hergeleitet"), int)
    assert _abnahmebericht(fall).exit_code == 0
