"""Algebraic / property gate tests (G6).

Two layers:

1. **Engine unit tests** (:mod:`rechner_pipeline.qa.algebraic`): applicability
   fail-fast (unknown tier, missing mapping, unsupported timing/product,
   unresolvable mapping), engine availability (Hypothesis mandatory, version
   match), and a full pass/counterexample run against an in-process toy kernel.
2. **End-to-end command** (:mod:`rechner_pipeline.toolbox.algebraic`): the
   mandated fixtures run through the static-security precondition (G2) and the
   confined child (G4): a matching toy kernel -> exit 0; a broken identity ->
   exit 31 with a counterexample; a missing mapping and an unknown-applicability
   contract -> exit 31 with a reason; a usage error -> exit 2. Confirms the
   ledger is written and loadable and that stdout is exactly one JSON object.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

from rechner_pipeline.qa import algebraic as eng
from rechner_pipeline.toolbox import algebraic as alg_cmd
from rechner_pipeline.toolbox._common import Exit
from rechner_pipeline.orchestrate.dossier import load_gate_ledger


# --------------------------------------------------------------------------- #
# In-process toy kernel (mirrors the .tmp fixture, omega = 6 for speed)
# --------------------------------------------------------------------------- #

OMEGA = 6
I = 0.025
V = 1.0 / (1.0 + I)
D = I / (1.0 + I)

_Q = {x: min(0.01 + 0.01 * x, 0.9) for x in range(OMEGA)}
_Q[OMEGA] = 1.0
_L = {0: 100000.0}
for _x in range(1, OMEGA + 1):
    _L[_x] = _L[_x - 1] * (1.0 - _Q[_x - 1])
_L[OMEGA + 1] = 0.0


def _qx(x):
    return _Q[int(x)]


def _px(x):
    return 1.0 - _qx(x)


def _lx(x):
    x = int(x)
    return _L.get(x, 0.0 if x > OMEGA else _L[x])


def _dx(x):
    return _lx(x) - _lx(x + 1)


def _Dx(x):
    x = int(x)
    return (V ** x) * _lx(x)


def _Nx(x):
    return sum(_Dx(k) for k in range(int(x), OMEGA + 1))


def _Cx(x):
    x = int(x)
    return (V ** (x + 1)) * _dx(x)


def _Mx(x):
    return sum(_Cx(k) for k in range(int(x), OMEGA + 1))


def _Ax(x):
    return _Mx(x) / _Dx(x)


def _aex(x):
    return _Nx(x) / _Dx(x)


def _net_premium(x):
    return _Ax(x) / _aex(x)


def _make_kernel_importer(ax=_Ax, aex=_aex):
    """Return an ``import_module``-shaped callable serving two synthetic modules."""
    commutation = types.SimpleNamespace(
        qx=_qx, px=_px, lx=_lx, Dx=_Dx, Nx=_Nx, Cx=_Cx, Mx=_Mx
    )
    actuarial = types.SimpleNamespace(
        Ax=ax,
        aex=aex,
        net_premium=lambda x: ax(x) / aex(x),
        pv_benefits=ax,
        pv_premiums=aex,
    )
    modules = {"commutation": commutation, "actuarial": actuarial}

    def _importer(name):
        if name in modules:
            return modules[name]
        raise ImportError(f"no module {name}")

    return _importer


_FULL_MAPPINGS = {
    "qx": "commutation.qx",
    "px": "commutation.px",
    "lx": "commutation.lx",
    "Dx": "commutation.Dx",
    "Nx": "commutation.Nx",
    "Cx": "commutation.Cx",
    "Mx": "commutation.Mx",
    "Ax": "actuarial.Ax",
    "aex": "actuarial.aex",
    "net_premium": "actuarial.net_premium",
    "pv_benefits": "actuarial.pv_benefits",
    "pv_premiums": "actuarial.pv_premiums",
}
_ALL_TIERS = list(eng.ALL_TIERS)
_BASIS = {"annual_effective_rate": 0.025}
_TERMINAL = {"omega": OMEGA, "q_omega": 1.0}
_ENGINE = {"name": "hypothesis", "version": "", "max_examples": 25}


def _run(mappings=None, tiers=None, importer=None, timing="annuity_due",
         product="endowment_net_premium", interest=None, terminal=None,
         engine=None):
    return eng.run_checks(
        product_type=product,
        interest_basis_raw=interest if interest is not None else _BASIS,
        timing_convention=timing,
        terminal_age_policy=terminal if terminal is not None else _TERMINAL,
        function_mappings=mappings if mappings is not None else _FULL_MAPPINGS,
        tiers_enabled=tiers if tiers is not None else _ALL_TIERS,
        tolerances_raw={"rel_tol": 1e-9, "abs_tol": 1e-12},
        property_engine=engine if engine is not None else _ENGINE,
        importer=importer or _make_kernel_importer(),
    )


# --------------------------------------------------------------------------- #
# 1. Engine: pass + counterexample
# --------------------------------------------------------------------------- #


def test_engine_full_pass_all_tiers():
    report = _run()
    assert report.ok
    assert report.engine == "hypothesis"
    assert report.engine_version  # recorded
    assert set(report.tiers_selected) == set(_ALL_TIERS)
    # Every tier produced identities and ran cases.
    assert report.total_cases > 0
    assert report.counterexamples == []
    # A representative identity from each tier was checked.
    ids = report.identities_checked
    assert any("0 <= qx <= 1" in s for s in ids)
    assert any("N_x = D_x + N_{x+1}" in s for s in ids)
    assert any("A_x + d" in s for s in ids)
    assert any("PV(benefits)" in s for s in ids)


def test_engine_counterexample_breaks_pv_balance():
    # aex inflated 5% -> A_x + d*ae_x != 1.
    bad_aex = lambda x: 1.05 * _aex(x)
    report = _run(importer=_make_kernel_importer(aex=bad_aex))
    assert not report.ok
    cxs = report.counterexamples
    assert cxs, "expected at least one counterexample"
    identities = {c.identity for c in cxs}
    assert any("A_x + d" in i for i in identities)
    # The counterexample carries a concrete falsifying age.
    assert any("x" in c.example for c in cxs)


def test_engine_counterexample_breaks_qx_bounds():
    bad_qx = lambda x: 1.5 if int(x) == 2 else _qx(x)
    imp = _make_kernel_importer()
    imp_mod = imp("commutation")
    imp_mod.qx = bad_qx
    report = _run(importer=imp, tiers=[eng.TIER_MORTALITY])
    assert not report.ok
    assert any("qx" in c.identity for c in report.counterexamples)


# --------------------------------------------------------------------------- #
# 1b. Commutation: D_x = v^x · l_x is GENUINELY exercised (Fix 1, false-coverage)
# --------------------------------------------------------------------------- #


def test_commutation_dx_definition_is_checked_and_passes():
    """The correct toy kernel passes the commutation tier AND the
    ``D_x = v^x · l_x`` identity is actually counted (no dead code)."""
    report = _run(tiers=[eng.TIER_COMMUTATION])
    assert report.ok
    ids = report.identities_checked
    assert "D_x = v^x · l_x" in ids, "the Dx definition must be live, not dead code"
    # The tier ran cases for that identity (not zero).
    tr = report.tier_reports[0]
    assert tr.tier == eng.TIER_COMMUTATION
    assert tr.cases > 0


def test_commutation_off_by_one_dx_now_fails():
    """REGRESSION: an off-by-one discount ``D_x = v^(x+1)·l_x`` is internally
    consistent (recursion/sum identities still hold) yet must now FAIL the
    commutation tier on the ``D_x = v^x·l_x`` definition with a concrete
    counterexample."""
    bad_Dx = lambda x: (V ** (int(x) + 1)) * _lx(x)  # off-by-one discount
    bad_Nx = lambda x: sum(bad_Dx(k) for k in range(int(x), OMEGA + 1))
    imp = _make_kernel_importer()
    comm = imp("commutation")
    comm.Dx = bad_Dx
    comm.Nx = bad_Nx  # keep N_x internally consistent with the wrong D_x
    report = _run(importer=imp, tiers=[eng.TIER_COMMUTATION])
    assert not report.ok, "off-by-one Dx must be caught"
    cxs = report.counterexamples
    assert any(c.identity == "D_x = v^x · l_x" for c in cxs)
    # Concrete falsifying age is captured.
    dx_cx = [c for c in cxs if c.identity == "D_x = v^x · l_x"][0]
    assert "x" in dx_cx.example


def test_commutation_internal_identities_alone_do_not_catch_off_by_one():
    """Proves the false-coverage hole was real: with the Dx-definition identity
    removed, the off-by-one Dx kernel would pass on recursion/sum alone."""
    bad_Dx = lambda x: (V ** (int(x) + 1)) * _lx(x)
    bad_Nx = lambda x: sum(bad_Dx(k) for k in range(int(x), OMEGA + 1))
    imp = _make_kernel_importer()
    comm = imp("commutation")
    comm.Dx = bad_Dx
    comm.Nx = bad_Nx
    report = _run(importer=imp, tiers=[eng.TIER_COMMUTATION])
    # The recursion / sum identities themselves still hold for the wrong Dx.
    nx_cxs = [
        c for c in report.counterexamples
        if c.identity in ("N_x = D_x + N_{x+1}", "N_x = Σ_{k=x}^{omega} D_k")
    ]
    assert nx_cxs == [], "recursion/sum identities are necessary but not sufficient"


def test_commutation_base_age_override():
    """A declared non-zero commutation base shifts the discount exponent to
    ``x - base`` (D_x = v^(x-base)·l_x)."""
    base = 2
    shifted_Dx = lambda x: (V ** (int(x) - base)) * _lx(x)
    shifted_Nx = lambda x: sum(shifted_Dx(k) for k in range(int(x), OMEGA + 1))
    imp = _make_kernel_importer()
    comm = imp("commutation")
    comm.Dx = shifted_Dx
    comm.Nx = shifted_Nx
    interest = {"annual_effective_rate": I, "commutation_base_age": base}
    report = _run(importer=imp, tiers=[eng.TIER_COMMUTATION], interest=interest)
    assert report.ok, "shifted Dx must pass when the matching base is declared"


# --------------------------------------------------------------------------- #
# 2. Engine: applicability fail-fast (unknown applicability = FAIL, not skip)
# --------------------------------------------------------------------------- #


def test_unknown_tier_fails():
    with pytest.raises(eng.ApplicabilityError) as ei:
        eng.select_tiers(["mortality_invariants", "made_up_tier"])
    assert ei.value.code == "unknown_tier"


def test_empty_tiers_fails():
    with pytest.raises(eng.ApplicabilityError) as ei:
        eng.select_tiers([])
    assert ei.value.code == "no_tiers"


def test_missing_required_mapping_fails():
    with pytest.raises(eng.ApplicabilityError) as ei:
        eng.assert_mappings_present(
            eng.TIER_PRESENT_VALUE, {"qx": "commutation.qx", "Ax": "actuarial.Ax"}
        )
    assert ei.value.code == "missing_mapping"


def test_unsupported_timing_fails_pv_tier():
    with pytest.raises(eng.ApplicabilityError) as ei:
        _run(timing="annuity_immediate", tiers=[eng.TIER_PRESENT_VALUE])
    assert ei.value.code == "timing_unknown"


def test_unknown_product_fails_product_tier():
    with pytest.raises(eng.ApplicabilityError) as ei:
        _run(product="unit_linked_fund", tiers=[eng.TIER_PRODUCT])
    assert ei.value.code == "product_unknown"


def test_missing_interest_basis_fails_pv_tier():
    with pytest.raises(eng.ApplicabilityError) as ei:
        _run(interest={}, tiers=[eng.TIER_PRESENT_VALUE])
    assert ei.value.code == "interest_unknown"


def test_missing_omega_fails():
    with pytest.raises(eng.ApplicabilityError) as ei:
        _run(terminal={"q_omega": 1.0}, tiers=[eng.TIER_MORTALITY])
    assert ei.value.code == "terminal_age_unknown"


def test_missing_terminal_policy_fails_when_mortality_runs():
    """Fix 2: no explicit terminal policy + mortality tier on => FAIL (not skip)."""
    with pytest.raises(eng.ApplicabilityError) as ei:
        _run(terminal={"omega": OMEGA}, tiers=[eng.TIER_MORTALITY])
    assert ei.value.code == "terminal_age_unknown"


def test_terminal_policy_not_required_without_mortality_tier():
    """Commutation-only contract need not declare a terminal q-policy."""
    report = _run(terminal={"omega": OMEGA}, tiers=[eng.TIER_COMMUTATION])
    assert report.ok


def test_terminal_policy_mode_q_omega_is_one():
    """``mode: q_omega_is_one`` declares the policy without an explicit q_omega."""
    report = _run(
        terminal={"omega": OMEGA, "mode": "q_omega_is_one"},
        tiers=[eng.TIER_MORTALITY],
    )
    assert report.ok
    assert any("q_omega=1.0" in i for i in report.identities_checked)


def test_terminal_policy_mode_explicit_requires_value():
    with pytest.raises(eng.ApplicabilityError) as ei:
        _run(terminal={"omega": OMEGA, "mode": "explicit"}, tiers=[eng.TIER_MORTALITY])
    assert ei.value.code == "terminal_age_unknown"


def test_terminal_policy_unknown_mode_fails():
    with pytest.raises(eng.ApplicabilityError) as ei:
        _run(
            terminal={"omega": OMEGA, "mode": "made_up"},
            tiers=[eng.TIER_MORTALITY],
        )
    assert ei.value.code == "terminal_age_unknown"


def test_unresolvable_mapping_fails():
    with pytest.raises(eng.ApplicabilityError) as ei:
        eng.resolve_mappings(
            {"qx": "commutation.does_not_exist"}, importer=_make_kernel_importer()
        )
    assert ei.value.code == "mapping_unresolved"


def test_bad_mapping_target_fails():
    with pytest.raises(eng.ApplicabilityError) as ei:
        eng.resolve_mappings({"qx": "not_dotted"})
    assert ei.value.code == "mapping_unresolved"


# --------------------------------------------------------------------------- #
# 3. Engine: Hypothesis is mandatory (never downgrade)
# --------------------------------------------------------------------------- #


def test_engine_required_hypothesis_name():
    with pytest.raises(eng.EngineUnavailableError) as ei:
        eng.require_engine({"name": "numpy", "version": "1.0"})
    assert ei.value.code == "engine_unknown"


def test_engine_version_mismatch_fails():
    import hypothesis

    pinned = "0.0.0-not-installed"
    assert pinned != hypothesis.__version__
    with pytest.raises(eng.EngineUnavailableError) as ei:
        eng.require_engine({"name": "hypothesis", "version": pinned})
    assert ei.value.code == "engine_version_mismatch"


def test_engine_placeholder_version_ok():
    hyp, version, max_ex = eng.require_engine(
        {"name": "hypothesis", "version": "<pinned-from-Artifactory-or-absent>"}
    )
    assert version  # the installed version is reported
    assert max_ex == 200  # default


def test_engine_records_installed_version():
    import hypothesis

    _hyp, version, _ = eng.require_engine({"name": "hypothesis", "version": ""})
    assert version == hypothesis.__version__


# --------------------------------------------------------------------------- #
# 4. End-to-end command (static G2 + confined child G4)
# --------------------------------------------------------------------------- #


def _write_toy(root: Path) -> None:
    """Write a passing toy kernel + a matching contract under *root*."""
    gen = root / "generated"
    gen.mkdir(parents=True, exist_ok=True)
    (root / "info_from_excel").mkdir(parents=True, exist_ok=True)
    (root / "info_from_excel" / "note.json").write_text("{}", encoding="utf-8")
    (gen / "commutation.py").write_text(
        "OMEGA=6\nI=0.025\nV=1.0/(1.0+I)\n"
        "_Q={x:min(0.01+0.01*x,0.9) for x in range(OMEGA)}\n_Q[OMEGA]=1.0\n"
        "_L={0:100000.0}\n"
        "for _x in range(1,OMEGA+1):\n    _L[_x]=_L[_x-1]*(1.0-_Q[_x-1])\n"
        "_L[OMEGA+1]=0.0\n"
        "def qx(x):\n    return _Q[int(x)]\n"
        "def px(x):\n    return 1.0-qx(x)\n"
        "def lx(x):\n    x=int(x)\n    return _L.get(x,0.0 if x>OMEGA else _L[x])\n"
        "def dx(x):\n    return lx(x)-lx(x+1)\n"
        "def Dx(x):\n    x=int(x)\n    return (V**x)*lx(x)\n"
        "def Nx(x):\n    return sum(Dx(k) for k in range(int(x),OMEGA+1))\n"
        "def Cx(x):\n    x=int(x)\n    return (V**(x+1))*dx(x)\n"
        "def Mx(x):\n    return sum(Cx(k) for k in range(int(x),OMEGA+1))\n",
        encoding="utf-8",
    )
    (gen / "actuarial.py").write_text(
        "import commutation\n"
        "def Ax(x):\n    return commutation.Mx(x)/commutation.Dx(x)\n"
        "def aex(x):\n    return commutation.Nx(x)/commutation.Dx(x)\n"
        "def pv_benefits(x):\n    return Ax(x)\n"
        "def pv_premiums(x):\n    return aex(x)\n"
        "def net_premium(x):\n    return pv_benefits(x)/pv_premiums(x)\n",
        encoding="utf-8",
    )
    contract = {
        "schema_version": 1,
        "product_type": "endowment_net_premium",
        "interest_basis": {"annual_effective_rate": 0.025},
        "timing_convention": "annuity_due",
        "terminal_age_policy": {"omega": 6, "q_omega": 1.0},
        "function_mappings": _FULL_MAPPINGS,
        "tiers_enabled": _ALL_TIERS,
        "tolerances": {"rel_tol": 1e-9, "abs_tol": 1e-12},
        "property_engine": {"name": "hypothesis", "version": "", "max_examples": 25},
    }
    (root / "qa_contract.json").write_text(json.dumps(contract), encoding="utf-8")


def _argv(root: Path, contract: str = "qa_contract.json"):
    return [
        "--repo-root", str(root),
        "--generated-dir", str(root / "generated"),
        "--info-dir", str(root / "info_from_excel"),
        "--qa-contract", str(root / contract),
        "--diagnostics-dir", str(root / "diag"),
    ]


def test_cmd_usage_error_missing_flags():
    result = alg_cmd.main([])
    assert result.exit_code == Exit.USAGE
    assert result.status == "failed"


def test_cmd_invalid_contract_is_usage(tmp_path: Path):
    _write_toy(tmp_path)
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
    result = alg_cmd.main(_argv(tmp_path, "bad.json"))
    assert result.exit_code == Exit.USAGE
    assert any(e["code"] == "contract_invalid" for e in result.errors)


def test_cmd_pass_toy_kernel(tmp_path: Path):
    _write_toy(tmp_path)
    result = alg_cmd.main(_argv(tmp_path))
    assert result.exit_code == Exit.OK
    assert result.status == "passed"
    assert result.summary["engine"] == "hypothesis"
    assert result.summary["counterexample_count"] == 0
    assert result.summary["total_cases"] > 0
    assert result.output_hashes.get("algebraic_report")
    assert result.input_hashes  # non-empty (dossier requires this)
    # Ledger written + loadable, no read errors.
    entries, read_errors = load_gate_ledger(tmp_path / "diag")
    assert read_errors == []
    assert len(entries) == 1
    assert entries[0].gate == "G6.algebraic-properties"
    assert entries[0].status == "passed"


def test_cmd_counterexample_exit_31(tmp_path: Path):
    _write_toy(tmp_path)
    # Break the PV balance: inflate aex.
    (tmp_path / "generated" / "actuarial.py").write_text(
        "import commutation\n"
        "def Ax(x):\n    return commutation.Mx(x)/commutation.Dx(x)\n"
        "def aex(x):\n    return 1.05*(commutation.Nx(x)/commutation.Dx(x))\n"
        "def pv_benefits(x):\n    return Ax(x)\n"
        "def pv_premiums(x):\n    return aex(x)\n"
        "def net_premium(x):\n    return pv_benefits(x)/pv_premiums(x)\n",
        encoding="utf-8",
    )
    result = alg_cmd.main(_argv(tmp_path))
    assert result.exit_code == Exit.ALGEBRAIC
    assert result.summary["counterexample_count"] >= 1
    assert any(e["code"] == "counterexample" for e in result.errors)


def test_cmd_off_by_one_dx_exit_31(tmp_path: Path):
    """End-to-end: an off-by-one discount Dx = v^(x+1)·l_x (with Nx kept
    internally consistent) now FAILS the commutation tier (exit 31) on the
    live D_x = v^x·l_x definition — the false-coverage hole is closed."""
    _write_toy(tmp_path)
    (tmp_path / "generated" / "commutation.py").write_text(
        "OMEGA=6\nI=0.025\nV=1.0/(1.0+I)\n"
        "_Q={x:min(0.01+0.01*x,0.9) for x in range(OMEGA)}\n_Q[OMEGA]=1.0\n"
        "_L={0:100000.0}\n"
        "for _x in range(1,OMEGA+1):\n    _L[_x]=_L[_x-1]*(1.0-_Q[_x-1])\n"
        "_L[OMEGA+1]=0.0\n"
        "def qx(x):\n    return _Q[int(x)]\n"
        "def px(x):\n    return 1.0-qx(x)\n"
        "def lx(x):\n    x=int(x)\n    return _L.get(x,0.0 if x>OMEGA else _L[x])\n"
        "def dx(x):\n    return lx(x)-lx(x+1)\n"
        # OFF-BY-ONE: exponent x+1 instead of x.
        "def Dx(x):\n    x=int(x)\n    return (V**(x+1))*lx(x)\n"
        "def Nx(x):\n    return sum(Dx(k) for k in range(int(x),OMEGA+1))\n"
        "def Cx(x):\n    x=int(x)\n    return (V**(x+1))*dx(x)\n"
        "def Mx(x):\n    return sum(Cx(k) for k in range(int(x),OMEGA+1))\n",
        encoding="utf-8",
    )
    # Only the commutation tier so the off-by-one Dx is isolated (PV tier would
    # also flag it; we want to prove commutation itself catches it).
    contract = json.loads((tmp_path / "qa_contract.json").read_text())
    contract["tiers_enabled"] = ["commutation_identities"]
    (tmp_path / "obo.json").write_text(json.dumps(contract), encoding="utf-8")
    result = alg_cmd.main(_argv(tmp_path, "obo.json"))
    assert result.exit_code == Exit.ALGEBRAIC
    assert result.summary["counterexample_count"] >= 1
    assert any(e["code"] == "counterexample" for e in result.errors)


def test_cmd_missing_terminal_policy_exit_31(tmp_path: Path):
    """End-to-end: mortality tier on but no terminal q-policy => exit 31."""
    _write_toy(tmp_path)
    contract = json.loads((tmp_path / "qa_contract.json").read_text())
    contract["tiers_enabled"] = ["mortality_invariants"]
    contract["terminal_age_policy"] = {"omega": 6}  # no q_omega / mode
    (tmp_path / "noterm.json").write_text(json.dumps(contract), encoding="utf-8")
    result = alg_cmd.main(_argv(tmp_path, "noterm.json"))
    assert result.exit_code == Exit.ALGEBRAIC
    assert any(e["code"] == "terminal_age_unknown" for e in result.errors)


def test_cmd_missing_mapping_exit_31(tmp_path: Path):
    _write_toy(tmp_path)
    contract = json.loads((tmp_path / "qa_contract.json").read_text())
    contract["tiers_enabled"] = ["mortality_invariants", "present_value_identities"]
    contract["function_mappings"] = {
        "qx": "commutation.qx",
        "lx": "commutation.lx",
        "Ax": "actuarial.Ax",
    }  # aex missing -> PV tier unknown applicability
    (tmp_path / "mm.json").write_text(json.dumps(contract), encoding="utf-8")
    result = alg_cmd.main(_argv(tmp_path, "mm.json"))
    assert result.exit_code == Exit.ALGEBRAIC
    assert any(e["code"] == "missing_mapping" for e in result.errors)


def test_cmd_unknown_applicability_exit_31(tmp_path: Path):
    _write_toy(tmp_path)
    contract = json.loads((tmp_path / "qa_contract.json").read_text())
    contract["tiers_enabled"] = ["present_value_identities"]
    contract["timing_convention"] = "annuity_immediate"  # unsupported
    (tmp_path / "ut.json").write_text(json.dumps(contract), encoding="utf-8")
    result = alg_cmd.main(_argv(tmp_path, "ut.json"))
    assert result.exit_code == Exit.ALGEBRAIC
    assert any(e["code"] == "timing_unknown" for e in result.errors)


def test_cmd_strict_underdeclaration_exit_31(tmp_path: Path):
    _write_toy(tmp_path)
    contract = json.loads((tmp_path / "qa_contract.json").read_text())
    # Net-premium product but no product_specific tier; --strict must flag it.
    contract["tiers_enabled"] = ["mortality_invariants"]
    (tmp_path / "ud.json").write_text(json.dumps(contract), encoding="utf-8")
    result = alg_cmd.main(_argv(tmp_path, "ud.json") + ["--strict"])
    assert result.exit_code == Exit.ALGEBRAIC
    assert any(e["code"] == "strict_underdeclaration" for e in result.errors)


def test_cmd_security_precondition_blocks_unsafe_kernel(tmp_path: Path):
    _write_toy(tmp_path)
    # Inject a network import into the generated dir; G2 must refuse to execute.
    (tmp_path / "generated" / "evil.py").write_text(
        "import socket\n", encoding="utf-8"
    )
    result = alg_cmd.main(_argv(tmp_path))
    assert result.exit_code == Exit.SECURITY
    assert any(e["code"] == "precondition_failed" for e in result.errors)


def test_cmd_stdout_is_single_json_object(tmp_path: Path, capsysbinary=None):
    """run_command must emit exactly one JSON object on stdout."""
    _write_toy(tmp_path)
    from rechner_pipeline.toolbox._common import run_command

    import io
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        code = run_command(alg_cmd.main, _argv(tmp_path))
    finally:
        sys.stdout = old
    out = buf.getvalue()
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert len(lines) == 1
    obj = json.loads(lines[0])
    assert obj["command"] == "algebraic"
    assert obj["exit_code"] == code == Exit.OK
