"""Six-file output contract validator (G1) — ported from the AS-IS pipeline.

This module is the single source of truth for the **deterministic** main-output
contract that gate G1 (``rechner_pipeline.toolbox.validate``) enforces. It ports
the AS-IS semantics from ``rechner-pipeline``'s ``generate/output.py`` (the
authoritative FILE-block grammar of MIGRATION.md §6.3) and adds a *static*
``golden_master_outputs()`` schema precheck so G1 can flag a broken calculation
contract before G4 (runtime confinement) / G5 (golden master) ever import the
generated code.

Two equivalent entry points enforce the **same** contract:

* :func:`validate_main_output_files` — secondary path: validate a single text
  blob that contains ``===FILE_START: <name>===`` / ``===FILE_END: <name>===``
  blocks (a CLI/LLM text response).
* :func:`validate_files_on_disk` — primary path: validate the six files already
  written into a ``generated/`` directory (direct-file-edit mode).

Neither path **executes** generated code. Python files are checked with
:func:`compile` / :mod:`ast`; the ``golden_master_outputs()`` shape is checked by
parsing ``test_run.py``'s AST. Executing the calculation core is the job of G4
(runtime confinement) and G5 (golden master).
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple


# --------------------------------------------------------------------------- #
# Contract constants (MIGRATION.md §6.3 / §2.3.5). Order is load-bearing.
# --------------------------------------------------------------------------- #

#: Expected main-output files, in their **exact required order**. This tuple is
#: the canonical six-file order constant; the golden-master and
#: end-to-end-generation authors must reuse it verbatim (do not re-derive).
EXPECTED_MAIN_OUTPUT_FILES: Tuple[str, ...] = (
    "inputs.py",
    "params.py",
    "tafeln.xml",
    "commutation.py",
    "actuarial.py",
    "test_run.py",
)
EXPECTED_MAIN_OUTPUT_FILE_SET = set(EXPECTED_MAIN_OUTPUT_FILES)

#: Every expected output ending in ``.py`` is compiled; ``tafeln.xml`` is not.
PYTHON_MAIN_OUTPUT_FILES: Tuple[str, ...] = tuple(
    name for name in EXPECTED_MAIN_OUTPUT_FILES if name.endswith(".py")
)

#: File whose AST must expose a schema-correct ``golden_master_outputs()``.
GOLDEN_MASTER_FILE = "test_run.py"
GOLDEN_MASTER_FUNC = "golden_master_outputs"
#: Required top-level keys of the dict returned by ``golden_master_outputs()``
#: (the fixed harness shape ``{"scalars": ..., "tables": ...}``).
GOLDEN_MASTER_REQUIRED_KEYS: Tuple[str, ...] = ("scalars", "tables")

#: Authoritative FILE-block grammar (MIGRATION.md §6.3). Multiline + dotall so a
#: block spans lines; the closing tag must repeat the opening ``name``.
PATTERN = re.compile(
    r"^===FILE_START:[ \t]*(?P<name>[^=\r\n]+?)[ \t]*===[ \t]*(?:\r?\n)"
    r"(?P<content>.*?)"
    r"^===FILE_END:[ \t]*(?P=name)[ \t]*===[ \t]*(?:\r?\n)?",
    re.DOTALL | re.MULTILINE,
)


class OutputValidationError(ValueError):
    """Raised when an output does not match the required six-file contract."""


# --------------------------------------------------------------------------- #
# Structured result (so the ``validate`` command can build precise JSON errors
# without re-parsing exception prose).
# --------------------------------------------------------------------------- #


@dataclass
class ValidationError:
    """One structured contract violation."""

    code: str
    message: str
    file: Optional[str] = None
    detail: Optional[str] = None

    def to_dict(self) -> dict:
        out: dict = {"code": self.code, "message": self.message}
        if self.file is not None:
            out["file"] = self.file
        if self.detail is not None:
            out["detail"] = self.detail
        return out


@dataclass
class ValidationResult:
    """Outcome of validating one set of files against the contract."""

    ok: bool
    names: List[str] = field(default_factory=list)
    errors: List[ValidationError] = field(default_factory=list)
    compiled: List[str] = field(default_factory=list)
    golden_master_ok: bool = False


# --------------------------------------------------------------------------- #
# FILE-block extraction (secondary / text-response path)
# --------------------------------------------------------------------------- #


def extract_files_from_text(text: str) -> List[Tuple[str, str]]:
    """Return ``(name, content)`` pairs; only the name is stripped (§6.3)."""
    out: List[Tuple[str, str]] = []
    for match in PATTERN.finditer(text):
        name = match.group("name").strip()
        content = match.group("content")
        out.append((name, content))
    return out


def _format_names(names) -> str:
    return ", ".join(sorted(names))


def _outer_text_error(text: str) -> Optional[ValidationError]:
    """Reject any non-whitespace outside recognized FILE blocks (§2.3.5 step 1)."""
    cursor = 0
    extra_parts: List[str] = []
    for match in PATTERN.finditer(text):
        before = text[cursor : match.start()]
        if before.strip():
            extra_parts.append(before.strip())
        cursor = match.end()
    after = text[cursor:]
    if after.strip():
        extra_parts.append(after.strip())
    if extra_parts:
        snippet = extra_parts[0].replace("\n", "\\n")[:120]
        return ValidationError(
            code="outer_text",
            message=f"Unexpected text outside FILE_START/FILE_END blocks: {snippet!r}",
            detail=snippet,
        )
    return None


# --------------------------------------------------------------------------- #
# Name / order / duplicate / path-component checks (shared by both paths)
# --------------------------------------------------------------------------- #


def _name_errors(names: List[str]) -> List[ValidationError]:
    """Validate names against the contract; stop at the first failing *category*
    in the same order as the AS-IS validator (§2.3.5 steps 2–6)."""
    errors: List[ValidationError] = []

    if not names:
        errors.append(
            ValidationError(
                code="no_files",
                message="No files extracted from LLM output "
                "(missing FILE_START/FILE_END blocks).",
            )
        )
        return errors

    # 3. Path components.
    invalid_path_names = [
        n for n in names if Path(n).name != n or "/" in n or "\\" in n
    ]
    if invalid_path_names:
        errors.append(
            ValidationError(
                code="path_components",
                message="Unexpected file names with path components: "
                f"{_format_names(invalid_path_names)}",
                detail=_format_names(invalid_path_names),
            )
        )
        return errors

    # 4. Duplicates.
    seen: set = set()
    duplicates: List[str] = []
    for n in names:
        if n in seen and n not in duplicates:
            duplicates.append(n)
        seen.add(n)
    if duplicates:
        errors.append(
            ValidationError(
                code="duplicate_blocks",
                message="Duplicate file blocks in LLM output: "
                f"{_format_names(duplicates)}",
                detail=_format_names(duplicates),
            )
        )
        return errors

    # 5. Exact file set: missing and/or unexpected.
    actual = set(names)
    missing = EXPECTED_MAIN_OUTPUT_FILE_SET - actual
    unexpected = actual - EXPECTED_MAIN_OUTPUT_FILE_SET
    set_errors: List[str] = []
    if missing:
        set_errors.append(f"missing files: {_format_names(missing)}")
    if unexpected:
        set_errors.append(f"unexpected files: {_format_names(unexpected)}")
    if set_errors:
        errors.append(
            ValidationError(
                code="invalid_file_set",
                message="Invalid LLM main output: " + "; ".join(set_errors),
                detail="; ".join(set_errors),
            )
        )
        return errors

    # 6. Exact order.
    expected_order = list(EXPECTED_MAIN_OUTPUT_FILES)
    if names != expected_order:
        errors.append(
            ValidationError(
                code="wrong_order",
                message="Invalid LLM main output order: "
                f"expected {expected_order}, got {names}",
                detail=f"expected {expected_order}, got {names}",
            )
        )
    return errors


# --------------------------------------------------------------------------- #
# Compile check (no execution) — §2.3.5 step 7
# --------------------------------------------------------------------------- #


def _compile_errors(items: List[Tuple[str, str]]) -> Tuple[List[ValidationError], List[str]]:
    """Compile every ``*.py`` output (``tafeln.xml`` is skipped). Returns
    ``(errors, compiled_names)``. Code is compiled, never executed."""
    errors: List[ValidationError] = []
    compiled: List[str] = []
    for filename, content in items:
        if filename not in PYTHON_MAIN_OUTPUT_FILES:
            continue
        try:
            compile(content, filename, "exec")
        except SyntaxError as exc:
            location = f"{filename}:{exc.lineno}:{exc.offset}"
            message = exc.msg or exc.__class__.__name__
            errors.append(
                ValidationError(
                    code="syntax_error",
                    message=f"{location}: {message}",
                    file=filename,
                    detail=f"line {exc.lineno}, col {exc.offset}: {message}",
                )
            )
        else:
            compiled.append(filename)
    return errors, compiled


# --------------------------------------------------------------------------- #
# golden_master_outputs() static schema precheck — §3.5 G1 / G5 contract
# --------------------------------------------------------------------------- #


def _dict_keys_from_node(node: ast.AST) -> Optional[set]:
    """Return the set of literal string keys of an ``ast.Dict`` node, else
    ``None`` when the value is not a dict literal with constant string keys."""
    if not isinstance(node, ast.Dict):
        return None
    keys: set = set()
    for key in node.keys:
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            keys.add(key.value)
        else:
            # A non-constant / unpacked (`**other`) key: we cannot statically
            # prove the shape, so treat as schema-indeterminate.
            return None
    return keys


def golden_master_schema_error(content: str) -> Optional[ValidationError]:
    """Static precheck of ``test_run.py``'s ``golden_master_outputs()``.

    Without executing the code, confirm that the file:

    1. parses,
    2. defines a top-level (or any) ``def golden_master_outputs(...)``,
    3. that function returns a dict literal whose keys include
       ``{"scalars", "tables"}`` on **every** ``return`` it makes
       (the fixed harness shape ``{"scalars": ..., "tables": ...}``).

    Returns ``None`` when the precheck passes, else a structured
    :class:`ValidationError`. This is intentionally conservative: it is a
    *precheck* — G5 still imports and runs the function under confinement.
    """
    try:
        tree = ast.parse(content, filename=GOLDEN_MASTER_FILE)
    except SyntaxError as exc:
        # Compile check already reports syntax; report consistently here too.
        return ValidationError(
            code="golden_master_schema",
            message=f"{GOLDEN_MASTER_FILE}:{exc.lineno}:{exc.offset}: {exc.msg}",
            file=GOLDEN_MASTER_FILE,
            detail="could not parse test_run.py to inspect golden_master_outputs()",
        )

    func: Optional[ast.FunctionDef] = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == GOLDEN_MASTER_FUNC:
                func = node  # type: ignore[assignment]
                break

    if func is None:
        return ValidationError(
            code="golden_master_schema",
            message=(
                f"{GOLDEN_MASTER_FILE}: missing required callable "
                f"{GOLDEN_MASTER_FUNC}()."
            ),
            file=GOLDEN_MASTER_FILE,
            detail="define golden_master_outputs() returning "
            '{"scalars": ..., "tables": ...}',
        )

    # Collect returns belonging directly to this function (not nested defs).
    returns: List[ast.Return] = []

    class _ReturnCollector(ast.NodeVisitor):
        def visit_FunctionDef(self, n: ast.FunctionDef) -> None:  # noqa: N802
            if n is func:
                self.generic_visit(n)

        def visit_AsyncFunctionDef(self, n: ast.AsyncFunctionDef) -> None:  # noqa: N802
            if n is func:
                self.generic_visit(n)

        def visit_Lambda(self, n: ast.Lambda) -> None:  # noqa: N802
            return  # don't descend into lambdas

        def visit_Return(self, n: ast.Return) -> None:  # noqa: N802
            returns.append(n)

    _ReturnCollector().visit(func)

    if not returns:
        return ValidationError(
            code="golden_master_schema",
            message=(
                f"{GOLDEN_MASTER_FILE}: {GOLDEN_MASTER_FUNC}() has no return "
                "statement; it must return a dict with keys "
                f"{list(GOLDEN_MASTER_REQUIRED_KEYS)}."
            ),
            file=GOLDEN_MASTER_FILE,
            detail="function returns nothing",
        )

    required = set(GOLDEN_MASTER_REQUIRED_KEYS)
    for ret in returns:
        if ret.value is None:
            return ValidationError(
                code="golden_master_schema",
                message=(
                    f"{GOLDEN_MASTER_FILE}:{ret.lineno}: {GOLDEN_MASTER_FUNC}() "
                    "has a bare 'return'; it must return a dict with keys "
                    f"{list(GOLDEN_MASTER_REQUIRED_KEYS)}."
                ),
                file=GOLDEN_MASTER_FILE,
                detail="bare return",
            )
        keys = _dict_keys_from_node(ret.value)
        if keys is None:
            return ValidationError(
                code="golden_master_schema",
                message=(
                    f"{GOLDEN_MASTER_FILE}:{ret.lineno}: {GOLDEN_MASTER_FUNC}() "
                    "must return a dict literal with constant string keys "
                    f"{list(GOLDEN_MASTER_REQUIRED_KEYS)}."
                ),
                file=GOLDEN_MASTER_FILE,
                detail="return value is not a dict literal with string keys",
            )
        missing = required - keys
        if missing:
            return ValidationError(
                code="golden_master_schema",
                message=(
                    f"{GOLDEN_MASTER_FILE}:{ret.lineno}: {GOLDEN_MASTER_FUNC}() "
                    f"return dict is missing required keys: {_format_names(missing)} "
                    f"(must contain {list(GOLDEN_MASTER_REQUIRED_KEYS)})."
                ),
                file=GOLDEN_MASTER_FILE,
                detail=f"missing keys: {_format_names(missing)}",
            )

    return None


# --------------------------------------------------------------------------- #
# Shared core validator (operates on already-extracted items)
# --------------------------------------------------------------------------- #


def validate_items(
    items: List[Tuple[str, str]],
    *,
    outer_text_error: Optional[ValidationError] = None,
) -> ValidationResult:
    """Apply the full contract to ``(name, content)`` items.

    ``outer_text_error`` is supplied only by the text-response path (the
    on-disk path has no surrounding text to check). Checks run in the AS-IS
    order: outer text -> names/order -> compile -> golden-master schema. The
    first failing *category* short-circuits later categories, mirroring the
    AS-IS validator's fail-fast behavior.
    """
    if outer_text_error is not None:
        return ValidationResult(ok=False, errors=[outer_text_error])

    names = [name for name, _content in items]

    name_errors = _name_errors(names)
    if name_errors:
        return ValidationResult(ok=False, names=names, errors=name_errors)

    compile_errs, compiled = _compile_errors(items)
    if compile_errs:
        return ValidationResult(
            ok=False, names=names, errors=compile_errs, compiled=compiled
        )

    # golden_master_outputs() precheck on test_run.py.
    content_by_name = dict(items)
    gm_error = golden_master_schema_error(content_by_name[GOLDEN_MASTER_FILE])
    if gm_error is not None:
        return ValidationResult(
            ok=False, names=names, errors=[gm_error], compiled=compiled
        )

    return ValidationResult(
        ok=True, names=names, compiled=compiled, golden_master_ok=True
    )


def validate_main_output_text(text: str) -> ValidationResult:
    """Validate a single text response containing FILE blocks (secondary path)."""
    outer = _outer_text_error(text)
    items = extract_files_from_text(text)
    return validate_items(items, outer_text_error=outer)


def validate_files_on_disk(generated_dir: Path) -> ValidationResult:
    """Validate the six files already present in ``generated_dir`` (primary path).

    Discovery is by exact expected file name (no recursion, no globbing of
    extra files): the on-disk contract enforces the same name/order/compile/
    golden-master rules as the text path. Files missing on disk become a
    ``missing files`` violation; unexpected siblings present in the directory
    are reported as ``unexpected files`` so the on-disk and text paths agree.
    """
    generated_dir = Path(generated_dir)

    # Build items in the on-disk order: read every expected file that exists,
    # plus any unexpected sibling files, so name/set/order checks behave like
    # the text path. We deliberately list the directory to detect extras.
    present_expected: List[Tuple[str, str]] = []
    missing: List[str] = []
    for name in EXPECTED_MAIN_OUTPUT_FILES:
        fpath = generated_dir / name
        if fpath.is_file():
            present_expected.append((name, fpath.read_text(encoding="utf-8")))
        else:
            missing.append(name)

    # Detect unexpected sibling files (top-level only).
    extras: List[Tuple[str, str]] = []
    if generated_dir.is_dir():
        for child in sorted(generated_dir.iterdir()):
            if child.is_file() and child.name not in EXPECTED_MAIN_OUTPUT_FILE_SET:
                extras.append((child.name, child.read_text(encoding="utf-8")))

    # Compose names for the set/order check: expected (in canonical order, only
    # those present) followed by extras. Missing names are injected as absent so
    # _name_errors reports them via the set check.
    items = present_expected + extras
    names = [n for n, _ in items]

    # If something is missing, surface it through the same set-check machinery by
    # passing the *present* names (the set diff yields "missing files: ...").
    if missing:
        # Names present (expected order) + extras; missing detected by set diff.
        name_errors = _name_errors(names if names else [])
        # _name_errors with present names will report missing via set check,
        # but if names is empty it reports "no_files". Prefer the explicit
        # missing-files message for an empty directory too.
        if not names:
            return ValidationResult(
                ok=False,
                names=[],
                errors=[
                    ValidationError(
                        code="invalid_file_set",
                        message="Invalid LLM main output: missing files: "
                        f"{_format_names(missing)}",
                        detail=f"missing files: {_format_names(missing)}",
                    )
                ],
            )
        return ValidationResult(ok=False, names=names, errors=name_errors)

    return validate_items(items)


# --------------------------------------------------------------------------- #
# Back-compat thin wrappers (raise the AS-IS exception) — kept so existing call
# sites / tests that expect the raising API continue to work.
# --------------------------------------------------------------------------- #


def validate_main_output_files(text: str) -> List[Tuple[str, str]]:
    """AS-IS-compatible API: validate text, raise :class:`OutputValidationError`
    on the first failing category, else return the extracted items."""
    result = validate_main_output_text(text)
    if not result.ok:
        raise OutputValidationError(result.errors[0].message)
    return extract_files_from_text(text)


def write_validated_main_output_to_generated_dir(text: str, repo_root: Path) -> int:
    """Validate FILE-block text and write the six files under ``generated/``.

    Validation is completed before any file is written, so a bad response cannot
    partially replace a previous generated directory. This helper exists only
    for CLIs that emit text responses; direct file edits plus G1 validation are
    the preferred target workflow.
    """
    items = validate_main_output_files(text)
    generated_dir = Path(repo_root) / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in items:
        (generated_dir / filename).write_text(content, encoding="utf-8")
    return len(items)
