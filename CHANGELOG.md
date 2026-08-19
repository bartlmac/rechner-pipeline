# Changelog

Format angelehnt an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/).
Es gibt noch keine Release-Nummerierung: das Repository ist ein
öffentlicher Prototyp, der Stand wird hier mit Datum benannt. Die
Architektur-Entscheidungen selbst stehen als ADRs unter
`docs/architektur/` — dieser Changelog fasst sie zusammen und macht
einen vorgeführten Stand zitierbar.

## Unveröffentlicht — Stand 2026-08-19

### Was das System kann

* **Migrationsfall Ende-zu-Ende**: Fall-Arbeitsbereich anlegen, Quellen
  mit SHA-256 registrieren (`rechner_pipeline.fall`), Vorverdichtung je
  Quelltyp (XLSM, DOCX, Bestandsabzugs-CSV), Agenten-Extraktion je
  Quelle, deterministischer Merge zur A-Box mit Provenienz je Aussage,
  Widersprüche als Diskrepanz-Objekte, Projektion zur Tarif-Spez,
  parametrierter Kern, Abnahme gegen die Lieferung.
* **Sechs Gates** als je ein Kommando mit JSON auf stdout und Ledger:
  `extract` (G0), `abox_merge` (O0), `abox_validate` (O1),
  `generation_golden` (O3), `gate_entscheid` (P9), `bestand_validate`
  (B1). Ein Nicht-Null-Exit blockiert und wird nie zur Warnung.
* **Menschliche Gates G-1/G-2/G-T** mit unveränderlichen Snapshots;
  `--rolle mensch|agent` ist Pflicht, ein Agent kann ein menschliches
  Gate nur ablehnen.
* **Zielrechenkern 3.0.0**: KLV und Berufsunfähigkeit auf einem
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
* **Vier fallgebundene Tests skippen ohne lokalen Fall-Arbeitsbereich**
  (`faelle/archiv/baldrian-klv-tg2015`) — darunter der einzige
  Ende-zu-Ende-Beleg für Gate O3. In der CI und im frischen Clone
  läuft er nicht mit; ein eingechecktes Minimal-Fixture ist offen.
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
  `assurance`-Orchestrator und der zugehörige Skill entfallen;
  konserviert auf Branch `parked/portierung-excel` (Tag
  `portierung-excel-2026-08`). Erhalten bleiben `gates.extract` und der
  Ledger-Mechanismus.
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
