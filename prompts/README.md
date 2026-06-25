# Prompts

LLM-Prompts sind die zentralen Verträge der Pipeline und werden hier **versioniert** abgelegt.

## Konvention

```
prompts/
└── v<N>/
    ├── excel_to_py.txt      Hauptprompt: Excel-Artefakte → Python-Module
    └── test_advanced.txt    Folgeprompt: Generierung des Regressionstests
```

- Jede neue Version liegt in einem eigenen Unterordner (`v1`, `v2`, …).
- Innerhalb einer Version werden Prompts **nicht überschrieben**, sondern bei Änderungen wird eine neue Version angelegt.
- Welche Version aktiv ist, steuert der `PipelineRunner` (siehe `src/rechner_pipeline/orchestrate/runner.py`).

## Aktuelle Version

`v1` — Stand der ersten öffentlichen Veröffentlichung (28.04.2026).

Beide Prompts erwarten die Platzhalter `{{PIPELINE_META}}` und `{{INPUT_FILES}}`,
die der `PipelineRunner` zur Laufzeit ersetzt.
