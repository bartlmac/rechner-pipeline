"""Tests for the architecture / import-convention gate (G3): AST engine rules +
the ``conventions`` toolbox command.

Covers the §6.7 allowed-import-graph enforcement (only ``actuarial -> commutation``
among the actuarial layers; the back-edge and every other disallowed edge fail),
circular imports, function-local imports, ``try/except ImportError``,
``TYPE_CHECKING`` tricks, conservative ``lru_cache`` hashability, and the §3.3
toolbox contract for the command (single JSON stdout object, exit 22, ledger).
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from rechner_pipeline.orchestrate.dossier import load_gate_ledger
from rechner_pipeline.qa.conventions import (
    GATE_VERSION,
    scan_conventions,
)
from rechner_pipeline.toolbox import conventions as conventions_cmd
from rechner_pipeline.toolbox._common import Exit, run_command


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _categories(*files: tuple[str, str]) -> set[str]:
    return {v.category for v in scan_conventions(files).violations}


# A CLEAN, spec-compliant 6-file generated set (correct layering, hashable cache).
CLEAN_FILES = {
    "inputs.py": "import math\n\nclass ModelPoint:\n    age: int = 30\n",
    "params.py": "import math\nfrom inputs import ModelPoint\n\nI = 0.0125\n",
    "commutation.py": (
        "import math\n"
        "from functools import lru_cache\n"
        "from inputs import ModelPoint\n"
        "from params import I\n\n"
        "@lru_cache(maxsize=None)\n"
        "def D_x(x: int) -> float:\n"
        "    return (1.0 + I) ** (-x)\n"
    ),
    "actuarial.py": (
        "import math\n"
        "from params import I\n"
        "from commutation import D_x\n\n"
        "def A_x(x: int) -> float:\n"
        "    return D_x(x)\n"
    ),
    "test_run.py": (
        "from actuarial import A_x\n"
        "from commutation import D_x\n\n"
        "def golden_master_outputs():\n"
        "    return {'scalars': {'A30': A_x(30)}, 'tables': {}}\n"
    ),
}


def _write_set(directory: Path, files: dict[str, str]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    for name, src in files.items():
        (directory / name).write_text(src, encoding="utf-8")
    (directory / "tafeln.xml").write_text("<tafeln/>\n", encoding="utf-8")
    return directory


# --------------------------------------------------------------------------- #
# Engine: clean set passes
# --------------------------------------------------------------------------- #


def test_clean_set_has_no_violations() -> None:
    report = scan_conventions(tuple(CLEAN_FILES.items()))
    assert report.violations == []
    assert report.import_graph["actuarial"] == ["commutation", "params"]
    assert report.import_graph["commutation"] == ["inputs", "params"]
    assert report.cycles == []


# --------------------------------------------------------------------------- #
# Engine: per-rule failures
# --------------------------------------------------------------------------- #


def test_back_edge_commutation_to_actuarial_fails() -> None:
    files = dict(CLEAN_FILES)
    files["commutation.py"] = (
        "from inputs import ModelPoint\n"
        "from params import I\n"
        "from actuarial import A_x\n"  # forbidden back-edge
    )
    cats = _categories(*files.items())
    assert "disallowed_edge" in cats


def test_arbitrary_disallowed_edge_fails() -> None:
    # inputs.py may import stdlib only; importing params is forbidden.
    files = dict(CLEAN_FILES)
    files["inputs.py"] = "from params import I\nclass ModelPoint:\n    pass\n"
    report = scan_conventions(tuple(files.items()))
    edges = {(e["from"], e["to"]) for e in report.layer_edges if not e["allowed"]}
    assert ("inputs", "params") in edges
    assert "disallowed_edge" in {v.category for v in report.violations}


def test_circular_import_detected() -> None:
    files = dict(CLEAN_FILES)
    # params -> commutation -> params  (params importing commutation is itself
    # disallowed, but the cycle must ALSO be reported).
    files["params.py"] = "from commutation import D_x\nI = 0.0125\n"
    report = scan_conventions(tuple(files.items()))
    assert report.cycles  # at least one cycle
    assert "circular_import" in {v.category for v in report.violations}


def test_function_local_import_fails() -> None:
    files = dict(CLEAN_FILES)
    files["actuarial.py"] = (
        "from params import I\n"
        "def A_x(x):\n"
        "    from commutation import D_x\n"  # function-local import
        "    return D_x(x)\n"
    )
    cats = _categories(*files.items())
    assert "function_local_import" in cats


def test_try_except_importerror_fails() -> None:
    files = dict(CLEAN_FILES)
    files["params.py"] = (
        "from inputs import ModelPoint\n"
        "try:\n"
        "    import numpy\n"
        "except ImportError:\n"
        "    numpy = None\n"
        "I = 0.0125\n"
    )
    cats = _categories(*files.items())
    assert "try_except_importerror" in cats


def test_modulenotfounderror_also_caught() -> None:
    files = dict(CLEAN_FILES)
    files["params.py"] = (
        "from inputs import ModelPoint\n"
        "try:\n"
        "    import numpy\n"
        "except ModuleNotFoundError:\n"
        "    numpy = None\n"
        "I = 0.0125\n"
    )
    assert "try_except_importerror" in _categories(*files.items())


def test_type_checking_trick_fails() -> None:
    files = dict(CLEAN_FILES)
    files["actuarial.py"] = (
        "from typing import TYPE_CHECKING\n"
        "from params import I\n"
        "from commutation import D_x\n"
        "if TYPE_CHECKING:\n"
        "    from inputs import ModelPoint\n"
        "def A_x(x):\n"
        "    return D_x(x)\n"
    )
    cats = _categories(*files.items())
    assert "type_checking_trick" in cats


def test_lru_cache_unhashable_arg_fails() -> None:
    files = dict(CLEAN_FILES)
    files["commutation.py"] = (
        "from functools import lru_cache\n"
        "from inputs import ModelPoint\n"
        "from params import I\n"
        "@lru_cache\n"
        "def D_x(mp: ModelPoint) -> float:\n"  # ModelPoint not provably hashable
        "    return 1.0\n"
    )
    cats = _categories(*files.items())
    assert "unhashable_lru_cache" in cats


def test_lru_cache_unannotated_arg_fails() -> None:
    # Unknown hashability must FAIL (conservative), not silently pass.
    files = dict(CLEAN_FILES)
    files["commutation.py"] = (
        "from functools import lru_cache\n"
        "from inputs import ModelPoint\n"
        "from params import I\n"
        "@lru_cache(maxsize=None)\n"
        "def D_x(x):\n"  # no annotation -> unknown hashability
        "    return float(x)\n"
    )
    assert "unhashable_lru_cache" in _categories(*files.items())


def test_lru_cache_dict_annotation_fails() -> None:
    files = dict(CLEAN_FILES)
    files["commutation.py"] = (
        "from functools import lru_cache\n"
        "from typing import Dict\n"
        "from inputs import ModelPoint\n"
        "from params import I\n"
        "@lru_cache\n"
        "def D_x(table: Dict[int, float]) -> float:\n"
        "    return 1.0\n"
    )
    assert "unhashable_lru_cache" in _categories(*files.items())


def test_lru_cache_hashable_args_passes() -> None:
    files = dict(CLEAN_FILES)
    files["commutation.py"] = (
        "from functools import lru_cache\n"
        "from typing import Optional\n"
        "from inputs import ModelPoint\n"
        "from params import I\n"
        "@lru_cache(maxsize=None)\n"
        "def D_x(x: int, key: Optional[str] = None) -> float:\n"
        "    return float(x)\n"
    )
    assert "unhashable_lru_cache" not in _categories(*files.items())


# --------------------------------------------------------------------------- #
# Fix 2: conservative lru_cache tuple hashability (bare tuple = UNKNOWN = FAIL)
# --------------------------------------------------------------------------- #


def test_lru_cache_bare_tuple_fails() -> None:
    # A bare untyped `tuple` arg has UNKNOWN element hashability -> FAIL.
    files = dict(CLEAN_FILES)
    files["commutation.py"] = (
        "from functools import lru_cache\n"
        "from inputs import ModelPoint\n"
        "from params import I\n"
        "@lru_cache\n"
        "def D_x(key: tuple) -> float:\n"
        "    return 1.0\n"
    )
    assert "unhashable_lru_cache" in _categories(*files.items())


def test_lru_cache_bare_typing_tuple_fails() -> None:
    # Bare `Tuple` (typing alias, no element types) is also UNKNOWN -> FAIL.
    files = dict(CLEAN_FILES)
    files["commutation.py"] = (
        "from functools import lru_cache\n"
        "from typing import Tuple\n"
        "from inputs import ModelPoint\n"
        "from params import I\n"
        "@lru_cache\n"
        "def D_x(key: Tuple) -> float:\n"
        "    return 1.0\n"
    )
    assert "unhashable_lru_cache" in _categories(*files.items())


def test_lru_cache_typed_hashable_tuple_passes() -> None:
    # Tuple[int, ...] of provably-hashable element types is OK (no false-positive).
    files = dict(CLEAN_FILES)
    files["commutation.py"] = (
        "from functools import lru_cache\n"
        "from typing import Tuple\n"
        "from inputs import ModelPoint\n"
        "from params import I\n"
        "@lru_cache(maxsize=None)\n"
        "def D_x(key: Tuple[int, ...]) -> float:\n"
        "    return 1.0\n"
    )
    assert "unhashable_lru_cache" not in _categories(*files.items())


def test_lru_cache_typed_heterogeneous_tuple_passes() -> None:
    # Tuple[int, str] of hashable elements is OK.
    files = dict(CLEAN_FILES)
    files["commutation.py"] = (
        "from functools import lru_cache\n"
        "from typing import Tuple\n"
        "from inputs import ModelPoint\n"
        "from params import I\n"
        "@lru_cache(maxsize=None)\n"
        "def D_x(key: Tuple[int, str]) -> float:\n"
        "    return 1.0\n"
    )
    assert "unhashable_lru_cache" not in _categories(*files.items())


def test_lru_cache_builtin_typed_tuple_passes() -> None:
    # PEP 585 builtin `tuple[str, ...]` of hashable elements is OK.
    files = dict(CLEAN_FILES)
    files["commutation.py"] = (
        "from functools import lru_cache\n"
        "from inputs import ModelPoint\n"
        "from params import I\n"
        "@lru_cache(maxsize=None)\n"
        "def D_x(key: tuple[str, ...]) -> float:\n"
        "    return 1.0\n"
    )
    assert "unhashable_lru_cache" not in _categories(*files.items())


def test_lru_cache_tuple_of_unhashable_element_fails() -> None:
    # Tuple[list, ...] -- the element type is unhashable -> FAIL.
    files = dict(CLEAN_FILES)
    files["commutation.py"] = (
        "from functools import lru_cache\n"
        "from typing import Tuple\n"
        "from inputs import ModelPoint\n"
        "from params import I\n"
        "@lru_cache\n"
        "def D_x(key: Tuple[list, ...]) -> float:\n"
        "    return 1.0\n"
    )
    assert "unhashable_lru_cache" in _categories(*files.items())


# --------------------------------------------------------------------------- #
# Fix 1: dynamic imports are invisible to the AST scan -> dynamic_import rule
# --------------------------------------------------------------------------- #


def test_dunder_import_call_fails() -> None:
    # __import__("actuarial") smuggles a forbidden edge past the graph scan.
    files = dict(CLEAN_FILES)
    files["commutation.py"] = (
        "from inputs import ModelPoint\n"
        "from params import I\n"
        "def D_x(x):\n"
        "    actuarial = __import__('actuarial')\n"
        "    return actuarial.A_x(x)\n"
    )
    cats = _categories(*files.items())
    assert "dynamic_import" in cats


def test_importlib_import_module_call_fails() -> None:
    files = dict(CLEAN_FILES)
    files["commutation.py"] = (
        "import importlib\n"
        "from inputs import ModelPoint\n"
        "from params import I\n"
        "def D_x(x):\n"
        "    mod = importlib.import_module('actuarial')\n"
        "    return mod.A_x(x)\n"
    )
    cats = _categories(*files.items())
    assert "dynamic_import" in cats


def test_import_importlib_statement_fails() -> None:
    # Even a bare `import importlib` (the dynamic-import module) is forbidden.
    files = dict(CLEAN_FILES)
    files["params.py"] = "import importlib\nfrom inputs import ModelPoint\nI = 0.0125\n"
    assert "dynamic_import" in _categories(*files.items())


def test_from_importlib_import_module_fails() -> None:
    files = dict(CLEAN_FILES)
    files["params.py"] = (
        "from importlib import import_module\n"
        "from inputs import ModelPoint\n"
        "I = 0.0125\n"
    )
    assert "dynamic_import" in _categories(*files.items())


def test_importlib_dunder_import_call_fails() -> None:
    files = dict(CLEAN_FILES)
    files["commutation.py"] = (
        "import importlib\n"
        "from inputs import ModelPoint\n"
        "from params import I\n"
        "def D_x(x):\n"
        "    mod = importlib.__import__('actuarial')\n"
        "    return mod.A_x(x)\n"
    )
    assert "dynamic_import" in _categories(*files.items())


def test_syntax_error_reported() -> None:
    cats = _categories(("inputs.py", "def broken(:\n"))
    assert "syntax_error" in cats


# --------------------------------------------------------------------------- #
# Command contract (single JSON stdout object, exit codes, ledger)
# --------------------------------------------------------------------------- #


def _run(args: list[str]) -> tuple[int, dict]:
    buf = io.StringIO()
    # run_command emits exactly one JSON object on the real stdout.
    import sys

    real = sys.stdout
    sys.stdout = buf
    try:
        code = run_command(conventions_cmd.main, args)
    finally:
        sys.stdout = real
    payload = json.loads(buf.getvalue())
    return code, payload


def test_command_usage_without_generated_dir(tmp_path: Path) -> None:
    code, payload = _run(["--diagnostics-dir", str(tmp_path)])
    assert code == Exit.USAGE
    assert payload["exit_code"] == Exit.USAGE
    assert payload["status"] == "failed"


def test_command_clean_set_exit_zero(tmp_path: Path) -> None:
    gen = _write_set(tmp_path / "generated", CLEAN_FILES)
    diag = tmp_path / "diag"
    code, payload = _run(["--generated-dir", str(gen), "--diagnostics-dir", str(diag)])
    assert code == Exit.OK
    assert payload["exit_code"] == Exit.OK
    assert payload["status"] == "passed"
    assert payload["gate"] == "G3.architecture-conventions"
    assert payload["summary"]["violation_count"] == 0
    assert payload["input_hashes"]  # non-empty so dossier does not block
    # ledger written + loadable
    entries, read_errors = load_gate_ledger(diag)
    assert read_errors == []
    assert any(e.command == "conventions" for e in entries)


@pytest.mark.parametrize(
    "mutate,category",
    [
        ("backedge", "disallowed_edge"),
        ("cycle", "circular_import"),
        ("local", "function_local_import"),
        ("importerror", "try_except_importerror"),
        ("typecheck", "type_checking_trick"),
        ("cache", "unhashable_lru_cache"),
        ("dynimport", "dynamic_import"),
        ("baretuple", "unhashable_lru_cache"),
    ],
)
def test_command_each_failure_exits_22(tmp_path: Path, mutate: str, category: str) -> None:
    files = dict(CLEAN_FILES)
    if mutate == "backedge":
        files["commutation.py"] = (
            "from inputs import ModelPoint\nfrom params import I\nfrom actuarial import A_x\n"
        )
    elif mutate == "cycle":
        files["params.py"] = "from commutation import D_x\nI = 0.0125\n"
    elif mutate == "local":
        files["actuarial.py"] = (
            "from params import I\ndef A_x(x):\n    from commutation import D_x\n    return D_x(x)\n"
        )
    elif mutate == "importerror":
        files["params.py"] = (
            "from inputs import ModelPoint\ntry:\n    import numpy\nexcept ImportError:\n    numpy = None\nI = 0.0125\n"
        )
    elif mutate == "typecheck":
        files["actuarial.py"] = (
            "from typing import TYPE_CHECKING\nfrom params import I\nfrom commutation import D_x\n"
            "if TYPE_CHECKING:\n    from inputs import ModelPoint\ndef A_x(x):\n    return D_x(x)\n"
        )
    elif mutate == "cache":
        files["commutation.py"] = (
            "from functools import lru_cache\nfrom inputs import ModelPoint\nfrom params import I\n"
            "@lru_cache\ndef D_x(mp: ModelPoint) -> float:\n    return 1.0\n"
        )
    elif mutate == "dynimport":
        files["commutation.py"] = (
            "import importlib\nfrom inputs import ModelPoint\nfrom params import I\n"
            "def D_x(x):\n    return importlib.import_module('actuarial').A_x(x)\n"
        )
    elif mutate == "baretuple":
        files["commutation.py"] = (
            "from functools import lru_cache\nfrom inputs import ModelPoint\nfrom params import I\n"
            "@lru_cache\ndef D_x(key: tuple) -> float:\n    return 1.0\n"
        )

    gen = _write_set(tmp_path / "generated", files)
    diag = tmp_path / "diag"
    code, payload = _run(["--generated-dir", str(gen), "--diagnostics-dir", str(diag)])
    assert code == Exit.CONVENTIONS
    assert payload["exit_code"] == Exit.CONVENTIONS
    assert payload["status"] == "failed"
    assert category in payload["summary"]["violation_categories"]
    assert category in {e["code"] for e in payload["errors"]}
    # ledger still written on the fail path
    entries, read_errors = load_gate_ledger(diag)
    assert read_errors == []


def test_command_gate_version_matches_engine(tmp_path: Path) -> None:
    gen = _write_set(tmp_path / "generated", CLEAN_FILES)
    code, payload = _run(["--generated-dir", str(gen), "--diagnostics-dir", str(tmp_path / "d")])
    assert payload["gate_version"] == GATE_VERSION
