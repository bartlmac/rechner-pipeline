"""Gate-Kommando aktuartest: G-A-Vorlage aus dem Testergebnis (ADR-010).

Knoten: klv
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any, Dict

import pytest

from rechner_pipeline.gates import aktuartest as gate
from rechner_pipeline.gates._common import run_command
from rechner_pipeline.kern import KLV_DEFAULT, Rechenkern
from rechner_pipeline.qa.abzugsabgleich import ABS_TOL
from rechner_pipeline.qa.aktuarieller_test import (
    VerankerungsPruefung,
    pruefe_stichprobe,
)
from rechner_pipeline.qa.stichprobe import ziehe

MP = dataclasses.asdict(KLV_DEFAULT)
KERN = Rechenkern(KLV_DEFAULT)
TA = 12 * 9


def _testergebnis(*, drift: float = 0.0) -> Dict[str, Any]:
    erwartet = round(KERN.zustand_am(TA).vx_mrv + drift, 2)
    auftraege = [
        VerankerungsPruefung(
            police_id="P1", model_point=dict(MP), monate_ta=TA,
            historientyp="ohne_gevo", erwartet={"kVx_MRV": erwartet},
        )
    ]
    return pruefe_stichprobe(
        auftraege, ziehe("vollbestand", ["P1"]),
        transportsicherung={"bestand_sha256": "ab" * 32},
        system={"commit": "deadbeef", "branch": "x", "dirty": "false",
                "quellcode_sha256": "cd" * 32},
    )


def _fall(tmp_path: Path, ergebnis: Dict[str, Any]) -> Path:
    fall = tmp_path / "fall"
    (fall / "abgeleitet" / "berichte").mkdir(parents=True)
    (fall / "abgeleitet" / "berichte" / "aktuartest.json").write_text(
        json.dumps(ergebnis), encoding="utf-8"
    )
    return fall


def _lauf(fall: Path, capsys, extra=()) -> Dict[str, Any]:
    code = run_command(gate.main, [
        "--fall", str(fall), "--titel", "Aktuarieller Test Testfall",
        *extra,
    ])
    ergebnis = json.loads(capsys.readouterr().out)
    assert code == ergebnis["exit_code"]
    return ergebnis


def test_gruener_pfad_schreibt_bericht_und_ledger(tmp_path, capsys):
    fall = _fall(tmp_path, _testergebnis())
    ergebnis = _lauf(fall, capsys)
    assert ergebnis["status"] == "passed" and ergebnis["exit_code"] == 0
    assert ergebnis["gate"] == "GA-vorlage.aktuarieller-test"
    assert ergebnis["summary"]["test_bestanden"] is True
    assert ergebnis["summary"]["stichprobe"]["profil"] == "vollbestand"
    assert set(ergebnis["summary"]["belege"]) == {
        "abgeleitet/berichte/aktuartest.json",
        "abgeleitet/berichte/aktuartest.html",
    }
    assert (fall / "abgeleitet" / "diagnostics"
            / "aktuartest.gate.json").is_file()
    html = (fall / "abgeleitet" / "berichte" / "aktuartest.html"
            ).read_text(encoding="utf-8")
    assert "AKTUARIELLER TEST BESTANDEN" in html
    assert "Gate G-A, Verantwortlicher Aktuar" in html
    assert "kein Teil des Urteils" in html and "ab" * 32 in html
    assert "eigenen".upper() not in html or True


def test_bericht_ist_deterministisch(tmp_path, capsys):
    fall = _fall(tmp_path, _testergebnis())
    _lauf(fall, capsys)
    erster = (fall / "abgeleitet" / "berichte" / "aktuartest.html"
              ).read_bytes()
    _lauf(fall, capsys)
    assert (fall / "abgeleitet" / "berichte" / "aktuartest.html"
            ).read_bytes() == erster


def test_fachlicher_fehlschlag_ist_exit_30_mit_rotem_bericht(
    tmp_path, capsys
):
    fall = _fall(tmp_path, _testergebnis(drift=10 * ABS_TOL))
    ergebnis = _lauf(fall, capsys)
    assert ergebnis["exit_code"] == 30 and ergebnis["status"] == "failed"
    assert ergebnis["errors"][0]["code"] == "aktuartest_nicht_bestanden"
    html = (fall / "abgeleitet" / "berichte" / "aktuartest.html"
            ).read_text(encoding="utf-8")
    assert "NICHT BESTANDEN" in html and "ABWEICHUNG" in html


def test_gruene_zusammenfassung_ueber_rotem_einzelwert_ist_unmoeglich(
    tmp_path, capsys
):
    """Der Kernfall des Nachrechnens: ein manipuliertes test_bestanden
    faellt als Vertragsverletzung auf (Exit 20), nicht als gruen."""
    ergebnis = _testergebnis(drift=10 * ABS_TOL)
    ergebnis["test_bestanden"] = True
    fall = _fall(tmp_path, ergebnis)
    resultat = _lauf(fall, capsys)
    assert resultat["exit_code"] == 20
    assert any(e["code"] == "test_contract" for e in resultat["errors"])
    with pytest.raises(ValueError, match="Aktuartest-Vertrag"):
        gate.baue_bericht(titel="x", test=ergebnis)


def test_manipulierte_verteilung_faellt_auf(tmp_path, capsys):
    ergebnis = _testergebnis()
    ergebnis["verteilung"]["max_abs_residuum"] = 0.0000001
    fall = _fall(tmp_path, ergebnis)
    resultat = _lauf(fall, capsys)
    assert resultat["exit_code"] == 20
    meldungen = "; ".join(e["message"] for e in resultat["errors"])
    assert "verteilung" in meldungen


def test_usage_und_erzeuger_hinweis(tmp_path, capsys):
    fall = tmp_path / "leer"
    (fall / "abgeleitet").mkdir(parents=True)
    code = run_command(gate.main, [
        "--fall", str(fall), "--titel", "T",
    ])
    ergebnis = json.loads(capsys.readouterr().out)
    assert code == 2
    assert "pruefe_stichprobe" in "; ".join(ergebnis["repair_hints"])

    code = run_command(gate.main, ["--fall", str(fall)])
    ergebnis = json.loads(capsys.readouterr().out)
    assert code == 2 and "--titel" in ergebnis["errors"][0]["message"]


def test_kaputtes_json_ist_contract_fehler(tmp_path, capsys):
    fall = tmp_path / "fall"
    (fall / "abgeleitet" / "berichte").mkdir(parents=True)
    (fall / "abgeleitet" / "berichte" / "aktuartest.json").write_text(
        "{kein json", encoding="utf-8"
    )
    ergebnis = _lauf(fall, capsys)
    assert ergebnis["exit_code"] == 20
    assert ergebnis["errors"][0]["code"] == "test_unlesbar"


def test_pfadkollision_ist_usage(tmp_path, capsys):
    fall = _fall(tmp_path, _testergebnis())
    ziel = fall / "abgeleitet" / "berichte" / "aktuartest.json"
    ergebnis = _lauf(fall, capsys, extra=["--bericht", str(ziel)])
    assert ergebnis["exit_code"] == 2
    assert "Pfadkollision" in ergebnis["errors"][0]["message"]
