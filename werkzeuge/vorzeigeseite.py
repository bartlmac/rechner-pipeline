"""Vorzeigeseite eines Migrationslaufs bauen — Beobachtungshilfe, kein Pipeline-Teil.

**Wozu.** Ein durchgefuehrter Migrationsfall soll sich zeigen lassen:
was geliefert wurde, was das System daraus gemacht hat, wo entschieden
wurde und wie der Lauf verlief. Die Artefakte dafuer liegen im
Fall-Arbeitsbereich — Gate-Ledger, Berichte, Entscheid-Snapshots. Dieses
Werkzeug sammelt sie zu einer statischen Seite (GitHub Pages).

**Warum die Artefakte NICHT ins Repo gehoeren.** ADR-002: "Das Repo ist
das System, nicht der Datenraum." ``faelle/`` ist der gitignorierte
Arbeitsbereich, echte Faelle liegen ausserhalb. Eine veroeffentlichte
Seite ist kein Datenraum, sondern eine Darstellung — sie wird als
datierter Schnappschuss publiziert, nicht nach ``main`` committet. Die
QUELLE der Seite (dieses Werkzeug, die Fallbeschreibung) ist
versioniert; der Schnappschuss ist es nicht.

**Drei Dinge, die dieses Werkzeug erzwingt, statt sie zu empfehlen:**

*Es laesst die Regie nicht durch.* ``simulation/`` und ``docs-local/``
enthalten die Aufloesungen des Vorfuehrfalls — welche Fehler absichtlich
eingebaut sind und wie die Beispieldaten entstehen. Wer das
mitveroeffentlicht, verschenkt die Vorfuehrung. Das Werkzeug bricht ab,
statt zu warnen.

*Es kennzeichnet die Simulation.* Auf der Seite stehen signierte
Abnahmen. Ein Aussenstehender muss auf den ersten Blick erkennen, dass
ein Simulationsschluessel gezeichnet hat und kein Verantwortlicher
Aktuar. Der Fingerabdruck steht ohnehin in jedem Snapshot; die Seite
erklaert ihn.

*Es stempelt die Provenienz.* Welcher Systemstand, welche Lieferung mit
welchen Pruefsummen, welche Schluesselrolle. Dieselbe Disziplin, die das
Repo intern fuehrt, gilt fuer die Veroeffentlichung.

Aufruf::

    python werkzeuge/vorzeigeseite.py --fall faelle/baldrian-uebernahme \\
        --out vorzeige/ [--verlauf verlauf.md]
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

#: Verzeichnisse, aus denen NICHTS auf die Seite gelangen darf. Sie
#: tragen die Aufloesungen des Vorfuehrfalls.
REGIE = ("simulation", "docs-local")

#: Dateien, die auch einzeln nie veroeffentlicht werden — der Name
#: allein genuegt, egal wo sie liegen.
REGIE_DATEIEN = ("MANIPULATIONEN.md", "NOTIZEN.md")

#: Was von einem Fall auf die Seite gehoert. Alles Uebrige bleibt
#: draussen; eine Positivliste ist sicherer als eine Sperrliste.
UEBERNEHMEN = (
    ("eingang.json", "Register der gelieferten Quellen"),
    ("fall.json", "Fallmanifest mit Scope"),
    ("abgeleitet/berichte", "Berichte des Laufs"),
    ("abgeleitet/diagnostics", "Gate-Ledger"),
    ("entscheide", "Entscheid-Snapshots der menschlichen Gates"),
)


#: Minimale Jekyll-Konfiguration der veroeffentlichten Seite. Das Thema
#: rendert Tabellen und Code lesbar; die Artefakte werden ausdruecklich
#: NICHT von Jekyll angefasst, damit JSON und CSV unveraendert
#: herunterladbar bleiben.
JEKYLL = """theme: jekyll-theme-cayman
title: Migrationsfall — Vorfuehrung
description: >-
  Vorfuehrung einer agentischen Bestandsmigration. Erfundene Unternehmen,
  synthetische Vertraege, mit einem Simulationsschluessel gezeichnete
  Abnahmen.
include:
  - artefakte
keep_files:
  - artefakte
"""


class VeroeffentlichungFehler(RuntimeError):
    """Etwas darf nicht auf die Seite — fail-fast statt Warnung."""


def _pruefe_regie(pfad: Path) -> None:
    """Abbrechen, wenn ein Pfad in die Regie zeigt."""
    teile = set(pfad.resolve().parts)
    for verzeichnis in REGIE:
        if verzeichnis in teile:
            raise VeroeffentlichungFehler(
                f"{pfad} liegt unter {verzeichnis!r}. Dort stehen die "
                "Aufloesungen des Vorfuehrfalls; sie duerfen nicht "
                "veroeffentlicht werden."
            )
    if pfad.name in REGIE_DATEIEN:
        raise VeroeffentlichungFehler(
            f"{pfad.name} ist ein Regie-Dokument und wird nicht "
            "veroeffentlicht, egal wo es liegt."
        )


def _systemstand(repo: Path) -> Dict[str, str]:
    def git(*args: str) -> str:
        try:
            return subprocess.run(
                ["git", *args], cwd=repo, capture_output=True, text=True,
                check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return "unbekannt"
    return {
        "commit": git("rev-parse", "HEAD"),
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "sauber": "ja" if not git("status", "--porcelain") else "nein",
    }


def _sha256(pfad: Path) -> str:
    h = hashlib.sha256()
    with pfad.open("rb") as datei:
        for block in iter(lambda: datei.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _lies_json(pfad: Path) -> Optional[Any]:
    try:
        return json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _gates(fall: Path) -> List[Dict[str, Any]]:
    """Die Gate-Ledger des Falls, nach Zeitpunkt geordnet."""
    verzeichnis = fall / "abgeleitet" / "diagnostics"
    aus: List[Dict[str, Any]] = []
    if not verzeichnis.is_dir():
        return aus
    for pfad in sorted(verzeichnis.glob("*.gate.json")):
        d = _lies_json(pfad)
        if not isinstance(d, dict):
            continue
        aus.append({
            "datei": pfad.name,
            "kommando": d.get("command", "?"),
            "gate": d.get("gate", "?"),
            "status": d.get("status", "?"),
            "gestartet": d.get("started_at", ""),
        })
    aus.sort(key=lambda e: (e["gestartet"], e["datei"]))
    return aus


def _entscheide(fall: Path) -> List[Dict[str, Any]]:
    """Die menschlichen Entscheide samt Schluesselrolle."""
    verzeichnis = fall / "entscheide"
    aus: List[Dict[str, Any]] = []
    if not verzeichnis.is_dir():
        return aus
    for pfad in sorted(verzeichnis.glob("*.json")):
        d = _lies_json(pfad)
        if not isinstance(d, dict):
            continue
        freigabe = d.get("freigabe") or {}
        aus.append({
            "gate": d.get("gate", "?"),
            "entscheid": d.get("entscheid", "?"),
            "entscheider": d.get("entscheider", "?"),
            "rolle": d.get("rolle", "?"),
            "begruendung": d.get("begruendung", ""),
            "schluessel": (freigabe.get("schluessel_sha256") or "")[:16],
        })
    return aus


#: Die drei aktuariellen Abnahmen mit dem Dateinamen, unter dem das
#: ``aktuartest``-Gate sie ablegt, und dem, was sie pruefen.
ABNAHMEN = (
    ("A-M1", "aktuartest", "Stichtagstest",
     "Übernahmezeitpunkt und nächster Vertragsstichtag"),
    ("A-M2", "aktuartest-A-M2", "Verlaufstest",
     "fünf und zehn Jahre nach der Übernahme, und der Ablauf"),
    ("A-M3", "aktuartest-A-M3", "Geschäftsvorfalltest",
     "je Vorfall die Änderung des Deckungskapitals"),
)


def _ergebnis(fall: Path) -> Dict[str, Any]:
    """Die Urteile des Laufs aus den Berichtsartefakten lesen.

    Die Seite RECHNET nichts. Jede Zahl steht so in einer Datei, die
    daneben liegt und nachpruefbar ist — sonst waere die Vorfuehrung
    eine Behauptung ueber sich selbst.
    """
    berichte = fall / "abgeleitet" / "berichte"
    abnahmen: List[Dict[str, Any]] = []
    for kennung, datei, titel, prueft in ABNAHMEN:
        d = _lies_json(berichte / f"{datei}.json")
        if not isinstance(d, dict):
            continue
        abnahmen.append({
            "kennung": kennung, "titel": titel, "prueft": prueft,
            "anzahl": d.get("anzahl"), "bestanden": d.get("bestanden"),
            "fehlgeschlagen": d.get("fehlgeschlagen"),
            "urteil": d.get("test_bestanden"),
            "bericht": (f"artefakte/abgeleitet/berichte/{datei}.html"
                        if (berichte / f"{datei}.html").is_file() else None),
        })

    suite = _lies_json(berichte / "migrationssuite.json")
    controlling = None
    if isinstance(suite, dict):
        luecken = suite.get("pruefluecken") or []
        controlling = {
            "anzahl": suite.get("anzahl"),
            "bestanden": suite.get("bestanden"),
            "pruefluecken": len(luecken),
            "vollstaendig": suite.get("vollstaendig_geprueft"),
            "stichtag_1": suite.get("stichtag_1"),
            "stichtag_2": suite.get("stichtag_2"),
        }

    budget = _lies_json(berichte / "umbaubudget.json")
    return {
        "abnahmen": abnahmen,
        "controlling": controlling,
        "budget": budget if isinstance(budget, dict) else None,
        "bestandsberichte": sorted(
            f"artefakte/abgeleitet/berichte/{p.name}"
            for p in berichte.glob("bestandsbericht*.html")
        ) if berichte.is_dir() else [],
    }


def _urteilswort(urteil: Any) -> str:
    if urteil is True:
        return "bestanden"
    if urteil is False:
        return "**nicht bestanden**"
    return "*(ohne Urteil)*"


def _quellen(fall: Path) -> List[Dict[str, Any]]:
    d = _lies_json(fall / "eingang.json") or {}
    return sorted(d.get("quellen", []), key=lambda q: q.get("datei", ""))


def _kopiere(fall: Path, ziel: Path) -> List[str]:
    """Die Positivliste in das Zielverzeichnis spiegeln."""
    kopiert: List[str] = []
    for name, _zweck in UEBERNEHMEN:
        quelle = fall / name
        if not quelle.exists():
            continue
        _pruefe_regie(quelle)
        zielpfad = ziel / "artefakte" / name
        if quelle.is_dir():
            for datei in sorted(quelle.rglob("*")):
                if not datei.is_file():
                    continue
                _pruefe_regie(datei)
                unterziel = zielpfad / datei.relative_to(quelle)
                unterziel.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(datei, unterziel)
                kopiert.append(str(unterziel.relative_to(ziel)))
        else:
            zielpfad.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(quelle, zielpfad)
            kopiert.append(str(zielpfad.relative_to(ziel)))
    return kopiert


def _seite(fall: Path, repo: Path, kopiert: List[str],
           verlauf: Optional[str]) -> str:
    stand = _systemstand(repo)
    manifest = _lies_json(fall / "fall.json") or {}
    gates = _gates(fall)
    entscheide = _entscheide(fall)
    quellen = _quellen(fall)
    ergebnis = _ergebnis(fall)
    heute = dt.date.today().isoformat()

    z: List[str] = []
    z.append(f"# Migrationsfall {manifest.get('name', fall.name)}")
    z.append("")
    z.append("> **Dies ist eine Vorführung, kein echter Bestand.** Die")
    z.append("> beteiligten Unternehmen sind frei erfunden, die Verträge")
    z.append("> synthetisch erzeugt. Die fachlichen Abnahmen auf dieser")
    z.append("> Seite sind mit einem **Simulationsschlüssel** gezeichnet")
    z.append("> und nicht von einem Verantwortlichen Aktuar. Wer die")
    z.append("> Snapshots prüft, erkennt das am Fingerabdruck des")
    z.append("> Schlüssels — er ist unten ausgewiesen.")
    z.append("")
    if manifest.get("beschreibung"):
        z.append(str(manifest["beschreibung"]))
        z.append("")

    z.append("## Provenienz")
    z.append("")
    z.append("| | |")
    z.append("|---|---|")
    z.append(f"| Veröffentlicht | {heute} |")
    z.append(f"| Systemstand | `{stand['commit'][:12]}` auf `{stand['branch']}` |")
    z.append(f"| Arbeitsbaum sauber | {stand['sauber']} |")
    z.append(f"| Scope des Falls | {(manifest.get('scope') or {}).get('typ', '?')} |")
    z.append("")

    z.append("## Die Lieferung")
    z.append("")
    z.append("Was das abgebende Unternehmen übergeben hat. In den Fall")
    z.append("gelangt eine Datei ausschließlich über die ausdrückliche")
    z.append("Registrierung — einen impliziten Eingangskanal gibt es nicht.")
    z.append("")
    z.append("| Datei | Bytes | SHA-256 |")
    z.append("|---|---:|---|")
    for q in quellen:
        z.append(f"| `{q.get('datei','?')}` | {q.get('bytes',0):,} "
                 f"| `{str(q.get('sha256',''))[:16]}…` |")
    z.append("")

    z.append("## Das Ergebnis")
    z.append("")
    if not (ergebnis["abnahmen"] or ergebnis["controlling"]):
        z.append("*(noch keine Berichte im Fall)*")
        z.append("")
    else:
        z.append("Was bei der Übernahme herausgekommen ist. Die Seite")
        z.append("rechnet nichts nach — jede Zahl steht so in einem")
        z.append("Artefakt, das unter `artefakte/` daneben liegt.")
        z.append("")
    if ergebnis["abnahmen"]:
        z.append("### Die aktuariellen Abnahmen")
        z.append("")
        z.append("Je Abnahme eine eigene Stichprobe und eigene Kriterien.")
        z.append("Sie prüfen denselben Bestand zu verschiedenen Zeitpunkten.")
        z.append("")
        z.append("| Abnahme | Geprüft wird | Verträge | Befunde | Urteil |")
        z.append("|---|---|---:|---:|---|")
        for a in ergebnis["abnahmen"]:
            name = f"{a['kennung']} {a['titel']}"
            if a["bericht"]:
                name = f"[{name}]({a['bericht']})"
            z.append(f"| {name} | {a['prueft']} | {a['anzahl']} "
                     f"| {a['fehlgeschlagen']} | {_urteilswort(a['urteil'])} |")
        z.append("")
    if ergebnis["controlling"]:
        c = ergebnis["controlling"]
        z.append("### Das Migrationscontrolling (A-M4)")
        z.append("")
        z.append("Kein Vertrag und keine Stichprobe, sondern der ganze")
        z.append(f"Bestand über zwei Stichtage ({c['stichtag_1']} und")
        z.append(f"{c['stichtag_2']}).")
        z.append("")
        z.append("| | |")
        z.append("|---|---:|")
        z.append(f"| Geprüfte Verträge | {c['anzahl']} |")
        z.append(f"| Davon bestanden | {c['bestanden']} |")
        z.append(f"| Prüflücken | {c['pruefluecken']} |")
        z.append(f"| Vollständig geprüft | "
                 f"{'ja' if c['vollstaendig'] else 'nein'} |")
        z.append("")
        if c["pruefluecken"]:
            z.append("Eine **Prüflücke** ist ein Vertrag, dessen Wert am")
            z.append("Folgestichtag nicht nachgerechnet werden konnte. Der")
            z.append("Bestands-Scope duldet keine: Der Lauf endet dort mit")
            z.append("einem Befund, und das ist die richtige Auskunft — ein")
            z.append("geglätteter Wert wäre eine Behauptung ohne Rechnung.")
            z.append("")
    for pfad in ergebnis["bestandsberichte"]:
        z.append(f"* Bestandsbericht: [{Path(pfad).name}]({pfad})")
    if ergebnis["bestandsberichte"]:
        z.append("")
    if ergebnis["budget"]:
        b = ergebnis["budget"]
        offene = b.get("befunde") or []
        gesamt = b.get("gesamt") or {}
        z.append("### Umfang des Umbaus")
        z.append("")
        z.append("Wie weit dieser Lauf das Zielsystem verändert hat.")
        z.append("")
        z.append(f"Geändert: {gesamt.get('summe','?')} Zeilen in `src/` und")
        z.append(f"`tests/` (Schranke {gesamt.get('vorgabe','?')}).")
        z.append("")
        if not offene:
            z.append("Im Rahmen der vereinbarten Schranken.")
        else:
            wort = ("eine Überschreitung" if len(offene) == 1
                    else f"{len(offene)} Überschreitungen")
            z.append(f"{wort[0].upper()}{wort[1:]}:")
            z.append("")
            for befund in offene:
                z.append(f"* {befund}")
            z.append("")
            begruendung = b.get("ueberschreitung_begruendet")
            if begruendung:
                z.append(f"Als Menschentscheidung begründet: „{begruendung}“")
            else:
                z.append("**Ohne Begründung.**")
        z.append("")

    z.append("## Der Lauf")
    z.append("")
    if gates:
        z.append("| Gate | Kommando | Urteil |")
        z.append("|---|---|---|")
        for g in gates:
            z.append(f"| {g['gate']} | `{g['kommando']}` | {g['status']} |")
    else:
        z.append("*(noch keine Gate-Ledger im Fall)*")
    z.append("")

    z.append("## Die menschlichen Entscheide")
    z.append("")
    if entscheide:
        z.append("| Gate | Entscheid | Entscheider | Rolle | Schlüssel |")
        z.append("|---|---|---|---|---|")
        for e in entscheide:
            schl = f"`{e['schluessel']}…`" if e["schluessel"] else "*(ohne Signatur)*"
            z.append(f"| {e['gate']} | {e['entscheid']} | {e['entscheider']} "
                     f"| {e['rolle']} | {schl} |")
        z.append("")
        z.append("Eine Annahme ist HMAC-signiert; das Schlüsselmaterial liegt")
        z.append("außerhalb des Falls. Ein Fall kann seine eigene menschliche")
        z.append("Freigabe deshalb nicht behaupten. Der Fingerabdruck oben")
        z.append("weist die **Schlüsselrolle** nach, nicht die Identität einer")
        z.append("natürlichen Person — hier die der Simulation.")
    else:
        z.append("*(noch keine Entscheide im Fall)*")
    z.append("")

    if verlauf:
        z.append("## Verlauf")
        z.append("")
        z.append("Der Ablauf des Laufs, aus dem Sitzungstranskript erzeugt:")
        z.append("[verlauf.md](verlauf.md).")
        z.append("")

    z.append("## Artefakte")
    z.append("")
    z.append(f"{len(kopiert)} Dateien unter `artefakte/`:")
    z.append("")
    for name, zweck in UEBERNEHMEN:
        treffer = [k for k in kopiert if k.startswith(f"artefakte/{name}")]
        if treffer:
            wort = "Datei" if len(treffer) == 1 else "Dateien"
            z.append(f"* `{name}` — {zweck} ({len(treffer)} {wort})")
    z.append("")
    return "\n".join(z) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Vorzeigeseite eines Laufs bauen.")
    p.add_argument("--fall", required=True, help="Fall-Arbeitsbereich")
    p.add_argument("--out", required=True, help="Zielverzeichnis der Seite")
    p.add_argument("--verlauf", default=None,
                   help="Verlaufsprotokoll der OPERATOR-Sitzung "
                        "(werkzeuge/verlaufsprotokoll.py --sitzung <uuid>). "
                        "Nicht --neueste nehmen: das ist womoeglich die "
                        "Sitzung, die das Werkzeug gebaut hat.")
    p.add_argument("--repo", default=".", help="Repo-Wurzel fuer den Systemstand")
    args = p.parse_args(argv)

    fall = Path(args.fall).resolve()
    if not (fall / "fall.json").is_file():
        print(f"Kein Fall-Arbeitsbereich: {fall}", file=sys.stderr)
        return 2

    ziel = Path(args.out).resolve()
    ziel.mkdir(parents=True, exist_ok=True)

    try:
        # Innerhalb des try, damit auch der Regie-Abbruch als Meldung
        # herauskommt und nicht als Traceback — er ist ein erwartetes
        # Urteil ueber die Eingabe, kein Defekt des Werkzeugs.
        _pruefe_regie(fall)
        kopiert = _kopiere(fall, ziel)
        verlauf_text = None
        if args.verlauf:
            quelle = Path(args.verlauf).resolve()
            _pruefe_regie(quelle)
            verlauf_text = quelle.read_text(encoding="utf-8")
            (ziel / "verlauf.md").write_text(verlauf_text, encoding="utf-8")
        (ziel / "index.md").write_text(
            _seite(fall, Path(args.repo).resolve(), kopiert, verlauf_text),
            encoding="utf-8")
        # Jekyll rendert die Markdown-Seiten; ohne Konfiguration nimmt
        # GitHub Pages ein Vorgabethema, das die Tabellen bricht.
        (ziel / "_config.yml").write_text(JEKYLL, encoding="utf-8")
    except VeroeffentlichungFehler as exc:
        print(f"ABBRUCH: {exc}", file=sys.stderr)
        return 1

    print(f"{ziel}/index.md geschrieben")
    print(f"  {len(kopiert)} Artefakte kopiert")
    if verlauf_text:
        print(f"  Verlaufsprotokoll uebernommen ({len(verlauf_text):,} Zeichen)")
    print()
    print("Vor der Veroeffentlichung von Hand pruefen:")
    print("  - Stehen Klarnamen im Verlaufsprotokoll?")
    print("  - Ist der Simulationshinweis oben noch zutreffend?")
    print("  - Traegt die Seite etwas, das die Vorfuehrung verrät?")
    print()
    print("Veroeffentlichen (der Mensch, bewusst — siehe werkzeuge/README.md):")
    print(f"  git worktree add /tmp/gh-pages gh-pages")
    print(f"  cp -r {ziel}/. /tmp/gh-pages/")
    print(f"  cd /tmp/gh-pages && git add -A && git commit && git push")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
