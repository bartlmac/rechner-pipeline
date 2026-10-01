"""Zaehltest: jede geordnete Zweierfolge von Vorgaengen durch ALLE Leser.

Die Invariante (Entscheid des Maintainers 2026-10-01): Der Zustand eines
Vertrags ist die Folge seiner Vorgaenge; jeder Leser rechnet auf derselben
Folge. Eine Welt mit hohen Raten fuer Beitragsherabsetzung (RED),
Teilkuendigung (TKU), Beitragsfreistellung (PEX) und Erhoehung (ERH) — eigene
Tarife der PLV, Umfang der Teilkuendigung "alle Bausteine" — zieht jede
zulaessige geordnete Zweierfolge, Dreierfolgen und Folgen mit Scheiben. Je
Folge muessen die Leser uebereinstimmen:

* die Engine bucht, das Datenmodell und P-B1 (Betraege aus dem Kern,
  Vollstaendigkeit, Bindung an die Raten) nehmen den Lauf ohne Befund an;
* die Bewertung monatsgenau (die Grundlage des Abschlusses) traegt den
  Zustand der Folge — und fuer reine Teilkuendigungsketten den unabhaengig
  gebauten gewoehnlichen Vertrag mit dem Produkt der Anteile;
* das Bewegungskonto schliesst je Jahr, Track und Mass und trifft die
  Einzelbewertung an jedem Jahresende;
* die Migrationssuite (Pruefstrecke des Zugangs) faltet die gebuchten
  Geschaeftsvorfaelle selbst und trifft jeden gebuchten Betrag (Rueckkauf,
  Tod, Ablauf, Beitragsfreistellung) und den Folgewert; der aktuarielle
  Test (A-M3) misst die Wertaenderung jedes Vorgangs.

Unzulaessige Folgen (Herabsetzung oder Erhoehung nach der
Beitragsfreistellung, zweite Beitragsfreistellung) zieht die Engine nie.

Knoten: klv
"""

from __future__ import annotations

import dataclasses
import datetime as _dt
from collections import Counter

import pandas as pd
import pytest

from rechner_pipeline.bestand.auswertung import einzelwerte_am
from rechner_pipeline.bestand.config import config_aus_text
from rechner_pipeline.bestand.ereignisse import fortschreiben, mit_zugaengen
from rechner_pipeline.bestand.fuehrung import fuehre_fort
from rechner_pipeline.bestand.kennzahlen import bewegungskonto
from rechner_pipeline.bestand.ledger_bindung import pruefe_ledger_betraege
from rechner_pipeline.kern import ModelPoint, Rechenkern
from rechner_pipeline.models.bestand import (
    leerer_stamm,
    model_point_kwargs,
    validate_ledger,
    validate_reduktionen,
)
from tests.test_bestand_uebernommen_fortschreiben import _CONFIG_TOML, _stamm

BIS = _dt.date(2040, 1, 1)
POLICEN = list(range(960_001, 960_121))
RED_ANTEIL, TK_ANTEIL = 0.7, 0.8
#: Rang am selben Jahrestag (Reihenfolge der Engine).
RANG = {"PEX": 0, "RED": 1, "TKU": 2, "ERH": 3}
ZULAESSIG = {("RED", "RED"), ("RED", "TKU"), ("TKU", "RED"), ("TKU", "TKU"),
             ("RED", "PEX"), ("TKU", "PEX"), ("PEX", "TKU"),
             ("RED", "ERH"), ("TKU", "ERH"), ("ERH", "RED"), ("ERH", "TKU"),
             ("ERH", "PEX"), ("ERH", "ERH")}
UNZULAESSIG = {("PEX", "RED"), ("PEX", "ERH"), ("PEX", "PEX")}


def _config():
    text = _CONFIG_TOML
    for alt, neu in (
        ("[annahmen.erhoehung]\na = 0.05", "[annahmen.erhoehung]\na = 0.3"),
        ("[annahmen.beitragsfreistellung]\na = 0.02", "[annahmen.beitragsfreistellung]\na = 0.06"),
        ("[annahmen]\nerh_prozent = 0.05",
         f"[annahmen]\nerh_prozent = 0.05\nred_anteil = {RED_ANTEIL}\ntk_anteil = {TK_ANTEIL}"),
    ):
        assert alt in text, alt
        text = text.replace(alt, neu)
    text += ("\n[annahmen.herabsetzung]\na = 0.2\nb = 0.0\n"
             "[annahmen.teilkuendigung]\na = 0.2\nb = 0.0\n")
    config = config_aus_text(text)
    assert config.validate() == []
    assert config.generationen[0].tarifwerk()["tku_umfang"] == "alle_bausteine"
    return config


@pytest.fixture(scope="module")
def welt():
    config = _config()
    stamm = _stamm([{"id": p, "beginn": "2015-01-01", "n": 25, "t": (12, 15, 20)[p % 3]}
                    for p in POLICEN])
    erg = fortschreiben(stamm, config, BIS)
    return config, stamm, erg


def _folgen(ledger: pd.DataFrame) -> dict:
    """Je Police die Folge ihrer Vorgaenge (Code, Jahr), geordnet nach
    Wirkungstag und Rang des Tages — aus dem Ledger, nicht aus der Engine."""
    zeilen = ledger[((ledger["ereignis"] == "RED") & (ledger["betrag_art"] == "VS_herabsetzung"))
                    | ((ledger["ereignis"] == "TKU") & (ledger["betrag_art"] == "VS_teilkuendigung"))
                    | (ledger["ereignis"] == "PEX")
                    | ((ledger["ereignis"] == "ERH") & (ledger["betrag_art"] == "VS_erhoehung"))]
    aus = {}
    for pid, eigene in zeilen.groupby("police_id"):
        eigene = sorted(zip(eigene["status_date"], eigene["ereignis"], eigene["vertragsjahr"]),
                        key=lambda z: (z[0], RANG[z[1]]))
        aus[int(pid)] = [(str(e), int(j)) for _, e, j in eigene]
    return aus


def test_jede_zulaessige_zweierfolge_kommt_vor_und_keine_unzulaessige(welt):
    """Zaehltest der Kombinationen (geordnete Zweierfolgen aus RED, TKU, PEX,
    ERH), dazu mindestens eine Dreierfolge aus RED/TKU und eine Folge mit
    Scheiben vor einer Teilkuendigung. Mutationsproben: die Teilkuendigung
    nach PEX nicht ziehen -> (PEX, TKU) fehlt -> rot; einen zweiten Vorgang
    verwerfen -> (RED, RED) usw. fehlen -> rot."""
    _c, _s, erg = welt
    paare, dreier, mit_scheiben = Counter(), 0, 0
    for folge in _folgen(erg.ledger).values():
        codes = [c for c, _ in folge]
        paare.update(zip(codes, codes[1:]))
        vorgaenge = [c for c in codes if c in ("RED", "TKU")]
        dreier += len(vorgaenge) >= 3
        mit_scheiben += any(c == "ERH" for c in codes[:codes.index("TKU")]) if "TKU" in codes else 0
    assert ZULAESSIG <= set(paare), sorted(ZULAESSIG - set(paare))
    assert not (UNZULAESSIG & set(paare)), sorted(UNZULAESSIG & set(paare))
    assert dreier >= 1 and mit_scheiben >= 1, (dreier, mit_scheiben)


def test_datenmodell_und_p_b1_nehmen_jede_folge_ohne_befund_an(welt):
    config, stamm, erg = welt
    assert validate_reduktionen(stamm, erg.reduktionen, erg.historie, horizont=BIS) == []
    assert validate_ledger(stamm, erg.ledger, erg.historie, erg.scheiben) == []
    assert pruefe_ledger_betraege(stamm, erg.ledger, config, scheiben=erg.scheiben,
                                  historie=erg.historie, reduktionen=erg.reduktionen) == []


def _stichtage():
    return [_dt.date(j, m, 1) for j in range(2017, 2040, 3) for m in (1, 8)]


@pytest.fixture(scope="module")
def bewertet(welt):
    config, stamm, erg = welt
    gesamt = fuehre_fort(mit_zugaengen(leerer_stamm(), stamm), erg.historie)
    return {s: {int(z["police_id"]): z for z in einzelwerte_am(
        gesamt, erg.historie, config, s, scheiben=erg.scheiben,
        reduktionen=erg.reduktionen)} for s in _stichtage()}


def test_eine_teilkuendigungskette_ist_der_vertrag_mit_dem_produkt(welt, bewertet):
    """Unabhaengige Kontrolle: Eine Police, die nur Teilkuendigungen und
    Erhoehungen erlebt (keine Herabsetzung, keine Freistellung), ist der
    gewoehnliche Vertrag aus Bausteinen mit gekuerzter Summe: die
    Grundversicherung mit S x f^k (k Teilkuendigungen bis zum Stichtag), jede
    Scheibe mit S_i x f^k_i (k_i Teilkuendigungen NACH ihrem Jahrestag) —
    Deckungskapital und Rueckkaufswert monatsgenau, gegen
    ``vertrags_monatsreserve`` ohne Vorgangsfolge. Mutationsproben: die
    zweite Teilkuendigung auf den Ursprungsvertrag statt auf den Zustand
    anwenden -> rot; die Scheiben auslassen (Umfang Grund) -> rot."""
    from rechner_pipeline.kern import erhoehungs_scheibe, vertrags_monatsreserve

    config, stamm, erg = welt
    haupt = stamm.set_index("police_id")
    felder = config.generationen[0].generation_fields()
    geprueft = mehrfach = mit_scheibe = 0
    for pid, folge in _folgen(erg.ledger).items():
        if not folge or any(c not in ("TKU", "ERH") for c, _ in folge) \
                or not any(c == "TKU" for c, _ in folge):
            continue
        beginn = pd.Timestamp(haupt.loc[pid, "insurance_start"])
        mp = ModelPoint(**model_point_kwargs(haupt.loc[pid], felder))
        tku = [j for c, j in folge if c == "TKU"]
        s = erg.scheiben[erg.scheiben["police_id"] == pid]
        for stichtag, zeilen in bewertet.items():
            if pid not in zeilen or zeilen[pid]["status"] != "POL":
                continue
            monate = (stichtag.year - beginn.year) * 12 + stichtag.month - beginn.month
            k = sum(1 for j in tku if 12 * j <= monate)
            if k == 0:
                continue
            grund = Rechenkern(dataclasses.replace(mp, sum_insured=mp.sum_insured * TK_ANTEIL ** k))
            kerne = []
            for e, vs in zip(s["erhoehung_jahr"], s["sum_insured"]):
                if 12 * int(e) > monate:
                    continue
                k_e = sum(1 for j in tku if int(e) < j and 12 * j <= monate)
                scheibe = erhoehungs_scheibe(mp, int(e), float(vs))
                kerne.append((int(e), Rechenkern(dataclasses.replace(
                    scheibe, sum_insured=scheibe.sum_insured * TK_ANTEIL ** k_e))))
            soll = vertrags_monatsreserve(grund, kerne, monate)
            assert zeilen[pid]["deckungskapital"] == pytest.approx(soll.drx_bpfl, rel=1e-9), pid
            assert zeilen[pid]["rueckkaufswert"] == pytest.approx(soll.rkw, rel=1e-9), pid
            geprueft += 1
            mehrfach += k >= 2
            mit_scheibe += bool(kerne)
    assert geprueft >= 5 and mehrfach >= 1 and mit_scheibe >= 1, (geprueft, mehrfach, mit_scheibe)


def test_das_bewegungskonto_schliesst_und_trifft_die_einzelbewertung(welt):
    """Je Jahr, Track und Mass geschlossen; Endbestand beitragspflichtig =
    Summe der gefuehrten Summen, beitragsfrei = Summe der beitragsfreien
    Summen der Einzelbewertung (eine unabhaengige Quelle: die Folge, nicht die
    Ledgerbetraege). Mutationsprobe: die Teilkuendigung nach PEX im
    beitragsfreien Track weglassen -> rot."""
    config, stamm, erg = welt
    konto = bewegungskonto(stamm, erg.historie, erg.ledger, erg.scheiben, bis=BIS)
    assert len(konto) >= 20
    gesamt = fuehre_fort(mit_zugaengen(leerer_stamm(), stamm), erg.historie)
    bfr_tku = 0.0
    for zeile in konto:
        for track, oks in zeile["identitaet"].items():
            assert all(oks.values()), (zeile["jahr"], track, oks)
        bfr_tku += zeile["bfr"]["veraenderung_teilkuendigung"]["summe"]
        if zeile["jahr"] % 4:
            continue
        stichtag = _dt.date(zeile["jahr"] + 1, 1, 1)
        einzeln = einzelwerte_am(gesamt, erg.historie, config, stichtag,
                                 scheiben=erg.scheiben, reduktionen=erg.reduktionen)
        bpfl = sum(z["leistung"] for z in einzeln if z["status"] == "POL")
        bfr = sum(z["vs_bfr"] for z in einzeln if z["status"] == "PEX")
        assert zeile["bpfl"]["ende"]["summe"] == pytest.approx(bpfl, rel=1e-9), zeile["jahr"]
        assert zeile["bfr"]["ende"]["summe"] == pytest.approx(bfr, rel=1e-9), zeile["jahr"]
    assert bfr_tku < 0.0, "keine Teilkuendigung im beitragsfreien Bestand"


def test_jede_auszahlung_ist_der_anteil_des_rueckkaufswerts_davor(welt, bewertet):
    """Die Auszahlung jeder Teilkuendigung ist (1-f) mal der Rueckkaufswert,
    den der Vertrag am Vortag ausweist (Bewertung am selben Jahrestag VOR dem
    Vorgang: die Folge bis zum Vortag). Beitragsfrei: der Rueckkaufswert des
    beitragsfreien Vertrags (B3). Gemessen ueber die Vorgangsfolge der
    Bewertung, nicht die der Engine."""
    from rechner_pipeline.kern.vorgangsfolge import Vorgangsfolge, vorgang
    from rechner_pipeline.bestand.auswertung import _scheiben_kerne, pex_jahr_je_police

    config, stamm, erg = welt
    haupt = stamm.set_index("police_id")
    felder = config.generationen[0].generation_fields()
    scheiben = _scheiben_kerne(stamm, erg.scheiben, config)
    pex = pex_jahr_je_police(stamm, erg.historie)
    led = erg.ledger
    zahl = led[(led["ereignis"] == "TKU") & (led["betrag_art"] == "RKW_teilkuendigung")]
    geprueft = 0
    for z in zahl.to_dict("records")[:60]:
        pid, jahr = int(z["police_id"]), int(z["vertragsjahr"])
        red = erg.reduktionen[erg.reduktionen["police_id"] == pid]
        davor = [vorgang(int(j), float(a), str(v)) for j, a, v in
                 zip(red["reduktion_jahr"], red["anteil"], red["verfahren"])
                 if int(j) < jahr or (int(j) == jahr and v != "teilkuendigung")]
        mp = ModelPoint(**model_point_kwargs(haupt.loc[pid], felder))
        folge = Vorgangsfolge(
            Rechenkern(mp), [(s["erh_jahr"], s["kern"]) for s in scheiben.get(pid, ())
                             if s["erh_jahr"] < jahr],
            davor, pex_jahr=pex.get(pid) if pex.get(pid, 99) <= jahr else None,
            stoab_je_baustein=False, tku_umfang="alle_bausteine")
        rkw = folge.stand_am(12 * jahr).werte(12 * jahr)["rueckkaufswert"]
        if folge.stand_am(12 * jahr).beitragsfrei:
            # Die Bewertung weist beitragsfrei null aus (Stufe 1); der
            # Rueckkaufswert des beitragsfreien Vertrags steht im Zustand.
            rkw = folge.stand_am(12 * jahr)._reserve_bfr(
                12 * jahr, folge.stand_am(12 * jahr).bausteine)["rkw"]
        assert float(z["betrag"]) == pytest.approx((1 - TK_ANTEIL) * rkw, rel=1e-9, abs=1e-6), pid
        geprueft += 1
    assert geprueft >= 20


def _gebuchte_gevos(ledger: pd.DataFrame, pid: int):
    """Die gebuchten Geschaeftsvorfaelle einer Police in der Sprache der
    Lieferung: (Code, Vertragsjahr, Betrag) — der Betrag, den die ENGINE
    gebucht hat (unabhaengig von der Vorgangsfolge der Suite)."""
    art_je_code = {"STO": "RKW", "TOD": "Todesfallleistung", "ABL": "Ablaufleistung",
                   "PEX": "VS_bfr", "ERH": "VS_erhoehung", "RED": "VS_herabsetzung",
                   "TKU": "VS_teilkuendigung"}
    eigene = ledger[ledger["police_id"] == pid]
    aus = []
    for code, betrag_art in art_je_code.items():
        z = eigene[(eigene["ereignis"] == code) & (eigene["betrag_art"] == betrag_art)]
        aus += [(code, int(j), float(b)) for j, b in zip(z["vertragsjahr"], z["betrag"])]
    return aus


def test_migrationssuite_und_a_m3_lesen_dieselbe_folge(welt):
    """Die Pruefstrecke als Leser: Je Police mit mindestens zwei Vorgaengen
    ein Pruefauftrag ueber das ganze Fenster der Vorgaenge — Anfangszustand
    und Folgestichtag aus der Vorgangsfolge des Kerns, die Geschaeftsvorfaelle
    dazwischen so, wie die ENGINE sie gebucht hat (Code, Jahr, Betrag; Anteil
    aus der Nebentabelle). Die Suite faltet sie selbst (eigene Schleife) und
    muss jeden gebuchten Betrag und den Folgewert treffen. A-M3: ein
    Pruefpunkt je Vorgang; die Herabsetzung prospektiv und die
    Beitragsfreistellung sind auf dem Rueckkaufs-Track verlustfrei (dDK 0 bis
    auf die Centrundung der Umwandlung), die Teilkuendigung kostet
    (1-f) x Rueckkaufs-Track der betroffenen Bausteine (Groessen des
    Kern-Ergebnisses je Baustein). Mutationsproben: die Suite verwirft den
    zweiten Vorgang -> Folgewert rot; die Suite liest RED nach PEX als
    Herabsetzung -> benannte Verweigerung -> rot."""
    from rechner_pipeline.bestand.auswertung import _scheiben_kerne, pex_jahr_je_police
    from rechner_pipeline.kern.vorgangsfolge import TKU, Vorgangsfolge, vorgang
    from rechner_pipeline.qa import aktuarieller_test as at
    from rechner_pipeline.qa.migrationssuite import GeVoErwartung, VertragsPruefung, pruefe_vertrag
    from rechner_pipeline.qa.testprofil import Kriterium, Testprofil

    config, stamm, erg = welt
    tarifwerk = config.generationen[0].tarifwerk()
    haupt = stamm.set_index("police_id")
    felder = config.generationen[0].generation_fields()
    kerne_je = _scheiben_kerne(stamm, erg.scheiben, config)
    pex_je = pex_jahr_je_police(stamm, erg.historie)
    profil = Testprofil(kennung="A-M3", weite="vollbestand", kriterien={},
                        grundtoleranz=Kriterium(abs_tol=0.02, rel_tol=1e-9))
    suite_geprueft = at_geprueft = betraege = 0
    for pid, folge in sorted(_folgen(erg.ledger).items()):
        if sum(1 for c, _ in folge if c in ("RED", "TKU")) < 2:
            continue
        mp = ModelPoint(**model_point_kwargs(haupt.loc[pid], felder))
        red = erg.reduktionen[erg.reduktionen["police_id"] == pid]
        vorgaenge = [(int(j), float(a), str(v)) for j, a, v in
                     zip(red["reduktion_jahr"], red["anteil"], red["verfahren"])]
        scheiben = [(s["erh_jahr"], s["kern"]) for s in kerne_je.get(pid, ())]
        pex = pex_je.get(pid)
        kern_folge = Vorgangsfolge(
            Rechenkern(mp), scheiben, [vorgang(*x) for x in vorgaenge], pex_jahr=pex,
            stoab_je_baustein=bool(tarifwerk["stoab_je_baustein"]),
            tku_umfang=str(tarifwerk["tku_umfang"]))

        def wert(monate: int) -> float:
            w = kern_folge.stand_am(monate).werte(monate)
            return w["deckungskapital"] if w["status"] == "PEX" else w["vx_mrv"]

        erstes = min(j for c, j in folge)
        s1 = 12 * erstes - 7
        letztes = max(j for c, j in folge)
        gebucht = _gebuchte_gevos(erg.ledger, pid)
        terminal = [j for c, j, _ in gebucht if c in ("STO", "TOD", "ABL")]
        s2 = 12 * (terminal[0] if terminal else letztes) + (0 if terminal else 5)
        if s2 >= 12 * mp.n:
            continue
        gevos = []
        for code, j, betrag in gebucht:
            if not s1 < 12 * j <= s2:
                continue
            if code in ("RED", "TKU"):
                anteil = next(a for jj, a, v in vorgaenge if jj == j
                              and (v == "teilkuendigung") == (code == "TKU"))
                gevos.append(GeVoErwartung(code, 12 * j, None, anteil=anteil))
            else:
                gevos.append(GeVoErwartung(code, 12 * j, round(betrag, 2)))
        auftrag = VertragsPruefung(
            police_id=str(pid), model_point=dict(dataclasses.asdict(mp)),
            monate_stichtag_1=s1, monate_stichtag_2=s2,
            dk_erwartet_1=round(wert(s1), 2),
            dk_erwartet_2=None if terminal else round(wert(s2), 2),
            gevos=tuple(gevos),
            scheiben=tuple((e, k.mp.sum_insured) for e, k in scheiben if 12 * e <= s1),
            beitragsfrei_seit_jahr=pex if pex is not None and 12 * pex <= s1 else None,
            vorgaenge=tuple(x for x in vorgaenge if 12 * x[0] <= s1),
            stoab_je_baustein=bool(tarifwerk["stoab_je_baustein"]),
            tku_umfang=str(tarifwerk["tku_umfang"]))
        urteil = pruefe_vertrag(auftrag, red_verfahren=str(tarifwerk["red_verfahren"]))
        assert urteil["bestanden"], (pid, folge, urteil["befunde"],
                                     [p for p in urteil["pruefungen"] if not p["ok"]])
        assert not urteil["nicht_geprueft"] or urteil["nicht_geprueft"] == ["bjb_stichtag_1"]
        betraege += sum(1 for p in urteil["pruefungen"] if p["groesse"].startswith("gevo_"))
        suite_geprueft += 1

        punkte = []
        for e in kern_folge.ergebnisse:
            j = e.vorgang.jahr
            if 12 * j >= 12 * mp.n:
                continue
            if e.vorgang.art == TKU:
                soll = sum(r.dk_nach - r.dk_vor for _, r in e.reduktionen)
            else:
                soll = 0.0
            punkte.append(at.Pruefpunkt(monate=12 * j, erwartet={"dDK": round(soll, 2)},
                                        anlass=e.vorgang.art,
                                        parameter={"anteil": e.vorgang.anteil}))
        if pex is not None:
            punkte.append(at.Pruefpunkt(monate=12 * pex, erwartet={"dDK": 0.0}, anlass="PEX"))
        v = at.Vertragspruefung(
            police_id=str(pid), model_point=dict(dataclasses.asdict(mp)), historientyp="folge",
            punkte=tuple(punkte), scheiben=tuple((e, k.mp.sum_insured) for e, k in scheiben),
            stoab_je_baustein=bool(tarifwerk["stoab_je_baustein"]),
            tku_umfang=str(tarifwerk["tku_umfang"]))
        a_m3 = at.pruefe_vertrag(v, profil, red_verfahren=str(tarifwerk["red_verfahren"]))
        assert a_m3["bestanden"], (pid, folge, a_m3["befunde"])
        at_geprueft += 1
    assert suite_geprueft >= 10 and at_geprueft >= 10 and betraege >= 10, (
        suite_geprueft, at_geprueft, betraege)
