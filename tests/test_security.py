"""Tests for the static security gate (G2): scanner rules + toolbox command.

Covers the AS-IS rule set (preserved verbatim) plus the EXTENSION families
required by MIGRATION.md §3.5 G2 (nondeterministic time/random/environment,
swallowed exceptions, generated-test self-approval) and the §3.3 toolbox
contract for the `security` command (single JSON stdout object, exit 21).
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from rechner_pipeline.qa.security import (
    GATE_VERSION,
    StaticSecurityError,
    raise_for_violations,
    scan_python_source,
    security_report,
)
from rechner_pipeline.toolbox import security as security_cmd
from rechner_pipeline.toolbox._common import Exit, run_command


def _symbols(src: str, name: str = "x.py") -> set[str]:
    return {v.symbol for v in scan_python_source(src, Path(name))}


def _categories(src: str, name: str = "x.py") -> set[str]:
    return {v.category for v in scan_python_source(src, Path(name))}


# --------------------------------------------------------------------------- #
# AS-IS rules (preserved verbatim behavior)
# --------------------------------------------------------------------------- #


def test_allows_plain_calculation_and_sys_import() -> None:
    source = (
        "import math\n"
        "import sys\n"
        "def present_value(x):\n"
        "    print('debug', file=sys.stderr)\n"
        "    return math.exp(-x)\n"
    )
    assert scan_python_source(source, Path("actuarial.py")) == []


def test_detects_dangerous_imports_and_calls() -> None:
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
    symbols = {v.symbol for v in violations}
    categories = {v.category for v in violations}

    assert {"requests", "pathlib", "subprocess"} <= symbols
    assert {"eval", "exec", "open"} <= symbols
    assert "subprocess.run" in symbols
    assert "pathlib.Path.read_text" in symbols
    assert "requests.get" in symbols
    assert "os" not in symbols  # bare import os is allowed
    assert "os.system" in symbols
    assert {"dangerous_import", "dangerous_call", "filesystem_access"} <= categories


def test_allows_os_path_string_ops() -> None:
    source = (
        "import os\n"
        "def _tafeln_xml_path():\n"
        "    here = os.path.dirname(os.path.abspath(__file__))\n"
        "    return os.path.join(here, 'tafeln.xml')\n"
    )
    assert scan_python_source(source, Path("commutation.py")) == []


def test_still_blocks_dangerous_os_calls() -> None:
    symbols = _symbols("import os\nos.system('id')\nos.remove('x')\nos.popen('ls')\n")
    assert "os" not in symbols
    assert {"os.system", "os.remove", "os.popen"} <= symbols


def test_allows_readonly_open_and_glob() -> None:
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


def test_blocks_write_open() -> None:
    for src in (
        "open('x.txt', 'w')\n",
        "open('x.txt', 'a')\n",
        "open('x.txt', mode='w')\n",
        "open('x.txt', 'r+')\n",
        "m = 'w'\nopen('x.txt', m)\n",
    ):
        assert "open" in _symbols(src), src
    assert scan_python_source("open('x.txt')\n", Path("x.py")) == []
    assert scan_python_source("open('x.txt', 'rb')\n", Path("x.py")) == []


def test_reports_syntax_errors() -> None:
    violations = scan_python_source("def broken(:\n", Path("test_run_advanced.py"))
    assert violations[0].category == "syntax_error"


# --------------------------------------------------------------------------- #
# EXTENSION: nondeterministic (time / random / environment)
# --------------------------------------------------------------------------- #


def test_blocks_random_import_and_call() -> None:
    cats = _categories("import random\nx = random.random()\n")
    assert "nondeterministic" in cats
    syms = _symbols("import random\nx = random.random()\n")
    assert "random" in syms
    assert "random.random" in syms


def test_blocks_time_now() -> None:
    syms = _symbols("import time\nt = time.time()\n")
    assert "time" in syms
    assert "time.time" in syms
    assert _categories("import time\nt = time.time()\n") == {"nondeterministic"}


def test_blocks_datetime_now_various_imports() -> None:
    # import datetime; datetime.datetime.now()
    assert "nondeterministic" in _categories("import datetime\nd = datetime.datetime.now()\n")
    # from datetime import datetime; datetime.now()
    assert "nondeterministic" in _categories(
        "from datetime import datetime\nd = datetime.now()\n"
    )
    # aliased
    assert "nondeterministic" in _categories(
        "from datetime import datetime as dt\nd = dt.now()\n"
    )
    # date.today()
    assert "nondeterministic" in _categories(
        "from datetime import date\nd = date.today()\n"
    )


def test_blocks_os_environ_and_getenv() -> None:
    assert "nondeterministic" in _categories("import os\nv = os.environ['X']\n")
    assert "nondeterministic" in _categories("import os\nv = os.environ.get('X')\n")
    assert "nondeterministic" in _categories("import os\nv = os.getenv('X')\n")


def test_allows_deterministic_datetime_construction() -> None:
    # A fixed datetime literal is deterministic and must be allowed.
    src = "import datetime\nd = datetime.datetime(2020, 1, 1)\n"
    assert _categories(src) == set()


# --------------------------------------------------------------------------- #
# EXTENSION: swallowed exceptions
# --------------------------------------------------------------------------- #


def test_blocks_bare_except() -> None:
    src = "try:\n    x = compute()\nexcept:\n    pass\n"
    assert "swallowed_exception" in _categories(src)


def test_blocks_except_exception_pass() -> None:
    src = "try:\n    x = compute()\nexcept Exception:\n    pass\n"
    assert "swallowed_exception" in _categories(src)


def test_allows_except_that_reraises() -> None:
    src = (
        "try:\n"
        "    x = compute()\n"
        "except ValueError as e:\n"
        "    raise RuntimeError('bad') from e\n"
    )
    assert "swallowed_exception" not in _categories(src)


def test_allows_narrow_except_doing_work() -> None:
    src = (
        "def f(x):\n"
        "    try:\n"
        "        return 1 / x\n"
        "    except ZeroDivisionError:\n"
        "        return 0.0\n"
    )
    assert "swallowed_exception" not in _categories(src)


# --------------------------------------------------------------------------- #
# EXTENSION: generated-test self-approval
# --------------------------------------------------------------------------- #


def test_blocks_assert_true_self_approval() -> None:
    src = "def test_values():\n    assert True\n"
    assert "self_approval" in _categories(src)


def test_blocks_vacuous_test() -> None:
    src = "def test_nothing():\n    pass\n"
    assert "self_approval" in _categories(src)


def test_allows_real_comparison_test() -> None:
    src = (
        "def test_pv():\n"
        "    result = present_value(0.5)\n"
        "    assert result == 0.6065306597126334\n"
    )
    assert "self_approval" not in _categories(src)


# --------------------------------------------------------------------------- #
# Report + error helpers
# --------------------------------------------------------------------------- #


def test_security_report_shape() -> None:
    violations = scan_python_source("import requests\n", Path("a.py"))
    report = security_report(checked_files=[Path("a.py")], violations=violations)
    assert report["status"] == "failed"
    assert report["checked_files"] == ["a.py"]
    assert report["violations"][0]["category"] == "dangerous_import"
    assert "snippet" in report["violations"][0]


def test_raise_for_violations() -> None:
    violations = scan_python_source("import subprocess\n", Path("a.py"))
    with pytest.raises(StaticSecurityError, match="subprocess"):
        raise_for_violations(violations)
    raise_for_violations([])  # no raise on empty


# --------------------------------------------------------------------------- #
# Toolbox command contract (§3.3)
# --------------------------------------------------------------------------- #


def _run(argv: list[str]) -> tuple[int, dict]:
    buf = io.StringIO()
    # run_command redirects stdout->stderr during the body and emits the single
    # JSON object on the real stdout afterwards.
    with redirect_stdout(buf):
        exit_code = run_command(security_cmd.main, argv)
    payload = json.loads(buf.getvalue())
    return exit_code, payload


def test_command_passes_clean_dir(tmp_path: Path) -> None:
    gen = tmp_path / "generated"
    gen.mkdir()
    (gen / "actuarial.py").write_text(
        "import math\ndef pv(x):\n    return math.exp(-x)\n", encoding="utf-8"
    )
    diag = tmp_path / "diag"
    exit_code, payload = _run(
        ["--generated-dir", str(gen), "--diagnostics-dir", str(diag)]
    )
    assert exit_code == Exit.OK
    assert payload["status"] == "passed"
    assert payload["command"] == "security"
    assert payload["gate"] == "G2.static-security"
    assert payload["gate_version"] == GATE_VERSION
    assert payload["summary"]["violation_count"] == 0
    assert payload["summary"]["checked_count"] == 1
    report = json.loads((diag / "static_security_report.json").read_text("utf-8"))
    assert report["status"] == "passed"


def test_command_blocks_with_exit_21(tmp_path: Path) -> None:
    gen = tmp_path / "generated"
    gen.mkdir()
    (gen / "evil.py").write_text(
        "import subprocess\nsubprocess.run(['echo', 'x'])\n", encoding="utf-8"
    )
    exit_code, payload = _run(["--generated-dir", str(gen)])
    assert exit_code == Exit.SECURITY  # 21
    assert payload["status"] == "failed"
    assert payload["summary"]["violation_count"] >= 1
    assert payload["errors"], "errors must be present and non-empty when blocking"
    assert payload["repair_hints"], "repair hints must guide repair"
    first = payload["errors"][0]
    assert {"code", "symbol", "path", "line", "column", "message"} <= set(first)


def test_command_usage_error_without_generated_dir() -> None:
    exit_code, payload = _run([])
    assert exit_code == Exit.USAGE
    assert payload["status"] == "failed"


def test_command_diagnostics_dir_defaults_to_generated(tmp_path: Path) -> None:
    gen = tmp_path / "generated"
    gen.mkdir()
    (gen / "ok.py").write_text("y = 1\n", encoding="utf-8")
    exit_code, payload = _run(["--generated-dir", str(gen)])
    assert exit_code == Exit.OK
    assert (gen / "static_security_report.json").exists()


def test_command_request_json_merges_flags(tmp_path: Path) -> None:
    gen = tmp_path / "generated"
    gen.mkdir()
    (gen / "ok.py").write_text("y = 1\n", encoding="utf-8")
    req = json.dumps({"generated_dir": str(gen)})
    import sys

    old_stdin = sys.stdin
    sys.stdin = io.StringIO(req)
    try:
        exit_code, payload = _run(["--request-json", "-"])
    finally:
        sys.stdin = old_stdin
    assert exit_code == Exit.OK
    assert payload["summary"]["checked_count"] == 1
