#!/usr/bin/env python3
"""Der Aufwand der Agenten eines Falls — aus ihren Sitzungsprotokollen
festgehalten.

Jede Antwort im Protokoll einer Agentensitzung traegt den Verbrauch, den
das Modell fuer sie gemeldet hat (Eingabe, Cache schreiben, Cache lesen,
Ausgabe). Das Werkzeug summiert ihn je Rolle und schreibt
``abgeleitet/aufwand.json`` in den Fall, mit der SHA-256 jedes
Protokolls, aus dem es gezaehlt hat.

Gezaehlt wird jede Antwort EINMAL: Eine Antwort aus mehreren Teilen (Text
und Werkzeugaufruf) steht im Protokoll in mehreren Zeilen mit derselben
Kennung und demselben vollstaendigen Verbrauch — zeilenweise summiert,
zaehlte sie doppelt und dreifach (gemessen an Fall 3, 04.10.2026).

Welche Sitzung zu welcher Rolle gehoert, liest das Werkzeug aus dem
Protokoll selbst (``--protokolle ORDNER``): Claude Code haelt fest, mit
welcher Agentenrolle eine Sitzung gestartet wurde (``agent-setting``,
gesetzt von ``claude --agent <rolle>``). Gezaehlt wird nur, was eine Rolle
der Agentendefinitionen traegt und eine Antwort hat; Sitzungen ohne
Agentenrolle (etwa Proben) bleiben draussen. ``--name-praefix`` trennt
Faelle, die sich einen Ordner teilen (``agent-name``). Von Hand geht es
mit ``--sitzung ROLLE=PROTOKOLL``; eine Rolle, die es nicht gibt, bricht
ab. Eine vorhandene Datei wird nicht ueberschrieben: Was festgehalten
ist, bleibt.

Die Dauer steht nicht hier — sie folgt aus den Entscheid-Snapshots des
Falls und wird beim Seitenbau gemessen (``falldaten.aufwand``).

Aufruf::

    python werkzeuge/aufwand.py --fall faelle/<fall> \\
        --protokolle ~/.claude/projects/<ordner-des-arbeitsbaums> --name-praefix fall3-
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ZIEL = "abgeleitet/aufwand.json"
FELDER = (("eingabe", "input_tokens"), ("cache_schreiben", "cache_creation_input_tokens"),
          ("cache_lesen", "cache_read_input_tokens"), ("ausgabe", "output_tokens"))


class AufwandFehler(Exception):
    """Ein Aufruf, aus dem kein belastbarer Aufwand entsteht."""


def rollen() -> List[str]:
    """Die Agentenrollen, die es gibt — aus ihren Definitionen."""
    repo = Path(__file__).resolve().parent.parent
    return sorted(p.stem for p in (repo / ".claude" / "agents").glob("*.md"))


def sitzung(protokoll: Path) -> Dict[str, Any]:
    """Verbrauch einer Sitzung: je Antwort (``message.id``) einmal gezaehlt."""
    je_antwort: Dict[str, Dict[str, int]] = {}
    modelle, zeiten = set(), []
    for zeile in protokoll.read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(zeile)
        except json.JSONDecodeError:
            continue
        m = d.get("message") if isinstance(d.get("message"), dict) else {}
        u = m.get("usage")
        if d.get("type") != "assistant" or not isinstance(u, dict) or not m.get("id"):
            continue
        je_antwort[str(m["id"])] = {name: int(u.get(feld) or 0) for name, feld in FELDER}
        if m.get("model"):
            modelle.add(str(m["model"]))
        if d.get("timestamp"):
            zeiten.append(str(d["timestamp"]))
    if not je_antwort:
        raise AufwandFehler(f"{protokoll.name}: keine Antwort mit gemeldetem Verbrauch")
    if not zeiten:
        raise AufwandFehler(f"{protokoll.name}: keine Antwort mit Zeitstempel")
    tokens = {name: sum(a[name] for a in je_antwort.values()) for name, _ in FELDER}
    # Die Datei waechst auch ohne neue Antwort (Verwaltungszeilen ohne
    # Zeitstempel, gemessen 05.10.2026); nachrechenbar bleibt, was gezaehlt
    # wurde: Kennung und Verbrauch jeder Antwort, kanonisch gehasht.
    gezaehlt = json.dumps(sorted(je_antwort.items()), sort_keys=True, separators=(",", ":"))
    return {"sitzung": protokoll.stem,
            "antworten_sha256": hashlib.sha256(gezaehlt.encode("utf-8")).hexdigest(),
            "protokoll_sha256": hashlib.sha256(protokoll.read_bytes()).hexdigest(),
            "modelle": sorted(modelle), "antworten": len(je_antwort),
            "erste_antwort": min(zeiten), "letzte_antwort": max(zeiten), "tokens": tokens}


def kopf(protokoll: Path) -> Tuple[Optional[str], Optional[str]]:
    """Mit welcher Agentenrolle (``agent-setting``) und unter welchem Namen
    (``agent-name``) die Sitzung lief — wie Claude Code es festhaelt."""
    rolle = name = None
    for zeile in protokoll.read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(zeile)
        except json.JSONDecodeError:
            continue
        if d.get("type") == "agent-setting" and d.get("agentSetting"):
            rolle = str(d["agentSetting"])
        elif d.get("type") == "agent-name" and d.get("agentName"):
            name = str(d["agentName"])
    return rolle, name


def entdecke(ordner: Path, praefix: Optional[str] = None) -> List[Tuple[str, Path]]:
    """Die Agentensitzungen eines Ordners, je mit ihrer Rolle: was eine Rolle
    der Agentendefinitionen traegt, zum Praefix passt und eine Antwort hat."""
    bekannt = set(rollen())
    aus: List[Tuple[str, Path]] = []
    for protokoll in sorted(ordner.glob("*.jsonl")):
        rolle, name = kopf(protokoll)
        if rolle not in bekannt or (praefix and not str(name or "").startswith(praefix)):
            continue
        try:
            sitzung(protokoll)
        except AufwandFehler:
            continue   # gestartet, aber ohne Antwort (Leerstart)
        aus.append((rolle, protokoll))
    if not aus:
        raise AufwandFehler(f"keine Agentensitzung mit Antwort in {ordner.name}"
                            + (f" mit Praefix {praefix!r}" if praefix else ""))
    return aus


def erfasse(fall: Path, sitzungen: List[Tuple[str, Path]], zuordnung: str = "Aufruf") -> Dict[str, Any]:
    bekannt = rollen()
    if not sitzungen:
        raise AufwandFehler("keine Sitzung genannt")
    aus: List[Dict[str, Any]] = []
    for rolle, protokoll in sitzungen:
        if rolle not in bekannt:
            raise AufwandFehler(f"unbekannte Rolle {rolle!r} — es gibt {', '.join(bekannt)}")
        if not protokoll.is_file():
            raise AufwandFehler(f"Protokoll fehlt: {protokoll.name}")
        aus.append({"rolle": rolle, **sitzung(protokoll)})
    if len({s["sitzung"] for s in aus}) != len(aus):
        raise AufwandFehler("eine Sitzung ist doppelt genannt")
    je_rolle: Dict[str, Dict[str, int]] = {}
    for s in aus:
        r = je_rolle.setdefault(s["rolle"], {"antworten": 0, **{n: 0 for n, _ in FELDER}})
        r["antworten"] += s["antworten"]
        for n, _ in FELDER:
            r[n] += s["tokens"][n]
    summe = {"antworten": sum(s["antworten"] for s in aus),
             **{n: sum(s["tokens"][n] for s in aus) for n, _ in FELDER}}
    return {"schema_version": 1, "art": "aufwand",
            "fall": fall.name,
            "quelle": "Sitzungsprotokolle der Agenten: je Antwort der vom Modell gemeldete Verbrauch, "
                      "jede Antwort einmal gezaehlt",
            "zuordnung": zuordnung, "sitzungen": aus, "je_rolle": je_rolle, "summe": summe}


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="python werkzeuge/aufwand.py", description=__doc__.split("\n\n")[0])
    p.add_argument("--fall", required=True, type=Path)
    p.add_argument("--sitzung", action="append", default=[], metavar="ROLLE=PROTOKOLL")
    p.add_argument("--protokolle", type=Path, metavar="ORDNER",
                   help="Rollen aus den Protokollen lesen (agent-setting)")
    p.add_argument("--name-praefix", help="nur Sitzungen, deren agent-name so beginnt")
    args = p.parse_args(argv)
    ziel = args.fall / ZIEL
    try:
        if not (args.fall / "fall.json").is_file():
            raise AufwandFehler(f"kein Fall: {args.fall}")
        if ziel.exists():
            raise AufwandFehler(f"{ZIEL} liegt schon im Fall — was festgehalten ist, bleibt")
        if bool(args.protokolle) == bool(args.sitzung):
            raise AufwandFehler("entweder --protokolle ORDNER oder --sitzung ROLLE=PROTOKOLL")
        if args.protokolle:
            paare = entdecke(args.protokolle, args.name_praefix)
            zuordnung = "agent-setting der Sitzung" + (f", agent-name {args.name_praefix}*"
                                                       if args.name_praefix else "")
        else:
            paare, zuordnung = [], "Aufruf"
            for a in args.sitzung:
                rolle, _, pfad = a.partition("=")
                if not pfad:
                    raise AufwandFehler(f"--sitzung erwartet ROLLE=PROTOKOLL, nicht {a!r}")
                paare.append((rolle, Path(pfad)))
        daten = erfasse(args.fall, paare, zuordnung)
    except AufwandFehler as exc:
        print(f"aufwand: {exc}", file=sys.stderr)
        return 2
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(json.dumps(daten, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ziel.chmod(0o444)
    s = daten["summe"]
    print(f"{ZIEL}: {s['antworten']} Antworten, Ausgabe {s['ausgabe']}, Cache lesen {s['cache_lesen']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
