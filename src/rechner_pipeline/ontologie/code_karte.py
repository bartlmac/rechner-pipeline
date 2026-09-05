"""Code-Karte: statischer Import-/Aufruf-Graph mit Schicht-Regeln (D4).

Die Karte macht die Schichtenkarte aus ADR-001 nachrechenbar statt
Prosa: sie parst jedes ``src``-Modul (ast, deterministisch, kein
Import/keine Ausfuehrung), loest paketinterne Kanten auf Modulebene auf
— mit den Symbolen, die ueber die Kante gehen (from-Imports plus
statisch aufloesbare Attribut-Aufrufe auf Modul-Aliase) — und prueft
deklarative Regeln:

* **Schicht-Allowlist**: jedes Paket darf nur aus explizit erlaubten
  Paketen importieren. Eine neue Kante ist damit eine bewusste
  Architektur-Entscheidung, kein Nebeneffekt.
* **Ebenen (ADR-017)**: jede Schicht gehoert dem KI-Tool (Ebene 2) oder
  der Vorzeige (Ebene 3). Das Tool importiert aus der Vorzeige nur ueber
  die Zielsystem-Schnittstelle — die heute gemessene Menge dieser Kanten
  ist als Ratsche festgeschrieben (``TOOL_NACH_VORZEIGE_ERLAUBT``); jede
  neue Kante Tool -> Vorzeige ist ein Befund, bis ein ADR sie aufnimmt.
* **Zweitkern-Regel (ADR-004)**: ``kommutationskern`` konsumiert nur
  ``qa`` — der Zielkern rechnet ohne Kommutation.
* **SDK-Verbot**: kein openai/anthropic/langgraph/langchain in src.

Dynamische Importe (``__import__``, ``importlib.import_module``) sind
mitgeprueft: mit String-Literal wie ein normaler Import, mit
berechnetem Namen als eigener Befund — ein Modul, dessen Import sich
statisch nicht lesen laesst, entzieht sich sonst allen Regeln
(Review-Befund).

Grenzen (ausgewiesen, nicht verschwiegen): der Aufruf-Graph ist
statisch — Registry-Dispatch (``hole(produkt)``) und Methodenaufrufe
auf Objekten werden nicht aufgeloest. Fuer die Schicht-Regeln ist das
egal (Imports sind vollstaendig); fuer die Symbol-Sicht ist es eine
Untergrenze.

Run via::

    python -m rechner_pipeline.ontologie.code_karte [--src src/rechner_pipeline]

Knoten: system/architektur
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

PAKET = "rechner_pipeline"

#: Erlaubte Import-Ziele je Schicht (Paket-Ebene). Fehlende Kante hier
#: == verboten. Kommentare nennen die Begruendung der Sonderfaelle.
SCHICHT_ERLAUBT: Dict[str, Set[str]] = {
    "kern": {"kern"},                                # rein: das Fundament
    "kommutationskern": {"kommutationskern", "kern"},  # Zweitkern liest Tafeln
    # models seit 2026-09-01: der Zeichnungsordnungs-Vertrag
    # (models.zeichnung) wird von gates UND ontologie.entscheide
    # gelesen (Vier-Rollen-Modell) — paketuebergreifende Vertraege
    # sind genau die models-Zustaendigkeit.
    "ontologie": {"ontologie", "kern", "models"},    # kern: nur lesende
    #                                                  Registry-Introspektion
    #                                                  (erlaubte_wurzeln)
    "models": {"models", "kern", "gates"},           # gates: Altlast
    #                                                  schemas<->Gate-Contract
    "spez": {"spez", "ontologie", "kern"},           # kern: lesende
    #                                                  Introspektion (D2)
    "quellen": {"quellen", "models", "ontologie", "kern", "spez"},
    "qa": {"qa", "models", "quellen", "kern"},
    "bestand": {"bestand", "kern", "models", "qa"},
    "gates": {"gates", "ontologie", "quellen", "kern", "models", "qa",
              "spez", "bestand", "fall"},            # Pruef-CLIs lesen alles;
    #                                                  fall: Gates operieren
    #                                                  auf Faellen (ADR-002)
    "fall": set(),
    "__init__": set(),                               # Paketwurzel
}

#: Ebene je Schicht (ADR-017). "tool" = das agentische Migrationssystem,
#: das bei jedem Versicherer unveraendert eingesetzt wuerde; "vorzeige" =
#: das Referenz-Zielsystem und die Bestandsfuehrung der fiktiven
#: Unternehmen. Die Vorzeige-Werkzeuge (Ebene 4) liegen ausserhalb von
#: src (simulation/, spaeter ein eigenes Paket) und erscheinen hier nicht.
EBENE_JE_SCHICHT: Dict[str, str] = {
    "ontologie": "tool", "spez": "tool", "gates": "tool", "models": "tool",
    "qa": "tool", "quellen": "tool", "fall": "tool", "cli": "tool",
    "__init__": "tool",
    "kern": "vorzeige", "bestand": "vorzeige", "betrieb": "vorzeige",
    "kommutationskern": "vorzeige",
}

#: Die Zielsystem-Schnittstelle, wie sie heute benutzt wird: alle Kanten
#: aus dem Tool in die Vorzeige, auf Modulebene, gemessen am Stand von
#: ADR-017 (29 Kanten). Das ist eine RATSCHE: bestehende Kanten sind
#: erlaubt, jede neue ist ein Befund. Ob daraus ein explizites
#: Schnittstellen-Modul und eine Paketteilung folgen, entscheidet ein
#: ADR nach der Messung — nicht ein Import nebenbei.
TOOL_NACH_VORZEIGE_ERLAUBT: Set[tuple] = {
    ("rechner_pipeline/gates/abnahmebericht.py", "rechner_pipeline/bestand/vorbedingungen.py"),
    ("rechner_pipeline/gates/aktuartest_lauf.py", "rechner_pipeline/bestand/parquet_io.py"),
    ("rechner_pipeline/gates/aktuartest_lauf.py", "rechner_pipeline/kern/beitragsreduktion.py"),
    ("rechner_pipeline/gates/aktuartest_lauf.py", "rechner_pipeline/kern/korrekturschicht.py"),
    ("rechner_pipeline/gates/bestand_uebernehmen.py", "rechner_pipeline/bestand/parquet_io.py"),
    ("rechner_pipeline/gates/bestand_uebernehmen.py", "rechner_pipeline/kern/__init__.py"),
    ("rechner_pipeline/gates/bestand_validate.py", "rechner_pipeline/bestand/manifest.py"),
    ("rechner_pipeline/gates/bestand_validate.py", "rechner_pipeline/bestand/vorbedingungen.py"),
    ("rechner_pipeline/gates/generation_golden.py", "rechner_pipeline/kern/__init__.py"),
    ("rechner_pipeline/gates/migrationssuite_lauf.py", "rechner_pipeline/bestand/migrationszugang.py"),
    ("rechner_pipeline/gates/migrationssuite_lauf.py", "rechner_pipeline/bestand/parquet_io.py"),
    ("rechner_pipeline/gates/migrationssuite_lauf.py", "rechner_pipeline/kern/beitragsreduktion.py"),
    ("rechner_pipeline/gates/verankerung_belegen.py", "rechner_pipeline/bestand/migrationszugang.py"),
    ("rechner_pipeline/gates/verankerung_belegen.py", "rechner_pipeline/bestand/parquet_io.py"),
    ("rechner_pipeline/gates/verankerung_belegen.py", "rechner_pipeline/kern/__init__.py"),
    ("rechner_pipeline/gates/verankerung_belegen.py", "rechner_pipeline/kern/beitragsreduktion.py"),
    ("rechner_pipeline/gates/verankerung_belegen.py", "rechner_pipeline/kern/rechenkern.py"),
    ("rechner_pipeline/models/bestand.py", "rechner_pipeline/kern/model_point.py"),
    ("rechner_pipeline/ontologie/code_index.py", "rechner_pipeline/kern/produkte/__init__.py"),
    ("rechner_pipeline/qa/abzugsabgleich.py", "rechner_pipeline/kern/__init__.py"),
    ("rechner_pipeline/qa/abzugsabgleich.py", "rechner_pipeline/kern/produkte/__init__.py"),
    ("rechner_pipeline/qa/aktuarieller_test.py", "rechner_pipeline/kern/__init__.py"),
    ("rechner_pipeline/qa/aktuarieller_test.py", "rechner_pipeline/kern/beitragsreduktion.py"),
    ("rechner_pipeline/qa/aktuarieller_test.py", "rechner_pipeline/kern/korrekturschicht.py"),
    ("rechner_pipeline/qa/aktuarieller_test.py", "rechner_pipeline/kern/rechenkern.py"),
    ("rechner_pipeline/qa/migrationssuite.py", "rechner_pipeline/kern/__init__.py"),
    ("rechner_pipeline/qa/migrationssuite.py", "rechner_pipeline/kern/beitragsreduktion.py"),
    ("rechner_pipeline/quellen/tafel_import.py", "rechner_pipeline/kern/tafeln.py"),
    ("rechner_pipeline/spez/erzeugen.py", "rechner_pipeline/kern/tafeln.py"),
}


def ebene(schicht: str) -> Optional[str]:
    """Die Ebene einer Schicht (ADR-017), None fuer eine unbekannte."""
    return EBENE_JE_SCHICHT.get(schicht)


#: ADR-013: Der Kommutations-Zweitkern hat KEINEN Konsumenten mehr im
#: Produktivpfad. Er lebt nur noch als unabhaengiger Zeuge der
#: algebraischen Eigenschaftstests (tests/test_kern_algebraisch.py), die
#: ihn testseitig direkt bauen — nicht ueber eine Schnittstelle, die der
#: Zielkern seinetwegen aufrechterhaelt. Genau darin liegt der
#: Unterschied zu vorher: Der Zweitkern hat keinen Anspruch mehr an den
#: lebenden Code, und deshalb formt er ihn auch nicht mehr.
ZWEITKERN = "kommutationskern"
ZWEITKERN_KONSUMENTEN = {"kommutationskern"}

#: Verbotene SDK-Namensfamilien. Geprueft wird die FAMILIE, nicht der
#: exakte Name: ``langchain_openai``, ``langgraph_sdk``,
#: ``anthropic_bedrock`` gehoeren dazu (Review-Befund).
SDK_VERBOTEN = frozenset({"openai", "anthropic", "langgraph", "langchain"})


def _ist_sdk(name: str) -> bool:
    """Top-Level-Modulname gegen die verbotenen Familien halten."""
    stamm = name.split(".")[0]
    return any(
        stamm == verboten or stamm.startswith(verboten + "_")
        or stamm.endswith("_" + verboten)
        for verboten in SDK_VERBOTEN
    )


def _exakt_geschriebene_datei(src: Path, teile: List[str]) -> Optional[Path]:
    """Datei nur bei exakt passenden Namen aller Pfadsegmente liefern.

    ``Path.is_file()`` folgt der Semantik des Dateisystems und akzeptiert
    deshalb auf ueblichen macOS-Volumes auch einen anders geschriebenen
    Namen. Fuer Python-Modulnamen ist die Schreibweise dagegen Teil der
    Identitaet. Die Verzeichnis-Eintraege tragen die tatsaechlichen Namen;
    der segmentweise Vergleich macht die Aufloesung plattformunabhaengig.
    """
    aktuell = src
    for teil in teile:
        try:
            treffer = next(
                (eintrag for eintrag in aktuell.iterdir()
                 if eintrag.name == teil),
                None,
            )
        except OSError:
            return None
        if treffer is None:
            return None
        aktuell = treffer
    return aktuell if aktuell.is_file() else None


def _modulpfad(dotted: str, src: Path) -> Optional[str]:
    """``rechner_pipeline.kern.tafeln`` -> ``rechner_pipeline/kern/tafeln.py``.

    Nicht aufloesbare Namen (extern) -> None. Pakete loesen auf ihr
    ``__init__.py`` auf.
    """
    teile = dotted.split(".")
    if teile[0] != PAKET:
        return None
    kandidat = (
        _exakt_geschriebene_datei(
            src, [*teile[1:-1], f"{teile[-1]}.py"])
        if teile[1:] else None
    )
    if kandidat is not None:
        return str(kandidat.relative_to(src.parent))
    init = _exakt_geschriebene_datei(src, [*teile[1:], "__init__.py"])
    if init is not None:
        return str(init.relative_to(src.parent))
    return None


def _schicht(rel: str) -> str:
    """Schicht eines Moduls = erstes Paketsegment (``fall.py`` -> fall)."""
    teile = Path(rel).parts
    if len(teile) <= 2:                    # rechner_pipeline/<datei>.py
        return Path(teile[-1]).stem if teile[-1] != "__init__.py" else "__init__"
    return teile[1]


def _absolut(modul: Optional[str], level: int, rel: str) -> Optional[str]:
    """Relative Imports (``from . import x``) auf dotted-Namen bringen."""
    if level == 0:
        return modul
    basis = Path(rel).parts[:-1]           # Paket des importierenden Moduls
    if len(basis) < level:
        return None
    # ``from . import x`` (level 1) meint das eigene Paket, ``from ..``
    # (level 2) das darueber. Vorher stand hier eine nie definierte
    # Variable — der Zweig war unerreichbar, weil src keine relativen
    # Importe traegt, und ungetestet (Review U1, Befund Z1-09).
    anker = basis[: len(basis) - (level - 1)]
    dotted = ".".join(anker)
    return f"{dotted}.{modul}" if modul else dotted


def baue_karte(src: Path) -> Dict[str, object]:
    """Die Karte deterministisch aus den Quelltexten bauen."""
    module: Dict[str, Dict[str, object]] = {}
    kanten: Dict[tuple, Set[str]] = {}
    extern: Dict[str, Set[str]] = {}
    dynamisch_unlesbar: Dict[str, int] = {}

    for pfad in sorted(src.rglob("*.py")):
        if "__pycache__" in pfad.parts:
            continue
        rel = str(pfad.relative_to(src.parent))
        text = pfad.read_text(encoding="utf-8")
        baum = ast.parse(text)
        defs = sorted(
            n.name for n in baum.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.ClassDef))
        )
        module[rel] = {
            "schicht": _schicht(rel),
            "ebene": ebene(_schicht(rel)),
            "defs": defs,
            "zeilen": text.count("\n") + 1,
        }
        alias_zu_modul: Dict[str, str] = {}     # Alias -> Modul-rel
        name_zu_kante: Dict[str, tuple] = {}    # from-Import: Name -> Kante
        for n in ast.walk(baum):
            if isinstance(n, ast.Import):
                for a in n.names:
                    ziel = _modulpfad(a.name, src)
                    if ziel is None:
                        extern.setdefault(
                            a.name.split(".")[0], set()).add(rel)
                        continue
                    kanten.setdefault((rel, ziel), set())
                    alias_zu_modul[a.asname or a.name.split(".")[-1]] = ziel
            elif isinstance(n, ast.ImportFrom):
                dotted = _absolut(n.module, n.level, rel)
                if dotted is None:
                    continue
                ziel = _modulpfad(dotted, src)
                if ziel is None:
                    extern.setdefault(dotted.split(".")[0], set()).add(rel)
                    continue
                for a in n.names:
                    # ``from paket import modul`` bindet ein Untermodul
                    unter = _modulpfad(f"{dotted}.{a.name}", src)
                    if unter is not None and unter != ziel:
                        kanten.setdefault((rel, unter), set())
                        alias_zu_modul[a.asname or a.name] = unter
                        continue
                    kanten.setdefault((rel, ziel), set()).add(a.name)
                    name_zu_kante[a.asname or a.name] = (rel, ziel)
        for n in ast.walk(baum):
            if not isinstance(n, ast.Call):
                continue
            # Attribut-Aufrufe auf Modul-Aliase: kommutation.fuer(...)
            if (isinstance(n.func, ast.Attribute)
                    and isinstance(n.func.value, ast.Name)):
                ziel = alias_zu_modul.get(n.func.value.id)
                if ziel is not None:
                    kanten.setdefault((rel, ziel), set()).add(n.func.attr)
            # Dynamische Importe: __import__ / importlib.import_module
            dynamisch = (
                (isinstance(n.func, ast.Name)
                 and n.func.id == "__import__")
                or (isinstance(n.func, ast.Attribute)
                    and n.func.attr == "import_module")
            )
            if not dynamisch:
                continue
            arg = n.args[0] if n.args else None
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                ziel = _modulpfad(arg.value, src)
                if ziel is not None:
                    kanten.setdefault((rel, ziel), set()).add(
                        f"<dynamisch:{arg.value}>")
                else:
                    extern.setdefault(arg.value.split(".")[0], set()).add(rel)
            else:
                dynamisch_unlesbar.setdefault(rel, 0)
                dynamisch_unlesbar[rel] += 1

    return {
        "module": dict(sorted(module.items())),
        "kanten": [
            {"von": von, "nach": nach, "symbole": sorted(symbole)}
            for (von, nach), symbole in sorted(kanten.items())
        ],
        "tool_nach_vorzeige": tool_nach_vorzeige(module, kanten),
        "extern": {k: sorted(v) for k, v in sorted(extern.items())},
        "dynamisch_unlesbar": dict(sorted(dynamisch_unlesbar.items())),
    }


def tool_nach_vorzeige(
    module: Dict[str, Dict[str, object]], kanten: Dict[tuple, Set[str]]
) -> List[Dict[str, str]]:
    """Alle Import-Kanten aus dem Tool in die Vorzeige (ADR-017), sortiert
    — die Messung, auf der die Ratsche steht."""
    aus: List[Dict[str, str]] = []
    for (von, nach) in sorted(kanten):
        e_von = module.get(von, {}).get("ebene") or ebene(_schicht(von))
        e_nach = module.get(nach, {}).get("ebene") or ebene(_schicht(nach))
        if e_von == "tool" and e_nach == "vorzeige":
            aus.append({"von": von, "nach": nach})
    return aus


def validate(karte: Dict[str, object]) -> List[str]:
    """Regel-Befunde (leer = Architektur eingehalten)."""
    befunde: List[str] = []
    module = karte["module"]
    # Jede Schicht hat eine Ebene (ADR-017); eine Schicht ohne Ebene ist
    # weder Tool noch Vorzeige und damit nicht einordenbar.
    for rel, daten in module.items():
        if daten.get("ebene") is None and daten["schicht"] in SCHICHT_ERLAUBT:
            befunde.append(
                f"{rel}: Schicht {daten['schicht']!r} ohne Ebene — Tool oder "
                "Vorzeige? (EBENE_JE_SCHICHT, ADR-017)"
            )
    # Ratsche: keine neue Kante aus dem Tool in die Vorzeige ohne ADR.
    for kante in karte.get("tool_nach_vorzeige", []):
        paar = (kante["von"], kante["nach"])
        if paar not in TOOL_NACH_VORZEIGE_ERLAUBT:
            befunde.append(
                f"{paar[0]} -> {paar[1]}: neue Kante aus dem KI-Tool in die "
                "Vorzeige — das Tool spricht das Zielsystem nur ueber die "
                "gemessene Schnittstelle an (TOOL_NACH_VORZEIGE_ERLAUBT, "
                "ADR-017); eine neue Kante ist eine Architektur-Entscheidung"
            )
    # Jede vorkommende Schicht braucht einen Regel-Eintrag — auch eine
    # ohne jede Kante (ein neues Paket, das nur nach aussen telefoniert,
    # waere sonst unsichtbar; Review-Befund).
    for rel, daten in module.items():
        if daten["schicht"] not in SCHICHT_ERLAUBT:
            befunde.append(
                f"{rel}: Schicht {daten['schicht']!r} ohne Regel-Eintrag — "
                "neue Schicht ist eine Architektur-Entscheidung (ADR noetig)"
            )
    for kante in karte["kanten"]:
        von, nach = kante["von"], kante["nach"]
        s_von = module[von]["schicht"] if von in module else _schicht(von)
        s_nach = module[nach]["schicht"] if nach in module else _schicht(nach)
        if s_von == s_nach:
            continue
        erlaubt = SCHICHT_ERLAUBT.get(s_von)
        if erlaubt is None:
            pass                       # oben schon als Schicht gemeldet
        elif s_nach not in erlaubt:
            befunde.append(
                f"{von} -> {nach}: Schicht {s_von!r} darf nicht aus "
                f"{s_nach!r} importieren (erlaubt: "
                f"{', '.join(sorted(erlaubt)) or 'nichts'})"
            )
        if s_nach == ZWEITKERN and s_von not in ZWEITKERN_KONSUMENTEN:
            befunde.append(
                f"{von} -> {nach}: der Kommutations-Zweitkern hat genau "
                f"einen Konsumenten ({', '.join(sorted(ZWEITKERN_KONSUMENTEN - {ZWEITKERN}))}) "
                "— der Zielkern rechnet ohne Kommutation (ADR-004)"
            )
    for name, nutzer in karte["extern"].items():
        if _ist_sdk(name):
            befunde.append(
                f"SDK-Import {name!r} in: {', '.join(nutzer)} — src ist "
                "SDK-frei (AGENTS.md)"
            )
    for rel, anzahl in karte.get("dynamisch_unlesbar", {}).items():
        befunde.append(
            f"{rel}: {anzahl} dynamische(r) Import(e) mit berechnetem Namen "
            "— statisch nicht pruefbar; Modulname als Literal schreiben "
            "(sonst entzieht sich die Kante allen Schicht-/SDK-Regeln)"
        )
    return sorted(befunde)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.ontologie.code_karte",
        description="Code-Karte bauen (Import-/Aufruf-Graph, Schicht-Regeln).",
    )
    parser.add_argument("--src", default="src/rechner_pipeline")
    args = parser.parse_args(argv)
    src = Path(args.src)
    if not src.is_dir():
        print(f"code_karte: kein Verzeichnis: {src}", file=sys.stderr)
        return 2
    karte = baue_karte(src)
    befunde = validate(karte)
    print(json.dumps(
        {**karte, "befunde": befunde},
        ensure_ascii=False, indent=2, sort_keys=True,
    ))
    return 1 if befunde else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
