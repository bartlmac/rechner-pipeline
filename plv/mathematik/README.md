# Mathematik — was das System rechnet

Hier liegt die **fachlich normative Rechenmethode**: was gerechnet wird
und warum, unabhaengig von einem einzelnen Migrationsfall und
unabhaengig von der technischen Umsetzung. Die beiden Dokumente haben
verschiedene Herkunft und verschiedene Aenderungswege — siehe unten.

| Dokument | Inhalt |
|---|---|
| [grundsatzdokumentation.md](grundsatzdokumentation.md) | Mathematik und Numerik des Zielrechenkerns, produktübergreifend — das gemeinsame Rückgrat, dem die Umsetzung folgt, einschließlich Migrationszugang und Korrekturschicht (Abschnitt 9) |

## Einordnung

Die Fachdokumentation ist zweistufig und produktseitig (Freigabekreis
Aktuariat/Entwicklung):

1. **Grundsatzdokumentation** (hier): normative Mathematik und Numerik,
   ein Dokument. *Die Implementierung folgt der Grundsatzdokumentation,
   nicht umgekehrt.* Sie traegt das Rueckgrat, das allen Produkten
   gemeinsam ist (Zustandsraum, Thiele-Rekursion,
   Rechnungsgrundlagen-Schicht, Numerik) und in Abschnitt 9 die
   vollstaendige Methode des Migrationszugangs — konstruktive
   Neuberechnung mit Korrekturschicht.
2. **Produktspezifische Ausgestaltung**: je Tarifplan des Zielsystems
   die konkrete Belegung aller produktabhaengigen Festlegungen
   (Zustandsgraph mit Uebergangsklassifikation, Ankerliste,
   Formfunktion, Floors, Datenlieferumfang, Testfallkatalog). Ihr Ort
   sind die Tarifplaene unter [../tarifplaene/](../tarifplaene/) — je
   migriertem Produkt ein Ausgestaltungs-Abschnitt, faellig sobald ein
   Produkt mit Korrekturschicht migriert wird (Grundsatzdokumentation
   Abschnitt 10 Nr. 9).

Daneben — nicht darunter — steht **projektseitig** das
[Migrationskonzept](../migrationskonzept/): je Bestand und Quellsystem
instanziiert, Freigabekreis Projekt. Es referenziert die
Grundsatzdokumentation, nie umgekehrt.

## Herkunft

Die Methode des Migrationszugangs geht auf das Fachkonzept
„Konstruktive Neuberechnung und Korrekturschicht" v0.2 zurueck (Autor
ausserhalb dieses Repos). Es ist vollstaendig aufgenommen: die
Rechenmethode in Abschnitt 9 der Grundsatzdokumentation, das Verfahren
in der Migrationskonzept-Vorlage. Die Vorlage selbst liegt nicht mehr
im Repo — sie war Zulieferung, nicht Systemdokumentation, und wird beim
Maintainer als Historie gefuehrt.

## Aenderungsweg

Die Grundsatzdokumentation wird **hier** gepflegt, und der Kern folgt
ihr — nicht umgekehrt. Substanzielle Aenderungen an ihren normativen
Abschnitten brauchen die Zustimmung des Aktuariats (dort Abschnitt 13);
Abweichungen zwischen Konzept und Realisierung werden entschieden und
im Abweichungsverzeichnis gefuehrt, nie implizit aufgeloest.
