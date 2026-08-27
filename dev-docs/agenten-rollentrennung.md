# Rollentrennung der Agenten

Stand: 2026-08-27 · Skizze, wartet auf Entscheidung · Auftraggeber

## 1 Problem

Alle Agenten dieses Systems teilen heute **einen** Wissensraum. Die
gemeinsame Anweisung `AGENTS.md` beginnt mit „Shared instructions for
**coding agents working in this repository**" und beschreibt danach
Schichtenkarte, Testdisziplin, Staging-Regeln und die Spiegelung der
Skill-Baeume. Wer sie liest — und sie wird geladen, bevor irgendein
Skill greift —, steht in der Entwicklerwelt.

Das trifft auch die fachlichen Rollen. Der Agent, der die aktuarielle
Abnahme vorbereitet, soll die Welt eines Aktuars sehen: einen
Rechenkern, der Bestaende bewertet und fortschreibt, uebernommene
Bestaende, die an ihrem Verankerungszeitpunkt abgefangen werden, und
Entscheidungspunkte, an denen ein Mensch zeichnet. Stattdessen sieht er
zuerst ein Repository.

**Belegt** ist der Effekt: In der Grundsatzdokumentation, beiden
Tarifplaenen und der Migrationskonzept-Vorlage standen Formulierungen
wie „laeuft als Commit mit dem Aenderungsgrund", „Changelog des
Repositories" und „weicht sie ab, faellt die Suite" — geschrieben von
einem Agenten, der die Dokumente als Repo-Inhalt sah statt als
Fachdokumente eines Versicherungsunternehmens. Bereinigt am 2026-08-27;
die Ursache ist damit nicht behoben.

Messbar ist auch, dass die Rollen fachlich laengst getrennt sind, die
Basis darunter aber nicht. Verhaeltnis technischer zu fachlichen
Stichworten je Skill:

| Skill | technisch | fachlich |
|---|---|---|
| `bereite-fachkonflikt-auf` | 1 | 10 |
| `aktuartest-durchfuehren` | 10 | 56 |
| `pruefe-migrationscontrolling` | 37 | 93 |
| `entwickle-im-zielsystem` | 25 | 9 |
| `author-rechner-toolbox-gate` | 53 | 1 |

## 2 Warum es zaehlt

Das System führt ein Versicherungsunternehmen vor. Wenn seine
Fachdokumente und Berichte in Werkzeugsprache abgleiten, ist die
Vorfuehrung unglaubwuerdig — und zwar genau an der Stelle, an der sie
ueberzeugen muss: beim Verantwortlichen Aktuar, beim Pruefer, in der
Revision.

Der zweite Grund ist methodisch. Das System trennt Verantwortung
konsequent: Migrationssystem gegen Rechenkern, Controlling gegen
aktuariellen Test, Vorschlag gegen Entscheidung. Nur die Agenten, die
diese Trennung ausfuehren, arbeiten alle aus derselben Sicht. Das ist
ein Bruch im eigenen Bauprinzip.

## 3 Loesungsskizze

**Der Kern:** Rollen bekommen eigene Wissensraeume — als
Stellenbeschreibung plus Zugriffsrecht, nicht als Gedaechtnisloeschung.

1. **`AGENTS.md` schneiden.** Sie behaelt, was jede Rolle teilt: Agenten
   schlagen vor, deterministischer Code entscheidet, Menschen
   entscheiden die Gates; keine Klarnamen; nichts erfinden, Unbekanntes
   bleibt offen. Alles Uebrige — Schichtenkarte, Testdisziplin,
   Staging, Ontologie-Werkzeuge — ist Entwicklungsarbeit und wandert
   unter eine eigene Ueberschrift oder in den Entwickler-Skill.
2. **Rollen-Agenten definieren** (`.claude/agents/`), entlang der Rollen
   des Unternehmens: Aktuariat, Migrationsprojekt, Entwicklung. Der
   Systemprompt einer solchen Definition ERSETZT den Standard; er traegt
   das Weltbild der Rolle.
3. **Zugriff je Rolle beschneiden.** Die Werkzeugliste ist eine
   Whitelist: Ohne Kommandozeile gibt es keine Versionsverwaltung und
   keine Testlaeufe. Der Aktuariats-Agent liest, rechnet ueber die
   fachlichen Kommandos und legt vor; er baut nicht.
4. **Fachliche Kommandos fachlich einfuehren.** „Die Pruefrechnung
   startest du mit …" statt „ruf das Modul auf". Ein Aktuar bedient
   heute auch ein Bewertungssystem, ohne dessen Quelltext zu kennen.

**Was die Loesung NICHT leistet:** Sie schaltet kein Wissen ab. Ein
Sprachmodell weiss, was eine Versionsverwaltung ist; man kann es nicht
vergessen lassen. Die Trennung wirkt ueber Rollenbeschreibung und
entzogene Werkzeuge — genau wie im Unternehmen, wo ein Aktuar keinen
Datenbankzugang hat, obwohl er wuesste, was eine Datenbank ist. Wer
einer Rolle die Kommandozeile zurueckgibt, hebt die Trennung auf.

Ebenfalls nicht loesbar: verzeichnisbezogene Anweisungen. Es gibt keine
Moeglichkeit, eine Anweisung nur fuer `docs/` gelten zu lassen.

## 4 Einordnung

**Aufwand:** mittel. Der Schnitt an `AGENTS.md` ist eine Stunde, die
Rollen-Definitionen je eine, das Nachziehen der Skill-Formulierungen
laenger. Der Aufwand liegt nicht im Schreiben, sondern im Abstimmen.

**Abhaengigkeiten:** `AGENTS.md` und der Skill-Katalog sind
Team-Vertraege; die Spiegelung `.claude`/`.agents` ist test-getragen.
Ein Schnitt beruehrt beide Baeume und die Tests, die sie halten.

**Wer entscheidet:** Auftraggeber, gemeinsam mit dem Team — es aendert
die Arbeitsweise aller Mitwirkenden.

**Woran man merkt, dass es faellig wird:** Wenn wieder Werkzeugsprache
in einem Fachdokument auftaucht, wenn eine fachliche Rolle technische
Entscheidungen trifft, oder wenn das System jemandem vorgefuehrt wird,
der aus dem Unternehmen kommt und nicht aus der Entwicklung.

**Nicht jetzt:** Der Umbau gehoert nicht in einen Branch, der die
Migrationspipeline erweitert. Er braucht einen eigenen Vorgang und die
Zustimmung derer, die danach unter den neuen Anweisungen arbeiten.

**Vorarbeit, die schon steht:** Die Regel „Fachdokumente sprechen die
Sprache des Unternehmens" steht im Skill `dokumentiere-system`
(beide Spiegel) — mit dem ausdruecklichen Hinweis, dass sie nicht
pruefbar ist und durch Schreiben unter dem Skill eingehalten wird.
