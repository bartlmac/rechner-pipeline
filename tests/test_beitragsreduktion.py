"""Beitragsreduktion: zwei vertretbare Verfahren, eine echte Differenz.

Der Geschaeftsvorfall, an dem sich zeigt, wofuer die Korrekturschicht da
ist. Sein Ergebnis ist nirgends per Groesse garantiert — zwei Systeme
duerfen ihn verschieden rechnen, und beide haben recht.

Geprueft wird deshalb nicht "der richtige Wert", sondern:

* dass beide Verfahren die Randfaelle treffen (keine Reduktion, volle
  Freistellung) — dort MUESSEN sie uebereinstimmen bzw. der bekannten
  Groesse entsprechen,
* dass sie dazwischen um genau den anteiligen Stornoabzug abweichen,
* dass die Differenz nicht im Rundungsrauschen verschwindet, sondern das
  erste echte Residuum unseres Vorfuehrbestands ist.

Knoten: klv
"""

from __future__ import annotations

import dataclasses

import pytest

from rechner_pipeline.kern import KLV_DEFAULT
from rechner_pipeline.kern.beitragsreduktion import (
    MIT_ABZUG,
    PROSPEKTIV,
    BeitragsreduktionFehler,
    reduziere,
    verfahrensdifferenz,
)
from rechner_pipeline.kern.rechenkern import Rechenkern

KERN = Rechenkern(KLV_DEFAULT)
JAHR = 9


# --------------------------------------------------------------------------- #
# 1. Die Randfaelle — dort ist die Rechnung nicht frei
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("verfahren", [PROSPEKTIV, MIT_ABZUG])
def test_ohne_reduktion_aendert_sich_nichts(verfahren: str):
    """Anteil 1.0 ist keine Reduktion — beide Verfahren muessen das treffen."""
    r = reduziere(KERN, JAHR, 1.0, verfahren=verfahren)
    assert r.vs_neu == pytest.approx(r.vs_alt, rel=1e-12)
    assert r.bjb_neu == pytest.approx(r.bjb_alt, rel=1e-12)
    assert r.d_dk == pytest.approx(0.0, abs=1e-9)


def test_volle_freistellung_prospektiv_ist_die_beitragsfreie_summe():
    """Unabhaengige Kontrolle: Anteil 0.0 muss VS_bfr des Kerns ergeben.

    Das Verfahren ist hier nicht frei — bei vollstaendiger Freistellung
    gibt es die etablierte Groesse, und die verlustfreie Variante muss
    sie treffen. Trifft sie sie nicht, ist die Konstruktion falsch.
    """
    r = reduziere(KERN, JAHR, 0.0, verfahren=PROSPEKTIV)
    assert r.vs_neu == pytest.approx(KERN.beitragsfreie_summe(JAHR), rel=1e-12)
    assert r.bjb_neu == 0.0


def test_volle_freistellung_mit_abzug_liegt_um_den_stornoabzug_darunter():
    """Das Altverfahren behandelt sie wie eine Kuendigung: Abzug faellig."""
    zeile = KERN.verlaufszeile(JAHR)
    ziel = reduziere(KERN, JAHR, 0.0, verfahren=PROSPEKTIV)
    quelle = reduziere(KERN, JAHR, 0.0, verfahren=MIT_ABZUG)
    erwartete_differenz = -zeile.stoab / zeile.vx_bfr
    assert quelle.vs_neu - ziel.vs_neu == pytest.approx(erwartete_differenz, rel=1e-12)
    # Und im Deckungskapital ist es genau der Stornoabzug.
    assert quelle.dk_nach - ziel.dk_nach == pytest.approx(-zeile.stoab, rel=1e-12)


# --------------------------------------------------------------------------- #
# 2. Dazwischen: die Verfahrensdifferenz
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("anteil", [0.8, 0.5, 0.2])
def test_differenz_ist_der_anteilige_stornoabzug(anteil: float):
    """Sie waechst linear mit dem freiwerdenden Teil — kein Zufallsrauschen."""
    zeile = KERN.verlaufszeile(JAHR)
    d = verfahrensdifferenz(KERN, JAHR, anteil)
    assert d["d_dk"] == pytest.approx(-zeile.stoab * (1.0 - anteil), rel=1e-12)


def test_das_prospektive_verfahren_haelt_die_reserve_vollstaendig():
    """Verlustfrei heisst: die Deckungsrückstellung bleibt im Vertrag."""
    for anteil in (0.0, 0.3, 0.7, 1.0):
        r = reduziere(KERN, JAHR, anteil, verfahren=PROSPEKTIV)
        assert r.dk_nach == pytest.approx(r.dk_vor, rel=1e-12)


def test_die_differenz_liegt_ueber_dem_rundungsrauschen():
    """Der Punkt der Uebung: ein Residuum, das kein Rundungsfehler ist.

    Bisher waren alle Abweichungen des Vorfuehrbestands reine
    Cent-Rundung (Median 0,0024). Eine Verfahrensdifferenz von dieser
    Groessenordnung ist etwas anderes — sie muss von der Korrekturschicht
    getragen und im Bericht begruendet werden.
    """
    from rechner_pipeline.qa.testprofil import RUNDUNGSRAUSCHEN

    d = verfahrensdifferenz(KERN, JAHR, 0.5)
    assert abs(d["d_dk"]) > 1000 * RUNDUNGSRAUSCHEN


def test_beide_verfahren_senken_den_beitrag_gleich():
    """Der Beitrag folgt dem Anteil — daran ist nichts frei."""
    for anteil in (0.0, 0.4, 1.0):
        ziel = reduziere(KERN, JAHR, anteil, verfahren=PROSPEKTIV)
        quelle = reduziere(KERN, JAHR, anteil, verfahren=MIT_ABZUG)
        assert ziel.bjb_neu == pytest.approx(quelle.bjb_neu, rel=1e-12)
        assert ziel.bjb_neu == pytest.approx(ziel.bjb_alt * anteil, rel=1e-12)


# --------------------------------------------------------------------------- #
# 3. Auftragsfehler
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("anteil", [-0.1, 1.5, float("nan")])
def test_anteil_ausserhalb_null_bis_eins_faellt_hart_aus(anteil: float):
    with pytest.raises(BeitragsreduktionFehler, match=r"nicht in \[0, 1\]"):
        reduziere(KERN, JAHR, anteil)


def test_unbekanntes_verfahren_faellt_hart_aus():
    with pytest.raises(BeitragsreduktionFehler, match="unbekanntes Verfahren"):
        reduziere(KERN, JAHR, 0.5, verfahren="erfunden")


def test_nach_beitragsende_gibt_es_nichts_zu_reduzieren():
    """Ein beitragsfreier Vertrag kann seinen Beitrag nicht senken."""
    with pytest.raises(BeitragsreduktionFehler, match="Beitragszahlungsdauer"):
        reduziere(KERN, KLV_DEFAULT.t, 0.5)


def test_jahr_ausserhalb_der_laufzeit_faellt_hart_aus():
    with pytest.raises(BeitragsreduktionFehler, match="ausserhalb der Laufzeit"):
        reduziere(KERN, KLV_DEFAULT.n + 1, 0.5)


# --------------------------------------------------------------------------- #
# 4. Beleg
# --------------------------------------------------------------------------- #


def test_beleg_traegt_das_verfahren_und_die_veraenderung():
    """Welches Verfahren gerechnet wurde, gehoert in den Beleg.

    Ohne diese Angabe ist die Differenz zwischen zwei Systemen nicht
    erklaerbar, sondern nur ein unerklaerter Rest.
    """
    import json

    r = reduziere(KERN, JAHR, 0.6, verfahren=MIT_ABZUG)
    beleg = r.als_beleg()
    json.dumps(beleg)
    assert beleg["verfahren"] == MIT_ABZUG
    assert beleg["anteil"] == 0.6
    assert beleg["dDK"] == pytest.approx(r.dk_nach - r.dk_vor)
