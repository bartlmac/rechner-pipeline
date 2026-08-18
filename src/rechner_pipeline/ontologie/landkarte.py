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

    python -m rechner_pipeline.ontologie.landkarte --out runs/landkarte.html
    python -m rechner_pipeline.ontologie.landkarte --out runs/x.html \\
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


# --------------------------------------------------------------------------- #
# Graph-Export in Standardformate — das Zeichnen macht fremdes Werkzeug
# --------------------------------------------------------------------------- #


#: Obergrenze fuer eine zeichenbare Sicht. Darueber ist jedes Bild ein
#: Knaeuel — dann ist nicht das Werkzeug schuld, sondern der Ausschnitt.
MAX_KNOTEN = 60


def graph(
    karte: Dict[str, object],
    index: Optional[Dict[str, object]] = None,
    umfang: str = "schichten",
    auswahl: Optional[str] = None,
    max_knoten: int = MAX_KNOTEN,
) -> tuple:
    """Knoten und Kanten einer ZEICHENBAREN Sicht (deterministisch sortiert).

    Im Zielbild (~1 Mio. Zeilen) gibt es kein Bild "der Codebasis" — es
    gibt begrenzte Ausschnitte. Die drei, die mitwachsen:

    * ``schichten`` — der Ueberblick. Eine Schicht ist ein Knoten, die
      Kante traegt die Zahl der Import-Beziehungen. Waechst mit der
      Zahl der Schichten, nicht mit der Codemenge.
    * ``knoten`` — die FACHLICHE Sicht: ein Ontologie-Knoten je Kasten,
      Kanten sind aggregierte Abhaengigkeiten zwischen ihnen. Das ist
      die Sicht, die bei 1 Mio. Zeilen noch eine Seite fuellt statt
      einer Wand.
    * ``modul`` mit ``auswahl`` — hinein in EINEN Knoten (``klv/tg2015``)
      oder EINE Schicht (``kern``). Begrenzt durch die Groesse des
      Gegenstands, nicht des Systems.

    Ueberschreitet die Sicht ``max_knoten``, ist das ein Fehler mit
    Ausweg in der Meldung — kein unlesbares Bild.
    """
    module = karte["module"]

    if umfang == "schichten":
        groesse: Dict[str, int] = {}
        for daten in module.values():
            groesse[daten["schicht"]] = groesse.get(daten["schicht"], 0) + 1
        knoten = [(s, f"{s}\n{n} Module") for s, n in sorted(groesse.items())]
        gewicht: Dict[tuple, int] = {}
        for kante in karte["kanten"]:
            von = module[kante["von"]]["schicht"]
            nach = module[kante["nach"]]["schicht"]
            if von != nach:
                gewicht[(von, nach)] = gewicht.get((von, nach), 0) + 1
        kanten = [(v, n, str(g)) for (v, n), g in sorted(gewicht.items())]
        titel = "Schichten"

    elif umfang == "knoten":
        if index is None:
            raise ValueError("umfang 'knoten' braucht den Code-Index")
        m2k: Dict[str, List[str]] = index["module"]
        anzahl: Dict[str, int] = {}
        for modul, ks in m2k.items():
            for k in ks:
                anzahl[k] = anzahl.get(k, 0) + 1
        knoten = [
            (k, f"{k}\n{n} Module") for k, n in sorted(anzahl.items())
        ]
        # Eine Kante a -> b entsteht NUR, wenn der Uebergang echt ist:
        # das importierende Modul traegt a und nicht b, das importierte
        # traegt b und nicht a. Sonst liegt die Abhaengigkeit innerhalb
        # eines geteilten Knotens — ein Rueckgrat-Modul (klv, bu) macht
        # KLV nicht von BU abhaengig, beide stehen darauf.
        gewicht = {}
        for kante in karte["kanten"]:
            von_k = set(m2k.get(kante["von"], ()))
            nach_k = set(m2k.get(kante["nach"], ()))
            for a in sorted(von_k - nach_k):
                for b in sorted(nach_k - von_k):
                    gewicht[(a, b)] = gewicht.get((a, b), 0) + 1
        kanten = [(v, n, str(g)) for (v, n), g in sorted(gewicht.items())]
        titel = "Fachknoten"

    elif umfang == "modul":
        if not auswahl:
            raise ValueError(
                "umfang 'modul' braucht --knoten <id> oder --schicht <name>")
        if index is not None and auswahl in index["knoten"]:
            drin = sorted(index["knoten"][auswahl])
        else:
            drin = sorted(
                m for m, d in module.items() if d["schicht"] == auswahl)
        if not drin:
            bekannt = sorted({d["schicht"] for d in module.values()})
            raise ValueError(
                f"{auswahl!r} ist weder Knoten noch Schicht "
                f"(Schichten: {', '.join(bekannt)})"
            )
        knoten = [(m, Path(m).stem) for m in drin]
        innen = set(drin)
        kanten = sorted(
            (k["von"], k["nach"], "")
            for k in karte["kanten"]
            if k["von"] in innen and k["nach"] in innen
            and k["von"] != k["nach"]
        )
        titel = auswahl
    else:
        raise ValueError(
            f"unbekannter Umfang {umfang!r} (schichten|knoten|modul)")

    if len(knoten) > max_knoten:
        raise ValueError(
            f"Sicht {titel!r} haette {len(knoten)} Kaesten (Grenze "
            f"{max_knoten}) — ein Bild dieser Groesse ist unlesbar. "
            "Engeren Ausschnitt waehlen: --umfang knoten fuer die "
            "fachliche Sicht, oder --umfang modul --auswahl <knoten-id>."
        )
    return knoten, kanten, titel


def _kennung(name: str) -> str:
    """Graph-taugliche Kennung aus einem Modulpfad/Schichtnamen."""
    sicher = "".join(c if c.isalnum() else "_" for c in name)
    return sicher if sicher[:1].isalpha() else "n" + sicher


def als_mermaid(knoten, kanten, titel: str) -> str:
    """Mermaid-Flowchart — GitHub zeichnet das direkt in Markdown."""
    zeilen = [f"%% {titel} — erzeugt von ontologie.landkarte",
              "flowchart TD"]
    for name, beschriftung in knoten:
        text = beschriftung.replace("\n", "<br/>")
        zeilen.append(f'    {_kennung(name)}["{text}"]')
    for von, nach, marke in kanten:
        pfeil = f"-- {marke} -->" if marke else "-->"
        zeilen.append(f"    {_kennung(von)} {pfeil} {_kennung(nach)}")
    return "\n".join(zeilen) + "\n"


def als_dot(knoten, kanten, titel: str) -> str:
    """Graphviz-DOT — Eingabe fuer dot, Gephi und viele andere."""
    zeilen = [f'digraph "{titel}" {{', "  rankdir=TB;",
              '  node [shape=box, fontname="Helvetica"];']
    for name, beschriftung in knoten:
        text = beschriftung.replace("\n", "\\n")   # DOT-Zeilenumbruch
        zeilen.append(f'  {_kennung(name)} [label="{text}"];')
    for von, nach, marke in kanten:
        zusatz = f' [label="{marke}"]' if marke else ""
        zeilen.append(f"  {_kennung(von)} -> {_kennung(nach)}{zusatz};")
    zeilen.append("}")
    return "\n".join(zeilen) + "\n"


def als_graphml(knoten, kanten, titel: str) -> str:
    """GraphML — Eingabe fuer Gephi, yEd, Neo4j-Import."""
    from xml.sax.saxutils import escape, quoteattr

    zeilen = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
        '  <key id="d0" for="node" attr.name="label" attr.type="string"/>',
        '  <key id="d1" for="edge" attr.name="gewicht" attr.type="string"/>',
        f"  <graph id={quoteattr(titel)} edgedefault=\"directed\">",
    ]
    for name, beschriftung in knoten:
        zeilen.append(
            f"    <node id={quoteattr(name)}>"
            f"<data key=\"d0\">"
            f"{escape(beschriftung.replace(chr(10), ' '))}</data></node>")
    for i, (von, nach, marke) in enumerate(kanten):
        zeilen.append(
            f'    <edge id="e{i}" source={quoteattr(von)} '
            f"target={quoteattr(nach)}>"
            f"<data key=\"d1\">{escape(marke)}</data></edge>")
    zeilen += ["  </graph>", "</graphml>"]
    return "\n".join(zeilen) + "\n"


FORMATE = {"mermaid": als_mermaid, "dot": als_dot, "graphml": als_graphml}


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
    parser.add_argument(
        "--format", dest="format", default="html",
        choices=["html", *sorted(FORMATE)],
        help="html = die Seite; mermaid/dot/graphml = Graph-Text fuer "
             "fremde Zeichenwerkzeuge (GitHub, Graphviz, Gephi, yEd)",
    )
    parser.add_argument(
        "--umfang", default="schichten",
        choices=["schichten", "knoten", "modul"],
        help="Ausschnitt des Graphen: schichten (Ueberblick), knoten "
             "(fachliche Sicht), modul (in EINEN Knoten/eine Schicht "
             "hinein, mit --auswahl)",
    )
    parser.add_argument(
        "--auswahl", default=None,
        help="Knoten-ID (klv/tg2015) oder Schichtname (kern) fuer "
             "--umfang modul",
    )
    parser.add_argument("--max-knoten", dest="max_knoten",
                        type=int, default=MAX_KNOTEN)
    args = parser.parse_args(argv)

    src, tests = Path(args.src), Path(args.tests)
    if not src.is_dir() or not tests.is_dir():
        print(f"landkarte: --src {src} und --tests {tests} muessen "
              "Verzeichnisse sein", file=sys.stderr)
        return 2

    if args.format != "html":
        from rechner_pipeline.ontologie.code_index import baue_index
        from rechner_pipeline.ontologie.code_karte import baue_karte

        try:
            knoten, kanten, titel = graph(
                baue_karte(src), baue_index(src),
                args.umfang, args.auswahl, args.max_knoten,
            )
        except ValueError as exc:
            print(f"landkarte: {exc}", file=sys.stderr)
            return 2
        ziel = Path(args.out)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_text(
            FORMATE[args.format](knoten, kanten, titel), encoding="utf-8")
        print(json.dumps({
            "datei": str(ziel), "format": args.format, "titel": titel,
            "kaesten": len(knoten), "kanten": len(kanten),
        }, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

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
