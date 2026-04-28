# Rechenkernentwicklung mit KI – Methodik, Leitplanken und Proof of Concept

> **Status:** öffentlicher Proof of Concept. Begleitender Arbeitsraum eines DAV-Projekts unter der AG Bestandsmigration. Vorgängerprojekt: [portxlpy](https://github.com/bartlmac/portxlpy) (handwerklicher und industrieller Workflow nebeneinander).

## Schnellstart

Voraussetzungen: **Windows mit installiertem Microsoft Excel**, **Python 3.13**, und ein gültiger **`OPENAI_API_KEY`**.

```powershell
git clone https://github.com/bartlmac/rechner-pipeline.git
cd rechner-pipeline

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

copy .env.example .env
# OPENAI_API_KEY in .env eintragen

python pipeline.py            # klassischer Lauf
python agentic_pipeline.py    # LangGraph-Variante mit Quality-Gates
```

Einmalige Excel-Einstellung: **Datei → Optionen → Trust Center → Einstellungen für das Trust Center → Einstellungen für Makros → „Zugriff auf das VBA-Projektobjektmodell vertrauen"**.

> **Hinweis zur Plattform:** Die Pipeline nutzt aktuell `pywin32` und ist dadurch auf Windows + Excel beschränkt. Eine plattformneutrale Extraktionsschiene (z. B. via `openpyxl`) ist Teil der weiteren Arbeit.

> **Hinweis zu den Beispieldaten:** `Tarifrechner_KLV.xlsm` und `Tarifrechner_Pipeline.pptx` sind synthetische Lehrbeispiele ohne realen Kundenbezug.

## Vision

Dieses Repository ist ein technischer und methodischer Arbeitsraum für die Frage, wie **KI und perspektivisch Agentensysteme die Rechenkernentwicklung sinnvoll unterstützen können**.

Im Zentrum steht nicht die Entwicklung eines unmittelbar einsetzbaren Standardtools, sondern der Aufbau eines **nachvollziehbaren, aktuarisch geführten Vorgehensmodells**. Wir wollen verstehen, wie sich fachliche Anforderungen, technische Umsetzung, Qualitätssicherung und menschliche Kontrolle in einem KI-gestützten Entwicklungsprozess sinnvoll zusammendenken lassen.

Dabei leiten uns insbesondere folgende Grundideen:

- **Methodik vor Produkt**: Ziel ist ein belastbares Vorgehen mit klaren Leitplanken, nicht ein universelles Toolversprechen.
- **End-to-End statt Einzelautomation**: Der Mehrwert entsteht im Zusammenspiel von Analyse, Kontextaufbereitung, Generierung, Review, Test, Dokumentation und Iteration.
- **Aktuarinnen und Aktuare in zentraler Rolle**: Fachliche Steuerung, Bewertung und Freigabe bleiben menschliche Kernaufgaben.
- **Whitebox-Prinzip**: Nachvollziehbarkeit, Prüfbarkeit, Reproduzierbarkeit und kontrollierte Verbesserung sind für diesen Kontext essenziell.
- **Pragmatischer Proof of Concept**: Wir wollen konkret zeigen, was heute bereits belastbar funktioniert, wo Grenzen liegen und welche Leitplanken notwendig sind.

Die langfristige Perspektive ist ein **methodischer Referenzrahmen für KI-gestützte Rechenkernentwicklung**: ein Ansatz, der technische Experimente, fachliche Verantwortung und Governance zusammenführt und damit Orientierung für weitere Anwendungen geben kann.

## Was ist unser MVP?

Unser aktuelles **Minimum Viable Product (MVP)** ist ein **End-to-End-funktionierender Proof of Concept**, mit dem sich ein KI-gestützter Entwicklungsablauf für Rechenlogik praktisch erproben und bewerten lässt.

Das MVP umfasst insbesondere:

- eine **durchgängige Pipeline** zur strukturierten Extraktion relevanter Artefakte,
- die **gezielte Aufbereitung von Kontext** für LLM-basierte Verarbeitung,
- die **Generierung von Code und Tests** in kontrollierten Schritten,
- einfache **Qualitäts- und Vergleichsmechanismen** zur Validierung der Ergebnisse,
- einen ersten **agentischen Orchestrierungsansatz** für wiederholbare Abläufe,
- sowie ein technisches Gerüst, an dem Fragen zu Rollen, Prüfpunkten, Fehlerschleifen und Governance konkret untersucht werden können.

Der Zweck des MVP ist damit:

1. die **Machbarkeit** eines durchgängigen KI-gestützten Ablaufs zu zeigen,
2. **Stärken und Grenzen** heutiger Modelle sichtbar zu machen,
3. Anforderungen an **Leitplanken, Qualitätssicherung und Human Oversight** herauszuarbeiten,
4. und eine belastbare Grundlage für die weitere methodische Arbeit zu schaffen.

## Weitere Entwicklungssprünge

Mögliche Entwicklungssprünge über das heutige MVP hinaus sind:

### 1. Robustere End-to-End-Pipeline
- bessere Zerlegung komplexer fachlicher Logik in verarbeitbare Arbeitspakete,
- stabilere Wiederholbarkeit der Ergebnisse,
- systematischeres Retry-, Debug- und Review-Verhalten.

### 2. Ausbau der Qualitätssicherung
- stärkere Testabdeckung,
- strukturierte Golden-Master-Vergleiche,
- automatische Konsistenzprüfungen zwischen Artefakten, generiertem Code und Testergebnissen.

### 3. Explainability und Governance
- sauberer Artefaktbezug,
- bessere Dokumentation der Herleitung,
- klar definierte menschliche Freigabepunkte,
- nachvollziehbare Protokollierung von Entscheidungen und Iterationen.

### 4. Agentische Zusammenarbeit spezialisierter Komponenten
- Trennung von Rollen wie Extraktion, Analyse, Code-Generierung, Test-Generierung, Review und Fehlerdiagnostik,
- explizite Orchestrierung dieser Rollen in einer kontrollierten Pipeline.

### 5. Erweiterung des Anwendungsbereichs
- Übertragbarkeit auf weitere fachliche Kontexte,
- perspektivisch Verknüpfung mit angrenzenden Fragestellungen wie ETL, Mapping, Verifikation und Dokumentation,
- Nutzung als methodischer Referenzrahmen für weitere KI-Use-Cases im Aktuariat.

---

# TarifRechner Pipeline

Dieses Projekt orchestriert eine zweistufige Pipeline:

1. Excel-Artefakte deterministisch exportieren und aufbereiten.
2. LLM-basierte Code- und Testgenerierung aus diesen Artefakten.

Die generierten Ordner `generated/` und `info_from_excel/` sind Laufzeit-Outputs und werden nicht manuell gepflegt.

## Projektstruktur

- `pipeline.py`
  - Dünner CLI-Einstiegspunkt.
  - Parst Argumente und startet den Runner.

- `pipeline_core.py`
  - Orchestriert den Ablauf (`export -> main_llm -> test_llm -> compare`).
  - Verwaltet Prompt-Bau, LLM-Aufrufe und Debug-Prompts.

- `matrix_extractor.py`
  - Rückwärtskompatible Fassade.
  - Re-exportiert die bisherigen öffentlichen Funktionen/Konstanten.

- `excel_exporter.py`
  - Excel-Export (Sheets, VBA, Name Manager).
  - Formel-Komprimierung.
  - Erzeugung des Export-Manifests.

- `scalar_table_extractor.py`
  - Ableitung von `*_scalar.json` und `*_table_values.csv` aus komprimierten CSVs.

- `llm_output_extractor.py`
  - Extraktion von `===FILE_START=== ... ===FILE_END===` Blöcken.
  - Sicheres Schreiben nach `generated/`.

- `prompt_builder.py`
  - Prompt-Template-Hilfen (Datei-Stuffing, Placeholder-Ersetzung, Trunkierung).

- `llm_client.py`
  - Aufbau und Validierung des OpenAI-Clients (`OPENAI_API_KEY`).

- `manifest_model.py`
  - Typisiertes Manifest-Modell (`ExportManifest`) inkl. `from_dict`/`to_dict`.

## Lauf (Beispiel)

```powershell
python pipeline.py --help
python pipeline.py
python agentic_pipeline.py --help
python agentic_pipeline.py --max_retries_main 1 --max_retries_test 1
```

## Agentic Orchestrierung (LangGraph)

- `agentic_pipeline.py`
  - Graph-basierte Orchestrierung fuer denselben Kernablauf (`prepare -> main_llm -> test_llm -> compare`).
  - Enthaelt Quality-Gates mit begrenzten Retries und Human-Review-Handoff.
  - Verwendet weiterhin die bestehende Business-Logik aus `PipelineRunner`.

Hinweis:
- Fuer den agentischen Einstieg wird `langgraph` benoetigt.

## Wichtige Hinweise

- Voraussetzungen für den Export:
  - Windows + installiertes Microsoft Excel
  - Excel Einstellungen: Datei -> Optionen -> Trust Center -> Einstellungen für das Trust Center -> Einstellungen für Makros -> „Zugriff auf das VBA-Projektobjektmodell vertrauen“
  - Python-Pakete laut `requirements.txt` (`openai`, `pandas`, `pywin32`, `langgraph`)
- Für LLM-Schritte muss `OPENAI_API_KEY` gesetzt sein (siehe `.env.example`).
- Die generierten Verzeichnisse `generated/` und `info_from_excel/` werden bei jedem Lauf neu erzeugt und sind nicht zu pflegen.

## Strukturelles Refactor (parallel)

In einem separaten Branch (`refactor/structure`) wird ein strukturelles Refactor des Repositories vorbereitet (Paketierung, Modulgrenzen entlang der Pipeline-Phasen, Trennung öffentlicher und interner API). Der Stand auf `main` ist bewusst der **lauffähige Demonstrator**. Hinweise zum Refactor-Branch sind willkommen — gerne als Issue oder Kommentar.

## Vorschlag für das Vorgehen

Für die weitere Arbeit an diesem Repository bietet sich ein bewusst zweigleisiges Vorgehen an:

### 1. Technische Weiterentwicklung des Proof of Concept
Das bestehende Repository wird schrittweise so weiterentwickelt, dass der End-to-End-Ablauf robuster, besser testbar und methodisch aussagekräftiger wird. Ziel ist ein sauberer Demonstrator mit klaren Prüfpunkten und reproduzierbaren Ergebnissen.

### 2. Methodische Verdichtung der Erkenntnisse
Parallel zur technischen Arbeit werden die gewonnenen Erfahrungen systematisch verdichtet:
- Welche Aufgaben eignen sich heute bereits gut für KI-Unterstützung?
- Wo liegen die Grenzen aktueller Modelle?
- Welche Rollen übernehmen Aktuarinnen und Aktuare sinnvoll in einem KI-gestützten Entwicklungsprozess?
- Welche Governance-, Freigabe- und Dokumentationsanforderungen sind notwendig?

### 3. Iterative Validierung an konkreten Teilproblemen
Anstatt früh einen universellen Zielzustand anzunehmen, sollten einzelne Arbeitsschritte gezielt verbessert und immer wieder an konkreten fachlichen Fällen überprüft werden. So entsteht ein belastbares methodisches Bild aus realen Iterationen.

### 4. Enge Verzahnung von Technik und Fachlichkeit
Die technische Entwicklung sollte laufend mit fachlicher Bewertung gekoppelt bleiben. Relevante Kriterien sind dabei insbesondere:
- fachliche Korrektheit,
- Reproduzierbarkeit,
- Nachvollziehbarkeit,
- Testbarkeit,
- Wartbarkeit,
- und die klare Verteilung von Verantwortung zwischen Mensch und KI.

## Nächste Schritte

### Kurzfristig
- Vision und Zielbild im Team abstimmen.
- Scope des MVP explizit festhalten.
- Qualitätskriterien für „funktioniert“ vs. „fachlich belastbar“ definieren.
- Bestehende Pipeline an den wichtigsten Schwachstellen stabilisieren.
- Rollenbild für Human-in-the-Loop, Review und Freigabe konkretisieren.

### Mittelfristig
- Agentische Zerlegung einzelner Arbeitsschritte weiter ausarbeiten.
- Test- und Vergleichslogik ausbauen.
- Explainability-Elemente und Artefaktbezug verbessern.
- Übertragbarkeit auf weitere fachliche Beispiele prüfen.
- Schnittstellen zu angrenzenden Themen wie ETL und Verifikation konkretisieren.

### Perspektivisch
- Methodik und Leitplanken dokumentieren.
- Ergebnisse in der Fachcommunity diskutieren.
- Prüfen, welche Bausteine sich später standardisieren oder offen bereitstellen lassen.

## Roadmap für die nächsten 24 Monate

### Phase 1: Konsolidierung des Proof of Concept (0–6 Monate)
- gemeinsames Zielbild schärfen,
- MVP klar abgrenzen,
- Repository bereinigen und stabilisieren,
- wichtigste End-to-End-Strecke reproduzierbar machen,
- erste methodische Lessons Learned dokumentieren.

### Phase 2: Ausbau von QS, Rollen und Orchestrierung (6–12 Monate)
- Test-Gates und Vergleichsmechanismen ausbauen,
- explizite Review- und Freigabeschritte definieren,
- agentische Rollenbilder konkretisieren,
- Fehler- und Eskalationslogik verbessern,
- erste belastbare Aussagen zu Grenzen und Erfolgsfaktoren formulieren.

### Phase 3: Übertragbarkeit und methodische Verdichtung (12–18 Monate)
- weitere fachliche Beispiele heranziehen,
- Übertragbarkeit auf andere Kontexte prüfen,
- Brücke zu angrenzenden Use Cases wie ETL-Verifikation schlagen,
- methodische Leitplanken konsolidieren,
- Governance- und Explainability-Aspekte systematisieren.

### Phase 4: Konsolidiertes Rahmenwerk und Ausblick (18–24 Monate)
- einen konsistenten methodischen Rahmen für KI-gestützte Rechenkernentwicklung formulieren,
- Bausteine für Dokumentation, Review und QS standardisieren,
- offene Punkte für weitergehende Forschung oder Tooling identifizieren,
- bewerten, welche Teile künftig in Richtung wiederverwendbarer Referenzbausteine weiterentwickelt werden können.

## Einordnung der Roadmap

Die Roadmap ist bewusst **methodisch** und nicht als klassischer Produktentwicklungsplan formuliert. Sie soll helfen,
- technische Experimente zu fokussieren,
- Ergebnisse fachlich einzuordnen,
- und aus einem funktionierenden Proof of Concept schrittweise ein belastbares Vorgehensmodell zu entwickeln.

Eine spätere Produktisierung einzelner Bausteine ist denkbar, steht derzeit aber nicht im Mittelpunkt. Vorrang hat die Entwicklung eines klaren methodischen Rahmens, der technische Machbarkeit, fachliche Verantwortung und kontrollierten KI-Einsatz zusammenführt.

## Mitwirken

Issues, Diskussionsanstöße und Pull Requests sind willkommen. Details siehe [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Lizenz

Veröffentlicht unter der [MIT-Lizenz](LICENSE).
