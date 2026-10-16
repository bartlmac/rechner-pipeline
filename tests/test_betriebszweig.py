"""Was der Workflow von plv-fiktion aus dem Zweig betrieb nimmt (werkzeuge/betriebszweig.py),
und der Workflow selbst (plv/seite/.github/workflows/seite.yml).

Weg C (Entscheid des Maintainers 09.10.2026): Automatisch aendert sich nur
``betrieb/``. Der Zweig traegt genau, was die Routine ablegt; ausserhalb von
``betrieb/`` gleicht der gebaute Baum dem Rahmen aus main. Der Workflow
liefert nur aus main aus, startet nicht bei einem Push auf betrieb und
pinnt jede Action auf einen Commit.

Knoten: system/betrieb
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "werkzeuge"))

import betriebszweig as bz  # noqa: E402

WORKFLOW = ROOT / "plv" / "seite" / ".github" / "workflows" / "seite.yml"


def _zweig(wurzel: Path) -> Path:
    paket = wurzel / "paket"
    paket.mkdir(parents=True)
    (paket / "stand.json").write_text(json.dumps({"dateien": {
        "index.html": "a" * 64, "protokoll.jsonl": "b" * 64, "laufmanifest.json": "c" * 64,
        "tagesjournal.parquet": "d" * 64, "abschluesse/abschluss_2026-10-01.parquet": "e" * 64}}),
        encoding="utf-8")
    for name in ("index.html", "protokoll.jsonl", "laufmanifest.json"):
        (paket / name).write_text("x", encoding="utf-8")
    (wurzel / "anker.jsonl").write_text("{}\n", encoding="utf-8")
    (wurzel / "A-B1.json").write_text("{}", encoding="utf-8")
    (wurzel / ".git").mkdir()
    (wurzel / ".git" / "HEAD").write_text("ref: refs/heads/betrieb\n", encoding="utf-8")
    return wurzel


@pytest.mark.parametrize("anlegen, befund", [
    (lambda z: (z / ".github" / "workflows").mkdir(parents=True)
     or (z / ".github" / "workflows" / "x.yml").write_text("on: push", encoding="utf-8"),
     ".github/workflows/x.yml: ein Workflow-Verzeichnis im Zweig betrieb"),
    (lambda z: (z / "paket" / ".github").mkdir()
     or (z / "paket" / ".github" / "a").write_text("", encoding="utf-8"),
     "paket/.github/a: ein Workflow-Verzeichnis im Zweig betrieb"),
    (lambda z: (z / "README.md").write_text("", encoding="utf-8"), "README.md: nicht erlaubt"),
    (lambda z: (z / "paket" / "tagesjournal.parquet").write_bytes(b"PAR1"),
     "paket/tagesjournal.parquet: keine oeffentliche Datei des Pakets"),
    (lambda z: (z / "paket" / "abschluesse").mkdir()
     or (z / "paket" / "abschluesse" / "abschluss_2026-10-01.parquet").write_bytes(b"PAR1"),
     "paket/abschluesse/abschluss_2026-10-01.parquet: nicht erlaubt (das Paket liegt flach unter paket/)"),
    (lambda z: (z / "paket" / "fremd.html").write_text("", encoding="utf-8"),
     "paket/fremd.html: steht nicht in stand.json"),
    (lambda z: (z / "A-B1.json").unlink(), "A-B1.json: fehlt"),
    (lambda z: (z / "paket" / "link.html").symlink_to(z / "paket" / "index.html"),
     "paket/link.html: ein Symlink"),
])
def test_im_zweig_betrieb_liegt_nur_was_die_routine_ablegt(tmp_path, anlegen, befund):
    """Positivkontrolle zuerst: Was die Routine ablegt (paket/ ohne Parquet,
    anker.jsonl, A-B1.json), geht durch, das .git des Checkouts zaehlt nicht.
    Jede Abweichung ist ein Befund, der die Auslieferung anhaelt."""
    zweig = _zweig(tmp_path / "zweig")
    assert bz.zweig(zweig) == []
    anlegen(zweig)
    assert befund in bz.zweig(zweig)
    assert bz.main(["zweig", str(zweig)]) == 1


@pytest.mark.parametrize("name", ["Bericht.html", "bericht(1).html", "bericht 1.html",
                                  'bericht"1.html', "bericht<b>.html", "berichtä.html"])
def test_ein_dateiname_im_paket_hat_nur_a_z_0_9_und_unterstrich_punkt_strich(tmp_path, name):
    """Der Name geht als Verweis in die Seite (Entscheid des Maintainers
    16.10.2026). Positivkontrolle: Ein Name aus allen erlaubten Zeichen geht
    durch. Die Abschluesse, die stand.json mit Schraegstrich nennt, sind kein
    Befund, denn geprueft werden die Dateien im Zweig. Ein fremdes Zeichen
    ist ein Befund, auch wenn stand.json den Namen nennt."""
    zweig = _zweig(tmp_path / "zweig")
    stand = json.loads((zweig / "paket" / "stand.json").read_text(encoding="utf-8"))
    for n in ("bestandsbericht_2026-01-01_teil-9.html", name):
        stand["dateien"][n] = "f" * 64
        (zweig / "paket" / "stand.json").write_text(json.dumps(stand), encoding="utf-8")
        (zweig / "paket" / n).write_text("x", encoding="utf-8")
        if n != name:
            assert bz.zweig(zweig) == []
    assert bz.zweig(zweig) == [f"paket/{name}: Dateiname mit anderen Zeichen als a-z, 0-9, _ . -"]
    assert bz.main(["zweig", str(zweig)]) == 1


def test_ausserhalb_von_betrieb_gleicht_der_baum_dem_rahmen(tmp_path):
    """Nur betrieb/ darf der Bau des Abends schreiben. Eine geaenderte, eine
    neue und eine fehlende Datei des Rahmens sind je ein Befund; ein Ordner
    betrieb/ im Rahmen selbst auch (den Betriebsteil baut nur der Workflow)."""
    rahmen, seite = tmp_path / "rahmen", tmp_path / "seite"
    for wurzel in (rahmen, seite):
        (wurzel / "it").mkdir(parents=True)
        (wurzel / "index.md").write_text("# Start\n", encoding="utf-8")
        (wurzel / "it" / "index.md").write_text("# IT\n", encoding="utf-8")
    (rahmen / ".git").mkdir()
    (rahmen / ".git" / "HEAD").write_text("x", encoding="utf-8")
    (seite / "betrieb").mkdir()
    (seite / "betrieb" / "index.md").write_text("# Bestandsführung\n", encoding="utf-8")
    assert bz.rahmen(rahmen, seite) == []
    (seite / "index.md").write_text("# Start, nachts geaendert\n", encoding="utf-8")
    (seite / "neu.html").write_text("", encoding="utf-8")
    (seite / "it" / "index.md").unlink()
    assert bz.rahmen(rahmen, seite) == [
        "it/index.md: im Rahmen, nicht im gebauten Baum",
        "neu.html: im gebauten Baum, nicht im Rahmen",
        "index.md: anders als im Rahmen"]
    (rahmen / "betrieb").mkdir()
    assert bz.rahmen(rahmen, seite)[0].startswith("betrieb/ liegt schon im Rahmen")


def _abschnitt(text: str, kopf: str) -> str:
    """Der Block unter einer Zeile ``kopf`` bis zur naechsten Zeile gleicher
    oder geringerer Einrueckung. Gelesen wird der Text: PyYAML ist keine
    Abhaengigkeit des Repositorys."""
    zeilen = text.splitlines()
    start = next(i for i, z in enumerate(zeilen) if z.rstrip() == kopf)
    tiefe = len(kopf) - len(kopf.lstrip())
    block = []
    for z in zeilen[start + 1:]:
        if z.strip() and not z.lstrip().startswith("#") and len(z) - len(z.lstrip()) <= tiefe:
            break
        block.append(z)
    return "\n".join(block)


def test_der_workflow_startet_nie_bei_einem_push_auf_betrieb():
    text = WORKFLOW.read_text(encoding="utf-8")
    ausloeser = _abschnitt(text, "on:")
    assert re.search(r"^  push:\n    branches: \[main\]$", ausloeser, re.M), ausloeser
    assert re.findall(r"^  (\w+):", ausloeser, re.M) == ["push", "workflow_dispatch", "schedule"]
    assert len(re.findall(r"^    - cron:", ausloeser, re.M)) >= 2, "GitHub laesst Zeitplaene aus"


def test_ausgeliefert_wird_nur_aus_main_und_nur_nach_dem_bau():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert _abschnitt(text, "permissions:").strip() == "contents: read"
    auslieferung = _abschnitt(text, "  veroeffentlichen:")
    assert "    needs: bauen" in auslieferung
    assert "    if: github.ref == 'refs/heads/main'" in auslieferung
    assert re.sub(r"\s+", " ", _abschnitt(auslieferung, "    permissions:")).strip() == \
        "pages: write id-token: write"
    assert "permissions" not in _abschnitt(text, "  bauen:")


def test_jede_action_ist_auf_einen_commit_gepinnt():
    """Ein Tag laesst sich verschieben, ein Commit nicht. jekyll-build-pages
    auf dem lokal gemessenen Stand v1.0.13."""
    text = WORKFLOW.read_text(encoding="utf-8")
    verwendet = re.findall(r"uses:\s*(\S+)", text)
    assert verwendet and all(re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", u) for u in verwendet), verwendet
    assert re.search(r"jekyll-build-pages@44a6e6beabd48582f863aeeb6cb2151cc1716697\s+# v1\.0\.13", text)


def test_der_workflow_baut_den_betriebsteil_mit_den_pruefungen():
    """Die Schritte, die der Plan verlangt, in dieser Folge: Allowlist des
    Zweigs, der Betriebsteil ohne Fall aus dem oeffentlichen Paket (die
    Seitenpruefung faehrt auftritt.py mit), der Vergleich mit dem Rahmen, erst
    dann Jekyll. Der Code kommt aus CODESTAND; python-markdown in der
    gemessenen Fassung; kein Checkout behaelt seine Zugangsdaten."""
    text = WORKFLOW.read_text(encoding="utf-8")
    bau = _abschnitt(text, "  bauen:")
    folge = ["betriebszweig.py zweig zweig", "auftritt.py --teil betrieb",
             "betriebszweig.py rahmen rahmen seite", "jekyll-build-pages@"]
    stellen = [bau.index(f) for f in folge]
    assert stellen == sorted(stellen), folge
    for teil in ("--oeffentliches-paket", "--ab1 zweig/A-B1.json", "--anker zweig/anker.jsonl",
                 "--stands-paket zweig/paket", "--vorschau", "markdown==3.4.1"):
        assert teil in bau, teil
    assert re.search(r"repository: bartlmac/rechner-pipeline\n\s+ref: \$\{\{ steps\.code\.outputs\.stand \}\}", bau)
    checkouts = bau.count("uses: actions/checkout@")
    assert checkouts == 3 and bau.count("persist-credentials: false") == checkouts
