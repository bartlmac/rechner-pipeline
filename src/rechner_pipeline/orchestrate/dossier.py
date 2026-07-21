"""Provenance writer for the TARGET acceptance dossier (G8, §6.8.3/§6.8.4).

This is the MIGRATED + UPGRADED descendant of the AS-IS
``rechner_pipeline.orchestrate.dossier`` (§4.1, §6.4). The AS-IS module wrote a
``schema_version=1`` dossier directly from a ``PipelineRunner`` and an
``ExportManifest``. In the TARGET full-agentic architecture the CLI agent owns
generation/repair and the deterministic toolbox owns acceptance, so this module
is reshaped into **pure aggregation functions** that the ``dossier`` toolbox
command (:mod:`rechner_pipeline.toolbox.dossier`) drives:

* :func:`load_gate_ledger` — read the §6.8.2 gate-result ledger JSONs that the
  other gate commands wrote into ``--diagnostics-dir``.
* :func:`dependency_versions` — record the **real** interpreter and library
  versions (python 3.12.x, openpyxl, oletools, pandas, hypothesis), never the
  §6.8 placeholder ``"3.11.x"``.
* :func:`build_qa_report` — aggregate the ledger into the §6.8.3
  ``qa_report.json`` and compute acceptance via
  :meth:`schemas.QaReport.compute_accepted`.
* :func:`build_run_dossier_v2` — build the §6.8.4 upgraded ``run_dossier.json``
  (``schema_version=2``) by layering the v2 delta onto an AS-IS-shaped base.
* :func:`evaluate_blockers` — the G8 blocking checks (missing gate result,
  missing hashes, unapproved open assumptions, required gate not passed).

All builders return :mod:`rechner_pipeline.models.schemas` dataclasses so the
caller can call ``.validate()`` before serializing. Nothing here writes stdout;
the toolbox command owns I/O. ``write_json`` is a small UTF-8 writer kept for
parity with the AS-IS ``write_run_dossier`` ergonomics.
"""

from __future__ import annotations

import importlib.metadata as importlib_metadata
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from rechner_pipeline.models import schemas
from rechner_pipeline.models.manifest import file_sha256
from rechner_pipeline.models.schemas import GateLedgerEntry, QaReport, RunDossierV2Delta

# Single source of truth for the ledger filename suffix lives in ``_common`` (the
# lowest module in the import graph). Import — never re-declare — it here so the
# writer (``_common.write_gate_ledger``) and this loader can never diverge. This
# is the non-circular direction (orchestrate.dossier -> toolbox._common).
from rechner_pipeline.toolbox._common import GATE_LEDGER_SUFFIX

__all__ = [
    "REQUIRED_GATES",
    "ALL_GATES",
    "GATE_LEDGER_SUFFIX",
    "utc_now",
    "path_record",
    "load_gate_ledger",
    "dependency_versions",
    "hash_generated_files",
    "build_qa_report",
    "build_run_dossier_v2",
    "evaluate_blockers",
    "write_json",
]


# --------------------------------------------------------------------------- #
# Gate catalogue (§3.5 G0–G8). ``required`` follows §3.5: every acceptance gate
# is required. Wave-2 gates (conventions/algebraic/roundtrip) may legitimately
# be absent because they have not been authored yet; they are still REQUIRED, so
# a missing entry honestly blocks full acceptance (see ``evaluate_blockers``).
# --------------------------------------------------------------------------- #

#: Canonical gate id -> command name. The order is the §3.5 G0..G7 acceptance
#: order (G8 is this dossier command itself and never appears in its own ledger).
ALL_GATES: Tuple[Tuple[str, str], ...] = (
    ("G0.extraction-manifest", "extract"),
    ("G1.file-contract", "validate"),
    ("G2.static-security", "security"),
    ("G3.architecture-conventions", "conventions"),
    ("G5.golden-master", "golden_master"),
    ("G6.algebraic-properties", "algebraic"),
    ("G7.roundtrips", "roundtrip"),
)

#: The gates that must be ``passed`` for mechanical acceptance (§3.5). All of
#: them are required; this is exported so gate authors and the end-to-end author
#: share one list.
REQUIRED_GATES: Tuple[str, ...] = tuple(gate for gate, _ in ALL_GATES)

#: Filename convention for a gate-result ledger entry written into
#: ``--diagnostics-dir``: ``<command>.gate.json`` (e.g. ``golden_master.gate.json``).
#: Re-exported from :data:`rechner_pipeline.toolbox._common.GATE_LEDGER_SUFFIX`
#: (the single source of truth) so ``provenance.GATE_LEDGER_SUFFIX`` stays valid.
GATE_LEDGER_SUFFIX = GATE_LEDGER_SUFFIX  # noqa: PLW0127 — re-export, see import above

#: Dependency distributions whose versions are recorded in
#: ``qa_report.dependency_versions`` (§6.8.3, with the placeholder corrected to
#: real values). ``python`` is added separately from :data:`platform`.
_RECORDED_DISTRIBUTIONS: Tuple[str, ...] = (
    "openpyxl",
    "oletools",
    "pandas",
    "hypothesis",
)


def utc_now() -> str:
    """UTC ISO-8601 timestamp (parity with the AS-IS ``_utc_now``)."""
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# PathRecord (§6.4 shape: {path, exists} + bytes/sha256 when an existing file)
# --------------------------------------------------------------------------- #


def path_record(path: Path, *, base: Optional[Path] = None) -> Dict[str, Any]:
    """Return the §6.4/§6.8.4 ``PathRecord`` for *path*.

    ``path`` is emitted repo-relative when *base* is given and *path* is inside
    it, so dossiers stay portable; otherwise the path string is used as-is.
    """
    display = str(path)
    if base is not None:
        try:
            display = str(path.resolve().relative_to(Path(base).resolve()))
        except (ValueError, OSError):
            display = str(path)
    record: Dict[str, Any] = {"path": display, "exists": path.exists()}
    if path.exists() and path.is_file():
        record["bytes"] = path.stat().st_size
        record["sha256"] = file_sha256(path)
    return record


# --------------------------------------------------------------------------- #
# Gate-result ledger (§6.8.2) loading
# --------------------------------------------------------------------------- #


def load_gate_ledger(
    diagnostics_dir: Path,
) -> Tuple[List[GateLedgerEntry], List[Dict[str, Any]]]:
    """Load all §6.8.2 gate-result ledger entries from *diagnostics_dir*.

    Reads every ``*<GATE_LEDGER_SUFFIX>`` file (``<command>.gate.json``), sorted
    by filename for determinism. Returns ``(entries, read_errors)`` where each
    ``read_errors`` item is ``{"path", "error"}`` for a file that could not be
    parsed as a JSON object. Parse failures do not raise — the caller turns them
    into blocking dossier errors.
    """
    entries: List[GateLedgerEntry] = []
    read_errors: List[Dict[str, Any]] = []
    if not diagnostics_dir.exists():
        return entries, read_errors
    for path in sorted(diagnostics_dir.glob(f"*{GATE_LEDGER_SUFFIX}"), key=str):
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 — surface as a structured read error
            read_errors.append(
                {"path": str(path), "error": f"{type(exc).__name__}: {exc}"}
            )
            continue
        if not isinstance(payload, dict):
            read_errors.append(
                {"path": str(path), "error": "ledger entry is not a JSON object"}
            )
            continue
        entries.append(GateLedgerEntry.from_dict(payload))
    return entries, read_errors


# --------------------------------------------------------------------------- #
# Real dependency versions (§6.8.3 — correct the "3.11.x" placeholder)
# --------------------------------------------------------------------------- #


def dependency_versions() -> Dict[str, Any]:
    """Record the REAL interpreter + library versions (§6.8.3).

    Unlike the §6.8 example payload (``"python": "3.11.x"``) this records the
    actual running interpreter (e.g. ``3.12.4``) and the installed distribution
    versions for openpyxl/oletools/pandas/hypothesis. A distribution that is not
    installed is recorded as ``null`` (honest absence) rather than guessed.
    """
    versions: Dict[str, Any] = {"python": platform.python_version()}
    for dist in _RECORDED_DISTRIBUTIONS:
        try:
            versions[dist] = importlib_metadata.version(dist)
        except importlib_metadata.PackageNotFoundError:
            versions[dist] = None
    return versions


# --------------------------------------------------------------------------- #
# Generated-file hashing (§6.8.3 generated_file_hashes / §6.8.4 generated_files)
# --------------------------------------------------------------------------- #


def hash_generated_files(
    generated_dir: Path, *, repo_root: Path
) -> List[Dict[str, Any]]:
    """Return sorted ``[{path, bytes, sha256}]`` for every file under
    *generated_dir*, with repo-relative ``path`` keys (§6.8.3)."""
    records: List[Dict[str, Any]] = []
    if not generated_dir.exists():
        return records
    for path in sorted(generated_dir.rglob("*"), key=str):
        if not path.is_file():
            continue
        try:
            rel = str(path.resolve().relative_to(Path(repo_root).resolve()))
        except (ValueError, OSError):
            rel = str(path)
        records.append(
            {"path": rel, "bytes": path.stat().st_size, "sha256": file_sha256(path)}
        )
    return records


# --------------------------------------------------------------------------- #
# qa_report.json (§6.8.3)
# --------------------------------------------------------------------------- #


def _blocking_warnings_from_ledger(
    entries: Iterable[GateLedgerEntry],
) -> List[Dict[str, Any]]:
    """Collect strict-error warnings surfaced by gates into blocking warnings.

    A gate may record ``summary.warnings`` (list of warning objects). Any with
    ``strict_error == True`` becomes a blocking warning (§6.8.3 acceptance rule).
    """
    blocking: List[Dict[str, Any]] = []
    for entry in entries:
        for warning in entry.summary.get("warnings", []) or []:
            if isinstance(warning, dict) and warning.get("strict_error"):
                blocking.append({"gate": entry.gate, **warning})
    return blocking


def build_qa_report(
    *,
    run_id: str,
    entries: List[GateLedgerEntry],
    open_assumptions: List[Dict[str, Any]],
    blocking_warnings: List[Dict[str, Any]],
    generated_file_hashes: List[Dict[str, Any]],
    dependency_versions_map: Dict[str, Any],
    expectation_coverage: str,
    attempts_used: int,
    max_attempts: int,
    qa_contract_path: str,
    tafeln_xml_canonical_sha256: Optional[str] = None,
    created_at: Optional[str] = None,
) -> QaReport:
    """Aggregate the ledger into a §6.8.3 :class:`QaReport`.

    ``accepted`` and ``decision`` are *computed*, never supplied:
    ``compute_accepted()`` is the single source of truth (every required gate
    ``passed`` AND no blocking warning AND no unapproved open assumption). When
    not accepted the decision is ``human_review_required`` if any open assumption
    requests a human-review handoff, otherwise ``failed``.
    """
    gates = [entry.to_dict() for entry in entries]

    report = QaReport(
        created_at=created_at or utc_now(),
        run_id=run_id,
        decision="failed",  # placeholder; corrected below from compute_accepted()
        accepted=False,
        attempts_used=attempts_used,
        max_attempts=max_attempts,
        expectation_coverage=expectation_coverage,
        qa_contract_path=qa_contract_path,
        gates=gates,
        blocking_warnings=blocking_warnings,
        open_assumptions=open_assumptions,
        generated_file_hashes=generated_file_hashes,
        dependency_versions=dependency_versions_map,
        tafeln_xml_canonical_sha256=tafeln_xml_canonical_sha256,
    )

    accepted = report.compute_accepted()
    report.accepted = accepted
    if accepted:
        report.decision = "accepted"
    else:
        wants_human_review = any(
            assumption.get("human_review_required")
            or str(assumption.get("code", "")).startswith("human_review")
            for assumption in open_assumptions
        )
        report.decision = "human_review_required" if wants_human_review else "failed"
    return report


# --------------------------------------------------------------------------- #
# Upgraded run_dossier.json (schema_version=2, §6.8.4)
# --------------------------------------------------------------------------- #


def build_run_dossier_v2(
    *,
    qa_report: QaReport,
    qa_report_record: Dict[str, Any],
    entries: List[GateLedgerEntry],
    run_status: str,
    repo_root: Path,
    run_cli: Dict[str, Any],
    options_extra: Dict[str, Any],
    input_bundle: Dict[str, Any],
    attempts: Optional[List[Dict[str, Any]]] = None,
    generated_files: Optional[List[Dict[str, Any]]] = None,
    created_at: Optional[str] = None,
) -> Tuple[Dict[str, Any], RunDossierV2Delta]:
    """Build the §6.8.4 upgraded ``run_dossier.json`` (schema_version=2).

    Returns ``(full_dossier_dict, delta)``. The full dict is the AS-IS §6.4
    structure (preserved keys) with the v2 delta layered on. The *delta* is
    returned separately so the caller can ``delta.validate()`` the new keys.
    """
    as_is_base: Dict[str, Any] = {
        "schema_version": 1,
        "created_at": created_at or utc_now(),
        "run": {
            "status": run_status,
            "human_review_required": qa_report.decision == "human_review_required",
            "repo_root": str(repo_root),
            "options": {},
        },
        "qa_report": qa_report_record,
        "open_assumptions": list(qa_report.open_assumptions),
        "warnings": list(qa_report.blocking_warnings),
        "generated_files": list(generated_files or []),
    }

    delta = RunDossierV2Delta(
        run_cli=dict(run_cli),
        options_extra=dict(options_extra),
        qa_report=dict(qa_report_record),
        gate_results=[entry.to_dict() for entry in entries],
        attempts=list(attempts or []),
        input_bundle=dict(input_bundle),
    )

    full = delta.merge_into(as_is_base)
    # Re-attach the preserved AS-IS provenance keys that ``merge_into`` does not
    # know about (it only manages the v2 delta surface).
    full["created_at"] = as_is_base["created_at"]
    full["open_assumptions"] = as_is_base["open_assumptions"]
    full["warnings"] = as_is_base["warnings"]
    full["generated_files"] = as_is_base["generated_files"]
    return full, delta


# --------------------------------------------------------------------------- #
# G8 blocking checks (§3.5: missing gate result / hashes / unapproved
# assumptions / required gate not passed)
# --------------------------------------------------------------------------- #


def evaluate_blockers(
    *,
    entries: List[GateLedgerEntry],
    read_errors: List[Dict[str, Any]],
    open_assumptions: List[Dict[str, Any]],
    generated_file_hashes: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Return the list of G8 blocking errors (empty == nothing blocks at G8).

    Each error is ``{"code", "message", ...}``. Blocking conditions (§3.3 row,
    §3.5 G8):

    * ``ledger.read_error`` — a ledger file could not be parsed.
    * ``gate.missing`` — a REQUIRED gate has no ledger entry (covers Wave-2 gates
      not yet authored; recorded honestly so acceptance is blocked).
    * ``gate.duplicate`` — two ledger entries claim the same gate id.
    * ``gate.not_passed`` — a REQUIRED gate's ledger status is not ``passed``.
    * ``hashes.missing`` — a passed gate recorded no ``input_hashes``, or no
      generated-file hashes were produced at all (acceptance needs provenance).
    * ``open_assumption.unapproved`` — an open assumption is not approved.
    """
    blockers: List[Dict[str, Any]] = []

    for err in read_errors:
        blockers.append(
            {
                "code": "ledger.read_error",
                "message": f"Gate ledger entry unreadable: {err.get('error')}",
                "path": err.get("path"),
            }
        )

    by_gate: Dict[str, List[GateLedgerEntry]] = {}
    for entry in entries:
        by_gate.setdefault(entry.gate, []).append(entry)

    for gate in REQUIRED_GATES:
        found = by_gate.get(gate)
        if not found:
            blockers.append(
                {
                    "code": "gate.missing",
                    "message": (
                        f"Required gate {gate!r} has no ledger entry in the "
                        "diagnostics dir (gate not run / not yet authored)."
                    ),
                    "gate": gate,
                }
            )
            continue
        if len(found) > 1:
            blockers.append(
                {
                    "code": "gate.duplicate",
                    "message": f"Required gate {gate!r} has {len(found)} ledger entries.",
                    "gate": gate,
                }
            )
        # Use the highest-attempt entry as the authoritative outcome.
        authoritative = max(found, key=lambda e: e.attempt)
        if authoritative.status != "passed":
            blockers.append(
                {
                    "code": "gate.not_passed",
                    "message": (
                        f"Required gate {gate!r} status is "
                        f"{authoritative.status!r}, not 'passed'."
                    ),
                    "gate": gate,
                    "status": authoritative.status,
                }
            )
        if not authoritative.input_hashes:
            blockers.append(
                {
                    "code": "hashes.missing",
                    "message": (
                        f"Required gate {gate!r} recorded no input_hashes; "
                        "provenance is incomplete."
                    ),
                    "gate": gate,
                }
            )

    if entries and not generated_file_hashes:
        blockers.append(
            {
                "code": "hashes.missing",
                "message": "No generated-file hashes were produced for the dossier.",
            }
        )

    for assumption in open_assumptions:
        if not assumption.get("approved", False):
            blockers.append(
                {
                    "code": "open_assumption.unapproved",
                    "message": (
                        "Unapproved open assumption blocks acceptance: "
                        f"{assumption.get('code', '<no-code>')}"
                    ),
                    "assumption": assumption,
                }
            )

    return blockers


# --------------------------------------------------------------------------- #
# Small UTF-8 writer (parity with AS-IS write_run_dossier ergonomics)
# --------------------------------------------------------------------------- #


def write_json(path: Path, obj: Dict[str, Any]) -> Path:
    """Write *obj* as UTF-8 JSON (``ensure_ascii=False``, ``indent=2``)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path
