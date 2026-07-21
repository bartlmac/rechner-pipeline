"""Roundtrip gate tests (G7) — XML / extraction / recomputation stability.

Three layers:

1. **Engine unit tests** (:mod:`rechner_pipeline.qa.roundtrip`): the canonical
   ``tafeln.xml`` parse/serialize fixed point, the §6.7 validation rules
   (duplicate age, qx out of [0, 1], non-finite qx), and the recompute /
   re-extraction stability checks.
2. **Command end-to-end** (:mod:`rechner_pipeline.toolbox.roundtrip`): the
   mandated fixtures — a stable canonical run -> exit 0, an invalid ``tafeln.xml``
   -> exit 32, a non-deterministic kernel -> exit 32, a G2 violation -> exit 21,
   and usage errors -> exit 2.
3. **Ledger wiring**: ``roundtrip.gate.json`` is written on pass and fail and is
   loadable by the dossier loader.

The re-extraction check needs an Excel workbook; the repo ships
``examples/Tarifrechner_KLV.xlsm``. Tests that exercise check 2/3 end-to-end use
it and are skipped if it (or openpyxl) is unavailable.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rechner_pipeline.qa import roundtrip as engine
from rechner_pipeline.toolbox import roundtrip as rt_cmd
from rechner_pipeline.toolbox._common import Exit

REPO_ROOT = Path(__file__).resolve().parents[1]
KLV = REPO_ROOT / "examples" / "Tarifrechner_KLV.xlsm"

_VALID_TAFELN = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    "<tafeln>\n"
    '  <table name="DAV1994_T_M">\n'
    '    <entry age="0" qx="0.011687"/>\n'
    '    <entry age="1" qx="0.001008"/>\n'
    "  </table>\n"
    "</tafeln>\n"
)

_DET_KERNEL = (
    "def golden_master_outputs():\n"
    "    return {'scalars': {'Kalkulation': {'BJB': 4465.6547}}, 'tables': {}}\n"
)


# --------------------------------------------------------------------------- #
# 1. Engine — tafeln.xml canonical roundtrip + validation
# --------------------------------------------------------------------------- #


def test_parse_empty_tafeln_is_valid():
    canonical = engine.parse_tafeln("<tafeln></tafeln>")
    assert canonical.tables == ()
    # Empty file is a fixed point.
    again = engine.parse_tafeln(engine.serialize_tafeln(canonical).decode("utf-8"))
    assert again == canonical


def test_canonical_is_a_fixed_point_regardless_of_input_order():
    """Two semantically equal files with different element/attr order/whitespace
    produce the SAME canonical object and SHA-256."""
    a = (
        "<tafeln><table name='B'><entry age='1' qx='0.2'/>"
        "<entry age='0' qx='0.1'/></table>"
        "<table name='A'><entry age='0' qx='0.5'/></table></tafeln>"
    )
    b = (
        '<tafeln>\n  <table name="A"><entry qx="0.5" age="0"/></table>\n'
        '  <table name="B"><entry age="0" qx="0.1"/>'
        '<entry age="1" qx="0.2"/></table>\n</tafeln>'
    )
    ca, cb = engine.parse_tafeln(a), engine.parse_tafeln(b)
    assert ca == cb
    assert engine.canonical_tafeln_sha256(ca) == engine.canonical_tafeln_sha256(cb)
    # Tables sorted by name, entries ascending by age.
    assert [t.name for t in ca.tables] == ["A", "B"]
    assert ca.tables[1].entries == ((0, 0.1), (1, 0.2))


def test_serialize_is_idempotent_byte_level():
    canonical = engine.parse_tafeln(_VALID_TAFELN)
    once = engine.serialize_tafeln(canonical)
    twice = engine.serialize_tafeln(engine.parse_tafeln(once.decode("utf-8")))
    assert once == twice


def test_duplicate_age_rejected():
    bad = '<tafeln><table name="M"><entry age="0" qx="0.1"/><entry age="0" qx="0.2"/></table></tafeln>'
    with pytest.raises(engine.RoundtripError) as exc:
        engine.parse_tafeln(bad)
    assert exc.value.code == "duplicate_age"


@pytest.mark.parametrize("qx", ["1.5", "-0.1", "nan", "inf", "abc"])
def test_invalid_qx_rejected(qx):
    bad = f'<tafeln><table name="M"><entry age="0" qx="{qx}"/></table></tafeln>'
    with pytest.raises(engine.RoundtripError) as exc:
        engine.parse_tafeln(bad)
    assert exc.value.code == "invalid_qx"


def test_qx_bounds_inclusive():
    ok = '<tafeln><table name="M"><entry age="0" qx="0"/><entry age="1" qx="1"/></table></tafeln>'
    canonical = engine.parse_tafeln(ok)
    assert canonical.tables[0].entries == ((0, 0.0), (1, 1.0))


def test_non_integer_age_rejected():
    bad = '<tafeln><table name="M"><entry age="x" qx="0.1"/></table></tafeln>'
    with pytest.raises(engine.RoundtripError) as exc:
        engine.parse_tafeln(bad)
    assert exc.value.code == "invalid_age"


def test_check_tafeln_canonical_pass(tmp_path: Path):
    p = tmp_path / "tafeln.xml"
    p.write_text(_VALID_TAFELN, encoding="utf-8")
    res = engine.check_tafeln_canonical(p)
    assert res.ok
    assert res.table_count == 1
    assert res.entry_count == 2
    assert res.canonical_sha256


def test_check_tafeln_canonical_invalid(tmp_path: Path):
    p = tmp_path / "tafeln.xml"
    p.write_text('<tafeln><table name="M"><entry age="0" qx="2"/></table></tafeln>', encoding="utf-8")
    res = engine.check_tafeln_canonical(p)
    assert not res.ok
    assert res.error_code == "invalid_qx"


def test_high_precision_qx_is_canonical(tmp_path: Path):
    """Regression (Fix 1): a faithfully-extracted high-precision qx (16
    significant decimals) must PASS as canonical. The old 12-decimal truncation
    made the re-parsed float object differ from the first, spuriously reporting
    ``non_canonical`` even though both serializations hashed identically."""
    hp = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<tafeln>\n"
        '  <table name="HP">\n'
        '    <entry age="0" qx="0.0123456789012345"/>\n'
        "  </table>\n"
        "</tafeln>\n"
    )
    p = tmp_path / "tafeln.xml"
    p.write_text(hp, encoding="utf-8")
    res = engine.check_tafeln_canonical(p)
    assert res.ok, res.error_message
    assert res.error_code is None
    assert res.canonical_sha256
    assert res.entry_count == 1
    # Full precision is carried: the canonical qx round-trips to the exact float.
    canonical = engine.parse_tafeln(p.read_text(encoding="utf-8"))
    assert canonical.tables[0].entries[0][1] == 0.0123456789012345


def test_high_precision_qx_serialization_is_exact_fixpoint():
    """The canonical float spelling must be an EXACT round-trip (no precision
    loss) so serialize->parse->serialize is a true byte-level fixpoint."""
    for value in (0.0123456789012345, 0.011687, 0.0, 1.0, 0.1, 0.9999999999999):
        assert float(engine._canon_float(value)) == value
    canonical = engine.parse_tafeln(
        '<tafeln><table name="M"><entry age="0" qx="0.0123456789012345"/></table></tafeln>'
    )
    once = engine.serialize_tafeln(canonical)
    twice = engine.serialize_tafeln(engine.parse_tafeln(once.decode("utf-8")))
    assert once == twice


def test_genuinely_non_canonical_still_fails(tmp_path: Path):
    """A genuinely invalid table (duplicate age / qx out of range / non-finite)
    must still FAIL — the precision fix must not weaken §6.7 validation."""
    cases = {
        "duplicate_age": '<tafeln><table name="M"><entry age="0" qx="0.1"/><entry age="0" qx="0.2"/></table></tafeln>',
        "invalid_qx": '<tafeln><table name="M"><entry age="0" qx="1.5"/></table></tafeln>',
    }
    for expected_code, xml in cases.items():
        p = tmp_path / f"tafeln_{expected_code}.xml"
        p.write_text(xml, encoding="utf-8")
        res = engine.check_tafeln_canonical(p)
        assert not res.ok
        assert res.error_code == expected_code


# --------------------------------------------------------------------------- #
# 2. Engine — recompute stability (no workbook needed)
# --------------------------------------------------------------------------- #


def _make_repo(tmp_path: Path, kernel_body: str):
    repo = tmp_path
    gen = repo / "generated"
    gen.mkdir()
    info = repo / "info_from_excel"
    info.mkdir()
    (gen / "test_run.py").write_text(kernel_body, encoding="utf-8")
    (info / "Kalkulation_scalar.json").write_text(json.dumps({"BJB": 4465.6547}), encoding="utf-8")
    return repo, gen, info


def test_recompute_stable_deterministic(tmp_path: Path):
    repo, gen, info = _make_repo(tmp_path, _DET_KERNEL)
    res = engine.check_recompute_stable(repo, gen, info)
    assert res.ok
    assert res.repeats == 2
    assert len(set(res.hashes)) == 1
    assert res.output_hash


def test_recompute_nondeterministic_detected(tmp_path: Path):
    # G2-clean nondeterminism: hash randomization (PYTHONHASHSEED) varies per process.
    kernel = (
        "def golden_master_outputs():\n"
        "    return {'scalars': {'Kalkulation': {'seed': float(hash('x') % 1000)}}, 'tables': {}}\n"
    )
    repo, gen, info = _make_repo(tmp_path, kernel)
    res = engine.check_recompute_stable(repo, gen, info)
    assert not res.ok
    assert res.error_code == "nondeterministic"
    assert len(set(res.hashes)) > 1


def test_recompute_g2_violation_refuses_execution(tmp_path: Path):
    kernel = (
        "import time\n"
        "def golden_master_outputs():\n"
        "    return {'scalars': {'Kalkulation': {'now': time.time()}}, 'tables': {}}\n"
    )
    repo, gen, info = _make_repo(tmp_path, kernel)
    res = engine.check_recompute_stable(repo, gen, info)
    assert not res.ok
    assert res.error_code == "security_precondition"
    assert res.security_violations


def test_recompute_missing_kernel(tmp_path: Path):
    repo = tmp_path
    gen = repo / "generated"
    gen.mkdir()
    info = repo / "info_from_excel"
    info.mkdir()
    res = engine.check_recompute_stable(repo, gen, info)
    assert not res.ok
    assert res.error_code == "missing_kernel"


# --------------------------------------------------------------------------- #
# 3. Command end-to-end — usage + tafeln + non-determinism
# --------------------------------------------------------------------------- #


def test_usage_missing_flags():
    r = rt_cmd.main([])
    assert r.exit_code == Exit.USAGE
    assert r.status == "failed"


def test_usage_info_dir_outside_repo(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / "generated").mkdir(parents=True)
    outside = tmp_path / "outside_info"
    outside.mkdir()
    r = rt_cmd.main(
        [
            "--repo-root", str(repo),
            "--generated-dir", str(repo / "generated"),
            "--info-dir", str(outside),
            "--input", str(KLV),
        ]
    )
    assert r.exit_code == Exit.USAGE
    assert any("repo-root" in e["message"] for e in r.errors)


def test_usage_missing_input(tmp_path: Path):
    repo = tmp_path / "repo"
    gen = repo / "generated"
    gen.mkdir(parents=True)
    info = repo / "info"
    info.mkdir()
    r = rt_cmd.main(
        [
            "--repo-root", str(repo),
            "--generated-dir", str(gen),
            "--info-dir", str(info),
        ]
    )
    assert r.exit_code == Exit.USAGE
    assert any("--input" in e["message"] for e in r.errors)


def _setup_e2e(tmp_path: Path, *, tafeln: str, kernel: str):
    """Build repo/{generated,info} with an info dir under repo-root and a
    KLV-extracted bundle (so the recompute child can read it)."""
    repo = tmp_path / "repo"
    gen = repo / "generated"
    info = repo / "info"
    gen.mkdir(parents=True)
    info.mkdir(parents=True)
    (gen / "tafeln.xml").write_text(tafeln, encoding="utf-8")
    (gen / "test_run.py").write_text(kernel, encoding="utf-8")
    (info / "Kalkulation_scalar.json").write_text(json.dumps({"BJB": 4465.6547}), encoding="utf-8")
    return repo, gen, info


requires_klv = pytest.mark.skipif(
    not KLV.is_file(), reason="examples/Tarifrechner_KLV.xlsm not available"
)


@requires_klv
def test_e2e_stable_canonical_exits_0(tmp_path: Path):
    repo, gen, info = _setup_e2e(tmp_path, tafeln=_VALID_TAFELN, kernel=_DET_KERNEL)
    r = rt_cmd.main(
        [
            "--repo-root", str(repo),
            "--generated-dir", str(gen),
            "--info-dir", str(info),
            "--input", str(KLV),
        ]
    )
    assert r.exit_code == Exit.OK, r.errors
    assert r.status == "passed"
    assert r.summary["tafeln"]["ok"]
    assert r.summary["reextraction"]["ok"]
    assert r.summary["reextraction"]["artifact_count"] > 0
    assert r.summary["recomputation"]["ok"]
    assert r.output_hashes["tafeln_xml_canonical"]
    assert r.output_hashes["golden_master_outputs"]


@requires_klv
def test_e2e_invalid_tafeln_exits_32(tmp_path: Path):
    bad = '<tafeln><table name="M"><entry age="0" qx="0.1"/><entry age="0" qx="0.2"/></table></tafeln>'
    repo, gen, info = _setup_e2e(tmp_path, tafeln=bad, kernel=_DET_KERNEL)
    r = rt_cmd.main(
        [
            "--repo-root", str(repo),
            "--generated-dir", str(gen),
            "--info-dir", str(info),
            "--input", str(KLV),
        ]
    )
    assert r.exit_code == Exit.ROUNDTRIP
    assert r.status == "failed"
    assert any(e["code"] == "duplicate_age" for e in r.errors)


@requires_klv
def test_e2e_nondeterministic_kernel_exits_32(tmp_path: Path):
    kernel = (
        "def golden_master_outputs():\n"
        "    return {'scalars': {'Kalkulation': {'seed': float(hash('x') % 1000)}}, 'tables': {}}\n"
    )
    repo, gen, info = _setup_e2e(tmp_path, tafeln=_VALID_TAFELN, kernel=kernel)
    r = rt_cmd.main(
        [
            "--repo-root", str(repo),
            "--generated-dir", str(gen),
            "--info-dir", str(info),
            "--input", str(KLV),
        ]
    )
    assert r.exit_code == Exit.ROUNDTRIP
    assert any(e["code"] == "nondeterministic" for e in r.errors)


@requires_klv
def test_e2e_g2_violation_exits_21(tmp_path: Path):
    kernel = (
        "import time\n"
        "def golden_master_outputs():\n"
        "    return {'scalars': {'Kalkulation': {'now': time.time()}}, 'tables': {}}\n"
    )
    repo, gen, info = _setup_e2e(tmp_path, tafeln=_VALID_TAFELN, kernel=kernel)
    r = rt_cmd.main(
        [
            "--repo-root", str(repo),
            "--generated-dir", str(gen),
            "--info-dir", str(info),
            "--input", str(KLV),
        ]
    )
    assert r.exit_code == Exit.SECURITY
    assert any(e["code"] == "security_precondition" for e in r.errors)


def test_e2e_corrupt_input_clean_exit_with_ledger(tmp_path: Path):
    """Regression (Fix 2): a corrupt / non-zip ``--input`` makes openpyxl raise a
    bare ``zipfile.BadZipFile`` (an ``Exception``, not ``RuntimeError``). The gate
    must NOT crash to exit 50 / a bare traceback; it returns a CLEAN blocking
    result (exit 10 = extraction failure) WITH the ledger written."""
    from rechner_pipeline.orchestrate.dossier import load_gate_ledger

    repo, gen, info = _setup_e2e(tmp_path, tafeln=_VALID_TAFELN, kernel=_DET_KERNEL)
    diag = repo / "diagnostics"
    corrupt = tmp_path / "corrupt.xlsm"
    corrupt.write_bytes(b"this is not a zip / xlsx workbook at all")

    r = rt_cmd.main(
        [
            "--repo-root", str(repo),
            "--generated-dir", str(gen),
            "--info-dir", str(info),
            "--input", str(corrupt),
            "--diagnostics-dir", str(diag),
        ]
    )
    # Clean blocking exit (extraction/input failure), never the internal-error 50.
    assert r.exit_code == Exit.EXTRACTION
    assert r.exit_code != Exit.INTERNAL
    assert r.status == "failed"
    assert any(e["code"] == "extraction_failed" for e in r.errors)
    # Ledger present and loadable on this fail path too.
    assert (diag / "roundtrip.gate.json").is_file()
    entries, read_errors = load_gate_ledger(diag)
    assert read_errors == []
    assert any(e.command == "roundtrip" and e.status == "failed" for e in entries)


def test_e2e_missing_tafeln_exits_32(tmp_path: Path):
    repo = tmp_path / "repo"
    gen = repo / "generated"
    info = repo / "info"
    gen.mkdir(parents=True)
    info.mkdir(parents=True)
    (gen / "test_run.py").write_text(_DET_KERNEL, encoding="utf-8")
    r = rt_cmd.main(
        [
            "--repo-root", str(repo),
            "--generated-dir", str(gen),
            "--info-dir", str(info),
            "--input", str(KLV) if KLV.is_file() else str(tmp_path / "x.xlsm"),
        ]
    )
    assert r.exit_code == Exit.ROUNDTRIP
    assert any(e["code"] == "missing_tafeln" for e in r.errors)


# --------------------------------------------------------------------------- #
# 4. Ledger wiring
# --------------------------------------------------------------------------- #


@requires_klv
def test_ledger_written_and_loadable_on_pass(tmp_path: Path):
    from rechner_pipeline.orchestrate.dossier import load_gate_ledger

    repo, gen, info = _setup_e2e(tmp_path, tafeln=_VALID_TAFELN, kernel=_DET_KERNEL)
    diag = repo / "diagnostics"
    r = rt_cmd.main(
        [
            "--repo-root", str(repo),
            "--generated-dir", str(gen),
            "--info-dir", str(info),
            "--input", str(KLV),
            "--diagnostics-dir", str(diag),
        ]
    )
    assert r.exit_code == Exit.OK
    assert (diag / "roundtrip.gate.json").is_file()
    entries, read_errors = load_gate_ledger(diag)
    assert read_errors == []
    assert any(e.command == "roundtrip" and e.status == "passed" for e in entries)


@requires_klv
def test_ledger_written_on_fail(tmp_path: Path):
    from rechner_pipeline.orchestrate.dossier import load_gate_ledger

    bad = '<tafeln><table name="M"><entry age="0" qx="9"/></table></tafeln>'
    repo, gen, info = _setup_e2e(tmp_path, tafeln=bad, kernel=_DET_KERNEL)
    diag = repo / "diagnostics"
    r = rt_cmd.main(
        [
            "--repo-root", str(repo),
            "--generated-dir", str(gen),
            "--info-dir", str(info),
            "--input", str(KLV),
            "--diagnostics-dir", str(diag),
        ]
    )
    assert r.exit_code == Exit.ROUNDTRIP
    assert (diag / "roundtrip.gate.json").is_file()
    entries, read_errors = load_gate_ledger(diag)
    assert read_errors == []
    assert any(e.command == "roundtrip" and e.status == "failed" for e in entries)
