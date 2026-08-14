"""Ontologie-Code-Index: Knoten <-> Modul, generiert, mit Drift-Report (D4).

Fachtragende Module annotieren sich mit einer Zeile ``Knoten: <id>`` im
Modul-Docstring. Dieses Werkzeug baut daraus den bidirektionalen Index
(nie handgepflegt) und meldet Drift in beide Richtungen:

* T-Box-Familien ohne annotiertes Modul — ein Fachknoten ohne
  Implementierungs-Ort (P6 auf die Codebasis angewandt),
* Module ohne Knoten-Annotation — als Bestandsaufnahme ausgewiesen
  (die technische Rueckgrat-Schicht steht bewusst ausserhalb des
  ontologischen Schnitts und ist hier gelistet, nicht verboten).

Der Index ist die Grundlage fuer "Fundstelle ableitbar statt suchbar":
die Frage "wo lebt klv?" ist ein Lookup, kein grep.

Run via::

    python -m rechner_pipeline.ontologie.code_index [--src src/rechner_pipeline]

Knoten: klv
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

_ANNOTATION = re.compile(r"^Knoten:\s*([a-z0-9_/,: .-]+?)\s*$", re.MULTILINE)


def baue_index(src: Path) -> Dict[str, object]:
    """Den Index aus den Modul-Docstrings bauen (deterministisch)."""
    import ast

    knoten_zu_modulen: Dict[str, List[str]] = {}
    unannotiert: List[str] = []
    for pfad in sorted(src.rglob("*.py")):
        if "__pycache__" in pfad.parts:
            continue
        rel = str(pfad.relative_to(src.parent))
        try:
            baum = ast.parse(pfad.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            unannotiert.append(rel)
            continue
        doc = ast.get_docstring(baum) or ""
        treffer = _ANNOTATION.findall(doc)
        if not treffer:
            unannotiert.append(rel)
            continue
        for zeile in treffer:
            for knoten in [k.strip() for k in zeile.split(",") if k.strip()]:
                module = knoten_zu_modulen.setdefault(knoten, [])
                if rel not in module:          # Doppel-Annotation dedupen
                    module.append(rel)
    module_zu_knoten = {
        modul: sorted(
            k for k, module in knoten_zu_modulen.items() if modul in module
        )
        for module in knoten_zu_modulen.values() for modul in module
    }
    return {
        "knoten": {k: sorted(v) for k, v in sorted(knoten_zu_modulen.items())},
        "module": dict(sorted(module_zu_knoten.items())),
        "unannotiert": sorted(unannotiert),
    }


def drift_report(index: Dict[str, object], familien: List[str]) -> List[str]:
    """Fachknoten ohne Implementierungs-Ort (leer = kein Drift)."""
    return [
        f"Familie {familie!r}: kein annotiertes Modul (Knoten ohne Code)"
        for familie in familien
        if familie not in index["knoten"]
    ]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.ontologie.code_index",
        description="Ontologie-Code-Index bauen (Knoten <-> Modul, Drift).",
    )
    parser.add_argument("--src", default="src/rechner_pipeline")
    args = parser.parse_args(argv)
    src = Path(args.src)
    if not src.is_dir():
        print(f"code_index: kein Verzeichnis: {src}", file=sys.stderr)
        return 2
    index = baue_index(src)
    # Familien aus der T-Box ableiten, nicht hart kodieren.
    import typing

    from rechner_pipeline.ontologie.tbox import Tarifgeneration

    familien = list(typing.get_args(
        Tarifgeneration.model_fields["familie"].annotation
    ))
    drift = drift_report(index, familien)
    print(json.dumps(
        {**index, "drift": drift}, ensure_ascii=False, indent=2,
        sort_keys=True,
    ))
    return 1 if drift else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
