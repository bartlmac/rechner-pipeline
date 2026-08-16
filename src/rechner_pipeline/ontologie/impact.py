"""Impact-Berechnung: geaenderte Dateien -> Knoten -> Tests/Gates (D4).

Der Baustein, der die 1M-LOC-These nachrechenbar macht: welcher Teil
der Suite muss nach einer Aenderung laufen? Die Antwort ist BERECHNET
aus drei Quellen, nicht geraten:

1. **Code-Index** (``ontologie.code_index``): Knoten der geaenderten
   Module und die Knoten-Bindung jedes Testmoduls.
2. **Lineage der Knoten-Hierarchie**: ein Test laeuft, wenn sein
   Knoten mit einem betroffenen Knoten verwandt ist — gleiche Linie
   (``klv`` ~ ``klv/tg2015``), nicht Geschwister (``klv/tg2012`` !~
   ``klv/tg2015``), nie fremde Familie (``bu`` !~ ``klv``). Das ist die
   FACHLICHE Kopplung.
3. **Direkte Import-Kanten der Tests**: ein Test laeuft ausserdem,
   wenn er das geaenderte Modul selbst importiert — auch wenn seine
   Knoten-Bindung eine andere Linie nennt. Das ist die CODE-Kopplung
   (Review-Befund: ``fall.py`` traegt ``system/fall``, wird aber von
   klv-gebundenen Ontologie-Tests direkt benutzt).

Bewusst NICHT transitiv: die Schliessung ueber ``__init__``-Re-Exports
zieht jede Aenderung auf "alles" hoch (gemessen: bu.py 5 -> 21 Tests)
und ist Lade-Zeit-Kopplung, keine fachliche. Dafuer laeuft in CI und
vor jedem Commit die VOLLE Suite; die Selektion ist ein Werkzeug fuer
die Arbeit dazwischen. Die Rueckwaerts-Schliessung dient als
Transparenz (``abhaengige_module``) und als Knoten-Fallback fuer
unannotierte Module.

Die Garantie ist ENTDECKUNG, nicht Vollstaendigkeit: erzwungen wird,
dass jedes geaenderte Modul von mindestens einem selektierten Test
geladen wird (sonst: volle Suite) — ein Import-Bruch faellt damit
immer auf. Tests, die ein geaendertes Modul laden, aber fachlich nicht
betroffen sind, stehen als ``weitere_lader`` im Ergebnis: ueber diese
Kante wuerde ein VERHALTENS-Bruch erst in der vollen Suite auffallen.
Das ist die bewusst getragene Restluecke (heute 34 der 79 Module) —
ausgewiesen, nicht versteckt.

Fail-safe statt fail-silent: laesst sich eine Aenderung keinem Knoten
zuordnen (unannotiertes Modul ohne annotierte Importeure, globale
Dateien, unbekannte Artefakte unter ``src/``/``tests/``, nicht
normalisierbare Pfade), ist der Impact KONSERVATIV — die volle Suite,
mit ausgewiesenem Grund. Praezision ist verdient, nie vermutet.

Kein Gate, ein Informationswerkzeug: Exit 0, JSON auf stdout. Die
Dateiliste kommt vom Aufrufer (z. B. ``git diff --name-only | python
-m rechner_pipeline.ontologie.impact``) — das Werkzeug selbst bleibt
ein reiner Funktionskern ohne Prozess-Aufrufe.

Run via::

    python -m rechner_pipeline.ontologie.impact --datei <pfad> [--datei ...]
    git diff --name-only | python -m rechner_pipeline.ontologie.impact

Knoten: system/architektur
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Dict, List, Optional, Set

SRC_PREFIX = "src/rechner_pipeline/"
TEST_PREFIX = "tests/"

#: Nicht-Python-Artefakte, die wie ein Modul wirken (Daten-Bindung).
#: Alles andere unter ``src/``/``tests/`` ist konservativ — die Liste
#: ist eine Praezisions-Erlaubnis, kein Filter.
DATEN_BINDUNG: Dict[str, str] = {
    SRC_PREFIX + "kern/tafeln.xml": "rechner_pipeline/kern/tafeln.py",
}

#: Doku-/Vertrags-Pfade, die an einen Knoten gebunden sind (test-tragend).
DOKU_BINDUNG: Dict[str, str] = {
    "AGENTS.md": "system/skills",
    ".claude/skills/": "system/skills",
    ".agents/skills/": "system/skills",
    "docs/architektur/skill-architektur.md": "system/skills",
}

#: Aenderungen hier machen jede Selektion unsicher -> volle Suite.
GLOBAL_KONSERVATIV = ("pyproject.toml", "tests/conftest.py",
                      "tests/__init__.py", ".github/")


def verwandt(a: str, b: str) -> bool:
    """Lineage-Verwandtschaft zweier Knoten (gleiche Linie, hierarchisch)."""
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def normalisiere(datei: str, repo_root: Optional[Path] = None) -> Optional[str]:
    """Pfad auf repo-relativ/posix bringen (None = nicht zuordenbar).

    Faengt die Formen, in denen Werkzeuge Pfade liefern: ``./x``,
    Windows-Trenner, absolute Pfade. Was sich nicht aufloesen laesst,
    gibt None zurueck — der Aufrufer behandelt das konservativ, statt
    es still als "keine Auswirkung" abzulegen (Review-Befund).
    """
    roh = datei.strip().strip('"').replace("\\", "/")
    if not roh:
        return None
    pfad = PurePosixPath(roh)
    if pfad.is_absolute():
        wurzel = PurePosixPath(
            (repo_root or Path.cwd()).resolve().as_posix()
        )
        try:
            pfad = pfad.relative_to(wurzel)
        except ValueError:
            return None
    teile = [t for t in pfad.parts if t not in (".", "")]
    if ".." in teile:
        return None
    return "/".join(teile) or None


def _schliessung(
    start: Set[str], kanten: List[Dict[str, object]], rueckwaerts: bool
) -> Set[str]:
    """Transitive Huelle ueber die Import-Kanten (inkl. ``start``).

    ``rueckwaerts``: wer importiert das hier (Importeure).
    Sonst: was wird von hier aus geladen (Ladekette).
    """
    nachbarn: Dict[str, Set[str]] = {}
    for kante in kanten:
        von, nach = kante["von"], kante["nach"]
        if rueckwaerts:
            nachbarn.setdefault(nach, set()).add(von)
        else:
            nachbarn.setdefault(von, set()).add(nach)
    huelle = set(start)
    rand = list(start)
    while rand:
        modul = rand.pop()
        for n in nachbarn.get(modul, ()):
            if n not in huelle:
                huelle.add(n)
                rand.append(n)
    return huelle


def _rueckwaerts_schliessung(
    start: Set[str], kanten: List[Dict[str, object]]
) -> Set[str]:
    """Alle Module, die (transitiv) auf ``start`` zeigen, inkl. start."""
    return _schliessung(start, kanten, rueckwaerts=True)


def ladende_tests(
    test_imports: Dict[str, List[str]], kanten: List[Dict[str, object]]
) -> Dict[str, Set[str]]:
    """Je Testmodul die transitiv geladene Modulmenge (Import-Zeit)."""
    return {
        name: _schliessung(set(module), kanten, rueckwaerts=False)
        for name, module in test_imports.items()
    }


def import_kanten_je_testmodul(tests: Path, src: Path) -> Dict[str, List[str]]:
    """Direkt importierte ``src``-Module je Testmodul (deterministisch)."""
    from rechner_pipeline.ontologie.code_karte import _modulpfad

    ergebnis: Dict[str, List[str]] = {}
    for pfad in sorted(tests.glob("test_*.py")):
        try:
            baum = ast.parse(pfad.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            ergebnis[pfad.name] = []
            continue
        module: Set[str] = set()
        for n in ast.walk(baum):
            if isinstance(n, ast.ImportFrom):
                if not (n.module and n.module.startswith("rechner_pipeline")):
                    continue
                for a in n.names:
                    unter = _modulpfad(f"{n.module}.{a.name}", src)
                    if unter:
                        module.add(unter)
                eigen = _modulpfad(n.module, src)
                if eigen:
                    module.add(eigen)
            elif isinstance(n, ast.Import):
                for a in n.names:
                    if a.name.startswith("rechner_pipeline"):
                        ziel = _modulpfad(a.name, src)
                        if ziel:
                            module.add(ziel)
        ergebnis[pfad.name] = sorted(module)
    return ergebnis


def berechne_impact(
    dateien: List[str],
    index: Dict[str, object],
    karte: Dict[str, object],
    test_bindung: Dict[str, List[str]],
    faelle_generationen: Optional[Dict[str, List[str]]] = None,
    test_imports: Optional[Dict[str, List[str]]] = None,
    repo_root: Optional[Path] = None,
) -> Dict[str, object]:
    """Impact einer Aenderungsmenge (rein, deterministisch)."""
    module_zu_knoten: Dict[str, List[str]] = index["module"]
    geaenderte_module: Set[str] = set()
    direkte_tests: Set[str] = set()
    knoten: Set[str] = set()
    hinweise: List[str] = []
    konservativ: List[str] = []

    for roh in sorted(set(dateien)):
        datei = normalisiere(roh, repo_root)
        if datei is None:
            konservativ.append(
                f"{roh.strip()!r}: Pfad nicht repo-relativ aufloesbar"
            )
            continue
        if any(datei.startswith(p) for p in GLOBAL_KONSERVATIV):
            konservativ.append(f"{datei}: globale Datei — volle Suite")
            continue
        doku = next(
            (k for pfx, k in DOKU_BINDUNG.items() if datei.startswith(pfx)),
            None,
        )
        if doku is not None:
            knoten.add(doku)
            continue
        if datei in DATEN_BINDUNG:
            geaenderte_module.add(DATEN_BINDUNG[datei])
            hinweise.append(
                f"{datei}: Daten-Bindung an {DATEN_BINDUNG[datei]} "
                "(Datei-Ebene — Tafel-/Zellen-Granularitaet ist Roadmap)"
            )
            continue
        if datei.startswith(TEST_PREFIX):
            if datei.endswith(".py"):
                direkte_tests.add(PurePosixPath(datei).name)
            else:                       # Fixtures, Daten, Hilfsdateien
                konservativ.append(
                    f"{datei}: Test-Artefakt ohne Modul-Bindung "
                    "(welche Tests es lesen, ist nicht abgeleitet)"
                )
            continue
        if datei.startswith(SRC_PREFIX):
            if datei.endswith(".py"):
                geaenderte_module.add(datei[len("src/"):])
            else:
                konservativ.append(
                    f"{datei}: Artefakt unter src/ ohne Daten-Bindung"
                )
            continue
        if datei.endswith(".py"):
            konservativ.append(
                f"{datei}: Python-Datei ausserhalb von src/ und tests/"
            )
            continue
        hinweise.append(f"{datei}: kein Code-/Vertrags-Impact (Doku o. ae.)")

    unbekannt = geaenderte_module - set(karte["module"])
    if unbekannt:
        konservativ.append(
            "geloeschte oder unbekannte Module: "
            + ", ".join(sorted(unbekannt))
        )
    geaenderte_module &= set(karte["module"])

    schliessung = _rueckwaerts_schliessung(
        geaenderte_module, karte["kanten"]
    )
    for modul in sorted(geaenderte_module):
        eigene = module_zu_knoten.get(modul)
        if eigene:
            knoten.update(eigene)
            continue
        # Fallback: Knoten der (transitiven) Importeure dieses Moduls.
        geerbte: Set[str] = set()
        for imp in _rueckwaerts_schliessung({modul}, karte["kanten"]):
            geerbte.update(module_zu_knoten.get(imp, ()))
        if geerbte:
            knoten.update(geerbte)
            hinweise.append(
                f"{modul}: unannotiert — Knoten der Importeure geerbt "
                f"({', '.join(sorted(geerbte))})"
            )
        else:
            konservativ.append(
                f"{modul}: unannotiert und ohne annotierte Importeure"
            )

    lader = ladende_tests(test_imports or {}, karte["kanten"])
    weitere_lader: List[str] = []
    if konservativ:
        tests = sorted(set(test_bindung) | direkte_tests)
    else:
        per_lineage = {
            name for name, gebunden in test_bindung.items()
            if any(verwandt(t, k) for t in gebunden for k in knoten)
        }
        # Code-Kopplung: Tests, die ein geaendertes Modul direkt
        # importieren, laufen unabhaengig von ihrer Knoten-Linie.
        per_import = {
            name for name, module in (test_imports or {}).items()
            if geaenderte_module.intersection(module)
        }
        for name in sorted(per_import - per_lineage):
            hinweise.append(
                f"{name}: ueber direkte Import-Kante selektiert "
                "(Knoten-Bindung nennt eine andere Linie)"
            )
        tests = sorted(per_lineage | per_import | direkte_tests)

        # ERZWUNGENE LADEDECKUNG: jedes geaenderte Modul muss von
        # mindestens einem selektierten Test geladen werden, sonst
        # bliebe schon ein Import-Bruch unsichtbar (Review-Befund).
        ungedeckt = sorted(
            modul for modul in geaenderte_module
            if not any(modul in lader.get(t, ()) for t in tests)
        )
        for modul in ungedeckt:
            konservativ.append(
                f"{modul}: kein selektierter Test laedt dieses Modul — "
                "schon ein Import-Bruch bliebe unentdeckt"
            )
        if ungedeckt:
            tests = sorted(set(test_bindung) | direkte_tests)
        else:
            # Transparenz: Tests, die ein geaendertes Modul laden, aber
            # fachlich nicht betroffen sind. Ein Verhaltens-Bruch ueber
            # diese Kante wuerde erst in der vollen Suite auffallen.
            weitere_lader = sorted(
                name for name, module in lader.items()
                if geaenderte_module.intersection(module)
                and name not in tests
            )

    betroffene_faelle = []
    for fall, generationen in sorted((faelle_generationen or {}).items()):
        treffer = sorted(
            g for g in generationen
            if konservativ or any(verwandt(g, k) for k in knoten)
        )
        for g in treffer:
            betroffene_faelle.append({
                "fall": fall, "generation": g,
                "hinweis": f"Gate O3 fuer {fall} --generation {g} "
                           "erneut fahren",
            })

    return {
        "geaendert": sorted(set(d.strip() for d in dateien if d.strip())),
        "module": sorted(geaenderte_module),
        "abhaengige_module": sorted(schliessung - geaenderte_module),
        "knoten": sorted(knoten),
        "tests": tests,
        "pytest_args": [f"tests/{t}" for t in tests],
        "faelle": betroffene_faelle,
        "weitere_lader": weitere_lader,
        "konservativ": sorted(konservativ),
        "hinweise": sorted(hinweise),
    }


def lade_faelle_generationen(faelle_dir: Path) -> Dict[str, List[str]]:
    """Generationen-IDs je Fall aus den A-Boxen lesen (fail-soft).

    Faelle sind gitignoriert und liegen nur lokal — ein fehlendes oder
    unlesbares Verzeichnis ist KEIN Fehler, nur ein leeres Ergebnis.
    """
    ergebnis: Dict[str, List[str]] = {}
    if not faelle_dir.is_dir():
        return ergebnis
    for abox in sorted(faelle_dir.glob("*/abgeleitet/abox/abox.json")):
        try:
            daten = json.loads(abox.read_text(encoding="utf-8"))
            ids = sorted(
                g["id"] for g in daten.get("generationen", []) if "id" in g
            )
        except (OSError, ValueError):
            continue
        if ids:
            ergebnis[abox.parents[2].name] = ids
    return ergebnis


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.ontologie.impact",
        description=(
            "Impact geaenderter Dateien berechnen (Knoten, Tests, Gates)."
        ),
    )
    parser.add_argument(
        "--datei", action="append", default=[],
        help="geaenderte Datei (mehrfach; ohne Angabe: eine je stdin-Zeile)",
    )
    parser.add_argument("--src", default="src/rechner_pipeline")
    parser.add_argument("--tests", default="tests")
    parser.add_argument("--faelle", default="faelle")
    parser.add_argument(
        "--repo-root", dest="repo_root", default=None,
        help="Wurzel fuer absolute Pfade (Default: aktuelles Verzeichnis)",
    )
    args = parser.parse_args(argv)

    from rechner_pipeline.ontologie.code_index import (
        baue_index,
        baue_test_bindung,
    )
    from rechner_pipeline.ontologie.code_karte import baue_karte

    src, tests = Path(args.src), Path(args.tests)
    if not src.is_dir() or not tests.is_dir():
        print(f"impact: --src {src} und --tests {tests} muessen "
              "Verzeichnisse sein", file=sys.stderr)
        return 2
    dateien = args.datei or [z for z in sys.stdin.read().splitlines()]
    ergebnis = berechne_impact(
        dateien,
        baue_index(src),
        baue_karte(src),
        baue_test_bindung(tests)["bindung"],
        lade_faelle_generationen(Path(args.faelle)),
        import_kanten_je_testmodul(tests, src),
        Path(args.repo_root) if args.repo_root else None,
    )
    print(json.dumps(ergebnis, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
