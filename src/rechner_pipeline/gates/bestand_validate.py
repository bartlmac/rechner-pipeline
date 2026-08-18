"""``bestand_validate`` toolbox command — gate B1 (Bestandsdaten-Contract).

Validates the Bestandsdaten tables against their schemas and invariants
(engines: :mod:`rechner_pipeline.models.bestand`,
:func:`rechner_pipeline.qa.bestand.sanity_check`):

* Basisbestand/Gesamtbestand (``--portfolio``): Spalten-Contract, Enums,
  Zeilen-Invarianten, Datums-Konsistenz (``validate_portfolio``).
* Statushistorie (``--historie``, optional): fortlaufende status_id,
  terminale Status nur am Ende, Datumsgrenzen (``validate_statushistorie``).
* Erhoehungsscheiben (``--scheiben``, optional): Arithmetik gegen den
  Hauptvertrag, Jahrestags-Konvention, Cross-Check gegen die Historie
  (``validate_scheiben``).
* Plausibilitaets-Baender (``--config``, optional): Sanity-Bänder aus der
  TOML gegen den Bestand (``sanity_check``); die Config selbst wird
  mitvalidiert.
* Bewegungs-Identitaeten (``--ledger`` + ``--bis``, optional; ``--bis`` =
  Fortschreibungs-Horizont des Producer-Laufs): Anfang + Zugang - Abgang =
  Endbestand je Kalenderjahr, Track (bpfl/bfr) und Mass (Stueck/Summe) via
  ``kennzahlen.bewegungskonto``; enthaelt der Ledger Erhoehungen (ERH),
  ist ``--scheiben`` Pflicht (ohne Scheiben waeren die Bestandssummen
  systematisch zu niedrig und die Pruefung falsch-positiv).

Blocking failures exit ``20`` (``Exit.FILE_CONTRACT``) with the error list
of the engines (repair happens data-side, not prose-side). Usage errors
exit ``2``. Writes the ``bestand_validate.gate.json`` ledger entry like the
other gates.

Run via::

    python -m rechner_pipeline.gates.bestand_validate \\
        --portfolio lauf/bestand_gesamt.parquet \\
        [--historie lauf/historie.parquet] [--scheiben lauf/scheiben.parquet] \\
        [--ledger lauf/ledger.parquet --bis 2035-01-01] \\
        [--config configs/bestand_klv.toml] [--diagnostics-dir diagnostics]

Knoten: klv, bu
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional

from rechner_pipeline.bestand.config import load_config
from rechner_pipeline.bestand.parquet_io import read_portfolio
from rechner_pipeline.models.bestand import (
    validate_portfolio,
    validate_scheiben,
    validate_statushistorie,
)
from rechner_pipeline.qa.bestand import sanity_check
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

GATE = "B1.bestand-contract"
GATE_VERSION = "1.0.0"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.gates.bestand_validate",
        description="Gate B1: Bestandsdaten-Tabellen gegen Schema und Invarianten pruefen.",
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
    parser.add_argument("--repo-root", dest="repo_root", default=None)
    parser.add_argument(
        "--diagnostics-dir", dest="diagnostics_dir", default=None,
        help="Verzeichnis fuer den Gate-Ledger-Eintrag (Default: ./diagnostics).",
    )
    add_request_json_arg(parser)
    return parser


def main(argv: Optional[List[str]] = None):
    started_at = utc_now()
    parser = _build_parser()
    args = parser.parse_args(argv)
    request = read_request_json(args.request_json)
    args = merge_request_into_args(args, request)

    diagnostics_dir = (
        Path(args.diagnostics_dir) if args.diagnostics_dir else Path.cwd() / "runs" / "diagnostics"
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
        except Exception as exc:  # noqa: BLE001 — Ledger darf das Gate nie maskieren
            log(f"bestand_validate: gate-ledger write failed: {exc}")
        return result

    def _usage(errors: List[dict]):
        return _finalize(build_result(
            command="bestand_validate",
            gate=GATE,
            gate_version=GATE_VERSION,
            exit_code=Exit.USAGE,
            errors=errors,
        ))

    if not args.portfolio:
        return _usage([{"code": "missing_arg", "message": "--portfolio ist erforderlich"}])
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
            import datetime as _dt

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
        return _usage([
            {"code": "missing_input", "message": f"Datei nicht gefunden: {p}"}
            for p in fehlend
        ])

    paths = {name: str(p) for name, p in eingaben.items()}
    repo_root = Path(args.repo_root).resolve() if args.repo_root else None
    input_hashes = hash_files(list(eingaben.values()), base=repo_root, missing_ok=True)

    portfolio = read_portfolio(eingaben["portfolio"])
    historie = read_portfolio(eingaben["historie"]) if "historie" in eingaben else None
    scheiben = read_portfolio(eingaben["scheiben"]) if "scheiben" in eingaben else None
    ledger = read_portfolio(eingaben["ledger"]) if "ledger" in eingaben else None

    errors: List[dict] = []
    geprueft: Dict[str, int] = {"portfolio_zeilen": int(len(portfolio))}

    for meldung in validate_portfolio(portfolio):
        errors.append({"code": "portfolio", "message": meldung})
    if historie is not None:
        geprueft["historie_zeilen"] = int(len(historie))
        for meldung in validate_statushistorie(portfolio, historie):
            errors.append({"code": "historie", "message": meldung})
    if scheiben is not None:
        geprueft["scheiben_zeilen"] = int(len(scheiben))
        for meldung in validate_scheiben(portfolio, scheiben, historie=historie):
            errors.append({"code": "scheiben", "message": meldung})
    if (
        ledger is not None
        and scheiben is None
        and (ledger["ereignis"] == "ERH").any()
    ):
        return _usage([{
            "code": "missing_arg",
            "message": "Ledger enthaelt dynamische Erhoehungen (ERH) — "
            "--scheiben ist erforderlich, sonst sind die Bestandssummen "
            "systematisch zu niedrig und die Bewegungs-Identitaet "
            "falsch-positiv verletzt",
        }])
    if ledger is not None and historie is not None and not errors:
        # Bewegungs-Identitaeten (BaFin-Nachweisungs-Struktur): Anfang +
        # Zugang - Abgang = Endbestand je Jahr, Track und Mass — eine
        # Verletzung ist ein Engine-/Datenfehler.
        from rechner_pipeline.bestand.kennzahlen import (
            bewegungskonto,
            bu_bewegungskonto,
        )

        konto: List[dict] = []
        try:
            konto = bewegungskonto(portfolio, historie, ledger, scheiben, bis=bis)
            # Gemischte Bestaende fuehren zwei Nachweisungen (KLV mit
            # Versicherungssumme, BU mit Jahresrente); beide Identitaeten
            # sind harte Gate-Bedingungen.
            konto = konto + bu_bewegungskonto(portfolio, historie, ledger, bis=bis)
        except ValueError as exc:
            errors.append({"code": "ledger", "message": str(exc)})
        geprueft["bewegungsjahre"] = len(konto)
        for zeile in konto:
            for track, oks in zeile["identitaet"].items():
                for mass, ok in oks.items():
                    if not ok:
                        errors.append({
                            "code": "bewegung",
                            "message": (
                                f"Jahr {zeile['jahr']} {track}/{mass}: "
                                "Anfang + Zugang - Abgang != Endbestand"
                            ),
                        })
    if "config" in eingaben:
        try:
            config = load_config(eingaben["config"])
        except ValueError as exc:
            errors.append({"code": "config", "message": str(exc)})
        else:
            for meldung in config.validate():
                errors.append({"code": "config", "message": meldung})
            for meldung in sanity_check(portfolio, config.plausibilitaet):
                errors.append({"code": "sanity", "message": meldung})
            geprueft["sanity_baender"] = len(config.plausibilitaet)

    summary = {**geprueft, "all_passed": not errors}

    if not errors:
        log(f"bestand_validate: B1 PASSED ({geprueft})")
        return _finalize(build_result(
            command="bestand_validate",
            gate=GATE,
            gate_version=GATE_VERSION,
            exit_code=Exit.OK,
            paths=paths,
            summary=summary,
            input_hashes=input_hashes,
        ))

    log(f"bestand_validate: B1 FAILED mit {len(errors)} Verletzung(en)")
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
