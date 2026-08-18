"""``generation_golden`` gate command — Gate O3 (Generations-Golden-Master).

DER Abnahme-Test einer migrierten Tarifgeneration: der stabile Kern,
parametriert ueber die Tarif-Spez des Falls (Projektion der A-Box),
muss die Erwartungswerte reproduzieren, die deterministisch aus dem
QUELL-Rechner extrahiert wurden — Skalare (Bxt, BJB, BZB, Pxt) und die
komplette Verlaufswerte-Tabelle, verglichen mit der bestehenden
Golden-Master-Engine (Rundung auf 4 Nachkommastellen, positionsweise
Zeilen, Namens-Matching).

Der Beispiel-Modellpunkt (x, n, t, VS, zw, Sex, Status, Tarifart) wird
deterministisch aus dem Names-Manager der Vorverdichtung gelesen; die
Spez-Zelle waehlt sich ueber (tarifart, status). Erwartungs-Skalare,
die keine Rechenergebnisse sind (Zins, Tafel), werden gegen die Spez
selbst geprueft; nicht zuordenbare Erwartungsreste werden AUSGEWIESEN,
nie still uebersprungen (P6).

Blocking failures exit ``30`` (``Exit.GOLDEN_MASTER``); Usage exit ``2``.

Run via::

    python -m rechner_pipeline.gates.generation_golden \\
        --fall faelle/baldrian-klv-tg2015 --generation klv/tg2015 [--repo-root .]

Knoten: klv
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

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
from rechner_pipeline.qa.golden_master import ROUND_DECIMALS, compare, load_expected

GATE = "O3.generation-golden-master"
GATE_VERSION = "0.1.0"

#: Skalare Rechenergebnisse: Erwartungsname -> Kern-Methode.
SKALAR_CONTRACT = ("Bxt", "BJB", "BZB", "Pxt")

#: Erwartungs-Skalare, die Parametrierung sind (gegen die Spez geprueft).
#: "Tafel" nennt die BASIS (ohne Unisex-Suffix) — die Pruefung beruecksichtigt
#: die Ableitungsregel der Spez.
PARAMETER_SKALARE = {"Zins": "zins", "Tafel": "tafel"}


def _lese_names(names_csv: Path) -> Dict[str, str]:
    namen: Dict[str, str] = {}
    with names_csv.open(encoding="utf-8") as f:
        for zeile in csv.reader(f, delimiter=";"):
            if len(zeile) >= 7 and zeile[0] and zeile[0] != "Name":
                namen[zeile[0]] = zeile[6]
    return namen


def _modellpunkt_eingaben(namen: Dict[str, str]) -> Dict[str, Any]:
    pflicht = ("x", "n", "t", "VS", "zw", "Sex")
    fehlend = [p for p in pflicht if p not in namen or namen[p] == ""]
    if fehlend:
        raise ValueError(
            f"Names-Manager ohne Modellpunkt-Eingaben {fehlend} — der "
            "Beispiel-Modellpunkt ist nicht ableitbar"
        )
    def _zahl(name: str, wandler) -> Any:
        try:
            return wandler(float(namen[name]))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Names-Manager: Eingabe {name}={namen[name]!r} ist nicht "
                f"numerisch ({exc})"
            ) from exc

    return {
        "x": _zahl("x", int),
        "n": _zahl("n", int),
        "t": _zahl("t", int),
        "sum_insured": _zahl("VS", float),
        "zw": _zahl("zw", int),
        "sex_roh": namen["Sex"],
        "status": namen.get("Status", ""),
        "tarifart": namen.get("Tarifart", ""),
    }


def _waehle_zelle(spez, status: str, tarifart: str):
    gesucht = {}
    if status:
        gesucht["status"] = status.strip().lower()
    if tarifart:
        gesucht["tarifart"] = tarifart.strip().lower()
    treffer = [z for z in spez.zellen if z.auspraegungen == gesucht]
    if not treffer:
        raise ValueError(
            f"keine Spez-Zelle fuer Auspraegungen {gesucht!r} "
            f"(vorhanden: {[z.auspraegungen for z in spez.zellen]})"
        )
    return treffer[0]


def main(argv: Optional[List[str]] = None):
    started_at = utc_now()
    parser = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.gates.generation_golden",
        description=(
            "Gate O3: Kern (parametriert ueber die Tarif-Spez) gegen die "
            "aus dem Quell-Rechner extrahierten Erwartungswerte."
        ),
    )
    parser.add_argument("--fall", default=None)
    parser.add_argument("--generation", default=None, help="z. B. klv/tg2015")
    parser.add_argument("--repo-root", dest="repo_root", default=None)
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
            log(f"generation_golden: gate-ledger write failed: {exc}")
        return result

    def _usage(message: str):
        return _finalize(build_result(
            command="generation_golden", gate=GATE, gate_version=GATE_VERSION,
            exit_code=Exit.USAGE,
            errors=[{"code": "usage", "message": message}],
        ))

    if fall is None or not args.generation:
        return _usage("--fall und --generation sind erforderlich")
    gen_name = args.generation.rsplit("/", 1)[-1].upper()
    vorverdichtung = fall / "abgeleitet" / "vorverdichtung" / f"xlsm-{gen_name}"
    names_csv = vorverdichtung / "names_manager.csv"
    from rechner_pipeline.spez.validierung import spez_pfad

    spez_datei = spez_pfad(fall, args.generation)
    fehlend = [str(p) for p in (names_csv, spez_datei) if not p.is_file()]
    if fehlend:
        return _usage(f"Datei nicht gefunden: {'; '.join(fehlend)}")

    from rechner_pipeline.spez.validierung import lade_spez

    def _contract_fehler(code: str, message: str):
        return _finalize(build_result(
            command="generation_golden", gate=GATE, gate_version=GATE_VERSION,
            exit_code=Exit.GOLDEN_MASTER,
            errors=[{"code": code, "message": message}],
            paths={"fall": str(fall), "spez": str(spez_datei)},
        ))

    try:
        spez = lade_spez(fall, args.generation)
    except Exception as exc:  # Schema-Bruch der Spez ist ein Gate-Befund
        return _contract_fehler("spez", f"Spez unlesbar: {exc}")

    # Die Spez ist Projektion der A-Box — ohne diese Pruefung koennte eine
    # editierte Spez eine eigene Wahrheit in den Golden Master tragen.
    from rechner_pipeline.ontologie.abox import abox_pfad, lade as lade_abox

    if abox_pfad(fall).is_file():
        try:
            abox = lade_abox(fall)
        except Exception as exc:
            return _contract_fehler("abox", f"A-Box unlesbar: {exc}")
        from rechner_pipeline.spez.validierung import validate_spez

        spez_fehler = validate_spez(spez, abox)
        if spez_fehler:
            return _contract_fehler(
                "spez_projektion",
                "Spez ist keine gueltige Projektion der A-Box: "
                + "; ".join(spez_fehler[:5]),
            )
    else:
        return _contract_fehler(
            "abox", f"A-Box fehlt ({abox_pfad(fall)}) — ohne A-Box ist die "
            "Spez nicht als Projektion pruefbar",
        )

    namen = _lese_names(names_csv)
    try:
        eingaben = _modellpunkt_eingaben(namen)
        zelle = _waehle_zelle(spez, eingaben["status"], eingaben["tarifart"])
    except ValueError as exc:
        return _usage(str(exc))

    from rechner_pipeline.kern import ModelPoint, Rechenkern

    mp_felder: Dict[str, Any] = dict(zelle.model_point)
    # 21: unbekannte Spez-Felder sind ein Contract-Befund, kein Crash.
    import dataclasses

    bekannte_mp_felder = {f.name for f in dataclasses.fields(ModelPoint)}
    fest = {"x", "sex", "n", "t", "sum_insured", "zw"}
    unbekannt = sorted(set(mp_felder) - (bekannte_mp_felder - fest))
    if unbekannt:
        return _contract_fehler(
            "model_point",
            f"Spez-Zelle traegt Felder ausserhalb des ModelPoint-Contracts "
            f"bzw. Kollisionen mit Vertragsfeldern: {unbekannt}",
        )
    sex = eingaben["sex_roh"]
    if sex.upper() not in ("M", "F"):
        # Unisex-Kennung (z. B. U70): die Tafel der Spez-Zelle ist bereits
        # die abgeleitete Mischtafel (exakter Name gewinnt in der
        # Kern-Aufloesung) — das Geschlecht ist fuer die Sterblichkeit
        # dann bedeutungslos. Kanonisierung VBA-treu: nicht-"M" -> "F".
        sex = "F"
    mp = ModelPoint(
        x=eingaben["x"], sex=sex, n=eingaben["n"], t=eingaben["t"],
        sum_insured=eingaben["sum_insured"], zw=eingaben["zw"],
        **{k: v for k, v in mp_felder.items()},
    )
    try:
        kern = Rechenkern(mp)
        berechnete_skalare = {
            "Bxt": kern.gross_premium_rate(),
            "BJB": kern.gross_annual_premium(),
            "BZB": kern.gross_payable_premium(),
            "Pxt": kern.net_premium_rate(),
        }
    except Exception as exc:  # Kern-Fehler ist ein GM-Befund MIT Ledger
        return _contract_fehler("kern", f"Kern-Rechnung scheitert: {exc}")

    expected = load_expected(vorverdichtung)
    erwartete_skalare = expected["scalars"].get("Kalkulation", {})
    # Der GM-Loader floatet alle Skalare (Strings -> None); fuer die
    # PARAMETER-Pruefungen (Tafel!) brauchen wir die Rohwerte.
    roh_skalare: Dict[str, Any] = {}
    roh_pfad = vorverdichtung / "Kalkulation_scalar.json"
    if roh_pfad.is_file():
        roh_skalare = json.loads(roh_pfad.read_text(encoding="utf-8"))
    # Erwartungs-Skalare dreiteilen: Rechenergebnis / Parametrierung /
    # nicht zuordenbar (AUSGEWIESEN, nie still verworfen).
    parameter_pruefungen: List[dict] = []
    uebersprungen: List[str] = []
    gefilterte_erwartung: Dict[str, Any] = {}
    for name, wert in erwartete_skalare.items():
        if name in SKALAR_CONTRACT:
            gefilterte_erwartung[name] = wert
        elif name in PARAMETER_SKALARE:
            wert = roh_skalare.get(name, wert)
            if wert is None:
                uebersprungen.append(name)
                continue
            feld = PARAMETER_SKALARE[name]
            soll = zelle.model_point.get(feld)
            if feld == "tafel":
                # Erwartung nennt die BASIS; die Spez traegt den finalen
                # Namen (Basis + ggf. Unisex-Ableitung).
                erwartet_final = (
                    f"{wert}_{spez.unisex}" if spez.unisex else str(wert)
                )
                ok = soll == erwartet_final
            else:
                ok = (soll is not None
                      and round(float(soll), ROUND_DECIMALS)
                      == round(float(wert), ROUND_DECIMALS))
            parameter_pruefungen.append({
                "name": name, "feld": feld,
                "erwartet": wert, "spez": soll, "ok": ok,
            })
        else:
            uebersprungen.append(name)

    zeilen_erwartet = expected["tables"].get("Kalkulation")
    anzahl_zeilen = len(zeilen_erwartet[1]) if zeilen_erwartet else 0
    if anzahl_zeilen == 0:
        return _contract_fehler(
            "coverage",
            "keine Verlaufswerte-Erwartung in der Vorverdichtung — ein "
            "Skalar-only-Vergleich waere kein Golden Master",
        )
    try:
        berechnete_tabelle = [
            kern.verlaufszeile(k).als_blattzeile() for k in range(anzahl_zeilen)
        ]
    except Exception as exc:
        return _contract_fehler("kern", f"Verlaufswerte scheitern: {exc}")

    report = compare(
        {"scalars": {"Kalkulation": gefilterte_erwartung},
         "tables": {"Kalkulation": zeilen_erwartet} if zeilen_erwartet else {}},
        {"scalars": {"Kalkulation": berechnete_skalare},
         "tables": {"Kalkulation": berechnete_tabelle}},
    )

    errors: List[dict] = []
    # deviations traegt Skalar- UND Tabellen-Abweichungen — eine zweite
    # Schleife ueber scalar_rows wuerde doppelt zaehlen.
    for abweichung in report.deviations:
        errors.append({"code": "golden_master", "message": abweichung})
    for spalte in report.unmatched_columns:
        errors.append({
            "code": "golden_master",
            "message": f"erwartete Spalte nicht zuordenbar: {spalte}",
        })
    for pruefung in parameter_pruefungen:
        if not pruefung["ok"]:
            errors.append({
                "code": "parameter",
                "message": (
                    f"{pruefung['name']}: Rechner-Erwartung "
                    f"{pruefung['erwartet']} != Spez {pruefung['spez']}"
                ),
            })
    if not report.compared_anything:
        errors.append({
            "code": "coverage",
            "message": "Null-Vergleich — nichts verglichen ist nicht bestanden",
        })

    andere_zellen = sorted(
        z.knoten for z in spez.zellen if z.knoten != zelle.knoten
    )
    summary = {
        "generation": args.generation,
        "zelle": zelle.knoten,
        # Ehrlichkeit der Abdeckung: der Quell-Rechner liefert EINEN
        # Beispiel-Modellpunkt; die uebrigen Zellen sind NICHT
        # GM-verglichen und stehen hier ausdruecklich.
        "zellen_gesamt": len(spez.zellen),
        "zellen_ohne_erwartungswerte": andere_zellen,
        "modellpunkt": {k: eingaben[k] for k in
                        ("x", "n", "t", "sum_insured", "zw")}
        | {"sex": eingaben["sex_roh"], "status": eingaben["status"],
           "tarifart": eingaben["tarifart"], "tafel": mp.tafel},
        "skalare_verglichen": len(gefilterte_erwartung),
        "parameter_geprueft": [p["name"] for p in parameter_pruefungen],
        "tabellen_zeilen": anzahl_zeilen,
        "werte_verglichen": report.scalars_tested + report.table_cells_tested,
        "erwartung_uebersprungen": sorted(uebersprungen),
        "abweichungen": len(errors),
    }
    return _finalize(build_result(
        command="generation_golden", gate=GATE, gate_version=GATE_VERSION,
        exit_code=Exit.GOLDEN_MASTER if errors else Exit.OK,
        errors=errors,
        paths={"fall": str(fall), "spez": str(spez_datei),
               "vorverdichtung": str(vorverdichtung)},
        summary=summary,
        input_hashes=hash_files(
            [
                names_csv,
                spez_datei,
                vorverdichtung / "Kalkulation_scalar.json",
                vorverdichtung / "Kalkulation_table_values.csv",
                Path(__file__).resolve().parent.parent / "kern" / "tafeln.xml",
            ],
            base=Path(args.repo_root).resolve() if args.repo_root else None,
            missing_ok=True,
        ),
    ))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_command(main))
