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
            z.append(f"* `{name}` — {zweck} ({len(treffer)} Dateien)")
    z.append("")
    return "\n".join(z) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Vorzeigeseite eines Laufs bauen.")
    p.add_argument("--fall", required=True, help="Fall-Arbeitsbereich")
    p.add_argument("--out", required=True, help="Zielverzeichnis der Seite")
    p.add_argument("--verlauf", default=None,
                   help="Verlaufsprotokoll (werkzeuge/verlaufsprotokoll.py)")
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
