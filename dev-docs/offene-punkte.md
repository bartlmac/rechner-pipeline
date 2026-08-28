# Offene Punkte

Kleinere Vorhaben, Nachzuege und Reviewfunde ohne eigenen Umbau. Ein
erledigter Punkt wird geloescht, nicht abgehakt — was hier steht, steht
noch aus.

Drei fruehere Punkte dieser Liste sind zu eigenen Vorhaben gewachsen und
stehen jetzt dort: die Verlaufs- und Geschaeftsvorfalltests sowie die
Verteilungstoleranzen in
[aktuarieller-test-at1-at2-at3.md](aktuarieller-test-at1-at2-at3.md), das
Rechenmodul der Korrekturschicht in
[korrekturschicht-umsetzung.md](korrekturschicht-umsetzung.md). Ein
vierter ist am 2026-08-28 dazugekommen: die fehlende Darstellung des
herabgesetzten Vertrags im Zielkern, jetzt in
[zahlungspfade-migrierter-vertraege.md](zahlungspfade-migrierter-vertraege.md).

## Fachlich

| Punkt | Herkunft | Anmerkung |
|---|---|---|
| **Verankerungsattribute** als Vertragsmerkmale ($t_a$, Verankerungszustand und Verweildauer) | Fruehere Befundliste, N6 | Durch die Bestandsfuehrung andockbereit; braucht einen ADR-Nachtrag, weil die Zustandsregeln fuer migrierte Bestaende zu lockern sind. Wird blockierend, sobald die Korrekturschicht laeuft ([korrekturschicht-umsetzung.md](korrekturschicht-umsetzung.md), K3). |
| **Uebergangsklassifikation je Produkt** (Grundsatzdokumentation 9.7) | Bau der Korrekturschicht | Die Tabelle in 9.7 ist der Default; die vollstaendige Klassifikation gehoert je Produkt in den Tarifplan. Fuer die KLV ist heute nur 'Tod mit fester Versicherungssumme' als vererbend gesetzt - fuer die BU steht sie aus. |
| **Rumpfjahr-Konvention der Korrekturschicht** | Bau des Migrationszugangs | Ein rechnender Geschaeftsvorfall zwischen zwei Vertragsstichtagen setzt nach Grundsatzdokumentation 9.12 den Verankerungszeitpunkt; die Schicht rechnet aber auf dem Jahresgitter (9.6). Es braucht entweder ein Monatsgitter oder eine Regel fuer das erste Rumpfjahr. Bis dahin faellt der Fall aus, und die Beitragsreduktion ist auf den Vertragsstichtag beschraenkt (Beschluss 2026-08-28). Betrifft nicht nur diesen Geschaeftsvorfall. |
| **Stichprobenprofile** jenseits von `vollbestand` und `geschichtet` | Grundsatzdokumentation, Erweiterungsstelle | Die Schichtung nach Historientyp ist am 2026-08-28 gebaut (ADR-010 Abschnitt 5). Offen bleiben Profile nach Restlaufzeit-Klasse oder Vorfallart; je Profil eine Festlegung des Aktuariats. |
| **Reihenfolge der aktuariellen Abnahmen** | Bau der drei Abnahmen | A-M1 bis A-M3 gehen A-M4 voraus (ADR-012). Ob A-M2 und A-M3 auch VORAUSSETZUNG sind oder nur zeitlich davor liegen, ist offen: Heute ist nur A-M1 Voraussetzung, ein Bestand mit richtigem Stichtagswert und falscher Ablaufleistung kaeme also durch das Controlling. |
| **Heilungsklasse von PEX, INV und REA** | Bau der Heilungstabelle | `kern.korrekturschicht.HEILUNG` fuehrt drei Eintraege mit `geprueft=False`: PEX steht in 9.7 unter Klasse A (plausibel, nicht bestaetigt), INV und REA haengen an der noch offenen BU-Zustandsbewertung. Die Tabelle weist die Unsicherheit aus, statt sie zu verschweigen. |
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
| **Werkzeug der Quellsimulation**: was wird versionierter Repo-Bestandteil, was bleibt Beispielandockung | Besprechung 2026-08-28 | Die Vorfuehrung beansprucht, dass sich alles hier nachvollziehen laesst; ein Teil des Werkzeugs (Berechnungslaeufe in der Tarifmappe) liegt aber auf einer Office-Umgebung ausserhalb. Was ohne Office geht, entsteht inzwischen hier (`simulation/quellwerkzeug/`). Es fehlt die Trennlinie — ohne sie waechst das Repo entweder um fremde Werkzeuge oder die Vorfuehrung bleibt unvollstaendig. |
| **Bestandsbericht kennt den Migrationszugang nicht**: `MIG` fehlt in den Berichtstexten | Bau des Migrationszugangs | Der Zugang steht in Journal und Kennzahlen, aber nicht im Text. Ein Leser sieht ihn in den Zahlen und findet ihn im Text nicht wieder — Luecke in der Darstellung, nicht in der Rechnung. |

## Vorgaenge

| Punkt | Anmerkung |
|---|---|
| **Showcase-Migrationsfall auf den aktuellen Entscheid-Vertrag heben** | Das Schema der Entscheid-Snapshots ist auf Version 5 gestiegen; Altketten werden revisionsfest archiviert und auf aktuellem Stand neu entschieden. Braucht einen Freigabeschluessel ausserhalb des Falls. |
| **Doku-Engine**: `\Bigl`/`\Bigr` bricht die Umwandlung nach Typst | Am 2026-08-27 in allen Dokumenten ersetzt; die Engine selbst kennt die Einschraenkung nicht. Ein Hinweis in der Doku-Konvention waere sinnvoll. |
