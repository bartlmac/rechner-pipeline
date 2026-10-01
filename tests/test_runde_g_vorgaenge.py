"""Pruefrunde G, Vorgaenge im Kern — zwei bestaetigte Funde der Sollrechnung.

**G01: Der Abschlusskostenrest am Jahrestag n.** Die Abschlusskosten folgen
dem Beitrag (Tarifplan KLV 7.1): Der fortgefuehrte Teil eines herabgesetzten
Bausteins traegt den Anteil ``c`` des noch nicht getilgten Rests — an JEDEM
Jahrestag ``0..n``. Das Profil des Zahlungspfads hat ``n`` Eintraege (Jahre
``0..n-1``); jenseits davon fiel der Faktor auf 1.0 zurueck. Sichtbar wird das,
sobald die Laufzeit eines Bausteins kuerzer ist als die Zillmerdauer (eine
spaete Erhoehungsscheibe, ``n' = n - e < 5``): Am Jahrestag ``n'`` traegt die
Kernformel dann noch einen Rest, und die Monatsmischung des letzten
Vertragsjahres liest ihn. Der Rueckkaufswert lag dort um bis zu rund 20 EUR zu
hoch, das Deckungskapital war gleich.

Das Soll rechnet hier NICHT ueber den Zahlungspfad, sondern aus den
Jahreszeilen des Kerns (``Rechenkern.verlaufszeile``): ``c * V^MRV + q * S *
V^bfr`` (Tarifplan 7.3, Kontrolle der Folge RED, RED), linear gemischt.
Geprueft werden beide Wege, die einen Pfad bauen (``Baustein.pfad`` der
Vorgangsfolge, ``als_zahlungspfad`` des Einzelvorgangs), beide Verfahren der
Herabsetzung und die Herabsetzung mit folgender Teilkuendigung.

**G02: Die Menge der zulaessigen Folgen.** Tarifplan 7.3: zulaessig ist eine
Folge mit jedem Vorgang im Vertragsjahr ``0 < a < n``; jede Folge ausserhalb
wird benannt verweigert, mit dem Ausweg. Herabsetzung und Teilkuendigung im
Jahr 0 und eine Beitragsfreistellung im Jahr 0 oder ab dem Beitragsende
rechnete der Kern still (eine Beitragsfreistellung gibt es nur, solange
Beitraege laufen: Entscheid 2026-10-01, GeVo-Katalog der T-Box). Die Jahresgrenzen stehen jetzt an EINER Stelle
(``beitragsreduktion.pruefe_vorgangsjahr``), durch die Einzelreduktion,
Herabsetzung, Teilkuendigung, Beitragsfreistellung und Erhoehung der Folge
gehen; jede Grenze ist in beide Richtungen getestet (letzter gueltiger, erster
ungueltiger Wert). Die Ratsche haelt die Menge der Vorgangsarten mit ``==``.

Knoten: klv
"""

from __future__ import annotations

import dataclasses

import pytest

from rechner_pipeline.kern import KLV_DEFAULT, Rechenkern, erhoehungs_scheibe
from rechner_pipeline.kern.beitragsreduktion import (
    MIT_ABZUG,
    PROSPEKTIV,
    TEILKUENDIGUNG,
    VORGANGSJAHR_OBERGRENZE,
    BeitragsreduktionFehler,
    ReduzierterVertrag,
    pruefe_vorgangsjahr,
    reduziere,
)
from rechner_pipeline.kern.vorgangsfolge import (
    ERH,
    PEX,
    RANG,
    RED,
    TKU,
    UMFANG_ALLE,
    Vertragsstand,
    Vorgangsfolge,
    VorgangsfolgeFehler,
    vorgang,
)

# --------------------------------------------------------------------------- #
# G01 — Abschlusskostenrest am Jahrestag n
# --------------------------------------------------------------------------- #

GRUND_MP = dataclasses.replace(KLV_DEFAULT, x=34, n=20, t=20, sum_insured=83000.0)
SCHEIBE_JAHR = 17
SCHEIBE_MP = erhoehungs_scheibe(GRUND_MP, SCHEIBE_JAHR, 4000.0, gamma1_uebernehmen=False)


def test_die_welt_traegt_den_fall():
    """Vorbedingung: Die Scheibe laeuft kuerzer als die Zillmerdauer, und am
    Jahrestag n' traegt der unveraenderte Kern noch einen Abschlusskostenrest
    (sonst waere der Test blind)."""
    assert SCHEIBE_MP.n < SCHEIBE_MP.zillmer_dauer
    z = Rechenkern(SCHEIBE_MP).verlaufszeile(SCHEIBE_MP.n)
    assert z.vx_mrv - z.drx_bpfl > 10.0


def _soll_zeile(kern: Rechenkern, a: int, c: float, q: float):
    """(DR, MRV) eines Bausteins mit Abschnitt (c, q) am Jahrestag a — aus der
    Jahreszeile des Kerns, nicht aus dem Zahlungspfad."""
    z = kern.verlaufszeile(a)
    s = kern.mp.sum_insured
    return (c * z.drx_bpfl + q * s * z.vx_bfr, c * z.vx_mrv + q * s * z.vx_bfr)


def _soll_monat(kern: Rechenkern, monate: int, c: float, q: float):
    a, r = divmod(int(monate), 12)
    d0, v0 = _soll_zeile(kern, a, c, q)
    if not r:
        return d0, v0
    d1, v1 = _soll_zeile(kern, a + 1, c, q)
    u = r / 12.0
    return (1 - u) * d0 + u * d1, (1 - u) * v0 + u * v1


@pytest.mark.parametrize("verfahren", [PROSPEKTIV, MIT_ABZUG])
@pytest.mark.parametrize("je_baustein", [False, True])
@pytest.mark.parametrize("mit_tku", [False, True])
def test_der_herabgesetzte_baustein_traegt_c_des_rests_auch_am_jahrestag_n(
        verfahren, je_baustein, mit_tku):
    """Vorgangsfolge: Scheibe aus Jahr 17 (n' = 3), Herabsetzung im Jahr 18 auf
    0,6, wahlweise Teilkuendigung im Jahr 19. Je Monat des letzten
    Vertragsjahres der Scheibe ist ihr Rueckkaufs-Track gleich dem Soll aus
    den Kern-Jahreszeilen mit (c, q) des letzten Abschnitts. Auf eab5a57 rot:
    im Monat 239 um (1-c) x Rest x 11/12 zu hoch."""
    vorgaenge = [vorgang(18, 0.6, verfahren)]
    if mit_tku:
        vorgaenge.append(vorgang(19, 0.7, TEILKUENDIGUNG))
    folge = Vorgangsfolge(Rechenkern(GRUND_MP), [(SCHEIBE_JAHR, Rechenkern(SCHEIBE_MP))],
                          vorgaenge, stoab_je_baustein=je_baustein, tku_umfang=UMFANG_ALLE)
    letzter = 12 * GRUND_MP.n - 1
    b = folge.stand_am(letzter).bausteine[1]
    ab, c, q = b.abschnitte[-1]
    assert c < 1.0 and ab == 18 - SCHEIBE_JAHR
    for lokal in range(12 * (SCHEIBE_MP.n - 1), 12 * SCHEIBE_MP.n):
        ist = b.monatsreserve(lokal)
        soll_dr, soll_mrv = _soll_monat(b.kern, lokal, c, q)
        assert ist.drx_bpfl == pytest.approx(soll_dr, rel=1e-12, abs=1e-8), lokal
        assert ist.vx_mrv == pytest.approx(soll_mrv, rel=1e-12, abs=1e-8), lokal


def test_der_rueckkaufswert_des_vertrags_im_letzten_jahr():
    """Vertragsweit (Abzug je Vertrag), unabhaengig nachgerechnet: Grund und
    Scheibe aus Jahreszeilen des Kerns, Stornoabzug aus den Tarifparametern.
    Ist auf eab5a57: Monat 239 84.528,05, Soll 84.512,44."""
    f = 0.6
    folge = Vorgangsfolge(Rechenkern(GRUND_MP), [(SCHEIBE_JAHR, Rechenkern(SCHEIBE_MP))],
                          [vorgang(19, f, PROSPEKTIV)], stoab_je_baustein=False,
                          tku_umfang=UMFANG_ALLE)
    for m in range(12 * 19 + 1, 12 * 20):
        teile = []
        for e, mp in ((0, GRUND_MP), (SCHEIBE_JAHR, SCHEIBE_MP)):
            kern = Rechenkern(mp)
            za = kern.verlaufszeile(19 - e)
            q = (1 - f) * za.vx_mrv / za.vx_bfr / mp.sum_insured
            dr, mrv = _soll_monat(kern, m - 12 * e, f, q)
            teile.append((dr, mrv, mp.sum_insured * (f + q)))
        dr = sum(t[0] for t in teile)
        mrv = sum(t[1] for t in teile)
        vs = sum(t[2] for t in teile)
        stoab = min(GRUND_MP.stoab_max, max(GRUND_MP.stoab_min, GRUND_MP.stoab_satz * (vs - dr)))
        soll = max(0.0, mrv - stoab)
        assert folge.stand_am(m).werte(m)["rueckkaufswert"] == pytest.approx(
            soll, rel=1e-12, abs=1e-8), m


@pytest.mark.parametrize("verfahren", [PROSPEKTIV, MIT_ABZUG])
def test_der_einzelweg_traegt_f_des_rests_auch_am_ablauf(verfahren):
    """Zweiter Weg zum Pfad (``als_zahlungspfad`` ueber ReduzierterVertrag):
    ein Vertrag, der kuerzer laeuft als die Zillmerdauer (n = t = 4),
    herabgesetzt im Jahr 2. Soll aus der Reduktion (f, q) und den
    Jahreszeilen des Kerns."""
    mp = dataclasses.replace(KLV_DEFAULT, n=4, t=4)
    kern = Rechenkern(mp)
    assert mp.n < mp.zillmer_dauer
    rv = ReduzierterVertrag.nach(kern, 2, 0.6, verfahren=verfahren)
    red = rv.reduktion
    f = red.anteil
    q = (red.vs_neu - f * red.vs_alt) / red.vs_alt
    for m in range(12 * (mp.n - 1), 12 * mp.n + 1):
        ist = rv.monatsreserve(m)
        soll_dr, soll_mrv = _soll_monat(kern, m, f, q)
        assert ist.drx_bpfl == pytest.approx(soll_dr, rel=1e-12, abs=1e-8), m
        assert ist.vx_mrv == pytest.approx(soll_mrv, rel=1e-12, abs=1e-8), m


def test_positivkontrolle_ohne_herabsetzung_ist_der_rest_voll():
    """Ohne Herabsetzung (Anteil 1) traegt der Baustein den vollen Rest — der
    Fix darf den unveraenderten Verlauf nicht kuerzen."""
    folge = Vorgangsfolge(Rechenkern(GRUND_MP), [(SCHEIBE_JAHR, Rechenkern(SCHEIBE_MP))],
                          [vorgang(19, 1.0, PROSPEKTIV)], stoab_je_baustein=False,
                          tku_umfang=UMFANG_ALLE)
    b = folge.stand_am(12 * 20 - 1).bausteine[1]
    kern = Rechenkern(SCHEIBE_MP)
    for lokal in range(24, 36):
        assert b.monatsreserve(lokal).vx_mrv == pytest.approx(
            kern.monatsreserve(lokal).vx_mrv, rel=1e-12, abs=1e-8)


# --------------------------------------------------------------------------- #
# G02 — Die Menge der zulaessigen Folgen, Grenzen in beide Richtungen
# --------------------------------------------------------------------------- #

MP = KLV_DEFAULT  # t = 20, n = 30
GRUND = Rechenkern(MP)


def _folge(vorgaenge, pex=None, scheiben=()):
    return Vorgangsfolge(GRUND, list(scheiben), vorgaenge, pex_jahr=pex,
                         stoab_je_baustein=False, tku_umfang=UMFANG_ALLE)


def _red(jahr):
    return _folge([vorgang(jahr, 0.6, PROSPEKTIV)])


def _tku(jahr):
    return _folge([vorgang(jahr, 0.6, TEILKUENDIGUNG)])


def _pex(jahr):
    # Die Teilkuendigung im letzten Vertragsjahr macht die Folge rechnend;
    # PEX allein ist bereits eine Folge.
    return _folge([vorgang(MP.n - 1, 0.6, TEILKUENDIGUNG)], pex=jahr)


def _erh(jahr):
    stand = Vertragsstand.anfang(GRUND, stoab_je_baustein=False, tku_umfang=UMFANG_ALLE)
    # Der Scheibenkern ist im Jahr 1 gebaut: Die Grenze, die hier gilt, ist die
    # der Folge, nicht die des Scheibenbaus.
    return stand.nach_erhoehung(jahr, Rechenkern(erhoehungs_scheibe(MP, 1, 1000.0, gamma1_uebernehmen=False)))


#: Je Vorgangsart: (Bauweg, letzter ungueltiger unten, erster gueltiger, letzter
#: gueltiger, erster ungueltiger oben). Unten ist die Grenze fuer jede Art das
#: Vertragsjahr 0; oben das Beitragsende (Herabsetzung, Erhoehung,
#: Beitragsfreistellung — Entscheid 2026-10-01: nur solange Beitraege laufen)
#: bzw. der Ablauf (Teilkuendigung).
GRENZEN = {
    RED: (_red, 0, 1, MP.t - 1, MP.t),
    TKU: (_tku, 0, 1, MP.n - 1, MP.n),
    PEX: (_pex, 0, 1, MP.t - 1, MP.t),
    ERH: (_erh, 0, 1, MP.t - 1, MP.t),
}


def test_ratsche_jede_vorgangsart_hat_ihre_grenzen():
    """Ratsche (Menge): Die Vorgangsarten der Folge (``RANG``), die Arten der
    einen Grenzstelle im Kern (``VORGANGSJAHR_OBERGRENZE``) und die hier
    getesteten sind dieselbe Menge, und die Obergrenzen stimmen mit diesem
    Test ueberein. Eine neue Art ohne Grenze ist ein Befund. Positivkontrolle:
    eine unbekannte Art verweigert die Grenzstelle benannt."""
    assert set(RANG) == set(GRENZEN) == set(VORGANGSJAHR_OBERGRENZE)
    for art, (_, _, _, letzter, oben) in GRENZEN.items():
        assert oben == getattr(MP, VORGANGSJAHR_OBERGRENZE[art]) == letzter + 1, art
    with pytest.raises(BeitragsreduktionFehler, match="unbekannte Vorgangsart"):
        pruefe_vorgangsjahr(MP, 3, "XYZ")


@pytest.mark.parametrize("art", sorted(GRENZEN))
def test_die_gueltigen_grenzwerte_werden_gerechnet(art):
    bauen, _, erster, letzter, _ = GRENZEN[art]
    bauen(erster)
    bauen(letzter)


@pytest.mark.parametrize("art", sorted(GRENZEN))
@pytest.mark.parametrize("seite", ["unten", "oben"])
def test_die_ungueltigen_grenzwerte_werden_benannt_verweigert(art, seite):
    """Auf eab5a57 rot fuer RED/TKU/PEX unten (Jahr 0 gerechnet) und PEX oben
    (Freistellung am Beitragsende gerechnet). Die Meldung nennt den Ausweg."""
    bauen, unten, _, _, oben = GRENZEN[art]
    jahr = unten if seite == "unten" else oben
    with pytest.raises(VorgangsfolgeFehler) as info:
        bauen(jahr)
    assert "Ausweg" in str(info.value), str(info.value)


@pytest.mark.parametrize("verfahren", [PROSPEKTIV, MIT_ABZUG, TEILKUENDIGUNG])
def test_auch_die_einzelreduktion_verweigert_das_jahr_null(verfahren):
    """Dieselbe Wache am Einzelweg (``reduziere``), den die Umkehrung der
    Migration noch ruft — die Grenze steht an einer Stelle."""
    with pytest.raises(BeitragsreduktionFehler, match="Vertragsjahr 0"):
        reduziere(GRUND, 0, 0.6, verfahren=verfahren)
    reduziere(GRUND, 1, 0.6, verfahren=verfahren)
