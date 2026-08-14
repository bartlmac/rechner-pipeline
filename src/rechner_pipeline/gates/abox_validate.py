"""``abox_validate`` gate command — Gate O1 (A-Box-Contract + Coverage).

Prueft die A-Box eines Fall-Arbeitsbereichs:

* Struktur- und Kreuz-Objekt-Contract (Pydantic-Validierung beim Laden
  plus :func:`rechner_pipeline.ontologie.abox.validate_abox`), inklusive
  Verankerung jeder Quelle im Eingang-Register des Falls (P1),
* Coverage gegen den PFLICHTUMFANG der T-Box je Parametrierungszelle
  (P6) — eine unvollstaendige A-Box blockiert Stage 2,
* offene Diskrepanzen (P2) — sie blockieren ebenfalls: die Aufloesung
  ist ein menschlicher Vorgang (Gate G-1), kein Durchwinken.

Blocking failures exit ``20`` (``Exit.FILE_CONTRACT``); Usage-Fehler
exit ``2``. Schreibt den ``abox_validate.gate.json``-Ledger-Eintrag wie
die uebrigen Gates; der Coverage-Bericht wird als eigenes Artefakt
neben die A-Box gelegt (deterministisch, diffbar).

Run via::

    python -m rechner_pipeline.gates.abox_validate --fall faelle/klv-tg2015 \\
        [--diagnostics-dir DIR] [--repo-root .]

Knoten: klv
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

from rechner_pipeline.ontologie.abox import abox_pfad, lade, validate_abox
from rechner_pipeline.ontologie.coverage import coverage_bericht
from rechner_pipeline.gates._common import (
    Exit,
    add_request_json_arg,
    build_result,
    hash_files,
    log,
    merge_request_into_args,
    read_request_json,
    run_command,
    utc_now,
    write_gate_ledger,
)

GATE = "O1.abox-contract"
GATE_VERSION = "0.1.0"

COVERAGE_DATEI = "coverage.json"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.gates.abox_validate",
        description=(
            "Gate O1: A-Box eines Falls gegen T-Box-Contract, "
            "Eingang-Register und Pflicht-Coverage pruefen."
        ),
    )
    parser.add_argument(
        "--fall", default=None,
        help="Fall-Arbeitsbereich (enthaelt eingang.json und "
        "abgeleitet/abox/abox.json).",
    )
    parser.add_argument("--repo-root", dest="repo_root", default=None)
    parser.add_argument(
        "--diagnostics-dir", dest="diagnostics_dir", default=None,
        help="Verzeichnis fuer den Gate-Ledger-Eintrag "
        "(Default: <fall>/abgeleitet/diagnostics).",
    )
    add_request_json_arg(parser)
    return parser


def main(argv: Optional[List[str]] = None):
    started_at = utc_now()
    parser = _build_parser()
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
                result,
                diagnostics_dir,
                repo_root=Path(args.repo_root) if args.repo_root else None,
                started_at=started_at,
                ended_at=utc_now(),
                command_line=argv if argv is not None else sys.argv[1:],
            )
        except Exception as exc:  # noqa: BLE001 — Ledger maskiert nie das Gate
            log(f"abox_validate: gate-ledger write failed: {exc}")
        return result

    def _usage(errors: List[dict]):
        return _finalize(build_result(
            command="abox_validate",
            gate=GATE,
            gate_version=GATE_VERSION,
            exit_code=Exit.USAGE,
            errors=errors,
        ))

    if fall is None:
        return _usage([{"code": "missing_arg", "message": "--fall ist erforderlich"}])
    register_pfad = fall / "eingang.json"
    abox_datei = abox_pfad(fall)
    fehlend = [str(p) for p in (register_pfad, abox_datei) if not p.is_file()]
    if fehlend:
        return _usage([
            {"code": "missing_input", "message": f"Datei nicht gefunden: {p}"}
            for p in fehlend
        ])

    repo_root = Path(args.repo_root).resolve() if args.repo_root else None
    input_hashes = hash_files(
        [register_pfad, abox_datei], base=repo_root, missing_ok=True
    )

    errors: List[dict] = []
    try:
        abox = lade(fall)
    except Exception as exc:  # Pydantic-Validierung ist Teil des Contracts
        return _finalize(build_result(
            command="abox_validate",
            gate=GATE,
            gate_version=GATE_VERSION,
            exit_code=Exit.FILE_CONTRACT,
            errors=[{"code": "schema", "message": str(exc)}],
            paths={"fall": str(fall), "abox": str(abox_datei)},
            input_hashes=input_hashes,
        ))

    register = json.loads(register_pfad.read_text(encoding="utf-8"))
    for meldung in validate_abox(abox, register):
        errors.append({"code": "abox", "message": meldung})

    bericht = coverage_bericht(abox)
    coverage_pfad = abox_datei.parent / COVERAGE_DATEI
    coverage_pfad.write_text(
        json.dumps(bericht, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if not bericht["vollstaendig"]:
        fehlende: List[str] = []
        for gen in bericht["generationen"]:
            for zid, felder in gen["zellen"].items():
                for feld, info in felder.items():
                    if info["zustand"] != "belegt":
                        fehlende.append(
                            f"{gen['generation']}/{zid}/{feld}: {info['zustand']}"
                        )
        errors.append({
            "code": "coverage",
            "message": (
                "Pflichtumfang nicht vollstaendig belegt — "
                + "; ".join(fehlende[:20])
                + (f" (+{len(fehlende) - 20} weitere)" if len(fehlende) > 20 else "")
            ),
        })
    if bericht["diskrepanzen_offen"]:
        offene = [d.id for d in abox.diskrepanzen if d.status == "offen"]
        errors.append({
            "code": "diskrepanzen_offen",
            "message": (
                f"{len(offene)} offene Diskrepanz(en) — Aufloesung ist ein "
                "menschlicher Vorgang (Gate G-1): " + ", ".join(offene)
            ),
        })

    summary: Dict[str, object] = {
        "generationen": [g.id for g in abox.generationen],
        "zellen": sum(len(g.zellen) for g in abox.generationen),
        "belegt_quoten": {
            g["generation"]: round(g["belegt_quote"], 4)
            for g in bericht["generationen"]
        },
        "diskrepanzen_offen": bericht["diskrepanzen_offen"],
        "diskrepanzen_aufgeloest": sum(
            1 for d in abox.diskrepanzen if d.status == "aufgeloest"
        ),
        "vollstaendig": bericht["vollstaendig"],
    }
    return _finalize(build_result(
        command="abox_validate",
        gate=GATE,
        gate_version=GATE_VERSION,
        exit_code=Exit.FILE_CONTRACT if errors else Exit.OK,
        errors=errors,
        paths={
            "fall": str(fall),
            "abox": str(abox_datei),
            "coverage": str(coverage_pfad),
        },
        summary=summary,
        input_hashes=input_hashes,
    ))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_command(main))
