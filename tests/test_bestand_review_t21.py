"""Externes Review, ToDo 21 (Stand 730fcb0): Nachweise und Regressionen.

Jeder Test traegt den Nachweis des Reviews als Repro: Was VORHER gruen
war und rot sein musste, ist hier festgeschrieben. Die Zeilen mit
"Mutationsprobe" nennen, welche Wache den Test faengt.

Knoten: klv, bu
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

import pytest

from rechner_pipeline.bestand import cli_fortschreibung
from rechner_pipeline.bestand.config import load_config
from rechner_pipeline.bestand.ereignisse import fortschreiben
from rechner_pipeline.bestand.generator import generate
from rechner_pipeline.bestand.kennzahlen import bu_bewegungskonto
from rechner_pipeline.bestand.ledger_bindung import pruefe_ledger_betraege, zustand_vor
from rechner_pipeline.bestand.parquet_io import read_portfolio
from rechner_pipeline.fall import anlegen
from rechner_pipeline.gates import bestand_validate
from rechner_pipeline.models.bestand import validate_ledger

REPO_ROOT = Path(__file__).resolve().parents[1]
KLV_CONFIG = REPO_ROOT / "configs" / "bestand_klv.toml"
BU_CONFIG = REPO_ROOT / "configs" / "bestand_bu.toml"
sys.path.insert(0, str(REPO_ROOT / "werkzeuge"))
import falldaten as fd  # noqa: E402
import vorzeigeseite as vz  # noqa: E402


# --------------------------------------------------------------------------- #
# T21-01: BU — der Betrag eines Abgangs folgt aus dem Zustand davor
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def bu_lauf():
    config = load_config(BU_CONFIG)
    stamm = generate(config)
    erg = fortschreiben(stamm, config, _dt.date(2060, 1, 1))
    return config, stamm, erg


def _terminal(erg, im_bezug: bool):
    ledger = erg.ledger
    term = ledger[ledger["ereignis"].isin(("TOD", "ABL"))]
    for idx, z in term.iterrows():
        if (zustand_vor(erg.historie, int(z["police_id"]), z["status_date"]) == "BU") is im_bezug:
            return idx
    raise AssertionError("kein passender Abgang im Beispielbestand")


def test_bu_abgang_aus_dem_bezug_darf_nicht_null_buchen(bu_lauf):
    """Nachweis des Reviews: 'null oder Rente' akzeptierte fuer einen
    Abgang aus dem Leistungsbezug auch 0,00. Mutationsprobe: erwartet
    wieder auf {0, rente} weiten -> gruen."""
    config, stamm, erg = bu_lauf
    assert pruefe_ledger_betraege(stamm, erg.ledger, config, historie=erg.historie) == []
    ledger = erg.ledger.copy()
    idx = _terminal(erg, im_bezug=True)
    assert ledger.loc[idx, "betrag"] > 0
    ledger.loc[idx, "betrag"] = 0.0
    fehler = pruefe_ledger_betraege(stamm, ledger, config, historie=erg.historie)
    assert len(fehler) == 1 and "Kern" in fehler[0] and str(int(ledger.loc[idx, "police_id"])) in fehler[0]


def test_bu_abgang_als_anwaerter_darf_nicht_die_rente_buchen(bu_lauf):
    config, stamm, erg = bu_lauf
    ledger = erg.ledger.copy()
    idx = _terminal(erg, im_bezug=False)
    assert ledger.loc[idx, "betrag"] == 0.0
    pid = int(ledger.loc[idx, "police_id"])
    ledger.loc[idx, "betrag"] = float(stamm.set_index("police_id").loc[pid, "bu_rente"])
    fehler = pruefe_ledger_betraege(stamm, ledger, config, historie=erg.historie)
    assert len(fehler) == 1 and str(pid) in fehler[0]


def test_vorzustand_bei_invalidisierung_und_ablauf_am_selben_tag(bu_lauf):
    """Im letzten Vertragsjahr bucht die Engine INV und ABL auf dasselbe
    Datum; der Vorzustand des Ablaufs ist dann BU, nicht der Zustand vor
    dem Tag. Mutationsprobe: '<=' zu '<' in zustand_vor -> rot."""
    config, stamm, erg = bu_lauf
    h, l = erg.historie, erg.ledger
    treffer = 0
    for z in l[l["ereignis"] == "INV"].itertuples():
        abl = l[(l["police_id"] == z.police_id) & (l["ereignis"] == "ABL")
                & (l["status_date"] == z.status_date)]
        if len(abl):
            treffer += 1
            assert zustand_vor(h, int(z.police_id), z.status_date) == "BU"
            assert float(abl["betrag"].iloc[0]) > 0
    assert treffer > 0, "der Beispielbestand traegt den Fall INV+ABL am selben Tag"


def test_bewegungskonto_liest_den_track_aus_der_historie_nicht_aus_dem_betrag(bu_lauf):
    """Nachweis des Reviews: Das Konto ordnete einen Abgang ueber
    betrag > 0 dem Track zu — Pruefung und Konto bestaetigten einander.
    Ein korrumpierter Betrag darf das Konto nicht veraendern."""
    config, stamm, erg = bu_lauf
    bis = _dt.date(2060, 1, 1)
    referenz = bu_bewegungskonto(stamm, erg.historie, erg.ledger, bis=bis)
    ledger = erg.ledger.copy()
    ledger.loc[_terminal(erg, im_bezug=True), "betrag"] = 0.0
    assert bu_bewegungskonto(stamm, erg.historie, ledger, bis=bis) == referenz


# --------------------------------------------------------------------------- #
# T21-03: endliche Parameter, nichtendlicher Bestand
# --------------------------------------------------------------------------- #

def test_ueberlaufende_lognormal_stoppt_den_produzenten_vor_dem_publish(tmp_path):
    """Nachweis des Reviews: meanlog = 1000 ist endlich, exp(1000) nicht;
    config.validate() war gruen, der Bestand voller inf, Manifest
    geschrieben. Mutationsprobe: errstate/Endlichkeitspruefung entfernen
    -> Exit 0 und Dateien."""
    text = KLV_CONFIG.read_text(encoding="utf-8")
    assert text.count("meanlog = 10.9") == 1
    config = tmp_path / "c.toml"
    config.write_text(text.replace("meanlog = 10.9", "meanlog = 1000.0"), encoding="utf-8")
    assert load_config(config).validate() == [], "die Parameter SIND endlich"
    out = tmp_path / "lauf"
    assert cli_fortschreibung.main([
        "--config", str(config), "--bis", "2020-01-01", "--out-dir", str(out),
    ]) == 2
    assert not out.exists() or not list(out.iterdir()), "nichts darf publiziert sein"


# --------------------------------------------------------------------------- #
# T21-04: unbekannter Fall-Scope ist eine Luecke, kein Tarif-Fall
# --------------------------------------------------------------------------- #

def _fall(tmp_path: Path, manifest: dict) -> Path:
    fall = tmp_path / "fall"
    fall.mkdir()
    (fall / "fall.json").write_text(json.dumps(manifest), "utf-8")
    (fall / "eingang.json").write_text(json.dumps({"quellen": []}), "utf-8")
    return fall


def test_fall_ohne_strengen_scope_wird_mit_dem_vollen_profil_geprueft(tmp_path):
    """Nachweis des Reviews: scope None zaehlte als Tarif-Fall — A-M4 und
    Bestandsabnahmen galten als nicht erwartet. Mutationsprobe: Fallback
    'bestand' zu 'tarif' -> rot."""
    fall = _fall(tmp_path, {"name": "alt", "scope": {"typ": "bestand"}})  # ohne schema_version
    modell = fd.sammle(fall, [])
    assert modell["fall"]["scope"] is None
    luecken = {(l["gruppe"], l["feld"]) for l in fd.luecken(modell)}
    assert ("fall", "scope") in luecken
    assert ("abnahmen", "controlling") in luecken, "fail-closed: das volle Profil"
    assert any(l["feld"] == "scope" and "schema_version" in l["wirkung"]
               for l in fd.luecken(modell))


def test_ein_echter_tarif_fall_verlangt_kein_controlling(tmp_path):
    fall = tmp_path / "tarif"
    anlegen(fall, scope="tarif")
    modell = fd.sammle(fall, [])
    assert modell["fall"]["scope"] == "tarif"
    luecken = {(l["gruppe"], l["feld"]) for l in fd.luecken(modell)}
    assert ("fall", "scope") not in luecken
    assert ("abnahmen", "controlling") not in luecken


# --------------------------------------------------------------------------- #
# T21-05: Die Darstellung behauptet nichts ueber die Besetzung
# --------------------------------------------------------------------------- #

def test_die_kopfzeile_behauptet_keinen_simulationsschluessel_ohne_snapshots(tmp_path):
    """Die Kopfzeile sagte fuer jeden Fall 'Simulationsschluessel' —
    auch fuer einen ohne Snapshots oder mit Schluesselklasse mensch."""
    fall = tmp_path / "fall"
    anlegen(fall, scope="bestand")
    modell = fd.sammle(fall, [])
    seite = vz._seite(fall, modell, tmp_path, [], None)
    assert "Simulationsschlüssel" not in seite
    assert "Schlüsselklasse" in seite
    def _e(gate, klasse):
        return {"gate": gate, "entscheid": "angenommen", "entscheider": "x",
                "rolle": "mensch/verantwortlicher-aktuar", "schluesselklasse": klasse,
                "schluessel_sha256": "", "strukturell_verifiziert": True,
                "verifikationsbefunde": [], "signatur_verifiziert": False}

    modell["kette"]["entscheide"] = [_e("A-M1", "simulation")]
    seite = vz._seite(fall, modell, tmp_path, [], None)
    assert "Simulationsschlüssel" in seite
    modell["kette"]["entscheide"] = [_e("A-M1", "simulation"), _e("A-M2", "mensch")]
    assert "Simulationsschlüssel" not in vz._seite(fall, modell, tmp_path, [], None)


def test_keine_darstellung_nennt_snapshots_menschliche_entscheide():
    for pfad in ("werkzeuge/falldaten.py", "werkzeuge/vorzeigeseite.py",
                 "werkzeuge/fallbericht.py"):
        text = (REPO_ROOT / pfad).read_text(encoding="utf-8")
        assert "menschlichen Entscheide" not in text and "menschlichen Abnahmen" not in text, pfad
        assert "menschlicher Entscheid" not in text, pfad


# --------------------------------------------------------------------------- #
# T21-07: betrag_herkunft folgt aus dem Erzeugungspfad
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def klv_lauf(tmp_path_factory) -> Path:
    ziel = tmp_path_factory.mktemp("klv")
    assert cli_fortschreibung.main([
        "--config", str(KLV_CONFIG), "--bis", "2020-01-01", "--out-dir", str(ziel),
    ]) == 0
    return ziel


def test_geliefert_nur_am_zugang_eines_uebernommenen_vertrags(klv_lauf):
    """Nachweis des Reviews: 'geliefert' an einem gerechneten STO gab []."""
    stamm = read_portfolio(klv_lauf / "bestand_gesamt.parquet")
    ledger = read_portfolio(klv_lauf / "ledger.parquet")
    historie = read_portfolio(klv_lauf / "historie.parquet")
    scheiben = read_portfolio(klv_lauf / "scheiben.parquet")
    assert validate_ledger(stamm, ledger, historie, scheiben) == []
    sto = ledger.index[ledger["ereignis"] == "STO"][0]
    ledger.loc[sto, "betrag_herkunft"] = "geliefert"
    fehler = validate_ledger(stamm, ledger, historie, scheiben)
    assert any("'geliefert' nur fuer den Zugang" in f for f in fehler), fehler


def test_zugang_eines_uebernommenen_vertrags_muss_geliefert_tragen(klv_lauf):
    """Umkehrung: Der Zugang eines UEBERNOMMENEN Vertrags (Zugang nach
    Beginn) traegt die gelieferte Summe — 'gerechnet' dort ist falsch."""
    import pandas as pd

    stamm = read_portfolio(klv_lauf / "bestand_gesamt.parquet").copy()
    ledger = read_portfolio(klv_lauf / "ledger.parquet")
    historie = read_portfolio(klv_lauf / "historie.parquet")
    scheiben = read_portfolio(klv_lauf / "scheiben.parquet")
    i = stamm.index[0]
    pid = int(stamm.loc[i, "police_id"])
    zugang = stamm.loc[i, "insurance_start"] + pd.Timedelta(days=400)
    stamm.loc[i, "bestandszugang"] = zugang
    zug = pd.DataFrame([{
        "police_id": pid, "tarif_generation": stamm.loc[i, "tarif_generation"],
        "ereignis": "ZUG", "vertragsjahr": 0, "status_date": zugang,
        "betrag_art": "VS", "betrag": float(stamm.loc[i, "sum_insured"]),
        "betrag_herkunft": "gerechnet",
    }])
    mit_zug = pd.concat([ledger, zug[ledger.columns]], ignore_index=True)
    mit_zug["status_date"] = pd.to_datetime(mit_zug["status_date"])
    fehler = validate_ledger(stamm, mit_zug, historie, scheiben)
    assert any("muss betrag_herkunft 'geliefert'" in f and str(pid) in f for f in fehler), fehler
    mit_zug.loc[mit_zug.index[-1], "betrag_herkunft"] = "geliefert"
    fehler = validate_ledger(stamm, mit_zug, historie, scheiben)
    assert not any("geliefert" in f for f in fehler), fehler


# --------------------------------------------------------------------------- #
# T21-09: Die Akzeptanzmenge von P-B1 hat sich geaendert -> Major
# --------------------------------------------------------------------------- #

def test_pb1_version_und_readme_nennen_den_versionssprung():
    assert bestand_validate.GATE_VERSION == "3.0.0"
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "P-B1 (Version `3.0.0`)" in readme
    assert "`2.1.0`" in readme and "T21-09" in readme
