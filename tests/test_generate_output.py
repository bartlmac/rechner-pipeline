from __future__ import annotations

from pathlib import Path

import pytest

from rechner_pipeline.generate.output import (
    EXPECTED_MAIN_OUTPUT_FILES,
    OutputValidationError,
    extract_files_from_text,
    validate_main_output_files,
    write_validated_main_output_to_generated_dir,
)


def _valid_content(filename: str) -> str:
    if filename.endswith(".py"):
        return f'"""Generated {filename}."""\nVALUE = {filename!r}\n'
    return "<tafeln></tafeln>\n"


def _main_output(
    *,
    omit: set[str] | None = None,
    extra_blocks: list[tuple[str, str]] | None = None,
    override_content: dict[str, str] | None = None,
    order: tuple[str, ...] = EXPECTED_MAIN_OUTPUT_FILES,
) -> str:
    omit = omit or set()
    extra_blocks = extra_blocks or []
    override_content = override_content or {}
    blocks: list[str] = []
    for filename in order:
        if filename in omit:
            continue
        content = override_content.get(filename, _valid_content(filename))
        blocks.append(
            f"===FILE_START: {filename}===\n"
            f"{content}"
            f"===FILE_END: {filename}==="
        )
    for filename, content in extra_blocks:
        blocks.append(
            f"===FILE_START: {filename}===\n"
            f"{content}"
            f"===FILE_END: {filename}==="
        )
    return "\n".join(blocks)


def test_validate_main_output_accepts_expected_six_files() -> None:
    items = validate_main_output_files(_main_output())

    assert [name for name, _content in items] == list(EXPECTED_MAIN_OUTPUT_FILES)


def test_extract_files_from_text_returns_named_blocks_in_order() -> None:
    text = (
        "ignored prefix\n"
        "===FILE_START: first.py===\nprint('one')\n===FILE_END: first.py===\n"
        "===FILE_START: second.txt===\nvalue\n===FILE_END: second.txt===\n"
        "ignored suffix"
    )

    assert extract_files_from_text(text) == [
        ("first.py", "print('one')\n"),
        ("second.txt", "value\n"),
    ]


def test_validate_main_output_rejects_missing_files() -> None:
    with pytest.raises(OutputValidationError, match="missing files: params.py"):
        validate_main_output_files(_main_output(omit={"params.py"}))


def test_validate_main_output_rejects_unexpected_files() -> None:
    with pytest.raises(OutputValidationError, match="unexpected files: notes.txt"):
        validate_main_output_files(
            _main_output(extra_blocks=[("notes.txt", "not part of contract\n")])
        )


def test_validate_main_output_rejects_duplicate_file_blocks() -> None:
    with pytest.raises(OutputValidationError, match="Duplicate file blocks"):
        validate_main_output_files(
            _main_output(extra_blocks=[("inputs.py", _valid_content("inputs.py"))])
        )


def test_validate_main_output_rejects_wrong_order() -> None:
    wrong_order = (
        "params.py",
        "inputs.py",
        "tafeln.xml",
        "commutation.py",
        "actuarial.py",
        "test_run.py",
    )

    with pytest.raises(OutputValidationError, match="output order"):
        validate_main_output_files(_main_output(order=wrong_order))


def test_validate_main_output_rejects_path_components() -> None:
    with pytest.raises(OutputValidationError, match="path components"):
        validate_main_output_files(
            _main_output(
                omit={"inputs.py"},
                extra_blocks=[("nested/inputs.py", _valid_content("inputs.py"))],
            )
        )


def test_validate_main_output_rejects_invalid_python() -> None:
    with pytest.raises(OutputValidationError, match="inputs.py:1"):
        validate_main_output_files(
            _main_output(override_content={"inputs.py": "def broken(:\n    pass\n"})
        )


def test_validate_main_output_rejects_outer_text() -> None:
    with pytest.raises(OutputValidationError, match="outside FILE_START"):
        validate_main_output_files("Here is the output:\n" + _main_output())


def test_write_validated_main_output_writes_only_after_validation(tmp_path: Path) -> None:
    generated_dir = tmp_path / "generated"
    generated_dir.mkdir()
    stale_file = generated_dir / "inputs.py"
    stale_file.write_text("STALE = True\n", encoding="utf-8")

    with pytest.raises(OutputValidationError):
        write_validated_main_output_to_generated_dir(
            _main_output(override_content={"inputs.py": "def broken(:\n    pass\n"}),
            tmp_path,
        )

    assert stale_file.read_text(encoding="utf-8") == "STALE = True\n"

    written = write_validated_main_output_to_generated_dir(_main_output(), tmp_path)

    assert written == len(EXPECTED_MAIN_OUTPUT_FILES)
    assert (generated_dir / "actuarial.py").exists()
    assert (generated_dir / "tafeln.xml").read_text(encoding="utf-8") == (
        "<tafeln></tafeln>\n"
    )
