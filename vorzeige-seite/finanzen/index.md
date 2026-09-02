<link rel="stylesheet" href="../assets/stil.css">
<div class="banderole">Fiktives Unternehmen — eine Vorführung agentischer
Bestandsmigration. <a href="../">Zur Startseite.</a></div>

# Finanzen

Was eine Übernahme in den Büchern bedeutet: die gelieferten Größen der
abgebenden Gesellschaft, die eigene Nachrechnung — und die Überleitung
zwischen beiden, Vertrag für Vertrag.

## Die Übernahme Baldrian in Zahlen

| | |
|---|---:|
| Übernommenes Deckungskapital (01.01.2026) | 22.488.836,41 € |
| Laufender Jahresbeitrag | 1.874.990,97 € |
| Verträge | 500 |

Die Beträge sind **gelieferte** Größen aus dem registrierten
Bestandsabzug — sie stehen nicht im geführten Stamm, dort wären sie
eine eigene Rechnung und kein Bestandteil der Lieferung. Jede Zahl ist
über den [Abnahmebericht](../migrationen/baldrian/) und die dort
abgelegten Artefakte nachrechenbar.

## Überleitung und Nachweisung

Das Migrationscontrolling rechnet den ganzen Bestand über zwei
Stichtage nach und legt die Ergebnisse als Artefakt ab
([migrationssuite.json](../migrationen/baldrian/artefakte/abgeleitet/berichte/migrationssuite.json)).
In den eigenen Büchern beginnt jeder übernommene Vertrag am
**Zugang**, nicht an seinem historischen Vertragsbeginn — was die
abgebende Gesellschaft gebucht hat, steht in ihrem Journal; die
Vorgeschichte trägt die Bewertung, ist aber keine eigene Bewegung
([ADR-014](../it/architektur/adr-014-bestandszugang-getrennt-vom-vertragsbeginn.html),
[ADR-015](../it/architektur/adr-015-uebernommenen-bestand-fortschreiben.html)).

*In Vorbereitung:* die fortgeschriebene Sicht des Gesamtbestands mit
Deckungskapital-Verlauf bis zum Ablauf und der Nachweisung der
Bewegungen je Berichtsjahr.
