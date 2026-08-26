"""Stichprobenprofile des aktuariellen Tests (ADR-010).

Knoten: klv
"""

from __future__ import annotations

import pytest

from rechner_pipeline.qa.stichprobe import (
    PROFILE,
    Stichprobe,
    StichprobenFehler,
    ziehe,
)


def test_vollbestand_zieht_alle_und_ist_vollerhebung():
    stichprobe = ziehe("vollbestand", ["P-1", "P-2", "P-3"])

    assert stichprobe.umfang == 3
    assert stichprobe.grundgesamtheit == 3
    assert stichprobe.ist_vollerhebung
    assert stichprobe.police_ids == ("P-1", "P-2", "P-3")


def test_beleg_beschreibt_die_stichprobe_vollstaendig():
    """Der Beleg muss die geprueften Vertraege nennen, nicht nur zaehlen."""
    beleg = ziehe("vollbestand", ["P-2", "P-1"]).als_beleg()

    assert beleg == {
        "profil": "vollbestand",
        "parameter": {},
        "umfang": 2,
        "grundgesamtheit": 2,
        "vollerhebung": True,
        "police_ids": ["P-2", "P-1"],
    }


def test_ziehung_ist_deterministisch():
    erste = ziehe("vollbestand", ["P-1", "P-2"])
    zweite = ziehe("vollbestand", ["P-1", "P-2"])

    assert erste == zweite


def test_unbekanntes_profil_faellt_hart_aus():
    """Kein stiller Rueckfall auf den Vollbestand — beide Richtungen waeren
    falsch: eine unbeabsichtigte Vollerhebung ist teuer, eine
    unbeabsichtigt kleine Stichprobe ist ein falscher Nachweis."""
    with pytest.raises(StichprobenFehler) as fehler:
        ziehe("geschichtet_nach_historientyp", ["P-1"])

    meldung = str(fehler.value)
    assert "Unbekanntes Stichprobenprofil" in meldung
    assert "vollbestand" in meldung


def test_leere_grundgesamtheit_ist_kein_bestandener_test():
    with pytest.raises(StichprobenFehler, match="leer"):
        ziehe("vollbestand", [])


def test_doppelte_police_in_der_grundgesamtheit_blockiert():
    with pytest.raises(StichprobenFehler, match="doppelte"):
        ziehe("vollbestand", ["P-1", "P-1"])


def test_vollbestand_nimmt_keine_parameter():
    with pytest.raises(StichprobenFehler, match="keine Parameter"):
        ziehe("vollbestand", ["P-1"], quote=0.1)


def test_stichprobe_verbietet_mehrfache_police():
    with pytest.raises(StichprobenFehler, match="mehrfach"):
        Stichprobe(
            profil="test", parameter={}, police_ids=("P-1", "P-1"),
            grundgesamtheit=2,
        )


def test_stichprobe_darf_die_grundgesamtheit_nicht_uebersteigen():
    with pytest.raises(StichprobenFehler, match="groesser als die"):
        Stichprobe(
            profil="test", parameter={}, police_ids=("P-1", "P-2"),
            grundgesamtheit=1,
        )


def test_v0_kennt_genau_ein_profil():
    """Haelt den bewussten Umfang fest: keine Profile auf Vorrat.

    Faellt dieser Test, ist ein Profil dazugekommen — dann gehoert die
    Erweiterung in ADR-010 Abschnitt 5 nachgezogen.
    """
    assert sorted(PROFILE) == ["vollbestand"]
