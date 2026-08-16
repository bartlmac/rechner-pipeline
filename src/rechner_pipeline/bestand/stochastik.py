"""Distributions and Gaussian copula for the Bestandsdaten generator — no scipy.

Follows the DAV reference architecture: every attribute has a configurable
marginal distribution (inverse-CDF transform of a uniform), and dependencies
between attributes are imposed via a Gaussian copula parameterized with
Spearman rank correlations. Implementation is dependency-lean by decision
(2026-08-11): numpy for linear algebra and draws, stdlib
``statistics.NormalDist`` for the normal CDF/quantile. gamma/beta are not
implemented (would need scipy) and are rejected at config validation.

Determinism: all randomness flows through one ``numpy.random.Generator``
passed in by the caller; no global RNG, no time-based state.

Knoten: klv, bu
"""

from __future__ import annotations

import math
from statistics import NormalDist
from typing import Any, Dict, List, Sequence

import numpy as np

_STD_NORMAL = NormalDist()

# --------------------------------------------------------------------------- #
# Normal helpers (vectorized over numpy arrays via python loops; portfolio
# sizes are thousands, not millions — clarity over micro-optimization)
# --------------------------------------------------------------------------- #


def norm_cdf(z: np.ndarray) -> np.ndarray:
    return np.array([_STD_NORMAL.cdf(float(v)) for v in z], dtype=float)


def norm_inv_cdf(u: np.ndarray) -> np.ndarray:
    return np.array([_STD_NORMAL.inv_cdf(float(v)) for v in u], dtype=float)


def _clip_u(u: np.ndarray) -> np.ndarray:
    """Keep uniforms strictly inside (0, 1) so quantile functions stay finite."""
    eps = 1e-12
    return np.clip(u, eps, 1.0 - eps)


# --------------------------------------------------------------------------- #
# Inverse-CDF transforms per distribution type
# --------------------------------------------------------------------------- #


def q_normal(u: np.ndarray, mean: float, sd: float) -> np.ndarray:
    return mean + sd * norm_inv_cdf(_clip_u(u))


def q_normal_trunc(u: np.ndarray, mean: float, sd: float, lo: float, hi: float) -> np.ndarray:
    """Truncated normal via CDF-window remapping (exact, no rejection)."""
    dist = NormalDist(mean, sd)
    f_lo, f_hi = dist.cdf(lo), dist.cdf(hi)
    if f_hi - f_lo < 1e-12:
        raise ValueError(
            "normal_trunc: Truncation-Fenster liegt numerisch zu weit im "
            f"Verteilungs-Tail (CDF-Masse {f_hi - f_lo:.2e} zwischen "
            f"[{lo}, {hi}] bei mean={mean}, sd={sd})"
        )
    u_mapped = f_lo + _clip_u(u) * (f_hi - f_lo)
    return np.array([dist.inv_cdf(float(v)) for v in _clip_u(u_mapped)], dtype=float)


def q_lognormal(u: np.ndarray, meanlog: float, sdlog: float) -> np.ndarray:
    return np.exp(meanlog + sdlog * norm_inv_cdf(_clip_u(u)))


def q_weibull(u: np.ndarray, shape: float, scale: float) -> np.ndarray:
    return scale * (-np.log(1.0 - _clip_u(u))) ** (1.0 / shape)


def q_poisson(u: np.ndarray, lam: float) -> np.ndarray:
    """Poisson quantile via CDF walk (lam is small in portfolio configs)."""
    out = np.zeros(len(u), dtype=float)
    for i, ui in enumerate(_clip_u(u)):
        k, cdf, pmf = 0, 0.0, math.exp(-lam)
        cdf = pmf
        while cdf < ui and k < 10_000:
            k += 1
            pmf *= lam / k
            cdf += pmf
        out[i] = k
    return out


def q_empirical_discrete(u: np.ndarray, values: Sequence[Any], probs: Sequence[float]) -> np.ndarray:
    """Weighted discrete draw via cumulative weights (the workhorse type)."""
    w = np.asarray([float(p) for p in probs], dtype=float)
    cum = np.cumsum(w / w.sum())
    idx = np.searchsorted(cum, _clip_u(u), side="left")
    return np.asarray(values, dtype=object)[idx]


def transform(u: np.ndarray, typ: str, params: Dict[str, Any]) -> np.ndarray:
    """Dispatch one uniform column through its configured marginal.

    Numeric results honour the optional ``round`` parameter (digits; negative
    rounds to tens/hundreds, like the reference).
    """
    if typ == "normal":
        out = q_normal(u, float(params["mean"]), float(params["sd"]))
    elif typ == "normal_trunc":
        out = q_normal_trunc(
            u, float(params["mean"]), float(params["sd"]),
            float(params["min"]), float(params["max"]),
        )
    elif typ == "lognormal":
        out = q_lognormal(u, float(params["meanlog"]), float(params["sdlog"]))
    elif typ == "weibull":
        out = q_weibull(u, float(params["shape"]), float(params["scale"]))
    elif typ == "poisson":
        out = q_poisson(u, float(params["lambda"]))
    elif typ == "empirical_discrete":
        return q_empirical_discrete(u, params["values"], params["probs"])
    else:  # pragma: no cover - config validation rejects earlier
        raise NotImplementedError(f"Verteilungstyp {typ!r} nicht implementiert")
    digits = params.get("round")
    if digits is not None:
        out = np.round(out, int(digits))
    return out


# --------------------------------------------------------------------------- #
# Gaussian copula
# --------------------------------------------------------------------------- #


def spearman_to_pearson(rho: float) -> float:
    """Convert a Spearman rank correlation to the Gaussian-copula Pearson rho."""
    return 2.0 * math.sin(math.pi * rho / 6.0)


def build_corr_matrix(order: Sequence[str], korrelationen: Sequence[Any]) -> np.ndarray:
    """Symmetric Pearson matrix over ``order`` from configured Spearman pairs."""
    index = {name: i for i, name in enumerate(order)}
    m = np.eye(len(order))
    for korr in korrelationen:
        i, j = index[korr.var_i], index[korr.var_j]
        r = spearman_to_pearson(float(korr.rho))
        m[i, j] = m[j, i] = r
    return m


def nearest_psd(matrix: np.ndarray, eps: float = 1e-8) -> np.ndarray:
    """Repair a correlation matrix to positive semi-definite.

    Eigenvalue clipping with re-normalized unit diagonal — the lean equivalent
    of the reference's nearPD step.
    """
    sym = (matrix + matrix.T) / 2.0
    eigval, eigvec = np.linalg.eigh(sym)
    if eigval.min() >= eps:
        return sym
    clipped = (eigvec * np.maximum(eigval, eps)) @ eigvec.T
    d = np.sqrt(np.diag(clipped))
    return clipped / np.outer(d, d)


def correlated_uniforms(rng: np.random.Generator, corr: np.ndarray, n: int) -> np.ndarray:
    """Draw ``n`` rows of correlated U(0,1) columns (one per matrix dim)."""
    chol = np.linalg.cholesky(nearest_psd(corr))
    z = rng.standard_normal(size=(n, corr.shape[0]))
    correlated = z @ chol.T
    return np.column_stack([norm_cdf(correlated[:, k]) for k in range(corr.shape[0])])


def empirical_spearman(a: np.ndarray, b: np.ndarray) -> float:
    """Spearman rank correlation of two samples (for tests/sanity, no scipy)."""
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    ra -= ra.mean()
    rb -= rb.mean()
    denom = math.sqrt(float((ra**2).sum()) * float((rb**2).sum()))
    return float((ra * rb).sum() / denom) if denom else 0.0
