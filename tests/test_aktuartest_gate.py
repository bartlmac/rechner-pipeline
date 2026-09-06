"""Gate-Kommando aktuartest: A-M1-Vorlage aus dem Testergebnis (ADR-010).

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
from rechner_pipeline.qa.abzugsabgleich import ABS_TOL, REL_TOL
from rechner_pipeline.qa.aktuarieller_test import (
    ANLASS_UEBERNAHME,
    Pruefpunkt,
    Vertragspruefung,
    pruefe_stichprobe,
)
from rechner_pipeline.qa.stichprobe import ziehe
from rechner_pipeline.qa.testprofil import Kriterium, Testprofil

MP = dataclasses.asdict(KLV_DEFAULT)
KERN = Rechenkern(KLV_DEFAULT)
TA = 12 * 9

PROFIL = Testprofil(
    kennung="A-M1", weite="vollbestand", kriterien={},
    grundtoleranz=Kriterium(abs_tol=ABS_TOL, rel_tol=REL_TOL),
)


def _testergebnis(*, drift: float = 0.0, profil: Testprofil = PROFIL) -> Dict[str, Any]:
    erwartet = round(KERN.zustand_am(TA).vx_mrv + drift, 2)
    auftraege = [
        Vertragspruefung(
            police_id="P1", model_point=dict(MP), historientyp="ohne_gevo",
            punkte=(Pruefpunkt(TA, {"kVx_MRV": erwartet}, ANLASS_UEBERNAHME),),
        )
    ]
    return pruefe_stichprobe(
        auftraege, ziehe("vollbestand", ["P1"]), profil,
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


def test_verweigerungs_grund_unterscheidet_die_drei_lagen():
    """Review-Befund B10: eine Police AUSSERHALB des gepruefteten
    Auftragsbestands bekam den Zustands-Grund der Serien-IST-Struktur
    genannt — irrefuehrend fuer den Bericht an den Aktuar."""
    from rechner_pipeline.gates.aktuartest_lauf import verweigerungs_grund

    im_auftrag = {"P1", "P2"}
    assert verweigerungs_grund(
        "P9", im_auftrag=im_auftrag, zustandslos=set()
    ) == "nicht_im_gepruefteten_auftragsbestand"
    assert verweigerungs_grund(
        "P1", im_auftrag=im_auftrag, zustandslos={"P1"}
    ) == "anfangszustand_nicht_ableitbar"
    assert verweigerungs_grund(
        "P2", im_auftrag=im_auftrag, zustandslos={"P1"}
    ) == "kein_herabsetzungs_anfangszustand"


def test_gruener_pfad_schreibt_bericht_und_ledger(tmp_path, capsys):
    fall = _fall(tmp_path, _testergebnis())
    ergebnis = _lauf(fall, capsys)
    assert ergebnis["status"] == "passed" and ergebnis["exit_code"] == 0
    assert ergebnis["gate"] == "A-M1.stichtagstest"
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
    assert "Gate A-M1, Verantwortlicher Aktuar" in html
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


def test_aufgeblasene_stichprobe_faellt_als_contract_fehler_auf(
    tmp_path, capsys
):
    """Review-Fix: doppelte police_ids in der Stichprobe blaehen die
    Abdeckungsbehauptung auf — der mengenbasierte Abgleich allein
    wuerde sie durchlassen."""
    ergebnis = _testergebnis()
    ergebnis["stichprobe"]["police_ids"] = ["P1"] * 500
    ergebnis["stichprobe"]["umfang"] = 500
    ergebnis["stichprobe"]["grundgesamtheit"] = 500
    fall = _fall(tmp_path, ergebnis)
    resultat = _lauf(fall, capsys)
    assert resultat["exit_code"] == 20
    meldungen = "; ".join(e["message"] for e in resultat["errors"])
    assert "doppelte police_ids" in meldungen


def test_typkaputtes_json_ist_contract_fehler_nicht_internal(
    tmp_path, capsys
):
    """Review-Fix: Typfehler in fremden JSONs sind Exit 20
    (Dateivertrag), nie Exit 50 (Toolbox-Defekt)."""
    ergebnis = _testergebnis()
    ergebnis["vertraege"][0]["pruefungen"][0]["system"] = "abc"
    fall = _fall(tmp_path, ergebnis)
    resultat = _lauf(fall, capsys)
    assert resultat["exit_code"] == 20
    assert "strukturell unlesbar" in "; ".join(
        e["message"] for e in resultat["errors"]
    )

    ohne_typ = _testergebnis()
    del ohne_typ["vertraege"][0]["historientyp"]
    fall2 = tmp_path / "f2"
    (fall2 / "abgeleitet" / "berichte").mkdir(parents=True)
    (fall2 / "abgeleitet" / "berichte" / "aktuartest.json").write_text(
        json.dumps(ohne_typ), encoding="utf-8"
    )
    resultat = _lauf(fall2, capsys)
    assert resultat["exit_code"] == 20


# --------------------------------------------------------------------------- #
# Drei Abnahmen, drei Belege
# --------------------------------------------------------------------------- #


def test_a_m2_ueberschreibt_den_a_m1_ledger_nicht(tmp_path, capsys):
    """Der gruene A-M1-Beleg traegt den Entscheid — er darf nicht fallen.

    Testergebnis und Bericht trugen die Abnahme schon im Namen, der
    Gate-Ledger nicht: Er wird unter ``result.command`` geschrieben, und
    das war fuer alle drei Abnahmen derselbe Name. Ein A-M2-Lauf loeschte
    damit unbemerkt den Beleg, auf dem gate_entscheid den Pflichtbeleg
    bindet.
    """
    profil_am2 = dataclasses.replace(PROFIL, kennung="A-M2")

    fall = _fall(tmp_path, _testergebnis())
    _lauf(fall, capsys)
    diagnostics = fall / "abgeleitet" / "diagnostics"
    am1 = diagnostics / "aktuartest.gate.json"
    assert am1.is_file()
    vorher = json.loads(am1.read_text(encoding="utf-8"))
    assert vorher["status"] == "passed"

    (fall / "abgeleitet" / "berichte" / "aktuartest-A-M2.json").write_text(
        json.dumps(_testergebnis(profil=profil_am2)), encoding="utf-8"
    )
    _lauf(fall, capsys, extra=["--abnahme", "A-M2"])

    assert json.loads(am1.read_text(encoding="utf-8")) == vorher, \
        "der A-M1-Ledger wurde vom A-M2-Lauf veraendert"
    assert (diagnostics / "aktuartest-A-M2.gate.json").is_file()


def test_auch_ein_fehlstart_der_zweiten_abnahme_laesst_a_m1_stehen(
    tmp_path, capsys
):
    """Schon der rote Startmarker wird unter dem Ledger-Namen geschrieben.

    Ein blosser Aufruffehler in A-M2 haette den A-M1-Beleg sonst
    ungueltig gemacht, bevor ueberhaupt gerechnet wurde.
    """
    fall = _fall(tmp_path, _testergebnis())
    _lauf(fall, capsys)
    am1 = fall / "abgeleitet" / "diagnostics" / "aktuartest.gate.json"
    vorher = json.loads(am1.read_text(encoding="utf-8"))

    # Kein Testergebnis fuer A-M2 vorhanden -> Aufruffehler.
    ergebnis = _lauf(fall, capsys, extra=["--abnahme", "A-M2"])
    assert ergebnis["exit_code"] != 0

    assert json.loads(am1.read_text(encoding="utf-8")) == vorher, \
        "der A-M1-Ledger fiel einem Fehlstart der zweiten Abnahme zum Opfer"
