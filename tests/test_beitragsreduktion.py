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


# --------------------------------------------------------------------------- #
# 5. Folgebewertung: der Vertrag NACH der Reduktion
# --------------------------------------------------------------------------- #

from rechner_pipeline.kern.beitragsreduktion import ReduzierterVertrag  # noqa: E402


def test_folgebewertung_setzt_stetig_an_der_reduktion_auf():
    """Am Reduktions-Jahrestag muss die DR exakt dk_nach sein."""
    rv = ReduzierterVertrag.nach(KERN, JAHR, 0.6)
    mr = rv.monatsreserve(12 * JAHR)
    assert mr.drx_bpfl == pytest.approx(rv.reduktion.dk_nach, rel=1e-12)


def test_anteil_eins_ist_der_unreduzierte_vertrag():
    """f=1 laesst alles unveraendert — bis in den Rueckkaufswert."""
    rv = ReduzierterVertrag.nach(KERN, JAHR, 1.0)
    for monate in (12 * JAHR, 12 * JAHR + 7, 12 * (JAHR + 5)):
        a, b = rv.monatsreserve(monate), KERN.monatsreserve(monate)
        assert a.vx_mrv == pytest.approx(b.vx_mrv, rel=1e-12)
        assert a.rkw == pytest.approx(b.rkw, rel=1e-12)


def test_anteil_null_prospektiv_ist_die_volle_beitragsfreistellung():
    """f=0 muss der beitragsfreien Fortfuehrung des Kerns entsprechen."""
    rv = ReduzierterVertrag.nach(KERN, JAHR, 0.0)
    for monate in (12 * JAHR + 6, 12 * (JAHR + 3)):
        assert rv.monatsreserve(monate).vx_mrv == pytest.approx(
            KERN.monatsreserve_beitragsfrei(JAHR, monate), rel=1e-12)
    assert rv.bjb(12 * JAHR) == 0.0


def test_am_ablauf_steht_die_neue_gesamtsumme():
    """Unabhaengige Kontrolle ueber die Produktlogik: die Reserve laeuft
    auf die Ablaufleistung zu, und die ist nach der Teilung vs_neu."""
    rv = ReduzierterVertrag.nach(KERN, JAHR, 0.6)
    n = KERN.mp.n
    assert rv.monatsreserve(12 * n).vx_mrv == pytest.approx(
        rv.reduktion.vs_neu, rel=1e-9)
    assert rv.terminale_leistung() == pytest.approx(rv.reduktion.vs_neu)


def test_spaetere_beitragsfreistellung_fixiert_beide_teile():
    rv = ReduzierterVertrag.nach(KERN, JAHR, 0.6)
    pex = JAHR + 4
    erwartet = 0.6 * KERN.beitragsfreie_summe(pex) + rv.bfr_teil
    assert rv.beitragsfreie_summe(pex) == pytest.approx(erwartet, rel=1e-12)
    assert rv.terminale_leistung(pex) == pytest.approx(erwartet, rel=1e-12)
    with pytest.raises(BeitragsreduktionFehler, match="vor der Reduktion"):
        rv.beitragsfreie_summe(JAHR - 1)


def test_beitrag_nach_reduktion_und_nach_beitragsende():
    rv = ReduzierterVertrag.nach(KERN, JAHR, 0.6)
    assert rv.bjb(12 * JAHR) == pytest.approx(
        0.6 * KERN.gross_annual_premium(), rel=1e-12)
    assert rv.bjb(12 * KERN.mp.t) == 0.0
    with pytest.raises(BeitragsreduktionFehler, match="vor der Reduktion"):
        rv.bjb(12 * (JAHR - 1))


def test_stornoabzug_gilt_vertragsweit_auf_der_neuen_gesamtsumme():
    """Unabhaengige Nachrechnung der Klammer min(max(...)) am Monatswert."""
    rv = ReduzierterVertrag.nach(KERN, JAHR, 0.6)
    monate = 12 * JAHR + 5
    mr = rv.monatsreserve(monate)
    mp = KERN.mp
    erwartet = min(mp.stoab_max,
                   max(mp.stoab_min,
                       mp.stoab_satz * (rv.reduktion.vs_neu - mr.drx_bpfl)))
    assert mr.stoab == pytest.approx(erwartet, rel=1e-12)
    assert mr.rkw == pytest.approx(mr.vx_mrv - mr.stoab, rel=1e-12)


def test_monat_vor_der_reduktion_faellt_hart():
    rv = ReduzierterVertrag.nach(KERN, JAHR, 0.6)
    with pytest.raises(BeitragsreduktionFehler, match="vor der Reduktion"):
        rv.monatsreserve(12 * JAHR - 1)


# --------------------------------------------------------------------------- #
# Herabsetzung geschichteter Vertraege (Tarifplan KLV 12, anteilig)
# --------------------------------------------------------------------------- #


def _geschichtet(jahre=(4, 8), vs=15_000.0):
    """Grundvertrag plus dynamische Erhoehungsscheiben."""
    from rechner_pipeline.kern.rechenkern import erhoehungs_scheibe

    return [
        (j, Rechenkern(erhoehungs_scheibe(KLV_DEFAULT, j, vs))) for j in jahre
    ]


def test_anteilig_trifft_den_zielbeitrag_ueber_alle_schichten():
    """Der Grund, warum anteilig ohne neue Konvention auskommt.

    Der Jahresbeitrag jeder Schicht ist proportional zu ihrer Summe.
    Derselbe Faktor je Schicht ergibt deshalb in der Summe genau den
    Zielbeitrag — das muss nicht zugesagt werden, das folgt.
    """
    from rechner_pipeline.kern.beitragsreduktion import reduziere_geschichtet

    grund = Rechenkern(KLV_DEFAULT)
    scheiben = _geschichtet()
    f = 0.6
    teile = reduziere_geschichtet(grund, scheiben, 10, f)

    alt = sum(r.bjb_alt for _, r in teile)
    neu = sum(r.bjb_neu for _, r in teile)
    assert alt > 0
    assert neu == pytest.approx(f * alt, rel=1e-12)
    assert len(teile) == 3, "Grundscheibe plus zwei Erhoehungen"
    assert [j for j, _ in teile] == [0, 4, 8]


@pytest.mark.parametrize("verfahren", [PROSPEKTIV, MIT_ABZUG])
def test_ohne_scheiben_ist_die_verallgemeinerung_der_sonderfall(verfahren):
    """Die geschichtete Rechnung MUSS den ungeteilten Fall exakt treffen.

    Sonst waere sie ein zweites Verfahren neben dem zugesagten, nicht
    seine Verallgemeinerung — und der Tarifplan saegte an seiner eigenen
    Zusage.
    """
    from rechner_pipeline.kern.beitragsreduktion import reduziere_geschichtet

    grund = Rechenkern(KLV_DEFAULT)
    einzeln = reduziere(grund, 10, 0.6, verfahren=verfahren)
    [(erh_jahr, geschichtet)] = reduziere_geschichtet(
        grund, [], 10, 0.6, verfahren=verfahren)

    assert erh_jahr == 0
    assert geschichtet == einzeln


def test_der_stornoabschlag_wird_nicht_je_schicht_erhoben():
    """Die Grenzen gelten je VERTRAG — sonst zahlt der Kunde sie dreifach.

    Der Tarifplan setzt Unter- und Obergrenze des Stornoabschlags je
    Vertrag (Abschnitt 6). Je Schicht gebildet griffe die Untergrenze
    einmal pro Schicht, und ein Vertrag mit zwei Erhoehungen verlore beim
    Herabsetzen mehr als der zugesagte Abschlag. Dieser Test haelt den
    Unterschied fest und zeigt, dass er nicht klein ist.
    """
    from rechner_pipeline.kern.beitragsreduktion import (
        reduziere_geschichtet,
        vertrags_monatsreserve_reduziert,
    )
    from rechner_pipeline.kern.rechenkern import vertrags_monatsreserve

    grund = Rechenkern(KLV_DEFAULT)
    scheiben = _geschichtet()
    jahr, f = 10, 0.6

    gesamt = vertrags_monatsreserve(grund, scheiben, 12 * jahr)
    teile = reduziere_geschichtet(grund, scheiben, jahr, f,
                                  verfahren=MIT_ABZUG)

    # Der insgesamt einbehaltene Abzug ist der VERTRAGSWEITE, anteilig
    # auf den freiwerdenden Teil: nicht die Summe je Schicht gebildeter.
    verlustfrei = reduziere_geschichtet(grund, scheiben, jahr, f,
                                        verfahren=PROSPEKTIV)
    einbehalten = sum(a.dk_nach for _, a in verlustfrei) - sum(
        b.dk_nach for _, b in teile)
    assert einbehalten == pytest.approx(gesamt.stoab * (1.0 - f), rel=1e-9)

    # Die falsche Rechnung zur Kontrolle: je Schicht ein eigener Abschlag.
    je_schicht = sum(
        k.verlaufszeile(jahr - j).stoab for j, k in [(0, grund)] + scheiben)
    assert je_schicht > gesamt.stoab, (
        "ohne den Kontrolltest sagt der Test oben nichts — die beiden "
        "Rechnungen muessen wirklich auseinanderliegen")


@pytest.mark.parametrize("verfahren", [PROSPEKTIV, MIT_ABZUG])
def test_voller_beitrag_laesst_den_geschichteten_vertrag_unveraendert(verfahren):
    """f = 1 ist keine Reduktion — auch mit Schichten nicht."""
    from rechner_pipeline.kern.beitragsreduktion import reduziere_geschichtet

    grund = Rechenkern(KLV_DEFAULT)
    scheiben = _geschichtet()
    for _, r in reduziere_geschichtet(grund, scheiben, 10, 1.0,
                                      verfahren=verfahren):
        assert r.vs_neu == pytest.approx(r.vs_alt, rel=1e-12)
        assert r.bjb_neu == pytest.approx(r.bjb_alt, rel=1e-12)
        assert r.dk_nach == pytest.approx(r.dk_vor, rel=1e-12)


def test_eine_noch_nicht_existierende_schicht_ist_ein_fehler():
    """Vor ihrem Erhoehungsjahr gibt es die Scheibe nicht.

    Dieselbe Wache wie in vertrags_monatsreserve: Eine Reduktion im
    Vertragsjahr 3 kann eine Scheibe aus Jahr 8 nicht herabsetzen.
    """
    from rechner_pipeline.kern.beitragsreduktion import reduziere_geschichtet

    grund = Rechenkern(KLV_DEFAULT)
    with pytest.raises(BeitragsreduktionFehler) as exc:
        reduziere_geschichtet(grund, _geschichtet(jahre=(8,)), 3, 0.6)
    assert "existiert im Vertragsjahr 3 noch nicht" in str(exc.value)


def test_die_folgebewertung_bildet_den_abschlag_einmal():
    """Vertragsweit auf der NEUEN Gesamtsumme.

    Nach der Herabsetzung ist die Bezugsgroesse des Abschlags die Summe
    der neuen Schichtsummen — fortgefuehrter plus umgewandelter Teil. Die
    alte waere die Summe eines Vertrags, den es nicht mehr gibt.
    """
    from rechner_pipeline.kern.beitragsreduktion import (
        ReduzierterVertrag,
        reduziere_geschichtet,
        vertrags_monatsreserve_reduziert,
    )

    grund = Rechenkern(KLV_DEFAULT)
    scheiben = _geschichtet()
    jahr = 10
    teile = reduziere_geschichtet(grund, scheiben, jahr, 0.6)
    kerne = dict([(0, grund)] + scheiben)
    vertraege = [
        (j, ReduzierterVertrag(kern=kerne[j], reduktion=r)) for j, r in teile
    ]

    monate = 12 * (jahr + 3)
    ges = vertrags_monatsreserve_reduziert(vertraege, monate)

    # Reserven summieren sich ueber die Schichten ...
    einzeln = sum(
        v.monatsreserve(monate - 12 * j).drx_bpfl for j, v in vertraege)
    assert ges.drx_bpfl == pytest.approx(einzeln, rel=1e-12)

    # ... der Abschlag nicht: er ist einmal auf den Gesamtwerten gebildet.
    je_schicht = sum(
        v.monatsreserve(monate - 12 * j).stoab for j, v in vertraege)
    assert 0.0 < ges.stoab < je_schicht
    vs_neu = sum(r.vs_neu for _, r in teile)
    erwartet = min(KLV_DEFAULT.stoab_max,
                   max(KLV_DEFAULT.stoab_min,
                       KLV_DEFAULT.stoab_satz * (vs_neu - ges.drx_bpfl)))
    assert ges.stoab == pytest.approx(erwartet, rel=1e-12)


@pytest.mark.parametrize("jahr,anteil,was", [
    (KLV_DEFAULT.t, 0.6, "nach Beitragsende"),
    (10, 5.0, "Anteil ueber 1"),
    (10, -1.0, "negativer Anteil"),
    (999, 0.6, "Jahr ausserhalb der Laufzeit"),
])
def test_beide_wege_weisen_dieselben_eingaben_ab(jahr, anteil, was):
    """Eine Wache, die nur an einem von zwei Eingaengen steht, ist keine.

    Die Eingangspruefungen standen zuerst nur im ungeteilten Weg. Der
    geschichtete lief daran vorbei und nahm klaglos einen Anteil von -1
    (negative Versicherungssummen), einen Anteil von 5 (der Vertrag
    verdreifacht sich) und ein Vertragsjahr nach dem Beitragsende. Keine
    Ausnahme, kein Befund — nur falsche Zahlen.

    Dieser Test stellt die beiden Wege gegeneinander: Was der eine
    ablehnt, muss der andere auch ablehnen.
    """
    from rechner_pipeline.kern.beitragsreduktion import reduziere_geschichtet

    grund = Rechenkern(KLV_DEFAULT)
    with pytest.raises(BeitragsreduktionFehler):
        reduziere(grund, jahr, anteil)
    with pytest.raises(BeitragsreduktionFehler):
        reduziere_geschichtet(grund, _geschichtet(jahre=(4,)), jahr, anteil)


class TestTeilkuendigung:
    """Drittes Verfahren (A-M3-Befund des zweiten Baldrian-Laufs):
    Kuendigung des (1-f)-Anteils der GRUNDVERSICHERUNG mit Auszahlung —
    der Rest laeuft zustandslos mit f x S weiter, dDK = -(1-f) x kVx.
    """

    def test_zustandslos_und_summen_homogen(self):
        import dataclasses as dc

        from rechner_pipeline.kern.beitragsreduktion import (
            TEILKUENDIGUNG,
            reduziere,
        )

        kern = Rechenkern(KLV_DEFAULT)
        r = reduziere(kern, 10, 0.6, verfahren=TEILKUENDIGUNG)
        zeile = kern.verlaufszeile(10)
        assert r.dk_vor == zeile.vx_mrv
        # Summen-Homogenitaet des Kerns: der gerechnete neue Vertrag
        # trifft die Formel f x dk_vor — unabhaengige Kontrolle.
        assert r.dk_nach == pytest.approx(0.6 * zeile.vx_mrv, rel=1e-9)
        assert r.d_dk == pytest.approx(-0.4 * zeile.vx_mrv, rel=1e-9)
        assert r.vs_neu == pytest.approx(0.6 * KLV_DEFAULT.sum_insured)
        neu = Rechenkern(dc.replace(
            KLV_DEFAULT, sum_insured=0.6 * KLV_DEFAULT.sum_insured))
        assert r.bjb_neu == pytest.approx(
            neu.gross_annual_premium(), rel=1e-12)
        assert r.als_beleg()["verfahren"] == "teilkuendigung"

    def test_im_beitragsfreien_nachlauf_definiert(self):
        """Ziffer 6 kuendigt einen SUMMEN-Anteil mit Auszahlung — die
        Beitragsende-Wache der beitragssenkenden Verfahren gilt hier
        nicht (Review-Befund B4, Kern 3.4.0): im Nachlauf t <= jahr < n
        ist die Teilkuendigung aktuariell definiert, ihre Grenze ist
        der Ablauf."""
        from rechner_pipeline.kern.beitragsreduktion import (
            TEILKUENDIGUNG,
            reduziere,
        )

        kern = Rechenkern(KLV_DEFAULT)
        assert KLV_DEFAULT.t < 25 < KLV_DEFAULT.n
        r = reduziere(kern, 25, 0.6, verfahren=TEILKUENDIGUNG)
        zeile = kern.verlaufszeile(25)
        assert r.dk_vor == zeile.vx_mrv
        assert r.dk_nach == pytest.approx(0.6 * zeile.vx_mrv, rel=1e-9)
        assert r.d_dk == pytest.approx(-0.4 * zeile.vx_mrv, rel=1e-9)

        with pytest.raises(BeitragsreduktionFehler, match="laeuft bei n="):
            reduziere(kern, KLV_DEFAULT.n, 0.6, verfahren=TEILKUENDIGUNG)
        # Die beitragssenkenden Verfahren behalten ihre Wache.
        with pytest.raises(BeitragsreduktionFehler,
                           match="Beitragszahlungsdauer"):
            reduziere(kern, 25, 0.6)

    def test_wachen_fail_fast(self):
        from rechner_pipeline.kern.beitragsreduktion import (
            TEILKUENDIGUNG,
            ReduzierterVertrag,
            reduziere,
            reduziere_geschichtet,
        )

        kern = Rechenkern(KLV_DEFAULT)
        with pytest.raises(BeitragsreduktionFehler, match="VOLLkuendigung"):
            reduziere(kern, 10, 0.0, verfahren=TEILKUENDIGUNG)
        with pytest.raises(BeitragsreduktionFehler, match="ZUSTANDSLOSE"):
            ReduzierterVertrag.nach(kern, 10, 0.6,
                                    verfahren=TEILKUENDIGUNG)
        with pytest.raises(BeitragsreduktionFehler,
                           match="NUR die Grundversicherung"):
            reduziere_geschichtet(kern, _geschichtet(jahre=(4,)), 10, 0.6,
                                  verfahren=TEILKUENDIGUNG)
