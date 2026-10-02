"""Pruefrunde G, Bestand — registrierte Vorgaenge ohne Config (Fund G05).

Die Invariante: Wer registrierte Vorgaenge traegt — im Ledger (RED/TKU)
ODER in der Reduktionstabelle —, wird nur mit Config geprueft und berichtet;
ohne Config ist es ein Bedienfehler, fuer JEDEN Aufrufer der P-B1-Engine
(``bestand.vorbedingungen.lies_und_pruefe_pb1``). Die Wache sah bisher nur
den Ledger: Ein Lauf, dessen Reduktionstabelle Vorgaenge registriert, deren
Buchungen im Ledger alle fehlen, ging ohne ``--config`` mit Exit 0 durch P-B1
und durch den Bestandsbericht — dieselben Bytes, die beide mit Config
verweigern ("Buchung(en) registrierter Herabsetzungen fehlen"). Ohne Config
wird keine Buchung hergeleitet, also auch die Vollstaendigkeit nicht
geprueft.

Die Wache steht in der Engine, durch die jeder Aufrufer muss; die Ratsche
haelt die Menge dieser Aufrufer mit ``==``.

Knoten: system/bestand
"""

from __future__ import annotations

import ast
import datetime as _dt
from pathlib import Path

import pandas as pd
import pytest

from rechner_pipeline.bestand import cli_fortschreibung, cli_report
from rechner_pipeline.bestand.manifest import schreibe_manifest
from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
from rechner_pipeline.bestand.vorbedingungen import lies_und_pruefe_pb1
from rechner_pipeline.gates import bestand_validate

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src" / "rechner_pipeline"
CONFIG = REPO_ROOT / "configs" / "bestand_klv.toml"
HORIZONT = _dt.date(2020, 1, 1)


@pytest.fixture(scope="module")
def lauf(tmp_path_factory) -> Path:
    ziel = tmp_path_factory.mktemp("lauf")
    assert cli_fortschreibung.main([
        "--config", str(CONFIG), "--neuzugang-ab", "1994-07-01", "--bis", HORIZONT.isoformat(),
        "--out-dir", str(ziel),
    ]) == 0
    return ziel


def _kopie(lauf: Path, ziel: Path, ledger: pd.DataFrame | None = None) -> Path:
    """Der Lauf, wahlweise mit einem Ledger ohne RED/TKU — Manifest
    nachgefuehrt: geprueft wird die Wache, nicht die Bindung."""
    ziel.mkdir()
    for pfad in lauf.glob("*.parquet"):
        (ziel / pfad.name).write_bytes(pfad.read_bytes())
    if ledger is not None:
        write_portfolio(ledger, ziel / "ledger.parquet")
    schreibe_manifest(ziel, horizont=HORIZONT, neuzugang_ab=None,
                      config_pfad=CONFIG, ausgaben=sorted(ziel.glob("*.parquet")))
    return ziel


@pytest.fixture(scope="module")
def verstuemmelt(lauf, tmp_path_factory) -> Path:
    ledger = read_portfolio(lauf / "ledger.parquet")
    ohne = ledger[~ledger["ereignis"].isin(["RED", "TKU"])].reset_index(drop=True)
    return _kopie(lauf, tmp_path_factory.mktemp("v") / "lauf", ohne)


def _eingaben(d: Path, *, config: bool) -> dict:
    e = {"portfolio": d / "bestand_gesamt.parquet", "historie": d / "historie.parquet",
         "ledger": d / "ledger.parquet", "scheiben": d / "scheiben.parquet",
         "reduktionen": d / "reduktionen.parquet"}
    if config:
        e["config"] = CONFIG
    return e


def test_die_welt_traegt_den_fall(lauf, verstuemmelt):
    """Vorbedingung, aus den Parquet-Dateien gezaehlt: Der Lauf registriert
    Vorgaenge und bucht sie; der verstuemmelte bucht keinen."""
    red = read_portfolio(lauf / "reduktionen.parquet")
    assert len(red) > 0
    assert read_portfolio(lauf / "ledger.parquet")["ereignis"].isin(["RED", "TKU"]).sum() > 0
    assert read_portfolio(verstuemmelt / "ledger.parquet")["ereignis"].isin(["RED", "TKU"]).sum() == 0
    assert len(read_portfolio(verstuemmelt / "reduktionen.parquet")) == len(red)


def _verlangt_config(usage) -> bool:
    return any(u["code"] == "missing_arg" and "--config" in u["message"] for u in usage)


def test_engine_verlangt_die_config_auch_wenn_nur_die_tabelle_vorgaenge_traegt(verstuemmelt):
    """Auf eab5a57 rot: keine Usage, keine Fehler."""
    _, _, fehler, usage = lies_und_pruefe_pb1(_eingaben(verstuemmelt, config=False), bis=HORIZONT)
    assert _verlangt_config(usage), (usage, fehler[:3])


def test_positivkontrolle_mit_config_fehlen_die_buchungen(verstuemmelt):
    """Dieselben Bytes mit Config: die Vollstaendigkeit schlaegt an."""
    _, _, fehler, usage = lies_und_pruefe_pb1(_eingaben(verstuemmelt, config=True), bis=HORIZONT)
    assert not usage
    assert any("registrierter Herabsetzungen fehlen" in f["message"] for f in fehler), fehler[:3]


def test_positivkontrolle_der_unveraenderte_lauf(lauf):
    """Unveraendert: ohne Config die Usage (Ledger traegt RED/TKU, wie
    bisher), mit Config gruen."""
    _, _, _, usage = lies_und_pruefe_pb1(_eingaben(lauf, config=False), bis=HORIZONT)
    assert _verlangt_config(usage)
    _, _, fehler, usage = lies_und_pruefe_pb1(_eingaben(lauf, config=True), bis=HORIZONT)
    assert not usage and not fehler, (usage, fehler[:3])


def test_gate_pb1_ohne_config_ist_ein_bedienfehler(verstuemmelt, tmp_path):
    """Oeffentlicher Weg P-B1 (gates.bestand_validate): Exit 2 statt 0."""
    d = verstuemmelt
    ergebnis = bestand_validate.main([
        "--portfolio", str(d / "bestand_gesamt.parquet"), "--historie", str(d / "historie.parquet"),
        "--ledger", str(d / "ledger.parquet"), "--scheiben", str(d / "scheiben.parquet"),
        "--reduktionen", str(d / "reduktionen.parquet"), "--bis", HORIZONT.isoformat(),
        "--diagnostics-dir", str(tmp_path / "diag")])
    assert ergebnis.exit_code == 2, ergebnis.status


def test_bericht_ohne_config_ist_ein_bedienfehler(verstuemmelt, tmp_path):
    """Oeffentlicher Weg Bestandsbericht (bestand.cli_report): Exit 2 statt 0,
    kein Bericht."""
    d = verstuemmelt
    out = tmp_path / "bericht.html"
    code = cli_report.main([
        "--portfolio", str(d / "bestand_gesamt.parquet"), "--historie", str(d / "historie.parquet"),
        "--ledger", str(d / "ledger.parquet"), "--scheiben", str(d / "scheiben.parquet"),
        "--bis", HORIZONT.isoformat(), "--stichtage", "2016-01-01", "--out", str(out)])
    assert code == 2
    assert not out.exists()


#: Die Aufrufer der P-B1-Engine — jeder bekommt die Wache, weil sie in der
#: Engine steht. Ein neuer Aufrufer ist kein Befund, aber er wird hier
#: genannt, damit seine Config-Herkunft geprueft wird: die Fortschreibung
#: (``cli_abschluss``: ``--config`` Pflicht; ``tageslauf``: Config der Ablage),
#: der Zugang (``uebernahme``: Config der Ablage, wenn vorhanden), die
#: Abnahme (``abnahmebericht``: die Rollen des P-B1-Belegs), Gate und Bericht.
AUFRUFER = {
    "bestand/cli_abschluss.py", "bestand/cli_report.py", "betrieb/tageslauf.py",
    "betrieb/uebernahme.py", "gates/abnahmebericht.py", "gates/bestand_validate.py",
}


def _ruft_engine(quelle: str) -> bool:
    for k in ast.walk(ast.parse(quelle)):
        if isinstance(k, ast.Call):
            f = k.func
            name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
            if name == "lies_und_pruefe_pb1":
                return True
    return False


def test_ratsche_die_aufrufer_der_engine():
    """Statische Ratsche (Menge, ``==``). Positivkontrolle: der Detektor
    erkennt einen Aufruf und uebersieht einen Kommentar nicht als Aufruf."""
    assert _ruft_engine("x = v.lies_und_pruefe_pb1(e)\n")
    assert not _ruft_engine("# lies_und_pruefe_pb1(e)\nx = 1\n")
    gemessen = {str(p.relative_to(SRC)) for p in sorted(SRC.rglob("*.py"))
                if str(p.relative_to(SRC)) != "bestand/vorbedingungen.py"
                and _ruft_engine(p.read_text(encoding="utf-8"))}
    assert gemessen == AUFRUFER
