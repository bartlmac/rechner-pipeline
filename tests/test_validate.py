"""Tests for the ``validate`` toolbox command (gate G1) and the ported
six-file output validator (:mod:`rechner_pipeline.generate.output`).

Both resolution modes are exercised against the same contract:

* direct-file-edit (files on disk in ``--generated-dir``), the primary path;
* file-block (parse a text response), the secondary path.

The command is driven in-process via ``main(argv) -> ToolboxResult`` so we can
assert on the structured ``exit_code`` / ``errors`` without spawning a process.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable

import pytest

from rechner_pipeline.generate.output import (
    EXPECTED_MAIN_OUTPUT_FILES,
    OutputValidationError,
    validate_files_on_disk,
    validate_main_output_files,
    validate_main_output_text,
)
from rechner_pipeline.toolbox import validate as validate_cmd
from rechner_pipeline.toolbox._common import Exit


# --------------------------------------------------------------------------- #
# Fixture helpers
# --------------------------------------------------------------------------- #


def _content(name: str) -> str:
    if name == "tafeln.xml":
        return "<tafeln></tafeln>\n"
    if name == "test_run.py":
        return (
            '"""Generated test_run.py."""\n\n'
            "def golden_master_outputs():\n"
            '    return {"scalars": {}, "tables": {}}\n'
        )
    return f'"""Generated {name}."""\nVALUE = {name!r}\n'


def _write_generated(
    base: Path,
    *,
    names: Iterable[str] = EXPECTED_MAIN_OUTPUT_FILES,
    overrides: Dict[str, str] | None = None,
    extras: Dict[str, str] | None = None,
) -> Path:
    overrides = overrides or {}
    extras = extras or {}
    gen = base / "generated"
    gen.mkdir(parents=True, exist_ok=True)
    for name in names:
        (gen / name).write_text(overrides.get(name, _content(name)), encoding="utf-8")
    for name, content in extras.items():
        (gen / name).write_text(content, encoding="utf-8")
    return gen


def _block(name: str, body: str) -> str:
    return f"===FILE_START: {name}===\n{body}===FILE_END: {name}===\n"


def _text_response(
    *,
    names: Iterable[str] = EXPECTED_MAIN_OUTPUT_FILES,
    overrides: Dict[str, str] | None = None,
    extras: Dict[str, str] | None = None,
    prefix: str = "",
    dup: str | None = None,
) -> str:
    overrides = overrides or {}
    parts = []
    if prefix:
        parts.append(prefix)
    for name in names:
        parts.append(_block(name, overrides.get(name, _content(name))))
    if dup:
        parts.append(_block(dup, _content(dup)))
    for name, content in (extras or {}).items():
        parts.append(_block(name, content))
    return "".join(parts)


def _run(argv) -> "object":
    return validate_cmd.main(argv)


def _error_codes(result) -> list[str]:
    # ValidationResult holds ValidationError dataclasses; ToolboxResult holds dicts.
    return [e["code"] if isinstance(e, dict) else e.code for e in result.errors]


# --------------------------------------------------------------------------- #
# generate.output unit tests (ported AS-IS contract)
# --------------------------------------------------------------------------- #


def test_text_path_accepts_six_files() -> None:
    result = validate_main_output_text(_text_response())
    assert result.ok
    assert result.names == list(EXPECTED_MAIN_OUTPUT_FILES)
    assert result.golden_master_ok


def test_text_path_rejects_missing_file() -> None:
    result = validate_main_output_text(
        _text_response(names=[n for n in EXPECTED_MAIN_OUTPUT_FILES if n != "params.py"])
    )
    assert not result.ok
    assert _error_codes(result) == ["invalid_file_set"]
    assert "missing files: params.py" in result.errors[0].message


def test_text_path_rejects_extra_file() -> None:
    result = validate_main_output_text(_text_response(extras={"notes.txt": "x\n"}))
    assert _error_codes(result) == ["invalid_file_set"]
    assert "unexpected files: notes.txt" in result.errors[0].message


def test_text_path_rejects_wrong_order() -> None:
    wrong = ("params.py", "inputs.py", "tafeln.xml",
             "commutation.py", "actuarial.py", "test_run.py")
    result = validate_main_output_text(_text_response(names=wrong))
    assert _error_codes(result) == ["wrong_order"]


def test_text_path_rejects_duplicate_block() -> None:
    result = validate_main_output_text(_text_response(dup="inputs.py"))
    assert _error_codes(result) == ["duplicate_blocks"]


def test_text_path_rejects_path_component() -> None:
    body = _block("nested/inputs.py", _content("inputs.py")) + _text_response(
        names=[n for n in EXPECTED_MAIN_OUTPUT_FILES if n != "inputs.py"]
    )
    result = validate_main_output_text(body)
    assert _error_codes(result) == ["path_components"]


def test_text_path_rejects_outer_text() -> None:
    result = validate_main_output_text(_text_response(prefix="Here is the output:\n"))
    assert _error_codes(result) == ["outer_text"]


def test_text_path_rejects_syntax_error() -> None:
    result = validate_main_output_text(
        _text_response(overrides={"inputs.py": "def broken(:\n    pass\n"})
    )
    assert _error_codes(result) == ["syntax_error"]
    assert result.errors[0].message.startswith("inputs.py:1")


def test_text_path_rejects_malformed_golden_master() -> None:
    result = validate_main_output_text(
        _text_response(
            overrides={"test_run.py": "def golden_master_outputs():\n"
                       '    return {"scalars": {}}\n'}
        )
    )
    assert _error_codes(result) == ["golden_master_schema"]
    assert "tables" in result.errors[0].message


def test_golden_master_missing_callable_fails() -> None:
    result = validate_main_output_text(
        _text_response(overrides={"test_run.py": "X = 1\n"})
    )
    assert _error_codes(result) == ["golden_master_schema"]
    assert "missing required callable" in result.errors[0].message


def test_no_files_fails() -> None:
    result = validate_main_output_text("nothing here at all")
    # No FILE blocks -> the whole string is outer text.
    assert _error_codes(result) == ["outer_text"]


def test_legacy_raising_api_accepts_valid() -> None:
    items = validate_main_output_files(_text_response())
    assert [n for n, _ in items] == list(EXPECTED_MAIN_OUTPUT_FILES)


def test_legacy_raising_api_raises_on_invalid() -> None:
    with pytest.raises(OutputValidationError, match="missing files: params.py"):
        validate_main_output_files(
            _text_response(
                names=[n for n in EXPECTED_MAIN_OUTPUT_FILES if n != "params.py"]
            )
        )


# --------------------------------------------------------------------------- #
# On-disk validation unit tests
# --------------------------------------------------------------------------- #


def test_disk_path_accepts_six_files(tmp_path: Path) -> None:
    _write_generated(tmp_path)
    result = validate_files_on_disk(tmp_path / "generated")
    assert result.ok
    assert result.names == list(EXPECTED_MAIN_OUTPUT_FILES)


def test_disk_path_missing_file(tmp_path: Path) -> None:
    _write_generated(tmp_path, names=[n for n in EXPECTED_MAIN_OUTPUT_FILES if n != "params.py"])
    result = validate_files_on_disk(tmp_path / "generated")
    assert _error_codes(result) == ["invalid_file_set"]
    assert "missing files: params.py" in result.errors[0].message


def test_disk_path_extra_file(tmp_path: Path) -> None:
    _write_generated(tmp_path, extras={"notes.txt": "x\n"})
    result = validate_files_on_disk(tmp_path / "generated")
    assert _error_codes(result) == ["invalid_file_set"]
    assert "unexpected files: notes.txt" in result.errors[0].message


def test_disk_path_syntax_error(tmp_path: Path) -> None:
    _write_generated(tmp_path, overrides={"inputs.py": "def broken(:\n    pass\n"})
    result = validate_files_on_disk(tmp_path / "generated")
    assert _error_codes(result) == ["syntax_error"]


def test_disk_path_malformed_golden_master(tmp_path: Path) -> None:
    _write_generated(
        tmp_path,
        overrides={"test_run.py": "def golden_master_outputs():\n"
                   '    return {"scalars": {}}\n'},
    )
    result = validate_files_on_disk(tmp_path / "generated")
    assert _error_codes(result) == ["golden_master_schema"]


def test_disk_path_empty_dir(tmp_path: Path) -> None:
    (tmp_path / "generated").mkdir()
    result = validate_files_on_disk(tmp_path / "generated")
    assert _error_codes(result) == ["invalid_file_set"]
    assert "missing files" in result.errors[0].message


# --------------------------------------------------------------------------- #
# Command-level tests (exit codes + status)
# --------------------------------------------------------------------------- #


def test_cmd_disk_valid_exit_0(tmp_path: Path) -> None:
    gen = _write_generated(tmp_path)
    result = _run(["--repo-root", str(tmp_path), "--generated-dir", str(gen),
                   "--info-dir", str(tmp_path)])
    assert result.exit_code == Exit.OK
    assert result.status == "passed"
    assert result.summary["resolution_mode"] == "direct_file_edit"
    assert result.summary["golden_master_schema_ok"] is True


def test_cmd_disk_failure_exit_20(tmp_path: Path) -> None:
    gen = _write_generated(tmp_path, overrides={"inputs.py": "def broken(:\n"})
    result = _run(["--repo-root", str(tmp_path), "--generated-dir", str(gen),
                   "--info-dir", str(tmp_path)])
    assert result.exit_code == Exit.FILE_CONTRACT
    assert result.status == "failed"
    assert _error_codes(result) == ["syntax_error"]
    assert result.to_dict()["repair_hints"]


def test_cmd_fileblock_valid_exit_0(tmp_path: Path) -> None:
    resp = tmp_path / "resp.txt"
    resp.write_text(_text_response(), encoding="utf-8")
    result = _run(["--repo-root", str(tmp_path), "--generated-dir", "g",
                   "--info-dir", "x", "--file-block-response", str(resp)])
    assert result.exit_code == Exit.OK
    assert result.summary["resolution_mode"] == "file_block"


def test_cmd_fileblock_failure_exit_20(tmp_path: Path) -> None:
    resp = tmp_path / "resp.txt"
    resp.write_text(_text_response(prefix="garbage\n"), encoding="utf-8")
    result = _run(["--repo-root", str(tmp_path), "--generated-dir", "g",
                   "--info-dir", "x", "--file-block-response", str(resp)])
    assert result.exit_code == Exit.FILE_CONTRACT
    assert _error_codes(result) == ["outer_text"]


def test_cmd_missing_required_arg_exit_2() -> None:
    result = _run(["--repo-root", ".", "--generated-dir", "g"])
    assert result.exit_code == Exit.USAGE
    assert any(e["code"] == "missing_arg" for e in result.to_dict()["errors"])


def test_cmd_missing_response_file_exit_2(tmp_path: Path) -> None:
    result = _run(["--repo-root", str(tmp_path), "--generated-dir", "g",
                   "--info-dir", "x", "--file-block-response", str(tmp_path / "nope.txt")])
    assert result.exit_code == Exit.USAGE
    assert _error_codes(result) == ["missing_response"]


def test_cmd_request_json_merges(tmp_path: Path, monkeypatch) -> None:
    """--request-json fills unset flags (flags win)."""
    gen = _write_generated(tmp_path)
    req = tmp_path / "req.json"
    import json
    req.write_text(json.dumps({"info_dir": str(tmp_path)}), encoding="utf-8")
    result = _run(["--repo-root", str(tmp_path), "--generated-dir", str(gen),
                   "--request-json", str(req)])
    assert result.exit_code == Exit.OK
    assert result.paths["info_dir"] == str(tmp_path)


def test_cmd_stdout_is_single_json_object(tmp_path: Path, capsys) -> None:
    """run_command must emit exactly one JSON object on stdout."""
    import json
    gen = _write_generated(tmp_path)
    from rechner_pipeline.toolbox._common import run_command
    code = run_command(
        validate_cmd.main,
        ["--repo-root", str(tmp_path), "--generated-dir", str(gen),
         "--info-dir", str(tmp_path)],
    )
    captured = capsys.readouterr()
    assert code == 0
    obj = json.loads(captured.out)  # parses cleanly -> single object
    assert obj["command"] == "validate"
    assert obj["exit_code"] == 0
