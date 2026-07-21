"""Orchestration support code for the deterministic toolbox.

In the TARGET architecture the CLI agent owns generation/repair while the
deterministic toolbox owns acceptance. The only orchestration code that
survives the migration is the provenance writer (:mod:`.dossier`), which builds
the upgraded ``run_dossier.json`` (schema_version=2, §6.8.4) and the new
``qa_report.json`` mechanical-acceptance aggregate (§6.8.3) from the gate-result
ledger entries emitted by the individual gate commands.
"""
