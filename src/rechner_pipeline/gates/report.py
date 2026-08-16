"""``report`` toolbox command — deterministic Markdown rendering of a run.

Renders the machine-readable acceptance artifacts of one ``assurance`` run
(``qa_report.json`` plus the ``<command>.gate.json`` ledger entries in a shared
``--diagnostics-dir``) into one human-readable Markdown report.

Properties:

* **Deterministic:** the output is a pure function of the ledger files — the
  same diagnostics directory always renders to the byte-identical report. The
  renderer adds no timestamps of its own (all times come from the ledger) and
  iterates in fixed order.
* **Comparable:** every run is rendered with the same section structure and the
  same per-gate metrics, so reports from different runs (or different source
  workbooks) can be diffed side by side.
* **Read-only:** the command never modifies the diagnostics directory; the
  report goes to stdout or to ``--out``.

This is NOT a gate — it writes no ledger entry and takes no part in acceptance.
The verdict it shows is whatever ``dossier`` decided.

Usage::

    python -m rechner_pipeline.gates.report --diagnostics-dir diagnostics
    python -m rechner_pipeline.gates.report --diagnostics-dir diagnostics --out bericht.md

Knoten: system/assurance
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from rechner_pipeline.gates.orchestrate.dossier import ALL_GATES

#: Renderer version, shown in the footer so reports state how they were made.
REPORT_VERSION = "1.0.0"

#: Cap for listed deviations / unmatched columns (the full lists stay in the
#: ledger). Overflow is rendered as an explicit "+N weitere" line.
MAX_LISTED = 20


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def load_run(diagnostics_dir: Path) -> Dict[str, Any]:
    """Load qa_report + all known gate ledger entries from *diagnostics_dir*."""
    run: Dict[str, Any] = {
        "qa_report": _load_json(diagnostics_dir / "qa_report.json"),
        "gates": {},
    }
    for _gate_id, command in ALL_GATES:
        entry = _load_json(diagnostics_dir / f"{command}.gate.json")
        if entry is not None:
            run["gates"][command] = entry
    return run


# --------------------------------------------------------------------------- #
# Rendering helpers
# --------------------------------------------------------------------------- #


def _num(value: Any) -> str:
    """Render a JSON number exactly as JSON would (round-trip stable)."""
    return json.dumps(value, ensure_ascii=False)


def _status_de(status: Any) -> str:
    return {
        "passed": "bestanden",
        "failed": "nicht bestanden",
        "skipped": "übersprungen",
    }.get(status, str(status))


def _gate_metric(command: str, summary: Dict[str, Any]) -> str:
    """One fixed, comparable metric string per gate command."""
    if command == "extract":
        bundle = summary.get("input_bundle", {})
        detail = bundle.get("coverage_detail", {})
        return (
            f"Coverage {bundle.get('expectation_coverage', '?')}: "
            f"{detail.get('scalar_keys_expected', '?')} Skalare, "
            f"{detail.get('table_cells_expected', '?')} Tabellenzellen erwartet"
        )
    if command == "validate":
        files = summary.get("extracted_files", [])
        order = "Reihenfolge ok" if summary.get("order_ok") else "Reihenfolge verletzt"
        return f"{len(files)} Dateien, {order}"
    if command == "security":
        metrics = summary.get("metrics", {})
        return (
            f"{metrics.get('files_scanned', '?')} Dateien geprüft, "
            f"{metrics.get('violations', '?')} Verstöße"
        )
    if command == "conventions":
        metrics = summary.get("metrics", {})
        return (
            f"{metrics.get('edges', '?')} Import-Kanten, "
            f"{metrics.get('disallowed_edges', '?')} unzulässig, "
            f"{metrics.get('cycles', '?')} Zyklen"
        )
    if command == "golden_master":
        return (
            f"{summary.get('scalars_tested', '?')} Skalare + "
            f"{summary.get('table_cells_tested', '?')} Tabellenzellen geprüft, "
            f"{summary.get('deviation_count', '?')} Abweichungen, "
            f"{len(summary.get('unmatched_columns', []))} nicht zugeordnete Spalten"
        )
    if command == "algebraic":
        return (
            f"{len(summary.get('identities_checked', []))} Identitäten, "
            f"{summary.get('total_cases', '?')} Fälle, "
            f"{summary.get('counterexample_count', '?')} Gegenbeispiele "
            f"({summary.get('engine', '?')} {summary.get('engine_version', '?')})"
        )
    if command == "roundtrip":
        tafeln = summary.get("tafeln", {})
        reex = summary.get("reextraction", {})
        recomp = summary.get("recomputation", {})
        parts = [
            f"tafeln {'ok' if tafeln.get('ok') else 'nicht ok'}",
            f"Re-Extraktion {'ok' if reex.get('ok') else 'nicht ok'}"
            + (f" ({len(reex.get('drifted', []))} Drift)" if reex.get("drifted") else ""),
            f"Neuberechnung {'ok' if recomp.get('ok') else 'nicht ok'}"
            + f" ({recomp.get('repeats', '?')}x)",
        ]
        return ", ".join(parts)
    return ""


def _source_name(run: Dict[str, Any]) -> str:
    extract = run["gates"].get("extract")
    if extract:
        source = extract.get("summary", {}).get("input_bundle", {}).get("source_path", "")
        if source:
            return Path(source).name
    return "unbekannte Quelle"


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #


def render(run: Dict[str, Any], *, diagnostics_dir_name: str) -> str:
    """Render the loaded *run* into the Markdown report (deterministic)."""
    qa = run["qa_report"] or {}
    gates: Dict[str, Dict[str, Any]] = run["gates"]
    lines: List[str] = []
    out = lines.append

    accepted = qa.get("accepted") is True
    verdict = "ANGENOMMEN" if accepted else "NICHT ANGENOMMEN"

    out(f"# Abnahmebericht — {_source_name(run)}")
    out("")
    out(f"**Verdikt: {verdict}** (decision: {qa.get('decision', '?')})")
    out("")
    out(f"- Erwartungs-Coverage: {qa.get('expectation_coverage', '?')}")
    out(f"- Zeitpunkt (dossier): {qa.get('created_at', '?')}")
    out(f"- Versuche: {qa.get('attempts_used', '?')} von max. {qa.get('max_attempts', '?')}")
    out(f"- QA-Contract: {qa.get('qa_contract_path') or 'nicht angegeben'}")
    out("")

    out("## Gates")
    out("")
    out("| Gate | Befehl | Status | Kennzahlen |")
    out("|---|---|---|---|")
    for gate_id, command in ALL_GATES:
        entry = gates.get(command)
        if entry is None:
            out(f"| {gate_id} | {command} | nicht vorhanden | — |")
            continue
        status = _status_de(entry.get("status"))
        metric = _gate_metric(command, entry.get("summary", {})) or "—"
        out(f"| {gate_id} | {command} | {status} | {metric} |")
    out("")

    gm = gates.get("golden_master", {}).get("summary", {})
    if gm:
        out("## Golden-Master")
        out("")
        deviations = gm.get("deviations", [])
        unmatched = gm.get("unmatched_columns", [])
        out(
            f"{gm.get('scalars_tested', '?')} Skalare und "
            f"{gm.get('table_cells_tested', '?')} Tabellenzellen gegen die aus der "
            f"Quelle extrahierten Erwartungswerte geprüft: "
            f"{gm.get('deviation_count', '?')} Abweichungen, "
            f"{len(unmatched)} nicht zugeordnete Spalten."
        )
        if deviations:
            out("")
            out("Abweichungen:")
            for d in deviations[:MAX_LISTED]:
                out(f"- {d}")
            if len(deviations) > MAX_LISTED:
                out(f"- +{len(deviations) - MAX_LISTED} weitere (siehe golden_master.gate.json)")
        if unmatched:
            out("")
            out("Nicht zugeordnete erwartete Spalten:")
            for c in unmatched[:MAX_LISTED]:
                out(f"- {c}")
            if len(unmatched) > MAX_LISTED:
                out(f"- +{len(unmatched) - MAX_LISTED} weitere")
        out("")

    alg = gates.get("algebraic", {}).get("summary", {})
    identities = alg.get("identities_checked", [])
    if identities:
        out("## Algebraische Identitäten")
        out("")
        out(
            f"{len(identities)} Identitäten property-basiert geprüft "
            f"({_num(alg.get('total_cases', 0))} Fälle, "
            f"{_num(alg.get('counterexample_count', 0))} Gegenbeispiele; "
            f"Engine {alg.get('engine', '?')} {alg.get('engine_version', '?')}, "
            f"max_examples {_num(alg.get('max_examples', 0))}):"
        )
        out("")
        for ident in identities:
            out(f"- `{ident}`")
        counterexamples = alg.get("counterexamples", [])
        if counterexamples:
            out("")
            out("Gegenbeispiele:")
            for ce in counterexamples[:MAX_LISTED]:
                out(f"- `{json.dumps(ce, ensure_ascii=False, sort_keys=True)}`")
        out("")

    out("## Annahmen und Warnungen")
    out("")
    assumptions = qa.get("open_assumptions", [])
    warnings = qa.get("blocking_warnings", [])
    if not assumptions and not warnings:
        out("Keine offenen Annahmen, keine blockierenden Warnungen.")
    if assumptions:
        out("Offene Annahmen:")
        for a in assumptions:
            out(f"- `{json.dumps(a, ensure_ascii=False, sort_keys=True)}`")
    if warnings:
        out("Blockierende Warnungen:")
        for w in warnings:
            out(f"- `{json.dumps(w, ensure_ascii=False, sort_keys=True)}`")
    out("")

    deps = qa.get("dependency_versions", {})
    if deps:
        out("## Umgebung")
        out("")
        out("| Komponente | Version |")
        out("|---|---|")
        for name in sorted(deps):
            out(f"| {name} | {deps[name]} |")
        out("")

    hashes = qa.get("generated_file_hashes", {})
    # Beide Ledger-Formen: Liste von {path, sha256, ...} oder dict path -> hash.
    if isinstance(hashes, list):
        hash_rows = {str(item.get("path", "?")): str(item.get("sha256", "?")) for item in hashes}
    else:
        hash_rows = {str(k): str(v) for k, v in hashes.items()}
    # Bytecode-Artefakte sind kein Kern-Inhalt.
    hash_rows = {p: h for p, h in hash_rows.items() if "__pycache__" not in p}
    if hash_rows:
        out("## Artefakt-Hashes (SHA-256, gekürzt)")
        out("")
        out("| Datei | Hash |")
        out("|---|---|")
        for path in sorted(hash_rows):
            out(f"| {path} | `{hash_rows[path][:12]}` |")
        out("")

    out("---")
    out("")
    out(
        f"Erzeugt mit `python -m rechner_pipeline.gates.report` "
        f"(Version {REPORT_VERSION}) aus `{diagnostics_dir_name}/`. "
        f"Das Rendering ist deterministisch: gleiche Ledger-Dateien ergeben "
        f"einen byte-identischen Bericht. Maschinenlesbares Original: "
        f"`qa_report.json`, `run_dossier.json` und die `*.gate.json`-Einträge."
    )
    out("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.gates.report",
        description=(
            "Deterministisches Markdown-Rendering eines assurance-Laufs aus "
            "dem Diagnostics-Ledger (read-only, kein Gate)."
        ),
    )
    parser.add_argument(
        "--diagnostics-dir",
        required=True,
        help="Verzeichnis mit qa_report.json und den <command>.gate.json-Einträgen.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Zieldatei für den Bericht (Default: stdout).",
    )
    ns = parser.parse_args(argv)

    diagnostics_dir = Path(ns.diagnostics_dir)
    if not diagnostics_dir.is_dir():
        print(f"report: --diagnostics-dir nicht gefunden: {diagnostics_dir}", file=sys.stderr)
        return 2
    run = load_run(diagnostics_dir)
    if run["qa_report"] is None:
        print(
            f"report: {diagnostics_dir / 'qa_report.json'} fehlt oder ist kein JSON "
            "(erst dossier bzw. assurance laufen lassen).",
            file=sys.stderr,
        )
        return 2

    text = render(run, diagnostics_dir_name=diagnostics_dir.name)
    if ns.out:
        out_path = Path(ns.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
