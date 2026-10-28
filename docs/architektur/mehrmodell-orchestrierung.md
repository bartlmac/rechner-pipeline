# Optionale Orchestrierung mit Herdr

Dieses Dokument beschreibt, wie Herdr die interaktiven Agentenprozesse eines
Laufs koordinieren kann, auch beim Einsatz von Open-Weight-Modellen. Die
Nutzung ist optional: Die Agentenrollen können auch ohne Herdr über den
jeweiligen Harness beauftragt werden. Die Migrations-Pipeline bleibt über
lokale Dateien und Shell-Kommandos ausführbar.

## Zweck und Einordnung

Bei der Orchestrierung eines Laufs koordiniert die Programmleitung die
Bearbeitung und Übergabe von Arbeitspaketen zwischen den Agentenrollen. Die
fünf Rollen des KI-Tools aus [ADR-018](adr-018-rollenmodell-und-schluesselklassen.md)
beschreiben die Verantwortlichkeiten
(`agent/programmleitung`, `agent/aktuariat`, `agent/architektur`,
`agent/rechenkern`, `agent/betrieb`). Die Programmleitung koordiniert die vier
anderen Rollen; der Betriebs-Agent bereitet A-B1 bis A-B3 vor.

Codex, OpenCode, Claude Code und Pi sind Beispiele für Agenten-Harnesses: Sie
stellen die Bedien- und Prozessschnittstelle bereit, nehmen Aufträge entgegen,
verwalten den Arbeitskontext und binden ein Modell an. Ein Modell kann eine
Rolle in einem konkreten Auftrag ausüben. Wird Herdr eingesetzt, startet und
beobachtet es die Harness-Prozesse und übergibt ihnen Text.

## Orchestrierung eines Laufs

Die Programmleitung legt je Arbeitspaket die ausführende Agentenrolle, den
Eingangsstand, die zugelassenen Quellen, das erwartete Ergebnis und die
Schreibgrenzen fest. Wird Herdr eingesetzt, startet die Programmleitung die
zugehörigen Harness-Prozesse darüber und versorgt sie mit den Aufträgen. Die
Rollen übergeben sich ihre Ergebnisse nach dem vorgesehenen Verfahren. Die
Programmleitung prüft die Ergebnisse anhand der vorgesehenen deterministischen
Belege und hält an menschlichen Entscheidungspunkten an.

Die Modellwahl findet im jeweiligen Harness statt: Pi, OpenCode, Codex oder
Claude Code wird mit seinem konfigurierten Modell und gegebenenfalls einem
lokalen Inferenzdienst gestartet. Bei Nutzung von Herdr verwaltet es den
Terminalprozess und die Übergabe des Arbeitspakets, nicht die Modellgewichte
oder den Inferenzdienst. So lassen sich die Agentenrollen eines Laufs mit
Open-Weight-Modellen besetzen und über Herdr koordinieren.

## Zuständigkeiten und bewusste Grenzen

Herdr übernimmt die Prozesskoordination; Bewertung, Transformation und
Gate-Entscheidung gehören nicht zu seinen Aufgaben. Modellantworten werden an
Quellen, Fallstand und deterministischen Werkzeugen geprüft. Widersprüche
zwischen Quellen und jede Annahmeentscheidung bleiben bei der zuständigen
menschlichen Rolle. Ein positives Modellurteil ersetzt weder die
Quellenabnahme A-Q1 noch spätere Abnahmen.

Herdr ist kein Bestandteil des Python-Pakets und entscheidet weder über
Quellenwidersprüche noch über ein Gate. Die Basis bleibt die Ausführung über
lokale Dateien und Shell-Kommandos.

## Herdr-Sitzungen und Plattformen

Herdr ist für [Linux, macOS und Windows](https://herdr.dev/docs/install/)
verfügbar. Die Sitzung läuft in einem Hintergrundserver: Wird das
Herdr-Fenster geschlossen oder der Client getrennt, bleiben die Sitzung und
die darin laufenden Agentenprozesse aktiv. Das gilt für das Trennen des
Clients; nach einem ausdrücklichen Server-Stopp laufen die Prozesse nicht
weiter. Der Unterschied ist in der [Herdr-Dokumentation zum
Sitzungszustand](https://herdr.dev/docs/session-state/) beschrieben.
