"""Shared deterministic-toolbox contract.

Every gate command (`python -m rechner_pipeline.gates.<command>`) imports this
module to obey one contract:

* **stdout is exactly one JSON object and nothing else.** All human logs go to
  stderr. Use :func:`emit_result` / :func:`emit_json` to write stdout, and
  :func:`log` / :func:`get_logger` for stderr diagnostics.
* Inputs are explicit flags; an optional ``--request-json -`` reads one UTF-8
  JSON request object from stdin and coexists with explicit flags
  (:func:`read_request_json`, :func:`add_request_json_arg`).
* The result object carries the common contract fields.
* SHA-256 helpers (:func:`file_sha256`, :func:`text_sha256`, :func:`hash_files`)
  feed ``input_hashes`` / ``output_hashes``.
* Gate ledgers use a red start marker and atomic final replacement, so a crash
  or evidence-write failure can never leave a previous green run current.

This module contains **no gate logic** — only the contract surface.

Knoten: klv, system/assurance
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import sys
import tempfile
import traceback
import warnings
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import IO, Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple, Union

# Re-export the canonical hashing helpers so commands have a single import site.
from rechner_pipeline.models.manifest import file_sha256, text_sha256

__all__ = [
    "SCHEMA_VERSION",
    "EXIT",
    "Exit",
    "STATUS_PASSED",
    "STATUS_FAILED",
    "STATUS_HUMAN_REVIEW",
    "STATUSES",
    "ToolboxResult",
    "build_result",
    "human_review_result",
    "HUMAN_REVIEW_EXIT_CODES",
    "REPO_ROOT",
    "repo_root",
    "run_command",
    "GateArgumentParser",
    "GateCliContract",
    "parse_gate_args",
    "emit_json",
    "emit_result",
    "get_logger",
    "log",
    "add_request_json_arg",
    "read_request_json",
    "merge_request_into_args",
    "file_sha256",
    "text_sha256",
    "hash_files",
    "status_for_exit",
    "GATE_LEDGER_SUFFIX",
    "begin_gate_ledger_attempt",
    "finalize_gate_ledger",
    "write_gate_ledger",
    "force_utf8_stream",
    "utc_now",
]

# --------------------------------------------------------------------------- #
# Schema / status constants
# --------------------------------------------------------------------------- #

#: Schema version stamped on every toolbox result object.
SCHEMA_VERSION: int = 1

STATUS_PASSED = "passed"
STATUS_FAILED = "failed"
STATUS_HUMAN_REVIEW = "human_review_required"

#: The only legal ``status`` values.
STATUSES: tuple[str, ...] = (STATUS_PASSED, STATUS_FAILED, STATUS_HUMAN_REVIEW)


# --------------------------------------------------------------------------- #
# Standard exit codes. Exit 0 means the selected gate passed.
# --------------------------------------------------------------------------- #


class Exit:
    """Named standard exit codes. ``0`` (pass) is intentionally not listed here
    because it is the absence of a blocking failure, not a failure category."""

    OK = 0
    USAGE = 2  # usage/configuration
    EXTRACTION = 10  # extraction / InputBundle failure
    FILE_CONTRACT = 20  # file-contract / compile / schema failure
    SECURITY = 21  # static security failure
    CONVENTIONS = 22  # architecture / convention / import failure
    GOLDEN_MASTER = 30  # golden-master mismatch
    ALGEBRAIC = 31  # algebraic / property / unknown-applicability failure
    ROUNDTRIP = 32  # roundtrip / hash-stability failure
    DOSSIER = 40  # dossier / provenance failure
    INTERNAL = 50  # internal toolbox error


#: Mapping of every standard exit code (name -> int). Includes the
#: full blocking set {2,10,20,21,22,30,31,32,40,50}.
EXIT: Dict[str, int] = {
    "OK": Exit.OK,
    "USAGE": Exit.USAGE,
    "EXTRACTION": Exit.EXTRACTION,
    "FILE_CONTRACT": Exit.FILE_CONTRACT,
    "SECURITY": Exit.SECURITY,
    "CONVENTIONS": Exit.CONVENTIONS,
    "GOLDEN_MASTER": Exit.GOLDEN_MASTER,
    "ALGEBRAIC": Exit.ALGEBRAIC,
    "ROUNDTRIP": Exit.ROUNDTRIP,
    "DOSSIER": Exit.DOSSIER,
    "INTERNAL": Exit.INTERNAL,
}

#: The blocking (non-zero) standard exit codes as an ordered tuple.
BLOCKING_EXIT_CODES: tuple[int, ...] = (2, 10, 20, 21, 22, 30, 31, 32, 40, 50)

#: The full set of standard exit codes including ``0`` (pass). Single source of
#: truth re-exported by :mod:`rechner_pipeline.models.schemas`.
STANDARD_EXIT_CODES: frozenset[int] = frozenset({Exit.OK, *BLOCKING_EXIT_CODES})


# --------------------------------------------------------------------------- #
# Human-review terminal-state exit codes
# --------------------------------------------------------------------------- #
#
# A human-review handoff is a *blocking, non-zero* terminal state: ``status`` is
# set to ``human_review_required`` while the process exit stays non-zero so the
# orchestrating skill cannot downgrade it to a warning. There are two mandatory
# human-review triggers and we map each to the standard exit code whose category
# it belongs to, so the command authors cannot diverge:
#
#   * ``"dossier"``  -> 40 (Exit.DOSSIER):   acceptance / dossier handoff — the
#       ``dossier`` gate (G8) decides mechanical acceptance and is where an
#       exhausted ``max_attempts`` run or an unresolved acceptance question
#       lands. 40 is the dossier/provenance category.
#   * ``"coverage"`` -> 31 (Exit.ALGEBRAIC): sparse/none expectation-coverage or
#       missing-mortality-table handoff — these surface in the algebraic /
#       unknown-applicability gate (G6). 31 is the
#       "algebraic/property/unknown-applicability" category, which is the chosen
#       mapping for a sparse-coverage handoff.
#
#: Canonical ``reason -> exit code`` mapping for human-review terminal states.
HUMAN_REVIEW_EXIT_CODES: Dict[str, int] = {
    "dossier": Exit.DOSSIER,  # 40 — acceptance / dossier handoff
    "coverage": Exit.ALGEBRAIC,  # 31 — sparse/none coverage handoff
}


# --------------------------------------------------------------------------- #
# Repo root (for repo-relative hash keys)
# --------------------------------------------------------------------------- #
# _common.py lives at <repo>/src/rechner_pipeline/toolbox/_common.py, so the repo
# root is four parents up. Computed once; callers may override per-call.
REPO_ROOT: Path = Path(__file__).resolve().parents[3]


def repo_root() -> Path:
    """Return the repository root used as the default ``base`` for hash maps."""
    return REPO_ROOT


# --------------------------------------------------------------------------- #
# Gate-result ledger filename suffix — single source of truth
# --------------------------------------------------------------------------- #
#
# Circular-import decision: ``_common`` is the lowest module in the import graph
# (``orchestrate.dossier`` -> ``models.schemas`` -> ``_common``), so it cannot
# import ``orchestrate.dossier`` at module load. We therefore make ``_common``
# the single source of truth for the ledger filename suffix and have
# ``orchestrate.dossier`` import it from here (the non-circular direction).
# ``orchestrate.dossier`` still re-exports ``GATE_LEDGER_SUFFIX`` so existing
# call sites (``provenance.GATE_LEDGER_SUFFIX``) keep working unchanged.
#
#: Filename convention for a gate-result ledger entry written into the
#: diagnostics dir: ``<command>.gate.json`` (e.g. ``golden_master.gate.json``).
GATE_LEDGER_SUFFIX: str = ".gate.json"


def utc_now() -> str:
    """Return a UTC ISO-8601 timestamp (deterministic-friendly, timezone-aware)."""
    return datetime.now(timezone.utc).isoformat()


def status_for_exit(exit_code: int) -> str:
    """Map an exit code to the mirrored ``status``.

    ``0`` -> ``passed``; any non-zero code -> ``failed``. A command that ends in
    a human-review handoff must set ``status`` explicitly to
    ``human_review_required`` (the exit code remains non-zero and blocking).
    """
    return STATUS_PASSED if exit_code == Exit.OK else STATUS_FAILED


# --------------------------------------------------------------------------- #
# stderr logging
# --------------------------------------------------------------------------- #

_LOGGER_NAME = "rechner_pipeline.gates"


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a logger that writes **only to stderr** (stdout stays JSON-pure).

    Idempotent: repeated calls do not stack handlers.
    """
    logger = logging.getLogger(name or _LOGGER_NAME)
    if not any(
        isinstance(h, logging.StreamHandler) and getattr(h, "stream", None) is sys.stderr
        for h in logger.handlers
    ):
        handler = logging.StreamHandler(stream=sys.stderr)
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def log(message: str, *, level: int = logging.INFO, name: Optional[str] = None) -> None:
    """Emit a human log line to stderr (never stdout)."""
    get_logger(name).log(level, message)


# --------------------------------------------------------------------------- #
# stdout JSON emission (exactly one object, nothing else)
# --------------------------------------------------------------------------- #


def force_utf8_stream(stream: Optional[IO[str]]) -> Optional[IO[str]]:
    """Best-effort force *stream* to UTF-8, returning it for chaining.

    Python text streams that wrap a buffer expose ``reconfigure`` (PEP 528/540);
    on Windows the process stdout/stderr default to the console code page (often
    cp1252), which raises :class:`UnicodeEncodeError` when we emit real UTF-8
    JSON (``ensure_ascii=False``) containing a BOM or other non-cp1252 char. We
    reconfigure to UTF-8 so emission cannot crash. Streams that lack
    ``reconfigure`` (``io.StringIO`` in tests, custom wrappers) are returned
    unchanged — :func:`emit_json` stays robust for those separately.
    """
    if stream is None:
        return stream
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        with contextlib.suppress(Exception):
            reconfigure(encoding="utf-8")
    return stream


def emit_json(obj: Mapping[str, Any], *, stream: Optional[IO[str]] = None) -> None:
    """Write exactly one JSON object to stdout and nothing else.

    Uses ``ensure_ascii=False`` and ``sort_keys=False`` so field order is the
    builder's order, with a single trailing newline. Emission is hardened so a
    stream whose encoding cannot represent a character (e.g. a Windows cp1252
    console that was never reconfigured) never raises
    :class:`UnicodeEncodeError`: we first try a UTF-8 ``reconfigure``, and as a
    last resort write UTF-8 bytes through the stream's underlying buffer. This
    keeps ``ensure_ascii=False`` (real UTF-8 output) while making it safe.
    """
    out = stream if stream is not None else sys.stdout
    payload = json.dumps(obj, ensure_ascii=False) + "\n"
    try:
        out.write(payload)
        out.flush()
        return
    except UnicodeEncodeError:
        pass
    # The stream's encoding cannot represent the payload. Try to upgrade it to
    # UTF-8 in place, then retry the normal text write.
    force_utf8_stream(out)
    try:
        out.write(payload)
        out.flush()
        return
    except UnicodeEncodeError:
        pass
    # Last resort: write UTF-8 bytes straight to the underlying binary buffer so
    # valid JSON still reaches the consumer instead of a bare traceback.
    buffer = getattr(out, "buffer", None)
    if buffer is not None:
        buffer.write(payload.encode("utf-8"))
        buffer.flush()
        return
    # No buffer available (pure text sink): escape to ASCII as the final fallback
    # so at least valid JSON is emitted rather than crashing the process.
    out.write(json.dumps(obj, ensure_ascii=True) + "\n")
    out.flush()


def emit_result(result: "ToolboxResult", *, stream: Optional[IO[str]] = None) -> int:
    """Serialize a :class:`ToolboxResult` to stdout and return its exit code."""
    emit_json(result.to_dict(), stream=stream)
    return result.exit_code


# --------------------------------------------------------------------------- #
# stdout-purity command wrapper (the __main__ entry point for every command)
# --------------------------------------------------------------------------- #

#: A command body returns a result, optionally paired with an explicit exit code.
MainCallable = Callable[
    [Optional[List[str]]],
    Union["ToolboxResult", Tuple["ToolboxResult", int]],
]


@dataclass(frozen=True)
class GateCliContract:
    """Metadata needed to evidence an argument error before a gate starts.

    ``argparse`` normally exits before a command body can resolve its ledger
    directory.  Keeping the small amount of routing metadata on the parser
    lets :func:`run_command` turn that early exit into the same structured
    result and current red ledger used by later usage failures.
    """

    command: str
    gate: str
    gate_version: str
    diagnostics_from: Optional[str] = None
    decision_gate_choices: Tuple[str, ...] = ()
    sensitive_options: Tuple[str, ...] = ()


class GateArgumentError(ValueError):
    """An ``argparse`` or request-JSON usage error of a gate command."""

    def __init__(
        self,
        message: str,
        *,
        contract: GateCliContract,
        namespace: Optional[argparse.Namespace] = None,
    ) -> None:
        super().__init__(message)
        self.contract = contract
        self.namespace = namespace


class GateArgumentParser(argparse.ArgumentParser):
    """Argument parser whose failures are finalized by ``run_command``.

    The inherited help action deliberately keeps its normal ``SystemExit(0)``
    path.  Only parser errors are converted to :class:`GateArgumentError`.
    """

    def __init__(
        self,
        *args: Any,
        gate_contract: GateCliContract,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.gate_contract = gate_contract

    def error(self, message: str) -> None:
        raise GateArgumentError(message, contract=self.gate_contract)


def _argv_option(argv: List[str], dest: str) -> Optional[str]:
    """Read the last simple store-option value without invoking argparse."""
    option = "--" + dest.replace("_", "-")
    found: Optional[str] = None
    for index, token in enumerate(argv):
        if token.startswith(option + "="):
            found = token.split("=", 1)[1]
        elif token == option and index + 1 < len(argv):
            candidate = argv[index + 1]
            if not candidate.startswith("--"):
                found = candidate
    return found


def _argument_value(
    error: GateArgumentError,
    argv: List[str],
    dest: str,
) -> Optional[str]:
    namespace = error.namespace
    if namespace is not None:
        value = getattr(namespace, dest, None)
        if value is not None and not isinstance(value, (list, dict)):
            return str(value)
    return _argv_option(argv, dest)


def _redact_argv(argv: List[str], sensitive_options: Tuple[str, ...]) -> List[str]:
    """Redact values of configured CLI options before ledger persistence."""
    redacted = list(argv)
    for dest in sensitive_options:
        option = "--" + dest.replace("_", "-")
        hide_next = False
        for index, token in enumerate(redacted):
            if hide_next:
                redacted[index] = "<extern-redigiert>"
                hide_next = False
            elif token == option:
                hide_next = True
            elif token.startswith(option + "="):
                redacted[index] = option + "=<extern-redigiert>"
    return redacted


def _argument_error_result(
    error: GateArgumentError,
    argv: List[str],
) -> "ToolboxResult":
    """Persist and return the structured usage result for an early parse error."""
    contract = error.contract
    diagnostics_raw = _argument_value(error, argv, "diagnostics_dir")
    if diagnostics_raw:
        diagnostics_dir = Path(diagnostics_raw)
    else:
        parent_raw = (
            _argument_value(error, argv, contract.diagnostics_from)
            if contract.diagnostics_from
            else None
        )
        if parent_raw and contract.diagnostics_from == "fall":
            diagnostics_dir = Path(parent_raw) / "abgeleitet" / "diagnostics"
        elif parent_raw and contract.diagnostics_from == "out_dir":
            diagnostics_dir = Path(parent_raw) / "diagnostics"
        else:
            diagnostics_dir = Path.cwd() / "runs" / "diagnostics"

    command = contract.command
    gate = contract.gate
    decision_gate = _argument_value(error, argv, "gate")
    if decision_gate in contract.decision_gate_choices:
        command = f"{command}_{decision_gate.lower().replace('-', '')}"
        gate = f"P9.{decision_gate}"

    result = build_result(
        command=command,
        gate=gate,
        gate_version=contract.gate_version,
        exit_code=Exit.USAGE,
        errors=[{"code": "usage", "message": str(error)}],
    )
    ledger_start_error = begin_gate_ledger_attempt(
        command=command,
        gate=gate,
        gate_version=contract.gate_version,
        diagnostics_dir=diagnostics_dir,
        repo_root=(
            Path(repo_root_raw)
            if (repo_root_raw := _argument_value(error, argv, "repo_root"))
            else None
        ),
        command_line=_redact_argv(argv, contract.sensitive_options),
    )
    if ledger_start_error is not None:
        return ledger_start_error
    return finalize_gate_ledger(result)


def _coerce_result(
    value: Union["ToolboxResult", Tuple["ToolboxResult", int]],
) -> "ToolboxResult":
    """Normalize a command body's return value to a :class:`ToolboxResult`."""
    if isinstance(value, tuple):
        result, _exit = value  # exit_code lives on the result; tuple form is for ergonomics
        return result
    return value


def run_command(
    main_callable: MainCallable, argv: Optional[List[str]] = None
) -> int:
    """Run a toolbox command body with a hard stdout-purity guarantee.

    This is the entry point every ``python -m rechner_pipeline.gates.<command>``
    ``__main__`` block should call::

        if __name__ == "__main__":
            raise SystemExit(run_command(main))

    where ``main(argv) -> ToolboxResult`` (or ``-> (ToolboxResult, exit_code)``).

    Guarantees, regardless of library chatter (pandas/oletools banners, ``print``,
    ``warnings.warn``):

    * Warnings are silenced for the body (``warnings.simplefilter("ignore")`` and
      ``PYTHONWARNINGS=ignore`` at runtime) so they never reach stdout.
    * ``sys.stdout`` is redirected to ``sys.stderr`` for the **duration** of
      ``main_callable`` (via :func:`contextlib.redirect_stdout`), so any library
      print lands on stderr, not stdout.
    * Only after the body completes is the real stdout restored and the single
      JSON object emitted on it (via :func:`emit_result`). Net effect: exactly
      one JSON object reaches the real stdout.
    * An unhandled exception from the body becomes an INTERNAL (exit ``50``)
      ``status="failed"`` result with the exception summarized in ``errors``; the
      traceback goes to stderr only — never to stdout.

    Returns the result's exit code (suitable for :class:`SystemExit`).
    """
    # Force the process stdout/stderr to UTF-8 up front so the single JSON emit
    # (``ensure_ascii=False``) cannot hit a Windows cp1252 console and raise
    # ``UnicodeEncodeError`` -> empty stdout + bare traceback. Guarded for streams
    # that lack ``reconfigure``.
    force_utf8_stream(sys.stdout)
    force_utf8_stream(sys.stderr)

    real_stdout = sys.stdout
    command_name = getattr(main_callable, "__module__", "toolbox").rsplit(".", 1)[-1]
    command_argv = list(argv if argv is not None else sys.argv[1:])

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        previous_pythonwarnings = os.environ.get("PYTHONWARNINGS")
        os.environ["PYTHONWARNINGS"] = "ignore"
        try:
            try:
                with contextlib.redirect_stdout(sys.stderr):
                    result = _coerce_result(main_callable(argv))
            except GateArgumentError as exc:
                result = _argument_error_result(exc, command_argv)
            except SystemExit:
                # argparse --help / explicit SystemExit: keep its successful
                # help path separate from the structured gate-result contract.
                raise
            except BaseException as exc:  # noqa: BLE001 — convert to INTERNAL result
                traceback.print_exc(file=sys.stderr)
                active_attempt = _ACTIVE_GATE_LEDGER_ATTEMPT.get()
                result = build_result(
                    command=(
                        active_attempt.command if active_attempt else command_name
                    ),
                    gate=(active_attempt.gate if active_attempt else None),
                    gate_version=(
                        active_attempt.gate_version
                        if active_attempt else "0.0.0"
                    ),
                    status=STATUS_FAILED,
                    exit_code=Exit.INTERNAL,
                    errors=[
                        {
                            "code": "internal_error",
                            "type": type(exc).__name__,
                            "message": str(exc),
                        }
                    ],
                    repair_hints=[],
                )
                if active_attempt is not None:
                    result = finalize_gate_ledger(result)

            # A command that began a ledger attempt but returned without its
            # gate-local finalizer must still replace the red start marker with
            # the actual result. This is also a safety net for newly added
            # early-return paths.
            if _ACTIVE_GATE_LEDGER_ATTEMPT.get() is not None:
                result = finalize_gate_ledger(result)

            # Emit the single JSON object INSIDE the protected region so any
            # emit failure (e.g. an encoding error :func:`emit_json` could not
            # recover from) becomes an INTERNAL (exit 50) result on a usable
            # stream, never a bare traceback with empty stdout. ``emit_json`` is
            # already hardened against encoding errors; this is defense in depth.
            try:
                return emit_result(result, stream=real_stdout)
            except BaseException as exc:  # noqa: BLE001 — last-resort INTERNAL emit
                traceback.print_exc(file=sys.stderr)
                fallback = build_result(
                    command=command_name,
                    gate_version="0.0.0",
                    status=STATUS_FAILED,
                    exit_code=Exit.INTERNAL,
                    errors=[
                        {
                            "code": "emit_error",
                            "type": type(exc).__name__,
                            "message": str(exc),
                        }
                    ],
                    repair_hints=[],
                )
                # ASCII-safe so this final emit cannot itself fail on encoding.
                emit_json(
                    {**fallback.to_dict(), "_emit_fallback": True},
                    stream=real_stdout,
                )
                return fallback.exit_code
        finally:
            if previous_pythonwarnings is None:
                os.environ.pop("PYTHONWARNINGS", None)
            else:
                os.environ["PYTHONWARNINGS"] = previous_pythonwarnings


# --------------------------------------------------------------------------- #
# Common result object
# --------------------------------------------------------------------------- #


@dataclass
class ToolboxResult:
    """The common JSON-stdout result every toolbox command returns.

    Required fields are always serialized; optional fields
    (``errors``, ``repair_hints``, ``warnings``, ``metrics``, ``diagnostics_path``)
    are omitted only when empty/unset. ``errors`` and ``repair_hints``
    are *always present* (possibly empty) so the agent can repair without parsing
    prose; pass ``always_repairable=True`` (default) to enforce that.
    """

    command: str
    status: str
    gate_version: str
    paths: Dict[str, Any] = field(default_factory=dict)
    summary: Dict[str, Any] = field(default_factory=dict)
    input_hashes: Dict[str, str] = field(default_factory=dict)
    gate: Optional[str] = None
    exit_code: int = Exit.OK
    errors: List[Any] = field(default_factory=list)
    repair_hints: List[Any] = field(default_factory=list)
    warnings: List[Any] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    output_hashes: Dict[str, str] = field(default_factory=dict)
    diagnostics_path: Optional[str] = None
    schema_version: int = SCHEMA_VERSION
    always_repairable: bool = True

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(
                f"invalid status {self.status!r}; must be one of {STATUSES}"
            )

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
        out["summary"] = dict(self.summary)
        out["input_hashes"] = dict(self.input_hashes)
        if self.output_hashes:
            out["output_hashes"] = dict(self.output_hashes)
        if self.metrics:
            out["metrics"] = dict(self.metrics)
        if self.warnings:
            out["warnings"] = list(self.warnings)
        # errors / repair_hints are always present unless opted out.
        if self.always_repairable or self.errors:
            out["errors"] = list(self.errors)
        if self.always_repairable or self.repair_hints:
            out["repair_hints"] = list(self.repair_hints)
        if self.diagnostics_path is not None:
            out["diagnostics_path"] = self.diagnostics_path
        return out


def build_result(
    *,
    command: str,
    gate_version: str,
    status: Optional[str] = None,
    exit_code: int = Exit.OK,
    gate: Optional[str] = None,
    paths: Optional[Mapping[str, Any]] = None,
    summary: Optional[Mapping[str, Any]] = None,
    input_hashes: Optional[Mapping[str, str]] = None,
    output_hashes: Optional[Mapping[str, str]] = None,
    errors: Optional[Iterable[Any]] = None,
    repair_hints: Optional[Iterable[Any]] = None,
    warnings: Optional[Iterable[Any]] = None,
    metrics: Optional[Mapping[str, Any]] = None,
    diagnostics_path: Optional[str] = None,
    always_repairable: bool = True,
) -> ToolboxResult:
    """Build a :class:`ToolboxResult` with the common fields.

    If ``status`` is omitted it is derived from ``exit_code`` via
    :func:`status_for_exit`. Provide ``status`` explicitly to set
    ``human_review_required``.
    """
    resolved_status = status if status is not None else status_for_exit(exit_code)
    return ToolboxResult(
        command=command,
        status=resolved_status,
        gate_version=gate_version,
        gate=gate,
        exit_code=exit_code,
        paths=dict(paths or {}),
        summary=dict(summary or {}),
        input_hashes=dict(input_hashes or {}),
        output_hashes=dict(output_hashes or {}),
        errors=list(errors or []),
        repair_hints=list(repair_hints or []),
        warnings=list(warnings or []),
        metrics=dict(metrics or {}),
        diagnostics_path=diagnostics_path,
        always_repairable=always_repairable,
    )


def human_review_result(
    *,
    command: str,
    gate_version: str,
    reason: str = "dossier",
    exit_code: Optional[int] = None,
    gate: Optional[str] = None,
    paths: Optional[Mapping[str, Any]] = None,
    summary: Optional[Mapping[str, Any]] = None,
    input_hashes: Optional[Mapping[str, str]] = None,
    output_hashes: Optional[Mapping[str, str]] = None,
    errors: Optional[Iterable[Any]] = None,
    repair_hints: Optional[Iterable[Any]] = None,
    warnings: Optional[Iterable[Any]] = None,
    metrics: Optional[Mapping[str, Any]] = None,
    diagnostics_path: Optional[str] = None,
    always_repairable: bool = True,
) -> ToolboxResult:
    """Build a human-review terminal-state result.

    Sets ``status="human_review_required"`` AND a consistent **blocking non-zero**
    exit code together so the command authors cannot diverge. ``reason`` selects
    the canonical exit code from :data:`HUMAN_REVIEW_EXIT_CODES`:

    * ``"dossier"``  -> 40 (:attr:`Exit.DOSSIER`): acceptance / dossier handoff,
      including ``max_attempts`` exhaustion.
    * ``"coverage"`` -> 31 (:attr:`Exit.ALGEBRAIC`): sparse/none coverage or
      missing-mortality-table handoff.

    Pass ``exit_code`` explicitly to override; it must be a blocking (non-zero)
    standard code or ``ValueError`` is raised (a human-review handoff is never a
    pass).
    """
    if exit_code is None:
        if reason not in HUMAN_REVIEW_EXIT_CODES:
            raise ValueError(
                f"unknown human-review reason {reason!r}; "
                f"expected one of {tuple(HUMAN_REVIEW_EXIT_CODES)} or an explicit exit_code"
            )
        exit_code = HUMAN_REVIEW_EXIT_CODES[reason]
    if exit_code not in BLOCKING_EXIT_CODES:
        raise ValueError(
            f"human-review exit_code {exit_code} must be a blocking standard code "
            f"{BLOCKING_EXIT_CODES}"
        )
    return build_result(
        command=command,
        gate_version=gate_version,
        status=STATUS_HUMAN_REVIEW,
        exit_code=exit_code,
        gate=gate,
        paths=paths,
        summary=summary,
        input_hashes=input_hashes,
        output_hashes=output_hashes,
        errors=errors,
        repair_hints=repair_hints,
        warnings=warnings,
        metrics=metrics,
        diagnostics_path=diagnostics_path,
        always_repairable=always_repairable,
    )


# --------------------------------------------------------------------------- #
# --request-json - stdin reader (coexists with explicit flags)
# --------------------------------------------------------------------------- #


def add_request_json_arg(parser: Any) -> None:
    """Register the standard ``--request-json`` flag on an argparse parser.

    Value ``-`` means "read one UTF-8 JSON request object from stdin". A path is
    also accepted for convenience. Explicit flags remain available alongside it
    (Windows shell reliability).
    """
    parser.add_argument(
        "--request-json",
        dest="request_json",
        default=None,
        metavar="(- | PATH)",
        help="Read one UTF-8 JSON request object from stdin ('-') or a file path. "
        "Explicit flags take precedence over request keys.",
    )


def read_request_json(
    source: Optional[str], *, stdin: Optional[IO[str]] = None
) -> Dict[str, Any]:
    """Read one UTF-8 JSON request object.

    ``source`` is the ``--request-json`` value: ``None`` -> ``{}``;
    ``-`` -> read all of stdin; otherwise treat as a file path. The decoded
    value must be a JSON object.
    """
    if source is None:
        return {}
    if source == "-":
        raw = (stdin if stdin is not None else sys.stdin).read()
    else:
        raw = Path(source).read_text(encoding="utf-8")
    if not raw.strip():
        return {}
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise ValueError("--request-json must decode to a JSON object")
    return obj


def merge_request_into_args(args: Any, request: Mapping[str, Any]) -> Any:
    """Fill unset argparse fields from a request object (flags win).

    A field is considered unset when its current value is ``None``. The mutated
    ``args`` namespace is returned for chaining.
    """
    for key, value in request.items():
        if hasattr(args, key) and getattr(args, key) is None:
            setattr(args, key, value)
    return args


def parse_gate_args(
    parser: GateArgumentParser,
    argv: Optional[List[str]],
) -> argparse.Namespace:
    """Parse flags and the optional request object under the gate contract.

    Parser failures and unreadable or malformed request JSON become one typed
    usage error.  :func:`run_command` catches that error, writes the current red
    gate ledger and emits exactly one structured result on stdout.  ``--help``
    remains the parser's untouched successful ``SystemExit(0)`` path.
    """
    args = parser.parse_args(argv)
    try:
        request = read_request_json(args.request_json)
    except (OSError, UnicodeError, ValueError) as exc:
        raise GateArgumentError(
            f"ungueltiges --request-json: {exc}",
            contract=parser.gate_contract,
            namespace=args,
        ) from exc
    return merge_request_into_args(args, request)


# --------------------------------------------------------------------------- #
# Hashing helpers for input_hashes / output_hashes
# --------------------------------------------------------------------------- #


#: Sentinel so callers can request "the original path string as given" by passing
#: ``base=None`` explicitly, distinct from the repo-root default.
_HASH_BASE_DEFAULT = object()


def hash_files(
    paths: Iterable[Any],
    *,
    base: Union[Path, None, Any] = _HASH_BASE_DEFAULT,
    missing_ok: bool = False,
) -> Dict[str, str]:
    """Return an ordered ``{path-string: sha256}`` map for the given files.

    Keys are **repo-relative by default**, so ``input_hashes`` / ``output_hashes``
    are portable across machines (e.g. ``generated\\test_run.py``) and never leak
    absolute OS paths:

    * ``base`` omitted -> keys are relative to the repository root
      (:data:`REPO_ROOT`); a path outside the repo falls back to its own string.
    * ``base=<Path>``  -> keys are relative to that base (same fallback).
    * ``base=None``    -> keys are the path string exactly as given (opt out of
      relativization).

    Duplicate path strings are collapsed (first occurrence wins). Missing/non-file
    paths raise ``FileNotFoundError`` unless ``missing_ok`` is set, in which case
    they are skipped.
    """
    if base is _HASH_BASE_DEFAULT:
        resolved_base: Optional[Path] = REPO_ROOT
    else:
        resolved_base = base  # type: ignore[assignment]

    out: Dict[str, str] = {}
    for raw in paths:
        path = Path(raw)
        if not path.is_file():
            if missing_ok:
                continue
            raise FileNotFoundError(str(path))
        if resolved_base is not None:
            try:
                key = path.resolve().relative_to(
                    Path(resolved_base).resolve()
                ).as_posix()
            except ValueError:
                key = path.resolve().as_posix()
        else:
            key = str(path)
        if key in out:
            continue
        out[key] = file_sha256(path)
    return out


# --------------------------------------------------------------------------- #
# Gate-result ledger writer — called by every gate command on BOTH the
# pass and fail paths so ``dossier`` (G8) can aggregate the run.
# --------------------------------------------------------------------------- #



#: Die Gates dieses Systems: (Gate-Id, Kommando-Name). Frueher fuehrte
#: der Assurance-Orchestrator diese Liste fuer die Portierungs-Kette;
#: seit deren Ausserbetriebnahme sind es die Gates der Migrations- und
#: Bestandsseite, die einzeln laufen.
def load_gate_ledger(
    diagnostics_dir: Path,
) -> Tuple[List["GateLedgerEntry"], List[Dict[str, Any]]]:
    """Load all gate-result ledger entries from *diagnostics_dir*.

    Reads every ``*<GATE_LEDGER_SUFFIX>`` file (``<command>.gate.json``), sorted
    by filename for determinism. Returns ``(entries, read_errors)`` where each
    ``read_errors`` item is ``{"path", "error"}`` for a file that could not be
    parsed as a JSON object. Parse failures do not raise — the caller turns them
    into blocking dossier errors.
    """
    from rechner_pipeline.models.schemas import GateLedgerEntry

    entries: List["GateLedgerEntry"] = []
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
        try:
            entries.append(GateLedgerEntry.from_dict(payload))
        except (TypeError, ValueError) as exc:
            read_errors.append({"path": str(path), "error": str(exc)})
    return entries, read_errors


ALL_GATES: Tuple[Tuple[str, str], ...] = (
    ("G0.extraction-manifest", "extract"),
    ("O0.abox-merge", "abox_merge"),
    ("O1.abox-contract", "abox_validate"),
    ("O3.generation-golden-master", "generation_golden"),
    ("P9.gate-entscheid", "gate_entscheid"),
    ("B1.bestand-contract", "bestand_validate"),
    ("G2-vorlage.migrationsabnahme", "abnahmebericht"),
)

def _gate_catalogue() -> Tuple[Dict[str, str], Tuple[str, ...]]:
    """Return ``(command -> gate-id, required-gate-ids)`` from the dossier.

    Der Katalog steht seit der Ausserbetriebnahme des Portierungspfads
    hier statt in einem Orchestrator: es gibt keine feste Kette mehr,
    die abgearbeitet wird, sondern einzelne Gates, die je Vorgang
    aufgerufen werden. Ein Gate, das hier fehlt, gilt als ``required``
    — ehrlicher als es stillschweigend als optional zu behandeln.
    """
    return ({command: gate for gate, command in ALL_GATES},
            tuple(gate for gate, _ in ALL_GATES))


def write_gate_ledger(
    result: "ToolboxResult",
    diagnostics_dir: Union[str, Path],
    *,
    repo_root: Optional[Path] = None,
    attempt: int = 1,
    started_at: Optional[str] = None,
    ended_at: Optional[str] = None,
    command_line: Optional[Iterable[str]] = None,
    gate: Optional[str] = None,
    required: Optional[bool] = None,
) -> Path:
    """Write a gate-result ledger entry for *result* and return its path.

    Builds a :class:`rechner_pipeline.models.schemas.GateLedgerEntry` from a
    :class:`ToolboxResult` (mapping ``command``/``gate``, ``gate_version``,
    ``status``, ``exit_code``, ``input_hashes``/``output_hashes``,
    ``summary``/``metrics``, ``errors`` and real wall-clock ISO-8601 UTC
    timestamps), ``.validate()``s it, and writes it to
    ``<diagnostics_dir>/<command>`` + :data:`GATE_LEDGER_SUFFIX` — the SAME
    suffix the ``dossier`` loader globs — so the round-trip counts toward
    ``gates_present``.

    Callable on BOTH the pass and fail paths (``status`` and ``exit_code`` are
    taken verbatim from *result*). Schema-fixed extras that have no first-class
    field on :class:`GateLedgerEntry` (``exit_code``, ``ended_at``,
    ``command_line``, ``output_hashes``, ``metrics``, ``errors``) are recorded
    under ``summary`` so they round-trip without breaking validation.

    Args:
        result: the command's :class:`ToolboxResult`.
        diagnostics_dir: directory the ``dossier`` loader globs; created if absent.
        repo_root: reserved for repo-relative provenance (currently unused beyond
            being accepted for a stable call contract).
        attempt: 1-based attempt index.
        started_at / ended_at: ISO-8601 UTC timestamps; default to ``utc_now()``.
        command_line: the argv that ran the gate, recorded in ``summary`` when given.
        gate / required: explicit overrides; otherwise derived from
            ``result.gate`` and the dossier gate catalogue.

    Raises:
        ValueError: if the assembled :class:`GateLedgerEntry` fails ``validate()``.
    """
    from rechner_pipeline.models.schemas import GateLedgerEntry

    command_to_gate, required_gates = _gate_catalogue()

    resolved_gate = gate or result.gate or command_to_gate.get(result.command, "")
    if not resolved_gate:
        # Last-resort: a gate id is mandatory; fall back to the command
        # name so the entry still validates and is honestly attributable.
        resolved_gate = result.command

    if required is None:
        # Jedes Gate blockt. Ein unbekanntes erst recht — ein Gate
        # stillschweigend als optional zu fuehren waere die gefaehrlichere
        # Annahme (P2: keine stillen Zustaende).
        resolved_required = True
    else:
        resolved_required = required

    started = started_at or utc_now()
    ended = ended_at or started

    # Merge the result summary with the schema-fixed extras under ``summary`` so
    # nothing is lost while keeping the ledger field set intact.
    summary: Dict[str, Any] = dict(result.summary)
    summary.setdefault("exit_code", result.exit_code)
    summary.setdefault("ended_at", ended)
    if result.metrics:
        summary.setdefault("metrics", dict(result.metrics))
    if result.output_hashes:
        summary.setdefault("output_hashes", dict(result.output_hashes))
    if result.errors:
        summary.setdefault("errors", list(result.errors))
    if command_line is not None:
        summary.setdefault("command_line", list(command_line))

    entry = GateLedgerEntry(
        gate=resolved_gate,
        command=result.command,
        gate_version=result.gate_version,
        required=resolved_required,
        status=result.status,
        attempt=attempt,
        started_at=started,
        input_hashes=dict(result.input_hashes),
        diagnostics_path=result.diagnostics_path,
        summary=summary,
    )

    validation_errors = entry.validate()
    if validation_errors:
        raise ValueError(
            "write_gate_ledger: GateLedgerEntry failed validation: "
            + "; ".join(validation_errors)
        )

    diag_dir = Path(diagnostics_dir)
    diag_dir.mkdir(parents=True, exist_ok=True)
    out_path = diag_dir / f"{result.command}{GATE_LEDGER_SUFFIX}"
    payload = json.dumps(entry.to_dict(), ensure_ascii=False, indent=2) + "\n"
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{out_path.name}.", suffix=".tmp", dir=diag_dir
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            fd = -1
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, out_path)
    finally:
        if fd >= 0:
            os.close(fd)
        with contextlib.suppress(FileNotFoundError):
            temp_path.unlink()
    return out_path


@dataclass(frozen=True)
class _GateLedgerAttempt:
    """Write context for the one active gate invocation in this context."""

    command: str
    gate: str
    gate_version: str
    diagnostics_dir: Path
    repo_root: Optional[Path]
    started_at: str
    command_line: Tuple[str, ...]


_ACTIVE_GATE_LEDGER_ATTEMPT: ContextVar[Optional[_GateLedgerAttempt]] = ContextVar(
    "active_gate_ledger_attempt", default=None
)


def _ledger_write_failure(
    result: "ToolboxResult", exc: BaseException
) -> "ToolboxResult":
    """Turn an unavailable current ledger into a blocking gate result."""
    return build_result(
        command=result.command,
        gate=result.gate,
        gate_version=result.gate_version,
        exit_code=Exit.INTERNAL,
        paths=result.paths,
        summary={
            "gate_ledger_written": False,
            "gate_result_status": result.status,
            "gate_result_exit_code": result.exit_code,
        },
        input_hashes=result.input_hashes,
        output_hashes=result.output_hashes,
        errors=[
            *result.errors,
            {
                "code": "gate_ledger",
                "type": type(exc).__name__,
                "message": f"Aktueller Gate-Beleg konnte nicht geschrieben werden: {exc}",
            },
        ],
        repair_hints=result.repair_hints,
        warnings=result.warnings,
        metrics=result.metrics,
        diagnostics_path=result.diagnostics_path,
    )


def begin_gate_ledger_attempt(
    *,
    command: str,
    gate: str,
    gate_version: str,
    diagnostics_dir: Union[str, Path],
    repo_root: Optional[Path] = None,
    started_at: Optional[str] = None,
    command_line: Optional[Iterable[str]] = None,
) -> Optional["ToolboxResult"]:
    """Invalidate an older latest ledger and persist a red start marker.

    The marker is written before gate work that may raise unexpectedly. Thus a
    crash can never leave the previous green ``<command>.gate.json`` as the
    apparent current evidence. Failure to invalidate or write the marker is
    itself a blocking INTERNAL result.
    """
    active = _ACTIVE_GATE_LEDGER_ATTEMPT.get()
    if active is not None:
        if (
            active.command == command
            and active.gate == gate
            and active.gate_version == gate_version
            and active.diagnostics_dir == Path(diagnostics_dir)
        ):
            return None
        _ACTIVE_GATE_LEDGER_ATTEMPT.set(None)
        return _ledger_write_failure(
            build_result(
                command=command,
                gate=gate,
                gate_version=gate_version,
                exit_code=Exit.INTERNAL,
            ),
            RuntimeError(
                f"Gate-Ledger-Lauf {active.command!r} ist noch aktiv"
            ),
        )
    started = started_at or utc_now()
    attempt = _GateLedgerAttempt(
        command=command,
        gate=gate,
        gate_version=gate_version,
        diagnostics_dir=Path(diagnostics_dir),
        repo_root=repo_root,
        started_at=started,
        command_line=tuple(command_line or ()),
    )
    _ACTIVE_GATE_LEDGER_ATTEMPT.set(attempt)
    marker = build_result(
        command=command,
        gate=gate,
        gate_version=gate_version,
        exit_code=Exit.INTERNAL,
        summary={"gate_attempt_started": True},
        errors=[{
            "code": "gate_attempt_incomplete",
            "message": "Gate-Lauf begonnen, aber noch nicht abgeschlossen",
        }],
    )
    out_path = attempt.diagnostics_dir / f"{command}{GATE_LEDGER_SUFFIX}"
    try:
        attempt.diagnostics_dir.mkdir(parents=True, exist_ok=True)
        if out_path.exists() or out_path.is_symlink():
            out_path.unlink()
        write_gate_ledger(
            marker,
            attempt.diagnostics_dir,
            repo_root=attempt.repo_root,
            started_at=attempt.started_at,
            ended_at=utc_now(),
            command_line=attempt.command_line,
        )
    except Exception as exc:  # noqa: BLE001 — evidence failure is the result
        _ACTIVE_GATE_LEDGER_ATTEMPT.set(None)
        log(f"{command}: gate-ledger start failed: {exc}")
        return _ledger_write_failure(marker, exc)
    return None


def finalize_gate_ledger(result: "ToolboxResult") -> "ToolboxResult":
    """Atomically replace the active marker with *result*.

    A write failure never preserves a green command result: the caller gets an
    INTERNAL failure, while the already persisted red marker remains current.
    """
    attempt = _ACTIVE_GATE_LEDGER_ATTEMPT.get()
    if attempt is None:
        return _ledger_write_failure(
            result, RuntimeError("kein aktiver Gate-Ledger-Lauf")
        )
    try:
        write_gate_ledger(
            result,
            attempt.diagnostics_dir,
            repo_root=attempt.repo_root,
            started_at=attempt.started_at,
            ended_at=utc_now(),
            command_line=attempt.command_line,
        )
    except Exception as exc:  # noqa: BLE001 — evidence failure is the result
        log(f"{result.command}: gate-ledger write failed: {exc}")
        return _ledger_write_failure(result, exc)
    finally:
        _ACTIVE_GATE_LEDGER_ATTEMPT.set(None)
    return result
