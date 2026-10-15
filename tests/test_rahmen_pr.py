"""Das Kommando fuer den Pull Request des Rahmens (werkzeuge/rahmen_pr.py).

Der Rahmen der Seite aendert sich nur per Pull Request nach plv-fiktion; den
Betriebsteil rendert der Workflow mit dem Code, den CODESTAND nennt
(Entscheid des Maintainers 09.10.2026, Weg C). Das Kommando schreibt CODESTAND
selbst, aus dem Commit, aus dem es baut. Gebaut wird hier nicht wirklich
(``_baue`` ist ersetzt); geprueft wird, was in den Zweig kommt und wann es
anhaelt.

Knoten: klv
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "werkzeuge"))

import rahmen_pr as rp  # noqa: E402

STAND = "b" * 40


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


@pytest.fixture()
def klon(tmp_path: Path) -> Path:
    """Ein Klon wie plv-fiktion: main traegt einen Rahmen und einen alten Stand."""
    repo = tmp_path / "plv-fiktion"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "test")
    for rel, text in (("index.md", "# Alt\n"), ("veraltet.md", "# Weg\n"),
                      ("CODESTAND", "a" * 40 + "\n")):
        (repo / rel).write_text(text, encoding="utf-8")
    _git(repo, "add", "index.md", "veraltet.md", "CODESTAND")
    _git(repo, "commit", "-q", "-m", "Seite vom Vortag")
    return repo


def _seite(ziel: Path) -> None:
    """Was auftritt.py baut: Rahmen und Betriebsteil."""
    for rel, text in (("index.md", "# Neu\n"), ("_config.yml", "baseurl: /plv-fiktion\n"),
                      (".github/workflows/seite.yml", "name: Seite\n"),
                      ("betrieb/index.md", "# Bestandsführung\n"),
                      ("betrieb/plv/index.html", "<p>Bestand heute</p>\n")):
        (ziel / rel).parent.mkdir(parents=True, exist_ok=True)
        (ziel / rel).write_text(text, encoding="utf-8")


def _argv(klon: Path, arbeit: Path, *extra: str):
    return ["--klon", str(klon), "--arbeit", str(arbeit), "--fall", "f", "--name", "n",
            "--film", "film.mp4", "--stands-paket", "p", "--anker", "a.jsonl",
            "--ab1", "A-B1.json", *extra]


@pytest.fixture()
def gebaut(monkeypatch):
    """Ein Bau, der die Seite in --out legt, und ein sauberer Codestand."""
    aufrufe = []

    def baue(kommando, umgebung):
        aufrufe.append((kommando, umgebung))
        _seite(Path(kommando[kommando.index("--out") + 1]))
        return 0
    monkeypatch.setattr(rp, "_baue", baue)
    monkeypatch.setattr(rp, "codestand", lambda: STAND)
    return aufrufe


def test_der_zweig_traegt_genau_den_rahmen_und_codestand(klon, tmp_path, gebaut, capsys):
    """Der Rahmen ohne betrieb/, CODESTAND aus dem Commit, aus dem gebaut
    wurde; was im Rahmen nicht mehr vorkommt, faellt weg. Der Klon selbst
    bleibt auf main und sauber: Der Zweig hat einen eigenen Arbeitsbaum."""
    assert rp.main(_argv(klon, tmp_path / "arbeit", "--zweig", "beitrag/rahmen-probe",
                         "--anhang", "Zeile am Ende")) == 0
    zweig = "beitrag/rahmen-probe"
    dateien = set(_git(klon, "ls-tree", "-r", "--name-only", zweig).splitlines())
    assert dateien == {"index.md", "_config.yml", ".github/workflows/seite.yml", "CODESTAND"}
    assert _git(klon, "show", f"{zweig}:CODESTAND") == STAND
    assert _git(klon, "show", f"{zweig}:index.md") == "# Neu"
    botschaft = _git(klon, "log", "-1", "--format=%B", zweig)
    assert f"gebaut aus rechner-pipeline {STAND[:7]}" in botschaft and "Zeile am Ende" in botschaft
    assert _git(klon, "rev-parse", f"{zweig}~1") == _git(klon, "rev-parse", "main")
    assert _git(klon, "branch", "--show-current") == "main" and not _git(klon, "status", "--porcelain")
    kommando, umgebung = gebaut[0]
    assert kommando[kommando.index("--teil") + 1] == "beide"
    assert umgebung["PYTHONPATH"] == str(rp.CODE / "src"), "gebaut wird mit dem Code dieses Baums"
    assert "Push, Pull Request und Merge macht der Maintainer." in capsys.readouterr().out


@pytest.mark.parametrize("fall, erwartet", [
    ("fremder-zweig", "nur unter beitrag/"),
    ("zweig-besteht", "besteht im Klon schon"),
    ("klon-unsauber", "nicht sauber"),
    ("bau-scheitert", "Exit 1"),
    ("nichts-neu", "nichts zu beantragen"),
])
def test_es_haelt_an_statt_zu_raten(klon, tmp_path, gebaut, monkeypatch, capsys, fall, erwartet):
    zweig = "beitrag/rahmen-probe"
    if fall == "fremder-zweig":
        zweig = "rahmen-probe"
    if fall == "zweig-besteht":
        _git(klon, "branch", zweig)
    if fall == "klon-unsauber":
        (klon / "index.md").write_text("# Von Hand\n", encoding="utf-8")
    if fall == "bau-scheitert":
        monkeypatch.setattr(rp, "_baue", lambda kommando, umgebung: 1)
    if fall == "nichts-neu":
        # Der Rahmen gleicht main schon (CODESTAND eingeschlossen).
        def gleich(kommando, umgebung):
            ziel = Path(kommando[kommando.index("--out") + 1])
            ziel.mkdir(parents=True)
            for rel in ("index.md", "veraltet.md"):
                (ziel / rel).write_bytes((klon / rel).read_bytes())
            return 0
        monkeypatch.setattr(rp, "_baue", gleich)
        monkeypatch.setattr(rp, "codestand", lambda: "a" * 40)
    assert rp.main(_argv(klon, tmp_path / "arbeit", "--zweig", zweig)) == 1
    assert erwartet in capsys.readouterr().err
    if fall != "zweig-besteht":
        assert not _git(klon, "branch", "--list", "beitrag/*")
    assert _git(klon, "branch", "--show-current") == "main"


def test_codestand_nur_aus_einem_commit(tmp_path):
    """Traegt der Codebaum Aenderungen ausserhalb eines Commits, gibt es den
    Stand nicht, den CODESTAND nennen muesste."""
    code = tmp_path / "code"
    code.mkdir()
    _git(code, "init", "-q", "-b", "main")
    _git(code, "config", "user.email", "test@example.invalid")
    _git(code, "config", "user.name", "test")
    (code / "a.py").write_text("x = 1\n", encoding="utf-8")
    _git(code, "add", "a.py")
    _git(code, "commit", "-q", "-m", "a")
    assert rp.codestand(code) == _git(code, "rev-parse", "HEAD")
    (code / "a.py").write_text("x = 2\n", encoding="utf-8")
    with pytest.raises(rp.Halt, match="ausserhalb eines Commits"):
        rp.codestand(code)
    _git(code, "checkout", "-q", "a.py")
    (code / "neu.md").write_text("# neu\n", encoding="utf-8")
    with pytest.raises(rp.Halt, match="ausserhalb eines Commits"):
        rp.codestand(code)
