# Auskunftsschreiben Nr. 5 — Nachtrag zur Lieferung: Erwartungswerte mit erweiterter Stichprobe

Betreff: Bestandsuebertragung KLV TG2015 an die Pfefferminzia Lebensversicherung — Antwort auf Rueckfrage 09, Nachtrag zur Lieferung

## Frage der PLV

Ein neuer, vollstaendiger Lieferlauf, dessen Stichprobe der Erwartungswerte die Policen 7000523, 7000533, 7000539, 7000676, 7000722, 7000754, 7000910 und 7000994 einschliesst, mit Lieferschein und Pruefsummen, Angabe der unveraenderten und der geaenderten Dateien, Erwartungswerte in den bisherigen Formaten.

## Antwort

Wir liefern. Die Bestandsfuehrung hat einen zweiten Lieferlauf mit erweiterter Stichprobe gefahren. Die acht Policen sind darin als Pflichtziehung enthalten. Die Werte der acht Policen stammen aus diesem Lauf, nicht aus einer Nachberechnung ausserhalb der Lieferung; Auskunftsschreiben Nr. 4 bleibt damit richtig.

### Lieferschein des Nachtrags

| Datei | SHA-256 |
|---|---|
| baldrian_erwartungswerte_stichprobe_lieferlauf2.json | e208aaaf93f1b20ff454fa827061fd8a2a89bf5143754be08aa7a040b9bd0bd6 |
| baldrian_erwartungswerte_stichtag_lieferlauf2.json | b8fe393a129f78108ec1600ac10c8202f0fd99c3515d42ca2554f18a81081d66 |
| baldrian_erwartungswerte_verlauf_lieferlauf2.json | f955351685c839477e7c59a9bc305fd2ebe0e82ad0090b313fce497751004cc9 |

Die Dateien tragen das Suffix `_lieferlauf2` und gelten als Nachtrag zur bisherigen Lieferung; die bisherigen Dateien bleiben im Eingang unveraendert. Fuer den Stichtagstest (A-M1) und den Verlaufstest (A-M2) gilt die erweiterte Stichprobe dieses Nachtrags.

### Was sich aendert und was nicht

- **Geaendert:** Stichprobe fuer A-M1 und A-M2: 108 statt 100 Vertraege, die acht Policen der Pflichtziehung kommen hinzu; entsprechend `baldrian_erwartungswerte_stichtag` und `baldrian_erwartungswerte_verlauf` mit 108 Vertraegen. Die Ziehung vor den Werten steht im Hinweis der Stichprobendatei; die Pflichtziehung ist dort benannt (Anlass Rueckfrage 09), ebenso benannt vor der Berechnung der Vergleichswerte.
- **Unveraendert fuer die bisherigen 100 Vertraege:** Die ersten 100 Policen der Stichprobe stehen in gleicher Reihenfolge; ihre Eintraege in den Erwartungswerten sind mit der bisherigen Lieferung inhaltsgleich. Saat, Schichtung (25 je Historientyp), Profil und Toleranzen sind unveraendert.
- **Byteidentisch zur bisherigen Lieferung, nicht erneut geliefert:** Bedingungswerk (AVB), Mitteilung 143, Tarifrechner-Arbeitsmappe, die beiden Bestandsabzuege (01.01.2026 und 01.01.2027), `baldrian_gevo_metadaten.csv`, `baldrian_gevo_protokoll_2026.csv`. Ein Bestandsabzug und eine GeVo-Datei aendern sich nicht; die Pruefsummen stehen im Lieferschein der bisherigen Lieferung.
- **Geschaeftsvorfalltest (A-M3):** unveraendert. Die Stichprobe ist dieselbe (Vollbestand, 166 Vorfaelle des Migrationsjahres); `baldrian_erwartungswerte_geschaeftsvorfaelle.json` wird deshalb nicht neu geliefert und gilt in der bisherigen Fassung weiter.

### Entstehung der Werte der acht Policen

Die Werte kommen aus demselben Rechenwerk und derselben Strecke wie der Bestandsabzug (Rechnungszins 1,25 %, Dynamik 5 %, Teilkuendigung auf der Grundversicherung mit dem fortgefuehrten Anteil der Kernverwaltung, Auskunftsschreiben Nr. 2). Zur Kontrolle: Der Punkt `uebernahme` stimmt fuer alle acht Policen mit dem DECKKAP des Bestandsabzugs 01.01.2026 ueberein. Die Zeitpunkte der Verlaufspunkte folgen dem Muster der bisherigen Datei (5 und 10 Jahre nach dem Uebernahmepunkt sowie am Ablauf, beschnitten auf die Restlaufzeit).

## Grundlagen

- Lieferlauf 2 der Bestandsfuehrung: drei Erwartungswerte-Dateien, Datei `baldrian_erwartungswerte_stichprobe_lieferlauf2.json` (Pflichtziehung, Ziehungshinweis).
- Lieferschein der bisherigen Lieferung (Pruefsummen der unveraenderten Dateien).
- Auskunftsschreiben Nr. 2 und Nr. 4.

Datum: 2026-10-02

Baldrian Lebensversicherung a. G., Bestandsfuehrung
