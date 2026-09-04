"""``bestand_validate`` toolbox command — gate P-B1 (Bestandsdaten-Contract).

Validates the Bestandsdaten tables against their schemas and invariants
(engines: :mod:`rechner_pipeline.models.bestand`,
:func:`rechner_pipeline.qa.bestand.sanity_check`):

* Basisbestand/Gesamtbestand (``--portfolio``): physischer Parquet- und
  Spalten-Contract, Basisstatus, Enums, Zeilen-Invarianten und
  Datums-Konsistenz (``read_portfolio``/``validate_portfolio``).
* Statushistorie (``--historie``, optional): fortlaufende status_id,
  terminale Status nur am Ende, Datumsgrenzen (``validate_statushistorie``).
* Erhoehungsscheiben (``--scheiben``, optional): Arithmetik gegen den
  Hauptvertrag, Jahrestags-Konvention, Cross-Check gegen die Historie
  (``validate_scheiben``).
* Plausibilitaets-Baender (``--config``, optional): Sanity-Bänder aus der
  TOML gegen den Bestand (``sanity_check``); die Config selbst wird
  mitvalidiert.
* Ereignis-Ledger (``--ledger``): Semantik jeder Buchung — GeVo-Code und
  Betragsart aus dem Vokabular, endlicher Betrag, Generation des
  Stammsatzes, Vertragsjahr = vollendete Vertragsjahre am Datum,
  Journalzeile zu jedem Zustandswechsel, und ZEILENWEISE Bindung jeder
  ``ERH``-Buchung an genau eine Scheibe (``validate_ledger``; T18-01,
  T18-06). Vorher band nur die Jahressumme, und vertauschte
  Scheibenbetraege passierten mit null Befunden.
* Bewegungs-Identitaeten (``--ledger`` + ``--bis``, optional; ``--bis`` =
  Fortschreibungs-Horizont des Producer-Laufs): Anfang + Zugang - Abgang =
  Endbestand je Kalenderjahr, Track (bpfl/bfr) und Mass (Stueck/Summe) via
  ``kennzahlen.bewegungskonto``; enthaelt der Ledger Erhoehungen (ERH),
  ist ``--scheiben`` Pflicht (ohne Scheiben waeren die Bestandssummen
  systematisch zu niedrig und die Pruefung falsch-positiv).
* Laufmanifest (``--manifest``, optional): ``laufmanifest.json`` des
  Producer-Laufs (``bestand.manifest``). Damit ist ``--bis`` keine
  Behauptung des Aufrufers mehr, sondern muss der belegte Horizont sein,
  und jede uebergebene Tabelle sowie die Config muss bytegleich die vom
  Lauf geschriebene sein (T18-02). Optional, weil das Gate auch einzelne
  Tabellen ohne Lauf prueft (Basisbestand aus ``generate``); der
  Abschluss-Produzent verlangt das Manifest dagegen immer.

Was ``--bis`` NICHT ist (Systempruefung Befund F3, geprueft und widerlegt):
``--bis`` ist der Fortschreibungs-HORIZONT des Producer-Laufs, kein
Stichtag, zu dem der Bestand ausgewiesen wird. Vertragsbeginne NACH
``--bis`` sind deshalb kein Widerspruch, sondern der Normalfall — der
Basis-Erzeuger besiedelt das volle Verkaufsfenster jeder Generation in
EINEM Batch (``configs/bestand_klv.toml`` und ``configs/bestand_gesamt.toml``
tragen Beginne bis 2035-12, unabhaengig von ``--bis``), waehrend ``--bis``
nur bestimmt, wie weit der GeVo-Strom projiziert wurde. P-B1 darf daraus
also keine Invariante ``max(insurance_start) <= --bis`` machen: sie waere
gegen jeden Beispiel-Bestand verletzt (bei ``--bis 2020-01-01`` in 241
bzw. 494 Zeilen) und wuerde die Kohorte des Datenmodells fuer einen
Datenfehler erklaeren. Aus demselben Grund prueft die Bewegungs-Identitaet
nur vollstaendig simulierte Kalenderjahre. Die Stichtags-Sicht (welche
Vertraege zaehlen zu einem Datum?) ist Sache des Berichts
(``bestand.cli_report --stichtag``), nicht dieses Gates: P-B1 prueft den
Datei-Contract.

Blocking failures exit ``20`` (``Exit.FILE_CONTRACT``) with the error list
of the engines (repair happens data-side, not prose-side). Usage errors
exit ``2``. Writes the ``bestand_validate.gate.json`` ledger entry like the
other gates.

Run via::

    python -m rechner_pipeline.gates.bestand_validate \\
        --portfolio lauf/bestand_gesamt.parquet \\
        [--historie lauf/historie.parquet] [--scheiben lauf/scheiben.parquet] \\
        [--ledger lauf/ledger.parquet --bis 2035-01-01] \\
        [--manifest lauf/laufmanifest.json] \\
        [--config configs/bestand_klv.toml] [--diagnostics-dir diagnostics]

Knoten: klv, bu
"""

from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Die Pruefengine wohnt in der Bestandsschicht, damit auch der
# Abschluss-Produzent sie erreicht (Schichtenkarte verbietet
# bestand -> gates). Der Name bleibt hier im Namensraum des Gates: der
# Abnahmebericht ruft ihn als bestand_validate.pruefe_pb1_eingaenge.
from rechner_pipeline.bestand.manifest import (
    ManifestError,
    lies_manifest_bytes,
    manifest_aus_bytes,
    sha256_bytes,
)
from rechner_pipeline.bestand.vorbedingungen import pruefe_pb1_eingaenge
from rechner_pipeline.gates._common import (
    Exit,
    GateArgumentParser,
    GateCliContract,
    add_request_json_arg,
    begin_gate_ledger_attempt,
    build_result,
    finalize_gate_ledger,
    hash_files,
    log,
    parse_gate_args,
    run_command,
    utc_now,
)
from rechner_pipeline.gates._provenienz import systemstand

GATE = "P-B1.bestandspruefung"
GATE_VERSION = "2.1.0"
CLI_CONTRACT = GateCliContract(
    command="bestand_validate",
    gate=GATE,
    gate_version=GATE_VERSION,
)

#: Der Weg hinaus, wenn der Eingang von P-B1 fehlt: ein Gate darf nicht nur
#: melden, DASS etwas fehlt, es nennt das Kommando, das den Eingang
#: herstellt (Nicht-Verhandelbare "fail fast, aber mit Ausweg").
ERZEUGER_HINWEIS = {
    "code": "bestand_erzeugen",
    "hint": "Bestand erzeugen mit: python -m "
    "rechner_pipeline.bestand.cli_fortschreibung --config <config>.toml "
    "--bis <ISO-Datum> --out-dir <lauf>. Der Lauf schreibt "
    "<lauf>/bestand_gesamt.parquet (--portfolio), historie.parquet, "
    "ledger.parquet, scheiben.parquet und laufmanifest.json (--manifest); "
    "--bis ist derselbe Horizont, den dieses Gate erwartet — mit "
    "--manifest wird er gegen den belegten Horizont gehalten.",
}


def _build_parser() -> GateArgumentParser:
    parser = GateArgumentParser(
        gate_contract=CLI_CONTRACT,
        prog="python -m rechner_pipeline.gates.bestand_validate",
        description="Gate P-B1: Bestandsdaten-Tabellen gegen Schema und Invarianten pruefen.",
    )
    parser.add_argument("--portfolio", default=None, help="Bestand-Parquet (Pflicht).")
    parser.add_argument("--historie", default=None, help="Statushistorie-Parquet (optional).")
    parser.add_argument("--scheiben", default=None, help="Erhoehungsscheiben-Parquet (optional).")
    parser.add_argument(
        "--ledger", default=None,
        help="Ereignis-Ledger-Parquet (optional; mit --historie und --bis: "
        "Bewegungs-Identitaeten).",
    )
    parser.add_argument(
        "--bis", default=None,
        help="Fortschreibungs-Horizont (ISO-Datum, dasselbe wie beim "
        "fortschreiben-Lauf; Pflicht mit --ledger).",
    )
    parser.add_argument(
        "--config", dest="config", default=None,
        help="Bestand-Config (TOML) fuer die Plausibilitaets-Baender (optional).",
    )
    parser.add_argument(
        "--manifest", default=None,
        help="laufmanifest.json des fortschreiben-Laufs (optional): bindet "
        "--bis an den belegten Horizont und jede Tabelle an die vom Lauf "
        "geschriebenen Bytes.",
    )
    parser.add_argument("--repo-root", dest="repo_root", default=None)
    parser.add_argument(
        "--diagnostics-dir", dest="diagnostics_dir", default=None,
        help="Verzeichnis fuer den Gate-Ledger-Eintrag "
             "(Default: ./runs/diagnostics). In einem Migrationsfall "
             "ausdruecklich auf <fall>/abgeleitet/diagnostics setzen — "
             "dort sucht A-M4 den P-B1-Pflichtbeleg, und nur dort.",
    )
    add_request_json_arg(parser)
    return parser




def main(argv: Optional[List[str]] = None):
    started_at = utc_now()
    parser = _build_parser()
    args = parse_gate_args(parser, argv)

    diagnostics_dir = (
        Path(args.diagnostics_dir) if args.diagnostics_dir else Path.cwd() / "runs" / "diagnostics"
    )
    ledger_start_fehler = begin_gate_ledger_attempt(
        command="bestand_validate",
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

    def _usage(errors: List[dict], repair_hints: Optional[List[dict]] = None):
        return _finalize(build_result(
            command="bestand_validate",
            gate=GATE,
            gate_version=GATE_VERSION,
            exit_code=Exit.USAGE,
            errors=errors,
            repair_hints=repair_hints,
        ))

    if not args.portfolio:
        return _usage(
            [{"code": "missing_arg", "message": "--portfolio ist erforderlich"}],
            [ERZEUGER_HINWEIS],
        )
    bis = None
    if args.ledger and not (args.historie and args.bis):
        return _usage([{
            "code": "missing_arg",
            "message": "--ledger verlangt --historie und --bis (Horizont des "
            "fortschreiben-Laufs — nur vollstaendig simulierte Jahre sind "
            "identitaets-pruefbar)",
        }])
    if args.bis:
        if not args.ledger:
            return _usage([{
                "code": "missing_arg",
                "message": "--bis nur zusammen mit --ledger",
            }])
        try:
            bis = _dt.date.fromisoformat(args.bis)
        except ValueError as exc:
            return _usage([{"code": "bad_arg", "message": f"Ungueltiges --bis-Datum: {exc}"}])
    eingaben = {"portfolio": Path(args.portfolio)}
    for name in ("historie", "scheiben", "ledger", "config"):
        wert = getattr(args, name)
        if wert:
            eingaben[name] = Path(wert)
    fehlend = [str(p) for p in eingaben.values() if not p.is_file()]
    if fehlend:
        return _usage(
            [
                {"code": "missing_input", "message": f"Datei nicht gefunden: {p}"}
                for p in fehlend
            ],
            [ERZEUGER_HINWEIS],
        )

    manifest = None
    manifest_sha256 = None
    if args.manifest:
        # Einmal gelesen: gehasht und geparst werden dieselben Bytes.
        try:
            manifest_bytes = lies_manifest_bytes(Path(args.manifest))
            manifest = manifest_aus_bytes(manifest_bytes)
        except ManifestError as exc:
            return _usage([{"code": "bad_arg", "message": str(exc)}],
                          [ERZEUGER_HINWEIS])
        manifest_sha256 = sha256_bytes(manifest_bytes)
    paths = {name: str(p) for name, p in eingaben.items()}
    repo_root = Path(args.repo_root).resolve() if args.repo_root else None
    input_hashes = hash_files(list(eingaben.values()), base=repo_root, missing_ok=True)
    portfolio_hashes = hash_files(
        [eingaben["portfolio"]], base=repo_root, missing_ok=True
    )
    [(portfolio_input, portfolio_sha256)] = portfolio_hashes.items()
    eingangsrollen: Dict[str, str] = {}
    for rolle, pfad in eingaben.items():
        rollen_hash = hash_files([pfad], base=repo_root, missing_ok=True)
        [(hash_schluessel, _hash)] = rollen_hash.items()
        eingangsrollen[rolle] = hash_schluessel
    geprueft, errors, usage_errors = pruefe_pb1_eingaenge(
        eingaben, bis=bis, manifest=manifest)
    if usage_errors:
        return _usage(usage_errors)

    summary = {
        **geprueft,
        "all_passed": not errors,
        "portfolio_input": portfolio_input,
        "portfolio_sha256": portfolio_sha256,
        "eingangsrollen": eingangsrollen,
        "bis": args.bis,
        "manifest": (
            {"sha256": manifest_sha256, "horizont": manifest.get("horizont")}
            if manifest is not None else None
        ),
    }
    if repo_root is not None:
        summary["system"] = systemstand(repo_root)

    if not errors:
        log(f"bestand_validate: P-B1 PASSED ({geprueft})")
        return _finalize(build_result(
            command="bestand_validate",
            gate=GATE,
            gate_version=GATE_VERSION,
            exit_code=Exit.OK,
            paths=paths,
            summary=summary,
            input_hashes=input_hashes,
        ))

    log(f"bestand_validate: P-B1 FAILED mit {len(errors)} Verletzung(en)")
    return _finalize(build_result(
        command="bestand_validate",
        gate=GATE,
        gate_version=GATE_VERSION,
        exit_code=Exit.FILE_CONTRACT,
        paths=paths,
        summary=summary,
        input_hashes=input_hashes,
        errors=errors,
        repair_hints=[
            {
                "code": "bestand_contract",
                "hint": "Fehlerliste stammt aus den Schema-/Invarianten-Engines "
                "(models/bestand, qa/bestand); Daten bzw. Config korrigieren "
                "und das Gate erneut ausfuehren.",
            }
        ],
    ))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_command(main))
