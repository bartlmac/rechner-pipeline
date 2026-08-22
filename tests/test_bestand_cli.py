"""CLI-Befehle des Bestandsmoduls: bestand_fortschreibung (Producer) + Gate B1.

Knoten: klv, bu
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from rechner_pipeline.bestand.config import load_config
from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
from rechner_pipeline.bestand import cli_fortschreibung as fs_cli
from rechner_pipeline.gates import _common as gate_common
from rechner_pipeline.gates._common import run_command
from rechner_pipeline.gates import bestand_validate as gate_cli

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = REPO_ROOT / "configs" / "bestand_klv.toml"
GEMISCHT = REPO_ROOT / "configs" / "bestand_gesamt.toml"


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
    erwartet = sum(
        g.sample_size for g in load_config(EXAMPLE).generationen
    )
    assert len(bestand) == erwartet and len(ledger) > 0
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


@pytest.fixture()
def lauf_gemischt(tmp_path):
    """CLI-Lauf auf dem GEMISCHTEN Beispielbestand (KLV + BU).

    Gate B1 prueft beide Nachweisungen als harte Bedingung; auf einem
    reinen KLV-Bestand laeuft der BU-Zweig leer durch und belegt nichts.
    """
    out = tmp_path / "lauf_gemischt"
    code = fs_cli.main(
        ["--config", str(GEMISCHT), "--bis", "2020-01-01", "--out-dir", str(out)]
    )
    assert code == 0
    return out


def test_gate_b1_prueft_die_bu_nachweisung(lauf_gemischt, tmp_path, capsys):
    """Der BU-Zweig des Gates mit echten BU-Daten.

    Ohne diesen Lauf war ``bu_bewegungskonto`` im Gate zwar aufgerufen,
    aber auf leerem Bestand: ein Fehler in der BU-Identitaet (Anwaerter/
    Rentner, Bezugsgroesse Jahresrente) waere unentdeckt geblieben.
    """
    from rechner_pipeline.bestand.kennzahlen import bu_bewegungskonto

    basis = [
        "--portfolio", str(lauf_gemischt / "bestand_gesamt.parquet"),
        "--historie", str(lauf_gemischt / "historie.parquet"),
        "--scheiben", str(lauf_gemischt / "scheiben.parquet"),
        "--diagnostics-dir", str(tmp_path / "diag_gemischt"),
    ]
    code = run_command(gate_cli.main, basis + [
        "--ledger", str(lauf_gemischt / "ledger.parquet"), "--bis", "2020-01-01",
    ])
    ergebnis = json.loads(capsys.readouterr().out)
    assert code == 0
    assert ergebnis["summary"]["all_passed"] is True

    # Der BU-Zweig traegt wirklich Zeilen bei (sonst prueft der Test nichts):
    portfolio = read_portfolio(lauf_gemischt / "bestand_gesamt.parquet")
    historie = read_portfolio(lauf_gemischt / "historie.parquet")
    ledger = read_portfolio(lauf_gemischt / "ledger.parquet")
    bu_zeilen = bu_bewegungskonto(portfolio, historie, ledger,
                                  bis=dt.date(2020, 1, 1))
    assert len(bu_zeilen) > 0
    assert ergebnis["summary"]["bewegungsjahre"] > len(bu_zeilen)
    # Anwaerter/Rentner statt bpfl/bfr — die BU-eigene Nachweisung:
    assert set(bu_zeilen[0]["identitaet"]) == {"anwaerter", "rentner"}

    # Manipulation NUR im BU-Teil: eine Invalidisierung entfernen. Die
    # KLV-Identitaet bleibt heil, das Gate muss trotzdem fallen.
    bu_ids = set(portfolio[portfolio["produkt"] == "bu"]["police_id"])
    inv = ledger[(ledger["ereignis"] == "INV")
                 & (ledger["police_id"].isin(bu_ids))]
    assert len(inv) > 0, "Beispielbestand ohne INV — Test waere wirkungslos"
    kaputt = ledger.drop(index=inv.index[:1]).reset_index(drop=True)
    pfad = write_portfolio(kaputt, tmp_path / "ledger_bu_kaputt.parquet")
    code = run_command(gate_cli.main, basis + [
        "--ledger", str(pfad), "--bis", "2020-01-01",
    ])
    ergebnis = json.loads(capsys.readouterr().out)
    assert code == 20
    assert any(e["code"] == "bewegung" for e in ergebnis["errors"])


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
    assert ergebnis["summary"]["portfolio_zeilen"] == sum(
        g.sample_size for g in load_config(EXAMPLE).generationen
    )
    assert (diagnostics / "bestand_validate.gate.json").is_file()


def test_gate_b1_kaputtes_parquet_ersetzt_alten_gruenen_ledger(
    lauf, tmp_path, capsys
):
    """Regression T6-12: Der bestaetigte B1-Crash darf nicht altgruen bleiben."""
    diagnostics = tmp_path / "diag_crash_regression"
    argv = [
        "--portfolio", str(lauf / "bestand_gesamt.parquet"),
        "--diagnostics-dir", str(diagnostics),
    ]
    assert run_command(gate_cli.main, argv) == 0
    capsys.readouterr()
    ledger_pfad = diagnostics / "bestand_validate.gate.json"
    alter_ledger = json.loads(ledger_pfad.read_text(encoding="utf-8"))
    assert alter_ledger["status"] == "passed"

    (lauf / "bestand_gesamt.parquet").write_bytes(b"kein Parquet")
    code = run_command(gate_cli.main, argv)
    ergebnis = json.loads(capsys.readouterr().out)
    aktueller_ledger = json.loads(ledger_pfad.read_text(encoding="utf-8"))

    assert code == 20
    assert ergebnis["status"] == "failed"
    assert aktueller_ledger["status"] == "failed"
    assert aktueller_ledger["started_at"] != alter_ledger["started_at"]
    assert any(
        error["code"] == "portfolio"
        for error in aktueller_ledger["summary"]["errors"]
    )


def test_gate_b1_unerwartete_exception_schreibt_aktuellen_roten_ledger(
    lauf, tmp_path, capsys, monkeypatch
):
    """Auch ein Fehler ausserhalb der B1-Contract-Faenger beendet den Versuch."""
    diagnostics = tmp_path / "diag_unexpected"
    argv = [
        "--portfolio", str(lauf / "bestand_gesamt.parquet"),
        "--diagnostics-dir", str(diagnostics),
    ]
    assert run_command(gate_cli.main, argv) == 0
    capsys.readouterr()
    ledger_pfad = diagnostics / "bestand_validate.gate.json"
    alter_ledger = json.loads(ledger_pfad.read_text(encoding="utf-8"))

    def _crash(*args, **kwargs):
        raise RuntimeError("erzwungener B1-Crash")

    monkeypatch.setattr(gate_cli, "hash_files", _crash)
    code = run_command(gate_cli.main, argv)
    ergebnis = json.loads(capsys.readouterr().out)
    aktueller_ledger = json.loads(ledger_pfad.read_text(encoding="utf-8"))

    assert code == 50
    assert ergebnis["status"] == "failed"
    assert ergebnis["errors"][0]["code"] == "internal_error"
    assert aktueller_ledger["status"] == "failed"
    assert aktueller_ledger["started_at"] != alter_ledger["started_at"]
    assert aktueller_ledger["summary"]["errors"][0]["code"] == "internal_error"


def test_gate_b1_ledger_schreibfehler_kann_nicht_gruen_enden(
    lauf, tmp_path, capsys, monkeypatch
):
    """Der rote Startmarker bleibt, wenn der atomare Abschluss-Write scheitert."""
    diagnostics = tmp_path / "diag_write_error"
    argv = [
        "--portfolio", str(lauf / "bestand_gesamt.parquet"),
        "--diagnostics-dir", str(diagnostics),
    ]
    assert run_command(gate_cli.main, argv) == 0
    capsys.readouterr()

    echtes_ersetzen = gate_common.os.replace
    aufrufe = 0

    def _zweites_ersetzen_scheitert(*args, **kwargs):
        nonlocal aufrufe
        aufrufe += 1
        if aufrufe == 2:
            raise OSError("simulierter Ledger-Schreibfehler")
        return echtes_ersetzen(*args, **kwargs)

    monkeypatch.setattr(gate_common.os, "replace", _zweites_ersetzen_scheitert)
    code = run_command(gate_cli.main, argv)
    ergebnis = json.loads(capsys.readouterr().out)
    ledger = json.loads(
        (diagnostics / "bestand_validate.gate.json").read_text(encoding="utf-8")
    )

    assert aufrufe == 2
    assert code == 50
    assert ergebnis["status"] == "failed"
    assert ergebnis["errors"][-1]["code"] == "gate_ledger"
    assert ledger["status"] == "failed"
    assert ledger["summary"]["errors"][0]["code"] == "gate_attempt_incomplete"
    assert not list(diagnostics.glob(".*.tmp"))


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

    # ERH im Ledger ohne --scheiben: Usage-Fehler statt falscher
    # Bewegungs-Verletzungen (Review-Fix — die Bestandssummen waeren ohne
    # Scheiben systematisch zu niedrig):
    ohne_scheiben = [a for a in basis if "scheiben" not in a]
    code = run_command(gate_cli.main, ohne_scheiben + [
        "--ledger", str(lauf / "ledger.parquet"), "--bis", "2020-01-01",
    ])
    ergebnis = json.loads(capsys.readouterr().out)
    assert code == 2
    assert any("ERH" in e["message"] for e in ergebnis["errors"])

    # Inkonsistenter Ledger (PEX-Zeile fehlt): Contract-Fehler 20 mit
    # Fehlercode ledger, kein KeyError/Exit 50 (Review-Fix):
    pex = ledger[ledger["ereignis"] == "PEX"]
    inkonsistent = ledger.drop(index=pex.index[:1]).reset_index(drop=True)
    pfad2 = write_portfolio(inkonsistent, tmp_path / "ledger_ohne_pex.parquet")
    code = run_command(gate_cli.main, basis + [
        "--ledger", str(pfad2), "--bis", "2020-01-01",
    ])
    ergebnis = json.loads(capsys.readouterr().out)
    assert code == 20
    assert any(e["code"] == "ledger" for e in ergebnis["errors"])
    assert any("PEX-Ledger-Zeile" in e["message"] for e in ergebnis["errors"])


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


@pytest.mark.parametrize(
    "zusatzspalte",
    [
        pytest.param("unexpected_supplier_field", id="global-unbekannt"),
        pytest.param("ereignis", id="fuer-portfolio-unbekannt"),
    ],
)
def test_gate_b1_lehnt_unbekannte_physische_parquet_spalte_ab(
    lauf, tmp_path, capsys, zusatzspalte
):
    quelle = lauf / "bestand.parquet"
    tabelle = pq.read_table(quelle)
    tabelle = tabelle.append_column(
        zusatzspalte,
        pa.array(["nicht_vertragsgemaess"] * tabelle.num_rows),
    )
    pfad = tmp_path / f"bestand_mit_{zusatzspalte}.parquet"
    pq.write_table(tabelle, pfad, compression="zstd")

    code = run_command(gate_cli.main, [
        "--portfolio", str(pfad),
        "--diagnostics-dir", str(tmp_path / f"diag_{zusatzspalte}"),
    ])
    ergebnis = json.loads(capsys.readouterr().out)

    assert code == 20
    assert ergebnis["status"] == "failed"
    assert any(
        e["code"] == "portfolio"
        and "Unbekannte physische Parquet-Spalten" in e["message"]
        and zusatzspalte in e["message"]
        for e in ergebnis["errors"]
    )


@pytest.mark.parametrize(
    ("mutation", "erwartete_meldung"),
    [
        pytest.param("status_id", "status_id != 1", id="status-id-ist-nicht-eins"),
        pytest.param(
            "status_code", "status_code ausserhalb", id="status-code-ist-nicht-pol"
        ),
        pytest.param(
            "status_date",
            "status_date != insurance_start",
            id="statusdatum-ist-nicht-versicherungsbeginn",
        ),
        pytest.param(
            "status_date_monatserster",
            "status_date: nicht auf Monatsersten normalisiert",
            id="statusdatum-ist-nicht-monatserster",
        ),
    ],
)
def test_gate_b1_prueft_jede_basisstatus_invariante(
    lauf, tmp_path, capsys, mutation, erwartete_meldung
):
    bestand = read_portfolio(lauf / "bestand.parquet")
    index = bestand.index[0]
    if mutation == "status_id":
        bestand.loc[index, "status_id"] = 99
    elif mutation == "status_code":
        bestand.loc[index, "status_code"] = "STO"
    elif mutation == "status_date":
        bestand.loc[index, "status_date"] += pd.DateOffset(months=7)
    else:
        bestand.loc[index, "status_date"] += pd.DateOffset(days=1)
    pfad = write_portfolio(bestand, tmp_path / f"{mutation}.parquet")

    code = run_command(gate_cli.main, [
        "--portfolio", str(pfad),
        "--diagnostics-dir", str(tmp_path / f"diag_{mutation}"),
    ])
    ergebnis = json.loads(capsys.readouterr().out)

    assert code == 20
    assert ergebnis["status"] == "failed"
    assert any(
        e["code"] == "portfolio" and erwartete_meldung in e["message"]
        for e in ergebnis["errors"]
    )


def test_gate_b1_usage(tmp_path, capsys):
    code = run_command(gate_cli.main, ["--diagnostics-dir", str(tmp_path)])
    ergebnis = json.loads(capsys.readouterr().out)
    assert code == 2
    assert any(e["code"] == "missing_arg" for e in ergebnis["errors"])


def test_gate_b1_nennt_den_erzeuger_wenn_der_eingang_fehlt(tmp_path, capsys):
    """Nicht-Verhandelbare: ein harter Fehler nennt den Weg hinaus.

    Fehlt der Eingang von B1, genuegt 'Datei nicht gefunden' nicht — die
    Meldung muss das Kommando tragen, das die Datei herstellt
    (Systempruefung F6). Geprueft fuer beide Einstiegsfaelle: gar kein
    --portfolio und ein --portfolio, das es nicht gibt.
    """
    def _hinweise(argv):
        run_command(gate_cli.main, argv + ["--diagnostics-dir", str(tmp_path)])
        return json.loads(capsys.readouterr().out)

    for argv in ([], ["--portfolio", str(tmp_path / "gibt_es_nicht.parquet")]):
        ergebnis = _hinweise(argv)
        assert ergebnis["exit_code"] == 2
        texte = " ".join(h["hint"] for h in ergebnis["repair_hints"])
        assert "rechner_pipeline.bestand.cli_fortschreibung" in texte
        # Das Kommando ist nur brauchbar, wenn es seine Pflichtargumente
        # und das erzeugte Artefakt mitnennt:
        for teil in ("--config", "--bis", "--out-dir", "bestand_gesamt.parquet"):
            assert teil in texte, teil


def test_gate_b1_akzeptiert_beginne_nach_dem_horizont(lauf, tmp_path, capsys):
    """--bis ist der Fortschreibungs-HORIZONT, kein Stichtag.

    Der Basis-Erzeuger besiedelt das volle Verkaufsfenster jeder
    Generation in einem Batch; Vertragsbeginne nach --bis sind deshalb
    Datenmodell, nicht Datenfehler (Systempruefung F3, geprueft und
    widerlegt). Der Test haelt das fest: wer B1 um die Invariante
    'max(insurance_start) <= --bis' erweitert, macht diesen Lauf rot.
    """
    portfolio = read_portfolio(lauf / "bestand_gesamt.parquet")
    horizont = dt.date(2020, 1, 1)
    spaeter = (portfolio["insurance_start"].dt.date > horizont).sum()
    # Ohne diese Vorbedingung wuerde der Test nichts pruefen:
    assert spaeter > 0, "Beispiel-Bestand traegt keine Beginne nach dem Horizont"

    code = run_command(gate_cli.main, [
        "--portfolio", str(lauf / "bestand_gesamt.parquet"),
        "--historie", str(lauf / "historie.parquet"),
        "--scheiben", str(lauf / "scheiben.parquet"),
        "--ledger", str(lauf / "ledger.parquet"),
        "--bis", horizont.isoformat(),
        "--config", str(EXAMPLE),
        "--diagnostics-dir", str(tmp_path / "diag"),
    ])
    ergebnis = json.loads(capsys.readouterr().out)
    assert code == 0, ergebnis["errors"]
    assert ergebnis["summary"]["all_passed"] is True
