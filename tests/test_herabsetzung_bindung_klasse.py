"""Jede Pruefung einer Herabsetzung bindet Soll-Menge, Verfahren und Anteil — Angriffsrunde nach T27.

Die Klasse: P-B1 hatte die Soll-Menge der RED-Buchungen seit T27-14, die
Fuehrungsprobe pruefte nur die Zeilen, die da waren; P-B1 band den Anteil
nur, wenn die Config einen kannte; der Bericht pruefte ohne Config
ueberhaupt keine Bindung. Jetzt gibt es EINE Regel
(ledger_bindung.red_sollbuchungen/red_bindung_fehler/red_vollstaendigkeit_fehler),
und jeder Konsument ruft sie.

Knoten: klv
"""

from __future__ import annotations

import copy
import datetime as _dt
from pathlib import Path

import pandas as pd
import pytest

from rechner_pipeline.bestand.ledger_bindung import pruefe_ledger_betraege


# --------------------------------------------------------------------------- #
# P-B1: eine Config ohne Herabsetzung belegt keinen Anteil
# --------------------------------------------------------------------------- #


def test_p_b1_weist_herabsetzungen_ab_die_die_config_nicht_kennt():
    """Mutationsprobe: den Zweig red_anteil == 0 in red_bindung_fehler
    entfernen -> rot."""
    from tests.test_t27_teilkuendigung_klasse import _voll
    from tests import test_t27_teilkuendigung_klasse as tk

    config = tk._config()
    stamm = tk._stamm([{"id": p, "beginn": "2015-01-01", "zugang": "2026-01-01"} for p in tk.POLICEN])
    schichten, verankerung = tk._tabellen(tk.POLICEN)
    from rechner_pipeline.bestand.ereignisse import fortschreiben

    erg = fortschreiben(stamm, config, tk.BIS, schichten=schichten, verankerung=verankerung)
    welt = (config, stamm, schichten, verankerung, erg)
    assert len(erg.reduktionen)
    assert tk._pb1(welt, erg.ledger) == []                          # Positivkontrolle
    ohne = copy.deepcopy(config)
    ohne.annahmen.red_anteil = 0.0
    fehler = pruefe_ledger_betraege(
        stamm, _voll(welt, erg.ledger), ohne, scheiben=erg.scheiben, historie=erg.historie,
        schichten=schichten, verankerung=verankerung, reduktionen=erg.reduktionen)
    assert any("kennen keine" in f for f in fehler), fehler[:3]


# --------------------------------------------------------------------------- #
# Fuehrungsprobe: Soll-Menge und Bindung wie P-B1
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def red_welt(gefahrener_fall):
    from rechner_pipeline.bestand.config import config_aus_text
    from rechner_pipeline.bestand.ereignisse import fortschreiben
    from rechner_pipeline.gates.fuehrungsprobe import pruefe_fuehrung
    from tests.test_baldrian2_e2e import RED_ANTEILE, _probe_material, _welt_wie_der_lauf

    ueb, _fort, basis = _probe_material(gefahrener_fall)
    text = (gefahrener_fall / "abgeleitet" / "bestand-config.toml").read_text(encoding="utf-8")
    anteil = float(RED_ANTEILE[0].split("=")[1])
    mit_red = config_aus_text(text + (
        f"\n[annahmen]\nred_anteil = {anteil}\n"
        "[annahmen.herabsetzung]\na = 0.20\nb = 0.0\n"))
    erg = fortschreiben(
        ueb["bestand"], mit_red, _dt.date(2040, 1, 1), merkmale=ueb["merkmale"],
        scheiben=ueb["scheiben"], schichten=ueb["schichten"], verankerung=ueb["verankerung"])
    fort = _welt_wie_der_lauf(ueb, erg, reduktionen=erg.reduktionen)
    red_basis = dict(basis, config=mit_red)
    gut = pruefe_fuehrung(uebernahme=ueb, fortschreibung=fort, **red_basis)
    assert gut["bestanden"], gut["befunde"][:3]

    def stimmig(ersetze_text: str, durch: str, anteil_neu: float):
        """Eine STIMMIG gefaelschte Fortschreibung: dieselbe Engine mit einem
        anderen Verfahren bzw. Anteil — Ledger und Tabelle passen zueinander,
        nur nicht zum System. Allein die Bindung kann das sehen."""
        assert ersetze_text in text
        anders = config_aus_text(text.replace(ersetze_text, durch) + (
            f"\n[annahmen]\nred_anteil = {anteil_neu}\n"
            "[annahmen.herabsetzung]\na = 0.20\nb = 0.0\n"))
        e2 = fortschreiben(
            ueb["bestand"], anders, _dt.date(2040, 1, 1), merkmale=ueb["merkmale"],
            scheiben=ueb["scheiben"], schichten=ueb["schichten"], verankerung=ueb["verankerung"])
        assert len(e2.reduktionen)
        return _welt_wie_der_lauf(ueb, e2, reduktionen=e2.reduktionen)

    return ueb, fort, red_basis, stimmig, anteil


from tests.test_baldrian2_e2e import gefahrener_fall  # noqa: E402,F401


def _urteil(red_welt, **ersetzt):
    from rechner_pipeline.gates.fuehrungsprobe import pruefe_fuehrung

    ueb, fort, basis = red_welt[:3]
    return pruefe_fuehrung(uebernahme=ueb, fortschreibung={**fort, **ersetzt}, **basis)


def _red(fort, art):
    led = fort["ledger"]
    return led.index[(led["ereignis"] == "RED") & (led["betrag_art"] == art)]


def test_eine_gestrichene_auszahlung_faellt(red_welt):
    """Mutationsprobe: die Vollstaendigkeit in der Probe nicht pruefen -> rot."""
    _ueb, fort, _b = red_welt[:3]
    idx = _red(fort, "RKW_teilkuendigung")
    assert len(idx)
    assert not _urteil(red_welt, ledger=fort["ledger"].drop(index=idx[:1]))["bestanden"]


def test_eine_doppelt_gebuchte_summe_faellt(red_welt):
    _ueb, fort, _b = red_welt[:3]
    led = fort["ledger"]
    idx = _red(fort, "VS_herabsetzung")
    doppelt = pd.concat([led, led.loc[idx[:1]]], ignore_index=True).astype(led.dtypes.to_dict())
    assert not _urteil(red_welt, ledger=doppelt)["bestanden"]


def test_ein_verschobener_wirkungstag_faellt(red_welt):
    _ueb, fort, _b = red_welt[:3]
    led = fort["ledger"].copy()
    idx = _red(fort, "VS_herabsetzung")
    led.loc[idx[0], "status_date"] = pd.Timestamp(led.loc[idx[0], "status_date"]) + pd.DateOffset(months=1)
    assert not _urteil(red_welt, ledger=led)["bestanden"]


def test_ein_stimmig_fremdes_verfahren_faellt_an_der_bindung(red_welt):
    """Ledger und Tabelle mit prospektiv gerechnet, das System sagt
    Teilkuendigung: die Auszahlung an den Kunden entfaellt, alles passt
    zueinander. Mutationsprobe: red_bindung_fehler in der Probe nicht
    rufen -> rot."""
    from rechner_pipeline.gates.fuehrungsprobe import pruefe_fuehrung

    ueb, _fort, basis, stimmig, anteil = red_welt
    fort = stimmig('red_verfahren = "teilkuendigung"', 'red_verfahren = "prospektiv"', anteil)
    urteil = pruefe_fuehrung(uebernahme=ueb, fortschreibung=fort, **basis)
    assert not urteil["bestanden"]
    assert any("Verfahren" in b["text"] for b in urteil["befunde"]), urteil["befunde"][:3]


def test_ein_stimmig_fremder_anteil_faellt_an_der_bindung(red_welt):
    from rechner_pipeline.gates.fuehrungsprobe import pruefe_fuehrung

    ueb, _fort, basis, stimmig, anteil = red_welt
    fort = stimmig('red_verfahren = "teilkuendigung"', 'red_verfahren = "teilkuendigung"', 0.2)
    urteil = pruefe_fuehrung(uebernahme=ueb, fortschreibung=fort, **basis)
    assert not urteil["bestanden"]
    assert any("Anteil" in b["text"] for b in urteil["befunde"]), urteil["befunde"][:3]


def test_eine_zusaetzliche_kappungszeile_faellt(red_welt):
    _ueb, fort, _b = red_welt[:3]
    led = fort["ledger"]
    idx = _red(fort, "RKW_teilkuendigung")
    extra = led.loc[idx[:1]].copy()
    extra["betrag_art"] = "Kappung_teilkuendigung"
    extra["betrag"] = 0.0
    assert not _urteil(red_welt, ledger=pd.concat([led, extra], ignore_index=True)
                       .astype(led.dtypes.to_dict()))["bestanden"]


# --------------------------------------------------------------------------- #
# Bericht: eine RED-Buchung ohne registrierte Herabsetzung wird nicht gerendert
# --------------------------------------------------------------------------- #


def test_der_bericht_rendert_keine_verstuemmelte_herabsetzung(tmp_path):
    """Mutationsprobe: die Config im Bericht wieder draussen lassen -> rot."""
    from rechner_pipeline.bestand import cli_report as cli
    from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
    from tests.test_herabsetzung_in_fuehrung import _lauf_mit_herabsetzung

    out, cfg = _lauf_mit_herabsetzung(tmp_path)
    argv = ["--portfolio", str(out / "bestand_gesamt.parquet"), "--historie", str(out / "historie.parquet"),
            "--ledger", str(out / "ledger.parquet"), "--scheiben", str(out / "scheiben.parquet"),
            "--reduktionen", str(out / "reduktionen.parquet"), "--config", str(cfg),
            "--bis", "2046-01-01", "--stichtag", "2030-01-01"]
    assert cli.main(argv + ["--out", str(tmp_path / "gut.html")]) == 0      # Positivkontrolle
    red = read_portfolio(out / "reduktionen.parquet")
    assert len(red) > 1
    write_portfolio(red.iloc[1:], out / "reduktionen.parquet")
    assert cli.main(argv + ["--out", str(tmp_path / "schlecht.html")]) != 0


# --------------------------------------------------------------------------- #
# Kern: mit Abzug zieht die Korrekturschicht den Stornoabzug nicht ein zweites Mal
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("a0", [1, 2, 5])
def test_mit_abzug_geht_die_schicht_ungekuerzt_in_die_umwandlung(a0):
    """Unabhaengige Sollrechnung (klv.md 7.1): umgewandelt = (1-f)(DR - StoAb) + Z,
    also traegt die Schicht Z genau Z / V_bfr zur neuen Summe bei — auch nahe
    DR = 0 und bei negativer Rueckstellung. Mutationsprobe: die Schicht
    wieder mit dem Reservefaktor multiplizieren -> rot."""
    from rechner_pipeline.kern import KLV_DEFAULT, Rechenkern
    from rechner_pipeline.kern.beitragsreduktion import MIT_ABZUG, reduziere

    kern = Rechenkern(KLV_DEFAULT)
    zeile = kern.verlaufszeile(a0)
    assert zeile.drx_bpfl != 0.0, "Testpunkt mit DR = 0 waehlen ist hier nicht gemeint"
    ohne = reduziere(kern, a0, 0.6, verfahren=MIT_ABZUG)
    mit = reduziere(kern, a0, 0.6, verfahren=MIT_ABZUG, zusatz_dk=2000.0)
    assert mit.vs_neu - ohne.vs_neu == pytest.approx(2000.0 / zeile.vx_bfr, rel=1e-12)
