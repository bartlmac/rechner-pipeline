# CR-003 — CI: GitHub-Actions-Matrix (Linux / macOS / Windows)

- **Status:** Vorschlag (Entscheidung offen)
- **Datum:** 2026-05-29
- **Branch-Kontext:** `feat/anthropic-provider`
- **Betroffen:** neue Datei `.github/workflows/ci.yml` (noch NICHT angelegt)
- **Abstimmung:** mit Bartek/Alexander (Repo-Infra, Actions-Minuten)

## 1. Problem / Ziel

Die Pipeline ist seit dem Excel-freien Backend **per Design** plattformneutral
(openpyxl + oletools + anthropic = pure Python), bislang aber **nur auf Linux
empirisch verifiziert**. Ziel: „cross-platform" **automatisch** absichern statt
zu behaupten — Tests + ein Excel-freier Export-Smoke auf **Linux/macOS/Windows**
über mehrere Python-Versionen, bei jedem Push/PR.

## 2. Vorschlag — `.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches: [main, "feat/**", "refactor/**"]
  pull_request:

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  test:
    name: tests (${{ matrix.os }}, py${{ matrix.python }})
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python: ["3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python }}
          cache: pip
      # Editable-Install inkl. Extras. pywin32 wird per sys_platform-Marker
      # nur auf Windows installiert; KEIN API-Key nötig (Tests nutzen Fakes).
      - name: Install
        run: pip install -e ".[all,dev]"
      - name: Tests
        run: pytest -q
      # Excel-freier Default-Backend (openpyxl + oletools), ohne LLM-Key:
      # smoke-testet die Roh-Extraktion + Scalar/Table + Manifest auf jeder OS.
      - name: Export-Smoke (kein API-Key)
        run: python pipeline.py --skip_main_llm --skip_test_llm --skip_compare_run
```

## 3. Was das abdeckt

- **Volle Test-Suite** auf 3 OS × 3 Python-Versionen. Die bisher per
  `importorskip` übersprungenen openpyxl/oletools-Tests **laufen** hier (Extra
  `all` installiert die Deps).
- **Excel-freier Export-Smoke** gegen `examples/Tarifrechner_KLV.xlsm` auf jeder
  Plattform → bestätigt openpyxl/olevba-Pfad real auf macOS/Windows.
- **Windows-Feinheit aus CR-Kontext:** Die Fixed-Mode-/Compare-Integrationstests
  starten echte Subprozesse → `fs_confine` (Pfad-Scope, `os.sep`/`realpath`) wird
  damit **direkt auf windows-latest** ausgeübt → klärt die case-Sensitivitäts-Frage.

## 4. Bewusste Grenzen

- **COM-Backend (`--export-backend com`) NICHT testbar** auf CI (kein echtes
  Excel/pywin32-COM auf Runnern) → nur der openpyxl-Default wird abgedeckt. COM
  bleibt manuell (z. B. dein Windows+Excel-Golden-Master-Lauf).
- **LLM-Stufen nicht end-to-end** in CI (kein `ANTHROPIC_API_KEY`/`OPENAI_API_KEY`
  als Secret hinterlegt; Tests decken die Provider-Logik per Fakes ab). Bewusst:
  kein Token-Verbrauch / keine Secrets in CI.

## 5. Offene Fragen

1. **Extras-Umfang:** `all` zieht auch `langgraph` (für agentic) — evtl. auf
   `".[export,llm,anthropic,dev]"` trimmen für schnellere/robustere Installs?
2. **Ruff:** separater Lint-Job (`ruff check`) gewünscht? (`.ruff_cache/` deutet
   auf ruff hin.)
3. **Trigger-Branches:** reichen `main` + `feat/**` + `refactor/**`, oder alle?
4. **Matrix-Breite vs. Minuten:** volle 3×3-Matrix, oder z. B. nur 3.11 + 3.13
   auf macOS/Windows und volle Range auf Linux (Minuten sparen)?
5. **Optionaler LLM-Smoke** als separater, manuell triggerbarer Job
   (`workflow_dispatch`) mit Secret — nur bei Bedarf, nicht pro Push?

## 6. Empfehlung

Annehmen — macht „cross-platform" von einer Designaussage zu einer bei jedem
Push geprüften Eigenschaft und sichert insbesondere den `fs_confine`-Pfad auf
Windows ab. Start schlank (Matrix wie oben, ggf. Extras getrimmt, optional
Ruff-Job); LLM-E2E bewusst aus CI heraushalten. Aktivierung (`.github/workflows/
ci.yml` anlegen) nach Freigabe — danach läuft sie bei jedem Push/PR.
