"""CLI-Befehle des Bestandsmoduls: bestand_fortschreibung (Producer) + Gate B1."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
from rechner_pipeline.toolbox import bestand_fortschreibung as fs_cli
from rechner_pipeline.toolbox._common import run_command
from rechner_pipeline.toolbox import bestand_validate as gate_cli

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = REPO_ROOT / "examples" / "bestand_klv.toml"


@pytest.fixture()
def lauf(tmp_path):
    """Ein kompletter CLI-Lauf: erzeugen + fortschreiben in tmp_path."""
    out = tmp_path / "lauf"
    code = fs_cli.main(
        ["--config", str(EXAMPLE), "--bis", "2020-01-01", "--out-dir", str(out)]
    )
    assert code == 0
    return out


def test_fortschreibung_cli_schreibt_alle_tabellen(lauf):
    dateien = {p.name for p in lauf.glob("*.parquet")}
    assert dateien == {
        "bestand.parquet", "historie.parquet", "ledger.parquet",
        "scheiben.parquet", "zugaenge.parquet", "bestand_gesamt.parquet",
    }
    bestand = read_portfolio(lauf / "bestand.parquet")
    ledger = read_portfolio(lauf / "ledger.parquet")
    assert len(bestand) == 1000 and len(ledger) > 0
    # Ohne --neuzugang-ab: keine Zugaenge, gesamt == basis.
    assert len(read_portfolio(lauf / "zugaenge.parquet")) == 0


def test_fortschreibung_cli_mit_neuzugang(tmp_path):
    import copy
    import tomllib

    # Config-Kopie mit Neuzugang (TOML um eine Zeile ergaenzt):
    quelle = EXAMPLE.read_text(encoding="utf-8")
    angepasst = quelle.replace(
        "# neuzugang_pro_jahr = 40", "", 1
    ).replace(
        'name = "KLV-2008"', 'name = "KLV-2008"\nneuzugang_pro_jahr = 30', 1
    )
    cfg_pfad = tmp_path / "cfg.toml"
    cfg_pfad.write_text(angepasst, encoding="utf-8")
    out = tmp_path / "lauf"
    code = fs_cli.main(
        ["--config", str(cfg_pfad), "--bis", "2014-01-01",
         "--neuzugang-ab", "2010-01-01", "--out-dir", str(out)]
    )
    assert code == 0
    zugaenge = read_portfolio(out / "zugaenge.parquet")
    gesamt = read_portfolio(out / "bestand_gesamt.parquet")
    basis = read_portfolio(out / "bestand.parquet")
    assert len(zugaenge) > 0
    assert len(gesamt) == len(basis) + len(zugaenge)
    # Basis wurde bis zum Referenzstichtag beschnitten erzeugt:
    assert (basis["insurance_start"] <= "2010-01-01").all()


def test_fortschreibung_cli_usage_fehler(tmp_path):
    assert fs_cli.main(
        ["--config", str(tmp_path / "fehlt.toml"), "--bis", "2020-01-01",
         "--out-dir", str(tmp_path)]
    ) == 2
    assert fs_cli.main(
        ["--config", str(EXAMPLE), "--bis", "kein-datum", "--out-dir", str(tmp_path)]
    ) == 2


def test_gate_b1_passed_und_ledger(lauf, tmp_path, capsys):
    diagnostics = tmp_path / "diag"
    code = run_command(gate_cli.main, [
        "--portfolio", str(lauf / "bestand_gesamt.parquet"),
        "--historie", str(lauf / "historie.parquet"),
        "--scheiben", str(lauf / "scheiben.parquet"),
        "--config", str(EXAMPLE),
        "--diagnostics-dir", str(diagnostics),
    ])
    ergebnis = json.loads(capsys.readouterr().out)
    assert code == 0
    assert ergebnis["status"] == "passed"
    assert ergebnis["summary"]["all_passed"] is True
    assert ergebnis["summary"]["portfolio_zeilen"] == 1000
    assert (diagnostics / "bestand_validate.gate.json").is_file()


def test_gate_b1_bewegungsidentitaet(lauf, tmp_path, capsys):
    basis = [
        "--portfolio", str(lauf / "bestand_gesamt.parquet"),
        "--historie", str(lauf / "historie.parquet"),
        "--scheiben", str(lauf / "scheiben.parquet"),
        "--diagnostics-dir", str(tmp_path / "diag"),
    ]
    code = run_command(gate_cli.main, basis + [
        "--ledger", str(lauf / "ledger.parquet"), "--bis", "2020-01-01",
    ])
    ergebnis = json.loads(capsys.readouterr().out)
    assert code == 0
    assert ergebnis["summary"]["bewegungsjahre"] > 0

    # Manipulierter Ledger (ein Storno entfernt): Identitaet bricht hart.
    ledger = read_portfolio(lauf / "ledger.parquet")
    sto = ledger[ledger["ereignis"] == "STO"]
    kaputt = ledger.drop(index=sto.index[:1]).reset_index(drop=True)
    pfad = write_portfolio(kaputt, tmp_path / "ledger_kaputt.parquet")
    code = run_command(gate_cli.main, basis + [
        "--ledger", str(pfad), "--bis", "2020-01-01",
    ])
    ergebnis = json.loads(capsys.readouterr().out)
    assert code == 20
    assert any(e["code"] == "bewegung" for e in ergebnis["errors"])

    # --ledger ohne --bis (bzw. --bis ohne --ledger) ist ein Usage-Fehler:
    assert run_command(gate_cli.main, basis + [
        "--ledger", str(lauf / "ledger.parquet"),
    ]) == 2
    capsys.readouterr()
    assert run_command(gate_cli.main, basis + ["--bis", "2020-01-01"]) == 2
    capsys.readouterr()


def test_gate_b1_findet_verletzungen(lauf, tmp_path, capsys):
    kaputt = read_portfolio(lauf / "bestand.parquet")
    kaputt.loc[kaputt.index[0], "sum_insured"] = -1.0
    pfad = write_portfolio(kaputt, tmp_path / "kaputt.parquet")
    code = run_command(gate_cli.main, [
        "--portfolio", str(pfad),
        "--diagnostics-dir", str(tmp_path / "diag"),
    ])
    ergebnis = json.loads(capsys.readouterr().out)
    assert code == 20  # Exit.FILE_CONTRACT
    assert ergebnis["status"] == "failed"
    assert any(e["code"] == "portfolio" for e in ergebnis["errors"])


def test_gate_b1_usage(tmp_path, capsys):
    code = run_command(gate_cli.main, ["--diagnostics-dir", str(tmp_path)])
    ergebnis = json.loads(capsys.readouterr().out)
    assert code == 2
    assert any(e["code"] == "missing_arg" for e in ergebnis["errors"])
