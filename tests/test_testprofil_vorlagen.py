"""Vorlagen der drei aktuariellen Abnahmen (ADR-010, ADR-012).

Geprueft wird die Mechanik der Vorlage, nicht die Hoehe der Toleranzen:
Welche Zahl fachlich richtig ist, entscheidet das Aktuariat je Fall, und
ein Test, der eine Zahl festnagelt, verhindert genau das. Festgehalten
wird, was die Vorlage LEISTEN muss — dass sie fuer jede Abnahme
existiert, dass sie eine Weite erzwingt, dass die Begruendung nicht
verlorengeht und dass die Grenzen intern zusammenpassen.

Knoten: klv
"""

from __future__ import annotations

import pytest

from rechner_pipeline.qa.testprofil import (
    RUNDUNGSRAUSCHEN,
    ProfilFehler,
    TESTS,
    VORLAGEN,
    vorlage,
)


def test_jede_abnahme_hat_eine_vorlage():
    """Sonst startet eine der drei Abnahmen ohne begruendeten Ausgangspunkt."""
    assert sorted(VORLAGEN) == sorted(TESTS)


@pytest.mark.parametrize("kennung", TESTS)
def test_vorlage_liefert_ein_gueltiges_profil(kennung):
    profil = vorlage(kennung, weite="Vollerhebung")

    assert profil.kennung == kennung
    assert profil.weite == "Vollerhebung"
    assert profil.bemerkung, "eine Vorlage ohne Begruendung ist eine nackte Zahl"


@pytest.mark.parametrize("kennung", TESTS)
def test_vorlage_erzwingt_die_weite(kennung):
    """Ein Ergebnis ohne Angabe der Ziehung traegt keinen Beleg."""
    with pytest.raises(ProfilFehler, match="Stichprobenweite"):
        vorlage(kennung, weite="")


def test_unbekannte_kennung_ist_harter_fehler():
    with pytest.raises(ProfilFehler, match="keine Vorlage"):
        vorlage("A-M9", weite="Vollerhebung")


def test_fallbemerkung_tritt_neben_die_begruendung_statt_sie_zu_ersetzen():
    """Wer im Fall abweicht, soll sagen warum — ohne das Warum der Vorlage
    zu loeschen."""
    ohne = vorlage("A-M1", weite="Vollerhebung")
    mit = vorlage("A-M1", weite="Vollerhebung", bemerkung="Erstlauf, eng gefahren")

    assert ohne.bemerkung in mit.bemerkung
    assert "Erstlauf, eng gefahren" in mit.bemerkung


@pytest.mark.parametrize("kennung", TESTS)
def test_grenzen_liegen_ueber_dem_rundungsrauschen(kennung):
    """Die Wache aus dem Profil greift auch fuer die eigenen Vorlagen.

    Eine Vorlage, die unter das Rauschen einer centgerundeten Lieferung
    ginge, misst die Darstellung statt der Rechnung — und waere als
    Ausgangspunkt schlimmer als gar keine.
    """
    profil = vorlage(kennung, weite="Vollerhebung")
    alle = [profil.grundtoleranz, *profil.kriterien.values()]
    for k in alle:
        for grenze in (k.max_abs_residuum, k.p95_abs_residuum):
            assert grenze is None or grenze >= RUNDUNGSRAUSCHEN


def test_verlaufstest_faehrt_weiter_als_der_stichtagstest():
    """Ein ueber Jahre fortgeschriebener Wert kann nicht centgleich sein.

    Faellt dieser Test, tragen beide dieselbe Grenze — dann misst einer
    von beiden die falsche Sache.
    """
    stichtag = vorlage("A-M1", weite="Vollerhebung").grundtoleranz
    verlauf = vorlage("A-M2", weite="Vollerhebung").grundtoleranz

    assert verlauf.abs_tol > stichtag.abs_tol
    assert verlauf.max_abs_residuum > stichtag.max_abs_residuum


def test_erhoehung_wird_enger_geprueft_als_ein_gerundeter_betrag():
    """dDK einer Erhoehung ist strukturell null, nicht centgerundet."""
    profil = vorlage("A-M3", weite="Vollerhebung")

    assert profil.fuer("ERH").abs_tol < profil.grundtoleranz.abs_tol


@pytest.mark.parametrize("art", ["STO", "TOD", "ABL", "PEX", "RED"])
def test_uebrige_vorfallarten_tragen_die_grundtoleranz(art):
    """Keine Schein-Differenzierung: Wer dieselbe Grenze traegt, bekommt
    keinen eigenen Eintrag, der etwas anderes suggeriert."""
    profil = vorlage("A-M3", weite="Vollerhebung")

    assert profil.fuer(art) == profil.grundtoleranz


def test_herabsetzung_wird_nicht_weicher_gefahren_als_die_uebrigen():
    """Die Verfahrensdifferenz soll SICHTBAR werden.

    Rechnet die Quelle mit Stornoabzug und das Ziel verlustfrei, weicht
    dDK ab. Diese Grenze aufzuweiten hiesse, den Sachverhalt zu
    verstecken, statt ihn zur Abnahme vorzulegen.
    """
    profil = vorlage("A-M3", weite="Vollerhebung")

    assert profil.fuer("RED").abs_tol <= profil.grundtoleranz.abs_tol
    assert "Herabsetzung" in profil.bemerkung
