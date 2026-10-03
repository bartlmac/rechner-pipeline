#!/usr/bin/env python3
"""Lagebild eines Falls fuer die Vorfuehrung — nur lesend, nur Anzeige.

Die rechten Panes der Vorfuehrungssession (``werkzeuge/vorfuehrung.py``)
zeigen, wo ein Fall steht: welche Gates entschieden sind, was zuletzt
entschieden wurde, auf welchem Systemstand gearbeitet wird und was die
Laufzeit fuehrt. Das Lagebild liest dafuer die Entscheid-Snapshots
(``<bereich>/entscheide/<gate>-<sha>.json``), die Glieder der Ordnungslinie
und die Ablage der Laufzeit.

Es ist eine ANZEIGE, kein Urteil: Es prueft keine Signatur, keine Rolle und
keinen Beleg — das tun die Gates und die Leser des Betriebs, und nur sie.
Deshalb traegt jede Sicht den Vermerk "Anzeige, ungeprueft", und das
Werkzeug braucht keinen Schluessel. Es schreibt nichts.

Sichten:

    python werkzeuge/lagebild.py lebenslauf --fall faelle/<fall> [--linie <linie>]
    python werkzeuge/lagebild.py entscheide --fall faelle/<fall> [--linie <linie>] [-n 12]
    python werkzeuge/lagebild.py system [--linie <linie>] [--stand <ablage>]
    python werkzeuge/lagebild.py rolle <rolle> --fall faelle/<fall> [--linie <linie>] [--stand <ablage>]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parent.parent

VERMERK = "Anzeige, ungeprueft: Signaturen, Rollen und Belege prueft das Gate."

#: Die Gates eines Falls in der Reihenfolge seines Lebenslaufs (ADR-026):
#: Auftrag, Quellen, Stand des Zielsystems, aktuarielle Tests, Abnahme der
#: Migration, Zugang im Betrieb; der Abbruch steht am Ende.
LEBENSLAUF: Tuple[Tuple[str, str], ...] = (
    ("A-M6", "Fallauftrag"),
    ("A-Q1", "Quellenauswertung"),
    ("A-O1", "T-Box-Stand"),
    ("A-K2", "Kernstand"),
    ("A-T1", "Tarifwerk"),
    ("A-M1", "Stichtagstest"),
    ("A-M2", "Verlaufstest"),
    ("A-M3", "Geschaeftsvorfalltest"),
    ("A-M4", "Migrationsabnahme"),
    ("A-B2", "Zugangsabnahme"),
    ("A-M5", "Fallabbruch"),
)
#: Gates, deren Abnahme auch im Linienbereich liegen kann (ADR-025).
LINIEN_GATES = ("A-O1", "A-K2", "A-T1", "A-B3")

#: Welche Gates die Vorlagen einer Agentenrolle betreffen — fuer die Sicht
#: je Rolle. Die Rolle bereitet vor, gezeichnet wird von der Menschenrolle.
ROLLEN: Dict[str, Tuple[str, ...]] = {
    "programmleitung": tuple(g for g, _ in LEBENSLAUF),
    "aktuariat": ("A-Q1", "A-T1", "A-M1", "A-M2", "A-M3", "A-M4"),
    "architektur": ("A-O1",),
    "rechenkern": ("A-K2",),
    "betrieb": ("A-B1", "A-B2", "A-B3"),
}
BEZEICHNUNG = dict(LEBENSLAUF) | {"A-B1": "Auslieferung", "A-B3": "Anfangsbestand"}

OFFEN, MEHRDEUTIG, UNLESBAR = "offen", "mehrdeutig", "unlesbar"


def kette(bereich: Optional[Path], gate: str) -> Dict[str, Dict[str, Any]]:
    """Die Snapshots eines Gates in einem Bereich, je Hash — strukturell
    gelesen. Eine Datei, die kein JSON-Objekt ist, steht als ``unlesbar``
    in der Kette, statt still zu fehlen."""
    aus: Dict[str, Dict[str, Any]] = {}
    if bereich is None:
        return aus
    verzeichnis = Path(bereich) / "entscheide"
    if not verzeichnis.is_dir():
        return aus
    for pfad in sorted(verzeichnis.iterdir()):
        if not (pfad.name.startswith(gate + "-") and pfad.suffix == ".json"):
            continue
        sha = pfad.stem[len(gate) + 1:]
        try:
            daten = json.loads(pfad.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            daten = None
        aus[sha] = daten if isinstance(daten, dict) else {"entscheid": UNLESBAR}
    return aus


def spitzen(snapshots: Dict[str, Dict[str, Any]]) -> List[str]:
    """Die Snapshots, die kein anderer als Vorgaenger nennt (sortiert)."""
    genannt = set()
    for daten in snapshots.values():
        vor = daten.get("vorgaenger")
        genannt.update(v for v in (vor if isinstance(vor, list) else [vor]) if isinstance(v, str))
    return sorted(sha for sha in snapshots if sha not in genannt)


def stand(bereich: Optional[Path], gate: str) -> Dict[str, Any]:
    """Der angezeigte Stand eines Gates: ``offen``, ``mehrdeutig``,
    ``unlesbar`` oder der Entscheid der einen Spitze mit Rolle, Zeit und ob
    sie eine Freigabe TRAEGT (nicht: ob die Signatur stimmt)."""
    snapshots = kette(bereich, gate)
    oben = spitzen(snapshots)
    if not snapshots:
        return {"gate": gate, "stand": OFFEN, "anzahl": 0}
    if len(oben) != 1:
        return {"gate": gate, "stand": MEHRDEUTIG, "anzahl": len(snapshots),
                "spitzen": [s[:12] for s in oben]}
    daten = snapshots[oben[0]]
    return {
        "gate": gate,
        "stand": str(daten.get("entscheid", UNLESBAR)),
        "anzahl": len(snapshots),
        "snapshot": oben[0][:12],
        "rolle": daten.get("rolle"),
        "am": daten.get("entschieden_am"),
        "freigabe": isinstance(daten.get("freigabe"), dict),
        "belege": sorted((daten.get("pflichtbelege") or {}).keys())
        if isinstance(daten.get("pflichtbelege"), dict) else [],
    }


def _zeit(wert: object) -> str:
    """JJJJ-MM-TTThh:mm... als TT.MM. hh:mm — die Panes sind schmal."""
    if not (isinstance(wert, str) and len(wert) >= 16):
        return "-"
    return f"{wert[8:10]}.{wert[5:7]}. {wert[11:16]}"


def _zeile(eintrag: Dict[str, Any], *, ort: str = "") -> str:
    gate = eintrag["gate"]
    kopf = f"{gate:<5} {BEZEICHNUNG.get(gate, ''):<22}"
    if eintrag["stand"] == OFFEN:
        return f"{kopf} {OFFEN}"
    if eintrag["stand"] == MEHRDEUTIG:
        return (f"{kopf} {MEHRDEUTIG}: {len(eintrag['spitzen'])} Spitzen "
                f"({', '.join(eintrag['spitzen'])})")
    freigabe = "" if eintrag["freigabe"] else "  ohne Freigabe"
    return (f"{kopf} {eintrag['stand']:<10} {_zeit(eintrag['am'])}  "
            f"{eintrag.get('rolle') or '-'}{freigabe}{ort}")


def sicht_lebenslauf(fall: Path, linie: Optional[Path]) -> List[str]:
    zeilen = [f"Lebenslauf des Falls {Path(fall).name}", VERMERK, ""]
    for gate, _ in LEBENSLAUF:
        im_fall = stand(fall, gate)
        if im_fall["stand"] == OFFEN and gate in LINIEN_GATES and linie is not None:
            in_linie = stand(linie, gate)
            if in_linie["stand"] != OFFEN:
                zeilen.append(_zeile(in_linie, ort="  (Linie)"))
                continue
        zeilen.append(_zeile(im_fall))
    return zeilen


def sicht_entscheide(fall: Path, linie: Optional[Path], anzahl: int) -> List[str]:
    alle: List[Tuple[str, str, str, Dict[str, Any]]] = []
    for ort, bereich in (("Fall", fall), ("Linie", linie)):
        if bereich is None:
            continue
        for gate in BEZEICHNUNG:
            for sha, daten in kette(bereich, gate).items():
                alle.append((str(daten.get("entschieden_am") or ""), ort, sha, {"gate": gate} | daten))
    alle.sort(key=lambda e: (e[0], e[2]), reverse=True)
    zeilen = [f"Die letzten {anzahl} Entscheide", VERMERK, ""]
    for am, ort, sha, daten in alle[:anzahl]:
        zeilen.append(f"{_zeit(am)}  {daten['gate']:<5} {str(daten.get('entscheid', UNLESBAR)):<10} "
                      f"{daten.get('rolle') or '-'}  {sha[:8]}  {ort}")
    if not alle:
        zeilen.append("noch kein Entscheid")
    return zeilen


def _git(*argumente: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(REPO), *argumente], capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unbekannt"


def glieder(linie: Optional[Path]) -> List[Dict[str, Any]]:
    """Die Glieder der Ordnungslinie, strukturell und nach Nummer sortiert."""
    if linie is None or not (Path(linie) / "ordnung").is_dir():
        return []
    aus = []
    for pfad in sorted((Path(linie) / "ordnung").glob("*.json")):
        try:
            daten = json.loads(pfad.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(daten, dict) and isinstance(daten.get("nummer"), int):
            aus.append(daten)
    return sorted(aus, key=lambda g: g["nummer"])


def sicht_system(linie: Optional[Path], ablage: Optional[Path]) -> List[str]:
    sys.path.insert(0, str(REPO / "src"))
    try:
        from rechner_pipeline import kern
        from rechner_pipeline.ontologie import tbox
        kernversion, tboxversion = kern.__version__, tbox.TBOX_VERSION
    except Exception as exc:  # noqa: BLE001 — Anzeige: benennen statt abbrechen
        kernversion = tboxversion = f"nicht lesbar ({type(exc).__name__})"
    geaendert = _git("status", "--porcelain")
    zeilen = [
        "Systemstand", "",
        f"Zweig     {_git('rev-parse', '--abbrev-ref', 'HEAD')}",
        f"Commit    {_git('rev-parse', '--short=12', 'HEAD')}",
        f"Baum      {'sauber' if geaendert == '' else 'unbekannt' if geaendert == 'unbekannt' else 'veraendert'}",
        f"Kern      {kernversion}",
        f"T-Box     {tboxversion}",
    ]
    kette_ = glieder(linie)
    if linie is not None:
        zeilen.append(f"Linie     {len(kette_)} Glied(er)"
                      + (f", Spitze Glied {kette_[-1]['nummer']} vom "
                         f"{_zeit(kette_[-1].get('eingetragen_am'))}" if kette_ else ""))
    if ablage is not None:
        zeilen += [""] + sicht_laufzeit(ablage)
    return zeilen


def sicht_laufzeit(ablage: Path) -> List[str]:
    ablage = Path(ablage)
    if not ablage.is_dir():
        return [f"Laufzeit  {ablage}: nicht vorhanden"]
    zeilen = [f"Laufzeit  {ablage}"]
    zugaenge = sorted(p.name for p in (ablage / "uebernahme").iterdir()
                      if p.is_dir()) if (ablage / "uebernahme").is_dir() else []
    zeilen.append("Zugaenge  " + (", ".join(zugaenge) if zugaenge else "keine"))
    abschluesse = sorted(p.name for p in (ablage / "abschluesse").iterdir()) \
        if (ablage / "abschluesse").is_dir() else []
    zeilen.append(f"Abschluesse  {len(abschluesse)}"
                  + (f", juengster {abschluesse[-1]}" if abschluesse else ""))
    reste = sorted(p.name for p in ablage.parent.iterdir()
                   if p.name.startswith(ablage.name + ".neu-"))
    if reste:
        zeilen.append("ACHTUNG   liegengebliebene Vorbereitung: " + ", ".join(reste))
    return zeilen


def sicht_rolle(rolle: str, fall: Path, linie: Optional[Path],
                ablage: Optional[Path]) -> List[str]:
    zeilen = [f"Rolle {rolle}: Gates und Belege im Fall {Path(fall).name}", VERMERK, ""]
    for gate in ROLLEN[rolle]:
        bereich = linie if gate == "A-B3" else fall
        eintrag = stand(bereich, gate)
        if eintrag["stand"] == OFFEN and gate in LINIEN_GATES and linie is not None:
            eintrag = stand(linie, gate)
        zeilen.append(_zeile(eintrag))
        for beleg in eintrag.get("belege", []):
            zeilen.append(f"        Beleg {beleg}")
    if rolle == "rechenkern":
        zeilen += ["", "Letzte Aenderungen am Kern:",
                   *(_git("log", "-5", "--format=%h %cs %s", "--",
                          "src/rechner_pipeline/kern").splitlines() or ["keine"])]
        zeilen = [z[:84] for z in zeilen]
    if rolle == "architektur":
        zeilen += ["", "Ordnungslinie:"]
        zeilen += [f"  Glied {g['nummer']}  {_zeit(g.get('eingetragen_am'))}  "
                   f"Ordnung {str(g.get('ordnung_sha256'))[:12]}" for g in glieder(linie)] \
            or ["  keine Glieder"]
    if rolle == "betrieb" and ablage is not None:
        zeilen += [""] + sicht_laufzeit(ablage)
    return zeilen


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="python werkzeuge/lagebild.py", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="sicht", required=True)
    for name in ("lebenslauf", "entscheide", "rolle"):
        s = sub.add_parser(name)
        if name == "rolle":
            s.add_argument("rolle", choices=sorted(ROLLEN))
            s.add_argument("--stand", type=Path, default=None, help="Ablage der Laufzeit")
        if name == "entscheide":
            s.add_argument("-n", type=int, default=12, dest="anzahl")
        s.add_argument("--fall", type=Path, required=True)
        s.add_argument("--linie", type=Path, default=None)
    s = sub.add_parser("system")
    s.add_argument("--linie", type=Path, default=None)
    s.add_argument("--stand", type=Path, default=None, help="Ablage der Laufzeit")
    args = p.parse_args(argv)
    if args.sicht != "system" and not args.fall.is_dir():
        print(f"lagebild: Fall {args.fall} nicht gefunden", file=sys.stderr)
        return 2
    if args.sicht == "lebenslauf":
        zeilen = sicht_lebenslauf(args.fall, args.linie)
    elif args.sicht == "entscheide":
        zeilen = sicht_entscheide(args.fall, args.linie, args.anzahl)
    elif args.sicht == "rolle":
        zeilen = sicht_rolle(args.rolle, args.fall, args.linie, args.stand)
    else:
        zeilen = sicht_system(args.linie, args.stand)
    print("\n".join(zeilen))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
