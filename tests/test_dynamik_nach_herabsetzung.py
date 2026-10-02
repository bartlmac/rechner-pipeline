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
    """Je Police mit GENAU EINER Herabsetzung die Erhoehungen DANACH (die
    Zusage dieses Moduls ist die des einen Vorgangs; Folgen mehrerer Vorgaenge
    haelt tests/test_vorgangsfolge_leser.py)."""
    red = erg.reduktionen
    red = red[~red["police_id"].duplicated(keep=False)].set_index("police_id")
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
        vor = [(int(j), Rechenkern(erhoehungs_scheibe(mp, int(j), float(vs), gamma1_uebernehmen=False)))
               for j, vs in zip(s["erhoehung_jahr"], s["sum_insured"]) if int(j) < rj]
        nach = [(int(j), Rechenkern(erhoehungs_scheibe(mp, int(j), float(vs), gamma1_uebernehmen=False)))
                for j, vs in zip(s["erhoehung_jahr"], s["sum_insured"]) if int(j) >= rj]
        # Mit der Korrekturschicht des uebernommenen Vertrags — sie geht in
        # die Neuberechnung der Herabsetzung ein.
        ohne = reduzierte_teile(grund, vor, rj, f, verf, schicht=(_parameter(), MONATE_TA), stoab_je_baustein=False)
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


@pytest.fixture(scope="module")
def grosse_welt():
    """Mehr Vertraege, damit Herabsetzung und Erhoehung am selben Jahrestag
    vorkommen (bei 40 Policen der Fixture tun sie es nicht)."""
    config = _config(True)
    policen = list(range(900_001, 900_401))
    stamm = _stamm([{"id": p, "beginn": "2015-01-01", "zugang": "2026-01-01"} for p in policen])
    schichten, verankerung = _tabellen(policen)
    erg = fortschreiben(stamm, config, BIS, schichten=schichten, verankerung=verankerung)
    return config, stamm, schichten, verankerung, erg


def test_das_bewegungskonto_fuehrt_die_erhoehung_am_tag_der_herabsetzung(grosse_welt):
    """Angriffsrunde 2026-09-26: Eine Erhoehung am Tag der Herabsetzung
    (die Engine bucht RED vor ERH desselben Jahrestags) fiel aus der
    Kontosumme, dauerhaft; die Identitaet hielt trotzdem, P-B1 blieb gruen.
    Gemessen gegen die Einzelbewertung an JEDEM Jahresstichtag.
    Mutationsprobe: 'datum >= ab' zurueck auf 'datum > ab' -> rot."""
    import datetime as _dt

    from rechner_pipeline.bestand.kennzahlen import bewegungskonto

    config, stamm, schichten, verankerung, erg = grosse_welt
    red = erg.reduktionen
    s = erg.scheiben
    gleichtaegig = s.merge(red, left_on=["police_id", "erhoehung_datum"],
                           right_on=["police_id", "reduktion_datum"])
    assert len(gleichtaegig), "keine Erhoehung am Tag einer Herabsetzung — der Test saehe nichts"
    konto = {z["jahr"]: z for z in bewegungskonto(
        stamm, erg.historie, erg.ledger, erg.scheiben, bis=_dt.date(2045, 1, 1))}
    assert len(konto) >= 10
    for jahr in sorted(konto):
        stichtag = _dt.date(jahr + 1, 1, 1)
        einzeln = einzelwerte_am(stamm, erg.historie, config, stichtag, scheiben=erg.scheiben,
                                 schichten=schichten, verankerung=verankerung, reduktionen=red)
        soll = sum(z["leistung"] for z in einzeln if z["status"] == "POL")
        assert konto[jahr]["bpfl"]["ende"]["summe"] == pytest.approx(soll, rel=1e-9), jahr


def test_p_b1_prueft_die_hoehe_jeder_gerechneten_erhoehung(welt):
    """Angriffsrunde 2026-09-26: Eine Erhoehung mit falschem Bezug (5 % der
    ungekuerzten statt der gefuehrten Summe), in Ledger UND Scheibe
    konsistent verfaelscht, passierte P-B1. Mutationsprobe: die
    Herleitung der Erhoehungshoehe entfernen -> rot."""
    config, stamm, schichten, verankerung, erg = welt
    pid, (rj, f, verf, spaeter) = next(iter(_nach_red(erg).items()))
    j = int(spaeter["erhoehung_jahr"].iloc[0])
    led, sch = erg.ledger.copy(), erg.scheiben.copy()
    falsch = float(config.annahmen.erh_prozent) * float(stamm.set_index("police_id").loc[pid, "sum_insured"])
    m_led = (led["police_id"] == pid) & (led["ereignis"] == "ERH") & (led["vertragsjahr"] == j) & (led["betrag_art"] == "VS_erhoehung")
    m_sch = (sch["police_id"] == pid) & (sch["erhoehung_jahr"] == j)
    assert m_led.sum() == 1 and m_sch.sum() == 1
    led.loc[m_led, "betrag"] = falsch
    sch.loc[m_sch, "sum_insured"] = falsch
    # Auch den Beitrag der Scheibe passend nachziehen — sonst finge die
    # (schon vorhandene) Beitragsherleitung den Fehler, nicht die Regel.
    gen = config.generationen[0]
    mp = ModelPoint(**model_point_kwargs(stamm.set_index("police_id").loc[pid], gen.generation_fields()))
    m_bjb = (led["police_id"] == pid) & (led["ereignis"] == "ERH") & (led["vertragsjahr"] == j) & (led["betrag_art"] == "BJB")
    led.loc[m_bjb, "betrag"] = Rechenkern(erhoehungs_scheibe(mp, j, falsch, gamma1_uebernehmen=False)).gross_annual_premium()
    gen = config.generationen[0]
    zug = pd.DataFrame([{
        "police_id": p, "tarif_generation": gen.name, "ereignis": "ZUG",
        "vertragsjahr": 11, "status_date": pd.Timestamp("2026-01-01"),
        "betrag_art": "VS", "betrag": 100_000.0, "betrag_herkunft": "geliefert",
    } for p in POLICEN])[[n for n, _ in LEDGER_SPALTEN]].astype(dict(LEDGER_SPALTEN))
    fehler = pruefe_ledger_betraege(
        stamm, pd.concat([zug, led], ignore_index=True), config, scheiben=sch,
        historie=erg.historie, schichten=schichten, verankerung=verankerung,
        reduktionen=erg.reduktionen)
    assert any(f"police {pid} ERH Jahr {j}" in f and "Regel" in f for f in fehler), fehler


def test_der_bestandsbericht_zeigt_die_gefuehrte_versicherungssumme(welt):
    """Angriffsrunde 2026-09-26: Tabelle und Grafik 'Versicherungssumme' des
    Berichts summierten die Stammspalte — herabgesetzte Vertraege standen
    ungekuerzt da, Erhoehungen fehlten. Jetzt: die bewertete Summe.
    Mutationsprobe: die Ueberschreibung mit vs_klv entfernen -> rot."""
    import datetime as _dt

    from rechner_pipeline.bestand import report as rp

    config, stamm, schichten, verankerung, erg = welt
    stichtage = [_dt.date(2030, 1, 1), _dt.date(2035, 1, 1)]
    gesehen = {}
    echt = rp._chart_verlauf_summe

    def merkend(reihe, *a, **k):
        gesehen["reihe"] = [dict(r) for r in reihe]
        return echt(reihe, *a, **k)

    import pytest as _pt
    mp = _pt.MonkeyPatch()
    mp.setattr(rp, "_chart_verlauf_summe", merkend)
    try:
        rp.render_html(stamm, stichtage=stichtage, historie=erg.historie, ledger=erg.ledger,
                       config=config, scheiben=erg.scheiben, schichten=schichten,
                       verankerung=verankerung, reduktionen=erg.reduktionen,
                       bis=BIS, stichtag=None)
    finally:
        mp.undo()
    for zeile, s in zip(gesehen["reihe"], stichtage):
        soll = sum(z["leistung"] for z in einzelwerte_am(
            stamm, erg.historie, config, s, scheiben=erg.scheiben, schichten=schichten,
            verankerung=verankerung, reduktionen=erg.reduktionen) if z["produkt"] == "klv")
        assert zeile["summe_vs"] == pytest.approx(soll, rel=1e-9), s


def test_die_nachweisung_zeigt_jede_position_der_identitaet():
    """Angriffsrunden 2 und 3 der Nacht: Die gedruckte Nachweisung liess die
    Herabsetzungsspalte weg; die gezeigte Rechnung ging nicht auf, obwohl
    Konto und P-B1 sie fuehren. Ratsche: jede Position, die das Konto in
    die Identitaet nimmt, steht als Spalte im Bericht."""
    import inspect

    from rechner_pipeline.bestand import kennzahlen, report

    quelle = inspect.getsource(kennzahlen.bewegungskonto)
    klv = next(n for n in report.NACHWEISUNGEN if n["produkt"] == "klv")
    for track, _titel, positionen in klv["tracks"]:
        gezeigt = {p for p, _ in positionen}
        for position in ("zugang_neuzugang", "zugang_erhoehung", "veraenderung_herabsetzung",
                         "abgang_storno", "abgang_tod", "abgang_ablauf", "umbuchung_beitragsfrei",
                         "zugang_umbuchung"):
            if track == "bpfl" and position == "zugang_umbuchung":
                continue
            if track == "bfr" and position not in ("zugang_umbuchung", "abgang_tod", "abgang_ablauf"):
                continue
            assert f'"{position}"' in quelle
            assert position in gezeigt, (track, position)
