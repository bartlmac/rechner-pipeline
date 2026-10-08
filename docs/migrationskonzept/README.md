# Migrationskonzept

Das Migrationskonzept wendet die Methode aus Abschnitt 9 der
[Grundsatzdokumentation](../mathematik/grundsatzdokumentation.md) auf einen
Bestand an. Es wird je Bestand und Quellsystem einmal ausgefüllt und von
Projektleitung, Verantwortlichen des Quellsystems und Aktuariat
freigegeben. Es beschreibt, wie ein konkreter Bestand übernommen und
geprüft wird: Systemkontext, Datenliefervertrag, Migrationszugangsroutine,
Controlling, aktuarielle Abnahme, Klärungsprozess und Archiv. Es verweist
auf die Grundsatzdokumentation, nie umgekehrt.

## Vorlage hier, Instanz im Fall

Dieses Verzeichnis enthält die Vorlage. Die ausgefüllte Fassung eines
Falls gehört in seinen Arbeitsbereich (`faelle/<fall>/`, nicht
eingecheckt, ADR-002), denn sie enthält Angaben zu Mandant, Quellsystem
und Lieferung, die nicht in ein öffentliches Repository gehören. Hier steht
nur, was über alle Fälle gleich bleibt.

Die Vorlage ist [vorlage.md](vorlage.md), ein Dokument mit elf Kapiteln,
das je Fall kopiert und ausgefüllt wird.

| Kapitel | Inhalt | Stand |
|---|---|---|
| 1-4 | Zweck, Systemkontext, Bestandsabgrenzung, Datenliefervertrag | Gerüst mit ⟨TODO⟩ — fallspezifisch auszufüllen |
| 5 | Migrationszugangsroutine (Statusmodell, Schrittfolge je Vertrag, Kohorten, Protokoll) | fachlich vorbefüllt; Änderungen nur nach menschlicher Freigabe |
| 6 | Migrationscontrolling am $t_0$ über den vollen Bestand, Vorlage für Gate A-M4 | ausgearbeitet |
| 7 | Aktuarielle Abnahme am $t_a$ je Vertrag auf einer Stichprobe, Vorlage für Gate A-M1 | ausgearbeitet |
| 8-10 | Fehler- und Klärungsprozess, Archiv, Ablaufplanung | Gerüst mit ⟨TODO⟩ |
| 11 | Entscheidungen und offene Punkte | zwei Entscheidungen mit festgelegtem Standard (E1, E2); eine Abweichung wird je Bestand begründet |

Zwei Markierungen steuern die Weiterarbeit: **⟨TODO: …⟩** ist noch zu
erarbeitender Inhalt; **⟨ENTSCHEIDUNG: …⟩** ist eine offene Entscheidung
eines Menschen. Sie wird nicht von dem aufgelöst, der die Vorlage
ausfüllt, sondern in Kapitel 11 geführt und vorgelegt. Die
Bearbeitungshinweise am Kopf der Vorlage gelten.

Ausgearbeitet sind die Kapitel, deren Werkzeuge gebaut sind (ADR-010);
die übrigen tragen die Struktur und ihre Platzhalter.

## Was hier nicht steht

Ein Verfahren, das an zwei Stellen beschrieben ist, läuft auseinander.
Deshalb hat jede Art von Aussage genau einen Ort:

| Aussage | Ort | Hier stattdessen |
|---|---|---|
| Mathematik der Methode, Invarianten, Toleranzphilosophie | [Grundsatzdokumentation](../mathematik/grundsatzdokumentation.md), Tarifpläne | Verweis auf Kapitelnummer |
| Warum das System so gebaut ist (Alternativen, Konsequenzen) | ADRs unter [../architektur/](../architektur/) | Verweis auf ADR-Nummer |
| Kommandozeilen, Flags, Reihenfolge der Handgriffe | Agenten-Skills unter `.claude/skills/`, Einstieg in `ONBOARDING.md` | Verweis auf den Skill-Namen |
| Was ein Modul rechnet und welche Fälle es hart ablehnt | Modul-Docstrings im Code | Verweis auf das Modul |

Nur hier steht das Verfahren aus Sicht des Projekts: welche Prüfebene
wann läuft, welche Artefakte dabei entstehen, wer was entscheidet, was ein
Befund für den Fortgang bedeutet und welche Nachweise am Ende die Abnahme
tragen. Diese Sicht brauchen ein Prüfer, ein Verantwortlicher Aktuar oder
eine Revision, und keines der anderen Dokumente bietet sie.
