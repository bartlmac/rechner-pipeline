---
name: integriere-migrationsinkrement
description: >-
  CI discipline for code changes to the target system during a running
  portfolio migration (ADR-007): small node-bound increments on short-lived
  branches, landing only with the full suite green including every open and
  closed case's anchors, human merge/acceptance. Trigger when a migration
  requires a code change (kernel, transformation catalog, valuation API)
  or when integrating any increment while one or more migration cases are
  open. Skip for: the content of the change itself
  (entwickle-im-zielsystem), the acceptance decision (human), pushing
  (always the human).
---

# Migrationsinkrement integrieren

## Rolle und Ziel

Du trägst die CI-Disziplin für Code-Änderungen am Zielsystem WÄHREND
laufender Migrationen. Grundlage ist ADR-007
(`docs/architektur/adr-007-parallele-migrationen-ein-kern.md`): ein
Kern, ein Trunk — die Trennung paralleler Migrationen leistet die
Ontologie, nicht Git. Eine Migration ist eine Folge kleiner,
knotengebundener Inkremente, nie ein langlebiger Branch.

## Nicht verhandelbar (aus ADR-007 und den Working Agreements)

- **Branch je INKREMENT** (Lebensdauer Tage), nie je Migration; keine
  Kern-Forks.
- **Knotenbindung**: jedes Inkrement trägt seine Ontologie-Knoten
  (Bausteine UND Tests); neuer knotengebundener Code ist für andere
  Fälle inert, bis eine Spez ihn parametriert.
- **Landung nur mit maschinellem Nicht-Berührungs-Beweis**: die
  GESAMT-Suite ist grün, einschließlich der Anker und O3-Läufe ALLER
  offenen und abgeschlossenen Fälle. "Betrifft die anderen nicht" wird
  bewiesen, nie behauptet.
- **Rückgrat-Änderungen** (Thiele-Rekursion, Tafelwerk, Bestand) sind
  ein Koordinationspunkt: menschliches Go vorab, grüne Gates aller
  Fälle danach.
- **Pro Generation-Knoten höchstens EIN offener Fall** — Kollision ist
  eine menschliche Serialisierungs-Entscheidung, kein Merge-Problem.
- **Don't ship without tests**; Commit erst NACH grüner Suite;
  benanntes Staging (nie `git add -A`); Merge nach menschlicher
  Abnahme; **Push macht der Mensch**.

## Ablauf je Inkrement

1. Zuschnitt: Was ist das kleinste abnehmbare Stück? Betroffene Knoten
   benennen; `ontologie.impact` für die Berührungsmenge (Tests, Fälle,
   Daten-/Doku-Bindungen) ziehen.
2. Rückgrat berührt oder fremder Fall-Knoten betroffen? STOPP —
   menschliche Koordination vor dem ersten Edit.
3. Implementieren unter `entwickle-im-zielsystem` (Schichtenkarte,
   Knoten-Annotation, Test-Pflicht), Doku-Bindungen nachziehen
   (Landkarte, Tarifplan, ADR wenn Architektur).
4. Gesamt-Suite ausführen; erst bei Grün committen (benanntes Staging,
   ehrliche Commit-Botschaft inkl. Suite-Stand).
5. Abnahme durch den Menschen, Merge, Push durch den Menschen.

## Ausbau (geplant, hier verankern)

- Automatisierte CI (z. B. GitHub Actions) mit derselben Regel:
  Landung nur mit Gesamt-Suite plus fallübergreifenden Gates — die
  Integration der O-Gates in die Team-Abnahme ist mit Albrecht
  abzustimmen (Rollen-Katalog: Release-/Merge-Vorbereitung).
- Knoten-Lebenszyklus (ADR-007 Regel 4): Status
  `in_migration`/`abgenommen` je Generation-Knoten, sobald in der
  T-Box umgesetzt.

## Abbruchkriterien (STOPP und Mensch fragen)

- Das Inkrement lässt sich nicht klein schneiden (verdeckter Umbau).
- Die Suite eines ANDEREN Falls wird rot — nie "mitfixen", erst
  Koordination.
- Ein Merge-Konflikt auf dem Trunk betrifft fremde Knoten.
- Zwei offene Fälle beanspruchen denselben Knoten.
