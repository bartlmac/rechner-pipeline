---
title: "Grundsatzdokumentation — Mathematik und Numerik des Zielrechenkerns"
lang: de
format:
  typst:
    papersize: a4
---

> **Die Mathematik und Numerik, der die Umsetzung folgt.** Sie gilt für
> **alle** Produkte des Zielrechenkerns; was ein einzelnes Produkt
> ausmacht, steht in seinem Tarifplan (`docs/tarifplaene/`) — und dort
> auch nur dort. Der Migrationszugang samt Korrekturschicht steht in
> Abschnitt 9.
>
> **Zur Reihenfolge, ehrlich:** Der Rechenkern existierte vor diesem
> Dokument. Was hier steht, kodifiziert die geltenden Konventionen des
> Kerns; ab dieser Fassung ist es normativ. Abweichungen der
> Implementierung sind ab hier unzulässig und laufen über den
> Änderungsprozess (Abschnitt 13), dokumentiert im
> Abweichungsverzeichnis (Abschnitt 12).
>
> **Herkunft:** Die Methode des Migrationszugangs (Abschnitt 9) geht auf
> das Fachkonzept „Konstruktive Neuberechnung und Korrekturschicht"
> v0.2 zurück und ist hier vollständig aufgenommen.

# 1 Zweck und Geltung

Dieses Dokument beschreibt das gemeinsame Rückgrat: den Zustandsraum,
die Bewertungsgleichung, die Rechnungsgrundlagen-Schicht, die
numerischen Konventionen und das Verhältnis der Bewertungsschichten
zueinander. Es ist die einzige Quelle für diese Aussagen — kein
Tarifplan wiederholt sie.

Die Abgrenzung nach oben und unten:

| Dokument | Gegenstand |
|---|---|
| **Grundsatzdokumentation (dieses Dokument)** | Mathematik und Numerik, verbindlich für die Implementierung; produktübergreifend — einschließlich Migrationszugang und Korrekturschicht (Abschnitt 9) |
| Tarifpläne (`docs/tarifplaene/*.md`) | die Ausgestaltung je Produkt: Zustandsraum des Tarifs, Leistungen, Rechnungsgrundlagen, Stellschrauben — bei migrierten Produkten zusätzlich die Parameter der Korrekturmathematik |

# 2 Notation

| Symbol | Bedeutung |
|---|---|
| $s, s'$ | Zustände des Modells |
| $j$ | Vertragsjahr, $j = 0$ ist das erste Jahr |
| $x_0$ | Eintrittsalter (technisches Alter beim Vertragsbeginn) |
| $d$ | Verweildauer im aktuellen Zustand in vollen Jahren |
| $p_{s \to s'}(x, d)$ | Übergangswahrscheinlichkeit im Jahr, in dem Alter $x$ und Verweildauer $d$ erreicht sind |
| $z(s, j)$ | vorschüssige Zahlung im Zustand $s$ zu Beginn des Jahres $j$ |
| $u(s, s', j)$ | nachschüssige Zahlung beim Übergang $s \to s'$ im Jahr $j$ |
| $V_j(s, d)$ | prospektiver Barwert im Zustand $s$ mit Verweildauer $d$ zu Beginn des Jahres $j$ |
| $d_{\max}$ | maximale Verweildauer des Modells (Select-Periode; $0$ = markovsch) |
| $i$ | Rechnungszins, $v = 1/(1+i)$ der jährliche Diskontfaktor |

Für die Korrekturschicht (Abschnitt 9) kommen hinzu:

| Symbol | Bedeutung |
|---|---|
| $t_a$ | Verankerungszeitpunkt — letzter exakter Rechenpunkt des Quellsystems |
| $t_0$ | Migrationsstichtag (Übernahmepunkt) |
| $s_0, d_0$ | Zustand und Verweildauer am Verankerungszeitpunkt |
| $R$ | Residuum: gelieferter minus prospektiver Wert am $t_a$ |
| $R_{\mathrm{hist}}, R_{\mathrm{conv}}$ | Historien- bzw. Konventionsresiduum |
| $V^{\mathrm{korr}}$ | Wert der Korrekturschicht |
| $c_s$ | (fiktive) Zahlungsfunktion der Korrekturschicht im Zustand $s$ |
| $g$, $\rho$ | Formfunktion und ihr Kalibrierungsfaktor, $c_s = \rho\, g$ |
| $\Pi_s(t,d)$ | Barwert des Einheitsstroms $g$ unter der Schicht-Dynamik |
| $F_s$ | Menge der **vererbenden** Übergänge aus dem Zustand $s$ |

Produktspezifische Größen (Beitragsraten, Reservebegriffe,
Rückkaufswerte) tragen ihre Bezeichner im jeweiligen Tarifplan; die
Quellnamen migrierter Größen bleiben dort bewusst erhalten
(Provenienz-Prinzip).

# 3 Zustandsraum und Semi-Markov-Modell

## 3.1 Zustände und Übergänge

Ein Produkt ist durch einen endlichen, eindeutigen Zustandsraum und eine
Übergangsfunktion definiert. Die Übergangsfunktion liefert je Paar
$(s, s')$, Alter und Verweildauer eine Wahrscheinlichkeit; sie ist die
einzige Stelle, an der Rechnungsgrundlagen in die Bewertung eingehen.

## 3.2 Residuum-Regel und Wegzugs-Gate

Der **Verbleib im Zustand ist stets das Residuum** der Wegzüge und wird
nie eigenständig tabelliert:

$$p_{s \to s}(x, d) \;=\; 1 - \sum_{s' \neq s} p_{s \to s'}(x, d)$$

Daraus folgen zwei harte Regeln der Rechenschicht:

* Eine negative Übergangswahrscheinlichkeit ist ein Fehler und bricht
  die Rechnung ab.
* Die **Summe der Wegzüge je Zustand muss $\le 1$ sein**; andernfalls
  bricht die Rechnung ab (fail-fast). Innerhalb eines
  Float-Epsilon-Fensters von $10^{-12}$ oberhalb von $1$ wird
  renormiert statt eine Gesamtmasse über eins zu akzeptieren — jenseits
  davon ist die Rechnungsgrundlage falsch, nicht die Numerik.

## 3.3 Verweildauer und Select-Kappung

Semi-Markov-Verhalten entsteht durch **Zustandsraum-Erweiterung**, nicht
durch eine zweite Uhr: Die Verweildauer $d$ zählt volle Jahre im
aktuellen Zustand, wird beim Zustandswechsel auf null gesetzt und beim
Verbleib um eins erhöht — gekappt auf die maximale Dauer des Modells
($d \le d_{\max}$). Die Kappung bildet die Select-Periode der
Rechnungsgrundlagen ab: Jenseits davon sind die Tafeln nach Alter
aggregiert.

Ein Startzustand außerhalb des Zustandsraums oder eine Startdauer
außerhalb $[0, d_{\max}]$ ist ein Aufruffehler und bricht ab. Ein
Produkt ohne Dauerabhängigkeit setzt $d_{\max} = 0$ und ist damit
markovsch.

# 4 Bewertung: Thiele-Rückwärtsrekursion

## 4.1 Die Rekursion

Alle Produkte des Kerns bewerten auf demselben Rückgrat. Bewertet wird
auf dem **erweiterten Zustand** $(s, d)$ — Zustand und Verweildauer
zusammen (3.3). Der Barwert zu Beginn des Jahres $j$ folgt der
Rückwärtsrekursion

$$
V_j(s, d) \;=\; z(s, j) \;+\; v \cdot [
\sum_{s' \neq s} p_{s \to s'}(x_0 + j,\, d)
\cdot ( u(s, s', j) + V_{j+1}(s', 0) )
\;+\; p_{s \to s}(x_0 + j,\, d) \cdot V_{j+1}(s,\, d^{+})
],
$$

mit $v = \tfrac{1}{1+i}$, der fortgeschriebenen Verweildauer
$d^{+} = \min(d + 1,\; d_{\max})$ und der Terminalbedingung
$V_n(s, d) = 0$ für alle Zustände und Dauern am Ende des
Bewertungshorizonts $n$.

Zwei Eigenschaften der Gleichung sind bindend und nicht bloß
Darstellung:

* **Die Verweildauer wird beim Zustandswechsel auf null gesetzt und
  beim Verbleib fortgeschrieben.** Sie ist Teil des Arguments, nicht
  ein Parameter der Übergangsfunktion allein — sonst ist der Barwert
  eines dauerabhängigen Produkts unterbestimmt.
* **Übergangszahlungen fallen nur beim echten Zustandswechsel an**
  ($s' \neq s$). Eine am Jahresende fällige Zahlung, die den Zustand
  nicht verlässt, ist über das Zahlungsprofil $z$ des Folgejahres
  abzubilden; die Rekursion kennt dafür keinen Term.

Für ein markovsches Produkt ist $d_{\max} = 0$, damit $d = d^{+} = 0$,
und die Gleichung fällt auf die gewohnte Form ohne Dauerargument
zusammen.

## 4.2 Fälligkeitskonventionen

* **Zustandszahlungen $z$ sind vorschüssig** — fällig zu Beginn des
  Jahres, in dem der Zustand besteht.
* **Übergangszahlungen $u$ sind nachschüssig** — fällig am Ende des
  Jahres, in dem der Übergang stattfindet, und nur bei echtem
  Zustandswechsel (4.1).

Diese Konvention gilt für alle Produkte und alle Schichten. Eine
Leistung, die davon abweicht, ist über die Zahlungsprofile abzubilden,
nicht über eine Sonderbehandlung in der Rekursion.

Unterjährige Zahlweisen werden nicht durch ein feineres Gitter
abgebildet, sondern durch ein **Abzugsglied** auf dem Jahresbarwert
(geschlossene Näherung, je Produkt im Tarifplan belegt). Die Rekursion
selbst bleibt jährlich.

## 4.3 Diskontierung

Diskontiert wird mit einem über die Vertragslaufzeit konstanten
Rechnungszins des Modellpunkts. Der Zins ist Parameter der Rechnung,
keine Modulkonstante: Jede Generation bringt ihren eigenen mit.

# 5 Rechnungsgrundlagen

## 5.1 Tafelschicht und Domäne

Rechnungsgrundlagen sind reine Ausscheidewahrscheinlichkeiten je Alter
(und bei Select-Tafeln je Dauer). Sie werden über einen Ladevertrag
bezogen, der das Altersgitter vollständig prüft: Das tabulierte Gitter
läuft von $0$ bis zum höchsten tabulierten Alter $x_{\max} = 123$;
Lücken sind ein Fehler.

Die Auflösung eines Tafelnamens berücksichtigt das Geschlecht des
Modellpunkts. Eine Anfrage jenseits der tabellierten Domäne ist ein
benannter Fehler, kein stiller Nullwert — ein Vertrag, dessen
Bewertungshorizont die Tafel erschöpft, muss als solcher auffallen.

## 5.2 Erste gegen dritte Ordnung

Die **Bewertung** rechnet auf Rechnungsgrundlagen **erster Ordnung**.
Wie sich ein Bestand über die Zeit **entwickelt**, steuern davon
getrennte **Erfahrungsannahmen dritter Ordnung**: Jede
Ereigniswahrscheinlichkeit der Fortschreibung entsteht daraus als
geklemmte affine Transformation

$$\text{Annahme} \;=\; \min(1,\; \max(0,\; a + b \cdot q)),
\qquad q = \text{Wert erster Ordnung}$$

Die Klemmung auf $[0, 1]$ gehört zur Definition: Ohne sie wäre die
Transformation keine Wahrscheinlichkeitsabbildung. Zur Belegung der
Parameter:

* $b < 1$ dämpft eine belastende, $b > 1$ verstärkt eine entlastende
  Ausscheideordnung; $b = 1$ übernimmt die erste Ordnung unverändert.
* $b = 0$ ist der Fall für Ereignisse, für die es **keine**
  Rechnungsgrundlage gibt (Storno, Beitragsfreistellung, dynamische
  Erhöhung): Dort ist $a$ die Rate selbst.

Beiträge und Reserven bleiben von den Erfahrungsannahmen unberührt.
Diese Trennung ist nicht verhandelbar: Eine Erfahrungsannahme darf nie
in die Bewertung zurückwirken.

# 6 Diskretisierung, Numerik und Rundung

* **Gitter.** Die Rekursion läuft auf **jährlichen** Stützstellen, den
  Vertragsjahrestagen. Ein unterjähriger Stichtag wird auf eine von
  **zwei benannten Konventionen** abgebildet, nie stillschweigend:

  | Konvention | Regel | Verwendung |
  |---|---|---|
  | **Zustand am Stichtag** | Werte des angebrochenen Vertragsjahres, also der Verlaufszeile $\lfloor m/12 \rfloor$ bei $m$ vollen Vertragsmonaten — **keine** Interpolation | Bestandsführung und ihre Bewertung, aktuarielle Prüfung |
  | **Monatsreserve** | lineare Interpolation zwischen den Jahresstützstellen $\lfloor m/12 \rfloor$ und $+1$; an einer Stützstelle bit-identisch zur Jahreszeile | Bilanzstichtage zwischen zwei Jahrestagen, Migrationscontrolling |

  Welche Konvention gilt, sagt der aufrufende Pfad — beide zu mischen
  oder eine für die andere zu halten, ist ein Fehler: An einem
  Stichtag mitten im Vertragsjahr liegen sie um Größenordnungen
  auseinander.
* **Rechenpunkt.** Bewertungen, die eine Aussage über die **Methode**
  tragen sollen (aktuarielle Prüfung, Verankerung), werden am
  Rechenpunkt gebildet — am Vertragsjahrestag, nicht am interpolierten
  Zwischenwert (9.12).
* **Rundung.** Rundung ist eine Konvention der Darstellung, nicht der
  Rekursion: Zwischenergebnisse der Bewertung laufen in voller
  Gleitkomma-Präzision. Wo gerundet wird, gilt **kaufmännisch von der
  Null weg** (half away from zero) — nicht das Runden zur geraden
  Ziffer, das Python voreinstellt.
* **Radix und Rundungsordnung der Kommutation.** Die Radix
  $l_0 = 1\,000\,000$ und die Rundung auf 16 Stellen sind Konventionen
  der **Kommutations-Vergleichsschiene** (Abschnitt 11), nicht des
  Zielkerns: Dieser führt keine $l_x$-Kette, sondern rechnet
  Verbleibswahrscheinlichkeiten direkt aus den Ausscheidewerten. Wer
  ein neues Produkt baut, braucht beide Größen nicht.
* **Verankerung in voller Präzision.** Charakterisierungs-Anker binden
  den produktiven Pfad in voller Float-Präzision. Eine auf
  Nachkommastellen gerundete Parität ist ein historischer
  Übersetzungsbeleg, kein laufender Anker.

# 7 Geschäftsvorfälle: Buchungskonvention

Geschäftsvorfälle werden auf **Vertragsjahrestagen** gebucht: Das Jahr
$a$ wirtschaftet, gebucht wird am Jahrestag $a+1$. Der Betrag eines
Vorfalls ist je Produkt im Tarifplan definiert (GeVo-Katalog); die
Buchungskonvention selbst gilt für alle.

Die Eintrittswahrscheinlichkeiten der Vorfälle sind
Erfahrungsannahmen dritter Ordnung (5.2) und keine
Rechnungsgrundlagen.

# 8 Schichten der Bewertung

Der Wert eines Vertrags setzt sich aus Schichten zusammen, die
**dieselbe** Rekursion (4.1) auf **demselben** Zustandsraum (3) nutzen
und sich nur in ihren Zahlungsfunktionen unterscheiden:

| Schicht | Zahlungen | Status |
|---|---|---|
| **Basis** | garantierte Leistungen und Beiträge des Tarifs | gebaut |
| **Bonus** | Überschussbeteiligung | nicht gebaut |
| **Korrektur** | Ausgleich des Migrationsresiduums (Abschnitt 9) | Mathematik festgelegt, nicht implementiert |
| **Konventionsresiduum** | unterjährige Altkonventionen des Quellsystems (9.12) | Mathematik festgelegt, nicht implementiert |

Die Schichten sind additiv und werden **getrennt ausgewiesen**. Keine
Schicht führt einen eigenen Zustand oder eine eigene Uhr ein
(9.5).

# 9 Korrekturschicht: die Mathematik des Migrationszugangs

Ein übernommener Bestand wird **konstruktiv neu gerechnet**: Der Vertrag
zieht mit seinen Ursprungsparametern ins Zielsystem und wird dort an
einem Rechenpunkt gegen die gelieferten Werte verankert. Die dabei
verbleibende Bewertungsdifferenz trägt eine eigene Bewertungsschicht.

Dieser Abschnitt ist die verbindliche Form der Rechenmethode, der die
Umsetzung zu folgen hat. Nicht hierher gehört die projektseitige
Hälfte: Der Datenliefervertrag mit seinen drei Lieferobjekten, das
Quellsystem-Mapping und die Ableitungsregeln stehen in der
Migrationskonzept-Vorlage.

**Status:** Die Rechenmethode ist normativ und hier vollständig; sie ist
noch **nicht implementiert**. Offen sind die technischen Freiheitsgrade
(siehe 9.16).

**Zur Notation:** Zustände sind $s, s'$, die Verweildauer ist $d$, das
Vertragsjahr $j$ (Abschnitt 2) — durchgehend, auch in diesem
Abschnitt.

## 9.1 Zwei-Schritt-Prinzip

1. **Migration im Initialzustand.** Der Vertrag wird mit seinen
   Ursprungsparametern angelegt: Versicherungsbeginn, Eintrittsalter,
   Tarif und **mitwandernde Rechnungsgrundlagen** (Rechnungszins,
   Ausscheideordnung, Kostensätze der Bestandsgruppe), ursprüngliche
   Summe und Beitrag, Ablauf. Keine Historie erforderlich.
2. **Konstruktive Neuberechnung am Verankerungszeitpunkt $t_a$.** Ein
   Geschäftsvorfall des Zielsystems rechnet den Vertrag unter Vorgabe
   anrechenbarer Werte (Anker) neu; die Differenz zwischen geliefertem
   und prospektivem Deckungskapital geht über den Verankerungsoperator
   (9.8) in die Korrekturschicht.

Bindend: Die Neuberechnung nutzt einen **regulären
Geschäftsvorfalltyp** des Zielsystems (Neuberechnung mit
Kapitalanrechnung), keinen migrationsspezifischen Sonderrechenpfad. Der
Vertrag rechnet nach der Migration in derselben Logik weiter, in der er
übernommen wurde.

## 9.2 Ankerhierarchie

Anker sind die Werte, die die Neuberechnung nicht verändern darf. Die
Reihenfolge ist der Default; die finale Festlegung samt Toleranzen
gehört je Produkt in den Tarifplan (Abschnitt 10 Nr. 9).

| Prio | Anker | Härte | Begründung |
|---|---|---|---|
| 1 | Garantierte Leistungen (Todesfall, Ablauf/Rente, beitragsfreie Summen) | hart | vertraglich zugesagt |
| 2 | Zahlbeitrag | hart | Kundensicht, Inkasso |
| 3 | Deckungskapital | hart | Bilanz, kein unerklärter Sprung |
| 4 | Rückkaufswert und Mindestwerte nach § 169 VVG | hart | gesetzlich |
| 5 | Künftiger Wertverlauf | weich | über Formfunktion (9.9) und Tests gesteuert |

Zur Deckungskapital-Invarianz: Gefordert ist **kein unerklärter Sprung**
am Übernahmepunkt, **keine Unterschreitung von Mindestwerten** zu
irgendeinem Zeitpunkt und **Konsistenz im Aggregat** einschließlich ZZR
— nicht bitgenaue Konstanz jedes Einzelwerts über die Laufzeit.

## 9.3 Das Residuum

Sind die Anker 1 bis 3 hart, ist das Residuum vollständig determiniert:

$$R(t_a) \;=\; V^{\mathrm{ist}}(t_a) \;-\; V^{\mathrm{prosp}}(t_a;\, S, B)$$

Es gibt **keinen Freiheitsgrad in der Höhe** von $R$ — nur in seiner
Fortschreibung (9.5 bis 9.9).

Die erwartete Verteilung über einen Bestand ist **bimodal**: Verträge
ohne Geschäftsvorfallhistorie liegen bei $R \approx 0$ (prospektive
Konsistenz per Konstruktion), Verträge mit Historie bilden einen
zweiten Cluster — getrieben vor allem durch die Zillmer-Amortisation des
Quellsystems, Dynamik-Schichtung, Beitragsabgrenzung und Kostenentnahmen
in beitragsfreien Zeiten. $R$ ist damit zugleich
**Migrationsqualitätskennzahl**; seine nach Historientyp geclusterte
Verteilung ist zentraler Prüfgegenstand beider Prüfebenen (9.15;
Verfahren im Migrationskonzept, Kapitel 6 und 7).

Daraus folgt: Die Korrekturschicht ist **Regelbestandteil jedes
migrierten Vertrags** (gegebenenfalls mit Kalibrierungsfaktor null),
kein Ausnahmepfad für Sonderfälle.

## 9.4 Abgrenzung: Residuum und Fehlerkorrektur

Zwei strikt getrennte Mechanismen, deren Vermischung nicht heilbar ist:

* Die **Korrekturschicht** absorbiert die unerklärte
  Bewertungsdifferenz. Anker bleiben unangetastet, die Kundensicht
  unverändert.
* Eine **Fehlerkorrektur** verändert einen Anker (falscher Beitrag,
  falsche Summe im Quellsystem). Sie ist ein Kundenrechts- und
  Kommunikationsthema mit eigenem Prozess und läuft **niemals** über die
  Korrekturschicht.

Beide müssen ex post unterscheidbar bleiben — sonst ist später nicht
mehr feststellbar, ob eine Differenz Modellrest oder Anspruch war.

## 9.5 Overlay-Prinzip

Die Korrekturschicht ist ein zusätzliches Paar von Zahlungsfunktionen
auf dem **vorhandenen** Zustandsraum, ausgewertet entlang desselben
Pfades wie Basis- und Bonusschicht. Ihre Ströme sind **fiktiv** — reine
Bewertungsgrößen ohne reale Zahlung; ihr Zweck ist, dem Korrekturwert
$V^{\mathrm{korr}}$ eine wohldefinierte Thiele-Dynamik zu geben. Der
„Abbau von $R$" *ist* dieser fiktive Strom.

Drei Anti-Pattern sind verbindlich ausgeschlossen:

* **Kein Zustand „migriert"** im Zustandsraum: Er würde die
  Verweildauer-Uhr zurücksetzen und die Biometrie verfälschen. Die
  Migration ist ein Ereignis mit statischem Attribut $t_a$
  beziehungsweise $t_0$, kein Zustand.
* **Keine dritte Uhr.** Die Zahlungsfunktion darf von Zeit,
  Verweildauer und statischen Vertragsattributen abhängen; „Zeit seit
  Migration" ist $t - t_a$ und damit kein zusätzlicher Zustandsraum.
  Auf die Verweildauer-Abhängigkeit soll **verzichtet** werden, wo es
  möglich ist; sie bleibt zulässig, ist aber begründungspflichtig.
* **Kein skalarer Restposten** in der Datenhaltung mit tabellarischer
  Tilgung: Er erfüllt keine Thiele-Rekursion und ist bei
  Zustandswechseln undefiniert.

## 9.6 Bewertungsdynamik und ihre diskrete Form

**Ausgangspunkt.** Weil der Erwartungswert linear ist, gilt die
Semi-Markov-Thiele-Gleichung **schichtweise**. Für eine Schicht mit
Zustandszahlung $b_s$ und Übergangszahlung $b_{s s'}$ lautet sie

$$(\partial_t + \partial_d)\, V_s(t,d) \;=\; \delta(t)\, V_s \;-\; b_s
\;-\; \sum_{s' \neq s} \mu_{s s'}(t,d)\,
[\, b_{s s'} + V_{s'}(t,0) - V_s(t,d) \,]$$

**Klassifikation der Übergänge.** Für die Korrekturschicht wird jeder
Übergang einer von zwei Klassen zugeordnet:

* **Wertkontinuierlich.** Der Schichtwert geht eins zu eins weiter —
  entweder als Übertrag, dann ist $b_{s s'} = 0$ und
  $V^{\mathrm{korr}}_{s'}(t,0) = V^{\mathrm{korr}}_s(t,d^-)$, oder als
  Auszahlung mit anschließender Absorption, dann ist
  $b_{s s'} = V^{\mathrm{korr}}_s$ und danach
  $V^{\mathrm{korr}}_{s'} = 0$. In **beiden** Fällen ist der eckige
  Klammerterm null: **wertkontinuierliche Übergänge fallen aus der
  Thiele-Gleichung heraus.**
* **Vererbend** ($s' \in F_s$): Der Wert verfällt ohne Gegenleistung;
  der Klammerterm reduziert sich auf $-V^{\mathrm{korr}}_s(t,d)$.

**Kollapsform.** Damit bleibt eine eindimensionale Rückwärtsgleichung,
zustandsweise mit zustandsabhängiger Menge $F_s$:

$$(\partial_t + \partial_d)\, V^{\mathrm{korr}} \;=\;
( \delta(t) + \sum_{s' \in F_s} \mu_{s s'}(t,d) )\, V^{\mathrm{korr}}
\;-\; c_s(t,d),
\qquad V^{\mathrm{korr}}(T) = 0$$

**Diskrete Form — hier festgelegt** (Grundsatzdokumentation 9.6 delegiert die
Diskretisierung an dieses Dokument). Auf dem Jahresgitter aus Abschnitt
6 und mit denselben Ersetzungen wie im übrigen Kern
($e^{-\delta} \to v$, $\mu_{s s'} \to p_{s \to s'}$ für $s' \neq s$):

$$V^{\mathrm{korr}}_j(s, d) \;=\; c_s(j, d) \;+\; v \cdot
( 1 - \sum_{s' \in F_s} p_{s \to s'}(x_0 + j,\, d) ) \cdot
V^{\mathrm{korr}}_{j+1}(s,\, d^{+}),
\qquad V^{\mathrm{korr}}_n(s, d) = 0$$

mit $d^{+} = \min(d+1,\, d_{\max})$ wie in Abschnitt 4.

**Wie sie zu lesen ist.** Im Zustand $s$ zehren ausschließlich die
**vererbenden** Ausscheideursachen am Schichtwert. Die
wertkontinuierlichen Übergänge erscheinen nicht in der Rekursion — nicht
weil sie ignoriert würden, sondern weil die Wertgleichheit oben sie
herausfallen lässt: Beim Übertrag gilt
$V^{\mathrm{korr}}_{j+1}(s', 0) = V^{\mathrm{korr}}_{j+1}(s, d^{+})$
per Konstruktion (bei Klasse C hergestellt durch die Neuverankerung,
9.8), bei der Auszahlung ist der Folgewert null und die Zahlung deckt
ihn exakt. Zahlungsprofil, Fälligkeit, Diskontierung und Rundung sind
dieselben wie für die Basisschicht: Die Korrekturschicht ist kein
zweiter Rechenweg, sondern dieselbe Rekursion mit anderen Zahlungen.

## 9.7 Übergangstaxonomie

Die Klassifikation entscheidet, was beim Übergang mit dem Schichtwert
geschieht. Die folgende Tabelle ist der **Default**; die vollständige
Klassifikation aller Übergänge des jeweiligen Zustandsgraphen gehört je
Produkt in den Tarifplan.

| Ereignis / Übergang | Klasse | Behandlung |
|---|---|---|
| Rechnender Geschäftsvorfall (Beitragsfreistellung, Herabsetzung, Dynamik, Zuzahlung, Teilrückkauf, Verlängerung) | A | **Absorption:** Das Gesamt-Deckungskapital *einschließlich der Schicht* wird angerechnet, danach Kalibrierungsfaktor null. Der Vertrag ist ab dem ersten rechnenden Vorfall rein prospektiv — „geheilt". |
| Rückkauf | B | wertkontinuierlich: Die Schicht zahlt sich im Rückkaufswert aus. Konvention: Den Stornoabzug trägt die Basisschicht. |
| Tod mit fester Versicherungssumme | B | **vererbend:** Die Leistung ist Anker und bleibt unangetastet, der Schichtwert verfällt. Die Sterblichkeit finanziert die Amortisation anteilig mit. |
| Tod oder Ablauf mit DK-bezogener Leistung | B | wertkontinuierlich: Die Schicht fließt in die Leistung ein. |
| Vertragsablauf | B | Terminalbedingung $V^{\mathrm{korr}}(T) = 0$; nicht verhandelbar, sonst wäre die Ablaufleistung ungleich dem Deckungskapital. |
| Fortführender Übergang ohne Neuberechnung (etwa Beitragsbefreiung aus einer Zusatzversicherung, Ende einer Stundung) | C | stetiger Übertrag und **Neuverankerung** im Zielzustand (9.8). |

## 9.8 Verankerungsoperator

$$\mathcal{A}(t, s, d, R):\qquad
\rho \;:=\; \frac{R}{\Pi_s(t,d)}, \qquad c_s \;=\; \rho\, g$$

$\Pi_s(t,d)$ ist der Barwert des Einheitsstroms $g$ unter der Dynamik
aus 9.6 — numerisch **dieselbe Rekursion** mit $c = g$ statt
$c = c_s$. Eine geschlossene Form ist **nicht erforderlich**; der Kern
bewertet $\Pi$ mit derselben Rekursion wie $V^{\mathrm{korr}}$ selbst.

Ein Operator, vier Aufrufkontexte:

| Kontext | Aufruf |
|---|---|
| Migration (Erstverankerung) | $\mathcal{A}(t_a,\, s_0,\, d_0,\, V^{\mathrm{ist}}(t_a) - V^{\mathrm{prosp}}(t_a))$ |
| Klasse-C-Übergang | $\mathcal{A}(t,\, s',\, 0,\, V^{\mathrm{korr}}(t^-))$ — Verweildauer-Reset beim Zustandseintritt |
| Klasse-A-Geschäftsvorfall | Anwendung mit $R = 0$ nach der Absorption |
| Zweitverankerung (Konventionsresiduum, 9.13) | $\mathcal{A}(t_0,\, s,\, d,\, \delta_{\mathrm{conv}})$ in eine eigene Schicht |

**Optionsunabhängigkeit.** Da alle Optionsübergänge des
Versicherungsnehmers (Storno, Beitragsfreistellung und weitere)
wertkontinuierlich sind, treten ihre Intensitäten in $\Pi$ nicht auf.
Der Kalibrierungsfaktor $\rho$ hängt damit nur vom Rechnungszins und den
vererbenden biometrischen Ausscheideursachen ab — **Stornoannahmen
spielen in der Migrationsbewertung keine Rolle.**

## 9.9 Formfunktion

Die Formfunktion $g$ bestimmt, wie sich das Residuum über die
Restlaufzeit verteilt. Anforderungen: in **allen Erlebenszuständen
definiert** (Verträge können beitragsfrei oder im Rentenbezug migrieren,
eine rein beitragsproportionale Form ist unvollständig) und über die
Restlaufzeit integrierbar mit $\Pi > 0$.

Zulässige Kandidaten, Wahl je Tarifplan:

1. $g \propto V^{\mathrm{base}}(t)$ — glatt und überall definiert.
   **Default.**
2. $g \equiv 1$ auf einem Amortisationsfenster $[t_a,\, t_a + n]$ — am
   leichtesten zu erklären; $n$ ist Produktparameter; ungeeignet bei
   kurzer Restlaufzeit.
3. Beitragsproportional — nur zulässig zusammen mit einer
   Fortsetzungsregel für beitragsfreie Zustände.

Optional kann die Form **per Kleinste-Quadrate** gegen
Stützstellen-Verläufe des Deckungskapitals aus dem Quellsystem
kalibriert werden (Approximation der Altsystemlogik statt bloßer
Stichtagsrettung). Ob das geschieht, ist je Bestand zu entscheiden und
in der Ausgestaltung des Tarifplans zu dokumentieren.

## 9.10 Guardrails

* **$R < 0$** (Ist unter prospektiv; typisch bei nicht getilgtem
  Abschlusskostenanteil): **pfadweise** Floor-Prüfung zur
  Kalibrierungszeit — Basiswert plus Korrekturwert muss die
  Mindestwerte nach § 169 VVG und DeckRV **für alle Zeitpunkte**
  einhalten, nicht nur am Verankerungspunkt. Bei Verletzung wird $R$
  gekappt; der gekappte Teil geht in den Fehler- und Klärungsprozess
  (9.4), nie in die Schicht.
* **$R > 0$** ist aufsichtsrechtlich unkritisch. Beim Abbau wird
  Ergebnis frei, das in Rohüberschuss und Überschussbeteiligung läuft
  (§ 153 VVG, RfB). **Ob und wie** es dem Bestand zusteht, ist
  Unternehmensentscheidung — der Kern muss den Effekt **sichtbar
  ausweisen** können.
* **Degeneration $\Pi \to 0$** bei kurzer Restlaufzeit: Unterhalb einer
  Schwelle wird $R$ sofort über das Ergebnis ausgebucht statt verrentet,
  sonst explodiert $\rho$. Dass es eine Schwelle gibt und die
  Ausbuchung im Ergebnis sichtbar ist, ist bindend; ihr Wert ist offen
  (9.16).
* **Flags:** Die Schicht ist Deckungskapital, trägt den Rechnungszins
  ihrer Bestandsgruppe und ist im Default in Überschussbemessung und
  ZZR-Ermittlung **enthalten** — beides als Konfiguration je
  Bestandsgruppe, nie als fest verdrahtete Regel.

## 9.11 Persistenz und Reporting

Persistiert werden **Parameter, keine Zwischenwerte**: Schichttyp,
Verankerungszustand $s_0$ und Verweildauer $d_0$, Verankerungszeitpunkt
$t_a$, Kennung und Parameter der Formfunktion, Kalibrierungsfaktor
$\rho$, die $F$-Klassifikation, die Flags und das Kohortenkennzeichen.
$V^{\mathrm{korr}}$ ist daraus jederzeit reproduzierbar.

Die Schicht wird je Vertrag **und** aggregiert als eigene
Reporting-Position ausgewiesen, nie unsichtbar im Deckungskapital.

## 9.12 Verankerungszeitpunkt

Verankert wird am **letzten exakten Rechenpunkt des Quellsystems**:

$$t_a \;=\; \max(\text{letzter Vertragsstichtag},\;
\text{letzter rechnender Geschäftsvorfall})$$

An einem Rechenpunkt vergleicht die Methode geschäftsplanmäßige
Rechenwerte. Am unterjährigen Migrationsstichtag verglichen würde $R$
zusätzlich Interpolationskonventionen und Beitragsabgrenzung messen und
wäre als Diagnoseinstrument entwertet. Zudem ist der zu
rekonstruierende Zustand innerhalb des Jahres dort minimal — Zillmerjahr,
Dynamikofferten, verdiente Beitragsanteile —, und der Wert am $t_a$
entspricht der letzten Standmitteilung nach § 155 VAG: Kundenkonsistenz
ist wörtlich erfüllt.

**Nachfahren bis zum Migrationsstichtag.** Der Zeitraum $[t_a, t_0]$
wird im Zielsystem nachgefahren (Fälligkeiten, gegebenenfalls
Geschäftsvorfälle, Fortschreibung). Der Vergleich des nachgefahrenen
Werts gegen den gelieferten Altwert am $t_0$ ist ein **eingebauter
Test** der Fortschreibungs- und Geschäftsvorfall-Logik am Echtbestand
vor der Inbetriebnahme. Abweichungen müssen je Zahlweise- und
Tarifcluster **systematisch** sein (Konventionsdifferenz);
unsystematische Abweichungen sind Befunde. Das Verfahren dazu steht im
Migrationskonzept.

**Fallback-Kohorte.** Kann die Quelle für einzelne Verträge nur den
Snapshot am $t_0$ liefern, wird auf eine Verankerung am $t_0$
ausgewichen — als **gekennzeichnete Kohorte mit eigener Toleranz**,
**niemals stillschweigend gemischt**. Die Kennzeichnung ist
Pflichtattribut (9.11).

## 9.13 Die beiden Residuen

Aus der Verankerungsregel folgen zwei getrennte Residuen mit eigenen
Ursachen, Verteilungen und Toleranzen:

* $R_{\mathrm{hist}}$ — Verankerung bei $t_a$, enthält ausschließlich
  Pfad- und Historienresiduen. **Primäre Qualitätskennzahl.**
* $R_{\mathrm{conv}}$ — optional. Wird bitgenaue Gleichheit am
  Migrationsstichtag gefordert (etwa zum Bilanzstichtag), wird die
  Konventionsdifferenz **primär eliminiert**, indem der Kern die
  unterjährigen Rechen- und Interpolationskonventionen des Altbestands
  als Teil der mitwandernden Rechnungsgrundlagen führt. Ein
  verbleibender Rest $\delta_{\mathrm{conv}}$ geht per Zweitverankerung
  (9.8) in eine **eigene Schicht** — getrennt persistiert, getrennt
  berichtet, mit eigener Toleranz. Im Kern kostet die Zweitschicht
  nichts, weil der Mechanismus identisch ist.

Die beiden Residuen werden nie vermischt.

## 9.14 Historienfreiheit des Rechenkerns

Die Methode verzichtet ausschließlich auf das **Replay**: Der Kern
rechnet den Vertrag nie ab Beginn nach und braucht keine Bewegungsdaten
vor $t_a$ als Recheninput. Die Historie entfällt damit nicht, sie
wechselt die Rolle:

| Rolle | Inhalt | Adressat |
|---|---|---|
| **Zustandsextrakt** | Historien*ergebnisse* als Vertragsattribute — Verankerungszustand und Verweildauer, Options- und Rechtszustände, Restzillmerstand, Beitragsrückstände, Steueraggregate | Rechenkern |
| **Migrationsanalytik** | Geschäftsvorfall-Metadatenliste für die $t_a$-Ermittlung, die Historien-Clusterung der Residuum-Verteilung und die Ausreißerdiagnose | Migrationsprojekt, Abnahme |
| **Archiv** | Vollhistorie dauerhaft auskunftsfähig: Aufbewahrungspflichten, Auskunftsersuchen, Rückabwicklung bei Widerruf — **Letzteres kann ein prospektiv verankerter Vertrag konstruktionsbedingt nicht liefern** | Auskunftssystem außerhalb des Rechenkerns |

Zwei Grundsätze sind bindend: Die **Ableitungslast liegt quellseitig
oder im Migrationssystem** — führt das Quellsystem die abgeleiteten
Attribute nicht als Bestandsfelder, berechnet sie die
Übernahmestrecke. Und der **Rechenkern bleibt historienfrei**: Er sieht
die Geschäftsvorfall-Liste zu keinem Zeitpunkt; sein einziger
Historieninput ist das Attributset des Zustandssnapshots.

**Ohne die Geschäftsvorfall-Metadatenliste ist die aktuarielle Abnahme
nicht durchführbar** — ohne sie gibt es keine Historien-Clusterung und
keine erklärbaren Ausreißer. Sie ist Abnahmevoraussetzung, nicht
Komfort.

Für den Kern dieses Repositories gilt die Invariante heute schon und
ist strukturell abgesichert: Kein Bewertungspfad liest das Journal
(ADR-011).

## 9.15 Prüfung der Methode und Verantwortung

Die Güte der konstruktiven Neuberechnung wird auf **zwei getrennten
Ebenen** geprüft. Die Trennung ist methodisch, nicht organisatorisch:

| Ebene | Zeitbezug | Gegenstand | Verantwortung |
|---|---|---|---|
| **Aktuarieller Test** | $t_a$ | methodische Güte: Verteilung von $R_{\mathrm{hist}}$ geclustert nach Historientyp, Ausreißeranalyse, Floor-Prüfungen | Aktuariat, Verantwortlicher Aktuar |
| **Migrationscontrolling** | $t_0$ | Vollständigkeit, Überleitung, Bilanz: Vertrags- und Summenabstimmung, Deckungskapital- und ZZR-Summen je Bestandsgruppe, Statistik des Konventionsresiduums, Nachfahr-Abweichungen je Cluster | Migrationsprojekt |

Das Controlling misst am Übernahmepunkt gegen die Bilanz, der
aktuarielle Test am Rechenpunkt gegen die Methode.

**Toleranzform.** Toleranzen werden auf der **Verteilung** definiert —
Maximum, hohe Perzentile, Betragssumme je Bestandsgruppe — **niemals
auf Mittelwert oder Median**. Erwartet wird Bimodalität (9.3); ein
unauffälliger Mittelwert bei großen Einzelmaxima ist ein Befund, keine
Entwarnung. „Rundung" ist als Ursache nur für Differenzen in
Cent-Größenordnung zulässig; größere Beträge verlangen eine benannte
Ursache je Cluster.

**Verlaufstests.** Stichtagstreue allein genügt nicht. Verlangt sind
zusätzlich die Vorwärtsrechnung über mehrere Jahre gegen eine
Schattenrechnung des Quellsystems für repräsentative Cluster und eine
Testmatrix je Vertragskonstellation, die alle Übergänge der Klassen A,
B und C mit ihrem Sollverhalten abdeckt (9.7). **Ohne Verlaufstests
gilt die Methode als nicht abgenommen.**

**Verantwortung und Rahmen.** Für die Methode der
Deckungsrückstellungsberechnung besteht kein Genehmigungsvorbehalt der
Aufsicht; eine Abstimmung ist möglich, aber kein Freibrief.
Verantwortlich zeichnet der **Verantwortliche Aktuar (§ 141 VAG)**,
flankiert von Abschlussprüfer und interner Revision. Grundlage der
Freigabe sind dieses Dokument, die produktspezifischen Ausgestaltungen
(Abschnitt 10 Nr. 9) und die Residualstatistik der beiden Prüfebenen.

Einschlägige Randbedingungen, die die Methode einhält: § 169 VVG und
DeckRV (Mindestwerte, Höchstzillmerung, 9.10), § 153 VVG
(Überschussbeteiligung beim Abbau eines positiven Residuums, 9.10),
§ 155 VAG (Standmitteilungskonsistenz, 9.12), § 341f HGB und ZZR
(Schicht in Bestandsgruppe und ZZR-Ermittlung, 9.10) sowie die
mitwandernden Rechnungsgrundlagen (9.1).

Das Verfahren beider Prüfebenen — Artefakte, Gates, Entscheidungswege —
steht in der Migrationskonzept-Vorlage, Kapitel 6 und 7.

## 9.16 Offene Freiheitsgrade

Die Mathematik oben ist verbindlich. Offen sind die folgenden Punkte
der Methode; sie sind **zwischen Entwicklung und
fachverantwortlichem Aktuar** zu entscheiden und danach hier oder im
Tarifplan zu belegen — nicht beim Implementieren nebenbei:

| Gegenstand | bindend ist | offen ist |
|---|---|---|
| Repräsentation der Schicht | Overlay-Semantik (9.5): kein eigener Zustand, keine dritte Uhr | eigenes Schichtobjekt oder Attributsatz am Vertrag; Datenmodell |
| Numerik | Rekursionsform konsistent zur Basisschicht, Schrittweite jährlich (9.6, Abschnitt 6) | Löser, Rundungsimplementierung |
| Klasse-A-Integration | Anrechnung des Gesamt-Deckungskapitals **einschließlich der Schicht**, danach $\rho := 0$ | Reihenfolge und Verortung in der Geschäftsvorfall-Engine, Transaktionsschnitt |
| Klasse-C-Neuverankerung | Operator nach 9.8 | Auslösemechanik (Ereignis-Haken oder Neubewertung) |
| Unterjährige Altkonventionen | als konfigurierbare Rechnungsgrundlage, nicht als Sonderlogik im Rechenpfad | Konfigurationsmodell, Granularität |
| Degenerationsfall | eine Schwelle muss existieren, die Ausbuchung sichtbar sein (9.10) | konkreter Schwellwert, Buchungsweg |
| Floor-Prüfung | pfadweise zur Kalibrierungszeit (9.10) | Prüfraster, Performance-Strategie |
| Persistenz | Parameter statt Werte, Reproduzierbarkeit (9.11) | Speichermodell, Versionierung |
| Reporting | eigene Position je Vertrag und aggregiert, beide Residuen getrennt | Kontenanbindung, Berichtsformate |
| Fallback-Kohorte | Kennzeichnungspflicht (9.12) | Umsetzung im Datenmodell |
| Geschäftsvorfall-Metadatenliste im Zielsystem | Abnahmevoraussetzung (9.14) | dauerhafte Mitführung als Auskunftsattribut oder Verbleib im Migrations-Staging |

Weicht die Architektur des Kerns von einer bindenden Vorgabe ab, wird
die Abweichung nicht implizit aufgelöst, sondern **zwischen Entwicklung
und fachverantwortlichem Aktuar** entschieden und im
Abweichungsverzeichnis (Abschnitt 12) dokumentiert. Nicht verhandelbar
sind: die Ankerhierarchie (9.2), Terminalbedingung und
Übergangssemantik (9.6, 9.7), die Floors (9.10), die Trennung von
Residuum und Fehlerkorrektur (9.4), die getrennte Ausweisbarkeit der
Residuen (9.13) und die Historienfreiheit des Kerns (9.14).

# 10 Produkt-Contract: was ein Tarifplan festlegt

Ein Produkt ist im Kern eine Belegung dieses Rückgrats. Der Tarifplan
eines Produkts legt fest — und nur er:

1. **Zustandsraum und Übergänge** des Tarifs samt zugeordneten
   Rechnungsgrundlagen.
2. **Leistungsdefinition und Zahlungsprofile** (welche Zahlung in
   welchem Zustand, bei welchem Übergang).
3. **Beitragsermittlung** und ihre Zuschläge.
4. **Reserve- und Wertbegriffe** des Produkts, einschließlich
   Rückkaufs- und Umwandlungswerten.
5. **GeVo-Katalog**: welche Geschäftsvorfälle das Produkt kennt und mit
   welchem Betrag.
6. **Stellschrauben** des Tarifwerks als Felder des Modellpunkts.
7. **Gültigkeitsgrenzen** und produktspezifische Fail-fast-Regeln.
8. **Bestandsgenerationen** mit ihren Ontologie-Knoten.
9. Bei **migrierten Produkten** zusätzlich die Ausgestaltung der
   Korrekturmathematik (Übergangsklassifikation,
   Ankerliste mit Härtegraden, Formfunktion, Floors,
   Degenerationsschwelle, Testfallkatalog).

Die Abgrenzung ist mechanisch prüfbar und folgt der
Knoten-Annotation des Codes: Was ein Modul beschreibt, das allen
Produkten dient (`Knoten: klv, bu`), gehört hierher; was ein Modul mit
genau einem Produktknoten beschreibt, gehört in den Tarifplan. **Kein
Satz steht an beiden Orten.**

# 11 Abnahme und Verankerung

Änderungen am Kern folgen seinem Abnahme-Protokoll
(`rechner_pipeline.kern`): Charakterisierungs-Anker in voller
Float-Präzision, algebraische Identitätsprüfungen, je Migrationsfall
Gate O3 gegen den Quell-Rechner, und für Produkte mit
Kommutations-Vergleichsschiene die Toleranz-Überleitung
(`qa/ueberleitung`). Die klassische Kommutationsrechnung lebt als
separater Zweitkern ausschließlich als Kreuz-Check; sie ist kein
Bestandteil des Zielkerns.

Die Abnahme einer **Migration** ist davon getrennt und läuft über die
beiden Prüfebenen (9.15; Verfahren im Migrationskonzept,
Kapitel 6 und 7).

# 12 Abweichungsverzeichnis

Nach der Konfliktregel (9.16) werden Abweichungen zwischen
Konzept und Realisierung nicht implizit aufgelöst, sondern entschieden
und hier dokumentiert.

| Nr | Gegenstand | Entscheidung | Datum |
|---|---|---|---|
| 1 | Ratenzuschlag-Staffel lag doppelt vor: wirksam als Feld am Modellpunkt, tot als Konstante der Konventionsschicht | Die tote Kopie ist entfernt; die Staffel wird immer übergeben, ein Default in der Konventionsschicht ist unzulässig — Tarifwerk gehört zum Produkt | 2026-08-27 |

Weitere Abweichungen sind derzeit nicht entschieden. Wer eine
feststellt, löst sie nicht implizit auf, sondern trägt sie hier ein
(Konfliktregel, 9.16).

# 13 Versionierung und Änderungsprozess

Dieses Dokument ist versioniert wie der Code, in dem es gilt: Eine
Änderung läuft als Commit mit dem Änderungsgrund, und der Kern folgt
ihr — nicht umgekehrt. Substanzielle Änderungen an den Abschnitten 3
bis 9 sind fachliche Änderungen und brauchen die Zustimmung des
Aktuariats — für Abschnitt 9 (Korrekturschicht) gilt zusätzlich die
Konfliktregel aus 9.16: entschieden wird zwischen Entwicklung und
fachverantwortlichem Aktuar. Sie erscheinen im Changelog des
Repositories.
