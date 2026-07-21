"""Algebraic / property-test engine — gate **G6** (§3.5 lines 1754-1761, §3.3
row line 1690, §6.8.6 ``qa_contract.json`` lines 2781-2789, §3.5 G6 line 1748,
risk note lines 1861-1862).

This module is the Excel-*independent* falsification gate. Where golden-master
(G5) only proves the generated kernel reproduces the *values it observed in the
workbook* (and a 4-decimal absolute compare can hide relative drift — see the
SKILL ``_eq4`` gotcha), G6 pressures the generated functions against the
*actuarial identities, bounds and recursions* that must hold for the declared
product / interest / timing convention, regardless of any cached workbook value.

**Hypothesis is mandatory.** The contract's ``property_engine`` declares
``hypothesis`` and a pinned version. If Hypothesis cannot be imported, or the
installed version does not match the pinned one, the gate **fails** (exit 31) —
it never downgrades to a weaker hand-rolled random loop (§3.5 line 1765, risk
note line 1862).

**Unknown applicability is a failure, never a silent skip** (§3.5 line 1761,
line 1748, line 1690). Every enabled tier declares the conventions and function
mappings it needs. If a needed mapping/convention/product/interest/timing
declaration is absent, the tier (and therefore the gate) fails fast with a
structured reason. A tier is never silently marked inapplicable.

Tiers (all over Hypothesis-sampled or enumerated integer-age domains):

* ``mortality_invariants`` — ``0 <= qx <= 1``, ``p_x = 1 - q_x``, finite,
  non-negative deaths ``d_x = l_x - l_{x+1} >= 0``, survival recursion
  ``l_{x+1} = l_x · p_x``, and an explicit terminal-age policy
  ``q(omega) == q_omega``.
* ``commutation_identities`` — ``D_x = v^x · l_x``, ``N_x = Σ_{k>=x} D_k``,
  ``N_x = D_x + N_{x+1}``, and the ``C_x`` / ``M_x`` first-difference identities
  ``M_x = C_x + M_{x+1}`` when those mappings are declared.
* ``present_value_identities`` — ``A_x + d·ä_x = 1``, ``ä_x = (1 - A_x)/d``,
  ``ä_x = 1 + v·p_x·ä_{x+1}``, ``A_x = v·q_x + v·p_x·A_{x+1}``, ``0 <= A_x <= 1``.
* ``product_specific`` (only when declared) — net premium
  ``P = PV_benefits / PV_premium_annuity`` and the equivalence-principle balance
  ``PV(benefits) - P·PV(premiums) == 0``; sum-insured linear scaling when a
  ``sum_insured``-parameterised benefit/premium mapping is declared.

The engine runs **inside the fs_confine child** (so the generated kernel executes
read-only under G4), and the parent (``toolbox.algebraic``) runs the static
security gate (G2) over the generated dir *before* the child is ever launched.
This module therefore contains only pure check logic + a small contract model; it
performs no I/O and imports nothing from the toolbox layer.
"""

from __future__ import annotations

import importlib
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

# --------------------------------------------------------------------------- #
# Tier names (single source of truth)
# --------------------------------------------------------------------------- #

TIER_MORTALITY = "mortality_invariants"
TIER_COMMUTATION = "commutation_identities"
TIER_PRESENT_VALUE = "present_value_identities"
TIER_PRODUCT = "product_specific"

ALL_TIERS: Tuple[str, ...] = (
    TIER_MORTALITY,
    TIER_COMMUTATION,
    TIER_PRESENT_VALUE,
    TIER_PRODUCT,
)

#: Function-mapping keys each tier requires. Missing => unknown applicability =>
#: FAIL (never a silent skip). ``optional`` keys enable extra identities when
#: present but their absence is not itself a failure.
TIER_REQUIRED_MAPPINGS: Dict[str, Tuple[str, ...]] = {
    TIER_MORTALITY: ("qx", "lx"),
    TIER_COMMUTATION: ("lx", "Dx", "Nx"),
    TIER_PRESENT_VALUE: ("qx", "Ax", "aex"),
    TIER_PRODUCT: ("net_premium", "pv_benefits", "pv_premiums"),
}
TIER_OPTIONAL_MAPPINGS: Dict[str, Tuple[str, ...]] = {
    TIER_MORTALITY: (),
    TIER_COMMUTATION: ("Cx", "Mx"),
    TIER_PRESENT_VALUE: (),
    TIER_PRODUCT: ("benefit_scaled", "premium_scaled"),
}


# --------------------------------------------------------------------------- #
# Contract applicability errors (unknown applicability => fail fast)
# --------------------------------------------------------------------------- #


class ApplicabilityError(Exception):
    """Raised when the contract cannot declare a needed convention / mapping /
    product / interest / timing for an enabled tier. Maps to exit 31 — NEVER a
    silent skip (§3.5 line 1761)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# --------------------------------------------------------------------------- #
# Resolved interest basis
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class InterestBasis:
    """Annual-effective interest basis with the standard discount factors.

    ``v = 1/(1+i)`` (one-year discount), ``d = i/(1+i) = 1 - v`` (annual
    discount rate / rate of discount). These are the conventions the PV
    identities (``A_x + d·ä_x = 1`` etc.) are stated under (§3.5 line 1758).
    """

    i: float
    v: float
    d: float

    @classmethod
    def from_contract(cls, interest_basis: Dict[str, Any]) -> "InterestBasis":
        if not isinstance(interest_basis, dict) or not interest_basis:
            raise ApplicabilityError(
                "interest_unknown",
                "interest_basis is required to select present-value identities "
                "but is missing/empty",
            )
        if "annual_effective_rate" not in interest_basis:
            raise ApplicabilityError(
                "interest_unknown",
                "interest_basis.annual_effective_rate is required (declared "
                "annual effective interest, §3.5 line 1758)",
            )
        i = interest_basis["annual_effective_rate"]
        if not isinstance(i, (int, float)) or isinstance(i, bool):
            raise ApplicabilityError(
                "interest_unknown",
                f"interest_basis.annual_effective_rate must be numeric, got {i!r}",
            )
        i = float(i)
        if i <= -1.0:
            raise ApplicabilityError(
                "interest_unknown",
                f"annual_effective_rate {i} is out of range (must be > -1)",
            )
        v = 1.0 / (1.0 + i)
        d = i / (1.0 + i)
        return cls(i=i, v=v, d=d)


#: Timing conventions the PV identities above are stated for. Only the
#: annuity-due immediate-whole-life form is asserted by the universal PV tier;
#: any other declared timing makes the PV identities *unknown applicability*
#: (we will not silently apply the wrong identity — risk note line 1861).
SUPPORTED_PV_TIMING: Tuple[str, ...] = ("annuity_due",)


# --------------------------------------------------------------------------- #
# Tolerances
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Tolerances:
    rel_tol: float = 1e-9
    abs_tol: float = 1e-12

    @classmethod
    def from_contract(cls, tolerances: Dict[str, Any]) -> "Tolerances":
        tol = tolerances or {}
        return cls(
            rel_tol=float(tol.get("rel_tol", 1e-9)),
            abs_tol=float(tol.get("abs_tol", 1e-12)),
        )

    def close(self, a: float, b: float) -> bool:
        return math.isclose(a, b, rel_tol=self.rel_tol, abs_tol=self.abs_tol)


# --------------------------------------------------------------------------- #
# Function-mapping resolution against the imported generated kernel
# --------------------------------------------------------------------------- #


@dataclass
class ResolvedKernel:
    """The generated functions resolved from ``function_mappings`` (e.g.
    ``"commutation.qx"`` -> the ``qx`` callable in module ``commutation``).

    Resolution happens against modules importable from the generated dir, which
    the child has put on ``sys.path``. A declared-but-unresolvable mapping is an
    applicability failure (the contract claimed a function that does not exist).
    """

    funcs: Dict[str, Callable[..., Any]] = field(default_factory=dict)

    def has(self, *names: str) -> bool:
        return all(n in self.funcs for n in names)

    def call(self, name: str, *args: Any) -> float:
        return float(self.funcs[name](*args))


def resolve_mappings(
    function_mappings: Dict[str, str],
    *,
    importer: Optional[Callable[[str], Any]] = None,
) -> ResolvedKernel:
    """Resolve every declared ``key -> "module.func"`` mapping to a callable.

    A mapping whose module or attribute cannot be resolved raises
    :class:`ApplicabilityError` (``mapping_unresolved``): the contract declared a
    function the generated kernel does not actually provide, which is exactly the
    "unknown applicability / missing function mapping" failure (§3.3 line 1690).
    """
    import_module = importer or importlib.import_module
    funcs: Dict[str, Callable[..., Any]] = {}
    for key, target in (function_mappings or {}).items():
        if not isinstance(target, str) or "." not in target:
            raise ApplicabilityError(
                "mapping_unresolved",
                f"function_mappings[{key!r}] must be 'module.func', got {target!r}",
            )
        mod_name, _, attr = target.rpartition(".")
        try:
            module = import_module(mod_name)
        except Exception as exc:  # noqa: BLE001 — surfaced as applicability failure
            raise ApplicabilityError(
                "mapping_unresolved",
                f"function_mappings[{key!r}] -> module {mod_name!r} not importable: {exc}",
            )
        func = getattr(module, attr, None)
        if not callable(func):
            raise ApplicabilityError(
                "mapping_unresolved",
                f"function_mappings[{key!r}] -> {target} is not a callable on the kernel",
            )
        funcs[key] = func
    return ResolvedKernel(funcs=funcs)


# --------------------------------------------------------------------------- #
# Counterexample / per-check result types
# --------------------------------------------------------------------------- #


@dataclass
class Counterexample:
    tier: str
    identity: str
    message: str
    example: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tier": self.tier,
            "identity": self.identity,
            "message": self.message,
            "example": self.example,
        }


@dataclass
class TierReport:
    tier: str
    identities: List[str] = field(default_factory=list)
    cases: int = 0
    counterexamples: List[Counterexample] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.counterexamples

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tier": self.tier,
            "identities": list(self.identities),
            "cases": self.cases,
            "ok": self.ok,
            "counterexamples": [c.to_dict() for c in self.counterexamples],
        }


@dataclass
class AlgebraicReport:
    tiers_selected: List[str] = field(default_factory=list)
    tier_reports: List[TierReport] = field(default_factory=list)
    max_examples: int = 0
    engine: str = ""
    engine_version: str = ""

    @property
    def identities_checked(self) -> List[str]:
        out: List[str] = []
        for tr in self.tier_reports:
            out.extend(tr.identities)
        return out

    @property
    def total_cases(self) -> int:
        return sum(tr.cases for tr in self.tier_reports)

    @property
    def counterexamples(self) -> List[Counterexample]:
        out: List[Counterexample] = []
        for tr in self.tier_reports:
            out.extend(tr.counterexamples)
        return out

    @property
    def ok(self) -> bool:
        return all(tr.ok for tr in self.tier_reports)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "engine": self.engine,
            "engine_version": self.engine_version,
            "max_examples": self.max_examples,
            "tiers_selected": list(self.tiers_selected),
            "identities_checked": self.identities_checked,
            "total_cases": self.total_cases,
            "tier_reports": [tr.to_dict() for tr in self.tier_reports],
            "counterexamples": [c.to_dict() for c in self.counterexamples],
            "ok": self.ok,
        }


# --------------------------------------------------------------------------- #
# Engine availability check (Hypothesis mandatory — never downgrade)
# --------------------------------------------------------------------------- #


class EngineUnavailableError(Exception):
    """Raised when the declared property engine (Hypothesis) is unavailable or
    its installed version does not match the pinned contract version. Maps to
    exit 31 — the gate fails rather than downgrading to a weak random loop
    (§3.5 line 1765, risk note line 1862)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def require_engine(property_engine: Dict[str, Any]) -> Tuple[Any, str, int]:
    """Import & validate the declared property engine.

    Returns ``(hypothesis_module, version, max_examples)``. Raises
    :class:`EngineUnavailableError` if the engine is not ``hypothesis``, cannot
    be imported, or its version does not match a pinned contract version.
    """
    engine = property_engine or {}
    name = str(engine.get("name", "")).strip().lower()
    if name != "hypothesis":
        raise EngineUnavailableError(
            "engine_unknown",
            f"property_engine.name must be 'hypothesis' (the only supported, "
            f"reviewed engine), got {name!r}",
        )
    try:
        hypothesis = importlib.import_module("hypothesis")
    except Exception as exc:  # noqa: BLE001
        raise EngineUnavailableError(
            "engine_unavailable",
            f"Hypothesis is declared but not importable: {exc}. The gate fails "
            f"rather than downgrading to a weaker random loop (§3.5).",
        )
    installed = getattr(hypothesis, "__version__", "")
    pinned = str(engine.get("version", "")).strip()
    # A pinned, concrete version must match the installed one exactly. Placeholder
    # text (e.g. the spec's "<pinned-from-Artifactory-or-absent>") or an absent
    # version means "use whatever reviewed Hypothesis is installed", but a
    # CONCRETE mismatch is a hard failure (recorded versions must agree, §3.5).
    if pinned and not pinned.startswith("<") and pinned != installed:
        raise EngineUnavailableError(
            "engine_version_mismatch",
            f"contract pins hypothesis=={pinned} but {installed} is installed; "
            f"versions must agree (§3.5 line 1765).",
        )
    max_examples = int(engine.get("max_examples", 200))
    if max_examples <= 0:
        max_examples = 200
    return hypothesis, installed, max_examples


# --------------------------------------------------------------------------- #
# Tier selection & applicability validation
# --------------------------------------------------------------------------- #


def select_tiers(tiers_enabled: List[str]) -> List[str]:
    """Return the enabled tiers in canonical order, failing on an unknown tier.

    An unknown tier name is an applicability failure: the contract asked for a
    check the engine does not know, which we must not silently ignore."""
    enabled = list(tiers_enabled or [])
    if not enabled:
        raise ApplicabilityError(
            "no_tiers", "tiers_enabled is empty; at least one tier is required"
        )
    unknown = [t for t in enabled if t not in ALL_TIERS]
    if unknown:
        raise ApplicabilityError(
            "unknown_tier",
            f"tiers_enabled contains unknown tier(s) {unknown}; known tiers are "
            f"{list(ALL_TIERS)}",
        )
    return [t for t in ALL_TIERS if t in enabled]


def assert_mappings_present(tier: str, function_mappings: Dict[str, str]) -> None:
    """Fail fast if a required mapping for *tier* is absent (unknown applicability)."""
    required = TIER_REQUIRED_MAPPINGS.get(tier, ())
    missing = [m for m in required if m not in (function_mappings or {})]
    if missing:
        raise ApplicabilityError(
            "missing_mapping",
            f"tier {tier!r} requires function_mappings {missing} which are not "
            f"declared; unknown applicability is a failure, not a skip "
            f"(§3.5 line 1761).",
        )


# --------------------------------------------------------------------------- #
# Domain helpers
# --------------------------------------------------------------------------- #


def _omega(terminal_age_policy: Dict[str, Any]) -> int:
    policy = terminal_age_policy or {}
    if "omega" not in policy:
        raise ApplicabilityError(
            "terminal_age_unknown",
            "terminal_age_policy.omega is required (explicit terminal-age policy, "
            "§3.5 line 1756)",
        )
    return int(policy["omega"])


#: Recognised explicit terminal-age policy modes. ``q_omega_is_one`` is the
#: standard "the table closes at omega with certain death" convention; ``explicit``
#: means the contract supplies the terminal ``q_omega`` value directly.
TERMINAL_MODE_Q_OMEGA_IS_ONE = "q_omega_is_one"
TERMINAL_MODE_EXPLICIT = "explicit"
SUPPORTED_TERMINAL_MODES: Tuple[str, ...] = (
    TERMINAL_MODE_Q_OMEGA_IS_ONE,
    TERMINAL_MODE_EXPLICIT,
)


def _q_omega(terminal_age_policy: Dict[str, Any]) -> float:
    """Resolve the REQUIRED terminal mortality value ``q(omega)``.

    The contract must declare an explicit terminal-age policy (§3.5 line 1756) —
    the mortality tier may not silently skip ``q(omega) == q_omega`` when it is
    absent. The policy is declared by EITHER:

    * ``terminal_age_policy.q_omega`` — the explicit numeric terminal value, OR
    * ``terminal_age_policy.mode``: ``"q_omega_is_one"`` (close the table with
      certain death, ``q_omega = 1``) or ``"explicit"`` (which then *requires* a
      ``q_omega`` value).

    A missing/unknown policy is an applicability failure (exit 31), never a skip.
    """
    policy = terminal_age_policy or {}
    mode = policy.get("mode")

    if mode is not None:
        mode = str(mode).strip().lower()
        if mode not in SUPPORTED_TERMINAL_MODES:
            raise ApplicabilityError(
                "terminal_age_unknown",
                f"terminal_age_policy.mode={mode!r} is not recognised; supported "
                f"modes are {list(SUPPORTED_TERMINAL_MODES)} (§3.5 line 1756)",
            )
        if mode == TERMINAL_MODE_Q_OMEGA_IS_ONE:
            return 1.0
        # explicit mode still needs the value
        if "q_omega" not in policy:
            raise ApplicabilityError(
                "terminal_age_unknown",
                "terminal_age_policy.mode='explicit' requires terminal_age_policy."
                "q_omega to be declared (§3.5 line 1756)",
            )
        return float(policy["q_omega"])

    if "q_omega" in policy:
        return float(policy["q_omega"])

    raise ApplicabilityError(
        "terminal_age_unknown",
        "no explicit terminal-age policy declared: terminal_age_policy must set "
        "either 'q_omega' or 'mode' (\"q_omega_is_one\"|\"explicit\"); unknown "
        "terminal applicability is a failure, not a silent skip (§3.5 line 1756).",
    )


# --------------------------------------------------------------------------- #
# The check engine — runs the tiered Hypothesis property tests
# --------------------------------------------------------------------------- #


def run_checks(
    *,
    product_type: str,
    interest_basis_raw: Dict[str, Any],
    timing_convention: str,
    terminal_age_policy: Dict[str, Any],
    function_mappings: Dict[str, str],
    tiers_enabled: List[str],
    tolerances_raw: Dict[str, Any],
    property_engine: Dict[str, Any],
    importer: Optional[Callable[[str], Any]] = None,
) -> AlgebraicReport:
    """Run every enabled tier's Hypothesis property tests and return a report.

    Raises :class:`EngineUnavailableError` or :class:`ApplicabilityError` for the
    fail-fast (exit-31) preconditions; a property *counterexample* is recorded in
    the returned report (also exit 31, but with a concrete falsifying example)
    rather than raised.
    """
    hypothesis, version, max_examples = require_engine(property_engine)
    from hypothesis import given, settings, HealthCheck, seed
    from hypothesis import strategies as st

    tiers = select_tiers(tiers_enabled)
    for tier in tiers:
        assert_mappings_present(tier, function_mappings)

    tol = Tolerances.from_contract(tolerances_raw)
    omega = _omega(terminal_age_policy)
    # The terminal-age policy is only required when the mortality tier actually
    # runs (it owns the q(omega) == q_omega check). Resolving it eagerly would
    # wrongly fail a contract that enables only commutation/PV tiers.
    q_omega = (
        _q_omega(terminal_age_policy) if TIER_MORTALITY in tiers else None
    )
    kernel = resolve_mappings(function_mappings, importer=importer)

    report = AlgebraicReport(
        tiers_selected=tiers,
        max_examples=max_examples,
        engine="hypothesis",
        engine_version=version,
    )

    # Deterministic settings: fixed seed + no DB so reruns are stable (a gate must
    # be rerunnable, §3.5 "rerunnable acceptance"). Function-scoped deadline off
    # because the generated kernel may be slow on first import.
    base_settings = settings(
        max_examples=max_examples,
        deadline=None,
        database=None,
        suppress_health_check=[HealthCheck.too_slow],
        print_blob=False,
    )

    # Sampling domain: integer ages strictly below omega so x+1 is a valid age for
    # the recursions; PV recursions also need x+1 in-domain.
    if omega < 1:
        raise ApplicabilityError(
            "terminal_age_unknown", f"omega must be >= 1, got {omega}"
        )
    age_strategy = st.integers(min_value=0, max_value=max(0, omega - 1))

    # A small helper that runs one identity over the age domain and records the
    # first falsifying example as a counterexample on the tier report.
    def _run_identity(
        tr: TierReport,
        identity: str,
        predicate: Callable[[int], None],
        *,
        strategy: Any = age_strategy,
    ) -> None:
        tr.identities.append(identity)
        case_counter = {"n": 0}
        captured: Dict[str, Any] = {}

        @seed(0xA1B2C3D4)
        @base_settings
        @given(strategy)
        def _prop(x: Any) -> None:
            case_counter["n"] += 1
            try:
                predicate(x)
            except AssertionError as exc:
                captured.setdefault("x", x)
                captured.setdefault("detail", str(exc))
                raise

        try:
            _prop()
        except AssertionError as exc:
            tr.counterexamples.append(
                Counterexample(
                    tier=tr.tier,
                    identity=identity,
                    message=str(exc),
                    example={
                        k: v for k, v in captured.items() if k != "detail"
                    }
                    or {"falsifying": repr(exc)},
                )
            )
        tr.cases += case_counter["n"]

    # ------------------------------------------------------------------ tiers --
    for tier in tiers:
        tr = TierReport(tier=tier)
        if tier == TIER_MORTALITY:
            _check_mortality(tr, kernel, tol, omega, q_omega, _run_identity, st)
        elif tier == TIER_COMMUTATION:
            _check_commutation(
                tr, kernel, tol, omega, interest_basis_raw, _run_identity, st
            )
        elif tier == TIER_PRESENT_VALUE:
            _check_present_value(
                tr,
                kernel,
                tol,
                omega,
                timing_convention,
                interest_basis_raw,
                _run_identity,
                st,
            )
        elif tier == TIER_PRODUCT:
            _check_product(
                tr, kernel, tol, omega, product_type, _run_identity, st
            )
        report.tier_reports.append(tr)

    return report


# --------------------------------------------------------------------------- #
# Tier implementations
# --------------------------------------------------------------------------- #


def _finite(name: str, value: float) -> None:
    assert math.isfinite(value), f"{name} is not finite: {value!r}"


def _check_mortality(tr, kernel, tol, omega, q_omega, run_identity, st) -> None:
    def qx_bounds(x: int) -> None:
        q = kernel.call("qx", x)
        _finite("qx", q)
        assert 0.0 <= q <= 1.0, f"qx({x})={q} not in [0,1]"

    run_identity(tr, "0 <= qx <= 1", qx_bounds)

    if kernel.has("px"):
        def px_complement(x: int) -> None:
            q = kernel.call("qx", x)
            p = kernel.call("px", x)
            assert tol.close(p, 1.0 - q), f"px({x})={p} != 1 - qx({x})={1.0 - q}"

        run_identity(tr, "p_x = 1 - q_x", px_complement)

    def lx_nonneg_finite(x: int) -> None:
        lx = kernel.call("lx", x)
        _finite("lx", lx)
        assert lx >= 0.0, f"lx({x})={lx} is negative"

    run_identity(tr, "l_x >= 0 and finite", lx_nonneg_finite)

    def deaths_nonneg(x: int) -> None:
        lx = kernel.call("lx", x)
        lx1 = kernel.call("lx", x + 1)
        dx = lx - lx1
        assert dx >= -tol.abs_tol, f"d_x = l_{x} - l_{x + 1} = {dx} is negative"

    run_identity(tr, "d_x = l_x - l_{x+1} >= 0", deaths_nonneg)

    def survival_recursion(x: int) -> None:
        lx = kernel.call("lx", x)
        lx1 = kernel.call("lx", x + 1)
        q = kernel.call("qx", x)
        assert tol.close(lx1, lx * (1.0 - q)), (
            f"l_{x + 1}={lx1} != l_{x}·p_{x}={lx * (1.0 - q)}"
        )

    run_identity(tr, "l_{x+1} = l_x · (1 - q_x)", survival_recursion)

    # Explicit terminal-age policy: q(omega) must equal the declared q_omega.
    if q_omega is not None:
        def terminal_policy(_x: int) -> None:
            q = kernel.call("qx", omega)
            assert tol.close(q, q_omega), (
                f"terminal-age policy violated: qx(omega={omega})={q} != q_omega={q_omega}"
            )

        run_identity(
            tr,
            f"qx(omega={omega}) == q_omega={q_omega}",
            terminal_policy,
            strategy=st.just(omega),
        )


def _commutation_base_age(interest_basis_raw: Dict[str, Any]) -> int:
    """Resolve the age at which the discount exponent is zero for ``D_x``.

    Standard actuarial convention: ``D_x = v^x · l_x`` with ``x`` the *attained
    age* — i.e. the discount exponent equals the age directly, so the base age is
    ``0``. A contract MAY declare a different commutation base via
    ``interest_basis.commutation_base_age`` (the entry age the table was tabulated
    from), in which case the exponent is ``x - base`` and ``D_x = v^(x-base)·l_x``.
    The DEFAULT (no declaration) is base ``0`` -> exponent ``x``.
    """
    basis = interest_basis_raw or {}
    base = basis.get("commutation_base_age", 0)
    if isinstance(base, bool) or not isinstance(base, (int, float)):
        raise ApplicabilityError(
            "interest_unknown",
            f"interest_basis.commutation_base_age must be an integer age, got "
            f"{base!r}",
        )
    return int(base)


def _check_commutation(
    tr, kernel, tol, omega, interest_basis_raw, run_identity, st
) -> None:
    # D_x = v^x · l_x  — the *definition* of the discounted-survivor commutation
    # column. This is asserted DIRECTLY from the interest basis (v = 1/(1+i)) and
    # the declared ``lx`` mapping; it does NOT rely on any ``vpow`` helper mapping
    # (which existed in no schema/example/spec and left this identity dead code,
    # so an off-by-one ``D_x = v^(x+1)·l_x`` kernel passed the tier on the
    # internally-consistent recursion/sum identities alone). The discount exponent
    # follows the commutation-base convention (default: exponent == attained age).
    basis = InterestBasis.from_contract(interest_basis_raw)
    v = basis.v
    base_age = _commutation_base_age(interest_basis_raw)

    def dx_definition(x: int) -> None:
        dx = kernel.call("Dx", x)
        lx = kernel.call("lx", x)
        _finite("Dx", dx)
        expected = (v ** (x - base_age)) * lx
        assert tol.close(dx, expected), (
            f"D_{x}={dx} != v^({x}-{base_age})·l_{x}={expected} "
            f"(v={v}); commutation definition D_x = v^x·l_x violated"
        )

    run_identity(tr, "D_x = v^x · l_x", dx_definition)

    # Internal recursion / closed-form sum identities (hold for ANY internally
    # consistent Dx, so they are necessary but NOT sufficient — see above):
    #   N_x = D_x + N_{x+1}   (recursive sum identity)
    #   N_x = Σ_{k=x}^{omega} D_k   (closed-form sum identity)
    def nx_recursion(x: int) -> None:
        nx = kernel.call("Nx", x)
        dx = kernel.call("Dx", x)
        nx1 = kernel.call("Nx", x + 1)
        _finite("Nx", nx)
        assert tol.close(nx, dx + nx1), (
            f"N_{x}={nx} != D_{x} + N_{x + 1}={dx + nx1}"
        )

    run_identity(tr, "N_x = D_x + N_{x+1}", nx_recursion)

    def nx_sum(x: int) -> None:
        nx = kernel.call("Nx", x)
        total = 0.0
        for k in range(x, omega + 1):
            total += kernel.call("Dx", k)
        assert tol.close(nx, total), (
            f"N_{x}={nx} != Σ_{{k={x}}}^{{{omega}}} D_k={total}"
        )

    run_identity(tr, "N_x = Σ_{k=x}^{omega} D_k", nx_sum)

    # C_x / M_x first-difference identity, when the mappings are declared.
    if kernel.has("Cx", "Mx"):
        def mx_recursion(x: int) -> None:
            mx = kernel.call("Mx", x)
            cx = kernel.call("Cx", x)
            mx1 = kernel.call("Mx", x + 1)
            assert tol.close(mx, cx + mx1), (
                f"M_{x}={mx} != C_{x} + M_{x + 1}={cx + mx1}"
            )

        run_identity(tr, "M_x = C_x + M_{x+1}", mx_recursion)


def _check_present_value(
    tr, kernel, tol, omega, timing_convention, interest_basis_raw, run_identity, st
) -> None:
    # PV identities are stated for a declared interest basis AND timing. An
    # unsupported timing makes them unknown-applicability: do NOT silently apply.
    basis = InterestBasis.from_contract(interest_basis_raw)
    if (timing_convention or "").strip() not in SUPPORTED_PV_TIMING:
        raise ApplicabilityError(
            "timing_unknown",
            f"present-value identities are stated for timing {list(SUPPORTED_PV_TIMING)} "
            f"but the contract declares timing_convention={timing_convention!r}; "
            f"applying the wrong identity is worse than skipping it (risk note "
            f"line 1861) — failing fast.",
        )
    v, d = basis.v, basis.d

    def ax_bounds(x: int) -> None:
        a = kernel.call("Ax", x)
        _finite("Ax", a)
        assert -tol.abs_tol <= a <= 1.0 + tol.abs_tol, f"A_{x}={a} not in [0,1]"

    run_identity(tr, "0 <= A_x <= 1", ax_bounds)

    def ax_due_balance(x: int) -> None:
        a = kernel.call("Ax", x)
        ae = kernel.call("aex", x)
        assert tol.close(a + d * ae, 1.0), (
            f"A_{x} + d·ä_{x} = {a + d * ae} != 1 (d={d})"
        )

    run_identity(tr, "A_x + d·ä_x = 1", ax_due_balance)

    def aex_from_ax(x: int) -> None:
        a = kernel.call("Ax", x)
        ae = kernel.call("aex", x)
        assert tol.close(ae, (1.0 - a) / d), (
            f"ä_{x}={ae} != (1 - A_{x})/d={(1.0 - a) / d}"
        )

    run_identity(tr, "ä_x = (1 - A_x)/d", aex_from_ax)

    def aex_recursion(x: int) -> None:
        ae = kernel.call("aex", x)
        q = kernel.call("qx", x)
        ae1 = kernel.call("aex", x + 1)
        rhs = 1.0 + v * (1.0 - q) * ae1
        assert tol.close(ae, rhs), f"ä_{x}={ae} != 1 + v·p_{x}·ä_{x + 1}={rhs}"

    run_identity(tr, "ä_x = 1 + v·p_x·ä_{x+1}", aex_recursion)

    def ax_recursion(x: int) -> None:
        a = kernel.call("Ax", x)
        q = kernel.call("qx", x)
        a1 = kernel.call("Ax", x + 1)
        rhs = v * q + v * (1.0 - q) * a1
        assert tol.close(a, rhs), f"A_{x}={a} != v·q_{x} + v·p_{x}·A_{x + 1}={rhs}"

    run_identity(tr, "A_x = v·q_x + v·p_x·A_{x+1}", ax_recursion)


def _check_product(tr, kernel, tol, omega, product_type, run_identity, st) -> None:
    # Product-specific identities ONLY when the product type is a recognised
    # net-premium product. An unknown product => unknown applicability => fail.
    pt = (product_type or "").strip().lower()
    if "net_premium" not in pt:
        raise ApplicabilityError(
            "product_unknown",
            f"product_specific tier enabled but product_type={product_type!r} is not "
            f"a recognised net-premium product; cannot select net-premium identities "
            f"without declaring the product (§3.5 line 1761).",
        )

    # Net premium definition: P = PV_benefits / PV_premium_annuity.
    def net_premium_def(x: int) -> None:
        pvb = kernel.call("pv_benefits", x)
        pvp = kernel.call("pv_premiums", x)
        p = kernel.call("net_premium", x)
        if abs(pvp) <= tol.abs_tol:
            return  # premium annuity ~ 0 at terminal ages: identity degenerate
        assert tol.close(p, pvb / pvp), (
            f"P({x})={p} != PV_benefits/PV_premiums={pvb / pvp}"
        )

    run_identity(tr, "P = PV_benefits / PV_premium_annuity", net_premium_def)

    # Equivalence principle: PV(benefits) - P·PV(premiums) = 0.
    def equivalence(x: int) -> None:
        pvb = kernel.call("pv_benefits", x)
        pvp = kernel.call("pv_premiums", x)
        p = kernel.call("net_premium", x)
        bal = pvb - p * pvp
        assert tol.close(bal, 0.0) or abs(bal) <= tol.abs_tol + tol.rel_tol * abs(pvb), (
            f"PV(benefits) - P·PV(premiums) = {bal} != 0 at x={x}"
        )

    run_identity(tr, "PV(benefits) - P·PV(premiums) = 0", equivalence)

    # Sum-insured linear scaling (expenses/rounding excluded), when declared.
    if kernel.has("benefit_scaled", "premium_scaled"):
        scale_strategy = st.tuples(
            st.integers(min_value=0, max_value=max(0, omega - 1)),
            st.sampled_from([1.0, 2.0, 10.0, 1000.0]),
        )

        def benefit_scaling(pair) -> None:
            x, s = pair
            base = kernel.funcs["benefit_scaled"](x, 1.0)
            scaled = kernel.funcs["benefit_scaled"](x, s)
            assert tol.close(float(scaled), s * float(base)), (
                f"benefit scaling non-linear at x={x}, S={s}: {scaled} != {s}·{base}"
            )

        run_identity(
            tr, "benefit scales linearly with sum insured", benefit_scaling,
            strategy=scale_strategy,
        )
