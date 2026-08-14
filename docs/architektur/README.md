# Architektur

Architektur-Dokumente und Entscheidungen (ADRs) des Gesamtsystems
"Rechenkern-Entwicklung mit KI, Fokus Bestandsmigration Leben".

## Inhalt

- [ADR-001: Repo-Zielstruktur entlang der Migrations-Pipeline](adr-001-repo-zielstruktur.md)
- [ADR-002: Fall-Arbeitsbereich — das Repo ist das System, nicht der Datenraum](adr-002-fall-arbeitsbereich.md)

## In Arbeit

Der Entwurf der ontologie-getriebenen Migrations-Pipeline (T-Box/A-Box
als einziges Interface zwischen den Pipeline-Stufen, Tarif-
Spezifikationen als Stage-2-Artefakt, menschliche Abnahme-Gates mit
unveraenderlichen Entscheidungs-Snapshots) wird hier abgelegt, sobald
die erste Entwurfsfassung steht. Die Pakete `rechner_pipeline.ontologie`
und `rechner_pipeline.spez` sind bis dahin dokumentierte Platzhalter.
