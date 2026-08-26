---
name: pruefe-migrationscontrolling
description: >-
  Run the deterministic migration controlling checks for a portfolio
  migration and prepare the human acceptance decision: two-reporting-date
  Deckungskapital comparison over the FULL portfolio, GeVo amounts between
  the dates, the transformation mapping table, and the before/after
  Bestandsbericht pair — rendered as one acceptance report for Gate G-2.
  Trigger when a migration case has a transformed portfolio plus delivered
  expectation data (second extract, GeVo protocol) and acceptance is due,
  or the user asks to "die Migration abnehmen/pruefen". Skip for: the
  actuarial test at each contract's own anchor date
  (aktuartest-durchfuehren, Gate G-A — it comes FIRST), deciding the
  acceptance itself (human, Gate G-2), computing any actuarial value by
  hand (deterministic suite only), resolving discrepancies
  (bereite-fachkonflikt-auf).
---

# Migrationscontrolling prüfen

## Rolle und Ziel

Du führst das DETERMINISTISCHE Migrationscontrolling einer
Bestandsmigration aus und bereitest das Urteil für die MENSCHLICHE
Abnahme (Gate G-2) auf. Der Beweis einer Migration endet nicht beim
Stichtags-Foto: Das Zielsystem muss den übernommenen Bestand auch
FORTSCHREIBEN wie das Quellsystem. Geprüft wird deshalb über zwei
Stichtage — jeder Vertrag des Bestands, aggregierend.

ABGRENZUNG (ADR-010): Das Controlling ist die ZWEITE Prüfebene. Die
ERSTE ist der aktuarielle Test je Vertrag am eigenen
Verankerungszeitpunkt (Skill `aktuartest-durchfuehren`, Gate G-A) —
G-A geht G-2 zwingend voraus; ein G-2-Entscheid ohne geltende
G-A-Annahme ist unmöglich. "Vollständig geprüft" heißt HIER: jeder
Vertrag des Bestands (`vollstaendig_geprueft`); im aktuariellen Test
heißt es: die Stichprobe wurde abgearbeitet.

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
  vom Menschen festgehalten. Eine ANNAHME verlangt dort seit ADR-008
  `--freigabe-schluessel <datei>`; die Schlüsseldatei liegt außerhalb
  des Falls und gehört dem Menschen. Du hast sie nicht und bekommst
  sie nicht — ein Agent kann an einem menschlichen Gate ausschließlich
  ablehnen.

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
   Im Bestands-Scope kommen vier Bindungen dazu, ohne die das
   Suite-JSON KEIN G-2-Beleg ist (der Abnahmebericht verlangt sie und
   gleicht sie gegen `fall.json` ab):
   - `stichtag_1=` / `stichtag_2=`: die beiden ISO-Stichtage,
     chronologisch; sie müssen den Berichtsstichtagen entsprechen.
   - `bestand_sha256=`: SHA-256 des geprüften Bestands — dieselbe
     Datei, die Gate B1 geprüft hat.
   - `system=`: der Systemstand aus
     `gates._provenienz.systemstand(repo_root)` (exakt die Schlüssel
     `commit`, `branch`, `dirty`, `quellcode_sha256`).
   Dann `qa.migrationssuite.pruefe_bestand` laufen lassen und das
   zurückgegebene Dict unverändert als JSON in den Fall schreiben
   (`json.dump`, z. B. `abgeleitet/berichte/migrationssuite.json`).
   Das JSON wird NIE von Hand nachgebessert — das Kommando in
   Schritt 4 prüft die Zusammenfassung gegen die Einzelurteile und
   bricht sonst mit `20` ab.
3. Bestandsberichte vor/nach erzeugen (gleiche Parameter, gleicher
   Horizont — nur so ist der visuelle Vergleich fair). Im
   Bestands-Scope muss außerdem Gate B1
   (`gates.bestand_validate`) grün gelaufen sein: Sein Ledger ist
   Pflichtbeleg für G-2 und wird vom Abnahmebericht mitgebunden.
4. Bericht erzeugen und protokollieren. ALLE aufgeführten Angaben
   sind Pflicht — fehlt eine, bricht das Kommando als Usage-Fehler ab:

   ```
   python -m rechner_pipeline.gates.abnahmebericht \
       --fall faelle/<fall> \
       --suite faelle/<fall>/abgeleitet/berichte/migrationssuite.json \
       --titel "Migrationsabnahme <Fall>" \
       --stichtag-1 <ISO> --stichtag-2 <ISO> \
       --spec <transformationsspec.json> \
       --transformation-ergebnis <ergebnis.json> \
       --bestandsbericht-vor <pfad> --bestandsbericht-nach <pfad>
   ```

   Vor- und Nachbericht müssen verschiedene Dateien sein; keine der
   Angaben darf auf dieselbe Datei zeigen wie eine andere oder wie
   der Gate-Ledger. Im Bestands-Scope zieht das Kommando das
   B1-Ledger automatisch aus
   `<fall>/abgeleitet/diagnostics/bestand_validate.gate.json`
   (abweichend: `--b1-ledger`).

   Der Bericht landet unter `<fall>/abgeleitet/berichte/`, der
   Ledger-Eintrag `abnahmebericht.gate.json` unter
   `<fall>/abgeleitet/diagnostics/`. Fehlschläge und Befunde werden
   vollständig ausgewiesen (keine Stichproben-Beschönigung); ein
   roter Bericht wird geschrieben wie ein grüner — er IST das
   Beweisstück.
5. Ergebnis dem Menschen zur G-2-Entscheidung vorlegen, STOPP.

## Abbruchkriterien (STOPP und Mensch fragen)

- Ein Lieferungsteil fehlt oder passt nicht zu den Stichtagen.
- Die Suite meldet Befunde zur Lieferungs-Konsistenz.
- Eine Toleranzfrage stellt sich (nie selbst entscheiden).
- Die Bestandsberichte vor/nach zeigen strukturell Unerwartetes.
