"""Tests for the source-neutral ``rechner-pipeline`` CLI (:mod:`rechner_pipeline.cli`).

Covers (§4.1 / §4.2 step 11; §3.3 assurance orchestrator):

* ``--help`` advertises the deterministic gate flow + strict validation and
  carries NO SDK/provider/model/token/reasoning surface;
* the source-neutral options (``--input``/``--adapter``/``--export-backend``/
  ``--strict-manifest-warnings``) exist and ``--excel`` is a compatibility alias;
* no subcommand -> exit 2 (usage/configuration);
* ``assurance --help`` works and documents the ordered gate chain;
* a real ``assurance`` run over a SYNTHETIC generated-dir + KLV extraction runs
  the whole chain and ends with a ``dossier`` (blocked / human-review) verdict;
* the SDK/LangGraph grep over ``src`` finds nothing (steps 9, 10).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List

import pytest

from rechner_pipeline import cli
from rechner_pipeline.toolbox._common import Exit

REPO_ROOT = Path(__file__).resolve().parents[1]
KLV_WORKBOOK = REPO_ROOT / "examples" / "Tarifrechner_KLV.xlsm"

# The forbidden SDK/LangGraph surface (§4.2 steps 9, 10; §5.3 non-goals).
_FORBIDDEN = re.compile(
    r"anthropic|openai|OPENAI_API_KEY|ANTHROPIC_API_KEY|langgraph|StateGraph|"
    r"rechner-pipeline-agentic",
    re.IGNORECASE,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def _write_synthetic_kernel(generated_dir: Path) -> None:
    """Write the six expected files (compilable placeholders, NO real kernel)."""
    generated_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "inputs.py": '"""inputs."""\nVALUE = "inputs"\n',
        "params.py": '"""params."""\nVALUE = "params"\n',
        "tafeln.xml": "<tafeln></tafeln>\n",
        "commutation.py": '"""commutation."""\nVALUE = "commutation"\n',
        "actuarial.py": '"""actuarial."""\nimport commutation\nVALUE = "actuarial"\n',
        "test_run.py": (
            '"""test_run."""\n\n'
            "def golden_master_outputs():\n"
            '    return {"scalars": {}, "tables": {}}\n'
        ),
    }
    for name, body in files.items():
        (generated_dir / name).write_text(body, encoding="utf-8")


# --------------------------------------------------------------------------- #
# --help: source-neutral, no SDK provider path
# --------------------------------------------------------------------------- #


def test_top_help_is_source_neutral(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out

    # Source-neutral options advertised.
    for token in ("--input", "--adapter", "--export-backend", "--strict-manifest-warnings"):
        assert token in out, token
    # Deterministic gate flow + strict validation advertised.
    assert "assurance" in out
    assert "deterministic" in out.lower()
    assert "gate" in out.lower()
    # NO SDK / provider / model / token / reasoning acceptance path.
    assert not _FORBIDDEN.search(out), "help must not advertise an SDK provider path"
    for banned in ("--provider", "--model", "--reasoning", "max_output_tokens", "test-mode", "test_mode"):
        assert banned not in out, banned


def test_excel_is_a_compatibility_alias() -> None:
    parser = cli._build_top_parser()
    ns = parser.parse_args(["--excel", "wb.xlsm"])
    # The alias itself is parsed; main() promotes it onto --input.
    assert ns.excel == "wb.xlsm"
    assert ns.input is None


def test_no_subcommand_exits_usage(capsys: pytest.CaptureFixture[str]) -> None:
    code = cli.main([])
    assert code == Exit.USAGE  # 2
    err = capsys.readouterr().err
    assert "assurance" in err


def test_assurance_help_documents_chain(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["assurance", "--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for gate in (
        "extract",
        "validate",
        "security",
        "conventions",
        "golden_master",
        "algebraic",
        "roundtrip",
        "dossier",
    ):
        assert gate in out, gate
    assert not _FORBIDDEN.search(out)


# --------------------------------------------------------------------------- #
# SDK / LangGraph absence over the target source tree (§4.2 steps 9, 10)
# --------------------------------------------------------------------------- #


def test_src_carries_no_sdk_or_langgraph() -> None:
    hits: List[str] = []
    for path in (REPO_ROOT / "src").rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="replace")
        for n, line in enumerate(text.splitlines(), start=1):
            if _FORBIDDEN.search(line):
                hits.append(f"{path}:{n}: {line.strip()}")
    assert not hits, "forbidden SDK/LangGraph tokens found:\n" + "\n".join(hits)


def test_pyproject_and_requirements_carry_no_sdk() -> None:
    for name in ("pyproject.toml", "requirements.txt", "requirements-dev.txt"):
        path = REPO_ROOT / name
        if not path.is_file():
            continue
        assert not _FORBIDDEN.search(path.read_text(encoding="utf-8")), name


# --------------------------------------------------------------------------- #
# Full assurance chain over a synthetic generated-dir + real KLV extraction
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(not KLV_WORKBOOK.is_file(), reason="KLV example workbook absent")
def test_assurance_chain_ends_with_dossier_verdict(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    generated = tmp_path / "generated"
    info = tmp_path / "info"
    diag = tmp_path / "diag"
    _write_synthetic_kernel(generated)

    code = cli.main(
        [
            "assurance",
            "--repo-root", str(REPO_ROOT),
            "--input", str(KLV_WORKBOOK),
            "--generated-dir", str(generated),
            "--info-dir", str(info),
            "--diagnostics-dir", str(diag),
            "--adapter", "excel",
        ]
    )

    # No real kernel -> golden master cannot match -> dossier blocks the run.
    # The aggregate exit is the dossier verdict (40 = dossier/human-review).
    assert code == Exit.DOSSIER  # 40

    # The chain actually ran: each preceding gate wrote a ledger entry and the
    # dossier produced its acceptance artifacts into --diagnostics-dir (NOT into
    # --generated-dir, whose six-file G1 contract forbids extra siblings).
    assert (diag / "extract.gate.json").is_file()
    assert (diag / "golden_master.gate.json").is_file()
    assert (diag / "run_dossier.json").is_file()
    assert (diag / "qa_report.json").is_file()
    assert not (generated / "run_dossier.json").exists()
    assert not (generated / "qa_report.json").exists()
    # validate (G1) wrote its ledger into the SHARED diagnostics dir (bug 3 fix),
    # not into <generated-dir>/diagnostics.
    assert (diag / "validate.gate.json").is_file()
    assert not (generated / "diagnostics").exists()

    # The final stdout JSON object is the dossier result with a blocked verdict.
    # The synthetic kernel extracts at FULL coverage (real KLV workbook), so the
    # block is an honest gate.not_passed (golden master cannot match the fake
    # kernel) -> decision 'failed', NOT a coverage human-review handoff.
    out_lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]
    last = json.loads(out_lines[-1])
    assert last["command"] == "dossier"
    assert last["status"] == "failed"
    assert last["summary"]["accepted"] is False
    assert any(e["code"] == "gate.not_passed" for e in last["errors"])
