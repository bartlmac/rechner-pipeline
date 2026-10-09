"""Pruefrunde I, Bestand und Bewertung — vier Funde, vier Invarianten.

**I10 — das Jahr des Vorgangs, nicht das der Uebernahmebuchung.** Die
Jahresgrenze der Beitragsfreistellung (Pruefrunde H) las auf dem Ledger-Weg
das ``vertragsjahr`` der PEX-Zeile. Die Uebernahme (``gates.bestand_uebernehmen``)
bucht einen beitragsfrei uebernommenen Vertrag aber zum ZUGANGSDATUM um, mit
dem Vertragsjahr des Zugangs. Jeder beitragsfrei uebernommene Vertrag mit
Zugangsjahr >= t fiel deshalb durch P-B1, den Abschluss und die
Registrierung — obwohl seine Freistellung vor dem Beitragsende lag.
Invariante: Geprueft wird das Jahr des VORGANGS, nie das Jahr einer Buchung,
die einen bestehenden Zustand in die Fuehrung des Zielsystems uebernimmt.
Merkmal: ``models.bestand.zugangsbuchungen`` (Zugangstag, Art aus
``ZUGANGSTAG_EREIGNISSE``, PEX nur beim uebernommenen Vertrag) — dasselbe, mit
dem das Buchungsfenster die Zugangsbuchungen zulaesst.

**I11 — ein leerer Ledger traegt nicht mehr Buchungen als ein fehlender.**
**I12 — jede Erhoehungsscheibe geht durch die Jahresgrenze des Kerns.**
**I13 — die Fortschreibung haelt ihren Uebernahme-Eingang gegen die Regel.**
(Die Abschnitte unten beschreiben je Fund Invariante, Menge und Ratsche.)

Knoten: klv, system/bestand
"""

from __future__ import annotations

import ast
import datetime as _dt
from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd
import pytest

from rechner_pipeline.bestand import cli_abschluss, cli_fortschreibung
from rechner_pipeline.bestand.config import load_config
from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
from rechner_pipeline.gates import bestand_validate
from rechner_pipeline.gates.bestand_uebernehmen import baue

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src" / "rechner_pipeline"
CONFIG = REPO_ROOT / "plv" / "configs" / "bestand_klv.toml"

#: Die Meldung der EINEN Stelle (kern.beitragsreduktion.pruefe_vorgangsjahr).
PEX_TEXT = "Beitragsfreistellung nach dem Beitragsende"
ERH_TEXT = "Erhoehung nach dem Beitragsende"
JAHR0_TEXT = "fruehestens am ersten Jahrestag"


# --------------------------------------------------------------------------- #
# I10 — Uebernahmebuchung gegen Vorgang
# --------------------------------------------------------------------------- #

BEGINN = _dt.date(2006, 1, 1)
LAUFZEIT = 25
POLICE = 7000001
GELIEFERT_BFR = 20000.0


def _felder() -> Dict:
    gen = {g.name: g for g in load_config(CONFIG).generationen}["KLV-2015"]
    return gen.generation_fields()


def _uebernahme(ziel: Path, t: int, pex_jahr: int, zugang_jahr: int) -> Tuple[Path, _dt.date]:
    """Ein beitragsfrei uebernommener Vertrag, gebaut vom ECHTEN Produzenten
    (``gates.bestand_uebernehmen.baue``, die Funktion hinter dem Kommando):
    Beginn 2006-01-01, n = 25, Beitragsdauer ``t``, Freistellung der Quelle im
    Vertragsjahr ``pex_jahr``, Migrationsstichtag im Vertragsjahr
    ``zugang_jahr``; geliefert ist die beitragsfreie Summe 20.000."""
    stichtag = _dt.date(BEGINN.year + zugang_jahr, 1, 1)
    zeile = {"police_id": POLICE, "beginn": BEGINN.isoformat(), "entry_age": 40,
             "duration": LAUFZEIT, "premium_duration": t, "sex": "M",
             "sum_insured": GELIEFERT_BFR, "zahlweise": 12}
    stamm, historie, ledger, _hinweise = baue(
        [zeile], tarif_generation="KLV-2015", produkt="klv", stichtag=stichtag,
        vorgeschichte={str(POLICE): [("PEX", _dt.date(BEGINN.year + pex_jahr, 1, 1))]},
        generationsfelder=_felder())
    ziel.mkdir(parents=True)
    for name, tab in (("bestand", stamm), ("historie", historie), ("ledger", ledger)):
        write_portfolio(tab, ziel / f"{name}.parquet")
    return ziel, stichtag


def _pb1(d: Path, stichtag: _dt.date, tmp: Path):
    return bestand_validate.main([
        "--portfolio", str(d / "bestand.parquet"), "--historie", str(d / "historie.parquet"),
        "--ledger", str(d / "ledger.parquet"), "--bis", stichtag.isoformat(),
        "--config", str(CONFIG), "--diagnostics-dir", str(tmp / "diag")])


#: (t, Freistellungsjahr, Zugangsjahr): Zugang vor, am und nach dem
#: Beitragsende; Freistellung frueh (Jahr 1) und im letzten zulaessigen Jahr
#: (t-1); kurze, mittlere und lange Beitragsdauer.
MATRIX = [
    (5, 1, 3), (5, 1, 5), (5, 4, 5), (5, 1, 10), (5, 4, 10), (5, 4, 24),
    (12, 1, 10), (12, 11, 12), (12, 1, 12), (12, 11, 15), (12, 1, 15),
    (20, 1, 2), (20, 19, 20), (20, 19, 24),
]


@pytest.mark.parametrize("t, pex_jahr, zugang_jahr", MATRIX)
def test_i10_beitragsfrei_uebernommen_besteht_p1_abschluss_und_registrierung(
        tmp_path, t, pex_jahr, zugang_jahr):
    """Auf 9fa1538 rot fuer jedes Zugangsjahr >= t: P-B1 Exit 20 mit
    'vorgangsjahr ledger: ... PEX — Vertragsjahr <Zugangsjahr>'. Soll: Die
    Lieferung ist zulaessig (Freistellung in 0 < a < t), also bestehen P-B1
    (oeffentlicher Weg, mit Config), die Registrierungsvorbedingung des
    Betriebs und der Abschluss nach der Fortschreibung; der Abschluss fuehrt
    den Vertrag beitragsfrei mit der GELIEFERTEN beitragsfreien Summe (die
    Lieferung ist die Sollquelle, nicht der Kern)."""
    from rechner_pipeline.betrieb.uebernahme import _eingang_pb1_fehler

    d, stichtag = _uebernahme(tmp_path / "uebernahme", t, pex_jahr, zugang_jahr)
    ledger = read_portfolio(d / "ledger.parquet")
    umbuchung = ledger[ledger["ereignis"] == "PEX"]
    # Die Welt ist die gemeinte: die Umbuchung traegt das Zugangsjahr.
    assert umbuchung["vertragsjahr"].tolist() == [zugang_jahr]

    ergebnis = _pb1(d, stichtag, tmp_path)
    assert ergebnis.exit_code == 0, [e["message"] for e in ergebnis.errors][:3]
    assert _eingang_pb1_fehler(d, stichtag, CONFIG) == []

    lauf = tmp_path / "lauf"
    assert cli_fortschreibung.main([
        "--config", str(CONFIG), "--bis", stichtag.isoformat(),
        "--uebernahme", str(d), "--out-dir", str(lauf)]) == 0
    out = tmp_path / "abschluss"
    assert cli_abschluss.main([
        "--config", str(CONFIG), "--lauf", str(lauf), "--stichtag", stichtag.isoformat(),
        "--bis", stichtag.isoformat(), "--out-dir", str(out)]) == 0
    zeile = read_portfolio(out / f"abschluss_{stichtag.isoformat()}.parquet").iloc[0]
    assert zeile["status_code"] == "PEX"
    assert float(zeile["vs_bfr"]) == pytest.approx(GELIEFERT_BFR, abs=0.005)


@pytest.mark.parametrize("t, zugang_jahr, falsches_jahr", [(5, 10, 5), (5, 10, 7), (12, 15, 12)])
def test_i10_positivkontrolle_eine_wirklich_unzulaessige_freistellung_wird_verweigert(
        tmp_path, t, zugang_jahr, falsches_jahr):
    """Dieselbe Welt, die Freistellung der Historie (und der Stamm) auf ein
    Jahr >= t gesetzt: P-B1 meldet sie auf dem Historie-Weg mit dem Text des
    Kerns, die Registrierung verweigert — die Regel trifft den Vorgang, nicht
    die Umbuchung."""
    from rechner_pipeline.betrieb.uebernahme import _eingang_pb1_fehler

    d, stichtag = _uebernahme(tmp_path / "uebernahme", t, 1, zugang_jahr)
    datum = pd.Timestamp(_dt.date(BEGINN.year + falsches_jahr, 1, 1))
    historie = read_portfolio(d / "historie.parquet")
    historie["status_date"] = datum
    stamm = read_portfolio(d / "bestand.parquet")
    stamm["status_date"] = datum
    write_portfolio(historie, d / "historie.parquet")
    write_portfolio(stamm, d / "bestand.parquet")

    meldungen = [e["message"] for e in _pb1(d, stichtag, tmp_path).errors]
    assert any(m.startswith(f"vorgangsjahr historie: police {POLICE}") and PEX_TEXT in m
               for m in meldungen), meldungen[:3]
    # Die Umbuchung selbst bleibt keine Meldung des Ledger-Wegs.
    assert not any(m.startswith("vorgangsjahr ledger") for m in meldungen), meldungen[:3]
    assert any(PEX_TEXT in m for m in _eingang_pb1_fehler(d, stichtag, CONFIG))


def _stamm_uebernommen(t: int = 5, zugang_jahr: int = 10) -> pd.DataFrame:
    from tests.test_bestand_uebernommen_fortschreiben import _stamm

    return _stamm([{"id": 1, "beginn": "2000-01-01", "n": 25, "t": t,
                    "zugang": f"{2000 + zugang_jahr}-01-01"}])


def _ledger_zeile(art: str, datum: str, jahr: int) -> pd.DataFrame:
    return pd.DataFrame([{"police_id": 1, "ereignis": art, "vertragsjahr": jahr,
                          "status_date": pd.Timestamp(datum)}])


def test_i10_auf_dem_ledger_weg_bleibt_jeder_vorgang_geprueft():
    """Nur die Buchung AM Zugangstag eines uebernommenen Vertrags ist eine
    Uebernahmebuchung. Eine PEX-Zeile ein Jahr nach dem Zugang (ein Vorgang
    der Fortschreibung) mit Jahr >= t meldet der Ledger-Weg weiter; dieselbe
    Zeile am Zugangstag eines EIGENEN Vertrags (kein Zugang nach Beginn) ist
    keine Umbuchung und wird ebenfalls gemeldet."""
    from rechner_pipeline.bestand.vorbedingungen import vorgangsjahr_fehler
    from tests.test_bestand_uebernommen_fortschreiben import _stamm

    stamm = _stamm_uebernommen()
    assert vorgangsjahr_fehler(stamm, ledger=_ledger_zeile("PEX", "2010-01-01", 10)) == []
    nachher = vorgangsjahr_fehler(stamm, ledger=_ledger_zeile("PEX", "2011-01-01", 11))
    assert any(f.startswith("vorgangsjahr ledger: police 1") and PEX_TEXT in f for f in nachher)
    eigen = _stamm([{"id": 1, "beginn": "2000-01-01", "n": 25, "t": 5}])
    am_beginn = vorgangsjahr_fehler(eigen, ledger=_ledger_zeile("PEX", "2000-01-01", 0))
    assert any(JAHR0_TEXT in f for f in am_beginn), am_beginn


def test_i10_ratsche_eine_definition_der_zugangsbuchung():
    """Ratsche (statisch, als solche benannt, ``==``): Das Buchungsfenster und
    die Jahresgrenze der Vorgaenge lesen die Zugangsbuchung aus DERSELBEN
    Funktion; und die Vorgangsarten, die am Zugangstag als Uebernahmebuchung
    stehen duerfen, sind genau {PEX}. Kommt eine Art hinzu (etwa eine
    mitgebrachte Herabsetzung als Umbuchung), muss hier entschieden werden,
    wo ihr Vorgangsjahr steht."""
    from rechner_pipeline.bestand.vorbedingungen import VORGANGSJAHR_WEGE
    from rechner_pipeline.models.bestand import ZUGANGSTAG_EREIGNISSE

    assert set(ZUGANGSTAG_EREIGNISSE) & set(VORGANGSJAHR_WEGE) == {"PEX"}

    def ruft(pfad: Path, funktion: str) -> set:
        baum = ast.parse(pfad.read_text("utf-8"))
        f = next(x for x in ast.walk(baum) if isinstance(x, ast.FunctionDef) and x.name == funktion)
        return {getattr(c.func, "id", getattr(c.func, "attr", None))
                for c in ast.walk(f) if isinstance(c, ast.Call)}

    assert "zugangsbuchungen" in ruft(SRC / "models" / "bestand.py", "buchungsfenster_verstoesse")
    assert "zugangsbuchungen" in ruft(SRC / "bestand" / "vorbedingungen.py", "vorgangsjahr_fehler")


# --------------------------------------------------------------------------- #
# I11 — ein leerer Ledger traegt nicht mehr Buchungen als ein fehlender
# --------------------------------------------------------------------------- #
#
# Invariante: Die Bindung der Reduktionstabelle an Tarifwerk und Annahmen
# haengt an der TABELLE, nicht am Ledger, und die Vollstaendigkeit "jeder
# registrierte Vorgang hat seine Buchungen" gilt fuer JEDEN vorhandenen
# Ledger, auch den leeren. Auf 9fa1538 kehrte ``pruefe_ledger_betraege`` bei
# null Zeilen sofort zurueck; die Wache "ohne Ledger" griff nur bei
# ``ledger is None``. Ein leerer Ledger mit verstuemmelter Tabelle ging gruen
# durch P-B1, und der Abschluss wurde festgeschrieben.

HORIZONT_I11 = _dt.date(2020, 1, 1)
STICHTAG_I11 = _dt.date(2019, 11, 1)
VERFAHREN_TEXT = "das Tarifwerk der Generation sagt 'prospektiv'"
ANTEIL_TEXT = "die Annahmen sagen"
FEHLEN_TEXT = "Buchung(en) registrierter Herabsetzungen fehlen"


@pytest.fixture(scope="module")
def lauf_i11(tmp_path_factory) -> Path:
    """Ein echter Lauf der Fortschreibung (oeffentlicher Weg)."""
    ziel = tmp_path_factory.mktemp("lauf_i11")
    assert cli_fortschreibung.main([
        "--config", str(CONFIG), "--neuzugang-ab", "1994-07-01",
        "--bis", HORIZONT_I11.isoformat(), "--out-dir", str(ziel)]) == 0
    return ziel


def _welt_i11(lauf: Path, ziel: Path, *, ledger: str, verstuemmelt: bool) -> Tuple[Path, int]:
    """Der Lauf eingeschraenkt auf beitragspflichtige Vertraege ohne
    Statuswechsel und ohne Scheiben, die eine prospektive Herabsetzung
    registriert haben; ihre Reduktionstabelle, eine Zeile auf Verfahren
    ``mit_abzug`` und Anteil 0,5 gesetzt (die Config sagt prospektiv und
    red_anteil 0,6). ``ledger``: ``leer`` (Schema, null Zeilen), ``zugang``
    (nur die Zugangsbuchungen der Vertraege), ``ohne_vorgang`` (alle Buchungen
    ausser denen der Vorgaenge EINER Police), ``voll`` (alle ihre Buchungen),
    ``fehlt`` (keine Datei). Manifest nachgefuehrt."""
    from rechner_pipeline.bestand.manifest import schreibe_manifest

    stamm = read_portfolio(lauf / "bestand_gesamt.parquet")
    hist = read_portfolio(lauf / "historie.parquet")
    sch = read_portfolio(lauf / "scheiben.parquet")
    red = read_portfolio(lauf / "reduktionen.parquet")
    led = read_portfolio(lauf / "ledger.parquet")
    pol = stamm[(stamm["status_id"] == 1) & ~stamm["police_id"].isin(hist["police_id"])
                & ~stamm["police_id"].isin(sch["police_id"])
                & stamm["police_id"].isin(red.loc[red["verfahren"] == "prospektiv", "police_id"])]
    assert len(pol) >= 1, "die Welt traegt keinen herabgesetzten Vertrag ohne Statuswechsel"
    ids = set(int(p) for p in pol["police_id"])
    r = red[red["police_id"].isin(ids)].reset_index(drop=True).copy()
    ziel_pid = int(r.loc[r["verfahren"] == "prospektiv", "police_id"].iloc[0])
    if verstuemmelt:
        m = (r["police_id"] == ziel_pid) & (r["verfahren"] == "prospektiv")
        r.loc[m, "verfahren"] = "mit_abzug"
        r.loc[m, "anteil"] = 0.5
    eigene = led[led["police_id"].isin(ids)].reset_index(drop=True)
    tabellen = {"bestand_gesamt": pol.reset_index(drop=True), "historie": hist.iloc[0:0].copy(),
                "scheiben": sch.iloc[0:0].copy(), "reduktionen": r}
    if ledger == "leer":
        tabellen["ledger"] = led.iloc[0:0].copy()
    elif ledger == "zugang":
        tabellen["ledger"] = eigene[eigene["ereignis"] == "ZUG"].reset_index(drop=True)
    elif ledger == "ohne_vorgang":
        weg = (eigene["police_id"] == ziel_pid) & eigene["ereignis"].isin(("RED", "TKU"))
        assert weg.any()
        tabellen["ledger"] = eigene[~weg].reset_index(drop=True)
    elif ledger == "voll":
        tabellen["ledger"] = eigene
    elif ledger == "formfehler":
        # Eine Zeile mit negativem Betrag: validate_ledger beanstandet die
        # Form, die Herleitung laeuft nicht — die Bindung der Tabelle muss
        # trotzdem laufen.
        kaputt = eigene.copy()
        kaputt.loc[kaputt.index[0], "betrag"] = -1.0
        tabellen["ledger"] = kaputt
    else:
        assert ledger == "fehlt"
    ziel.mkdir(parents=True)
    for name, df in tabellen.items():
        write_portfolio(df, ziel / f"{name}.parquet")
    schreibe_manifest(ziel, horizont=HORIZONT_I11, neuzugang_ab=None, config_pfad=CONFIG,
                      ausgaben=sorted(ziel.glob("*.parquet")))
    return ziel, ziel_pid


def _pb1_i11(d: Path):
    from rechner_pipeline.bestand.manifest import lies_manifest_bytes, manifest_aus_bytes
    from rechner_pipeline.bestand.vorbedingungen import lies_und_pruefe_pb1

    eingaben = {"portfolio": d / "bestand_gesamt.parquet", "historie": d / "historie.parquet",
                "scheiben": d / "scheiben.parquet", "reduktionen": d / "reduktionen.parquet",
                "config": CONFIG}
    if (d / "ledger.parquet").is_file():
        eingaben["ledger"] = d / "ledger.parquet"
    manifest = manifest_aus_bytes(lies_manifest_bytes(d / "laufmanifest.json"))
    _t, geprueft, fehler, usage = lies_und_pruefe_pb1(eingaben, bis=HORIZONT_I11, manifest=manifest)
    return geprueft, [f["message"] for f in fehler], usage


@pytest.mark.parametrize("ledger", ["leer", "zugang", "ohne_vorgang", "voll", "fehlt",
                                    "formfehler"])
def test_i11_die_bindung_der_tabelle_haengt_nicht_am_ledger(lauf_i11, tmp_path, ledger):
    """Auf 9fa1538 rot fuer ``leer`` (gruen, keine Meldung) und ``formfehler``
    (nur der Formfehler, die Tabelle ungeprueft). Soll: auf JEDEM
    Ledger-Zustand dieselben beiden Befunde der Tabelle (Verfahren gegen das
    Tarifwerk, Anteil gegen die Annahmen)."""
    d, _pid = _welt_i11(lauf_i11, tmp_path / "w", ledger=ledger, verstuemmelt=True)
    _g, meldungen, usage = _pb1_i11(d)
    assert not usage, usage
    assert any(VERFAHREN_TEXT in m for m in meldungen), meldungen[:3]
    assert any(ANTEIL_TEXT in m and "0.5" in m for m in meldungen), meldungen[:3]


@pytest.mark.parametrize("ledger, fehlen", [("leer", True), ("zugang", True),
                                            ("ohne_vorgang", True), ("voll", False)])
def test_i11_jeder_vorhandene_ledger_traegt_die_buchungen_jedes_vorgangs(
        lauf_i11, tmp_path, ledger, fehlen):
    """Unverstuemmelte Tabelle: Ein vorhandener Ledger ohne die Buchungen der
    registrierten Vorgaenge ist unvollstaendig — auch der leere (auf 9fa1538
    rot: gruen). Positivkontrolle: der volle Ledger der Vertraege besteht."""
    d, _pid = _welt_i11(lauf_i11, tmp_path / "w", ledger=ledger, verstuemmelt=False)
    geprueft, meldungen, usage = _pb1_i11(d)
    assert not usage, usage
    if fehlen:
        assert any(FEHLEN_TEXT in m for m in meldungen), meldungen[:3]
    else:
        assert meldungen == [], meldungen[:3]
    # Wo die Herleitung lief, gibt es nichts "ungeprueft" auszuweisen.
    assert "reduktionen_buchungen_ungeprueft" not in geprueft


def test_i11_oeffentlicher_weg_p1_und_abschluss_mit_leerem_ledger(lauf_i11, tmp_path):
    """P-B1 ueber die CLI: Exit 20 mit Verfahren, Anteil und fehlenden
    Buchungen; der Abschluss schreibt nichts fest (auf 9fa1538: Exit 0 und
    ein 0444-Abschluss mit der verstuemmelten Regel)."""
    d, _pid = _welt_i11(lauf_i11, tmp_path / "w", ledger="leer", verstuemmelt=True)
    ergebnis = bestand_validate.main([
        "--portfolio", str(d / "bestand_gesamt.parquet"), "--historie", str(d / "historie.parquet"),
        "--scheiben", str(d / "scheiben.parquet"), "--reduktionen", str(d / "reduktionen.parquet"),
        "--ledger", str(d / "ledger.parquet"), "--bis", HORIZONT_I11.isoformat(),
        "--config", str(CONFIG), "--manifest", str(d / "laufmanifest.json"),
        "--diagnostics-dir", str(tmp_path / "diag")])
    meldungen = [e["message"] for e in ergebnis.errors]
    assert ergebnis.exit_code == 20, meldungen[:3]
    for text in (VERFAHREN_TEXT, ANTEIL_TEXT, FEHLEN_TEXT):
        assert any(text in m for m in meldungen), (text, meldungen[:3])
    out = tmp_path / "abs"
    assert cli_abschluss.main([
        "--config", str(CONFIG), "--lauf", str(d), "--stichtag", STICHTAG_I11.isoformat(),
        "--bis", HORIZONT_I11.isoformat(), "--out-dir", str(out)]) != 0
    assert not list(out.glob("abschluss_*.parquet"))


def test_i11_ratsche_keine_herleitung_endet_vor_bindung_und_vollstaendigkeit():
    """Ratsche (statisch, als solche benannt): ``pruefe_ledger_betraege``
    kehrt vor dem Aufruf der Bindung nirgends zurueck (ausser im Fehlerfall
    der Schichten, der selbst ein Befund ist), und die Engine bindet die
    Tabelle, wann immer die Herleitung nicht lief — nicht nur bei
    ``ledger is None``."""
    baum = ast.parse((SRC / "bestand" / "ledger_bindung.py").read_text("utf-8"))
    f = next(x for x in ast.walk(baum)
             if isinstance(x, ast.FunctionDef) and x.name == "pruefe_ledger_betraege")
    bindung = next(c.lineno for c in ast.walk(f) if isinstance(c, ast.Call)
                   and getattr(c.func, "id", None) == "pruefe_reduktionen_tarifwerk")
    fruehe = [ast.unparse(r) for r in ast.walk(f)
              if isinstance(r, ast.Return) and r.lineno < bindung]
    assert fruehe == ["return [f'schichten: {exc}']"], fruehe
    quelle = (SRC / "bestand" / "vorbedingungen.py").read_text("utf-8")
    assert "if not hergeleitet and reduktionen is not None" in quelle
    assert "if ledger is None and reduktionen is not None" not in quelle


# --------------------------------------------------------------------------- #
# I12 — jede Erhoehungsscheibe geht durch die Jahresgrenze des Kerns
# --------------------------------------------------------------------------- #
#
# Invariante (Tarifplan KLV 7.3: eine Wache an einem von zwei Eingaengen ist
# keine): JEDER Eingang des Kerns, der Erhoehungsscheiben entgegennimmt, geht
# durch die eine Regel (``beitragsreduktion.pruefe_vorgangsjahr``, gerufen
# ueber ``rechenkern.pruefe_scheibenjahre``). Auf 9fa1538 pruefte sie nur
# ``Vertragsstand.nach_erhoehung``; ``vertrags_monatsreserve`` (Bewertung und
# Fuehrungswert eines beitragspflichtigen Vertrags ohne weiteren Vorgang)
# rechnete eine Scheibe im Vertragsjahr 0 still. Gemessen: Die Scheibentabelle
# (``validate_scheiben``) laesst nur 0 < j < t mit t' = t - j zu, und jeder
# echte Produzent (Engine, Uebernahme) baut seine Scheiben ueber
# ``erhoehungs_scheibe``; das Jahr t entsteht nur mit inkonsistenter Restdauer.

def _grund_und_scheibe(jahr: int):
    """Grundversicherung KLV_DEFAULT-artig (n = 25, t = 20) und eine Scheibe im
    Vertragsjahr ``jahr``, direkt gebaut (nicht ueber ``erhoehungs_scheibe``,
    die selbst verweigert) — wie eine Zeile der Scheibentabelle."""
    import dataclasses

    from rechner_pipeline.kern import KLV_DEFAULT, Rechenkern

    grund_mp = dataclasses.replace(KLV_DEFAULT, x=40, n=25, t=20, sum_insured=100_000.0)
    scheibe_mp = dataclasses.replace(grund_mp, x=40 + jahr, n=25 - jahr, t=max(20 - jahr, 1),
                                     sum_insured=5_000.0, gamma1=0.0)
    return Rechenkern(grund_mp), Rechenkern(scheibe_mp)


def _eingaenge():
    """Je Kern-Eingang (und je Eingang der Bestandsschicht, der eine Scheibe
    in den Kern bringt) ein Aufruf mit einer Scheibe im Jahr ``jahr``."""
    from rechner_pipeline.bestand.kernlauf import vertrags_rkw
    from rechner_pipeline.kern import Vertragsstand, Vorgangsfolge, vertrags_monatsreserve
    from rechner_pipeline.kern.beitragsreduktion import (
        TEILKUENDIGUNG,
        nachher_zugekommen,
        reduziere_geschichtet,
        reduzierte_teile,
        vertrags_monatsreserve_reduziert,
    )
    from rechner_pipeline.kern.rechenkern import erhoehungs_scheibe
    from rechner_pipeline.kern.vorgangsfolge import UMFANG_ALLE

    tw = dict(stoab_je_baustein=False, tku_umfang=UMFANG_ALLE)

    def scheibe(jahr):
        g, k = _grund_und_scheibe(jahr)
        return erhoehungs_scheibe(g.mp, jahr, 5_000.0, gamma1_uebernehmen=False)

    def monatsreserve(jahr):
        g, k = _grund_und_scheibe(jahr)
        return vertrags_monatsreserve(g, [(jahr, k)], 12 * 22, stoab_je_baustein=False)

    def anfang(jahr):
        g, k = _grund_und_scheibe(jahr)
        return Vertragsstand.anfang(g, [(jahr, k)], **tw).werte(12 * 22)

    def nach_erhoehung(jahr):
        g, k = _grund_und_scheibe(jahr)
        return Vertragsstand.anfang(g, [], **tw).nach_erhoehung(jahr, k)

    def folge(jahr):
        g, k = _grund_und_scheibe(jahr)
        return Vorgangsfolge(g, [(jahr, k)], [], **tw).stand_am(12 * 22)

    def geschichtet(jahr):
        g, k = _grund_und_scheibe(jahr)
        return reduziere_geschichtet(g, [(jahr, k)], 22, 0.5, verfahren=TEILKUENDIGUNG,
                                     stoab_je_baustein=False)

    def teile(jahr):
        g, k = _grund_und_scheibe(jahr)
        return reduzierte_teile(g, [(jahr, k)], 22, 0.5, TEILKUENDIGUNG, stoab_je_baustein=False)

    def reduziert(jahr):
        g, k = _grund_und_scheibe(jahr)
        return vertrags_monatsreserve_reduziert(
            [(0, nachher_zugekommen(g)), (jahr, nachher_zugekommen(k))], 12 * 22,
            stoab_je_baustein=False)

    def rkw(jahr):
        g, k = _grund_und_scheibe(jahr)
        return vertrags_rkw(g, [(jahr, k)], 22, stoab_je_baustein=False)

    return {"erhoehungs_scheibe": scheibe, "vertrags_monatsreserve": monatsreserve,
            "Vertragsstand.anfang": anfang, "Vertragsstand.nach_erhoehung": nach_erhoehung,
            "Vorgangsfolge.__init__": folge, "reduziere_geschichtet": geschichtet,
            "reduzierte_teile": teile, "vertrags_monatsreserve_reduziert": reduziert,
            "kernlauf.vertrags_rkw": rkw}


@pytest.mark.parametrize("eingang", sorted(_eingaenge()))
@pytest.mark.parametrize("jahr, text", [(0, JAHR0_TEXT), (20, ERH_TEXT)])
def test_i12_jeder_eingang_verweigert_die_scheibe_ausserhalb_der_grenze(eingang, jahr, text):
    """Auf 9fa1538 rot fuer ``vertrags_monatsreserve``, ``Vertragsstand.anfang``,
    ``reduziere_geschichtet``, ``reduzierte_teile``,
    ``vertrags_monatsreserve_reduziert`` und ``kernlauf.vertrags_rkw``: still
    gerechnet. Soll: die Meldung des Kerns."""
    with pytest.raises(ValueError, match=text):
        _eingaenge()[eingang](jahr)


@pytest.mark.parametrize("eingang", sorted(_eingaenge()))
def test_i12_positivkontrolle_jeder_eingang_rechnet_die_scheibe_im_jahr_1(eingang):
    _eingaenge()[eingang](1)


def _bewertungswelt(jahr: int, pex: Optional[int]):
    from rechner_pipeline.bestand.config import config_aus_text
    from rechner_pipeline.models.bestand import (
        SCHEIBEN_NAMES,
        SCHEIBEN_SPALTEN,
        STATUS_HISTORIE_SPALTEN,
    )
    from tests.test_bestand_uebernommen_fortschreiben import _CONFIG_TOML, _stamm

    stamm = _stamm([{"id": 1, "beginn": "2000-01-01", "n": 25, "t": 20}])
    zeilen = []
    if pex is not None:
        datum = pd.Timestamp(f"{2000 + pex}-01-01")
        stamm["status_id"], stamm["status_code"], stamm["status_date"] = 2, "PEX", datum
        zeilen = [{"police_id": 1, "status_id": 2, "status_code": "PEX", "status_date": datum}]
    historie = pd.DataFrame(zeilen, columns=[n for n, _ in STATUS_HISTORIE_SPALTEN]).astype(
        dict(STATUS_HISTORIE_SPALTEN))
    scheiben = pd.DataFrame([{
        "police_id": 1, "scheiben_id": 1, "erhoehung_jahr": jahr,
        "erhoehung_datum": pd.Timestamp(f"{2000 + jahr}-01-01"), "entry_age": 40 + jahr,
        "duration": 25 - jahr, "premium_duration": max(20 - jahr, 1), "sum_insured": 5000.0,
        "gamma1": 0.0}])[list(SCHEIBEN_NAMES)].astype(dict(SCHEIBEN_SPALTEN))
    return stamm, historie, scheiben, config_aus_text(_CONFIG_TOML)


@pytest.mark.parametrize("pex", [None, 8])
@pytest.mark.parametrize("konvention", ["monatsgenau", "jahreszeile"])
@pytest.mark.parametrize("jahr, text", [(0, JAHR0_TEXT), (20, ERH_TEXT), (1, None)])
def test_i12_bewertung_und_fuehrungswert_in_jeder_konvention(pex, konvention, jahr, text):
    """Der Weg der Bewertung (``einzelwerte_am``) und des Fuehrungswerts der
    A-M4-Nachrechnung (``migrationszugang.fuehrungswerte``) — beitragspflichtig
    ohne weiteren Vorgang und beitragsfrei, in beiden Konventionen. Auf 9fa1538
    rot: Jahr 0 gerechnet (beitragspflichtig in beiden, beitragsfrei in der
    Jahreszeile); Jahr t mit konsistenter Restdauer gerechnet oder
    ZeroDivisionError. Positivkontrolle: Jahr 1 rechnet."""
    from rechner_pipeline.bestand.auswertung import einzelwerte_am
    from rechner_pipeline.bestand.migrationszugang import fuehrungswerte

    stamm, historie, scheiben, config = _bewertungswelt(jahr, pex)
    stichtag = _dt.date(2022, 6, 1)
    if text is None:
        zeile = einzelwerte_am(stamm, historie, config, stichtag, scheiben=scheiben,
                               konvention=konvention)[0]
        assert zeile["deckungskapital"] > 0.0
        return
    with pytest.raises(ValueError, match=text):
        einzelwerte_am(stamm, historie, config, stichtag, scheiben=scheiben,
                       konvention=konvention)
    if konvention == "monatsgenau":
        from tests.test_bestand_uebernommen_fortschreiben import _CONFIG_TOML

        with pytest.raises(ValueError, match=text):
            fuehrungswerte(stamm, historie, _CONFIG_TOML, {"s": stichtag}, scheiben=scheiben)


def test_i12_ratsche_die_menge_der_kern_eingaenge_fuer_scheiben():
    """Ratsche (statisch, ``==``, als solche benannt): Die oeffentlichen
    Funktionen und Methoden des Kerns mit einem Parameter ``scheiben`` oder
    ``teile`` sind genau die bekannten; jede ruft die Regel (``pruefe_scheiben
    jahre`` bzw. in der Folge ``_jahr_der_folge``/``nach_erhoehung``) — bis auf
    den reinen Filter ``bestehende_teile``. Ein neuer Eingang faellt hier auf
    und wird bewusst aufgenommen; die Verhaltensprobe je Eingang steht oben."""
    gefunden = {}
    for pfad in sorted((SRC / "kern").rglob("*.py")):
        baum = ast.parse(pfad.read_text("utf-8"))
        for klasse in [None] + [k for k in baum.body if isinstance(k, ast.ClassDef)]:
            for f in (baum.body if klasse is None else klasse.body):
                if not isinstance(f, ast.FunctionDef) or (f.name.startswith("_") and f.name != "__init__"):
                    continue
                namen = {a.arg for a in f.args.posonlyargs + f.args.args + f.args.kwonlyargs}
                if not {"scheiben", "teile"} & namen:
                    continue
                gerufen = {getattr(c.func, "id", getattr(c.func, "attr", None))
                           for c in ast.walk(f) if isinstance(c, ast.Call)}
                name = f"{pfad.stem}.{(klasse.name + '.') if klasse else ''}{f.name}"
                gefunden[name] = bool(gerufen & {"pruefe_scheibenjahre", "_jahr_der_folge",
                                                 "nach_erhoehung", "pruefe_vorgangsjahr"})
    assert gefunden == {
        "rechenkern.pruefe_scheibenjahre": True,       # die Stelle selbst
        "rechenkern.vertrags_monatsreserve": True,
        "beitragsreduktion.reduziere_geschichtet": True,
        "beitragsreduktion.reduzierte_teile": True,
        "beitragsreduktion.vertrags_monatsreserve_reduziert": True,
        "beitragsreduktion.bestehende_teile": False,     # Filter, rechnet nicht
        "vorgangsfolge.Vertragsstand.anfang": True,
        "vorgangsfolge.Vorgangsfolge.__init__": True,
    }, gefunden
    # Die Regel selbst steht an einer Stelle: pruefe_scheibenjahre ruft den Kern.
    baum = ast.parse((SRC / "kern" / "rechenkern.py").read_text("utf-8"))
    f = next(x for x in ast.walk(baum)
             if isinstance(x, ast.FunctionDef) and x.name == "pruefe_scheibenjahre")
    assert "pruefe_vorgangsjahr" in {getattr(c.func, "id", None) for c in ast.walk(f)
                                     if isinstance(c, ast.Call)}
    f = next(x for x in ast.walk(baum)
             if isinstance(x, ast.FunctionDef) and x.name == "erhoehungs_scheibe")
    vergleiche = [c for c in ast.walk(f) if isinstance(c, ast.Compare)]
    assert vergleiche == [], "erhoehungs_scheibe traegt wieder eine eigene Abschrift der Grenze"


# --------------------------------------------------------------------------- #
# I13 — die Fortschreibung haelt ihren Uebernahme-Eingang gegen die Regel
# --------------------------------------------------------------------------- #
#
# Invariante: Kein Produzent schreibt einen Lauf, den die Bestandswache auf
# denselben Bytes verweigert. Die Fortschreibung mit --uebernahme nahm eine
# Beitragsfreistellung im Vertragsjahr >= t an (Exit 0, Lauf und Manifest);
# P-B1 verweigerte dieselben Bytes. Der Uebernahme-Eingang geht jetzt vor dem
# Lauf durch dieselbe Regel (``vorgangsjahr_fehler``), mit dem Stamm-Zustand,
# aus dem die Engine das Freistellungsjahr liest.


def _setze_pex_jahr(d: Path, jahr: int) -> None:
    datum = pd.Timestamp(_dt.date(BEGINN.year + jahr, 1, 1))
    for name in ("historie", "bestand"):
        tab = read_portfolio(d / f"{name}.parquet")
        tab["status_date"] = datum
        write_portfolio(tab, d / f"{name}.parquet")


def _mit_scheibe(d: Path, jahr: int, t: int) -> None:
    from rechner_pipeline.models.bestand import SCHEIBEN_NAMES, SCHEIBEN_SPALTEN

    scheiben = pd.DataFrame([{
        "police_id": POLICE, "scheiben_id": 1, "erhoehung_jahr": jahr,
        "erhoehung_datum": pd.Timestamp(_dt.date(BEGINN.year + jahr, 1, 1)),
        "entry_age": 40 + jahr, "duration": LAUFZEIT - jahr, "premium_duration": max(t - jahr, 1),
        "sum_insured": 1000.0, "gamma1": 0.0,
    }])[list(SCHEIBEN_NAMES)].astype(dict(SCHEIBEN_SPALTEN))
    write_portfolio(scheiben, d / "scheiben.parquet")


def _pb1_vorgangsjahr(d: Path, stichtag: _dt.date) -> list:
    from rechner_pipeline.bestand.vorbedingungen import lies_und_pruefe_pb1

    eingaben = {"portfolio": d / "bestand.parquet", "historie": d / "historie.parquet",
                "ledger": d / "ledger.parquet"}
    if (d / "scheiben.parquet").is_file():
        eingaben["scheiben"] = d / "scheiben.parquet"
    _t, _g, fehler, _u = lies_und_pruefe_pb1(eingaben, bis=stichtag)
    return [f["message"] for f in fehler if f["code"] == "vorgangsjahr"]


@pytest.mark.parametrize("pex_jahr, zulaessig", [(11, True), (12, False), (14, False)])
def test_i13_fortschreibung_und_p1_urteilen_gleich_ueber_die_freistellung(
        tmp_path, pex_jahr, zulaessig):
    """t = 12, Zugang im Jahr 15. Auf 9fa1538 rot fuer 12 und 14: die
    Fortschreibung schrieb Lauf und Manifest. Soll: Exit 2 und kein Manifest,
    genau dann, wenn P-B1 auf demselben Eingang die Jahresgrenze meldet."""
    d, stichtag = _uebernahme(tmp_path / "u", 12, 11, 15)
    if pex_jahr != 11:
        _setze_pex_jahr(d, pex_jahr)
    meldungen = _pb1_vorgangsjahr(d, stichtag)
    assert (meldungen == []) is zulaessig, meldungen
    lauf = tmp_path / "lauf"
    code = cli_fortschreibung.main([
        "--config", str(CONFIG), "--bis", _dt.date(stichtag.year + 2, 1, 1).isoformat(),
        "--uebernahme", str(d), "--out-dir", str(lauf)])
    assert code == (0 if zulaessig else 2)
    assert (lauf / "laufmanifest.json").is_file() is zulaessig


def test_i13_die_fortschreibung_prueft_das_jahr_das_die_engine_liest(tmp_path):
    """Die Engine liest das Freistellungsjahr aus dem Zustand des STAMMS
    (``ereignisse._zugangslage``), nicht aus der Historie. Steht nur dort ein
    Jahr >= t (Historie zulaessig), verweigert die Fortschreibung ebenso."""
    d, stichtag = _uebernahme(tmp_path / "u", 12, 11, 15)
    stamm = read_portfolio(d / "bestand.parquet")
    stamm["status_date"] = pd.Timestamp(_dt.date(BEGINN.year + 13, 1, 1))
    write_portfolio(stamm, d / "bestand.parquet")
    assert cli_fortschreibung.main([
        "--config", str(CONFIG), "--bis", _dt.date(stichtag.year + 2, 1, 1).isoformat(),
        "--uebernahme", str(d), "--out-dir", str(tmp_path / "lauf")]) == 2
    assert not (tmp_path / "lauf" / "laufmanifest.json").exists()


@pytest.mark.parametrize("erh_jahr, zulaessig", [(1, True), (0, False), (12, False)])
def test_i13_mitgebrachte_scheiben_gehen_durch_dieselbe_regel(tmp_path, erh_jahr, zulaessig):
    """Eine mitgebrachte Erhoehungsscheibe im Jahr 0 oder ab t (= 12) an einem
    beitragspflichtig uebernommenen Vertrag: P-B1 meldet sie, die
    Fortschreibung schreibt keinen Lauf. Positivkontrolle: Jahr 1."""
    stichtag = _dt.date(BEGINN.year + 15, 1, 1)
    zeile = {"police_id": POLICE, "beginn": BEGINN.isoformat(), "entry_age": 40,
             "duration": LAUFZEIT, "premium_duration": 12, "sex": "M",
             "sum_insured": 20000.0, "zahlweise": 12}
    stamm, historie, ledger, _h = baue(
        [zeile], tarif_generation="KLV-2015", produkt="klv", stichtag=stichtag,
        vorgeschichte={}, generationsfelder=_felder())
    d = tmp_path / "u"
    d.mkdir()
    for name, tab in (("bestand", stamm), ("historie", historie), ("ledger", ledger)):
        write_portfolio(tab, d / f"{name}.parquet")
    _mit_scheibe(d, erh_jahr, 12)
    meldungen = _pb1_vorgangsjahr(d, stichtag)
    assert (meldungen == []) is zulaessig, meldungen
    code = cli_fortschreibung.main([
        "--config", str(CONFIG), "--bis", _dt.date(stichtag.year + 2, 1, 1).isoformat(),
        "--uebernahme", str(d), "--out-dir", str(tmp_path / "lauf")])
    assert (code == 0) is zulaessig, code
