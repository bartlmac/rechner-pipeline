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
  - Python-Pakete: `pywin32`, `pandas`, `openai`
- Für LLM-Schritte muss `OPENAI_API_KEY` gesetzt sein.
