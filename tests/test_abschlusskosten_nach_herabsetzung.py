"""Der Abschlusskostenrest nach einer Herabsetzung — ein Vertrag, eine Regel.

Der herabgesetzte Vertrag rechnete seine Reserve ueber den Zahlungspfad
mit dem VOLLEN noch nicht getilgten Abschlusskostenrest, seine
beitragsfreie Summe aber ueber den skalierten Ursprungsvertrag mit dem
f-fachen Rest. Eine Beitragsfreistellung nach der Herabsetzung sprang
deshalb in der Zillmerdauer (Befund aus einer blinden Angriffsrunde,
entstanden mit der Umstellung auf den Zahlungspfad). Die Regel steht
jetzt im Tarifplan (klv.md 7.1): Die Abschlusskosten folgen dem Beitrag,
der fortgefuehrte Vertrag traegt f des Rests.

Knoten: klv
"""

from __future__ import annotations

import dataclasses

import pytest

from rechner_pipeline.kern import KLV_DEFAULT, Rechenkern
from rechner_pipeline.kern.beitragsreduktion import MIT_ABZUG, PROSPEKTIV, ReduzierterVertrag

F = 0.6


@pytest.mark.parametrize("verfahren", [PROSPEKTIV, MIT_ABZUG])
@pytest.mark.parametrize("a0", [1, 2, 3, 4, 8])
def test_die_beitragsfreistellung_nach_der_herabsetzung_ist_wertstetig(verfahren, a0):
    """An der Naht ist die beitragsfreie Reserve der Rueckkaufs-Track des
    Vertrags davor — in JEDEM Jahr, auch in der Zillmerdauer. Die alte
    Fassung wich in den Jahren 1-4 um bis zu 1.017 EUR ab."""
    rv = ReduzierterVertrag.nach(Rechenkern(KLV_DEFAULT), a0, F, verfahren=verfahren)
    for pex in range(a0, KLV_DEFAULT.t):
        vor = rv.monatsreserve(12 * pex).vx_mrv
        nach = rv.reserve_beitragsfrei(pex, 12 * pex)
        assert nach == pytest.approx(vor, rel=1e-12, abs=1e-9), (verfahren, a0, pex)


@pytest.mark.parametrize("a0", [1, 3])
def test_der_fortgefuehrte_vertrag_traegt_f_des_abschlusskostenrests(a0):
    """Unabhaengig gerechnet: Rest = MRV - DR des unveraenderten Vertrags;
    der herabgesetzte (prospektiv, ohne umgewandelten Teil im Rest) traegt
    davon genau f. Kontrolle: ab dem Ende der Zillmerdauer ist der Rest
    null, dort aendert sich nichts."""
    kern = Rechenkern(KLV_DEFAULT)
    rv = ReduzierterVertrag.nach(kern, a0, F, verfahren=PROSPEKTIV)
    for a in range(a0, KLV_DEFAULT.zillmer_dauer + 2):
        z = kern.verlaufszeile(a)
        rest_voll = z.vx_mrv - z.drx_bpfl
        m = rv.monatsreserve(12 * a)
        assert m.vx_mrv - m.drx_bpfl == pytest.approx(F * rest_voll, rel=1e-9, abs=1e-9), a


def test_der_unveraenderte_vertrag_rechnet_wie_bisher():
    """Ratsche gegen Nebenwirkung: Ohne Herabsetzung ist der Faktor 1."""
    from rechner_pipeline.kern.zahlungspfad import standardpfad, verlaufszeile

    kern = Rechenkern(KLV_DEFAULT)
    for a in range(0, 8):
        pz = verlaufszeile(KLV_DEFAULT, standardpfad(KLV_DEFAULT), kern.basis, a)
        assert pz.vx_mrv == pytest.approx(kern.verlaufszeile(a).vx_mrv, rel=1e-12)


def test_mit_abzug_bei_negativer_deckungsrueckstellung_bricht_nicht_ab():
    """Angriffsrunde 2026-09-26: Bei negativer Deckungsrueckstellung (frueher
    Jahrestag, lange Laufzeit) brach die Herabsetzung mit Abzug den ganzen
    Lauf ab. Seit F1 (b) (Entscheid 2026-09-30) wird auf dem Rueckkaufs-Track
    umgewandelt, und der Abzug ist hoechstens der Rueckkaufswert: umgewandelt
    wird (1-f) x RKW, RKW = max(0, V^MRV - StoAb) — auch wenn die
    Rueckstellung negativ ist, der Rueckkaufswert aber positiv.
    Mutationsprobe: die Wache 'mrv <= 0' als Abbruch zurueck oder auf die
    Rueckstellung umwandeln -> rot."""
    from rechner_pipeline.kern.beitragsreduktion import reduziere

    mp = dataclasses.replace(KLV_DEFAULT, x=40, n=40, t=40)
    kern = Rechenkern(mp)
    z = kern.verlaufszeile(1)
    assert z.drx_bpfl < 0, "die Welt hat keine negative Rueckstellung"
    assert z.rkw > 0, "die Welt hat keinen positiven Rueckkaufswert"
    r = reduziere(kern, 1, F, verfahren=MIT_ABZUG)
    q = (1 - F) * z.rkw / (mp.sum_insured * z.vx_bfr)
    assert r.vs_neu == pytest.approx(mp.sum_insured * (F + q), rel=1e-12)
