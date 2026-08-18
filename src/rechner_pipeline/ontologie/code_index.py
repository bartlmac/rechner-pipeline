"""Ontologie-Code-Index: Knoten <-> Modul/Test, generiert, mit Drift-Report (D4).

Fachtragende Module UND Testmodule annotieren sich mit einer Zeile
``Knoten: <id>`` im Modul-Docstring. Dieses Werkzeug baut daraus den
bidirektionalen Index (nie handgepflegt) und meldet Drift:

* T-Box-Familien ohne annotiertes Modul — ein Fachknoten ohne
  Implementierungs-Ort (P6 auf die Codebasis angewandt),
* Knoten mit unbekannter Wurzel — die erste Ebene einer Knoten-ID muss
  eine T-Box-Familie, ein registriertes Kern-Produkt oder die
  System-Wurzel ``system`` sein (Tippfehler-Schutz; tiefere Ebenen wie
  ``klv/tg2015`` sind Instanzen und bewusst offen),
* Testmodule ohne Knoten-Bindung — jede Testdatei erklaert, welchen
  Fachknoten sie verankert; das ist die Grundlage der
  Impact-Berechnung (``ontologie.impact``),
* Module ohne Knoten-Annotation — ein HARTER Befund fuer jedes
  Modul ausser ``__init__.py`` (Beschluss Bartek 2026-08-18: kein
  Rechenkern-Baustein ohne ontologischen Knoten; Paket-Initialisierer
  ohne eigenes Fachverhalten sind die einzige Ausnahme und bleiben als
  Bestandsaufnahme gelistet).

Knoten-IDs sind hierarchisch (``familie[/generation[/zelle]]``,
``ontologie.ids.knoten_id``): Code bindet an die groebste Ebene, die er
fachlich traegt (eine neue Generation ist Parametrierung — kein Code),
Tests und Daten binden so fein wie ihr Gegenstand.

Der Index ist die Grundlage fuer "Fundstelle ableitbar statt suchbar":
die Frage "wo lebt klv?" ist ein Lookup, kein grep.

Run via::

    python -m rechner_pipeline.ontologie.code_index \\
        [--src src/rechner_pipeline] [--tests tests]

Knoten: system/architektur
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

_ANNOTATION = re.compile(r"^Knoten:\s*([a-z0-9_/,: .-]+?)\s*$", re.MULTILINE)

#: Erlaubte Nicht-Fach-Wurzeln fuer Knoten-IDs (Werkzeug-/Systemstraenge).
SYSTEM_WURZELN = frozenset({"system"})


def _annotationen(pfad: Path) -> Optional[List[str]]:
    """Knoten-IDs aus dem Modul-Docstring (None = unlesbar/unannotiert)."""
    import ast

    try:
        baum = ast.parse(pfad.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return None
    doc = ast.get_docstring(baum) or ""
    knoten: List[str] = []
    for zeile in _ANNOTATION.findall(doc):
        for k in [k.strip() for k in zeile.split(",") if k.strip()]:
            if k not in knoten:
                knoten.append(k)
    return knoten or None


def baue_index(src: Path) -> Dict[str, object]:
    """Den Index aus den Modul-Docstrings bauen (deterministisch)."""
    knoten_zu_modulen: Dict[str, List[str]] = {}
    unannotiert: List[str] = []
    for pfad in sorted(src.rglob("*.py")):
        if "__pycache__" in pfad.parts:
            continue
        rel = str(pfad.relative_to(src.parent))
        knoten = _annotationen(pfad)
        if not knoten:
            unannotiert.append(rel)
            continue
        for k in knoten:
            module = knoten_zu_modulen.setdefault(k, [])
            if rel not in module:              # Doppel-Annotation dedupen
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


def baue_test_bindung(tests: Path) -> Dict[str, object]:
    """Knoten-Bindung der Testmodule (``tests/test_*.py``) einsammeln.

    Ungebundene Testdateien sind ein Befund, kein stiller Zustand:
    ohne Bindung kann die Impact-Berechnung diesen Test nur noch
    konservativ (immer) einplanen.
    """
    bindung: Dict[str, List[str]] = {}
    ohne: List[str] = []
    for pfad in sorted(tests.glob("test_*.py")):
        knoten = _annotationen(pfad)
        if not knoten:
            ohne.append(pfad.name)
            continue
        bindung[pfad.name] = sorted(knoten)
    return {"bindung": dict(sorted(bindung.items())), "ohne_bindung": ohne}


def erlaubte_wurzeln() -> List[str]:
    """Fachliche Wurzeln: T-Box-Familien + Kern-Produkt-Registry + system.

    Ein Fachknoten ist entweder eine migrierte Produktfamilie (T-Box)
    oder ein registriertes Kern-Produkt (das noch keinen Migrationsfall
    hat, wie BU). Lesende Registry-Introspektion, keine Fachformel.
    """
    import typing

    from rechner_pipeline.kern.produkte import PRODUKTE
    from rechner_pipeline.ontologie.tbox import Tarifgeneration

    familien = list(typing.get_args(
        Tarifgeneration.model_fields["familie"].annotation
    ))
    return sorted({*familien, *PRODUKTE, *SYSTEM_WURZELN})


def drift_report(
    index: Dict[str, object],
    familien: List[str],
    wurzeln: Optional[List[str]] = None,
    test_bindung: Optional[Dict[str, object]] = None,
) -> List[str]:
    """Alle Drift-Befunde (leer = kein Drift)."""
    befunde = [
        f"Familie {familie!r}: kein annotiertes Modul (Knoten ohne Code)"
        for familie in familien
        if familie not in index["knoten"]
    ]
    if wurzeln is not None:
        alle_knoten = set(index["knoten"])
        if test_bindung is not None:
            for ks in test_bindung["bindung"].values():
                alle_knoten.update(ks)
        for k in sorted(alle_knoten):
            wurzel = k.split("/", 1)[0]
            if wurzel not in wurzeln:
                befunde.append(
                    f"Knoten {k!r}: unbekannte Wurzel {wurzel!r} "
                    f"(erlaubt: {', '.join(wurzeln)})"
                )
    for modul in index.get("unannotiert", []):
        if not modul.endswith("__init__.py"):
            befunde.append(
                f"Modul {modul}: keine Knoten-Annotation — kein Baustein "
                "ohne ontologischen Knoten (Zeile 'Knoten: <id>' im "
                "Modul-Docstring ergaenzen)"
            )
    if test_bindung is not None:
        for name in test_bindung["ohne_bindung"]:
            befunde.append(
                f"Testmodul {name}: keine Knoten-Bindung "
                "(Zeile 'Knoten: <id>' im Modul-Docstring ergaenzen)"
            )
    return befunde


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.ontologie.code_index",
        description=(
            "Ontologie-Code-Index bauen (Knoten <-> Modul/Test, Drift)."
        ),
    )
    parser.add_argument("--src", default="src/rechner_pipeline")
    parser.add_argument(
        "--tests", default=None,
        help="Testverzeichnis fuer die Knoten-Bindung (ohne Angabe: kein "
             "Test-Scan — rueckwaertskompatibler Modul-Index)",
    )
    args = parser.parse_args(argv)
    src = Path(args.src)
    if not src.is_dir():
        print(f"code_index: kein Verzeichnis: {src}", file=sys.stderr)
        return 2
    index = baue_index(src)
    test_bindung = None
    if args.tests is not None:
        tests = Path(args.tests)
        if not tests.is_dir():
            print(f"code_index: kein Verzeichnis: {tests}", file=sys.stderr)
            return 2
        test_bindung = baue_test_bindung(tests)
    # Familien aus der T-Box ableiten, nicht hart kodieren.
    import typing

    from rechner_pipeline.ontologie.tbox import Tarifgeneration

    familien = list(typing.get_args(
        Tarifgeneration.model_fields["familie"].annotation
    ))
    drift = drift_report(index, familien, erlaubte_wurzeln(), test_bindung)
    ausgabe = {**index, "drift": drift}
    if test_bindung is not None:
        ausgabe["tests"] = test_bindung["bindung"]
    print(json.dumps(ausgabe, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if drift else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
