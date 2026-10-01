"""Runde F, Bereich Kern — drei Funde der Herabsetzung (Sollrechnung des Angreifers).

1. **Herabsetzung mit Abzug, ein Baustein mit negativem Rueckkaufs-Track.**
   ``reduziere_geschichtet`` bildete den Faktor RKW / V^MRV aus der
   UNBEGRENZTEN Summe der Baustein-Werte; in die Umwandlung geht aber nur
   die Summe der auf null begrenzten Werte. Sobald eine junge Scheibe in
   der Zillmerdauer negativ war, wurde der Faktor groesser als eins, und
   "mit Abzug" lag ueber "prospektiv" (Messfall: KLV x = 18, n = t = 40,
   alpha 0,04, zillmer_dauer 1, Scheibe 20.000 aus Jahr 1, Herabsetzung in
   Jahr 2, f = 0,5, Abzug 0,005 / 50 / 200: Ist 334,40, Soll 114,88).
   Invariante: umgewandelt wird genau (1-f) x RKW des Storno am selben Tag,
   und "mit Abzug" liegt nie ueber "prospektiv" — mit und ohne negativen
   Baustein, bei jedem Abzugsregime, in beiden Tarifwerks-Schaltern.
2. **Beitragsfreie Summe nie negativ (Basisschicht).** Mit zulaessigen
   Parametern (alpha 0,06, zillmer_dauer 2) ist V^MRV im Vertragsjahr 1
   negativ; der Kern rechnete S_bfr = V^MRV / V^bfr ohne Untergrenze, die
   Engine buchte eine negative PEX-Summe, P-B1 wies den eigenen Lauf ab,
   und die Herabsetzung mit f -> 0 (auf null begrenzt) war nicht mehr die
   Beitragsfreistellung. Entscheid des Maintainers 2026-09-30: keine Summe
   der Basisschicht wird negativ — EINE Regel an einem Ort
   (``konventionen.untergrenze_basissumme``), fuer PEX und RED gleich.
3. **Absetzung ableiten (Migrationszugang).** ``leite_absetzung_ab`` nahm
   beim Pauschalabzug (stoab_satz 0, stoab_min > 0) StoAb = 0 an und
   versuchte die Zweige min/max nicht.

Jede Aussage hat ihre Positivkontrolle (dieselbe Rechnung an zulaessiger
Stelle bleibt unveraendert) und einen Zaehltest ueber die Menge, aus der
die Invariante hergeleitet ist.

Knoten: klv
"""

from __future__ import annotations

import ast
import dataclasses
import functools
import itertools
import math
import re
from pathlib import Path

import pytest

from rechner_pipeline.kern import (
    KLV_DEFAULT,
    ModelPoint,
    Rechenkern,
    erhoehungs_scheibe,
    vertrags_monatsreserve,
)
from rechner_pipeline.kern.beitragsreduktion import (
    MIT_ABZUG,
    PROSPEKTIV,
    reduziere_geschichtet,
)

# --------------------------------------------------------------------------- #
# Fund 1: umgewandelt == (1-f) x Storno-RKW, auch mit negativem Baustein
# --------------------------------------------------------------------------- #

#: Die drei Abzugsregime (satz, min, max): Satz mit Grenzen, kein Abzug,
#: Pauschalabzug (Satz 0, min = max > 0).
_REGIME = {
    "satz": (0.005, 50.0, 200.0),
    "kein": (0.0, 0.0, 0.0),
    "pauschal": (0.0, 120.0, 120.0),
}
#: Nur fuer die Saldierung (unten): ein Abzug, der den saldierten Track aufzehrt.
_REGIME_ZUSATZ = {"aufzehrend": (0.0, 400.0, 400.0)}
#: Zillmerdauer 1 -> die Scheibe aus Jahr 1 hat im Jahr 2 einen negativen
#: Rueckkaufs-Track (Kontrolle unten); Zillmerdauer 5 ist die Positivwelt.
_ZILLMER = (1, 5)
_ANTEILE = (1e-6, 0.5, 0.95)
_SCHALTER = (True, False)
_A0 = 2
_E = 1


def _welt(zillmer: int, regime: str):
    satz, umin, umax = {**_REGIME, **_REGIME_ZUSATZ}[regime]
    mp = dataclasses.replace(
        KLV_DEFAULT, x=18, n=40, t=40, sum_insured=100000.0, zins=0.0125,
        tafel="DAV2008_T", alpha=0.04, zillmer_dauer=zillmer,
        stoab_satz=satz, stoab_min=umin, stoab_max=umax)
    scheibe = erhoehungs_scheibe(mp, _E, 20000.0)
    return Rechenkern(mp), Rechenkern(scheibe)


def _storno_von_hand(grund: Rechenkern, scheibe: Rechenkern, je_baustein: bool) -> float:
    """Der RKW, den ein Storno am Jahrestag zahlt — aus den Verlaufszeilen der
    Bausteine und den Grenzen des Tarifwerks, nicht ueber den Kern-Weg
    ``vertrags_monatsreserve`` (der ist der Gegenstand der Kontrolle)."""
    zg, zs = grund.verlaufszeile(_A0), scheibe.verlaufszeile(_A0 - _E)
    mp = grund.mp
    if je_baustein:
        return sum(max(0.0, z.vx_mrv - z.stoab) for z in (zg, zs))
    vs = mp.sum_insured + scheibe.mp.sum_insured
    stoab = min(mp.stoab_max, max(mp.stoab_min, mp.stoab_satz * (vs - zg.drx_bpfl - zs.drx_bpfl)))
    return max(0.0, zg.vx_mrv + zs.vx_mrv - stoab)


def _umgewandelt(teile, f: float) -> float:
    return sum(r.dk_nach - f * r.dk_vor for _, r in teile)


def test_der_negative_baustein_ist_nur_in_der_zillmerdauer_eins_da():
    """Positivkontrolle: Ohne einen Baustein mit V^MRV < 0 waere das Gitter
    unten blind fuer Fund 1; und die Welt mit Zillmerdauer 5 muss ohne
    negativen Baustein sein, sonst unterscheidet das Gitter nichts."""
    for regime in _REGIME:
        grund, scheibe = _welt(1, regime)
        assert scheibe.verlaufszeile(_A0 - _E).vx_mrv < 0.0 < grund.verlaufszeile(_A0).vx_mrv
        grund5, scheibe5 = _welt(5, regime)
        assert min(grund5.verlaufszeile(_A0).vx_mrv, scheibe5.verlaufszeile(_A0 - _E).vx_mrv) > 0.0


def test_der_messfall_des_angreifers():
    """Handrechnung des Angreifers (eigene Tafelarithmetik): V^MRV Grund 429,77,
    Scheibe -282,12; Abzug 0,005 / 50 / 200 -> Storno-RKW 229,77, bei f = 0,5
    umgewandelt 114,88 (Ist vor dem Fix 334,40); ohne Abzug 214,88 (Ist
    625,47); ohne Abzug und f = 1e-6 der Storno-RKW 429,77 (Ist 1.250,94).
    Mutationsprobe: den Faktor in ``reduziere_geschichtet`` wieder aus
    ``gesamt.vx_mrv`` bilden -> rot."""
    for regime, f, soll in (("satz", 0.5, 114.88), ("kein", 0.5, 214.88), ("kein", 1e-6, 429.77)):
        grund, scheibe = _welt(1, regime)
        teile = reduziere_geschichtet(
            grund, [(_E, scheibe)], _A0, f, verfahren=MIT_ABZUG, stoab_je_baustein=True)
        assert _umgewandelt(teile, f) == pytest.approx(soll, abs=0.01), (regime, f)


@pytest.mark.parametrize("zillmer", _ZILLMER)
@pytest.mark.parametrize("regime", sorted(_REGIME))
@pytest.mark.parametrize("f", _ANTEILE)
@pytest.mark.parametrize("je_baustein", _SCHALTER)
def test_mit_abzug_wandelt_genau_den_storno_rkw_um_und_liegt_nie_ueber_prospektiv(
        zillmer, regime, f, je_baustein):
    """Runde F, F1. Die Invariante ueber das Gitter (negativer Baustein ja/nein,
    drei Abzugsregime, f klein/mittel/gross, beide Schalter): die Summe der
    umgewandelten Teile ist (1-f) x Storno-RKW — von Hand aus den
    Verlaufszeilen UND ueber ``vertrags_monatsreserve`` — und die Summe nach
    der Herabsetzung mit Abzug liegt nie ueber der prospektiven."""
    grund, scheibe = _welt(zillmer, regime)
    teile_k = [(_E, scheibe)]
    mit = reduziere_geschichtet(grund, teile_k, _A0, f, verfahren=MIT_ABZUG,
                                stoab_je_baustein=je_baustein)
    pro = reduziere_geschichtet(grund, teile_k, _A0, f, verfahren=PROSPEKTIV,
                                stoab_je_baustein=je_baustein)
    storno_hand = _storno_von_hand(grund, scheibe, je_baustein)
    storno_kern = vertrags_monatsreserve(
        grund, teile_k, 12 * _A0, stoab_je_baustein=je_baustein).rkw
    assert storno_hand == pytest.approx(storno_kern, rel=1e-12, abs=1e-9)
    assert _umgewandelt(mit, f) == pytest.approx((1.0 - f) * storno_hand, rel=1e-9, abs=1e-9)
    assert sum(r.vs_neu for _, r in mit) <= sum(r.vs_neu for _, r in pro) + 1e-9
    assert _umgewandelt(mit, f) <= _umgewandelt(pro, f) + 1e-9
    # Kein Baustein bekommt eine negative umgewandelte Summe (Floor je Schicht).
    for _, r in mit:
        assert r.dk_nach - f * r.dk_vor >= -1e-12


def test_das_gitter_von_fund_1_hat_die_hergeleitete_groesse():
    """Zaehltest je Instanz: Das Gitter oben hat 2 x 3 x 3 x 2 = 36 Zellen; eine
    stillschweigend verkuerzte Parametrisierung faellt hier auf (== statt >=)."""
    zellen = list(itertools.product(_ZILLMER, _REGIME, _ANTEILE, _SCHALTER))
    assert len(zellen) == 36
    assert len({(z, r) for z, r, _, _ in zellen}) == 6


def _soll_je_schicht(grund: Rechenkern, scheibe: Rechenkern, f: float,
                     verfahren: str, je_baustein: bool):
    """Die ganze Tabelle der Herabsetzung, je Schicht, aus den Verlaufszeilen von
    Hand (nicht ueber ``reduziere_geschichtet`` und nicht ueber den Kern-Weg
    ``vertrags_monatsreserve``): (vs_neu, dk_vor, dk_nach) je Schicht.

    Der umgewandelte Teil je Schicht (Runde F, Nachbesserung 2 — die Fassung des
    Auftrags: verteilt nach dem geklemmten Baustein-RKW):

    * prospektiv: ``(1-f) x max(0, V^MRV_i)``;
    * mit Abzug, Abzug je Baustein: ``(1-f) x RKW_i`` mit dem EIGENEN Abzug
      des Bausteins, ``RKW_i = max(0, V^MRV_i - StoAb_i)`` — jeder Baustein
      wandelt genau den Rueckkaufswert um, den sein Storno zahlt;
    * mit Abzug, Abzug je Vertrag: der Vertrags-RKW ``max(0, sum V^MRV - StoAb)``
      verteilt nach dem auf null begrenzten Rueckkaufs-Track des Bausteins
      (die Baustein-Groesse, auf der der vertragsweite Abzug aufsitzt).
    """
    mp = grund.mp
    teile = ((grund, _A0), (scheibe, _A0 - _E))
    z = [k.verlaufszeile(a) for k, a in teile]
    summen = [k.mp.sum_insured for k, _ in teile]
    pos = [max(0.0, zi.vx_mrv) for zi in z]
    if verfahren == "prospektiv":
        umg = [(1.0 - f) * p for p in pos]
    elif je_baustein:
        umg = []
        for zi, vs_i in zip(z, summen):
            stoab = min(mp.stoab_max, max(mp.stoab_min, mp.stoab_satz * (vs_i - zi.drx_bpfl)))
            umg.append((1.0 - f) * max(0.0, zi.vx_mrv - stoab))
    else:
        stoab = min(mp.stoab_max, max(mp.stoab_min, mp.stoab_satz * (
            sum(summen) - sum(zi.drx_bpfl for zi in z))))
        rkw = max(0.0, sum(zi.vx_mrv for zi in z) - stoab)
        umg = [(1.0 - f) * rkw * p / sum(pos) for p in pos]
    return [(f * vs_i + u / zi.vx_bfr, zi.drx_bpfl, f * zi.drx_bpfl + u)
            for vs_i, zi, u in zip(summen, z, umg)]


@pytest.mark.parametrize("zillmer", _ZILLMER)
@pytest.mark.parametrize("regime", sorted(_REGIME))
@pytest.mark.parametrize("f", _ANTEILE)
@pytest.mark.parametrize("je_baustein", _SCHALTER)
@pytest.mark.parametrize("verfahren", (MIT_ABZUG, PROSPEKTIV))
def test_die_werte_je_schicht_folgen_der_eigenen_sollrechnung(
        zillmer, regime, f, je_baustein, verfahren):
    """Runde F, Nachbesserung 2: nicht nur die SUMME, die ganze Tabelle. Je
    Schicht (Grund, Scheibe) stimmen Summe nach der Herabsetzung, Reserve vor
    und Reserve nach mit der Sollrechnung aus den Verlaufszeilen ueberein —
    mit Abzug je Baustein wandelt jeder Baustein SEINEN Rueckkaufswert um (die
    Summe war schon richtig, die Verteilung auf die Schichten nicht: ein
    gemeinsamer Faktor RKW_ges / sum max(0, V^MRV) verschob Geld vom Baustein mit
    dem kleineren Abzug zu dem mit dem groesseren). Mutationsprobe: den Faktor je
    Baustein wieder gemeinsam bilden -> rot."""
    grund, scheibe = _welt(zillmer, regime)
    ist = reduziere_geschichtet(grund, [(_E, scheibe)], _A0, f, verfahren=verfahren,
                                stoab_je_baustein=je_baustein)
    soll = _soll_je_schicht(grund, scheibe, f, verfahren, je_baustein)
    assert [e for e, _ in ist] == [0, _E]
    for (_, r), (vs_neu, dk_vor, dk_nach) in zip(ist, soll):
        assert r.vs_neu == pytest.approx(vs_neu, rel=1e-9, abs=1e-9)
        assert r.dk_vor == pytest.approx(dk_vor, rel=1e-9, abs=1e-9)
        assert r.dk_nach == pytest.approx(dk_nach, rel=1e-9, abs=1e-9)


def test_die_verteilung_je_baustein_unterscheidet_sich_vom_gemeinsamen_faktor():
    """Positivkontrolle zum Test oben: In der Welt ``satz`` / Zillmerdauer 5 haben
    Grund und Scheibe verschiedene Abzuege (Grund an der Obergrenze 200, Scheibe
    im Satzbereich bei 101,41), und die beiden Verteilungen (Baustein-RKW gegen
    gemeinsamer Faktor ueber max(0, V^MRV)) geben je Schicht verschiedene Werte
    bei GLEICHER Summe (Grund 1.202,93 / Scheibe 86,92 gegen 1.166,62 / 123,23)
    — sonst unterschiede der Test oben die Fassungen nicht."""
    grund, scheibe = _welt(5, "satz")
    f = 0.5
    z = [grund.verlaufszeile(_A0), scheibe.verlaufszeile(_A0 - _E)]
    assert z[0].stoab != z[1].stoab
    je_b = [d[2] - f * d[1] for d in _soll_je_schicht(grund, scheibe, f, MIT_ABZUG, True)]
    # Die alte Verteilung: gemeinsamer Faktor RKW_ges / sum max(0, V^MRV).
    rkw = sum(max(0.0, zi.vx_mrv - zi.stoab) for zi in z)
    pos = sum(max(0.0, zi.vx_mrv) for zi in z)
    alt = [(1.0 - f) * rkw * max(0.0, zi.vx_mrv) / pos for zi in z]
    assert sum(je_b) == pytest.approx(sum(alt), rel=1e-12)
    assert je_b == pytest.approx([1202.93, 86.92], abs=0.01)
    assert alt == pytest.approx([1166.62, 123.23], abs=0.01)


@pytest.mark.parametrize("regime", sorted({**_REGIME, **_REGIME_ZUSATZ}))
@pytest.mark.parametrize("je_baustein", _SCHALTER)
def test_mit_abzug_liegt_um_abzug_plus_saldo_unter_prospektiv(regime, je_baustein):
    """Runde F, Nachbesserung 3 (Tarifplan klv.md 7.1, „Saldierung beim
    vertragsweiten Tarifwerk"): Der Satz „die mit Abzug liegt um den Stornoabzug
    darunter" gilt mit einem negativen Baustein nur beim Abzug je Baustein. Der
    Abstand der umgewandelten Summen (prospektiv minus mit Abzug) ist

    * je Baustein: (1-f) x sum_i min(StoAb_i, max(0, V^MRV_i)) — ein negativer
      Baustein traegt nichts bei;
    * je Vertrag: (1-f) x (StoAb + sum_i max(0, -V^MRV_i)), solange der
      Vertrags-RKW positiv ist, sonst (1-f) x sum_i max(0, V^MRV_i) — die
      Saldierung im Storno-RKW kommt zum Abzug hinzu.

    Alles von Hand aus den Verlaufszeilen, in der Welt mit negativem Baustein
    (Zillmerdauer 1)."""
    f = 0.5
    grund, scheibe = _welt(1, regime)
    mp = grund.mp
    z = [grund.verlaufszeile(_A0), scheibe.verlaufszeile(_A0 - _E)]
    assert z[1].vx_mrv < 0.0 < z[0].vx_mrv
    teile = [(_E, scheibe)]
    mit = reduziere_geschichtet(grund, teile, _A0, f, verfahren=MIT_ABZUG,
                                stoab_je_baustein=je_baustein)
    pro = reduziere_geschichtet(grund, teile, _A0, f, verfahren=PROSPEKTIV,
                                stoab_je_baustein=je_baustein)
    abstand = _umgewandelt(pro, f) - _umgewandelt(mit, f)
    summen = (mp.sum_insured, scheibe.mp.sum_insured)
    if je_baustein:
        stoab = [min(mp.stoab_max, max(mp.stoab_min, mp.stoab_satz * (vs - zi.drx_bpfl)))
                 for vs, zi in zip(summen, z)]
        soll = (1.0 - f) * sum(min(a, max(0.0, zi.vx_mrv)) for a, zi in zip(stoab, z))
    else:
        stoab = min(mp.stoab_max, max(mp.stoab_min, mp.stoab_satz * (
            sum(summen) - sum(zi.drx_bpfl for zi in z))))
        saldo = sum(zi.vx_mrv for zi in z)
        if saldo - stoab > 0.0:
            soll = (1.0 - f) * (stoab + sum(max(0.0, -zi.vx_mrv) for zi in z))
        else:
            soll = (1.0 - f) * sum(max(0.0, zi.vx_mrv) for zi in z)
    assert abstand == pytest.approx(soll, rel=1e-9, abs=1e-9)


# --------------------------------------------------------------------------- #
# Fund 1 im Engine-Weg: Fortschreibung (CLI) + P-B1
# --------------------------------------------------------------------------- #

import datetime as _dt

import pandas as pd

from rechner_pipeline.bestand import cli_fortschreibung as _fs
from rechner_pipeline.bestand.config import load_config
from rechner_pipeline.bestand.manifest import lauf_eingaben, lies_manifest
from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
from rechner_pipeline.bestand.vorbedingungen import lies_und_pruefe_pb1
from rechner_pipeline.models.bestand import model_point_kwargs
from tests.test_bestand_uebernommen_fortschreiben import _CONFIG_TOML, _stamm

_BIS = "2030-01-01"


def _engine_config(zillmer: int, verfahren: str) -> str:
    """Eine Generation mit Abzug je Baustein und kurzer Zillmerdauer; hohe
    Raten fuer Erhoehung und Herabsetzung, damit die Scheibe bei der
    Herabsetzung jung ist (die Raten sind die der Angriffswelt)."""
    text = _CONFIG_TOML.replace("alpha = 0.025", "alpha = 0.04").replace(
        "min_rlz_flex = 5",
        "min_rlz_flex = 5\nstoab_satz = 0.005\nstoab_min = 50.0\nstoab_max = 200.0\n"
        f"zillmer_dauer = {zillmer}\nstoab_je_baustein = true\nred_verfahren = \"{verfahren}\"")
    text = text.replace("[annahmen]\nerh_prozent = 0.05",
                        "[annahmen]\nerh_prozent = 0.05\nred_anteil = 0.5")
    text = text.replace("[annahmen.erhoehung]\na = 0.05", "[annahmen.erhoehung]\na = 0.9")
    text = text.replace("[annahmen.storno]\na = 0.02", "[annahmen.storno]\na = 0.0")
    text = text.replace("[annahmen.beitragsfreistellung]\na = 0.02",
                        "[annahmen.beitragsfreistellung]\na = 0.0")
    return text + "\n[annahmen.herabsetzung]\na = 0.5\nb = 0.0\n"


def _engine_lauf(tmp_path: Path, zillmer: int, verfahren: str) -> dict:
    d = tmp_path / f"zd{zillmer}_{verfahren}"
    d.mkdir()
    cfg = d / "config.toml"
    cfg.write_text(_engine_config(zillmer, verfahren), encoding="utf-8")
    st = _stamm([{"id": 5000 + i, "beginn": "2020-01-01", "n": 40, "t": 40} for i in range(40)])
    st["entry_age"] = 18
    st["date_of_birth"] = pd.Timestamp("2002-01-01")
    portfolio = d / "portfolio.parquet"
    write_portfolio(st, portfolio)
    out = d / "lauf"
    assert _fs.main(["--config", str(cfg), "--bis", _BIS, "--portfolio", str(portfolio),
                     "--out-dir", str(out)]) == 0
    _t, _g, fehler, usage = lies_und_pruefe_pb1(
        lauf_eingaben(out, cfg), bis=_dt.date.fromisoformat(_BIS), manifest=lies_manifest(out))
    return {"cfg": cfg, "stamm": st, "ledger": read_portfolio(out / "ledger.parquet"),
            "red": read_portfolio(out / "reduktionen.parquet"),
            "scheiben": read_portfolio(out / "scheiben.parquet"), "pb1": fehler + usage}


@pytest.fixture(scope="module")
def engine_welten(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("runde_f_f1")
    return {(zd, v): _engine_lauf(tmp, zd, v)
            for zd in (5, 1) for v in ("prospektiv", "mit_abzug")}


def _bausteine(welt: dict, pid: int, a0: int):
    """Grund- und Erhoehungskerne einer Police am Reduktionsjahr, aus Stamm,
    Config und scheiben.parquet (nicht aus der Engine)."""
    gen = load_config(welt["cfg"]).generationen[0].generation_fields()
    zeile = welt["stamm"][welt["stamm"].police_id == pid].iloc[0].to_dict()
    mp = ModelPoint(**model_point_kwargs(zeile, gen))
    sch = welt["scheiben"]
    sch = sch[(sch.police_id == pid) & (sch.erhoehung_jahr < a0)]
    return mp, [(int(e), Rechenkern(erhoehungs_scheibe(mp, int(e), float(v))))
                for e, v in zip(sch.erhoehung_jahr, sch.sum_insured)]


@pytest.mark.parametrize("zillmer", [5, 1])
def test_engine_mit_abzug_liegt_nie_ueber_prospektiv_und_p_b1_nimmt_den_lauf_ab(
        engine_welten, zillmer):
    """Runde F, F1 im oeffentlichen Weg. Je Police mit Herabsetzung: die
    Summe mit Abzug ist hoechstens die prospektive, und sie liegt unter der
    Schranke, die aus dem Storno-RKW folgt (alles umgewandelte Geld in den
    Baustein mit dem kleinsten beitragsfreien Reservesatz). Positivkontrolle:
    in der Welt mit Zillmerdauer 1 hat mindestens eine Herabsetzung einen
    Baustein mit negativem Rueckkaufs-Track, in der mit Zillmerdauer 5 keine.
    Mutationsprobe: den Faktor wieder aus ``gesamt.vx_mrv`` bilden -> rot."""
    pro = engine_welten[(zillmer, "prospektiv")]
    abz = engine_welten[(zillmer, "mit_abzug")]
    assert pro["pb1"] == [] and abz["pb1"] == []
    led = lambda w: w["ledger"][w["ledger"].ereignis == "RED"].set_index("police_id").betrag
    vp, va = led(pro), led(abz)
    gemeinsam = sorted(set(vp.index) & set(va.index))
    assert len(gemeinsam) >= 10, "Welt ohne Herabsetzungen waere blind"
    mit_negativem = 0
    for pid in gemeinsam:
        r = abz["red"][abz["red"].police_id == pid].iloc[0]
        a0, f = int(r.reduktion_jahr), float(r.anteil)
        mp, scheiben = _bausteine(abz, pid, a0)
        kerne = [(0, Rechenkern(mp))] + [(e, k) for e, k in scheiben]
        zeilen = [k.verlaufszeile(a0 - e) for e, k in kerne]
        mit_negativem += any(z.vx_mrv < 0.0 for z in zeilen)
        assert va[pid] <= vp[pid] + 0.005, (pid, a0, va[pid], vp[pid])
        rkw = vertrags_monatsreserve(kerne[0][1], kerne[1:], 12 * a0, stoab_je_baustein=True).rkw
        schranke = (sum(f * k.mp.sum_insured for _, k in kerne)
                    + (1.0 - f) * rkw / min(z.vx_bfr for z in zeilen))
        assert va[pid] <= schranke + 0.005, (pid, a0, va[pid], schranke)
    assert (mit_negativem > 0) == (zillmer == 1)


# --------------------------------------------------------------------------- #
# Fund 2: keine negative beitragsfreie Summe der Basisschicht
# --------------------------------------------------------------------------- #

from rechner_pipeline.bestand.config import config_aus_text
from rechner_pipeline.bestand.ereignisse import fortschreiben
from rechner_pipeline.bestand.ledger_bindung import pruefe_ledger_betraege
from rechner_pipeline.kern import beitragsreduktion as _br
from rechner_pipeline.kern import konventionen as _konv
from rechner_pipeline.kern.beitragsreduktion import ReduzierterVertrag, reduziere
from rechner_pipeline.kern.produkte import klv as _klv
from rechner_pipeline.models.bestand import validate_ledger

#: (alpha, zillmer_dauer): Standard, und zwei zulaessige Paare, bei denen V^MRV
#: in der Zillmerdauer negativ ist (Messung der Suche, klv.md 7.1).
_PAARE = ((0.025, 5), (0.06, 2), (0.04, 1))
_PUNKTE = ((18, 40), (45, 30))


def _f2_kern(alpha: float, zillmer: int, x: int, n: int) -> Rechenkern:
    return Rechenkern(dataclasses.replace(
        KLV_DEFAULT, x=x, n=n, t=n, sum_insured=100000.0, zins=0.0125,
        tafel="DAV2008_T", alpha=alpha, zillmer_dauer=zillmer))


def _f2_zellen():
    for (alpha, zd), (x, n) in itertools.product(_PAARE, _PUNKTE):
        kern = _f2_kern(alpha, zd, x, n)
        for a0 in range(0, n):
            yield alpha, zd, x, n, a0, kern


def test_die_suche_von_fund_2_hat_negative_und_positive_zellen():
    """Positivkontrolle und Zaehltest je Instanz: Die Zellen (3 Paare x 2
    Vertragspunkte x Vertragsjahre 0..n-1 = 3 x (40 + 30) = 210) enthalten
    Jahre mit rohem V^MRV < 0 — ohne sie waere die Untergrenze nie
    geprueft — und die Standardwelt (alpha 0,025, zillmer_dauer 5) hat keines."""
    zellen = list(_f2_zellen())
    assert len(zellen) == 210
    # Schwelle -1 EUR: im Vertragsjahr 0 steht rechnerisches Rauschen (-0.0).
    negativ = {(a, zd) for a, zd, _x, _n, a0, k in zellen if k.verlaufszeile(a0).vx_mrv < -1.0}
    assert negativ == {(0.06, 2), (0.04, 1)}


def test_die_beitragsfreie_summe_ist_nie_negativ_und_sonst_die_tarifformel():
    """Runde F, F2. Fuer jede Zelle: PEX-Summe = max(0, V^MRV / V^bfr) vor dem
    Beitragsende (Handrechnung aus der Verlaufszeile, nicht die Kern-Methode);
    ab dem Beitragsende unveraendert. Mutationsprobe: die Untergrenze in
    ``KLVProdukt.beitragsfreie_summe`` entfernen -> rot."""
    for alpha, zd, x, n, a0, kern in _f2_zellen():
        z = kern.verlaufszeile(a0)
        soll = max(0.0, z.vx_mrv / z.vx_bfr)
        assert kern.beitragsfreie_summe(a0) == pytest.approx(soll, rel=1e-12, abs=1e-12), (
            alpha, zd, x, a0)
        assert kern.beitragsfreie_summe(a0) >= 0.0


def test_die_herabsetzung_mit_f_gegen_null_ist_die_beitragsfreistellung():
    """Runde F, F2. ``f = 0 == PEX`` in jeder Zelle, auch dort, wo V^MRV
    negativ ist (beide null). Gegen die Kern-Methode ``beitragsfreie_summe``,
    ein eigener Weg als ``reduziere``. Mutationsprobe: die Untergrenze in
    ``_reduziere_eine_schicht`` entfernen -> rot (negative Summe)."""
    for alpha, zd, x, n, a0, kern in _f2_zellen():
        if a0 == 0:
            continue
        red = reduziere(kern, a0, 0.0, verfahren=PROSPEKTIV)
        assert red.vs_neu == pytest.approx(kern.beitragsfreie_summe(a0), rel=1e-6, abs=1e-6), (
            alpha, zd, x, a0)


def test_die_summe_nach_spaeterer_beitragsfreistellung_ist_nie_negativ():
    """Die dritte Stelle der Regel: Beitragsfreistellung NACH einer
    Herabsetzung (``ReduzierterVertrag.beitragsfreie_summe``) und die Reserve
    darauf. Mutationsprobe: die Untergrenze dort entfernen -> rot."""
    kern = _f2_kern(0.06, 2, 18, 40)
    assert kern.verlaufszeile(1).vx_mrv < 0.0, "Positivkontrolle: negatives V^MRV in Jahr 1"
    rv = ReduzierterVertrag.nach(kern, 1, 0.5, verfahren=PROSPEKTIV)
    assert rv.beitragsfreie_summe(1) == 0.0
    assert rv.reserve_beitragsfrei(1, 12) >= 0.0
    # Positivkontrolle: im Standardfall unveraendert und positiv.
    std = _f2_kern(0.025, 5, 18, 40)
    assert ReduzierterVertrag.nach(std, 1, 0.5, verfahren=PROSPEKTIV).beitragsfreie_summe(1) > 0.0


_PAKET = Path(_br.__file__).resolve().parent.parent       # src/rechner_pipeline
#: Die Stellen, die eine Summe der Basisschicht bilden — GENAU diese rufen
#: ``untergrenze_basissumme`` ab (Pfad im Paket, qualifizierter Funktionsname).
_RATSCHE_STELLEN = {
    ("kern/produkte/klv.py", "KLV.beitragsfreie_summe"),
    ("kern/beitragsreduktion.py", "_reduziere_eine_schicht"),
    ("kern/beitragsreduktion.py", "ReduzierterVertrag.beitragsfreie_summe"),
}
_REGEL = "untergrenze_basissumme"


class _Sammler(ast.NodeVisitor):
    """Sammelt je innerster umschliessender Funktion die Aufrufe der Regel und
    die Aufrufe von ``max`` mit einer Null als Argument (die Abschrift)."""

    def __init__(self) -> None:
        self.pfad: list[str] = []
        self.regel: list[str] = []
        self.max_null: list[str] = []
        self.aliase: list[str] = []

    def _stelle(self) -> str:
        return ".".join(self.pfad) or "<modul>"

    def _betritt(self, node) -> None:
        self.pfad.append(node.name)
        self.generic_visit(node)
        self.pfad.pop()

    visit_ClassDef = visit_FunctionDef = visit_AsyncFunctionDef = _betritt

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.aliase += [a.asname for a in node.names if a.name == _REGEL and a.asname]
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        f = node.func
        name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
        if name == _REGEL:
            self.regel.append(self._stelle())
        elif isinstance(f, ast.Name) and f.id == "max" and any(
                isinstance(a, ast.Constant) and not isinstance(a.value, bool)
                and a.value == 0 for a in node.args):
            self.max_null.append(self._stelle())
        self.generic_visit(node)


def _ratsche_befunde(quellen: dict) -> list:
    """Die Ratsche ueber den Quelltext (Pfad im Paket -> Text): genau drei
    Aufrufstellen der Regel, in den benannten Funktionen (``==``, nicht
    ``>=``), kein Alias, und dort KEINE Abschrift (``max(0, ...)``)."""
    befunde, aufrufe = [], []
    for pfad, text in sorted(quellen.items()):
        sammler = _Sammler()
        sammler.visit(ast.parse(text))
        aufrufe += [(pfad, stelle) for stelle in sammler.regel]
        befunde += [f"{pfad}: Alias {a!r} der Regel" for a in sammler.aliase]
        befunde += [f"{pfad}: Abschrift max(0, ...) in {stelle}"
                    for stelle in sammler.max_null if (pfad, stelle) in _RATSCHE_STELLEN]
    if sorted(aufrufe) != sorted(_RATSCHE_STELLEN):
        befunde.append(f"Aufrufstellen {sorted(aufrufe)} statt {sorted(_RATSCHE_STELLEN)}")
    return befunde


@functools.lru_cache(maxsize=None)
def _paket_quellen_gecacht() -> tuple:
    return tuple(sorted(_paket_quellen_lesen().items()))


def _paket_quellen_lesen() -> dict:
    return {str(f.relative_to(_PAKET)): f.read_text(encoding="utf-8")
            for f in sorted(_PAKET.rglob("*.py"))}


def _paket_quellen() -> dict:
    """Die Quellen des Pakets; gelesen wird je Lauf einmal, die Ratsche
    mutiert nur Kopien."""
    return dict(_paket_quellen_gecacht())


def _abschrift_statt_aufruf(text: str, nr: int) -> str:
    """Der Aufruf Nr. ``nr`` (0-basiert) der Regel als Abschrift: aus
    ``untergrenze_basissumme(X)`` wird ``max(0.0, X)`` (Klammern bleiben)."""
    treffer = list(re.finditer(rf"\b{_REGEL}\(", text))
    return text[:treffer[nr].start()] + "max(0.0, " + text[treffer[nr].end():], len(treffer)


def test_die_untergrenze_der_basissumme_ist_eine_regel_an_einem_ort():
    """Echte Ratsche (AST ueber das ganze Paket, Nachbesserung 4): Die Regel
    ``konventionen.untergrenze_basissumme`` wird an GENAU drei Stellen
    abgerufen — ``KLV.beitragsfreie_summe``, ``_reduziere_eine_schicht``,
    ``ReduzierterVertrag.beitragsfreie_summe`` (``==``) —, und in diesen drei
    Funktionen steht keine ``max(0, ...)``-Abschrift. Vorher pruefte der Test
    nur, dass der importierte Name dieselbe Funktion ist; eine Abschrift an der
    Aufrufstelle liess er durch. Mutationsprobe M4 des Pruefers: an einer Stelle
    ``max(0.0, ...)`` statt des Aufrufs -> rot."""
    assert _ratsche_befunde(_paket_quellen()) == []
    # Die Regel selbst, als Verhalten.
    assert _konv.untergrenze_basissumme(-1.5) == 0.0
    assert _konv.untergrenze_basissumme(2.5) == 2.5


@pytest.mark.parametrize("pfad,stelle,nr", [
    ("kern/produkte/klv.py", "KLV.beitragsfreie_summe", 0),
    ("kern/beitragsreduktion.py", "_reduziere_eine_schicht", 0),
    ("kern/beitragsreduktion.py", "ReduzierterVertrag.beitragsfreie_summe", 1),
])
def test_die_ratsche_findet_die_eingesetzte_abschrift(pfad, stelle, nr):
    """Positivkontrolle der Ratsche: Wird an einer der drei Stellen der Aufruf
    durch die Abschrift ``max(0.0, ...)`` ersetzt (Mutation M4), meldet sie
    sowohl die Abschrift in der benannten Funktion als auch die fehlende
    Aufrufstelle — und die unveraenderten Quellen bleiben ohne Befund."""
    quellen = _paket_quellen()
    assert _ratsche_befunde(quellen) == []
    mutiert, anzahl = _abschrift_statt_aufruf(quellen[pfad], nr)
    assert anzahl == (2 if pfad.endswith("beitragsreduktion.py") else 1)
    befunde = _ratsche_befunde({**quellen, pfad: mutiert})
    assert f"{pfad}: Abschrift max(0, ...) in {stelle}" in befunde
    assert any(b.startswith("Aufrufstellen") for b in befunde)


def test_die_ratsche_findet_eine_vierte_aufrufstelle_und_einen_alias():
    """Positivkontrolle des Umfangs: Eine vierte Aufrufstelle irgendwo im Paket
    (hier in ``zahlungspfad.py``) und ein Alias-Import verletzen die Ratsche
    (``==``, nicht ``>=``)."""
    quellen = _paket_quellen()
    vierte = quellen["kern/zahlungspfad.py"] + (
        "\n\ndef _vierte(x):\n    from rechner_pipeline.kern.konventionen import "
        f"{_REGEL}\n    return {_REGEL}(x)\n")
    befunde = _ratsche_befunde({**quellen, "kern/zahlungspfad.py": vierte})
    assert any(b.startswith("Aufrufstellen") and "_vierte" in b for b in befunde)
    alias = quellen["kern/zahlungspfad.py"] + (
        f"\nfrom rechner_pipeline.kern.konventionen import {_REGEL} as _u\n")
    assert _ratsche_befunde({**quellen, "kern/zahlungspfad.py": alias}) == [
        "kern/zahlungspfad.py: Alias '_u' der Regel"]
    # Eine max(0, ...)-Verwendung ANDERSWO (RKW, Gewichte) ist keine Abschrift der Regel.
    assert _ratsche_befunde(quellen) == []


_F2_CONFIG_ZUSATZ = "zillmer_dauer = 2\n"


def test_die_engine_bucht_keine_negative_pex_summe_und_p_b1_nimmt_den_lauf_ab():
    """Runde F, F2 im Engine-Weg: Generation mit alpha 0,06 und
    zillmer_dauer 2 (die Config-Validierung laesst sie zu), PEX im
    Vertragsjahr 1 oder 2. Vorher: ``VS_bfr`` -2.152,96, ``validate_ledger``
    meldet ``betrag < 0``. Jetzt: nie negativ, beide Pruefer leer."""
    text = _CONFIG_TOML.replace("alpha = 0.025", "alpha = 0.06").replace(
        "min_rlz_flex = 5", "min_rlz_flex = 5\n" + _F2_CONFIG_ZUSATZ)
    text = text.replace("[annahmen.beitragsfreistellung]\na = 0.02",
                        "[annahmen.beitragsfreistellung]\na = 0.9")
    text = text.replace("[annahmen.storno]\na = 0.02", "[annahmen.storno]\na = 0.0")
    cfg = config_aus_text(text)
    assert cfg.validate() == []
    st = _stamm([{"id": i, "beginn": "2020-01-01", "n": 40, "t": 40} for i in range(1, 6)])
    st["entry_age"] = 18
    st["date_of_birth"] = pd.Timestamp("2002-01-01")
    fs = fortschreiben(st, cfg, _dt.date(2024, 1, 1))
    pex = fs.ledger[fs.ledger.ereignis == "PEX"]
    assert len(pex) >= 3, "Welt ohne Beitragsfreistellung im Jahr 1/2 waere blind"
    assert (pex[pex.betrag_art == "VS_bfr"].betrag >= 0.0).all()
    assert (pex[pex.betrag_art == "VS_bfr"].vertragsjahr <= 2).all()
    assert validate_ledger(st, fs.ledger) == []
    assert pruefe_ledger_betraege(st, fs.ledger, cfg, historie=fs.historie,
                                  scheiben=fs.scheiben) == []


# --------------------------------------------------------------------------- #
# Fund 3: Absetzung ableiten, auch beim Pauschalabzug
# --------------------------------------------------------------------------- #

from rechner_pipeline.bestand.migrationszugang import (
    MigrationszugangFehler,
    leite_absetzung_ab,
    leite_ursprungssumme_ab,
)

#: Die Regime des Stornoabzugs (satz, min, max): Satz mit Grenzen (zwei),
#: kein Abzug, Pauschalabzug (Satz 0, min > 0) und Satz ohne Untergrenze —
#: dazu (Nachbesserung, Klemmrand) drei Regime, in denen der Abzug den
#: Rueckkaufs-Track in der Gitterwelt aufzehren kann: ein grosser Pauschalabzug
#: (8.000), ein Satz von 10 % mit Obergrenze 1.500 und ein Satz von 10 % ohne
#: Obergrenze.
_ABSETZ_REGIME = ((0.01, 50.0, 150.0), (0.005, 50.0, 200.0), (0.0, 0.0, 0.0),
                  (0.0, 50.0, 150.0), (0.02, 0.0, 1e9),
                  (0.0, 8000.0, 8000.0), (0.1, 0.0, 1500.0), (0.1, 0.0, 1e9))
_ABSETZ_VERFAHREN = ("prospektiv", "mit_abzug")
_ABSETZ_SUMMEN = (20000.0, 100000.0, 700000.0)
_ABSETZ_ANTEILE = (0.3, 0.8)
_ABSETZ_JAHRE = (2, 6, 12)


def _absetzung_vorwaerts(felder: dict, jahr: int, f: float, verfahren: str):
    """Die gelieferten Felder (ERLSUMME, JBRUTTO) aus (VS, f) — von Hand aus
    der Verlaufszeile: umgewandelt = (1-f) x RKW / V^bfr bzw. ohne Abzug
    (1-f) x V^MRV / V^bfr; JBRUTTO = f x Beitrag. Nicht ueber ``reduziere``
    und nicht ueber die Umkehrung."""
    kern = Rechenkern(ModelPoint(**felder))
    z = kern.verlaufszeile(jahr)
    basis = z.vx_mrv if verfahren == "prospektiv" else max(0.0, z.vx_mrv - _stoab_von_hand(felder, z))
    erl = f * felder["sum_insured"] + (1.0 - f) * basis / z.vx_bfr
    return round(erl, 2), round(f * kern.gross_annual_premium(), 2)


def _stoab_von_hand(felder: dict, z) -> float:
    """StoAb = min(umax, max(umin, s x (VS - DR))) des Regelwerks (Tarifplan 6),
    ausserhalb der flexiblen Phase und vor dem Ablauf (das Gitter liegt dort)."""
    return min(felder["stoab_max"],
               max(felder["stoab_min"],
                   felder["stoab_satz"] * (felder["sum_insured"] - z.drx_bpfl)))


def _am_klemmrand_von_hand(felder: dict, jahr: int, verfahren: str) -> bool:
    """Das Klemmrand-Soll der Zelle: mit Abzug und StoAb >= V^MRV (RKW 0,
    nichts umgewandelt, ERLSUMME = f x VS) — aus der Verlaufszeile, nicht aus
    der Ableitung."""
    if verfahren != "mit_abzug":
        return False
    z = Rechenkern(ModelPoint(**felder)).verlaufszeile(jahr)
    return z.vx_mrv - _stoab_von_hand(felder, z) <= 0.0


def _absetz_zellen():
    return list(itertools.product(
        _ABSETZ_REGIME, _ABSETZ_VERFAHREN, _ABSETZ_SUMMEN, _ABSETZ_ANTEILE, _ABSETZ_JAHRE))


def test_das_gitter_von_fund_3_hat_die_hergeleitete_groesse():
    """Zaehltest je Instanz: 8 Regime x 2 Verfahren x 3 Summen x 2 Anteile x 3
    Jahre = 288 Zellen je Ableitung (== statt >=)."""
    assert len(_absetz_zellen()) == 288


def test_die_absetzung_ist_in_jedem_regime_ableitbar():
    """Runde F, F3: Rundreise ueber alle Zellen — (VS, f) vorwaerts von Hand,
    centgerundet geliefert, zurueckgerechnet. Vorher wurden die 18 Zellen mit
    Pauschalabzug (0 / 50 / 150, mit Abzug) verweigert. Mutationsprobe:
    ``or s_satz <= 0.0`` in ``leite_absetzung_ab`` wieder einfuehren -> rot."""
    verweigert = []
    for (satz, umin, umax), verf, vs, f, jahr in _absetz_zellen():
        felder = dataclasses.asdict(dataclasses.replace(
            KLV_DEFAULT, sum_insured=vs, stoab_satz=satz, stoab_min=umin, stoab_max=umax))
        if _am_klemmrand_von_hand(felder, jahr, verf):
            continue     # eigener Test unten: benannt verweigert
        erl, jb = _absetzung_vorwaerts(felder, jahr, f, verf)
        try:
            ab = leite_absetzung_ab(felder, jahr=jahr, erlsumme=erl, jbrutto=jb, verfahren=verf)
        except MigrationszugangFehler as exc:
            verweigert.append(((satz, umin, umax), verf, vs, f, jahr, str(exc)[:80]))
            continue
        assert ab.vs_alt == pytest.approx(vs, rel=5e-5), ((satz, umin, umax), verf, vs, f, jahr)
        assert ab.anteil == pytest.approx(f, rel=5e-5), ((satz, umin, umax), verf, vs, f, jahr)
    assert verweigert == []


def test_die_ursprungssumme_bei_bekanntem_anteil_ist_in_jedem_regime_ableitbar():
    """Dieselbe Klasse in der zweiten Ableitung (``leite_ursprungssumme_ab``,
    Anteil geliefert): dieselbe Abkuerzung ``s_satz <= 0`` stand dort ein
    zweites Mal. Mutationsprobe: sie dort wieder einfuehren -> rot."""
    for (satz, umin, umax), verf, vs, f, jahr in _absetz_zellen():
        felder = dataclasses.asdict(dataclasses.replace(
            KLV_DEFAULT, sum_insured=vs, stoab_satz=satz, stoab_min=umin, stoab_max=umax))
        erl, _jb = _absetzung_vorwaerts(felder, jahr, f, verf)
        ist = leite_ursprungssumme_ab(felder, jahr=jahr, erlsumme=erl, anteil=f, verfahren=verf)
        assert ist == pytest.approx(vs, rel=5e-5), ((satz, umin, umax), verf, vs, f, jahr)


def test_der_pauschalabzug_wird_ueber_den_zweig_min_abgeleitet():
    """Der Zweig ist benannt, nicht geraten: Pauschalabzug (Satz 0, min 50,
    max 150) mit Abzug -> Zweig ``min``; kein Abzug (0 / 0 / 0) -> ``null``;
    prospektiv bleibt ``flex_oder_null``."""
    zweige = {}
    for regime, verf in (((0.0, 50.0, 150.0), "mit_abzug"), ((0.0, 0.0, 0.0), "mit_abzug"),
                         ((0.0, 50.0, 150.0), "prospektiv")):
        satz, umin, umax = regime
        felder = dataclasses.asdict(dataclasses.replace(
            KLV_DEFAULT, sum_insured=100000.0, stoab_satz=satz, stoab_min=umin, stoab_max=umax))
        erl, jb = _absetzung_vorwaerts(felder, 6, 0.6, verf)
        zweige[(regime, verf)] = leite_absetzung_ab(
            felder, jahr=6, erlsumme=erl, jbrutto=jb, verfahren=verf).stoab_zweig
    assert zweige == {((0.0, 50.0, 150.0), "mit_abzug"): "min",
                      ((0.0, 0.0, 0.0), "mit_abzug"): "null",
                      ((0.0, 50.0, 150.0), "prospektiv"): "flex_oder_null"}


# --------------------------------------------------------------------------- #
# Nachbesserung Kern, Punkt 1: der Klemmrand ist ein eigener Zweig
# --------------------------------------------------------------------------- #

from rechner_pipeline.bestand import migrationszugang as _mz


def test_der_klemmrand_wird_benannt_verweigert_statt_still_erfunden():
    """Runde F, Nachbesserung 1. Am Klemmrand (mit Abzug, StoAb >= V^MRV, RKW 0,
    nichts umgewandelt, ERLSUMME = f x VS) zerfaellt die quadratische
    Gleichung: Die Wurzel VS = c/m besteht die Vorwaertsprobe, und die
    Ableitung gab still ein erfundenes (VS, f) zurueck (Messfall: geliefert
    VS 20.000 / f 0,8 bei Pauschalabzug 8.000, Rueckgabe VS 114.398 /
    f 0,14). Jede Klemmrand-Zelle des Gitters — Vorwaerts-Soll von Hand —
    wird mit der benannten Meldung verweigert, und zwar auf BEIDEN Seiten
    der Rundung (ERLSUMME ueber und unter dem fortgefuehrten Teil).
    Mutationsprobe: den Waechter ``_am_klemmrand`` in den Klammerzweigen
    entfernen -> rot (erfundene Rueckgabe)."""
    zellen = []
    for (satz, umin, umax), verf, vs, f, jahr in _absetz_zellen():
        felder = dataclasses.asdict(dataclasses.replace(
            KLV_DEFAULT, sum_insured=vs, stoab_satz=satz, stoab_min=umin, stoab_max=umax))
        if not _am_klemmrand_von_hand(felder, jahr, verf):
            continue
        erl, jb = _absetzung_vorwaerts(felder, jahr, f, verf)
        k_teil = jb / Rechenkern(ModelPoint(**felder)).gross_premium_rate()
        # Das Soll von Hand: nichts umgewandelt, ERLSUMME = f x VS (centgerundet).
        assert erl == pytest.approx(f * vs, abs=0.0051)
        with pytest.raises(MigrationszugangFehler) as exc:
            leite_absetzung_ab(felder, jahr=jahr, erlsumme=erl, jbrutto=jb, verfahren=verf)
        assert str(exc.value).startswith(
            "am Klemmrand nicht bestimmbar: Stornoabzug zehrt den Rueckkaufs-Track auf"
            " — Anteil als Auskunft registrieren"), ((satz, umin, umax), vs, f, jahr, str(exc.value))
        zellen.append((satz, umin, umax, vs, f, jahr, erl > k_teil))
    # Zaehltest: 7 Kombinationen (Regime, Summe, Jahr) klemmen, je zwei Anteile.
    assert len(zellen) == 14
    # Positivkontrolle der Rundungsseiten: Zellen mit ERLSUMME ueber dem
    # fortgefuehrten Teil (dort greift der Waechter der Klammerzweige, nicht
    # die fruehere Abweisung ``erlsumme <= k_teil``) UND darunter.
    assert any(ueber for *_, ueber in zellen)
    assert any(not ueber for *_, ueber in zellen)
    # Die Regime des Gitters sind alle drei vertreten (Pauschal, Satz+Obergrenze, Satz).
    assert {(z[0], z[1], z[2]) for z in zellen} == {
        (0.0, 8000.0, 8000.0), (0.1, 0.0, 1500.0), (0.1, 0.0, 1e9)}


def test_der_klemmrand_kippt_keine_bestimmbare_zelle_in_die_verweigerung():
    """Gegenprobe zum Waechter: Zellen mit wirksamem Abzug (RKW > 0), auch in den
    Klammerzweigen min/max, werden weiter abgeleitet — der Waechter ist keine
    Pauschalverweigerung. Das Gitter enthaelt solche Zellen in den
    Klemmrand-Regimen selbst (Pauschal 8.000 bei Summe 100.000, Jahr 6/12 ->
    Zweig min; Satz 10 % mit Obergrenze 1.500 bei Summe 20.000, Jahr 6 -> Zweig max)."""
    zweige = set()
    for (satz, umin, umax), verf, vs, f, jahr in _absetz_zellen():
        if verf != "mit_abzug" or (satz, umin, umax) not in (
                (0.0, 8000.0, 8000.0), (0.1, 0.0, 1500.0)):
            continue
        felder = dataclasses.asdict(dataclasses.replace(
            KLV_DEFAULT, sum_insured=vs, stoab_satz=satz, stoab_min=umin, stoab_max=umax))
        if _am_klemmrand_von_hand(felder, jahr, verf):
            continue
        erl, jb = _absetzung_vorwaerts(felder, jahr, f, verf)
        ab = leite_absetzung_ab(felder, jahr=jahr, erlsumme=erl, jbrutto=jb, verfahren=verf)
        assert ab.vs_alt == pytest.approx(vs, rel=5e-5)
        assert ab.anteil == pytest.approx(f, rel=5e-5)
        zweige.add(ab.stoab_zweig)
    assert {"min", "max"} <= zweige


def test_der_klemmrand_bei_bekanntem_anteil_ist_bestimmt():
    """Mit BEKANNTEM Anteil ist der Klemmrand bestimmt (VS = ERLSUMME / f) und
    wird als eigener Zweig abgeleitet — jede Klemmrand-Zelle des Gitters, Soll von
    Hand. Ohne den Zweig scheiterte die Vorwaertsprobe an der Formel der
    Klammerzweige (sie setzt RKW > 0 voraus). Mutationsprobe: den Zweig
    ``klemmrand`` in ``leite_ursprungssumme_ab`` entfernen -> rot."""
    anzahl = 0
    for (satz, umin, umax), verf, vs, f, jahr in _absetz_zellen():
        felder = dataclasses.asdict(dataclasses.replace(
            KLV_DEFAULT, sum_insured=vs, stoab_satz=satz, stoab_min=umin, stoab_max=umax))
        if not _am_klemmrand_von_hand(felder, jahr, verf):
            continue
        erl, _jb = _absetzung_vorwaerts(felder, jahr, f, verf)
        ist = leite_ursprungssumme_ab(felder, jahr=jahr, erlsumme=erl, anteil=f, verfahren=verf)
        assert ist == pytest.approx(vs, rel=5e-5), ((satz, umin, umax), vs, f, jahr)
        anzahl += 1
    assert anzahl == 14


def test_die_untergrenze_reicht_nicht_endliche_werte_durch():
    """Runde F, Nachbesserung: ``max(0.0, nan)`` ist in Python 0.0. Die
    Untergrenze haette damit einen Rechenfehler zur gueltigen Summe null
    gemacht, und die Fuehrungsprobe sah statt des NaN eine gewoehnliche
    Abweichung (Zusammenfuehrung der Runde-F-Fixes: ein Test der Probe
    wurde rot). Eine Grenze klemmt Zahlen, sie repariert keine Nicht-Zahlen.
    Mutationsprobe: den isfinite-Zweig entfernen -> rot."""
    from rechner_pipeline.kern.konventionen import untergrenze_basissumme

    assert untergrenze_basissumme(-1.0) == 0.0
    assert untergrenze_basissumme(2.5) == 2.5
    assert math.isnan(untergrenze_basissumme(float("nan")))
    assert untergrenze_basissumme(float("inf")) == float("inf")
    assert untergrenze_basissumme(float("-inf")) == float("-inf")
