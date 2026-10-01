"""Der Baumwaechter sieht, was er sehen soll — und sagt, wenn er nichts sieht.

Die Tests bauen einen eigenen kleinen Git-Baum unter ``tmp_path`` und
veraendern IHN, nie den Baum der Suite (das waere der Fehler, den der
Waechter meldet).

Knoten: system/architektur
"""

from __future__ import annotations

import ast
import subprocess
import tempfile
import time
from pathlib import Path

import pytest

from tests.baumwaechter import Baumwaechter, abweichung, urteil

TESTS = Path(__file__).resolve().parent


def _git_baum(wurzel: Path) -> Path:
    baum = wurzel / "baum"
    baum.mkdir()
    subprocess.run(["git", "init", "-q", str(baum)], check=True, capture_output=True)
    return baum


def _warte_auf_fund(waechter: Baumwaechter, sekunden: float = 5.0) -> None:
    ende = time.monotonic() + sekunden
    while not waechter.funde and time.monotonic() < ende:
        time.sleep(0.01)


def test_eine_datei_die_waehrend_des_laufs_entsteht_ist_ein_fund(tmp_path):
    baum = _git_baum(tmp_path)
    waechter = Baumwaechter(baum, abstand=0.02)
    waechter.start()
    assert waechter.aktiv and waechter.ausgang == ""
    (baum / "liegengeblieben.txt").write_text("x", encoding="utf-8")
    _warte_auf_fund(waechter)
    waechter.stop()
    assert waechter.funde, "die Datei blieb unbemerkt"
    assert waechter.funde[0][2] == ["+ ?? liegengeblieben.txt"]
    assert urteil(waechter, 0) == 1
    assert "veraendert" in waechter.bericht()[0] and "liegengeblieben.txt" in waechter.bericht()[1]


def test_ein_verzeichnis_das_hinter_sich_aufraeumt_ist_trotzdem_ein_fund(tmp_path):
    """Die Bauform des Verursachers vom 2026-10-01: ein Kontextmanager im
    Repo-Root. Vorher und nachher ist der Baum gleich — ein Vergleich je
    Test saehe nichts; der Zeitgeber sieht das Dazwischen."""
    baum = _git_baum(tmp_path)
    waechter = Baumwaechter(baum, abstand=0.02)
    waechter.start()
    with tempfile.TemporaryDirectory(prefix=".arbeit-", dir=baum) as tmp:
        (Path(tmp) / "fall.json").write_text("{}", encoding="utf-8")
        _warte_auf_fund(waechter)
    assert waechter.lies() == waechter.ausgang  # hinterher wieder wie vorher
    waechter.stop()
    assert waechter.funde and waechter.funde[0][2][0].startswith("+ ?? .arbeit-")


def test_verglichen_wird_gegen_den_sitzungsbeginn_nicht_gegen_leer(tmp_path):
    """Ein schon schmutziger Baum ist kein Fund; eine WEITERE Aenderung ist
    einer — sonst bliebe der Verursacher auf dem Entwicklerrechner unsichtbar."""
    baum = _git_baum(tmp_path)
    (baum / "schon-da.txt").write_text("x", encoding="utf-8")
    waechter = Baumwaechter(baum, abstand=0.02)
    waechter.start()
    assert waechter.ausgang == "?? schon-da.txt\n"
    time.sleep(0.15)
    assert not waechter.funde and waechter.lesungen > 0
    (baum / "neu.txt").write_text("x", encoding="utf-8")
    _warte_auf_fund(waechter)
    waechter.stop()
    assert waechter.funde[0][2] == ["+ ?? neu.txt"]


def test_ein_ruhiger_baum_ist_kein_fund_und_der_bericht_nennt_die_lesungen(tmp_path):
    baum = _git_baum(tmp_path)
    waechter = Baumwaechter(baum, abstand=0.02)
    waechter.start()
    time.sleep(0.15)
    waechter.stop()
    assert waechter.funde == [] and waechter.lesungen > 0
    assert urteil(waechter, 0) == 0 and urteil(waechter, 5) == 5
    (zeile,) = waechter.bericht()
    assert f"{waechter.lesungen} Lesungen" in zeile


def test_ohne_git_baum_sagt_der_waechter_dass_er_nicht_prueft(tmp_path):
    """Ein Detektor, der nichts sehen kann, sagt das — er meldet nicht gruen."""
    waechter = Baumwaechter(tmp_path / "gibtsnicht", abstand=0.02)
    waechter.start()
    waechter.stop()
    assert not waechter.aktiv
    (zeile,) = waechter.bericht()
    assert "NICHT AKTIV" in zeile and "nicht geprueft" in zeile


def test_ein_roter_lauf_bleibt_rot_und_ein_gruener_mit_fund_wird_rot(tmp_path):
    waechter = Baumwaechter(tmp_path)
    assert urteil(waechter, 0) == 0
    waechter.funde.append((1.0, "12:00:00", ["+ ?? x"]))
    assert urteil(waechter, 0) == 1
    assert urteil(waechter, 2) == 2


def test_abweichung_nennt_hinzugekommenes_und_verschwundenes():
    assert abweichung("?? a\n M b\n", "?? a\n?? c\n") == ["+ ?? c", "-  M b"]
    assert abweichung("", "") == []


def test_die_suite_haengt_den_waechter_an_ihren_lauf():
    """Die drei Haken stehen in conftest.py und rufen den Waechter — ein
    Waechter, den niemand startet, ist ein Detektor ohne Treffer."""
    baum = ast.parse((TESTS / "conftest.py").read_text(encoding="utf-8"))
    haken = {k.name: ast.unparse(k) for k in baum.body if isinstance(k, ast.FunctionDef)}
    assert "Baumwaechter(" in haken["pytest_sessionstart"]
    assert "workerinput" in haken["pytest_sessionstart"]
    assert "urteil(" in haken["pytest_sessionfinish"]
    assert "bericht()" in haken["pytest_terminal_summary"]


def test_der_waechter_dieses_laufs_ist_aktiv(request):
    """Positivkontrolle am echten Lauf: In einem Git-Baum laeuft der Waechter
    (im Steuerprozess; ein xdist-Worker traegt keinen)."""
    if hasattr(request.config, "workerinput"):
        assert getattr(request.config, "_baumwaechter", None) is None
        return
    waechter = request.config._baumwaechter
    if (TESTS.parent / ".git").exists():
        assert waechter.aktiv
    else:
        assert "NICHT AKTIV" in waechter.bericht()[0]
