# Architektur

Architektur-Dokumente und Entscheidungen (ADRs) des Gesamtsystems
"Rechenkern-Entwicklung mit KI, Fokus Bestandsmigration Leben".

## Inhalt

- [Prinzipien P1-P10 der Migrations-Pipeline](prinzipien.md)
- [Migrations-Pipeline v0.1: Ontologie als Stage-Interface](migrations-pipeline-v01.md)
- [Skill-Architektur: die Agenten-Rollen des Gesamtsystems](skill-architektur.md)
- [ADR-001: Repo-Zielstruktur entlang der Migrations-Pipeline](adr-001-repo-zielstruktur.md)
- [ADR-002: Fall-Arbeitsbereich — das Repo ist das System, nicht der Datenraum](adr-002-fall-arbeitsbereich.md)
- [ADR-003: Pydantic fuer T-Box und A-Box](adr-003-pydantic-fuer-ontologie.md)
- [ADR-004: Der Zielkern ist Thiele-Welt — Excel-Paritaet ist Uebersetzungsbeleg, kein Anker](adr-004-thiele-kern-ohne-excel-anker.md)
- [ADR-005: Knoten-Hierarchie, Test-Bindung, Code-Karte und berechneter Impact](adr-005-knoten-hierarchie-und-impact.md)

Die Pakete `rechner_pipeline.ontologie` und `rechner_pipeline.spez`
setzen die Pipeline um; ihr Zusammenspiel und der Praezedenzfall
TG2012 -> TG2015 stehen im Pipeline-Dokument.

Generierte Sicht: [Landkarte des Zielsystems](landkarte.md) (Diagramme aus dem Code, drift-geprueft).
