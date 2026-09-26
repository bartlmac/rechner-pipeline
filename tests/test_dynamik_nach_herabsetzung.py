"""Die Dynamik laeuft nach einer Herabsetzung weiter — auf die neue Summe bezogen.

Bis 2026-09-26 zog die Engine nach einer Herabsetzung keine dynamische
Erhoehung mehr; das stand in keinem Tarifplan und war ein Fehler
(Entscheid des Projekts). Eine Scheibe NACH der Herabsetzung liess die
Bewertung ausserdem still weg (Fund einer blinden Angriffsrunde: -7.000
EUR Summe). Jetzt: Die Erhoehung bezieht sich auf die gefuehrte Summe
nach der Herabsetzung, die neue Scheibe ist ein gewoehnlicher, nicht
herabgesetzter Baustein, und jeder Konsument (Engine, Bewertung, P-B1)
fuehrt sie.

Knoten: klv
"""

from __future__ import annotations

import pandas as pd
import pytest

from rechner_pipeline.bestand.auswertung import einzelwerte_am
from rechner_pipeline.bestand.ereignisse import fortschreiben
from rechner_pipeline.bestand.ledger_bindung import pruefe_ledger_betraege
from rechner_pipeline.kern import ModelPoint, Rechenkern
from rechner_pipeline.kern.beitragsreduktion import (
    reduzierte_teile,
    vertrags_monatsreserve_reduziert,
)
from rechner_pipeline.kern.rechenkern import erhoehungs_scheibe
from rechner_pipeline.models.bestand import LEDGER_SPALTEN, model_point_kwargs
from tests.test_bestand_uebernommen_fortschreiben import _stamm
from tests.test_herabsetzung_in_fuehrung import BIS, POLICEN, _config
from tests.test_schicht_in_fuehrung import MONATE_TA, _parameter, _tabellen


@pytest.fixture(scope="module")
def welt():
    config = _config(True)
    stamm = _stamm([{"id": p, "beginn": "2015-01-01", "zugang": "2026-01-01"} for p in POLICEN])
    schichten, verankerung = _tabellen(POLICEN)
    erg = fortschreiben(stamm, config, BIS, schichten=schichten, verankerung=verankerung)
    return config, stamm, schichten, verankerung, erg


def _nach_red(erg):
    """Je Police mit Herabsetzung die Erhoehungen DANACH."""
    red = erg.reduktionen.set_index("police_id")
    s = erg.scheiben
    aus = {}
    for pid, zeile in red.iterrows():
        spaeter = s[(s["police_id"] == pid) & (s["erhoehung_jahr"] >= int(zeile["reduktion_jahr"]))]
        if len(spaeter):
            aus[int(pid)] = (int(zeile["reduktion_jahr"]), float(zeile["anteil"]), str(zeile["verfahren"]), spaeter)
    return aus


def test_nach_einer_herabsetzung_gibt_es_wieder_erhoehungen(welt):
    """Mutationsprobe: die alte Bedingung 'reduktion is None' zurueck -> rot."""
    assert _nach_red(welt[4]), "keine Erhoehung nach einer Herabsetzung"


def test_die_erhoehung_bezieht_sich_auf_die_summe_nach_der_herabsetzung(welt):
    config, stamm, schichten, verankerung, erg = welt
    led = erg.ledger
    prozent = float(config.annahmen.erh_prozent)
    for pid, (rj, f, verf, spaeter) in _nach_red(erg).items():
        vs_red = float(led[(led["police_id"] == pid) & (led["ereignis"] == "RED")
                           & (led["betrag_art"] == "VS_herabsetzung")]["betrag"].iloc[0])
        summe = vs_red
        for _, s in spaeter.sort_values("erhoehung_jahr").iterrows():
            assert float(s["sum_insured"]) == pytest.approx(prozent * summe, rel=1e-9), pid
            summe += float(s["sum_insured"])


def test_die_bewertung_fuehrt_die_scheibe_nach_der_herabsetzung(welt):
    """Unabhaengig: Summe und Deckungskapital sind additiv — der
    herabgesetzte Vertrag OHNE die spaeteren Scheiben plus jede spaetere
    Scheibe als gewoehnlicher Kern. Mutationsprobe: spaetere Scheiben in
    reduzierte_teile nicht anhaengen -> rot (vorher: still weggelassen)."""
    config, stamm, schichten, verankerung, erg = welt
    gen = config.generationen[0]
    haupt = stamm.set_index("police_id")
    geprueft = 0
    for pid, (rj, f, verf, spaeter) in _nach_red(erg).items():
        letzte = int(spaeter["erhoehung_jahr"].max())
        beginn = pd.Timestamp(haupt.loc[pid, "insurance_start"])
        stichtag = (beginn + pd.DateOffset(years=letzte)).date()
        h = erg.historie
        if len(h[(h["police_id"] == pid) & (h["status_date"] <= pd.Timestamp(stichtag))]):
            continue
        mp = ModelPoint(**model_point_kwargs(haupt.loc[pid], gen.generation_fields()))
        grund = Rechenkern(mp)
        s = erg.scheiben[erg.scheiben["police_id"] == pid]
        vor = [(int(j), Rechenkern(erhoehungs_scheibe(mp, int(j), float(vs))))
               for j, vs in zip(s["erhoehung_jahr"], s["sum_insured"]) if int(j) < rj]
        nach = [(int(j), Rechenkern(erhoehungs_scheibe(mp, int(j), float(vs))))
                for j, vs in zip(s["erhoehung_jahr"], s["sum_insured"]) if int(j) >= rj]
        # Mit der Korrekturschicht des uebernommenen Vertrags — sie geht in
        # die Neuberechnung der Herabsetzung ein.
        ohne = reduzierte_teile(grund, vor, rj, f, verf, schicht=(_parameter(), MONATE_TA))
        m = 12 * letzte
        dk_soll = (vertrags_monatsreserve_reduziert(ohne, m, stoab_je_baustein=False).drx_bpfl
                   + sum(k.monatsreserve(m - 12 * j).drx_bpfl for j, k in nach))
        vs_soll = sum(v.reduktion.vs_neu for _, v in ohne) + sum(k.mp.sum_insured for _, k in nach)
        zeile = next(z for z in einzelwerte_am(
            stamm, erg.historie, config, stichtag, scheiben=erg.scheiben, schichten=schichten,
            verankerung=verankerung, reduktionen=erg.reduktionen) if int(z["police_id"]) == pid)
        assert zeile["leistung"] == pytest.approx(vs_soll, rel=1e-9), pid
        assert zeile["deckungskapital"] == pytest.approx(dk_soll, rel=1e-9), pid
        geprueft += 1
    assert geprueft > 0


def test_p_b1_leitet_den_lauf_mit_dynamik_nach_herabsetzung_her(welt):
    config, stamm, schichten, verankerung, erg = welt
    gen = config.generationen[0]
    zug = pd.DataFrame([{
        "police_id": pid, "tarif_generation": gen.name, "ereignis": "ZUG",
        "vertragsjahr": 11, "status_date": pd.Timestamp("2026-01-01"),
        "betrag_art": "VS", "betrag": 100_000.0, "betrag_herkunft": "geliefert",
    } for pid in POLICEN])[[n for n, _ in LEDGER_SPALTEN]].astype(dict(LEDGER_SPALTEN))
    assert pruefe_ledger_betraege(
        stamm, pd.concat([zug, erg.ledger], ignore_index=True), config, scheiben=erg.scheiben,
        historie=erg.historie, schichten=schichten, verankerung=verankerung,
        reduktionen=erg.reduktionen) == []
