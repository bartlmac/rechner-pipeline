# Mathematik — was das System rechnet

Hier liegt die **fachlich normative Rechenmethode**: was gerechnet wird
und warum, unabhaengig von einem einzelnen Migrationsfall und
unabhaengig von der technischen Umsetzung. Die beiden Dokumente haben
verschiedene Herkunft und verschiedene Aenderungswege — siehe unten.

| Dokument | Inhalt |
|---|---|
| [konstruktive-neuberechnung.md](konstruktive-neuberechnung.md) | Fachkonzept „Konstruktive Neuberechnung und Korrekturschicht" v0.2 — Methode, Invarianten, Prozess- und Testrahmen, Freiheitsgrade |
| [grundsatzdokumentation.md](grundsatzdokumentation.md) | Mathematik und Numerik des Zielrechenkerns, produktübergreifend — das gemeinsame Rückgrat, dem die Umsetzung folgt |

## Einordnung (Fachkonzept Kap. 1.3)

Das Fachkonzept steht an der Spitze einer dreistufigen **produktseitigen**
Dokumentation (Freigabekreis Aktuariat/Entwicklung):

1. **Fachkonzept** (hier): Methode, Invarianten, Prozess- und Testrahmen,
   Freiheitsgrade.
2. **Grundsatzdokumentation** ([grundsatzdokumentation.md](grundsatzdokumentation.md)):
   normative Mathematik und Numerik, ein Dokument. *Die Implementierung
   folgt der Grundsatzdokumentation, nicht umgekehrt.* Sie trägt das
   Rückgrat, das allen Produkten gemeinsam ist (Zustandsraum,
   Thiele-Rekursion, Rechnungsgrundlagen-Schicht, Numerik) — und in
   Abschnitt 9 die vollstaendige Mathematik der Korrekturschicht
   (Migrationszugang). Deren technische Freiheitsgrade sind dort
   ausgewiesen und noch zu entscheiden; die Rechenmethode selbst ist
   festgelegt.
3. **Produktspezifische Ausgestaltung** (FK Kap. 8.2): je Tarifplan des
   Zielsystems die konkrete Belegung aller produktabhaengigen
   Festlegungen (Zustandsgraph mit Uebergangsklassifikation, Ankerliste,
   Formfunktion, Floors, Datenlieferumfang, Testfallkatalog). Ihr Ort in
   diesem Repo sind die bestehenden Tarifplaene unter
   [../tarifplaene/](../tarifplaene/) — je migriertem Produkt ein
   Ausgestaltungs-Abschnitt. Er wird faellig, sobald ein Produkt mit
   Korrekturschicht migriert wird; welche Punkte er belegen muss, steht
   in Grundsatzdokumentation Abschnitt 10 Nummer 9.

Daneben — nicht darunter — steht **projektseitig** das
[Migrationskonzept](../migrationskonzept/): je Bestand und Quellsystem
instanziiert, Freigabekreis Projekt. Es referenziert das Fachkonzept,
nie umgekehrt.

## Stand der Uebernahme

Das Fachkonzept ist die **Quelle**, aus der die Dokumente dieses Repos
gespeist werden. Es kann pensioniert werden, sobald jede seiner
normativen Aussagen ein Zuhause hier hat — heute ist das nicht der
Fall. Der Stand, damit niemand raten muss:

| Fachkonzept-Kapitel | Zuhause im Repo | Stand |
|---|---|---|
| 1 Zweck, Geltungsbereich, Einordnung | dieses README (Hierarchie) | uebernommen |
| 2 Begriffe und Notation | Grundsatzdokumentation Abschnitt 2 | uebernommen |
| 3 Methodik der konstruktiven Neuberechnung | Grundsatzdokumentation 9.1 bis 9.4 | uebernommen |
| 4 Korrekturschicht | Grundsatzdokumentation 9.5 bis 9.11 | uebernommen; die diskrete Rekursion ist dort festgelegt (FK 4.2 delegiert sie ausdruecklich) |
| 5 Verankerungszeitpunkt und Historienfreiheit | Grundsatzdokumentation 9.12 und 9.13 | uebernommen |
| 5.2 und 5.4 Nachfahren, Lieferobjekte | Grundsatzdokumentation 9.12; Migrationskonzept Kapitel 4 und 5 | uebernommen — die fallspezifischen Feldlisten bleiben dort ⟨TODO⟩, das ist ihr Zustand als Vorlage |
| 6 Test- und Abnahmekonzept | Migrationskonzept Kapitel 6 und 7 | uebernommen (mit ausgewiesener Luecke bei 6.3) |
| 7 Regulatorischer Rahmen | Migrationskonzept Kapitel 7.7 | uebernommen |
| 8 Zu erstellende Dokumentation | dieses README, Grundsatzdokumentation | uebernommen |
| 9 Implementierungsfreiheiten und Konfliktregel | Grundsatzdokumentation 9.14 und Abschnitt 12 | uebernommen; die elf Freiheitsgrade sind als offen ausgewiesen — das ist ihr Zustand, keine Luecke der Uebernahme |

Damit ist das Fachkonzept **inhaltlich vollstaendig uebernommen**: Die
Rechenmethode steht in der Grundsatzdokumentation, das Verfahren in der
Migrationskonzept-Vorlage. Was dort noch ⟨TODO⟩ traegt, sind
fallspezifische Angaben (welches Quellsystem welches Feld liefert) —
kein ungehobener Inhalt des Fachkonzepts.

Es bleibt trotzdem hier liegen, und zwar als **zitierte Quelle**: Code,
ADRs und beide Konzepte verweisen an rund fuenfzig Stellen auf seine
Kapitelnummern ("FK 4.3", "FK 6.2"). Eine Pensionierung waere erst
sinnvoll, wenn diese Verweise auf die Grundsatzdokumentation umgestellt
sind — eine eigene, saubere Aufgabe, keine Loeschung nebenbei.

## Aenderungswege — zwei verschiedene

**`konstruktive-neuberechnung.md` ist FREMD.** Die Datei ist eine
unveraenderte Kopie der freigegebenen Fassung aus dem Wissens-Graph des
Maintainers; das Repo traegt sie, damit Code, Tests und ADRs eine
zitierfaehige Quelle im selben Stand haben. Aenderungen entstehen
**nicht hier**: Sie laufen ueber den Autor und kommen als neue Fassung
herein. Wer beim Bauen einen Aenderungsbedarf sieht, meldet ihn als
Vorschlag, statt das Dokument anzupassen.

**`grundsatzdokumentation.md` ist repo-eigen.** Sie wird hier gepflegt,
und der Kern folgt ihr — nicht umgekehrt. Substanzielle Aenderungen an
ihren normativen Abschnitten brauchen die Zustimmung des Aktuariats
(dort Abschnitt 13); Abweichungen zwischen Konzept und Realisierung
werden entschieden und im Abweichungsverzeichnis gefuehrt, nie implizit
aufgeloest.

## Was hier NICHT steht

* **Wie das System gebaut ist** und warum es so entschieden wurde:
  Architektur-Entscheidungen stehen als ADRs unter
  [../architektur/](../architektur/). ADR-010 etwa instanziiert den
  Testrahmen aus FK Kap. 6 in unserer Gate-Architektur; es definiert
  fachlich nichts Neues.
* **Die Mathematik EINES Produkts**: die steht im jeweiligen Tarifplan
  ([../tarifplaene/](../tarifplaene/)).
* **Der Ablauf eines Migrationsfalls**: der steht im
  [Migrationskonzept](../migrationskonzept/) (Verfahren) und in den
  Agenten-Skills unter `.claude/skills/` (Handgriffe).
