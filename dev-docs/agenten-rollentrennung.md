# Rollentrennung der Agenten

Stand: 2026-08-27 · Skizze; ENTSCHIEDEN und umgesetzt am 2026-09-05 als
ADR-017/ADR-018 (vier Agentenrollen unter `.claude/agents/`,
Schlüsselklassen, Besetzung im Snapshot). Dieses Dokument bleibt als
Herleitung stehen. · Auftraggeber

## 1 Problem

Alle Agenten dieses Systems teilen heute **einen** Wissensraum. Die
gemeinsame Anweisung `AGENTS.md` beginnt mit „Shared instructions for
**coding agents working in this repository**“ und beschreibt danach
Schichtenkarte, Testdisziplin, Staging-Regeln und die Spiegelung der
Skill-Bäume. Wer sie liest — und sie wird geladen, bevor irgendein
Skill greift —, steht in der Entwicklerwelt.

Das trifft auch die fachlichen Rollen. Der Agent, der die aktuarielle
Abnahme vorbereitet, soll die Welt eines Aktuars sehen: einen
Rechenkern, der Bestände bewertet und fortschreibt, übernommene
Bestände, die an ihrem Verankerungszeitpunkt abgefangen werden, und
Entscheidungspunkte, an denen ein Mensch zeichnet. Stattdessen sieht er
zuerst ein Repository.

**Belegt** ist der Effekt: In der Grundsatzdokumentation, beiden
Tarifplänen und der Migrationskonzept-Vorlage standen Formulierungen
wie „läuft als Commit mit dem Änderungsgrund“, „Changelog des
Repositories“ und „weicht sie ab, fällt die Suite“ — geschrieben von
einem Agenten, der die Dokumente als Repo-Inhalt sah statt als
Fachdokumente eines Versicherungsunternehmens. Bereinigt am 2026-08-27;
die Ursache ist damit nicht behoben.

Messbar ist auch, dass die Rollen fachlich längst getrennt sind, die
Basis darunter aber nicht. Verhältnis technischer zu fachlichen
Stichworten je Skill:

| Skill | technisch | fachlich |
|---|---|---|
| `bereite-fachkonflikt-auf` | 1 | 10 |
| `aktuartest-durchfuehren` | 10 | 56 |
| `pruefe-migrationscontrolling` | 37 | 93 |
| `entwickle-im-zielsystem` | 25 | 9 |
| `author-rechner-toolbox-gate` | 53 | 1 |

## 2 Warum es zählt

Das System führt ein Versicherungsunternehmen vor. Wenn seine
Fachdokumente und Berichte in Werkzeugsprache abgleiten, ist die
Vorführung unglaubwürdig — und zwar genau an der Stelle, an der sie
überzeugen muss: beim Verantwortlichen Aktuar, beim Prüfer, in der
Revision.

Der zweite Grund ist methodisch. Das System trennt Verantwortung
konsequent: Migrationssystem gegen Rechenkern, Controlling gegen
aktuariellen Test, Vorschlag gegen Entscheidung. Nur die Agenten, die
diese Trennung ausführen, arbeiten alle aus derselben Sicht. Das ist
ein Bruch im eigenen Bauprinzip.

## 3 Lösungsskizze

**Der Kern:** Rollen bekommen eigene Wissensräume — als
Stellenbeschreibung plus Zugriffsrecht, nicht als Gedächtnislöschung.

1. **`AGENTS.md` schneiden.** Sie behält, was jede Rolle teilt: Agenten
   schlagen vor, deterministischer Code entscheidet, Menschen
   entscheiden die Gates; keine Klarnamen; nichts erfinden, Unbekanntes
   bleibt offen. Alles Übrige — Schichtenkarte, Testdisziplin,
   Staging, Ontologie-Werkzeuge — ist Entwicklungsarbeit und wandert
   unter eine eigene Überschrift oder in den Entwickler-Skill.
2. **Rollen-Agenten definieren** (`.claude/agents/`), entlang der Rollen
   des Unternehmens: Aktuariat, Migrationsprojekt, Entwicklung. Der
   Systemprompt einer solchen Definition ERSETZT den Standard; er trägt
   das Weltbild der Rolle.
3. **Zugriff je Rolle beschneiden.** Die Werkzeugliste ist eine
   Whitelist: Ohne Kommandozeile gibt es keine Versionsverwaltung und
   keine Testläufe. Der Aktuariats-Agent liest, rechnet über die
   fachlichen Kommandos und legt vor; er baut nicht.
4. **Fachliche Kommandos fachlich einführen.** „Die Prüfrechnung
   startest du mit …“ statt „ruf das Modul auf“. Ein Aktuar bedient
   heute auch ein Bewertungssystem, ohne dessen Quelltext zu kennen.

**Was die Lösung NICHT leistet:** Sie schaltet kein Wissen ab. Ein
Sprachmodell weiß, was eine Versionsverwaltung ist; man kann es nicht
vergessen lassen. Die Trennung wirkt über Rollenbeschreibung und
entzogene Werkzeuge — genau wie im Unternehmen, wo ein Aktuar keinen
Datenbankzugang hat, obwohl er wüsste, was eine Datenbank ist. Wer
einer Rolle die Kommandozeile zurückgibt, hebt die Trennung auf.

Ebenfalls nicht lösbar: verzeichnisbezogene Anweisungen. Es gibt keine
Möglichkeit, eine Anweisung nur für `docs/` gelten zu lassen.

## 4 Einordnung

**Aufwand:** mittel. Der Schnitt an `AGENTS.md` ist eine Stunde, die
Rollen-Definitionen je eine, das Nachziehen der Skill-Formulierungen
länger. Der Aufwand liegt nicht im Schreiben, sondern im Abstimmen.

**Abhängigkeiten:** `AGENTS.md` und der Skill-Katalog sind
Team-Verträge; die Spiegelung `.claude`/`.agents` ist test-getragen.
Ein Schnitt berührt beide Bäume und die Tests, die sie halten.

**Wer entscheidet:** Auftraggeber, gemeinsam mit dem Team — es ändert
die Arbeitsweise aller Mitwirkenden.

**Woran man merkt, dass es fällig wird:** Wenn wieder Werkzeugsprache
in einem Fachdokument auftaucht, wenn eine fachliche Rolle technische
Entscheidungen trifft, oder wenn das System jemandem vorgeführt wird,
der aus dem Unternehmen kommt und nicht aus der Entwicklung.

**Nicht jetzt:** Der Umbau gehört nicht in einen Branch, der die
Migrationspipeline erweitert. Er braucht einen eigenen Vorgang und die
Zustimmung derer, die danach unter den neuen Anweisungen arbeiten.

**Vorarbeit, die schon steht:** Die Regel „Fachdokumente sprechen die
Sprache des Unternehmens“ steht im Skill `dokumentiere-system`
(beide Spiegel) — mit dem ausdrücklichen Hinweis, dass sie nicht
prüfbar ist und durch Schreiben unter dem Skill eingehalten wird.
