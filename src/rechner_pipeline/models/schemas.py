"""Typed builders/validators for the §6.8 TARGET acceptance JSON schemas.

Covers:

* §6.8.1 — common toolbox result object (:class:`CommonResult`)
* §6.8.2 — gate-result ledger entry (:class:`GateLedgerEntry`)
* §6.8.3 — ``qa_report.json`` aggregate (:class:`QaReport`)
* §6.8.4 — upgraded ``run_dossier.json`` v2 delta (:class:`RunDossierV2Delta`)
* §6.8.6 — ``qa_contract.json`` algebraic-gate contract (:class:`QaContract`)

Each class is a plain ``dataclass`` with ``to_dict`` / ``from_dict`` and a
``validate(obj) -> list[error]`` (no external schema library). ``validate`` runs
on the dataclass instance and returns human-readable error strings; an empty list
means the object satisfies the schema.

The common-result object here is a *schema view* of §6.8.1 used for
serialization round-trips; the live toolbox emitter is
:class:`rechner_pipeline.toolbox._common.ToolboxResult`. Both produce the same
field set.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from rechner_pipeline.models.manifest import FileHashRecord, ManifestWarning

# Single source of truth for status values and exit codes lives in ``_common``
# (the live toolbox contract). Import — never re-declare — them here so the
# schema view and the emitter can never diverge (§3.3 / §6.8.1).
from rechner_pipeline.toolbox._common import (
    SCHEMA_VERSION,
    STANDARD_EXIT_CODES as _STANDARD_EXIT_CODES,
    STATUSES as STATUS_VALUES,
)

__all__ = [
    "SCHEMA_VERSION",
    "STATUS_VALUES",
    "GATE_VERSION_DEFAULT",
    "DECISION_VALUES",
    "EXPECTATION_COVERAGE_VALUES",
    "CommonResult",
    "GateLedgerEntry",
    "QaReport",
    "RunDossierV2Delta",
    "QaContract",
]

# SCHEMA_VERSION, STATUS_VALUES, and _STANDARD_EXIT_CODES are imported from
# ``_common`` above (single source of truth). The remaining tuples below are
# schema-view-only enumerations with no ``_common`` counterpart.
DECISION_VALUES: tuple[str, ...] = ("accepted", "human_review_required", "failed")
EXPECTATION_COVERAGE_VALUES: tuple[str, ...] = ("full", "sparse", "none")
GATE_VERSION_DEFAULT = "1.0.0"


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(c in "0123456789abcdef" for c in value)
    )


def _hashmap_errors(prefix: str, mapping: Any) -> List[str]:
    errs: List[str] = []
    if not isinstance(mapping, dict):
        return [f"{prefix} must be an object"]
    for key, value in mapping.items():
        if not _is_sha256(value):
            errs.append(f"{prefix}[{key!r}] is not a SHA-256 hex string")
    return errs


# --------------------------------------------------------------------------- #
# §6.8.1 Common toolbox result object
# --------------------------------------------------------------------------- #


@dataclass
class CommonResult:
    """§6.8.1 common toolbox result (schema view)."""

    command: str
    gate_version: str
    status: str
    exit_code: int
    gate: Optional[str] = None
    paths: Dict[str, Any] = field(default_factory=dict)
    summary: Dict[str, Any] = field(default_factory=dict)
    input_hashes: Dict[str, str] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    warnings: List[Any] = field(default_factory=list)
    errors: List[Any] = field(default_factory=list)
    repair_hints: List[Any] = field(default_factory=list)
    output_hashes: Dict[str, str] = field(default_factory=dict)
    diagnostics_path: Optional[str] = None
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "schema_version": self.schema_version,
            "command": self.command,
        }
        if self.gate is not None:
            out["gate"] = self.gate
        out["gate_version"] = self.gate_version
        out["status"] = self.status
        out["exit_code"] = self.exit_code
        out["paths"] = dict(self.paths)
        out["input_hashes"] = dict(self.input_hashes)
        out["summary"] = dict(self.summary)
        if self.metrics:
            out["metrics"] = dict(self.metrics)
        if self.output_hashes:
            out["output_hashes"] = dict(self.output_hashes)
        out["warnings"] = list(self.warnings)
        out["errors"] = list(self.errors)
        out["repair_hints"] = list(self.repair_hints)
        if self.diagnostics_path is not None:
            out["diagnostics_path"] = self.diagnostics_path
        return out

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CommonResult":
        return cls(
            command=str(data.get("command", "")),
            gate_version=str(data.get("gate_version", "")),
            status=str(data.get("status", "")),
            exit_code=int(data.get("exit_code", 0)),
            gate=data.get("gate"),
            paths=dict(data.get("paths") or {}),
            summary=dict(data.get("summary") or {}),
            input_hashes=dict(data.get("input_hashes") or {}),
            metrics=dict(data.get("metrics") or {}),
            warnings=list(data.get("warnings") or []),
            errors=list(data.get("errors") or []),
            repair_hints=list(data.get("repair_hints") or []),
            output_hashes=dict(data.get("output_hashes") or {}),
            diagnostics_path=data.get("diagnostics_path"),
            schema_version=int(data.get("schema_version", SCHEMA_VERSION)),
        )

    def validate(self) -> List[str]:
        errors: List[str] = []
        if self.schema_version != SCHEMA_VERSION:
            errors.append(f"schema_version must be {SCHEMA_VERSION}")
        if not self.command:
            errors.append("command is required")
        if not self.gate_version:
            errors.append("gate_version is required")
        if self.status not in STATUS_VALUES:
            errors.append(f"status must be one of {STATUS_VALUES}, got {self.status!r}")
        if self.exit_code not in _STANDARD_EXIT_CODES:
            errors.append(f"exit_code {self.exit_code} is not a standard exit code")
        # status mirrors exit code (§6.8.1): 0 <-> passed, non-zero <-> not passed.
        if (self.exit_code == 0) != (self.status == "passed"):
            errors.append("status must mirror exit_code (0 <-> passed)")
        if not isinstance(self.paths, dict):
            errors.append("paths must be an object")
        if not isinstance(self.summary, dict):
            errors.append("summary must be an object")
        errors.extend(_hashmap_errors("input_hashes", self.input_hashes))
        if self.output_hashes:
            errors.extend(_hashmap_errors("output_hashes", self.output_hashes))
        for name in ("errors", "repair_hints", "warnings"):
            if not isinstance(getattr(self, name), list):
                errors.append(f"{name} must be an array")
        return errors


# --------------------------------------------------------------------------- #
# §6.8.2 Gate-result ledger entry
# --------------------------------------------------------------------------- #


@dataclass
class GateLedgerEntry:
    """§6.8.2 gate-result ledger entry; one per gate execution."""

    gate: str
    command: str
    gate_version: str
    required: bool
    status: str
    attempt: int
    started_at: str
    input_hashes: Dict[str, str] = field(default_factory=dict)
    diagnostics_path: Optional[str] = None
    summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "gate": self.gate,
            "command": self.command,
            "gate_version": self.gate_version,
            "required": self.required,
            "status": self.status,
            "attempt": self.attempt,
            "started_at": self.started_at,
            "input_hashes": dict(self.input_hashes),
        }
        if self.diagnostics_path is not None:
            out["diagnostics_path"] = self.diagnostics_path
        out["summary"] = dict(self.summary)
        return out

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GateLedgerEntry":
        return cls(
            gate=str(data.get("gate", "")),
            command=str(data.get("command", "")),
            gate_version=str(data.get("gate_version", "")),
            required=bool(data.get("required", False)),
            status=str(data.get("status", "")),
            attempt=int(data.get("attempt", 0)),
            started_at=str(data.get("started_at", "")),
            input_hashes=dict(data.get("input_hashes") or {}),
            diagnostics_path=data.get("diagnostics_path"),
            summary=dict(data.get("summary") or {}),
        )

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not self.gate:
            errors.append("gate is required")
        if not self.command:
            errors.append("command is required")
        if not self.gate_version:
            errors.append("gate_version is required")
        if not isinstance(self.required, bool):
            errors.append("required must be a boolean")
        if self.status not in STATUS_VALUES:
            errors.append(f"status must be one of {STATUS_VALUES}, got {self.status!r}")
        if not isinstance(self.attempt, int) or self.attempt < 0:
            errors.append("attempt must be a non-negative integer")
        if not self.started_at:
            errors.append("started_at is required")
        errors.extend(_hashmap_errors("input_hashes", self.input_hashes))
        if not isinstance(self.summary, dict):
            errors.append("summary must be an object")
        return errors


# --------------------------------------------------------------------------- #
# §6.8.3 qa_report.json
# --------------------------------------------------------------------------- #


@dataclass
class QaReport:
    """§6.8.3 ``qa_report.json`` mechanical acceptance aggregate.

    ``accepted`` is computed, not supplied: ``accepted == every required gate has
    status==passed AND no strict_error warning AND no unapproved open assumption``.
    Use :meth:`compute_accepted` to derive it from the populated fields.
    """

    created_at: str
    run_id: str
    decision: str
    accepted: bool
    attempts_used: int
    max_attempts: int
    expectation_coverage: str
    qa_contract_path: str
    gates: List[Dict[str, Any]] = field(default_factory=list)
    blocking_warnings: List[Dict[str, Any]] = field(default_factory=list)
    open_assumptions: List[Dict[str, Any]] = field(default_factory=list)
    generated_file_hashes: List[Dict[str, Any]] = field(default_factory=list)
    dependency_versions: Dict[str, Any] = field(default_factory=dict)
    tafeln_xml_canonical_sha256: Optional[str] = None
    schema_version: int = SCHEMA_VERSION

    def compute_accepted(self) -> bool:
        """Derive acceptance from the populated fields (§6.8.3)."""
        all_required_passed = all(
            entry.get("status") == "passed"
            for entry in self.gates
            if entry.get("required", True)
        )
        return (
            all_required_passed
            and not self.blocking_warnings
            and not self.open_assumptions
        )

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "run_id": self.run_id,
            "decision": self.decision,
            "accepted": self.accepted,
            "attempts_used": self.attempts_used,
            "max_attempts": self.max_attempts,
            "expectation_coverage": self.expectation_coverage,
            "qa_contract_path": self.qa_contract_path,
            "gates": [dict(g) for g in self.gates],
            "blocking_warnings": [dict(w) for w in self.blocking_warnings],
            "open_assumptions": [dict(a) for a in self.open_assumptions],
            "generated_file_hashes": [dict(h) for h in self.generated_file_hashes],
            "dependency_versions": dict(self.dependency_versions),
        }
        if self.tafeln_xml_canonical_sha256 is not None:
            out["tafeln_xml_canonical_sha256"] = self.tafeln_xml_canonical_sha256
        return out

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QaReport":
        return cls(
            created_at=str(data.get("created_at", "")),
            run_id=str(data.get("run_id", "")),
            decision=str(data.get("decision", "")),
            accepted=bool(data.get("accepted", False)),
            attempts_used=int(data.get("attempts_used", 0)),
            max_attempts=int(data.get("max_attempts", 0)),
            expectation_coverage=str(data.get("expectation_coverage", "")),
            qa_contract_path=str(data.get("qa_contract_path", "")),
            gates=[dict(g) for g in data.get("gates", [])],
            blocking_warnings=[dict(w) for w in data.get("blocking_warnings", [])],
            open_assumptions=[dict(a) for a in data.get("open_assumptions", [])],
            generated_file_hashes=[
                dict(h) for h in data.get("generated_file_hashes", [])
            ],
            dependency_versions=dict(data.get("dependency_versions") or {}),
            tafeln_xml_canonical_sha256=data.get("tafeln_xml_canonical_sha256"),
            schema_version=int(data.get("schema_version", SCHEMA_VERSION)),
        )

    def validate(self) -> List[str]:
        errors: List[str] = []
        if self.schema_version != SCHEMA_VERSION:
            errors.append(f"schema_version must be {SCHEMA_VERSION}")
        if not self.created_at:
            errors.append("created_at is required")
        if not self.run_id:
            errors.append("run_id is required")
        if self.decision not in DECISION_VALUES:
            errors.append(
                f"decision must be one of {DECISION_VALUES}, got {self.decision!r}"
            )
        if not isinstance(self.accepted, bool):
            errors.append("accepted must be a boolean")
        if self.expectation_coverage not in EXPECTATION_COVERAGE_VALUES:
            errors.append(
                "expectation_coverage must be one of "
                f"{EXPECTATION_COVERAGE_VALUES}, got {self.expectation_coverage!r}"
            )
        if self.attempts_used < 0:
            errors.append("attempts_used must be non-negative")
        if self.max_attempts < 0:
            errors.append("max_attempts must be non-negative")
        # Consistency between decision and accepted (§6.8.3).
        if self.accepted and self.decision != "accepted":
            errors.append("accepted=true requires decision=='accepted'")
        if not self.accepted and self.decision == "accepted":
            errors.append("decision=='accepted' requires accepted=true")
        if self.decision != "accepted":
            non_passing = any(g.get("status") != "passed" for g in self.gates)
            if not (non_passing or self.blocking_warnings or self.open_assumptions):
                errors.append(
                    "non-accepted decision requires a non-passing gate, a blocking "
                    "warning, or an open assumption"
                )
        if self.tafeln_xml_canonical_sha256 is not None and not _is_sha256(
            self.tafeln_xml_canonical_sha256
        ):
            errors.append("tafeln_xml_canonical_sha256 must be a SHA-256 hex string")
        for h in self.generated_file_hashes:
            if not _is_sha256(h.get("sha256")):
                errors.append(
                    f"generated_file_hashes entry {h.get('path')!r} lacks a valid sha256"
                )
        return errors


# --------------------------------------------------------------------------- #
# §6.8.4 Upgraded run_dossier.json (v2) delta
# --------------------------------------------------------------------------- #


@dataclass
class RunDossierV2Delta:
    """The §6.8.4 TARGET *delta* over the AS-IS ``run_dossier.json`` (§6.4).

    Represents only the new/added keys: the bumped ``schema_version`` (2), the
    extended ``run.options`` provenance, ``run.cli``, ``qa_report``,
    ``gate_results``, ``attempts``, and ``input_bundle``. The full v2 dossier is
    the AS-IS structure merged with this delta (see :meth:`merge_into`).
    """

    schema_version: int = 2
    run_cli: Dict[str, Any] = field(default_factory=dict)
    options_extra: Dict[str, Any] = field(default_factory=dict)
    qa_report: Dict[str, Any] = field(default_factory=dict)
    gate_results: List[Dict[str, Any]] = field(default_factory=list)
    attempts: List[Dict[str, Any]] = field(default_factory=list)
    input_bundle: Dict[str, Any] = field(default_factory=dict)

    #: The new option keys added by §6.8.4 over the AS-IS option set.
    OPTION_KEYS: tuple[str, ...] = (
        "provider",
        "max_output_tokens",
        "export_backend",
        "test_mode",
        "adapter_id",
        "max_attempts",
    )
    PROVIDER_VALUES: tuple[str, ...] = (
        "claude",
        "copilot",
        "codex",
        "opencode",
        "replay",
    )
    OUTCOME_VALUES: tuple[str, ...] = ("repaired", "accepted", "exhausted")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run": {"cli": dict(self.run_cli), "options": dict(self.options_extra)},
            "qa_report": dict(self.qa_report),
            "gate_results": [dict(g) for g in self.gate_results],
            "attempts": [dict(a) for a in self.attempts],
            "input_bundle": dict(self.input_bundle),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunDossierV2Delta":
        run = dict(data.get("run") or {})
        return cls(
            schema_version=int(data.get("schema_version", 2)),
            run_cli=dict(run.get("cli") or {}),
            options_extra=dict(run.get("options") or {}),
            qa_report=dict(data.get("qa_report") or {}),
            gate_results=[dict(g) for g in data.get("gate_results", [])],
            attempts=[dict(a) for a in data.get("attempts", [])],
            input_bundle=dict(data.get("input_bundle") or {}),
        )

    def merge_into(self, as_is: Dict[str, Any]) -> Dict[str, Any]:
        """Produce the full v2 dossier by layering this delta onto an AS-IS
        dossier dict (§6.4). The AS-IS dict is not mutated."""
        merged = dict(as_is)
        merged["schema_version"] = self.schema_version
        run = dict(merged.get("run") or {})
        options = dict(run.get("options") or {})
        options.update(self.options_extra)
        run["options"] = options
        if self.run_cli:
            run["cli"] = dict(self.run_cli)
        merged["run"] = run
        merged["qa_report"] = dict(self.qa_report)
        merged["gate_results"] = [dict(g) for g in self.gate_results]
        merged["attempts"] = [dict(a) for a in self.attempts]
        merged["input_bundle"] = dict(self.input_bundle)
        return merged

    def validate(self) -> List[str]:
        errors: List[str] = []
        if self.schema_version != 2:
            errors.append("schema_version must be 2 for the TARGET dossier")
        if "name" not in self.run_cli:
            errors.append("run.cli.name is required")
        if "headless" in self.run_cli and not isinstance(
            self.run_cli["headless"], bool
        ):
            errors.append("run.cli.headless must be a boolean")
        provider = self.options_extra.get("provider")
        if provider is not None and provider not in self.PROVIDER_VALUES:
            errors.append(
                f"run.options.provider must be one of {self.PROVIDER_VALUES}, "
                f"got {provider!r}"
            )
        for entry in self.attempts:
            outcome = entry.get("outcome")
            if outcome is not None and outcome not in self.OUTCOME_VALUES:
                errors.append(
                    f"attempts[].outcome must be one of {self.OUTCOME_VALUES}, "
                    f"got {outcome!r}"
                )
        return errors


# --------------------------------------------------------------------------- #
# §6.8.6 qa_contract.json
# --------------------------------------------------------------------------- #


@dataclass
class QaContract:
    """§6.8.6 ``qa_contract.json`` — the algebraic/property gate (G6) contract."""

    product_type: str
    interest_basis: Dict[str, Any]
    timing_convention: str
    terminal_age_policy: Dict[str, Any]
    function_mappings: Dict[str, str]
    tiers_enabled: List[str] = field(default_factory=list)
    tolerances: Dict[str, Any] = field(default_factory=dict)
    property_engine: Dict[str, Any] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "product_type": self.product_type,
            "interest_basis": dict(self.interest_basis),
            "timing_convention": self.timing_convention,
            "terminal_age_policy": dict(self.terminal_age_policy),
            "function_mappings": dict(self.function_mappings),
            "tiers_enabled": list(self.tiers_enabled),
            "tolerances": dict(self.tolerances),
            "property_engine": dict(self.property_engine),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QaContract":
        return cls(
            product_type=str(data.get("product_type", "")),
            interest_basis=dict(data.get("interest_basis") or {}),
            timing_convention=str(data.get("timing_convention", "")),
            terminal_age_policy=dict(data.get("terminal_age_policy") or {}),
            function_mappings=dict(data.get("function_mappings") or {}),
            tiers_enabled=list(data.get("tiers_enabled") or []),
            tolerances=dict(data.get("tolerances") or {}),
            property_engine=dict(data.get("property_engine") or {}),
            schema_version=int(data.get("schema_version", SCHEMA_VERSION)),
        )

    def validate(self) -> List[str]:
        errors: List[str] = []
        if self.schema_version != SCHEMA_VERSION:
            errors.append(f"schema_version must be {SCHEMA_VERSION}")
        if not self.product_type:
            errors.append("product_type is required")
        if not self.timing_convention:
            errors.append("timing_convention is required")
        if not self.interest_basis:
            errors.append("interest_basis is required")
        if not self.function_mappings:
            errors.append("function_mappings is required")
        if not isinstance(self.tiers_enabled, list) or not self.tiers_enabled:
            errors.append("tiers_enabled must be a non-empty array")
        return errors
