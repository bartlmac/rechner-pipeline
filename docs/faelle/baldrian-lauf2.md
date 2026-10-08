# Abschlussbericht Bestandsmigration Baldrian KLV TG2015 (Lauf 2)

Pfefferminzia Lebensversicherung — Programm Bestandsmigration.
Abnahmebericht zur Übernahme des Baldrian-Teilbestands KLV TG2015,
zweiter Migrationslauf. Der Lauf ersetzt den ersten Durchgang
vollständig; er wurde auf einer neuen, umfangreicheren Lieferung der
abgebenden Gesellschaft durchgeführt.

**Vorführfall.** Pfefferminzia und Baldrian sind erfundene Unternehmen,
der Bestand ist synthetisch erzeugt. Die zeichnenden Rollen wurden in
diesem Lauf von KI-Sitzungen im Mandat des Maintainers besetzt und haben
mit einem Simulationsschlüssel gezeichnet (Abschnitt 7). Dieser
Bericht ist ein Erzeugnis der Vorführung, kein Dokument eines realen
Versicherers.

## 1 Ergebnis

Der Migrationsfall ist vollständig geprüft und abgenommen. Alle
fünf Abnahme-Gates wurden von der Rolle des Verantwortlichen Aktuars
auf demselben Systemstand gezeichnet (Stand f7c545d; die Quelltext-
Prüfsumme jedes Snapshots entspricht diesem Stand). Während des
Laufs wurden 25 Korrekturen am System vorgenommen und die betroffenen
Gates jeweils neu gezeichnet; der Umbaubericht des Falls weist sie aus
(Abschnitt 7).

| Gate | Gegenstand | Ergebnis |
|---|---|---|
| A-Q1 | Quell-Tarifwerk und Spezifikation | angenommen; Golden Master 616/616 exakt reproduziert |
| A-M1 | Stichtagstest (geschichtete Stichprobe, 100 Verträge) | 100/100 bestanden, max. Restabweichung 0,022 EUR |
| A-M2 | Verlaufstest (dieselbe Stichprobe) | 100/100 bestanden, max. Restabweichung 0,021 EUR |
| A-M3 | Geschäftsvorfalltest (Vollerhebung, 166 Vorfälle) | 166/166 bestanden, max. Restabweichung 0,010 EUR |
| A-M4 | Migrationscontrolling (Vollbestand, 834 Verträge) | 834/834 bestanden, 2508 Einzelprüfungen, keine Befunde |

Zeichnungs-Belege (SHA-256-Snapshots, Rolle Verantwortlicher Aktuar
über die Zeichnungsordnung): A-Q1 fd793260, A-M1 fb1550c0, A-M2
411ac21c, A-M3 d260e621, A-M4 32682e95 — das Abschluss-Gate bindet
die vier vorangehenden Zeichnungen sowie die vollständige
Produzenten-Kette (Golden Master, Bestandsübernahme,
Migrationscontrolling, Abnahmebericht).

Kernaussage der Bewertung: Nach Klärung aller Tarifwerks- und
Konventionsfragen rechnet das Zielsystem den gelieferten Bestand aus
den Ursprungsparametern praktisch exakt nach. Die Korrekturschicht,
die verbleibende Übernahme-Residuen tragen würde, ist über alle
834 Verträge nahezu leer: Residuensumme -0,14 EUR, größte
Einzelabweichung 0,02 EUR.

## 2 Gegenstand und Datenlage

Übernommen wurden 834 Verträge der Tarifgeneration KLV TG2015
(kapitalbildende Lebensversicherung, Verkaufsfenster ab 2015) zum
Migrationsstichtag 01.01.2026, mit Kontrollstichtag 01.01.2027.
Lieferumfang der abgebenden Gesellschaft: Bestandsabzüge zu beiden
Stichtagen, Vorgeschichts-Metadaten (2750 Geschäftsvorfall-Zeilen
2016-2025), Geschäftsvorfall-Protokoll des Migrationsjahres,
Erwartungswerte für Stichtags-, Verlaufs- und Vorfallprüfung samt
Ziehungsbeleg der Referenzstichprobe, Tarifwerk (Versicherungs-
bedingungen, Mitteilung Nr. 143, Tarifrechner-Arbeitsmappe) sowie
vier im Laufe des Falls registrierte Auskunftsschreiben.

Bestandsstruktur nach Vorgeschichte: 257 Verträge ohne Vorgeschichte,
360 mit dynamischen Erhöhungen (mehrjährige Erhöhungsserien sind
der Regelfall, nicht die Ausnahme), 160 beitragsfrei gestellte, 57 mit
Herabsetzung — darunter kombinierte Verläufe (Erhöhungsserie mit
anschließender Herabsetzung oder Beitragsfreistellung) als gut ein
Fünftel der Stichprobe.

## 3 Feststellungen zum Quell-Tarifwerk

Die Prüfstrecke rechnet die Konventionen der abgebenden Gesellschaft
nach; sie werden je Lieferung festgestellt und belegt, nie
unterstellt. Für diese Lieferung wurden festgestellt und vom
Verantwortlichen Aktuar bestätigt:

1. **Rechnungszins 1,25 %** je Mitteilung Nr. 143 — die im
   Tarifrechner hinterlegten 1,75 % sind ein Arbeitsstand des
   Rechners, nicht das Tarifwerk (drei Diskrepanz-Typen, vierzehn
   Einzelentscheide im Rahmen von A-Q1; ebenso Verwaltungskostensatz
   der Bestandsgruppe Haus 0,01 statt 0,0).
2. **Unisex-Kalkulation** (Mischtafel 70/30) für die gesamte
   Generation — im Rechenwerk der Quelle implizit über das
   Geschlechts-Präfix der Beispielrechnung, nicht als ausgesprochene
   Vorschrift; ohne diese Feststellung wichen 251 von 616
   Referenzwerten systematisch um rund 2 % ab.
3. **Volle Beitragsformel je Erhöhungsbaustein**: Jede dynamische
   Erhöhung ist ein eigenständiger Baustein mit eigener
   Wertermittlung einschließlich aller Kostenbestandteile
   (Bedingungswerk Ziffer 3) — anders als in der ersten Lieferung,
   deren Tarifmitteilung die Stückkosten auf der Grundsumme beließ.
4. **Stornoabzug je Baustein**: Mindest- und Höchstbetrag werden für
   Grundversicherung und jede Erhöhung einzeln erhoben; der
   Rückkaufswert des Vertrags ist die Summe der Baustein-
   Rückkaufswerte (Ziffer 4).
5. **Herabsetzung als Teilkündigung mit Auszahlung** (Ziffer 6): Der
   gekündigte Anteil der Grundversicherung verlässt den Vertrag,
   die Erhöhungsbausteine bleiben unberührt, der Vertrag läuft
   zustandslos mit der gesenkten Grundsumme weiter — kein geteilter
   Vertrag mit beitragsfrei gestelltem Teil.
6. **Deckungskapital zum Vertragsjahrestag**: Die gelieferte
   DECKKAP-Größe ist die letzte Standmitteilung zum
   Vertragsjahrestag vor dem Stichtag, keine kalendertägliche
   Interpolation (Mitteilung 143 Abschnitt 6).
7. **Dynamiksatz einheitlich 5 %** der jeweiligen Gesamtsumme für
   alle Erhöhungstermine 2016-2025 (registrierte Auskunft Nr. 1).

## 4 Bewertungsmethodik

Die Übernahme folgt der konstruktiven Neuberechnung: Das Zielsystem
rechnet jeden Vertrag aus seinen Ursprungsparametern selbst; der
gelieferte Stand geht ausschließlich in das Verankerungs-Residuum
ein, das eine je Vertrag parametrierte Korrekturschicht über die
Restlaufzeit trägt (Formfunktion proportional zum Basisverlauf,
Verankerung am letzten Vertragsjahrestag vor dem Stichtag,
Terminalbedingung am Ablauf gleich null). Vorgeschichts-Verläufe
werden als Ist-Struktur rekonstruiert: Erhöhungsserien geschlossen
aus dem belegten Dynamiksatz, Beitragsfreistellungen über die
Gesamtsummen-Inversion, Herabsetzungen nach der
Teilkündigungs-Semantik der Quelle.

Toleranzen folgen der Fehlerfortpflanzung der Lieferung, nicht einem
Pauschalmaß: Jeder für sich gerundete Baustein eines Lieferwerts
erweitert die zulässige Abweichung um einen halben Cent — dieselbe
Regel in Stichtagstest, Migrationscontrolling und der unabhängigen
Nachrechnung des Abnahmeberichts.

## 5 Behandlung der Datenlücke Herabsetzungsanteile

Die fortgeführten Anteile der 70 Vorgeschichts-Herabsetzungen sind
bei der abgebenden Gesellschaft strukturell geführt, aber praktisch
nicht mehr abrufbar (registrierte Auskunft Nr. 4 nach ernsthafter
Rekonstruktionsprüfung). Die Behandlung erfolgte ohne Punktschätzung:

- Für beitragszahlende Verträge bestimmt die unabhängige
  **Beitragsgleichung** den Anteil eindeutig aus den belegten
  Tarifstufen (0,50/0,60/0,75, Auskunft Nr. 2); für beitragsfreie
  Serien übernimmt der **Ankerwert** (geliefertes Deckungskapital)
  die Wahl unter den endlichen Hypothesen.
- Liegt die Herabsetzung vor der ersten Erhöhung, ist der Anteil aus
  der Ist-Welt **nachweislich unerheblich** (jede Stufe ergibt
  dieselbe Struktur) und wird als unbestimmt ausgewiesen statt
  geschätzt.
- Scheinbare Herabsetzungen unterhalb der Auflösung cent-gerundeter
  Lieferfelder werden als Widerspruch zwischen Vorfallshistorie und
  Wertlage benannt, nicht als Zustand geführt.
- Für genau zwei Verträge (7000679, 7000396) blieb der Anteil
  unbestimmbar bei nachgewiesener Bewertungsinvarianz aller
  Prüfpunkte; die dokumentierte Arbeits-Lesart 0,60 trägt eine
  **Falsifizierbarkeits-Auflage**: Sobald ein Verlaufspunkt vor dem
  Beitragsende dieser Verträge geprüft wird, ist die Lesart dort zu
  rechnen und zu würdigen.

## 6 Offene Punkte

Einziger fachlich offener Punkt ist die vorstehende
Falsifizierbarkeits-Auflage; sie ist kein Abnahmehindernis und in der
Tarifplan-Ausgestaltung des Falls als Pflicht-Testpunkt künftiger
Verlaufsprüfungen festgehalten.

## 7 Zeichnende Rollen, Mandate und eingesetzte Systeme

Dieser Abschnitt legt offen, wer in diesem Lauf entschieden hat und
womit — er gehört in jeden Bericht einer Vorführung (ADR-018).

**Rollen und Besetzung.** Vorbereitet wurde der Fall von Agentenrollen
des KI-Tools; entschieden und gezeichnet hat die Rolle des
Verantwortlichen Aktuars der Pfefferminzia. Diese Rolle war im Lauf
nicht durch eine natürliche Person besetzt, sondern durch eine
KI-Sitzung, die im Mandat des Maintainers handelte und die Abnahmen
nach Prüfung der Vorlagen zeichnete. Der Fall trägt 25 Entscheid-
Snapshots: die fünf geltenden (Neuzeichnung nach Korrektur 25 am
7. September 2026, Stand f7c545d) und zwanzig Vorgänger aus den
Neuzeichnungen nach früheren Korrekturen. Die fünf geltenden tragen
die Rolle in der heutigen Schreibweise (``mensch/plv-aktuar``) mit der
Schlüsselklasse ``simulation`` und binden das Mandat des Maintainers
und die Zeichnungsordnung als Dateihashes; die Vorgänger tragen noch die
Schreibweise des damaligen Vier-Rollen-Modells (``mensch``, Entscheider
``plv-aktuar``) ohne Schlüsselklasse.

**Schlüssel.** Gezeichnet wurde mit einem Simulationsschlüssel,
Fingerabdruck ``162817c937c33d0a…``. Er weist die Rolle nach, nicht die
Identität einer Person; das Mandat, in dem die Rolle handelte, liegt
außerhalb des Falls und ist im Snapshot gebunden. Die Snapshots sind
mit HMAC-SHA-256 signiert und bleiben gültig; sie werden nicht
nachsigniert. Wer sie prüft, erkennt die Simulation an der
Schlüsselklasse und am Fingerabdruck (geltende Snapshots: Schema-Version
7; Vorgänger: Schema-Version 6).

**Systemänderungen während des Laufs.** Das KI-Tool ist während
eines Falls eine Konstante; dieser Lauf lag in der ersten Ausbaustufe,
in der Korrekturen am System erlaubt und vom Maintainer abgenommen
wurden. 25 Korrekturen (Kern-Verfahren, Prüf-Engines, Gates,
Bestandsführung, Freischaltung des übernommenen Bestands) sind im
Umbaubericht des Falls einzeln begründet; nach jeder wurden die
betroffenen Gates auf dem neuen Stand neu gezeichnet, zuletzt alle fünf
auf f7c545d. Dieser Stand ist auf dem Hauptzweig des Repositories
erreichbar (über die Zusammenführung c67eb8f); die Belege binden den
Stand, nicht die Zweigspitze.

**Was dieser Bericht nicht leistet.** Er ist keine Abnahme durch eine
natürliche Person und kein Dokument eines realen Versicherers. Die
Nachrechenbarkeit gilt für den lokalen Fall-Arbeitsbereich; wer nur
das Repository hat, prüft die Rechenkette über die versionierten
Fixturen, nicht die konkreten Snapshots.

## Nachtrag 2026-09-07: Freischaltung des übernommenen Bestands (Korrektur 24)

Nach der Annahme von A-M4 stellte sich heraus, dass die Bestandsführung
für den übernommenen Bestand eine andere Welt rechnete als die
Abnahmen: Die Übernahme nahm die gelieferte Summe als Versicherungssumme
(550 von 834 Verträge ohne ihre Bausteine, 160 beitragsfrei gelieferte
Summen ein zweites Mal umgewandelt), und die Bestand-Config trug für die
TG2015 den Rechnungszins des Tarifrechners (1,75 %) statt des in A-Q1
entschiedenen (1,25 %). Der gezeichnete Bestandsbericht nach der
Migration war damit falsch, kein Gate hatte die Führung gegen die
Prüfstrecke gestellt. Befund, Zahlen und Vorgehen:
`dev-docs/freischaltung-uebernommener-bestand.md`; Korrektur-Protokoll
des Falls, Eintrag 24.

Die Übernahme materialisiert seither den Anfangszustand der Abnahmen
(Grundsumme, Alt-Erhöhungen als Bausteine, Ursprungssumme beitragsfreier
Verträge, Korrekturschicht), die Führung rechnet nach dem Tarifwerk der
Generation (Stornoabzug je Baustein, Scheiben mit voller Beitragsformel),
und die Führungsprobe belegt vor A-M4, dass der geführte Bestand die
abgenommene Welt trägt (834 Verträge, 42 Buchungen nach dem Stichtag,
0 Befunde). Die Abnahmen A-M1 bis A-M3 und das Migrationscontrolling sind
auf dem neuen Stand unverändert bestanden (100/100, 100/100, 166/166,
834/834). Die fünf Gates wurden mit Korrekturvermerk neu gezeichnet
(Korrektur 25: die Kettenprüfung der Entscheide unterscheidet seither
den Stand, auf dem ein Vorgänger gezeichnet wurde, von dem geltenden
Belegvertrag; Stand f7c545d). Der Tagesbetrieb der PLV wird aus der neuen
Übernahme neu aufgesetzt (Betriebsweg, offen).

## Nachtrag 2026-09-30: Systemstand des Laufs und Wiederholung

Der Lauf selbst — Registrierung der Lieferung am 01.09.2026, die vier
Auskunftsschreiben, die Producer-Kette und alle fünf Zeichnungen (A-Q1
fd793260 bis A-M4 32682e95, gezeichnet am 02.09.2026, 00:48 bis 00:49
Uhr) — fand auf Systemstand `4b1abf04` statt (Kern 3.3.0,
Quelltext-Prüfsumme `ef1af1a3...`). Abschnitt 1 nennt diese fünf
Snapshot-Kennungen und zugleich „Stand f7c545d“: Die Kennungen sind die
des Laufs, der Stand ist der der Neuzeichnung vom 07.09.2026 (Korrekturen
24 und 25). Beides ist richtig, aber nicht dasselbe. Die fünf Gates
wurden am 20.09.2026 ein zweites Mal neu gezeichnet, auf `17091b39`
(Korrektur 26: PEX-Zuschlag; Korrektur 27: Laufmanifest als Pflichtbeleg
von A-M4; `dev-docs/annahmen-2026-09-20.md`); das ist die heute geltende
Spitze der Snapshots.

Wer den Lauf nachstellen will, nimmt `4b1abf04`. Die Anleitung dazu —
Systemstand, was das Repository trägt, die drei Sorten Schritte, der
eigene Bestand ohne die Lieferung, die gemessene Kommandofolge und die
Referenzwerte — steht in `baldrian-lauf2-wiederholen.md`; die Kennzahlen
sind dort auf zwei Ständen nachgemessen. Nebenbefund derselben Messung:
Das `bestand/`-Verzeichnis des Lauftags entstand vor der
A-Q1-Zinsentscheidung, der von A-M4 gebundene P-B1-Beleg liegt damit auf
einem Ledger mit 1,75 % Rechnungszins, während die gezeichnete Spez
1,25 % trägt — dieselbe Inkonsistenz wie in der Bestand-Config, die
Korrektur 24 behoben hat.
