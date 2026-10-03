# Pfefferminzia Lebensversicherung

## Festlegung zum Tarifplan der Migration — Kapitallebensversicherung KLV TG2015 (Baldrian): Formfunktion und Fenster der Korrekturschicht

Fassung 1 — Festgelegt von der Regie in der Rolle mensch/aktuariat unter Mandat (Simulation), Datum 2026-10-02

Diese Festlegung ist ein Dokument der Pfefferminzia Lebensversicherung. Sie bindet die PLV bei der Fuehrung des uebernommenen Bestands, nicht die abgebende Gesellschaft, und ist keine Aussage der Baldrian. Sie wird erst mit der Festlegung durch den Verantwortlichen Aktuar wirksam.

## 1. Gegenstand
Beim Uebernehmen eines Bestands kann der Wert, den die PLV nach dem Tarifwerk rechnet, am Uebernahmezeitpunkt von dem gelieferten Deckungskapital abweichen. Diesen Unterschied traegt eine Korrekturschicht ueber die Restlaufzeit ab (Grundsatzdokumentation 9.9). Diese Festlegung bestimmt, **wie der Unterschied ueber die Restlaufzeit verteilt wird (Formfunktion)** und **ob dafuer ein festes Fenster in Jahren gilt (Fenster)**, fuer die Tarifgeneration KLV TG2015 aller Bestandsgruppen (Einzel, Kollektiv, Haus) und beider Risikoklassen (Nichtraucher, Raucher).

## 2. Grundlagen
- Auskunft Nr. 3 der Baldrian: Die Bestandsfuehrung bewertet nur am Vertragsjahrestag und nicht dazwischen; sie kennt keine Ausgleichsgroesse, kein Fenster; das gilt unveraendert fuer beitragsfreie Vertraege (je Baustein mit der fest gefuehrten beitragsfreien Summe, AVB Ziffer 5) und fuer Vertraege nach dem Ende der Beitragszahlungsdauer; die gelieferten Erwartungswerte sind nach diesem Verfahren gerechnet. Schriftlich festgelegt ist laut Baldrian nur Mitteilung 143, Fassung Januar 2015, Abschnitt 6; eine Dienstanweisung liegt der Baldrian nicht vor.
- Grundsatzdokumentation 9.9 (Formfunktion), 9.10 (Schutzregeln) und 10 Nr. 9 (Ausgestaltung der Korrekturmathematik migrierter Produkte).
- Vorabrechnung der PLV an der Lieferung (Pruefung der Abnahmen mit sieben Varianten, siehe Abschnitt 5).

## 3. Entscheid 1 — Formfunktion
**Festgelegt:** Die Formfunktion ist **proportional zur Basis** (`proportional_zur_basis`): Der Unterschied wird ueber die Restlaufzeit im Verhaeltnis zum rechnerischen Verlauf des Deckungskapitals des jeweiligen Vertrags verteilt.

**Gruende.**
1. Sie ist in allen Erlebenszustaenden definiert — beitragspflichtig, beitragsfrei (hier 160 Vertraege) und nach Ende der Beitragszahlungsdauer; die Anforderung nach 9.9 verlangt genau das.
2. Sie ist glatt und folgt dem Verlauf, den das Tarifwerk fuer den Vertrag selbst rechnet; sie fuehrt keine zusaetzliche Annahme ein.
3. Die abgebende Gesellschaft bewertet nur an Jahrestagen und kennt keine eigene Verteilungsregel (Auskunft Nr. 3, Punkte 1 und 2). Es gibt kein Verfahren der Baldrian, dem die PLV folgen oder das sie nachbilden muesste; die Wahl ist deshalb eine Konvention der PLV, nicht eine Nachbildung der Quelle.
4. Sie ist die Vorgabe der Grundsatzdokumentation (9.9, Kandidat 1).

**Verworfene Alternativen.**
- *Konstantes Fenster ueber n Jahre* (9.9, Kandidat 2): am leichtesten zu erklaeren, aber ohne Vorbild bei der Quelle und ohne Beleg fuer irgendein n; jedes n waere eine freie Setzung. Bei kurzer Restlaufzeit ungeeignet (9.9).
- *Beitragsproportionale Form* (9.9, Kandidat 3): nur zulaessig mit einer Fortsetzungsregel fuer beitragsfreie Zustaende; im Bestand sind 160 Vertraege beitragsfrei und viele nach Beitragsende, die Form waere fuer sie nicht von selbst definiert. Zudem nicht Teil des Vokabulars des Tarifplans.
- *Kalibrierung nach kleinsten Quadraten* gegen Stuetzstellen der Quelle (9.9, optional): Die Baldrian fuehrt zwischen den Jahrestagen keine Werte (Auskunft Nr. 3); es gibt keinen Verlauf zwischen den Jahrestagen, gegen den kalibriert werden koennte, und die gelieferten Erwartungswerte sind nach Auskunft Nr. 3 am Jahrestag gerechnet.

## 4. Entscheid 2 — Fenster
**Festgelegt:** **Kein Fenster.** Ein Fenster in Jahren gilt nur zur Formfunktion „konstantes Fenster“; zur Formfunktion „proportional zur Basis“ wird keines angegeben.

**Gruende.** Die Baldrian kennt kein Fenster (Auskunft Nr. 3, Punkt 3, fuer alle Bestandsgruppen und Risikoklassen gleich). Ein Fenster haette keine Grundlage, die die PLV nennen koennte; die Zahl waere erfunden. Mit der Formfunktion „proportional zur Basis“ entfaellt die Frage.

**Verworfene Alternative.** Ein Fenster von beispielsweise 5 oder 10 Jahren: haette dieselben Maengel wie oben; die Vorabrechnung zeigt zudem keinen Nutzen (Abschnitt 5).

## 5. Befunde der Vorabrechnung (Beleg, nicht Begruendung der Wahl)
Die PLV hat die Abnahmen (Stichtagstest, Verlaufstest, Geschaeftsvorfalltest) mit der Formfunktion „proportional zur Basis“ und mit einem festen Fenster von 1, 2, 3, 5, 10 und 20 Jahren vorab gerechnet. In **jeder** der sieben Varianten bestehen alle gezogenen Vertraege (100 von 100, 100 von 100, 166 von 166). Die Korrekturschicht der Lieferung traegt nur Cent: je Vertrag hoechstens 0,02 EUR, Summe ueber alle 834 Vertraege −0,14 EUR. Die groessten Abweichungen an den Pruefpunkten liegen bei 0,022 EUR (Stichtagstest), 0,021 EUR (Verlaufstest) und zwischen 0,010 und 0,020 EUR (Geschaeftsvorfalltest) gegen Toleranzen von 0,05 EUR bzw. 1,00 EUR beim Verlaufstest. Die Messung bindet die Wahl nicht; es gibt nichts Nennenswertes zu verteilen. Gilt der Bestand spaeter mit einer groesseren Abweichung, bleibt die Wahl gleich.

## 6. Was diese Festlegung nicht regelt
Die Grundsatzdokumentation (10 Nr. 9) nennt fuer migrierte Produkte weitere Teile der Ausgestaltung. Sie sind **nicht** Gegenstand dieser Festlegung:
- Uebergangsklassifikation, Ankerliste mit Haertegraden, Schutzregeln (Untergrenzen), eine Ausbuchungsregel fuer kurze Restlaufzeiten und der Testfallkatalog bleiben offen oder entfallen. Wegen der kleinen Abweichung (Cent) ist denkbar, dass sie entfallen oder in verkuerzter Form gezeichnet werden; das ist nicht entschieden.
- Der Pflichtschritt „Ausgestaltung des migrierten Tarifplans“ vor der Migrationsabnahme (A-M4) wird vom Verantwortlichen Aktuar entschieden und gezeichnet. Diese Festlegung nimmt ihm den Schritt nicht ab.
- Behandlung eines etwaigen positiven Rests (Ergebnisverwendung, Ueberschussbeteiligung) ist Unternehmensentscheidung (9.10) und hier nicht geregelt.

## 7. Fundstellen fuer die Uebernahme in die Ausgestaltung (A-Box)
| Merkmal | Wert | Fundstelle in diesem Dokument | Konfidenz |
|---|---|---|---|
| quellverfahren.formfunktion | proportional_zur_basis | Abschnitt 3, „Festgelegt“ | 1,0 (Festlegung, keine Auslegung) |
| quellverfahren.fenster | kein Wert (nicht anzugeben, da die Formfunktion kein Fenster hat) | Abschnitt 4, „Festgelegt“ | — |
Der Name der Quelle der Aussage ist die Pfefferminzia Lebensversicherung (Festlegung des Verantwortlichen Aktuars), nicht die Baldrian.

## Zeichnung
Festgelegt von der Regie in der Rolle mensch/aktuariat unter Mandat (Simulation), Datum 2026-10-02
