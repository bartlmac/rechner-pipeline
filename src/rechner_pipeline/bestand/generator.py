"""Seed-deterministic portfolio generator (Bestandsaufbau, Stufe 1: KLV).

Draws contract attributes per tariff generation — marginals and pairwise
Spearman correlations from the TOML config, dependence via Gaussian copula
(:mod:`rechner_pipeline.bestand.stochastik`) — and assembles the canonical
portfolio DataFrame (:mod:`rechner_pipeline.models.bestand`).

The generator computes NOTHING actuarial: no premiums, no present values, no
reserves (project decision — calculated quantities come from the target
kernel via :mod:`rechner_pipeline.bestand.kernlauf`).

Determinism: one master seed from the config; every generation draws from its
own child stream ``PCG64(SeedSequence([seed, generation_index]))``, so adding
a generation never changes the contracts of earlier generations.
"""

from __future__ import annotations

import datetime as _dt
from typing import Dict, List

import numpy as np
import pandas as pd

from rechner_pipeline.bestand.config import BestandConfig, TarifGeneration
from rechner_pipeline.bestand.stochastik import (
    build_corr_matrix,
    correlated_uniforms,
    transform,
)
from rechner_pipeline.models.bestand import STAMM_NAMES, stamm_dtypes

#: Fixed draw order of copula columns — part of the determinism contract.
COPULA_ORDER = ("entry_age", "sex", "duration", "premium_duration", "sum_insured")


def _month_first(year: int, month: int) -> _dt.date:
    return _dt.date(year, month, 1)


def _add_years(d: _dt.date, years: int) -> _dt.date:
    return _dt.date(d.year + years, d.month, 1)


def _draw_insurance_start(
    rng: np.random.Generator, gen: TarifGeneration, n: int
) -> List[_dt.date]:
    """Uniform month-first start dates within the generation's validity window."""
    von, bis = gen.gueltig_von, gen.gueltig_bis
    first = von.year * 12 + (von.month - 1) + (1 if von.day > 1 else 0)
    last = bis.year * 12 + (bis.month - 1)
    months = rng.integers(first, last + 1, size=n)
    return [_month_first(int(m) // 12, int(m) % 12 + 1) for m in months]


def _generate_generation(
    gen: TarifGeneration, gen_index: int, master_seed: int
) -> pd.DataFrame:
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([master_seed, gen_index])))
    n = gen.sample_size

    # 1) Correlated uniforms for the copula attributes (fixed column order),
    #    then the marginal transform per configured distribution.
    corr = build_corr_matrix(COPULA_ORDER, gen.korrelationen)
    u = correlated_uniforms(rng, corr, n)
    drawn: Dict[str, np.ndarray] = {}
    for k, merkmal in enumerate(COPULA_ORDER):
        spec = gen.verteilungen[merkmal]
        drawn[merkmal] = transform(u[:, k], spec.typ, spec.params)

    # 2) Independent attributes (after the copula block — fixed order).
    spec_zw = gen.verteilungen["zahlweise"]
    zahlweise_raw = transform(rng.random(n), spec_zw.typ, spec_zw.params)

    # 3) Coerce + constrain into contract-valid integers.
    entry_age = np.asarray(np.rint(drawn["entry_age"].astype(float)), dtype=np.int64)
    entry_age = np.clip(entry_age, 18, gen.max_endalter - 1)

    duration = np.asarray(np.rint(drawn["duration"].astype(float)), dtype=np.int64)
    duration = np.clip(duration, 1, None)
    duration = np.minimum(duration, gen.max_endalter - entry_age)
    duration = np.maximum(duration, 1)

    premium_duration = np.asarray(
        np.rint(drawn["premium_duration"].astype(float)), dtype=np.int64
    )
    premium_duration = np.clip(premium_duration, 1, None)
    premium_duration = np.minimum(premium_duration, duration)

    sum_insured = np.asarray(drawn["sum_insured"], dtype=np.float64)
    sum_insured = np.maximum(sum_insured, 1000.0)

    sex = np.asarray([str(v) for v in drawn["sex"]], dtype=object)
    zahlweise = np.asarray([int(v) for v in zahlweise_raw], dtype=np.int64)

    # 4) Time axis (month-first convention).
    starts = _draw_insurance_start(rng, gen, n)
    birth = [_add_years(s, -int(a)) for s, a in zip(starts, entry_age)]
    ins_end = [_add_years(s, int(d)) for s, d in zip(starts, duration)]
    pay_end = [_add_years(s, int(t)) for s, t in zip(starts, premium_duration)]

    df = pd.DataFrame(
        {
            "police_id": np.arange(1, n + 1, dtype=np.int64) + (gen_index + 1) * 10_000_000,
            "tarif_generation": np.full(n, gen.name, dtype=object),
            "status_id": np.ones(n, dtype=np.int64),
            "status_code": np.full(n, "POL", dtype=object),
            "status_date": pd.to_datetime(starts),
            "sex": sex,
            "date_of_birth": pd.to_datetime(birth),
            "entry_age": entry_age,
            "duration": duration,
            "premium_duration": premium_duration,
            "sum_insured": sum_insured,
            "zahlweise": zahlweise,
            "insurance_start": pd.to_datetime(starts),
            "insurance_end": pd.to_datetime(ins_end),
            "payment_end": pd.to_datetime(pay_end),
        }
    )
    return df


def generate(config: BestandConfig) -> pd.DataFrame:
    """Generate the full portfolio for all configured tariff generations."""
    errors = config.validate()
    if errors:
        raise ValueError("Config ungueltig: " + "; ".join(errors))
    frames = [
        _generate_generation(gen, idx, config.seed)
        for idx, gen in enumerate(config.generationen)
    ]
    df = pd.concat(frames, ignore_index=True)
    df = df[list(STAMM_NAMES)].astype(stamm_dtypes())
    df = df.sort_values("police_id", kind="stable").reset_index(drop=True)
    if df["police_id"].duplicated().any():
        raise ValueError(
            "police_id-Kollision zwischen Generationen — Nummernkreis verletzt "
            "(sample_size-Obergrenze der Config umgangen?)"
        )
    return df
