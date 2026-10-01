"""Die Fuehrungsprobe traegt beide Klassen der Runde E — Zaehltest je Instanz.

* **Buchungsfenster** (``test_klasse_buchungsfenster_e``): Die Probe prueft
  jede Buchung der uebernommenen Vertraege gegen den Zugang und den belegten
  Horizont, nicht nur ``RED``. Menge: ``EREIGNIS_VALUES``.
* **Bindung Ereignisart -> Rate** (``test_klasse_ereignis_rate_e``): Die Probe
  meldet jede Buchung nach dem Zugang, die keine Annahme der Config erzeugen
  kann. Menge: die KLV-Felder von ``ANNAHME_ERZEUGT`` (die Probe ist
  KLV-Werkzeug; die BU-Felder misst der Zaehltest an P-B1).

Die Welt ist der gefahrene zweite Baldrian-Lauf wie in
``test_t27_pruefstrecke_runde_c``; nur der ORT bzw. die Art der von Hand
eingelegten Zeile ist der Fehler, die Positivkontrolle jeweils derselbe Weg an
zulaessiger Stelle.

Knoten: klv
"""

from __future__ import annotations

import copy
import datetime as _dt
import inspect
from typing import Any, Dict, List

import pandas as pd
import pytest

from rechner_pipeline.bestand.config import Annahme
from rechner_pipeline.gates.fuehrungsprobe import pruefe_fuehrung
from rechner_pipeline.models.bestand import (
    ANNAHME_ERZEUGT,
    BETRAG_ART_JE_EREIGNIS,
    EREIGNIS_OHNE_ANNAHME,
    EREIGNIS_VALUES,
    LEDGER_NAMES,
    LEDGER_SPALTEN,
)
from tests.test_baldrian2_e2e import gefahrener_fall  # noqa: F401
from tests.test_t27_pruefstrecke_runde_c import (  # noqa: F401
    POL,
    ZUGANGSJAHR,
    _mit_red,
    _texte,
    _urteil,
    welt,
)

ZUGANG = pd.Timestamp("2026-01-01")          # Stichtag der Uebernahme = Bestandszugang
VOR = pd.Timestamp("2025-01-01")
HORIZONT = pd.Timestamp("2027-01-01")        # belegter Horizont der Welt
DAHINTER = pd.Timestamp("2028-01-01")
AM_ZUGANGSTAG_ERLAUBT = {"ZUG", "MIG", "PEX"}
KLV_FELDER = sorted(f for f, (p, _e) in ANNAHME_ERZEUGT.items() if p == "klv")
#: Eine Rate, die die Engine im Test nie zieht, aber als Rate zaehlt.
KLEIN = Annahme(a=1e-6, b=0.0)
NULL = Annahme(a=0.0, b=0.0)


def _mit_zeile(welt, art: str, datum: pd.Timestamp, tab=None) -> Dict[str, Any]:
    """Die Fortschreibung der Welt mit EINER eingelegten Buchung der Art —
    ohne Tabelle und Folgezeilen; nur Art und Datum sind der Gegenstand."""
    tab = dict(tab or welt["tab"])
    stamm = welt["ueb"]["bestand"]
    row = stamm[stamm["police_id"] == POL].iloc[0]
    jahr = ((datum.year * 12 + datum.month)
            - (pd.Timestamp(row["insurance_start"]).year * 12
               + pd.Timestamp(row["insurance_start"]).month)) // 12
    neu = pd.DataFrame([{
        "police_id": POL, "tarif_generation": row["tarif_generation"], "ereignis": art,
        "vertragsjahr": int(jahr), "status_date": datum,
        "betrag_art": BETRAG_ART_JE_EREIGNIS[art][0], "betrag": 1.0,
        "betrag_herkunft": "gerechnet"}])[list(LEDGER_NAMES)].astype(dict(LEDGER_SPALTEN))
    tab["ledger"] = pd.concat([tab["ledger"], neu], ignore_index=True).sort_values(
        ["police_id", "status_date"], kind="stable").reset_index(drop=True)
    return tab


def _fenster_texte(urteil) -> List[str]:
    """Befunde zum Buchungsfenster, gleich unter welcher Art sie stehen
    (RED-Zeilen stehen unter 'herabsetzung', die uebrigen unter
    'buchungsfenster')."""
    return [b["text"] for b in urteil["befunde"]
            if "-Buchung" in b["text"]
            and ("nicht nach dem Bestandszugang" in b["text"]
                 or "nach dem belegten Horizont" in b["text"])]


# --------------------------------------------------------------------------- #
# Ratsche (statisch)
# --------------------------------------------------------------------------- #


def test_ratsche_die_probe_ruft_beide_regeln():
    """Statisch: Die Probe fuehrt keine eigene Abschrift, sie ruft die Regeln
    von P-B1. Mutationsprobe: einen der beiden Aufrufe in pruefe_fuehrung
    entfernen -> rot."""
    quelle = inspect.getsource(pruefe_fuehrung)
    assert "buchungsfenster_verstoesse(" in quelle
    assert "ausnahme_ereignis_verstoesse(" in quelle
    assert "unbelegte_ereignisse(" in quelle
    assert "unzugeordnete_ereignisse(" in quelle


# --------------------------------------------------------------------------- #
# Zaehltest Buchungsfenster je Ereignisart
# --------------------------------------------------------------------------- #


def test_positivkontrolle_die_welt_ist_gruen_und_ihre_zugangsbuchungen_bestehen(welt):
    """Die unveraenderte Welt: ZUG, PEX (Umbuchung) am Zugangstag sind
    Buchungen der Uebernahme und bleiben gruen."""
    urteil = _urteil(welt, welt["tab"])
    assert urteil["bestanden"], urteil["befunde"][:3]
    assert _fenster_texte(urteil) == []


@pytest.mark.parametrize("art", EREIGNIS_VALUES)
def test_die_probe_haelt_jede_art_im_fenster_gruen(welt, art):
    """Positivkontrolle je Art: dieselbe Zeile am Horizont selbst (nach dem
    Zugang, nicht dahinter) bringt keinen Fensterbefund."""
    urteil = _urteil(welt, _mit_zeile(welt, art, HORIZONT))
    assert _fenster_texte(urteil) == [], urteil["befunde"][:4]


@pytest.mark.parametrize("art", EREIGNIS_VALUES)
def test_die_probe_weist_jede_art_vor_dem_zugang_ab(welt, art):
    """Zaehltest je Art. Mutationsprobe: die Untergrenze fuer genau diese Art
    in buchungsfenster_verstoesse ausnehmen -> genau dieser Fall rot."""
    urteil = _urteil(welt, _mit_zeile(welt, art, VOR))
    texte = _fenster_texte(urteil)
    assert any(t.startswith(f"{art}-Buchung nicht nach dem Bestandszugang (am 2025-01-01)")
               for t in texte), (art, urteil["befunde"][:4])
    assert not urteil["bestanden"]


@pytest.mark.parametrize("art", EREIGNIS_VALUES)
def test_die_probe_laesst_am_zugangstag_nur_die_zugangsbuchungen_zu(welt, art):
    """Die Grenze der Probe ist scharf; die Erwartung steht von Hand hier.
    Mutationsprobe: die Zugangstag-Regel aufweichen -> alle nicht erlaubten
    Arten rot."""
    urteil = _urteil(welt, _mit_zeile(welt, art, ZUGANG))
    texte = [t for t in _fenster_texte(urteil) if t.startswith(f"{art}-Buchung")]
    assert bool(texte) == (art not in AM_ZUGANGSTAG_ERLAUBT), (art, texte)


@pytest.mark.parametrize("art", EREIGNIS_VALUES)
def test_die_probe_weist_jede_art_hinter_dem_horizont_ab_und_zaehlt_sie_nicht(welt, art):
    """Zaehltest je Art (auch der Zugang an einem anderen Tag als dem
    Zugangstag). Eine Buchung hinter dem Horizont ist keine Buchung dieses
    Laufs: Sie wird weder nachgerechnet noch als geprueft gezaehlt.
    Mutationsprobe: die Obergrenze fuer genau diese Art ausnehmen -> rot."""
    grund = _urteil(welt, welt["tab"])["buchungen_geprueft"]
    urteil = _urteil(welt, _mit_zeile(welt, art, DAHINTER))
    texte = _fenster_texte(urteil)
    assert any(t.startswith(f"{art}-Buchung nach dem belegten Horizont 2027-01-01")
               for t in texte), (art, urteil["befunde"][:4])
    assert urteil["buchungen_geprueft"] == grund


# --------------------------------------------------------------------------- #
# Zaehltest Bindung an die Rate je KLV-Feld
# --------------------------------------------------------------------------- #


def _mit_raten(welt, nullfeld: str | None):
    """Alle KLV-Annahmen auf eine kleine positive Rate, ``nullfeld`` auf null —
    Config des Laufs plus genau diese eine Aenderung."""
    config = copy.deepcopy(welt["config"])
    for feld in KLV_FELDER:
        setattr(config.annahmen, feld, KLEIN)
    if nullfeld is not None:
        setattr(config.annahmen, nullfeld, NULL)
    return dict(welt["basis"], config=config)


def _tab_mit_ereignis(welt, feld: str):
    art = ANNAHME_ERZEUGT[feld][1]
    if art == "TKU":
        # Teilkuendigung mit Tabelle (die Generation des Falls fuehrt das
        # Verfahren teilkuendigung, ADR-023).
        return _mit_red(welt, POL, ZUGANGSJAHR + 1)
    return _mit_zeile(welt, art, HORIZONT)


def _ratebefunde(urteil):
    return [b for b in urteil["befunde"] if b["art"] == "ratebindung"]


@pytest.mark.parametrize("feld", KLV_FELDER)
def test_die_probe_meldet_jede_buchung_ohne_rate_genau_fuer_ihr_feld(welt, feld):
    """Zaehltest je Feld: Mit kleinen positiven Raten ist die Probe ohne
    Ratebefund (Positivkontrolle); das Nullsetzen genau von ``feld`` bringt
    genau einen Ratebefund, und der nennt ``feld``.
    Mutationsprobe: ``annahme_erzeugt_nicht`` fuer genau dieses Feld
    verneinen -> genau dieser Fall rot."""
    tab = _tab_mit_ereignis(welt, feld)
    gut = pruefe_fuehrung(uebernahme=welt["ueb"], fortschreibung=tab, **_mit_raten(welt, None))
    assert _ratebefunde(gut) == [], gut["befunde"][:4]
    schlecht = pruefe_fuehrung(uebernahme=welt["ueb"], fortschreibung=tab, **_mit_raten(welt, feld))
    befunde = _ratebefunde(schlecht)
    if feld == "teilkuendigung":
        # Annahme A1 (ADR-023): Die Generation dieses Falls (TG2015,
        # red_verfahren = teilkuendigung) fuehrt den Herabsetzungswunsch vor
        # dem Beitragsende als Teilkuendigung aus — die TKU im Jahr 12 belegt
        # hier auch die Rate ``herabsetzung``. Ohne beide Raten ist sie
        # unbelegt (zweite Probe); den Fall ohne A1 zaehlt
        # tests/test_klasse_ereignis_rate_e.py an einer prospektiven Generation.
        assert befunde == [], schlecht["befunde"][:4]
        cfg = copy.deepcopy(_mit_raten(welt, feld)["config"])
        cfg.annahmen.herabsetzung = NULL
        schlecht = pruefe_fuehrung(uebernahme=welt["ueb"], fortschreibung=tab,
                                   **dict(welt["basis"], config=cfg))
        befunde = [b for b in _ratebefunde(schlecht) if b["feld"] == feld]
    assert [b["feld"] for b in befunde] == [feld], schlecht["befunde"][:4]
    assert f"annahmen.{feld}:" in befunde[0]["text"]
    assert not schlecht["bestanden"]


def test_die_probe_laesst_die_zugangsbuchungen_ohne_rate_in_ruhe(welt):
    """Die Ausnahmen der Menge, an der Probe gemessen: Mit ALLEN KLV-Annahmen
    auf null bleibt die Welt (ZUG, PEX-Umbuchung am Zugangstag, ABL) ohne
    Ratebefund."""
    config = copy.deepcopy(welt["config"])
    for feld in KLV_FELDER:
        setattr(config.annahmen, feld, NULL)
    urteil = pruefe_fuehrung(uebernahme=welt["ueb"], fortschreibung=welt["tab"],
                             **dict(welt["basis"], config=config))
    assert _ratebefunde(urteil) == []


def test_die_probe_meldet_ein_paar_ohne_zuordnung_genau_einmal(welt):
    """Nachbesserung Runde E: Eine INV-Buchung an einer KLV-Police (INV ist
    nur das Ziel der BU-Invalidisierung) ist weder Ziel einer KLV-Annahme
    noch Ausnahme — genau ein Befund der Art 'zuordnung', auch mit vollen
    Raten. Positivkontrolle: die Welt und eine Buchung eines KLV-Ziels (STO)
    bringen keinen. Mutationsprobe: den Aufruf von unzugeordnete_ereignisse
    in pruefe_fuehrung entfernen -> rot."""
    def zuordnung(urteil):
        return [b for b in urteil["befunde"] if b["art"] == "zuordnung"]

    assert zuordnung(_urteil(welt, welt["tab"])) == []
    assert zuordnung(_urteil(welt, _mit_zeile(welt, "STO", HORIZONT))) == []
    urteil = _urteil(welt, _mit_zeile(welt, "INV", HORIZONT))
    befunde = zuordnung(urteil)
    assert len(befunde) == 1, urteil["befunde"][:4]
    assert "Ereignis INV fuer Produkt klv ist keiner Annahme und keiner Ausnahme zugeordnet" \
        in befunde[0]["text"]
    assert not urteil["bestanden"]


# --------------------------------------------------------------------------- #
# Nachbesserung: ZUG, MIG und ABL stehen an ihrem Zeitpunkt
# --------------------------------------------------------------------------- #


def _ausnahme_befunde(urteil, art):
    return [b["text"] for b in urteil["befunde"]
            if b["art"] == "ausnahme_ereignis" and b["text"].startswith(f"{art}-Buchung")]


def _ausnahme_tab(welt, art: str, fall: str):
    """Die Fortschreibung der Welt mit einer Zeile der Art am richtigen oder
    falschen Platz. ZUG: der Zugang der Welt selbst, verschoben oder
    verdoppelt; MIG: das Residuum am Zugangstag (gruen) bzw. am Horizont;
    ABL: am Horizont, weit vor dem Vertragsende (der Stamm der Welt laeuft
    ueber den Horizont hinaus, ein Ablauf am richtigen Platz ist dort nicht
    gebucht — sein gruener Fall steht in ``test_klasse_buchungsfenster_e``)."""
    tab = dict(welt["tab"])
    led = tab["ledger"]
    if art == "ZUG":
        i = led.index[(led["police_id"] == POL) & (led["ereignis"] == "ZUG")][0]
        if fall == "verschoben":
            led = led.copy()
            led.loc[i, "status_date"] = led.loc[i, "status_date"] + pd.DateOffset(months=1)
        elif fall == "verdoppelt":
            led = pd.concat([led, led.loc[[i]]], ignore_index=True)
        tab["ledger"] = led
        return tab
    datum = {"gruen": ZUGANG, "verschoben": HORIZONT}[fall]
    return _mit_zeile(welt, art, datum, tab)


@pytest.mark.parametrize("art,fall", [
    ("ZUG", "verschoben"), ("ZUG", "verdoppelt"),
    ("MIG", "verschoben"), ("ABL", "verschoben"),
])
def test_die_probe_weist_ein_ausnahme_ereignis_am_falschen_platz_ab(welt, art, fall):
    """Zaehltest je Art und Fall, an der Probe des Baldrian-Laufs: die
    unveraenderte Welt hat keinen Befund (Positivkontrolle, ZUG und PEX am
    Zugangstag); eine verschobene oder verdoppelte Zeile ergibt GENAU EINEN
    Befund dieser Art und zaehlt nicht als nachgerechnet (kein Zuwachs bei
    ``buchungen_geprueft``). MIG am Zugangstag eines uebernommenen Vertrags
    ist gruen, ein Jahr spaeter nicht.
    Mutationsprobe: den Aufruf von ausnahme_ereignis_verstoesse in
    pruefe_fuehrung entfernen -> alle vier rot; die Einmal-Regel leeren ->
    ZUG/verdoppelt rot."""
    grund = _urteil(welt, welt["tab"])
    assert _ausnahme_befunde(grund, art) == [], grund["befunde"][:3]
    if art == "MIG":          # am Zugangstag eines uebernommenen Vertrags: gruen
        assert _ausnahme_befunde(_urteil(welt, _ausnahme_tab(welt, art, "gruen")), art) == []
    urteil = _urteil(welt, _ausnahme_tab(welt, art, fall))
    befunde = _ausnahme_befunde(urteil, art)
    assert len(befunde) == 1, (art, fall, urteil["befunde"][:4])
    assert not urteil["bestanden"]
    assert urteil["buchungen_geprueft"] == grund["buchungen_geprueft"]


def test_ratsche_die_probe_testet_jede_ausnahme_art():
    """Die Faelle oben decken jede Ausnahme-Art ab (``==``): ein neues
    Ausnahme-Ereignis ohne Probenfall ist rot."""
    assert {"ZUG", "MIG", "ABL"} == set(EREIGNIS_OHNE_ANNAHME)
