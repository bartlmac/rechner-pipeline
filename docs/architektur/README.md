# Architektur

Architektur-Dokumente und Entscheidungen (ADRs) des Gesamtsystems
"Rechenkern-Entwicklung mit KI, Fokus Bestandsmigration Leben".

## Inhalt

- [Migrations-Pipeline v0.1: Ontologie als Stage-Interface](migrations-pipeline-v01.md)
- [ADR-001: Repo-Zielstruktur entlang der Migrations-Pipeline](adr-001-repo-zielstruktur.md)
- [ADR-002: Fall-Arbeitsbereich — das Repo ist das System, nicht der Datenraum](adr-002-fall-arbeitsbereich.md)
- [ADR-003: Pydantic fuer T-Box und A-Box](adr-003-pydantic-fuer-ontologie.md)

Die Pakete `rechner_pipeline.ontologie` und `rechner_pipeline.spez`
setzen die Pipeline um; ihr Zusammenspiel und der Praezedenzfall
TG2012 -> TG2015 stehen im Pipeline-Dokument.
