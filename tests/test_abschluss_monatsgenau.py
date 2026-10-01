"""Der Monatsabschluss fuehrt monatsgenau — und sagt, in welcher Konvention.

Entscheid des Maintainers (2026-10-01): "Bisher dachte ich, dass der
Monatsabschluss die Werte monatlich fortschreibt. Wie wollen wir einen
Monatsabschluss mit angebrochenen Jahreswerten machen?" Der Abschluss
fuehrte das Deckungskapital als TREPPE — die Zeile des angebrochenen
Vertragsjahres (``zustand_am``), fuer jeden Vertragstyp gleich falsch, seit
die Funde N5/N11 der Pruefrunde T27 die Zweige auf "dieselbe
Stichtagskonvention" gezogen hatten. Jetzt mischt die eine Bewertungsstrecke
(``bestand.auswertung.einzelwerte_am``) unterjaehrig linear zwischen den
Jahrestagen, wie der Kern es kann — ohne Beitragsuebertrag (zurueckgestellt,
dev-docs/offene-punkte.md).

Die Kontrollrechnung ist unabhaengig: Der Test mischt die JAHRESZEILE der
alten Konvention an den beiden umschliessenden Jahrestagen selbst (die
Strecke rechnet dort ueber ``zustand_am``/``reserve_beitragsfrei``, die
monatsgenaue ueber ``monatsreserve``), statt f(x) == f(x) zu pruefen. Raender:
Monat 0, 11, 12, der letzte Monat vor Ablauf, Beitragsende, Monat der
Beitragsfreistellung und des Vorgangs.

Die Konvention ist ein Vertrag an EINER Stelle (``models.bestand.
abschluss_konvention``): Spaltenwert, oder bei fehlender Spalte benannt
"Jahreszeile, vor der Umstellung geschrieben". Jeder Leser einer
Abschlussdatei geht ueber ``bestand.abschluss.lies_abschluss`` — Ratsche
(statisch, ``==``) und Zaehltest (dynamisch) gehen gegen diese Funktion.
Die Alt-Gestalt ist eine ECHTE Datei: mit dem Schreiber VOR der Umstellung
erzeugt und gepinnt (``tests/fixtures/abschluss_vor_umstellung``).

Knoten: klv, bu
"""

from __future__ import annotations

import ast
import datetime as dt
import shutil
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import pytest

from rechner_pipeline.bestand.abschluss import (
    lies_abschluss,
    pruefe_abschluss,
    schreibe_abschluss,
)
from rechner_pipeline.bestand.auswertung import einzelwerte_am
from rechner_pipeline.bestand.config import config_aus_text
from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
from rechner_pipeline.kern import ModelPoint, Rechenkern
from rechner_pipeline.models.bestand import (
    ABSCHLUSS_NAMES,
    ABSCHLUSS_NAMES_VOR_UMSTELLUNG,
    FUEHRUNGSKONVENTION,
    HERKUNFT_SPALTE,
    HERKUNFT_VOR_UMSTELLUNG,
    KONVENTION_JAHRESZEILE,
    KONVENTION_MONATSGENAU,
    REDUKTIONEN_NAMES,
    REDUKTIONEN_SPALTEN,
    SCHEIBEN_NAMES,
    SCHEIBEN_SPALTEN,
    SCHICHTEN_NAMES,
    SCHICHTEN_SPALTEN,
    STATUS_HISTORIE_SPALTEN,
    VERANKERUNG_SPALTEN,
    AbschlussKonventionFehler,
    abschluss_konvention,
    konventionsbruch,
    model_point_kwargs,
    schichten_zeile,
    validate_abschluss,
)
from tests.test_bestand_uebernommen_fortschreiben import _CONFIG_TOML, _stamm
from tests.test_schicht_in_fuehrung import _parameter

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src" / "rechner_pipeline"
ALT = Path(__file__).resolve().parent / "fixtures" / "abschluss_vor_umstellung"
ALT_DATEI = ALT / "abschluss_2026-10-01.parquet"
ALT_STICHTAG = dt.date(2026, 10, 1)
BEGINN = dt.date(2015, 1, 1)


def _config():
    return config_aus_text(_CONFIG_TOML)


def _tag(monate: int, beginn: dt.date = BEGINN) -> dt.date:
    j, m = divmod(beginn.month - 1 + monate, 12)
    return dt.date(beginn.year + j, m + 1, 1)


# --------------------------------------------------------------------------- #
# Die Vertragstypen — selbst gebaute Welt, keine Betraege aus Config-Welten
# --------------------------------------------------------------------------- #


def _welt(typ: str) -> Dict[str, Optional[pd.DataFrame]]:
    """Ein Vertrag je Typ (Beginn 2015-01-01, n=25, t=20) mit seinen Nebentabellen."""
    zeile = {"id": 1, "beginn": BEGINN.isoformat(), "n": 25, "t": 20}
    if typ in ("schicht", "schicht_absorbiert", "schicht_pex_vorher"):
        zeile["zugang"] = "2025-01-01"
    stamm = _stamm([zeile])
    t: Dict[str, Optional[pd.DataFrame]] = {
        "stamm": stamm, "historie": None, "scheiben": None, "schichten": None,
        "verankerung": None, "reduktionen": None}
    pex = {"pex": "2020-01-01", "schicht_absorbiert": "2026-01-01",
           "schicht_pex_vorher": "2024-01-01"}.get(typ)
    if pex:
        t["historie"] = pd.DataFrame([{"police_id": 1, "status_id": 2, "status_code": "PEX",
                                       "status_date": pd.Timestamp(pex)}]
                                     ).astype(dict(STATUS_HISTORIE_SPALTEN))
    if typ == "scheiben":
        t["scheiben"] = pd.DataFrame([{
            "police_id": 1, "scheiben_id": 1, "erhoehung_jahr": 5,
            "erhoehung_datum": pd.Timestamp("2020-01-01"), "entry_age": 45, "duration": 20,
            "premium_duration": 15, "sum_insured": 5000.0, "gamma1": 0.0,
        }])[list(SCHEIBEN_NAMES)].astype(dict(SCHEIBEN_SPALTEN))
    if typ in ("red", "tku"):
        t["reduktionen"] = pd.DataFrame([{
            "police_id": 1, "reduktion_jahr": 8, "reduktion_datum": pd.Timestamp("2023-01-01"),
            "anteil": 0.6, "verfahren": "prospektiv" if typ == "red" else "teilkuendigung",
        }])[list(REDUKTIONEN_NAMES)].astype(dict(REDUKTIONEN_SPALTEN))
    if typ.startswith("schicht"):
        t["schichten"] = pd.DataFrame([schichten_zeile(1, _parameter(0.04).als_beleg())],
                                      columns=list(SCHICHTEN_NAMES)).astype(dict(SCHICHTEN_SPALTEN))
        zustand = "beitragsfrei" if typ == "schicht_pex_vorher" else "beitragspflichtig"
        t["verankerung"] = pd.DataFrame([{
            "police_id": 1, "monate_ta": 120, "zustand_ta": zustand, "verweildauer_ta": 10,
            "dk_ta": 1.0}])[[n for n, _ in VERANKERUNG_SPALTEN]].astype(dict(VERANKERUNG_SPALTEN))
    return t


def _zeile(t, monate: int, konvention: str) -> Optional[dict]:
    zeilen = einzelwerte_am(
        t["stamm"], t["historie"], _config(), _tag(monate), scheiben=t["scheiben"],
        schichten=t["schichten"], verankerung=t["verankerung"], reduktionen=t["reduktionen"],
        konvention=konvention)
    return zeilen[0] if zeilen else None


#: Je Typ die Monate, an denen geprueft wird: die allgemeinen Raender und die
#: des Typs (Beitragsende 240, Freistellung, Vorgang, Verankerung).
MONATE = {
    "gewoehnlich": [0, 1, 11, 12, 13, 95, 96, 239, 240, 241, 298, 299],
    "pex": [59, 60, 61, 71, 72, 141, 239, 240, 241, 299],
    "scheiben": [59, 60, 61, 71, 72, 141, 239, 240, 241, 299],
    "red": [95, 96, 97, 107, 108, 141, 239, 240, 241, 299],
    "tku": [95, 96, 97, 107, 108, 141, 239, 240, 241, 299],
    "schicht": [120, 121, 131, 132, 141, 239, 240, 241, 299],
    "schicht_absorbiert": [131, 132, 133, 141, 143, 144, 239, 240, 241, 299],
    "schicht_pex_vorher": [120, 121, 131, 132, 141, 239, 240, 241, 299],
}
#: Der Vertragsmonat des Vorgangs je Typ (Freistellung, Erhoehung,
#: Herabsetzung, Teilkuendigung) — er wirkt am Jahrestag. Im Jahr DAVOR
#: laeuft der Vertrag, wie er war: Die Mischung des letzten Monats vor dem
#: Vorgang nimmt am oberen Jahrestag den Vertrag OHNE den Vorgang.
VORGANG = {"pex": 60, "scheiben": 60, "red": 96, "tku": 96,
           "schicht_absorbiert": 132, "schicht_pex_vorher": 108}
GROESSEN = ("deckungskapital", "korrekturschicht", "vs_bfr")


def _ohne_vorgang(t):
    neu = dict(t)
    neu["historie"] = neu["scheiben"] = neu["reduktionen"] = None
    return neu


@pytest.mark.parametrize("typ", sorted(MONATE))
def test_monatsgenau_ist_die_mischung_der_jahreszeile_an_beiden_jahrestagen(typ):
    """Am Jahrestag gleich der Jahreszeile; dazwischen die lineare Mischung
    der Jahreszeilen der beiden umschliessenden Jahrestage — fuer jeden
    Vertragstyp dieselbe Regel (kein Typ rechnet anders als der Nachbar,
    der Kern der Funde N5/N11). Die Mischung rechnet der Test; die Strecke
    liest unter ``jahreszeile`` andere Kern-Funktionen als unter
    ``monatsgenau``.

    Der letzte Monat vor Ablauf (299) mischt mit dem Ablaufjahrestag, an
    dem der Vertrag nicht mehr im Bestand steht — dort ist die Kontrolle
    die Kern-Zeile des Jahres n selbst (Ablaufleistung, beitragsfreie
    Reserve am Ablauf)."""
    t = _welt(typ)
    for monate in MONATE[typ]:
        neu = _zeile(t, monate, KONVENTION_MONATSGENAU)
        a, rest = divmod(monate, 12)
        unten = _zeile(t, 12 * a, KONVENTION_JAHRESZEILE)
        assert neu is not None and unten is not None, (typ, monate)
        if rest == 0:
            for g in GROESSEN + ("rueckkaufswert",):
                assert neu[g] == unten[g], (typ, monate, g)
            continue
        welt_oben = t if a + 1 < 25 else _ueber_den_ablauf(t)
        if VORGANG.get(typ) == 12 * (a + 1):
            welt_oben = _ohne_vorgang(welt_oben)
        oben = _zeile(welt_oben, 12 * (a + 1), KONVENTION_JAHRESZEILE)
        u = rest / 12.0
        for g in ("deckungskapital", "korrekturschicht"):
            erwartet = (1.0 - u) * unten[g] + u * oben[g]
            assert neu[g] == pytest.approx(erwartet, rel=1e-12, abs=1e-8), (typ, monate, g)
        # Die beitragsfreie Summe ist bei der Freistellung fixiert — keine
        # Mischung, in beiden Konventionen derselbe Wert.
        assert neu["vs_bfr"] == unten["vs_bfr"], (typ, monate)
        # Unterjaehrig liegt der Wert zwischen den Jahrestagen — die Treppe
        # wies den unteren aus (bis 11/12 des Jahreszuwachses zu wenig).
        if rest and oben is not None and oben["deckungskapital"] != unten["deckungskapital"]:
            assert neu["deckungskapital"] != unten["deckungskapital"], (typ, monate)


def _ueber_den_ablauf(t):
    """Dieselbe Welt, der Vertrag aber einen Monat ueber den Ablauf im
    Bestand: Am Ablaufjahrestag selbst steht er nicht mehr im Abschluss, die
    Jahreszeile des Jahres n (Ablaufwert, Schicht null) liest die Strecke
    trotzdem — die Dauern des Modellpunkts bleiben, nur der Bestandsschnitt
    (``insurance_end``) ruckt."""
    neu = dict(t)
    neu["stamm"] = t["stamm"].copy()
    neu["stamm"]["insurance_end"] = neu["stamm"]["insurance_end"] + pd.DateOffset(months=1)
    return neu


def test_rueckkaufswert_der_mischung_folgt_dem_tarifwerk_des_angebrochenen_jahres():
    """Der Rueckkaufswert wird nicht gemischt, sondern aus der gemischten
    Reserve neu gerechnet (Stornoabschlag auf die gemischte Deckungs-
    rueckstellung, Regeln des Jahres ``a``) — Kontrolle aus Kern-Zeilen und
    ``stornoabzug``, ohne ``monatsreserve``."""
    t = _welt("gewoehnlich")
    mp = ModelPoint(**model_point_kwargs(
        t["stamm"].iloc[0], _config().generationen[0].generation_fields()))
    kern = Rechenkern(mp)
    for monate in (1, 11, 95, 239, 241, 299):
        a, rest = divmod(monate, 12)
        u = rest / 12.0
        za, zb = kern.verlaufszeile(a), kern.verlaufszeile(a + 1)
        dr = (1 - u) * za.drx_bpfl + u * zb.drx_bpfl
        mrv = (1 - u) * za.vx_mrv + u * zb.vx_mrv
        erwartet = max(0.0, mrv - kern.produkt.stornoabzug(a, dr))
        assert _zeile(t, monate, KONVENTION_MONATSGENAU)["rueckkaufswert"] == pytest.approx(
            erwartet, rel=1e-12), monate


def test_referenzvertrag_monat_95_ist_nicht_mehr_die_treppe():
    """Der Befund des Maintainers in Zahlen: Monat 84 und 96 sind Jahrestage,
    Monat 95 lag auf der Treppe beim Wert von Monat 84. Kontrolle: die
    Mischung der beiden Jahreszeilen, aus dem Kern gelesen."""
    t = _welt("gewoehnlich")
    mp = ModelPoint(**model_point_kwargs(
        t["stamm"].iloc[0], _config().generationen[0].generation_fields()))
    kern = Rechenkern(mp)
    j7, j8 = kern.verlaufszeile(7).drx_bpfl, kern.verlaufszeile(8).drx_bpfl
    assert _zeile(t, 95, KONVENTION_JAHRESZEILE)["deckungskapital"] == j7
    assert _zeile(t, 95, KONVENTION_MONATSGENAU)["deckungskapital"] == pytest.approx(
        j7 / 12 + 11 * j8 / 12, rel=1e-12)
    assert j8 - j7 > 1000.0   # der Unterschied ist kein Rauschen


def test_der_absorbierte_schichtwert_ist_der_anteil_an_der_beitragsfreien_monatsreserve():
    """Der Kern fuehrt den in die beitragsfreie Summe ueberfuehrten
    Schichtwert nur je Vertragsjahr; die Strecke mischt ihn wie die
    Reserve. Kontrolle ueber die Linearitaet (Kern-Doku zu
    ``absorptions_zuschlag``): Schichtwert am Freistellungsjahr mal
    beitragsfreie Monatsreserve durch die Umwandlungsreserve."""
    from rechner_pipeline.kern.korrekturschicht import schichtwert_bei

    t = _welt("schicht_absorbiert")
    mp = ModelPoint(**model_point_kwargs(
        t["stamm"].iloc[0], _config().generationen[0].generation_fields()))
    kern = Rechenkern(mp)
    pex = 11
    w = schichtwert_bei(_parameter(0.04), 120, mp, 12 * pex)
    for monate in (133, 137, 143):
        erwartet = w * kern.monatsreserve_beitragsfrei(pex, monate) / kern.reserve_beitragsfrei(pex, pex)
        assert _zeile(t, monate, KONVENTION_MONATSGENAU)["korrekturschicht"] == pytest.approx(
            erwartet, rel=1e-12), monate


def test_die_bu_bleibt_benannt_bei_der_jahreszeile():
    """Der Kern fuehrt fuer die BU keine unterjaehrige Reserve
    (``kern.produkte.bu`` kennt nur Vertragsjahre). Die Konvention wird je
    Produkt gefuehrt: unter ``monatsgenau`` bleibt die BU bei der
    Jahreszeile — benannt in ``KONVENTION_JE_PRODUKT``, nicht still
    gemischt. Kontrolle: die Aktivenreserve des Kerns im angebrochenen
    Jahr, in beiden Konventionen."""
    from rechner_pipeline.bestand.config import load_config
    from rechner_pipeline.models.bestand import KONVENTION_JE_PRODUKT
    from tests.test_bestand_bu import BU_EXAMPLE, _bu_stamm

    assert KONVENTION_JE_PRODUKT[KONVENTION_MONATSGENAU]["bu"] == KONVENTION_JAHRESZEILE
    config = load_config(BU_EXAMPLE)
    gen = config.generationen[0].name
    stamm = _bu_stamm({"police_id": 1, "start": dt.date(2015, 1, 1), "x": 40, "n": 25,
                       "tarif_generation": gen})
    for monate in (11, 95, 141):
        werte = {k: einzelwerte_am(stamm, None, config, _tag(monate), konvention=k)[0]
                 for k in (KONVENTION_JAHRESZEILE, KONVENTION_MONATSGENAU)}
        assert werte[KONVENTION_JAHRESZEILE]["deckungskapital"] == \
            werte[KONVENTION_MONATSGENAU]["deckungskapital"]
        from rechner_pipeline.bestand.auswertung import _bu_produkte_je_police
        produkt = _bu_produkte_je_police(stamm, config)[1]
        assert werte[KONVENTION_MONATSGENAU]["deckungskapital"] == produkt.reserve_aktiv(monate // 12)


def test_eine_unbekannte_konvention_ist_ein_aufruffehler():
    t = _welt("gewoehnlich")
    with pytest.raises(ValueError, match="unbekannt"):
        _zeile(t, 95, "treppe")


# --------------------------------------------------------------------------- #
# Die Konvention ist ein Vertrag an EINER Stelle
# --------------------------------------------------------------------------- #


def _alt_tabellen():
    return {n: read_portfolio(ALT / f"{n}.parquet")
            for n in ("bestand", "historie", "scheiben", "schichten", "verankerung", "reduktionen")}


def _alt_pruefen(pfad: Path) -> List[str]:
    t = _alt_tabellen()
    return pruefe_abschluss(
        pfad, t["bestand"], t["historie"], config_aus_text((ALT / "config.toml").read_text("utf-8")),
        scheiben=t["scheiben"], schichten=t["schichten"], verankerung=t["verankerung"],
        reduktionen=t["reduktionen"], merkmale=None)


def test_die_alt_gestalt_ist_eine_echte_datei_des_alten_schreibers():
    """Die gepinnte Datei hat die Spalten VOR der Umstellung und traegt
    unterjaehrige Vertraege aller Typen (gewoehnlich, beitragsfrei, Scheibe,
    Schicht, herabgesetzt, teilgekuendigt, Schicht ueberfuehrt)."""
    import pyarrow.parquet as pq

    assert pq.read_table(ALT_DATEI).column_names == list(ABSCHLUSS_NAMES_VOR_UMSTELLUNG)
    tabelle, konvention = lies_abschluss(ALT_DATEI)
    assert list(tabelle.columns) == list(ABSCHLUSS_NAMES_VOR_UMSTELLUNG)
    assert len(tabelle) == 8 and set(tabelle["status_code"]) == {"POL", "PEX"}
    assert konvention.name == KONVENTION_JAHRESZEILE
    assert konvention.herkunft == HERKUNFT_VOR_UMSTELLUNG and konvention.vor_umstellung
    assert validate_abschluss(tabelle) == []


def test_ein_alter_abschluss_wird_in_seiner_konvention_nachgerechnet_und_ist_deckungsgleich():
    """Nicht an der Spaltengestalt abgewiesen, nicht pauschal als Abweichung
    gegen die heutige Konvention gemeldet: deckungsgleich mit der
    Jahreszeile, in der er geschrieben wurde.

    Die Fixture ist unter Kern 3.16.0 festgeschrieben. Ein spaeterer
    Kernstand (3.17.0: die Vorgangsfolge) meldet den Versionssprung als
    EIGENE Zeile (ADR-011: der Abschluss bleibt stehen) — und sonst nichts:
    Die Neuberechnung ist deckungsgleich, auch fuer die Vertraege mit
    Herabsetzung der Fixture (ein Vorgang je Vertrag rechnet bitgleich)."""
    from rechner_pipeline.kern import __version__ as kern_version

    befunde = _alt_pruefen(ALT_DATEI)
    sprung = [b for b in befunde if "festgeschrieben unter Kern ['3.16.0']" in b]
    assert len(sprung) == (kern_version != "3.16.0")
    assert [b for b in befunde if b not in sprung] == []


def test_der_alte_abschluss_waere_in_der_heutigen_konvention_eine_abweichung(tmp_path):
    """Gegenprobe: Dieselbe Datei MIT der Spalte "monatsgenau" (so taete ein
    Leser, der die Konvention nicht fragt) weicht bei jedem unterjaehrigen
    Vertrag ab — die Nachrechnung in der Konvention der Datei ist also keine
    Formsache."""
    tabelle, _ = lies_abschluss(ALT_DATEI)
    tabelle["bewertungskonvention"] = KONVENTION_MONATSGENAU
    pfad = tmp_path / ALT_DATEI.name
    write_portfolio(tabelle[list(ABSCHLUSS_NAMES)], pfad)
    befunde = _alt_pruefen(pfad)
    assert any("deckungskapital festgeschrieben" in b for b in befunde), befunde


def test_ein_cent_im_alten_abschluss_faellt_der_nachrechnung_auf(tmp_path):
    """Die Nachrechnung des alten Abschlusses ist kein Detektor ohne Treffer."""
    pfad = tmp_path / ALT_DATEI.name
    tabelle, _ = lies_abschluss(ALT_DATEI)
    tabelle.loc[tabelle["police_id"] == 3, "deckungskapital"] += 0.01
    write_portfolio(tabelle, pfad)
    assert any("police 3: deckungskapital" in b for b in _alt_pruefen(pfad))


def test_der_schreiber_nennt_seine_konvention_und_die_nachrechnung_deckt_ihn(tmp_path):
    t = _alt_tabellen()
    config = config_aus_text((ALT / "config.toml").read_text("utf-8"))
    pfad = schreibe_abschluss(t["bestand"], t["historie"], config, ALT_STICHTAG, tmp_path,
                              scheiben=t["scheiben"], schichten=t["schichten"],
                              verankerung=t["verankerung"], reduktionen=t["reduktionen"], merkmale=None)
    tabelle, konvention = lies_abschluss(pfad)
    assert list(tabelle.columns) == list(ABSCHLUSS_NAMES)
    assert set(tabelle["bewertungskonvention"]) == {FUEHRUNGSKONVENTION} == {KONVENTION_MONATSGENAU}
    assert konvention.name == KONVENTION_MONATSGENAU and konvention.herkunft == HERKUNFT_SPALTE
    assert _alt_pruefen(pfad) == []
    alt, _ = lies_abschluss(ALT_DATEI)
    # Jeder Vertrag der Fixture ist unterjaehrig: der neue Stand liegt ueber
    # der Treppe (die Reserven wachsen in diesen Jahren).
    assert (tabelle["deckungskapital"].to_numpy() > alt["deckungskapital"].to_numpy()).all()


@pytest.mark.parametrize("werte,meldung", [
    (["monatsgenau", "jahreszeile"], "genau eine"),
    (["treppe", "treppe"], "genau eine"),
])
def test_eine_datei_in_zwei_oder_unbekannter_konvention_ist_keine_bilanz(werte, meldung):
    tabelle, _ = lies_abschluss(ALT_DATEI)
    tabelle = tabelle.iloc[:2].copy()
    tabelle["bewertungskonvention"] = werte
    with pytest.raises(AbschlussKonventionFehler, match=meldung):
        abschluss_konvention(tabelle[list(ABSCHLUSS_NAMES)])
    assert any("bewertungskonvention" in b for b in validate_abschluss(tabelle[list(ABSCHLUSS_NAMES)]))


def test_eine_fremde_gestalt_hat_keine_konvention():
    tabelle, _ = lies_abschluss(ALT_DATEI)
    with pytest.raises(AbschlussKonventionFehler, match="weder"):
        abschluss_konvention(tabelle.drop(columns=["korrekturschicht"]))


def test_ein_leerer_abschluss_traegt_keine_bewertung_in_beiden_gestalten():
    tabelle, _ = lies_abschluss(ALT_DATEI)
    for spalten in (ABSCHLUSS_NAMES_VOR_UMSTELLUNG, ABSCHLUSS_NAMES):
        leer = pd.DataFrame({n: pd.Series(dtype="object") for n in spalten})
        assert abschluss_konvention(leer).name is None


def test_eine_reihe_ueber_die_naht_ist_ein_benannter_bruch():
    """Wer Abschluesse verschiedener Stichtage in eine Reihe legt
    (vorzeige-url: Monatsbericht ueber zwoelf Abschluesse), fragt
    ``konventionsbruch``: Ueber die Umstellung hinweg springt das
    Deckungskapital ohne Geschaeftsvorfall."""
    alt = lies_abschluss(ALT_DATEI)[1]
    tabelle, _ = lies_abschluss(ALT_DATEI)
    tabelle["bewertungskonvention"] = KONVENTION_MONATSGENAU
    neu = abschluss_konvention(tabelle[list(ABSCHLUSS_NAMES)])
    leer = abschluss_konvention(pd.DataFrame(
        {n: pd.Series(dtype="object") for n in ABSCHLUSS_NAMES}))
    assert konventionsbruch([alt, alt]) is None
    assert konventionsbruch([neu, leer, neu]) is None
    assert "Konventionsbruch" in str(konventionsbruch([alt, leer, neu]))


def test_read_portfolio_kennt_die_alte_gestalt_als_familie():
    """Ohne Familieneintrag fiele eine alte Datei in den Stamm-Rueckfall und
    kaeme als Teilmenge OHNE Bewertungsspalten zurueck."""
    assert list(read_portfolio(ALT_DATEI).columns) == list(ABSCHLUSS_NAMES_VOR_UMSTELLUNG)


# --------------------------------------------------------------------------- #
# Ratsche und Zaehltest: jeder Leser fragt die eine Funktion
# --------------------------------------------------------------------------- #

#: Wo eine Abschlussdatei liegt — Namen, an denen eine Funktion sich als
#: Abschluss-Hantierer zu erkennen gibt.
_ORT = {"abschluss_pfad", "abschluesse", "abschluesse_dir", "ABSCHLUSS_DIR",
        "PAKET_ABSCHLUESSE_DIR", "_abschluesse", "vorhandene_abschluesse",
        "_festgeschriebene_abschluesse"}
#: Rohe Parquet-Leser.
_ROH = {"read_portfolio", "read_portfolio_aus_bytes", "read_table", "read_parquet"}


def _scan(quellen: Dict[str, str]) -> Dict[str, set]:
    """Je Funktion (Modul::Name), die Abschlussdateien hantiert: ob sie
    ``lies_abschluss`` ruft und welche rohen Leser."""
    aus: Dict[str, set] = {}
    for modul, text in quellen.items():
        for f in ast.walk(ast.parse(text)):
            if not isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            namen = set()
            aufrufe = set()
            for k in ast.walk(f):
                if isinstance(k, ast.Name):
                    namen.add(k.id)
                elif isinstance(k, ast.Attribute):
                    namen.add(k.attr)
                elif isinstance(k, ast.Constant) and isinstance(k.value, str) \
                        and "abschluss_" in k.value:
                    namen.add("abschluss_")
                if isinstance(k, ast.Call):
                    fn = k.func
                    aufrufe.add(fn.id if isinstance(fn, ast.Name)
                                else fn.attr if isinstance(fn, ast.Attribute) else None)
            if namen & _ORT or "abschluss_" in namen:
                aus[f"{modul}::{f.name}"] = (aufrufe & _ROH) | (
                    {"lies_abschluss"} if "lies_abschluss" in aufrufe else set())
    return aus


def _quellen() -> Dict[str, str]:
    return {str(p.relative_to(SRC)): p.read_text(encoding="utf-8")
            for p in sorted(SRC.rglob("*.py"))}


#: Die Leser einer Abschlussdatei — jeder ueber ``lies_abschluss``.
LESER = {
    "bestand/abschluss.py::pruefe_abschluss",
    "betrieb/seite.py::_ergaenze_kennzahlen",
    "betrieb/tageslauf.py::_pruefe_zahlen_der_zeile",
    "betrieb/tageslauf.py::_abschluss_kennt_eingang",
    "betrieb/tageslauf.py::_tageslauf_mit_config",
    "betrieb/zugangsprobe.py::vergleiche",
}
#: Funktionen, die Abschlussdateien hantieren UND roh lesen — je mit dem,
#: was sie roh lesen (keine Abschlussdatei). Eine neue Zeile ist zu
#: begruenden; wer hier eine Abschlussdatei roh liest, liest an der
#: Konvention vorbei.
ROH_ANDERES = {
    "bestand/abschluss.py::lies_abschluss": "der eine Leseweg selbst",
    "betrieb/seite.py::stand_modell_mit_bytes": "das Tagesjournal",
    "betrieb/tageslauf.py::_pruefe_zahlen_der_zeile": "Stand-Tabellen und Tagesjournal",
    "betrieb/tageslauf.py::_tageslauf_mit_config": "Stand-, Eingangs- und Journaltabellen",
    "betrieb/zugangsprobe.py::vergleiche": "die Tagesjournale der Kopien",
}


def test_ratsche_jeder_leser_einer_abschlussdatei_fragt_die_eine_funktion():
    """Statisch, mit ``==``: die Funktionen, die ``lies_abschluss`` rufen,
    sind genau :data:`LESER`, und die Abschluss-Hantierer, die daneben roh
    lesen, genau :data:`ROH_ANDERES` (mit dem, was sie roh lesen).

    Grenze (benannt): Die Ratsche sieht eine Funktion, nicht den
    Datenfluss — eine Funktion aus ROH_ANDERES koennte eine Abschlussdatei
    roh lesen, ohne dass sich eine Menge aendert. Dafuer steht der
    Zaehltest daneben."""
    scan = _scan(_quellen())
    leser = {f for f, a in scan.items() if "lies_abschluss" in a}
    roh = {f for f, a in scan.items() if a & _ROH}
    assert leser == LESER
    assert roh == set(ROH_ANDERES)


def test_ratsche_positivkontrolle_ein_roher_leser_wird_gefunden():
    """Detektor mit Treffer: ein neuer Leser, der die Datei roh liest."""
    neu = _scan({"x.py": (
        "def bericht(ablage, tag):\n"
        "    return read_portfolio(abschluss_pfad(ablage.abschluesse, tag))\n")})
    assert neu == {"x.py::bericht": {"read_portfolio"}}


def test_ratsche_die_spalte_liest_niemand_ausser_dem_vertrag():
    """Gegen die Funktion, nicht gegen die Spalte: Den Spaltennamen nennt nur
    der Datenvertrag (models.bestand) und der Schreiber (bestand.abschluss)."""
    nennen = {m for m, text in _quellen().items() if "bewertungskonvention" in text}
    assert nennen == {"models/bestand.py", "bestand/abschluss.py"}


def test_zaehltest_jeder_leser_ruft_abschluss_konvention(tmp_path, monkeypatch):
    """Dynamisch: Jeder hier fahrbare Leser ruft ``abschluss_konvention``
    (ueber ``lies_abschluss``) — gezaehlt je Leser."""
    from rechner_pipeline.bestand import abschluss as abschluss_mod
    from rechner_pipeline.betrieb import seite
    from rechner_pipeline.betrieb import tageslauf as tl
    from rechner_pipeline.betrieb import zugangsprobe as zpb
    from rechner_pipeline.models.bestand import LEDGER_SPALTEN, TAGESJOURNAL_SPALTEN

    aufrufe: List[str] = []
    echt = abschluss_mod.abschluss_konvention

    def zaehlend(df):
        aufrufe.append("x")
        return echt(df)

    monkeypatch.setattr(abschluss_mod, "abschluss_konvention", zaehlend)

    def gezaehlt(leser) -> int:
        vorher = len(aufrufe)
        leser()
        return len(aufrufe) - vorher

    assert gezaehlt(lambda: _alt_pruefen(ALT_DATEI)) == 1
    assert gezaehlt(lambda: seite._ergaenze_kennzahlen(
        [{"stichtag": ALT_STICHTAG.isoformat(), "datei": ALT_DATEI.name}], None, ALT)) == 1
    ablage = tl.Ablage(tmp_path / "ablage")
    ablage.abschluesse.mkdir(parents=True)
    shutil.copy(ALT_DATEI, ablage.abschluesse / ALT_DATEI.name)
    assert gezaehlt(lambda: tl._abschluss_kennt_eingang(ablage, ALT_STICHTAG, [1])) == 1

    # Die Zugangsprobe: zwei Kopien mit demselben alten Abschluss am
    # Zugangsstichtag — sie liest beide und verweigert den Vergleich
    # benannt, weil die Abnahme monatsgenau rechnet.
    leeres_journal = pd.DataFrame({n: pd.Series(dtype=d) for n, d in TAGESJOURNAL_SPALTEN})
    for name in (zpb.KOPIE_OHNE, zpb.KOPIE_MIT):
        a = tl.Ablage(tmp_path / name)
        a.abschluesse.mkdir(parents=True)
        shutil.copy(ALT_DATEI, a.abschluesse / ALT_DATEI.name)
        a.journal.mkdir()
        write_portfolio(leeres_journal, a.tagesjournal_pfad)
    soll = zpb.Soll(anzahl=0, uebersetzung={}, vs={}, jb={},
                    ledger=pd.DataFrame({n: pd.Series(dtype=d) for n, d in LEDGER_SPALTEN}),
                    folgetermin=None, in_kraft_folge=None, eingaben={},
                    konvention=KONVENTION_MONATSGENAU)
    befunde: List[str] = []
    assert gezaehlt(lambda: befunde.extend(zpb.vergleiche(
        tmp_path / zpb.KOPIE_OHNE, tmp_path / zpb.KOPIE_MIT, soll, stichtag=ALT_STICHTAG)[1])) == 2
    assert any("Konvention 'jahreszeile'" in b and "nicht verglichen" in b for b in befunde), befunde
