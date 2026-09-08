"""Die Unternehmensgeschichte beginnt 1994, ein Zugang darf mitten im Betrieb liegen.

Der Betriebsbeginn war bisher zugleich die Obergrenze jeder Uebernahme: Ein
Bestand durfte nur am ersten Tag der Fuehrung zugehen, danach nie mehr. Das
war eine Regel der Ablauforganisation, keine des Modells — die Engine
simuliert einen uebernommenen Vertrag ohnehin erst ab seinem Bestandszugang
(``ereignisse._zugangslage``), weil alles davor beim abgebenden Unternehmen
geschah. Jetzt gilt die fachliche Ordnung: Ein Zugang liegt in der
GEFUEHRTEN ZEIT, also zwischen dem ersten gefuehrten Tag und heute.

Damit faellt auch die Kopplung, die der Betriebsbeginn getragen hat. Er ist
nur noch die ERZEUGUNGSGRENZE: Der Batch stellt den Bestand bis zu ihr, der
Tagesstrom danach. Die PLV setzt sie an den Anfang ihrer Geschichte
(1994-07-01) — der Batch zieht nichts, der Bestand entsteht Werktag fuer
Werktag, und kein Bericht kennt mehr einen Zeitraum "vor dem Betriebsbeginn".

Knoten: system/betrieb
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import pytest

from rechner_pipeline.bestand.config import load_config
from rechner_pipeline.bestand.generator import generate
from rechner_pipeline.bestand.parquet_io import read_portfolio
from rechner_pipeline.betrieb import uebernahme as ueb
from rechner_pipeline.betrieb.neugeschaeft import tagesziel
from rechner_pipeline.betrieb.tageslauf import (
    EXIT_OK,
    Ablage,
    tageslauf,
)
from tests.test_betrieb_neuaufsetzen import _fall_mit_nebentabellen
from tests.test_betrieb_uebernahme import STICHTAG, PLV


def _ablage_ab(wurzel: Path, betriebsbeginn: dt.date) -> Ablage:
    """Eine Ablage mit frei gesetzter Erzeugungsgrenze (sechs Vertraege je
    Generation, damit der Tagesstrom kurz bleibt)."""
    text = PLV.read_text(encoding="utf-8")
    text = re.sub(r"^sample_size = [1-9]\d*$", "sample_size = 6", text, flags=re.M)
    text = re.sub(r"^betriebsbeginn = .*$",
                  f"betriebsbeginn = {betriebsbeginn.isoformat()}", text, flags=re.M)
    ablage = Ablage(wurzel)
    ablage.configs.mkdir(parents=True, exist_ok=True)
    ablage.config_pfad.write_text(text, encoding="utf-8")
    return ablage


# --------------------------------------------------------------------------- #
# Der Zugang liegt in der gefuehrten Zeit
# --------------------------------------------------------------------------- #

def test_ein_zugang_mitten_im_betrieb_wird_gefuehrt(tmp_path):
    """Betriebsbeginn ein Jahr vor dem Zugang: Der uebernommene Bestand tritt
    mitten in die laufende Fuehrung ein, seine Buchungen stehen am Zugangstag
    im Journal, und die Wache ist gruen.

    Mutationsprobe: die alte Sperre (Stichtag hoechstens Betriebsbeginn)
    zurueckstellen -> dieser Lauf bricht mit TageslaufError ab."""
    fall = _fall_mit_nebentabellen(tmp_path)
    stand = tmp_path / "daten"
    ueb.eingang_anlegen(stand, fall, STICHTAG)               # Zugang 2026-01-01
    ablage = _ablage_ab(stand, dt.date(2025, 1, 1))          # gefuehrt seit 2025
    code, zeile = tageslauf(ablage, dt.date(2026, 1, 9))
    assert code == EXIT_OK, zeile.get("fehler") or zeile.get("pb1")
    assert zeile["pb1"]["urteil"] == "gruen"
    stamm = read_portfolio(ablage.stand / "bestand_gesamt.parquet")
    assert 7_000_001 in set(stamm["police_id"])
    # Der Zugang ist eine Buchung DIESES Unternehmens an seinem Zugangstag —
    # die Vorgeschichte des abgebenden bleibt draussen. (Eigenes Neugeschaeft
    # bucht seinen ZUG an seinem eigenen Beginn, deshalb nur die
    # uebernommenen Policen.)
    journal = read_portfolio(ablage.tagesjournal_pfad)
    uebernommen = set(read_portfolio(
        ablage.uebernahme / "probe-uebernahme" / "bestand.parquet")["police_id"])
    zug = journal[(journal["ereignis"] == "ZUG")
                  & (journal["police_id"].isin(uebernommen))]
    assert len(zug) == len(uebernommen)
    assert set(zug["status_date"].dt.date) == {STICHTAG}
    assert zeile["uebernahmen"][0]["stichtag"] == STICHTAG.isoformat()


@pytest.mark.parametrize("betriebsbeginn, heute", [
    (dt.date(2026, 6, 1), dt.date(2026, 6, 2)),   # Zugang vor dem ersten gefuehrten Tag
    (dt.date(2025, 1, 1), dt.date(2025, 6, 1)),   # Zugang nach heute
])
def test_ein_zugang_ausserhalb_der_gefuehrten_zeit_wird_verweigert(
    tmp_path, betriebsbeginn, heute
):
    """Vor dem ersten gefuehrten Tag gibt es keine Buecher, in die ein Bestand
    eintreten koennte; nach heute ist nichts geschehen, was zu buchen waere.
    Der Lauf bricht ab, ohne einen Stand zu uebernehmen."""
    fall = _fall_mit_nebentabellen(tmp_path)
    stand = tmp_path / "daten"
    ueb.eingang_anlegen(stand, fall, STICHTAG)
    ablage = _ablage_ab(stand, betriebsbeginn)
    code, zeile = tageslauf(ablage, heute)
    assert code != EXIT_OK and zeile["uebernommen"] is False
    assert "ausserhalb der gefuehrten Zeit" in zeile["fehler"]
    assert not ablage.stand.exists()


# --------------------------------------------------------------------------- #
# Der Betriebsbeginn ist nur noch die Erzeugungsgrenze
# --------------------------------------------------------------------------- #

def test_die_plv_beginnt_1994_und_zieht_ihren_bestand_taeglich():
    """Liegt die Erzeugungsgrenze am Anfang der Geschichte, zieht der Batch
    nichts: Jeder Vertrag entsteht aus dem Tagesstrom."""
    config = load_config(PLV)
    beginn = config.tagesbetrieb.betriebsbeginn
    assert beginn == dt.date(1994, 7, 1)
    # Vor dem ersten Verkaufstag gibt es kein Fenster — der Batch findet
    # nichts vor, was er ziehen koennte. Was er liefert, sind genau die
    # Vertraege des Grenztages selbst; jeden weiteren verkauft der
    # Tagesstrom (Beginn ab dem naechsten Monatsersten).
    assert min(g.gueltig_von for g in config.generationen) == beginn
    batch = generate(config, bis=beginn)
    assert len(batch) < 10
    assert set(batch["insurance_start"].dt.date) <= {beginn}


def test_batchdichte_und_jahresziel_beschreiben_dieselbe_generation():
    """Die Klasse hinter der Umstellung: Beide Erzeuger bauen denselben
    Bestand, sie unterscheiden sich nur darin, WANN sie greifen. Eine
    Generation mit Stichprobe, aber ohne Jahresziel (oder umgekehrt) waere
    ein Bestand, dessen Groesse davon abhinge, wo die Erzeugungsgrenze
    liegt — genau das soll es nicht mehr geben.

    Mutationsprobe: bei einer Generation neuzugang_pro_jahr entfernen oder
    halbieren -> rot."""
    config = load_config(PLV)
    geprueft = 0
    for gen in config.generationen:
        jahre = ((gen.gueltig_bis - gen.gueltig_von).days + 1) / 365.25
        if gen.sample_size == 0 and gen.neuzugang_pro_jahr == 0:
            continue                      # uebernommene Generation (TG2015)
        assert gen.neuzugang_pro_jahr > 0, gen.name
        # Die tatsaechliche Strommenge: die Tagesziele ueber die Tage des
        # Verkaufsfensters, mit Trend, wo einer gesetzt ist. Weder die
        # lineare Naeherung (sieht den Trend nicht) noch die Summe ueber
        # Kalenderjahre (zaehlt bei halben Fensterjahren zu viel) taugt
        # dafuer — beides waren Zwischenstaende dieses Tests.
        aus_dem_strom = sum(
            tagesziel(config, gen, gen.gueltig_von + dt.timedelta(days=k))
            for k in range((gen.gueltig_bis - gen.gueltig_von).days + 1)
        )
        if gen.neuzugang_trend == 0.0:
            assert abs(aus_dem_strom - gen.sample_size) <= 0.05 * gen.sample_size, (
                gen.name, gen.sample_size, aus_dem_strom)
        else:
            # Mit Trend ist sample_size die trendfreie Dichte des ersten
            # Jahres mal Fensterjahre; der Strom liegt darunter (schrumpfendes
            # Unternehmen) und darf sich nicht davon loesen.
            assert gen.neuzugang_trend < 0, gen.name
            assert gen.neuzugang_pro_jahr * jahre == pytest.approx(
                gen.sample_size, rel=0.05), gen.name
            assert 0.7 * gen.sample_size < aus_dem_strom < gen.sample_size, (
                gen.name, gen.sample_size, aus_dem_strom)
        geprueft += 1
    assert geprueft == 13


# --------------------------------------------------------------------------- #
# Der Betriebsbericht kennt keine Prognose
# --------------------------------------------------------------------------- #

def test_der_betriebsbericht_endet_am_berichtsstichtag(tmp_path):
    """Der Betrieb entdeckt die Zukunft taeglich; eine Prognosekurve waere
    eine Behauptung ueber Tage, die noch nicht stattgefunden haben.

    Mutationsprobe: im Tageslauf wieder stichtag= statt berichtsstichtag=
    uebergeben -> die Prognose-Saetze stehen wieder im Bericht."""
    ablage = _ablage_ab(tmp_path / "daten", dt.date(2026, 1, 1))
    code, zeile = tageslauf(ablage, dt.date(2026, 2, 3))
    assert code == EXIT_OK, zeile.get("fehler") or zeile.get("pb1")
    bericht = next(e for e in zeile["abschluesse"] if "bericht" in e)["bericht"]
    html = (ablage.berichte / bericht).read_text("utf-8")
    assert "Berichtsstichtag: 2026-02-01" in html
    assert "keine Projektion" in html
    for prognose in ("danach Prognose", "ab hier Prognose", "Projektionshorizont"):
        assert prognose not in html, prognose


def test_fallbericht_und_betriebsbericht_schliessen_sich_aus():
    """Zwei Aussagen ueber denselben Bericht: Der Fallbericht zeigt die
    Projektion (dort ist sie der Gegenstand), der Betriebsbericht den Stand
    der Fuehrung. Beides zugleich ist ein Fehler, kein Vorrang."""
    import pandas as pd
    from rechner_pipeline.bestand.report import render_html

    leer = pd.DataFrame()
    with pytest.raises(ValueError, match="schliessen sich aus"):
        render_html(leer, stichtag=dt.date(2026, 1, 1),
                    berichtsstichtag=dt.date(2026, 2, 1))
    with pytest.raises(ValueError, match="weiter reichen als der Lauf"):
        render_html(leer, bis=dt.date(2026, 1, 1),
                    berichtsstichtag=dt.date(2026, 2, 1))


# --------------------------------------------------------------------------- #
# Ein Zugang reicht nicht hinter einen festgeschriebenen Abschluss zurueck
# --------------------------------------------------------------------------- #

def test_ein_zugang_vor_dem_juengsten_abschluss_wird_verweigert(tmp_path):
    """Der Befund des adversarialen Reviews: Die Grenzen der gefuehrten Zeit
    allein genuegen nicht. Ein Zugang, dessen Stichtag hinter einen bereits
    mit 0444 festgeschriebenen Monatsabschluss zurueckreicht, wuerde in der
    Gegenwart getragen und in der eingefrorenen Vergangenheit fehlen — ein
    Bilanzwert, der sich rueckwirkend bewegt haette, wenn er duerfte
    (ADR-011: genau einmal, nie ueberschrieben).

    Mutationsprobe: die Abschluss-Sperre entfernen -> der Lauf geht gruen
    durch, und der Abschluss zum 1.3. kennt die uebernommenen Vertraege
    nicht, obwohl der Stand sie ab dem 1.1. fuehrt."""
    stand = tmp_path / "daten"
    ablage = _ablage_ab(stand, dt.date(2026, 1, 1))
    assert tageslauf(ablage, dt.date(2026, 3, 3))[0] == EXIT_OK
    abschluesse = sorted(p.name for p in ablage.abschluesse.glob("abschluss_*.parquet"))
    assert abschluesse[-1] == "abschluss_2026-03-01.parquet"

    fall = _fall_mit_nebentabellen(tmp_path)                  # Stichtag 2026-01-01
    ueb.eingang_anlegen(stand, fall, STICHTAG)
    code, zeile = tageslauf(ablage, dt.date(2026, 3, 4))
    assert code != EXIT_OK and zeile["uebernommen"] is False
    assert "festgeschriebenen Monatsabschluss" in zeile["fehler"]


def test_ein_zugang_in_der_offenen_zeit_wird_gefuehrt(tmp_path):
    """Die Gegenprobe: Liegt der Zugang NACH dem juengsten Abschluss, faehrt
    der Betrieb ihn mit — der naechste Monatsabschluss kennt ihn dann."""
    stand = tmp_path / "daten"
    ablage = _ablage_ab(stand, dt.date(2025, 1, 1))
    assert tageslauf(ablage, dt.date(2025, 12, 31))[0] == EXIT_OK
    juengster = sorted(ablage.abschluesse.glob("abschluss_*.parquet"))[-1].stem
    assert juengster == "abschluss_2025-12-01"               # vor dem Zugang

    fall = _fall_mit_nebentabellen(tmp_path)                  # Stichtag 2026-01-01
    ueb.eingang_anlegen(stand, fall, STICHTAG)
    code, zeile = tageslauf(ablage, dt.date(2026, 1, 9))
    assert code == EXIT_OK, zeile.get("fehler") or zeile.get("pb1")
    stamm = read_portfolio(ablage.stand / "bestand_gesamt.parquet")
    assert 7_000_001 in set(stamm["police_id"])
    # Der Abschluss zum 1.1. entstand MIT dem Zugang:
    abschluss = read_portfolio(ablage.abschluesse / "abschluss_2026-01-01.parquet")
    assert 7_000_001 in set(abschluss["police_id"])


def test_ein_zugang_genau_am_juengsten_abschluss_wird_verweigert(tmp_path):
    """Die KANTE der Sperre: juengster Abschluss GLEICH Zugangsstichtag.

    Ein Abschluss ist die Bewertung AN seinem Stichtag; ein Bestand, der an
    diesem Tag zugeht, gehoert hinein. Liegt der Abschluss schon fest und
    kommt der Zugang danach, kennt der eingefrorene Wert ihn nie, waehrend
    der Stand ihn ab demselben Tag fuehrt. Der Annahmetest oben zeigt die
    andere Haelfte: Entsteht der Abschluss IM SELBEN LAUF, traegt er den
    Zugang (7000001 steht darin).

    Mutationsprobe (Testat der merge-session zu a47f72d): ein Zeichen im
    Guard, >= zu >, und die Suite blieb gruen — die Kante war ungebunden.
    Jetzt nicht mehr."""
    stand = tmp_path / "daten"
    ablage = _ablage_ab(stand, dt.date(2026, 1, 1))
    assert tageslauf(ablage, dt.date(2026, 1, 1))[0] == EXIT_OK
    assert (ablage.abschluesse / "abschluss_2026-01-01.parquet").is_file()

    fall = _fall_mit_nebentabellen(tmp_path)                  # Stichtag 2026-01-01
    ueb.eingang_anlegen(stand, fall, STICHTAG)
    code, zeile = tageslauf(ablage, dt.date(2026, 1, 2))
    assert code != EXIT_OK and zeile["uebernommen"] is False
    assert "festgeschriebenen Monatsabschluss 2026-01-01" in zeile["fehler"]
