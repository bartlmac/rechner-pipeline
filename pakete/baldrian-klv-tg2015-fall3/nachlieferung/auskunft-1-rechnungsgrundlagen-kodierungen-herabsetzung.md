# Auskunftsschreiben Nr. 1 — Rechnungsgrundlagen, Dynamiksatz, Herabsetzung, STORNO_KZ, Kodierungen

Betreff: Bestandsuebertragung KLV TG2015 an die Pfefferminzia Lebensversicherung — Auskunft zu den Rueckfragen 01 bis 05

Wir beantworten die Rueckfragen 01 bis 05 gebuendelt in einem Schreiben.

## Zu Rueckfrage 01 — Tarifzins und Inkassokosten Haus

Frage der PLV: Mit welchem Rechnungszins ist der Bestand kalkuliert; gilt fuer Haus beta1 = 0,01 oder 0; welches Dokument ist massgeblich; beruhen die Erwartungswerte darauf.

Antwort:

| Groesse | Wert | Massgeblich |
|---|---|---|
| Rechnungszins (alle sechs Zellen) | 0,0125 (1,25 %) | Mitteilung 143, Abschnitt 1 |
| beta1 Bestandsgruppe Haus | 0,01 (10 Promille) | Mitteilung 143, Abschnitt 2 |

- Massgeblich ist die Mitteilung 143, Fassung Januar 2015. Die Werte der Tarifrechner-Arbeitsmappe (Zins 0,0175; beta1 Haus = 0) sind in Einzelstaenden veraltet bzw. fehlen. Die Mappe ist nicht fortgeschrieben worden, und eine korrigierte Mappe wird nicht nachgeliefert.
- Die gelieferten Deckungskapitalien (DECKKAP), Jahresbeitraege (JBRUTTO) und alle Erwartungswerte (Stichtag, Verlauf, Geschaeftsvorfaelle) sind mit 1,25 % und beta1 Haus = 0,01 gerechnet; das Rechenwerk der Bestandsfuehrung fuehrt diese Werte.

## Zu Rueckfrage 02 — Dynamiksatz und Verfahren bei Absetzungen

Antwort:

1. Der Satz betraegt einheitlich 5 % der Gesamtversicherungssumme je Erhoehungstermin, 2016 bis 2025 unveraendert. Das Rechenwerk fuehrt einen einzigen Satz, keine Staffelung und keine Unterscheidung nach Bestandsgruppen. Der Satz ist Fuehrungspraxis; die AVB (Ziffer 3) und der Tarifplan nennen keinen Zahlwert.
2. Absetzungen (GEVO = RED) sind Teilkuendigungen der Grundversicherung mit Auszahlung (AVB Ziffer 6): Auszahlung = (Deckungskapital der Grundscheibe abzueglich anteiliger Abzug nach AVB Ziffer 4) mal (1 minus fortgefuehrter Anteil f). Die Grundsumme sinkt auf f, planmaessige Erhoehungen bleiben unberuehrt, der Vertrag bleibt beitragspflichtig. Die Angabe lautet daher fuer alle Absetzungen: teilkuendigung. Weder "prospektiv" noch "mit_abzug" im Sinne einer Herabsetzung bei erhaltenem Deckungskapital kommt vor.

## Zu Rueckfrage 03 — STORNO_KZ

Antwort:

| Wert | Bedeutung | Wirkung |
|---|---|---|
| R | Beitragsrueckstand (Mahnverfahren laeuft) | keine Rechenwirkung |
| S | Sperrvermerk (z. B. Abtretung oder Pfaendung; Auszahlungen gesperrt) | keine Rechenwirkung; der Vertrag laeuft wirtschaftlich normal weiter |
| leer | ohne Kennzeichen | — |

- Die Spalte ist ein verwaltungsinternes Kennzeichen. Gekennzeichnete Vertraege stehen mit normalen Werten in beiden Abzuegen (Stichtage 01.01.2026 und 01.01.2027) und bleiben im uebertragenen Bestand.
- Sie hatten im Migrationsjahr keine Geschaeftsvorfaelle und stehen deshalb nicht im GeVo-Protokoll 2026. Der Rueckgang von 834 auf 811 Zeilen geht damit nicht auf gekennzeichnete Vertraege zurueck.

## Zu Rueckfrage 04 — fortgefuehrter Anteil bei Absetzungen

Antwort:

- Bezug (Frage 2): Der Anteil bezieht sich auf die Grundversicherung allein, nicht auf die Gesamtsumme einschliesslich der Erhoehungen (AVB Ziffer 6).
- Art (Frage 3): Alle Absetzungen sind Teilkuendigungen mit Auszahlung, keine Herabsetzungen bei erhaltenem Deckungskapital (siehe Rueckfrage 02).
- Anteile je Ereignis (Frage 1): Der Export der Vorgeschichte traegt keine Betraege und keine Parameter; die Einzelwerte sind aus der Lieferung nicht ableitbar. Die Herabsetzungspraxis kennt drei fortgefuehrte Anteile: 0,50, 0,60 und 0,75. Eine Tabelle fuer 38 Policen bzw. 40 Ereignisse koennen wir neben dem Tagesgeschaeft nicht leisten.
- Wir bitten um Eingrenzung: Einzelwerte koennen wir fuer hoechstens zehn namentlich genannte Policen pruefen, mit Begruendung je Police, warum der Wert aus der Lieferung nicht ableitbar ist. Bis dahin geben wir keine Einzelwerte heraus.

## Zu Rueckfrage 05 — Kodierungen, Beitragsfreiheit, Erhoehungs-Bausteine

Antwort:

1. Kodierungen: GESCHL M = maennlich, W = weiblich. Eine Rechenwirkung hat das Geschlecht nicht, denn die Sterbetafel richtet sich allein nach der Risikoklasse (Mitteilung 143, Abschnitt 1). RK NR = Nichtraucher, R = Raucher. BGRP E = Einzel, K = Kollektiv, H = Haus; die Lesart stimmt. Das Eintrittsalter ist die Differenz der Kalenderjahre von Versicherungsbeginn und Geburt (Mitteilung 143, Abschnitt 3): bestaetigt.
2. VTG_STATUS: BFR bedeutet beitragsfrei gestellt und fuehrt immer zu JBRUTTO = 0,00 (Mitteilung 143, Abschnitt 6); im Abzug 01.01.2026 trifft das auf alle 160 BFR-Zeilen zu. Die Umkehrung gilt nicht: JBRUTTO = 0,00 steht auch bei AKT-Vertraegen nach Ablauf der Beitragszahlungsdauer. Die Beitragsfreistellung entspricht dem Vorfall PEX; sie gilt ab dessen Datum, und die Vorgeschichte bis zum Stichtag traegt PEX. Abgleich Abzug 01.01.2026 mit baldrian_gevo_metadaten.csv: alle 160 BFR-Vertraege tragen ein PEX, kein AKT-Vertrag traegt eines.
3. ERLSUMME bei beitragsfreien Vertraegen ist die beitragsfreie Summe (Mitteilung 143, Abschnitt 6), nicht die urspruengliche Versicherungssumme. Sie wird je Baustein zum letzten Jahrestag des Versicherungsbeginns ermittelt und fest gefuehrt (AVB Ziffer 5); geliefert wird die Summe ueber die Bausteine.
4. Ja: Jede planmaessige Erhoehung wird als eigenstaendiger Baustein mit ihrem eigenen Alter, ihrer eigenen Rest-Versicherungs- und Rest-Beitragszahlungsdauer nach der vollen Beitragssatzformel gerechnet (Mitteilung 143, Abschnitt 4; Rechenwerk der Bestandsfuehrung). Zu den Kostenanteilen: gamma1 ist die Verwaltungskostenkomponente fuer die Beitragszahlungsdauer, keine Abschlusskosten. Die Abschlusskosten sind alpha. Die Formel enthaelt alpha, beta1, gamma1 und gamma2 und gilt je Baustein unveraendert. Die AVB (Ziffer 3) nennen die Kostensaetze nicht, sie verweisen auf den Tarifplan. Weitergehende Rechenvorschriften fuer Bausteine kennt die Quelle nicht.

## Grundlagen

- Mitteilung 143, Fassung Januar 2015, Abschnitte 1 bis 4 und 6 (Tarifplan).
- Allgemeine Versicherungsbedingungen, Fassung Januar 2015, Ziffern 3 bis 6.
- Rechenwerk der Bestandsfuehrung (Tarifwerk, Beitragsrechnung, Dynamik, Herabsetzung, Bestandsabzug).
- Auskunft der Bestandsfuehrung zu Tarifrechner-Arbeitsmappe, STORNO_KZ, Dynamiksatz, Herabsetzungsverfahren und Herabsetzungsanteilen.
- Bestandsabzug 01.01.2026, Spalten VTG_STATUS und JBRUTTO.

Datum: 2026-10-02

Baldrian Lebensversicherung a. G., Bestandsfuehrung
