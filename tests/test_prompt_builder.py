"""
Smoke-Tests für den Prompt-Builder.

Diese Tests sind plattformneutral und benötigen weder Excel noch einen LLM-Key.
Sie sichern die deterministischen Hilfsfunktionen rund um Prompt-Stuffing,
Truncation und Placeholder-Ersetzung.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rechner_pipeline.context.prompt_builder import (
    apply_placeholders,
    build_stuffed_inputs,
    build_stuffed_inputs_with_metadata,
    format_file_block,
    read_and_cap_file,
)


def test_apply_placeholders_replaces_known_keys():
    template = "A={{X}}; B={{Y}}; C={{X}}"
    result = apply_placeholders(template, {"X": "1", "Y": "2"})
    assert result == "A=1; B=2; C=1"


def test_apply_placeholders_leaves_unknown_keys_alone():
    template = "A={{X}}; B={{Y}}"
    result = apply_placeholders(template, {"X": "1"})
    assert result == "A=1; B={{Y}}"


def test_format_file_block_wraps_with_markers():
    block = format_file_block("foo.txt", "hello\nworld")
    assert "BEGIN_INPUT_FILE: foo.txt" in block
    assert "END_INPUT_FILE: foo.txt" in block
    assert "hello\nworld" in block


def test_read_and_cap_file_truncates_when_too_long(tmp_path: Path):
    path = tmp_path / "big.txt"
    path.write_text("x" * 200, encoding="utf-8")
    text, truncated = read_and_cap_file(path, max_chars_per_file=50)
    assert truncated is True
    assert text.startswith("x" * 50)
    assert "[TRUNCATED]" in text


def test_read_and_cap_file_passthrough_when_short(tmp_path: Path):
    path = tmp_path / "small.txt"
    path.write_text("hello", encoding="utf-8")
    text, truncated = read_and_cap_file(path, max_chars_per_file=100)
    assert truncated is False
    assert text == "hello"


def test_build_stuffed_inputs_respects_total_cap(tmp_path: Path):
    files = []
    for i in range(3):
        p = tmp_path / f"f{i}.txt"
        p.write_text("y" * 100, encoding="utf-8")
        files.append(p)

    result = build_stuffed_inputs(
        base_dir=tmp_path,
        files=files,
        max_chars_per_file=200,
        max_total_chars=250,
    )
    # First file fits, second triggers the notice; third never gets added.
    assert "f0.txt" in result
    assert "PIPELINE_NOTICE" in result
    assert "f2.txt" not in result


def test_build_stuffed_inputs_with_metadata_records_truncation(tmp_path: Path):
    big = tmp_path / "big.txt"
    small = tmp_path / "small.txt"
    big.write_text("x" * 20, encoding="utf-8")
    small.write_text("ok", encoding="utf-8")

    result = build_stuffed_inputs_with_metadata(
        base_dir=tmp_path,
        files=[big, small],
        max_chars_per_file=5,
        max_total_chars=1_000,
    )

    by_label = {item.label: item for item in result.files}
    assert result.truncated is True
    assert by_label["big.txt"].truncated is True
    assert by_label["big.txt"].original_chars == 20
    assert by_label["big.txt"].included_chars > 5
    assert by_label["small.txt"].truncated is False
    assert len(by_label["big.txt"].original_sha256) == 64
