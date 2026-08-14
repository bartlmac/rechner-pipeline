"""``gate_entscheid`` — der P9-Snapshot eines menschlichen Gates.

Ein menschliches Gate (G-1 fachlich, G-2 Abnahme, G-T T-Box-Aenderung)
endet nicht in einer Commit-Message, sondern in einem unveraenderlichen,
inhaltsadressierten Snapshot: WER hat WAS auf WELCHEM Stand entschieden,
mit welcher Begruendung. Der Snapshot haelt die SHA-256-Hashes aller
entscheidungsrelevanten Artefakte des Falls fest (Eingang-Register,
A-Box, Spez, Coverage, Fachspez, Gate-Ledger) plus den Git-Stand des
Systems (Setup-Provenienz, P1) — der Lauf ist daraus reproduzierbar.

Die Sperre gegen stille Dauerprovisorien (P2/P4): eine ANNAHME wird
verweigert, solange die A-Box VORLAEUFIGE Diskrepanz-Aufloesungen
traegt — die fachliche Entscheidung ist genau der Zweck des Gates
(``python -m rechner_pipeline.ontologie.entscheide`` ersetzt eine
vorlaeufige Aufloesung durch die menschliche). Eine ABLEHNUNG ist
jederzeit snapshotbar.

Der Snapshot-Dateiname traegt den Inhalts-Hash; eine bestehende Datei
wird NIE ueberschrieben.

Run via::

    python -m rechner_pipeline.gates.gate_entscheid --fall faelle/klv-tg2015 \\
        --gate G-1 --entscheid angenommen --entscheider "Bartek" \\
        --begruendung "..." [--repo-root .]

Knoten: klv
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

from rechner_pipeline.gates._common import (
    Exit,
    add_request_json_arg,
    build_result,
    log,
    merge_request_into_args,
    read_request_json,
    run_command,
    utc_now,
    write_gate_ledger,
)

GATE_VERSION = "0.1.0"
GUELTIGE_GATES = ("G-1", "G-2", "G-T")


def _sha256_datei(pfad: Path) -> str:
    h = hashlib.sha256()
    with pfad.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _artefakt_hashes(fall: Path) -> Dict[str, str]:
    """Alle entscheidungsrelevanten Artefakte des Falls, gehasht."""
    kandidaten: List[Path] = [fall / "eingang.json", fall / "fall.json"]
    abgeleitet = fall / "abgeleitet"
    for muster in ("abox/abox.json", "abox/coverage.json"):
        kandidaten.append(abgeleitet / muster)
    for unterordner in ("spez", "fachspez", "diagnostics"):
        verzeichnis = abgeleitet / unterordner
        if verzeichnis.is_dir():
            kandidaten.extend(sorted(
                p for p in verzeichnis.iterdir() if p.is_file()
            ))
    return {
        str(p.relative_to(fall)): _sha256_datei(p)
        for p in kandidaten if p.is_file()
    }


def _git_stand(repo_root: Path) -> Dict[str, str]:
    """Setup-Provenienz: der Git-Stand des Systems (P1)."""
    stand: Dict[str, str] = {}
    for name, argv in (
        ("commit", ["git", "rev-parse", "HEAD"]),
        ("branch", ["git", "rev-parse", "--abbrev-ref", "HEAD"]),
        ("dirty", ["git", "status", "--porcelain"]),
    ):
        try:
            out = subprocess.run(
                argv, cwd=repo_root, capture_output=True, text=True,
                check=True, timeout=30,
            ).stdout.strip()
        except Exception:  # noqa: BLE001 — Snapshot ohne Git bleibt moeglich
            out = "unbekannt"
        stand[name] = ("ja" if out else "nein") if name == "dirty" else out
    return stand


def main(argv: Optional[List[str]] = None):
    started_at = utc_now()
    parser = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.gates.gate_entscheid",
        description="P9-Snapshot eines menschlichen Gates schreiben.",
    )
    parser.add_argument("--fall", default=None)
    parser.add_argument("--gate", default=None, choices=GUELTIGE_GATES)
    parser.add_argument("--entscheid", default=None,
                        choices=["angenommen", "abgelehnt"])
    parser.add_argument("--entscheider", default=None)
    parser.add_argument("--begruendung", default=None)
    parser.add_argument("--repo-root", dest="repo_root", default=".")
    parser.add_argument("--diagnostics-dir", dest="diagnostics_dir", default=None)
    add_request_json_arg(parser)
    args = parser.parse_args(argv)
    request = read_request_json(args.request_json)
    args = merge_request_into_args(args, request)

    fall = Path(args.fall) if args.fall else None
    diagnostics_dir = (
        Path(args.diagnostics_dir) if args.diagnostics_dir
        else (fall / "abgeleitet" / "diagnostics" if fall
              else Path.cwd() / "runs" / "diagnostics")
    )

    def _finalize(result):
        try:
            write_gate_ledger(
                result, diagnostics_dir,
                repo_root=Path(args.repo_root) if args.repo_root else None,
                started_at=started_at, ended_at=utc_now(),
                command_line=argv if argv is not None else sys.argv[1:],
            )
        except Exception as exc:  # noqa: BLE001
            log(f"gate_entscheid: gate-ledger write failed: {exc}")
        return result

    def _usage(message: str):
        return _finalize(build_result(
            command="gate_entscheid", gate=f"P9.{args.gate or '?'}",
            gate_version=GATE_VERSION, exit_code=Exit.USAGE,
            errors=[{"code": "usage", "message": message}],
        ))

    fehlend = [name for name, wert in (
        ("--fall", fall), ("--gate", args.gate),
        ("--entscheid", args.entscheid), ("--entscheider", args.entscheider),
        ("--begruendung", args.begruendung),
    ) if not wert]
    if fehlend:
        return _usage("erforderlich: " + ", ".join(fehlend))
    if not (fall / "eingang.json").is_file():
        return _usage(f"kein Fall-Arbeitsbereich: {fall}")

    # Vorlaeufig-Sperre: eine Annahme setzt endgueltige Entscheidungen
    # voraus — sonst wuerde der Arbeitsstand eines Agenten still zur
    # abgenommenen Wahrheit (P2/P4).
    if args.entscheid == "angenommen":
        from rechner_pipeline.ontologie.abox import abox_pfad, lade

        if abox_pfad(fall).is_file():
            abox = lade(fall)
            vorlaeufige = sorted(
                d.id for d in abox.diskrepanzen
                if d.entscheidung is not None and d.entscheidung.vorlaeufig
            )
            if vorlaeufige:
                return _finalize(build_result(
                    command="gate_entscheid", gate=f"P9.{args.gate}",
                    gate_version=GATE_VERSION,
                    exit_code=Exit.FILE_CONTRACT,
                    errors=[{
                        "code": "vorlaeufig",
                        "message": (
                            "Annahme verweigert: vorlaeufige "
                            "Diskrepanz-Aufloesungen stehen aus — "
                            + ", ".join(vorlaeufige)
                            + " (aufloesen mit python -m "
                            "rechner_pipeline.ontologie.entscheide)"
                        ),
                    }],
                    paths={"fall": str(fall)},
                ))

    snapshot = {
        "schema_version": 1,
        "gate": args.gate,
        "entscheid": args.entscheid,
        "entscheider": args.entscheider,
        "begruendung": args.begruendung,
        "entschieden_am": utc_now(),
        "fall": str(fall),
        "artefakt_hashes": _artefakt_hashes(fall),
        "system": _git_stand(Path(args.repo_root)),
    }
    kanonisch = json.dumps(
        snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    inhalt_hash = hashlib.sha256(kanonisch.encode("utf-8")).hexdigest()
    snapshot["snapshot_sha256"] = inhalt_hash

    ziel = (fall / "abgeleitet" / "entscheide"
            / f"{args.gate}-{inhalt_hash[:12]}.json")
    ziel.parent.mkdir(parents=True, exist_ok=True)
    if ziel.exists():
        return _usage(f"Snapshot existiert bereits: {ziel} — nie ueberschreiben")
    ziel.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return _finalize(build_result(
        command="gate_entscheid", gate=f"P9.{args.gate}",
        gate_version=GATE_VERSION, exit_code=Exit.OK,
        paths={"fall": str(fall), "snapshot": str(ziel)},
        summary={
            "gate": args.gate,
            "entscheid": args.entscheid,
            "entscheider": args.entscheider,
            "snapshot_sha256": inhalt_hash,
            "artefakte": len(snapshot["artefakt_hashes"]),
            "system_commit": snapshot["system"]["commit"][:12],
            "system_dirty": snapshot["system"]["dirty"],
        },
    ))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_command(main))
