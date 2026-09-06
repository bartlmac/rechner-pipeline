"""``abox_validate`` gate command — Gate P-Q3 (A-Box-Contract + Coverage).

Prueft die A-Box eines Fall-Arbeitsbereichs:

* Struktur- und Kreuz-Objekt-Contract (Pydantic-Validierung beim Laden
  plus :func:`rechner_pipeline.ontologie.abox.validate_abox`), inklusive
  Bindung jeder Quelle an das Eingang-Register des Falls (P1),
* Coverage gegen den PFLICHTUMFANG der T-Box je Parametrierungszelle
  (P6) — eine unvollstaendige A-Box blockiert Stage 2,
* offene Diskrepanzen (P2) — sie blockieren ebenfalls: die Aufloesung
  ist ein menschlicher Vorgang (Gate A-Q1), kein Durchwinken.

Blocking failures exit ``20`` (``Exit.FILE_CONTRACT``); Usage-Fehler
exit ``2``. Schreibt den ``abox_validate.gate.json``-Ledger-Eintrag wie
die uebrigen Gates; der Coverage-Bericht wird als eigenes Artefakt
neben die A-Box gelegt (deterministisch, diffbar).

Run via::

    python -m rechner_pipeline.gates.abox_validate --fall faelle/baldrian-klv-tg2015 \\
        [--diagnostics-dir DIR] [--repo-root .]

Knoten: klv
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rechner_pipeline.ontologie.abox import abox_pfad, lade, validate_abox
from rechner_pipeline.ontologie.coverage import coverage_bericht
from rechner_pipeline.gates._common import (
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

GATE = "P-Q3.fachliche-pruefung"
GATE_VERSION = "0.3.0"
CLI_CONTRACT = GateCliContract(
    command="abox_validate",
    gate=GATE,
    gate_version=GATE_VERSION,
    diagnostics_from="fall",
)

COVERAGE_DATEI = "coverage.json"


def _build_parser() -> GateArgumentParser:
    parser = GateArgumentParser(
        gate_contract=CLI_CONTRACT,
        prog="python -m rechner_pipeline.gates.abox_validate",
        description=(
            "Gate P-Q3: A-Box eines Falls gegen T-Box-Contract, "
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


def pruefe_belege(abox, fall: Path) -> Tuple[int, List[str]]:
    """Die Belege der aufgeloesten Diskrepanzen nachrechnen (P2).

    Gibt zurueck, wie viele Aufloesungen eine Rechnung mitfuehren, und
    was daran nicht mehr stimmt. Fehlt der Beleg ganz, ist das KEIN
    Fehler: Nicht jede Aufloesung hat eine Rechnung; manche entscheidet
    das Aktuariat aus dem Tarifwerk. Erzwungen waere der Beleg eine
    Einladung zur Attrappe.
    """
    geprueft = 0
    fehler: List[str] = []
    for d in abox.diskrepanzen:
        beleg = getattr(d.entscheidung, "beleg", None) if d.entscheidung else None
        if beleg is None:
            continue
        geprueft += 1
        pfad = fall / beleg.datei
        if not pfad.is_file():
            fehler.append(f"{d.id}: Beleg {beleg.datei} fehlt")
            continue
        ist = hashlib.sha256(pfad.read_bytes()).hexdigest()
        if ist != beleg.sha256:
            fehler.append(
                f"{d.id}: Beleg {beleg.datei} veraendert "
                f"({ist[:12]}… statt {beleg.sha256[:12]}…)")
    return geprueft, fehler


def main(argv: Optional[List[str]] = None):
    started_at = utc_now()
    parser = _build_parser()
    args = parse_gate_args(parser, argv)

    fall = Path(args.fall) if args.fall else None
    diagnostics_dir = (
        Path(args.diagnostics_dir) if args.diagnostics_dir
        else (fall / "abgeleitet" / "diagnostics" if fall
              else Path.cwd() / "runs" / "diagnostics")
    )
    ledger_start_fehler = begin_gate_ledger_attempt(
        command="abox_validate",
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

    # Stabile Rollenschluessel statt zufaelliger absoluter Temp-Pfade: P9
    # bindet P-Q3 genau an diese beiden Eingaben und darf den A-Box-SHA nicht
    # unter irgendeinem frei waehlbaren Hash-Key akzeptieren.
    input_hashes = {
        "eingang.json": hash_files([register_pfad], base=fall)["eingang.json"],
        "abgeleitet/abox/abox.json": hash_files(
            [abox_datei], base=fall
        )["abgeleitet/abox/abox.json"],
    }

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

    try:
        register = json.loads(register_pfad.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return _finalize(build_result(
            command="abox_validate",
            gate=GATE,
            gate_version=GATE_VERSION,
            exit_code=Exit.FILE_CONTRACT,
            errors=[{"code": "register",
                     "message": f"eingang.json unlesbar: {exc}"}],
            paths={"fall": str(fall), "abox": str(abox_datei)},
            input_hashes=input_hashes,
        ))
    for meldung in validate_abox(abox, register):
        errors.append({"code": "abox", "message": meldung})

    # Ketten-Pruefung: die A-Box muss aus ihren Fragmenten folgen
    # (Systempruefung Befund 45 — eine direkt editierte A-Box passierte
    # sonst alle Gates). "keine_fragmente" ist ein ausgewiesener
    # Zustand (synthetische A-Box), kein stilles Gruen.
    from rechner_pipeline.ontologie.kette import pruefe_kette

    ketten_befunde = pruefe_kette(fall)
    kette_status = "geprueft"
    if ketten_befunde == ["keine_fragmente"]:
        kette_status = "keine_fragmente"
    else:
        for meldung in ketten_befunde:
            errors.append({"code": "kette", "message": meldung})

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
                "menschlicher Vorgang (Gate A-Q1): " + ", ".join(offene)
            ),
        })

    # Die BELEGE der aufgeloesten Diskrepanzen nachrechnen (P2).
    #
    # Eine Begruendung in Prosa kann auf eine Rechnung VERWEISEN; sie kann
    # nicht sichern, dass es noch dieselbe ist. Wo eine Aufloesung ihren
    # Beleg strukturiert traegt, prueft das Gate ihn: Datei vorhanden,
    # Pruefsumme unveraendert. Sonst haenge der Beweis fuer die
    # Parametrierung an einer Datei, die niemand bindet.
    #
    # Fehlt der Beleg ganz, ist das KEIN Fehler: Nicht jede Aufloesung hat
    # eine Rechnung; manche entscheidet das Aktuariat aus dem Tarifwerk.
    # Gezaehlt wird sie trotzdem, damit sichtbar bleibt, wie viel der
    # Aufloesungen nachrechenbar belegt ist.
    belegt_geprueft, beleg_fehler = pruefe_belege(abox, fall)
    if beleg_fehler:
        errors.append({
            "code": "beleg_veraendert",
            "message": (
                "Belege aufgeloester Diskrepanzen stimmen nicht mehr: "
                + "; ".join(beleg_fehler[:10])
                + " — die Aufloesung stuetzt sich auf eine Rechnung, die es "
                  "so nicht mehr gibt. Beleg neu erzeugen und Diskrepanz neu "
                  "entscheiden."
            ),
        })

    # Deterministischer Rueck-Check LLM-gelesener Formel-Staffeln (P4).
    # Das Kalkulationsblatt ermittelt der Check aus der Vorverdichtung
    # selbst; welchen Zustand er erreicht hat, steht je Generation im
    # Summary. Entscheidend sind die Trennungen, die frueher alle zu
    # einer stillen Null zusammenfielen:
    #
    # * "gar keine Vorverdichtung" — der Check faellt VOLLSTAENDIG aus.
    #   Kein Fehler (es liegt nichts vor, was falsch sein koennte), aber
    #   eine Warnung mit dem extract-Kommando: ein Fall ohne
    #   Vorverdichtung darf nicht aussehen wie einer, in dem es nichts
    #   nachzurechnen gab,
    # * "Vorverdichtung da, aber nichts war nachrechenbar" — BEFUND,
    #   ebenfalls als Warnung sichtbar,
    # * Aussagen ohne Rechner-Beleg (nur Tarifmeldung) — ausserhalb der
    #   Zustaendigkeit des Checks: gezaehlt, nicht bemaengelt.
    from rechner_pipeline.quellen.formeln import pruefe_ratzu_staffeln

    formel_checks: Dict[str, object] = {}
    warnungen: List[dict] = []
    for gen in abox.generationen:
        pruefung = pruefe_ratzu_staffeln(fall, gen.id)
        eintrag: Dict[str, object] = {
            "status": pruefung.status,
            "geprueft": pruefung.geprueft,
        }
        if pruefung.blatt is not None:
            eintrag["blatt"] = pruefung.blatt
        if pruefung.ausserhalb:
            eintrag["ausserhalb"] = pruefung.ausserhalb
        if pruefung.befunde:
            eintrag["befunde"] = list(pruefung.befunde)
        if pruefung.hinweise:
            eintrag["hinweise"] = list(pruefung.hinweise)
        formel_checks[gen.id] = eintrag
        for meldung in pruefung.fehler:
            errors.append({"code": "formel_check", "message": meldung})
        for meldung in pruefung.befunde:
            warnungen.append({
                "code": "formel_check_ausgefallen",
                "message": (
                    "Rueck-Check der Formel-Staffeln nicht durchgefuehrt, "
                    f"obwohl die Vorverdichtung vorliegt: {meldung}"
                ),
            })
        for meldung in pruefung.hinweise:
            warnungen.append({
                "code": "formel_check_ohne_vorverdichtung",
                "message": (
                    "Rueck-Check der Formel-Staffeln mangels "
                    f"Vorverdichtung nicht durchgefuehrt: {meldung}"
                ),
            })

    summary: Dict[str, object] = {
        "kette": kette_status,
        "formel_checks": formel_checks,
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
        # Wie viele Aufloesungen ihre Rechnung nachrechenbar mitfuehren.
        # Der Rest stuetzt sich allein auf seine Begruendung — kein
        # Fehler, aber ein Unterschied, den ein Leser kennen sollte.
        "diskrepanzen_mit_beleg": belegt_geprueft,
        # Vorlaeufige (Agenten-)Aufloesungen tragen Stage 2/3, aber kein
        # menschliches Gate: hier sichtbar, geblockt wird im P9-Snapshot.
        "entscheidungen_vorlaeufig": sorted(
            d.id for d in abox.diskrepanzen
            if d.entscheidung is not None and d.entscheidung.vorlaeufig
        ),
        "vollstaendig": bericht["vollstaendig"],
    }
    return _finalize(build_result(
        command="abox_validate",
        gate=GATE,
        gate_version=GATE_VERSION,
        exit_code=Exit.FILE_CONTRACT if errors else Exit.OK,
        errors=errors,
        warnings=warnungen,
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
