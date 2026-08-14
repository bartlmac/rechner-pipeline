"""Orchestration support code for the deterministic toolbox.

The CLI agent owns generation/repair while the deterministic toolbox owns
acceptance. The orchestration code here is the provenance writer
(:mod:`.dossier`), which builds the ``run_dossier.json`` (schema_version=2) and
the ``qa_report.json`` mechanical-acceptance aggregate from the gate-result
ledger entries emitted by the individual gate commands.
"""
