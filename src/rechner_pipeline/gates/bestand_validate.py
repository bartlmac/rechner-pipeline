"""``bestand_validate`` toolbox command — gate B1 (Bestandsdaten-Contract).

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
* Bewegungs-Identitaeten (``--ledger`` + ``--bis``, optional; ``--bis`` =
  Fortschreibungs-Horizont des Producer-Laufs): Anfang + Zugang - Abgang =
  Endbestand je Kalenderjahr, Track (bpfl/bfr) und Mass (Stueck/Summe) via
  ``kennzahlen.bewegungskonto``; enthaelt der Ledger Erhoehungen (ERH),
  ist ``--scheiben`` Pflicht (ohne Scheiben waeren die Bestandssummen
  systematisch zu niedrig und die Pruefung falsch-positiv).

Was ``--bis`` NICHT ist (Systempruefung Befund F3, geprueft und widerlegt):
``--bis`` ist der Fortschreibungs-HORIZONT des Producer-Laufs, kein
Stichtag, zu dem der Bestand ausgewiesen wird. Vertragsbeginne NACH
``--bis`` sind deshalb kein Widerspruch, sondern der Normalfall — der
Basis-Erzeuger besiedelt das volle Verkaufsfenster jeder Generation in
EINEM Batch (``configs/bestand_klv.toml`` und ``configs/bestand_gesamt.toml``
tragen Beginne bis 2035-12, unabhaengig von ``--bis``), waehrend ``--bis``
nur bestimmt, wie weit der GeVo-Strom projiziert wurde. B1 darf daraus
also keine Invariante ``max(insurance_start) <= --bis`` machen: sie waere
gegen jeden Beispiel-Bestand verletzt (bei ``--bis 2020-01-01`` in 241
bzw. 494 Zeilen) und wuerde die Kohorte des Datenmodells fuer einen
Datenfehler erklaeren. Aus demselben Grund prueft die Bewegungs-Identitaet
nur vollstaendig simulierte Kalenderjahre. Die Stichtags-Sicht (welche
Vertraege zaehlen zu einem Datum?) ist Sache des Berichts
(``bestand.cli_report --stichtag``), nicht dieses Gates: B1 prueft den
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
        [--config configs/bestand_klv.toml] [--diagnostics-dir diagnostics]

Knoten: klv, bu
"""

from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from rechner_pipeline.bestand.config import load_config
from rechner_pipeline.bestand.parquet_io import read_portfolio
from rechner_pipeline.models.bestand import (
    LEDGER_NAMES,
    SCHEIBEN_NAMES,
    STATUS_HISTORIE_NAMES,
    STAMM_NAMES,
    validate_portfolio,
    validate_scheiben,
    validate_statushistorie,
)
from rechner_pipeline.qa.bestand import sanity_check
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

GATE = "B1.bestand-contract"
GATE_VERSION = "1.3.0"
CLI_CONTRACT = GateCliContract(
    command="bestand_validate",
    gate=GATE,
    gate_version=GATE_VERSION,
)

#: Der Weg hinaus, wenn der Eingang von B1 fehlt: ein Gate darf nicht nur
#: melden, DASS etwas fehlt, es nennt das Kommando, das den Eingang
#: herstellt (Nicht-Verhandelbare "fail fast, aber mit Ausweg").
ERZEUGER_HINWEIS = {
    "code": "bestand_erzeugen",
    "hint": "Bestand erzeugen mit: python -m "
    "rechner_pipeline.bestand.cli_fortschreibung --config <config>.toml "
    "--bis <ISO-Datum> --out-dir <lauf>. Der Lauf schreibt "
    "<lauf>/bestand_gesamt.parquet (--portfolio), historie.parquet, "
    "ledger.parquet und scheiben.parquet; --bis ist derselbe Horizont, "
    "den dieses Gate erwartet.",
}


def _build_parser() -> GateArgumentParser:
    parser = GateArgumentParser(
        gate_contract=CLI_CONTRACT,
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


def pruefe_b1_eingaenge(
    eingaben: Mapping[str, Path],
    *,
    bis: Optional[_dt.date] = None,
) -> Tuple[Dict[str, int], List[dict], List[dict]]:
    """B1-Engines rein lesend auf einer benannten Eingabenkonfiguration.

    Der CLI-Produzent und G-2 benutzen bewusst dieselbe Funktion. So ist ein
    frei editierbares, passend neu gehashtes B1-Ledger keine Selbstaussage:
    G-2 fuehrt Schema-, Invarianten-, Bewegungs- und optionale Sanity-Pruefung
    auf den aktuellen Bytes erneut aus.

    Rueckgabe: ``(geprueft, contract_fehler, usage_fehler)``.
    """
    erlaubt = {"portfolio", "historie", "scheiben", "ledger", "config"}
    rollen = set(eingaben)
    errors: List[dict] = []
    usage_errors: List[dict] = []
    if "portfolio" not in rollen:
        return {}, [{"code": "portfolio", "message": "Portfolio-Rolle fehlt"}], []
    if not rollen <= erlaubt:
        return {}, [{
            "code": "eingangsrollen",
            "message": f"Unbekannte B1-Eingangsrollen: {sorted(rollen - erlaubt)}",
        }], []

    tabellen: Dict[str, Any] = {}
    spaltenvertrag = {
        "portfolio": STAMM_NAMES,
        "historie": STATUS_HISTORIE_NAMES,
        "scheiben": SCHEIBEN_NAMES,
        "ledger": LEDGER_NAMES,
    }
    for rolle in ("portfolio", "historie", "scheiben", "ledger"):
        if rolle not in eingaben:
            continue
        try:
            tabellen[rolle] = read_portfolio(
                eingaben[rolle], expected_columns=spaltenvertrag[rolle]
            )
        except Exception as exc:  # noqa: BLE001 — Parquet-Backends variieren
            errors.append({
                "code": rolle,
                "message": f"{rolle}-Datei ist nicht als Bestand lesbar: {exc}",
            })

    portfolio = tabellen.get("portfolio")
    historie = tabellen.get("historie")
    scheiben = tabellen.get("scheiben")
    ledger = tabellen.get("ledger")
    geprueft: Dict[str, int] = {}
    if portfolio is not None:
        geprueft["portfolio_zeilen"] = int(len(portfolio))
        try:
            for meldung in validate_portfolio(portfolio):
                errors.append({"code": "portfolio", "message": meldung})
        except Exception as exc:  # noqa: BLE001 — malformed data blockiert
            errors.append({"code": "portfolio", "message": str(exc)})
    if portfolio is not None and historie is not None:
        geprueft["historie_zeilen"] = int(len(historie))
        try:
            for meldung in validate_statushistorie(portfolio, historie):
                errors.append({"code": "historie", "message": meldung})
        except Exception as exc:  # noqa: BLE001 — malformed data blockiert
            errors.append({"code": "historie", "message": str(exc)})
    if portfolio is not None and scheiben is not None:
        geprueft["scheiben_zeilen"] = int(len(scheiben))
        try:
            for meldung in validate_scheiben(
                portfolio, scheiben, historie=historie
            ):
                errors.append({"code": "scheiben", "message": meldung})
        except Exception as exc:  # noqa: BLE001 — malformed data blockiert
            errors.append({"code": "scheiben", "message": str(exc)})

    if ledger is not None and scheiben is None:
        try:
            hat_erhoehungen = bool((ledger["ereignis"] == "ERH").any())
        except Exception as exc:  # noqa: BLE001 — malformed data blockiert
            errors.append({"code": "ledger", "message": str(exc)})
            hat_erhoehungen = False
        if hat_erhoehungen:
            usage_errors.append({
                "code": "missing_arg",
                "message": "Ledger enthaelt dynamische Erhoehungen (ERH) — "
                "--scheiben ist erforderlich, sonst sind die Bestandssummen "
                "systematisch zu niedrig und die Bewegungs-Identitaet "
                "falsch-positiv verletzt",
            })

    if (
        portfolio is not None
        and ledger is not None
        and historie is not None
        and not errors
        and not usage_errors
    ):
        from rechner_pipeline.bestand.kennzahlen import (
            bewegungskonto,
            bu_bewegungskonto,
        )

        konto: List[dict] = []
        try:
            konto = bewegungskonto(
                portfolio, historie, ledger, scheiben, bis=bis
            )
            konto += bu_bewegungskonto(
                portfolio, historie, ledger, bis=bis
            )
        except Exception as exc:  # noqa: BLE001 — malformed inputs blockieren
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

    if "config" in eingaben and portfolio is not None:
        try:
            config = load_config(eingaben["config"])
        except (OSError, ValueError) as exc:
            errors.append({"code": "config", "message": str(exc)})
        else:
            try:
                for meldung in config.validate():
                    errors.append({"code": "config", "message": meldung})
                for meldung in sanity_check(portfolio, config.plausibilitaet):
                    errors.append({"code": "sanity", "message": meldung})
                geprueft["sanity_baender"] = len(config.plausibilitaet)
            except Exception as exc:  # noqa: BLE001 — malformed data blockiert
                errors.append({"code": "sanity", "message": str(exc)})
    return geprueft, errors, usage_errors


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
    geprueft, errors, usage_errors = pruefe_b1_eingaenge(eingaben, bis=bis)
    if usage_errors:
        return _usage(usage_errors)

    summary = {
        **geprueft,
        "all_passed": not errors,
        "portfolio_input": portfolio_input,
        "portfolio_sha256": portfolio_sha256,
        "eingangsrollen": eingangsrollen,
        "bis": args.bis,
    }
    if repo_root is not None:
        summary["system"] = systemstand(repo_root)

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
