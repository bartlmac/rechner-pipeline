---
title: "Erfahrungsannahmen der Bestandssimulation"
lang: de
format:
  typst:
    papersize: a4
---

> Wie das Simulationswerkzeug entscheidet, **wann** einem Vertrag etwas
> zustößt. Das ist keine Bewertungsmathematik: Die Bewertung rechnet auf
> Rechnungsgrundlagen erster Ordnung
> ([Grundsatzdokumentation](../mathematik/grundsatzdokumentation.md),
> Abschnitt 5) und weiß von diesen Annahmen nichts.

# 1 Warum es sie gibt

Ein simulierter Bestand muss sich entwickeln: Verträge stornieren,
Menschen sterben, Beiträge werden freigestellt, Erhöhungen laufen. In
einem echten Unternehmen entscheidet das die Wirklichkeit; im
Vorzeigebestand entscheidet es ein Modell. Dieses Modell heißt hier
**Erfahrungsannahme** und arbeitet auf Rechnungsgrundlagen **dritter
Ordnung** — den Werten, die man erwartet, nicht den vorsichtigen
Werten, mit denen bewertet wird.

# 2 Die Transformation

Jede Ereigniswahrscheinlichkeit der Simulation entsteht als geklemmte
affine Transformation des Wertes erster Ordnung:

$$\text{Annahme} \;=\; \min(1,\; \max(0,\; a + b \cdot q)),
\qquad q = \text{Wert erster Ordnung}$$

Die Klemmung auf $[0, 1]$ gehört zur Definition — ohne sie wäre die
Transformation keine Wahrscheinlichkeitsabbildung.

Zur Belegung der beiden Parameter:

* $b < 1$ dämpft eine belastende, $b > 1$ verstärkt eine entlastende
  Ausscheideursache; $b = 1$ übernimmt die erste Ordnung unverändert.
  Der Grund ist die Vorsicht der ersten Ordnung: Sie ist bei
  belastenden Ursachen bewusst zu hoch und bei entlastenden bewusst zu
  niedrig angesetzt, die Erfahrung liegt jeweils dazwischen.
* $b = 0$ ist der Fall für Ereignisse, für die es **keine**
  Rechnungsgrundlage gibt — Storno, Beitragsfreistellung, dynamische
  Erhöhung. Dort ist $a$ die Rate selbst.

# 3 Wo die Werte stehen

Je Bestand in der Konfiguration unter `[annahmen]`, eine Zeile je
Ereignisart mit ihren beiden Parametern. Die Konfiguration ist
Bestandteil des Laufs: Derselbe Startwert und dieselbe Konfiguration
ergeben denselben Bestand, Vorfall für Vorfall.

# 4 Was daraus NICHT folgt

Beiträge und Reserven bleiben von den Erfahrungsannahmen unberührt.
Wenn die Simulation einen Vertrag stornieren lässt, rechnet der
Rechenkern den Rückkaufswert auf **erster** Ordnung — die
Simulationsannahme hat nur bestimmt, dass storniert wird, nicht mit
welchem Betrag.

Ebenso wenig sind diese Annahmen eine Aussage über echte Bestände. Sie
sind so gewählt, dass ein Vorzeigebestand plausibel aussieht, nicht als
Schätzung realer Erfahrung.
