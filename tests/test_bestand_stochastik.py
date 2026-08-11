"""Distribution transforms and Gaussian copula (no scipy)."""

from __future__ import annotations

import numpy as np
import pytest

from rechner_pipeline.bestand.config import Korrelation
from rechner_pipeline.bestand.stochastik import (
    build_corr_matrix,
    correlated_uniforms,
    empirical_spearman,
    nearest_psd,
    norm_cdf,
    norm_inv_cdf,
    q_empirical_discrete,
    q_normal_trunc,
    spearman_to_pearson,
    transform,
)


def _rng(seed: int = 7) -> np.random.Generator:
    return np.random.Generator(np.random.PCG64(seed))


def test_norm_cdf_inv_roundtrip():
    u = np.linspace(0.01, 0.99, 25)
    assert np.allclose(norm_cdf(norm_inv_cdf(u)), u, atol=1e-12)


def test_normal_trunc_respects_bounds_and_center():
    u = _rng().random(4000)
    x = q_normal_trunc(u, mean=36.0, sd=11.0, lo=18.0, hi=60.0)
    assert x.min() >= 18.0 and x.max() <= 60.0
    assert 33.0 < x.mean() < 40.0


def test_empirical_discrete_frequencies_follow_probs():
    u = _rng().random(20000)
    x = q_empirical_discrete(u, values=["a", "b"], probs=[0.8, 0.2])
    share_a = float(np.mean(x == "a"))
    assert 0.78 < share_a < 0.82


def test_transform_applies_negative_rounding():
    u = _rng().random(500)
    x = transform(u, "lognormal", {"meanlog": 10.9, "sdlog": 0.55, "round": -3})
    assert np.all(x % 1000 == 0)


def test_spearman_to_pearson_identity_points():
    assert spearman_to_pearson(0.0) == 0.0
    assert spearman_to_pearson(1.0) == pytest.approx(1.0)
    assert spearman_to_pearson(-1.0) == pytest.approx(-1.0)


def test_nearest_psd_repairs_and_keeps_unit_diagonal():
    bad = np.array([[1.0, 0.95, -0.95], [0.95, 1.0, 0.95], [-0.95, 0.95, 1.0]])
    assert np.linalg.eigvalsh(bad).min() < 0  # tatsaechlich nicht psd
    fixed = nearest_psd(bad)
    assert np.linalg.eigvalsh(fixed).min() >= 0
    assert np.allclose(np.diag(fixed), 1.0, atol=1e-9)


def test_copula_reproduces_configured_rank_correlation():
    order = ("entry_age", "duration")
    corr = build_corr_matrix(order, [Korrelation("entry_age", "duration", -0.45)])
    u = correlated_uniforms(_rng(42), corr, 4000)
    rho = empirical_spearman(u[:, 0], u[:, 1])
    assert -0.55 < rho < -0.35  # Spearman-Ziel -0.45 wird getroffen


def test_copula_is_seed_deterministic():
    order = ("entry_age", "duration")
    corr = build_corr_matrix(order, [Korrelation("entry_age", "duration", 0.3)])
    a = correlated_uniforms(_rng(1), corr, 100)
    b = correlated_uniforms(_rng(1), corr, 100)
    assert np.array_equal(a, b)
