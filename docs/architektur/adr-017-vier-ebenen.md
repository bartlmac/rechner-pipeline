# ADR-017: Vier Ebenen — Entwickler, KI-Tool, Vorzeige, Vorzeige-Werkzeuge

**Status:** angenommen am 2026-09-05 (Maintainer). Die Schritte der
Umsetzung und ihr Stand stehen unter „Umsetzung“.

## Kontext

Das Repository trägt vier Dinge, die bisher als eines beschrieben,
geprüft und dokumentiert wurden: die Arbeit des Entwicklers mit seiner
KI; das KI-Tool, das eine Bestandsmigration agentisch durchführt; die
Vorzeige, an der sich dieses Tool zeigt und testen lässt — ein fiktives
Unternehmen mit Rechenkern, Produkten, Bestand, Bestandsführung und
Migrationsfall; und die Werkzeuge, mit denen die Vorzeige hergestellt
wird. Ein Paket, eine Schichtenkarte, eine README, ein Rollenbegriff.

Zwei Prüfungen, eine externe und eine unabhängige, fanden dieselbe
Ursache hinter verschiedenen Befunden: Die Frage „wer
entscheidet“ hatte drei Antworten, Skills und Auftragsprofile lagen in
verschiedenen Welten (versioniertes Repo gegen Spielleiter-Bereich), der
Fachbericht eines Versicherers erwähnte nicht, dass eine KI-Session
gezeichnet hatte, und die Rahmendokumentation beschrieb Tool und
Vorzeige in einem Atemzug. Keiner dieser Befunde ist mit einer Zeile zu
beheben, weil die Ebene, auf der die Antwort gelten soll, im Code nicht
existiert.

## Entscheidung

Das System hat vier Ebenen. Jedes Modul, jedes Dokument, jede Rolle und
jeder Schlüssel gehört genau einer davon an.

| Ebene | Was sie ist | Beispiele | Während eines Falls |
|---|---|---|---|
| 1 Entwickler und KI | die Arbeit an Tool und Vorzeige | diese Sitzungen, Reviews, ADRs, Suite | der Fall hält an; die Tool-Version wechselt außerhalb |
| 2 KI-Tool | das agentische Migrationssystem, unabhängig vom Unternehmen | Ontologie, Spez-Vertrag, Gates und Ledger, Zeichnungsordnung, Skills, Agentenrollen, die Generatoren der Berichte | fix; im Rahmen konfigurierbar |
| 3 Vorzeige | ein Unternehmen, an dem das Tool greifbar und testbar wird | Referenz-Zielsystem (Rechenkern, Produkte, Tarifpläne), Bestand und Bestandsführung, der Migrationsfall mit seinen Zeichnungen, die Unternehmensseite, die konfigurierten Berichte | lebt |
| 4 Vorzeige-Werkzeuge | was die Vorzeige herstellt und in der Wirklichkeit ein Unternehmen oder Quellsystem liefern würde | Bestandssimulation, Quellsystem-Erzeugung, Regie-Mechanik | außerhalb des Falls |

**Abgrenzungskriterium.** Alles, was bei einem beliebigen Versicherer in
einem beliebigen Fall unverändert eingesetzt würde, ist Tool. Alles,
was nur für die fiktiven Unternehmen gilt, ist Vorzeige. Der Generator
eines Berichts ist Tool, die konfigurierte Instanz und ihr Fachinhalt
sind Vorzeige. Der Gate-Vertrag von P-B1 ist Tool, die Fachregeln des
konkreten Bestands gehören zum Zielsystem.

**Der Rechenkern ist das Referenz-Zielsystem.** Das Tool definiert die
Schnittstelle, die es von einem Zielsystem braucht — Parametrierung
entgegennehmen, Werte liefern, Verlauf liefern —, und diese Schnittstelle
ist Tool. Der Kern, der sie in der Vorzeige erfüllt, ist Vorzeige. Ein
anderes Haus brächte sein eigenes Zielsystem mit.

**Regie: Mechanik im Repo, Auflösungen lokal (Weg B).** Simulations-
werkzeuge, Drehbuchformat, Auftragsprofile simulierter Menschen und
künftige Rückfragen-Generatoren sind versioniertes Ebene-4-Paket. Nur
die konkreten Auflösungen eines Falls — Manipulationen, Antworten —
liegen als lokale, nicht eingecheckte Daten, nach demselben Muster wie
`faelle/`: Code öffentlich, Daten lokal. Damit wird die Vorzeige
reproduzierbar und die Regie testbar, ohne die Vorführung zu verraten.

**Das Tool ist während eines Falls fix.** Änderungen am Tool während
eines laufenden Falls sind ein Ereignis der Ebene 1 — und sie laufen
über kein Laufzeit-Gate.

*Korrigiert am 2026-09-16 (Entscheid des Maintainers).* Hier stand, sie
liefen über das Gate A-K1, und das sei „der Inhalt, der ihm bisher
fehlte“. Beides ist mit der Einführung von `A-O1.tbox-aenderung` und
`A-K2.kernaenderung` überholt: Die T-Box ist ein Teil des Tools, nicht
das ganze Tool — Gates und Ledger, Zeichnungsordnung, Skills und
Agentenrollen gehören ebenfalls dazu, und für die gibt es kein Gate.

Es soll auch keines geben. Ein Fall, der sein Werkzeug während des
Laufs nachschärft, hat keinen festen Boden mehr, auf dem seine Belege
stehen — genau dafür pinnen wir Systemstände. Der Fall hält an und
wartet auf eine neue Tool-Version; die Version wechselt kontrolliert
außerhalb, und der Fall läuft auf dem neuen Stand weiter. Das ist eine
Entscheidung des Maintainers und in der Regel eine kollektive eines
menschlichen Teams — also ausdrücklich keine Rolle des Laufzeitmodells
(ADR-018 hält den Maintainer aus dem Rollenmodell heraus).

Die Vorzeige darf in den ersten Ausbaustufen davon abweichen.

## Konsequenzen

- Rollen und Schlüssel bekommen Ebenen (ADR-018): Agentenrollen des
  Tools legen vor und zeichnen nie; menschliche Rollen zeichnen; in der
  Vorzeige werden menschliche Rollen simuliert, und der Schlüssel sagt
  das.
- Die Schichtenkarte (`ontologie.code_karte`) erhält die Ebene als
  Attribut je Modul und erzwingt: Das Tool importiert nichts aus der
  Vorzeige außer über die Zielsystem-Schnittstelle; die Vorzeige-
  Werkzeuge importiert niemand außer der Vorzeige selbst. Ob daraus
  eine Paketteilung folgt, wird nach der Messung entschieden, nicht
  vorher.
  Reichweite (präzisiert 2026-09-06 nach Befund T22-08): Erzwungen ist
  das innerhalb des Pakets `src/rechner_pipeline` — die Grenze Ebene 2
  zu 3 als gemessene Schnittstelle, die Grenze Ebene 3 zu 4 als feste
  Liste der heute bestehenden Importe in die Simulationsmodule
  (Generator, Stochastik, Ereignis-Engine, Fortschreibungs-Kommando,
  Neugeschäft; `VORZEIGE_NACH_WERKZEUG_ERLAUBT` in
  `ontologie/code_karte.py`, jede neue Kante ist ein Befund), und aus
  Ebene 2 keine Kante in Ebene 4. Nicht gemessen sind Ebene 1
  (Entwickler und KI haben keinen Code) und die Teile der Ebene 4
  außerhalb des Pakets (`simulation/`, `quellsystem/`, die
  Berichtsgeneratoren unter `werkzeuge/`); dass die Berichtsgeneratoren
  das Produkt lesen und nie umgekehrt, gilt heute durch Messung von
  Hand, nicht durch Prüfung — Backlog „werkzeuge/ in die
  Schichtenkarte“. Der Satz „vier Ebenen erzwungen“ wäre zu groß;
  richtig ist: zwei Grenzen im Paket erzwungen, der Rest benannt.
  Nachtrag 2026-09-07 (Freischaltung des übernommenen Bestands,
  dev-docs/freischaltung-uebernommener-bestand.md, Schritt 3): Die
  Zielsystem-Schnittstelle wächst um zwei Kanten aus der Übernahme
  (`gates/bestand_uebernehmen`) in `bestand/migrationszugang` und
  `kern/beitragsreduktion`. Grund: Der Anfangszustand eines
  übernommenen Vertrags entsteht an einem Ort — derselben Ableitung,
  die Prüfstrecke und Verankerung längst über genau diese Kanten
  rufen — und die Übernahme materialisiert ihn in den Tabellen der
  Führung. Zwei Rechenwege für denselben Zustand waren der Befund;
  eine zweite Ableitung im Tool wäre die Wiederholung davon. Keine
  neue Art von Kante, dieselbe Schnittstelle von einem weiteren Modul.
  Dazu (Schritt 6) die Führungsprobe `gates/fuehrungsprobe`: Sie
  stellt den geführten Bestand gegen die Prüfstrecke und liest dazu
  die Config und die Tabellen der Führung (`bestand/config`,
  `bestand/parquet_io`, `bestand/auswertung` für die Grundlagen je
  Police) und rechnet mit Kern, Verfahren und Schicht — sechs Kanten,
  jede davon bei `migrationssuite_lauf` oder `bestand_validate` schon
  vorhanden. Ein Tool-Modul, das die Führung prüft, muss die Führung
  lesen; erzeugen tut es nichts.
- README, ONBOARDING und die Unternehmensseite werden nach Ebenen
  geschnitten: Was ist das Tool, was ist die Vorzeige, was stellt sie
  her. Fachdokumente der Vorzeige nennen KI-Beteiligung und
  Simulationscharakter.
- Der zweite Baldrian-Lauf wird als Ausnahme ausgewiesen: Seine
  Zeichnungen erfolgten durch KI-Sessions im Mandat unter der Rolle
  `mensch`. Die Snapshots bleiben gültig und gepinnt; der Fachbericht
  und die Fall-Seite sagen, wer gezeichnet hat und mit welcher
  Schlüsselklasse.
- Der Tagesbetrieb der Vorzeige (docs/simulation/tagesbetrieb.md) ist
  Ebene 3 und 4 und berührt das Tool nicht.

## Umsetzung

| Schritt | Inhalt | Stand |
|---|---|---|
| 0 | dieses ADR und ADR-018 | angenommen |
| 1 | Zeichnungsordnung mit Schlüsselklassen; Snapshot trägt Besetzung; Agentenschlüssel zeichnen nicht | umgesetzt (ADR-018) |
| 2 | die Agentenrollen als versionierte Definitionen (Ziel, Perspektive, Skills, Schreibgrenzen); Programmleitung orchestriert | umgesetzt, inzwischen fünf Rollen (`.claude/agents/`) |
| 3 | Ebene je Modul in der Schichtenkarte, gemessen und erzwungen | umgesetzt (`ontologie.code_karte.EBENE_JE_SCHICHT`) |
| 4 | README, ONBOARDING, Unternehmensseite nach Ebenen; Fachbericht mit Abgrenzungen | README und ONBOARDING sind seit ADR-027 nach den fünf Gegenständen gegliedert; der übrige Teil ist nicht nachgehalten |

## Bewusst nicht Bestandteil

Eine sofortige Paketteilung; die Herauslösung der Vorzeige in ein
eigenes Repository (das Drift-Prinzip lebt von der Ko-Lokation); die
Modellierung simulierter Rückfragen in der Vorzeige (nächste
Ausbaustufe der Regie, nach Schritt 4).
