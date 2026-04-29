from __future__ import annotations

from rechner_pipeline.extract.excel import (
    a1_to_rc,
    addr_to_rc,
    normalize_formula_to_pattern,
    rc_to_a1,
    safe_filename,
)


def test_safe_filename_removes_invalid_filesystem_characters() -> None:
    assert safe_filename(' A<B>:C/D\\E|F?G*H. ') == "A_B_C_D_E_F_G_H"


def test_safe_filename_falls_back_to_unnamed_and_truncates() -> None:
    assert safe_filename(" ... ") == "unnamed"
    assert safe_filename("x" * 20, max_len=8) == "x" * 8


def test_a1_to_rc_preserves_absolute_flags() -> None:
    assert a1_to_rc("A1") == (1, 1, False, False)
    assert a1_to_rc("$AA$10") == (10, 27, True, True)
    assert a1_to_rc("not-a-cell") is None


def test_addr_to_rc_strips_absolute_markers() -> None:
    assert addr_to_rc("$XFD$1048576") == (1048576, 16384)
    assert addr_to_rc("A") is None


def test_rc_to_a1_converts_column_numbers_to_letters() -> None:
    assert rc_to_a1(1, 1) == "A1"
    assert rc_to_a1(5, 28) == "AB5"
    assert rc_to_a1(42, 703) == "AAA42"


def test_normalize_formula_to_pattern_converts_relative_and_absolute_refs() -> None:
    formula = "=A1 + B$2 + $C3 + $D$4"

    assert normalize_formula_to_pattern(formula, "B2") == (
        "=R[-1]C[-1]+R2C[0]+R[1]C3+R4C4"
    )


def test_normalize_formula_to_pattern_preserves_sheet_prefixes() -> None:
    formula = "='Rates'!C3 + Other_1!$D$4"

    assert normalize_formula_to_pattern(formula, "B2") == (
        "='RATES'!R[1]C[1]+OTHER_1!R4C4"
    )


def test_normalize_formula_to_pattern_leaves_non_formulas_unchanged() -> None:
    assert normalize_formula_to_pattern("plain text", "B2") == "plain text"
