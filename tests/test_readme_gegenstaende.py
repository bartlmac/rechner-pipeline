"""README: die Tabelle der fuenf Ebenen haelt mit dem Baum zusammen (ADR-028).

Das README ist die Landkarte des Repositorys: fuenf Ebenen (bis 08.10.2026
fuenf Gegenstaende nach ADR-027), dazu was quer zu ihnen liegt. Eine Landkarte veraltet still — das Bild mit sieben
Komponenten, das hier vorher stand, wurde an drei Stellen ueber seine
Nummern zitiert und nannte weder die Routinen noch die Webseite. Mechanisch
pruefbar ist zweierlei:

* Jeder Pfad, den der Abschnitt "Was dieses Repository ist" nennt, existiert.
* Jedes Verzeichnis der obersten Ebene, das Dateien des Repositorys traegt,
  ist dort zugeordnet — einer Ebene oder "quer". Ein neues Verzeichnis
  ohne Zuordnung ist rot.

Ob eine Zuordnung fachlich stimmt, ist Sprache und kein Test.

Knoten: system/architektur
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ABSCHNITT = "## Was dieses Repository ist"
#: Eine Zeile der Tabelle: Nummer und fett gesetzter Name der Ebene.
GEGENSTAND = re.compile(r"^\| ([0-9]+) \| \*\*([^*]+)\*\* \|", re.M)
CODE = re.compile(r"`([^`\n]+)`")


def _abschnitt(readme: str) -> str:
    assert readme.count(ABSCHNITT + "\n") == 1, "der Abschnitt fehlt oder steht doppelt"
    rest = readme.split(ABSCHNITT + "\n", 1)[1]
    return rest.split("\n## ", 1)[0]


def _pfade(abschnitt: str) -> list[str]:
    """Die Pfade, die der Abschnitt nennt: Code-Spannen ohne Leerraum, die
    einen Schraegstrich tragen oder mit einem Punkt beginnen."""
    return sorted({
        s.rstrip("/") for s in CODE.findall(abschnitt)
        if " " not in s and ("/" in s or s.startswith("."))
    })


def _verzeichnisse_der_obersten_ebene() -> set[str]:
    """Die Verzeichnisse, unter denen das Repository Dateien fuehrt."""
    dateien = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    return {d.split("/", 1)[0] for d in dateien if "/" in d}


def _fehlende(pfade: list[str], wurzel: Path) -> list[str]:
    return [p for p in pfade if not (wurzel / p).exists()]


def _nicht_zugeordnet(pfade: list[str], verzeichnisse: set[str]) -> list[str]:
    return sorted(
        v for v in verzeichnisse
        if not any(p == v or p.startswith(v + "/") for p in pfade)
    )


def _readme() -> str:
    return (REPO / "README.md").read_text(encoding="utf-8")


def test_die_tabelle_nennt_fuenf_ebenen():
    nummern = [n for n, _ in GEGENSTAND.findall(_abschnitt(_readme()))]
    assert nummern == ["1", "2", "3", "4", "5"]


def test_jeder_genannte_pfad_existiert():
    pfade = _pfade(_abschnitt(_readme()))
    # Positivkontrolle: Die Suche findet die Pfade der Tabelle ueberhaupt.
    assert {"src/rechner_pipeline/kern", "system", "plv", "migrationen",
            "werkzeuge", "pakete", ".claude"} <= set(pfade), pfade
    assert _fehlende(pfade, REPO) == []


def test_jedes_verzeichnis_der_obersten_ebene_ist_zugeordnet():
    verzeichnisse = _verzeichnisse_der_obersten_ebene()
    assert {"src", "tests", "docs", "deploy"} <= verzeichnisse, verzeichnisse
    assert _nicht_zugeordnet(_pfade(_abschnitt(_readme())), verzeichnisse) == [], (
        "ein Verzeichnis der obersten Ebene steht nicht im README-Abschnitt "
        f"'{ABSCHNITT[3:]}' — einer Ebene zuordnen oder unter 'quer' "
        "nennen (ADR-028)")


def test_die_pruefung_sieht_ein_fremdes_verzeichnis_und_einen_toten_pfad(tmp_path):
    abschnitt = (
        "| 1 | **A** | wozu | `src/paket/kern`, `configs/` |\n"
        "Quer: `tests/`. Kein Pfad: `main`, `python -m paket.x`.\n")
    pfade = _pfade(abschnitt)
    assert pfade == ["configs", "src/paket/kern", "tests"]
    (tmp_path / "src" / "paket" / "kern").mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    assert _fehlende(pfade, tmp_path) == ["configs"]
    assert _nicht_zugeordnet(pfade, {"src", "tests", "configs"}) == []
    assert _nicht_zugeordnet(pfade, {"src", "tests", "configs", "neuland"}) == ["neuland"]
    # Ein Verzeichnis, das nur als Anfang eines anderen Namens vorkommt,
    # gilt nicht als zugeordnet.
    assert _nicht_zugeordnet(["tests-alt/x"], {"tests"}) == ["tests"]
