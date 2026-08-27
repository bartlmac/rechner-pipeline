# Changelog

Format angelehnt an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/).
Es gibt noch keine Release-Nummerierung: das Repository ist ein
öffentlicher Prototyp, der Stand wird hier mit Datum benannt. Die
Architektur-Entscheidungen selbst stehen als ADRs unter
`docs/architektur/` — dieser Changelog fasst sie zusammen und macht
einen vorgeführten Stand zitierbar.

## Unveröffentlicht — Stand 2026-08-24

### Was das System kann

* **Migrationsfall Ende-zu-Ende**: Fall-Arbeitsbereich anlegen, Quellen
  mit SHA-256 registrieren (`rechner_pipeline.fall`), Vorverdichtung je
  Quelltyp (XLSM, DOCX, Bestandsabzugs-CSV), Agenten-Extraktion je
  Quelle, deterministischer Merge zur A-Box mit Provenienz je Aussage,
  Widersprüche als Diskrepanz-Objekte, Projektion zur Tarif-Spez,
  parametrierter Kern, Abnahme gegen die Lieferung.
* **Acht Gates** als je ein Kommando mit JSON auf stdout und Ledger:
  `extract` (G0), `abox_merge` (O0), `abox_validate` (O1),
  `generation_golden` (O3), `gate_entscheid` (P9), `bestand_validate`
  (B1), `aktuartest` (GA-Vorlage) und `abnahmebericht` (G2-Vorlage). Ein Nicht-Null-Exit blockiert
  und wird nie zur Warnung. Jeder Lauf ersetzt den alten Beleg vor der
  Facharbeit durch einen roten Startbeleg und publiziert den Abschluss
  atomar.
* **Menschliche Gates G-1/G-A/G-2/G-T** mit unveränderlichen Snapshots;
  `--rolle mensch|agent` ist Pflicht, ein Agent kann ein menschliches
  Gate nur ablehnen.
* **Zielrechenkern 3.0.1**: KLV und Berufsunfähigkeit auf einem
  gemeinsamen (Semi-)Markov-Zustandsmodell mit Thiele-Rückwärts-
  rekursion, Tafelwerk als reine qx-Vektoren, Monatsreserven für
  Bilanzstichtage, vertragsweite Bewertung dynamischer
  Erhöhungsscheiben. Die Kommutationsrechnung lebt als separater
  Zweitkern ausschließlich als Kreuz-Check-Schiene.
* **Bestandsmodul**: deterministisch reproduzierbare Bestände, deren
  Datenmodell auf dem Kern-Contract liegt; Entwicklung über die Zeit
  als ein Strom datierter Geschäftsvorfälle (Zugang, Storno, Tod,
  Beitragsfreistellung, Invalidisierung/Reaktivierung, dynamische
  Erhöhungen als eigene Scheiben, Ablauf) mit Bewegungskonto in der
  Struktur der BaFin-Nachweisungen und HTML-Bestandsbericht.
* **Migrationsabnahme über zwei Stichtage**: Deckungskapital am
  Migrations- und am Folgestichtag plus die Geschäftsvorfälle
  dazwischen, gegen die gelieferten Erwartungswerte, zusammengefasst im
  HTML-Abnahmebericht als Vorlage für Gate G-2.
* **Code-Ontologie**: Module und Tests deklarieren ihren Fachknoten;
  Index, Schichtenkarte, Impact und Landkarte werden daraus berechnet
  statt gepflegt.
* **SDK-frei und deterministisch**: kein Modell-, Provider- oder
  Token-Pfad in `src/`, gleiche Eingaben ergeben byte-identische
  Artefakte.

### Was es bewusst noch nicht kann

* **Formelidentität ist keine Maschinenprüfung.** Der Formel-Rück-
  Check in Gate O1 deckt die IF-Staffeln; jede andere Formelform meldet
  er fail-fast als "nicht prüfbar". Ob Tarifmeldung und Quell-Rechner
  dieselbe Formel meinen, entscheidet heute ein Mensch gegen den
  Tarifplan.
* **Gate O3 deckt die Beispielzelle** des Quell-Rechners
  (einzel/nichtraucher); die übrigen Zellen brauchen weitere
  Erwartungswerte vom Lieferanten. Das Komplement weist das Gate aus.
* **Das O3-/G-2-Pflicht-Fixture ist bewusst klein und synthetisch.** Es deckt
  einen Modellpunkt und eine Ratenzuschlagsstaffel ab, nicht die sechs Zellen
  des archivierten TG2015-Falls. Dafür laufen echte Vorverdichtung, O3 und
  G-2 im frischen Clone verpflichtend; ein fehlendes oder hashabweichendes
  Fixture ist ein Testfehler statt eines Skips.
* **Der Knoten-Lebenszyklus** (`in_migration` / `abgenommen`, ADR-007
  Regel 4) ist in der T-Box noch nicht umgesetzt.
* **Kein geteilter Fall-Speicher**: Fall-Artefakte (A-Box, Entscheide,
  Spez) liegen im gitignorierten Arbeitsbereich; die Nachweiskette endet
  damit an einem Einzelplatz. Versionierung echter Fälle außerhalb des
  Repos ist ADR-002-Zielbild, nicht gebaut.
* **T-Box ohne Zahlungsprofil**: das Struktur-Urteil unterscheidet
  Parametrierung von Erweiterung innerhalb einer vorgegebenen
  Produktfamilie, kann "neue Produktfamilie" aber nicht selbst
  feststellen. Kommt mit dem zweiten Fall (Risiko/Rente).
* **Kein Graph-Store, keine Embeddings, kein MCP/RPC-Pfad.** Die
  portable Basis sind lokale Dateien und einfache Python-Kommandos.

### Geändert in der Woche vom 2026-08-14 bis 2026-08-19

* **ADR-001 (14.08.): Repo-Zielstruktur entlang der Pipeline** —
  Schichtenschnitt `quellen -> ontologie -> spez -> kern -> bestand ->
  qa -> gates`, ein Laufverzeichnis für regenerierbare Artefakte.
* **ADR-002 (14.08.): Fall-Arbeitsbereich** — das Repo ist das System,
  nicht der Datenraum. Quellen gelangen ausschließlich über die
  ausdrückliche Registrierung in einen Fall; dort beginnt die
  Provenienzkette.
* **ADR-003 (14.08.): Pydantic für T-Box und A-Box** — die Ontologie
  bekommt ein generiertes Schema (Structured Output der
  Extraktions-Agenten); das leichtgewichtige dataclass-Idiom bleibt für
  Nutzer-Configs.
* **ADR-004 (16.08.): Der Zielkern ist Thiele-Welt** — Kern 3.0.0. Die
  Excel-Parität (617/617 Werte, 22.07.2026) ist Übersetzungsbeleg der
  Vergangenheit, kein Anker mehr; die Kommutationsrechnung wandert in
  einen separaten Zweitkern.
* **ADR-005 (16.08.): Knoten-Hierarchie, Test-Bindung, Code-Karte,
  berechneter Impact** — Knoten-Annotation wird Pflicht und maschinell
  geprüft, Tests sind knotengebunden, die Schichtenkarte ist Code statt
  Prosa.
* **ADR-006 (17.08.): Der Portierungs-Anwendungsfall geht außer
  Betrieb** — die G0-G8-Kette des Sechs-Datei-Vergleichskerns, der
  `assurance`-Orchestrator und der zugehörige Skill entfallen; der
  Stand ist beim Maintainer archiviert (kein veröffentlichter Branch).
  Erhalten bleiben `gates.extract` und der Ledger-Mechanismus.
* **ADR-007 (18.08.): Parallele Migrationen in einem Kern** — ein Trunk
  statt Kern-Forks oder langlebiger Branches; die Trennung leistet die
  Ontologie, nicht Git. Inkremente landen klein und beweisen bei jeder
  Landung die Nicht-Berührung aller anderen Fälle. Korrigiert
  ausdrücklich die Verengung "Migration ist im Wesentlichen
  Parametrierung": das gilt für den Präzedenzfall TG2012 -> TG2015,
  der Normalfall ist eine knotengebundene Code-Erweiterung.
* **Beispielartefakte auf die PLV-Fiktion umgestellt** — Zielsystem,
  Bestand und Configs gehören der fiktiven Pfefferminzia
  Lebensversicherung; abgebende Unternehmen der Showcase-Migrationen
  sind ebenfalls fiktiv (`lieferungen/`). Die Demo-Generationen sind
  Ontologie-Knoten (`klv/plv_*`, `bu/plv_*`), keine Parametrierung am
  System vorbei.
* **Showcase-Migrationsfall `baldrian-uebernahme`** — Übernahme des
  KLV-Bestands (Tarifgeneration TG2015) der fiktiven Baldrian Leben in
  die PLV, mit Tarifrechner, Tarifmeldung und Bestandsdaten-Lieferung zu
  zwei Stichtagen samt Geschäftsvorfall-Protokoll. Der erste
  Baldrian-Fall ist als Vorlauf archiviert.
* **Migrationsabnahme-Schicht** — Abzugsabgleich, Migrationssuite über
  zwei Stichtage und HTML-Abnahmebericht mit Bestandsberichten
  vor/nach.
* **Bestandsmodul erweitert** — GeVo-Strom mit Erhöhungsscheiben und
  Bewegungskonto, Gate B1 auf Bewegungs-Identitäten je Jahr, Track und
  Maß.
* **Tarifpläne** (`docs/tarifplaene/klv.md`, `bu.md`) als Fachdokumente
  des Zielkerns in seiner eigenen Mathematik, gerendert über eine
  gepinnte Doku-Engine.
* **CI über die Pin-Dateien** statt über `pip install -e ".[dev]"`:
  reproduzierbare Eingabe, damit die strenge Warnungs-Behandlung
  (`filterwarnings = ["error"]`) nur eigene Änderungen anzeigt und
  nicht fremde Neuveröffentlichungen.

### Geändert am 2026-08-20 bis 2026-08-24 (externe Review-Runde)

Ein externes Review des Stands vom 19.08. hat Beweislücken der
Abnahmekette aufgedeckt: Ein von Hand geschriebener P9-Snapshot konnte
G-2 freischalten, ein grüner O3-Ledger schaltete G-2 nie frei, und der
Abnahmebericht übernahm Selbstauskünfte der Suite, statt sie
nachzurechnen. Daraus:

* **ADR-008 (20.08.): Signierte P9-Freigaben** — striktes Ledger- und
  Snapshot-Schema, kanonischer Eigenhash, inhaltsadressierter
  Dateiname, geprüfter Vorgängergraph; jede menschliche Annahme trägt
  eine HMAC-SHA-256-Freigabe gegen eine Schlüsseldatei außerhalb des
  Falls (`--freigabe-schluessel`). Eine Ablehnung bleibt ohne Schlüssel
  möglich — der sichere Agentenpfad.
* **ADR-009 (20.08.): Fall-Scope und Bestands-Pflichtbelege** — jeder
  Fall deklariert `tarif` oder `bestand` in `fall.json`; daraus leitet
  G-2 seine Pflichtbelege ab und rechnet sie neu nach, statt dem
  Ledger zu glauben. Ein Altfall ohne Deklaration blockiert.
* **O3-Belege** sind unveränderlich und inhaltsadressiert und binden
  A-Box, Systemstand und Eingangsartefakte.
* **Abnahmebericht rechnet neu**: Residuen, Vertrags- und Suiteurteile,
  Mengenbefunde und Prüflücken werden aus den atomaren Fakten
  abgeleitet; Prüflücken, Zeilenverlust, Transformationsbefunde und
  offene Konflikte blockieren als `abnahmehindernisse`.
* **Fehlende GeVo-Erwartungsbeträge** (STO/TOD/ABL/PEX) werden zur
  benannten Prüflücke, statt still zu bestehen.
* **Provenienz und Integrität**: O1 verwirft Belege aus abgelehnten
  Lesarten; der Tafelimport prüft die Kette XLSM → Exportmanifest →
  Blatt-CSV per Vollhash; Sterbewahrscheinlichkeiten und Altersgitter
  werden an allen Ladepfaden validiert (Kern 3.0.1); Fall-Registrierung
  ist gegen Symlinks, Pfadtraversal und parallele Läufe gehärtet;
  Excel-Blattnamen werden bijektiv auf Dateinamen abgebildet.
* **Ein eingechecktes O3-Fixture** löst die vier fallgebundenen
  Test-Auslassungen ab; die CI fährt es als Pflichtstufe vor der
  Vollsuite.
* **Bewusst nicht umgesetzt**: statische QS (Lint/Typprüfung/Security),
  eine unveränderliche Attempt-Historie der Gate-Ledger und ein
  mehrstufiges Statusmodell des Abnahmeberichts — der Gate-Vertrag
  bleibt binär und blockierend.

### Geändert am 2026-08-27

* **Dreistufige Fachdokumentation nach Fachkonzept Kap. 1.3 und 8** —
  das Fachkonzept „Konstruktive Neuberechnung und Korrekturschicht"
  v0.2 liegt als zitierfähige Kopie im Repo
  (`docs/fachkonzept/`, Änderungen laufen über seinen Autor), daneben
  neu die **Grundsatzdokumentation**: Mathematik und Numerik, der die
  Umsetzung folgt — Zustandsraum und Semi-Markov-Modell,
  Thiele-Rekursion auf dem erweiterten Zustand, Rechnungsgrundlagen
  und Ordnungs-Abgrenzung, die beiden unterjährigen Konventionen,
  Rundung, Schichtenbild und Produkt-Contract. Die **Tarifpläne**
  tragen seither nur noch die Ausgestaltung je Produkt und verweisen
  für das gemeinsame Rückgrat; rund ein Viertel jedes Plans stand
  vorher wortgleich im anderen. Ein Wächter hält den Schnitt
  (`tests/test_tarifplan_struktur.py`): je Produkt ein Tarifplan und
  umgekehrt, gemeinsame Gliederung, kein Backbone-Thema im Tarifplan,
  keine widersprüchliche Abschnittszahl.
* **Projektseitig** das Migrationskonzept (`docs/migrationskonzept/`)
  mit den ausgearbeiteten Kapiteln 6 (Migrationscontrolling) und 7
  (aktuarielle Abnahme), jeweils mit Deckungsgrad gegenüber
  Fachkonzept Kapitel 6.
* **Impact kennt die Doku-Bindungen**: Tarifpläne binden über ihren
  Dateinamen an den Produktknoten (ein neues Produkt bringt seinen
  Plan damit nicht an der Testselektion vorbei), das Fachkonzept fällt
  konservativ aus.

### Geändert am 2026-08-26

* **ADR-010 umgesetzt: aktuarieller Test und Migrationscontrolling sind
  getrennte Gates** — die Test-Engine (`qa.aktuarieller_test`)
  vergleicht je Vertrag am eigenen Verankerungszeitpunkt, am Rechenpunkt
  ohne Interpolation und ohne Summation der Vergleichsgrößen (nur
  Verteilungsgrößen der Residuen, geclustert nach Historientyp) auf
  einer belegten Stichprobe (`qa.stichprobe`, v0-Profil `vollbestand`).
  Das Gate `gates.aktuartest` rechnet das Ergebnis von innen nach außen
  nach und rendert die Entscheidungsvorlage für das neue menschliche
  Gate G-A (aktuarielle Abnahme, Verantwortlicher Aktuar).
  Prüfsummen laufen als Transportsicherung getrennt und sind nie Teil
  des fachlichen Urteils.
* **G-A geht G-2 voraus (erzwungen)** — `P9_GATES` wächst um `G-A`, die
  Pflichtbelegmenge wird je Gate aufgelöst (`fall.BELEGROLLEN`,
  ADR-009-Nachtrag), G-2 verlangt den geltenden signierten G-A-Snapshot
  auf demselben Stand und pinnt ihn als Rolle `ga_snapshot`. Das
  P9-Schema hebt auf Version 5 (Gate-Version 0.6.0); Altketten mit
  v4-Snapshots werden revisionsfest archiviert und neu entschieden.
* **ADR-011: Bestandsführung mit geführtem Zustand und Journal** — der
  Stammsatz trägt den aktuellen Zustand (Status und seit wann), das
  Journal (Statushistorie + Ledger) ist die vollständige Aufzeichnung,
  aus der die Auskunft den Bestand zu jedem früheren Tag rekonstruiert.
  Kein Bewertungspfad liest das Journal; die Bewertung rechnet aus dem
  Zustand. `bestand_gesamt.parquet` ist seither geführt; Gate B1 prüft
  die Deckungsgleichheit von Stamm und Journal. Die rückwirkende
  Zeitscheiben-Sicht ist pensioniert. Erhöhungsscheiben tragen ihre
  Rechnungsgrundlage (`gamma1`) selbst — behebt einen Defekt, bei dem
  die Auswertung die Scheibe mit dem Verwaltungskostensatz der
  Generation statt der Tarifwerk-Regel rekonstruierte (+2,0 %
  Scheibenbeitrag).
* **Abschlüsse als Teil des Datenhaushalts** — festgeschriebene
  einzelvertragliche Bewertungsstände je Stichtag
  (`bestand/abschluss.py`, `cli_abschluss`): genau einer je Stichtag,
  nie überschrieben, mit Kern-Version je Zeile; die Kontrolle stellt
  die Neuberechnung dagegen und weist Abweichungen aus. Gerechnet über
  dieselbe einzelvertragliche Strecke (`auswertung.einzelwerte_am`),
  die auch die Berichts-Aggregation trägt.
