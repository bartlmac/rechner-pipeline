---
name: pruefe-migrationscontrolling
description: >-
  Run the deterministic migration controlling of a full portfolio over TWO
  reporting dates and prepare the human acceptance decision for Gate A-M4:
  two-reporting-date Deckungskapital comparison over the FULL portfolio,
  GeVo amounts between the dates, the transformation mapping table, and
  the before/after Bestandsbericht pair, rendered as one acceptance
  report. Trigger ONLY for Gate A-M4: a migration case with a transformed
  portfolio plus the delivered second Bestandsabzug, the GeVo protocol
  and the before/after report pair, with stichtag_2 greater than
  stichtag_1. A vague "pruefe die Migration" request without that
  evidence is not a trigger: clarify the phase first, never run an A-M4
  as a default. Skip for: the actuarial test at each contract's own anchor
  date (aktuartest-durchfuehren, Gates A-M1/A-M2/A-M3 — they come FIRST and
  are separate acceptances), deciding the acceptance itself (human, Gate
  A-M4), computing any actuarial value by hand (deterministic suite
  only), resolving discrepancies (bereite-fachkonflikt-auf).
---

# Migrationscontrolling prüfen

## Fachreferenz vor Arbeit laden

Vor der Arbeit lade diese Fachreferenz GANZ — sie ist verbindlich,
nicht fakultativ:

- [references/fuehrung-und-berichtspaar.md](references/fuehrung-und-berichtspaar.md#berichtspaar)
  — Fortschreibung des uebernommenen Bestands (Anker `fortschreibung`),
  Freischaltung inkl. Fuehrungsprobe (Anker `freischaltung`), das
  Bestandsberichtspaar vor/nach mit den vollstaendigen Aufrufen (Anker
  `berichtspaar`) und der Abnahmebericht (Anker `abnahmebericht`). Was
  sie benennt, steht nicht zusätzlich in dieser Skill-Datei — die
  Referenz ist ihr Zuhause.

## Rolle und Ziel

Du führst das DETERMINISTISCHE Migrationscontrolling einer
Bestandsmigration aus und bereitest das Urteil für die MENSCHLICHE
Abnahme (Gate A-M4) auf. Der Beweis einer Migration endet nicht beim
Stichtags-Foto: Das Zielsystem muss den übernommenen Bestand auch
FORTSCHREIBEN wie das Quellsystem. Geprüft wird deshalb über zwei
Stichtage — jeder Vertrag des Bestands, aggregierend.

ABGRENZUNG (ADR-010): Das Controlling ist die ZWEITE Prüfebene. Die
ERSTE ist der aktuarielle Test je Vertrag am eigenen
Verankerungszeitpunkt (Skill `aktuartest-durchfuehren`, Gate A-M1) —
A-M1 geht A-M4 zwingend voraus; ein A-M4-Entscheid ohne geltende
A-M1-Annahme ist unmöglich. "Vollständig geprüft" heißt HIER: jeder
Vertrag des Bestands (`vollstaendig_geprueft`); im aktuariellen Test
heißt es: die Stichprobe wurde abgearbeitet.

Werkzeuge (alle deterministisch, du rechnest NIE selbst):

- `python -m rechner_pipeline.gates.migrationssuite_lauf` — der EINE Weg
  zum Suite-Beleg, den A-M4 annimmt: Es baut je Vertrag den Prüfauftrag
  aus den Fall-Artefakten, bezieht die Tarifregeln aus der Spez der
  Generation (`tarifregeln_des_falls`, ADR-024, Nachtrag), rechnet mit
  der Engine `qa/migrationssuite` und schreibt deren Ergebnis samt
  Tarifregeln, Eingaben, Führungswert und Pflichtschicht nach
  `abgeleitet/berichte/migrationssuite.json`. Die Engine rechnet je
  Vertrag: Deckungskapital am
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

- Werte rechnet NUR die Suite, und sie läuft NUR über das Kommando
  `gates.migrationssuite_lauf`. Du baust keine Prüfaufträge
  (`VertragsPruefung`) und rufst die Engine
  (`qa.migrationssuite.pruefe_bestand`) nicht selbst: Ein selbst gebauter
  Lauf rechnet nicht mit den belegten Regeln der Spez, sein JSON nennt
  weder Tarifregeln noch Führungswert, und A-M4 verweigert es. Die Engine
  hat für keine Tarifregel eine Vorgabe (Prüfrunde H) — wer sie ruft,
  muss jede Regel nennen, und das tut das Kommando aus der Spez. Du
  interpretierst die Urteile.
- Toleranzen kommen aus `qa` (REL_TOL/ABS_TOL) und werden NIE
  aufgeweicht, um "grün zu werden".
- Jeder Fehlschlag und jeder Befund geht an den Menschen. Du
  korrigierst keine Erwartungswerte und keine Lieferung — eine
  Abweichung ist ein Ergebnis, kein Hindernis.
- Der Bericht ist die Entscheidungsvorlage; die Abnahme selbst ist
  Gate A-M4 (Mensch, Entscheid-Snapshot). Ein Exit-Code `0` des
  Berichts-Kommandos heißt "Vorlage vollständig und ohne Fehlschlag",
  NICHT "abgenommen" — die Abnahme wird mit `gates/gate_entscheid`
  vom Menschen festgehalten. Eine ANNAHME verlangt dort seit ADR-008
  `--freigabe-schluessel <datei>`; die Schlüsseldatei liegt außerhalb
  des Falls und gehört dem Menschen. Du hast sie nicht und bekommst
  sie nicht — ein Agent kann an einem menschlichen Gate ausschließlich
  ablehnen.

## Ablauf

1. Vollständigkeit prüfen: transformierter Bestand (Verzeichnis der
   Übernahme mit Historie und Nebentabellen), Spez der Generation im
   Fall mit belegten Tarifregeln (`abgeleitet/spez/<generation>.spez.json`,
   Scope `bestand`), Bestand-Config der Führung, registrierte Abzüge zu
   beiden Stichtagen, registriertes GeVo-Protokoll. Fehlt etwas: STOPP.
2. Die Suite mit dem Kommando fahren — die Spez liest es selbst, eine
   Tarifregel wird NIE am Aufruf genannt (die früheren Tarifschalter sind
   entfallen; das Kommando verweigert sie und nennt den Abschnitt der
   Spez):

   ```
   python -m rechner_pipeline.gates.migrationssuite_lauf \
       --fall faelle/<fall> --generation klv/tg2015 \
       --abzug-1 <registriert>.csv --abzug-2 <registriert>.csv \
       --gevo-protokoll <registriert>.csv \
       --bestand faelle/<fall>/abgeleitet/bestand/bestand.parquet \
       --config <bestand-config>.toml \
       --stichtag-1 <iso> --stichtag-2 <iso> \
       [--zeilen <zeilen>.json] [--vorgeschichte <registriert>.csv] \
       [--red-anteile-datei <registrierte-auskunft>.csv] \
       [--schicht <schichtbeleg>.json] --repo-root .
   ```

   `--zeilen` ist Pflicht, sobald die Spez mehr als eine Zelle trägt;
   `--vorgeschichte` trägt die Anfangszustände (Alt-Scheiben,
   Beitragsfreistellung, Alt-Absetzung), `--red-anteile-datei` die
   registrierte Auskunft zu den Anteilen. Liegt im festen Fallbestand
   `abgeleitet/bestand/verankerung.parquet`, ist `--schicht` Pflicht:
   zuerst `gates.verankerung_belegen` auf genau diesem Bestand fahren,
   dann seinen abgeleiteten Beleg nennen. Der Beleg muss die gebundenen
   Bytes von `bestand.parquet` und `verankerung.parquet` führen; ein
   registrierter Beleg zählt hier nicht. Dieselbe Pflicht gilt für
   `gates.fuehrungsprobe`. Ohne Verankerung bleibt `--schicht` optional
   (dann zeigt jeder Vertrag sein rohes Verankerungs-Residuum). Weichen die
   Spaltennamen der Lieferung von den Vorgaben ab: `--spalte-<name>`.
   Was das Kommando dabei zieht und in das JSON schreibt — du lieferst es
   nicht von Hand:
   - je Vertrag den gelieferten Bruttojahresbeitrag am
     Migrationsstichtag (`bjb_erwartet_1`, zweite Prüfachse neben dem
     Deckungskapital) und die Zeilenzahl des Abzugs als
     `erwartete_anzahl` (Vollständigkeit der Prüfmenge); fehlt eines,
     weist der Bericht dafür eine Prüflücke aus;
   - die Bindungen, ohne die das JSON KEIN A-M4-Beleg ist und die der
     Abnahmebericht nachrechnet: `stichtag_1`/`stichtag_2`,
     `bestand_sha256`, den Systemstand, die Eingaben (`eingaben`), die
     Tarifregeln, mit denen gerechnet wurde (`tarifregeln`, aus der
     Spez), den Führungswert je Vertrag (`fuehrungswert`, mit der
     `--config`) und die Pflichtschicht (`pflichtschicht`).
   Fehlt eine Tarifregel in der Spez, verweigert das Kommando mit Ausweg
   (A-Box belegen, P-Q3, Spez neu erzeugen) — dann STOPP, nicht umgehen.
   Das JSON wird NIE von Hand nachgebessert — das Kommando in
   Schritt 4 prüft die Zusammenfassung gegen die Einzelurteile und
   bricht sonst mit `20` ab.
3. Bestandsberichte vor/nach erzeugen: gleiche fachliche Bewertungs-
   und Darstellungsregeln, aber jeweils Datenbasis und Horizont des
   geprueften Bestandsstands. VOR: Uebernahmebestand mit zugehoeriger
   Historie/Ledger bis `stichtag_1`; NACH: fortgeschriebener Gesamtbestand
   mit seinem Laufjournal bis `stichtag_2`. Die Horizonte sind bewusst
   verschieden; dies ist nicht Eigenbestand vor/nach Zugang. Die
   vollstaendigen VOR-/NACH-Aufrufe und ihre verbindlichen Regeln
   (Fortschreibung, Freischaltung mit Fuehrungsprobe, Abnahmebericht)
   stehen in der Fachreferenz
   [fuehrung-und-berichtspaar.md](references/fuehrung-und-berichtspaar.md#berichtspaar),
   die du vor der Arbeit ganz gelesen hast (Anker `berichtspaar`).
   Den Betriebsbericht
   mit `--berichtsstichtag` nicht als Fallbericht-Aufruf wiederverwenden.
   Die Zwei-Stichtags-Pruefung liefert die Suite; die Berichte sind
   gebundene visuelle Artefakte, deren fachliche HTML-Semantik A-M4
   nicht automatisch prueft. Im Bestands-Scope muss ausserdem Gate P-B1
   (`gates.bestand_validate`) gruen gelaufen sein: Sein Ledger ist
   Pflichtbeleg fuer A-M4 und wird vom Abnahmebericht mitgebunden.
4. Bericht erzeugen und protokollieren: der vollstaendige Aufruf von
   `gates.abnahmebericht` samt Pflichtartefakten, Ablage und Bindung
   des gruenen Gate-Ledgers steht normativ in der Fachreferenz (Anker
   `abnahmebericht`), die du vor der Arbeit ganz gelesen hast — rufe
   das Kommando wörtlich mit allen dort genannten Angaben auf. Im
   Bestands-Scope zieht es das P-B1-Ledger automatisch (abweichend:
   `--pb1-ledger`) und rechnet den Fuehrungswert der Suite auf den
   gebundenen Bytes nach; Fehlschlag und Befunde werden vollstaendig
   ausgewiesen und nie nachgebessert.
5. Ergebnis dem Menschen zur A-M4-Entscheidung vorlegen, STOPP.

## Abbruchkriterien (STOPP und Mensch fragen)

- Ein Lieferungsteil fehlt oder passt nicht zu den Stichtagen.
- Die Suite meldet Befunde zur Lieferungs-Konsistenz.
- Eine Toleranzfrage stellt sich (nie selbst entscheiden).
- Die Bestandsberichte vor/nach zeigen strukturell Unerwartetes.
