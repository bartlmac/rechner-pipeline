# Prüf-Gates: Vertrag und Versionen

Wer welches Gate zeichnet und worüber, steht in
[ADR-012](adr-012-gate-namensordnung.md) (Namensordnung) und
[ADR-018](adr-018-rollenmodell-und-schluesselklassen.md) (Rollen). Dieses
Dokument trägt, was für jedes Prüf-Gate gleich gilt — seinen Vertrag — und je
Gate das Kommando, den Gegenstand der Prüfung und die Geschichte seiner
Version.

## Der Vertrag

Jedes Gate schreibt ein JSON auf stdout und ein Ledger in den
Diagnostics-Ordner; ein Nicht-Null-Exit ist **blockierend** und wird
nie zur Warnung abgeschwächt. Vor der fachlichen Arbeit ersetzt ein roter
Startbeleg einen etwaigen Beleg des vorigen Laufs. Der Abschluss ersetzt
diesen Startbeleg atomar durch das aktuelle Ergebnis. Eine unerwartete
Exception bleibt damit als aktueller fehlgeschlagener Lauf sichtbar; scheitert
das Schreiben des Abschlussbelegs, endet auch eine fachlich grüne Prüfung mit
Exit 50 statt ohne aktuellen Beleg erfolgreich zu erscheinen.
Fehlende Pflichtargumente und ungültige Optionen liefern ebenfalls genau ein
strukturiertes Fehler-JSON und ersetzen einen alten grünen Beleg durch den
aktuellen roten Lauf. Syntax- und `argparse`-Choice-Fehler verwenden Exit 2;
fachlich kategorisierte fehlende Eingaben behalten den vom jeweiligen Gate
definierten Fehlercode. `--help` bleibt ein erfolgreicher Aufruf mit Exit 0 und
startet keinen Gate-Lauf.

## Die Gates

| Gate | Kommando | Prüft |
|---|---|---|
| P-Q1 | `gates.extract` | deterministische Vorverdichtung einer Quellmappe (Formeln, Werte, Namen, VBA) |
| P-Q2 | `gates.abox_merge` | Zusammenführung der Extraktions-Fragmente zur A-Box |
| P-Q3 (Version `2.0.0`) | `gates.abox_validate` | die A-Box gegen die T-Box |
| P-K1 (Version `1.0.0`) | `gates.generation_golden` | den parametrierten Kern gegen die Erwartungswerte der Lieferung |
| P9 (Version `5.0.0`) | `gates.gate_entscheid` | die Snapshots der menschlichen Gates |
| P-B1 (Version `4.0.0`) | `gates.bestand_validate` | den geführten Bestand |
| A-M-Vorlagen | `gates.aktuartest --abnahme A-M1\|A-M2\|A-M3` | rechnet das Ergebnis des aktuariellen Tests (`qa.aktuarieller_test`: je Vertrag am eigenen Verankerungszeitpunkt, am Rechenpunkt ohne Interpolation, ohne Summation — nur Verteilungsgrößen der Residuen je Historientyp) von innen nach außen nach und rendert die Entscheidungsvorlage für das jeweilige Gate A-M1, A-M2 oder A-M3 (im Bestands-Scope alle drei Pflichtvorgänger von A-M4, im Tarif-Scope nur A-M1); Transportsicherung wird getrennt ausgewiesen |
| A-M4-Vorlage (Version `10.0.0`) | `gates.abnahmebericht` | die Migrationssuite und die Pflichtbelege des Migrationscontrollings; rendert die Entscheidungsvorlage für A-M4 |

Was ein versioniertes Gate im Einzelnen prüft und wie seine Version
gewachsen ist, steht in den Abschnitten darunter.

### P-Q3: die A-Box gegen die T-Box

Abdeckung, Wertebereiche und Formel-Rück-Check. Die A-Box muss die
geltende T-Box-Version tragen (Befund T22-02, Major: Eine A-Box fremder
Version war vorher grün).

- `2.0.0`: Im Bestands-Scope muss die A-Box die Tarifregeln der migrierten Generation belegt führen, also Tarifwerk und Quellverfahren (`tbox.BESTAND_PFLICHT`, Code `tarifregeln`). Eine A-Box ohne sie war vorher ein gültiger Beleg (ADR-024, Nachtrag).

### P-K1: der Kern gegen die Erwartungswerte der Lieferung

Das Gate rechnet den parametrierten Kern gegen die Erwartungswerte der
Lieferung und schreibt je Generation einen inhaltsadressierten Beleg des
A-Box- und Systemstands. Spez, A-Box und Code müssen dieselbe
T-Box-Version sprechen (Befund T22-02, Major).

### P9: die Snapshots der menschlichen Gates

P9 prüft schema- und kettengültige Snapshots der menschlichen Gates
(A-Q1, A-O1, A-K2, A-T1, A-M1 bis A-M6, A-B1, A-B2, A-B3), im Fall oder,
mit `--linie` allein, im Linienbereich der Erstabnahme (A-K2, A-O1, A-T1,
A-B3). Dabei gilt:

- Annahmen sind mit einem extern verwahrten HMAC-Schlüssel autorisiert.
- A-M1 und A-M4 verlangen die zum Fall-Scope passenden Pflichtbelege je Gate.
- A-M4 verlangt die geltende, signierte A-M1-Annahme auf demselben Stand und pinnt sie als Pflichtrolle `am1_snapshot` (aktuarielle vor finanzieller Abnahme, ADR-010).
- A-O1 (gezeichnet von `mensch/architektur`) verlangt den Beleg der T-Box-Änderung `abgeleitet/tbox/aenderung.json` (alte und neue Version, Hash des T-Box-Moduls, Änderungsartefakt).
- Eine simulierte Rolle zeichnet nur mit Mandat (ADR-018).

Versionen:

- `1.0.0`: Akzeptanzmenge geändert durch die Mandatspflicht und den Beleg der T-Box-Änderung, damals unter dem Gate-Namen A-K1, der entfallen ist (heute A-O1, ADR-012; Befunde T22-02 und T22-07).
- `2.0.0`: A-M4 verlangt im Bestands-Scope die Führungsprobe als Pflichtbelegrolle `fuehrungsprobe` (Freischaltung des übernommenen Bestands, Schritt 6).
- `3.0.0`: A-M4 verlangt in beiden Scopes, dass der Stand des Falls abgenommen ist: Kernstand (A-K2, Rolle `kernstand`) und T-Box-Stand (A-O1, Rolle `tboxstand`), nach einer Regel, nämlich im Fall gezeichnet, „keine Änderung seit Abnahme …“ über einen Verweis auf einen früher angenommenen Snapshot (`gates.stand_belegen verweisen`) oder für die T-Box die Basislinie. A-K2 nimmt den Kernstand ab (Änderungen entlang der Module mit Commits, `gates.kernstand_belegen`; Regression bis zu ihrem Werkzeug als benannte Ausnahme „nicht gefahren“). P9-Schema 8 mit `stand`, `ausnahmen` und `standabnahmen` (ADR-018, Nachtrag 2026-10-01).
- `4.0.0`: A-M4 verlangt zusätzlich das Tarifwerk der PLV (A-T1, Rolle `tarifwerkstand`, `gates.tarifwerk_belegen`). Die Basislinie der T-Box fällt weg (Erstabnahme im Linienbereich, Verweis `stand_belegen verweisen --linie`). Mit `--linie` wird nur unter der Spitze der Versionslinie der Zeichnungsordnung gezeichnet, und jede Vorbedingung wird gegen die Ordnung gelesen, unter der sie gezeichnet wurde. P9-Schema 9 mit Scope `linie` und `zeichnung.ordnungsglied_sha256` (ADR-025).
- `5.0.0`: Jede Annahme eines Falls außer dem Auftrag selbst verlangt den geltenden, vom Vorstand gezeichneten Fallauftrag `A-M6` auf der heutigen Lieferung (`eingang.json`, `fall.json`) und nennt ihn signiert (`fallauftrag`). Simulierte Rollen zeichnen nur unter dem Mandat, das der Auftrag ihnen nennt. Neu ist der Fallabbruch `A-M5`, gezeichnet von der Programmleitung mit dem Recht aus dem Auftrag; danach ist im Fall nichts mehr zeichenbar. P9-Schema 10 mit `auftrag`, `abbruch` und `fallauftrag` (ADR-026). Eine Annahme gründet nur auf Annahmen des Falls unter dem geltenden Auftrag, die Linie des Aufrufs ist die Linie des Auftrags, und A-M5 geht auch bei verletztem Eingang, mit dem Befund im Abbruch (ADR-026, Nachtrag Runde G). Zugleich ist die Linie Pflicht: Ohne `--linie` wird nicht entschieden, und keine Vorbedingung wird ohne sie gelesen (ADR-025, Nachtrag 2026-10-01).

### P-B1: der geführte Bestand

P-B1 prüft:

- das physische Parquet-Schema mit exakten Arrow-Typen und ohne unbekannte Spalten, eine nichtleere `tarif_generation` und endliche Beträge in Stamm, Scheiben und Ledger (`NaN` und `inf` sind Datenfehler);
- die Zustandsregeln des geführten Bestands: Ursprungssatz `1`/`POL` am Versicherungsbeginn, Folgezustände nur mit Journal und deckungsgleich zum jüngsten Journalstand;
- die Form des `gamma1` jeder Erhöhungsscheibe (endlich, nicht negativ) und mit `--config` seinen Wert gegen das Tarifwerk der Generation (`0`, oder das `gamma1` der Zelle bei `scheiben_mit_gamma1`);
- mit `--schichten`/`--verankerung` die Korrekturschicht übernommener Verträge (Form, Zugehörigkeit, Anker) und ihren Anteil an jeder Storno-Herleitung;
- die Semantik jeder Ledger-Buchung (GeVo-Vokabular, Betragsart zum GeVo, Generation des Stammsatzes, Vertragsjahr zum Datum, Journalzeile zum Zustandswechsel) mit zeilenweiser Bindung jeder `ERH`-Buchung an genau eine Scheibe;
- mit `--config` die Betragsidentität jeder STO-, PEX-, TOD-, ABL- und ZUG-Buchung gegen die Kern-Herleitung für genau diese Police (Tarifzellen brauchen `--merkmale`);
- die Bewegungs-Identitäten je Jahr, Track und Maß;
- mit `--manifest` zusätzlich den belegten Horizont und die Bytes jeder Tabelle gegen das Laufmanifest.

Versionen:

- `2.0.0`: änderte die normative Akzeptanzmenge (vorher grüne Belege werden rot und umgekehrt).
- `2.1.0`: ergänzte die optionale Manifest-Bindung.
- `3.0.0`: erweitert die Akzeptanzmenge um Ledger-Semantik, Betragsidentität und Herkunftsbindung; mit Config geprüfte, betragsfalsche Ledger werden rot (Befund T21-09: Eine geänderte Akzeptanzmenge braucht einen Versionssprung).
- `4.0.0`: macht die `gamma1`-Regel zur Eigenschaft der Generation und nimmt Schicht und Verankerung in die Herleitung. Scheiben mit `gamma1` einer freigeschalteten Generation werden grün, Storno-Buchungen ohne ihre Schicht rot (Freischaltung des übernommenen Bestands, Schritt 4 und 5).

### A-M4-Vorlage: Migrationssuite und Migrationscontrolling

Die Vorlage berechnet Residuen, Einzel-, Vertrags- und Suiteurteile neu.
Ein grünes Ledger verlangt vollständige Pflichtartefakte, eine lückenlose
Suite, kongruente Transformationszeilen, keine Transformationsbefunde und
keine offenen Konflikte. Im Bestands-Scope bindet es P-B1, Suite und
Bericht auf denselben Stand sowie die vier Renderer-Eingaben unter festen
Pfad- und SHA-256-Rollen, und der P-B1-Beleg muss das Vollprofil tragen
(Stamm, Journal, Ledger, Config, Horizont, Betragsbindung).

Versionen:

- `2.0.0`: Ein Teilprofil war vorher ein gültiger Beleg (Befund T22-01).
- `3.0.0`: Im Bestands-Scope bindet es zusätzlich die Führungsprobe (`gates.fuehrungsprobe`, bestanden, auf demselben Systemstand, auf dem Bestand der Suite); ohne sie gibt es keinen grünen Beleg (Freischaltung, Schritt 6).
- `4.0.0`: Die Führungsprobe wird mit ihrem eigenen Aufruf nachgerechnet und Feld für Feld gegen den Beleg gehalten, die Fortschreibung ist Pflicht, und die Probe leitet den Endzustand (Historie, Zustand, Scheiben) aus Übernahme und Geschäftsvorfällen her (Prüfrunde T27).
- `5.0.0`: Die Probe prüft die Übernahme des Falls (`abgeleitet/bestand`), ihre Fortschreibung reicht bis zum Folgestichtag, und P-B1 läuft vollständig auf dieser Fortschreibung.
- `6.0.0`: Im Bestands-Scope muss die Suite die Auskunft zu den Herabsetzungsanteilen als `red_anteile_datei` führen (`null` = keine; Name und SHA-256 müssen unter den Eingaben der Suite stehen), und Suite und Führungsprobe müssen dieselbe Auskunft gelesen haben. Eine Suite ohne das Feld war vorher ein gültiger Beleg (Nachbesserung nach einer Prüfrunde, ADR-002).
- `7.0.0`: Die Policen, deren Anfangszustand die Auskunft trägt (Übernahme, über die Führungsprobe als `gedeckt` geführt), sind die Pflichtschicht der Abnahmen: Die Suite führt dieselbe Menge als `pflichtschicht`, und kein Beleg des aktuariellen Tests hat eine Fehlstelle in ihr. Vorher lag eine solche Police in keiner Stichprobe, und der Beleg war gültig (Prüfrunde vom 2026-10-01).
- `8.0.0`: Im Bestands-Scope trägt die Suite in Fassung 2 je Vertrag den `fuehrungswert`: Deckungskapital, Rückkaufswert und Korrekturschicht, die der Monatsabschluss am Zugangs- und am Folgestichtag führt, als Systemwert auf dem Bestand der Suite (`models.fuehrungswert`). Eine Suite ohne ihn war vorher ein gültiger Beleg (Entscheid des Maintainers 2026-10-01).
- `9.0.0`: Die Führungsprobe trägt Fassung 5, Tarifwerk und Quellverfahren aus der Spez statt aus Schaltern; ihr Aufruf nennt keine Tarifschalter mehr. Ein Beleg der Fassung 4 war gültig und ist mit seinem Aufruf nicht mehr nachrechenbar (ADR-024, Nachtrag).
- `10.0.0`: Der Führungswert der Suite wird auf den gebundenen Bytes (Bestand, Nebentabellen, Config, Tarifwerk der Spez) über denselben Weg wie die Suite nachgerechnet und in der Vorlage ausgewiesen (Summary `fuehrungswert`, HTML je Vertrag). A-M4 bindet die Spez der Generation (Summary `tarifregeln`), und jeder Beleg der Bestandsstrecke (Übernahme, Schicht, aktuarieller Test, Suite, Führungsprobe) muss genau ihre Regeln nennen und sie gelesen haben. Ein verfälschter Führungswert oder ein Beleg mit anderer Regelangabe war vorher gültig (Prüfrunde G, ADR-024, vierter Nachtrag).

## Die Versionsregel

Gate-Versionen folgen der Akzeptanzmenge (ADR-012, Nachtrag 2026-09-05): Major, wenn ein vorher grüner Beleg rot werden kann oder umgekehrt; Minor für eine optionale Rolle oder Prüfung, die bestehende Belege nicht berührt; Patch für Meldetexte und Summary-Felder. Trägt eine Zeile dieser Tabelle eine Version, hält `tests/test_gate_versionsregel.py` sie mit der `GATE_VERSION` des Moduls zusammen.

Dazu prüfen Hypothesis-Tests die aktuariellen Identitäten des Kerns
(`tests/test_kern_algebraisch.py`: qx-Schranken, Barwert-Bilanz
`A + d·ä = 1`, Rekursionen, Äquivalenzprinzip) — unabhängig von jeder
Quell-Lieferung.
