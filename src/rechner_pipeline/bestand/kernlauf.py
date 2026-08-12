"""Kernel-based evaluation of portfolio contracts (Fortschreibung support).

Project decision (Leo/Bartek 2026-08-11): every calculated quantity — premium,
present values, reserve at a reporting date — comes EXCLUSIVELY from the
kernel; the Bestandsdaten module carries no actuarial formulas of its own.

Two evaluation paths (governance decision 2026-08-12):

* :func:`berechne_vertrag` — the STANDARD path against the stable, promoted
  kernel (:mod:`rechner_pipeline.kern`): in-process ``berechne(mp)``, no
  subprocess and no confinement — the promoted kernel is reviewed,
  version-anchored repo code (measured ~90x faster per contract; bit-parity
  of both paths is test-anchored). This is what the Fortschreibung and the
  Ereignis-Engine use.
* :func:`run_kernel_for_contract` — the migration path for TRANSIENT,
  freshly generated kernels (``generated/``) that bind to ``inputs.DEFAULT``
  at import time: one confined child process per contract (copy kernel to a
  scratch dir, render ``inputs.py`` via
  :func:`rechner_pipeline.models.bestand.render_inputs_py`, static security
  scan, execute under :mod:`rechner_pipeline.qa.fs_confine`). Unreviewed
  generated code keeps its confinement.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from rechner_pipeline.kern import ModelPoint, berechne
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


def berechne_vertrag(
    row: Mapping[str, Any], generation_fields: Mapping[str, Any]
) -> Dict[str, Any]:
    """Evaluate one portfolio contract through the stable kernel, in-process.

    Joins the portfolio row with its tariff generation into a
    :class:`~rechner_pipeline.kern.model_point.ModelPoint` and returns
    ``berechne(mp)`` in the golden-master contract shape — same format as
    :func:`run_kernel_for_contract`, without subprocess or scratch files.

    The output is reporting-date independent (a pure function of the model
    point): a Fortschreibung over several Stichtage calls this ONCE per
    contract and indexes per Stichtag via :func:`fortschreibungswerte`.
    """
    mp = ModelPoint(**model_point_kwargs(row, generation_fields))
    return berechne(mp)


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
    outputs: Mapping[str, Any], months_exp: int, *, prefix: Optional[str] = None
) -> Dict[str, Any]:
    """Pick the reporting-date values from kernel outputs (no own formulas).

    The kernel's table rows are per completed contract year; the row for
    ``months_exp // 12`` is the state at the reporting date. Scalars pass
    through unchanged. Without an explicit ``prefix`` the output must contain
    exactly one table prefix — ambiguity (a future multi-product kernel) is
    an error, never a silent first-key pick.
    """
    jahr = int(months_exp) // 12
    tables = outputs.get("tables", {})
    if prefix is None:
        if len(tables) != 1:
            raise KernlaufError(
                f"Mehrdeutiger Kernel-Output: {len(tables)} Tabellen-Prefixe "
                f"({sorted(tables)}) — prefix explizit angeben"
            )
        prefix = next(iter(tables))
    rows = tables.get(prefix, [])
    if not 0 <= jahr < len(rows):
        raise KernlaufError(
            f"Kein Tabellenjahr {jahr} in Kernel-Output (Zeilen: {len(rows)})"
        )
    scalars = outputs.get("scalars", {})
    return {
        "jahr": jahr,
        "zeile": dict(rows[jahr]),
        "skalare": dict(scalars.get(prefix, {})),
    }
