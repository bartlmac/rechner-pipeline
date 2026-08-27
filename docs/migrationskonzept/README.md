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

Die Vorlage ist [vorlage.md](vorlage.md) — ein Dokument mit allen elf
Kapiteln, das je Fall kopiert und ausgefuellt wird.

| Kapitel | Inhalt | Stand |
|---|---|---|
| 1-4 | Zweck, Systemkontext, Bestandsabgrenzung, Datenliefervertrag | Geruest mit ⟨TODO⟩ — fallspezifisch auszufuellen |
| 5 | Migrationszugangsroutine (Statusmodell, Schrittfolge je Vertrag, Kohorten, Protokoll) | **fachlich vorbefuellt** — Aenderungen nur nach menschlicher Freigabe |
| 6 | Migrationscontrolling am $t_0$ ueber den vollen Bestand, Vorlage fuer Gate G-2 | ausgearbeitet |
| 7 | Aktuarielle Abnahme am $t_a$ je Vertrag auf einer Stichprobe, Vorlage fuer Gate G-A | ausgearbeitet |
| 8-10 | Fehler- und Klaerungsprozess, Archiv, Ablaufplanung | Geruest mit ⟨TODO⟩ |
| 11 | Entscheidungen und offene Punkte | zwei offene Entscheidungen (E1, E2) |

Zwei Markierungen steuern die Weiterarbeit, beide aus dem Geruest:
**⟨TODO: …⟩** ist zu erarbeitender Inhalt; **⟨ENTSCHEIDUNG: …⟩** ist
eine offene menschliche Entscheidung, die nie selbst aufgeloest, sondern
in Kapitel 11 gefuehrt und vorgelegt wird. Die Bearbeitungshinweise am
Kopf der Vorlage sind bindend.

Ausgearbeitet sind die Kapitel, deren Werkzeuge gebaut sind (ADR-010);
die uebrigen tragen die Struktur und ihre Platzhalter.

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
