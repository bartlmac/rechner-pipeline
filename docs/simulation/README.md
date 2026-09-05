# Simulation — wie die Vorzeigebestände entstehen

Das System braucht Bestände, an denen es sich zeigen kann: den
geführten Zielbestand der Pfefferminzia und die Quellbestände der
fiktiven abgebenden Unternehmen. Beide sind **simuliert**. Diese Doku
beschreibt, wie.

Das ist bewusst von der Fachdokumentation getrennt. Die
[Grundsatzdokumentation](../mathematik/grundsatzdokumentation.md) und
die [Tarifpläne](../tarifplaene/) beschreiben, wie ein
Versicherungsunternehmen **bewertet** — Rechnungsgrundlagen erster
Ordnung, prospektive Reserven, Migrationszugang. Wie ein Bestand über
die Zeit **entsteht und sich entwickelt**, ist dagegen eine Eigenschaft
des Simulationswerkzeugs: In einem echten Unternehmen tut das die
Wirklichkeit, nicht ein Modell.

Diese Trennung ist nicht verhandelbar: Eine Simulationsannahme darf nie
in die Bewertung zurückwirken.

| Dokument | Inhalt |
|---|---|
| [erfahrungsannahmen.md](erfahrungsannahmen.md) | Wie die Simulation ihre Ereigniswahrscheinlichkeiten bildet: dritte Ordnung als Transformation der ersten |
| [tagesbetrieb.md](tagesbetrieb.md) | Fachkonzept: die PLV als laufendes Unternehmen — tägliches Neugeschäft, Buchungstag und Wirkungstag, nächtlicher Lauf, Monatsabschluss, Laufzeitumgebung |

## Die Werkzeuge

| Werkzeug | Erzeugt |
|---|---|
| `bestand.generator` + `bestand.ereignisse` | den Zielbestand der Pfefferminzia: Modellpunkte je Generation, dann ein Strom datierter Geschäftsvorfälle |
| `simulation/` (nicht eingecheckt) | die Lieferungen der fiktiven abgebenden Unternehmen |
| geplant (Konzept: [tagesbetrieb.md](tagesbetrieb.md)) | tägliche Fortschreibung — der Punkt, ab dem das Unternehmen zu leben beginnt |

Jeder Betrag kommt auch in der Simulation aus dem Rechenkern; das
Simulationswerkzeug rechnet nichts Aktuarielles selbst. Es entscheidet
nur, **wann** etwas passiert.
