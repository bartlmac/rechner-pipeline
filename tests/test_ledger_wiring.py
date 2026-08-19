"""Ledger wiring of the ``extract`` (G0) gate command.

Current scope: ``extract`` is the only gate command covered here. The
module asserts that it

* accepts ``--diagnostics-dir``;
* writes an ``extract.gate.json`` ledger entry into that dir on BOTH the
  pass and the fail path, carrying the gate id ``G0.extraction-manifest``
  and the matching status;
* keeps stdout JSON-pure — the ledger is a side artifact to disk, written by
  the command body, separate from the single stdout JSON emitted by
  ``run_command``.

The command is driven in-process via ``main(argv) -> ToolboxResult`` so the
structured result and the on-disk ledger can be asserted without spawning a
process.

Knoten: system/assurance
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from rechner_pipeline.gates import extract as extract_cmd
from rechner_pipeline.gates._common import GATE_LEDGER_SUFFIX, load_gate_ledger

REPO_ROOT = Path(__file__).resolve().parents[1]
KLV = REPO_ROOT / "tests" / "fixtures" / "Tarifrechner_KLV_TG2012.xlsm"


# --------------------------------------------------------------------------- #
# Fixture helpers
# --------------------------------------------------------------------------- #






def _ledger_path(diag_dir: Path, command: str) -> Path:
    return diag_dir / f"{command}{GATE_LEDGER_SUFFIX}"


def _load_ledger(diag_dir: Path, command: str) -> dict:
    return json.loads(_ledger_path(diag_dir, command).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# validate (G1) — pass and fail paths
# --------------------------------------------------------------------------- #








# --------------------------------------------------------------------------- #
# security (G2) — pass and fail paths
# --------------------------------------------------------------------------- #






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




# --------------------------------------------------------------------------- #
# stdout purity — main() must not leak the ledger (or anything) to stdout
# --------------------------------------------------------------------------- #


def test_ledger_write_does_not_leak_to_stdout(tmp_path: Path):
    """main() schreibt den Ledger auf die Platte, nicht nach stdout.

    Der Contract gehoert run_command: es gibt genau EINE Ausgabe je Lauf.
    Geprueft am Fehlerpfad von extract — er schreibt garantiert einen
    Ledger und braucht keine Excel-Datei.
    """
    diag = tmp_path / "diag"

    buf = io.StringIO()
    with redirect_stdout(buf):
        result = extract_cmd.main(
            [
                "--repo-root", str(REPO_ROOT),
                "--input", str(tmp_path / "fehlt.xlsm"),
                "--out-dir", str(tmp_path / "out"),
                "--diagnostics-dir", str(diag),
            ]
        )

    assert result.exit_code != 0
    assert buf.getvalue() == ""
    assert _ledger_path(diag, "extract").is_file()
