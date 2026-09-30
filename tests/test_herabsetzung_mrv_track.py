"""Die Herabsetzung wandelt auf dem Rueckkaufswert-Track um — Entscheid F1 (b), Floor RC01.

Drei Aussagen, jede mit ihrem Befund:

1. **Umwandlung auf V^MRV.** Die Herabsetzung (prospektiv und mit Abzug)
   wandelt den freiwerdenden Beitragsanteil auf dem Rueckkaufswert-Track
   um, GENAU wie die Beitragsfreistellung (PEX) — nicht auf der
   Deckungsrueckstellung V^bpfl. Innerhalb der Zillmerdauer liegen beide
   Tracks um den Abschlusskostenrest auseinander; auf V^bpfl lag die
   Herabsetzung mit f -> 0 unter der Beitragsfreistellung (Messung der
   Runde C, KLV a0 = 1: PEX 4.898,47 gegen RED f = 0 2.356,97), und
   klv.md 7.1 widersprach sich. Mit V^MRV ist RED bei f = 0 die
   vollstaendige Beitragsfreistellung und der Pfad danach derselbe.
2. **Floor.** Der umgewandelte Teil ist nie negativ (wie RKW = max(0, ...)):
   keine Summe und keine Leistung wird negativ, auch bei nicht positiver
   Rueckstellung (RC01: x=20, n=t=40, zins 1,25 %, f=0,001, a0=1). Zwei
   Zahlen gehoeren zu zwei Modellpunkten und duerfen nicht vermischt
   werden: -239,41 lieferte der Modellpunkt des Angreifers (Pruefrunde T27,
   Runde C); auf dem Testpunkt RC01 dieses Moduls (KLV_DEFAULT) war es
   -305,02 (alt, vor F1 (b)).
3. **Nachmessung.** Nach F1 (b) hat der Rueckkaufs-Track im Vertragsjahr 1
   keine negativen Werte mehr; der Floor bleibt als Untergrenze der Regel
   und wird an einer Eingabe geprueft, die ihn wirklich erreicht.

Knoten: klv
"""

from __future__ import annotations

import dataclasses
import itertools

import pytest

from rechner_pipeline.kern import KLV_DEFAULT, Rechenkern
from rechner_pipeline.kern.beitragsreduktion import (
    MIT_ABZUG,
    PROSPEKTIV,
    ReduzierterVertrag,
    reduziere,
)

KERN = Rechenkern(KLV_DEFAULT)
#: Die Jahre INNERHALB der Zillmerdauer, in denen V^MRV und V^bpfl
#: auseinanderliegen — nur dort kann die Regel falsch sein.
ZILLMER_JAHRE = list(range(1, KLV_DEFAULT.zillmer_dauer))


def test_die_kontrollwelt_hat_einen_abschlusskostenrest():
    """Positivkontrolle: ohne Rest zwischen V^MRV und V^bpfl waeren alle
    Tests dieses Moduls blind (beide Regeln lieferten dasselbe)."""
    for a0 in ZILLMER_JAHRE:
        z = KERN.verlaufszeile(a0)
        assert z.vx_mrv - z.drx_bpfl > 100.0, a0


# --------------------------------------------------------------------------- #
# 1. F1 (b): f -> 0 ist die Beitragsfreistellung
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("a0", ZILLMER_JAHRE)
@pytest.mark.parametrize("f", [0.0, 1e-9])
def test_red_an_der_grenze_hat_dieselbe_summe_wie_pex(a0, f):
    """Unabhaengige Kontrolle: die beitragsfreie Summe der Beitragsfreistellung
    im selben Jahr (Rechenkern.beitragsfreie_summe, ein eigener Weg).
    Mutationsprobe: umgewandelt auf drx_bpfl statt vx_mrv -> rot (a0 = 1:
    2.356,97 statt 4.898,47)."""
    r = reduziere(KERN, a0, f, verfahren=PROSPEKTIV)
    pex = KERN.beitragsfreie_summe(a0)
    assert r.vs_neu == pytest.approx(pex, rel=1e-6), (a0, f)


@pytest.mark.parametrize("a0", ZILLMER_JAHRE)
def test_red_mit_f_null_folgt_pex_im_ganzen_pfad(a0):
    """Nicht nur die Summe: Rueckstellung, Todesfall- und Ablaufleistung nach der
    Herabsetzung sind die der Beitragsfreistellung, Jahr fuer Jahr."""
    rv = ReduzierterVertrag.nach(KERN, a0, 0.0, verfahren=PROSPEKTIV)
    pex = KERN.beitragsfreie_summe(a0)
    assert rv.terminale_leistung() == pytest.approx(pex, rel=1e-9)
    for a in range(a0, KLV_DEFAULT.n):
        soll = KERN.monatsreserve_beitragsfrei(a0, 12 * a)
        ist = rv.monatsreserve(12 * a).vx_mrv
        assert ist == pytest.approx(soll, rel=1e-9, abs=1e-6), (a0, a)
        assert rv.reserve_beitragsfrei(a0, 12 * a) == pytest.approx(soll, rel=1e-9, abs=1e-6)


@pytest.mark.parametrize("a0", ZILLMER_JAHRE)
@pytest.mark.parametrize("f", [0.25, 0.6])
def test_umgewandelt_wird_der_rueckkaufs_track_nicht_die_rueckstellung(a0, f):
    """Handrechnung aus den Verlaufszeilen: S_neu = f x S + (1-f) x V^MRV / V^bfr.
    Zwischen den Grenzen f = 0 und f = 1 gilt dieselbe Regel."""
    z = KERN.verlaufszeile(a0)
    soll = f * KLV_DEFAULT.sum_insured + (1.0 - f) * z.vx_mrv / z.vx_bfr
    assert reduziere(KERN, a0, f, verfahren=PROSPEKTIV).vs_neu == pytest.approx(soll, rel=1e-12)


@pytest.mark.parametrize("a0", ZILLMER_JAHRE)
@pytest.mark.parametrize("f", [0.0, 0.25])
def test_mit_abzug_wandelt_den_rueckkaufswert_um(a0, f):
    """Mit Abzug ist der umgewandelte Teil (1-f) x RKW, RKW = max(0, V^MRV -
    StoAb) — die Groesse, die die Quelle bei der Teilkuendigung auszahlt.
    Bei f = 0 ist die prospektive Herabsetzung die Beitragsfreistellung
    (gleiche Summe, gleicher Pfad); die mit Abzug liegt um den Stornoabzug
    darunter (Test unten)."""
    z = KERN.verlaufszeile(a0)
    assert z.rkw > 0.0
    soll = f * KLV_DEFAULT.sum_insured + (1.0 - f) * z.rkw / z.vx_bfr
    assert reduziere(KERN, a0, f, verfahren=MIT_ABZUG).vs_neu == pytest.approx(soll, rel=1e-12)


@pytest.mark.parametrize("a0", ZILLMER_JAHRE)
@pytest.mark.parametrize("f", [0.0, 0.25])
def test_mit_abzug_liegt_um_den_stornoabzug_unter_dem_prospektiven(a0, f):
    """Die Differenz der beiden Verfahren ist genau der anteilige Stornoabzug,
    umgewandelt: vs_prospektiv - vs_mit_abzug = (1-f) x StoAb / V^bfr. Bei
    f = 0 ist das die Luecke zwischen Beitragsfreistellung (= prospektive
    Herabsetzung) und der mit Abzug — NICHT null: mit Abzug ist bei f = 0
    gerade nicht die Beitragsfreistellung. Unabhaengig aus den Verlaufszeilen
    nachgerechnet (nicht ueber reduziere).
    Positivkontrolle: der Abzug ist im Gitter positiv und kleiner als der
    Rueckkaufs-Track, sonst pruefte die Differenz nichts.
    Mutationsproben: den Abzug in _abzugsfaktor auf 0 setzen -> rot;
    f = 0 mit Abzug wie Beitragsfreistellung (Faktor 1) fuehren -> rot."""
    z = KERN.verlaufszeile(a0)
    assert 0.0 < z.stoab < z.vx_mrv, a0
    prosp = reduziere(KERN, a0, f, verfahren=PROSPEKTIV)
    mit = reduziere(KERN, a0, f, verfahren=MIT_ABZUG)
    luecke = (1.0 - f) * z.stoab / z.vx_bfr
    assert prosp.vs_neu - mit.vs_neu == pytest.approx(luecke, rel=1e-9)
    assert luecke > 0.0
    if f == 0.0:
        assert prosp.vs_neu == pytest.approx(KERN.beitragsfreie_summe(a0), rel=1e-6)
        assert mit.vs_neu == pytest.approx(KERN.beitragsfreie_summe(a0) - z.stoab / z.vx_bfr, rel=1e-6)


@pytest.mark.parametrize("a0", ZILLMER_JAHRE)
def test_das_deckungskapital_nach_dem_vorfall_ist_das_des_pfades(a0):
    """dk_nach der Reduktion und die Rueckstellung des Folgepfades im
    Reduktionsjahr sind DIESELBE Groesse (f x DR + umgewandelter Teil):
    sonst rechnete die Reduktion eine Reserve, die die Bewertung nicht hat."""
    f = 0.4
    rv = ReduzierterVertrag.nach(KERN, a0, f, verfahren=PROSPEKTIV)
    assert rv.reduktion.dk_nach == pytest.approx(rv.monatsreserve(12 * a0).drx_bpfl, rel=1e-9)


# --------------------------------------------------------------------------- #
# 2. Floor: nie eine negative Summe, nie eine negative Leistung
# --------------------------------------------------------------------------- #

#: Der Fall der Runde C (RC01) als Testpunkt auf KLV_DEFAULT: Hier war der
#: alte Wert -305,02 (vor F1 (b)). Die -239,41 gehoeren dem Modellpunkt des
#: Angreifers (Pruefrunde T27, Runde C), nicht diesem.
RC01 = dataclasses.replace(KLV_DEFAULT, x=20, n=40, t=40, zins=0.0125)


@pytest.mark.parametrize("verfahren", [PROSPEKTIV, MIT_ABZUG])
@pytest.mark.parametrize("f", [0.001, 0.05, 0.5])
def test_keine_negative_summe_im_fall_der_runde_c(verfahren, f):
    """x=20, n=t=40, zins 1,25 %, a0 = 1: vs_neu war bei f = 0,001 auf V^bpfl
    negativ (-305,02 auf diesem Modellpunkt, alt; -239,41 auf dem des Angreifers).
    Mutationsprobe: den Floor (max(0, ...)) entfernen -> rot, falls die
    Rechnung dort negativ ausfaellt; sonst deckt ihn der Test unten."""
    kern = Rechenkern(RC01)
    rv = ReduzierterVertrag.nach(kern, 1, f, verfahren=verfahren)
    assert rv.reduktion.vs_neu >= f * RC01.sum_insured - 1e-9
    assert rv.terminale_leistung() >= 0.0
    for a in range(1, RC01.n):
        assert rv.monatsreserve(12 * a).vx_mrv >= 0.0
        assert rv.beitragsfreie_summe(a) >= 0.0


@pytest.mark.parametrize("verfahren", [PROSPEKTIV, MIT_ABZUG])
@pytest.mark.parametrize("mrv", [-200.0, 0.0])
def test_der_floor_greift_bei_nicht_positivem_rueckkaufswert(monkeypatch, verfahren, mrv):
    """Der Floor ist eine eigene Regel, nicht Zufall der Zahlen: Wird der
    Rueckkaufs-Track im Reduktionsjahr nicht positiv (hier ein Modellpunkt mit
    kuenstlich vorgegebener Verlaufszeile), bleibt die Summe bei f x S; der
    umgewandelte Teil ist 0, nicht negativ. Der Wert genau null gehoert dazu:
    mit Abzug gibt es dort keinen Anteil zu bilden (Division), und die Regel
    bricht nicht ab.
    Mutationsproben: max(0, ...) im umgewandelten Teil entfernen -> rot;
    die Wache 'mrv <= 0' im Abzugsfaktor entfernen -> rot (mrv = 0)."""
    kern = Rechenkern(RC01)
    echte = kern.verlaufszeile

    def vorgegeben(a):
        return dataclasses.replace(echte(a), vx_mrv=mrv, drx_bpfl=-300.0, stoab=50.0, rkw=0.0)

    monkeypatch.setattr(kern, "verlaufszeile", vorgegeben)
    r = reduziere(kern, 1, 0.3, verfahren=verfahren)
    assert r.vs_neu == pytest.approx(0.3 * RC01.sum_insured, rel=1e-12)
    assert r.dk_nach == pytest.approx(0.3 * (-300.0), rel=1e-12)


def test_der_abzug_ist_hoechstens_der_rueckkaufs_track(monkeypatch):
    """Ist der Stornoabzug groesser als der Rueckkaufs-Track (kleine Summe,
    Mindestabzug), ist RKW = 0 und mit Abzug wird nichts umgewandelt — die
    Summe bleibt f x S, nicht darunter und nicht darueber. Gleichzeitig
    wandelt das prospektive Verfahren den Track voll um (kein Abzug).
    Mutationsprobe: den Abzug nicht auf den Track begrenzen UND den Floor
    entfernen -> rot (jede der beiden Massnahmen allein faengt es ab, der
    Test faellt erst, wenn beide fehlen; deshalb prueft er auch dk_nach)."""
    kern = Rechenkern(RC01)
    echte = kern.verlaufszeile

    def klein(a):
        return dataclasses.replace(echte(a), vx_mrv=20.0, drx_bpfl=-300.0, stoab=50.0, rkw=0.0)

    monkeypatch.setattr(kern, "verlaufszeile", klein)
    f, S = 0.3, RC01.sum_insured
    z = klein(1)
    mit = reduziere(kern, 1, f, verfahren=MIT_ABZUG)
    assert mit.vs_neu == pytest.approx(f * S, rel=1e-12)
    assert mit.dk_nach == pytest.approx(f * z.drx_bpfl, rel=1e-12)
    prosp = reduziere(kern, 1, f, verfahren=PROSPEKTIV)
    assert prosp.vs_neu == pytest.approx(f * S + (1 - f) * 20.0 / z.vx_bfr, rel=1e-12)
    assert prosp.vs_neu > mit.vs_neu


def test_nachmessung_der_negativen_summen_nach_f1b():
    """Ergebnis der Nachmessung, festgehalten. Gitter aus 5 Eintrittsaltern,
    2 Geschlechtern, 4 Laufzeiten, 3 Zinsen, 2 Abschlusskostensaetzen und 2
    Summen, Vertragsjahre 1 bis 7, beide Verfahren, drei Anteile: Auf V^bpfl
    (vor F1 (b)) wurde in 748 von 20.160 Faellen die Summe negativ (bis
    -9.203 EUR); auf V^MRV in keinem, weil der Rueckkaufs-Track im
    Gitter nirgends negativ ist. Der Floor bleibt trotzdem als Eigenschaft
    der Regel (Test oben, an einer Eingabe, die ihn erreicht).
    Faellt dieser Test, ist der Floor kein Sicherheitsnetz mehr, sondern
    wirksam — und die Regel gehoert im Tarifplan benannt.
    Positivkontrolle: das Gitter enthaelt Jahre mit negativer Rueckstellung,
    sonst pruefte es nichts."""
    dr_negativ = 0
    for x, sex, (n, t), zins, alpha, summe in itertools.product(
            (18, 35, 55), ("M", "F"), ((30, 25), (45, 45)), (0.0025, 0.04),
            (0.025, 0.04), (2000.0, 100000.0)):
        mp = dataclasses.replace(KLV_DEFAULT, x=x, sex=sex, n=n, t=t, zins=zins,
                                 alpha=alpha, sum_insured=summe)
        k = Rechenkern(mp)
        for a0 in range(1, 6):
            z = k.verlaufszeile(a0)
            dr_negativ += z.drx_bpfl < 0.0
            assert z.vx_mrv > 0.0, (x, sex, n, t, zins, alpha, summe, a0)
            for verfahren in (PROSPEKTIV, MIT_ABZUG):
                for f in (0.001, 0.05, 0.5):
                    r = reduziere(k, a0, f, verfahren=verfahren)
                    assert r.vs_neu >= f * summe - 1e-9, (x, sex, n, t, zins, a0, verfahren, f)
    assert dr_negativ > 20, dr_negativ


# --------------------------------------------------------------------------- #
# 4. Die Rueckrechnung der Uebernahme folgt derselben Regel
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("verfahren", [PROSPEKTIV, MIT_ABZUG])
@pytest.mark.parametrize("jahr", ZILLMER_JAHRE)
@pytest.mark.parametrize("summe, f", [(100000.0, 0.6), (2000.0, 0.4), (60000.0, 0.75), (10000.0, 0.5)])
def test_die_rueckrechnung_der_absetzung_trifft_die_vorwaertsregel(verfahren, jahr, summe, f):
    """leite_absetzung_ab / leite_ursprungssumme_ab (Migrationszugang) invertieren
    die Vorwaertsregel in geschlossener Form. Wandelt die Herabsetzung auf
    V^MRV um, muss die Umkehrung das auch: Innerhalb der Zillmerdauer lagen
    beide sonst um den Abschlusskostenrest auseinander, und jede
    Alt-Absetzung dort waere an der eigenen Vorwaertsprobe gescheitert
    ("kein Stornoabzugs-Zweig reproduziert die gelieferten Felder").
    Rundreise: vorwaerts rechnen, auf Cent runden (wie die Lieferung),
    zurueckrechnen — Ursprungssumme und Anteil kommen zurueck.
    Mutationsprobe: in der Umkehrung wieder v = vx_bpfl fuer die
    Umwandlung (Flex-, Satz- und Klammerzweig einzeln) -> rot."""
    from rechner_pipeline.bestand.migrationszugang import (
        leite_absetzung_ab,
        leite_ursprungssumme_ab,
    )

    felder = dataclasses.asdict(dataclasses.replace(KLV_DEFAULT, sum_insured=summe))
    r = reduziere(Rechenkern(dataclasses.replace(KLV_DEFAULT, sum_insured=summe)),
                  jahr, f, verfahren=verfahren)
    erl, jb = round(r.vs_neu, 2), round(r.bjb_neu, 2)
    ab = leite_absetzung_ab(felder, jahr=jahr, erlsumme=erl, jbrutto=jb, verfahren=verfahren)
    # Die Lieferung ist centgerundet: die Summe kommt auf Centbruchteile zurueck.
    if verfahren == MIT_ABZUG and summe == 10000.0:
        # Der Satz-Zweig des Stornoabzugs (Grenzen nicht erreicht) ist eigens
        # gebaut — die anderen Summen laufen in die Klammerzweige.
        assert ab.stoab_zweig == "satz"
    assert ab.vs_alt == pytest.approx(summe, abs=0.02)
    assert ab.anteil == pytest.approx(f, rel=1e-6)
    vs = leite_ursprungssumme_ab(felder, jahr=jahr, erlsumme=erl, anteil=f, verfahren=verfahren)
    assert vs == pytest.approx(summe, abs=0.02)
