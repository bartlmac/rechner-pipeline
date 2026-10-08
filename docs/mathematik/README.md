# Mathematik

Hier liegt die Rechenmethode der PLV: was der Rechenkern rechnet und warum,
unabhängig von einem einzelnen Migrationsfall und von der technischen
Umsetzung.

| Dokument | Inhalt |
|---|---|
| [Grundsatzdokumentation](grundsatzdokumentation.md) | Mathematik und Numerik des Rechenkerns für alle Produkte: Zustandsraum, Thiele-Rekursion, Rechnungsgrundlagen, Numerik; in Abschnitt 9 der Migrationszugang mit Korrekturschicht |

## Einordnung

Die Fachdokumentation hat zwei Stufen:

1. **Grundsatzdokumentation** (hier): die normative Mathematik. Die
   Implementierung folgt ihr, nicht umgekehrt.
2. **Tarifpläne** ([docs/tarifplaene/](../tarifplaene/README.md)): je
   Tarif die konkrete Belegung aller produktabhängigen Festlegungen. Für
   ein migriertes Produkt mit Korrekturschicht gehört dazu ein Abschnitt zur
   Ausgestaltung (Grundsatzdokumentation, Abschnitt 10 Nr. 9).

Daneben steht das [Migrationskonzept](../migrationskonzept/README.md), das
je Bestand und Quellsystem ausgefüllt wird. Es verweist auf die
Grundsatzdokumentation, nie umgekehrt.

Die Methode des Migrationszugangs geht auf das Fachkonzept „Konstruktive
Neuberechnung und Korrekturschicht“ (v0.2) zurück. Sie ist vollständig in
Abschnitt 9 der Grundsatzdokumentation und in die Vorlage des
Migrationskonzepts aufgenommen.

## Änderungen

Grundsatzdokumentation und Tarifpläne sind abgenommen: Fall 3 hat sie
zusammen mit dem Rechenkern (`A-K2`) und dem Tarifwerk (`A-T1`) über
Prüfsummen gebunden. Eine Änderung braucht deshalb eine neue Abnahme und
die Zustimmung des Aktuariats (Grundsatzdokumentation, Abschnitt 13).
Abweichungen zwischen Konzept und Umsetzung werden entschieden und im
Abweichungsverzeichnis geführt (Abschnitt 12).
