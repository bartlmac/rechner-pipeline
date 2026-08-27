"""``aktuartest`` toolbox command — Vorlage fuer das menschliche Gate G-A.

Rendert aus dem Ergebnis des aktuariellen Tests (``qa.aktuarieller_test``,
als JSON persistiert) die Entscheidungsvorlage fuer den Verantwortlichen
Aktuar und prueft dabei den Ergebnis-Vertrag von innen nach aussen neu:
Einzelurteile gegen die Toleranzen, Zaehler, Stichproben-Vollstaendigkeit
und die Verteilungsgroessen werden nachgerechnet — eine gruene
Zusammenfassung ueber einem roten Einzelvergleich ist damit auch auf dem
Bibliothekspfad unmoeglich. Die Werte selbst rechnet ausschliesslich die
Engine; der Zusammenbau der Pruefauftraege ist Sache des Falls.

Die Transportsicherung (Datei-Hashes, gelieferte Kontrollsummen) wird im
Bericht GETRENNT ausgewiesen und ist nie Teil des fachlichen Urteils
(ADR-010). Der Bericht ist deterministisch: gleiche Eingaben ergeben
byte-identisches HTML, keine Zeitstempel.

Exit-Codes: 0 = Vorlage vollstaendig und Test bestanden; 30 = Test nicht
bestanden (Wertabweichung oder Stichprobe nicht abgearbeitet); 20 =
Ergebnis-Datei verletzt den Vertrag; 2 = Bedienfehler.

Run via::

    python -m rechner_pipeline.gates.aktuartest \\
        --fall faelle/<fall> --titel "Aktuarieller Test <Fall>" \\
        [--test <pfad>.json] [--bericht <pfad>.html]

Knoten: klv
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from rechner_pipeline.gates._common import (
    Exit,
    GATE_LEDGER_SUFFIX,
    GateCliContract,
    GateArgumentParser,
    add_request_json_arg,
    begin_gate_ledger_attempt,
    build_result,
    finalize_gate_ledger,
    hash_files,
    parse_gate_args,
    run_command,
    utc_now,
)
from rechner_pipeline.qa.abzugsabgleich import ABS_TOL, REL_TOL
from rechner_pipeline.qa.aktuarieller_test import PERZENTILE, verteilung

COMMAND = "aktuartest"
#: Bewusst "GA-vorlage", nicht "GA": Das Kommando liefert die Vorlage;
#: die aktuarielle ABNAHME ist der menschliche P9-Entscheid am Gate G-A.
GATE = "GA-vorlage.aktuarieller-test"
GATE_VERSION = "1.0.0"
CLI_CONTRACT = GateCliContract(
    command=COMMAND,
    gate=GATE,
    gate_version=GATE_VERSION,
    diagnostics_from="fall",
)

_ERGEBNIS_FELDER = {
    "stichprobe", "anzahl", "bestanden", "fehlgeschlagen",
    "mengenbefunde", "stichprobe_vollstaendig", "verteilung", "gruppen",
    "vertraege", "test_bestanden",
}
_STICHPROBEN_FELDER = {
    "profil", "parameter", "umfang", "grundgesamtheit", "vollerhebung",
    "police_ids",
}
_VERTRAGS_FELDER = {
    "police_id", "historientyp", "monate_ta", "bestanden", "pruefungen",
    "befunde",
}

_STIL = """
body { font-family: sans-serif; margin: 2em; color: #222; }
h1 { border-bottom: 2px solid #444; padding-bottom: 0.2em; }
table { border-collapse: collapse; margin: 1em 0; }
th, td { border: 1px solid #999; padding: 0.3em 0.7em; text-align: left; }
th { background: #eee; }
.gruen { color: #060; font-weight: bold; }
.rot { color: #a00; font-weight: bold; }
.hinweis { background: #ffd; border: 1px solid #cc9; padding: 0.6em; }
td.zahl { text-align: right; }
"""


def _e(text: Any) -> str:
    return (
        str(text)
        .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _ok(ist: float, soll: float) -> bool:
    return math.isclose(ist, soll, rel_tol=REL_TOL, abs_tol=ABS_TOL)


def test_fehler(test: Any) -> List[str]:
    """Ergebnis-Vertrag von innen nach aussen neu ableiten.

    Rueckgabe: Befundliste (leer = konsistent). Geprueft wird alles, was
    sich ohne die Modellpunkte nachrechnen laesst: Einzel-Urteile gegen
    die Toleranzen, Residuen, Zaehler, Mengenabgleich gegen die
    Stichprobe und saemtliche Verteilungsgroessen.
    """
    if not isinstance(test, dict):
        return ["Ergebnis ist kein Objekt"]
    fehler: List[str] = []
    fehlend = sorted(_ERGEBNIS_FELDER - set(test))
    if fehlend:
        return [f"Pflichtfelder fehlen: {fehlend}"]

    stichprobe = test["stichprobe"]
    if not isinstance(stichprobe, dict) or (
        _STICHPROBEN_FELDER - set(stichprobe)
    ):
        fehler.append("stichprobe: Beleg-Felder unvollstaendig")
        return fehler
    if stichprobe["umfang"] != len(stichprobe["police_ids"]):
        fehler.append("stichprobe: umfang deckt police_ids nicht")
    if len(set(stichprobe["police_ids"])) != len(stichprobe["police_ids"]):
        fehler.append(
            "stichprobe: doppelte police_ids — die Abdeckungsbehauptung "
            "waere aufgeblasen"
        )
    if stichprobe["umfang"] > stichprobe["grundgesamtheit"]:
        fehler.append("stichprobe: umfang uebersteigt die Grundgesamtheit")
    if stichprobe["vollerhebung"] != (
        stichprobe["umfang"] == stichprobe["grundgesamtheit"]
    ):
        fehler.append("stichprobe: vollerhebung widerspricht den Zahlen")

    vertraege = test["vertraege"]
    ids = [v.get("police_id") for v in vertraege]
    if len(ids) != len(set(ids)):
        fehler.append("vertraege: doppelte police_id")
    alle_residuen: List[float] = []
    fehlgeschlagen = 0
    feld_fehler = False
    for v in vertraege:
        v_fehlend = sorted(_VERTRAGS_FELDER - set(v))
        if v_fehlend:
            fehler.append(f"vertrag {v.get('police_id')}: {v_fehlend} fehlt")
            feld_fehler = True
            continue
        alle_ok = bool(v["pruefungen"])
        for p in v["pruefungen"]:
            residuum = p["system"] - p["erwartet"]
            if p["residuum"] != residuum:
                fehler.append(
                    f"police {v['police_id']} {p['groesse']}: residuum "
                    "ist nicht system - erwartet"
                )
            soll_ok = _ok(p["system"], p["erwartet"])
            if bool(p["ok"]) != soll_ok:
                fehler.append(
                    f"police {v['police_id']} {p['groesse']}: ok-Urteil "
                    "widerspricht den Toleranzen"
                )
            alle_ok = alle_ok and soll_ok
            alle_residuen.append(residuum)
        if bool(v["bestanden"]) != (alle_ok and not v["befunde"]):
            fehler.append(
                f"police {v['police_id']}: bestanden widerspricht den "
                "Einzelurteilen"
            )
        if not v["bestanden"]:
            fehlgeschlagen += 1

    if feld_fehler:
        # Ohne vollstaendige Vertragszeilen sind die nachgelagerten
        # Aggregate nicht ableitbar — die Feld-Befunde stehen fuer sich.
        return fehler
    if test["anzahl"] != len(vertraege):
        fehler.append("anzahl deckt vertraege nicht")
    if test["fehlgeschlagen"] != fehlgeschlagen:
        fehler.append("fehlgeschlagen-Zaehler widerspricht den Urteilen")
    if test["bestanden"] != len(vertraege) - fehlgeschlagen:
        fehler.append("bestanden-Zaehler widerspricht den Urteilen")

    gezogen = set(stichprobe["police_ids"])
    geliefert = set(ids)
    soll_vollstaendig = gezogen == geliefert
    if bool(test["stichprobe_vollstaendig"]) != soll_vollstaendig:
        fehler.append(
            "stichprobe_vollstaendig widerspricht dem Mengenabgleich"
        )
    if bool(test["stichprobe_vollstaendig"]) != (not test["mengenbefunde"]):
        fehler.append("mengenbefunde widersprechen stichprobe_vollstaendig")

    if test["verteilung"] != verteilung(alle_residuen):
        fehler.append("verteilung ist nicht die Nachrechnung der Residuen")
    for typ, gruppe in sorted(test["gruppen"].items()):
        im_typ = [v for v in vertraege if v.get("historientyp") == typ]
        residuen = [
            p["system"] - p["erwartet"]
            for v in im_typ for p in v.get("pruefungen", [])
        ]
        soll = {
            "anzahl": len(im_typ),
            "bestanden": sum(1 for v in im_typ if v.get("bestanden")),
            **verteilung(residuen),
        }
        if gruppe != soll:
            fehler.append(f"gruppe {typ}: Aggregat ist nicht nachgerechnet")
    if sorted(test["gruppen"]) != sorted(
        {v.get("historientyp") for v in vertraege}
    ):
        fehler.append("gruppen decken die Historientypen nicht")

    soll_bestanden = bool(test["stichprobe_vollstaendig"]) and (
        fehlgeschlagen == 0
    )
    if bool(test["test_bestanden"]) != soll_bestanden:
        fehler.append("test_bestanden widerspricht der Neuableitung")
    return fehler


def baue_bericht(*, titel: str, test: Dict[str, Any]) -> str:
    """Entscheidungsvorlage fuer G-A — deterministisch, byte-identisch.

    Nur aus einem intern konsistenten Ergebnis (``test_fehler`` leer);
    sonst ``ValueError`` — derselbe fail-fast Contract wie im Kommando.
    """
    fehler = test_fehler(test)
    if fehler:
        raise ValueError(
            "Testergebnis verletzt den Aktuartest-Vertrag: "
            + "; ".join(fehler)
        )
    s = test["stichprobe"]
    teile: List[str] = [
        "<!DOCTYPE html>", "<html lang='de'><head><meta charset='utf-8'>",
        f"<title>{_e(titel)}</title><style>{_STIL}</style></head><body>",
        f"<h1>{_e(titel)}</h1>",
        "<p>Aktuarieller Test: Vergleich je Vertrag am EIGENEN "
        "Verankerungszeitpunkt t_a — am Rechenpunkt, ohne Interpolation, "
        "ohne Summation der Vergleichsgr&ouml;&szlig;en (ADR-010).</p>",
    ]
    if test["test_bestanden"]:
        teile.append(
            f"<p class='gruen'>AKTUARIELLER TEST BESTANDEN "
            f"({test['bestanden']:.0f} von {test['anzahl']:.0f} "
            "Verträgen, Stichprobe vollständig abgearbeitet).</p>"
        )
    else:
        gruende: List[str] = []
        if test["fehlgeschlagen"]:
            gruende.append(
                f"{test['fehlgeschlagen']:.0f} von {test['anzahl']:.0f} "
                "Verträgen FEHLGESCHLAGEN"
            )
        if not test["stichprobe_vollstaendig"]:
            gruende.append("Stichprobe nicht vollständig abgearbeitet")
        teile.append(
            "<p class='rot'>AKTUARIELLER TEST NICHT BESTANDEN — "
            + ", ".join(gruende) + ".</p>"
        )
    teile.append(
        "<p class='hinweis'>Maschinelle Prüfaussage des deterministischen "
        "aktuariellen Tests. Die AKTUARIELLE ABNAHME ist eine menschliche "
        "Entscheidung (Gate G-A, Verantwortlicher Aktuar) auf Grundlage "
        "dieses Berichts.</p>"
    )

    teile.append("<h2>Stichprobe (Beleg)</h2>")
    parameter = ", ".join(
        f"{k}={v}" for k, v in sorted(s["parameter"].items())
    ) or "keine"
    teile.append(
        "<table><tr><th>Profil</th><th>Parameter</th><th>Umfang</th>"
        "<th>Grundgesamtheit</th><th>Vollerhebung</th></tr>"
        f"<tr><td>{_e(s['profil'])}</td><td>{_e(parameter)}</td>"
        f"<td class='zahl'>{s['umfang']:d}</td>"
        f"<td class='zahl'>{s['grundgesamtheit']:d}</td>"
        f"<td>{'ja' if s['vollerhebung'] else 'nein'}</td></tr></table>"
        "<p>Die vollständige Police-Liste der Ziehung steht im "
        "Test-Ergebnis (JSON) und gehört zum Beleg.</p>"
    )
    if test["mengenbefunde"]:
        teile.append("<table><tr><th>Befund der Stichprobe</th></tr>")
        teile.extend(
            f"<tr><td class='rot'>{_e(b)}</td></tr>"
            for b in test["mengenbefunde"]
        )
        teile.append("</table>")
    else:
        teile.append(
            "<p>Die Stichprobe wurde vollständig abgearbeitet. Die "
            "Nichtprüfung der Nicht-Stichprobe ist kein Befund, sondern "
            "die Definition des Tests.</p>"
        )

    def _verteilungs_zellen(v: Dict[str, Any]) -> str:
        if not v.get("anzahl_werte"):
            return "<td class='zahl'>0</td>" + "<td>—</td>" * (
                2 + len(PERZENTILE)
            )
        zellen = [f"<td class='zahl'>{v['anzahl_werte']:d}</td>",
                  f"<td class='zahl'>{v['max_abs_residuum']:.6f}</td>"]
        zellen.extend(
            f"<td class='zahl'>{v[f'p{p}_abs_residuum']:.6f}</td>"
            for p in PERZENTILE
        )
        zellen.append(f"<td class='zahl'>{v['summe_abs_residuum']:.6f}</td>")
        return "".join(zellen)

    kopf = (
        "<th>Werte</th><th>max |R|</th>"
        + "".join(f"<th>p{p} |R|</th>" for p in PERZENTILE)
        + "<th>Summe |R|</th>"
    )
    teile.append(
        "<h2>Verteilung des Residuums</h2>"
        "<p>Ausschließlich Verteilungsgrößen der Abweichungen — keine "
        "Summe der Vergleichswerte, kein Mittelwert (Grundsatzdokumentation 9.15).</p>"
        f"<table><tr><th>Gruppe</th><th>Verträge</th><th>bestanden</th>{kopf}"
        "</tr>"
        f"<tr><td>alle</td><td class='zahl'>{test['anzahl']:d}</td>"
        f"<td class='zahl'>{test['bestanden']:d}</td>"
        + _verteilungs_zellen(test["verteilung"]) + "</tr>"
    )
    for typ, gruppe in sorted(test["gruppen"].items()):
        teile.append(
            f"<tr><td>{_e(typ)}</td>"
            f"<td class='zahl'>{gruppe['anzahl']:d}</td>"
            f"<td class='zahl'>{gruppe['bestanden']:d}</td>"
            + _verteilungs_zellen(gruppe) + "</tr>"
        )
    teile.append("</table>")

    fehlgeschlagene = [v for v in test["vertraege"] if not v["bestanden"]]
    teile.append("<h2>Fehlschläge und Befunde</h2>")
    if fehlgeschlagene:
        teile.append(
            "<table><tr><th>Police</th><th>Historientyp</th>"
            "<th>t_a (Monate)</th><th>Befunde</th></tr>"
        )
        teile.extend(
            f"<tr><td>{_e(v['police_id'])}</td>"
            f"<td>{_e(v['historientyp'])}</td>"
            f"<td class='zahl'>{v['monate_ta']:d}</td>"
            f"<td class='rot'>{_e('; '.join(v['befunde']))}</td></tr>"
            for v in fehlgeschlagene
        )
        teile.append("</table>")
    else:
        teile.append("<p>Keine.</p>")

    teile.append(
        "<h2>Einzelvergleiche</h2>"
        "<table><tr><th>Police</th><th>Historientyp</th>"
        "<th>t_a (Monate)</th><th>Größe</th><th>System</th>"
        "<th>Lieferung</th><th>Residuum</th><th>Urteil</th></tr>"
    )
    for v in test["vertraege"]:
        for p in v["pruefungen"]:
            urteil = (
                "<td class='gruen'>OK</td>" if p["ok"]
                else "<td class='rot'>ABWEICHUNG</td>"
            )
            teile.append(
                f"<tr><td>{_e(v['police_id'])}</td>"
                f"<td>{_e(v['historientyp'])}</td>"
                f"<td class='zahl'>{v['monate_ta']:d}</td>"
                f"<td>{_e(p['groesse'])}</td>"
                f"<td class='zahl'>{p['system']:.6f}</td>"
                f"<td class='zahl'>{p['erwartet']:.6f}</td>"
                f"<td class='zahl'>{p['residuum']:.6f}</td>{urteil}</tr>"
            )
    teile.append("</table>")

    teile.append("<h2>Transportsicherung (kein Teil des Urteils)</h2>")
    transport = test.get("transportsicherung")
    if transport:
        teile.append(
            "<p>Mitgelieferte Prüfsummen und Bindungen sichern den "
            "Transport der Lieferung. Sie werden hier ausgewiesen und "
            "fließen NICHT in das fachliche Urteil ein (ADR-010).</p>"
            "<table><tr><th>Schlüssel</th><th>Wert</th></tr>"
        )
        teile.extend(
            f"<tr><td>{_e(k)}</td><td>{_e(v)}</td></tr>"
            for k, v in sorted(transport.items())
        )
        teile.append("</table>")
    else:
        teile.append("<p>Keine Transportangaben mitgeliefert.</p>")

    system = test.get("system")
    if system:
        teile.append("<h2>Systemstand</h2><table>")
        teile.extend(
            f"<tr><th>{_e(k)}</th><td>{_e(v)}</td></tr>"
            for k, v in sorted(system.items())
        )
        teile.append("</table>")
    teile.append("</body></html>")
    return "\n".join(teile) + "\n"


def _build_parser() -> GateArgumentParser:
    parser = GateArgumentParser(
        gate_contract=CLI_CONTRACT,
        prog=f"python -m rechner_pipeline.gates.{COMMAND}",
        description=(
            "Vorlage fuer das menschliche Gate G-A: prueft das Ergebnis "
            "des aktuariellen Tests und rendert die Entscheidungsvorlage."
        ),
    )
    parser.add_argument("--fall", default=None, help="Fall-Arbeitsbereich.")
    parser.add_argument(
        "--test", default=None,
        help="Testergebnis-JSON (Default: <fall>/abgeleitet/berichte/"
        "aktuartest.json).",
    )
    parser.add_argument("--titel", default=None, help="Berichtstitel.")
    parser.add_argument(
        "--bericht", default=None,
        help="Zielpfad des HTML-Berichts (Default: <fall>/abgeleitet/"
        "berichte/aktuartest.html).",
    )
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--diagnostics-dir", default=None)
    add_request_json_arg(parser)
    return parser


def main(argv: Optional[List[str]] = None):
    started_at = utc_now()
    args = parse_gate_args(_build_parser(), argv)

    fall = Path(args.fall).resolve() if args.fall else None
    diagnostics_dir = (
        Path(args.diagnostics_dir) if args.diagnostics_dir
        else (fall / "abgeleitet" / "diagnostics" if fall
              else Path.cwd() / "runs" / "diagnostics")
    )
    fehlstart = begin_gate_ledger_attempt(
        command=COMMAND, gate=GATE, gate_version=GATE_VERSION,
        diagnostics_dir=diagnostics_dir,
        repo_root=Path(args.repo_root) if args.repo_root else None,
        started_at=started_at,
        command_line=argv if argv is not None else sys.argv[1:],
    )
    if fehlstart is not None:
        return fehlstart

    def _finalize(result):
        return finalize_gate_ledger(result)

    def _usage(message: str, *, hints: Optional[List[str]] = None):
        return _finalize(build_result(
            command=COMMAND, gate=GATE, gate_version=GATE_VERSION,
            exit_code=Exit.USAGE,
            errors=[{"code": "usage", "message": message}],
            repair_hints=list(hints or []),
        ))

    if not args.titel:
        return _usage("erforderlich: --titel")
    test_pfad = (
        Path(args.test) if args.test
        else (fall / "abgeleitet" / "berichte" / "aktuartest.json"
              if fall else None)
    )
    if test_pfad is None:
        return _usage(
            "Testergebnis unbestimmt: --test angeben oder --fall setzen "
            "(dann <fall>/abgeleitet/berichte/aktuartest.json)"
        )
    bericht_pfad = (
        Path(args.bericht) if args.bericht
        else (fall / "abgeleitet" / "berichte" / "aktuartest.html"
              if fall else None)
    )
    if bericht_pfad is None:
        return _usage(
            "Zielpfad des Berichts unbestimmt: --bericht angeben oder "
            "--fall setzen (dann <fall>/abgeleitet/berichte/"
            "aktuartest.html)"
        )
    ledger_ziel = (diagnostics_dir / f"{COMMAND}{GATE_LEDGER_SUFFIX}")
    belegte = {
        test_pfad.resolve(), bericht_pfad.resolve(), ledger_ziel.resolve()
    }
    if len(belegte) != 3:
        return _usage(
            "Pfadkollision: --test, --bericht und der Gate-Ledger "
            "muessen drei verschiedene Dateien sein"
        )
    if not test_pfad.is_file():
        return _usage(
            f"Testergebnis nicht gefunden: {test_pfad}",
            hints=[
                "Erst den aktuariellen Test fahren: Pruefauftraege je "
                "Vertrag bauen und qa.aktuarieller_test.pruefe_stichprobe "
                "als JSON persistieren (Skill: aktuartest-durchfuehren)."
            ],
        )

    try:
        test = json.loads(test_pfad.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return _finalize(build_result(
            command=COMMAND, gate=GATE, gate_version=GATE_VERSION,
            exit_code=Exit.FILE_CONTRACT,
            errors=[{
                "code": "test_unlesbar",
                "message": f"Testergebnis nicht lesbar: {exc}",
            }],
            input_hashes=hash_files([test_pfad], missing_ok=True),
        ))

    # Fremd erzeugte oder beschaedigte JSONs duerfen die Nachrechnung
    # nicht zu einem Toolbox-Defekt (INTERNAL) machen: ein Typfehler in
    # den Daten ist eine Vertragsverletzung der DATEI.
    try:
        fehler = test_fehler(test)
    except (TypeError, ValueError, KeyError, AttributeError) as exc:
        fehler = [
            "Ergebnis strukturell unlesbar: "
            f"{type(exc).__name__}: {exc}"
        ]
    input_hashes = hash_files(
        [test_pfad] + ([fall / "fall.json"] if fall else []),
        base=fall, missing_ok=True,
    )
    if fehler:
        return _finalize(build_result(
            command=COMMAND, gate=GATE, gate_version=GATE_VERSION,
            exit_code=Exit.FILE_CONTRACT,
            errors=[
                {"code": "test_contract", "message": f}
                for f in fehler[:50]
            ],
            input_hashes=input_hashes,
            paths={"test": str(test_pfad)},
        ))

    try:
        html = baue_bericht(titel=args.titel, test=test)
    except (TypeError, ValueError, KeyError) as exc:
        return _finalize(build_result(
            command=COMMAND, gate=GATE, gate_version=GATE_VERSION,
            exit_code=Exit.FILE_CONTRACT,
            errors=[{
                "code": "test_contract",
                "message": (
                    "Ergebnis nicht renderbar: "
                    f"{type(exc).__name__}: {exc}"
                ),
            }],
            input_hashes=input_hashes,
            paths={"test": str(test_pfad)},
        ))
    bericht_pfad.parent.mkdir(parents=True, exist_ok=True)
    bericht_pfad.write_text(html, encoding="utf-8", newline="\n")

    summary = {
        "test_bestanden": bool(test["test_bestanden"]),
        "anzahl": test["anzahl"],
        "fehlgeschlagen": test["fehlgeschlagen"],
        "stichprobe_vollstaendig": bool(test["stichprobe_vollstaendig"]),
        "stichprobe": {
            k: test["stichprobe"][k]
            for k in ("profil", "umfang", "grundgesamtheit", "vollerhebung")
        },
        "max_abs_residuum": test["verteilung"].get("max_abs_residuum", 0.0),
        "belege": hash_files(
            [test_pfad, bericht_pfad], base=fall, missing_ok=False,
        ),
        # Renderer-Vertrag: mit diesen Eingaben ist der Bericht
        # deterministisch reproduzierbar — G-A rendert ihn bytegenau
        # neu, statt dem Ledger-Status zu glauben.
        "bericht_erzeugung": {"titel": args.titel},
    }
    paths = {"test": str(test_pfad), "bericht": str(bericht_pfad)}
    output_hashes = hash_files([bericht_pfad], base=fall)
    if test["test_bestanden"]:
        return _finalize(build_result(
            command=COMMAND, gate=GATE, gate_version=GATE_VERSION,
            exit_code=Exit.OK, paths=paths, summary=summary,
            input_hashes=input_hashes, output_hashes=output_hashes,
        ))
    return _finalize(build_result(
        command=COMMAND, gate=GATE, gate_version=GATE_VERSION,
        exit_code=Exit.GOLDEN_MASTER, paths=paths, summary=summary,
        input_hashes=input_hashes, output_hashes=output_hashes,
        errors=[
            {"code": "aktuartest_nicht_bestanden", "message": m}
            for m in (
                [f"{test['fehlgeschlagen']} von {test['anzahl']} "
                 "Vertraegen fehlgeschlagen"]
                if test["fehlgeschlagen"] else []
            ) + list(test["mengenbefunde"])
        ],
    ))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_command(main))
