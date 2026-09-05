# ADR-017: Vier Ebenen — Entwickler, KI-Tool, Vorzeige, Vorzeige-Werkzeuge

Status: akzeptiert (Auftraggeber, 2026-09-05); Umsetzung in Schritten,
dieses ADR ist Schritt 0.

## Kontext

Das Repository traegt vier Dinge, die bisher als eines beschrieben,
gepruft und dokumentiert wurden: die Arbeit des Entwicklers mit seiner
KI; das KI-Tool, das eine Bestandsmigration agentisch durchfuehrt; die
Vorzeige, an der sich dieses Tool zeigt und testen laesst — ein fiktives
Unternehmen mit Rechenkern, Produkten, Bestand, Bestandsfuehrung und
Migrationsfall; und die Werkzeuge, mit denen die Vorzeige hergestellt
wird. Ein Paket, eine Schichtenkarte, eine README, ein Rollenbegriff.

Das externe Review T20 (DORA) und das unabhaengige Review U1 fanden
dieselbe Ursache hinter verschiedenen Befunden: Die Frage "wer
entscheidet" hatte drei Antworten, Skills und Auftragsprofile lagen in
verschiedenen Welten (versioniertes Repo gegen Spielleiter-Bereich), der
Fachbericht eines Versicherers erwaehnte nicht, dass eine KI-Session
gezeichnet hatte, und die Rahmendokumentation beschrieb Tool und
Vorzeige in einem Atemzug. Keiner dieser Befunde ist mit einer Zeile zu
beheben, weil die Ebene, auf der die Antwort gelten soll, im Code nicht
existiert.

## Entscheidung

Das System hat vier Ebenen. Jedes Modul, jedes Dokument, jede Rolle und
jeder Schluessel gehoert genau einer davon an.

| Ebene | Was sie ist | Beispiele | Waehrend eines Falls |
|---|---|---|---|
| 1 Entwickler und KI | die Arbeit an Tool und Vorzeige | diese Sitzungen, Reviews, ADRs, Suite | aendert das Tool nur ueber A-K1 |
| 2 KI-Tool | das agentische Migrationssystem, unabhaengig vom Unternehmen | Ontologie, Spez-Vertrag, Gates und Ledger, Zeichnungsordnung, Skills, Agentenrollen, Berichts-GENERATOREN | fix; im Rahmen konfigurierbar |
| 3 Vorzeige | ein Unternehmen, an dem das Tool greifbar und testbar wird | Referenz-Zielsystem (Rechenkern, Produkte, Tarifplaene), Bestand und Bestandsfuehrung, der Migrationsfall mit seinen Zeichnungen, die Unternehmensseite, konfigurierte Berichts-INSTANZEN | lebt |
| 4 Vorzeige-Werkzeuge | was die Vorzeige herstellt und in der Wirklichkeit ein Unternehmen oder Quellsystem liefern wuerde | Bestandssimulation, Quellsystem-Erzeugung, Regie-Mechanik | ausserhalb des Falls |

**Abgrenzungskriterium.** Alles, was bei einem beliebigen Versicherer in
einem beliebigen Fall unveraendert eingesetzt wuerde, ist Tool. Alles,
was nur fuer die fiktiven Unternehmen gilt, ist Vorzeige. Der Generator
eines Berichts ist Tool, die konfigurierte Instanz und ihr Fachinhalt
sind Vorzeige. Der Gate-Vertrag von P-B1 ist Tool, die Fachregeln des
konkreten Bestands gehoeren zum Zielsystem.

**Der Rechenkern ist das Referenz-Zielsystem.** Das Tool definiert die
Schnittstelle, die es von einem Zielsystem braucht — Parametrierung
entgegennehmen, Werte liefern, Verlauf liefern —, und diese Schnittstelle
ist Tool. Der Kern, der sie in der Vorzeige erfuellt, ist Vorzeige. Ein
anderes Haus braechte sein eigenes Zielsystem mit.

**Regie: Mechanik im Repo, Aufloesungen lokal (Weg B).** Simulations-
werkzeuge, Drehbuchformat, Auftragsprofile simulierter Menschen und
kuenftige Rueckfragen-Generatoren sind versioniertes Ebene-4-Paket. Nur
die konkreten Aufloesungen eines Falls — Manipulationen, Antworten —
liegen als lokale, nicht eingecheckte Daten, nach demselben Muster wie
`faelle/`: Code oeffentlich, Daten lokal. Damit wird die Vorzeige
reproduzierbar und die Regie testbar, ohne die Vorfuehrung zu verraten.

**Das Tool ist waehrend eines Falls fix.** Aenderungen am Tool waehrend
eines laufenden Falls sind ein Ereignis der Ebene 1 und laufen ueber das
Gate A-K1; die Vorzeige darf in den ersten Ausbaustufen davon abweichen,
und der Entwickler nimmt solche Aenderungen ab — ausgewiesen, nicht
still. Das gibt A-K1 den Inhalt, der ihm bisher fehlte (U1, Befund Z1-04).

## Konsequenzen

- Rollen und Schluessel bekommen Ebenen (ADR-018): Agentenrollen des
  Tools legen vor und zeichnen nie; menschliche Rollen zeichnen; in der
  Vorzeige werden menschliche Rollen simuliert, und der Schluessel sagt
  das.
- Die Schichtenkarte (`ontologie.code_karte`) erhaelt die Ebene als
  Attribut je Modul und erzwingt: Das Tool importiert nichts aus der
  Vorzeige ausser ueber die Zielsystem-Schnittstelle; die Vorzeige-
  Werkzeuge importiert niemand ausser der Vorzeige selbst. Ob daraus
  eine Paketteilung folgt, wird nach der Messung entschieden, nicht
  vorher.
- README, ONBOARDING und die Unternehmensseite werden nach Ebenen
  geschnitten: Was ist das Tool, was ist die Vorzeige, was stellt sie
  her. Fachdokumente der Vorzeige nennen KI-Beteiligung und
  Simulationscharakter (U1, Klasse K5).
- Der zweite Baldrian-Lauf wird als Ausnahme ausgewiesen: Seine
  Zeichnungen erfolgten durch KI-Sessions im Mandat unter der Rolle
  "mensch". Die Snapshots bleiben gueltig und gepinnt; der Fachbericht
  und die Fall-Seite sagen, wer gezeichnet hat und mit welcher
  Schluesselklasse.
- Der Tagesbetrieb der Vorzeige (docs/simulation/tagesbetrieb.md) ist
  Ebene 3 und 4 und beruehrt das Tool nicht.

## Umsetzung

| Schritt | Inhalt |
|---|---|
| 0 | dieses ADR und ADR-018 |
| 1 | Zeichnungsordnung mit Schluesselklassen; Snapshot traegt Besetzung; Agentenschluessel zeichnen nicht |
| 2 | die vier Agentenrollen als versionierte Definitionen (Ziel, Perspektive, Skills, Schreibgrenzen); Programmleitung orchestriert |
| 3 | Ebene je Modul in der Schichtenkarte, gemessen und erzwungen |
| 4 | README, ONBOARDING, Unternehmensseite nach Ebenen; Fachbericht mit Abgrenzungen |

## Bewusst nicht Bestandteil

Eine sofortige Paketteilung; die Herausloesung der Vorzeige in ein
eigenes Repository (das Drift-Prinzip lebt von der Ko-Lokation); die
Modellierung simulierter Rueckfragen in der Vorzeige (naechste
Ausbaustufe der Regie, nach Schritt 4).
