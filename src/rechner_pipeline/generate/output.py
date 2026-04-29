from __future__ import annotations

import re
from pathlib import Path


EXPECTED_MAIN_OUTPUT_FILES = (
    "inputs.py",
    "params.py",
    "tafeln.xml",
    "commutation.py",
    "actuarial.py",
    "test_run.py",
)
EXPECTED_MAIN_OUTPUT_FILE_SET = set(EXPECTED_MAIN_OUTPUT_FILES)
PYTHON_MAIN_OUTPUT_FILES = tuple(
    name for name in EXPECTED_MAIN_OUTPUT_FILES if name.endswith(".py")
)

PATTERN = re.compile(
    r"^===FILE_START:[ \t]*(?P<name>[^=\r\n]+?)[ \t]*===[ \t]*(?:\r?\n)"
    r"(?P<content>.*?)"
    r"^===FILE_END:[ \t]*(?P=name)[ \t]*===[ \t]*(?:\r?\n)?",
    re.DOTALL | re.MULTILINE,
)


class OutputValidationError(ValueError):
    """Raised when an LLM output does not match the required file contract."""


def extract_files_from_text(text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for match in PATTERN.finditer(text):
        name = match.group("name").strip()
        content = match.group("content")
        out.append((name, content))
    return out


def _format_names(names: list[str] | set[str] | tuple[str, ...]) -> str:
    return ", ".join(sorted(names))


def _validate_no_outer_text(text: str) -> None:
    cursor = 0
    extra_parts: list[str] = []
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
        raise OutputValidationError(
            "Unexpected text outside FILE_START/FILE_END blocks: " f"{snippet!r}"
        )


def _validate_main_output_names(items: list[tuple[str, str]]) -> None:
    if not items:
        raise OutputValidationError(
            "No files extracted from LLM output (missing FILE_START/FILE_END blocks)."
        )

    names = [name for name, _content in items]
    invalid_path_names = [
        name for name in names if Path(name).name != name or "/" in name or "\\" in name
    ]
    if invalid_path_names:
        raise OutputValidationError(
            "Unexpected file names with path components: "
            f"{_format_names(invalid_path_names)}"
        )

    seen: set[str] = set()
    duplicates: list[str] = []
    for name in names:
        if name in seen and name not in duplicates:
            duplicates.append(name)
        seen.add(name)
    if duplicates:
        raise OutputValidationError(
            "Duplicate file blocks in LLM output: " f"{_format_names(duplicates)}"
        )

    actual = set(names)
    missing = set(EXPECTED_MAIN_OUTPUT_FILES) - actual
    unexpected = actual - EXPECTED_MAIN_OUTPUT_FILE_SET
    errors: list[str] = []
    if missing:
        errors.append(f"missing files: {_format_names(missing)}")
    if unexpected:
        errors.append(f"unexpected files: {_format_names(unexpected)}")
    if errors:
        raise OutputValidationError("Invalid LLM main output: " + "; ".join(errors))

    expected_order = list(EXPECTED_MAIN_OUTPUT_FILES)
    if names != expected_order:
        raise OutputValidationError(
            "Invalid LLM main output order: expected "
            f"{expected_order}, got {names}"
        )


def _validate_python_compiles(items: list[tuple[str, str]]) -> None:
    errors: list[str] = []
    for filename, content in items:
        if filename not in PYTHON_MAIN_OUTPUT_FILES:
            continue
        try:
            compile(content, filename, "exec")
        except SyntaxError as exc:
            location = f"{filename}:{exc.lineno}:{exc.offset}"
            message = exc.msg or exc.__class__.__name__
            errors.append(f"{location}: {message}")

    if errors:
        raise OutputValidationError(
            "Python files in LLM main output do not compile: " + "; ".join(errors)
        )


def validate_main_output_files(text: str) -> list[tuple[str, str]]:
    _validate_no_outer_text(text)
    items = extract_files_from_text(text)
    _validate_main_output_names(items)
    _validate_python_compiles(items)
    return items


def safe_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def write_extracted_files_to_generated_dir(text: str, script_dir: Path) -> int:
    items = extract_files_from_text(text)
    if not items:
        return 0

    written = 0
    for filename, content in items:
        safe_name = Path(filename).name
        out_path = script_dir / "generated" / safe_name
        safe_write(out_path, content)
        written += 1
    return written


def write_validated_main_output_to_generated_dir(text: str, script_dir: Path) -> int:
    items = validate_main_output_files(text)
    return write_main_output_items_to_generated_dir(items, script_dir)


def write_main_output_items_to_generated_dir(
    items: list[tuple[str, str]],
    script_dir: Path,
) -> int:
    written = 0
    for filename, content in items:
        out_path = script_dir / "generated" / filename
        safe_write(out_path, content)
        written += 1
    return written
