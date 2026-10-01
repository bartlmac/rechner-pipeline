"""Die Vorgangsfolge ueber GENERIERTE Folgen — Eigenschaften statt Aufzaehlung.

Beliebig viele Vorgaenge in jeder Reihenfolge (Entscheid des Maintainers
2026-10-01) sind nicht aufzaehlbar; die Tabelle der Kombinationen im
Tarifplan (klv.md 7.3) zeigt eine Auswahl. Dieses Modul deckt die MENGE ab:
``hypothesis`` erzeugt Folgen aus Beitragsherabsetzungen (prospektiv, mit
Abzug), Teilkuendigungen, einer Beitragsfreistellung und Erhoehungsscheiben,
mit und ohne Abzug je Baustein und beiden Umfaengen der Teilkuendigung, und
haelt jede gegen Invarianten:

* Nichts unter null: keine Summe, kein Rueckkaufswert, keine Auszahlung.
* Was die PLV-Welt ausschliesst — ein Vorgang ausserhalb ``0 < a < n``,
  Herabsetzung oder Beitragsfreistellung ab dem Beitragsende, Herabsetzung
  nach der Beitragsfreistellung, zwei
  gleiche Vorgaenge an einem Jahrestag —, wird
  in JEDER Folge benannt verweigert (``VorgangsfolgeFehler`` mit Ausweg), nie
  still gerechnet.
* Nach jedem Vorgang ist der Zustand der, den jeder Leser rechnet: das
  Ergebnis des Vorgangs (Soll der Buchung, Groesse des GeVo-Tests) ist der
  Zustand, den die Bewertung am Wirkungstag liest.
* Zwei Teilkuendigungen sind vertauschbar und gleich der einen mit dem
  Produkt der Anteile (gegen den gewoehnlichen Kern).
* Eine Teilkuendigung nach der Beitragsfreistellung aendert die beitragsfreie
  Summe genau proportional.
* Ein Vorgang mit Anteil 1 aendert nichts.

Deterministisch: ``derandomize=True``, begrenzte Beispielzahl, keine
Datenbank — die Suite bleibt reproduzierbar und schnell.

Knoten: klv
"""

from __future__ import annotations

import dataclasses
import math

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from rechner_pipeline.kern import KLV_DEFAULT, Rechenkern, erhoehungs_scheibe
from rechner_pipeline.kern.beitragsreduktion import MIT_ABZUG, PROSPEKTIV, TEILKUENDIGUNG
from rechner_pipeline.kern.vorgangsfolge import (
    RED,
    TKU,
    UMFANG_ALLE,
    UMFANG_GRUND,
    Vorgangsfolge,
    VorgangsfolgeFehler,
    vorgang,
)

MP = dataclasses.replace(KLV_DEFAULT, n=25, t=18, stoab_min=50.0, stoab_max=200.0,
                         stoab_satz=0.005)
GRUND = Rechenkern(MP)
EINSTELLUNG = settings(max_examples=60, derandomize=True, deadline=None, database=None,
                       suppress_health_check=[HealthCheck.too_slow])

_ANTEIL = st.sampled_from([0.3, 0.55, 0.8, 0.95])


@st.composite
def folgen(draw):
    """Eine Folge: Scheiben (0 bis 2), eine Beitragsfreistellung oder keine,
    1 bis 4 Vorgaenge, Tarifwerk."""
    # Die Grenzen der Menge gehoeren in die Erzeugung (Pruefrunde G, Fund
    # G02): Jahr 0 und der Ablauf fuer jede Art, die Freistellung bis zum
    # Ablauf (verweigert ab dem Beitragsende). Vorher zog die Erzeugung nur aus dem Inneren der
    # Menge, und die Verweigerung am Rand war ungeprueft.
    pex = draw(st.one_of(st.none(), st.integers(0, MP.n)))
    obergrenze = min(pex - 1, MP.t - 1) if pex is not None else MP.t - 1
    jahre = draw(st.lists(st.integers(1, max(1, obergrenze)), max_size=2, unique=True)) \
        if obergrenze >= 1 else []
    scheiben = [(j, Rechenkern(erhoehungs_scheibe(MP, j, 4000.0 + 500.0 * j)))
                for j in sorted(jahre)]
    vorgaenge = draw(st.lists(st.tuples(
        st.sampled_from([PROSPEKTIV, MIT_ABZUG, TEILKUENDIGUNG]),
        st.integers(0, MP.n), _ANTEIL), min_size=1, max_size=4))
    return {
        "scheiben": scheiben, "pex": pex,
        "vorgaenge": [vorgang(j, a, v) for v, j, a in vorgaenge],
        "je_baustein": draw(st.booleans()),
        "umfang": draw(st.sampled_from([UMFANG_ALLE, UMFANG_GRUND])),
    }


def _ausgeschlossen(f) -> bool:
    """Was die PLV-Welt ausschliesst — unabhaengig von der Folge berechnet."""
    schluessel = [(v.jahr, v.art) for v in f["vorgaenge"]]
    if len(schluessel) != len(set(schluessel)):
        return True
    if f["pex"] is not None and not 0 < f["pex"] < MP.t:
        return True
    for v in f["vorgaenge"]:
        if not 0 < v.jahr < MP.n:
            return True
        if v.art == RED and (v.jahr >= MP.t or (f["pex"] is not None and v.jahr >= f["pex"])):
            return True
    return False


def _bauen(f):
    return Vorgangsfolge(GRUND, f["scheiben"], f["vorgaenge"], pex_jahr=f["pex"],
                         stoab_je_baustein=f["je_baustein"], tku_umfang=f["umfang"])


@EINSTELLUNG
@given(folgen())
def test_jede_folge_wird_gerechnet_oder_benannt_verweigert(f):
    if _ausgeschlossen(f):
        with pytest.raises(VorgangsfolgeFehler) as info:
            _bauen(f)
        text = str(info.value)
        assert "Ausweg" in text or "Teilkuendigung" in text, text
        return
    folge = _bauen(f)
    assert len(folge.ergebnisse) == len(f["vorgaenge"])
    for e in folge.ergebnisse:
        assert e.vs_neu >= 0.0 and math.isfinite(e.vs_neu)
        assert e.auszahlung is None or e.auszahlung >= 0.0
        # Der Zustand nach dem Vorgang ist der, den die Bewertung liest
        # (ohne Korrekturschicht ist dk_nach das Deckungskapital).
        monate = 12 * e.vorgang.jahr
        # Der Zustand unmittelbar nach dem Vorgang (vor dem naechsten des Tages).
        stand = folge.stand_vor(e.vorgang.jahr, "TKU" if e.vorgang.art == RED else "ERH")
        assert stand.werte(monate)["deckungskapital"] == pytest.approx(e.dk_nach, rel=1e-12, abs=1e-9)
    for monate in range(0, 12 * MP.n + 1, 13):
        w = folge.stand_am(monate).werte(monate)
        assert w["rueckkaufswert"] >= 0.0
        assert w["leistung"] >= 0.0 and w["vs_bfr"] >= 0.0


@EINSTELLUNG
@given(st.integers(1, MP.n - 2), st.integers(1, MP.n - 2), _ANTEIL, _ANTEIL, st.booleans())
def test_zwei_teilkuendigungen_sind_vertauschbar_und_das_produkt(j1, j2, f1, f2, je_baustein):
    """Gegen den gewoehnlichen Kern mit f1 x f2 x S (ohne Scheiben)."""
    if j1 == j2:
        j2 = j1 + 1
    a, b = sorted((j1, j2))
    eins = Vorgangsfolge(GRUND, [], [vorgang(a, f1, TEILKUENDIGUNG), vorgang(b, f2, TEILKUENDIGUNG)],
                         stoab_je_baustein=je_baustein, tku_umfang=UMFANG_ALLE)
    zwei = Vorgangsfolge(GRUND, [], [vorgang(a, f2, TEILKUENDIGUNG), vorgang(b, f1, TEILKUENDIGUNG)],
                         stoab_je_baustein=je_baustein, tku_umfang=UMFANG_ALLE)
    kontrolle = Rechenkern(dataclasses.replace(MP, sum_insured=f1 * f2 * MP.sum_insured))
    for monate in (12 * b, 12 * b + 5, 12 * MP.n):
        x = eins.stand_am(monate).reserve(monate)
        y = zwei.stand_am(monate).reserve(monate)
        z = kontrolle.monatsreserve(monate)
        for feld in ("drx_bpfl", "vx_mrv", "rkw"):
            assert getattr(x, feld) == pytest.approx(getattr(y, feld), rel=1e-12, abs=1e-9)
            assert getattr(x, feld) == pytest.approx(getattr(z, feld), rel=1e-12, abs=1e-9)


@EINSTELLUNG
@given(st.integers(2, MP.t - 1), st.integers(0, 6), _ANTEIL, st.booleans())
def test_teilkuendigung_nach_pex_kuerzt_die_beitragsfreie_summe_proportional(pex, nach, f, je_b):
    jahr = min(pex + nach, MP.n - 1)
    ohne = Vorgangsfolge(GRUND, [], [], pex_jahr=pex, stoab_je_baustein=je_b,
                         tku_umfang=UMFANG_ALLE)
    mit = Vorgangsfolge(GRUND, [], [vorgang(jahr, f, TEILKUENDIGUNG)], pex_jahr=pex,
                        stoab_je_baustein=je_b, tku_umfang=UMFANG_ALLE)
    assert mit.stand_am(12 * jahr).vs_bfr() == pytest.approx(
        f * ohne.stand_am(12 * jahr).vs_bfr(), rel=1e-12)
    assert mit.stand_am(12 * jahr).vs_bfr() == pytest.approx(
        f * GRUND.beitragsfreie_summe(pex), rel=1e-12)


@EINSTELLUNG
@given(folgen(), st.sampled_from([PROSPEKTIV, MIT_ABZUG, TEILKUENDIGUNG]), st.integers(1, MP.n - 1))
def test_ein_vorgang_mit_anteil_eins_aendert_nichts(f, verfahren, jahr):
    if _ausgeschlossen(f):
        return
    zusatz = vorgang(jahr, 1.0, verfahren)
    mit_f = dict(f, vorgaenge=f["vorgaenge"] + [zusatz])
    if _ausgeschlossen(mit_f):
        return
    basis, mit = _bauen(f), _bauen(mit_f)
    for monate in range(12 * jahr, 12 * MP.n + 1, 17):
        a = basis.stand_am(monate).werte(monate)
        b = mit.stand_am(monate).werte(monate)
        for feld in ("deckungskapital", "rueckkaufswert", "leistung", "vs_bfr"):
            assert b[feld] == pytest.approx(a[feld], rel=1e-12, abs=1e-9), (feld, monate)
