# Rechenkernentwicklung mit KI – Methodik, Leitplanken und Proof of Concept

> **Status:** öffentlicher Proof of Concept. Begleitender Arbeitsraum eines
> DAV-Projekts unter der AG Bestandsmigration. Vorgängerprojekt:
> [portxlpy](https://github.com/bartlmac/portxlpy).

Dieses Repository migriert einen Excel/VBA-Tarifrechner **1:1 in einen reinen
Python-Rechenkern** und weist die funktionale Äquivalenz gegen ein
unabhängiges Golden-Master-Orakel nach. Die Migration leistet ein
**Coding-Agent** (Codex- oder Claude-CLI) — als **einmaliger
Übersetzungsakt**; dieses Paket ist die **deterministische, SDK-freie
Abnahme-Schicht**: es extrahiert die Eingaben, fährt eine Kette von
Prüf-Gates und erzeugt ein nachvollziehbares Abnahme-Dossier.

Das Ergebnis der Migration lebt als **stabiler, versionierter Rechenkern**
(`rechner_pipeline.kern`) im Repo weiter — Software zusammen mit Bestand und
Tests, die sich im Betrieb nicht verändert. Das **Bestandsdaten-Modul**
liefert dazu synthetische, fortschreibbare Bestände, deren Datenmodell 1:1
auf dem Kern-Contract liegt. Zusammen ergibt das das vollständige, laufende
Beispiel der Methodik: **Rechenkern + Bestand + Assurance** — und die Bühne
für den eigentlichen Anwendungsfall: das KI-System baut **marginale
Änderungen** in den stabilen Kern ein (neue Tarifgeneration, neues Produkt)
und bindet neu zu migrierende Bestände über Datentransformationen an.

## Vision

Dieses Repository ist ein technischer und methodischer Arbeitsraum für die Frage,
wie **KI und Agentensysteme die Rechenkernentwicklung sinnvoll unterstützen
können**. Im Zentrum steht nicht ein fertiges Standardtool, sondern ein
**nachvollziehbares, aktuarisch geführtes Vorgehensmodell** — wie fachliche
Anforderungen, technische Umsetzung, Qualitätssicherung und menschliche Kontrolle
in einem KI-gestützten Entwicklungsprozess zusammenwirken.

Leitideen:

- **Methodik vor Produkt** — ein belastbares Vorgehen mit klaren Leitplanken,
  kein universelles Toolversprechen.
- **End-to-End statt Einzelautomation** — Wert entsteht im Zusammenspiel von
  Analyse, Kontextaufbereitung, Generierung, Review, Test, Dokumentation und
  Iteration.
- **Aktuarinnen und Aktuare in zentraler Rolle** — fachliche Steuerung, Bewertung
  und Freigabe bleiben menschliche Kernaufgaben.
- **Whitebox-Prinzip** — Nachvollziehbarkeit, Prüfbarkeit, Reproduzierbarkeit und
  kontrollierte Verbesserung sind essenziell.

Die langfristige Perspektive ist ein **methodischer Referenzrahmen für
KI-gestützte Rechenkernentwicklung**, der technische Experimente, fachliche
Verantwortung und Governance zusammenführt.

Konkretes Zielbild (Stand August 2026): **stabiler Kern + marginale
KI-Änderungen.** Der KLV-Kern ist nach dem einmaligen agentischen
Übersetzungsakt eine stabile, versionierte Komponente; das
Bestandsdaten-Modul liefert die **Datenbasis, die genau dieser Kern
verarbeiten kann**, und wird per Ereignis-Fortschreibung über die Zeit
entwickelt. Auf dieser Basis entsteht der eigentliche
Migrations-Anwendungsfall: das KI-System erweitert den Kern um eine neue
Tarifgeneration oder ein neues Produkt, bindet den neu zu migrierenden
Bestand über eine **Datenmodell-Transformation** an, und die
Assurance-Schicht nimmt die **Änderung** mechanisch ab (Regression:
Bestehendes bleibt, Neues stimmt).

## Ansatz: Agent generiert, deterministische Schicht nimmt ab

Die Verantwortung ist klar getrennt:

- **Generierung und Selbstkorrektur** besitzt ein externer Coding-Agent (Codex-
  oder Claude-CLI) über die Skill `build-vergleichsrechenkern`. Der Agent schreibt
  den Rechenkern und repariert ihn anhand der Gate-Rückmeldungen, bis er besteht.
- **Abnahme** besitzt dieses Paket — rein deterministisch. Es gibt **keine**
  Modell-, Provider-, Token- oder Reasoning-Fläche und keinen LLM-Pfad in der
  Abnahme. Die Prüfung ist damit unabhängig von der (probabilistischen)
  Generierung und selbst nachvollziehbar.

Diese Trennung ist bewusst: das probabilistische Schreiben und das deterministische
Prüfen sind zwei verschiedene Dinge, und nur die Prüfung entscheidet über die
Annahme.

## Die Gate-Kette (`assurance`)

Der Befehl `assurance` fährt die deterministische Prüf-Kette **in Reihenfolge**
über einen bereits generierten Rechenkern und endet mit einem `dossier`-Verdikt.
Er enthält selbst keine Gate-Logik, sondern ruft die einzelnen Toolbox-Gates auf
und aggregiert deren Ergebnisse:

```
extract → validate → security → conventions → golden_master → algebraic → roundtrip → dossier
```

- **extract** — deterministische Extraktion der Excel-Artefakte (Zellformeln +
  gecachte Werte + Defined Names via openpyxl, VBA via `oletools.olevba`) sowie
  der Skalar-/Tabellen-Erwartungswerte.
- **validate** — der Sechs-Datei-Contract des Rechenkerns.
- **security** — statische Prüfung des generierten Codes (blockt Netz, Subprozess,
  dynamische Ausführung, schreibende/gefährliche Aufrufe).
- **conventions** — Architektur-/Namenskonventionen des Kerns.
- **golden_master** — Vergleich der berechneten Werte gegen die aus dem Excel
  extrahierten Erwartungswerte (unabhängiges Orakel).
- **algebraic** — property-based Prüfung aktuarieller Identitäten gegen einen
  deklarativen `qa_contract.json` (Sterblichkeits-, Kommutations- und
  Barwert-Identitäten); geprüft mit Hypothesis. Übersprungen ohne `--qa-contract`.
- **roundtrip** — Roundtrip-/Konsistenzprüfungen.
- **dossier** — aggregiert die Gate-Ergebnisse zum Abnahme-Verdikt.

Jedes Gate schreibt sein Ergebnis als einzelnes JSON auf stdout und eine
`<command>.gate.json`-Ledger-Datei in den gemeinsamen `--diagnostics-dir`.
`extract` und `validate` sind Voraussetzungen; schlägt eine fehl, werden die
QA-Gates übersprungen, `dossier` läuft aber weiter und protokolliert ein ehrliches
blockiertes Verdikt. `security`..`roundtrip` laufen **continue-on-fail**, damit
ein Lauf das vollständige Bild liefert. Ein Nicht-Null-Exit ist **blockierend**
und wird nie zu einer Warnung abgeschwächt.

## Schnellstart

Voraussetzung: **Python 3.11 oder neuer**. Kein LLM-Key nötig — die Abnahme ist
SDK-frei.

```bash
git clone https://github.com/bartlmac/rechner-pipeline.git
cd rechner-pipeline

python -m venv .venv
. .venv/bin/activate                 # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
```

Voller Abnahme-Lauf über einen bereits generierten Rechenkern:

```bash
rechner-pipeline assurance --repo-root . --input examples/Tarifrechner_KLV.xlsm \
    --generated-dir <gen> --info-dir <info> --diagnostics-dir <diag> \
    [--qa-contract qa_contract.json] [--adapter auto|excel] \
    [--export-backend openpyxl|com] [--strict-manifest-warnings] \
    [--max-attempts N]
```

Quell-neutrale Optionen: `--input <pfad>` (Excel heute, Adapter-Naht für weitere
Quellen; `--excel` bleibt als kompatibler Alias). `--adapter auto|excel`.
`--export-backend openpyxl|com` — `openpyxl` ist der plattformneutrale Default
(Windows/macOS/Linux, ohne Microsoft Excel); `com` benötigt Windows + Excel.
`--strict-manifest-warnings` behandelt `strict_error`-Manifest-Warnungen als
blockierend.

Jedes Gate ist auch einzeln lauffähig:

```bash
python -m rechner_pipeline.toolbox.<command> [flags]
```

## Sicherheit und Reproduzierbarkeit

- **Statisches Gate** (`security`) prüft den generierten Code vor jeder
  Ausführung.
- **Laufzeit-Confinement** (`qa/fs_confine.py`): der Golden-Master-/Roundtrip-Lauf
  führt den generierten Code in einem Subprozess aus, in dem Schreiben, Lesen
  außerhalb des Repos, Netz (`socket`), Subprozesse (`subprocess`, `os.system`)
  und schreibende `os`-Primitive hart abgewiesen werden.
- **Unabhängiges Orakel**: die Erwartungswerte stammen deterministisch aus dem
  Excel, nicht vom Modell; der Vergleichs-Harness ist reviewter Code.
- **Gepinnte Abhängigkeiten** (openpyxl/oletools/pandas/pyarrow/matplotlib,
  exakt) für reproduzierbare Läufe.

## Der stabile Rechenkern (`rechner_pipeline.kern`)

Die Promotion des am 22.07.2026 agentisch migrierten und mechanisch
angenommenen KLV-Kerns (Golden-Master 617/617) in versionierte Software —
formeltreu (Excel-/VBA-Semantik inkl. 16-stelliger Excel-Rundung), aber mit
**parametrisierter API** statt der Bindung an einen festen Modellpunkt:

```python
import dataclasses
from rechner_pipeline.kern import KLV_DEFAULT, berechne

ergebnis = berechne(KLV_DEFAULT)              # Golden-Master-Referenzvertrag
mp = dataclasses.replace(KLV_DEFAULT, x=30, sex="F", zins=0.0225, tafel="DAV2008_T")
ergebnis2 = berechne(mp)                      # beliebiger Modellpunkt, in-process
```

Kommutationswerte werden je Rechnungsbasis (Geschlecht, Tafel, Zins) gebaut
und gecacht; fehlende Tafeln führen zu einem harten Fehler (kein erfundenes
qx). Die Parität zum angenommenen Migrationsergebnis ist testseitig verankert
(617/617 gegen die extrahierten Erwartungswerte, geprüft mit der
Golden-Master-Engine der Abnahme-Schicht). Der transiente Migrationspfad
(`generated/` + Gates) bleibt daneben bestehen — für künftige einmalige
Übersetzungen weiterer Produkte.

**Rechenrückgrat (seit Kern 2.0.0): ein (Semi-)Markov-Zustandsmodell**
(`kern/zustandsmodell.py`) — benannte Zustände, jährliche Übergänge,
Bewertung per Thiele-Rückwärtsrekursion, Dauerabhängigkeit über
Zustandsraum-Erweiterung (Select-Perioden-Prinzip). KLV ist der
2-Zustands-Spezialfall (aktiv/tot) hinter demselben Barwerte-Interface;
weitere Produkte sind Konfigurationen dieser Engine, keine neuen Engines —
als erstes Beispiel ist **Berufsunfähigkeit** implementiert
(`kern/produkte/bu.py`: drei Zustände aktiv/bu/tot, Select-Tafeln mit
Dauerabhängigkeit) — gerechnet auf den **DAV-1997-I-Ausscheideordnungen**
(Invalidisierung, Aktivensterblichkeit, Reaktivierung und
Invalidensterblichkeit, je Geschlecht).
Der Wechsel des produktiven Pfads von der Kommutations- auf die
Zustandsmodell-Schiene wurde über eine **Toleranz-Überleitung** abgenommen
(`qa/ueberleitung.py`: Abnahme-Lauf 6.170 Werte über 10 Modellpunkte, keine
Abweichung außerhalb der Rundungsklasse, maximal 4e-13 relativ; der
dauerhafte Kreuz-Check fährt heute einen Standard-Sweep über 16
Modellpunkte); die Kommutations-Schiene bleibt dauerhaft als Kreuz-Check
erhalten, und die 617/617-Parität gilt unverändert.

## Bestandsdaten: synthetischer, fortschreibbarer Bestand

Das Modul `rechner_pipeline.bestand` erzeugt synthetische KLV-Bestände als
**echten Input für den Zielrechenkern** — committeter, reviewter,
deterministischer Code (wie die Abnahme-Schicht; im Gegensatz zum
agent-generierten Kern). Fachliche Referenz ist eine R-Toolchain aus dem
DAV-Kontext (Bestandserzeugung + Zeitscheiben); die Implementierung ist eine
eigenständige Neuentwicklung, keine Portierung.

Prinzipien:

- **Schema stromabwärts des Kerns:** `models/bestand.py` definiert das
  Portfolio-Schema als statischen Anker. Die Vertragsfelder entsprechen 1:1 dem
  `ModelPoint`-Contract des generierten Kerns; `model_point_kwargs` und
  `render_inputs_py` machen die Kopplung ausführbar (sie erzeugen das
  `inputs.py` für den Kern-Aufruf).
- **Der Generator rechnet nichts:** Prämien, Barwerte und Reserven liefert
  ausschließlich der Rechenkern — der stabile Kern (`rechner_pipeline.kern`)
  direkt in-process; frisch agentisch generierte (noch nicht promotete)
  Kerne über den abgesicherten Kind-Prozess-Pfad (`bestand/kernlauf.py`:
  Laufzeit-Confinement + vorgeschalteter Security-Scan).
- **Deterministisch reproduzierbar:** Seed in der TOML-Config, je
  Tarifgeneration ein eigener Zufallsstrom (eine neue Generation ändert
  frühere Verträge nicht); die Parquet-Ausgabe ist byte-reproduzierbar
  (Golden-Master per SHA-256).
- **Realistische Abhängigkeiten:** konfigurierbare Randverteilungen je Merkmal
  plus Gauß-Copula mit Spearman-Rangkorrelationen (ohne scipy). Nicht
  realisierbare Korrelations-Kombinationen sind ein Config-Fehler, keine
  stille Reparatur.
- **Fortschreibung als Zeitscheibe:** ein Stichtag *filtert* den Bestand und
  *leitet ab* (Alter mit 6-Monats-Rundung, abgelaufene/verbleibende Monate mit
  der Invariante `months_exp + months_rem == 12 · duration`); Stammdaten
  bleiben unangetastet.
- **Ereignis-Engine (`bestand/ereignisse.py`):** die Fortschreibung als
  Statushistorie — Storno, Tod, Beitragsfreistellung (PEX) und Ablauf werden
  jährlich auf Vertragsjahrestagen simuliert (konfigurierbare Raten,
  Tod nach Tafel-qx). Jeder Betrag (Rückkaufswert, beitragsfreie Summe,
  Leistungen) kommt in-process aus dem stabilen Kern. Deterministisch: ein
  Zufallsstrom je Vertrag; ein längerer Horizont ändert frühere Ereignisse
  nicht, Läufe verschiedener Raten sind pfadweise vergleichbar (Common
  Random Numbers).
- **Dynamische Erhöhungen (Schichtungsprinzip):** eine angenommene Erhöhung
  erzeugt eine neue Scheibe — aktuariell ein eigener Modellpunkt auf
  derselben Tarifgeneration (Eintrittsalter = aktuelles Alter, Laufzeiten =
  Restlaufzeiten, Summe = konfigurierter Prozentsatz der aktuellen
  Gesamt-VS). Der Vertragszustand ändert sich nicht; der GeVo steht im
  Ledger, die Scheibe in der Scheiben-Tabelle, und alle späteren Beträge
  summieren über Grund- und Erhöhungsscheiben (Stornoabschlag-Grenzen
  gelten je Vertrag, nicht je Scheibe).
- **Neuzugang als GeVo-Strom:** die Bestandsentwicklung ist ein einziger
  Strom datierter Geschäftsvorfälle — der Generator ist seine
  Batch-Auswertung bis zum Referenzstichtag, `fortschreiben(...,
  neuzugang_ab=...)` setzt denselben Erzeuger inkrementell fort
  (`neuzugang_pro_jahr` je Generation, eigener Zufallsstrom je
  Kalenderjahr). Neue Verträge erhalten einen ZUG-Ledger-Eintrag und
  werden ab Beginn mitsimuliert; ein längerer Horizont ändert frühere
  Zugänge nicht, und pro Zeitfenster schreibt genau ein Erzeuger
  (Doppelzählungs-Guard).
- **Aktuarielle Auswertungen (`bestand/auswertung.py`):** Deckungskapital
  und Rückkaufswert je Stichtag über den ganzen Bestand — in-process über
  `Rechenkern.zustand_am`, nach Beitragsfreistellung über die beitragsfreie
  Reserve. Der Bestandsbericht (`toolbox/bestand_report`) zeigt
  Abgangs-Sichten, Nachweisungen und Reserveverläufe als eine
  selbst-enthaltene HTML-Datei (Inline-SVG, kein Werkzeug beim Empfänger
  nötig). `--stichtag` teilt die Nachweisungen in Historie und Prognose.
- **Ein Bestand, mehrere Versicherungsarten:** ein Unternehmen führt
  einen Bestand; getrennt sind die *Nachweisungen*, nicht der Bestand.
  `examples/bestand_gesamt.toml` konfiguriert entsprechend beide
  Versicherungsarten in einem Bestand — ein Lauf, ein Bericht mit beiden
  Nachweisungen.
- **Zwei Produkte im Bestand:** Verträge tragen einen Produkt-Diskriminator
  (`produkt` = `klv` | `bu`) und die produktführende Leistungsspalte
  (Versicherungssumme bzw. versicherte Jahresrente). Für **BU** simuliert
  die Ereignis-Engine denselben Zustandsprozess, den der Kern bewertet —
  Invalidisierung, Reaktivierung, Tod und Ablauf aus den vier
  Ausscheideordnungen, nicht aus freien Raten; die Wahrscheinlichkeiten
  der Simulation laufen dabei über die Erfahrungsannahmen (nächster
  Punkt), die Bewertung unverändert auf erster Ordnung. Die Statushistorie wechselt dabei strikt
  alternierend zwischen Anwärterstand und Leistungsbezug; Reserven kommen
  aus dem Kern (Aktiven- bzw. Invalidenreserve mit der Dauer seit
  Rentenbeginn). Beispiel-Config: `examples/bestand_bu.toml`.
- **Erfahrungsannahmen (3. Ordnung):** die Fortschreibung würfelt nicht
  aus den Rechnungsgrundlagen, sondern aus einer eigenen Annahmenschicht.
  Jede Ereigniswahrscheinlichkeit entsteht nach einer Regel aus der ersten
  Ordnung — `annahme = a + b · erste_ordnung`. Der Faktor `b` rechnet die
  Sicherheitsmarge heraus, und zwar richtungsrichtig (bei belastenden
  Ausscheideordnungen `b < 1`, bei entlastenden wie der Reaktivierung
  `b > 1`); Ereignisse ohne Rechnungsgrundlage — Storno,
  Beitragsfreistellung, dynamische Erhöhung — tragen ihre Rate in `a` bei
  `b = 0`. Die **Bewertung bleibt unberührt**: Beiträge und Reserven
  rechnet der Kern unverändert auf erster Ordnung. Konfiguriert wird das
  je Bestand unter `[annahmen]`.
- **Bestandsbewegung (Nachweisungs-Struktur):**
  `kennzahlen.bewegungskonto` führt die Bewegung je Kalenderjahr in der
  Struktur der BaFin-Nachweisungen zur Bestandsbewegung — getrennt nach
  beitragspflichtig/beitragsfrei, jeweils Stück und Versicherungssumme.
  Abgänge werden zu Versicherungssummen (inklusive Erhöhungsscheiben)
  geführt, die Beitragsfreistellung als Umbuchung zwischen den Tracks;
  dadurch gilt die Identität Anfangsbestand + Zugang - Abgang =
  Endbestand exakt. BU wird als **eigene Nachweisung** geführt (Anwärter
  und Leistungsbezieher, Bezugsgröße Jahresrente) — Versicherungssummen und
  Jahresrenten sind nicht addierbar. Der Bericht rendert die Tabellen mit
  `--bis` (dem Fortschreibungs-Horizont — nur vollständig simulierte Jahre
  sind ausweisbar), das Gate B1 prüft beide Identitäten hart.
- **Ein-Befehl-Workflow:** `toolbox/bestand_fortschreibung` fährt den
  ganzen GeVo-Strom (erzeugen bis Referenzstichtag, fortschreiben bis
  Horizont) und schreibt alle Tabellen als Parquet; das Gate
  `toolbox/bestand_validate` (B1) prüft Bestand, Statushistorie,
  Erhöhungsscheiben, Plausibilitäts-Bänder und (mit `--ledger --bis`)
  die Bewegungs-Identitäten im Toolbox-Contract (JSON-stdout,
  Gate-Ledger).

Verwendung:

```python
import datetime as dt
from rechner_pipeline.bestand.config import load_config
from rechner_pipeline.bestand.generator import generate
from rechner_pipeline.bestand.zeitscheibe import zeitscheibe
from rechner_pipeline.bestand.ereignisse import fortschreiben, mit_zugaengen
from rechner_pipeline.bestand.auswertung import auswertungs_verlauf
from rechner_pipeline.bestand.parquet_io import write_portfolio

config = load_config("examples/bestand_klv.toml")   # 2 KLV-Generationen
referenz = dt.date(2010, 1, 1)
portfolio = generate(config, bis=referenz)          # Batch bis Referenzstichtag
ergebnis = fortschreiben(portfolio, config, dt.date(2035, 1, 1),
                         neuzugang_ab=referenz)     # GeVo-Strom danach
bestand = mit_zugaengen(portfolio, ergebnis.zugaenge)
write_portfolio(bestand, "bestand.parquet")
scheibe = zeitscheibe(bestand, dt.date(2012, 1, 1))
kennzahlen = auswertungs_verlauf(bestand, ergebnis.historie, config,
                                 [dt.date(2020, 1, 1)],
                                 scheiben=ergebnis.scheiben)
```

Simulierter Neuzugang (`neuzugang_ab`) wirkt nur, wenn `neuzugang_pro_jahr`
je Generation gesetzt ist — in der Beispiel-Config ist die Zeile bewusst
auskommentiert (Default 0, der Aufruf ist dann ein No-op).

Geprüft wird über die Test-Suite (Schema-Validierung, Verteilungs-Sanity-
Bänder, Zeitscheiben-Invarianten, Kern-Roundtrip) und über das
Toolbox-Gate `bestand_validate` (B1, siehe oben); als eigene Gate-CLIs
stehen noch `bestand_golden` (Parquet-Byte-Hash bei festem Seed) und
`bestand_zeitscheibe` (Invarianten) aus.

## Dokumente: Tarifpläne und Doku-Engine

Tarifplan-Dokumente leben in zwei getrennten Welten:

- **Zielkern-Tarifpläne** (`docs/tarifplaene/klv.md`, `bu.md`): neu
  verfasste, versionierbare Fachdokumente in der Mathematik des Kerns
  (Zustandsmodell, Thiele-Rekursion, GeVo-Katalog mit Betragsformeln) —
  keine Konversionen der Quell-Dokumente.
- **Migrationsstaging** (`toolbox/tarifplan_staging`): die DOCX-Tarifpläne
  der Quellsysteme (`examples/Mitteilung_143_*.docx`) sind
  Migrationsartefakte; das Kommando extrahiert sie deterministisch und
  stdlib-only nach strukturiertem JSON (`migrationsstaging/`, gitignored)
  — maschinenlesbar für den Migrations-Anwendungsfall, nicht hübsch.

Gerendert werden die Zielkern-Tarifpläne über die **Doku-Engine** — ein
gepinnter Quarto/Typst/Pandoc-Container (`docs/engine/`, optional als
Image über ghcr, GitHub-Workflow `docs-image.yml`), damit keine
Dokument-Toolchain in die Python-Dependencies wandert:

```bash
docs/engine/render.sh                 # alle Tarifplaene nach PDF (Typst)
IMAGE=local docs/engine/render.sh     # ohne ghcr: Engine lokal bauen
```


## Agenten-Anbindung

Claude-CLI wird über `.claude/skills/` unterstützt, Codex-CLI über die
`AGENTS.md` im Repo-Root plus gespiegelte Skills unter `.agents/skills/`. Die
Codex-Kopien werden auf Parität mit den Claude-Skill-Bodies getestet, damit ein
Workflow nicht still vom anderen abweicht. Die portable Basis ist: lokale Dateien
plus einfache Python-Kommandos — kein MCP/RPC-Pfad.

## Beispieldaten

Demo-Artefakte liegen unter `examples/` (`Tarifrechner_KLV.xlsm`,
`Tarifrechner_FLV_v1.xlsm`, Bestands-Konfiguration `bestand_klv.toml` u. a.).
Es sind **synthetische Lehrbeispiele** ohne realen Kundenbezug.

## Mitwirken

Beiträge laufen über GitHub-Collaborators auf Vertrauensbasis; siehe
`CONTRIBUTING.md` und `AGENTS.md`. **Arbeitsweise am gemeinsamen Branch:** klonen
und lokal arbeiten, **kein direkter Push** in den gemeinsamen Branch — Änderungen
werden nach Absprache übernommen.

## Lizenz

MIT — siehe `LICENSE`.
