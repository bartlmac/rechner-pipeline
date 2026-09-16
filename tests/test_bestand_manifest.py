"""Laufmanifest: Der Horizont ist belegt, das Bundle ist EIN Lauf (T18-02).

Externes Review T18-02, als Regression festgeschrieben: ``--bis`` war
bei den Konsumenten eines Laufs eine Behauptung des Aufrufers. Ein bis
2020-01-01 simulierter Lauf, festgeschrieben mit ``--bis 2020-12-01``,
lief mit Exit 0 durch. Jetzt schreibt der Erzeuger einen Lieferschein,
und der Abschluss verweigert ohne ihn oder gegen ihn.

Jeder Test ist so gebaut, dass er VOR der Korrektur durchgelaufen
waere (Mutationsprobe: Manifestpflicht in cli_abschluss entfernen bzw.
die Hash-/Horizontpruefung in der Engine — die Tests werden rot).

Knoten: klv
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from rechner_pipeline.bestand import cli_abschluss, cli_fortschreibung
from rechner_pipeline.bestand.abschluss import abschluss_pfad
from rechner_pipeline.bestand.manifest import (
    MANIFEST_DATEI,
    ManifestError,
    lies_manifest,
    schreibe_manifest,
)
from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
from rechner_pipeline.bestand.vorbedingungen import lies_und_pruefe_pb1
from rechner_pipeline.gates import bestand_validate

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = REPO_ROOT / "configs" / "bestand_klv.toml"
HORIZONT = _dt.date(2020, 1, 1)
STICHTAG = _dt.date(2016, 1, 1)


@pytest.fixture(scope="module")
def lauf(tmp_path_factory) -> Path:
    """Ein echter Lauf ueber die CLI — so, wie er auf der Platte landet."""
    ziel = tmp_path_factory.mktemp("lauf")
    assert cli_fortschreibung.main([
        "--config", str(CONFIG), "--bis", HORIZONT.isoformat(),
        "--out-dir", str(ziel),
    ]) == 0
    return ziel


def _kopie(lauf: Path, tmp_path: Path) -> Path:
    ziel = tmp_path / "lauf"
    shutil.copytree(lauf, ziel)
    return ziel


def _argv(lauf_dir: Path, out_dir: Path, bis: _dt.date = HORIZONT) -> list:
    return [
        "--config", str(CONFIG), "--lauf", str(lauf_dir),
        "--stichtag", STICHTAG.isoformat(), "--bis", bis.isoformat(),
        "--out-dir", str(out_dir),
    ]


def _sha(pfad: Path) -> str:
    return hashlib.sha256(pfad.read_bytes()).hexdigest()


# --------------------------------------------------------------------------- #
# Der Erzeuger schreibt den Lieferschein — ueber die Bytes, die daliegen
# --------------------------------------------------------------------------- #

def test_der_lauf_schreibt_sein_manifest_ueber_die_geschriebenen_bytes(lauf):
    manifest = lies_manifest(lauf)

    assert manifest["horizont"] == HORIZONT.isoformat()
    assert manifest["neuzugang_ab"] is None
    assert manifest["config"]["sha256"] == _sha(CONFIG)
    # Unabhaengige Kontrollrechnung: jede Ausgabe, jede Summe.
    erwartet = {
        p.name: _sha(p) for p in lauf.glob("*.parquet")
    }
    assert manifest["ausgaben"] == erwartet
    assert set(erwartet) == {
        "bestand.parquet", "bestand_gesamt.parquet", "historie.parquet",
        "ledger.parquet", "scheiben.parquet", "zugaenge.parquet",
    }


def test_das_manifest_ist_deterministisch(lauf, tmp_path):
    """Wie die Parquet-Ausgaben: derselbe Lauf, dieselben Bytes."""
    zweit = tmp_path / "zweit"
    assert cli_fortschreibung.main([
        "--config", str(CONFIG), "--bis", HORIZONT.isoformat(),
        "--out-dir", str(zweit),
    ]) == 0
    assert (zweit / MANIFEST_DATEI).read_bytes() == (lauf / MANIFEST_DATEI).read_bytes()


# --------------------------------------------------------------------------- #
# Der Abschluss verlangt den Lieferschein: Pflicht, fail-fast
# --------------------------------------------------------------------------- #

def test_ohne_manifest_wird_nichts_festgeschrieben(lauf, tmp_path, capsys):
    lauf_dir = _kopie(lauf, tmp_path)
    (lauf_dir / MANIFEST_DATEI).unlink()
    out = tmp_path / "ab"

    assert cli_abschluss.main(_argv(lauf_dir, out)) == 2
    assert not abschluss_pfad(out, STICHTAG).exists()
    meldung = capsys.readouterr().err
    assert "kein Laufmanifest" in meldung
    assert "cli_fortschreibung" in meldung, "die Meldung nennt den Ausweg"


def test_behaupteter_horizont_wird_abgewiesen(lauf, tmp_path, capsys):
    """Der Repro des Reviews: Lauf bis 2020-01-01, Abschluss mit
    behauptetem --bis 2020-12-01. Vorher Exit 0 und ein um 1,37 Mio EUR
    ueberzeichnetes Bewegungskonto."""
    out = tmp_path / "ab"

    assert cli_abschluss.main(_argv(lauf, out, bis=_dt.date(2020, 12, 1))) == 2
    assert not abschluss_pfad(out, STICHTAG).exists()
    assert "widerspricht dem Laufmanifest" in capsys.readouterr().err


def test_datei_aus_anderem_lauf_faellt_auf(lauf, tmp_path, capsys):
    """Die T16-Klasse geschlossen: ein fuer sich wohlgeformtes Teil aus
    einem ANDEREN Lauf (gleiche Config, anderer Horizont) im Bundle."""
    anderer = tmp_path / "anderer"
    assert cli_fortschreibung.main([
        "--config", str(CONFIG), "--bis", "2022-01-01", "--out-dir", str(anderer),
    ]) == 0
    lauf_dir = _kopie(lauf, tmp_path)
    shutil.copy(anderer / "scheiben.parquet", lauf_dir / "scheiben.parquet")
    out = tmp_path / "ab"

    assert cli_abschluss.main(_argv(lauf_dir, out)) == 2
    assert not abschluss_pfad(out, STICHTAG).exists()
    assert "nicht die im Laufmanifest belegte SHA-256" in capsys.readouterr().err


def test_nachtraeglich_veraenderte_config_faellt_auf(lauf, tmp_path, capsys):
    """Die Config ist Teil des Laufs: Ein Abschluss unter anderen
    Rechnungsgrundlagen als denen der Fortschreibung ist kein Abschluss
    dieses Laufs."""
    config = tmp_path / "bestand_klv.toml"
    config.write_text(
        CONFIG.read_text(encoding="utf-8") + "\n# nachtraeglich\n", encoding="utf-8")
    out = tmp_path / "ab"
    argv = _argv(lauf, out)
    argv[argv.index("--config") + 1] = str(config)

    assert cli_abschluss.main(argv) == 2
    assert not abschluss_pfad(out, STICHTAG).exists()
    assert "die Config" in capsys.readouterr().err


def test_manifest_von_hand_ist_kein_manifest(lauf, tmp_path, capsys):
    lauf_dir = _kopie(lauf, tmp_path)
    (lauf_dir / MANIFEST_DATEI).write_text(
        json.dumps({"horizont": HORIZONT.isoformat()}), encoding="utf-8")

    assert cli_abschluss.main(_argv(lauf_dir, tmp_path / "ab")) == 2
    assert "ungueltig" in capsys.readouterr().err


def test_mit_manifest_schreibt_und_prueft_der_abschluss(lauf, tmp_path):
    out = tmp_path / "ab"
    assert cli_abschluss.main(_argv(lauf, out)) == 0
    assert abschluss_pfad(out, STICHTAG).is_file()
    assert cli_abschluss.main(_argv(lauf, out) + ["--pruefen"]) == 0


# --------------------------------------------------------------------------- #
# Die Engine: gehasht und geparst werden dieselben Bytes
# --------------------------------------------------------------------------- #

def test_engine_haelt_jede_rolle_und_die_config_gegen_das_manifest(lauf, tmp_path):
    lauf_dir = _kopie(lauf, tmp_path)
    manifest = lies_manifest(lauf_dir)
    eingaben = {
        "portfolio": lauf_dir / "bestand_gesamt.parquet",
        "historie": lauf_dir / "historie.parquet",
        "ledger": lauf_dir / "ledger.parquet",
        "scheiben": lauf_dir / "scheiben.parquet",
        "config": CONFIG,
    }
    tabellen, geprueft, fehler, usage = lies_und_pruefe_pb1(
        eingaben, bis=HORIZONT, manifest=manifest)
    assert fehler == [] and usage == []
    assert geprueft["manifest_gebunden"] == 5
    assert "config" in tabellen, "die geparste Config kommt aus der Pruefung"

    # Ein Byte anders in der Historie — gleicher Inhalt waere moeglich,
    # aber der Lauf hat DIESE Bytes nicht geschrieben.
    historie = read_portfolio(lauf_dir / "historie.parquet")
    write_portfolio(historie.iloc[::-1].reset_index(drop=True),
                    lauf_dir / "historie.parquet")
    _, _, fehler, _ = lies_und_pruefe_pb1(eingaben, bis=HORIZONT, manifest=manifest)
    assert any(f["code"] == "manifest" and "historie" in f["message"]
               for f in fehler)


def test_ohne_manifest_prueft_die_engine_wie_bisher(lauf):
    """Das Gate darf auch Tabellen ohne Lauf pruefen — der Abschluss nicht."""
    eingaben = {"portfolio": lauf / "bestand_gesamt.parquet",
                "historie": lauf / "historie.parquet"}
    _, geprueft, fehler, _ = lies_und_pruefe_pb1(eingaben)
    assert fehler == []
    assert "manifest_gebunden" not in geprueft


# --------------------------------------------------------------------------- #
# Gate P-B1 bindet das Manifest auf Wunsch
# --------------------------------------------------------------------------- #

def _gate_argv(lauf: Path, tmp_path: Path, bis: _dt.date, *extra: str) -> list:
    return [
        "--portfolio", str(lauf / "bestand_gesamt.parquet"),
        "--historie", str(lauf / "historie.parquet"),
        "--ledger", str(lauf / "ledger.parquet"),
        "--scheiben", str(lauf / "scheiben.parquet"),
        "--bis", bis.isoformat(),
        "--diagnostics-dir", str(tmp_path / "diag"),
        *extra,
    ]


def test_gate_bindet_manifest_und_traegt_es_im_ledger(lauf, tmp_path):
    argv = _gate_argv(lauf, tmp_path, HORIZONT,
                      "--manifest", str(lauf / MANIFEST_DATEI))
    ergebnis = bestand_validate.main(argv)
    assert ergebnis.exit_code == 0
    assert ergebnis.summary["manifest"] == {
        "sha256": _sha(lauf / MANIFEST_DATEI),
        "horizont": HORIZONT.isoformat(),
    }
    assert ergebnis.summary["manifest_gebunden"] == 4
    # Der Beleg auf der Platte traegt dieselbe Bindung.
    ledger = json.loads(
        (tmp_path / "diag" / "bestand_validate.gate.json").read_text(encoding="utf-8"))
    assert ledger["summary"]["manifest"]["sha256"] == _sha(lauf / MANIFEST_DATEI)


def test_gate_weist_behaupteten_horizont_gegen_das_manifest_ab(lauf, tmp_path):
    argv = _gate_argv(lauf, tmp_path, _dt.date(2020, 12, 1),
                      "--manifest", str(lauf / MANIFEST_DATEI))
    ergebnis = bestand_validate.main(argv)
    assert ergebnis.exit_code == 20
    assert any(e["code"] == "manifest" for e in ergebnis.errors)


def test_gate_ohne_manifest_bleibt_wie_bisher(lauf, tmp_path):
    """Die Rueckwaertskompatibilitaet ist gewollt: einzelne Tabellen
    ohne Lauf sind ein gueltiger Eingang des Gates."""
    ergebnis = bestand_validate.main(_gate_argv(lauf, tmp_path, HORIZONT))
    assert ergebnis.exit_code == 0
    assert ergebnis.summary["manifest"] is None


# --------------------------------------------------------------------------- #
# Bibliotheksvertrag
# --------------------------------------------------------------------------- #

def test_schreibe_manifest_nimmt_nur_vorhandene_ausgaben(tmp_path):
    ausgabe = tmp_path / "x.parquet"
    ausgabe.write_bytes(b"egal")
    pfad = schreibe_manifest(
        tmp_path, horizont=HORIZONT, neuzugang_ab=_dt.date(2010, 1, 1),
        config_pfad=CONFIG, ausgaben=[ausgabe])
    manifest = lies_manifest(pfad)
    assert manifest["ausgaben"] == {"x.parquet": _sha(ausgabe)}
    assert manifest["neuzugang_ab"] == "2010-01-01"
    with pytest.raises(ManifestError, match="kein Laufmanifest"):
        lies_manifest(tmp_path / "leer")
