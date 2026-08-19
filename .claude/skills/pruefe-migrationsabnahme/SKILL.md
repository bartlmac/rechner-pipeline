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
  interpoliert), Bruttojahresbeitrag am Migrationsstichtag (wenn
  geliefert), GeVo-Beträge zwischen den Stichtagen (STO → RKW am
  Ereignismonat, TOD und ABL → Gesamtsumme bzw. nach einer
  Beitragsfreistellung die Summe der beitragsfreien Summen, ERH →
  vertragsweite Scheiben-Bewertung), Deckungskapital am Folgestichtag
  auf dem richtigen Track; Lieferungs-Inkonsistenzen werden Befunde.
  Was die Suite mangels Erwartungswert nicht geprüft hat, steht als
  `pruefluecken` neben dem Urteil — eine Lücke ist nie ein Bestehen.
- `python -m rechner_pipeline.gates.abnahmebericht` — der
  Migrationsabnahmebericht (HTML): Abnahmetests, GeVo-Vergleich,
  Transformations-Tabelle, Verweise auf die Bestandsberichte
  vor/nach der Migration. Das Kommando nimmt das Suite-Ergebnis als
  JSON entgegen, rendert den Bericht in den Fall, schreibt
  `abnahmebericht.gate.json` in die Diagnostics und urteilt über den
  Exit-Code: `0` Vorlage ohne Fehlschlag, `30` Abnahmetest
  fehlgeschlagen oder Befund, `20` Suite-Ergebnis unlesbar oder
  inkonsistent, `2` Aufruf unvollständig.
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
  Gate G-2 (Mensch, Entscheid-Snapshot). Ein Exit-Code `0` des
  Berichts-Kommandos heißt "Vorlage vollständig und ohne Fehlschlag",
  NICHT "abgenommen" — die Abnahme wird mit `gates/gate_entscheid`
  vom Menschen festgehalten.

## Ablauf

1. Vollständigkeit prüfen: transformierter Bestand, Spez (Lesart),
   Folge-Abzug, GeVo-Protokoll, beide Stichtage. Fehlt etwas: STOPP.
2. Je Vertrag den Prüfauftrag bauen (Modellpunkt aus Spez + Vertrag,
   Monats-Stichtage, Erwartungswerte, GeVos). Zwei Größen liegen im
   Bestandsabzug vor und werden DURCHGEREICHT — fehlen sie, weist der
   Bericht dafür je eine Prüflücke aus:
   - `bjb_erwartet_1` je `VertragsPruefung`: der gelieferte
     Bruttojahresbeitrag am Migrationsstichtag (Beitragsspalte des
     Abzugs, z. B. `JBRUTTO`; `0.00`, wo die Beitragszahlung beendet
     oder der Vertrag beitragsfrei ist). Er ist die zweite Prüfachse
     neben dem Deckungskapital: ein um ein Jahr versetztes
     Eintrittsalter verschiebt die Reserve oft nur um Bruchteile eines
     Cents, den Beitrag deutlich.
   - `erwartete_anzahl=` an `pruefe_bestand`: die Zeilenzahl des
     Bestandsabzugs. Ohne sie ist NICHT geprüft, dass die Prüfmenge
     dem gelieferten Bestand entspricht.
   Dann `qa.migrationssuite.pruefe_bestand` laufen lassen und das
   zurückgegebene Dict unverändert als JSON in den Fall schreiben
   (`json.dump`, z. B. `abgeleitet/berichte/migrationssuite.json`).
   Das JSON wird NIE von Hand nachgebessert — das Kommando in
   Schritt 4 prüft die Zusammenfassung gegen die Einzelurteile und
   bricht sonst mit `20` ab.
3. Bestandsberichte vor/nach erzeugen (gleiche Parameter, gleicher
   Horizont — nur so ist der visuelle Vergleich fair).
4. Bericht erzeugen und protokollieren:

   ```
   python -m rechner_pipeline.gates.abnahmebericht \
       --fall faelle/<fall> \
       --suite faelle/<fall>/abgeleitet/berichte/migrationssuite.json \
       --titel "Migrationsabnahme <Fall>" \
       --stichtag-1 <ISO> --stichtag-2 <ISO> \
       [--spec <transformationsspec.json>] \
       [--transformation-ergebnis <ergebnis.json>] \
       [--bestandsbericht-vor <pfad>] [--bestandsbericht-nach <pfad>]
   ```

   Der Bericht landet unter `<fall>/abgeleitet/berichte/`, der
   Ledger-Eintrag `abnahmebericht.gate.json` unter
   `<fall>/abgeleitet/diagnostics/`. Fehlschläge und Befunde werden
   vollständig ausgewiesen (keine Stichproben-Beschönigung); ein
   roter Bericht wird geschrieben wie ein grüner — er IST das
   Beweisstück.
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
