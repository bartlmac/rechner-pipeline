# Offene Punkte

Kleinere Vorhaben, Nachzuege und Reviewfunde ohne eigenen Umbau. Ein
erledigter Punkt wird geloescht, nicht abgehakt — was hier steht, steht
noch aus.

## Fachlich

Drei fruehere Punkte dieser Liste sind zu eigenen Vorhaben gewachsen und
stehen jetzt dort: die Verlaufs- und Geschaeftsvorfalltests sowie die
Verteilungstoleranzen in
[aktuarieller-test-at1-at2-at3.md](aktuarieller-test-at1-at2-at3.md), das
Rechenmodul der Korrekturschicht in
[korrekturschicht-umsetzung.md](korrekturschicht-umsetzung.md).

## Fachlich

| Punkt | Herkunft | Anmerkung |
|---|---|---|
| **Verankerungsattribute** als Vertragsmerkmale ($t_a$, Verankerungszustand und Verweildauer) | Fruehere Befundliste, N6 | Durch die Bestandsfuehrung andockbereit; braucht einen ADR-Nachtrag, weil die Zustandsregeln fuer migrierte Bestaende zu lockern sind. Wird blockierend, sobald die Korrekturschicht laeuft ([korrekturschicht-umsetzung.md](korrekturschicht-umsetzung.md), K3). |
| **Uebergangsklassifikation je Produkt** (Grundsatzdokumentation 9.7) | Bau der Korrekturschicht | Die Tabelle in 9.7 ist der Default; die vollstaendige Klassifikation gehoert je Produkt in den Tarifplan. Fuer die KLV ist heute nur 'Tod mit fester Versicherungssumme' als vererbend gesetzt - fuer die BU steht sie aus. |
| **Rumpfjahr-Konvention der Korrekturschicht** | Bau des Migrationszugangs | Ein rechnender Geschaeftsvorfall zwischen zwei Vertragsstichtagen setzt nach Grundsatzdokumentation 9.12 den Verankerungszeitpunkt; die Schicht rechnet aber auf dem Jahresgitter (9.6). Es braucht entweder ein Monatsgitter oder eine Regel fuer das erste Rumpfjahr. Bis dahin faellt der Fall aus, und die Beitragsreduktion ist auf den Vertragsstichtag beschraenkt (Beschluss 2026-08-28). Betrifft nicht nur diesen Geschaeftsvorfall. |
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
