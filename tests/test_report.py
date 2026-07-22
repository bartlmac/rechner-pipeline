"""Tests for the deterministic run-report renderer (toolbox ``report``).

The renderer is a pure function of the diagnostics ledger: same input files ->
byte-identical Markdown. It is read-only and not a gate.
"""

from __future__ import annotations

import json
from pathlib import Path

from rechner_pipeline.toolbox import report


# --------------------------------------------------------------------------- #
# Fixture builder — a minimal but schema-shaped diagnostics dir
# --------------------------------------------------------------------------- #


def _write(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def _make_diagnostics(tmp_path: Path, *, accepted: bool = True, with_roundtrip: bool = True) -> Path:
    diag = tmp_path / "diagnostics"
    diag.mkdir(parents=True)
    _write(diag / "qa_report.json", {
        "schema_version": 1,
        "created_at": "2026-07-22T08:00:00+00:00",
        "run_id": "diagnostics",
        "decision": "accepted" if accepted else "failed",
        "accepted": accepted,
        "attempts_used": 1,
        "max_attempts": 4,
        "expectation_coverage": "full",
        "qa_contract_path": "qa_contract.json",
        "open_assumptions": [],
        "blocking_warnings": [],
        "dependency_versions": {"python": "3.11.2", "hypothesis": "6.155.5"},
        "generated_file_hashes": {
            "generated/actuarial.py": "a" * 64,
            "generated/commutation.py": "b" * 64,
        },
        "gates": [],
    })
    _write(diag / "extract.gate.json", {
        "gate": "G0.extraction-manifest", "command": "extract", "status": "passed",
        "summary": {"input_bundle": {
            "source_path": "/repo/examples/Tarifrechner_KLV.xlsm",
            "expectation_coverage": "full",
            "coverage_detail": {"scalar_keys_expected": 5, "table_cells_expected": 612},
        }},
    })
    _write(diag / "validate.gate.json", {
        "gate": "G1.file-contract", "command": "validate", "status": "passed",
        "summary": {"extracted_files": ["inputs.py", "params.py", "tafeln.xml",
                                        "commutation.py", "actuarial.py", "test_run.py"],
                    "order_ok": True},
    })
    _write(diag / "security.gate.json", {
        "gate": "G2.static-security", "command": "security", "status": "passed",
        "summary": {"metrics": {"files_scanned": 5, "violations": 0}},
    })
    _write(diag / "conventions.gate.json", {
        "gate": "G3.architecture-conventions", "command": "conventions", "status": "passed",
        "summary": {"metrics": {"edges": 6, "disallowed_edges": 0, "cycles": 0}},
    })
    _write(diag / "golden_master.gate.json", {
        "gate": "G5.golden-master", "command": "golden_master",
        "status": "passed" if accepted else "failed",
        "summary": {"scalars_tested": 5, "table_cells_tested": 612,
                    "deviation_count": 0 if accepted else 2,
                    "deviations": [] if accepted else ["Kalkulation:Bxt fehlt",
                                                       "Kalkulation:Pxt fehlt"],
                    "unmatched_columns": []},
    })
    _write(diag / "algebraic.gate.json", {
        "gate": "G6.algebraic-properties", "command": "algebraic", "status": "passed",
        "summary": {"identities_checked": ["0 <= qx <= 1", "A_x + d*ae_x = 1"],
                    "total_cases": 400, "counterexample_count": 0, "counterexamples": [],
                    "engine": "hypothesis", "engine_version": "6.155.5",
                    "max_examples": 200},
    })
    if with_roundtrip:
        _write(diag / "roundtrip.gate.json", {
            "gate": "G7.roundtrips", "command": "roundtrip", "status": "passed",
            "summary": {"tafeln": {"ok": True},
                        "reextraction": {"ok": True, "drifted": []},
                        "recomputation": {"ok": True, "repeats": 2}},
        })
    return diag


def _render(diag: Path) -> str:
    return report.render(report.load_run(diag), diagnostics_dir_name=diag.name)


# --------------------------------------------------------------------------- #
# Determinism and comparability
# --------------------------------------------------------------------------- #


def test_render_is_deterministic(tmp_path: Path):
    diag = _make_diagnostics(tmp_path)
    assert _render(diag) == _render(diag)


def test_same_ledger_in_other_location_renders_identically(tmp_path: Path):
    a = _make_diagnostics(tmp_path / "runA")
    b = _make_diagnostics(tmp_path / "runB")
    assert _render(a) == _render(b)  # same content, same report -> comparable


# --------------------------------------------------------------------------- #
# Content
# --------------------------------------------------------------------------- #


def test_report_core_facts(tmp_path: Path):
    md = _render(_make_diagnostics(tmp_path))
    assert "# Abnahmebericht — Tarifrechner_KLV.xlsm" in md
    assert "**Verdikt: ANGENOMMEN**" in md
    assert "| G5.golden-master | golden_master | bestanden |" in md
    assert "612 Tabellenzellen" in md
    assert "hypothesis 6.155.5" in md
    assert "| python | 3.11.2 |" in md
    assert "`aaaaaaaaaaaa`" in md  # 12-char hash prefix


def test_failed_run_lists_deviations(tmp_path: Path):
    md = _render(_make_diagnostics(tmp_path, accepted=False))
    assert "**Verdikt: NICHT ANGENOMMEN**" in md
    assert "Kalkulation:Bxt fehlt" in md
    assert "| G5.golden-master | golden_master | nicht bestanden |" in md


def test_missing_gate_is_marked_not_invented(tmp_path: Path):
    md = _render(_make_diagnostics(tmp_path, with_roundtrip=False))
    assert "| G7.roundtrips | roundtrip | nicht vorhanden | — |" in md


def test_report_has_no_meta_commentary(tmp_path: Path):
    md = _render(_make_diagnostics(tmp_path)).lower()
    for banned in ("ehrlich", "honest"):
        assert banned not in md


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def test_cli_writes_out_file(tmp_path: Path):
    diag = _make_diagnostics(tmp_path)
    out = tmp_path / "bericht.md"
    assert report.main(["--diagnostics-dir", str(diag), "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == _render(diag)


def test_cli_missing_dir_exits_2(tmp_path: Path):
    assert report.main(["--diagnostics-dir", str(tmp_path / "nope")]) == 2


def test_cli_missing_qa_report_exits_2(tmp_path: Path):
    empty = tmp_path / "diag"
    empty.mkdir()
    assert report.main(["--diagnostics-dir", str(empty)]) == 2
