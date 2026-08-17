"""Landkarte: die Ontologie-Sicht auf die Codebasis als eine HTML-Datei.

Erzeugt aus ``code_index``, ``code_karte`` und ``impact`` eine
selbsttragende Seite: Knotenbaum, Test-Bindungen, Erlaubnismatrix der
Schichten und eine Auswahl gerechneter Impact-Szenarien zum
Durchklicken. Zweck ist das Vorfuehren und Nachvollziehen der
1M-LOC-Mechanik (ADR-005) — fuer Menschen, die dem System ansehen
sollen, dass Kontext- und Pruefaufwand an der Aenderung haengen, nicht
am Bestand.

Bewusst OHNE Layout-Engine und ohne neue Abhaengigkeit: Graphviz
braucht ein System-Binary (widerspricht der Multiplattform-Regel),
kraftbasierte Layouts (D3, vis-network, pyvis) liefern bei jedem Lauf
ein anderes Bild und damit keine diffbare Ausgabe. Die Seite zeigt
stattdessen Tabellen, eine Matrix und Listen — bei 93 Modulen
lesbarer als ein Knaeuel, und bei 1000+ erst recht.

Deterministisch: gleicher Repo-Stand -> byte-identische Datei. Es gibt
keinen Zeitstempel in der Ausgabe; wer einen Stand benennen will,
uebergibt ihn selbst (``--stand``).

Run via::

    python -m rechner_pipeline.ontologie.landkarte --out landkarte.html
    python -m rechner_pipeline.ontologie.landkarte --out x.html \\
        --szenario src/rechner_pipeline/kern/produkte/bu.py --stand "v0.1"

Knoten: system/architektur
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

VORLAGE = Path(__file__).with_name("landkarte_vorlage.html")
PLATZHALTER = "__DATEN__"

#: Aenderung, die immer konservativ ausfaellt — zeigt den Fail-safe-Fall.
KONSERVATIVES_SZENARIO = "pyproject.toml"


def standard_szenarien(
    index: Dict[str, object], karte: Dict[str, object]
) -> List[tuple]:
    """Je Knoten ein kennzeichnendes Modul, plus der Fail-safe-Fall.

    Kennzeichnend heisst: ein Modul, das GENAU diesen Knoten traegt —
    dann zeigt das Szenario die Selektion dieses Knotens und nicht die
    Vereinigung mehrerer. Unter diesen faellt die Wahl auf das groesste
    (die Zeilenzahl ist ein brauchbarer Hinweis darauf, wo der Knoten
    seinen Schwerpunkt hat); ohne exklusiven Traeger auf das erste
    Modul des Knotens. Rein deterministisch und selbstpflegend: neue
    Knoten erscheinen von allein, verschwundene fallen weg.

    Liefert Paare ``(pfad, beschriftung)``.
    """
    module_zu_knoten: Dict[str, List[str]] = index["module"]
    knoten_zu_modulen: Dict[str, List[str]] = index["knoten"]
    zeilen = {m: d["zeilen"] for m, d in karte["module"].items()}
    gewaehlt: List[tuple] = []
    gesehen = set()
    for knoten in sorted(knoten_zu_modulen):
        module = sorted(knoten_zu_modulen[knoten])
        exklusiv = [m for m in module if module_zu_knoten.get(m) == [knoten]]
        kandidaten = exklusiv or module
        kandidat = max(kandidaten, key=lambda m: (zeilen.get(m, 0), m))
        pfad = "src/" + kandidat
        if pfad in gesehen:
            continue
        gesehen.add(pfad)
        gewaehlt.append((pfad, f"{knoten} · {Path(pfad).name}"))
    gewaehlt.append(
        (KONSERVATIVES_SZENARIO, "Projekt-Konfiguration (Fail-safe)"))
    return gewaehlt


def sammle(
    src: Path,
    tests: Path,
    faelle: Path,
    szenarien: Optional[List[str]] = None,
    repo_root: Optional[Path] = None,
) -> Dict[str, object]:
    """Alle Daten der Landkarte einsammeln (deterministisch, sortiert)."""
    from rechner_pipeline.ontologie.code_index import (
        baue_index,
        baue_test_bindung,
    )
    from rechner_pipeline.ontologie.code_karte import SCHICHT_ERLAUBT, baue_karte
    from rechner_pipeline.ontologie.impact import (
        berechne_impact,
        import_kanten_je_testmodul,
        lade_faelle_generationen,
    )

    index = baue_index(src)
    karte = baue_karte(src)
    bindung = baue_test_bindung(tests)["bindung"]
    test_imports = import_kanten_je_testmodul(tests, src)
    generationen = lade_faelle_generationen(faelle)

    pfade = (
        [(p, f"{Path(p).name}") for p in szenarien] if szenarien
        else standard_szenarien(index, karte)
    )
    berechnet = []
    for pfad, beschriftung in pfade:
        ergebnis = berechne_impact(
            [pfad], index, karte, bindung, generationen,
            test_imports, repo_root,
        )
        berechnet.append({
            "titel": beschriftung,
            "dateien": [pfad],
            "knoten": ergebnis["knoten"],
            "tests": ergebnis["tests"],
            "konservativ": ergebnis["konservativ"],
            "weitere_lader": ergebnis["weitere_lader"],
            "faelle": [f["generation"] for f in ergebnis["faelle"]],
            "hinweise": ergebnis["hinweise"],
        })

    schichten: Dict[str, Dict[str, int]] = {}
    for daten in karte["module"].values():
        eintrag = schichten.setdefault(
            daten["schicht"], {"module": 0, "zeilen": 0})
        eintrag["module"] += 1
        eintrag["zeilen"] += daten["zeilen"]

    schicht_kanten: Dict[str, int] = {}
    for kante in karte["kanten"]:
        von = karte["module"][kante["von"]]["schicht"]
        nach = karte["module"][kante["nach"]]["schicht"]
        if von != nach:
            schluessel = f"{von}>{nach}"
            schicht_kanten[schluessel] = schicht_kanten.get(schluessel, 0) + 1

    return {
        "knoten": index["knoten"],
        "test_bindung": bindung,
        "schichten": dict(sorted(schichten.items())),
        "schicht_kanten": dict(sorted(schicht_kanten.items())),
        "erlaubt": {k: sorted(v) for k, v in sorted(SCHICHT_ERLAUBT.items())},
        "szenarien": berechnet,
        "faelle": generationen,
        "gesamt": {
            "module": len(karte["module"]),
            "kanten": len(karte["kanten"]),
            "tests": len(bindung),
            "zeilen": sum(d["zeilen"] for d in karte["module"].values()),
        },
    }


def rendere(daten: Dict[str, object], stand: str = "") -> str:
    """Vorlage mit den Daten fuellen (eine selbsttragende HTML-Datei)."""
    vorlage = VORLAGE.read_text(encoding="utf-8")
    if PLATZHALTER not in vorlage:
        raise ValueError(
            f"{VORLAGE.name}: Platzhalter {PLATZHALTER} fehlt — die Vorlage "
            "gehoert zum Generator und darf ihn nicht verlieren"
        )
    nutzlast = dict(daten)
    nutzlast["stand"] = stand
    # separators + sort_keys: gleicher Stand -> byte-identische Datei.
    return vorlage.replace(PLATZHALTER, json.dumps(
        nutzlast, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.ontologie.landkarte",
        description=(
            "Landkarte der Codebasis als eine selbsttragende HTML-Datei."
        ),
    )
    parser.add_argument("--out", required=True, help="Zieldatei (.html)")
    parser.add_argument("--src", default="src/rechner_pipeline")
    parser.add_argument("--tests", default="tests")
    parser.add_argument("--faelle", default="faelle")
    parser.add_argument(
        "--szenario", action="append", default=[],
        help="Szenario-Pfad (mehrfach; ohne Angabe: je Knoten eines)",
    )
    parser.add_argument(
        "--stand", default="",
        help="frei waehlbare Stand-Bezeichnung fuer den Seitenkopf "
             "(z. B. ein Git-Kurz-SHA); leer bleibt leer, damit die "
             "Ausgabe reproduzierbar ist",
    )
    parser.add_argument("--repo-root", dest="repo_root", default=None)
    args = parser.parse_args(argv)

    src, tests = Path(args.src), Path(args.tests)
    if not src.is_dir() or not tests.is_dir():
        print(f"landkarte: --src {src} und --tests {tests} muessen "
              "Verzeichnisse sein", file=sys.stderr)
        return 2
    daten = sammle(
        src, tests, Path(args.faelle), args.szenario or None,
        Path(args.repo_root) if args.repo_root else None,
    )
    ziel = Path(args.out)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(rendere(daten, args.stand), encoding="utf-8")
    print(json.dumps({
        "datei": str(ziel),
        "bytes": ziel.stat().st_size,
        "module": daten["gesamt"]["module"],
        "testmodule": daten["gesamt"]["tests"],
        "szenarien": [s["titel"] for s in daten["szenarien"]],
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
