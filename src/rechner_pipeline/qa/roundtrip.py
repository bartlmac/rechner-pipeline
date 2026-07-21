"""Roundtrip / hash-stability engine — gate **G7** (MIGRATION.md §3.3 row line
1691, §3.5 G7 line 1749, roundtrip paragraph line 1763, §6.7 mortality-table /
``tafeln.xml`` rules lines 2595-2610).

G7 is the *reproducibility* gate: it proves that the calculator's deterministic
artifacts are stable across serialization, re-extraction, and recomputation. It
is reviewed (NOT LLM-generated) code; the generated kernel is only *executed*
(under :mod:`rechner_pipeline.qa.fs_confine`), never trusted.

Three independent checks (any failure is blocking, exit ``32`` upstream):

1. :func:`check_tafeln_canonical` — ``tafeln.xml`` must parse to a canonical
   *semantic* mortality-table object, serialize back, and re-parse to the SAME
   canonical object AND the SAME SHA-256. The canonical serialization is fully
   deterministic (sorted tables, ages ascending, fixed float repr, sorted
   attributes, LF newlines, no trailing whitespace), so a stable input is a
   fixed point of ``parse -> serialize``. Per §6.7 the data is validated as it
   is canonicalized: **duplicate ages**, a ``qx`` **outside [0, 1]**, or a
   **non-finite** ``qx`` is a hard failure (the agent must never fabricate or
   smuggle an invalid mortality curve through the roundtrip).

2. :func:`check_reextraction_stable` — re-running the extraction engine
   (:class:`rechner_pipeline.adapters.excel.ExcelAdapter`) twice into a
   deterministic staging location *under* ``--repo-root`` must produce identical
   hashes for the MATERIAL artifacts (the semantic surface: raw sheet CSVs,
   ``*_compressed.csv``, ``*_scalar.json``, ``*_table_values.csv``,
   ``names_manager.csv``, source-logic text). The manifest JSON is intentionally
   excluded from the material set because it embeds absolute, machine-specific
   paths; material drift between two runs is a determinism failure.

3. :func:`check_recompute_stable` — running ``test_run.golden_master_outputs()``
   in FRESH child processes (reusing the golden_master / fs_confine execution
   pattern; ``--info-dir`` MUST live under ``--repo-root`` so the confined child
   may read it) must yield an IDENTICAL canonical output hash across repeats. A
   kernel whose output varies between runs (time/random/dict-iteration/float
   noise) is non-deterministic and fails.

This module contains no CLI/ledger wiring — that lives in
:mod:`rechner_pipeline.toolbox.roundtrip`.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rechner_pipeline.qa import fs_confine

__all__ = [
    "RoundtripError",
    "MortalityTable",
    "CanonicalTafeln",
    "parse_tafeln",
    "serialize_tafeln",
    "canonical_tafeln_sha256",
    "TafelnResult",
    "check_tafeln_canonical",
    "ReextractionResult",
    "check_reextraction_stable",
    "RecomputeResult",
    "check_recompute_stable",
]


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


class RoundtripError(ValueError):
    """Raised when a ``tafeln.xml`` is structurally or semantically invalid.

    Carries a stable ``code`` so the command layer can map it to a repair hint
    without parsing prose.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# --------------------------------------------------------------------------- #
# Canonical mortality-table model
# --------------------------------------------------------------------------- #
#
# The canonical semantic object is intentionally minimal and order-independent
# on input but fully ordered on output: a table is a name plus an age->qx map.
# Two ``tafeln.xml`` files are the SAME canonical object iff they have the same
# set of tables, each with the same (age, qx) pairs. Equality therefore does NOT
# depend on element order, attribute order, whitespace, or float spelling in the
# source — only on the validated numeric content.

def _canon_float(value: float) -> str:
    """Deterministic, exactly round-trippable text for a qx value.

    Uses Python's shortest-round-tripping float repr (``repr(float)``), which is
    the unique shortest decimal string that parses back to the *identical* IEEE-
    754 double — so ``float(_canon_float(x)) == x`` for every finite ``x`` and the
    serialization is a TRUE fixpoint at full precision (no 12-decimal truncation
    that would corrupt a faithfully-extracted high-precision DAV table, §6.7).
    The result is normalized to plain (non-exponent) decimal notation so the on-
    disk spelling is platform-stable and human-auditable; ``repr`` only emits
    exponents far outside the qx domain ``[0, 1]``, so this is purely defensive.
    """
    # value is guaranteed finite and in [0, 1] by _require_finite_qx.
    text = repr(float(value))
    if "e" in text or "E" in text:
        # Defensive: expand any scientific notation to a fixed-point spelling
        # that still round-trips exactly (qx in [0, 1] never reaches here).
        from decimal import Decimal

        text = format(Decimal(text), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


@dataclass(frozen=True)
class MortalityTable:
    """One canonical mortality table: a name and ascending (age, qx) pairs."""

    name: str
    entries: Tuple[Tuple[int, float], ...]  # sorted ascending by age, unique ages

    def to_element(self) -> ET.Element:
        el = ET.Element("table", {"name": self.name})
        for age, qx in self.entries:
            ET.SubElement(el, "entry", {"age": str(age), "qx": _canon_float(qx)})
        return el


@dataclass(frozen=True)
class CanonicalTafeln:
    """Canonical container: tables sorted by name, each with sorted entries."""

    tables: Tuple[MortalityTable, ...]

    def to_xml_bytes(self) -> bytes:
        return serialize_tafeln(self)


# --------------------------------------------------------------------------- #
# Parse / validate
# --------------------------------------------------------------------------- #


def _require_finite_qx(table_name: str, age: int, raw_qx: str) -> float:
    try:
        qx = float(raw_qx)
    except (TypeError, ValueError):
        raise RoundtripError(
            "invalid_qx",
            f"table {table_name!r} age {age}: qx {raw_qx!r} is not a number",
        )
    if not math.isfinite(qx):
        raise RoundtripError(
            "invalid_qx",
            f"table {table_name!r} age {age}: qx {qx!r} is not finite",
        )
    if qx < 0.0 or qx > 1.0:
        raise RoundtripError(
            "invalid_qx",
            f"table {table_name!r} age {age}: qx {qx} is outside [0, 1]",
        )
    return qx


def parse_tafeln(xml_text: str) -> CanonicalTafeln:
    """Parse ``tafeln.xml`` text into a validated :class:`CanonicalTafeln`.

    Accepted shape (deliberately permissive on input ordering/whitespace)::

        <tafeln>
          <table name="DAV1994_T_M">
            <entry age="0" qx="0.011687"/>
            <entry age="1" qx="0.001008"/>
          </table>
        </tafeln>

    An empty ``<tafeln></tafeln>`` is a valid canonical object with zero tables
    (the AS-IS placeholder file). Raises :class:`RoundtripError` on malformed
    XML, a missing required attribute, a non-integer age, a **duplicate age**
    within a table, or a ``qx`` that is non-finite or outside ``[0, 1]``.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise RoundtripError("xml_parse", f"tafeln.xml is not well-formed XML: {exc}")

    if root.tag != "tafeln":
        raise RoundtripError(
            "xml_root",
            f"tafeln.xml root element must be <tafeln>, got <{root.tag}>",
        )

    tables: List[MortalityTable] = []
    seen_names: set[str] = set()
    for tbl in root.findall("table"):
        name = tbl.get("name")
        if not name:
            raise RoundtripError("missing_attr", "a <table> is missing the 'name' attribute")
        if name in seen_names:
            raise RoundtripError("duplicate_table", f"duplicate table name {name!r}")
        seen_names.add(name)

        by_age: Dict[int, float] = {}
        for entry in tbl.findall("entry"):
            raw_age = entry.get("age")
            raw_qx = entry.get("qx")
            if raw_age is None or raw_qx is None:
                raise RoundtripError(
                    "missing_attr",
                    f"table {name!r}: an <entry> is missing 'age' or 'qx'",
                )
            try:
                age = int(raw_age)
            except (TypeError, ValueError):
                raise RoundtripError(
                    "invalid_age",
                    f"table {name!r}: age {raw_age!r} is not an integer",
                )
            if age in by_age:
                raise RoundtripError(
                    "duplicate_age",
                    f"table {name!r}: duplicate age {age}",
                )
            by_age[age] = _require_finite_qx(name, age, raw_qx)

        entries = tuple(sorted(by_age.items()))
        tables.append(MortalityTable(name=name, entries=entries))

    tables.sort(key=lambda t: t.name)
    return CanonicalTafeln(tables=tuple(tables))


# --------------------------------------------------------------------------- #
# Serialize (canonical, deterministic)
# --------------------------------------------------------------------------- #


def serialize_tafeln(canonical: CanonicalTafeln) -> bytes:
    """Serialize a :class:`CanonicalTafeln` to deterministic UTF-8 XML bytes.

    Fully canonical: tables sorted by name, entries ascending by age, attribute
    order fixed (``name``; ``age`` then ``qx``), 2-space indentation, LF
    newlines, a single trailing newline, and the fixed :func:`_canon_float` qx
    spelling. A stable input is therefore a fixed point of
    ``parse -> serialize`` at the byte level.
    """
    lines: List[str] = ['<?xml version="1.0" encoding="UTF-8"?>']
    if not canonical.tables:
        lines.append("<tafeln></tafeln>")
        return ("\n".join(lines) + "\n").encode("utf-8")

    lines.append("<tafeln>")
    for table in canonical.tables:  # already sorted by name
        lines.append(f'  <table name="{_xml_attr_escape(table.name)}">')
        for age, qx in table.entries:  # already sorted by age
            lines.append(f'    <entry age="{age}" qx="{_canon_float(qx)}"/>')
        lines.append("  </table>")
    lines.append("</tafeln>")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _xml_attr_escape(value: str) -> str:
    """Escape the minimal set for a double-quoted XML attribute value."""
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def canonical_tafeln_sha256(canonical: CanonicalTafeln) -> str:
    """SHA-256 of the canonical XML serialization (the gate's emitted hash)."""
    return sha256(serialize_tafeln(canonical)).hexdigest()


# --------------------------------------------------------------------------- #
# Check 1 — tafeln.xml canonical roundtrip
# --------------------------------------------------------------------------- #


@dataclass
class TafelnResult:
    ok: bool
    canonical_sha256: Optional[str] = None
    table_count: int = 0
    entry_count: int = 0
    error_code: Optional[str] = None
    error_message: Optional[str] = None


def check_tafeln_canonical(tafeln_path: Path) -> TafelnResult:
    """Run the ``tafeln.xml`` parse -> serialize -> parse canonical roundtrip.

    Passes iff the file parses+validates, and the canonical object AND its
    SHA-256 are invariant under one serialize/re-parse cycle. Returns a
    :class:`TafelnResult`; never raises for a content/validation problem (those
    are reported via ``error_code``), only a genuinely unreadable file surfaces
    as an ``io`` error code.
    """
    try:
        raw = tafeln_path.read_text(encoding="utf-8")
    except OSError as exc:
        return TafelnResult(
            ok=False, error_code="io", error_message=f"cannot read tafeln.xml: {exc}"
        )

    try:
        first = parse_tafeln(raw)
    except RoundtripError as exc:
        return TafelnResult(ok=False, error_code=exc.code, error_message=exc.message)

    first_bytes = serialize_tafeln(first)
    first_sha = sha256(first_bytes).hexdigest()

    # Canonicality is defined by SERIALIZATION idempotence, not by float-object
    # identity. The canonical SHA is the gate's emitted, source-of-truth hash:
    # a file is canonical iff ``serialize(parse(serialize(x))) == serialize(x)``
    # at the byte level. Comparing the parsed float *objects* would spuriously
    # FAIL high-precision qx (e.g. 16 significant decimals): the first parse
    # keeps full binary-float precision while the re-parse sees the canonical
    # decimal spelling, so the objects differ even though BOTH serialize to the
    # identical bytes/SHA. The serialization is the only thing the gate hashes,
    # ships, and re-extracts against — so byte-equal serializations ARE canonical.
    try:
        second = parse_tafeln(first_bytes.decode("utf-8"))
    except RoundtripError as exc:  # pragma: no cover — our own output must re-parse
        return TafelnResult(
            ok=False,
            error_code="reparse",
            error_message=f"canonical serialization failed to re-parse: {exc.message}",
        )
    second_bytes = serialize_tafeln(second)
    second_sha = sha256(second_bytes).hexdigest()

    table_count = len(first.tables)
    entry_count = sum(len(t.entries) for t in first.tables)

    if first_bytes != second_bytes:
        return TafelnResult(
            ok=False,
            canonical_sha256=first_sha,
            table_count=table_count,
            entry_count=entry_count,
            error_code="non_canonical",
            error_message=(
                "tafeln.xml is not a fixed point of parse->serialize "
                f"(sha {first_sha} != {second_sha})"
            ),
        )

    return TafelnResult(
        ok=True,
        canonical_sha256=first_sha,
        table_count=table_count,
        entry_count=entry_count,
    )


# --------------------------------------------------------------------------- #
# Check 2 — re-extraction material-hash stability
# --------------------------------------------------------------------------- #
#
# The "material" artifacts are the source-neutral semantic surface (§3.4 table):
# raw sheet CSVs, the compressed CSVs, scalar JSONs, table-value CSVs, the names
# manager, and source-logic text. The manifest JSON is excluded because it
# records absolute machine-specific paths (its hash would differ by staging dir,
# not by content), and ``diagnostics``/ledger files are excluded as side
# artifacts.

_MATERIAL_SUFFIXES: Tuple[str, ...] = (
    ".csv",
    "_compressed.csv",
    "_scalar.json",
    "_table_values.csv",
    ".txt",
)


def _material_hashes(out_dir: Path) -> Dict[str, str]:
    """Return ``{relative-name: sha256}`` for every material artifact under
    *out_dir*, keyed by the path relative to *out_dir* (so two different staging
    directories produce identical keys for identical content)."""
    out: Dict[str, str] = {}
    if not out_dir.is_dir():
        return out
    for path in sorted(out_dir.rglob("*"), key=lambda p: p.as_posix()):
        if not path.is_file():
            continue
        name = path.name
        if name == "export_manifest.json":
            continue  # absolute-path-bearing; not a material semantic artifact
        if not any(name.endswith(suffix) for suffix in _MATERIAL_SUFFIXES):
            continue
        rel = path.relative_to(out_dir).as_posix()
        out[rel] = sha256(path.read_bytes()).hexdigest()
    return out


@dataclass
class ReextractionResult:
    ok: bool
    run_a_hashes: Dict[str, str] = field(default_factory=dict)
    run_b_hashes: Dict[str, str] = field(default_factory=dict)
    drifted: List[str] = field(default_factory=list)
    missing_in_b: List[str] = field(default_factory=list)
    extra_in_b: List[str] = field(default_factory=list)
    artifact_count: int = 0
    error_code: Optional[str] = None
    error_message: Optional[str] = None


def check_reextraction_stable(
    source_path: Path, repo_root: Path, generated_dir: Path
) -> ReextractionResult:
    """Extract *source_path* twice into deterministic staging dirs under
    *repo_root* and compare the MATERIAL artifact hashes.

    The two staging dirs (``<generated_dir>/.roundtrip_reextract/run_{a,b}``)
    live under *repo_root* (a clean, deterministic location the gate owns). A
    difference in any material hash, or a difference in the set of material
    artifacts, is a determinism failure. A dependency/extractor error is reported
    via ``error_code`` (the command maps it to the roundtrip exit) rather than
    raising.
    """
    # Imported here at engine scope (read-only use of the extract engine, never
    # edited). The adapter writes the byte-identical info_from_excel bundle.
    from rechner_pipeline.adapters.excel import ExcelAdapter, ExcelAdapterError

    if not source_path.is_file():
        return ReextractionResult(
            ok=False,
            error_code="source_missing",
            error_message=f"extraction source not found: {source_path}",
        )

    staging_root = generated_dir / ".roundtrip_reextract"
    run_a = staging_root / "run_a"
    run_b = staging_root / "run_b"

    def _extract_into(out_dir: Path) -> Optional[ReextractionResult]:
        # Clean the staging dir so a stale artifact from a prior gate run cannot
        # be globbed (skill gotcha: stage output dirs before a run).
        if out_dir.exists():
            _rmtree(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        try:
            ExcelAdapter(backend="openpyxl").extract(source_path, out_dir)
        except ExcelAdapterError as exc:
            return ReextractionResult(
                ok=False, error_code="extraction_failed", error_message=str(exc)
            )
        except RuntimeError as exc:  # dependency unavailable
            return ReextractionResult(
                ok=False, error_code="dependency_unavailable", error_message=str(exc)
            )
        except Exception as exc:  # noqa: BLE001
            # A corrupt / non-zip / unreadable workbook makes openpyxl raise a
            # bare ``zipfile.BadZipFile`` (an ``Exception``, NOT a ``RuntimeError``)
            # before the adapter can wrap it. Catch the broad failure here so the
            # gate returns a CLEAN blocking result with a ledger instead of
            # crashing to an unhandled exit 50 / bare traceback. Treated as an
            # extraction/input failure (the source cannot be opened at all).
            return ReextractionResult(
                ok=False,
                error_code="extraction_failed",
                error_message=f"{type(exc).__name__}: {exc}",
            )
        return None

    err = _extract_into(run_a)
    if err is not None:
        return err
    err = _extract_into(run_b)
    if err is not None:
        return err

    hashes_a = _material_hashes(run_a)
    hashes_b = _material_hashes(run_b)

    names_a = set(hashes_a)
    names_b = set(hashes_b)
    missing_in_b = sorted(names_a - names_b)
    extra_in_b = sorted(names_b - names_a)
    drifted = sorted(n for n in (names_a & names_b) if hashes_a[n] != hashes_b[n])

    ok = not (missing_in_b or extra_in_b or drifted) and len(hashes_a) > 0
    error_code = None
    error_message = None
    if not ok:
        if not hashes_a:
            error_code = "no_material_artifacts"
            error_message = "re-extraction produced no material artifacts to compare"
        else:
            error_code = "material_drift"
            error_message = (
                f"re-extraction is not stable: {len(drifted)} drifted, "
                f"{len(missing_in_b)} missing, {len(extra_in_b)} extra"
            )

    # Best-effort cleanup of the staging tree (it is a transient gate artifact).
    _rmtree(staging_root)

    return ReextractionResult(
        ok=ok,
        run_a_hashes=hashes_a,
        run_b_hashes=hashes_b,
        drifted=drifted,
        missing_in_b=missing_in_b,
        extra_in_b=extra_in_b,
        artifact_count=len(hashes_a),
        error_code=error_code,
        error_message=error_message,
    )


def _rmtree(path: Path) -> None:
    """Best-effort recursive delete (transient staging only; never raises)."""
    if not path.exists():
        return
    for child in sorted(path.rglob("*"), key=lambda p: len(p.as_posix()), reverse=True):
        try:
            if child.is_file() or child.is_symlink():
                child.unlink()
            elif child.is_dir():
                child.rmdir()
        except OSError:
            pass
    try:
        path.rmdir()
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# Check 3 — recomputation (fresh-process) output-hash stability
# --------------------------------------------------------------------------- #
#
# Reuses the golden_master execution pattern: a tiny child program is run via
# ``fs_confine.main`` (so the generated kernel executes read-only under the repo
# root) with cwd == generated/. The child imports test_run, calls
# golden_master_outputs(), and emits the canonical output hash between markers.
# We run it in N FRESH processes (default 2) and require an identical hash.

_BEGIN = "@@RT_JSON_BEGIN@@"
_END = "@@RT_JSON_END@@"

_CHILD_SOURCE = r'''
import hashlib
import json
import sys
from pathlib import Path

_BEGIN = "{begin}"
_END = "{end}"


def _emit(payload):
    sys.stdout.write(_BEGIN)
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.write(_END)
    sys.stdout.write("\n")
    sys.stdout.flush()


def _run():
    generated = Path.cwd()
    sys.path.insert(0, str(generated))
    try:
        import test_run
    except Exception as exc:  # noqa: BLE001
        _emit({{"error": "import", "message": "test_run import failed: %s" % exc}})
        raise SystemExit(0)
    if not hasattr(test_run, "golden_master_outputs"):
        _emit({{"error": "contract", "message": "test_run.golden_master_outputs() missing"}})
        raise SystemExit(0)
    try:
        computed = test_run.golden_master_outputs()
    except Exception as exc:  # noqa: BLE001
        _emit({{"error": "runtime", "message": "golden_master_outputs() raised: %s" % exc}})
        raise SystemExit(0)
    try:
        canonical = json.dumps(computed, ensure_ascii=False, sort_keys=True)
    except Exception as exc:  # noqa: BLE001
        _emit({{"error": "serialize", "message": "output not JSON-serializable: %s" % exc}})
        raise SystemExit(0)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    _emit({{"output_hash": digest}})


_run()
'''


@dataclass
class RecomputeResult:
    ok: bool
    repeats: int = 0
    hashes: List[str] = field(default_factory=list)
    output_hash: Optional[str] = None
    security_violations: List[str] = field(default_factory=list)
    error_code: Optional[str] = None
    error_message: Optional[str] = None


def _extract_child_payload(stdout: str) -> Optional[Dict[str, Any]]:
    start = stdout.find(_BEGIN)
    end = stdout.find(_END)
    if start == -1 or end == -1 or end < start:
        return None
    blob = stdout[start + len(_BEGIN) : end]
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        return None


def check_recompute_stable(
    repo_root: Path,
    generated_dir: Path,
    info_dir: Path,
    *,
    repeats: int = 2,
) -> RecomputeResult:
    """Run ``golden_master_outputs()`` in *repeats* FRESH processes and require
    an identical canonical output hash.

    Each repeat launches ``python fs_confine.py <repo_root> <child> <info_dir>``
    with cwd == *generated_dir* (the AS-IS run_compare contract), exactly as the
    golden_master gate does, so the kernel runs read-only under *repo_root*.
    ``info_dir`` MUST be under *repo_root* (the caller validates this) so the
    confined child may read its expectation files. A child import/contract/
    runtime error, or any hash difference between repeats, fails the check.
    """
    test_run_py = generated_dir / "test_run.py"
    if not test_run_py.is_file():
        return RecomputeResult(
            ok=False,
            error_code="missing_kernel",
            error_message=f"generated kernel not found: {test_run_py}",
        )

    # G2 PRECONDITION (skill contract): a gate that EXECUTES generated code must
    # run the static AST security scanner first and refuse to run unsafe code —
    # even if an orchestrator skipped G2. The read-only import of the scanner is
    # allowed (qa.security is reviewed, not LLM-generated). fs_confine (G4) is
    # defense-in-depth, not the first line of defense.
    from rechner_pipeline.qa.security import scan_python_paths

    generated_py = sorted(generated_dir.glob("*.py"))
    violations = scan_python_paths(generated_py)
    if violations:
        details = [
            f"{Path(v.path).name}:{v.line}:{v.column} {v.category}/{v.symbol} — {v.message}"
            for v in violations[:50]
        ]
        return RecomputeResult(
            ok=False,
            security_violations=details,
            error_code="security_precondition",
            error_message=(
                "static security gate (G2) found a violation; refusing to execute "
                f"the generated kernel before the recompute check ({len(violations)} total)"
            ),
        )

    hashes: List[str] = []
    with tempfile.TemporaryDirectory(prefix="rt_recompute_") as tmp:
        child = Path(tmp) / "_rt_child.py"
        child.write_text(_CHILD_SOURCE.format(begin=_BEGIN, end=_END), encoding="utf-8")
        cmd = [
            sys.executable,
            fs_confine.__file__,
            str(repo_root),
            str(child),
            str(info_dir),
        ]
        for _ in range(max(2, repeats)):
            proc = subprocess.run(
                cmd,
                cwd=str(generated_dir),
                capture_output=True,
                text=True,
                check=False,
            )
            payload = _extract_child_payload(proc.stdout)
            if payload is None:
                return RecomputeResult(
                    ok=False,
                    repeats=len(hashes),
                    hashes=hashes,
                    error_code="confinement_failure",
                    error_message=(
                        "recompute child produced no result envelope "
                        f"(returncode={proc.returncode})"
                    ),
                )
            if payload.get("error"):
                return RecomputeResult(
                    ok=False,
                    repeats=len(hashes),
                    hashes=hashes,
                    error_code=payload["error"],
                    error_message=payload.get("message", ""),
                )
            hashes.append(payload["output_hash"])

    unique = set(hashes)
    if len(unique) != 1:
        return RecomputeResult(
            ok=False,
            repeats=len(hashes),
            hashes=hashes,
            error_code="nondeterministic",
            error_message=(
                f"recomputation is not deterministic across {len(hashes)} runs: "
                f"{len(unique)} distinct output hashes"
            ),
        )

    return RecomputeResult(
        ok=True,
        repeats=len(hashes),
        hashes=hashes,
        output_hash=hashes[0],
    )
