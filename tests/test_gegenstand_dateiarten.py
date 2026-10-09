"""Kernstand und Tarifwerk zaehlen nur die Dateien ihres Gegenstands (2026-10-09).

Vorher las der lebende Stand jede Datei unter den Verzeichnissen des
Gegenstands, auch eine, die git nicht sieht. Die Doku-Engine legte beim
Rendern ``klv.pdf`` neben ``klv.md``, ``.gitignore`` versteckte sie, und das
Tarifwerk war still "anders": Das Nachfahren hielt mit "ein anderes Tarifwerk
als im festgehaltenen Fall" an, obwohl git keine Aenderung zeigte. Eine
``.DS_Store`` des Finders wirkte ebenso, sinngemaess im Kern.

Was hier gehalten wird:

* Jede Datei, die git unter den Gegenstaenden verfolgt, zaehlt; eine neue
  Dateiart haelt hier an, statt still aus dem Fingerabdruck zu fallen.
* Fremde Dateien daneben aendern keinen Fingerabdruck, eine Aenderung an
  einer Datei des Gegenstands schon (Positivkontrolle).
* Ein Beleg gegen den eigenen Stand bleibt "unveraendert", auch wenn fremde
  Dateien im Arbeitsbaum liegen: Commit- und Arbeitsbaumseite lesen dieselbe
  Auswahl.

Knoten: system/entscheid
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from rechner_pipeline.gates import kernstand_belegen as kb
from rechner_pipeline.gates import tarifwerk_belegen as tb
from rechner_pipeline.models import kernabnahme as ka
from rechner_pipeline.models import tarifwerkabnahme as tw

REPO_ROOT = Path(__file__).resolve().parents[1]
GRUNDSATZ = ka.kernstand_pfade()[-1]

#: Was neben den Gegenstaenden liegen kann, ohne zu ihnen zu gehoeren.
FREMDE = (
    f"{ka.KERN_PAKET}/.DS_Store",
    f"{ka.KERN_PAKET}/rechenkern.py~",
    f"{ka.KERN_REFERENZWERTE}/.DS_Store",
    f"{tw.TARIFPLAENE}/klv.pdf",
    f"{tw.TARIFPLAENE}/klv.typ",
    f"{tw.TARIFPLAENE}/.DS_Store",
)


def _git(repo: Path, *argv: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=Pruefung", "-c", "user.email=p@example.invalid",
         "-c", "commit.gpgsign=false", *argv],
        cwd=repo, capture_output=True, text=True, check=True).stdout


def _fingerabdruecke(wurzel: Path) -> dict:
    return {"kern": kb.kern_modul_hash(wurzel), "referenzwerte": kb.referenzwerte_hash(wurzel),
            "kernstand": kb.kernstand_hash(wurzel), "tarifwerk": tb.lebender_stand(wurzel)}


def _gegenstaende_kopieren(ziel: Path) -> None:
    for pfad in (ka.KERN_PAKET, ka.KERN_REFERENZWERTE, tw.TARIFPLAENE, tw.CONFIG_VERZEICHNIS):
        shutil.copytree(REPO_ROOT / pfad, ziel / pfad,
                        ignore=shutil.ignore_patterns("__pycache__"))
    (ziel / GRUNDSATZ).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(REPO_ROOT / GRUNDSATZ, ziel / GRUNDSATZ)


def test_jede_verfolgte_datei_des_gegenstands_zaehlt():
    verfolgt = _git(REPO_ROOT, "ls-files", "--", ka.KERN_PAKET, ka.KERN_REFERENZWERTE,
                    GRUNDSATZ).split()
    assert len(verfolgt) > 3
    assert [p for p in verfolgt if not ka.gehoert_zum_kernstand(p)] == []
    plaene = _git(REPO_ROOT, "ls-files", "--", tw.TARIFPLAENE).split()
    assert plaene and tw.tarifplan_pfade(plaene) == sorted(plaene)


def test_fremde_dateien_aendern_keinen_fingerabdruck(tmp_path):
    _gegenstaende_kopieren(tmp_path)
    vorher = _fingerabdruecke(tmp_path)
    assert all(vorher.values())
    for pfad in FREMDE:
        (tmp_path / pfad).write_bytes(b"fremd")
    assert _fingerabdruecke(tmp_path) == vorher

    # Positivkontrolle: Dateien des Gegenstands zaehlen weiter.
    klv = tmp_path / tw.TARIFPLAENE / "klv.md"
    klv.write_bytes(klv.read_bytes() + b"\n")
    assert tb.lebender_stand(tmp_path) != vorher["tarifwerk"]
    init = tmp_path / ka.KERN_PAKET / "__init__.py"
    init.write_bytes(init.read_bytes() + b"\n")
    assert kb.kern_modul_hash(tmp_path) != vorher["kern"]
    assert kb.kernstand_hash(tmp_path) != vorher["kernstand"]


def _repo(tmp_path: Path) -> tuple:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--quiet", "--initial-branch=main")
    for pfad, text in ((f"{tw.TARIFPLAENE}/klv.md", "# KLV\n"),
                       (f"{tw.CONFIG_VERZEICHNIS}/bestand_test.toml",
                        '[[generation]]\nname = "KLV-T"\nknoten = "klv/plv_test"\nzins = 0.01\n'),
                       (GRUNDSATZ, "# Grundsatz\n"),
                       (f"{ka.KERN_PAKET}/__init__.py", '__version__ = "1.0.0"\n'),
                       (f"{ka.KERN_REFERENZWERTE}/r.json", "{}\n"),
                       (".gitignore", ".DS_Store\n")):
        (repo / pfad).parent.mkdir(parents=True, exist_ok=True)
        (repo / pfad).write_text(text, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "--quiet", "-m", "Stand")
    return repo, _git(repo, "rev-parse", "HEAD").strip()


def test_ein_beleg_gegen_den_eigenen_stand_bleibt_unveraendert(tmp_path):
    """Fremde Dateien im Arbeitsbaum: ignoriert (.DS_Store) wie nicht
    ignoriert (eine PDF, eine Notiz im Kern)."""
    repo, stand = _repo(tmp_path)
    for pfad in (f"{ka.KERN_PAKET}/.DS_Store", f"{ka.KERN_PAKET}/notizen.txt",
                 f"{tw.TARIFPLAENE}/klv.pdf"):
        (repo / pfad).write_bytes(b"fremd")
    tarifwerk = tb.baue_aenderungsbeleg(repo, stand, "Erstabnahme")
    assert tarifwerk["veraendert"] is False
    assert [p["pfad"] for p in tarifwerk["tarifplaene"]] == [f"{tw.TARIFPLAENE}/klv.md"]
    kern = kb.baue_aenderungsbeleg(repo, stand, "Erstabnahme")
    assert kern["veraendert"] is False
