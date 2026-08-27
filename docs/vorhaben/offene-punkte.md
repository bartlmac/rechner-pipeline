# Offene Punkte

Kleinere Vorhaben, Nachzuege und Reviewfunde ohne eigenen Umbau. Ein
erledigter Punkt wird geloescht, nicht abgehakt — was hier steht, steht
noch aus.

## Fachlich

| Punkt | Herkunft | Anmerkung |
|---|---|---|
| **Verlaufs- und Geschaeftsvorfalltests** fuer den aktuariellen Test: Vorwaertsrechnung gegen eine Schattenrechnung des Quellsystems, Testmatrix je Vertragskonstellation | Grundsatzdokumentation 9.15 | Ohne sie gilt die Methode als nicht abgenommen. Der heutige Test belegt nur die Stichtagstreue am Rechenpunkt. |
| **Verteilungstoleranzen als Urteilskriterium**: Schwelle auf Maximum oder hohem Perzentil je Cluster | Grundsatzdokumentation 9.15 | Heute haengt das maschinelle Urteil an Toleranzen je Einzelwert; die Verteilung wird nur ausgewiesen. Festlegung des Aktuariats. |
| **Verankerungsattribute** als Vertragsmerkmale ($t_a$, Verankerungszustand und Verweildauer) | Fruehere Befundliste, N6 | Durch die Bestandsfuehrung andockbereit; braucht einen ADR-Nachtrag, weil die Zustandsregeln fuer migrierte Bestaende zu lockern sind. |
| **Rechenmodul der Korrekturschicht** ohne Produktpolitik | Fruehere Befundliste, N7 | Die Mathematik steht (Grundsatzdokumentation Abschnitt 9); offen sind die Freiheitsgrade in 9.16. |
| **Stichprobenprofile** jenseits von `vollbestand` | Grundsatzdokumentation, Erweiterungsstelle | Je Profil eine Festlegung des Aktuariats. |
| **Ausgestaltung je migriertem Tarifplan** (Uebergangsklassifikation, Ankerliste, Formfunktion, Floors, Testfallkatalog) | Grundsatzdokumentation Abschnitt 10 Nr. 9 | Faellig, sobald ein Produkt mit Korrekturschicht migriert wird. |
| **Zwei offene Entscheidungen des Migrationskonzepts**: Verbleib der Geschaeftsvorfall-Metadatenliste (E1) und Aktivierung des Konventionsresiduum-Pfads (E2) | Migrationskonzept Kapitel 11 | Je Bestand zu entscheiden. |

## Technisch

| Punkt | Herkunft | Anmerkung |
|---|---|---|
| **Modellpunkte im Testergebnis persistieren**, damit der Entscheid die Vertragswerte nachrechnen kann | Review der N1-N5-Welle | Heute prueft das Gate nur die innere Konsistenz, bindet Systemstand und reproduziert den Bericht. Dieselbe Grenze hat die Controlling-Pruefrechnung. |
| **Tote Zuweisungen** in `bestand/report.py` (`stichtag_zeile`, `fortschreibung_zeile`) | Review der Bestandsfuehrung | Werden berechnet, aber nie in die Ausgabe uebernommen — Driftquelle, wenn jemand dort eine Formulierung aendert. |
| **Produzenten-Kommandos und der Referenzstichtag**: `cli_fortschreibung --neuzugang-ab` und `cli_abschluss --stichtag` lesen `meta.referenzstichtag` nicht | Review der Referenzstichtag-Aenderung | Abweichende Daten fallen heute still auseinander; ein Hinweis waere das Mindeste. |
| **`runs/`-Schutz**: echte Laeufe getrennt und nicht aufraeumbar ablegen | Nach versehentlichem Verlust | |
| **Demo-Ausgabe**: bei Stichproben „… und weitere X von Y" ausgeben | Backlog | |
| **Office-Metadaten-Werkzeug** dauerhaft einchecken | Nach der externen Reviewrunde | Ort noch zu bestimmen. |

## Vorgaenge

| Punkt | Anmerkung |
|---|---|
| **Showcase-Migrationsfall auf den aktuellen Entscheid-Vertrag heben** | Das Schema der Entscheid-Snapshots ist auf Version 5 gestiegen; Altketten werden revisionsfest archiviert und auf aktuellem Stand neu entschieden. Braucht einen Freigabeschluessel ausserhalb des Falls. |
| **Doku-Engine**: `\Bigl`/`\Bigr` bricht die Umwandlung nach Typst | Am 2026-08-27 in allen Dokumenten ersetzt; die Engine selbst kennt die Einschraenkung nicht. Ein Hinweis in der Doku-Konvention waere sinnvoll. |
