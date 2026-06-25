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
        test_mode="llm",
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
        "import requests as rq\n"
        "from pathlib import Path\n"
        "from subprocess import run as run_process\n"
        "import os\n"
        "eval('1 + 1')\n"
        "exec('x = 1')\n"
        "open('secret.txt', 'w')\n"
        "run_process(['echo', 'x'])\n"
        "Path('secret.txt').read_text()\n"
        "rq.get('https://example.invalid')\n"
        "os.system('id')\n"
    )

    violations = scan_python_source(source, Path("test_run_advanced.py"))
    symbols = {item.symbol for item in violations}
    categories = {item.category for item in violations}

    assert {"requests", "pathlib", "subprocess"} <= symbols
    assert {"eval", "exec", "open"} <= symbols  # open hier im Schreib-Modus
    assert "subprocess.run" in symbols
    assert "pathlib.Path.read_text" in symbols
    assert "requests.get" in symbols
    # `import os` allein ist nun erlaubt; ein gefährlicher os-Call bleibt geblockt.
    assert "os" not in symbols
    assert "os.system" in symbols
    assert {"dangerous_import", "dangerous_call", "filesystem_access"} <= categories


def test_static_security_allows_os_path_string_ops() -> None:
    # Muster aus generiertem commutation.py: Pfad zur tafeln.xml bauen.
    source = (
        "import os\n"
        "def _tafeln_xml_path():\n"
        "    here = os.path.dirname(os.path.abspath(__file__))\n"
        "    return os.path.join(here, 'tafeln.xml')\n"
    )

    assert scan_python_source(source, Path("commutation.py")) == []


def test_static_security_still_blocks_dangerous_os_calls() -> None:
    source = "import os\nos.system('id')\nos.remove('x')\nos.popen('ls')\n"

    symbols = {item.symbol for item in scan_python_source(source, Path("x.py"))}

    assert "os" not in symbols  # bloßer Import nicht mehr geflaggt
    assert {"os.system", "os.remove", "os.popen"} <= symbols


def test_static_security_allows_readonly_open_and_glob() -> None:
    # Muster aus generiertem test_run_advanced.py: erwartete Werte lesen.
    source = (
        "import glob\n"
        "import os\n"
        "import json\n"
        "def load(info_dir):\n"
        "    out = {}\n"
        "    for p in sorted(glob.glob(os.path.join(info_dir, '*_scalar.json'))):\n"
        "        with open(p, 'r', encoding='utf-8') as f:\n"
        "            out[p] = json.load(f)\n"
        "    return out\n"
    )

    assert scan_python_source(source, Path("test_run_advanced.py")) == []


def test_static_security_blocks_write_open() -> None:
    for src in (
        "open('x.txt', 'w')\n",
        "open('x.txt', 'a')\n",
        "open('x.txt', mode='w')\n",
        "open('x.txt', 'r+')\n",
        "m = 'w'\nopen('x.txt', m)\n",  # nicht-literal -> konservativ blockiert
    ):
        symbols = {v.symbol for v in scan_python_source(src, Path("x.py"))}
        assert "open" in symbols, src

    # Reines Lesen ist erlaubt.
    assert scan_python_source("open('x.txt')\n", Path("x.py")) == []
    assert scan_python_source("open('x.txt', 'rb')\n", Path("x.py")) == []


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
