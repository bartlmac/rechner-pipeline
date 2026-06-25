from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OPTIONAL_IMPORTS = ("openai", "pandas", "win32com", "langgraph")


def _write_optional_import_blocker(tmp_path: Path) -> Path:
    sitecustomize = tmp_path / "sitecustomize.py"
    blocked = repr(OPTIONAL_IMPORTS)
    sitecustomize.write_text(
        "\n".join(
            [
                "import sys",
                "",
                f"BLOCKED = {blocked}",
                "",
                "class OptionalDependencyBlocker:",
                "    def find_spec(self, fullname, path=None, target=None):",
                "        for name in BLOCKED:",
                "            if fullname == name or fullname.startswith(name + '.'):",
                "                raise ImportError(",
                "                    f'blocked optional dependency import: {fullname}'",
                "                )",
                "        return None",
                "",
                "sys.meta_path.insert(0, OptionalDependencyBlocker())",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return tmp_path


def _run_help_with_optional_imports_blocked(tmp_path: Path, script_name: str):
    blocker_dir = _write_optional_import_blocker(tmp_path)
    existing_pythonpath = os.environ.get("PYTHONPATH")
    pythonpath_parts = [str(blocker_dir), str(REPO_ROOT / "src")]
    if existing_pythonpath:
        pythonpath_parts.append(existing_pythonpath)

    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    env.pop("OPENAI_API_KEY", None)

    return subprocess.run(
        [sys.executable, script_name, "--help"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_pipeline_help_does_not_import_optional_dependencies(tmp_path: Path) -> None:
    completed = _run_help_with_optional_imports_blocked(tmp_path, "pipeline.py")

    assert completed.returncode == 0, completed.stderr
    assert "--excel" in completed.stdout
    assert "Default:" in completed.stdout
    assert "examples/Tarifrechner_KLV.xlsm" in completed.stdout


def test_agentic_help_does_not_import_optional_dependencies(tmp_path: Path) -> None:
    completed = _run_help_with_optional_imports_blocked(tmp_path, "agentic_pipeline.py")

    assert completed.returncode == 0, completed.stderr
    assert "--max_retries_main" in completed.stdout
    assert "Default:" in completed.stdout
    assert "examples/Tarifrechner_KLV.xlsm" in completed.stdout
