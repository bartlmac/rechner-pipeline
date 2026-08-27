# Fachkonzept — die produktseitige Methode

Hier liegt die **fachlich normative Methode** der konstruktiven
Neuberechnung: was gerechnet wird und warum, unabhaengig von einem
einzelnen Migrationsfall und unabhaengig von der technischen Umsetzung.

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
   Thiele-Rekursion, Rechnungsgrundlagen-Schicht, Numerik) und nimmt in
   Abschnitt 9 die Korrekturmathematik auf, sobald deren Freiheitsgrade
   entschieden sind.
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

## Aenderungsweg

Diese Datei ist eine **unveraenderte Kopie** der freigegebenen Fassung
aus dem Wissens-Graph des Maintainers; das Repo traegt sie, damit Code,
Tests und ADRs eine zitierfaehige Quelle im selben Stand haben.
Aenderungen entstehen **nicht hier**: Sie laufen ueber den Autor des
Fachkonzepts und kommen als neue Fassung herein. Wer beim Bauen einen
Aenderungsbedarf sieht, meldet ihn als Vorschlag, statt das Dokument
anzupassen.

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
