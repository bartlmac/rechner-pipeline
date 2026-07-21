"""Tests for the gate-result ledger wiring of the wave-1 gate commands.

The reviewer found that ``extract`` (G0), ``validate`` (G1) and ``security``
(G2) did not emit the ``<command>.gate.json`` ledger entries that ``dossier``
(G8) aggregates — so ``gates_present`` never counted them. This module asserts
that all three commands:

* accept ``--diagnostics-dir`` (previously ``extract``/``validate`` rejected it
  with argparse exit 2);
* write a §6.8.2 ``<command>.gate.json`` ledger entry into that dir on BOTH the
  pass and fail paths;
* produce entries that round-trip through
  :func:`rechner_pipeline.orchestrate.dossier.load_gate_ledger` with no read
  errors and the correct gate ids (G0/G1/G2);
* keep stdout JSON-pure — the ledger is a side artifact to disk, written by the
  command body, separate from the single stdout JSON emitted by ``run_command``.

The commands are driven in-process via ``main(argv) -> ToolboxResult`` so the
structured result and the on-disk ledger can be asserted without spawning a
process.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from typing import Iterable

import pytest

from rechner_pipeline.generate.output import EXPECTED_MAIN_OUTPUT_FILES
from rechner_pipeline.orchestrate.dossier import load_gate_ledger
from rechner_pipeline.toolbox import extract as extract_cmd
from rechner_pipeline.toolbox import security as security_cmd
from rechner_pipeline.toolbox import validate as validate_cmd
from rechner_pipeline.toolbox._common import GATE_LEDGER_SUFFIX

REPO_ROOT = Path(__file__).resolve().parents[1]
KLV = REPO_ROOT / "examples" / "Tarifrechner_KLV.xlsm"


# --------------------------------------------------------------------------- #
# Fixture helpers
# --------------------------------------------------------------------------- #


def _content(name: str) -> str:
    if name == "tafeln.xml":
        return "<tafeln></tafeln>\n"
    if name == "test_run.py":
        return (
            '"""Generated test_run.py."""\n\n'
            "def golden_master_outputs():\n"
            '    return {"scalars": {}, "tables": {}}\n'
        )
    return f'"""Generated {name}."""\nVALUE = {name!r}\n'


def _write_valid_generated(
    base: Path, *, names: Iterable[str] = EXPECTED_MAIN_OUTPUT_FILES
) -> Path:
    """Write a contract-valid six-file generated dir under ``base``."""
    gen = base / "generated"
    gen.mkdir(parents=True, exist_ok=True)
    for name in names:
        (gen / name).write_text(_content(name), encoding="utf-8")
    return gen


def _ledger_path(diag_dir: Path, command: str) -> Path:
    return diag_dir / f"{command}{GATE_LEDGER_SUFFIX}"


def _load_ledger(diag_dir: Path, command: str) -> dict:
    return json.loads(_ledger_path(diag_dir, command).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# validate (G1) — pass and fail paths
# --------------------------------------------------------------------------- #


def test_validate_accepts_diagnostics_dir_and_writes_ledger_on_pass(tmp_path: Path):
    gen = _write_valid_generated(tmp_path)
    diag = tmp_path / "diag"
    info = tmp_path / "info"
    info.mkdir()

    result = validate_cmd.main(
        [
            "--repo-root",
            str(tmp_path),
            "--generated-dir",
            str(gen),
            "--info-dir",
            str(info),
            "--diagnostics-dir",
            str(diag),
        ]
    )

    assert result.exit_code == 0
    ledger = _load_ledger(diag, "validate")
    assert ledger["gate"] == "G1.file-contract"
    assert ledger["command"] == "validate"
    assert ledger["status"] == "passed"
    assert ledger["summary"]["exit_code"] == 0


def test_validate_writes_ledger_on_fail(tmp_path: Path):
    # Empty generated dir -> the six-file contract fails (exit 20).
    gen = tmp_path / "generated"
    gen.mkdir()
    diag = tmp_path / "diag"
    info = tmp_path / "info"
    info.mkdir()

    result = validate_cmd.main(
        [
            "--repo-root",
            str(tmp_path),
            "--generated-dir",
            str(gen),
            "--info-dir",
            str(info),
            "--diagnostics-dir",
            str(diag),
        ]
    )

    assert result.exit_code != 0
    ledger = _load_ledger(diag, "validate")
    assert ledger["gate"] == "G1.file-contract"
    assert ledger["status"] == "failed"
    assert ledger["summary"]["exit_code"] == result.exit_code


def test_validate_defaults_diagnostics_dir_under_generated(tmp_path: Path):
    """Omitting --diagnostics-dir defaults to <generated-dir>/diagnostics."""
    gen = _write_valid_generated(tmp_path)
    info = tmp_path / "info"
    info.mkdir()

    result = validate_cmd.main(
        [
            "--repo-root",
            str(tmp_path),
            "--generated-dir",
            str(gen),
            "--info-dir",
            str(info),
        ]
    )

    assert result.exit_code == 0
    assert _ledger_path(gen / "diagnostics", "validate").is_file()


# --------------------------------------------------------------------------- #
# security (G2) — pass and fail paths
# --------------------------------------------------------------------------- #


def test_security_writes_ledger_on_pass(tmp_path: Path):
    gen = _write_valid_generated(tmp_path)
    diag = tmp_path / "diag"

    result = security_cmd.main(
        ["--generated-dir", str(gen), "--diagnostics-dir", str(diag)]
    )

    assert result.exit_code == 0
    ledger = _load_ledger(diag, "security")
    assert ledger["gate"] == "G2.static-security"
    assert ledger["command"] == "security"
    assert ledger["status"] == "passed"


def test_security_writes_ledger_on_fail(tmp_path: Path):
    # A dangerous import trips the static security gate (exit 21).
    gen = _write_valid_generated(tmp_path)
    (gen / "actuarial.py").write_text(
        '"""bad."""\nimport os\nos.system("echo hi")\n', encoding="utf-8"
    )
    diag = tmp_path / "diag"

    result = security_cmd.main(
        ["--generated-dir", str(gen), "--diagnostics-dir", str(diag)]
    )

    assert result.exit_code != 0
    ledger = _load_ledger(diag, "security")
    assert ledger["gate"] == "G2.static-security"
    assert ledger["status"] == "failed"
    assert ledger["summary"]["exit_code"] == result.exit_code


# --------------------------------------------------------------------------- #
# extract (G0) — uses the KLV workbook when available
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(not KLV.exists(), reason="KLV example workbook missing")
def test_extract_writes_ledger_on_pass(tmp_path: Path):
    pytest.importorskip("openpyxl")
    pytest.importorskip("oletools")
    pytest.importorskip("pandas")
    out_dir = tmp_path / "klv_info"
    diag = tmp_path / "diag"

    result = extract_cmd.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--input",
            str(KLV),
            "--out-dir",
            str(out_dir),
            "--adapter",
            "excel",
            "--export-backend",
            "openpyxl",
            "--diagnostics-dir",
            str(diag),
        ]
    )

    assert result.exit_code == 0
    ledger = _load_ledger(diag, "extract")
    assert ledger["gate"] == "G0.extraction-manifest"
    assert ledger["command"] == "extract"
    assert ledger["status"] == "passed"


def test_extract_writes_ledger_on_fail_missing_source(tmp_path: Path):
    """extract resolves G0 from the dossier catalogue even on the fail path."""
    diag = tmp_path / "diag"

    result = extract_cmd.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--input",
            str(tmp_path / "does_not_exist.xlsm"),
            "--out-dir",
            str(tmp_path / "out"),
            "--diagnostics-dir",
            str(diag),
        ]
    )

    assert result.exit_code != 0
    ledger = _load_ledger(diag, "extract")
    assert ledger["gate"] == "G0.extraction-manifest"
    assert ledger["status"] == "failed"


# --------------------------------------------------------------------------- #
# Cross-command round-trip through the dossier loader
# --------------------------------------------------------------------------- #


def test_three_gates_round_trip_through_dossier_loader(tmp_path: Path):
    """validate + security into one diag dir -> loader sees G1 and G2 cleanly."""
    gen = _write_valid_generated(tmp_path)
    diag = tmp_path / "diag"
    info = tmp_path / "info"
    info.mkdir()

    validate_cmd.main(
        [
            "--repo-root",
            str(tmp_path),
            "--generated-dir",
            str(gen),
            "--info-dir",
            str(info),
            "--diagnostics-dir",
            str(diag),
        ]
    )
    security_cmd.main(
        ["--generated-dir", str(gen), "--diagnostics-dir", str(diag)]
    )

    entries, read_errors = load_gate_ledger(diag)
    assert read_errors == []
    gates = {e.gate for e in entries}
    assert {"G1.file-contract", "G2.static-security"} <= gates
    for entry in entries:
        assert entry.validate() == []


# --------------------------------------------------------------------------- #
# stdout purity — main() must not leak the ledger (or anything) to stdout
# --------------------------------------------------------------------------- #


def test_ledger_write_does_not_leak_to_stdout(tmp_path: Path):
    """Driving main() in-process writes the ledger to disk, not to stdout."""
    gen = _write_valid_generated(tmp_path)
    diag = tmp_path / "diag"

    buf = io.StringIO()
    with redirect_stdout(buf):
        result = security_cmd.main(
            ["--generated-dir", str(gen), "--diagnostics-dir", str(diag)]
        )

    assert result.exit_code == 0
    # main() itself emits nothing to stdout; run_command owns the single emit.
    assert buf.getvalue() == ""
    assert _ledger_path(diag, "security").is_file()
