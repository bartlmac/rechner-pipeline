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
| **Rumpfjahr-Konvention der Korrekturschicht** (BESCHLOSSEN 2026-08-31: wird umgesetzt) | Bau des Migrationszugangs | Ein rechnender Geschaeftsvorfall zwischen zwei Vertragsstichtagen setzt nach Grundsatzdokumentation 9.12 den Verankerungszeitpunkt; die Schicht rechnet aber auf dem Jahresgitter (9.6). Es braucht entweder ein Monatsgitter oder eine Regel fuer das erste Rumpfjahr. Bis dahin faellt der Fall aus, und die Beitragsreduktion ist auf den Vertragsstichtag beschraenkt (Beschluss 2026-08-28). Betrifft nicht nur diesen Geschaeftsvorfall. |
| **Stichprobenprofile** jenseits von `vollbestand` und `geschichtet` | Grundsatzdokumentation, Erweiterungsstelle | Die Schichtung nach Historientyp ist am 2026-08-28 gebaut (ADR-010 Abschnitt 5). Offen bleiben Profile nach Restlaufzeit-Klasse oder Vorfallart; je Profil eine Festlegung des Aktuariats. |
| **Reihenfolge der aktuariellen Abnahmen** (ENTSCHIEDEN 2026-08-31: A-M4 verlangt A-M1 UND A-M2 UND A-M3; Bau steht aus) | Bau der drei Abnahmen | A-M1 bis A-M3 gehen A-M4 voraus (ADR-012). Ob A-M2 und A-M3 auch VORAUSSETZUNG sind oder nur zeitlich davor liegen, ist offen: Heute ist nur A-M1 Voraussetzung, ein Bestand mit richtigem Stichtagswert und falscher Ablaufleistung kaeme also durch das Controlling. |
| **Heilungsklasse von PEX, INV und REA** | Bau der Heilungstabelle | `kern.korrekturschicht.HEILUNG` fuehrt drei Eintraege mit `geprueft=False`: PEX steht in 9.7 unter Klasse A (plausibel, nicht bestaetigt), INV und REA haengen an der noch offenen BU-Zustandsbewertung. Die Tabelle weist die Unsicherheit aus, statt sie zu verschweigen. |
| **Ausgestaltung je migriertem Tarifplan** (Uebergangsklassifikation, Ankerliste, Formfunktion, Floors, Testfallkatalog) | Grundsatzdokumentation Abschnitt 10 Nr. 9 | Faellig, sobald ein Produkt mit Korrekturschicht migriert wird. |
| ~~Merkmalsdimensionen eines uebernommenen Tarifs~~ ERLEDIGT 2026-08-31 (Tarifzellen in der Config, merkmale.parquet, Bewertung je Zelle; a8cf3a9/92d261d) | Baldrian-Lauf 2026-08-29 | Die Config traegt je Generation EINEN Parametersatz; die uebernommene TG2015 hat sechs Zellen (tarifart x status). Der Bestandsbericht bewertet den zugewanderten Bestand deshalb mit einer Zelle. Fuer die Abnahmegroessen ohne Wirkung — dort rechnet die Spez je Vertrag —, fuer die Bestandskennzahlen eine benannte Ungenauigkeit. |
| ~~Herabsetzung geschichteter Vertraege~~ ERLEDIGT | Baldrian-Lauf 2026-08-29, praezisiert 2026-08-30, zugesagt 2026-08-31 | Der Tarifplan fuehrt die Herabsetzung als Zahlungsprofil statt als Vertragsteilung (klv.md 7.1) — die alte Beschraenkung auf den 'ungeteilten Track' war die Grenze der SKALIERUNG, nicht der Rechnung, und ist mit dem Zahlungspfad entfallen. Die Verteilung auf dynamische Erhoehungsscheiben ist entschieden und ZUGESAGT: anteilig, jede Schicht mit demselben Faktor und ihrem eigenen beitragsfreien Reservesatz; der Stornoabschlag wird einmal vertragsweit gebildet und proportional zur Deckungsrueckstellung getragen (kern.beitragsreduktion.reduziere_geschichtet). Die ZUORDNUNG bleibt wie zuvor: Eine eigene Teilkuendigung des Zielsystems ist eine Zusage und gehoert in den Tarifplan, waehrend der Abzug eines UEBERNOMMENEN Vertrags eine Rekonstruktion fremder Praxis bleibt und Fall-Eigenschaft ist (die abgebende Gesellschaft hat der Werthoehe nach nie etwas zugesagt, Aktuarielle Notiz 2026/05). |
| **Zwei offene Entscheidungen des Migrationskonzepts**: Verbleib der Geschaeftsvorfall-Metadatenliste (E1) und Aktivierung des Konventionsresiduum-Pfads (E2) | Migrationskonzept Kapitel 11 | Je Bestand zu entscheiden. |

## Technisch

| Punkt | Herkunft | Anmerkung |
|---|---|---|
| **Modellpunkte im Testergebnis persistieren**, damit der Entscheid die Vertragswerte nachrechnen kann | Review der N1-N5-Welle | Heute prueft das Gate nur die innere Konsistenz, bindet Systemstand und reproduziert den Bericht. Dieselbe Grenze hat die Controlling-Pruefrechnung. |
| ~~Tote Zuweisungen~~ ERLEDIGT 2026-08-31 (entfernt) in `bestand/report.py` (`stichtag_zeile`, `fortschreibung_zeile`) | Review der Bestandsfuehrung | Werden berechnet, aber nie in die Ausgabe uebernommen — Driftquelle, wenn jemand dort eine Formulierung aendert. |
| **Produzenten-Kommandos und der Referenzstichtag**: `cli_fortschreibung --neuzugang-ab` und `cli_abschluss --stichtag` lesen `meta.referenzstichtag` nicht | Review der Referenzstichtag-Aenderung | Abweichende Daten fallen heute still auseinander; ein Hinweis waere das Mindeste. |
| **`runs/`-Schutz**: echte Laeufe getrennt und nicht aufraeumbar ablegen | Nach versehentlichem Verlust | |
| **Demo-Ausgabe**: bei Stichproben „… und weitere X von Y" ausgeben | Backlog | |
| **Office-Metadaten-Werkzeug** dauerhaft einchecken | Nach der externen Reviewrunde | Ort noch zu bestimmen. |
| **Werkzeug der Quellsimulation**: was wird versionierter Repo-Bestandteil, was bleibt Beispielandockung | Besprechung 2026-08-28 | Die Vorfuehrung beansprucht, dass sich alles hier nachvollziehen laesst; ein Teil des Werkzeugs (Berechnungslaeufe in der Tarifmappe) liegt aber auf einer Office-Umgebung ausserhalb. Was ohne Office geht, entsteht inzwischen hier (`simulation/quellwerkzeug/`). Es fehlt die Trennlinie — ohne sie waechst das Repo entweder um fremde Werkzeuge oder die Vorfuehrung bleibt unvollstaendig. |
| ~~Bestandsbericht kennt den Migrationszugang nicht~~ ERLEDIGT 2026-08-31 (MIG in Reihenfolge, Beschriftung, Farbe): `MIG` fehlt in den Berichtstexten | Bau des Migrationszugangs | Der Zugang steht in Journal und Kennzahlen, aber nicht im Text. Ein Leser sieht ihn in den Zahlen und findet ihn im Text nicht wieder — Luecke in der Darstellung, nicht in der Rechnung. |
| ~~Gesamtfixture eines Fallverlaufs~~ ERLEDIGT (tests/test_baldrian_e2e.py, 0b12591): den Baldrian-Lauf als E2E-Regressionstest einfrieren | Besprechung 2026-08-28; FAELLIG seit dem Lauf 2026-08-29 | Die Vorbedingung ist eingetreten: Der Lauf ist durch (A-M4 erteilt), die Erwartungswerte des Zielsystems existieren also und sind keine Vermutung mehr. Die EINGABEN sind versioniert (`lieferungen/baldrian/`, elf Dateien, mit Hygienetest ueber die Office-Dateien). Es fehlen die Erwartungswerte des ZIELsystems — und die kann es vor dem Lauf nicht geben: Sie sind sein Ergebnis. Ein vorab gebautes Geruest wuerde eine Vermutung einfrieren statt eines Verhaltens. Also nach dem Lauf, dem Muster von `tests/e2e_fixture.py` und `tests/fixtures/pk1_am4_minimal/` folgend: eingecheckt werden fachliche Eingaben und unabhaengige Erwartungswerte, die Laufartefakte entstehen je Test neu unter `tmp_path` — sonst waere ein gitignorierter Fall-Arbeitsbereich eine versteckte Vorbedingung. Wegen Laufzeit und Repo-Groesse als reduzierte Scheibe, nicht als voller 500er-Bestand. |
| **Auswahl statt Dauerlauf** fuer teure E2E-Fixtures | dito | Ein Gesamtfixture soll nicht bei jeder Aenderung laufen. Der Mechanismus dafuer existiert schon: `ontologie/impact` leitet aus einem Diff die betroffenen Knoten ab (`git diff --name-only \| python -m rechner_pipeline.ontologie.impact`). Damit liesse sich die Auswahl aus der Aenderung ABLEITEN statt eine Markerliste von Hand zu pflegen — eine handgepflegte Liste veraltet genau dann, wenn sie gebraucht wird. Offen ist, wer die Auswahl trifft (CI-Schritt, Marker, Hook) und was der Vollauf ausloest. |

## Vorgaenge

| Punkt | Anmerkung |
|---|---|
| **Showcase-Migrationsfall auf den aktuellen Entscheid-Vertrag heben** | Das Schema der Entscheid-Snapshots ist auf Version 5 gestiegen; Altketten werden revisionsfest archiviert und auf aktuellem Stand neu entschieden. Braucht einen Freigabeschluessel ausserhalb des Falls. |
| **Doku-Engine**: `\Bigl`/`\Bigr` bricht die Umwandlung nach Typst | Am 2026-08-27 in allen Dokumenten ersetzt; die Engine selbst kennt die Einschraenkung nicht. Ein Hinweis in der Doku-Konvention waere sinnvoll. |
| **Rollenzuordnung Gate -> Zeichnungsberechtigung** | Regie-Entscheid 2026-08-31 | Zwei Operatoren: Quell-Experte (zeichnet NUR Lieferungs-Registrierungen, bedient eingang/, beantwortet fachliche Fragen) und PLV-Operator (Entscheidungen und Abnahmen, eigener Schluessel). Der Mensch steigt nur nach Abbruchkriterien ein: klarer Systemfehler (durch Agenten/Operatoren nicht heilbar), Zirkelreferenz, drei fruchtlose Q&A-Schleifen zum selben Thema, Budget ueberschritten. Heute prueft gate_entscheid NICHT, welche Rolle welches Gate zeichnen darf -- die Tabelle Gate->Rolle plus Pruefung fehlt. |
| **Quellsystem in Python (quellsystem/)** | Beschluss 2026-08-31 | Eigene Bestandsfuehrung der Quelle: KOPIE des Kommutationskerns (kein Import aus rechner_pipeline, Zielkern unerreichbar), abweichende Konventionen (StoAb je Scheibe, RED mit Abzug, Rundung je Zwischenschritt, Kalenderjahr-Logik, VS_bfr auf Vormonat), Export erzeugt die Lieferungen inkl. mehrfacher GeVos je Vertrag. Versioniertes Tooling OHNE ADR (Bartek: ADRs gelten dem System, nicht dem Simulationswerkzeug); Baldrian-Regie bleibt in simulation/. Eigener Branch quellsystem. |
