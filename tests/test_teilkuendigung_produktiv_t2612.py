"""Die Teilkuendigung im produktiven Pfad (Bauauftrag T26-12, 2026-09-22).

Bedingungswerk Ziffer 6 der uebernommenen TG2015: Der Anteil (1-f) der
GRUNDVERSICHERUNG wird gekuendigt und sein Rueckkaufswert ausgezahlt, der
Rest laeuft zustandslos mit f x S weiter, die Erhoehungsscheiben laufen
unveraendert (A-M3-Befund des zweiten Laufs). Die Pruefstrecke
rekonstruierte das schon (``reduziere``); der produktive Pfad verweigerte
es — die Luecke, die der Gutachter meldete.

Vier Zusicherungen: (1) die Folgebewertung braucht keinen Sonderweg — der
Zahlungspfad mit q = 0 IST der zustandslose Vertrag, gemessen gegen den
unabhaengigen Kern mit gesenkter Summe; (2) der geschichtete Zweig trifft
nur den Grund; (3) die Engine bucht Summe, absorbierte Schicht und
Auszahlung, und P-B1 leitet alle drei aus dem Kern her; (4) die
Teilkuendigung SENKT — immer.

Annahme zur Bestaetigung durch das Aktuariat: Die Korrekturschicht geht bei
der Teilkuendigung vollstaendig in die AUSZAHLUNG (Entscheid 2026-09-15,
"Schicht geht vollstaendig in die Neuberechnung ein"; hier ist die Zahlung
das einzige Vehikel — es gibt keinen beitragsfreien Teil), der Abzug wirkt
proportional ueber den Rueckkaufswert der Grundscheibe allein.

Knoten: klv
"""

from __future__ import annotations

import dataclasses

import pandas as pd
import pytest

from rechner_pipeline.bestand.config import config_aus_text, load_config
from rechner_pipeline.bestand.ereignisse import fortschreiben
from rechner_pipeline.bestand.kernlauf import vertrags_rkw
from rechner_pipeline.bestand.ledger_bindung import pruefe_ledger_betraege
from rechner_pipeline.kern import ModelPoint, Rechenkern, vertrags_monatsreserve
from rechner_pipeline.kern.beitragsreduktion import (
    PRODUKTIV_AUSFUEHRBAR,
    TEILKUENDIGUNG,
    ReduzierterVertrag,
    reduziere,
    reduziere_geschichtet,
    vertrags_monatsreserve_reduziert,
)
from rechner_pipeline.kern.korrekturschicht import schichtwert_bei
from rechner_pipeline.models.bestand import LEDGER_SPALTEN, model_point_kwargs
from tests.test_bestand_uebernommen_fortschreiben import _CONFIG_TOML, _stamm
from tests.test_betrieb_uebernahme import PLV
from tests.test_herabsetzung_in_fuehrung import ANTEIL, BIS, POLICEN
from tests.test_schicht_in_fuehrung import MONATE_TA, _parameter, _tabellen


def _kern(sum_insured: float = 60000.0) -> Rechenkern:
    gen = next(g for g in load_config(PLV).generationen if g.name == "KLV-2017")
    return Rechenkern(ModelPoint(x=35, sex="F", n=25, t=20, sum_insured=sum_insured,
                                 zw=12, **gen.generation_fields()))


def test_der_zahlungspfad_mit_q_null_ist_der_zustandslose_vertrag():
    """Unabhaengige Kontrolle: derselbe Vertrag, einmal als Zahlungspfad
    (die bestehende Folgebewertung, q = 0), einmal als Rechenkern mit der
    gesenkten Summe f x S. Reserven, Abzug, Rueckkaufswert, Beitrag,
    beitragsfreie Summe und Leistung stimmen an jedem Stichtag ueberein.
    Deshalb braucht die Teilkuendigung keinen zweiten Rechenweg.

    Mutationsprobe: in ``als_zahlungspfad`` die Leistung auf ``f`` statt
    ``f + q`` mit q = 0 zu belassen ist die Identitaet — die Probe ist
    hier die Toleranz: 1e-9 relativ, keine Naeherung."""
    kern, f, jahr = _kern(), 0.6, 5
    red = reduziere(kern, jahr, f, verfahren=TEILKUENDIGUNG)
    pfad = ReduzierterVertrag(kern=kern, reduktion=red)
    neu = Rechenkern(dataclasses.replace(kern.mp, sum_insured=f * kern.mp.sum_insured))
    assert pfad.bfr_teil == 0.0
    for m in (60, 66, 72, 96, 120, 180, 240, 299):
        a, b = pfad.monatsreserve(m), vertrags_monatsreserve(neu, [], m)
        for feld in ("drx_bpfl", "vx_mrv", "stoab", "rkw"):
            assert getattr(a, feld) == pytest.approx(getattr(b, feld), rel=1e-9, abs=1e-9), (m, feld)
    assert pfad.bjb(60) == pytest.approx(neu.gross_annual_premium(), rel=1e-12)
    for pj in (6, 10, 15):
        assert pfad.beitragsfreie_summe(pj) == pytest.approx(neu.beitragsfreie_summe(pj), rel=1e-12)
    assert pfad.terminale_leistung() == pytest.approx(f * kern.mp.sum_insured)


def test_der_geschichtete_zweig_kuendigt_nur_den_grund():
    """Grund gekuendigt, Scheibe unveraendert; dDK des Grundes ist der der
    Pruefstrecke (A-M3: -(1-f) x kVx), die Vertragsreserve danach ist die
    des f x S-Grundes plus die der unveraenderten Scheibe — unabhaengig
    gerechnet."""
    grund, f, jahr = _kern(), 0.6, 8
    scheibe = _kern(4000.0)
    teile = reduziere_geschichtet(grund, [(5, scheibe)], jahr, f, verfahren=TEILKUENDIGUNG)
    (e0, g), (e1, sch) = teile
    assert (e0, e1) == (0, 5)
    assert g.vs_neu == pytest.approx(f * grund.mp.sum_insured)
    assert g.d_dk == pytest.approx(-(1 - f) * grund.verlaufszeile(jahr).vx_mrv, rel=1e-9)
    assert sch.anteil == 1.0 and sch.vs_neu == sch.vs_alt == 4000.0 and sch.d_dk == 0.0
    assert PRODUKTIV_AUSFUEHRBAR[-1] == TEILKUENDIGUNG
    # Reserve des herabgesetzten Vertrags = f x S-Grund + Scheibe (unabhaengig).
    m = 12 * 10
    reduziert = vertrags_monatsreserve_reduziert(
        [(0, ReduzierterVertrag(kern=grund, reduktion=g)),
         (5, ReduzierterVertrag(kern=scheibe, reduktion=sch))], m)
    neu = Rechenkern(dataclasses.replace(grund.mp, sum_insured=f * grund.mp.sum_insured))
    erwartet = vertrags_monatsreserve(neu, [], m).vx_mrv + vertrags_monatsreserve(scheibe, [], m - 60).vx_mrv
    assert reduziert.vx_mrv == pytest.approx(erwartet, rel=1e-9)


def _welt():
    anker = '[[generation]]\nname = "klv/zellen"\n'
    assert anker in _CONFIG_TOML
    toml = _CONFIG_TOML.replace(anker, anker + 'red_verfahren = "teilkuendigung"\n', 1).replace(
        "[annahmen]\nerh_prozent = 0.05",
        f"[annahmen]\nerh_prozent = 0.05\nred_anteil = {ANTEIL}",
    ) + "\n[annahmen.herabsetzung]\na = 0.08\nb = 0.0\n"
    config = config_aus_text(toml)
    assert config.validate() == [], "die Teilkuendigung ist gebaut — die Config ist gueltig"
    stamm = _stamm([{"id": p, "beginn": "2015-01-01", "zugang": "2026-01-01"} for p in POLICEN])
    schichten, verankerung = _tabellen(POLICEN)
    ergebnis = fortschreiben(stamm, config, BIS, schichten=schichten, verankerung=verankerung)
    return config, stamm, schichten, verankerung, ergebnis


def test_die_engine_bucht_summe_schicht_und_auszahlung_und_pb1_leitet_sie_her():
    """Je Teilkuendigung drei Zeilen: die neue Gesamtsumme (f x Grund plus
    unveraenderte Scheiben), die vollstaendig absorbierte Schicht, und die
    Auszahlung des gekuendigten Grundanteils (Rueckkaufswert der
    Grundscheibe allein plus Schicht). Jede der drei folgt aus dem Kern —
    P-B1 leitet sie her und findet keine Abweichung.

    Zusicherungen statt Skip: mindestens eine Teilkuendigung, und
    mindestens eine mit einer Scheibe VOR ihr — sonst saehe der Test die
    Regel "Scheiben unveraendert" nicht.
    Mutationsprobe: in ``herabsetzen`` die Schicht nicht in die Auszahlung
    nehmen -> die Auszahlungs-Zusicherung UND P-B1 rot; ``(1 - anteil)``
    zu ``anteil`` -> rot."""
    config, stamm, schichten, verankerung, ergebnis = _welt()
    gen = config.generationen[0]
    felder = gen.generation_fields()
    haupt = stamm.set_index("police_id")
    led = ergebnis.ledger
    red = led[led["ereignis"] == "RED"]
    assert len(red) > 0, "Fixture ohne Teilkuendigung bezeugt nichts"
    mit_scheibe = 0
    for pid, zeilen in red.groupby("police_id"):
        pid = int(pid)
        jahr = int(zeilen["vertragsjahr"].iloc[0])
        arten = dict(zip(zeilen["betrag_art"], zeilen["betrag"]))
        assert set(arten) == {"VS_herabsetzung", "dDK_absorption", "RKW_teilkuendigung"}, arten
        mp = ModelPoint(**model_point_kwargs(haupt.loc[pid], felder))
        grund = Rechenkern(mp)
        erh = led[(led["police_id"] == pid) & (led["ereignis"] == "ERH")
                  & (led["betrag_art"] == "VS_erhoehung") & (led["vertragsjahr"] < jahr)]
        mit_scheibe += int(len(erh) > 0)
        assert arten["VS_herabsetzung"] == pytest.approx(
            ANTEIL * mp.sum_insured + float(erh["betrag"].sum()), rel=1e-9)
        schicht = schichtwert_bei(_parameter(), MONATE_TA, mp, 12 * jahr)
        assert schicht > 0.0
        assert arten["dDK_absorption"] == pytest.approx(schicht, rel=1e-12)
        rkw_grund = vertrags_rkw(grund, [], jahr, stoab_je_baustein=bool(gen.tarifwerk()["stoab_je_baustein"]))
        assert arten["RKW_teilkuendigung"] == pytest.approx((1 - ANTEIL) * rkw_grund + schicht, rel=1e-9)
        # Kein Statuswechsel: Die Teilkuendigung schreibt keine
        # Historienzeile — am Tag der Buchung steht in der Historie nichts.
        h = ergebnis.historie
        tag = zeilen["status_date"].iloc[0]
        assert not ((h["police_id"] == pid) & (h["status_date"] == tag)).any(), (pid, tag)
    assert mit_scheibe > 0, "keine Teilkuendigung mit Scheibe davor — die Regel 'Scheiben unveraendert' bliebe ungesehen"

    zug = pd.DataFrame([{
        "police_id": pid, "tarif_generation": gen.name, "ereignis": "ZUG",
        "vertragsjahr": 11, "status_date": pd.Timestamp("2026-01-01"),
        "betrag_art": "VS", "betrag": 100_000.0, "betrag_herkunft": "geliefert",
    } for pid in POLICEN])[[n for n, _ in LEDGER_SPALTEN]].astype(dict(LEDGER_SPALTEN))
    voll = pd.concat([zug, ergebnis.ledger], ignore_index=True)
    assert pruefe_ledger_betraege(
        stamm, voll, config, scheiben=ergebnis.scheiben, historie=ergebnis.historie,
        schichten=schichten, verankerung=verankerung,
        reduktionen=ergebnis.reduktionen) == []


def test_die_teilkuendigung_senkt_immer():
    """Per Definition: Die neue Gesamtsumme liegt unter der alten — Grund
    auf f x S, Scheiben unveraendert, kein beitragsfreier Zuwachs. Anders
    als beim PLV-Verfahren kann hier auch die absorbierte Schicht die
    Summe nicht heben: Sie geht in die Auszahlung, nicht in die Summe."""
    _config, stamm, _s, _v, ergebnis = _welt()
    led = ergebnis.ledger
    red = led[(led["ereignis"] == "RED") & (led["betrag_art"] == "VS_herabsetzung")]
    assert len(red) > 0
    for z in red.to_dict("records"):
        pid, jahr = int(z["police_id"]), int(z["vertragsjahr"])
        erh = led[(led["police_id"] == pid) & (led["ereignis"] == "ERH")
                  & (led["betrag_art"] == "VS_erhoehung") & (led["vertragsjahr"] < jahr)]
        vorher = 100_000.0 + float(erh["betrag"].sum())
        assert float(z["betrag"]) < vorher, (pid, jahr)
