"""
LangGraph-basierter Wrapper um den klassischen ``PipelineRunner``.

Verwendet die öffentliche API des Runners (``assert_required_files``,
``prepare_manifest``, ``run_main_llm``, ``run_test_llm``, ``run_compare``)
statt private Underscore-Methoden.

Ergänzt:
- explizite State-Übergänge,
- Quality-Gates,
- begrenzte Retries,
- Human-Review-Handoff.
"""

from __future__ import annotations

import json
import os
import re
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, TypedDict

from rechner_pipeline.generate.output import OutputValidationError
from rechner_pipeline.orchestrate.runner import PipelineOptions, PipelineRunner
from rechner_pipeline.models.manifest import ExportManifest
from rechner_pipeline.qa.security import StaticSecurityError


StepStatus = Literal["pending", "ok", "skipped", "error"]
Decision = Literal["continue", "repair", "human_review", "finish"]


class AgenticState(TypedDict, total=False):
    repo_root: str
    excel_path: str
    options: PipelineOptions
    manifest: ExportManifest
    step_status: Dict[str, StepStatus]
    failed_step: str | None
    errors: List[str]
    diagnostics: List[Dict[str, Any]]
    repair_contexts: Dict[str, str]
    repair_artifacts: Dict[str, str]
    agentic_diagnostics_path: str
    retries: Dict[str, int]
    gate_decision: Decision
    human_review_required: bool


@dataclass(frozen=True)
class AgenticOptions:
    pipeline: PipelineOptions
    max_retries_main: int
    max_retries_test: int
    fail_on_human_review: bool


def _runner_from_state(state: AgenticState) -> PipelineRunner:
    repo_root = Path(state["repo_root"])
    options = state["options"]
    excel_path_str = state.get("excel_path")
    excel_path = Path(excel_path_str) if excel_path_str else None
    return PipelineRunner(repo_root=repo_root, options=options, excel_path=excel_path)


def _set_step_status(state: AgenticState, step: str, status: StepStatus) -> Dict[str, Any]:
    step_status = dict(state.get("step_status", {}))
    step_status[step] = status
    return {"step_status": step_status}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json_artifact(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"read_error": f"{exc.__class__.__name__}: {exc}"}


def _read_text_excerpt(path: Path, limit: int = 4000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"<read error: {exc.__class__.__name__}: {exc}>"
    if len(text) <= limit:
        return text
    return text[:limit] + "\n... <truncated>"


def _diagnostics_path(runner: PipelineRunner) -> Path:
    return runner.generated_dir / "agentic_diagnostics.json"


def _repair_artifact_path(runner: PipelineRunner, target_step: str) -> Path:
    return runner.generated_dir / f"agentic_repair_context_{target_step}.json"


def _classify_exception(step: str, exc: Exception) -> str:
    message = str(exc).lower()
    if isinstance(exc, OutputValidationError):
        return "compile" if "do not compile" in message else "output_contract"
    if isinstance(exc, (SyntaxError, IndentationError)):
        return "compile"
    if isinstance(exc, StaticSecurityError) or "static security" in message:
        return "runtime_security"
    if step == "compare" or "regression test failed" in message or "returncode" in message:
        return "test"
    return "runtime"


def _artifact_record(path: Path) -> Dict[str, Any]:
    record: Dict[str, Any] = {"path": str(path), "exists": path.exists()}
    if not path.exists():
        return record
    if path.suffix == ".json":
        record["json"] = _read_json_artifact(path)
    else:
        record["text_excerpt"] = _read_text_excerpt(path)
    return record


def _diagnostic_artifacts(runner: PipelineRunner, step: str) -> List[Dict[str, Any]]:
    paths = [
        runner.manifest_path,
        runner.static_security_report_path,
        runner.compare_result_path,
    ]
    if step in {"main_llm", "test_llm"}:
        debug_prompt = (
            wflog.run_dir() / "main_prompt.txt"
            if step == "main_llm"
            else wflog.run_dir() / "test_prompt.txt"
        )
        paths.append(debug_prompt)
    if step in {"test_llm", "compare"}:
        paths.append(runner.test_py_path)
    return [_artifact_record(path) for path in paths]


def _write_diagnostics(runner: PipelineRunner, diagnostics: List[Dict[str, Any]]) -> Path:
    path = _diagnostics_path(runner)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "created_at": _utc_now(),
                "diagnostics": diagnostics,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def _record_error(state: AgenticState, step: str, exc: Exception) -> Dict[str, Any]:
    runner = _runner_from_state(state)
    errors = list(state.get("errors", []))
    summary = f"{step}: {exc.__class__.__name__}: {exc}"
    errors.append(summary)
    errors.append(traceback.format_exc())

    diagnostic = {
        "created_at": _utc_now(),
        "step": step,
        "category": _classify_exception(step, exc),
        "exception": {
            "type": exc.__class__.__name__,
            "message": str(exc),
        },
        "traceback": traceback.format_exc(),
        "retry_counts": dict(state.get("retries", {})),
        "artifacts": _diagnostic_artifacts(runner, step),
    }
    diagnostics = [*state.get("diagnostics", []), diagnostic]
    diagnostic_path = _write_diagnostics(runner, diagnostics)
    errors.append(f"Structured diagnostic written to {diagnostic_path}")
    return {
        "errors": errors,
        "failed_step": step,
        "diagnostics": diagnostics,
        "agentic_diagnostics_path": str(diagnostic_path),
    }


def _latest_diagnostic(state: AgenticState) -> Dict[str, Any] | None:
    diagnostics = state.get("diagnostics", [])
    if not diagnostics:
        return None
    return diagnostics[-1]


def _format_repair_context(diagnostic: Dict[str, Any]) -> str:
    focused = {
        "failed_step": diagnostic.get("step"),
        "category": diagnostic.get("category"),
        "exception": diagnostic.get("exception"),
        "artifacts": diagnostic.get("artifacts", []),
    }
    return json.dumps(focused, ensure_ascii=False, indent=2)


def _clear_repair_context(state: AgenticState, step: str) -> Dict[str, Any]:
    contexts = dict(state.get("repair_contexts", {}))
    contexts.pop(step, None)
    return {"repair_contexts": contexts}


def _repair_node(state: AgenticState, target_step: str) -> Dict[str, Any]:
    diagnostic = _latest_diagnostic(state)
    if diagnostic is None:
        return {"gate_decision": "human_review", "human_review_required": True}

    runner = _runner_from_state(state)
    repair_context = _format_repair_context(diagnostic)
    artifact = {
        "schema_version": 1,
        "created_at": _utc_now(),
        "target_step": target_step,
        "source_step": diagnostic.get("step"),
        "category": diagnostic.get("category"),
        "repair_context": repair_context,
    }
    path = _repair_artifact_path(runner, target_step)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")

    contexts = dict(state.get("repair_contexts", {}))
    contexts[target_step] = repair_context
    artifacts = dict(state.get("repair_artifacts", {}))
    artifacts[target_step] = str(path)
    update: Dict[str, Any] = {
        "repair_contexts": contexts,
        "repair_artifacts": artifacts,
        "failed_step": None,
    }
    update.update(_set_step_status(state, f"repair_{target_step}", "ok"))
    return update


from rechner_pipeline.orchestrate import wflog


def _iteration_no(state: AgenticState) -> int:
    return int(state.get("retries", {}).get("compare", 0)) + 1


def _capture_fixture(runner: PipelineRunner, n: int):
    """Modell-Ausgabe dieser Iteration als wiederverwendbares Replay-Fixture
    wegsichern: ``runs/<stamp>/fixtures/<nn>_iteration.txt``.

    So liefert jeder echte Lauf automatisch ein echtes Replay-Set. Nur für
    echte Provider (bei ``replay`` wäre die Ausgabe nur die Kopie der Eingabe);
    per ``RP_CAPTURE_FIXTURES=0`` abschaltbar. Gibt den Pfad zurück oder None.
    """
    if runner.options.provider == "replay":
        return None
    if os.environ.get("RP_CAPTURE_FIXTURES", "1") == "0":
        return None
    output_path = wflog.run_dir() / "main_output.txt"
    if not output_path.exists():
        return None
    fixtures = wflog.run_dir() / "fixtures"
    try:
        fixtures.mkdir(parents=True, exist_ok=True)
        target = fixtures / f"{n:02d}_iteration.txt"
        target.write_text(
            output_path.read_text(encoding="utf-8", errors="replace"),
            encoding="utf-8",
        )
        return target
    except OSError:
        return None


def _code_excerpt(runner: PipelineRunner, n: int = 18):
    """Auszug der echten Rechenlogik: ``actuarial.py`` ab der ersten
    Funktionsdefinition (deterministisch, kein Raten). Zeigt, wie das Modell
    eine Excel-Größe tatsächlich nachrechnet — echter Code, kein Hardcoding."""
    path = runner.generated_dir / "actuarial.py"
    if not path.exists():
        cands = sorted(runner.generated_dir.glob("*.py"))
        if not cands:
            return None, []
        path = cands[0]
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for i, ln in enumerate(lines):
        if ln.startswith("def "):
            return path.name, lines[i:i + n]
    return path.name, lines[:n]


def _excel_formula_samples(runner: PipelineRunner, limit: int = 3):
    """Ein paar echte Excel-Originalformeln aus den Sheet-CSVs
    (Blatt;Adresse;Formel;Wert). Reines Auslesen, kein Raten."""
    import csv

    out = []
    sheets = sorted(
        p for p in runner.out_dir.glob("*.csv")
        if p.name != "names_manager.csv"
        and not p.name.endswith(("_compressed.csv", "_table_values.csv"))
    )
    for sheet in sheets:
        try:
            with sheet.open(encoding="utf-8", newline="") as f:
                reader = csv.reader(f, delimiter=";")
                next(reader, None)  # Kopfzeile
                for row in reader:
                    if len(row) >= 4 and row[2].startswith("="):
                        addr = row[1].replace("$", "")
                        out.append(f"{row[0]}!{addr}: {row[2]}")
                        if len(out) >= limit:
                            return out
        except OSError:
            continue
    return out


def _function_inventory(runner: PipelineRunner):
    """Öffentliche Funktionsnamen aus actuarial.py — die 'API' des Rechenkerns."""
    path = runner.generated_dir / "actuarial.py"
    if not path.exists():
        return []
    names = []
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if ln.startswith("def "):
            names.append(ln[4:].split("(", 1)[0])
    return names


def _scalar_table(runner: PipelineRunner):
    """Soll/Ist je Skalar aus dem Compare-Ergebnis (SKALAR:-Zeilen des Harness).
    Liefert [(name, erwartet, berechnet, status)] — echte Werte aus dem Lauf."""
    path = runner.compare_result_path
    if not path.exists():
        return []
    try:
        stdout = json.loads(path.read_text(encoding="utf-8")).get("stdout", "")
    except (OSError, json.JSONDecodeError):
        return []
    rows = []
    for ln in stdout.splitlines():
        t = ln.strip()
        if not t.startswith("SKALAR:"):
            continue
        parts = t[len("SKALAR:"):].split()
        if not parts:
            continue
        name = parts[0].split(":", 1)[-1]
        kv = dict(p.split("=", 1) for p in parts[1:] if "=" in p)
        rows.append((name, kv.get("erwartet"), kv.get("berechnet"), kv.get("status")))
    return rows


def _table_sample(runner: PipelineRunner):
    """Stichprobe der Verlaufs-/Tabellenwerte aus dem Compare-Ergebnis
    (TABELLE:-Zeilen). Liefert [(zeile, spalte, erwartet, berechnet, status)]."""
    path = runner.compare_result_path
    if not path.exists():
        return []
    try:
        stdout = json.loads(path.read_text(encoding="utf-8")).get("stdout", "")
    except (OSError, json.JSONDecodeError):
        return []
    rows = []
    for ln in stdout.splitlines():
        t = ln.strip()
        if not t.startswith("TABELLE:"):
            continue
        parts = t[len("TABELLE:"):].split()
        if not parts:
            continue
        body = parts[0].split(":", 1)[-1]  # spalte[zeile]
        kv = dict(p.split("=", 1) for p in parts[1:] if "=" in p)
        if "[" in body:
            col, rest = body.split("[", 1)
            ri = rest.rstrip("]")
        else:
            col, ri = body, ""
        rows.append((ri, col, kv.get("erwartet"), kv.get("berechnet"), kv.get("status")))
    return rows


def _gm_return_block(runner: PipelineRunner):
    """Die ganze Funktion ``golden_master_outputs()`` aus den erzeugten Dateien
    (über den festen Namen gefunden). So findet ein Diff genau die geänderten
    Zeilen (z. B. ergänzte Skalar-Einträge). Zeilen oder []."""
    for p in sorted(runner.generated_dir.glob("*.py")):
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        for i, ln in enumerate(lines):
            if ln.lstrip().startswith("def golden_master_outputs"):
                block = [lines[i]]
                for k in range(i + 1, len(lines)):
                    # Funktion endet bei der nächsten Zeile auf Spalte 0
                    if lines[k].strip() and not lines[k][0].isspace():
                        break
                    block.append(lines[k])
                return block
    return []


def _wflog_int(name: str, default: int) -> int:
    """Ganzzahl aus einer Umgebungsvariable; bei Fehler der Default."""
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _fmt_num(s):
    """Zahl kompakt formatieren; None/'None' -> Gedankenstrich."""
    if s is None or s == "None":
        return "—"
    try:
        return f"{float(s):.8g}"
    except (TypeError, ValueError):
        return str(s)


def _delta(ev, cv):
    try:
        return f"{abs(float(cv) - float(ev)):.0e}"
    except (TypeError, ValueError):
        return "—"


_STATUS_LABEL = {"ok": "ok", "abw": "ABW", "fehlt": "fehlt", "kein-soll": "kein Soll"}


def _render_scalar_table(runner: PipelineRunner) -> None:
    """Soll/Ist-Tabelle der Skalare (Excel-Soll vs. berechnet, Δ, Status)."""
    rows = _scalar_table(runner)
    if not rows:
        return
    table_rows = [
        [name, _fmt_num(ev), _fmt_num(cv), _delta(ev, cv), _STATUS_LABEL.get(status, status)]
        for name, ev, cv, status in rows[:12]
    ]
    wflog.table(
        ["Skalar", "Excel-Soll", "berechnet", "Δ", "Status"],
        table_rows,
        aligns=["l", "r", "r", "r", "l"],
    )


def _render_table_sample(runner: PipelineRunner) -> None:
    """Auszug der Verlaufs-/Tabellenwerte als Soll/Ist-Tabelle.

    Umfang konfigurierbar: ``RP_WFLOG_TABLE_ROWS`` (Zeilen, Default 3) und
    ``RP_WFLOG_TABLE_COLS`` (Spalten, Default 3); jeweils 0 = so viele wie
    vorhanden.
    """
    rows = _table_sample(runner)
    if not rows:
        return
    max_rows = _wflog_int("RP_WFLOG_TABLE_ROWS", 3)
    max_cols = _wflog_int("RP_WFLOG_TABLE_COLS", 3)

    def _ri(r):
        s = str(r[0])
        return int(s) if s.lstrip("-").isdigit() else 0

    # Spalten in Reihenfolge des ersten Auftretens (= Excel-Spaltenreihenfolge)
    col_order = []
    for _, col, *_ in rows:
        if col not in col_order:
            col_order.append(col)
    cols = col_order if max_cols <= 0 else col_order[:max_cols]
    row_ids = sorted({_ri(r) for r in rows})
    row_ids = row_ids if max_rows <= 0 else row_ids[:max_rows]
    col_set, row_set = set(cols), set(row_ids)

    sel = [r for r in rows if r[1] in col_set and _ri(r) in row_set]
    sel.sort(key=lambda r: (_ri(r), cols.index(r[1])))
    if not sel:
        return
    trows = [
        [ri, col, _fmt_num(ev), _fmt_num(cv), _delta(ev, cv), _STATUS_LABEL.get(st, st)]
        for ri, col, ev, cv, st in sel
    ]
    wflog.detail(f"Verlaufswerte (Auszug {len(row_ids)} Zeilen x {len(cols)} Spalten, Soll/Ist):")
    wflog.table(
        ["Zeile", "Spalte", "Excel-Soll", "berechnet", "Δ", "Status"],
        trows,
        aligns=["r", "l", "r", "r", "r", "l"],
    )


def _record_convergence(runner: PipelineRunner, n: int, deviations: int, tested: int) -> None:
    """Pro Iteration eine Zeile (n;Abweichungen;geprüft) für die Abschluss-Karte.

    Erste Iteration schreibt die Datei frisch ("w"), sonst anhängen ("a") —
    wichtig, weil Demo-Läufe sich ``runs/demo`` teilen und sich sonst über
    mehrere Läufe aufsummieren würden.
    """
    try:
        mode = "w" if n <= 1 else "a"
        with (wflog.run_dir() / "convergence.csv").open(mode, encoding="utf-8") as f:
            f.write(f"{n};{deviations};{tested}\n")
    except OSError:
        pass


def _compare_summary(runner: PipelineRunner):
    """(Abweichungszahl, [Abweichungs-Zeilen], geprüfte Werte) aus dem echten
    Compare-Ergebnis lesen — keine festen Werte, alles aus dem Lauf."""
    path = runner.compare_result_path
    if not path.exists():
        return 0, [], 0
    try:
        stdout = json.loads(path.read_text(encoding="utf-8")).get("stdout", "")
    except (OSError, json.JSONDecodeError):
        return 0, [], 0
    n, devs, tested = 0, [], 0
    for ln in stdout.splitlines():
        t = ln.strip()
        if t.startswith("ABWEICHUNG:"):
            devs.append(t.replace("ABWEICHUNG:", "").strip())
        m = re.match(r"Abweichungen:\s*(\d+)", t)
        if m:
            n = int(m.group(1))
        for g in re.findall(r"getestet=(\d+)", t):
            tested += int(g)
    return n, devs, tested


def prepare_node(state: AgenticState) -> Dict[str, Any]:
    runner = _runner_from_state(state)
    try:
        runner.assert_required_files()
        wflog.phase("Auslesen", "Excel/VBA ohne Excel in Artefakte überführen")
        if wflog.enabled():
            import contextlib
            import io
            with contextlib.redirect_stdout(io.StringIO()):
                manifest = runner.prepare_manifest()
        else:
            manifest = runner.prepare_manifest()
        wflog.items("Tabellenblätter", [p.stem for p in manifest.sheet_csvs])
        if manifest.vba_txts:
            wflog.items("VBA-Module", [p.stem for p in manifest.vba_txts])
        wflog.items("Eingabe-Artefakte", [p.name for p in manifest.llm_inputs])
        if wflog.enabled():
            for f in _excel_formula_samples(runner):
                wflog.detail(f"Excel-Original  {f}")
        update: Dict[str, Any] = {"manifest": manifest, "failed_step": None}
        update.update(_set_step_status(state, "prepare", "ok"))
        return update
    except Exception as exc:
        update = _record_error(state, "prepare", exc)
        update.update(_set_step_status(state, "prepare", "error"))
        return update


def main_llm_node(state: AgenticState) -> Dict[str, Any]:
    options = state["options"]
    if options.skip_main_llm:
        return _set_step_status(state, "main_llm", "skipped")

    runner = _runner_from_state(state)
    manifest = state["manifest"]
    repair = state.get("repair_contexts", {}).get("main_llm")
    wflog.iteration(_iteration_no(state),
                    "Rechenkern erzeugen" + (" (mit Korrektur-Kontext)" if repair else ""))
    try:
        manifest = runner.run_main_llm(manifest, repair_context=repair)
        n = _iteration_no(state)
        _capture_fixture(runner, n)  # Replay-Set still mitschneiden (nicht im Log)
        if wflog.enabled():
            prompt_path = wflog.run_dir() / "main_prompt.txt"
            if prompt_path.exists():
                ptext = prompt_path.read_text(encoding="utf-8", errors="replace")
                keep = wflog.run_dir() / f"prompt_iteration_{n}.txt"
                keep.write_text(ptext, encoding="utf-8")
                wflog.detail(f"Prompt an das Modell: {len(ptext)} Zeichen"
                             + (" inkl. Korrektur-Kontext" if repair else "")
                             + f"  (vollständig: {keep.name})")
                wflog.detail("Prompt-Anfang:")
                for ln in ptext.strip()[:280].splitlines():
                    wflog.code(ln)
            gen_files = sorted(runner.generated_dir.glob("*.py")) + sorted(runner.generated_dir.glob("*.xml"))
            wflog.items(
                "Erzeugte Dateien",
                [f"{p.name} ({len(p.read_text(encoding='utf-8', errors='replace').splitlines())} Z.)"
                 for p in gen_files],
            )
            wflog.detail("Hauptdateien statisch geprüft")
            wflog.items("Funktionen (actuarial.py)", _function_inventory(runner))
            fname, excerpt = _code_excerpt(runner)
            if excerpt and n == 1:
                wflog.detail(f"Auszug {fname} (Rechenlogik):")
                for ln in excerpt:
                    wflog.code(ln)
            # Inter-Iterations-Diff von golden_master_outputs(): macht die
            # Selbstkorrektur in echtem Code sichtbar (nutzt die erzeugten Dateien)
            cur = _gm_return_block(runner)
            keep_gm = wflog.run_dir() / f"gm_return_{n}.txt"
            keep_gm.write_text("\n".join(cur), encoding="utf-8")
            prev_gm = wflog.run_dir() / f"gm_return_{n - 1}.txt"
            if n >= 2 and cur and prev_gm.exists():
                import difflib

                prev = prev_gm.read_text(encoding="utf-8").splitlines()
                changed = [
                    ln for ln in difflib.unified_diff(prev, cur, lineterm="")
                    if ln[:1] in "+-" and not ln.startswith(("+++", "---")) and ln[1:].strip()
                ]
                if changed:
                    wflog.detail(f"Änderung an golden_master_outputs() ggü. Iteration {n - 1}:")
                    for ln in changed[:12]:
                        wflog.diff(ln[0], ln[1:].strip())
        update: Dict[str, Any] = {"manifest": manifest, "failed_step": None}
        update.update(_set_step_status(state, "main_llm", "ok"))
        update.update(_clear_repair_context(state, "main_llm"))
        return update
    except Exception as exc:
        update = _record_error(state, "main_llm", exc)
        update.update(_set_step_status(state, "main_llm", "error"))
        return update


def test_llm_node(state: AgenticState) -> Dict[str, Any]:
    options = state["options"]
    # Im fixed-Modus gibt es keinen LLM-generierten Test (fester Harness in
    # run_compare); die Stufe wird übersprungen.
    if options.skip_test_llm or options.test_mode == "fixed":
        return _set_step_status(state, "test_llm", "skipped")

    runner = _runner_from_state(state)
    manifest = state["manifest"]
    try:
        manifest = runner.run_test_llm(
            manifest,
            repair_context=state.get("repair_contexts", {}).get("test_llm"),
        )
        update: Dict[str, Any] = {"manifest": manifest, "failed_step": None}
        update.update(_set_step_status(state, "test_llm", "ok"))
        update.update(_clear_repair_context(state, "test_llm"))
        return update
    except Exception as exc:
        update = _record_error(state, "test_llm", exc)
        update.update(_set_step_status(state, "test_llm", "error"))
        return update


def compare_node(state: AgenticState) -> Dict[str, Any]:
    options = state["options"]
    if options.skip_compare_run:
        return _set_step_status(state, "compare", "skipped")

    runner = _runner_from_state(state)
    wflog.phase("Validieren", "Vergleich gegen die Excel-Originalwerte (Golden-Master)")
    n = _iteration_no(state)
    try:
        runner.run_compare()
        _n, _d, tested = _compare_summary(runner)
        if wflog.enabled():
            _render_scalar_table(runner)
            _render_table_sample(runner)
            _record_convergence(runner, n, 0, tested)
        wflog.ok((f"{tested} Werte geprüft — alle stimmen mit dem Excel-Original")
                 if tested else "alle Werte stimmen mit dem Excel-Original")
        update: Dict[str, Any] = {"failed_step": None}
        update.update(_set_step_status(state, "compare", "ok"))
        return update
    except Exception as exc:
        dn, devs, tested = _compare_summary(runner)
        if wflog.enabled():
            _render_scalar_table(runner)
            _render_table_sample(runner)
            _record_convergence(runner, n, dn, tested)
            # Tabellen-Zell-Abweichungen ergänzen (Skalare stehen in der Tabelle)
            for d in [x for x in devs if "[" in x][:6]:
                wflog.detail(f"abweichend: {d}")
        if dn and tested:
            wflog.fail(f"{dn} von {tested} geprüften Werten abweichend — nicht bestanden")
        else:
            wflog.fail(f"{dn} Abweichung(en) — nicht bestanden" if dn else "Validierung nicht bestanden")
        update = _record_error(state, "compare", exc)
        update.update(_set_step_status(state, "compare", "error"))
        return update


def repair_main_node(state: AgenticState) -> Dict[str, Any]:
    wflog.detail("Korrektur: Abweichungen werden dem Modell zurückgegeben -> neue Iteration")
    return _repair_node(state, "main_llm")


def repair_test_node(state: AgenticState) -> Dict[str, Any]:
    return _repair_node(state, "test_llm")


def _gate_step(
    state: AgenticState,
    step: str,
    max_retries: int,
) -> Dict[str, Any]:
    status = state.get("step_status", {}).get(step, "pending")
    if status != "error":
        return {"gate_decision": "continue"}

    retries = dict(state.get("retries", {}))
    current = retries.get(step, 0)
    if current < max_retries:
        retries[step] = current + 1
        return {
            "gate_decision": "repair",
            "retries": retries,
        }
    return {"gate_decision": "human_review", "human_review_required": True}


def gate_after_prepare_node(state: AgenticState) -> Dict[str, Any]:
    return _gate_step(state, "prepare", max_retries=0)


def gate_after_main_node(state: AgenticState) -> Dict[str, Any]:
    max_retries = state.get("retries", {}).get("_max_main", 0)
    return _gate_step(state, "main_llm", max_retries=max_retries)


def gate_after_test_node(state: AgenticState) -> Dict[str, Any]:
    max_retries = state.get("retries", {}).get("_max_test", 0)
    return _gate_step(state, "test_llm", max_retries=max_retries)


def gate_after_compare_node(state: AgenticState) -> Dict[str, Any]:
    status = state.get("step_status", {}).get("compare", "pending")
    if status == "error":
        options = state["options"]
        retries = dict(state.get("retries", {}))
        current = retries.get("compare", 0)
        # fixed: Compare-Fehler = der Rechenkern weicht ab -> main neu generieren
        # (mit den Abweichungen als Repair-Kontext). llm: bisheriges Verhalten
        # (Test-Harness reparieren).
        if options.test_mode == "fixed":
            max_retries = retries.get("_max_main", 0)
            repair_target = "repair_main"
        else:
            max_retries = retries.get("_max_test", 0)
            repair_target = "repair_test"
        if current < max_retries:
            retries["compare"] = current + 1
            return {
                "gate_decision": repair_target,
                "retries": retries,
            }
        return {"gate_decision": "human_review", "human_review_required": True}
    return {"gate_decision": "finish"}


def human_review_node(state: AgenticState) -> Dict[str, Any]:
    from rechner_pipeline.orchestrate.dossier import write_run_dossier

    runner = _runner_from_state(state)
    dossier_path = write_run_dossier(
        runner,
        manifest=state.get("manifest"),
        run_status="human_review_required",
        human_review_required=True,
        agentic_state=state,
    )
    print("\n[HUMAN_REVIEW_REQUIRED]")
    for err in state.get("errors", []):
        print(err)
    print(f"Run dossier: {dossier_path}")
    diagnostics_path = state.get("agentic_diagnostics_path")
    if diagnostics_path:
        print(f"Structured diagnostics: {diagnostics_path}")
    for step, path in state.get("repair_artifacts", {}).items():
        print(f"Repair context for {step}: {path}")
    print()
    return {}


def route_from_gate(state: AgenticState) -> str:
    return state.get("gate_decision", "continue")


def build_graph() -> Any:
    try:
        from langgraph.graph import END, START, StateGraph
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "LangGraph is required for the agentic pipeline. "
            "Install it first, e.g. `pip install -e '.[agentic]'`."
        ) from exc

    graph = StateGraph(AgenticState)

    graph.add_node("prepare", prepare_node)
    graph.add_node("gate_prepare", gate_after_prepare_node)
    graph.add_node("main_llm", main_llm_node)
    graph.add_node("repair_main", repair_main_node)
    graph.add_node("gate_main", gate_after_main_node)
    graph.add_node("test_llm", test_llm_node)
    graph.add_node("repair_test", repair_test_node)
    graph.add_node("gate_test", gate_after_test_node)
    graph.add_node("compare", compare_node)
    graph.add_node("gate_compare", gate_after_compare_node)
    graph.add_node("human_review", human_review_node)

    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "gate_prepare")

    graph.add_conditional_edges(
        "gate_prepare",
        route_from_gate,
        {
            "continue": "main_llm",
            "human_review": "human_review",
        },
    )

    graph.add_edge("main_llm", "gate_main")
    graph.add_edge("repair_main", "main_llm")
    graph.add_conditional_edges(
        "gate_main",
        route_from_gate,
        {
            "continue": "test_llm",
            "repair": "repair_main",
            "human_review": "human_review",
        },
    )

    graph.add_edge("test_llm", "gate_test")
    graph.add_edge("repair_test", "test_llm")
    graph.add_conditional_edges(
        "gate_test",
        route_from_gate,
        {
            "continue": "compare",
            "repair": "repair_test",
            "human_review": "human_review",
        },
    )

    graph.add_edge("compare", "gate_compare")
    graph.add_conditional_edges(
        "gate_compare",
        route_from_gate,
        {
            "finish": END,
            "repair_main": "repair_main",  # fixed-Modus: Rechenkern reparieren
            "repair_test": "repair_test",  # llm-Modus: Test-Harness reparieren
            "human_review": "human_review",
        },
    )

    graph.add_edge("human_review", END)
    return graph.compile()
