---
title: "Grundsatzdokumentation — Mathematik und Numerik des Zielrechenkerns"
lang: de
format:
  typst:
    papersize: a4
---

> **Grundsatzdokumentation** im Sinne des Fachkonzepts „Konstruktive
> Neuberechnung und Korrekturschicht" v0.2, Kapitel 8.1: die Mathematik
> und Numerik, **der die Umsetzung folgt**. Sie gilt für **alle**
> Produkte des Zielrechenkerns. Was ein einzelnes Produkt ausmacht,
> steht in seinem Tarifplan (`docs/tarifplaene/`, Fachkonzept Kap. 8.2)
> — und dort auch nur dort.
>
> **Zur Reihenfolge, ehrlich:** Der Rechenkern existierte vor diesem
> Dokument. Was hier steht, kodifiziert die geltenden Konventionen des
> Kerns; ab dieser Fassung ist es normativ. Abweichungen der
> Implementierung sind ab hier unzulässig und laufen über den
> Änderungsprozess (Abschnitt 13), dokumentiert im
> Abweichungsverzeichnis (Abschnitt 12).

# 1 Zweck und Geltung

Dieses Dokument beschreibt das gemeinsame Rückgrat: den Zustandsraum,
die Bewertungsgleichung, die Rechnungsgrundlagen-Schicht, die
numerischen Konventionen und das Verhältnis der Bewertungsschichten
zueinander. Es ist die einzige Quelle für diese Aussagen — kein
Tarifplan wiederholt sie.

Die Abgrenzung nach oben und unten:

| Dokument | Gegenstand |
|---|---|
| Fachkonzept (`konstruktive-neuberechnung.md`) | die Methode: Invarianten, Prozess- und Testrahmen, Freiheitsgrade — fachlich normativ, technisch offen |
| **Grundsatzdokumentation (dieses Dokument)** | Mathematik und Numerik, verbindlich für die Implementierung; produktübergreifend |
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
V_j(s, d) \;=\; z(s, j) \;+\; v \cdot \Bigl[
\sum_{s' \neq s} p_{s \to s'}(x_0 + j,\, d)
\cdot \bigl( u(s, s', j) + V_{j+1}(s', 0) \bigr)
\;+\; p_{s \to s}(x_0 + j,\, d) \cdot V_{j+1}\bigl(s,\, d^{+}\bigr)
\Bigr],
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

$$\text{Annahme} \;=\; \min\bigl(1,\; \max(0,\; a + b \cdot q)\bigr),
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
  Zwischenwert (Fachkonzept Kap. 5.1).
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
| **Korrektur** | Ausgleich des Migrationsresiduums (Abschnitt 9) | nicht gebaut |
| **Konventionsresiduum** | unterjährige Altkonventionen des Quellsystems | nicht gebaut |

Die Schichten sind additiv und werden **getrennt ausgewiesen**. Keine
Schicht führt einen eigenen Zustand oder eine eigene Uhr ein
(Fachkonzept Kap. 4.1).

# 9 Korrekturschicht

*Dieser Abschnitt ist benannt und bewusst leer.* Er nimmt die
Mathematik der Korrekturschicht auf, sobald die Freiheitsgrade des
Fachkonzepts (dort Kapitel 9) zwischen Aktuariat und Entwicklung
entschieden sind. Aufzunehmen sind dann, mit der Nummerierung der
Pflichtinhalte aus Fachkonzept 8.1:

* die Rückwärtsgleichung der Korrekturschicht und die Herleitung ihrer
  Kollapsform über die vererbenden Übergänge (Pflichtinhalt 2),
* der Verankerungsoperator samt Optionsunabhängigkeit des
  Kalibrierungsfaktors, Mehrfachverankerung und Degenerationsbehandlung
  (Pflichtinhalt 3),
* Floor- und Kappungslogik nach § 169 VVG und DeckRV inklusive
  Prüfzeitpunkten (Pflichtinhalt 5),
* die Behandlung der Flags für Überschussbemessung und ZZR je
  Bestandsgruppe (Pflichtinhalt 6),
* übernommene unterjährige Rechenkonventionen des Quellsystems, falls
  der Konventionsresiduum-Pfad aktiviert wird (Pflichtinhalt 7).

Bis dahin gilt: Die Methode ist im Fachkonzept beschrieben, aber nicht
implementiert. Der aktuarielle Test trägt solange den reinen
Wertvergleich am Verankerungszeitpunkt
(`docs/migrationskonzept/07-aktuarielle-abnahme.md`).

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
   Korrekturmathematik nach Fachkonzept 8.2 (Übergangsklassifikation,
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
beiden Prüfebenen des Fachkonzepts Kapitel 6 (Migrationskonzept
Kapitel 6 und 7).

# 12 Abweichungsverzeichnis

Nach Fachkonzept Kap. 9 (Konfliktregel) werden Abweichungen zwischen
Konzept und Realisierung nicht implizit aufgelöst, sondern entschieden
und hier dokumentiert.

| Nr | Gegenstand | Entscheidung | Datum |
|---|---|---|---|
| — | *(keine entschiedenen Abweichungen)* | — | — |

Offen und noch nicht entschieden ist eine Doppelung der
Ratenzuschlag-Staffel: Der **wirksame** Default liegt bereits beim
Produkt (Felder des Modellpunkts, vom Produkt stets explizit
übergeben). Daneben steht dieselbe Staffel ein zweites Mal als
Konstante in der untersten Konventionsschicht, die der Produktpfad nie
erreicht. Zwei Kopien derselben Zahlen sind eine Driftquelle; welche
verschwindet, ist zu entscheiden.

# 13 Versionierung und Änderungsprozess

Dieses Dokument ist versioniert wie der Code, in dem es gilt: Eine
Änderung läuft als Commit mit dem Änderungsgrund, und der Kern folgt
ihr — nicht umgekehrt. Substanzielle Änderungen an Abschnitten 3 bis 8
sind fachliche Änderungen und brauchen die Zustimmung des Aktuariats;
sie erscheinen im Changelog des Repositories.
