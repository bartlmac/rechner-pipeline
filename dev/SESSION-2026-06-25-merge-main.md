# Merge 2026-06-25 — feat/anthropic-provider nach main

Großer Integrations-Merge (Merge-Commit `72b9647`, echter no-ff-Merge). Bringt
den kompletten Feature-Strang seit `refactor/structure` -> `alex_1` ->
`feat/anthropic-provider` auf `main`. Freigabe in der Sitzung 2026-06-15
(Alexander dabei): Fixes zu den Review-Findings plus Merge.

## TL;DR

`main` enthält jetzt die plattformneutrale, Excel-freie Pipeline mit
Anthropic-Provider und festem Golden-Master-Orakel — inkl. der vier behobenen
Review-Findings. Volle Test-Suite grün (98 passed, 0 skipped mit
export-Extras), keine offenen Konflikte.

## Was auf main gelandet ist (Feature-Strang)

1. **src-Layout mit Phasen-Subpaketen** (`extract/`, `context/`, `generate/`,
   `qa/`, `orchestrate/`, `models/`) + öffentliche Runner-API; Wrapper
   `pipeline.py` / `agentic_pipeline.py` rückwärtskompatibel
   (aus `refactor/structure` + `alex_1`).
2. **Excel-freies Extraktions-Backend als Default** (`--export-backend openpyxl`,
   openpyxl + oletools, pure Python); COM bleibt als `--export-backend com`
   (Windows-Pfad).
3. **LLM-Provider-Abstraktion** `--provider {openai,anthropic}` + `--model`;
   Anthropic-Streaming, Truncation-Erkennung, `max_output_tokens`.
4. **Secret-Handling** über `*_FILE`-Pointer-Konvention.
5. **Fester Golden-Master-Harness** (`qa/golden_master.py`, Default
   `--test-mode fixed`) als unabhängiges Orakel; Test-LLM-Stufe entfällt.
6. **Security:** statisches Gate (`qa/security.py`) + Laufzeit-Confinement
   (`qa/fs_confine.py`).
7. **Agentische Variante** (`agentic.py`, LangGraph) mit Repair-Loop.
8. **Workflow-Log** (`RP_WFLOG`) + Replay-Provider + `demo_fixtures/` für die
   kostenfreie Vorführung.
9. **requires-python** 3.12 -> 3.11.

## Review-Findings (vor dem Merge behoben, Commit `3ba3e1e`)

Alle vier mit Tests; Details in den jeweiligen Modulen und in CR-002 §9.

- **F1 (hoch, Security):** `run_compare()` scannt die generierten `*.py` jetzt
  auch im `fixed`-Modus statisch vor Ausführung (der reviewte Harness importiert
  das untrusted `generated/test_run.py`). CR-002-Annahme korrigiert (Commit
  `8c9131b`).
- **F2 (hoch, Validierung):** `Report.ok` berücksichtigt `unmatched_columns` —
  fehlende Tabellenspalten mit Daten gelten nicht mehr still als bestanden.
- **F3 (mittel, Dossier):** `provider`, `max_output_tokens`, `export_backend`,
  `test_mode` ins Run-Dossier aufgenommen.
- **F4 (mittel, Extraktion):** openpyxl warnt bei Formelzellen ohne gecachten
  Wert (`export.formula_cache_missing`, strict_error).

## Konfliktauflösung

- `.gitignore`: allgemeinere Form vom Feature-Branch (`runs/` + `DEBUG_*.txt`
  deckt die alten `DEBUG_first/second`-Namen ab) + `docs-local/`;
  Claude-Overrides-Block zusammengeführt.
- `README.md`: von git automatisch gemergt.

## Validierung

- Volle Suite **98 passed, 0 skipped** auf dem gemergten Stand (System-pytest +
  `.venv`-openpyxl/oletools-site-packages, da `.venv` kein pytest hat und
  `pip install` gesperrt ist). `compileall src` sauber.

## Branch-Aufräumen (2026-06-25)

Nach dem Merge sind `feat/anthropic-provider`, `alex_1` und `refactor/structure`
**vollständig in `main` enthalten** (`git branch --merged main`). Die lokalen
Branches wurden gelöscht. Die Remote-Pendants (`origin/*`) und GitHub-PR #3
(Basis war `alex_1`) bleiben Bartek vorbehalten — PR #3 zuerst klären, dann
ggf. Remote-Branches entfernen.

## Push

`main` wurde **lokal** gemergt; `origin/main` ist unverändert. Push macht Bartek.

## Offene Follow-ups

Siehe `dev/FOLLOWUPS-post-merge-2026-06-25.md`.
