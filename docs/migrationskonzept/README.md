# Migrationskonzept — das projektseitige Verfahren

Das Migrationskonzept ist die **projektseitige Instanz** der Methode aus
dem [Fachkonzept](../mathematik/konstruktive-neuberechnung.md): je Bestand und Quellsystem einmal
ausgefuellt, Freigabekreis Projektleitung, Quellsystem-Verantwortliche
und Fachexperte Aktuariat. Es beschreibt, wie ein konkreter Bestand
uebernommen und geprueft wird — Systemkontext, Datenliefervertrag,
Migrationszugangsroutine, Controlling, aktuarielle Abnahme,
Klaerungsprozess, Archiv.

**Es referenziert das Fachkonzept, nie umgekehrt.**

## Vorlage hier, Instanz im Fall

Dieses Verzeichnis traegt die **Vorlage**. Die ausgefuellte Instanz
eines Falls gehoert in seinen Arbeitsbereich
(`faelle/<fall>/`, gitignored, ADR-002) — sie enthaelt Mandanten-,
Quellsystem- und Lieferdetails, die nicht ins oeffentliche Repo
gehoeren. Was hier steht, ist der Teil, der ueber alle Faelle gleich
bleibt.

| Kapitel | Inhalt | Stand |
|---|---|---|
| 1-5 | Zweck, Systemkontext, Bestandsabgrenzung, Datenliefervertrag, Migrationszugangsroutine | beim Maintainer, noch nicht hier |
| [6 Migrationscontrolling](06-migrationscontrolling.md) | Pruefung am Migrationsstichtag $t_0$ ueber den vollen Bestand, Vorlage fuer Gate G-2 | ausgearbeitet |
| [7 Aktuarielle Abnahme](07-aktuarielle-abnahme.md) | Pruefung am Verankerungszeitpunkt $t_a$ je Vertrag auf einer Stichprobe, Vorlage fuer Gate G-A | ausgearbeitet |
| 8-11 | Fehler- und Klaerungsprozess, Archiv, Ablaufplanung, Entscheidungen | beim Maintainer, noch nicht hier |

Die Kapitelnummern folgen dem Geruest des Maintainers; die hier
ausgearbeiteten sind die, deren Werkzeuge gebaut sind (ADR-010).

## Was hier NICHT steht — die Regel gegen Doppelpflege

Ein Verfahren, das an zwei Stellen beschrieben ist, driftet. Deshalb
hat jede Art von Aussage **genau ein Zuhause**:

| Aussage | Zuhause | Hier stattdessen |
|---|---|---|
| Mathematik der Methode, Invarianten, Toleranzphilosophie | [../mathematik/](../mathematik/) (Fachkonzept und Grundsatzdokumentation), Tarifplaene | Verweis auf Kapitelnummer |
| Warum das System so gebaut ist (Alternativen, Konsequenzen) | ADRs unter [../architektur/](../architektur/) | Verweis auf ADR-Nummer |
| Kommandozeilen, Flags, Reihenfolge der Handgriffe | Agenten-Skills unter `.claude/skills/`, Einstieg in `ONBOARDING.md` | Verweis auf den Skill-Namen |
| Was ein Modul rechnet und welche Faelle es hart ablehnt | Modul-Docstrings im Code | Verweis auf das Modul |

Was **nur hier** steht: das Verfahren aus Projektsicht — welche
Pruefebene wann laeuft, welche Artefakte dabei entstehen, wer was
entscheidet, was ein Befund fuer den Fortgang bedeutet, und welche
Nachweise am Ende die Abnahme tragen. Das ist die Sicht, die ein
Pruefer, ein Verantwortlicher Aktuar oder eine Revision braucht und die
in keinem der anderen Dokumente steht.
