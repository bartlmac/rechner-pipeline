"""Bestandsdaten module: synthetic, reproducible KLV portfolios.

Generates seed-deterministic portfolio data whose per-contract schema maps
1:1 onto the stable kernel's ``ModelPoint`` contract
(:mod:`rechner_pipeline.models.bestand`), rolls portfolios forward to a
reporting date (Zeitscheibe), and persists them as Parquet. The generator
draws attributes only — every calculated quantity (premiums, reserves) comes
from the kernel, never from formulas of its own. Standard path (decision
2026-08-12): the stable kernel in-process via
:func:`rechner_pipeline.bestand.kernlauf.berechne_vertrag`; the confined
child-process path in the same module remains for transient, freshly
generated migration kernels only.
"""
