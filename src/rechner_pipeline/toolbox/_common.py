"""Shared deterministic-toolbox contract (§3.3 of MIGRATION.md).

Every gate command (`python -m rechner_pipeline.toolbox.<command>`) imports this
module to obey one contract:

* **stdout is exactly one JSON object and nothing else.** All human logs go to
  stderr. Use :func:`emit_result` / :func:`emit_json` to write stdout, and
  :func:`log` / :func:`get_logger` for stderr diagnostics.
* Inputs are explicit flags; an optional ``--request-json -`` reads one UTF-8
  JSON request object from stdin and coexists with explicit flags
  (:func:`read_request_json`, :func:`add_request_json_arg`).
* The result object carries the common fields from §3.3 / §6.8.1.
* SHA-256 helpers (:func:`file_sha256`, :func:`text_sha256`, :func:`hash_files`)
  feed ``input_hashes`` / ``output_hashes``.

This module contains **no gate logic** — only the contract surface.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import sys
import traceback
import warnings
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
    "write_gate_ledger",
    "force_utf8_stream",
    "utc_now",
]

# --------------------------------------------------------------------------- #
# Schema / status constants
# --------------------------------------------------------------------------- #

#: Schema version stamped on every toolbox result object (§6.8.1).
SCHEMA_VERSION: int = 1

STATUS_PASSED = "passed"
STATUS_FAILED = "failed"
STATUS_HUMAN_REVIEW = "human_review_required"

#: The only legal ``status`` values (§3.3).
STATUSES: tuple[str, ...] = (STATUS_PASSED, STATUS_FAILED, STATUS_HUMAN_REVIEW)


# --------------------------------------------------------------------------- #
# Standard exit codes (§3.3). Exit 0 means the selected gate passed.
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


#: Mapping of every standard exit code (name -> int), per §3.3. Includes the
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
# Human-review terminal-state exit codes (§6.7 / §6.8.3)
# --------------------------------------------------------------------------- #
#
# A human-review handoff is a *blocking, non-zero* terminal state: ``status`` is
# set to ``human_review_required`` while the process exit stays non-zero so the
# orchestrating skill cannot downgrade it to a warning (§3.3, §6.7). §6.8.3 names
# two mandatory human-review triggers and we map each to the standard exit code
# whose category it belongs to (§3.3), so the 8 command authors cannot diverge:
#
#   * ``"dossier"``  -> 40 (Exit.DOSSIER):   acceptance / dossier handoff — the
#       ``dossier`` gate (G8) decides mechanical acceptance and is where an
#       exhausted ``max_attempts`` run or an unresolved acceptance question
#       lands. 40 is the dossier/provenance category in §3.3.
#   * ``"coverage"`` -> 31 (Exit.ALGEBRAIC): sparse/none expectation-coverage or
#       missing-mortality-table handoff — these surface in the algebraic /
#       unknown-applicability gate (G6). 31 is the
#       "algebraic/property/unknown-applicability" category in §3.3, which is the
#       reviewer's chosen mapping for a sparse-coverage handoff.
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
# Gate-result ledger filename suffix (§6.8.2) — single source of truth
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
    """Map an exit code to the mirrored ``status`` (§6.8.1).

    ``0`` -> ``passed``; any non-zero code -> ``failed``. A command that ends in
    a human-review handoff must set ``status`` explicitly to
    ``human_review_required`` (the exit code remains non-zero and blocking).
    """
    return STATUS_PASSED if exit_code == Exit.OK else STATUS_FAILED


# --------------------------------------------------------------------------- #
# stderr logging
# --------------------------------------------------------------------------- #

_LOGGER_NAME = "rechner_pipeline.toolbox"


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

    This is the entry point every ``python -m rechner_pipeline.toolbox.<command>``
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

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        previous_pythonwarnings = os.environ.get("PYTHONWARNINGS")
        os.environ["PYTHONWARNINGS"] = "ignore"
        try:
            try:
                with contextlib.redirect_stdout(sys.stderr):
                    result = _coerce_result(main_callable(argv))
            except SystemExit:
                # argparse / explicit SystemExit: re-raise so the caller sees it.
                raise
            except BaseException as exc:  # noqa: BLE001 — convert to INTERNAL result
                traceback.print_exc(file=sys.stderr)
                result = build_result(
                    command=command_name,
                    gate_version="0.0.0",
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
# Common result object (§6.8.1)
# --------------------------------------------------------------------------- #


@dataclass
class ToolboxResult:
    """The common JSON-stdout result every toolbox command returns (§6.8.1).

    Required fields are always serialized; optional fields
    (``errors``, ``repair_hints``, ``warnings``, ``metrics``, ``diagnostics_path``)
    are omitted only when empty/unset. Per §6.8.1, ``errors`` and ``repair_hints``
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
        # errors / repair_hints are always present per §6.8.1 unless opted out.
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
    """Build a human-review terminal-state result (§6.7 / §6.8.3).

    Sets ``status="human_review_required"`` AND a consistent **blocking non-zero**
    exit code together so the 8 command authors cannot diverge. ``reason`` selects
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
    (Windows shell reliability, §3.3).
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
                key = str(path.resolve().relative_to(Path(resolved_base).resolve()))
            except ValueError:
                key = str(path)
        else:
            key = str(path)
        if key in out:
            continue
        out[key] = file_sha256(path)
    return out


# --------------------------------------------------------------------------- #
# Gate-result ledger writer (§6.8.2) — called by every gate command on BOTH the
# pass and fail paths so ``dossier`` (G8) can aggregate the run.
# --------------------------------------------------------------------------- #


def _gate_catalogue() -> Tuple[Dict[str, str], Tuple[str, ...]]:
    """Return ``(command -> gate-id, required-gate-ids)`` from the dossier.

    Imported lazily (inside the call) so ``_common`` — the lowest module in the
    import graph — never imports ``orchestrate.dossier`` at module load and the
    chain stays acyclic. By the time any gate command calls
    :func:`write_gate_ledger` at runtime, ``orchestrate.dossier`` is fully
    importable. If the import fails for any reason the catalogue is empty and the
    caller falls back to ``required=True`` (honest: an unknown gate still blocks).
    """
    try:
        from rechner_pipeline.orchestrate import dossier as _dossier

        command_to_gate = {command: gate for gate, command in _dossier.ALL_GATES}
        return command_to_gate, tuple(_dossier.REQUIRED_GATES)
    except Exception:  # noqa: BLE001 — never let provenance break a gate command
        return {}, ()


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
    """Write a §6.8.2 gate-result ledger entry for *result* and return its path.

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
            being accepted for a stable call contract across the parallel wave).
        attempt: 1-based attempt index (§6.8.2 ``attempt``).
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
        # Last-resort: a gate id is mandatory in §6.8.2; fall back to the command
        # name so the entry still validates and is honestly attributable.
        resolved_gate = result.command

    if required is None:
        resolved_required = resolved_gate in required_gates if required_gates else True
    else:
        resolved_required = required

    started = started_at or utc_now()
    ended = ended_at or started

    # Merge the result summary with the schema-fixed extras under ``summary`` so
    # nothing is lost while keeping the §6.8.2 field set intact.
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
    out_path.write_text(
        json.dumps(entry.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out_path
