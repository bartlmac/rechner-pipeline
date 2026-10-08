# Rechenkern und Tarifwerk

Jeder Betrag in unseren Büchern kommt aus einem Rechenkern, und jeder
Vertrag wird nach einem dokumentierten Tarifplan bewertet. Die Arbeit am
Rechenkern ist ein Zusammenspiel von Aktuariat und Rechenkernentwicklung.
Sie erfolgt nach Dokumentation und in fachlicher Rollentrennung: Das
Aktuariat verantwortet, was gerechnet wird, die Rechenkernentwicklung, wie
es gerechnet wird. In beiden Rollen unterstützt KI die Menschen.

## Was der Kern rechnet {#rechenkern}

Der Kern bewertet mehrere Tarifgenerationen nebeneinander, übernommene
Tarifwerke eingeschlossen. Eine Übernahme bringt kein zweites System
mit: Das fremde Tarifwerk wird als weitere Generation im selben Kern
parametriert, und danach rechnet dieselbe Maschine für eigene und
übernommene Verträge.

Die Bewertung folgt der Thiele-Rekursion. Sie ist deterministisch —
gleiche Eingaben ergeben gleiche Ergebnisse, auf den Cent. Jede
produktive Änderung am Kern muss eine Suite von Charakterisierungstests
mit eingefrorenen Referenzwerten unverändert bestehen; ändert sich ein
Wert, ist das ein Befund und keine Anpassung.

## Tarifwerk {#tarifwerk}

Die Bewertung jedes Vertrags folgt einem dokumentierten Tarifplan mit
Zustandsmodell, Rechnungsgrundlagen und den Formeln des Rechenkerns.
Geführt werden die kapitalbildende Lebensversicherung in mehreren
Generationen (darunter die Tarifgeneration 2015 aus der Übernahme
Baldrian) und die Berufsunfähigkeitsversicherung.

* [Tarifpläne](tarifplaene/) — je Generation Zustandsmodell,
  Rechnungsgrundlagen und Formeln.
* [Grundsatzdokumentation](mathematik/grundsatzdokumentation.html) —
  Zustandsraum, Thiele-Rekursion, Rechnungsgrundlagen, Numerik.

## Was der Kern für den Bestand leistet {#im-bestand}

Die Zahlen, die der Kern für den geführten Bestand rechnet, stehen unter
[Bestandsführung](../geschaeftsentwicklung/): der Bestand am Stichtag und
die [Monatsberichte](../geschaeftsentwicklung/#monatsberichte).

Wie der Kern eine Übernahme nachrechnet und wer sie abnimmt, steht unter
[Bestandsmigrationen](../migrationen/#abnahmen). Die Bestandsberichte zur
Übernahme Baldrian:
[nach der Übernahme, Stichtag 01.01.2026](../migrationen/baldrian/artefakte/abgeleitet/berichte/bestandsbericht-nach.html)
und [der gelieferte Bestand zum Vergleich](../migrationen/baldrian/artefakte/abgeleitet/berichte/bestandsbericht-vor.html).
