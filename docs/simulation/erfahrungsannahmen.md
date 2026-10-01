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
  Erhöhung, Beitragsherabsetzung, Teilkündigung. Dort ist $a$ die Rate
  selbst.

# 3 Wo die Werte stehen

Je Bestand in der Konfiguration unter `[annahmen]`, eine Zeile je
Ereignisart mit ihren beiden Parametern. Die Konfiguration ist
Bestandteil des Laufs: Derselbe Startwert und dieselbe Konfiguration
ergeben denselben Bestand, Vorfall für Vorfall.

# 4 Beitragsherabsetzung und Teilkündigung

Zwei Vorgänge des Tarifplans KLV (Abschnitte 7.1 und 7.2), die ein
gewachsener Bestand immer trägt und die eine Migration deshalb immer
antrifft: Kunden senken ihren Beitrag, und Kunden kündigen einen Teil
ihrer Versicherung und lassen sich ihn auszahlen. Ein Vorzeigebestand
ohne sie wirkt künstlich. Die Konfigurationen der Kapitalversicherung
der PLV (`bestand_klv.toml`, `bestand_gesamt.toml`) führen deshalb für
beide eine Annahme, für alle Tarifgenerationen gleich:

| Annahme | Wert | Bedeutung |
|---|---|---|
| `herabsetzung` | $a = 0{,}008$, $b = 0$ | 0,8 % je Jahr eines beitragspflichtigen Vertrags senken den Beitrag |
| `red_anteil` | $0{,}6$ | der **fortgeführte** Beitragsanteil: Beitrag auf 60 % gesenkt; der freiwerdende Teil wird beitragsfreie Summe, es fließt kein Geld |
| `teilkuendigung` | $a = 0{,}005$, $b = 0$ | 0,5 % je Jahr eines Vertrags kündigen einen Teil der Versicherung |
| `tk_anteil` | $0{,}7$ | der **fortgeführte** Summenanteil der Grundversicherung: 30 % gekündigt und mit dem Rückkaufswert ausgezahlt |

Beide Anteile nennen, was **bleibt**, nicht was wegfällt — 30 %
gekündigt ist `tk_anteil = 0.7`. Ein Anteil von 0 heißt „nicht
konfiguriert“; eine Rate über null ohne Anteil weist die Konfiguration
ab.

Gezogen wird je Vertrag und Vertragsjahr aus je einem eigenen
Zufallsstrom, nach den Grenzen des Tarifplans: die Herabsetzung nur,
solange ein Beitrag gezahlt wird, die Teilkündigung bis zum Ablauf,
beide nicht nach einer Beitragsfreistellung und höchstens ein Vorgang
je Vertrag. Weil die Ströme eigene sind, verschiebt die neue Annahme
keinen anderen Vorfall: Ein Vertrag ohne Herabsetzung und ohne
Teilkündigung bleibt Vorfall für Vorfall derselbe, und an einem
betroffenen Vertrag ändern sich nur die Beträge späterer Vorfälle, die
von der Summe abhängen (Erhöhung, Storno, Tod, Ablauf).

Was die Werte ergeben, gemessen am Bestand der PLV bis zum 1. Oktober
2026 (3.333 Verträge seit 1994): 168 Herabsetzungen und 107
Teilkündigungen, davon 9 nach dem Beitragsende; seit 1997 trägt jedes
Kalenderjahr beide Vorgänge. Bezogen auf die Verträge am Jahresanfang
sind das rund 0,7 % der beitragspflichtigen beziehungsweise 0,4 % aller
Verträge — unter den Raten, weil beitragsfrei gestellte und schon
herabgesetzte Verträge nicht mehr ziehen.

Die übernommene Generation TG2015 kennt nach ihrem Bedingungswerk keine
Herabsetzung ohne Auszahlung; sie führt den Herabsetzungswunsch als
Teilkündigung aus, mit `red_anteil` (Tarifplan KLV 7.2, Annahme A1).
Vor dem Beitragsende hat sie damit zwei Wege in eine Teilkündigung, und
ihre Teilkündigungen sind entsprechend häufiger als in den eigenen
Generationen. Die Berufsunfähigkeitsversicherung kennt keinen der beiden
Vorgänge; ihre Konfiguration führt keine Rate.

Beide Annahmen sind Annahmen der **Vorführung**, keine Tarifgrößen und
keine Schätzung realer Erfahrung: Sie stehen da, damit der Bestand die
Vorgänge enthält, die eine Migration antrifft. Eine Änderung gilt vom
Beginn der Simulation an — für eine laufende Ablage des Tagesbetriebs
heißt das: neu aufsetzen ([Tagesbetrieb](tagesbetrieb.md), Abschnitt 8).

# 5 Was daraus NICHT folgt

Beiträge und Reserven bleiben von den Erfahrungsannahmen unberührt.
Wenn die Simulation einen Vertrag stornieren lässt, rechnet der
Rechenkern den Rückkaufswert auf **erster** Ordnung — die
Simulationsannahme hat nur bestimmt, dass storniert wird, nicht mit
welchem Betrag.

Ebenso wenig sind diese Annahmen eine Aussage über echte Bestände. Sie
sind so gewählt, dass ein Vorzeigebestand plausibel aussieht, nicht als
Schätzung realer Erfahrung.
