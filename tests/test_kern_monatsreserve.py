"""Monatsreserve: unterjährig interpolierte Reserven des Zielkerns.

Bilanz-Stichtage fallen praktisch nie auf Vertragsjahrestage — die
Bilanzierungskonvention mischt die Betragsgrößen der umschließenden
Jahrestage linear nach Monaten. Geprüft werden die Vertragsidentitäten
dieser Konvention: Jahrestags-Identität (u=0 ist bit-gleich zur
Verlaufszeile), Linearität, Schranken durch die Endpunkte, die
StoAb/RKW-Neurechnung auf interpolierter Basis und die fail-fast-Grenzen
(vor Beginn, nach Ablauf).

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


def test_stoab_und_rkw_auf_interpolierter_basis(kern: Rechenkern) -> None:
    mp = KLV_DEFAULT
    m = kern.monatsreserve(12 * 10 + 5)
    erwartet_stoab = min(
        mp.stoab_max,
        max(mp.stoab_min, mp.stoab_satz * (mp.sum_insured - m.drx_bpfl)),
    )
    assert m.stoab == pytest.approx(erwartet_stoab)
    assert m.rkw == pytest.approx(max(0.0, m.vx_mrv - m.stoab))


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


def test_vertragsreserve_summiert_scheiben_und_klammert_stoab(
    kern: Rechenkern,
) -> None:
    a, s_neu = 8, 20000.0
    scheibe = Rechenkern(erhoehungs_scheibe(KLV_DEFAULT, a, s_neu))
    monate = 12 * 12 + 5
    vertrag = vertrags_monatsreserve(kern, [(a, scheibe)], monate)
    r_grund = kern.monatsreserve(monate)
    r_scheibe = scheibe.monatsreserve(monate - 12 * a)
    assert vertrag.vx_mrv == pytest.approx(r_grund.vx_mrv + r_scheibe.vx_mrv)
    assert vertrag.drx_bpfl == pytest.approx(
        r_grund.drx_bpfl + r_scheibe.drx_bpfl)
    # StoAb einmal je VERTRAG auf die Gesamtwerte, nicht je Scheibe:
    mp = KLV_DEFAULT
    erwartet = min(mp.stoab_max, max(
        mp.stoab_min,
        mp.stoab_satz * (mp.sum_insured + s_neu - vertrag.drx_bpfl)))
    assert vertrag.stoab == pytest.approx(erwartet)
    assert vertrag.rkw == pytest.approx(
        max(0.0, vertrag.vx_mrv - vertrag.stoab))


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
