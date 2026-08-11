"""Bestandsdaten module: synthetic, reproducible KLV portfolios.

Generates seed-deterministic portfolio data whose per-contract schema maps
1:1 onto the target kernel's ``ModelPoint`` contract
(:mod:`rechner_pipeline.models.bestand`), rolls portfolios forward to a
reporting date (Zeitscheibe), and persists them as Parquet. The generator
draws attributes only — every calculated quantity (premiums, reserves) comes
from the generated target kernel (:mod:`rechner_pipeline.bestand.kernlauf`),
never from formulas of its own.
"""
