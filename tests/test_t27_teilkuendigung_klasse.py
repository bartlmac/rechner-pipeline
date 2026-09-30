"""Die Teilkuendigung ist EIN Vertrag — Pruefrunde T27, Befunde 12 bis 15 und A27-02.

Der Gutachter hat nach dem Bau der Teilkuendigung (T26-12, b637898)
gemessen, was die vier Zusicherungen von damals nicht sahen: Der
herabgesetzte Vertrag lief in einer ZWEITEN WELT (``reduzierte_teile`` +
``vertrags_monatsreserve_reduziert``), die das Tarifwerk der Generation
nicht kannte — kein Stornoabzug je Baustein (T27-12) —, der Beitragsausweis
skalierte Scheiben und Stueckkosten mit dem Anteil (T27-13), P-B1 prueften
nur die vorhandenen Zeilen und vermissten keine Auszahlung (T27-14), die
Leistungszaehlung hielt RED fuer zahlungsfrei (T27-15), und der oeffentliche
P-B1-Weg nahm die Reduktionstabelle nicht entgegen (A27-02).

Die Zusage, gegen die hier JEDER Konsument gemessen wird — Engine, P-B1,
Bewertung —, ist unabhaengig aufgebaut: Nach der Teilkuendigung mit Anteil f
ist der Vertrag die Grundversicherung mit Summe f x S als gewoehnlicher
Rechenkern unter dem vollstaendigen Tarifwerk seiner Generation plus seine
unveraenderten Erhoehungsscheiben (Bedingungswerk Ziffer 6; klv.md 7.1).

Knoten: klv
"""

from __future__ import annotations

import dataclasses
import datetime as _dt
import inspect

import pandas as pd
import pytest

from rechner_pipeline.bestand.auswertung import beitraege, einzelwerte_am, werte_reduziert
from rechner_pipeline.bestand.config import config_aus_text
from rechner_pipeline.bestand.ereignisse import _Vertrag, fortschreiben
from rechner_pipeline.bestand.kennzahlen import bewegungskennzahlen
from rechner_pipeline.bestand.ledger_bindung import _Herleitung, pruefe_ledger_betraege
from rechner_pipeline.bestand.manifest import ROLLEN_DATEIEN
from rechner_pipeline.gates._common import merge_request_into_args
from rechner_pipeline.gates.bestand_validate import _build_parser
from rechner_pipeline.kern import ModelPoint, Rechenkern, vertrags_monatsreserve
from rechner_pipeline.kern.beitragsreduktion import (
    TEILKUENDIGUNG,
    vertrags_monatsreserve_reduziert,
)
from rechner_pipeline.kern.rechenkern import erhoehungs_scheibe
from rechner_pipeline.models.bestand import (
    LEDGER_SPALTEN,
    TAGESJOURNAL_SPALTEN,
    model_point_kwargs,
)
from tests.test_bestand_uebernommen_fortschreiben import _CONFIG_TOML, _stamm
from tests.test_herabsetzung_in_fuehrung import ANTEIL, BIS, POLICEN
from tests.test_schicht_in_fuehrung import MONATE_TA, _parameter, _tabellen


def _config(verfahren: str = TEILKUENDIGUNG, je_baustein: bool = True):
    anker = '[[generation]]\nname = "klv/zellen"\n'
    assert anker in _CONFIG_TOML
    toml = _CONFIG_TOML.replace(
        anker,
        anker + f'red_verfahren = "{verfahren}"\n'
        f'stoab_je_baustein = {"true" if je_baustein else "false"}\n', 1,
    ).replace(
        "[annahmen]\nerh_prozent = 0.05",
        f"[annahmen]\nerh_prozent = 0.05\nred_anteil = {ANTEIL}",
    ) + "\n[annahmen.herabsetzung]\na = 0.08\nb = 0.0\n"
    config = config_aus_text(toml)
    assert config.validate() == []
    return config


@pytest.fixture(scope="module")
def welt():
    """Ein uebernommener Bestand mit Scheiben, Korrekturschicht, Stornoabzug
    je Baustein und Teilkuendigungen — in-memory, ueber die echte Engine."""
    config = _config()
    stamm = _stamm([{"id": p, "beginn": "2015-01-01", "zugang": "2026-01-01"}
                    for p in POLICEN])
    schichten, verankerung = _tabellen(POLICEN)
    erg = fortschreiben(stamm, config, BIS, schichten=schichten, verankerung=verankerung)
    return config, stamm, schichten, verankerung, erg


def _reduktionen(erg) -> pd.DataFrame:
    red = erg.reduktionen
    assert len(red) > 0, "Fixture ohne Teilkuendigung bezeugt nichts"
    assert set(red["verfahren"]) == {TEILKUENDIGUNG}
    return red


def _scheiben_vor(erg, pid: int, jahr: int):
    s = erg.scheiben
    s = s[(s["police_id"] == pid) & (s["erhoehung_jahr"] < jahr)]
    return [(int(j), float(vs)) for j, vs in zip(s["erhoehung_jahr"], s["sum_insured"])]


def _folgevertrag(config, stamm, pid: int, jahr: int):
    """Die Zusage, unabhaengig gebaut: f x S als gewoehnlicher Kern, dazu die
    unveraenderten Scheiben — kein Aufruf des reduzierten Pfads."""
    gen = config.generationen[0]
    haupt = stamm.set_index("police_id")
    mp = ModelPoint(**model_point_kwargs(haupt.loc[pid], gen.generation_fields()))
    grund_neu = Rechenkern(dataclasses.replace(mp, sum_insured=ANTEIL * mp.sum_insured))
    return mp, grund_neu


def _scheiben_kerne(mp: ModelPoint, config, scheiben):
    gamma1 = bool(config.generationen[0].tarifwerk()["scheiben_mit_gamma1"])
    return [(j, vs, Rechenkern(erhoehungs_scheibe(mp, j, vs, gamma1_uebernehmen=gamma1)))
            for j, vs in scheiben]


def _soll_rkw(grund_neu, scheiben_kerne, jahr: int) -> float:
    return vertrags_monatsreserve(
        grund_neu, [(j, k) for j, _, k in scheiben_kerne], 12 * jahr,
        stoab_je_baustein=True).rkw


# --------------------------------------------------------------------------- #
# T27-12: der Rueckkaufswert nach der Teilkuendigung traegt den Abzug je Baustein
# --------------------------------------------------------------------------- #


def test_die_engine_rechnet_den_folgevertrag_mit_dem_tarifwerk_der_generation(welt):
    """Mutationsprobe: ``stoab_je_baustein`` in ``_Vertrag.rkw`` nach der
    Herabsetzung nicht durchreichen -> rot (Differenz = Mindestabzug je
    Scheibe, weit ueber Rundung)."""
    config, stamm, schichten, verankerung, erg = welt
    gen = config.generationen[0]
    mit_scheibe = 0
    for z in _reduktionen(erg).to_dict("records"):
        pid, jahr = int(z["police_id"]), int(z["reduktion_jahr"])
        scheiben = _scheiben_vor(erg, pid, jahr)
        if not scheiben:
            continue
        mp, grund_neu = _folgevertrag(config, stamm, pid, jahr)
        kerne = _scheiben_kerne(mp, config, scheiben)
        v = _Vertrag(mp, tarifwerk=gen.tarifwerk(), mitgebracht=kerne,
                     schicht=(_parameter(), MONATE_TA))
        v.herabsetzen(jahr, ANTEIL, TEILKUENDIGUNG)
        for j in range(jahr + 1, mp.n):
            assert v.rkw(j) == pytest.approx(_soll_rkw(grund_neu, kerne, j), rel=1e-9), (pid, j)
        mit_scheibe += 1
    assert mit_scheibe > 0, "keine Teilkuendigung mit Scheibe davor — der Abzug je Baustein bliebe ungesehen"


def test_p_b1_leitet_den_folgevertrag_mit_dem_tarifwerk_her(welt):
    """Dieselbe Zusage, gemessen an der Herleitung, die die Engine WIDERLEGEN
    soll — sie darf nicht dieselbe Luecke haben."""
    config, stamm, schichten, verankerung, erg = welt
    gen = config.generationen[0]
    haupt = stamm.set_index("police_id")
    geprueft = 0
    for z in _reduktionen(erg).to_dict("records"):
        pid, jahr = int(z["police_id"]), int(z["reduktion_jahr"])
        scheiben = _scheiben_vor(erg, pid, jahr)
        if not scheiben:
            continue
        mp, grund_neu = _folgevertrag(config, stamm, pid, jahr)
        kerne = _scheiben_kerne(mp, config, scheiben)
        h = _Herleitung(haupt.loc[pid].to_dict() | {"police_id": pid},
                        gen.generation_fields(), scheiben, gen.tarifwerk())
        h.setze_reduktion(jahr, ANTEIL, TEILKUENDIGUNG, (_parameter(), MONATE_TA))
        for j in range(jahr + 1, mp.n):
            assert h.rkw(j) == pytest.approx(_soll_rkw(grund_neu, kerne, j), rel=1e-9), (pid, j)
        geprueft += 1
    assert geprueft > 0


def _stichtag_nach(erg, pid: int, jahre: int = 1, monate: int = 0):
    red = erg.reduktionen
    datum = pd.Timestamp(red.loc[red["police_id"] == pid, "reduktion_datum"].iloc[0])
    stichtag = (datum + pd.DateOffset(years=jahre, months=monate)).date()
    h = erg.historie
    terminal = h[(h["police_id"] == pid) & (h["status_code"].isin(["STO", "TOD", "ABL"]))
                 & (h["status_date"] <= pd.Timestamp(stichtag))]
    return None if len(terminal) or stichtag > BIS else stichtag


def _bewertung(welt, pid: int, stichtag):
    config, stamm, schichten, verankerung, erg = welt
    zeilen = einzelwerte_am(
        stamm, erg.historie, config, stichtag, scheiben=erg.scheiben,
        schichten=schichten, verankerung=verankerung, reduktionen=erg.reduktionen)
    return next(z for z in zeilen if int(z["police_id"]) == pid)


def test_die_bewertung_weist_den_rueckkaufswert_des_folgevertrags_aus(welt):
    config, stamm, schichten, verankerung, erg = welt
    geprueft = 0
    for z in _reduktionen(erg).to_dict("records"):
        pid, jahr = int(z["police_id"]), int(z["reduktion_jahr"])
        scheiben = _scheiben_vor(erg, pid, jahr)
        stichtag = _stichtag_nach(erg, pid)
        if not scheiben or stichtag is None:
            continue
        mp, grund_neu = _folgevertrag(config, stamm, pid, jahr)
        kerne = _scheiben_kerne(mp, config, scheiben)
        zeile = _bewertung(welt, pid, stichtag)
        assert zeile["rueckkaufswert"] == pytest.approx(
            _soll_rkw(grund_neu, kerne, jahr + 1), rel=1e-9), pid
        geprueft += 1
    assert geprueft > 0


def test_die_bewertung_am_unterjaehrigen_stichtag_nimmt_die_jahreszeile(welt):
    """Kalibrierungsfund N5: Der reduzierte Verlauf interpolierte innerhalb
    des Vertragsjahres, jeder gewoehnliche Vertrag rechnet die Zeile des
    angebrochenen Jahres. Am 1.12. lag das Deckungskapital um 11/12 des
    Jahreszuwachses zu hoch. Mutationsprobe: ``12 * jahr`` zurueck auf
    ``months_exp`` -> rot."""
    config, stamm, schichten, verankerung, erg = welt
    geprueft = 0
    for z in _reduktionen(erg).to_dict("records"):
        pid, jahr = int(z["police_id"]), int(z["reduktion_jahr"])
        stichtag = _stichtag_nach(erg, pid, jahre=1, monate=7)
        if stichtag is None:
            continue
        scheiben = _scheiben_vor(erg, pid, jahr)
        mp, grund_neu = _folgevertrag(config, stamm, pid, jahr)
        kerne = _scheiben_kerne(mp, config, scheiben)
        soll = vertrags_monatsreserve(
            grund_neu, [(j, k) for j, _, k in kerne], 12 * (jahr + 1), stoab_je_baustein=True)
        zeile = _bewertung(welt, pid, stichtag)
        assert zeile["deckungskapital"] == pytest.approx(soll.drx_bpfl, rel=1e-9), pid
        assert zeile["rueckkaufswert"] == pytest.approx(soll.rkw, rel=1e-9), pid
        geprueft += 1
    assert geprueft > 0


# --------------------------------------------------------------------------- #
# T27-13: Beitraege komponentenweise — Scheiben unveraendert, Stueckkosten fix
# --------------------------------------------------------------------------- #


def test_der_beitragsausweis_rechnet_den_folgevertrag_komponentenweise(welt):
    """Jahresbeitrag = f x BJB(Grund) + BJB(jede Scheibe); Zahlvolumen =
    Zahlbeitrag des f x S-Kerns (Stueckkosten NICHT skaliert) + das jeder
    Scheibe. Mutationsprobe: ``bt * anteil`` ueber die Gesamtsumme -> rot,
    auch ohne Scheibe (Stueckkosten)."""
    config, stamm, schichten, verankerung, erg = welt
    ohne_scheibe = mit_scheibe = 0
    for z in _reduktionen(erg).to_dict("records"):
        pid, jahr = int(z["police_id"]), int(z["reduktion_jahr"])
        stichtag = _stichtag_nach(erg, pid)
        if stichtag is None:
            continue
        scheiben = _scheiben_vor(erg, pid, jahr)
        mp, grund_neu = _folgevertrag(config, stamm, pid, jahr)
        kerne = _scheiben_kerne(mp, config, scheiben)
        j = jahr + 1
        if j >= mp.t:
            continue
        soll = beitraege(grund_neu, j)
        for e, _, k in kerne:
            bt = beitraege(k, j - e)
            soll = {n: soll[n] + bt[n] for n in soll}
        zeile = _bewertung(welt, pid, stichtag)
        assert zeile["jahresbeitrag"] == pytest.approx(soll["bjb"], rel=1e-9), pid
        assert zeile["bzb_jahr"] == pytest.approx(soll["bzb_jahr"], rel=1e-9), pid
        if scheiben:
            mit_scheibe += 1
        else:
            ohne_scheibe += 1
    assert mit_scheibe > 0 and ohne_scheibe > 0, (mit_scheibe, ohne_scheibe)


# --------------------------------------------------------------------------- #
# T27-14: P-B1 vermisst fehlende Zeilen — Soll-Menge aus der Reduktionstabelle
# --------------------------------------------------------------------------- #


def _voll(welt, ledger: pd.DataFrame) -> pd.DataFrame:
    config, stamm, *_ = welt
    gen = config.generationen[0]
    zug = pd.DataFrame([{
        "police_id": pid, "tarif_generation": gen.name, "ereignis": "ZUG",
        "vertragsjahr": 11, "status_date": pd.Timestamp("2026-01-01"),
        "betrag_art": "VS", "betrag": 100_000.0, "betrag_herkunft": "geliefert",
    } for pid in POLICEN])[[n for n, _ in LEDGER_SPALTEN]].astype(dict(LEDGER_SPALTEN))
    return pd.concat([zug, ledger], ignore_index=True)


def _pb1(welt, ledger: pd.DataFrame, reduktionen=None):
    config, stamm, schichten, verankerung, erg = welt
    return pruefe_ledger_betraege(
        stamm, _voll(welt, ledger), config, scheiben=erg.scheiben, historie=erg.historie,
        schichten=schichten, verankerung=verankerung,
        reduktionen=erg.reduktionen if reduktionen is None else reduktionen)


def test_p_b1_bestaetigt_den_vollstaendigen_lauf(welt):
    assert _pb1(welt, welt[4].ledger) == []


@pytest.mark.parametrize("art", ["RKW_teilkuendigung", "dDK_absorption", "VS_herabsetzung"])
def test_p_b1_vermisst_jede_fehlende_zeile_einer_bekannten_reduktion(welt, art):
    """Alle Zeilen einer Betragsart entfernt, Tabelle unveraendert: Die
    Reduktion ist bekannt, ihre Buchung fehlt — das ist ein Fehler, keine
    leere Pruefliste. Mutationsprobe: die Soll-Menge nicht bilden -> gruen."""
    led = welt[4].ledger
    ohne = led[~((led["ereignis"] == "RED") & (led["betrag_art"] == art))]
    assert len(ohne) < len(led)
    fehler = _pb1(welt, ohne)
    assert fehler, art
    assert any(art in f for f in fehler), fehler


def test_p_b1_vermisst_eine_einzelne_auszahlung(welt):
    led = welt[4].ledger
    idx = led.index[(led["ereignis"] == "RED") & (led["betrag_art"] == "RKW_teilkuendigung")][:1]
    fehler = _pb1(welt, led.drop(idx))
    assert fehler and any("RKW_teilkuendigung" in f for f in fehler), fehler


def test_p_b1_weist_eine_auszahlung_ab_die_das_verfahren_nicht_erzeugt(welt):
    """Kalibrierungsfund N2: Die Auszahlung wurde hergeleitet, ohne das
    Verfahren zu befragen — eine prospektive Herabsetzung mit
    RKW_teilkuendigung-Zeile passierte. Die Soll-Menge ist je Verfahren."""
    erg = welt[4]
    red = erg.reduktionen.copy()
    pid = int(red["police_id"].iloc[0])
    red.loc[red["police_id"] == pid, "verfahren"] = "prospektiv"
    fehler = _pb1(welt, erg.ledger, reduktionen=red)
    assert any("RKW_teilkuendigung" in f and str(pid) in f for f in fehler), fehler


def test_p_b1_erkennt_eine_reduktion_ohne_tabellenzeile(welt):
    """Umgekehrt: Ledger bucht RED, die Tabelle kennt die Police nicht."""
    erg = welt[4]
    red = erg.reduktionen
    fehler = _pb1(welt, erg.ledger, reduktionen=red.iloc[1:])
    assert fehler, "RED-Buchung ohne registrierte Reduktion passiert"


# --------------------------------------------------------------------------- #
# T27-15: die Auszahlung der Teilkuendigung ist eine Leistung
# --------------------------------------------------------------------------- #


def _journal(zeilen) -> pd.DataFrame:
    df = pd.DataFrame([{
        "buchungsdatum": pd.Timestamp(z["tag"]), "police_id": z["pid"],
        "ereignis": z["ereignis"], "status_date": pd.Timestamp(z["tag"]),
        "betrag": float(z["betrag"]), "betrag_art": z["art"],
        "herkunft": "fortschreibung",
    } for z in zeilen])
    return df[[n for n, _ in TAGESJOURNAL_SPALTEN]].astype(dict(TAGESJOURNAL_SPALTEN))


def test_die_teilkuendigung_zaehlt_als_eine_leistung_die_prospektive_nicht():
    tag = "2026-03-01"
    tk = _journal([
        {"tag": tag, "pid": 1, "ereignis": "RED", "betrag": 60_000.0, "art": "VS_herabsetzung"},
        {"tag": tag, "pid": 1, "ereignis": "RED", "betrag": 0.02, "art": "dDK_absorption"},
        {"tag": tag, "pid": 1, "ereignis": "RED", "betrag": 7_751.14, "art": "RKW_teilkuendigung"},
    ])
    plv = _journal([
        {"tag": tag, "pid": 2, "ereignis": "RED", "betrag": 60_000.0, "art": "VS_herabsetzung"},
        {"tag": tag, "pid": 2, "ereignis": "RED", "betrag": 0.02, "art": "dDK_absorption"},
    ])
    sto = _journal([{"tag": tag, "pid": 3, "ereignis": "STO", "betrag": 5_000.0, "art": "RKW"}])
    stichtag = _dt.date(2026, 3, 1)
    assert bewegungskennzahlen(sto, stichtag)["leistungen"] == 1     # Kontrolle
    assert bewegungskennzahlen(tk, stichtag)["leistungen"] == 1      # EIN Vorfall, nicht drei Zeilen
    assert bewegungskennzahlen(plv, stichtag)["leistungen"] == 0
    assert bewegungskennzahlen(tk, stichtag)["zugaenge"] == 0


# --------------------------------------------------------------------------- #
# A27-02: der oeffentliche P-B1-Weg nimmt JEDE Rolle des Erzeugers entgegen
# --------------------------------------------------------------------------- #


def test_jede_rolle_des_erzeugers_hat_ein_flag_und_einen_request_schluessel():
    parser = _build_parser()
    dests = {a.dest for a in parser._actions}
    fehlend = [r for r in ROLLEN_DATEIEN if r not in dests]
    assert fehlend == [], f"Rollen ohne Flag: {fehlend}"
    args = parser.parse_args(["--portfolio", "p.parquet", "--reduktionen", "r.parquet"])
    assert args.reduktionen == "r.parquet"
    leer = parser.parse_args(["--portfolio", "p.parquet"])
    merge_request_into_args(leer, {"reduktionen": "aus-request.parquet"})
    assert leer.reduktionen == "aus-request.parquet"


# --------------------------------------------------------------------------- #
# Ratsche: das Tarifwerk ist kein Default — wer den reduzierten Verlauf
# bewertet, muss es hinschreiben
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("funktion", [vertrags_monatsreserve_reduziert, werte_reduziert])
def test_das_tarifwerk_hat_im_reduzierten_pfad_keinen_default(funktion):
    p = inspect.signature(funktion).parameters["stoab_je_baustein"]
    assert p.kind is inspect.Parameter.KEYWORD_ONLY
    assert p.default is inspect.Parameter.empty, funktion.__name__


# --------------------------------------------------------------------------- #
# Angriffsrunde 2 auf den gefixten Stand: N10/N14, N11, N12, N15, N16, N6
# --------------------------------------------------------------------------- #


def test_der_folgevertrag_traegt_nur_seinen_zillmer_rest():
    """N10: Der Zahlungspfad mit q = 0 fuehrte den Zillmer-Rueckstand des
    UNGEKUERZTEN Vertrags weiter; in der Zillmerdauer lag der
    Rueckkaufswert um (1-f) x alpha x t x BJB x azd/azd_full zu hoch. Der
    Test von T26-12 verglich ab Jahr 10 — nach der Zillmerdauer — und war
    blind. Hier: Reduktion in Jahr 1, Vergleich in JEDEM Jahr, Soll ist der
    zustandslose Kern mit f x S. Mutationsprobe: die Delegation an den
    folgekern in monatsreserve entfernen -> rot in den Jahren 1-4."""
    from rechner_pipeline.kern import KLV_DEFAULT
    from rechner_pipeline.kern.beitragsreduktion import reduzierte_teile

    grund = Rechenkern(KLV_DEFAULT)
    f = 0.6
    teile = reduzierte_teile(grund, [], 1, f, TEILKUENDIGUNG)
    soll_kern = Rechenkern(dataclasses.replace(KLV_DEFAULT, sum_insured=f * KLV_DEFAULT.sum_insured))
    for j in range(1, 8):
        ist = vertrags_monatsreserve_reduziert(teile, 12 * j, stoab_je_baustein=False)
        soll = soll_kern.monatsreserve(12 * j)
        assert ist.vx_mrv == pytest.approx(soll.vx_mrv, rel=1e-9), j
        assert ist.rkw == pytest.approx(soll.rkw, rel=1e-9), j
        assert ist.drx_bpfl == pytest.approx(soll.drx_bpfl, rel=1e-9), j
    # N14: auch die beitragsfreie Fortfuehrung nach der Teilkuendigung ist
    # die des f x S-Kerns — kein Sprung zwischen Reserve und Summe.
    v = teile[0][1]
    assert v.beitragsfreie_summe(3) == pytest.approx(soll_kern.beitragsfreie_summe(3), rel=1e-12)
    assert v.reserve_beitragsfrei(3, 12 * 5) == pytest.approx(
        soll_kern.monatsreserve_beitragsfrei(3, 12 * 5), rel=1e-12)


def test_die_bewertung_nach_beitragsfreistellung_nimmt_die_jahreszeile():
    """N11: der PEX-Zweig von werte_reduziert interpolierte monatsgenau —
    Saegezahn auf einer Bilanzzahl. Mutationsprobe: months_exp statt
    12 * jahr im PEX-Zweig -> rot."""
    from rechner_pipeline.kern import KLV_DEFAULT
    from rechner_pipeline.kern.beitragsreduktion import PROSPEKTIV, reduzierte_teile

    teile = reduzierte_teile(Rechenkern(KLV_DEFAULT), [], 8, 0.6, PROSPEKTIV)
    am_jahrestag = werte_reduziert(teile, 168, 12, stoab_je_baustein=False)["deckungskapital"]
    mitten_im_jahr = werte_reduziert(teile, 174, 12, stoab_je_baustein=False)["deckungskapital"]
    naechster = werte_reduziert(teile, 180, 12, stoab_je_baustein=False)["deckungskapital"]
    assert mitten_im_jahr == pytest.approx(am_jahrestag, rel=1e-12)
    assert naechster != pytest.approx(am_jahrestag, rel=1e-6)


def test_der_bestandsbericht_bekommt_die_reduktionstabelle(tmp_path, monkeypatch):
    """N12: cli_report las reduktionen.parquet und reichte es nicht an die
    Bewertung weiter — jeder herabgesetzte Vertrag stand ungekuerzt im
    Bericht (+32 bis +48 % Deckungskapital). Mutationsprobe: das Argument
    im render_html-Aufruf entfernen -> rot."""
    from rechner_pipeline.bestand import cli_report as cli
    from tests.test_herabsetzung_in_fuehrung import _lauf_mit_herabsetzung

    out, cfg = _lauf_mit_herabsetzung(tmp_path)
    gesehen = {}
    echt = cli.render_html

    def merkend(*a, **kw):
        gesehen.update(kw)
        return echt(*a, **kw)

    monkeypatch.setattr(cli, "render_html", merkend)
    code = cli.main([
        "--portfolio", str(out / "bestand_gesamt.parquet"), "--historie", str(out / "historie.parquet"),
        "--ledger", str(out / "ledger.parquet"), "--scheiben", str(out / "scheiben.parquet"),
        "--bis", "2046-01-01", "--stichtag", "2030-01-01", "--out", str(tmp_path / "bericht.html"),
        "--config", str(cfg),
    ])
    assert code == 0
    assert gesehen.get("reduktionen") is not None and len(gesehen["reduktionen"]) > 0


def test_eine_negative_korrekturschicht_ist_eine_umbuchung_mit_vorzeichen(welt):
    """N15: der Erzeuger bucht dDK_absorption mit Vorzeichen (negatives
    Residuum), das Datenmodell wies jeden Betrag < 0 ausser MIG ab — ein
    korrekter Lauf war nicht validierbar. Mutationsprobe: die Ausnahme fuer
    dDK_absorption entfernen -> rot."""
    from rechner_pipeline.models.bestand import validate_ledger

    config, stamm, schichten, verankerung, erg = welt
    led = erg.ledger.copy()
    idx = led.index[(led["ereignis"] == "RED") & (led["betrag_art"] == "dDK_absorption")][:1]
    assert len(idx) == 1
    led.loc[idx, "betrag"] = -0.02
    fehler = validate_ledger(stamm, led, erg.historie, erg.scheiben)
    assert not any("betrag < 0" in f for f in fehler), fehler
    sto = led.index[led["ereignis"] == "STO"][:1]
    if len(sto):
        led.loc[sto, "betrag"] = -1.0
        assert any("betrag < 0" in f for f in validate_ledger(stamm, led, erg.historie, erg.scheiben))


def test_die_reduktionstabelle_ist_an_jahrestag_und_buchung_gebunden(welt):
    """N16: reduktion_datum war an nichts gebunden — zwei Sichten desselben
    Bestands zum selben Stichtag wichen um 20.880 EUR ab, bei gruenem P-B1.
    Jetzt: das Datum ist der Jahrestag des Reduktionsjahres (Datenmodell),
    und die RED-Buchung traegt genau diesen Wirkungstag (P-B1)."""
    from rechner_pipeline.models.bestand import validate_reduktionen

    config, stamm, schichten, verankerung, erg = welt
    red = erg.reduktionen.copy()
    assert validate_reduktionen(stamm, red, erg.historie) == []
    red.loc[red.index[0], "reduktion_datum"] = red.loc[red.index[0], "reduktion_datum"] + pd.DateOffset(months=1)
    fehler = validate_reduktionen(stamm, red, erg.historie)
    assert any("Jahrestag" in f for f in fehler), fehler
    # P-B1: Tabelle verschoben, Ledger unveraendert -> Wirkungstag passt nicht.
    pb1 = _pb1(welt, erg.ledger, reduktionen=red)
    assert any("Wirkungstag" in f for f in pb1), pb1


def test_die_teilkuendigung_im_beitragsfreien_nachlauf_ist_im_datenmodell_zulaessig(welt):
    """N6: der Kern rechnet die Teilkuendigung auch nach dem Beitragsende
    (t <= jahr < n, Kern 3.4.0), validate_reduktionen wies sie ab — ein
    Vertragsbruch zwischen Kern und Datenmodell."""
    from rechner_pipeline.models.bestand import validate_reduktionen

    config, stamm, schichten, verankerung, erg = welt
    stamm2 = stamm.copy()
    pid = int(stamm2["police_id"].iloc[0])
    stamm2.loc[stamm2["police_id"] == pid, "premium_duration"] = 20
    beginn = pd.Timestamp(stamm2.loc[stamm2["police_id"] == pid, "insurance_start"].iloc[0])
    zeile = lambda verfahren: pd.DataFrame([{
        "police_id": pid, "reduktion_jahr": 22, "reduktion_datum": beginn + pd.DateOffset(years=22),
        "anteil": ANTEIL, "verfahren": verfahren}])
    assert validate_reduktionen(stamm2, zeile(TEILKUENDIGUNG), None) == []
    assert any("Beitragszahlungsdauer" in f for f in validate_reduktionen(stamm2, zeile("prospektiv"), None))


# --------------------------------------------------------------------------- #
# Angriffsrunde 4: Auszahlung mit Vorzeichen, PEX-Grenze der TK, P-B1-Wache, Bericht ohne --scheiben
# --------------------------------------------------------------------------- #


def test_eine_negative_auszahlung_wird_auf_null_gekappt_und_ausgewiesen():
    """Entscheid 2026-09-26: Faellt die Auszahlung der Teilkuendigung unter
    null (Schicht negativer als der Rueckkaufswert-Anteil), wird auf null
    gekappt — kein Kunde bekommt aus einer Migrationsdifferenz eine
    Nachzahlungsforderung. Der gekappte Betrag steht als eigene Zeile
    Kappung_teilkuendigung im Ledger, P-B1 leitet beide her, das
    Datenmodell weist negative Auszahlungen ab. Mutationsprobe: max(0, ...)
    entfernen -> rot; Kappungszeile nicht buchen -> P-B1 rot."""
    from rechner_pipeline.bestand.kernlauf import vertrags_rkw
    from rechner_pipeline.kern.korrekturschicht import schichtwert_bei
    from rechner_pipeline.models.bestand import validate_ledger

    config = _config()
    gen = config.generationen[0]
    stamm = _stamm([{"id": p, "beginn": "2015-01-01", "zugang": "2026-01-01"} for p in POLICEN])
    schichten, verankerung = _tabellen(POLICEN, rho=-0.03)
    erg = fortschreiben(stamm, config, BIS, schichten=schichten, verankerung=verankerung)
    red, led = erg.reduktionen, erg.ledger
    assert len(red) > 0
    haupt = stamm.set_index("police_id")
    gekappt = 0
    for z in red.to_dict("records"):
        pid, jahr = int(z["police_id"]), int(z["reduktion_jahr"])
        mp = ModelPoint(**model_point_kwargs(haupt.loc[pid], gen.generation_fields()))
        rechnerisch = (1 - ANTEIL) * vertrags_rkw(
            Rechenkern(mp), [], jahr, stoab_je_baustein=True
        ) + schichtwert_bei(_parameter(rho=-0.03), MONATE_TA, mp, 12 * jahr)
        eigene = led[(led["police_id"] == pid) & (led["ereignis"] == "RED")]
        arten = dict(zip(eigene["betrag_art"], eigene["betrag"]))
        assert arten["RKW_teilkuendigung"] == pytest.approx(max(0.0, rechnerisch), abs=1e-6)
        if rechnerisch < 0:
            gekappt += 1
            assert arten["Kappung_teilkuendigung"] == pytest.approx(-rechnerisch, rel=1e-9)
        else:
            assert "Kappung_teilkuendigung" not in arten
    assert gekappt > 0, "keine Kappung in der Welt — der Test bezeugt nichts"
    assert not any("betrag < 0" in f for f in validate_ledger(stamm, led, erg.historie, erg.scheiben))
    assert not (led.loc[led["betrag_art"] == "RKW_teilkuendigung", "betrag"] < 0).any()
    zug = pd.DataFrame([{
        "police_id": pid, "tarif_generation": gen.name, "ereignis": "ZUG",
        "vertragsjahr": 11, "status_date": pd.Timestamp("2026-01-01"),
        "betrag_art": "VS", "betrag": 100_000.0, "betrag_herkunft": "geliefert",
    } for pid in POLICEN])[[n for n, _ in LEDGER_SPALTEN]].astype(dict(LEDGER_SPALTEN))
    voll = pd.concat([zug, led], ignore_index=True)
    assert pruefe_ledger_betraege(
        stamm, voll, config, scheiben=erg.scheiben, historie=erg.historie,
        schichten=schichten, verankerung=verankerung, reduktionen=red) == []
    ohne = voll[voll["betrag_art"] != "Kappung_teilkuendigung"]
    fehler = pruefe_ledger_betraege(
        stamm, ohne, config, scheiben=erg.scheiben, historie=erg.historie,
        schichten=schichten, verankerung=verankerung, reduktionen=red)
    assert any("Kappung_teilkuendigung" in f for f in fehler), fehler
    # Eine NEGATIVE Auszahlungszeile ist wieder ein Formfehler.
    neg = led.copy()
    i = neg.index[neg["betrag_art"] == "RKW_teilkuendigung"][0]
    neg.loc[i, "betrag"] = -1.0
    assert any("betrag < 0" in f for f in validate_ledger(stamm, neg, erg.historie, erg.scheiben))


def test_die_teilkuendigung_liegt_vor_einer_beitragsfreistellung(welt):
    """Runde 4 hatte die Teilkuendigung NACH der Beitragsfreistellung
    zugelassen (Ziffer 6 kuendige nur einen Summenanteil). Runde C,
    Befund RC03, hat das zurueckgenommen: Die Engine zieht fuer
    beitragsfreie Vertraege keine Herabsetzung, und die Bewertung bricht
    ab (``Beitragsfreistellung im Jahr p vor der Reduktion (Jahr r)``) —
    P-B1 nahm eine Auszahlung vom 4,6-fachen der beitragsfreien Reserve
    an. Jetzt gilt fuer JEDES Verfahren: Reduktionsjahr < PEX-Jahr.
    Mutationsprobe: die PEX-Jahr-Regel in validate_reduktionen entfernen
    -> die ersten beiden Aussagen kippen."""
    from rechner_pipeline.models.bestand import validate_reduktionen

    config, stamm, schichten, verankerung, erg = welt
    pid = int(stamm["police_id"].iloc[0])
    beginn = pd.Timestamp(stamm.loc[stamm["police_id"] == pid, "insurance_start"].iloc[0])
    historie = pd.DataFrame([{"police_id": pid, "status_id": 2, "status_code": "PEX",
                              "status_date": beginn + pd.DateOffset(years=13)}])
    zeile = lambda verfahren, jahr=14: pd.DataFrame([{
        "police_id": pid, "reduktion_jahr": jahr, "reduktion_datum": beginn + pd.DateOffset(years=jahr),
        "anteil": ANTEIL, "verfahren": verfahren}])
    fehler = validate_reduktionen(stamm, zeile(TEILKUENDIGUNG), historie)
    assert any("Zustandswechsel" in f and "Teilkuendigung" in f for f in fehler), fehler
    assert any("Zustandswechsel" in f for f in validate_reduktionen(stamm, zeile("prospektiv"), historie))
    # Im PEX-Jahr selbst ist der Vertrag schon beitragsfrei (Engine: PEX vor RED).
    assert validate_reduktionen(stamm, zeile(TEILKUENDIGUNG, 13), historie)
    # Positivkontrolle: VOR der Beitragsfreistellung bleibt sie zulaessig.
    assert validate_reduktionen(stamm, zeile(TEILKUENDIGUNG, 12), historie) == []
    tod = pd.DataFrame([{"police_id": pid, "status_id": 2, "status_code": "TOD",
                         "status_date": beginn + pd.DateOffset(years=14)}])
    assert any("nichts mehr zu kuendigen" in f for f in validate_reduktionen(stamm, zeile(TEILKUENDIGUNG), tod))


def test_p_b1_verlangt_die_reduktionstabelle_wenn_der_ledger_red_traegt(tmp_path):
    """Runde 4: wie ERH -> --scheiben. Ohne die Tabelle ist das ein
    Bedienfehler (usage), kein Befund gegen den Lauf."""
    from rechner_pipeline.bestand.manifest import lauf_eingaben, lies_manifest
    from rechner_pipeline.bestand.vorbedingungen import lies_und_pruefe_pb1
    from tests.test_herabsetzung_in_fuehrung import _lauf_mit_herabsetzung

    out, cfg = _lauf_mit_herabsetzung(tmp_path)
    eingaben = dict(lauf_eingaben(out, cfg))
    eingaben.pop("reduktionen", None)
    _t, _g, _f, usage = lies_und_pruefe_pb1(eingaben, bis=_dt.date(2046, 1, 1), manifest=None)
    assert any("--reduktionen" in u.get("message", "") for u in usage), usage


def test_der_bestandsbericht_findet_die_reduktionstabelle_neben_dem_ledger(tmp_path, monkeypatch):
    """Runde 4: Die Nebentabellen wurden nur neben --scheiben gesucht. Liegt
    die Scheibentabelle anderswo (oder gibt es keine), fand der Bericht
    reduktionen.parquet nicht und bewertete ungekuerzt. Jetzt: auch neben
    dem Ledger. Mutationsprobe: die Ledger-Nachbarschaft nicht durchsuchen
    -> rot."""
    import shutil

    from rechner_pipeline.bestand import cli_report as cli
    from tests.test_herabsetzung_in_fuehrung import _lauf_mit_herabsetzung

    out, cfg = _lauf_mit_herabsetzung(tmp_path)
    anderswo = tmp_path / "anderswo"
    anderswo.mkdir()
    shutil.copyfile(out / "scheiben.parquet", anderswo / "scheiben.parquet")
    gesehen = {}
    echt = cli.render_html

    def merkend(*a, **kw):
        gesehen.update(kw)
        return echt(*a, **kw)

    monkeypatch.setattr(cli, "render_html", merkend)
    code = cli.main([
        "--portfolio", str(out / "bestand_gesamt.parquet"), "--historie", str(out / "historie.parquet"),
        "--ledger", str(out / "ledger.parquet"), "--scheiben", str(anderswo / "scheiben.parquet"),
        "--bis", "2046-01-01", "--stichtag", "2030-01-01", "--out", str(tmp_path / "bericht.html"),
        "--config", str(cfg),
    ])
    assert code == 0
    assert gesehen.get("reduktionen") is not None and len(gesehen["reduktionen"]) > 0


def test_verfahren_und_anteil_der_reduktionstabelle_sind_an_die_config_gebunden(welt):
    """Angriffsrunde 2026-09-26: Eine Teilkuendigung, in der Tabelle als
    prospektiv eingetragen (Auszahlungs- und Kappungszeile entfernt),
    passierte P-B1. Mutationsprobe: die Bindung entfernen -> rot."""
    erg = welt[4]
    red = erg.reduktionen.copy()
    pid = int(red["police_id"].iloc[0])
    red.loc[red["police_id"] == pid, "verfahren"] = "prospektiv"
    led = erg.ledger[~((erg.ledger["police_id"] == pid)
                       & erg.ledger["betrag_art"].isin(["RKW_teilkuendigung", "Kappung_teilkuendigung"]))]
    assert any("Tarifwerk" in f and str(pid) in f for f in _pb1(welt, led, reduktionen=red))
    red2 = erg.reduktionen.copy()
    red2.loc[red2["police_id"] == pid, "anteil"] = 0.3
    assert any("red_anteil" in f and str(pid) in f for f in _pb1(welt, erg.ledger, reduktionen=red2))


def test_p_b1_verlangt_die_schicht_tabelle_wenn_der_ledger_eine_schicht_absorbiert(tmp_path):
    """Angriffsrunde 2026-09-26: Ohne --schichten meldete P-B1 den korrekten
    Lauf als falsch gebucht (Exit 20) statt eines Bedienfehlers."""
    from rechner_pipeline.bestand.parquet_io import write_portfolio
    from rechner_pipeline.bestand.vorbedingungen import lies_und_pruefe_pb1

    stamm = _stamm([{"id": p, "beginn": "2015-01-01", "zugang": "2026-01-01"} for p in POLICEN])
    schichten, verankerung = _tabellen(POLICEN)
    uebernahme = tmp_path / "zugang"
    uebernahme.mkdir()
    write_portfolio(stamm, uebernahme / "bestand.parquet")
    write_portfolio(schichten, uebernahme / "schichten.parquet")
    write_portfolio(verankerung, uebernahme / "verankerung.parquet")
    led_welt = fortschreiben(stamm, _config(), BIS, schichten=schichten, verankerung=verankerung).ledger
    assert (led_welt["betrag_art"] == "dDK_absorption").any()
    eingaben = {"portfolio": uebernahme / "bestand.parquet"}
    ledger_pfad = tmp_path / "ledger.parquet"
    write_portfolio(led_welt, ledger_pfad)
    eingaben["ledger"] = ledger_pfad
    _t, _g, _f, usage = lies_und_pruefe_pb1(eingaben, bis=_dt.date(2046, 1, 1), manifest=None)
    assert any("--schichten" in u.get("message", "") for u in usage), usage


def test_p_b1_ohne_config_prueft_keine_herabsetzung_und_sagt_das(tmp_path):
    """Angriffsrunde der Nacht: Ohne --config meldete P-B1 PASSED fuer
    beliebig verfaelschte Herabsetzungsbuchungen. Jetzt: Bedienfehler."""
    from rechner_pipeline.bestand.manifest import lauf_eingaben
    from rechner_pipeline.bestand.vorbedingungen import lies_und_pruefe_pb1
    from tests.test_herabsetzung_in_fuehrung import _lauf_mit_herabsetzung

    out, cfg = _lauf_mit_herabsetzung(tmp_path)
    eingaben = dict(lauf_eingaben(out, cfg))
    eingaben.pop("config", None)
    _t, _g, _f, usage = lies_und_pruefe_pb1(eingaben, bis=_dt.date(2046, 1, 1), manifest=None)
    assert any("--config" in u.get("message", "") for u in usage), usage


def test_eine_herabsetzung_auf_einem_bu_vertrag_ist_ein_fehler(welt):
    """Angriffsrunde der Nacht: RED auf einem BU-Vertrag blieb ungeprueft
    und zaehlte als hergeleitet."""
    from rechner_pipeline.models.bestand import validate_reduktionen

    config, stamm, schichten, verankerung, erg = welt
    stamm2 = stamm.copy()
    pid = int(erg.reduktionen["police_id"].iloc[0])
    stamm2.loc[stamm2["police_id"] == pid, "produkt"] = "bu"
    fehler = validate_reduktionen(stamm2, erg.reduktionen, erg.historie)
    assert any("Kapitalversicherung" in f and str(pid) in f for f in fehler), fehler


def test_der_bestandsbericht_hat_ein_flag_je_rolle_des_erzeugers(tmp_path, monkeypatch):
    """Angriffsrunde der Nacht: cli_report kannte --reduktionen nicht."""
    import shutil

    from rechner_pipeline.bestand import cli_report as cli
    from tests.test_herabsetzung_in_fuehrung import _lauf_mit_herabsetzung

    out, cfg = _lauf_mit_herabsetzung(tmp_path)
    anderswo = tmp_path / "anderswo"
    anderswo.mkdir()
    for datei in ("ledger.parquet", "historie.parquet", "scheiben.parquet", "reduktionen.parquet"):
        shutil.copyfile(out / datei, anderswo / datei)
    (anderswo / "reduktionen.parquet").rename(tmp_path / "red.parquet")
    gesehen = {}
    echt = cli.render_html
    monkeypatch.setattr(cli, "render_html", lambda *a, **kw: (gesehen.update(kw), echt(*a, **kw))[1])
    code = cli.main([
        "--portfolio", str(out / "bestand_gesamt.parquet"), "--historie", str(anderswo / "historie.parquet"),
        "--ledger", str(anderswo / "ledger.parquet"), "--scheiben", str(anderswo / "scheiben.parquet"),
        "--reduktionen", str(tmp_path / "red.parquet"),
        "--bis", "2046-01-01", "--stichtag", "2030-01-01", "--out", str(tmp_path / "b.html"),
        "--config", str(cfg),
    ])
    assert code == 0
    assert gesehen.get("reduktionen") is not None and len(gesehen["reduktionen"]) > 0
