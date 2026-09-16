# Was sich durch die Uebernahme veraendert hat (Baldrian KLV TG2015, Lauf 2)

Pfefferminzia Lebensversicherung — Programm Bestandsmigration.
Begleitdokument zum Abschlussbericht des zweiten Migrationslaufs:
was die Uebernahme am Tarifwerk-Verstaendnis, am Rechenkern, an den
Pruefstrecken und an den fachlichen Entscheidungen veraendert hat.
Jede Aussage traegt ihren Beleg; die Systemarbeit in Zahlen misst der
Umbaubericht des Falls.

## 1 Tarifwerks-Ausgestaltung: der Zieltarif blieb, die Quell-Ausgestaltung kam hinzu

Die wichtigste Veraenderung ist eine, die bewusst NICHT stattfand:
Der Tarifplan der Pfefferminzia wurde durch die Uebernahme nicht
umgebaut. Der uebernommene Bestand behaelt seine eigene
Bedingungswelt — sie wird seit Lauf 2 als **Ausgestaltung des
migrierten Tarifplans** je Lieferung gefuehrt und im Rechenwerk als
benannte Eigenschaft der Lieferung parametriert; die Vorgabe jedes
Schalters ist das bisherige Verhalten der Pfefferminzia. Festgestellt
wurde je Eigenschaft, nie unterstellt:

| Gegenstand | vor Lauf 2 | nach Lauf 2 | Grund und Beleg |
|---|---|---|---|
| Beitragsformel dynamischer Erhoehungen | Stueckkosten verbleiben auf der Grundsumme (Regel der ersten Lieferung) | volle Beitragsformel je Erhoehungsbaustein, waehlbar je Lieferung | Bedingungswerk Ziffer 3; belegt auf 2 Cent am Referenzvertrag |
| Stornoabzug | vertragsweit erhoben | Mindest-/Hoechstbetrag je Baustein, Rueckkaufswert als Summe der Baustein-Rueckkaufswerte | Bedingungswerk Ziffer 4; Residuenmuster in Grenzen-Vielfachen |
| Herabsetzung | anteilige, verlustfreie Vertragsteilung bzw. Verfahren mit Abzug | drittes Verfahren: Teilkuendigung der Grundversicherung MIT Auszahlung, zustandslose Fortfuehrung | Bedingungswerk Ziffer 6; A-M3-Befund des Laufs |
| Deckungskapital-Konvention | kalendertaegliche Interpolation | Stand zum letzten Vertragsjahrestag, waehlbar je Lieferung | Mitteilung Nr. 143 Abschnitt 6 |
| Dynamiksatz der Vorgeschichte | nicht gefuehrt | einheitlich 5 Prozent je Erhoehungstermin, als registrierte Auskunft | Auskunft Nr. 1 der abgebenden Gesellschaft |
| Kalkulationsbasis | geschlechtsabhaengige Tafeln | Unisex-Mischtafel 70/30 fuer die gesamte Generation | implizit in der Beispielrechnung der Quelle; ohne die Feststellung wichen 251 von 616 Referenzwerten systematisch ab |

Die einzige Aenderung am Zieltarif selbst — die anteilige Herabsetzung
geschichteter Vertraege — war eine eigene Zusage der Pfefferminzia
und lag VOR dem Lauf (Tarifplan klv.md, Abschnitt 7.1).

## 2 Rechenkern: welche Faehigkeit fehlte, was er jetzt kann

Der Kern ging mit Version 3.1.0 in den Lauf und mit 3.4.0 aus der
Nacharbeit; jeder Sprung ist im Versionsprotokoll des Kerns fachlich
begruendet. In Faehigkeiten gesprochen:

- **Es fehlte** die volle Beitragsformel je Erhoehungsbaustein —
  **jetzt** rechnet jede Scheibe wahlweise mit allen
  Kostenbestandteilen (3.2.0).
- **Es fehlte** der Stornoabzug je Baustein — **jetzt** klemmt der
  Abzug wahlweise je Grund- und Erhoehungsbaustein einzeln, der
  Rueckkaufswert ist die Summe der Baustein-Werte (3.3.0).
- **Es fehlte** die Teilkuendigung mit Auszahlung — **jetzt** ist sie
  das dritte Herabsetzungs-Verfahren: der gekuendigte Anteil der
  Grundversicherung verlaesst den Vertrag, der Rest laeuft zustandslos
  weiter; seit 3.4.0 auch im beitragsfreien Nachlauf definiert.
- **Es fehlte** eine saubere Terminalbedingung der Korrekturschicht —
  **jetzt** endet die Amortisation am Ablauf (Zahlungsjahre bis n-1),
  statt in das Ablaufjahr hineinzurechnen.
- **Es fehlte** die Verankerung von Zustands-Welten — **jetzt**
  verankern beitragsfreie, herabgesetzte und Serien-Vertraege auf dem
  GEFUEHRTEN Wert ihrer tatsaechlichen Welt, nicht auf dem
  Stamm-Modellpunkt.

Alle bestehenden Rechenwerte blieben dabei unveraendert: Die neuen
Faehigkeiten sind Parametrierungen mit dem alten Verhalten als
Vorgabe, keine Umbauten — belegt durch die unangetasteten
Charakterisierungs-Referenzwerte des Kerns und den Umbaubericht.

## 3 Pruefstrecken: was neu gebaut oder veraendert werden musste

- **Toleranzen aus der Fehlerfortpflanzung**: Jeder je fuer sich
  gerundete Baustein eines Lieferwerts erweitert die zulaessige
  Abweichung um einen halben Cent — dieselbe Regel in Stichtagstest,
  Migrationscontrolling und der unabhaengigen Nachrechnung des
  Abnahmeberichts; Pauschaltoleranzen gibt es nicht mehr.
- **Jahrestags-Konvention des Deckungskapital-Vergleichs**: Der
  Vergleich misst wahlweise am Vertragsjahrestag — vorher deutete ein
  kalendertaeglicher Vergleich bis zu elf Monate Reservezuwachs als
  Befund.
- **Serien-Rekonstruktion mit Kandidaten-Bestimmung**: Offene
  Herabsetzungsanteile werden ueber die Beitrags- bzw. Ankergleichung
  aus einer belegten Kandidatenmenge bestimmt, mit
  Plausibilitaets-Korridoren, Identifizierbarkeits-Wache gegen
  Rundungsphantome und ausgewiesener Anteils-Unerheblichkeit.
- **Korrekturschicht bis in das Controlling**: Ein eigener
  Schichtbeleg-Producer verankert jede Police und weist Residuen aus;
  das Migrationscontrolling bewertet die Schicht universal — genau
  diese zweite, unabhaengige Anwendung deckte zwei sich gegenseitig
  verdeckende Fehler auf, die der aktuarielle Test allein nicht sehen
  konnte.
- **Zeichnungsordnung durchgezogen**: Gates und Diskrepanz-Entscheide
  vollzieht die zeichnende Rolle mit mitsigniertem Snapshot; auch die
  vierzehn Einzelentscheide der Quellenauswertung tragen Zeichnung.
- **Ehrlicher Ausweis statt stiller Zustaende**: Prueffluecken,
  abgelehnte Antraege und nicht anwendbare Plausibilisierungen stehen
  benannt im Ergebnis; ein Vergleich, der nicht gerechnet werden kann,
  ist eine ausgewiesene Luecke, keine Zahl.
- **Pruefumfang**: 1479 Tests vor dem Lauf, 1517 nach den 23
  Korrekturen, 1534 nach Review-Nacharbeit und dem eingefrorenen
  Ende-zu-Ende-Fixture des Laufs.

## 4 Fachliche Einzelentscheide und Plausibilisierungen

Kein Wert wurde geraten; jede Festlegung ist entschieden, gezeichnet
oder als dokumentierte Lesart mit Auflage gefuehrt:

| Entscheid | Inhalt | Entscheider | Beleg |
|---|---|---|---|
| Vierzehn Diskrepanz-Einzelentscheide der Quellenauswertung | drei Typen ueber sechs Tarifzellen: Rechnungszins 1,25 % statt des Rechner-Arbeitsstands 1,75 % (6), Tafel-Basisname mit separater Unisex-Mischung statt doppelter Verankerung (6), Verwaltungskostensatz der Bestandsgruppe Haus 0,01 statt 0,0 (2) | Verantwortlicher Aktuar, je Entscheid gezeichnet | A-Box-Journal des Falls; Gate A-Q1, Snapshot fd793260 |
| Unisex-Feststellung | Mischtafel 70/30 fuer die Generation | Verantwortlicher Aktuar | Golden Master 616/616 exakt; 251/616-Abweichungsbeleg ohne die Feststellung |
| Reichweite der Rueckkaufswert-Plausibilisierung | NICHT auf dynamische Vertraege ausgeweitet — der Beleg der Quelle traegt nur die Herabsetzungs-Vorfaelle | Verantwortlicher Aktuar | Fall-Chronik der Tarifplan-Ausgestaltung |
| Herabsetzungsanteile der Vorgeschichte | keine Punktschaetzung: Beitragsgleichung fuer beitragszahlende, Ankerwert fuer beitragsfreie Serien, Unerheblichkeits-Ausweis wo die Ist-Welt den Anteil nicht braucht | Verantwortlicher Aktuar | Abschlussbericht Abschnitt 5; Auskuenfte Nr. 2 und 4 |
| Arbeits-Lesart f = 0,60 fuer die Policen 7000679 und 7000396 | bei nachgewiesener Bewertungsinvarianz aller Pruefpunkte; mit Falsifizierbarkeits-Auflage: der erste Verlaufspunkt vor dem Beitragsende ist dort zu rechnen und zu wuerdigen | Verantwortlicher Aktuar, dokumentierte Lesart | Tarifplan-Ausgestaltung des Falls, Testfallkatalog |
| Verfahrenswahl der Herabsetzung | Teilkuendigungs-Semantik der Quelle statt der Verfahren des Zielsystems — als Eigenschaft des Falls, nicht des Tarifplans | Verantwortlicher Aktuar | Nachtrag der Tarifplan-Ausgestaltung |

Zusammen mit dem Abschlussbericht (Ergebnis und Methodik) und dem
Umbaubericht (Umfang der Systemarbeit in Zahlen) ergibt dieses
Dokument das vollstaendige Bild: WAS die Uebernahme ergab, WIE
geprueft wurde — und was sich dafuer am System und am Verstaendnis
des Quell-Tarifwerks aendern musste.
