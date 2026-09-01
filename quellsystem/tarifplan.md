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

```{=typst}
#set par(leading: 0.65em, justify: false)
#set text(hyphenate: false)
#show par: set block(spacing: 1.65em)
#show heading: set text(size: 9.5pt)
#show heading: set block(above: 1.65em, below: 1.65em)
#show raw.where(block: true): set block(fill: none, inset: 0em)
#show raw: set text(size: 9.5pt)
```

# Tarifplan KLV TG2015 (Mitteilung 143)

Kapitallebensversicherung nach Tarifwerk KLV TG2015 — Baldrian
Lebensversicherung a. G. Mitteilung Nr. 143, Fassung Januar 2015.

Dieser Tarifplan enthält die versicherungsmathematischen
Rechnungsgrundlagen, Kostensätze und Rechenvorschriften des Tarifwerks.
Die vertraglichen Zusagen ergeben sich aus den Allgemeinen
Versicherungsbedingungen (AVB) zum Tarifwerk TG2015.

## 1. Rechnungsgrundlagen

Der Rechnungszins beträgt 1,25 %. Die Sterblichkeit richtet sich nach
dem Raucherstatus der versicherten Person:

| Raucherstatus | Sterbetafel |
|---|---|
| Nichtraucher | DAV2008_T_NR_U70 |
| Raucher | DAV2008_T_R_U70 |

Das Höchstalter der Ausscheideordnung ist omega = 123, die Wurzel
l(0) = 1.000.000. Die Abschlusskosten werden über die ersten fünf
Versicherungsjahre getilgt (Zillmerdauer). In der flexiblen
Abrufphase — ab Alter 60 bei einer Restlaufzeit von höchstens fünf
Jahren — entfällt der Abzug nach Abschnitt 2.

## 2. Kostensätze und Abzüge je Bestandsgruppe

Die Kostensätze hängen nur von der Bestandsgruppe ab; der
Raucherstatus bestimmt allein die Sterbetafel.

Bestandsgruppe Einzel:

| Größe | Wert |
|---|---|
| Abschlusskosten alpha (der Beitragssumme) | 25 Promille |
| Inkassokosten beta1 (des Beitrags) | 3 % |
| Verwaltung gamma1 (Beitragszahlungsdauer) | 1 Promille |
| Verwaltung gamma2 (beitragsfreie Jahre) | 1,25 Promille |
| Verwaltung gamma3 (nach Beitragsfreistellung) | 2,5 Promille |
| Stückkosten je Jahr | 12,00 EUR |
| Abzug bei Rückkauf (der Differenz VS - DK) | 0,5 % |
| Abzug mindestens | 50,00 EUR |
| Abzug höchstens | 200,00 EUR |
| Ratenzuschlag halbjährlich | 2 % |
| Ratenzuschlag vierteljährlich | 3 % |
| Ratenzuschlag monatlich | 5 % |

Bestandsgruppe Kollektiv:

| Größe | Wert |
|---|---|
| Abschlusskosten alpha (der Beitragssumme) | 15 Promille |
| Inkassokosten beta1 (des Beitrags) | 1,5 % |
| Verwaltung gamma1 (Beitragszahlungsdauer) | 0,8 Promille |
| Verwaltung gamma2 (beitragsfreie Jahre) | 1 Promille |
| Verwaltung gamma3 (nach Beitragsfreistellung) | 2,5 Promille |
| Stückkosten je Jahr | 12,00 EUR |
| Abzug bei Rückkauf (der Differenz VS - DK) | 0,5 % |
| Abzug mindestens | 50,00 EUR |
| Abzug höchstens | 200,00 EUR |
| Ratenzuschlag halbjährlich | 1 % |
| Ratenzuschlag vierteljährlich | 1,5 % |
| Ratenzuschlag monatlich | 2,5 % |

Bestandsgruppe Haus:

| Größe | Wert |
|---|---|
| Abschlusskosten alpha (der Beitragssumme) | 0 Promille |
| Inkassokosten beta1 (des Beitrags) | 1 % |
| Verwaltung gamma1 (Beitragszahlungsdauer) | 0,8 Promille |
| Verwaltung gamma2 (beitragsfreie Jahre) | 1 Promille |
| Verwaltung gamma3 (nach Beitragsfreistellung) | 2,5 Promille |
| Stückkosten je Jahr | 0,00 EUR |
| Abzug bei Rückkauf | entfällt |
| Ratenzuschlag | entfällt |

## 3. Zusammenstellung der Bezeichnungen und Grundformeln

Die Wertermittlung erfolgt nach der Kommutationsmethode. Ausgehend von
der jeweiligen Sterbetafel q(x) und dem Rechnungszins i mit
v = 1/(1+i) werden gebildet:

```
l(0) = 1.000.000;   l(x+1) = l(x) * (1 - q(x));   T(x) = l(x) - l(x+1)

D(x) = l(x) * v^x;   C(x) = T(x) * v^(x+1)

N(x) = Summe von j=1 bis omega-x über D(x+j)

M(x) = Summe von j=0 bis omega-x über C(x+j)
```

## 4. Barwerte und Beitragssatz

Temporäre vorschüssige Rente (jährliche Zahlung) und
Leistungsbarwerte:

```
             N(x) - N(x+n)                M(x) - M(x+n)
ax:n    =   ---------------  ;   nAx  =  ---------------
                 D(x)                         D(x)

             D(x+n)
nEx     =   --------
              D(x)
```

Bei k Zahlungen im Jahr vermindert sich der Rentenbarwert um das
Abzugsglied AG(k) * ( 1 - D(x+n)/D(x) ) mit

```
            1 + i                    s/k
AG(k)  =   ------- * Summe ( ----------------- )   fuer s = 0, ..., k-1
              k               1 + (s/k) * i
```

Beitragssatz je Einheit Versicherungssumme:

```
            nAx + nEx + gamma1 * ax:t + gamma2 * (ax:n - ax:t)
B(x,t)  =  ----------------------------------------------------
                    (1 - beta1) * ax:t - alpha * t
```

## 5. Rundung

Die Werte der Ausscheideordnung und die Kommutationszahlen werden in
jedem Rechenschritt kaufmännisch auf 16 Nachkommastellen gerundet
(halb weg von null). Barwerte und Beitragssätze bleiben in der
Rechenkette ungerundet. Beträge in Euro — Beiträge, Deckungskapitale,
Abzüge, Rückkaufswerte und beitragsfreie Summen — werden erst in der
Ausgabe kaufmännisch auf den Cent gerundet; gebucht wird centgenau.
