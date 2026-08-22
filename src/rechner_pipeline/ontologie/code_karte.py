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
    "ontologie": {"ontologie", "kern"},              # kern: nur lesende
    #                                                  Registry-Introspektion
    #                                                  (erlaubte_wurzeln)
    "models": {"models", "kern", "gates"},           # gates: Altlast
    #                                                  schemas<->Gate-Contract
    "spez": {"spez", "ontologie", "kern"},           # kern: lesende
    #                                                  Introspektion (D2)
    "quellen": {"quellen", "models", "ontologie", "kern", "spez"},
    "qa": {"qa", "models", "quellen", "kern", "kommutationskern"},
    "bestand": {"bestand", "kern", "models", "qa"},
    "gates": {"gates", "ontologie", "quellen", "kern", "models", "qa",
              "spez", "bestand", "fall"},            # Pruef-CLIs lesen alles;
    #                                                  fall: Gates operieren
    #                                                  auf Faellen (ADR-002)
    "fall": set(),
    "__init__": set(),                               # Paketwurzel
}

#: ADR-004: der Kommutations-Zweitkern hat genau einen Konsumenten.
ZWEITKERN = "kommutationskern"
ZWEITKERN_KONSUMENTEN = {"qa", "kommutationskern"}

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
    if len(basis) < level - 1 + 1:
        return None
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
        "extern": {k: sorted(v) for k, v in sorted(extern.items())},
        "dynamisch_unlesbar": dict(sorted(dynamisch_unlesbar.items())),
    }


def validate(karte: Dict[str, object]) -> List[str]:
    """Regel-Befunde (leer = Architektur eingehalten)."""
    befunde: List[str] = []
    module = karte["module"]
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
