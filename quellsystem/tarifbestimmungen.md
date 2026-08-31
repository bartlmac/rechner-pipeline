---
lang: de
format:
  typst:
    mainfont: "DejaVu Sans Mono"
    fontsize: 9.5pt
    margin:
      x: 2.4cm
      y: 2.6cm
    papersize: a4
---

# Allgemeine Tarifbestimmungen

Kapitallebensversicherung nach Tarifwerk KLV TG2015 — Baldrian
Lebensversicherung a. G.

Fassung Januar 2015. Diese Bestimmungen gelten für alle ab dem
1. Januar 2015 nach Tarifwerk TG2015 geschlossenen Versicherungen.

## 1. Versicherungsformen und Rechnungsgrundlagen

Der Tarif wird in sechs Ausgestaltungen geführt (Raucherstatus,
Vertriebsweg). Für jede Ausgestaltung gelten die folgenden
Rechnungsgrundlagen:

| Zelle | Sterbetafel | Rechnungszins | Abschlusskosten (alpha) | Inkassokosten (beta1) | Verwaltung (gamma1/2/3) | Stückkosten p. a. |
|---|---|---|---|---|---|---|
| Nichtraucher / Einzel | DAV2008_T_NR_U70 | 1,25 % | 25 Promille | 3,0 % | 0.001/0.00125/0.0025 | 12,00 EUR |
| Nichtraucher / Haus | DAV2008_T_NR_U70 | 1,25 % | 0 Promille | 1,0 % | 0.0008/0.001/0.0025 | 0,00 EUR |
| Nichtraucher / Kollektiv | DAV2008_T_NR_U70 | 1,25 % | 15 Promille | 1,5 % | 0.0008/0.001/0.0025 | 12,00 EUR |
| Raucher / Einzel | DAV2008_T_R_U70 | 1,25 % | 25 Promille | 3,0 % | 0.001/0.00125/0.0025 | 12,00 EUR |
| Raucher / Haus | DAV2008_T_R_U70 | 1,25 % | 0 Promille | 1,0 % | 0.0008/0.001/0.0025 | 0,00 EUR |
| Raucher / Kollektiv | DAV2008_T_R_U70 | 1,25 % | 15 Promille | 1,5 % | 0.0008/0.001/0.0025 | 12,00 EUR |

Beitragszuschläge bei unterjähriger Zahlweise sowie Mindest- und
Höchstbeträge des Abzugs nach Ziffer 4 ergeben sich aus dem Tarifblatt
der jeweiligen Ausgestaltung.

## 2. Beiträge

Der Jahresbeitrag ergibt sich aus der Versicherungssumme und dem
tariflichen Beitragssatz B(x,t) nach Anhang B. Bei unterjähriger
Zahlweise wird der Jahresbeitrag zuzüglich Stückkosten durch die Zahl
der Raten geteilt und um den Ratenzuschlag erhöht.

## 3. Planmäßige Erhöhungen (Dynamik)

Vereinbarte planmäßige Erhöhungen erhöhen die Versicherungssumme ohne
erneute Gesundheitsprüfung. Jede Erhöhung wird versicherungstechnisch
als eigenständiger Baustein geführt: mit dem bei Wirksamwerden
erreichten Alter, der restlichen Versicherungs- und
Beitragszahlungsdauer und eigener Wertermittlung nach Anhang A.

Erhöhungen sind ausgeschlossen, sobald die restliche
Versicherungsdauer weniger als fünf Jahre beträgt; ein so kurzer
Baustein ließe sich nicht mehr über die Abschlusskostenverteilung
der Beitragskalkulation (Anhang A) ausfinanzieren.

## 4. Rückkauf und Abzug

Bei Kündigung erstatten wir den Zeitwert der Versicherung abzüglich
eines Abzugs. Der Abzug beträgt 0,5 % der Differenz aus
Versicherungssumme und Deckungskapital, mindestens jedoch den im
Tarifblatt genannten Mindestbetrag und höchstens den dort genannten
Höchstbetrag.

Der Abzug wird für jeden Versicherungsbaustein GESONDERT erhoben: für
die Grundversicherung und für jede planmäßige Erhöhung je einzeln,
jeweils mit Mindest- und Höchstbetrag. Der Rückkaufswert der
Versicherung ist die Summe der Rückkaufswerte ihrer Bausteine.

## 5. Beitragsfreistellung

Auf Verlangen wird die Versicherung beitragsfrei gestellt. Die
beitragsfreie Versicherungssumme wird je Baustein zum letzten Jahrestag
des Versicherungsbeginns ermittelt (Anhang B) und ab diesem Zeitpunkt
fest geführt.

## 6. Herabsetzung der Beiträge (Teilkündigung)

Verlangt der Versicherungsnehmer eine Herabsetzung des Beitrags, wird
die Grundversicherung anteilig gekündigt: Die Versicherungssumme der
Grundversicherung wird auf den fortgeführten Anteil herabgesetzt, und
das freiwerdende Deckungskapital wird nach Abzug des anteiligen Abzugs
gemäß Ziffer 4 AUSGEZAHLT. Planmäßige Erhöhungen bleiben von der
Herabsetzung unberührt; das Recht auf künftige Erhöhungen bleibt
bestehen.

## Anhang A: Zusammenstellung der Bezeichnungen und Grundformeln

Die Wertermittlung erfolgt nach der Kommutationsmethode. Ausgehend von
der jeweiligen Sterbetafel q(x) und dem Rechnungszins i mit v = 1/(1+i)
werden gebildet (RUNDEN bezeichnet die kaufmännische Rundung auf
16 Nachkommastellen; Höchstalter omega = 123):

l(0) = 1.000.000;  l(x+1) = RUNDEN( l(x) * (1 - q(x)) );
T(x) = RUNDEN( l(x) - l(x+1) )

D(x) = RUNDEN( l(x) * v^x );  C(x) = RUNDEN( T(x) * v^(x+1) )

N(x) = Summe von j=1 bis omega-x über D(x+j)

M(x) = Summe von j=0 bis omega-x über C(x+j)

## Anhang B: Barwerte und Beitragssatz

Temporäre vorschüssige Rente (jährlich): ax:n = ( N(x) - N(x+n) ) / D(x).
Bei k Zahlungen im Jahr vermindert um das Abzugsglied
AG(k) * ( 1 - D(x+n)/D(x) ) mit
AG(k) = (1+i)/k * Summe( (s/k) / (1 + (s/k)*i) ) für s = 0, ..., k-1.

Todesfallbarwert: nAx = ( M(x) - M(x+n) ) / D(x);
Erlebensfallbarwert: nEx = D(x+n) / D(x).

Beitragssatz je Einheit Versicherungssumme:
B(x,t) = ( nAx + nEx + gamma1 * ax:t + gamma2 * (ax:n - ax:t) )
/ ( (1 - beta1) * ax:t - alpha * t ).
