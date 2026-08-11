"""Kernel-based evaluation of portfolio contracts (Fortschreibung support).

Project decision (Leo/Bartek 2026-08-11): every calculated quantity — premium,
present values, reserve at a reporting date — comes EXCLUSIVELY from the
generated target kernel; the Bestandsdaten module carries no actuarial
formulas of its own.

Mechanics: the transient kernel (``generated/``) binds to ``inputs.DEFAULT``
at import time, so it evaluates exactly one model point per process. This
module therefore runs one confined child process per contract: it copies the
kernel into a scratch dir under the repo root, replaces ``inputs.py`` with a
rendering of the contract's ModelPoint
(:func:`rechner_pipeline.models.bestand.render_inputs_py` — the executable
form of the schema coupling), statically security-scans the scratch kernel,
and executes it under the filesystem confinement launcher
(:mod:`rechner_pipeline.qa.fs_confine`), the same trust pattern as the
roundtrip gate.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, Mapping

from rechner_pipeline.models.bestand import model_point_kwargs, render_inputs_py
from rechner_pipeline.qa import fs_confine
from rechner_pipeline.qa.security import scan_python_paths

#: Kernel files copied verbatim from the generated kernel (inputs.py is
#: replaced per contract, hence not in this list).
KERNEL_FILES = ("params.py", "commutation.py", "actuarial.py", "test_run.py", "tafeln.xml")

_MARK_START = "===BESTAND_KERNLAUF_JSON_START==="
_MARK_END = "===BESTAND_KERNLAUF_JSON_END==="

_RUNNER = f"""\
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import test_run

out = test_run.golden_master_outputs()
sys.stdout.write({_MARK_START!r})
sys.stdout.write(json.dumps(out, sort_keys=True))
sys.stdout.write({_MARK_END!r})
"""


class KernlaufError(RuntimeError):
    """Raised when the kernel child fails or violates its contract."""


def run_kernel_for_contract(
    row: Mapping[str, Any],
    generation_fields: Mapping[str, Any],
    *,
    repo_root: Path,
    kernel_dir: Path,
    timeout: int = 120,
) -> Dict[str, Any]:
    """Evaluate one portfolio contract through the generated kernel.

    Returns the kernel's ``golden_master_outputs()`` dict for the contract's
    model point. Raises :class:`KernlaufError` on any failure — a missing or
    unsafe kernel is an error, never silently skipped.
    """
    repo_root = Path(repo_root).resolve()
    kernel_dir = Path(kernel_dir).resolve()
    for name in KERNEL_FILES:
        if not (kernel_dir / name).is_file():
            raise KernlaufError(f"Kernel-Datei fehlt: {kernel_dir / name}")

    scratch = repo_root / ".tmp" / f"bestand_kernlauf_{uuid.uuid4().hex[:12]}"
    scratch.mkdir(parents=True, exist_ok=False)
    try:
        for name in KERNEL_FILES:
            shutil.copy2(kernel_dir / name, scratch / name)
        kwargs = model_point_kwargs(row, generation_fields)
        (scratch / "inputs.py").write_text(render_inputs_py(kwargs), encoding="utf-8")
        (scratch / "_runner.py").write_text(_RUNNER, encoding="utf-8")

        # Statisches Gate vor jeder Ausfuehrung (gleiches Muster wie roundtrip):
        violations = scan_python_paths(sorted(scratch.glob("*.py")))
        if violations:
            first = violations[0]
            raise KernlaufError(
                f"Security-Scan blockiert Kernlauf: {first.symbol} "
                f"({Path(first.path).name}:{first.line})"
            )

        completed = subprocess.run(
            [sys.executable, fs_confine.__file__, str(repo_root), str(scratch / "_runner.py")],
            cwd=str(scratch),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if completed.returncode != 0:
            raise KernlaufError(
                f"Kernlauf fehlgeschlagen (exit {completed.returncode}): "
                f"{completed.stderr.strip()[-500:]}"
            )
        stdout = completed.stdout
        if _MARK_START not in stdout or _MARK_END not in stdout:
            raise KernlaufError("Kernlauf ohne JSON-Marker im Output")
        payload = stdout.split(_MARK_START, 1)[1].split(_MARK_END, 1)[0]
        return json.loads(payload)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def fortschreibungswerte(
    outputs: Mapping[str, Any], months_exp: int
) -> Dict[str, Any]:
    """Pick the reporting-date values from kernel outputs (no own formulas).

    The kernel's table rows are per completed contract year; the row for
    ``months_exp // 12`` is the state at the reporting date. Scalars pass
    through unchanged.
    """
    jahr = int(months_exp) // 12
    tables = outputs.get("tables", {})
    prefix = next(iter(tables), None)
    rows = tables.get(prefix, []) if prefix else []
    if not 0 <= jahr < len(rows):
        raise KernlaufError(
            f"Kein Tabellenjahr {jahr} in Kernel-Output (Zeilen: {len(rows)})"
        )
    scalars = outputs.get("scalars", {})
    return {
        "jahr": jahr,
        "zeile": dict(rows[jahr]),
        "skalare": dict(scalars.get(next(iter(scalars), ""), {})) if scalars else {},
    }
