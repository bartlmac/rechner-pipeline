# Abschlussbericht Bestandsmigration Baldrian KLV TG2015 (Lauf 2)

Pfefferminzia Lebensversicherung — Programm Bestandsmigration.
Abnahmebericht zur Uebernahme des Baldrian-Teilbestands KLV TG2015,
zweiter Migrationslauf. Der Lauf ersetzt den ersten Durchgang
vollstaendig; er wurde auf einer neuen, umfangreicheren Lieferung der
abgebenden Gesellschaft durchgefuehrt.

## 1 Ergebnis

Der Migrationsfall ist vollstaendig geprueft und abgenommen. Alle
fuenf Abnahme-Gates wurden vom Verantwortlichen Aktuar auf einem
einzigen, unveraenderten Systemstand gezeichnet:

| Gate | Gegenstand | Ergebnis |
|---|---|---|
| A-Q1 | Quell-Tarifwerk und Spezifikation | angenommen; Golden Master 616/616 exakt reproduziert |
| A-M1 | Stichtagstest (geschichtete Stichprobe, 100 Vertraege) | 100/100 bestanden, max. Restabweichung 0,022 EUR |
| A-M2 | Verlaufstest (dieselbe Stichprobe) | 100/100 bestanden, max. Restabweichung 0,021 EUR |
| A-M3 | Geschaeftsvorfalltest (Vollerhebung, 166 Vorfaelle) | 166/166 bestanden, max. Restabweichung 0,010 EUR |
| A-M4 | Migrationscontrolling (Vollbestand, 834 Vertraege) | 834/834 bestanden, 2508 Einzelpruefungen, keine Befunde |

Zeichnungs-Belege (SHA-256-Snapshots, Rolle Verantwortlicher Aktuar
ueber die Zeichnungsordnung): A-Q1 fd793260, A-M1 fb1550c0, A-M2
411ac21c, A-M3 d260e621, A-M4 32682e95 — das Abschluss-Gate bindet
die vier vorangehenden Zeichnungen sowie die vollstaendige
Produzenten-Kette (Golden Master, Bestandsuebernahme,
Migrationscontrolling, Abnahmebericht).

Kernaussage der Bewertung: Nach Klaerung aller Tarifwerks- und
Konventionsfragen rechnet das Zielsystem den gelieferten Bestand aus
den Ursprungsparametern praktisch exakt nach. Die Korrekturschicht,
die verbleibende Uebernahme-Residuen tragen wuerde, ist ueber alle
834 Vertraege nahezu leer: Residuensumme -0,14 EUR, groesste
Einzelabweichung 0,02 EUR.

## 2 Gegenstand und Datenlage

Uebernommen wurden 834 Vertraege der Tarifgeneration KLV TG2015
(kapitalbildende Lebensversicherung, Verkaufsfenster ab 2015) zum
Migrationsstichtag 01.01.2026, mit Kontrollstichtag 01.01.2027.
Lieferumfang der abgebenden Gesellschaft: Bestandsabzuege zu beiden
Stichtagen, Vorgeschichts-Metadaten (2750 Geschaeftsvorfall-Zeilen
2016-2025), Geschaeftsvorfall-Protokoll des Migrationsjahres,
Erwartungswerte fuer Stichtags-, Verlaufs- und Vorfallpruefung samt
Ziehungsbeleg der Referenzstichprobe, Tarifwerk (Versicherungs-
bedingungen, Mitteilung Nr. 143, Tarifrechner-Arbeitsmappe) sowie
vier im Laufe des Falls registrierte Auskunftsschreiben.

Bestandsstruktur nach Vorgeschichte: 257 Vertraege ohne Vorgeschichte,
360 mit dynamischen Erhoehungen (mehrjaehrige Erhoehungsserien sind
der Regelfall, nicht die Ausnahme), 160 beitragsfrei gestellte, 57 mit
Herabsetzung — darunter kombinierte Verlaeufe (Erhoehungsserie mit
anschliessender Herabsetzung oder Beitragsfreistellung) als gut ein
Fuenftel der Stichprobe.

## 3 Feststellungen zum Quell-Tarifwerk

Die Pruefstrecke rechnet die Konventionen der abgebenden Gesellschaft
nach; sie werden je Lieferung festgestellt und belegt, nie
unterstellt. Fuer diese Lieferung wurden festgestellt und vom
Verantwortlichen Aktuar bestaetigt:

1. **Rechnungszins 1,25 %** je Mitteilung Nr. 143 — die im
   Tarifrechner hinterlegten 1,75 % sind ein Arbeitsstand des
   Rechners, nicht das Tarifwerk (drei Diskrepanz-Typen, vierzehn
   Einzelentscheide im Rahmen von A-Q1; ebenso Verwaltungskostensatz
   der Bestandsgruppe Haus 0,01 statt 0,0).
2. **Unisex-Kalkulation** (Mischtafel 70/30) fuer die gesamte
   Generation — im Rechenwerk der Quelle implizit ueber das
   Geschlechts-Praefix der Beispielrechnung, nicht als ausgesprochene
   Vorschrift; ohne diese Feststellung wichen 251 von 616
   Referenzwerten systematisch um rund 2 % ab.
3. **Volle Beitragsformel je Erhoehungsbaustein**: Jede dynamische
   Erhoehung ist ein eigenstaendiger Baustein mit eigener
   Wertermittlung einschliesslich aller Kostenbestandteile
   (Bedingungswerk Ziffer 3) — anders als in der ersten Lieferung,
   deren Tarifmitteilung die Stueckkosten auf der Grundsumme beliess.
4. **Stornoabzug je Baustein**: Mindest- und Hoechstbetrag werden fuer
   Grundversicherung und jede Erhoehung einzeln erhoben; der
   Rueckkaufswert des Vertrags ist die Summe der Baustein-
   Rueckkaufswerte (Ziffer 4).
5. **Herabsetzung als Teilkuendigung mit Auszahlung** (Ziffer 6): Der
   gekuendigte Anteil der Grundversicherung verlaesst den Vertrag,
   die Erhoehungsbausteine bleiben unberuehrt, der Vertrag laeuft
   zustandslos mit der gesenkten Grundsumme weiter — kein geteilter
   Vertrag mit beitragsfrei gestelltem Teil.
6. **Deckungskapital zum Vertragsjahrestag**: Die gelieferte
   DECKKAP-Groesse ist die letzte Standmitteilung zum
   Vertragsjahrestag vor dem Stichtag, keine kalendertaegliche
   Interpolation (Mitteilung 143 Abschnitt 6).
7. **Dynamiksatz einheitlich 5 %** der jeweiligen Gesamtsumme fuer
   alle Erhoehungstermine 2016-2025 (registrierte Auskunft Nr. 1).

## 4 Bewertungsmethodik

Die Uebernahme folgt der konstruktiven Neuberechnung: Das Zielsystem
rechnet jeden Vertrag aus seinen Ursprungsparametern selbst; der
gelieferte Stand geht ausschliesslich in das Verankerungs-Residuum
ein, das eine je Vertrag parametrierte Korrekturschicht ueber die
Restlaufzeit traegt (Formfunktion proportional zum Basisverlauf,
Verankerung am letzten Vertragsjahrestag vor dem Stichtag,
Terminalbedingung am Ablauf gleich null). Vorgeschichts-Verlaeufe
werden als Ist-Struktur rekonstruiert: Erhoehungsserien geschlossen
aus dem belegten Dynamiksatz, Beitragsfreistellungen ueber die
Gesamtsummen-Inversion, Herabsetzungen nach der
Teilkuendigungs-Semantik der Quelle.

Toleranzen folgen der Fehlerfortpflanzung der Lieferung, nicht einem
Pauschalmass: Jeder fuer sich gerundete Baustein eines Lieferwerts
erweitert die zulaessige Abweichung um einen halben Cent — dieselbe
Regel in Stichtagstest, Migrationscontrolling und der unabhaengigen
Nachrechnung des Abnahmeberichts.

## 5 Behandlung der Datenluecke Herabsetzungsanteile

Die fortgefuehrten Anteile der 70 Vorgeschichts-Herabsetzungen sind
bei der abgebenden Gesellschaft strukturell gefuehrt, aber praktisch
nicht mehr abrufbar (registrierte Auskunft Nr. 4 nach ernsthafter
Rekonstruktionspruefung). Die Behandlung erfolgte ohne Punktschaetzung:

- Fuer beitragszahlende Vertraege bestimmt die unabhaengige
  **Beitragsgleichung** den Anteil eindeutig aus den belegten
  Tarifstufen (0,50/0,60/0,75, Auskunft Nr. 2); fuer beitragsfreie
  Serien uebernimmt der **Ankerwert** (geliefertes Deckungskapital)
  die Wahl unter den endlichen Hypothesen.
- Liegt die Herabsetzung vor der ersten Erhoehung, ist der Anteil aus
  der Ist-Welt **nachweislich unerheblich** (jede Stufe ergibt
  dieselbe Struktur) und wird als unbestimmt ausgewiesen statt
  geschaetzt.
- Scheinbare Herabsetzungen unterhalb der Aufloesung cent-gerundeter
  Lieferfelder werden als Widerspruch zwischen Vorfallshistorie und
  Wertlage benannt, nicht als Zustand gefuehrt.
- Fuer genau zwei Vertraege (7000679, 7000396) blieb der Anteil
  unbestimmbar bei nachgewiesener Bewertungsinvarianz aller
  Pruefpunkte; die dokumentierte Arbeits-Lesart 0,60 traegt eine
  **Falsifizierbarkeits-Auflage**: Sobald ein Verlaufspunkt vor dem
  Beitragsende dieser Vertraege geprueft wird, ist die Lesart dort zu
  rechnen und zu wuerdigen.

## 6 Offene Punkte

Einziger fachlich offener Punkt ist die vorstehende
Falsifizierbarkeits-Auflage; sie ist kein Abnahmehindernis und in der
Tarifplan-Ausgestaltung des Falls als Pflicht-Testpunkt kuenftiger
Verlaufspruefungen festgehalten.
