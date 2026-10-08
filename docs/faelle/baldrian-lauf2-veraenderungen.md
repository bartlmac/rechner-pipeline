# Was sich durch die Übernahme verändert hat (Baldrian KLV TG2015, Lauf 2)

Pfefferminzia Lebensversicherung — Programm Bestandsmigration.
Begleitdokument zum Abschlussbericht des zweiten Migrationslaufs:
was die Übernahme am Tarifwerk-Verständnis, am Rechenkern, an den
Prüfstrecken und an den fachlichen Entscheidungen verändert hat.
Jede Aussage trägt ihren Beleg; die Systemarbeit in Zahlen misst der
Umbaubericht des Falls.

## 1 Tarifwerks-Ausgestaltung: der Zieltarif blieb, die Quell-Ausgestaltung kam hinzu

Die wichtigste Veränderung ist eine, die bewusst nicht stattfand:
Der Tarifplan der Pfefferminzia wurde durch die Übernahme nicht
umgebaut. Der übernommene Bestand behält seine eigene
Bedingungswelt — sie wird seit Lauf 2 als **Ausgestaltung des
migrierten Tarifplans** je Lieferung geführt und im Rechenwerk als
benannte Eigenschaft der Lieferung parametriert; die Vorgabe jedes
Schalters ist das bisherige Verhalten der Pfefferminzia. Festgestellt
wurde je Eigenschaft, nie unterstellt:

| Gegenstand | vor Lauf 2 | nach Lauf 2 | Grund und Beleg |
|---|---|---|---|
| Beitragsformel dynamischer Erhöhungen | Stückkosten verbleiben auf der Grundsumme (Regel der ersten Lieferung) | volle Beitragsformel je Erhöhungsbaustein, wählbar je Lieferung | Bedingungswerk Ziffer 3; belegt auf 2 Cent am Referenzvertrag |
| Stornoabzug | vertragsweit erhoben | Mindest-/Hoechstbetrag je Baustein, Rückkaufswert als Summe der Baustein-Rückkaufswerte | Bedingungswerk Ziffer 4; Residuenmuster in Grenzen-Vielfachen |
| Herabsetzung | anteilige, verlustfreie Vertragsteilung bzw. Verfahren mit Abzug | drittes Verfahren: Teilkündigung der Grundversicherung MIT Auszahlung, zustandslose Fortführung | Bedingungswerk Ziffer 6; A-M3-Befund des Laufs |
| Deckungskapital-Konvention | kalendertägliche Interpolation | Stand zum letzten Vertragsjahrestag, wählbar je Lieferung | Mitteilung Nr. 143 Abschnitt 6 |
| Dynamiksatz der Vorgeschichte | nicht geführt | einheitlich 5 Prozent je Erhöhungstermin, als registrierte Auskunft | Auskunft Nr. 1 der abgebenden Gesellschaft |
| Kalkulationsbasis | geschlechtsabhängige Tafeln | Unisex-Mischtafel 70/30 für die gesamte Generation | implizit in der Beispielrechnung der Quelle; ohne die Feststellung wichen 251 von 616 Referenzwerten systematisch ab |

Die einzige Änderung am Zieltarif selbst — die anteilige Herabsetzung
geschichteter Verträge — war eine eigene Zusage der Pfefferminzia
und lag vor dem Lauf (Tarifplan klv.md, Abschnitt 7.1).

## 2 Rechenkern: welche Fähigkeit fehlte, was er jetzt kann

Der Kern ging mit Version 3.1.0 in den Lauf und mit 3.4.0 aus der
Nacharbeit; jeder Sprung ist im Versionsprotokoll des Kerns fachlich
begründet. In Fähigkeiten gesprochen:

- **Es fehlte** die volle Beitragsformel je Erhöhungsbaustein —
  **jetzt** rechnet jede Scheibe wahlweise mit allen
  Kostenbestandteilen (3.2.0).
- **Es fehlte** der Stornoabzug je Baustein — **jetzt** klemmt der
  Abzug wahlweise je Grund- und Erhöhungsbaustein einzeln, der
  Rückkaufswert ist die Summe der Baustein-Werte (3.3.0).
- **Es fehlte** die Teilkündigung mit Auszahlung — **jetzt** ist sie
  das dritte Herabsetzungs-Verfahren: der gekündigte Anteil der
  Grundversicherung verlässt den Vertrag, der Rest läuft zustandslos
  weiter; seit 3.4.0 auch im beitragsfreien Nachlauf definiert.

Nicht zu diesem Fall gehört die Regel zum Abschlusskostenrest nach
einer Herabsetzung (Kern 3.8.0): Sie behebt einen Fehler im eigenen
Kern, der vor dem Fall entstand, und bleibt bei einer Wiederholung des
Falls stehen. Für die Teilkündigung gilt dieselbe Regel (klv.md 13).
- **Es fehlte** eine saubere Terminalbedingung der Korrekturschicht —
  **jetzt** endet die Amortisation am Ablauf (Zahlungsjahre bis n-1),
  statt in das Ablaufjahr hineinzurechnen.
- **Es fehlte** die Verankerung von Zustands-Welten — **jetzt**
  verankern beitragsfreie, herabgesetzte und Serien-Verträge auf dem
  geführten Wert ihrer tatsächlichen Welt, nicht auf dem
  Stamm-Modellpunkt.

Alle bestehenden Rechenwerte blieben dabei unverändert: Die neuen
Fähigkeiten sind Parametrierungen mit dem alten Verhalten als
Vorgabe, keine Umbauten — belegt durch die unangetasteten
Charakterisierungs-Referenzwerte des Kerns und den Umbaubericht.

## 3 Prüfstrecken: was neu gebaut oder verändert werden musste

- **Toleranzen aus der Fehlerfortpflanzung**: Jeder je für sich
  gerundete Baustein eines Lieferwerts erweitert die zulässige
  Abweichung um einen halben Cent — dieselbe Regel in Stichtagstest,
  Migrationscontrolling und der unabhängigen Nachrechnung des
  Abnahmeberichts; Pauschaltoleranzen gibt es nicht mehr.
- **Jahrestags-Konvention des Deckungskapital-Vergleichs**: Der
  Vergleich misst wahlweise am Vertragsjahrestag — vorher deutete ein
  kalendertäglicher Vergleich bis zu elf Monate Reservezuwachs als
  Befund.
- **Serien-Rekonstruktion mit Kandidaten-Bestimmung**: Offene
  Herabsetzungsanteile werden über die Beitrags- bzw. Ankergleichung
  aus einer belegten Kandidatenmenge bestimmt, mit
  Plausibilitäts-Korridoren, Identifizierbarkeits-Wache gegen
  Rundungsphantome und ausgewiesener Anteils-Unerheblichkeit.
- **Korrekturschicht bis in das Controlling**: Ein eigener
  Schichtbeleg-Producer verankert jede Police und weist Residuen aus;
  das Migrationscontrolling bewertet die Schicht universal — genau
  diese zweite, unabhängige Anwendung deckte zwei sich gegenseitig
  verdeckende Fehler auf, die der aktuarielle Test allein nicht sehen
  konnte.
- **Zeichnungsordnung durchgezogen**: Gates und Diskrepanz-Entscheide
  vollzieht die zeichnende Rolle mit mitsigniertem Snapshot; auch die
  vierzehn Einzelentscheide der Quellenauswertung tragen Zeichnung.
- **Ehrlicher Ausweis statt stiller Zustände**: Prüfflücken,
  abgelehnte Anträge und nicht anwendbare Plausibilisierungen stehen
  benannt im Ergebnis; ein Vergleich, der nicht gerechnet werden kann,
  ist eine ausgewiesene Lücke, keine Zahl.
- **Prüfumfang**: 1479 Tests vor dem Lauf, 1517 nach den 23
  Korrekturen, 1534 nach Review-Nacharbeit und dem eingefrorenen
  Ende-zu-Ende-Fixture des Laufs.

## 4 Fachliche Einzelentscheide und Plausibilisierungen

Kein Wert wurde geraten; jede Festlegung ist entschieden, gezeichnet
oder als dokumentierte Lesart mit Auflage geführt:

| Entscheid | Inhalt | Entscheider | Beleg |
|---|---|---|---|
| Vierzehn Diskrepanz-Einzelentscheide der Quellenauswertung | drei Typen über sechs Tarifzellen: Rechnungszins 1,25 % statt des Rechner-Arbeitsstands 1,75 % (6), Tafel-Basisname mit separater Unisex-Mischung statt doppelter Verankerung (6), Verwaltungskostensatz der Bestandsgruppe Haus 0,01 statt 0,0 (2) | Verantwortlicher Aktuar, je Entscheid gezeichnet | A-Box-Journal des Falls; Gate A-Q1, Snapshot fd793260 |
| Unisex-Feststellung | Mischtafel 70/30 für die Generation | Verantwortlicher Aktuar | Golden Master 616/616 exakt; 251/616-Abweichungsbeleg ohne die Feststellung |
| Reichweite der Rückkaufswert-Plausibilisierung | Nicht auf dynamische Verträge ausgeweitet — der Beleg der Quelle trägt nur die Herabsetzungs-Vorfälle | Verantwortlicher Aktuar | Fall-Chronik der Tarifplan-Ausgestaltung |
| Herabsetzungsanteile der Vorgeschichte | keine Punktschätzung: Beitragsgleichung für beitragszahlende, Ankerwert für beitragsfreie Serien, Unerheblichkeits-Ausweis wo die Ist-Welt den Anteil nicht braucht | Verantwortlicher Aktuar | Abschlussbericht Abschnitt 5; Auskünfte Nr. 2 und 4 |
| Arbeits-Lesart f = 0,60 für die Policen 7000679 und 7000396 | bei nachgewiesener Bewertungsinvarianz aller Prüfpunkte; mit Falsifizierbarkeits-Auflage: der erste Verlaufspunkt vor dem Beitragsende ist dort zu rechnen und zu würdigen | Verantwortlicher Aktuar, dokumentierte Lesart | Tarifplan-Ausgestaltung des Falls, Testfallkatalog |
| Verfahrenswahl der Herabsetzung | Teilkündigungs-Semantik der Quelle statt der Verfahren des Zielsystems — als Eigenschaft des Falls, nicht des Tarifplans | Verantwortlicher Aktuar | Nachtrag der Tarifplan-Ausgestaltung |

Zusammen mit dem Abschlussbericht (Ergebnis und Methodik) und dem
Umbaubericht (Umfang der Systemarbeit in Zahlen) ergibt dieses
Dokument das vollständige Bild: Was die Übernahme ergab, wie
geprüft wurde — und was sich dafür am System und am Verständnis
des Quell-Tarifwerks ändern musste.
