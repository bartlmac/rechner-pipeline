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

Der Snapshot-Dateiname traegt den Hash des ENTSCHEIDUNGSINHALTS (ohne
Zeitstempel): derselbe Entscheid auf demselben Stand ist idempotent,
eine bestehende Datei wird nie ueberschrieben. Jeder Snapshot pinnt die
Hashes aller frueheren Snapshots seines Gates (``vorgaenger``) — es
gilt der Snapshot, den kein anderer als Vorgaenger nennt. Abgelegt wird
in ``<fall>/entscheide/`` neben dem Eingang: Entscheidungen sind wie
der Eingang NICHT regenerierbar und liegen deshalb ausserhalb der
aufraeumbaren ``abgeleitet/``-Zone.

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


def entscheide_verzeichnis(fall: Path) -> Path:
    """Snapshots liegen NEBEN dem Eingang: nicht regenerierbar,
    ausserhalb der aufraeumbaren abgeleitet/-Zone."""
    return fall / "entscheide"


def _artefakt_hashes(fall: Path, ausser_gate: str = "") -> Dict[str, str]:
    """Alle entscheidungsrelevanten Artefakte des Falls, gehasht —
    inklusive der registrierten Eingangsdateien selbst und der
    Entscheid-Snapshots ANDERER Gates (Kreuz-Verkettung). Die eigenen
    Gate-Snapshots laufen ueber ``vorgaenger``, nicht ueber die
    Artefaktliste — sonst waere kein Wiederholungs-Aufruf je idempotent.
    """
    kandidaten: List[Path] = [fall / "eingang.json", fall / "fall.json"]
    eingang = fall / "eingang"
    if eingang.is_dir():
        kandidaten.extend(sorted(p for p in eingang.iterdir() if p.is_file()))
    abgeleitet = fall / "abgeleitet"
    for muster in ("abox/abox.json", "abox/coverage.json"):
        kandidaten.append(abgeleitet / muster)
    for verzeichnis in (
        abgeleitet / "spez", abgeleitet / "fachspez",
        abgeleitet / "diagnostics", entscheide_verzeichnis(fall),
    ):
        if not verzeichnis.is_dir():
            continue
        for pfad in sorted(verzeichnis.iterdir()):
            if not pfad.is_file():
                continue
            # Eigene Gate-Snapshots laufen ueber die vorgaenger-Kette;
            # die gate_entscheid-Ledger sind Prozessprotokolle DIESES
            # Werkzeugs, nicht entschiedener Stand — beides wuerde jede
            # Wiederholung un-idempotent machen.
            if (ausser_gate and pfad.parent == entscheide_verzeichnis(fall)
                    and pfad.name.startswith(f"{ausser_gate}-")):
                continue
            if pfad.name.startswith("gate_entscheid"):
                continue
            kandidaten.append(pfad)
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
            stand[name] = "unbekannt"
            continue
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

    ledger_command = (
        f"gate_entscheid_{args.gate.lower().replace('-', '')}"
        if args.gate else "gate_entscheid"
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
            command=ledger_command, gate=f"P9.{args.gate or '?'}",
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
    # --request-json umgeht die argparse-choices — hier hart nachpruefen.
    if args.gate not in GUELTIGE_GATES:
        return _usage(f"unbekanntes Gate {args.gate!r} (erlaubt: "
                      + ", ".join(GUELTIGE_GATES) + ")")
    if args.entscheid not in ("angenommen", "abgelehnt"):
        return _usage(f"unbekannter Entscheid {args.entscheid!r}")
    if not (fall / "eingang.json").is_file():
        return _usage(f"kein Fall-Arbeitsbereich: {fall}")

    def _sperre(code: str, message: str):
        return _finalize(build_result(
            command=ledger_command, gate=f"P9.{args.gate}",
            gate_version=GATE_VERSION,
            exit_code=Exit.FILE_CONTRACT,
            errors=[{"code": code, "message": message}],
            paths={"fall": str(fall)},
        ))

    # Annahme-Sperre: eine Annahme setzt einen integeren Fall und
    # endgueltige Entscheidungen voraus — sonst wuerde ein ungeloester
    # Quellen-Widerspruch oder der Arbeitsstand eines Agenten still zur
    # abgenommenen Wahrheit (P2/P4). Die A-Box ist dafuer PFLICHT: eine
    # Sperre, die per Dateiloeschung abschaltbar waere, ist keine.
    if args.entscheid == "angenommen":
        import json as _json

        from rechner_pipeline import fall as fall_mod
        from rechner_pipeline.ontologie.abox import (
            abox_pfad,
            lade,
            validate_abox,
        )

        eingangs_fehler = fall_mod.pruefen(fall)
        if eingangs_fehler:
            return _sperre("eingang", "Annahme verweigert — Eingang "
                           "verletzt das Register: "
                           + "; ".join(eingangs_fehler[:5]))
        if not abox_pfad(fall).is_file():
            return _sperre(
                "abox", f"Annahme verweigert: keine A-Box ({abox_pfad(fall)}) "
                "— ohne Stage 1 gibt es nichts abzunehmen",
            )
        try:
            abox = lade(fall)
        except Exception as exc:  # Ladefehler ist Befund MIT Ledger
            return _sperre("abox", f"A-Box unlesbar: {exc}")
        register = _json.loads(
            (fall / "eingang.json").read_text(encoding="utf-8")
        )
        abox_fehler = validate_abox(abox, register)
        if abox_fehler:
            return _sperre("abox", "Annahme verweigert — A-Box "
                           "inkonsistent: " + "; ".join(abox_fehler[:5]))
        offene = sorted(
            d.id for d in abox.diskrepanzen if d.status == "offen"
        )
        if offene:
            return _sperre(
                "offen", "Annahme verweigert: OFFENE Diskrepanzen — "
                + ", ".join(offene)
                + " (aufloesen mit python -m "
                "rechner_pipeline.ontologie.entscheide)",
            )
        vorlaeufige = sorted(
            d.id for d in abox.diskrepanzen
            if d.entscheidung is not None and d.entscheidung.vorlaeufig
        )
        if vorlaeufige:
            return _sperre(
                "vorlaeufig", "Annahme verweigert: vorlaeufige "
                "Diskrepanz-Aufloesungen stehen aus — "
                + ", ".join(vorlaeufige)
                + " (aufloesen mit python -m "
                "rechner_pipeline.ontologie.entscheide)",
            )

    verzeichnis = entscheide_verzeichnis(fall)
    verzeichnis.mkdir(parents=True, exist_ok=True)
    bestehende = {}
    for pfad in sorted(verzeichnis.glob(f"{args.gate}-*.json")):
        daten = json.loads(pfad.read_text(encoding="utf-8"))
        bestehende[daten.get("snapshot_sha256", pfad.name)] = (pfad, daten)
    referenziert = {
        v for _, daten in bestehende.values()
        for v in daten.get("vorgaenger", [])
    }
    # Es GILT der Snapshot, den kein anderer als Vorgaenger nennt.
    geltende = [
        (pfad, daten) for sha, (pfad, daten) in bestehende.items()
        if sha not in referenziert
    ]

    kern_inhalt = {
        "gate": args.gate,
        "entscheid": args.entscheid,
        "entscheider": args.entscheider,
        "begruendung": args.begruendung,
        "fall": str(fall),
        "artefakt_hashes": _artefakt_hashes(fall, ausser_gate=args.gate),
        "system": _git_stand(Path(args.repo_root)),
    }
    # Idempotenz gegen den GELTENDEN Snapshot: derselbe Entscheid auf
    # demselben Stand wird gemeldet, nicht dupliziert. Ein INHALTLICH
    # anderer Entscheid erzeugt einen neuen Snapshot, der alle
    # bisherigen pinnt (Kette).
    for pfad, daten in geltende:
        if all(daten.get(k) == v for k, v in kern_inhalt.items()):
            return _finalize(build_result(
                command=ledger_command, gate=f"P9.{args.gate}",
                gate_version=GATE_VERSION, exit_code=Exit.OK,
                paths={"fall": str(fall), "snapshot": str(pfad)},
                summary={"gate": args.gate, "entscheid": args.entscheid,
                         "snapshot_sha256": daten.get("snapshot_sha256"),
                         "bereits_vorhanden": True},
            ))

    vorgaenger = sorted(bestehende)
    snapshot = {"schema_version": 1, **kern_inhalt, "vorgaenger": vorgaenger}
    # Der Hash adressiert den ENTSCHEIDUNGSINHALT plus Kette — ohne
    # Zeitstempel (sonst waere jeder Snapshot unik und die
    # Nie-Ueberschreiben-Pruefung toter Code). Der Zeitstempel steht im
    # Dateiinhalt, nicht im Hash.
    kanonisch = json.dumps(
        snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    inhalt_hash = hashlib.sha256(kanonisch.encode("utf-8")).hexdigest()
    snapshot["snapshot_sha256"] = inhalt_hash
    snapshot["entschieden_am"] = utc_now()

    ziel = verzeichnis / f"{args.gate}-{inhalt_hash[:12]}.json"
    if ziel.exists():
        return _usage(
            f"Snapshot existiert bereits: {ziel} — nie ueberschreiben"
        )
    ziel.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return _finalize(build_result(
        command=ledger_command, gate=f"P9.{args.gate}",
        gate_version=GATE_VERSION, exit_code=Exit.OK,
        paths={"fall": str(fall), "snapshot": str(ziel)},
        summary={
            "gate": args.gate,
            "entscheid": args.entscheid,
            "entscheider": args.entscheider,
            "snapshot_sha256": inhalt_hash,
            "vorgaenger": len(vorgaenger),
            "artefakte": len(snapshot["artefakt_hashes"]),
            "system_commit": snapshot["system"]["commit"][:12],
            "system_dirty": snapshot["system"]["dirty"],
        },
    ))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_command(main))
