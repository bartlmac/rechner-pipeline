"""Typed builders/validators for the acceptance JSON schemas.

Covers:

* common toolbox result object (:class:`CommonResult`)
* gate-result ledger entry (:class:`GateLedgerEntry`)
* strict, content-addressed P9 decision snapshot (:class:`P9Snapshot`)
* ``qa_report.json`` aggregate (:class:`QaReport`)
* upgraded ``run_dossier.json`` v2 delta (:class:`RunDossierV2Delta`)
* ``qa_contract.json`` algebraic-gate contract (:class:`QaContract`)

Each class is a plain ``dataclass`` with ``to_dict`` / ``from_dict`` and a
``validate(obj) -> list[error]`` (no external schema library). ``validate`` runs
on the dataclass instance and returns human-readable error strings; an empty list
means the object satisfies the schema.

The common-result object here is a *schema view* of the common toolbox result
used for serialization round-trips; the live toolbox emitter is
:class:`rechner_pipeline.gates._common.ToolboxResult`. Both produce the same
field set.

Knoten: system/assurance
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from rechner_pipeline.models.manifest import FileHashRecord, ManifestWarning

# Single source of truth for status values and exit codes lives in ``_common``
# (the live toolbox contract). Import — never re-declare — them here so the
# schema view and the emitter can never diverge.
from rechner_pipeline.gates._common import (
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
    "P9Snapshot",
    "P9_SNAPSHOT_SCHEMA_VERSION",
    "P9_GATE_VERSION",
    "P9_FREIGABE_VERFAHREN",
    "p9_freigabe_nachricht",
    "p9_snapshot_sha256",
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
P9_SNAPSHOT_SCHEMA_VERSION = 3
P9_GATE_VERSION = "0.4.0"
P9_FREIGABE_VERFAHREN = "hmac-sha256-v1"
P9_GATES: tuple[str, ...] = ("G-1", "G-2", "G-T")


def _kanonisches_json(data: Any) -> bytes:
    return json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(c in "0123456789abcdef" for c in value)
    )


def _iso_zeit_fehler(name: str, value: Any) -> Optional[str]:
    if not isinstance(value, str) or not value:
        return f"{name} must be a non-empty ISO-8601 timestamp"
    try:
        zeit = datetime.fromisoformat(value)
    except ValueError:
        return f"{name} must be an ISO-8601 timestamp"
    if zeit.tzinfo is None or zeit.utcoffset() is None:
        return f"{name} must include a timezone"
    return None


def _hashmap_errors(prefix: str, mapping: Any) -> List[str]:
    errs: List[str] = []
    if not isinstance(mapping, dict):
        return [f"{prefix} must be an object"]
    for key, value in mapping.items():
        if not isinstance(key, str) or not key:
            errs.append(f"{prefix} contains a non-string or empty key")
        if not _is_sha256(value):
            errs.append(f"{prefix}[{key!r}] is not a SHA-256 hex string")
    return errs


def _ledger_summary_errors(
    summary: Any, status: Any, started_at: Any
) -> List[str]:
    if not isinstance(summary, dict):
        return ["summary must be an object"]
    errors: List[str] = []
    exit_code = summary.get("exit_code")
    if type(exit_code) is not int or exit_code not in _STANDARD_EXIT_CODES:
        errors.append("summary.exit_code must be a standard integer exit code")
    elif (exit_code == 0) != (status == "passed"):
        errors.append("status must mirror summary.exit_code (0 <-> passed)")
    zeit_fehler = _iso_zeit_fehler("summary.ended_at", summary.get("ended_at"))
    if zeit_fehler:
        errors.append(zeit_fehler)
    if not zeit_fehler and _iso_zeit_fehler("started_at", started_at) is None:
        if datetime.fromisoformat(summary["ended_at"]) < datetime.fromisoformat(
            started_at
        ):
            errors.append("summary.ended_at must not precede started_at")
    if "output_hashes" in summary:
        errors.extend(_hashmap_errors("summary.output_hashes", summary["output_hashes"]))
    if "metrics" in summary and not isinstance(summary["metrics"], dict):
        errors.append("summary.metrics must be an object")
    if "errors" in summary and not isinstance(summary["errors"], list):
        errors.append("summary.errors must be an array")
    if "command_line" in summary and (
        not isinstance(summary["command_line"], list)
        or any(not isinstance(value, str) for value in summary["command_line"])
    ):
        errors.append("summary.command_line must be an array of strings")
    return errors


# --------------------------------------------------------------------------- #
# Common toolbox result object
# --------------------------------------------------------------------------- #


@dataclass
class CommonResult:
    """Common toolbox result (schema view)."""

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
        # status mirrors exit code: 0 <-> passed, non-zero <-> not passed.
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
# Gate-result ledger entry
# --------------------------------------------------------------------------- #


@dataclass
class GateLedgerEntry:
    """Gate-result ledger entry; one per gate execution."""

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
    schema_version: int = SCHEMA_VERSION

    _REQUIRED_FIELDS = frozenset({
        "schema_version", "gate", "command", "gate_version", "required",
        "status", "attempt", "started_at", "input_hashes", "summary",
    })
    _OPTIONAL_FIELDS = frozenset({"diagnostics_path"})

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "schema_version": self.schema_version,
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
        errors = cls.validate_payload(data)
        if errors:
            raise ValueError("ungueltiger Gate-Ledger: " + "; ".join(errors))
        return cls(
            gate=data["gate"],
            command=data["command"],
            gate_version=data["gate_version"],
            required=data["required"],
            status=data["status"],
            attempt=data["attempt"],
            started_at=data["started_at"],
            input_hashes=dict(data["input_hashes"]),
            diagnostics_path=data.get("diagnostics_path"),
            summary=dict(data["summary"]),
            schema_version=data["schema_version"],
        )

    @classmethod
    def validate_payload(cls, data: Any) -> List[str]:
        """Validate raw JSON without lossy truthy/string coercions.

        A ledger is evidence.  In particular, ``"false"`` must never become
        ``True`` and a missing field must never be synthesized by ``from_dict``.
        """
        if not isinstance(data, dict):
            return ["ledger entry must be a JSON object"]
        errors: List[str] = []
        fields = set(data)
        missing = sorted(cls._REQUIRED_FIELDS - fields)
        unknown = sorted(fields - cls._REQUIRED_FIELDS - cls._OPTIONAL_FIELDS)
        if missing:
            errors.append(f"required fields missing: {missing}")
        if unknown:
            errors.append(f"unknown fields: {unknown}")
        if missing:
            return errors
        if type(data.get("schema_version")) is not int or data.get(
            "schema_version"
        ) != SCHEMA_VERSION:
            errors.append(f"schema_version must be {SCHEMA_VERSION}")
        for name in ("gate", "command", "gate_version"):
            if not isinstance(data.get(name), str) or not data[name]:
                errors.append(f"{name} must be a non-empty string")
        if type(data.get("required")) is not bool:
            errors.append("required must be a boolean")
        if data.get("status") not in STATUS_VALUES:
            errors.append(
                f"status must be one of {STATUS_VALUES}, got {data.get('status')!r}"
            )
        if type(data.get("attempt")) is not int or data["attempt"] < 1:
            errors.append("attempt must be a positive integer")
        zeit_fehler = _iso_zeit_fehler("started_at", data.get("started_at"))
        if zeit_fehler:
            errors.append(zeit_fehler)
        errors.extend(_hashmap_errors("input_hashes", data.get("input_hashes")))
        errors.extend(_ledger_summary_errors(
            data.get("summary"), data.get("status"), data.get("started_at")
        ))
        diagnostics = data.get("diagnostics_path")
        if diagnostics is not None and (
            not isinstance(diagnostics, str) or not diagnostics
        ):
            errors.append("diagnostics_path must be a non-empty string or null")
        return errors

    def validate(self) -> List[str]:
        errors: List[str] = []
        if self.schema_version != SCHEMA_VERSION:
            errors.append(f"schema_version must be {SCHEMA_VERSION}")
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
        if type(self.attempt) is not int or self.attempt < 1:
            errors.append("attempt must be a positive integer")
        zeit_fehler = _iso_zeit_fehler("started_at", self.started_at)
        if zeit_fehler:
            errors.append(zeit_fehler)
        errors.extend(_hashmap_errors("input_hashes", self.input_hashes))
        errors.extend(_ledger_summary_errors(
            self.summary, self.status, self.started_at
        ))
        if self.diagnostics_path is not None and (
            not isinstance(self.diagnostics_path, str) or not self.diagnostics_path
        ):
            errors.append("diagnostics_path must be a non-empty string or null")
        return errors


# --------------------------------------------------------------------------- #
# P9 decision snapshot
# --------------------------------------------------------------------------- #


def p9_freigabe_nachricht(data: Dict[str, Any]) -> bytes:
    """Return the domain-separated bytes authorized by the human key."""
    kern = {
        key: value
        for key, value in data.items()
        if key not in {"snapshot_sha256", "freigabe"}
    }
    return b"rechner-pipeline:p9-freigabe:v1\0" + _kanonisches_json(kern)


def p9_snapshot_sha256(data: Dict[str, Any]) -> str:
    """Hash every persisted field except the self-addressing hash itself."""
    kern = {key: value for key, value in data.items() if key != "snapshot_sha256"}
    return hashlib.sha256(_kanonisches_json(kern)).hexdigest()


@dataclass
class P9Snapshot:
    """Strict schema view of an immutable, content-addressed P9 snapshot."""

    data: Dict[str, Any]

    _BASE_FIELDS = frozenset({
        "schema_version", "command", "gate_version", "gate", "entscheid",
        "entscheider", "rolle", "begruendung", "fall", "artefakt_hashes",
        "system", "vorgaenger", "entschieden_am", "snapshot_sha256",
    })

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "P9Snapshot":
        errors = cls.validate_payload(data)
        if errors:
            raise ValueError("ungueltiger P9-Snapshot: " + "; ".join(errors))
        return cls(data=dict(data))

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.data)

    def validate(self) -> List[str]:
        return self.validate_payload(self.data)

    @classmethod
    def validate_payload(cls, data: Any) -> List[str]:
        if not isinstance(data, dict):
            return ["snapshot must be a JSON object"]
        errors: List[str] = []
        gate = data.get("gate")
        expected_fields = set(cls._BASE_FIELDS)
        if gate == "G-2":
            expected_fields.update({
                "o3_belege", "fall_scope", "gate_dag_version", "pflichtbelege",
            })
        if data.get("entscheid") == "angenommen":
            expected_fields.add("freigabe")
        fields = set(data)
        missing = sorted(expected_fields - fields)
        unknown = sorted(fields - expected_fields)
        if missing:
            errors.append(f"required fields missing: {missing}")
        if unknown:
            errors.append(f"unknown fields: {unknown}")
        if missing:
            return errors

        if type(data.get("schema_version")) is not int or data.get(
            "schema_version"
        ) != P9_SNAPSHOT_SCHEMA_VERSION:
            errors.append(
                f"schema_version must be {P9_SNAPSHOT_SCHEMA_VERSION}"
            )
        if data.get("command") != "gate_entscheid":
            errors.append("command must be 'gate_entscheid'")
        if data.get("gate_version") != P9_GATE_VERSION:
            errors.append(f"gate_version must be {P9_GATE_VERSION!r}")
        if gate not in P9_GATES:
            errors.append(f"gate must be one of {P9_GATES}, got {gate!r}")
        if data.get("entscheid") not in ("angenommen", "abgelehnt"):
            errors.append("entscheid must be 'angenommen' or 'abgelehnt'")
        if data.get("rolle") not in ("mensch", "agent"):
            errors.append("rolle must be 'mensch' or 'agent'")
        if data.get("rolle") == "agent" and data.get("entscheid") == "angenommen":
            errors.append("an agent cannot authorize an accepted human gate")
        for name in ("entscheider", "begruendung", "fall"):
            if not isinstance(data.get(name), str) or not data[name].strip():
                errors.append(f"{name} must be a non-empty string")

        hashes = data.get("artefakt_hashes")
        errors.extend(_hashmap_errors("artefakt_hashes", hashes))
        if data.get("entscheid") == "angenommen" and isinstance(hashes, dict):
            for key in ("eingang.json", "abgeleitet/abox/abox.json"):
                if key not in hashes:
                    errors.append(f"artefakt_hashes must contain {key!r}")

        system = data.get("system")
        system_fields = {"commit", "branch", "dirty", "quellcode_sha256"}
        if not isinstance(system, dict) or set(system) != system_fields:
            errors.append(f"system must contain exactly {sorted(system_fields)}")
        else:
            for key, value in system.items():
                if not isinstance(value, str) or not value:
                    errors.append(f"system.{key} must be a non-empty string")
            if not _is_sha256(system.get("quellcode_sha256")):
                errors.append("system.quellcode_sha256 is not a SHA-256")

        vorgaenger = data.get("vorgaenger")
        if not isinstance(vorgaenger, list):
            errors.append("vorgaenger must be an array")
        else:
            gueltige_vorgaenger = [
                value for value in vorgaenger if _is_sha256(value)
            ]
            if len(gueltige_vorgaenger) != len(set(gueltige_vorgaenger)):
                errors.append("vorgaenger must not contain duplicates")
            for value in vorgaenger:
                if not _is_sha256(value):
                    errors.append("every vorgaenger entry must be a SHA-256")

        zeit_fehler = _iso_zeit_fehler(
            "entschieden_am", data.get("entschieden_am")
        )
        if zeit_fehler:
            errors.append(zeit_fehler)

        if gate == "G-2":
            if data.get("fall_scope") not in ("tarif", "bestand"):
                errors.append("fall_scope must be 'tarif' or 'bestand'")
            if (
                not isinstance(data.get("gate_dag_version"), str)
                or not data["gate_dag_version"]
            ):
                errors.append("gate_dag_version must be a non-empty string")
            pflichtbelege = data.get("pflichtbelege")
            if not isinstance(pflichtbelege, dict):
                errors.append("pflichtbelege must be an object")
            elif data.get("entscheid") == "angenommen" and not pflichtbelege:
                errors.append("pflichtbelege must not be empty for acceptance")
            else:
                for rolle, belege in pflichtbelege.items():
                    if (
                        not isinstance(rolle, str) or not rolle
                        or re.fullmatch(r"[a-z0-9_]+", rolle) is None
                    ):
                        errors.append(f"invalid pflichtbelege role {rolle!r}")
                    if not isinstance(belege, list) or not belege:
                        errors.append(
                            f"pflichtbelege[{rolle!r}] must be a non-empty array"
                        )
                        continue
                    gueltige_belege = [
                        value for value in belege if _is_sha256(value)
                    ]
                    if len(gueltige_belege) != len(set(gueltige_belege)):
                        errors.append(
                            f"pflichtbelege[{rolle!r}] contains duplicates"
                        )
                    for value in belege:
                        if not _is_sha256(value):
                            errors.append(
                                f"pflichtbelege[{rolle!r}] contains a non-SHA-256"
                            )
            o3_belege = data.get("o3_belege")
            if not isinstance(o3_belege, dict):
                errors.append("o3_belege must be an object")
            else:
                for generation, belege in o3_belege.items():
                    if (
                        not isinstance(generation, str)
                        or re.fullmatch(r"[a-z0-9_]+/[a-z0-9_]+", generation)
                        is None
                    ):
                        errors.append(f"invalid O3 generation key {generation!r}")
                    if not isinstance(belege, list):
                        errors.append(f"o3_belege[{generation!r}] must be an array")
                        continue
                    if data.get("entscheid") == "angenommen" and not belege:
                        errors.append(
                            f"o3_belege[{generation!r}] must not be empty"
                        )
                    gueltige_belege = [
                        value for value in belege if _is_sha256(value)
                    ]
                    if len(gueltige_belege) != len(set(gueltige_belege)):
                        errors.append(
                            f"o3_belege[{generation!r}] contains duplicates"
                        )
                    for value in belege:
                        if not _is_sha256(value):
                            errors.append(
                                f"o3_belege[{generation!r}] contains a non-SHA-256"
                            )

        if data.get("entscheid") == "angenommen":
            freigabe = data.get("freigabe")
            required = {"verfahren", "schluessel_sha256", "signatur"}
            if not isinstance(freigabe, dict) or set(freigabe) != required:
                errors.append(f"freigabe must contain exactly {sorted(required)}")
            else:
                if freigabe.get("verfahren") != P9_FREIGABE_VERFAHREN:
                    errors.append(
                        f"freigabe.verfahren must be {P9_FREIGABE_VERFAHREN!r}"
                    )
                for name in ("schluessel_sha256", "signatur"):
                    if not _is_sha256(freigabe.get(name)):
                        errors.append(f"freigabe.{name} is not a SHA-256")

        snapshot_sha = data.get("snapshot_sha256")
        if not _is_sha256(snapshot_sha):
            errors.append("snapshot_sha256 is not a SHA-256")
        elif p9_snapshot_sha256(data) != snapshot_sha:
            errors.append("snapshot_sha256 does not match the canonical content")
        return errors


# --------------------------------------------------------------------------- #
# qa_report.json
# --------------------------------------------------------------------------- #


@dataclass
class QaReport:
    """``qa_report.json`` mechanical acceptance aggregate.

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
        """Derive acceptance from the populated fields."""
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
        # Consistency between decision and accepted.
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
# Upgraded run_dossier.json (v2) delta
# --------------------------------------------------------------------------- #


@dataclass
class RunDossierV2Delta:
    """The *delta* over the base ``run_dossier.json`` structure.

    Represents only the new/added keys: the bumped ``schema_version`` (2), the
    extended ``run.options`` provenance, ``run.cli``, ``qa_report``,
    ``gate_results``, ``attempts``, and ``input_bundle``. The full v2 dossier is
    the base structure merged with this delta (see :meth:`merge_into`).
    """

    schema_version: int = 2
    run_cli: Dict[str, Any] = field(default_factory=dict)
    options_extra: Dict[str, Any] = field(default_factory=dict)
    qa_report: Dict[str, Any] = field(default_factory=dict)
    gate_results: List[Dict[str, Any]] = field(default_factory=list)
    attempts: List[Dict[str, Any]] = field(default_factory=list)
    input_bundle: Dict[str, Any] = field(default_factory=dict)

    #: The new option keys added over the base option set.
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
        """Produce the full v2 dossier by layering this delta onto a base
        dossier dict. The base dict is not mutated."""
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
# qa_contract.json
# --------------------------------------------------------------------------- #


@dataclass
class QaContract:
    """``qa_contract.json`` — the algebraic/property gate (G6) contract."""

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
