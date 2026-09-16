"""Freischaltung, Schritt 5: Die Korrekturschicht in der Fuehrung.

Der Rueckkaufswert eines uebernommenen Vertrags ist Basiswert plus
Korrekturschicht (Grundsatzdokumentation 9.7: Storno wertkontinuierlich,
Ausgestaltung des Tarifplans). Die Schicht ist ein Vertragsattribut
(``schichten.parquet`` neben ``verankerung.parquet``), die Engine bucht
sie im Storno mit, der Abschluss weist sie als eigene Position aus, und
P-B1 leitet den Stornobetrag mit ihr her. Ein Rechenweg: dieselbe
Funktion wie in den Pruef-Engines (``kern.korrekturschicht.schichtwert_bei``).

Knoten: klv
"""

from __future__ import annotations

import datetime as _dt
import json

import pandas as pd
import pytest

from rechner_pipeline.bestand.config import config_aus_text
from rechner_pipeline.bestand.ereignisse import EreignisError, fortschreiben
from rechner_pipeline.bestand.kernlauf import vertrags_rkw
from rechner_pipeline.kern import ModelPoint, Rechenkern
from rechner_pipeline.kern.korrekturschicht import Schichtparameter, schichtwert_bei
from rechner_pipeline.bestand.schichten import schichtparameter_aus_zeile
from rechner_pipeline.models.bestand import (
    SCHICHTEN_NAMES,
    SCHICHTEN_SPALTEN,
    VERANKERUNG_SPALTEN,
    model_point_kwargs,
    schichten_zeile,
    validate_schichten,
)
from tests.test_bestand_uebernommen_fortschreiben import _CONFIG_TOML, _stamm

BIS = _dt.date(2046, 1, 1)
MONATE_TA = 132   # elf volle Jahre am Stichtag 2026-01-01 (Beginn 2015-01-01)


def _parameter(rho: float = 0.04) -> Schichtparameter:
    return Schichtparameter(
        schichttyp="hist", verankerungszustand="aktiv", verweildauer=0,
        rho=rho, formfunktion="proportional_zur_basis", formparameter={},
        vererbend=(("aktiv", "tot"),), kohorte="t_a",
    )


def _tabellen(policen, rho: float = 0.04):
    schichten = pd.DataFrame(
        [schichten_zeile(pid, _parameter(rho).als_beleg()) for pid in policen],
        columns=list(SCHICHTEN_NAMES)).astype(dict(SCHICHTEN_SPALTEN))
    verankerung = pd.DataFrame([{
        "police_id": pid, "monate_ta": MONATE_TA, "zustand_ta": "beitragspflichtig",
        "verweildauer_ta": 11, "dk_ta": 1.0,
    } for pid in policen])[[n for n, _ in VERANKERUNG_SPALTEN]].astype(
        dict(VERANKERUNG_SPALTEN))
    return schichten, verankerung


def test_kern_api_ist_dieselbe_funktion_wie_in_der_pruefstrecke():
    from rechner_pipeline.qa import aktuarieller_test

    mp = ModelPoint(**model_point_kwargs(
        _stamm([{"id": 1, "beginn": "2015-01-01"}]).iloc[0],
        config_aus_text(_CONFIG_TOML).generationen[0].generation_fields()))
    for monate in (MONATE_TA, MONATE_TA + 7, MONATE_TA + 60):
        assert aktuarieller_test.schichtwert_bei(_parameter(), MONATE_TA, mp, monate) == \
            schichtwert_bei(_parameter(), MONATE_TA, mp, monate)
    assert schichtwert_bei(_parameter(), MONATE_TA, mp, MONATE_TA) != 0.0


def test_schichten_tabelle_ist_konstruktorkompatibel_und_geprueft():
    policen = [900_001, 900_002]
    schichten, verankerung = _tabellen(policen)
    stamm = _stamm([{"id": pid, "beginn": "2015-01-01", "zugang": "2026-01-01"}
                    for pid in policen])
    assert validate_schichten(stamm, schichten, verankerung) == []
    for zeile in schichten.to_dict("records"):
        assert schichtparameter_aus_zeile(zeile) == _parameter()
    # Fremde Police, fehlender Anker, kaputter Parametersatz.
    fremd = schichten.copy(); fremd.loc[0, "police_id"] = 900_009
    assert any("unbekannt" in b for b in validate_schichten(stamm, fremd, verankerung))
    assert any("ohne Verankerung" in b for b in validate_schichten(
        stamm, schichten, verankerung.iloc[:1]))
    assert any("verankerung" in b for b in validate_schichten(stamm, schichten, None))
    kaputt = schichten.copy(); kaputt.loc[0, "schichttyp"] = "fremd"
    assert any("police 900001" in b for b in validate_schichten(stamm, kaputt, verankerung))


def test_storno_zahlt_basiswert_plus_schicht_und_p_b1_leitet_es_her():
    """Die Buchung der Engine und die Herleitung von P-B1 gehen denselben
    Weg; ohne die Schicht faende P-B1 den Betrag nicht aus dem Kern."""
    from rechner_pipeline.bestand.ledger_bindung import pruefe_ledger_betraege
    from rechner_pipeline.models.bestand import LEDGER_SPALTEN

    config = config_aus_text(_CONFIG_TOML)
    gen = config.generationen[0]
    policen = list(range(900_001, 900_041))
    stamm = _stamm([{"id": pid, "beginn": "2015-01-01", "zugang": "2026-01-01"}
                    for pid in policen])
    schichten, verankerung = _tabellen(policen)
    ergebnis = fortschreiben(stamm, config, BIS, schichten=schichten,
                             verankerung=verankerung)
    ledger = ergebnis.ledger
    sto = ledger[ledger["ereignis"] == "STO"]
    assert len(sto) >= 1
    haupt = stamm.set_index("police_id")
    felder = gen.generation_fields()
    for z in sto.to_dict("records"):
        pid, jahr = int(z["police_id"]), int(z["vertragsjahr"])
        h = haupt.loc[pid]
        grund_mp = ModelPoint(**model_point_kwargs(h, felder))
        teile = []
        for s in ergebnis.scheiben[ergebnis.scheiben["police_id"] == pid].to_dict("records"):
            if int(s["erhoehung_jahr"]) >= jahr:
                continue
            row = {"entry_age": s["entry_age"], "sex": h["sex"],
                   "duration": s["duration"], "premium_duration": s["premium_duration"],
                   "sum_insured": s["sum_insured"], "zahlweise": h["zahlweise"]}
            kw = model_point_kwargs(row, felder); kw["gamma1"] = float(s["gamma1"])
            teile.append((int(s["erhoehung_jahr"]), Rechenkern(ModelPoint(**kw))))
        basis = vertrags_rkw(Rechenkern(grund_mp), teile, jahr)
        schicht = schichtwert_bei(_parameter(), MONATE_TA, grund_mp, 12 * jahr)
        assert schicht != 0.0
        assert z["betrag"] == basis + schicht, (pid, jahr)

    zug = pd.DataFrame([{
        "police_id": pid, "tarif_generation": gen.name, "ereignis": "ZUG",
        "vertragsjahr": 11, "status_date": pd.Timestamp("2026-01-01"),
        "betrag_art": "VS", "betrag": 100_000.0, "betrag_herkunft": "geliefert",
    } for pid in policen])[[n for n, _ in LEDGER_SPALTEN]].astype(dict(LEDGER_SPALTEN))
    voll = pd.concat([zug, ledger], ignore_index=True)
    assert pruefe_ledger_betraege(
        stamm, voll, config, scheiben=ergebnis.scheiben, historie=ergebnis.historie,
        schichten=schichten, verankerung=verankerung) == []
    ohne = pruefe_ledger_betraege(
        stamm, voll, config, scheiben=ergebnis.scheiben, historie=ergebnis.historie)
    assert ohne and "STO" in ohne[0]


def test_abschluss_weist_die_schicht_als_eigene_position_aus(tmp_path):
    from rechner_pipeline.bestand.abschluss import pruefe_abschluss, schreibe_abschluss
    from rechner_pipeline.bestand.auswertung import einzelwerte_am
    from rechner_pipeline.bestand.parquet_io import read_portfolio
    from rechner_pipeline.models.bestand import ABSCHLUSS_NAMES, STATUS_HISTORIE_SPALTEN

    config = config_aus_text(_CONFIG_TOML)
    policen = [900_001, 900_002]
    stamm = _stamm([{"id": pid, "beginn": "2015-01-01", "zugang": "2026-01-01"}
                    for pid in policen])
    schichten, verankerung = _tabellen(policen)
    historie = pd.DataFrame(columns=[n for n, _ in STATUS_HISTORIE_SPALTEN]).astype(
        dict(STATUS_HISTORIE_SPALTEN))
    stichtag = _dt.date(2027, 4, 1)
    mit = einzelwerte_am(stamm, historie, config, stichtag,
                         schichten=schichten, verankerung=verankerung)
    ohne = einzelwerte_am(stamm, historie, config, stichtag)
    felder = config.generationen[0].generation_fields()
    for a, b in zip(mit, ohne):
        mp = ModelPoint(**model_point_kwargs(stamm.set_index("police_id").loc[a["police_id"]], felder))
        monate = (2027 - 2015) * 12 + 3
        korr = schichtwert_bei(_parameter(), MONATE_TA, mp, monate)
        assert a["korrekturschicht"] == korr and korr != 0.0
        assert a["deckungskapital"] == b["deckungskapital"] + korr
        assert a["rueckkaufswert"] == b["rueckkaufswert"] + korr
        assert b["korrekturschicht"] == 0.0

    pfad = schreibe_abschluss(stamm, historie, config, stichtag, tmp_path / "ab",
                              schichten=schichten, verankerung=verankerung)
    fest = read_portfolio(pfad)
    assert list(fest.columns) == list(ABSCHLUSS_NAMES)
    assert (fest["korrekturschicht"] != 0.0).all()
    assert pruefe_abschluss(pfad, stamm, historie, config,
                            schichten=schichten, verankerung=verankerung) == []
    # Ohne die Schicht ist der festgeschriebene Stand nicht reproduzierbar.
    assert pruefe_abschluss(pfad, stamm, historie, config) != []


def test_schicht_ohne_anker_oder_an_eigenem_vertrag_ist_ein_fehler():
    config = config_aus_text(_CONFIG_TOML)
    schichten, verankerung = _tabellen([900_001])
    uebernommen = _stamm([{"id": 900_001, "beginn": "2015-01-01", "zugang": "2026-01-01"}])
    with pytest.raises(EreignisError, match="Verankerung"):
        fortschreiben(uebernommen, config, BIS, schichten=schichten, verankerung=None)
    eigen = _stamm([{"id": 900_001, "beginn": "2015-01-01"}])
    with pytest.raises(EreignisError, match="eigenen Vertrag"):
        fortschreiben(eigen, config, BIS, schichten=schichten, verankerung=verankerung)


def test_eine_verankerte_police_ohne_schicht_ist_ein_fehler():
    """Die GEGENRICHTUNG (Review T25-04): Verankerung und Schicht
    beschreiben dieselbe Population.

    Geprueft wurde nur "Schicht ohne Verankerung". Der umgekehrte Fall —
    eine verankerte Police, fuer die keine Schicht in der Tabelle steht —
    fiel nirgends auf, und die Bewertung dieses Vertrags rechnete still
    ohne seine Korrektur weiter. Moeglich ist er, weil die beiden Tabellen
    aus getrennten Dateien kommen: Ein Lauf schreibt sie zusammen, aber
    nichts verlangte, dass die auf der Platte auch zusammengehoeren.

    Der Produzent schreibt die Tabelle nur, wenn JEDE verankerte Police
    eine getragene Schicht hat (T25-04, gleicher Commit) — ein Paar, das
    auseinandergeht, stammt also nicht aus einem Lauf.
    """
    from rechner_pipeline.models.bestand import validate_schichten

    stamm = _stamm([{"id": 900_001, "beginn": "2015-01-01", "zugang": "2026-01-01"},
                    {"id": 900_002, "beginn": "2015-01-01", "zugang": "2026-01-01"}])
    # Beide verankert, nur einer mit Schicht.
    _, verankerung = _tabellen([900_001, 900_002])
    schichten, _ = _tabellen([900_001])
    fehler = validate_schichten(stamm, schichten, verankerung)
    assert any("ohne Schicht" in f and "900002" in f.replace("_", "") for f in fehler), fehler
    # Und das Paar aus EINEM Lauf ist in Ordnung.
    schichten_beide, verankerung_beide = _tabellen([900_001, 900_002])
    assert validate_schichten(stamm, schichten_beide, verankerung_beide) == []


def test_der_beleg_und_die_tabelle_tragen_dieselben_parameter(tmp_path):
    """Roundtrip Beleg -> Tabelle -> Parquet -> Schichtparameter."""
    from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio

    schichten, _ = _tabellen([900_001], rho=-0.01)
    write_portfolio(schichten, tmp_path / "schichten.parquet")
    zurueck = read_portfolio(tmp_path / "schichten.parquet", expected_columns=SCHICHTEN_NAMES)
    assert schichtparameter_aus_zeile(zurueck.iloc[0]) == _parameter(-0.01)
    assert json.loads(zurueck.iloc[0]["vererbend"]) == [["aktiv", "tot"]]


# --- T25-06: die Beitragsfreistellung nach der Verankerung ---------------
#
# Entscheid des Maintainers 2026-09-15: WERTSTETIGE Absorption. Die
# beitragsfreie Summe ist eine garantierte Leistung, also muss die
# Umwandlung werthaltend sein — das Residuum wandert hinein, statt zu
# verschwinden. Vorher hoerte die Bewertung an dieser Naht einfach auf,
# den Schichtwert zu addieren, und beide "unabhaengigen" Gegenrechnungen
# bestaetigten den zu kleinen Betrag, statt ihn zu widerlegen.


def test_beitragsfreistellung_nach_verankerung_bucht_die_schicht_mit():
    """Engine und P-B1-Herleitung gehen denselben Weg — wie beim Storno."""
    from rechner_pipeline.bestand.ledger_bindung import pruefe_ledger_betraege
    from rechner_pipeline.models.bestand import LEDGER_SPALTEN

    config = config_aus_text(_CONFIG_TOML)
    gen = config.generationen[0]
    policen = list(range(900_001, 900_041))
    stamm = _stamm([{"id": pid, "beginn": "2015-01-01", "zugang": "2026-01-01"}
                    for pid in policen])
    schichten, verankerung = _tabellen(policen)
    ergebnis = fortschreiben(stamm, config, BIS, schichten=schichten,
                             verankerung=verankerung)
    pex = ergebnis.ledger[ergebnis.ledger["ereignis"] == "PEX"]
    assert len(pex) >= 1
    haupt = stamm.set_index("police_id")
    felder = gen.generation_fields()
    for z in pex.to_dict("records"):
        pid, jahr = int(z["police_id"]), int(z["vertragsjahr"])
        assert 12 * jahr >= MONATE_TA, "Fixture: PEX muss nach der Verankerung liegen"
        kern = Rechenkern(ModelPoint(**model_point_kwargs(haupt.loc[pid], felder)))
        ohne_schicht = kern.beitragsfreie_summe(jahr)
        # Die gebuchte Summe ist echt groesser — genau um den Gegenwert der
        # Schicht. Ohne die Absorption stuende hier die nackte Summe.
        assert float(z["betrag"]) > ohne_schicht

    zug = pd.DataFrame([{
        "police_id": pid, "tarif_generation": gen.name, "ereignis": "ZUG",
        "vertragsjahr": 11, "status_date": pd.Timestamp("2026-01-01"),
        "betrag_art": "VS", "betrag": 100_000.0, "betrag_herkunft": "geliefert",
    } for pid in policen])[[n for n, _ in LEDGER_SPALTEN]].astype(dict(LEDGER_SPALTEN))
    voll = pd.concat([zug, ergebnis.ledger], ignore_index=True)
    assert pruefe_ledger_betraege(
        stamm, voll, config, scheiben=ergebnis.scheiben, historie=ergebnis.historie,
        schichten=schichten, verankerung=verankerung) == []
    # Und die Gegenprobe, auf den PEX-Zeilen allein: Die Befunde werden
    # aggregiert und nennen nur drei Beispiele — mit den Stornozeilen im
    # selben Ledger bewiese ein Treffer nicht, dass es die PEX war.
    nur_pex = pd.concat(
        [zug, ergebnis.ledger[ergebnis.ledger["ereignis"] == "PEX"]],
        ignore_index=True)
    ohne = pruefe_ledger_betraege(
        stamm, nur_pex, config, scheiben=ergebnis.scheiben,
        historie=ergebnis.historie)
    assert ohne and "PEX" in ohne[0]


def test_absorption_haelt_den_wert_und_weist_ihn_weiter_aus():
    """Die eigentliche fachliche Zusage, an einer unabhaengigen Groesse
    gemessen: Das Deckungskapital des freigestellten Vertrags ist die
    Reserve des Rueckkaufs-Tracks PLUS den Schichtwert.

    ``kVx_MRV`` ist der Bezug, weil die Umwandlung in die beitragsfreie
    Summe genau gegen ihn stetig definiert ist (Blatt der Produkte:
    ``reserve_beitragsfrei(a0, a0) == kVx_MRV(a0)``). Die erwartete Zahl
    kommt damit aus dem Blatt und aus ``schichtwert_bei`` — nicht aus der
    Formel, die hier geprueft wird."""
    from rechner_pipeline.bestand.auswertung import einzelwerte_am
    from rechner_pipeline.models.bestand import STATUS_HISTORIE_SPALTEN

    config = config_aus_text(_CONFIG_TOML)
    policen = [900_001, 900_002]
    stamm = _stamm([{"id": pid, "beginn": "2015-01-01", "zugang": "2026-01-01"}
                    for pid in policen])
    schichten, verankerung = _tabellen(policen)
    pex_jahr = 13                      # 156 Monate, also NACH MONATE_TA = 132
    historie = pd.DataFrame([{
        "police_id": pid, "status_id": 2, "status_code": "PEX",
        "status_date": pd.Timestamp("2028-01-01"),
    } for pid in policen])[[n for n, _ in STATUS_HISTORIE_SPALTEN]].astype(
        dict(STATUS_HISTORIE_SPALTEN))

    felder = config.generationen[0].generation_fields()
    haupt = stamm.set_index("police_id")
    mit = einzelwerte_am(stamm, historie, config, _dt.date(2028, 1, 1),
                         schichten=schichten, verankerung=verankerung)
    ohne = einzelwerte_am(stamm, historie, config, _dt.date(2028, 1, 1))
    assert mit and len(mit) == len(ohne)
    for a, b in zip(mit, ohne):
        pid = int(a["police_id"])
        assert a["status"] == "PEX"
        mp = ModelPoint(**model_point_kwargs(haupt.loc[pid], felder))
        kern = Rechenkern(mp)
        korr = schichtwert_bei(_parameter(), MONATE_TA, mp, 12 * pex_jahr)
        assert korr > 0.0
        # Wertstetig: Reserve des Rueckkaufs-Tracks plus Schicht.
        erwartet = kern.zustand_am(12 * pex_jahr).vx_mrv + korr
        assert a["deckungskapital"] == pytest.approx(erwartet, rel=1e-12)
        # Ohne Schicht gerechnet fehlt genau dieser Betrag.
        assert a["deckungskapital"] - b["deckungskapital"] == pytest.approx(
            korr, rel=1e-12)
        # Der Wert steckt jetzt in der GARANTIERTEN beitragsfreien Summe...
        assert a["vs_bfr"] > b["vs_bfr"] > 0.0
        # ...und bleibt trotzdem ausgewiesen (9.11: nie unsichtbar im
        # Deckungskapital). Im Freistellungsjahr selbst ist der
        # ueberfuehrte Wert der Schichtwert.
        assert a["korrekturschicht"] == pytest.approx(korr, rel=1e-12)
        assert b["korrekturschicht"] == 0.0
