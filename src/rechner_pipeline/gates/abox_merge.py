"""``abox_merge`` — der Stage-1-Merge als protokollierter Uebergang.

Die Systempruefung fand den Merge als einzige unprotokollierte Stelle
der Kette. Dieses Kommando macht ihn zum Gate-artigen Producer: es
merged die Fragmente eines Falls deterministisch zur A-Box UND
schreibt den Ledger, der die Kette traegt — Fragment-Hashes, Akteure
(Konvention erzwungen), Erhebungszeitpunkt. Gate P-Q3 rechnet den Merge
daraus nach (``ontologie.kette``): eine A-Box, die nicht aus ihren
Fragmenten folgt, faellt dort.

Akteure kommen aus ``fragmente/akteure.json``
(``{"<fragment-datei>": "<modell>/<skill>@<git-sha>"}``) — der
Orchestrator legt sie beim Extrahieren ab.

**Einmal, nicht bei jeder Neuzeichnung.** Der Merge baut die A-Box
FRISCH aus den Fragmenten. Traegt die vorhandene A-Box aufgeloeste
Diskrepanzen (Entscheidungen des Verantwortlichen Aktuars, Gate A-Q1),
wuerde ein erneuter Merge sie still ueberschreiben — genau das ist am
2026-09-07 im zweiten Baldrian-Fall passiert (14 Entscheidungen weg,
Recovery ueber Backup). Deshalb verweigert das Kommando dann den
Lauf; ``--ueberschreiben`` ist die ausdrueckliche Entscheidung, die
Aufloesungen zu verwerfen und A-Q1 neu zu entscheiden. Bei einer
Neuzeichnung auf neuem Systemstand werden nur die PRUEF-Gates neu
gefahren (P-Q3, P-K1, ...), nicht der Merge.

Run via::

    python -m rechner_pipeline.gates.abox_merge --fall faelle/<fall> \\
        [--repo-root .] [--diagnostics-dir DIR] [--ueberschreiben]

Knoten: klv
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List, Optional

from rechner_pipeline.gates._common import (
    hashes_von,
    lies_gehasht,
    Exit,
    GateArgumentParser,
    GateCliContract,
    add_request_json_arg,
    begin_gate_ledger_attempt,
    build_result,
    finalize_gate_ledger,
    hash_files,
    parse_gate_args,
    run_command,
    utc_now,
)

GATE = "P-Q2.zusammenfuehrung"
GATE_VERSION = "0.1.0"
CLI_CONTRACT = GateCliContract(
    command="abox_merge",
    gate=GATE,
    gate_version=GATE_VERSION,
    diagnostics_from="fall",
)


def _aufgeloeste_diskrepanzen(fall: Path) -> List[str]:
    """Ids der aufgeloesten Diskrepanzen der vorhandenen A-Box (leer, wenn
    keine A-Box da ist oder sie nicht lesbar ist — dann gibt es nichts zu
    schuetzen, und der Merge darf schreiben)."""
    pfad = fall / "abgeleitet" / "abox" / "abox.json"
    if not pfad.is_file():
        return []
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(daten, dict):
        return []
    return sorted(
        str(d.get("id"))
        for d in (daten.get("diskrepanzen") or [])
        if isinstance(d, dict) and d.get("status") == "aufgeloest"
    )


def main(argv: Optional[List[str]] = None):
    started_at = utc_now()
    parser = GateArgumentParser(
        gate_contract=CLI_CONTRACT,
        prog="python -m rechner_pipeline.gates.abox_merge",
        description=(
            "Fragmente eines Falls deterministisch zur A-Box mergen "
            "(mit Ketten-Ledger)."
        ),
    )
    parser.add_argument("--fall", default=None)
    parser.add_argument("--repo-root", dest="repo_root", default=None)
    parser.add_argument("--diagnostics-dir", dest="diagnostics_dir", default=None)
    parser.add_argument(
        "--ueberschreiben", dest="ueberschreiben", action="store_true",
        help="Eine vorhandene A-Box MIT aufgeloesten Diskrepanzen verwerfen "
             "und neu mergen (die Entscheidungen von A-Q1 gehen verloren "
             "und sind neu zu treffen). Ohne dieses Flag verweigert das "
             "Kommando den Lauf.")
    add_request_json_arg(parser)
    args = parse_gate_args(parser, argv)

    fall = Path(args.fall) if args.fall else None
    diagnostics_dir = (
        Path(args.diagnostics_dir) if args.diagnostics_dir
        else (fall / "abgeleitet" / "diagnostics" if fall
              else Path.cwd() / "runs" / "diagnostics")
    )
    ledger_start_fehler = begin_gate_ledger_attempt(
        command="abox_merge",
        gate=GATE,
        gate_version=GATE_VERSION,
        diagnostics_dir=diagnostics_dir,
        repo_root=Path(args.repo_root) if args.repo_root else None,
        started_at=started_at,
        command_line=argv if argv is not None else sys.argv[1:],
    )
    if ledger_start_fehler is not None:
        return ledger_start_fehler

    def _finalize(result):
        return finalize_gate_ledger(result)

    def _fehler(exit_code: int, code: str, message: str):
        return _finalize(build_result(
            command="abox_merge", gate=GATE, gate_version=GATE_VERSION,
            exit_code=exit_code,
            errors=[{"code": code, "message": message}],
            paths={"fall": str(fall) if fall else ""},
        ))

    if fall is None:
        return _fehler(Exit.USAGE, "usage", "--fall ist erforderlich")
    register_pfad = fall / "eingang.json"
    if not register_pfad.is_file():
        return _fehler(Exit.USAGE, "usage", f"kein Fall-Arbeitsbereich: {fall}")

    # Kein stiller Overwrite von Entscheidungen: Eine A-Box mit
    # aufgeloesten Diskrepanzen ist ein Entscheidungstraeger, kein
    # Zwischenstand. Geprueft auf der JSON-Ebene, damit die Wache auch
    # eine A-Box aelteren Schemas erkennt.
    entschieden = _aufgeloeste_diskrepanzen(fall)
    if entschieden and not args.ueberschreiben:
        return _fehler(
            Exit.FILE_CONTRACT, "abox_entschieden",
            f"{fall / 'abgeleitet' / 'abox' / 'abox.json'} traegt "
            f"{len(entschieden)} aufgeloeste Diskrepanz(en) (z. B. "
            f"{entschieden[:3]}) — ein erneuter Merge wuerde die Entscheidungen "
            "von A-Q1 verwerfen. Bei einer Neuzeichnung nur die Pruef-Gates "
            "(P-Q3, P-K1, ...) neu fahren; wer die Aufloesungen wirklich "
            "verwerfen will, sagt es mit --ueberschreiben.",
        )

    from rechner_pipeline.ontologie.befuellung import (
        BefuellungsFehler,
        baue_abox,
    )
    from rechner_pipeline.ontologie.kette import (
        fragment_aus_bytes,
        fragment_pfade,
        fragmente_ordner,
    )

    # Fragmente genau einmal lesen: fragment_hashes, input_hashes UND das
    # Parsen stammen aus denselben Bytes (Review T23-01) — vorher wurde jede
    # Fragmentdatei dreimal getrennt gelesen.
    try:
        gelesene = {p.name: lies_gehasht(p) for p in fragment_pfade(fall)}
        fragmente = {
            name: fragment_aus_bytes(g.roh) for name, g in gelesene.items()
        }
    except Exception as exc:  # Schema-Bruch eines Fragments
        return _fehler(Exit.FILE_CONTRACT, "fragment", f"Fragment unlesbar: {exc}")
    if not fragmente:
        return _fehler(Exit.FILE_CONTRACT, "fragment",
                       f"keine Fragmente unter {fragmente_ordner(fall)}")
    akteure_pfad = fragmente_ordner(fall) / "akteure.json"
    if not akteure_pfad.is_file():
        return _fehler(
            Exit.FILE_CONTRACT, "akteure",
            f"{akteure_pfad} fehlt — je Fragment ein Akteur "
            "(<modell>/<skill>@<git-sha>), P1",
        )
    akteure = json.loads(akteure_pfad.read_text(encoding="utf-8"))
    fehlend = sorted(set(fragmente) - set(akteure))
    if fehlend:
        return _fehler(Exit.FILE_CONTRACT, "akteure",
                       f"Akteur fehlt fuer: {', '.join(fehlend)}")

    register_gelesen = lies_gehasht(register_pfad)
    register = register_gelesen.json()
    erhoben_am = utc_now()
    namen = sorted(fragmente)
    try:
        abox = baue_abox(
            str(fall),
            [fragmente[n] for n in namen],
            register,
            [akteure[n] for n in namen],
            erhoben_am,
        )
    except BefuellungsFehler as exc:
        return _fehler(Exit.FILE_CONTRACT, "merge", str(exc))

    from rechner_pipeline.ontologie.abox import speichere

    abox_pfad_ = speichere(abox, fall)

    fragment_hashes = {name: gelesene[name].sha256 for name in namen}
    return _finalize(build_result(
        command="abox_merge", gate=GATE, gate_version=GATE_VERSION,
        exit_code=Exit.OK,
        paths={"fall": str(fall), "abox": str(abox_pfad_)},
        summary={
            "fragmente": namen,
            "fragment_hashes": fragment_hashes,
            "akteure": {n: akteure[n] for n in namen},
            "erhoben_am": erhoben_am,
            "generationen": [g.id for g in abox.generationen],
            "diskrepanzen": len(abox.diskrepanzen),
        },
        input_hashes=hashes_von(
            [register_gelesen, *(gelesene[n] for n in namen)],
            base=Path(args.repo_root).resolve() if args.repo_root else None,
        ),
        output_hashes=hash_files([abox_pfad_], missing_ok=True),
    ))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_command(main))
