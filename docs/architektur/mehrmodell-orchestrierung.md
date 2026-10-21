# Optionale Orchestrierung und Modellvergleiche mit Herdr

Dieses Dokument beschreibt, wie Herdr die interaktiven Agentenprozesse eines Laufs koordinieren kann, auch beim Einsatz von Open-Weight-Modellen. Zusätzlich wurde Herdr genutzt, um Modelle und Agenten-Harnesses an denselben Arbeitspaketen zu vergleichen. Beide Nutzungen sind optional: Die Agenten lassen sich auch einzeln über ihre Oberflächen oder normale Shell-Kommandos beauftragen. Die Migrations-Pipeline bleibt über lokale Dateien und Shell-Kommandos ausführbar.

## Zweck und Einordnung

Bei der Orchestrierung eines Laufs koordiniert die Programmleitung die Bearbeitung und Übergabe von Arbeitspaketen zwischen den Agentenrollen. Ein zusätzlicher Vergleich von Modellen und Harnesses soll sichtbar machen, welche Kombination einen fachlich oder technisch belastbaren Beitrag zum jeweiligen Arbeitspaket liefert.

Die vier Rollen des KI-Tools aus [ADR-018](adr-018-rollenmodell-und-schluesselklassen.md) beschreiben Verantwortlichkeiten (`agent/programmleitung`, `agent/aktuariat`, `agent/architektur`, `agent/rechenkern`). Codex, OpenCode, Claude Code und Pi sind Beispiele für Agenten-Harnesses: Sie nehmen Aufträge entgegen, verwalten den Arbeitskontext und binden ein Modell an. Ein Modell kann eine Rolle in einem konkreten Auftrag ausüben. Wird Herdr eingesetzt, startet und beobachtet es die Harness-Prozesse, übergibt ihnen Text und zeigt ihre Antworten.

## Zuständigkeiten und bewusste Grenzen

Herdr übernimmt die Prozesskoordination; Merge, Coverage, Bewertung, Transformation und Gate-Entscheidung gehören nicht zu seinen Aufgaben. Die Produktbezeichnung eines Modells verleiht ihm keine fachliche oder zeichnende Befugnis. Modellantworten werden an Quellen, Fallstand und deterministischen Werkzeugen geprüft; auch übereinstimmende Antworten ersetzen diesen Beleg nicht. Widersprüche zwischen Quellen und jede Annahmeentscheidung bleiben bei der zuständigen menschlichen Rolle. Ein positives Modellurteil ersetzt weder die Quellenabnahme A-Q1 noch spätere Abnahmen.

## Anbindung lokaler und offener Modelle

Die Modellwahl findet im jeweiligen Harness statt: Pi, OpenCode, Codex oder Claude Code wird mit seinem konfigurierten Modell und gegebenenfalls einem lokalen Inferenzdienst gestartet. Bei Nutzung von Herdr verwaltet es den Terminalprozess und die Übergabe des Arbeitspakets, nicht die Modellgewichte oder den Inferenzdienst. So lassen sich die Agentenrollen eines Laufs mit Open-Weight-Modellen besetzen und über Herdr koordinieren. Ein lokal betriebenes Open-Weight-Modell kann dabei ebenso Arbeitspakete bearbeiten wie ein über einen Anbieter erreichbares Modell.

## Orchestrierung eines Laufs

Die Programmleitung legt je Arbeitspaket die ausführende Agentenrolle, den Eingangsstand, die zugelassenen Quellen, das erwartete Ergebnis und die Schreibgrenzen fest. Die zugehörigen Harness-Prozesse werden über Herdr gestartet und mit den Aufträgen versorgt. Die Programmleitung prüft die Ergebnisse anhand der vorgesehenen deterministischen Belege und übergibt den belegten Stand an die nächste Rolle. Dabei können die Rollen dasselbe oder unterschiedliche Modelle nutzen.

Die Arbeitspakete folgen den Zuständigkeiten und Übergaben des Migrationsverfahrens. Ein Vergleichslauf kann dieses Vorgehen ergänzen, indem mehrere Modell-Harness-Kombinationen unabhängig dasselbe Arbeitspaket bearbeiten.

## Möglicher Ablauf eines Vergleichs

1. Die Programmleitung grenzt ein Arbeitspaket ab: Fall und Eingangsstand, Ziel, zugelassene Vorverdichtungen und Dossiers, erwartetes Ausgabeformat, Schreibgrenzen und offene menschliche Entscheidungen.
2. Jeder vorgesehene Agent erhält **denselben Auftrag**. Im Vergleichsverfahren bekommt jede untersuchte Modell-Harness-Kombination jedes Arbeitspaket. Harness und Version, Modellkennung, Anbieter oder lokaler Endpunkt und relevante Denk-/Laufparameter werden je Lauf festgehalten, damit die Ergebnisse zugeordnet werden können.
3. Die Agenten arbeiten unabhängig. Für eine lesende Prüfung können sie getrennte Herdr-Panes oder einzeln gestartete Prozesse auf demselben Fallstand nutzen. Wenn ein Arbeitspaket Dateien ändert, braucht jeder Kandidat einen eigenen Arbeitsbereich oder Worktree; gemeinsame, gleichzeitige Änderungen am selben Fall würden die Zuordnung der Ergebnisse zerstören.
4. Die Programmleitung sichert jede vollständige Antwort im Fallprotokoll.
5. Die Programmleitung verifiziert Aussagen und Vorschläge gegen die registrierten Quellen, Fundstellen, Schemata, vorhandenen Kommandos und deterministischen Belege. Sie dokumentiert je Paket Vergleich, konkrete Korrekturen und eine auf diesen Lauf bezogene Bewertung der Modell-Harness-Kombination. Der übernommene Befund erhält einen eigenen Belegweg; Modellantworten werden nicht direkt in A-Box, Transformations-Spec oder Gate-Snapshot kopiert.
6. Fachliche Konflikte gehen an die zuständige menschliche Rolle.

## Nachweis im Fall

Die Arbeitsdateien eines Vergleichs liegen unter `faelle/<fall>/abgeleitet/protokoll/<vergleich>/`. Ein Paket hat genau einen `auftrag.md`; je untersuchter Modell-Harness-Kombination gibt es eine gesicherte Antwort und bei Bedarf eine gekennzeichnete Fortsetzung; `auswertung.md` nennt den geprüften Fallstand, die eingesetzten Modelle und Harnesses, den Beleg für jede Bewertung und den übernommenen beziehungsweise verworfenen Vorschlag.

Eine Bewertung misst die Antwort **auf dieses Arbeitspaket** und begründet keine allgemeine Rangliste von Modellen oder Harnesses. Besonders wichtig sind vollständige Fundstellen, erkennbare Unsicherheit, Einhaltung der Schreibgrenzen, technisch ausführbare Folgeschritte und die Trennung von Lieferantenaussage und menschlicher Entscheidung. Der Vergleich hält auch fest, wenn ein Agent einen nicht vorhandenen Befehl, eine unbelegte Normalisierung oder einen unzulässigen Gate-Schritt vorschlägt.

## Herdr-Sitzungen und Plattformen

Herdr ist für [Linux, macOS und Windows](https://herdr.dev/docs/install/) verfügbar. Die Sitzung läuft in einem Hintergrundserver: Wird das Herdr-Fenster geschlossen oder der Client getrennt, bleiben die Sitzung und die darin laufenden Agentenprozesse aktiv. Das gilt für das Trennen des Clients; nach einem ausdrücklichen Server-Stopp laufen die Prozesse nicht weiter. Der Unterschied ist in der [Herdr-Dokumentation zum Sitzungszustand](https://herdr.dev/docs/session-state/) beschrieben.
