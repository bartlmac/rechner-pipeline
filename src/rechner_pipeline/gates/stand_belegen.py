"""``stand_belegen`` — Belege der Standabnahme: lebender Stand, Verweis, T-Box-Uebergang.

Entscheid des Maintainers 2026-10-01 (ADR-018, Nachtrag 2026-10-01): Der
Stand, auf dem ein Fall laeuft, ist abgenommen — Kernstand (A-K2) und
T-Box-Stand (A-O1) nach EINER Regel (``models.standabnahme``). Dieses
Modul haelt, was beide Gegenstaende gemeinsam brauchen:

* :func:`lebender_stand` — der Stand, den der Code JETZT traegt (Kern:
  Version, Sammelhash des Kernpakets, der Referenzwerte und der ganzen
  Pfadmenge; T-Box: Version und SHA-256 des Moduls). Das Gate schreibt ihn
  beim Zeichnen von A-K2/A-O1 als Feld ``stand`` in den Snapshot und haelt
  ihn bei A-M4 per ``==`` gegen jeden abgenommenen Stand.
* ``verweisen`` — der Weg "keine Aenderung": Ein Fall, dessen Stand ein
  FRUEHER angenommener Snapshot schon abgenommen hat, legt eine
  vollstaendige Kopie dieses Snapshots an den festen Ort
  (``abgeleitet/kern/verweis.json`` bzw. ``abgeleitet/tbox/verweis.json``).
  Die Kopie ist selbstadressiert und signiert; A-M4 prueft Signatur, Rolle,
  Klasse und Stand. Kein neuer Entscheid.
* ``tbox`` — der Aenderungsbeleg eines T-Box-Uebergangs
  (``abgeleitet/tbox/aenderung.json``) aus der Versionslinie des Codes: der
  Produzent, den A-O1 bis hierher nicht hatte. Die aktuarielle
  Stellungnahme bleibt fachliche Arbeit des Aktuariats.

Run via::

    python -m rechner_pipeline.gates.stand_belegen verweisen --fall faelle/<fall> \\
        --gate A-K2|A-O1 --snapshot <frueherer-snapshot.json> --repo-root .
    python -m rechner_pipeline.gates.stand_belegen tbox --fall faelle/<fall> \\
        --artefakt <adr-oder-vermerk> --begruendung "<text>" --repo-root .

Knoten: system/entscheid
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
from pathlib import Path
from typing import Any, Dict, List, Optional

from rechner_pipeline.gates import kernstand_belegen as _kern
from rechner_pipeline.gates._common import (
    Exit,
    ToolboxResult,
    build_result,
    raeume_schreibreste,
    run_command,
)
from rechner_pipeline.models import kernabnahme as ka
from rechner_pipeline.models import standabnahme as sa
from rechner_pipeline.models.schemas import P9Snapshot

COMMAND = "stand_belegen"
GATE_VERSION = "1.0.0"

#: Fester Ort des T-Box-Aenderungsbelegs (wie bisher von A-O1 gelesen).
TBOX_AENDERUNG_RELATIV = "abgeleitet/tbox/aenderung.json"
TBOX_STELLUNGNAHME_RELATIV = "abgeleitet/tbox/stellungnahme.json"
#: Schema des T-Box-Aenderungsbelegs (gates.gate_entscheid.pruefe_tbox_aenderung).
TBOX_AENDERUNG_SCHEMA_VERSION = 1


class StandFehler(RuntimeError):
    """Der Stand oder ein Beleg dazu ist nicht bestimmbar — mit dem Grund."""


def _tbox_modul():
    from rechner_pipeline.ontologie import tbox

    return tbox


def tbox_modul_sha256() -> str:
    return hashlib.sha256(Path(_tbox_modul().__file__).read_bytes()).hexdigest()


def lebender_stand(gate: str, repo_root: Optional[Path]) -> Optional[Dict[str, str]]:
    """Der Stand, den der Code JETZT traegt (None = nicht bestimmbar)."""
    if gate == "A-K2":
        if repo_root is None:
            return None
        init = repo_root / ka.KERN_PAKET / "__init__.py"
        stand = {
            "version": _kern.kern_version(init.read_text(encoding="utf-8")
                                          if init.is_file() else None),
            "kern_sha256": _kern.kern_modul_hash(repo_root),
            "referenzwerte_sha256": _kern.referenzwerte_hash(repo_root),
            "kernstand_sha256": _kern.kernstand_hash(repo_root),
        }
    elif gate == "A-O1":
        stand = {"version": _tbox_modul().TBOX_VERSION, "tbox_sha256": tbox_modul_sha256()}
    else:
        raise ValueError(f"{gate!r} ist kein Gegenstand der Standabnahme")
    return stand if all(isinstance(v, str) and v for v in stand.values()) else None


def basislinie_gilt() -> bool:
    """Weg (c): Die Versionslinie der T-Box hat EIN Element — kein Uebergang."""
    tbox = _tbox_modul()
    return len(tuple(tbox.TBOX_VERSIONEN)) == 1


def verweis_fehler(daten: object, gegenstand: sa.Gegenstand,
                   stand: Optional[Dict[str, str]]) -> List[str]:
    """Was sich an einem Verweis OHNE Schluessel pruefen laesst: Form,
    Schema und Selbstadressierung der Kopie, Gate, Annahme, Herkunft und —
    der Kern des Wegs — der abgenommene Stand gleich dem lebenden.
    Signatur und Rollenregel prueft das Gate (es haelt den Ring)."""
    if not isinstance(daten, dict):
        return ["kein JSON-Objekt"]
    fehler: List[str] = []
    if set(daten) != sa.VERWEIS_FELDER:
        fehler.append(f"der Verweis traegt genau die Felder {sorted(sa.VERWEIS_FELDER)}")
    if daten.get("schema_version") != sa.VERWEIS_SCHEMA_VERSION:
        fehler.append(f"schema_version muss {sa.VERWEIS_SCHEMA_VERSION} sein")
    if daten.get("art") != sa.VERWEIS_ART:
        fehler.append(f"art muss {sa.VERWEIS_ART!r} sein")
    if daten.get("gate") != gegenstand.gate:
        fehler.append(f"gate muss {gegenstand.gate!r} sein")
    snap = daten.get("snapshot")
    if not isinstance(snap, dict):
        return fehler + ["snapshot fehlt oder ist kein Objekt"]
    fehler += [f"snapshot: {f}" for f in P9Snapshot.validate_payload(snap)]
    if snap.get("gate") != gegenstand.gate:
        fehler.append(f"der Snapshot gehoert zu {snap.get('gate')!r}, nicht {gegenstand.gate!r}")
    if snap.get("entscheid") != "angenommen":
        fehler.append("der Snapshot ist keine Annahme — eine Ablehnung nimmt keinen Stand ab")
    if daten.get("herkunft") != sa.herkunft(snap):
        fehler.append(f"herkunft muss {sa.herkunft(snap)!r} sein (abgeleitet, nicht angegeben)")
    if stand is None:
        fehler.append("der lebende Stand ist nicht bestimmbar (--repo-root fehlt?)")
    elif snap.get("stand") != stand:
        fehler.append(
            f"der abgenommene Stand {snap.get('stand')!r} ist nicht der lebende {stand!r} "
            "— es gab eine Aenderung; sie braucht eine Abnahme im Fall")
    return fehler


def baue_verweis(snapshot: dict) -> Dict[str, Any]:
    return {
        "schema_version": sa.VERWEIS_SCHEMA_VERSION,
        "art": sa.VERWEIS_ART,
        "gate": snapshot.get("gate"),
        "herkunft": sa.herkunft(snapshot),
        "snapshot": snapshot,
    }


def tbox_aenderungsbeleg(fall: Path, repo_root: Optional[Path], artefakt: str,
                         begruendung: str) -> Dict[str, Any]:
    """Der Aenderungsbeleg des letzten Uebergangs der T-Box-Versionslinie."""
    tbox = _tbox_modul()
    linie = tuple(tbox.TBOX_VERSIONEN)
    if len(linie) < 2:
        raise StandFehler(
            f"die Versionslinie {linie!r} hat ein Element — kein Uebergang, nichts "
            "abzunehmen (Weg c: keine Aenderung)")
    if linie[-1] != tbox.TBOX_VERSION:
        raise StandFehler(f"die Linie endet nicht bei der Version des Codes ({tbox.TBOX_VERSION})")
    if Path(artefakt).is_absolute() or ".." in Path(artefakt).parts:
        raise StandFehler(f"artefakt {artefakt!r} ist kein relativer, kanonischer Pfad")
    for wurzel in [fall] + ([repo_root] if repo_root is not None else []):
        ort = wurzel / artefakt
        if ort.is_file():
            sha = hashlib.sha256(ort.read_bytes()).hexdigest()
            break
    else:
        raise StandFehler(f"artefakt {artefakt!r} liegt weder im Fall noch im Repo")
    return {
        "schema_version": TBOX_AENDERUNG_SCHEMA_VERSION,
        "von_version": linie[-2],
        "nach_version": linie[-1],
        "tbox_sha256": tbox_modul_sha256(),
        "artefakt": {"pfad": artefakt, "sha256": sha},
        "begruendung": begruendung,
    }


def _ersetze(ziel: Path, daten: bytes) -> None:
    ziel.parent.mkdir(parents=True, exist_ok=True)
    raeume_schreibreste(ziel)
    tmp = ziel.parent / f".{ziel.name}.{secrets.token_hex(8)}.tmp"
    try:
        with open(tmp, "wb") as datei:
            datei.write(daten)
            datei.flush()
            os.fsync(datei.fileno())
        os.replace(tmp, ziel)
    finally:
        tmp.unlink(missing_ok=True)


def _json_bytes(daten: Dict[str, Any]) -> bytes:
    return (json.dumps(daten, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def main(argv: Optional[List[str]] = None) -> ToolboxResult:
    p = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.gates.stand_belegen",
        description="Belege der Standabnahme (A-K2, A-O1): Verweis 'keine Aenderung', "
                    "T-Box-Uebergang. Producer, kein Gate.")
    unter = p.add_subparsers(dest="aktion", required=True)
    v = unter.add_parser("verweisen", help="Verweis auf einen frueher angenommenen Snapshot")
    v.add_argument("--fall", required=True)
    v.add_argument("--repo-root", dest="repo_root", required=True)
    v.add_argument("--gate", required=True, choices=[g.gate for g in sa.GEGENSTAENDE])
    v.add_argument("--snapshot", required=True, help="der frueher angenommene Snapshot (Datei)")
    t = unter.add_parser("tbox", help="Aenderungsbeleg des letzten T-Box-Uebergangs")
    t.add_argument("--fall", required=True)
    t.add_argument("--repo-root", dest="repo_root", required=True)
    t.add_argument("--artefakt", required=True,
                   help="ADR oder Aenderungsvermerk, relativ zu Fall oder Repo")
    t.add_argument("--begruendung", required=True)
    args = p.parse_args(argv)

    def _fehler(code: int, text: str) -> ToolboxResult:
        return build_result(command=COMMAND, gate_version=GATE_VERSION, exit_code=code,
                            errors=[{"code": "stand", "message": text}])

    fall = Path(args.fall)
    if not (fall / "eingang.json").is_file():
        return _fehler(Exit.USAGE, f"kein Fall-Arbeitsbereich: {fall}")
    repo = Path(args.repo_root).resolve()
    if args.aktion == "verweisen":
        gegenstand = sa.gegenstand_fuer(args.gate)
        try:
            snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return _fehler(Exit.USAGE, f"--snapshot nicht lesbar: {exc}")
        verweis = baue_verweis(snapshot)
        fehler = verweis_fehler(verweis, gegenstand, lebender_stand(args.gate, repo))
        if fehler:
            return _fehler(Exit.FILE_CONTRACT, "; ".join(fehler[:5]))
        ziel, daten = fall / gegenstand.verweis_relativ, _json_bytes(verweis)
        summary = {"gate": args.gate, "anzeige": sa.anzeige_keine_aenderung(
            snapshot["snapshot_sha256"], verweis["herkunft"])}
    else:
        try:
            beleg = tbox_aenderungsbeleg(fall, repo, args.artefakt, args.begruendung.strip())
        except StandFehler as exc:
            return _fehler(Exit.FILE_CONTRACT, str(exc))
        ziel, daten = fall / TBOX_AENDERUNG_RELATIV, _json_bytes(beleg)
        summary = {"von_version": beleg["von_version"], "nach_version": beleg["nach_version"],
                   "stellungnahme": f"{TBOX_STELLUNGNAHME_RELATIV} legt das Aktuariat vor"}
    _ersetze(ziel, daten)
    return build_result(command=COMMAND, gate_version=GATE_VERSION, exit_code=Exit.OK,
                        paths={"beleg": str(ziel)}, summary=summary,
                        output_hashes={str(ziel): hashlib.sha256(daten).hexdigest()})


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_command(main))
