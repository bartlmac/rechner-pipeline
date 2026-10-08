# Changelog

Es gibt noch keine Release-Nummerierung: Das Repository ist ein
öffentlicher Prototyp, der Stand wird hier mit Datum benannt. Dieses
Dokument sagt, was der Stand kann und was er bewusst nicht kann. Die
einzelnen Änderungen stehen in der Geschichte des Repositorys, die
Entscheidungen dahinter als ADRs unter `docs/architektur/`.

## Stand 2026-10-08 — nach dem dritten Fall

### Was das System kann

* **Ein Migrationsfall vom Auftrag bis in die Ablage.** Die Lieferung wird
  registriert, und der Vorstand beauftragt den Fall (`A-M6`); jede Quelle
  wird vorverdichtet und extrahiert, zur A-Box mit Herkunft je Aussage
  zusammengeführt; Widersprüche werden Diskrepanz-Objekte und von einem
  Menschen entschieden; daraus entstehen Spez und parametrierter Kern; der
  Bestand wird transformiert und übernommen, in drei aktuariellen Tests und
  dem Migrationscontrolling abgenommen und danach in die Ablage des
  Tagesbetriebs gebracht. Ein scheiternder Fall endet mit dem gezeichneten
  Abbruch (`A-M5`). Ablauf: `docs/architektur/ablauf-eines-falls.md`.
* **Der dritte Fall der Baldrian:** 834 Verträge der
  Tarifgeneration KLV TG2015, übernommen zum 01.01.2026. Der Rechenkern
  ging dabei von 3.21.0 auf 3.22.0; die Ablage trägt danach 388
  Monatsabschlüsse.
* **Nachfahren ohne Agenten.** Ein festgehaltener Fall liegt als Paket im
  Repository (`pakete/`). Ein Aufruf stellt eine Welt auf dem Stand vor dem
  Fall auf, fährt den Fall nach und erzeugt eine Laufzeit mit übernommenem
  Bestand (`deploy/welt/laufzeit_aufstellen.sh`). Zwei Welten tragen in
  ihrer Ablage dieselben Bytes, gleich mit welchen Schlüsseln gezeichnet
  wird.
* **Menschliche Gates mit gezeichneten Snapshots:** `A-Q1`, `A-O1`,
  `A-K2`, `A-T1`, `A-M1` bis `A-M6`, `A-B1`, `A-B2`, `A-B3`. Wer zeichnen
  darf, steht in der Zeichnungsordnung; die Rolle wird aus dem Schlüssel
  bestimmt und wandert mitsigniert in den Snapshot. Agenten legen vor und
  können nur ablehnen (ADR-018).
* **Abnahme des Zielsystems außerhalb der Fälle.** Kernstand, T-Box-Stand,
  Tarifwerk und Anfangsbestand werden einmal in der Linie abgenommen; ein
  Fall zeichnet nur, was sich durch ihn ändert, und verweist sonst auf die
  geltende Abnahme (ADR-025).
* **Acht Prüf-Gates**, je ein Kommando mit JSON auf stdout und Ledger:
  `extract` (P-Q1), `abox_merge` (P-Q2), `abox_validate` (P-Q3),
  `generation_golden` (P-K1), `bestand_validate` (P-B1), `gate_entscheid`
  (P9), `aktuartest` (Vorlagen A-M1 bis A-M3) und `abnahmebericht` (Vorlage
  A-M4). Ein Exit ungleich null blockiert und wird nie zur Warnung.
  Vertrag und Versionen: `docs/architektur/gate-vertrag-und-versionen.md`.
* **Zielrechenkern 3.22.0:** KLV und Berufsunfähigkeit auf einem
  gemeinsamen (Semi-)Markov-Zustandsmodell mit Thiele-Rückwärtsrekursion;
  Tafelwerk als reine qx-Vektoren; Monatsreserven für Bilanzstichtage;
  vertragsweite Bewertung dynamischer Erhöhungsscheiben; Herabsetzung und
  Teilkündigung als getrennte Geschäftsvorfälle (ADR-023).
* **Bestandsmigration ohne Historienmigration:** konstruktive
  Neuberechnung mit Korrekturschicht (Grundsatzdokumentation, Abschnitt 9).
* **Geführter Bestand und Tagesbetrieb:** Der Bestand entsteht aus seinem
  Zugangsstrom (ADR-020) und wird mit Stammzustand und Journal geführt
  (ADR-011). Die PLV läuft Tag für Tag — Neugeschäft, nächtliche
  Fortschreibung, Monatsabschluss. Festgeschriebene Abschlüsse werden nie
  überschrieben.
* **Berichte des Betriebs:** Zu jedem Monatsabschluss entsteht ein
  Monatsbericht mit dem Stand am Monatsende und dem Verlauf der zwölf
  Monate davor, gelesen aus den festgeschriebenen Abschlüssen. Zum
  Jahresende kommt der Jahresbericht mit der Entwicklung seit
  Betriebsbeginn dazu. Wechselt die Bewertungskonvention der Abschlüsse im
  Berichtszeitraum, weist der Monatsbericht den Wechsel aus.
* **Zugang und Auslieferung sind abgenommen:** Der Betrieb nimmt den
  Zugang eines übernommenen Bestands mit einer Zugangsprobe ab (`A-B2`,
  ADR-022) und zeichnet, wenn ein Stand nach außen geht (`A-B1`).
* **Vorverdichtung** für Excel-Mappen, DOCX, Text-PDF und
  CSV-Bestandsabzüge; Agenten lesen nie Rohdateien.
* **Code-Ontologie:** Module und Tests deklarieren ihren Fachknoten;
  Index, Schichtenkarte, Impact und Landkarte werden daraus berechnet.
* **SDK-frei und deterministisch:** kein Modell-, Provider- oder
  Token-Pfad in `src/`; gleiche Eingaben ergeben byte-identische Artefakte.

### Was es bewusst noch nicht kann

* **Ein Paket ist an den Stand gebunden, auf dem es festgehalten wurde.**
  Nachfahrbar ist es nur auf einem Baum, der Kern und Tarifwerk unverändert
  trägt. Ändert sich einer der beiden Gegenstände, wird das Paket neu
  festgehalten (ADR-027, dort als offen benannt).
* **Formelidentität ist keine Maschinenprüfung.** Der Formel-Rück-Check
  in Gate P-Q3 deckt eine Formelform, die IF-Staffeln; jede andere meldet
  er als benannten Zustand, statt sie nachzurechnen. Ob Tarifmeldung und
  Tarifrechner dieselbe Formel meinen, entscheidet ein Mensch gegen den
  Tarifplan.
* **Die Regression des Kerns für `A-K2` ist nicht gebaut.** Die Abnahme
  führt sie als benannte Ausnahme „nicht gefahren, Werkzeug noch nicht
  erstellt“; sie deckt dann nur die qualitative Prüfung der Änderungen.
* **Belege tragen Pfade des Rechners, auf dem sie entstanden.** Die
  Ledger der Gates halten die Kommandozeile wörtlich fest, das
  Eingangsregister den Herkunftspfad jeder Datei. Unkenntlich gemacht
  werden bisher nur Schlüsselpfade.
* **Kein geteilter Fall-Speicher.** Der Arbeitsbereich eines Falls liegt
  lokal und nicht im Repository; die Nachweiskette eines live geführten
  Falls endet an einem Einzelplatz.
* **Der Knoten-Lebenszyklus** (`in_migration` / `abgenommen`, ADR-007
  Regel 4) ist nicht umgesetzt.
* **Eine Plattform, nicht viele.** Referenz ist Linux mit Python 3.11;
  alles andere läuft im Container. Der Code wird nicht auf weitere
  Betriebssysteme gehärtet.
* **Kein Graph-Store, keine Embeddings, kein MCP/RPC-Pfad.** Die portable
  Basis sind lokale Dateien und einfache Python-Kommandos.

Weitere offene Punkte, fachlich und technisch: `dev-docs/offene-punkte.md`.

### Entscheidungen seit ADR-016 (2026-09-01)

| Entscheidung | Inhalt |
|---|---|
| ADR-017, ADR-018 (2026-09-05) | vier Ebenen im Paket; Rollenmodell mit Zeichnungsordnung und Schlüsselklassen |
| ADR-019 (2026-09-20) | die Testsuite läuft parallel |
| ADR-020 (2026-09-21) | der Bestand entsteht aus dem Zugangsstrom |
| ADR-021 (2026-09-22) | Belegrollen und Freigabesignatur als gemeinsamer Vertrag |
| ADR-022 (2026-09-30) | Zugangsabnahme `A-B2` mit Zugangsprobe |
| ADR-023 (2026-10-01) | Herabsetzung und Teilkündigung getrennt |
| ADR-024 (2026-10-01) | T-Box 0.2.0: Tarifwerk, Geschäftsvorfälle, Zustandsextrakt |
| ADR-025 (2026-10-01) | Erstabnahme des Zielsystems in der Linie |
| ADR-026 (2026-10-01) | Fallauftrag `A-M6` und Fallabbruch `A-M5` |
| ADR-027 (2026-10-04) | fünf Gegenstände des Repositorys, keine Infrastruktur |
