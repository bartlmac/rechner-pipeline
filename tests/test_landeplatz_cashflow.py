"""Landeplatz der Cashflow-Modelle: plv/cashflow/ (ADR-007, Nachtrag vom 10.11.2026).

Zwei Wachen und die Probe:

- W1: Code unter plv/cashflow/ importiert kein Modul aus rechner_pipeline,
  also auch nicht den Rechenkern.
- W2: Kein Modul in src/, werkzeuge/ oder system/ importiert den Landeplatz.
- Die Probe liest ihre Eingabe nur und liefert die Beitragsreihe.

Die Schichtenkarte sieht den Ordner noch nicht (#67); bis dahin wacht dieser
Test. Die Probe wird ueber ihren Pfad geladen, sys.path bleibt unberuehrt.

Knoten: system/architektur
"""

import ast
import hashlib
import importlib.util
from pathlib import Path

import pandas as pd
import pytest

WURZEL = Path(__file__).resolve().parents[1]
LANDEPLATZ = WURZEL / "plv" / "cashflow"
NACHBARN = ("src", "werkzeuge", "system")


def _namen(quelle: str) -> list:
    """Absolut importierte Modulnamen und alle Zeichenketten einer Datei.

    Zeichenketten zaehlen mit, damit ein Laden ueber importlib oder ueber
    einen Pfad nicht an der Wache vorbeigeht. Relative Importe bleiben im
    eigenen Paket und zaehlen nicht.
    """
    namen = []
    for knoten in ast.walk(ast.parse(quelle)):
        if isinstance(knoten, ast.Import):
            namen += [a.name for a in knoten.names]
        elif isinstance(knoten, ast.ImportFrom) and knoten.level == 0 and knoten.module:
            namen.append(knoten.module)
        elif isinstance(knoten, ast.Constant) and isinstance(knoten.value, str):
            namen.append(knoten.value)
    return namen


def _aus_dem_system(name: str) -> bool:
    return name == "rechner_pipeline" or name.startswith("rechner_pipeline.")


def _auf_den_landeplatz(name: str) -> bool:
    n = name.replace("\\", "/")
    return n == "cashflow" or n.startswith(("cashflow.", "plv.cashflow")) or "plv/cashflow" in n


def befunde_w1(ordner: Path) -> list:
    """W1: Importe aus rechner_pipeline im Landeplatz."""
    return [f"{datei.relative_to(ordner)}: {name}"
            for datei in sorted(ordner.rglob("*.py"))
            for name in _namen(datei.read_text(encoding="utf-8"))
            if _aus_dem_system(name)]


def befunde_w2(wurzel: Path) -> list:
    """W2: Importe des Landeplatzes aus src/, werkzeuge/ und system/."""
    return [f"{datei.relative_to(wurzel)}: {name}"
            for teil in NACHBARN
            for datei in sorted((wurzel / teil).rglob("*.py"))
            for name in _namen(datei.read_text(encoding="utf-8"))
            if _auf_den_landeplatz(name)]


def _probe():
    spec = importlib.util.spec_from_file_location(
        "landeplatz_cashflow_probe", LANDEPLATZ / "probe.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


# --- die zwei Wachen am echten Baum -------------------------------------------

def test_w1_landeplatz_importiert_nichts_aus_rechner_pipeline():
    assert sorted(p.name for p in LANDEPLATZ.rglob("*.py")), "Landeplatz ohne Python-Datei"
    assert befunde_w1(LANDEPLATZ) == []


def test_w2_kein_nachbar_importiert_den_landeplatz():
    gelesen = sum(1 for teil in NACHBARN for _ in (WURZEL / teil).rglob("*.py"))
    assert gelesen > 100, f"nur {gelesen} Dateien gelesen"
    assert befunde_w2(WURZEL) == []


# --- Gegenproben: jede Wache meldet, was sie verbietet -------------------------

@pytest.mark.parametrize("quelle", [
    "import rechner_pipeline.kern\n",
    "from rechner_pipeline.bestand import parquet_io\n",
    "import rechner_pipeline\n",
    "import importlib\nimportlib.import_module('rechner_pipeline.kern')\n",
])
def test_w1_meldet_einen_import_aus_dem_system(tmp_path, quelle):
    (tmp_path / "rechenwerk.py").write_text("import pandas as pd\n" + quelle, encoding="utf-8")
    assert len(befunde_w1(tmp_path)) == 1


def test_w1_laesst_fremde_bibliotheken_zu(tmp_path):
    (tmp_path / "rechenwerk.py").write_text(
        "import numpy as np\nimport pandas as pd\nfrom pathlib import Path\n", encoding="utf-8")
    assert befunde_w1(tmp_path) == []


@pytest.mark.parametrize("teil, quelle", [
    ("src", "from plv.cashflow import probe\n"),
    ("werkzeuge", "import importlib.util\n"
                  "importlib.util.spec_from_file_location('p', 'plv/cashflow/probe.py')\n"),
    ("system", "import cashflow.probe\n"),
])
def test_w2_meldet_einen_import_des_landeplatzes(tmp_path, teil, quelle):
    for t in NACHBARN:
        (tmp_path / t).mkdir()
    (tmp_path / teil / "modul.py").write_text(quelle, encoding="utf-8")
    assert len(befunde_w2(tmp_path)) == 1


def test_w2_laesst_relative_importe_im_eigenen_paket_zu(tmp_path):
    for t in NACHBARN:
        (tmp_path / t).mkdir()
    (tmp_path / "src" / "modul.py").write_text("from .cashflow import x\n", encoding="utf-8")
    assert befunde_w2(tmp_path) == []


# --- die Probe ------------------------------------------------------------------

def test_probe_liefert_die_beitragsreihe_und_liest_nur(tmp_path):
    pfad = tmp_path / "bestand.parquet"
    pd.DataFrame({"jahr": [2027, 2026, 2026], "beitrag": [50.0, 100.0, 200.0],
                  "vertrag": ["c", "a", "b"]}).to_parquet(pfad)
    vorher = hashlib.sha256(pfad.read_bytes()).hexdigest()
    assert _probe().beitragsreihe(pfad, jahr="jahr", beitrag="beitrag") == {2026: 300.0, 2027: 50.0}
    assert hashlib.sha256(pfad.read_bytes()).hexdigest() == vorher


def test_probe_verweigert_einen_leeren_beitrag(tmp_path):
    pfad = tmp_path / "bestand.parquet"
    pd.DataFrame({"jahr": [2026, 2026], "beitrag": [100.0, None]}).to_parquet(pfad)
    with pytest.raises(ValueError, match="leere Werte"):
        _probe().beitragsreihe(pfad, jahr="jahr", beitrag="beitrag")
