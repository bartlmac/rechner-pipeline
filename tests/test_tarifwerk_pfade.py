"""Tarifwerk und Kernstand nach dem Umzug nach plv/ (ADR-028, Nachtrag 2026-10-09).

Gemessen vor dem Bau: Ein Beleg gegen einen Stand der frueheren Ordnung
(Tarifplaene unter docs/tarifplaene, Configs unter configs/) lief mit Exit 0
durch und sagte "Tarifwerk vorher leer", alle Tarifplaene und Generationen
"neu". Die Erstabnahme einer neuen Welt verglich so mit ``e8fa2b4``.

Was hier gehalten wird, gegen eigene kleine Git-Repos (die CI klont flach):

* ``konfig_pfade`` nimmt nur die Configs direkt unter ``plv/configs``.
* A-T1 und A-K2 verweigern einen Vergleichsstand, dem ihr Gegenstand an
  den heutigen Pfaden fehlt, mit einem Satz, der den Ausweg nennt.
* Gegen einen Stand der heutigen Ordnung ist ein unveraendertes Tarifwerk
  ein gueltiger Beleg: ``veraendert`` ist falsch, jeder Teil unveraendert.

Knoten: system/entscheid
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from rechner_pipeline.gates import kernstand_belegen as kb
from rechner_pipeline.gates import tarifwerk_belegen as tb
from rechner_pipeline.models import kernabnahme as ka
from rechner_pipeline.models import tarifwerkabnahme as tw

PLAN = "# KLV\n\nDer Tarif verspricht.\n"
CONFIG = """[[generation]]
name = "KLV-T"
knoten = "klv/plv_test"
zins = 0.01
"""


def _git(repo: Path, *argv: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=Pruefung", "-c", "user.email=p@example.invalid",
         "-c", "commit.gpgsign=false", *argv],
        cwd=repo, capture_output=True, text=True, check=True).stdout


def _schreibe(pfad: Path, text: str) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(text, encoding="utf-8")


def _repo(tmp_path: Path, plaene: str, configs: str, grundsatz: str) -> tuple:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--quiet", "--initial-branch=main")
    _schreibe(repo / plaene / "klv.md", PLAN)
    _schreibe(repo / configs / "bestand_test.toml", CONFIG)
    _schreibe(repo / grundsatz, "# Grundsatz\n")
    _schreibe(repo / ka.KERN_PAKET / "__init__.py", '__version__ = "1.0.0"\n')
    _schreibe(repo / ka.KERN_REFERENZWERTE / "r.json", "{}\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "--quiet", "-m", "Stand")
    return repo, _git(repo, "rev-parse", "HEAD").strip()


def test_konfig_pfade_nimmt_nur_configs_direkt_unter_plv_configs():
    namen = [f"{tw.CONFIG_VERZEICHNIS}/bestand_klv.toml",
             f"{tw.CONFIG_VERZEICHNIS}/unter/bestand_x.toml",
             f"{tw.CONFIG_VERZEICHNIS}/README.md",
             "configs/bestand_klv.toml"]
    assert tw.konfig_pfade(namen) == [f"{tw.CONFIG_VERZEICHNIS}/bestand_klv.toml"]
    assert tw.tarifplan_pfade([f"{tw.TARIFPLAENE}/klv.md", "docs/tarifplaene/klv.md"]) == [
        f"{tw.TARIFPLAENE}/klv.md"]


def test_gegen_die_heutige_ordnung_ist_ein_unveraendertes_tarifwerk_gueltig(tmp_path):
    repo, stand = _repo(tmp_path, tw.TARIFPLAENE, tw.CONFIG_VERZEICHNIS,
                        ka.kernstand_pfade()[-1])
    beleg = tb.baue_aenderungsbeleg(repo, stand, "Erstabnahme")
    assert beleg["veraendert"] is False and beleg["stand_vorher"] == beleg["stand"]
    assert [p["zustand"] for p in beleg["tarifplaene"]] == ["unveraendert"]
    assert [g["zustand"] for g in beleg["generationen"]] == ["unveraendert"]


def test_ein_vergleichsstand_der_frueheren_ordnung_wird_verweigert(tmp_path):
    repo, alt = _repo(tmp_path, "docs/tarifplaene", "configs",
                      "docs/mathematik/grundsatzdokumentation.md")
    with pytest.raises(tw.TarifwerkFehler, match="frueherer Ordnung"):
        tb.baue_aenderungsbeleg(repo, alt, "Erstabnahme")
    with pytest.raises(kb.KernstandFehler, match="frueherer Ordnung"):
        kb.baue_aenderungsbeleg(repo, alt, "Erstabnahme")


def test_die_verweigerung_haengt_an_jedem_teil(tmp_path):
    """Fehlt nur die Config am heutigen Ort, ist der Stand ebenso unbrauchbar."""
    repo, alt = _repo(tmp_path, tw.TARIFPLAENE, "configs", ka.kernstand_pfade()[-1])
    with pytest.raises(tw.TarifwerkFehler, match="keine Configs"):
        tb.baue_aenderungsbeleg(repo, alt, "Erstabnahme")
