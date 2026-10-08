# Architektur

Wie das Migrationssystem gebaut ist und warum. Die Entscheidungen stehen als
Architecture Decision Records (ADRs): je Entscheidung ein Dokument mit
Kontext, Beschluss und Folgen. Die Fachdokumente der PLV, also Mathematik und
Tarifpläne, liegen getrennt davon unter `docs/mathematik/` und
`docs/tarifplaene/`.

## Zum Einstieg

1. [Glossar](glossar.md): die Begriffe, mit denen alle anderen Dokumente
   arbeiten.
2. [Ablauf eines Migrationsfalls](ablauf-eines-falls.md): vom Auftrag bis zum
   Zugang in die Ablage, mit allen Gates.
3. [Skill-Architektur](skill-architektur.md): die Rollen der Agenten und was
   jede darf.
4. [ADR-027](adr-027-fuenf-gegenstaende-keine-infrastruktur.md): was das
   Repository trägt und was nicht.

Die ADRs sind danach ein Nachschlagewerk. Man liest sie, wenn man an der
Stelle arbeitet, die sie regeln.

## Grundlagen

| Dokument | Inhalt | Stand |
|---|---|---|
| [Prinzipien P1 bis P10](prinzipien.md) | die Grundsätze der Migrations-Pipeline: Herkunft je Aussage, Widerspruch als Objekt, Trennung von Vorschlag und Prüfung | gilt |
| [Prüf-Gates: Vertrag und Versionen](gate-vertrag-und-versionen.md) | was jedes Prüf-Gate einhält, sein Kommando und die Geschichte seiner Version | gilt |
| [Landkarte](landkarte.md) | Schichten, Knoten und Module als Diagramme, aus dem Code erzeugt | erzeugt |
| [Migrations-Pipeline v0.1](migrations-pipeline-v01.md) | die Ontologie als Schnittstelle zwischen den Stufen; dazu der erste Fall TG2012 nach TG2015 | teilweise überholt; der Kopf des Dokuments nennt die überholten Abschnitte |

## Entscheidungen

**Der Fall und seine Belege**

| ADR | Entscheidung | Stand |
|---|---|---|
| [002](adr-002-fall-arbeitsbereich.md) | Ein Fall lebt in einem eigenen Arbeitsbereich; das Repository ist das System, nicht der Datenraum | gilt, teilweise abgelöst durch ADR-006 |
| [009](adr-009-fall-scope-und-gate-dag.md) | Der Scope eines Falls (Tarif oder Bestand) bestimmt die Pflichtbelege der Migrationsabnahme | gilt |
| [012](adr-012-gate-namensordnung.md) | Gate-Namen sagen, wer entscheidet und worüber | gilt |
| [025](adr-025-erstabnahme-des-zielsystems.md) | Das Zielsystem wird einmal außerhalb jedes Falls abgenommen; ein Fall zeichnet nur, was er ändert | gilt |
| [026](adr-026-lebenslauf-eines-falls.md) | Ein Fall beginnt mit dem Auftrag des Vorstands und endet mit der Abnahme oder dem Abbruch | gilt |

**Rollen, Schlüssel und Zeichnung**

| ADR | Entscheidung | Stand |
|---|---|---|
| [008](adr-008-signierte-p9-freigaben.md) | Menschliche Entscheide werden mit Schlüsseln signiert, die außerhalb des Falls liegen | gilt |
| [018](adr-018-rollenmodell-und-schluesselklassen.md) | Agenten legen vor, Menschen zeichnen; der Schlüssel bestimmt die Rolle | gilt, ersetzt die Rollenregel vom 2026-09-01 |
| [021](adr-021-belegrollen-und-freigabe-in-models.md) | Belegrollen und Signaturprüfung liegen an einem Ort, den Gate und Betrieb gleich lesen | gilt |

**Quellen, Ontologie und Prüfung**

| ADR | Entscheidung | Stand |
|---|---|---|
| [003](adr-003-pydantic-fuer-ontologie.md) | T-Box und A-Box sind Pydantic-Modelle | gilt |
| [005](adr-005-knoten-hierarchie-und-impact.md) | Code, Tests und Aussagen sind an Knoten gebunden; der Impact einer Änderung wird berechnet | gilt |
| [010](adr-010-aktuarieller-test-und-controlling.md) | Aktuarieller Test und Migrationscontrolling sind getrennte Gates | gilt |
| [016](adr-016-pdf-vorverdichtung.md) | Die Vorverdichtung liest Text-PDF; Texterkennung bleibt draußen | gilt |
| [024](adr-024-tbox-020-tarifwerk-gevo-zustandsextrakt.md) | T-Box 0.2.0: Tarifwerk, Geschäftsvorfälle und Zustand als belegte Aussagen | gilt |

**Rechenkern und Bestand**

| ADR | Entscheidung | Stand |
|---|---|---|
| [004](adr-004-thiele-kern-ohne-excel-referenzwerte.md) | Der Zielkern rechnet nach Thiele; die Parität mit Excel war ein einmaliger Übersetzungsbeleg | gilt, Punkt 2 abgelöst durch ADR-013 |
| [006](adr-006-portierung-ausser-betrieb.md) | Die Portierung von Excel-Rechnern wird außer Betrieb genommen | gilt |
| [007](adr-007-parallele-migrationen-ein-kern.md) | Parallele Migrationen arbeiten an einem Kern, in kleinen, knotengebundenen Schritten | gilt |
| [011](adr-011-bestandsfuehrung.md) | Der Bestand wird geführt: aktueller Zustand je Vertrag und ein Journal | gilt |
| [013](adr-013-kommutations-kreuzcheck-ausser-betrieb.md) | Der Kreuzcheck gegen einen Kommutations-Zweitkern wird außer Betrieb genommen | gilt |
| [014](adr-014-bestandszugang-getrennt-vom-vertragsbeginn.md) | Der Zugang in den Bestand ist vom Vertragsbeginn getrennt | gilt |
| [015](adr-015-uebernommenen-bestand-fortschreiben.md) | Ein übernommener Bestand wird ab dem Zugang fortgeschrieben | gilt |
| [020](adr-020-ein-erzeuger-bestand-aus-dem-zugangsstrom.md) | Der Bestand entsteht aus dem Strom der Zugänge, nicht aus einem gezogenen Anfangsbestand | gilt |
| [022](adr-022-zugangsabnahme-a-b2.md) | Der Betrieb nimmt den Zugang eines übernommenen Bestands mit einer Probe ab | gilt |
| [023](adr-023-herabsetzung-und-teilkuendigung.md) | Herabsetzung und Teilkündigung sind getrennte Geschäftsvorfälle | gilt |

**Repository und Entwicklung**

| ADR | Entscheidung | Stand |
|---|---|---|
| [001](adr-001-repo-zielstruktur.md) | Die Verzeichnisse folgen der Migrations-Pipeline | gilt, teilweise abgelöst durch ADR-006 |
| [017](adr-017-vier-ebenen.md) | Vier Ebenen regeln, wer wen importieren darf: Entwickler, KI-Tool, Vorzeige, Vorzeige-Werkzeuge | gilt |
| [019](adr-019-parallele-testsuite.md) | Die Testsuite läuft parallel | gilt |
| [027](adr-027-fuenf-gegenstaende-keine-infrastruktur.md) | Das Repository trägt fünf Gegenstände und keine Infrastruktur | gilt |

Ältere Dokumente und Belege nennen Gates teils noch mit früheren Kennungen
(`G-2` statt `A-M4`, `O3` statt `P-K1`). Die Zuordnung steht im Register in
[ADR-012](adr-012-gate-namensordnung.md).
