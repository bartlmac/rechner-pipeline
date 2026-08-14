"""``tarifplan_staging`` toolbox command — Migrationsartefakte nach JSON.

Architektur-Entscheidung (Bartek, 2026-08-13): Tarifplan-Dokumente von zu
migrierenden Bestaenden (DOCX der Quellsysteme) sind MIGRATIONSARTEFAKTE.
Sie gehoeren nicht in die Zielkern-Dokumentation (dort leben neu verfasste
Tarifplaene in der Mathematik des Kerns, ``docs/tarifplaene/``), sondern in
ein maschinenlesbares Staging: dieses Kommando extrahiert die Inhalte eines
DOCX strukturiert nach JSON (``runs/migrationsstaging/``) — nicht fuer Menschen
formatiert, sondern als Datenvorbereitung fuer die Migration (Abgleich mit
Geschaeftsplan/Quellsystem, spaeterer Migrations-Contract).

Stdlib-only: ein DOCX ist ein ZIP mit XML — gelesen werden
``word/document.xml`` (Absaetze mit Formatvorlagen, Tabellen als
Zellmatrizen, OMML-Formeln als Rohtext) und ``docProps/core.xml``
(Metadaten). Deterministisch: gleiche Datei -> byte-gleiches JSON (keine
Zeitstempel; der SHA-256 der Quelle ist Teil des Outputs).

Usage::

    python -m rechner_pipeline.quellen.tarifplan_staging \\
        --docx examples/Mitteilung_143_KLV_TG2012.docx \\
        --out runs/migrationsstaging/klv_mitteilung_143.json
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional

from rechner_pipeline.models.manifest import file_sha256

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
_CORE = "{http://purl.org/dc/elements/1.1/}"


def _text(element: ET.Element) -> str:
    """Sichtbarer Text eines Elements (w:t- und m:t-Runs, in Dokumentreihenfolge)."""
    teile: List[str] = []
    for node in element.iter():
        if node.tag in (f"{_W}t", f"{_M}t") and node.text:
            teile.append(node.text)
    return "".join(teile)


def _zellen_text(zelle: ET.Element) -> str:
    """Zellentext mit Zeilenumbruechen zwischen Absaetzen/inneren Tabellen
    (Review-Fix: vorher klebten Mehrfach-Absaetze und verschachtelte
    Tabellen separatorlos aneinander)."""
    teile = [
        _text(kind)
        for kind in zelle
        if kind.tag in (f"{_W}p", f"{_W}tbl")
    ]
    return "\n".join(teil.strip() for teil in teile if teil.strip())


def _inhalts_kinder(container: ET.Element) -> List[ET.Element]:
    """Direkte Inhalts-Elemente inkl. Entpacken von w:sdt-Containern
    (Content Controls, Inhaltsverzeichnisse — Review-Fix: deren Absaetze
    und Tabellen fielen vorher stillschweigend weg)."""
    kinder: List[ET.Element] = []
    for kind in container:
        if kind.tag == f"{_W}sdt":
            inhalt = kind.find(f"{_W}sdtContent")
            if inhalt is not None:
                kinder.extend(_inhalts_kinder(inhalt))
        else:
            kinder.append(kind)
    return kinder


def _stil(absatz: ET.Element) -> str:
    stil = absatz.find(f"{_W}pPr/{_W}pStyle")
    return stil.get(f"{_W}val", "") if stil is not None else ""


def extrahiere(docx_pfad: Path) -> Dict[str, Any]:
    """DOCX strukturiert nach dict (Absaetze, Tabellen, Formeln, Metadaten)."""
    with zipfile.ZipFile(docx_pfad) as archiv:
        dokument = ET.fromstring(archiv.read("word/document.xml"))
        metadaten: Dict[str, str] = {}
        try:
            core = ET.fromstring(archiv.read("docProps/core.xml"))
            for feld in ("title", "subject", "creator", "description"):
                knoten = core.find(f"{_CORE}{feld}")
                if knoten is not None and knoten.text:
                    metadaten[feld] = knoten.text
        except KeyError:
            pass

    body = dokument.find(f"{_W}body")
    if body is None:
        raise ET.ParseError("document.xml ohne w:body")
    absaetze: List[Dict[str, Any]] = []
    tabellen: List[Dict[str, Any]] = []
    # Formeln GLOBAL einsammeln (OMML steckt bei Tabellen-Layouts der
    # Quelldokumente typischerweise in Zellen, nicht in Top-Level-Absaetzen):
    formeln: List[str] = [
        inhalt
        for formel in body.iter(f"{_M}oMath")
        if (inhalt := _text(formel))
    ]

    for kind in _inhalts_kinder(body):
        if kind.tag == f"{_W}p":
            text = _text(kind)
            if text.strip():
                absaetze.append({"stil": _stil(kind), "text": text.strip()})
        elif kind.tag == f"{_W}tbl":
            # Leere Zeilen bleiben erhalten — die Zeilen-Indizes entsprechen
            # der Quelltabelle (Review-Fix).
            zeilen: List[List[str]] = []
            for zeile in kind.findall(f"{_W}tr"):
                zeilen.append(
                    [_zellen_text(zelle) for zelle in zeile.findall(f"{_W}tc")]
                )
            tabellen.append({"index": len(tabellen), "zeilen": zeilen})

    return {
        "quelle": str(docx_pfad),
        "quelle_sha256": file_sha256(docx_pfad),
        "metadaten": metadaten,
        "absaetze": absaetze,
        "tabellen": tabellen,
        "formeln": formeln,
        "hinweis": (
            "Migrationsartefakt-Staging: strukturierte Rohdaten fuer die "
            "Migration, kein Zielkern-Tarifplan (siehe docs/tarifplaene/). "
            "Formel-Inhalte (OMML) stehen in 'formeln' UND unmarkiert im "
            "Absatz-/Zellentext (m:t-Runs); eine positionsgenaue "
            "Formel-Zuordnung ist bewusst nicht Teil dieser Stufe."
        ),
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.quellen.tarifplan_staging",
        description=(
            "Migrationsartefakt (DOCX-Tarifplan) strukturiert nach JSON "
            "extrahieren. Producer, kein Gate."
        ),
    )
    parser.add_argument("--docx", required=True, help="Quell-DOCX (Migrationsartefakt).")
    parser.add_argument("--out", required=True, help="Ziel-JSON (runs/migrationsstaging/...).")
    ns = parser.parse_args(argv)

    docx_pfad = Path(ns.docx)
    if not docx_pfad.is_file():
        print(f"tarifplan_staging: DOCX nicht gefunden: {docx_pfad}", file=sys.stderr)
        return 2
    try:
        daten = extrahiere(docx_pfad)
    except (zipfile.BadZipFile, ET.ParseError, KeyError) as exc:
        print(f"tarifplan_staging: DOCX nicht lesbar: {exc}", file=sys.stderr)
        return 2

    out_pfad = Path(ns.out)
    out_pfad.parent.mkdir(parents=True, exist_ok=True)
    out_pfad.write_text(
        json.dumps(daten, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(
        f"tarifplan_staging: {len(daten['absaetze'])} Absaetze, "
        f"{len(daten['tabellen'])} Tabellen, {len(daten['formeln'])} Formeln "
        f"-> {out_pfad}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
