---
name: pruefe-migrationsabnahme
description: >-
  Run the deterministic migration acceptance checks for a portfolio
  migration and prepare the human acceptance decision: two-reporting-date
  Deckungskapital comparison, GeVo amounts between the dates, the
  transformation mapping table, and the before/after Bestandsbericht pair
  — rendered as one acceptance report. Trigger when a migration case has a
  transformed portfolio plus delivered expectation data (second extract,
  GeVo protocol) and acceptance is due, or the user asks to "die Migration
  abnehmen/pruefen". Skip for: deciding the acceptance itself (human, Gate
  G-2), computing any actuarial value by hand (deterministic suite only),
  resolving discrepancies (bereite-fachkonflikt-auf).
---

# Migrationsabnahme prüfen

## Rolle und Ziel

Du führst die DETERMINISTISCHE Abnahmeprüfung einer Bestandsmigration
aus und bereitest das Urteil für die MENSCHLICHE Abnahme (Gate G-2)
auf. Der Beweis einer Migration endet nicht beim Stichtags-Foto: Das
Zielsystem muss den übernommenen Bestand auch FORTSCHREIBEN wie das
Quellsystem. Geprüft wird deshalb über zwei Stichtage.

Werkzeuge (alle deterministisch, du rechnest NIE selbst):

- `qa/migrationssuite` — je Vertrag: Deckungskapital am
  Migrationsstichtag (Bilanzgröße = Monatsreserve, unterjährig
  interpoliert), GeVo-Beträge zwischen den Stichtagen (STO → RKW am
  Ereignismonat, TOD → Summe, PEX → beitragsfreie Summe, ERH →
  vertragsweite Scheiben-Bewertung), Deckungskapital am Folgestichtag
  auf dem richtigen Track; Lieferungs-Inkonsistenzen werden Befunde.
- `gates/abnahmebericht` — der Migrationsabnahmebericht (HTML):
  Abnahmetests, GeVo-Vergleich, Transformations-Tabelle, Verweise auf
  die Bestandsberichte vor/nach der Migration.
- `bestand/cli_report` — Bestandsbericht VOR (Quellsicht des
  transformierten Bestands) und NACH der Migration (Zielsystem-Lauf):
  zwei Berichte zum visuellen Vergleich, Teil der Abnahme.

## Nicht verhandelbar

- Werte rechnet NUR die Suite. Du baust die Prüfaufträge
  (`VertragsPruefung`) aus den Fall-Artefakten — transformierter
  Bestand, Lesart der Rechnungsgrundlagen aus der Spez, gelieferter
  Folge-Abzug, GeVo-Protokoll — und interpretierst Urteile.
- Toleranzen kommen aus `qa` (REL_TOL/ABS_TOL) und werden NIE
  aufgeweicht, um "grün zu werden".
- Jeder Fehlschlag und jeder Befund geht an den Menschen. Du
  korrigierst keine Erwartungswerte und keine Lieferung — eine
  Abweichung ist ein Ergebnis, kein Hindernis.
- Der Bericht ist die Entscheidungsvorlage; die Abnahme selbst ist
  Gate G-2 (Mensch, Entscheid-Snapshot).

## Ablauf

1. Vollständigkeit prüfen: transformierter Bestand, Spez (Lesart),
   Folge-Abzug, GeVo-Protokoll, beide Stichtage. Fehlt etwas: STOPP.
2. Je Vertrag den Prüfauftrag bauen (Modellpunkt aus Spez + Vertrag,
   Monats-Stichtage, Erwartungswerte, GeVos) und
   `qa.migrationssuite.pruefe_bestand` laufen lassen.
3. Bestandsberichte vor/nach erzeugen (gleiche Parameter, gleicher
   Horizont — nur so ist der visuelle Vergleich fair).
4. `gates/abnahmebericht` erzeugen; Fehlschläge und Befunde
   vollständig ausweisen (keine Stichproben-Beschönigung).
5. Ergebnis dem Menschen zur G-2-Entscheidung vorlegen, STOPP.

## Ausbau (geplant, hier verankern)

- Golden-Master-Tests der Migration: definierte Referenz-Verträge mit
  eingefrorenen Erwartungswerten als dauerhafte Regression — Definition
  folgt, dieser Skill ist ihr Zuhause.

## Abbruchkriterien (STOPP und Mensch fragen)

- Ein Lieferungsteil fehlt oder passt nicht zu den Stichtagen.
- Die Suite meldet Befunde zur Lieferungs-Konsistenz.
- Eine Toleranzfrage stellt sich (nie selbst entscheiden).
- Die Bestandsberichte vor/nach zeigen strukturell Unerwartetes.
