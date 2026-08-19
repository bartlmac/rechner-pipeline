"""Monatsreserve: unterjährig interpolierte Reserven des Zielkerns.

Bilanz-Stichtage fallen praktisch nie auf Vertragsjahrestage — die
Bilanzierungskonvention mischt die Betragsgrößen der umschließenden
Jahrestage linear nach Monaten. Geprüft werden die Vertragsidentitäten
dieser Konvention: Jahrestags-Identität (u=0 ist bit-gleich zur
Verlaufszeile), Linearität, Schranken durch die Endpunkte, die
StoAb/RKW-Neurechnung auf interpolierter Basis und die fail-fast-Grenzen
(vor Beginn, nach Ablauf).

Zum Stornoabschlag gehört eine Zonen-Unterscheidung, ohne die eine
Zusicherung nichts prüft: der Rohwert ``satz*(VS - DR)`` liegt für
``KLV_DEFAULT`` in den Vertragsjahren 0..19 über der Obergrenze (1022.33
bis 181.81) und wird dort IMMER auf ``stoab_max`` gekappt — eine
Zusicherung in dieser Zone hält auch dann, wenn die Interpolation der DR
kaputt ist. DR-abhängig wird der Abschlag erst in den Jahren 20..24
(127.17, 116.31, 105.23, 93.88, 82.22), ab Jahr 25 greift die flexible
Phase mit 0. Die Tests sind deshalb nach Zone benannt: ``…_in_der_kappung``
prüft die Kappung, ``…_folgt_der_interpolierten_dr`` prüft die Rechnung.
Die Grenzwerte selbst (exakt auf ``stoab_min``/``stoab_max``) stehen in
``test_stoab_grenzwerte_exakt_getroffen``.

Knoten: klv
"""

from __future__ import annotations

import dataclasses

import pytest

from rechner_pipeline.kern import (
    KLV_DEFAULT,
    Rechenkern,
    erhoehungs_scheibe,
    vertrags_monatsreserve,
)


@pytest.fixture(scope="module")
def kern() -> Rechenkern:
    return Rechenkern(KLV_DEFAULT)


def test_jahrestag_ist_bitgleich_zur_verlaufszeile(kern: Rechenkern) -> None:
    for a in (0, 1, 7, 19, 25, KLV_DEFAULT.n):
        zeile = kern.verlaufszeile(a)
        m = kern.monatsreserve(12 * a)
        assert m.jahr == a and m.monatsanteil == 0.0
        assert m.drx_bpfl == zeile.drx_bpfl
        assert m.vx_mrv == zeile.vx_mrv
        assert m.stoab == zeile.stoab
        assert m.rkw == zeile.rkw


def test_linearitaet_und_schranken(kern: Rechenkern) -> None:
    for a in (2, 10, 20):
        za, zb = kern.verlaufszeile(a), kern.verlaufszeile(a + 1)
        for rest in range(1, 12):
            u = rest / 12.0
            m = kern.monatsreserve(12 * a + rest)
            assert m.drx_bpfl == pytest.approx(
                (1 - u) * za.drx_bpfl + u * zb.drx_bpfl, rel=1e-12)
            assert m.vx_mrv == pytest.approx(
                (1 - u) * za.vx_mrv + u * zb.vx_mrv, rel=1e-12)
            lo, hi = sorted((za.vx_mrv, zb.vx_mrv))
            assert lo <= m.vx_mrv <= hi


def test_halbjahr_ist_mittelwert(kern: Rechenkern) -> None:
    a = 10
    za, zb = kern.verlaufszeile(a), kern.verlaufszeile(a + 1)
    m = kern.monatsreserve(12 * a + 6)
    assert m.monatsanteil == 0.5
    assert m.drx_bpfl == pytest.approx((za.drx_bpfl + zb.drx_bpfl) / 2)


def test_stoab_in_der_kappung_und_rkw(kern: Rechenkern) -> None:
    """Vertragsjahr 10: der Rohwert liegt über ``stoab_max`` — geprüft wird
    die Kappung und die RKW-Definition, NICHT die Interpolation.

    Der Punkt bleibt bewusst stehen (er verankert die Kappungsregel und
    den RKW), sagt aber nichts über die DR-Abhängigkeit: bei ``a=10`` ist
    ``satz*(VS - DR) = 611.07``, also das Vierfache der Obergrenze. Die
    DR-abhängige Zone prüft
    ``test_stoab_folgt_der_interpolierten_dr_in_der_sensitiven_zone``.
    """
    mp = KLV_DEFAULT
    m = kern.monatsreserve(12 * 10 + 5)
    roh = mp.stoab_satz * (mp.sum_insured - m.drx_bpfl)
    assert roh > mp.stoab_max        # Zonen-Beleg: hier kappt es immer
    erwartet_stoab = min(mp.stoab_max, max(mp.stoab_min, roh))
    assert erwartet_stoab == mp.stoab_max
    assert m.stoab == pytest.approx(erwartet_stoab)
    assert m.rkw == pytest.approx(max(0.0, m.vx_mrv - m.stoab))


def test_stoab_folgt_der_interpolierten_dr_in_der_sensitiven_zone(
    kern: Rechenkern,
) -> None:
    """Vertragsjahre 20..24: hier hängt der Abschlag wirklich am Deckungskapital.

    Eigene Rechnung für ``KLV_DEFAULT`` (satz 1 %, VS 100 000, Grenzen
    50/150): der Rohwert ``satz*(VS - DR)`` unterschreitet die Obergrenze
    erstmals im Vertragsjahr 20 (127.17) und die flexible Phase beginnt
    mit Jahr 25 — dazwischen liegt das einzige Fenster, in dem eine
    Zusicherung die Interpolation prüfen kann. Gegenprobe im selben Test:
    der Abschlag aus der DR des JAHRESTAGS wäre ein anderer Wert.
    """
    mp = KLV_DEFAULT
    for a in range(20, 25):
        za, zb = kern.verlaufszeile(a), kern.verlaufszeile(a + 1)
        roh_jahrestag = mp.stoab_satz * (mp.sum_insured - za.drx_bpfl)
        for rest in (1, 5, 11):
            u = rest / 12.0
            dr = (1.0 - u) * za.drx_bpfl + u * zb.drx_bpfl
            roh = mp.stoab_satz * (mp.sum_insured - dr)
            # Zonen-Beleg: ungekappt, also DR-abhängig.
            assert mp.stoab_min < roh < mp.stoab_max
            m = kern.monatsreserve(12 * a + rest)
            assert m.stoab == pytest.approx(roh)
            # ... und zwar auf der interpolierten DR: der Jahrestagswert
            # liegt messbar daneben (mindestens 0.5 Einheiten).
            assert abs(roh - roh_jahrestag) > 0.5
            assert m.rkw == pytest.approx(m.vx_mrv - m.stoab)


def test_stoab_grenzwerte_exakt_getroffen(kern: Rechenkern) -> None:
    """Grenzwerttest: Rohwert exakt auf ``stoab_min`` bzw. ``stoab_max``.

    Der Stichtag bleibt derselbe (Vertragsjahr 22, fünfter Monat, Rohwert
    ~100.50); verschoben werden die GRENZEN des Tarifwerks auf genau
    diesen Rohwert. Damit ist jede der drei Lagen einmal geprüft: exakt
    auf der Kante (beide Zweige liefern denselben Wert) und je einen Cent
    daneben, wo die Kappung übernehmen muss.
    """
    mp = KLV_DEFAULT
    monate = 12 * 22 + 5
    za, zb = kern.verlaufszeile(22), kern.verlaufszeile(23)
    u = 5 / 12.0
    dr = (1.0 - u) * za.drx_bpfl + u * zb.drx_bpfl
    roh = mp.stoab_satz * (mp.sum_insured - dr)
    assert mp.stoab_min < roh < mp.stoab_max

    def stoab_mit(**grenzen: float) -> float:
        return Rechenkern(dataclasses.replace(mp, **grenzen)).monatsreserve(
            monate).stoab

    # Obergrenze: exakt getroffen, knapp darunter (kappt), knapp darüber.
    assert stoab_mit(stoab_max=roh) == pytest.approx(roh)
    assert stoab_mit(stoab_max=roh - 0.01) == pytest.approx(roh - 0.01)
    assert stoab_mit(stoab_max=roh + 0.01) == pytest.approx(roh)
    # Untergrenze: exakt getroffen, knapp darüber (hebt an), knapp darunter.
    assert stoab_mit(stoab_min=roh) == pytest.approx(roh)
    assert stoab_mit(stoab_min=roh + 0.01) == pytest.approx(roh + 0.01)
    assert stoab_mit(stoab_min=roh - 0.01) == pytest.approx(roh)


def test_flexible_phase_ohne_stoab() -> None:
    # x=45, n=30, min_alter_flex=60, min_rlz_flex=5: ab a=25 flexible Phase.
    kern = Rechenkern(KLV_DEFAULT)
    m = kern.monatsreserve(12 * 26 + 3)
    assert m.stoab == 0.0
    assert m.rkw == pytest.approx(m.vx_mrv)


def test_grenzen_fail_fast(kern: Rechenkern) -> None:
    with pytest.raises(ValueError, match="negativ"):
        kern.monatsreserve(-1)
    with pytest.raises(ValueError, match="Ablauf"):
        kern.monatsreserve(12 * KLV_DEFAULT.n + 1)
    # Genau am Ablauf-Jahrestag ist die Reserve definiert (Ablaufwert):
    assert kern.monatsreserve(12 * KLV_DEFAULT.n).monatsanteil == 0.0


def test_beitragsfrei_jahrestag_und_linearitaet(kern: Rechenkern) -> None:
    a0 = 8
    assert kern.monatsreserve_beitragsfrei(a0, 12 * 12) == pytest.approx(
        kern.reserve_beitragsfrei(a0, 12))
    satz_a = kern.verlaufszeile(12).vx_bfr
    satz_b = kern.verlaufszeile(13).vx_bfr
    u = 4 / 12.0
    erwartet = kern.beitragsfreie_summe(a0) * ((1 - u) * satz_a + u * satz_b)
    assert kern.monatsreserve_beitragsfrei(a0, 12 * 12 + 4) == pytest.approx(
        erwartet)


def test_beitragsfrei_grenzen(kern: Rechenkern) -> None:
    with pytest.raises(ValueError, match="vor der Beitragsfreistellung"):
        kern.monatsreserve_beitragsfrei(8, 12 * 8 - 1)
    with pytest.raises(ValueError, match="Ablauf"):
        kern.monatsreserve_beitragsfrei(8, 12 * KLV_DEFAULT.n + 1)


def test_erhoehungs_scheibe_traegt_kein_gamma1() -> None:
    scheibe = erhoehungs_scheibe(KLV_DEFAULT, 8, 5000.0)
    assert (scheibe.x, scheibe.n, scheibe.t) == (53, 22, 12)
    assert scheibe.sum_insured == 5000.0 and scheibe.gamma1 == 0.0
    # gamma1-Bezugsgroesse GrundVS: die Scheibe ist billiger als ein
    # gleicher Modellpunkt mit eigenem gamma1.
    mit_gamma1 = dataclasses.replace(scheibe, gamma1=KLV_DEFAULT.gamma1)
    assert Rechenkern(scheibe).gross_annual_premium() < \
        Rechenkern(mit_gamma1).gross_annual_premium()
    with pytest.raises(ValueError, match="beitragspflichtigen"):
        erhoehungs_scheibe(KLV_DEFAULT, KLV_DEFAULT.t, 5000.0)
    with pytest.raises(ValueError, match="beitragspflichtigen"):
        erhoehungs_scheibe(KLV_DEFAULT, 0, 5000.0)


def test_vertragsreserve_ohne_scheiben_identisch(kern: Rechenkern) -> None:
    for monate in (0, 12 * 10 + 7, 12 * KLV_DEFAULT.n):
        einzeln = kern.monatsreserve(monate)
        vertrag = vertrags_monatsreserve(kern, [], monate)
        assert vertrag == einzeln


def test_vertragsreserve_summiert_scheiben_stoab_in_der_kappung(
    kern: Rechenkern,
) -> None:
    """Summation der Scheiben; der StoAb liegt hier in der Kappung.

    Bei ``a=12`` ist der Rohwert mit Gesamt-VS 647.69 und mit Grund-VS
    447.69 — beide über ``stoab_max``. Die Zusicherung prüft also die
    Summenbildung und die Kappung, aber NICHT, auf welche VS der
    Abschlag gerechnet wird; das leistet
    ``test_vertragsreserve_stoab_je_vertrag_in_der_sensitiven_zone``.
    """
    a, s_neu = 8, 20000.0
    scheibe = Rechenkern(erhoehungs_scheibe(KLV_DEFAULT, a, s_neu))
    monate = 12 * 12 + 5
    vertrag = vertrags_monatsreserve(kern, [(a, scheibe)], monate)
    r_grund = kern.monatsreserve(monate)
    r_scheibe = scheibe.monatsreserve(monate - 12 * a)
    assert vertrag.vx_mrv == pytest.approx(r_grund.vx_mrv + r_scheibe.vx_mrv)
    assert vertrag.drx_bpfl == pytest.approx(
        r_grund.drx_bpfl + r_scheibe.drx_bpfl)
    # StoAb auf die Gesamtwerte — in dieser Zone gekappt (Zonen-Beleg):
    mp = KLV_DEFAULT
    roh = mp.stoab_satz * (mp.sum_insured + s_neu - vertrag.drx_bpfl)
    assert roh > mp.stoab_max
    erwartet = min(mp.stoab_max, max(mp.stoab_min, roh))
    assert vertrag.stoab == pytest.approx(erwartet)
    assert vertrag.rkw == pytest.approx(
        max(0.0, vertrag.vx_mrv - vertrag.stoab))


def test_vertragsreserve_stoab_je_vertrag_in_der_sensitiven_zone(
    kern: Rechenkern,
) -> None:
    """Der Abschlag wird einmal je VERTRAG auf die Gesamt-VS gerechnet.

    Stichtag im DR-sensitiven Fenster (Vertragsjahr 22, fünfter Monat)
    und eine kleine Erhöhungsscheibe (5 000 aus Jahr 8): eigene Rechnung
    ergibt 105.53 auf die Gesamt-VS von 105 000 und 55.53 auf die
    Grund-VS allein — beide innerhalb der Grenzen 50/150, also erstmals
    unterscheidbar. Die Summe der Scheiben-Einzelabschläge (150.50) ist
    ein dritter, ebenfalls verschiedener Wert.
    """
    mp = KLV_DEFAULT
    a, s_neu, monate = 8, 5000.0, 12 * 22 + 5
    scheibe = Rechenkern(erhoehungs_scheibe(mp, a, s_neu))
    vertrag = vertrags_monatsreserve(kern, [(a, scheibe)], monate)

    roh_vertrag = mp.stoab_satz * (mp.sum_insured + s_neu - vertrag.drx_bpfl)
    roh_nur_grund = mp.stoab_satz * (mp.sum_insured - vertrag.drx_bpfl)
    # Zonen-Beleg: beide Lesarten ungekappt, also unterscheidbar.
    assert mp.stoab_min < roh_vertrag < mp.stoab_max
    assert mp.stoab_min < roh_nur_grund < mp.stoab_max
    assert abs(roh_vertrag - roh_nur_grund) > 1.0

    assert vertrag.stoab == pytest.approx(roh_vertrag)
    assert vertrag.stoab != pytest.approx(roh_nur_grund, rel=1e-6)
    # ... und nicht je Scheibe summiert:
    je_scheibe = (kern.monatsreserve(monate).stoab
                  + scheibe.monatsreserve(monate - 12 * a).stoab)
    assert vertrag.stoab != pytest.approx(je_scheibe, rel=1e-6)
    assert vertrag.rkw == pytest.approx(vertrag.vx_mrv - vertrag.stoab)


def test_vertragsreserve_scheibe_vor_entstehung(kern: Rechenkern) -> None:
    scheibe = Rechenkern(erhoehungs_scheibe(KLV_DEFAULT, 10, 5000.0))
    with pytest.raises(ValueError, match="existiert"):
        vertrags_monatsreserve(kern, [(10, scheibe)], 12 * 10 - 1)


def test_kurzer_vertrag_ohne_zillmer_luecke() -> None:
    """Auch ein Vertrag ohne Abschlusskosten interpoliert konsistent."""
    mp = dataclasses.replace(KLV_DEFAULT, alpha=0.0, n=12, t=7, x=37)
    kern = Rechenkern(mp)
    m = kern.monatsreserve(12 * 9 + 11)
    za, zb = kern.verlaufszeile(9), kern.verlaufszeile(10)
    # Ohne Zillmer-Forderung fallen MRV und DR zusammen — auch monatlich:
    assert za.vx_mrv == pytest.approx(za.drx_bpfl)
    assert m.vx_mrv == pytest.approx(m.drx_bpfl)
    assert m.vx_mrv == pytest.approx((1 / 12) * za.vx_mrv + (11 / 12) * zb.vx_mrv)
