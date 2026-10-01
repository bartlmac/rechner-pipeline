"""Die Vorgangsfolge im Kern — Regeln B2 bis B4 gegen unabhaengige Kontrollen.

Entscheid des Maintainers 2026-10-01 (ADR-023, Nachtrag; Tarifplan KLV
7.1 bis 7.3): beliebig viele Beitragsherabsetzungen und Teilkuendigungen je
Vertrag, in jeder Reihenfolge; die Teilkuendigung trifft jeden Baustein
proportional (eigene Tarife) und ist auch nach der Beitragsfreistellung
moeglich. ``kern.vorgangsfolge`` ist die EINE Darstellung, die alle Leser
rechnen.

Kontrollen, die nicht ``f(x) == f(x)`` sind:

* EIN Vorgang rechnet bitgleich wie der Weg davor
  (``beitragsreduktion.reduzierte_teile`` / ``ReduzierterVertrag``) — der
  Zeuge, dass sich fuer bestehende Vertraege kein Wert bewegt;
* zwei Teilkuendigungen mit f1 und f2 sind der gewoehnliche Vertrag mit
  f1 x f2 x S je Baustein (``Rechenkern`` mit kleinerer Summe);
* eine Teilkuendigung nach einer Herabsetzung ist die Herabsetzung des um f
  gekuerzten Vertrags (Homogenitaet, prospektives Verfahren);
* zwei Herabsetzungen: Reserve = c x Reserve des Ursprungsvertrags plus
  fixierte beitragsfreie Teilsummen x beitragsfreier Satz, Verlaufszeilen
  des Kerns, kein Zahlungspfad;
* nach der Beitragsfreistellung: die Teilkuendigung kuerzt die
  beitragsfreie Summe genau proportional und zahlt (1-f) x RKW des
  beitragsfreien Vertrags aus (Entscheid B3 vom 2026-10-01), nachgerechnet mit dem
  Stornoabzug aus den Tarifparametern;
* Anteil 1 aendert nichts; Teilkuendigungen sind vertauschbar,
  Herabsetzung und Teilkuendigung in verschiedenen Jahren nicht;
* die PLV-Welt verweigert benannt: Herabsetzung ab dem Beitragsende, nach
  der Beitragsfreistellung, zwei gleiche Vorgaenge an einem Jahrestag;
* B4 je Groesse: Zillmer-Rueckstand und Bruttobeitrag homogen (Kontrolle:
  Kern mit kleinerer Summe, Tarifparameter), Stueckkosten, Grenzen des
  Stornoabzugs und Korrekturschicht nicht skaliert (Kontrolle: Tarifregel,
  Schichtwert-Funktion).

Knoten: klv
"""

from __future__ import annotations

import dataclasses
import itertools
import math

import pytest

from rechner_pipeline.kern import KLV_DEFAULT, Rechenkern, erhoehungs_scheibe, vertrags_monatsreserve
from rechner_pipeline.kern.beitragsreduktion import (
    MIT_ABZUG,
    PROSPEKTIV,
    TEILKUENDIGUNG,
    ReduzierterVertrag,
    bestehende_teile,
    reduzierte_teile,
    vertrags_monatsreserve_reduziert,
)
from rechner_pipeline.kern.vorgangsfolge import (
    UMFANG_ALLE,
    UMFANG_GRUND,
    Vertragsstand,
    Vorgangsfolge,
    VorgangsfolgeFehler,
    stornoabzug_auf,
    vorgang,
)

#: Ein Modellpunkt mit spuerbaren Grenzen des Stornoabzugs (sie sind die
#: nicht homogene Groesse, an der eine Skalierung scheitern wuerde).
MP = dataclasses.replace(KLV_DEFAULT, stoab_min=50.0, stoab_max=200.0, stoab_satz=0.005)
GRUND = Rechenkern(MP)
SCHEIBEN = [(2, Rechenkern(erhoehungs_scheibe(MP, 2, 5000.0))),
            (3, Rechenkern(erhoehungs_scheibe(MP, 3, 5250.0)))]


def _folge(vorgaenge, scheiben=(), *, pex=None, je_baustein=False, umfang=UMFANG_ALLE):
    return Vorgangsfolge(GRUND, list(scheiben), list(vorgaenge), pex_jahr=pex,
                         stoab_je_baustein=je_baustein, tku_umfang=umfang)


def _rel(a: float, b: float) -> float:
    return abs(a - b) / max(1.0, abs(b))


# --------------------------------------------------------------------------- #
# Zeuge: EIN Vorgang rechnet bitgleich wie zuvor
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("verfahren,jahr,je_baustein,mit_scheiben", [
    (v, j, b, s) for v, j, b, s in itertools.product(
        (PROSPEKTIV, MIT_ABZUG, TEILKUENDIGUNG), (1, 4, 12, 19, 24), (False, True), (False, True))
    if not (v != TEILKUENDIGUNG and j >= MP.t)])
def test_ein_vorgang_ist_bitgleich_zum_weg_davor(verfahren, jahr, je_baustein, mit_scheiben):
    """Fuer jeden Vertrag mit EINEM Vorgang dieselben Bits wie ueber
    ``reduzierte_teile`` (Teilkuendigung dort: nur die Grundversicherung,
    deshalb Umfang ``grundversicherung``). Mutationsprobe: in
    ``Baustein.pfad`` die Leistung als ``q + c`` statt ``c + q`` -> gleich
    (kommutativ); als ``c * 1.0 + q`` ebenso; den umgewandelten Teil als
    ``zeile.vx_mrv * c * ...`` (andere Reihenfolge) -> rot an einzelnen
    Bits."""
    scheiben = SCHEIBEN if mit_scheiben else []
    alt = reduzierte_teile(GRUND, scheiben, jahr, 0.6, verfahren,
                           stoab_je_baustein=je_baustein)
    folge = _folge([vorgang(jahr, 0.6, verfahren)], scheiben, je_baustein=je_baustein,
                   umfang=UMFANG_GRUND)
    for monate in range(12 * jahr, 12 * MP.n + 1, 5):
        a = vertrags_monatsreserve_reduziert(alt, monate, stoab_je_baustein=je_baustein)
        n = folge.stand_am(monate).reserve(monate)
        assert (a.drx_bpfl, a.vx_mrv, a.stoab, a.rkw) == (n.drx_bpfl, n.vx_mrv, n.stoab, n.rkw)
        assert sum(v.reduktion.vs_neu for _, v in bestehende_teile(alt, monate)) == \
            folge.stand_am(monate).werte(monate)["leistung"]


def test_ein_vorgang_und_spaetere_beitragsfreistellung_bitgleich():
    alt = reduzierte_teile(GRUND, SCHEIBEN, 4, 0.6, PROSPEKTIV, stoab_je_baustein=False)
    folge = _folge([vorgang(4, 0.6, PROSPEKTIV)], SCHEIBEN, pex=7)
    st = folge.stand_am(12 * 7)
    assert sum(v.beitragsfreie_summe(7 - e) for e, v in alt) == st.vs_bfr()
    for monate in range(84, 12 * MP.n + 1, 7):
        alt_dk = sum(v.reserve_beitragsfrei(7 - e, monate - 12 * e) for e, v in alt)
        assert alt_dk == st.werte(monate)["deckungskapital"]


# --------------------------------------------------------------------------- #
# B2/B4: Teilkuendigungen sind homogen — Kontrolle gegen den gewoehnlichen Kern
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("je_baustein", [False, True])
def test_zwei_teilkuendigungen_sind_der_vertrag_mit_dem_produkt_der_anteile(je_baustein):
    """Kontrolle: Grund und jede Scheibe als gewoehnlicher Kern mit f1 x f2 x
    S_i, Stornoabzug auf dieser Summe (Grenzen nicht skaliert, B4).
    Mutationsprobe: in ``_teilkuendigen`` die Scheiben auslassen (Umfang
    Grund) -> rot; den Zillmer-Rueckstand nicht mitskalieren (Pfad statt
    Kern) -> rot in der Zillmerdauer."""
    f1, f2 = 0.7, 0.55
    folge = _folge([vorgang(3, f1, TEILKUENDIGUNG), vorgang(4, f2, TEILKUENDIGUNG)],
                   SCHEIBEN[:1], je_baustein=je_baustein)
    grund = Rechenkern(dataclasses.replace(MP, sum_insured=f2 * (f1 * MP.sum_insured)))
    scheibe = SCHEIBEN[0][1]
    scheibe = Rechenkern(dataclasses.replace(
        scheibe.mp, sum_insured=f2 * (f1 * scheibe.mp.sum_insured)))
    for monate in range(48, 12 * MP.n + 1, 11):
        soll = vertrags_monatsreserve(grund, [(2, scheibe)], monate,
                                      stoab_je_baustein=je_baustein)
        ist = folge.stand_am(monate).reserve(monate)
        for feld in ("drx_bpfl", "vx_mrv", "stoab", "rkw"):
            assert _rel(getattr(ist, feld), getattr(soll, feld)) < 1e-12, (monate, feld)


def test_teilkuendigung_nach_herabsetzung_ist_die_herabsetzung_des_gekuerzten_vertrags():
    """Prospektiv ist die Umwandlung homogen: Herabsetzung f1 im Jahr 3, dann
    Teilkuendigung f2 im Jahr 6, ist ab Jahr 6 der herabgesetzte Vertrag mit
    f2 x S (``ReduzierterVertrag`` auf dem gekuerzten Kern, der alte Weg)."""
    f1, f2 = 0.6, 0.8
    folge = _folge([vorgang(3, f1, PROSPEKTIV), vorgang(6, f2, TEILKUENDIGUNG)])
    kontrolle = ReduzierterVertrag.nach(
        Rechenkern(dataclasses.replace(MP, sum_insured=f2 * MP.sum_insured)), 3, f1)
    for monate in range(72, 12 * MP.n + 1, 13):
        ist = folge.stand_am(monate).reserve(monate)
        soll = kontrolle.monatsreserve(monate)
        assert _rel(ist.drx_bpfl, soll.drx_bpfl) < 1e-12
        assert _rel(ist.vx_mrv, soll.vx_mrv) < 1e-12
    assert _rel(folge.stand_am(72).gesamt_vs(), kontrolle.reduktion.vs_neu) < 1e-12


def test_zwei_herabsetzungen_gegen_die_verlaufszeilen_des_kerns():
    """B2: Die zweite Herabsetzung wirkt auf den Zustand: Sie wandelt (1-f2)
    des FORTGEFUEHRTEN Rueckkaufs-Tracks um (c = f1 vor ihr), die schon
    fixierte beitragsfreie Teilsumme bleibt. Kontrolle allein aus den
    Verlaufszeilen des Kerns: Am Jahrestag a ist die Reserve
    c x V(a) + (q1 + q2) x V_bfr(a). Mutationsprobe: in ``_herabsetzen`` den
    Faktor c weglassen (die zweite Herabsetzung wandelt den vollen Track um)
    -> rot."""
    f1, f2 = 0.7, 0.5
    folge = _folge([vorgang(3, f1, PROSPEKTIV), vorgang(8, f2, PROSPEKTIV)])
    z3, z8 = GRUND.verlaufszeile(3), GRUND.verlaufszeile(8)
    q1 = (1 - f1) * z3.vx_mrv / z3.vx_bfr
    q2 = (1 - f2) * f1 * z8.vx_mrv / z8.vx_bfr
    stand = folge.stand_am(96)
    assert _rel(stand.gesamt_vs(), f1 * f2 * MP.sum_insured + q1 + q2) < 1e-12
    for a in range(8, MP.n + 1):
        z = GRUND.verlaufszeile(a)
        r = stand.reserve(12 * a)
        assert _rel(r.drx_bpfl, f1 * f2 * z.drx_bpfl + (q1 + q2) * z.vx_bfr) < 1e-9, a
        assert _rel(r.vx_mrv, f1 * f2 * z.vx_mrv + (q1 + q2) * z.vx_bfr) < 1e-9, a


@pytest.mark.parametrize("art", [PROSPEKTIV, MIT_ABZUG, TEILKUENDIGUNG])
def test_anteil_eins_aendert_nichts(art):
    folge = _folge([vorgang(5, 1.0, art)], SCHEIBEN)
    for monate in (60, 61, 120, 12 * MP.n):
        ist = folge.stand_am(monate).reserve(monate)
        soll = vertrags_monatsreserve(GRUND, SCHEIBEN, monate)
        assert _rel(ist.drx_bpfl, soll.drx_bpfl) < 1e-12
        assert _rel(ist.rkw, soll.rkw) < 1e-12
    erg = folge.ergebnisse[0]
    assert erg.vs_neu == erg.vs_vor
    if art == TEILKUENDIGUNG:
        assert erg.auszahlung == 0.0


# --------------------------------------------------------------------------- #
# Reihenfolge
# --------------------------------------------------------------------------- #


def test_teilkuendigungen_sind_vertauschbar():
    """Nach der letzten Erhoehung vertauschbar. Eine Scheibe, die ZWISCHEN
    beiden entsteht, traegt nur den zweiten Anteil — dort sind sie es nicht
    (die Scheibe aus Jahr 3 entsteht am Jahrestag NACH der Teilkuendigung des
    Jahres 3)."""
    a = _folge([vorgang(4, 0.7, TEILKUENDIGUNG), vorgang(9, 0.4, TEILKUENDIGUNG)], SCHEIBEN)
    b = _folge([vorgang(4, 0.4, TEILKUENDIGUNG), vorgang(9, 0.7, TEILKUENDIGUNG)], SCHEIBEN)
    for monate in (108, 140, 12 * MP.n):
        assert _rel(a.stand_am(monate).reserve(monate).rkw,
                    b.stand_am(monate).reserve(monate).rkw) < 1e-12
    c = _folge([vorgang(3, 0.7, TEILKUENDIGUNG), vorgang(9, 0.4, TEILKUENDIGUNG)], SCHEIBEN)
    d = _folge([vorgang(3, 0.4, TEILKUENDIGUNG), vorgang(9, 0.7, TEILKUENDIGUNG)], SCHEIBEN)
    assert [b.vs for b in c.stand_am(120).bausteine][2] == pytest.approx(0.4 * 5250.0)
    assert [b.vs for b in d.stand_am(120).bausteine][2] == pytest.approx(0.7 * 5250.0)


def test_herabsetzung_und_teilkuendigung_sind_nicht_vertauschbar():
    """Die Herabsetzung wandelt den Rueckkaufs-Track IHRES Jahres um; in einem
    anderen Jahr ist es ein anderer Vertrag."""
    a = _folge([vorgang(3, 0.6, PROSPEKTIV), vorgang(9, 0.8, TEILKUENDIGUNG)])
    b = _folge([vorgang(3, 0.8, TEILKUENDIGUNG), vorgang(9, 0.6, PROSPEKTIV)])
    assert _rel(a.stand_am(120).gesamt_vs(), b.stand_am(120).gesamt_vs()) > 1e-4


def test_teilkuendigung_vor_und_nach_der_beitragsfreistellung_gleich():
    """Die Beitragsfreistellung fixiert eine homogene Summe: kuendigen vor
    oder nach ihr ergibt dieselbe beitragsfreie Summe."""
    vorher = _folge([vorgang(4, 0.6, TEILKUENDIGUNG)], SCHEIBEN, pex=7)
    nachher = _folge([vorgang(10, 0.6, TEILKUENDIGUNG)], SCHEIBEN, pex=7)
    assert _rel(vorher.stand_am(120).vs_bfr(), nachher.stand_am(120).vs_bfr()) < 1e-12


# --------------------------------------------------------------------------- #
# B3: Teilkuendigung nach der Beitragsfreistellung
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("je_baustein", [False, True])
@pytest.mark.parametrize("jahr", [7, 12, 26])
def test_teilkuendigung_nach_pex_kuerzt_proportional_und_zahlt_den_rkw_bfr(je_baustein, jahr):
    """Die beitragsfreie Summe sinkt genau auf f; ausgezahlt wird (1-f) mal
    beitragsfreie Reserve minus Stornoabzug der Tarifregel auf der
    beitragsfreien Summe (null in der flexiblen Phase). Kontrolle aus den
    Tarifparametern und den Verlaufszeilen. Jahr 26 liegt in der flexiblen
    Phase (Alter 71, Restlaufzeit 4): dort kein Abzug."""
    f = 0.6
    pex = 7
    folge = _folge([vorgang(jahr, f, TEILKUENDIGUNG)], SCHEIBEN, pex=pex,
                   je_baustein=je_baustein)
    vor = folge.stand_vor(jahr, "TKU")
    nach = folge.stand_am(12 * jahr)
    assert _rel(nach.vs_bfr(), f * vor.vs_bfr()) < 1e-12
    teile = [(0, GRUND)] + SCHEIBEN
    summen = [k.beitragsfreie_summe(pex - e) for e, k in teile]
    reserven = [s * k.verlaufszeile(jahr - e).vx_bfr for s, (e, k) in zip(summen, teile)]

    def abzug(mp, a, summe, reserve):
        flex = mp.x + a >= mp.min_alter_flex and a >= mp.n - mp.min_rlz_flex
        if a > mp.n or flex:
            return 0.0
        return min(mp.stoab_max, max(mp.stoab_min, mp.stoab_satz * (summe - reserve)))

    if je_baustein:
        rkw = sum(max(0.0, r - abzug(k.mp, jahr - e, s, r))
                  for s, r, (e, k) in zip(summen, reserven, teile))
    else:
        rkw = max(0.0, sum(reserven) - abzug(MP, jahr, sum(summen), sum(reserven)))
    assert _rel(folge.ergebnis(jahr, "TKU").auszahlung, (1 - f) * rkw) < 1e-12
    if jahr == 26:
        assert stornoabzug_auf(GRUND, jahr, sum(summen), sum(reserven)) == 0.0


def test_die_regel_des_rueckkaufswerts_laesst_die_verlaufszeile_unberuehrt():
    """B3 sitzt am Ereignis-Anschluss: Die Spalten RKW und VS_bfr der
    Verlaufszeile (Charakterisierung) rechnen wie zuvor."""
    z = GRUND.verlaufszeile(5)
    assert z.rkw == max(0.0, z.vx_mrv - GRUND.produkt.stornoabzug(5, z.drx_bpfl))
    assert stornoabzug_auf(GRUND, 5, MP.sum_insured, z.drx_bpfl) == z.stoab


# --------------------------------------------------------------------------- #
# B1: Umfang der Teilkuendigung
# --------------------------------------------------------------------------- #


def test_umfang_grundversicherung_laesst_die_scheiben_unberuehrt():
    alle = _folge([vorgang(5, 0.6, TEILKUENDIGUNG)], SCHEIBEN, umfang=UMFANG_ALLE)
    grund = _folge([vorgang(5, 0.6, TEILKUENDIGUNG)], SCHEIBEN, umfang=UMFANG_GRUND)
    s_alle = [b.vs for b in alle.stand_am(60).bausteine]
    s_grund = [b.vs for b in grund.stand_am(60).bausteine]
    assert s_alle == [0.6 * MP.sum_insured, 0.6 * 5000.0, 0.6 * 5250.0]
    assert s_grund == [0.6 * MP.sum_insured, 5000.0, 5250.0]


def test_die_auszahlung_ist_der_anteil_des_rkw_des_betroffenen_teils():
    folge = _folge([vorgang(5, 0.6, TEILKUENDIGUNG)], SCHEIBEN)
    rkw_vor = vertrags_monatsreserve(GRUND, SCHEIBEN, 60).rkw
    assert _rel(folge.ergebnisse[0].auszahlung, 0.4 * rkw_vor) < 1e-12


# --------------------------------------------------------------------------- #
# Verweigert, benannt
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("vorgaenge,pex,text", [
    ([vorgang(20, 0.6, PROSPEKTIV)], None, "Beitragszahlungsdauer ist beendet"),
    ([vorgang(9, 0.6, PROSPEKTIV)], 7, "nach der Beitragsfreistellung"),
    ([vorgang(30, 0.6, TEILKUENDIGUNG)], None, "laeuft bei n=30 ab"),
    ([vorgang(4, 0.6, TEILKUENDIGUNG), vorgang(4, 0.5, TEILKUENDIGUNG)], None,
     "zwei Vorgaenge TKU"),
    ([vorgang(4, 0.0, TEILKUENDIGUNG)], None, "nicht in (0, 1]"),
])
def test_die_plv_welt_verweigert_benannt(vorgaenge, pex, text):
    with pytest.raises(VorgangsfolgeFehler, match=text.replace("(", r"\(").replace(")", r"\)")
                       .replace("[", r"\[").replace("]", r"\]")):
        _folge(vorgaenge, pex=pex)


def test_erhoehung_nach_beitragsfreistellung_wird_verweigert():
    stand = Vertragsstand.anfang(GRUND, stoab_je_baustein=False, tku_umfang=UMFANG_ALLE)
    with pytest.raises(VorgangsfolgeFehler, match="keine Dynamik"):
        stand.nach_pex(5).nach_erhoehung(6, SCHEIBEN[0][1])


def test_das_tarifwerk_hat_keinen_default():
    with pytest.raises(TypeError):
        Vorgangsfolge(GRUND, [], [])  # type: ignore[call-arg]


def test_ein_unbekannter_umfang_faellt():
    with pytest.raises(VorgangsfolgeFehler, match="tku_umfang"):
        Vertragsstand.anfang(GRUND, stoab_je_baustein=False, tku_umfang="scheiben")


def test_keine_summe_und_kein_rueckkaufswert_unter_null_bei_kleiner_summe():
    """Floor der umgewandelten Summe (RC01) und RKW = max(0, ...) auch in der
    Folge: kleine Summe, Mindestabzug greift, frueher Vorgang."""
    mp = dataclasses.replace(MP, sum_insured=800.0, alpha=0.06, zillmer_dauer=2)
    folge = Vorgangsfolge(Rechenkern(mp), [], [vorgang(1, 0.5, MIT_ABZUG),
                                                vorgang(1, 0.5, TEILKUENDIGUNG)],
                          stoab_je_baustein=False, tku_umfang=UMFANG_ALLE)
    for e in folge.ergebnisse:
        assert e.vs_neu >= 0.0 and (e.auszahlung is None or e.auszahlung >= 0.0)
    for monate in range(12, 12 * mp.n + 1, 7):
        assert folge.stand_am(monate).reserve(monate).rkw >= 0.0
    assert all(not math.isnan(b.vs) for b in folge.stand_am(12).bausteine)



# --------------------------------------------------------------------------- #
# B4: Homogenitaet — jede Groesse einzeln, je mit unabhaengiger Kontrolle
# --------------------------------------------------------------------------- #
#
# Die Teilkuendigung skaliert die Summe eines Bausteins und rechnet danach den
# gewoehnlichen Kern mit kleinerer Summe. Das traegt nur, soweit jede Groesse
# des Kerns homogen in der Summe ist. Geprueft je Groesse: der Bruttobeitrag
# (Satz x Summe) und der Zillmer-Rueckstand (Satz x Summe) sind homogen; die
# Stueckkosten im Zahlbeitrag, die Grenzen des Stornoabzugs (Mindest- und
# Hoechstbetrag: die einzigen Pauschalbetraege des Abzugs) und die
# Korrekturschicht (ein Betrag, keine Quote) sind es NICHT und werden darum nie
# skaliert, sondern auf dem Zustand gebildet bzw. vom ersten Vorgang aufgenommen.


def test_b4_zillmer_rueckstand_skaliert_mit_der_summe():
    """In der Zillmerdauer (Teilkuendigung im Jahr 1): Reserve und
    Rueckkaufs-Track des Zustands sind die des gewoehnlichen Kerns mit f x S
    — auch der negative Zillmer-Rest. Kontrolle: ``Rechenkern`` mit der
    kleineren Summe, kein Zahlungspfad."""
    f = 0.6
    folge = _folge([vorgang(1, f, TEILKUENDIGUNG)])
    kontrolle = Rechenkern(dataclasses.replace(MP, sum_insured=f * MP.sum_insured))
    assert MP.zillmer_dauer >= 2
    for monate in range(12, 12 * (MP.zillmer_dauer + 1) + 1):
        ist = folge.stand_am(monate).reserve(monate)
        soll = kontrolle.monatsreserve(monate)
        assert _rel(ist.drx_bpfl, soll.drx_bpfl) < 1e-12, monate
        assert _rel(ist.vx_mrv, soll.vx_mrv) < 1e-12, monate


def test_b4_stueckkosten_bleiben_im_zahlbeitrag_fix():
    """Bruttojahresbeitrag = Summe x Satz (homogen); der Zahlbeitrag traegt
    die Stueckkosten k je Baustein UNSKALIERT. Kontrolle aus den
    Tarifparametern des Ursprungsvertrags (Satz, Ratenzuschlag, Zahlweise)."""
    f = 0.4
    stand = _folge([vorgang(4, f, TEILKUENDIGUNG)]).stand_am(48)
    (_, kern), = stand.beitragskerne(48)
    bxt = GRUND.gross_premium_rate()
    assert _rel(kern.gross_annual_premium(), f * MP.sum_insured * bxt) < 1e-12
    soll_bzb = (1.0 + GRUND.produkt.ratzu()) / MP.zw * (f * MP.sum_insured * bxt + MP.policy_fee)
    assert _rel(kern.gross_payable_premium(), soll_bzb) < 1e-12
    # Mutationsfaenger: skalierte Stueckkosten waeren ein anderer Beitrag.
    assert abs(kern.gross_payable_premium() - f * GRUND.gross_payable_premium()) > 0.01


def test_b4_die_grenzen_des_stornoabzugs_werden_nicht_skaliert():
    """Der Satzteil des Abzugs ist homogen, Mindest- und Hoechstbetrag sind
    Pauschalbetraege des Tarifs: Nach einer kleinen Teilkuendigung greift der
    Mindestbetrag auf dem Zustand — nicht f x Mindestbetrag. Kontrolle aus
    der Tarifregel mit den Werten des Ursprungsvertrags."""
    f = 0.1
    folge = _folge([vorgang(10, f, TEILKUENDIGUNG)])
    monate = 12 * 10 + 5
    ist = folge.stand_am(monate).reserve(monate)
    vor = GRUND.monatsreserve(monate)
    satzteil = MP.stoab_satz * (f * MP.sum_insured - f * vor.drx_bpfl)
    soll = min(MP.stoab_max, max(MP.stoab_min, satzteil))
    assert satzteil < MP.stoab_min                      # die Grenze greift hier
    assert ist.stoab == pytest.approx(soll, rel=1e-12)
    assert ist.stoab != pytest.approx(f * vor.stoab, rel=1e-6)
    assert ist.rkw == pytest.approx(max(0.0, f * vor.vx_mrv - soll), rel=1e-12)


def test_b4_die_korrekturschicht_nimmt_der_erste_vorgang_ganz_auf():
    """Die Korrekturschicht ist ein Betrag, keine Quote: Die erste
    Teilkuendigung zahlt sie VOLLSTAENDIG aus (nicht (1-f) davon), danach
    traegt der Vertrag keine Schicht mehr, und eine zweite Teilkuendigung
    zahlt nur (1-f2) x Rueckkaufswert. Kontrollen: der Schichtwert aus
    ``korrekturschicht.schichtwert_bei``, die Rueckkaufswerte aus dem
    gewoehnlichen Kern vor bzw. mit f1 x S."""
    from rechner_pipeline.bestand.migrationszugang import Uebernahme, uebernehmen
    from rechner_pipeline.kern.korrekturschicht import schichtwert_bei

    prosp = GRUND.verlaufszeile(2).drx_bpfl
    eintrag, = uebernehmen([Uebernahme(police_id=1, model_point=dataclasses.asdict(MP),
                                       monate_ta=24, dk_ist=prosp - 400.0)])
    schicht = (eintrag.parameter, 24)
    f1, f2 = 0.8, 0.5
    stand = Vertragsstand.anfang(GRUND, stoab_je_baustein=False, tku_umfang=UMFANG_ALLE,
                                 schicht=schicht)
    stand1, e1 = stand.nach_vorgang(vorgang(4, f1, TEILKUENDIGUNG))
    wert = schichtwert_bei(eintrag.parameter, 24, MP, 48)
    assert abs(wert) > 1.0
    assert e1.auszahlung == pytest.approx((1 - f1) * GRUND.monatsreserve(48).rkw + wert, rel=1e-12)
    assert e1.absorbiert == pytest.approx(wert, rel=1e-12)
    assert stand1.schicht is None and stand1.werte(60)["korrekturschicht"] == 0.0
    _, e2 = stand1.nach_vorgang(vorgang(6, f2, TEILKUENDIGUNG))
    gekuerzt = Rechenkern(dataclasses.replace(MP, sum_insured=f1 * MP.sum_insured))
    assert e2.auszahlung == pytest.approx((1 - f2) * gekuerzt.monatsreserve(72).rkw, rel=1e-12)
