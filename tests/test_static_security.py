from __future__ import annotations

import json
from pathlib import Path

import pytest

from rechner_pipeline.orchestrate.runner import PipelineOptions, PipelineRunner
from rechner_pipeline.qa.security import StaticSecurityError, scan_python_source


def _options() -> PipelineOptions:
    return PipelineOptions(
        model="test-model",
        skip_export=True,
        skip_main_llm=True,
        skip_test_llm=True,
        skip_compare_run=False,
        main_max_chars_per_file=100,
        main_max_total_chars=100,
        test_max_chars_per_file=100,
        test_max_total_chars=100,
        reasoning_effort="low",
    )


def test_static_security_allows_plain_calculation_and_sys_import() -> None:
    source = (
        "import math\n"
        "import sys\n"
        "def present_value(x):\n"
        "    print('debug', file=sys.stderr)\n"
        "    return math.exp(-x)\n"
    )

    assert scan_python_source(source, Path("actuarial.py")) == []


def test_static_security_detects_dangerous_imports_and_calls() -> None:
    source = (
        "import os\n"
        "import requests as rq\n"
        "from pathlib import Path\n"
        "from subprocess import run as run_process\n"
        "eval('1 + 1')\n"
        "exec('x = 1')\n"
        "open('secret.txt')\n"
        "run_process(['echo', 'x'])\n"
        "Path('secret.txt').read_text()\n"
        "rq.get('https://example.invalid')\n"
    )

    violations = scan_python_source(source, Path("test_run_advanced.py"))
    symbols = {item.symbol for item in violations}
    categories = {item.category for item in violations}

    assert {"os", "requests", "pathlib", "subprocess"} <= symbols
    assert {"eval", "exec", "open"} <= symbols
    assert "subprocess.run" in symbols
    assert "pathlib.Path.read_text" in symbols
    assert "requests.get" in symbols
    assert {"dangerous_import", "dangerous_call", "filesystem_access"} <= categories


def test_static_security_reports_syntax_errors() -> None:
    violations = scan_python_source("def broken(:\n", Path("test_run_advanced.py"))

    assert violations[0].category == "syntax_error"


def test_run_compare_blocks_unsafe_generated_code_before_execution(tmp_path: Path) -> None:
    generated_dir = tmp_path / "generated"
    generated_dir.mkdir()
    marker_path = generated_dir / "marker.txt"
    (generated_dir / "test_run_advanced.py").write_text(
        f"open({str(marker_path)!r}, 'w').write('executed')\n",
        encoding="utf-8",
    )

    runner = PipelineRunner(repo_root=tmp_path, options=_options())

    with pytest.raises(RuntimeError, match="Static security check blocked"):
        runner.run_compare()

    assert not marker_path.exists()
    assert not runner.compare_result_path.exists()
    report = json.loads(runner.static_security_report_path.read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert report["violations"][0]["symbol"] == "open"


def test_run_static_security_check_raises_direct_error(tmp_path: Path) -> None:
    generated_dir = tmp_path / "generated"
    generated_dir.mkdir()
    (generated_dir / "actuarial.py").write_text(
        "import subprocess\nsubprocess.run(['echo', 'x'])\n",
        encoding="utf-8",
    )

    runner = PipelineRunner(repo_root=tmp_path, options=_options())

    with pytest.raises(StaticSecurityError, match="subprocess"):
        runner.run_static_security_check()
