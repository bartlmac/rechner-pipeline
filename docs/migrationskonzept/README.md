# Migrationskonzept — das projektseitige Verfahren

Das Migrationskonzept ist die **projektseitige Instanz** der Methode aus
der [Grundsatzdokumentation](../mathematik/grundsatzdokumentation.md),
Abschnitt 9: je Bestand und Quellsystem einmal
ausgefüllt, Freigabekreis Projektleitung, Quellsystem-Verantwortliche
und Fachexperte Aktuariat. Es beschreibt, wie ein konkreter Bestand
übernommen und geprüft wird — Systemkontext, Datenliefervertrag,
Migrationszugangsroutine, Controlling, aktuarielle Abnahme,
Klärungsprozess, Archiv.

**Es referenziert die Grundsatzdokumentation, nie umgekehrt.**

## Vorlage hier, Instanz im Fall

Dieses Verzeichnis trägt die **Vorlage**. Die ausgefüllte Instanz
eines Falls gehört in seinen Arbeitsbereich
(`faelle/<fall>/`, gitignored, ADR-002) — sie enthält Mandanten-,
Quellsystem- und Lieferdetails, die nicht ins öffentliche Repo
gehören. Was hier steht, ist der Teil, der über alle Fälle gleich
bleibt.

Die Vorlage ist [vorlage.md](vorlage.md) — ein Dokument mit allen elf
Kapiteln, das je Fall kopiert und ausgefüllt wird.

| Kapitel | Inhalt | Stand |
|---|---|---|
| 1-4 | Zweck, Systemkontext, Bestandsabgrenzung, Datenliefervertrag | Gerüst mit ⟨TODO⟩ — fallspezifisch auszufüllen |
| 5 | Migrationszugangsroutine (Statusmodell, Schrittfolge je Vertrag, Kohorten, Protokoll) | **fachlich vorbefüllt** — Änderungen nur nach menschlicher Freigabe |
| 6 | Migrationscontrolling am $t_0$ über den vollen Bestand, Vorlage für Gate A-M4 | ausgearbeitet |
| 7 | Aktuarielle Abnahme am $t_a$ je Vertrag auf einer Stichprobe, Vorlage für Gate A-M1 | ausgearbeitet |
| 8-10 | Fehler- und Klärungsprozess, Archiv, Ablaufplanung | Gerüst mit ⟨TODO⟩ |
| 11 | Entscheidungen und offene Punkte | zwei offene Entscheidungen (E1, E2) |

Zwei Markierungen steuern die Weiterarbeit, beide aus dem Gerüst:
**⟨TODO: …⟩** ist zu erarbeitender Inhalt; **⟨ENTSCHEIDUNG: …⟩** ist
eine offene menschliche Entscheidung, die nie selbst aufgelöst, sondern
in Kapitel 11 geführt und vorgelegt wird. Die Bearbeitungshinweise am
Kopf der Vorlage sind bindend.

Ausgearbeitet sind die Kapitel, deren Werkzeuge gebaut sind (ADR-010);
die übrigen tragen die Struktur und ihre Platzhalter.

## Was hier NICHT steht — die Regel gegen Doppelpflege

Ein Verfahren, das an zwei Stellen beschrieben ist, driftet. Deshalb
hat jede Art von Aussage **genau ein Zuhause**:

| Aussage | Zuhause | Hier stattdessen |
|---|---|---|
| Mathematik der Methode, Invarianten, Toleranzphilosophie | [Grundsatzdokumentation](../mathematik/grundsatzdokumentation.md), Tarifpläne | Verweis auf Kapitelnummer |
| Warum das System so gebaut ist (Alternativen, Konsequenzen) | ADRs unter [../architektur/](../architektur/) | Verweis auf ADR-Nummer |
| Kommandozeilen, Flags, Reihenfolge der Handgriffe | Agenten-Skills unter `.claude/skills/`, Einstieg in `ONBOARDING.md` | Verweis auf den Skill-Namen |
| Was ein Modul rechnet und welche Fälle es hart ablehnt | Modul-Docstrings im Code | Verweis auf das Modul |

Was **nur hier** steht: das Verfahren aus Projektsicht — welche
Prüfebene wann läuft, welche Artefakte dabei entstehen, wer was
entscheidet, was ein Befund für den Fortgang bedeutet, und welche
Nachweise am Ende die Abnahme tragen. Das ist die Sicht, die ein
Prüfer, ein Verantwortlicher Aktuar oder eine Revision braucht und die
in keinem der anderen Dokumente steht.
