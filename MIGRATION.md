# MIGRATION.md — Vergleichsrechenkern Pipeline: SDK → Full-Agentic Migration

> **Self-containment guarantee.** This document is the single deliverable for
> migrating the rechner-pipeline from an SDK-driven LLM pipeline to a
> full-agentic, CLI-driven design. A reader needs no access to the source
> repository; every contract, schema, prompt text, file format, and design
> decision is reproduced here. German prompt texts are verbatim; all other
> prose is English.

---

## Table of contents

- [§0 How to read this document](#0-how-to-read-this-document)
- [§1 Executive summary & migration goals](#1-executive-summary--migration-goals)
- [§2 AS-IS reference](#2-as-is-reference)
  - [§2.1 End-to-end data flow & file lifecycle](#21-end-to-end-data-flow--file-lifecycle)
  - [§2.2 Extraction subsystem](#22-extraction-subsystem-as-is)
  - [§2.3 Prompt, context assembly & generation contract](#23-prompt-context-assembly--generation-contract-as-is)
  - [§2.4 Quality assurance](#24-quality-assurance-as-is)
  - [§2.5 Orchestration, manifest & dossier](#25-orchestration-manifest--dossier-as-is)
  - [§2.6 Known AS-IS limitations](#26-known-as-is-limitations)
- [§3 TARGET design (full-agentic, CLI-agnostic)](#3-target-design-full-agentic-cli-agnostic)
  - [§3.1 Architecture overview](#31-architecture-overview)
  - [§3.2 Skill spec: build-vergleichsrechenkern](#32-skill-spec-build-vergleichsrechenkern)
  - [§3.3 Deterministic toolbox](#33-deterministic-toolbox)
  - [§3.4 Pluggable input-adapter seam](#34-pluggable-input-adapter-seam)
  - [§3.5 Quality & reproducibility module](#35-quality--reproducibility-module)
  - [§3.6 Per-CLI mapping table](#36-per-cli-mapping-table)
- [§4 Migration steps](#4-migration-steps)
  - [§4.1 Component disposition](#41-component-disposition)
  - [§4.2 Ordered migration checklist](#42-ordered-migration-checklist)
- [§5 Risk register, open questions, explicit non-goals](#5-risk-register-open-questions-explicit-non-goals)
  - [§5.1 Risk register](#51-risk-register)
  - [§5.2 Open questions / residual VERIFY items](#52-open-questions--residual-verify-items)
  - [§5.3 Explicit non-goals](#53-explicit-non-goals)
- [§6 Appendices](#6-appendices)
  - [§6.1 Verbatim prompt: excel_to_py.txt](#61-verbatim-prompt-excel_to_pytxt)
  - [§6.2 Verbatim prompt: test_advanced.txt](#62-verbatim-prompt-test_advancedtxt)
  - [§6.3 FILE-block grammar](#63-file-block-grammar)
  - [§6.4 Manifest & dossier JSON schemas](#64-manifest--dossier-json-schemas)
  - [§6.5 InputBundle schema](#65-inputbundle-schema)
  - [§6.6 Example info_from_excel/ output formats](#66-example-info_from_excel-output-formats)
  - [§6.7 Canonical TARGET instruction / SKILL body](#67-canonical-target-instruction--skill-body-install-neutral)
  - [§6.8 TARGET acceptance JSON schemas](#68-target-acceptance-json-schemas)

---

## 0 How to read this document

### Self-containment guarantee

Every file format, validation rule, prompt text, JSON schema, and design
decision referenced in the migration is reproduced in this document.
Cross-references point to sections within this file using `§N.N` notation.
No source-file reading is required.

### Glossary

| Term | Definition |
|---|---|
| **Vergleichsrechenkern** | "Comparison calculation kernel" — a pure-Python package that reproduces an Excel tariff calculator's results without Excel. |
| **Tarifrechner** | The source Excel workbook (`.xlsm`/`.xlsx`) containing actuarial formulas, VBA, and cached values for a specific insurance tariff. |
| **Sterbetafel / qx** | Mortality table. `qx` is the one-year probability of death at age `x`. Serialized to `tafeln.xml`. |
| **Kommutationswerte** | Commutation values — `D_x`, `N_x`, `C_x`, `M_x` (and optionally `S_x`, `R_x`) — precomputed discount-weighted life-table columns used in actuarial present-value formulas. |
| **Barwert** | Present value (PV). Actuarial PVs include life-insurance PVs (`A_x`), life-annuity PVs (`ä_x`), and net premiums (`P`). |
| **Golden master** | A deterministic comparison gate: generated Python recomputes values that must match the Excel workbook's cached scalar and table expectations, rounded to 4 decimals. |
| **info_from_excel/** | The extraction output directory. Contains raw/compressed CSVs, VBA text, scalar/table expectations, and the export manifest. |
| **generated/** | The code output directory. Contains exactly six generated files: `inputs.py`, `params.py`, `tafeln.xml`, `commutation.py`, `actuarial.py`, `test_run.py`. |
| **Skill** | A reusable, trigger-activated instruction set that a CLI agent loads to execute a multi-step workflow. |
| **MCP** | Model Context Protocol — a standard for tool servers. Only **local stdio** transport is permitted (no HTTP/SSE). |
| **Gate** | A deterministic, reviewed validation step (e.g. `G5.golden-master`). Gates are blocking: failure means non-acceptance. |

---

## 1 Executive summary & migration goals

### What changes

The current pipeline uses the Anthropic and OpenAI Python SDKs (via
`generate_completion()` in `generate/client.py`) plus LangGraph (in
`orchestrate/agentic.py`) to orchestrate model calls, retry loops, and
gate-driven repair. In the target design:

- **The CLI agent IS the model.** There is no Python-hosted SDK client,
  API-key management, or LangGraph state graph.
- **Deterministic Python becomes a toolbox.** Extraction, validation,
  static security, golden-master comparison, and new algebraic/property
  tests become CLI-callable scripts the agent invokes.
- **The current prompt rules become skill instructions.** The German
  prompt texts (§6.1, §6.2) are migrated into the portable, install-neutral
  canonical instruction body (§6.7) that any of the four supported CLIs can load.
- **Self-repair is agent-native.** The agent's own tool-use loop replaces
  LangGraph's prepare→generate→test→compare→repair graph, bounded by an
  explicit attempt convention in the skill instructions.

### What is preserved (I/O contract)

- **`info_from_excel/` artifacts are byte-identical** for Excel inputs.
  The extraction subsystem (§2.2) is wrapped, not rewritten.
- **The six generated files** (`inputs.py`, `params.py`, `tafeln.xml`,
  `commutation.py`, `actuarial.py`, `test_run.py`) and their order,
  naming, and layer contract are unchanged.
- **The `golden_master_outputs() -> dict` contract** in `test_run.py`
  is preserved.
- **The golden-master comparison** (4-decimal rounding, prefix-based
  scalar/table matching) is preserved.

### Non-goals

- Redesigning the six-file generated-code contract.
- Replacing the golden-master comparison algorithm.
- Supporting non-Excel inputs in the initial migration (the adapter seam
  is designed but Word/other adapters are future work).
- Mandating a specific CLI — the design is portable across Claude CLI,
  GitHub Copilot CLI, Codex CLI, and OpenCode CLI.
- Building an HTTP/SSE MCP server (explicitly prohibited).
- Installing software from unapproved sources.

---

## 2 AS-IS reference

### 2.1 End-to-end data flow & file lifecycle

#### Pipeline diagram (AS-IS)

```text
┌──────────────────────────────────────────────────────────────────────┐
│ INPUT                                                                │
│  Tarifrechner_KLV.xlsm  (Excel workbook with formulas + VBA)        │
└──────────────┬───────────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STAGE 1: EXTRACTION  (export_excel_infos)                            │
│  Backend: openpyxl (default) or COM                                  │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ Raw sheets → <sheet>.csv  (Blatt;Adresse;Formel;Wert)          │ │
│  │ VBA modules → vba/<module>.txt                                 │ │
│  │ Defined names → names_manager.csv                              │ │
│  │ Compression → <sheet>_compressed.csv                           │ │
│  │ Scalar/table expectations → *_scalar.json, *_table_values.csv  │ │
│  │ Manifest → export_manifest.json                                │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│  Output dir: info_from_excel/                                        │
└──────────────┬───────────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STAGE 2: PROMPT ASSEMBLY + SDK GENERATION  (run_main_llm)            │
│  Read manifest.llm_inputs → stuff into prompt template               │
│  apply_placeholders(excel_to_py.txt, {PIPELINE_META, INPUT_FILES})   │
│  generate_completion(prompt) → raw text with 6 FILE blocks           │
│  validate_main_output_files(text) → 6 (name, content) pairs          │
│  Static security scan → static_security_report.json                  │
│  Write to generated/                                                 │
└──────────────┬───────────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STAGE 3: QUALITY GATES  (run_compare)                                │
│  Execute golden_master.py under fs_confine                           │
│  Import generated/test_run → call golden_master_outputs()            │
│  Compare scalars vs *_scalar.json (round 4 decimals)                 │
│  Compare tables vs *_table_values.csv (round 4 decimals)             │
│  Write test_run_advanced_result.json                                  │
└──────────────┬───────────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STAGE 4: DOSSIER + OPTIONAL AGENTIC REPAIR                           │
│  Write run_dossier.json (provenance, hashes, gate results)           │
│  LangGraph: if gates fail → repair context → re-run Stage 2+3       │
│  Bounded retries → human_review_required on exhaustion               │
└──────────────────────────────────────────────────────────────────────┘
```

#### File inventory

| File | Producer | Consumer | Purpose |
|---|---|---|---|
| `info_from_excel/<sheet>.csv` | Extraction (§2.2) | Compression, scalar/table extraction | Raw sheet data: `Blatt;Adresse;Formel;Wert` |
| `info_from_excel/<sheet>_compressed.csv` | Compression (§2.2.6) | Main prompt (via `llm_inputs`) | Token-reduced formula blocks + value rows |
| `info_from_excel/names_manager.csv` | Extraction (§2.2.5) | Main prompt (via `llm_inputs`) | Defined names with evaluated values |
| `info_from_excel/vba/<module>.txt` | VBA extraction (§2.2.4) | Main prompt (via `llm_inputs`) | VBA source code |
| `info_from_excel/<prefix>_scalar.json` | Scalar extraction (§2.2.7) | Golden-master harness (§2.4) | Expected scalar values keyed by label |
| `info_from_excel/<prefix>_table_values.csv` | Table extraction (§2.2.7) | Golden-master harness (§2.4) | Expected table rows, comma-delimited |
| `info_from_excel/export_manifest.json` | Extraction (§2.2.8) | Runner, dossier, strict warnings | Manifest: paths, hashes, warnings, prompt records |
| `generated/inputs.py` | LLM / agent | `test_run.py`, downstream code | Contract input parameters |
| `generated/params.py` | LLM / agent | `commutation.py`, `actuarial.py` | Tariff parameters and constants |
| `generated/tafeln.xml` | LLM / agent | `commutation.py` | Serialized mortality tables (qx) |
| `generated/commutation.py` | LLM / agent | `actuarial.py` | Mortality access, commutation values, math utilities |
| `generated/actuarial.py` | LLM / agent | `test_run.py` | Present values, tariff logic, actuarial targets |
| `generated/test_run.py` | LLM / agent | Golden-master harness | Minimal example + `golden_master_outputs()` |
| `generated/static_security_report.json` | `qa.security` | Dossier, runner | Static scan results |
| `generated/test_run_advanced_result.json` | `run_compare()` | Dossier | Compare gate exit code, stdout, stderr |
| `generated/run_dossier.json` | Dossier writer (§2.5) | Audit, CI | Full provenance record |

---

### 2.2 Extraction subsystem (AS-IS)

This section reverse-documents the extraction subsystem implemented by `export_excel_infos()` in `src\rechner_pipeline\extract\excel.py`, the platform-neutral backend in `src\rechner_pipeline\extract\openpyxl_backend.py`, and the golden-master expectation extractor in `src\rechner_pipeline\extract\scalar_table.py`. It is intentionally repo-independent: a compatible implementation must reproduce the files and semantics described here, not the surrounding orchestration.

#### 2.2.1 Purpose and high-level contract

Extraction turns one Excel workbook into deterministic files under an output directory normally named `info_from_excel` (`GENERATED_SUBDIR_NAME = "info_from_excel"`). The extraction output is the only Excel-derived input used by the later LLM/golden-master stages.

The subsystem produces four classes of artifacts:

1. Raw workbook artifacts:
   - one semicolon-delimited sheet CSV per non-empty worksheet: `<safe-sheet-name>.csv`
   - optional `names_manager.csv`
   - optional `vba\<safe-module-name>.txt`
2. Token-reduced LLM prompt artifacts:
   - `<safe-sheet-name>_compressed.csv` for sheets containing formulas
3. Golden-master expectation artifacts:
   - `<prefix>_scalar.json`
   - `<prefix>_table_values.csv`
4. Optional manifest:
   - `export_manifest.json`

`safe_filename(name, max_len=180)` is used for sheet and VBA-module filenames. It replaces any run of `[<>:"/\\|?*\x00-\x1F]` with `_`, strips leading/trailing spaces and dots, falls back to `unnamed`, and truncates to 180 characters.

#### 2.2.2 Entry point: `export_excel_infos()`

Signature:

```python
def export_excel_infos(
    excel_path: Path,
    out_dir: Path,
    save_manifest_json: bool = True,
    backend: str = "openpyxl",
) -> Dict[str, Any]
```

Control flow, including the important backend-independent boundary:

```text
export_excel_infos(excel_path, out_dir, save_manifest_json=True, backend="openpyxl")
  if excel_path does not exist:
      raise FileNotFoundError
  mkdir out_dir parents=True exist_ok=True
  warnings = []

  if backend == "openpyxl":
      call openpyxl_backend.export_raw(excel_path, out_dir, warnings)
      -> (sheet_csvs, vba_txts, names_manager_csv)
  elif backend == "com":
      call _export_raw_com(excel_path, out_dir, warnings)
      -> (sheet_csvs, vba_txts, names_manager_csv)
  else:
      raise ValueError("Unknown export backend ... expected 'openpyxl' or 'com'")

  # From here onward the pipeline is backend-independent.
  replacements = compress_exported_csvs(sheet_csvs, out_dir, warnings)
  llm_sheet_csvs = [replacements[p] if present else p for p in sheet_csvs]
  llm_inputs = llm_sheet_csvs + optional names_manager_csv + vba_txts

  manifest = {
      out_dir, sheet_csvs, vba_txts, names_manager_csv,
      replacements, llm_inputs, all_outputs, warnings,
      prompt_runs=[], output_hashes=[]
  }

  scalar_warnings = extract_all_pairs_in_info_dir(out_dir)
  warnings.extend(scalar_warnings)
  append all *_scalar.json and *_table_values.csv in out_dir to manifest["all_outputs"]

  if save_manifest_json:
      write export_manifest.json as UTF-8 JSON, ensure_ascii=False, indent=2
      append export_manifest.json to the returned in-memory manifest["all_outputs"]

  return manifest
```

Backend choices:

- `backend="openpyxl"` is the default and is platform-neutral. It uses `openpyxl` for workbook cells and defined names, `oletools.olevba.VBA_Parser` for VBA, and `pandas` for later compression/scalar extraction.
- `backend="com"` is the legacy Windows path. It uses `pywin32`/Excel COM and therefore requires Windows plus installed Microsoft Excel.

Downstream prompt selection is deliberate: for each sheet, if `<sheet>_compressed.csv` exists, `manifest["llm_inputs"]` contains only the compressed file for that sheet, not the raw sheet CSV. The raw CSV remains in `manifest["all_outputs"]` and remains the value source for scalar/table extraction. Sheets without formulas do not get a compressed file, so their raw CSV is used in `llm_inputs`.

Dependency failures are raised, not converted to manifest warnings: `_import_pandas()`, `_import_openpyxl()`, `_import_vba_parser()`, and `_dispatch_excel_application()` raise `RuntimeError` with install guidance if their package is missing.

#### 2.2.3 Raw sheet CSV extraction

Every non-empty worksheet is exported as UTF-8 CSV with semicolon delimiter and exact header:

```csv
Blatt;Adresse;Formel;Wert
```

Rows are cell records. `Blatt` is the worksheet name, `Adresse` is an A1-style address, `Formel` is the formula/literal text, and `Wert` is the cached/current value text. Empty cells are skipped when both `Formel` and `Wert` are empty after stripping whitespace. If a sheet produces no data rows, its just-created CSV is deleted and omitted from `sheet_csvs`.

Value-to-text conversion is shared where `excel_value_to_text()` is used:

- `None` -> empty string
- `True` -> `TRUE`, `False` -> `FALSE`
- anything else -> `str(value)`

##### `openpyxl` sheet extraction

`openpyxl_backend.export_raw()` opens the workbook twice:

```python
wb_formula = openpyxl.load_workbook(excel_path, data_only=False, read_only=False)
wb_value   = openpyxl.load_workbook(excel_path, data_only=True,  read_only=False)
```

For each worksheet in `wb_formula.worksheets`, it finds the same sheet by title in `wb_value` and calls `export_one_sheet(ws_formula, ws_value, sheet_name, out_dir)`.

For each cell yielded by `ws_formula.iter_rows()`:

- `raw_formula = cell.value` from the formula workbook.
  - For formula cells this is the formula string, normally starting with `=`.
  - For literal cells this is the literal value.
  - `_cell_text()` unwraps `openpyxl.worksheet.formula.ArrayFormula` and `DataTableFormula` objects via their `.text` attribute.
  - `_cell_text()` renders integer floats as integers (`5.0` -> `"5"`) for formula/literal text.
- `raw_value = ws_value[cell.coordinate].value` from the data-only workbook.
  - This is the value cached in the workbook by Excel, not a fresh recalculation.
  - If the workbook was never calculated/saved by Excel, cached values for formulas may be missing.
- `Adresse` is always written in absolute form: `f"${cell.column_letter}${cell.row}"`, e.g. `$K$6`.

The openpyxl backend explicitly documents that `Wert` is the last saved cached Excel value, not live COM recalculation. This makes the default backend platform-neutral and reproducible, but dependent on the workbook having valid cached values.

##### COM sheet extraction

`_export_raw_com()` starts Excel with `win32com.client.DispatchEx("Excel.Application")`, sets:

```python
excel.Visible = False
excel.DisplayAlerts = False
excel.AskToUpdateLinks = False
```

It opens the workbook read-only:

```python
excel.Workbooks.Open(str(excel_path), ReadOnly=True, UpdateLinks=0, AddToMru=False)
```

For each `wb.Worksheets` item, `export_one_sheet(ws, out_dir)` computes `usedrange_bounds(ws)` from `ws.UsedRange`. If Excel reports only `A1` as used and that cell has no value and no meaningful formula (`""` or `"="`), the sheet is treated as empty. Otherwise it iterates all cells in the used range.

For each COM cell:

- `Formel` comes from `cell.Formula`.
- `Wert` comes from `cell.Value`.
- `Adresse` comes from `get_a1_address(cell)`, which first calls `cell.Address(False, False, _XL_A1)` and falls back to `cell.Address` on error.

Important address caveat: the openpyxl path always writes `$A$1`-style addresses, and `scalar_table.py` later performs `$A$1` lookups. The COM code asks Excel for a non-absolute A1 address but can fall back to Excel's default absolute address; existing COM fixtures show `$` addresses. A reimplementation should preserve `$A$1` compatibility for scalar/table extraction.

#### 2.2.4 VBA extraction

VBA files are written under `info_from_excel\vba\`. If no modules are exported, the code tries to remove the empty `vba` directory.

##### `openpyxl`/`oletools` VBA extraction

`openpyxl_backend.export_vba_modules_to_txt(excel_path, out_dir, warnings)` uses:

```python
from oletools.olevba import VBA_Parser
parser = VBA_Parser(str(excel_path))
```

If `parser.detect_vba_macros()` is false, no files are written. Otherwise it iterates:

```python
for _fname, _stream, vba_filename, code in parser.extract_macros():
```

Module naming and body normalization:

- `module_name = Path(str(vba_filename)).stem`
- output path is `vba\<safe_filename(module_name)>.txt`
- `_strip_vba_attribute_lines(code)` removes only lines whose text starts exactly with `Attribute VB_`:

```python
lines = [ln for ln in code.splitlines() if not ln.startswith("Attribute VB_")]
body = "\n".join(lines)
```

It does not remove indented attribute lines and does not remove non-`VB_` attribute lines. If the stripped body is blank, the module is skipped. Non-empty modules are written as UTF-8 text with LF newlines and one final newline (`body + "\n"`).

If any exception occurs in this parser block, extraction appends warning `export.vba_extraction_failed` and continues without VBA files.

##### COM VBA extraction

`excel.py.export_vba_modules_to_txt(wb, out_dir, warnings)` uses Excel's `wb.VBProject`. If `VBProject` cannot be accessed, it emits `export.vba_access_unavailable`, prints the Excel Trust Center setting that must be enabled, tries to remove `vba`, and returns no VBA files.

For each `vbproj.VBComponents` component:

- `comp_name = str(comp.Name)`
- code comes from `comp.CodeModule.Lines(1, CountOfLines)`
- output path is `vba\<safe_filename(comp_name)>.txt`
- blank modules are skipped

If a component's code cannot be read, the code emits `export.vba_module_read_failed`, writes a one-line error string as that module's code, and continues.

#### 2.2.5 Defined names: `names_manager.csv`

If any defined names are found, extraction writes `names_manager.csv` as UTF-8 semicolon CSV with exact header:

```csv
Name;Scope;Visible;RefersTo;RefersToLocal;RefersToRangeAddress;ValueEvaluated;Comment
```

If no rows are found, no `names_manager.csv` is generated.

##### `openpyxl` defined names

`openpyxl_backend.export_name_manager_to_csv(wb_formula, wb_value, out_dir)` reads defined names from `wb_formula.defined_names.values()`, with a defensive fallback to very old openpyxl's `definedName` list.

For each defined name `dn`, it writes:

| Column | openpyxl value |
|---|---|
| `Name` | `str(dn.name)` |
| `Scope` | `Workbook` if `dn.localSheetId is None`, otherwise `Worksheet:<localSheetId>` (numeric sheet id, not title) |
| `Visible` | `str(not bool(dn.hidden))` |
| `RefersTo` | `excel_value_to_text(dn.value)` |
| `RefersToLocal` | empty string |
| `RefersToRangeAddress` | empty string |
| `ValueEvaluated` | cached value only if the name has exactly one destination cell |
| `Comment` | empty string |

Single-cell name evaluation is implemented by `_evaluate_single_cell_name(defined_name, wb_value)`:

```text
destinations = list(defined_name.destinations)
if len(destinations) != 1: return ""
sheet_title, coord = destinations[0]
return _cell_text(wb_value[sheet_title][coord.replace("$", "")].value)
```

Therefore openpyxl evaluates only names that resolve to exactly one cell. Multi-cell ranges, constants, formulas that do not expose a single destination, or lookup failures get an empty `ValueEvaluated`.

##### COM defined names

`excel.py.export_name_manager_to_csv(wb, out_dir)` collects both workbook-level names (`wb.Names`) and worksheet-local names (`for ws in wb.Worksheets: ws.Names`). It appends rows from both sources; it does not de-duplicate.

For each COM `Name` object:

| Column | COM value |
|---|---|
| `Name` | `getattr(nm, "Name", "")` |
| `Scope` | `try_get_name_scope(nm)`: returns `Worksheet:<Parent.Name>` if `nm.Parent` has a `Name` attribute, otherwise `Workbook`; returns empty string on exception. In practice this can label workbook-parent names as `Worksheet:<workbook filename>` because a workbook also has `Name`. |
| `Visible` | `getattr(nm, "Visible", "")` |
| `RefersTo` | `getattr(nm, "RefersTo", "")` via `excel_value_to_text()` |
| `RefersToLocal` | `getattr(nm, "RefersToLocal", "")` via `excel_value_to_text()` |
| `RefersToRangeAddress` | `nm.RefersToRange.Address(False, False, _XL_A1, True)` if possible, else `rng.Address`, else empty string |
| `ValueEvaluated` | `wb.Application.Evaluate(nm.Name)` via `excel_value_to_text()`, else empty string |
| `Comment` | `getattr(nm, "Comment", "")` via `excel_value_to_text()` |

Unlike openpyxl, COM attempts to evaluate any name through Excel, including multi-cell ranges; array results become whatever `str(value)` produces through `excel_value_to_text()`.

#### 2.2.6 CSV compression for LLM inputs

Compression is implemented by `compress_exported_csvs()` and `compress_sheet_csv_with_labels()`. Its purpose is token reduction: repeated formula columns are represented as one block row per contiguous run of equivalent formulas, while literal/input cells are retained as value rows.

`compress_exported_csvs(sheet_csv_paths, out_dir, warnings)` behavior:

- ignores `names_manager.csv`
- ignores any path already ending `_compressed.csv`
- output name is `<raw-stem>_compressed.csv`
- if that output already exists, it is reused and recorded in `replacements` without recomputing
- if a sheet has no formulas, no compressed CSV is generated
- on exception, emits `export.compression_failed`; the raw CSV remains available

##### Input contract

`compress_sheet_csv_with_labels(in_path, out_path, sep=";")` reads the raw sheet CSV with pandas using `dtype=str` and `keep_default_na=False`. It requires exact columns:

```text
Blatt, Adresse, Formel, Wert
```

A formula row is any row whose `Formel` starts with `=`. All other rows are value rows.

##### Exact compressed output schema

Compressed files are semicolon-delimited CSVs written with `index=False` and exact columns in this order:

```csv
Section;Blatt;Adresse;Formel;Wert;Anzahl_Zellen;Normalisierte_Formel_R1C1;Label_Adresse;Label_Wert;Label_Formel;Label_Source;LLM_Hint
```

There are two `Section` values:

1. `values`
   - one row for every non-formula row from the raw sheet CSV
   - original `Blatt`, `Adresse`, `Formel`, `Wert` are preserved
   - all added columns are blank
2. `formulas_unique_block`
   - one row per contiguous vertical block of formulas with the same normalized pattern in the same sheet and same column
   - `Wert` is blank
   - `Anzahl_Zellen` is the number of formula cells in that block
   - `Formel` is the first formula in that block
   - `Adresse` is `A1` for a one-cell block or `A1:A2` for a vertical block; these block addresses are emitted without `$`

Pseudocode for formula blocks:

```text
cell_index = all raw rows indexed by (Blatt, row, col)
formula_rows = rows where Formel starts with "="
for each formula row:
    _row, _col = parsed Adresse
    Normalisierte_Formel_R1C1 = normalize_formula_to_pattern(Formel, Adresse)

for each group by (Blatt, _col, Normalisierte_Formel_R1C1), preserving group order:
    sort group by _row
    split whenever row is not previous_row + 1
    for each contiguous block:
        start_row = min(_row); end_row = max(_row); col = _col
        label = choose_label(cell_index, Blatt, start_row, col, block_size)
        write formulas_unique_block row
```

##### Label selection: `choose_label()`

Labels are inferred from adjacent non-formula cells. A label cell is meaningful only if `CellInfo.is_meaningful_label()` is true:

```python
bool(cell.value.strip()) and not cell.formula.startswith("=")
```

Selection rules:

- For a single-cell formula block (`block_size == 1`):
  1. use the cell immediately left of the formula cell if meaningful (`Label_Source = "left"`)
  2. otherwise use the cell immediately above if meaningful (`Label_Source = "above"`)
  3. otherwise leave label fields blank
- For a multi-cell formula block (`block_size > 1`):
  1. use only the cell immediately above the first formula cell if meaningful (`Label_Source = "above"`)
  2. otherwise leave label fields blank

Returned label fields are:

```text
Label_Adresse, Label_Wert, Label_Formel, Label_Source
```

`LLM_Hint` is always formatted exactly as:

```text
Label(<Label_Source>:<Label_Adresse>)=<Label_Wert> | Formula=<example_formula> | Pattern=<normalized_pattern>
```

If no label is found, the prefix becomes `Label(:)=`.

##### Formula normalization: `normalize_formula_to_pattern()`

Only strings starting with `=` are normalized. Non-formulas are returned as strings unchanged, except that a formula with an unparsable current address is stripped.

Address parsing/conversion:

- Current cell address is parsed as A1 after removing `$`.
- Formula references are matched by `_SHEET_A1_RE`:

```text
((?:'[^']+'|[A-Za-z0-9_]+)!)?(\$?[A-Z]{1,3}\$?\d+)
```

This handles optional quoted sheet prefixes like `'My Sheet'!` and unquoted sheet prefixes like `Sheet1!`, followed by one A1 cell reference. Ranges are normalized because both endpoints are matched separately.

Each matched A1 reference is converted to a custom R1C1-like form relative to the current formula cell:

- relative row: `R[ref_row - current_row]`
- absolute row (`$` before row): `R<ref_row>`
- relative column: `C[ref_col - current_col]`
- absolute column (`$` before column): `C<ref_col>`

Examples for a formula in `B16`:

| A1 reference | Pattern fragment |
|---|---|
| `A16` | `R[0]C[-1]` |
| `$A16` | `R[0]C1` |
| `A$16` | `R16C[-1]` |
| `$A$16` | `R16C1` |

After replacement, all whitespace is removed and the whole formula is uppercased. Named ranges and function names that are not A1 references are therefore uppercased but not otherwise resolved.

This is why a filled-down formula column can become one row: for example, formulas in `B16:B66` with row-relative references normalize to the same pattern and are emitted as one `formulas_unique_block` with `Anzahl_Zellen = 51`.

#### 2.2.7 Scalar and table extraction: golden-master expectation files

`scalar_table.py` derives deterministic expectation files from compressed formula metadata plus the raw cached values. These files are the golden-master inputs consumed later by the fixed QA harness:

- `*_scalar.json` is loaded as expected scalar values.
- `*_table_values.csv` is loaded as expected table/matrix values.

They are not added to `llm_inputs`; they are validation artifacts.

##### Pair discovery: `extract_all_pairs_in_info_dir()`

The extractor scans one `info_dir`:

```python
compressed = {p.stem.replace("_compressed", ""): p for p in info_dir.glob("*_compressed.csv")}
address_values = {p.stem.replace("_address_values", ""): p for p in info_dir.glob("*_address_values.csv")}
sheet_csv = {
    p.stem: p
    for p in info_dir.glob("*.csv")
    if not p.name.endswith("_compressed.csv") and not p.name.endswith("_address_values.csv")
}
```

For each compressed prefix in sorted order:

1. Prefer `<prefix>_address_values.csv` if present.
2. Else use `<prefix>.csv` if present.
3. Else emit `export.scalar_table_value_source_missing` and skip that prefix.
4. Call `extract_one_pair(addr_path, comp_path, info_dir, prefix)`.
5. If extraction raises, emit `export.scalar_table_extraction_failed` and continue.

`*_address_values.csv` is supported but not produced by the current extraction subsystem. If used, `load_address_values()` reads it with pandas' default comma delimiter and expects columns `Adresse` and `Wert`.

##### Value loading

For a normal raw sheet CSV, `load_sheet_values(path)` reads semicolon CSV with `dtype=str` and `keep_default_na=False`, requires `Adresse` and `Wert`, and returns:

```python
{Adresse: try_float(Wert) if Wert != "" else None}
```

`try_float(x)` returns `float(x)` when possible and otherwise returns the original value. The value-source address keys are not canonicalized on load; they are used exactly as written in the CSV. Because later lookups use `$A$1` form, compatible raw exports must provide `$A$1` addresses for scalar/table values.

##### Scalar JSON: `extract_one_pair_from_values()`

Scalars are extracted from compressed rows with:

```python
scal_df = cp[(cp["Label_Wert"].notna()) & (cp["Anzahl_Zellen"] == 1)]
```

Use pandas-compatible behavior here: blank label fields in generated compressed CSVs read back as `NaN` and are excluded by `.notna()`.

For each scalar row:

```text
label = stripped Label_Wert
addr = stripped Adresse
if addr parses as a single cell:
    addr = "$<COL>$<ROW>"
scalars[label] = fv.get(addr)
```

The JSON file is written as:

```python
out_dir / f"{prefix}_scalar.json"
json.dumps(scalars, ensure_ascii=False, indent=2)
```

It is therefore a JSON object mapping label text to cached value. Values may be numbers, strings, `null`, or whatever the value loader returned. If the same label appears more than once, the later row overwrites the earlier entry because assignment is `scalars[label] = ...`.

##### Table CSV: `extract_one_pair_from_values()`

Tables are extracted from compressed rows with:

```python
mat_df = cp[(cp["Label_Wert"].notna()) & (cp["Anzahl_Zellen"] > 1)]
```

For each row:

1. Parse `Adresse` as a range `COL1ROW1:COL2ROW2`, allowing optional `$`.
2. Skip rows that are not ranges.
3. Skip ranges where `COL1 != COL2`; only vertical one-column blocks become table columns.
4. Group remaining columns by `(row_start, row_end)`.

For each `(r1, r2)` group:

```text
sort columns left-to-right by Excel column number
for each column block:
    output column name = stripped Label_Wert
    output values = [fv.get("$<COL>$<row>") for row in r1..r2]
df = DataFrame(data)
maybe insert a left index column
append df to tables
```

`detect_left_index_column(fv, header_row, r1, r2, col_start_num)` is called with `header_row = r1 - 1` and `col_start_num = min(table_column_numbers)`. It looks one column left of the first table column:

- if there is no left column, return `None`
- header cell is `fv["$<left_col>$<header_row>"]`; it must be a string
- row values are `fv["$<left_col>$<r>"]` for `r1..r2`
- at least three of those row values must be numeric (`int` or `float`)
- numeric values must form an exact arithmetic progression using `nums[i] - nums[i-1] == step`

If detected, the left column is inserted as the first CSV column with the detected header text and the full value list.

The output file is always written to:

```python
out_dir / f"{prefix}_table_values.csv"
```

If at least one table DataFrame exists, `pd.concat(tables, ignore_index=True).to_csv(index=False)` is used. Multiple row-range groups are stacked vertically into one CSV; there is no separate table identifier column. If no tables exist, `pd.DataFrame().to_csv(index=False)` writes an empty no-column CSV (pandas emits just a newline).

#### 2.2.8 Manifest fields produced by extraction

`export_excel_infos()` returns a plain dict compatible with `models.manifest.ExportManifest`. Extraction initializes these fields:

| Field | Meaning |
|---|---|
| `out_dir` | output directory path as string |
| `sheet_csvs` | raw per-sheet CSV paths |
| `vba_txts` | exported VBA text paths |
| `names_manager_csv` | `names_manager.csv` path or empty string |
| `replacements` | dict mapping raw sheet CSV path string to compressed CSV path string |
| `llm_inputs` | compressed sheet CSVs where available, otherwise raw sheet CSVs; then `names_manager.csv`; then VBA text files |
| `all_outputs` | every written output path collected into a set, then `sorted(..., key=str)` — so raw and compressed per-sheet CSVs, VBA files, `names_manager.csv`, and scalar/table files are emitted in **lexicographic** order (raw/compressed interleave per sheet), not in functional groups; `export_manifest.json` is appended to the returned in-memory manifest after writing |
| `warnings` | extraction warnings; all warning objects have `code`, `stage`, `message`, `strict_error`, optional `path`, optional `details` |
| `prompt_runs` | empty list at extraction time |
| `output_hashes` | empty list at extraction time; the orchestrator may fill it later |

Subtle AS-IS behavior: when `save_manifest_json=True`, `export_manifest.json` is serialized before its own path is appended to the returned `manifest["all_outputs"]`. A later orchestrator rewrite can include the manifest path, but a direct call's first JSON write does not list itself.

The code does not clear `out_dir` before extraction. Existing `_compressed.csv`, `_scalar.json`, or `_table_values.csv` files can therefore be reused or globbed if left in place.

#### 2.2.9 Extraction warning codes

All warnings emitted by these extraction files use `stage = "export"` and `strict_error = True`.

| Code | Emitter | Trigger | Path/details |
|---|---|---|---|
| `export.vba_access_unavailable` | COM `export_vba_modules_to_txt()` | `wb.VBProject` cannot be accessed, usually because Excel Trust Center does not allow access to the VBA project object model | no path; `details.exception` |
| `export.vba_module_read_failed` | COM `export_vba_modules_to_txt()` | A specific `VBComponent.CodeModule` or its lines cannot be read | `path = vba\<module>.txt`; `details.module`, `details.exception` |
| `export.vba_extraction_failed` | openpyxl backend `export_vba_modules_to_txt()` | `oletools.olevba.VBA_Parser` construction, detection, extraction, or related parser work raises | no path; `details.exception` |
| `export.compression_failed` | `compress_exported_csvs()` | `compress_sheet_csv_with_labels()` raises for a sheet CSV | `path = <raw sheet csv>`; `details.exception`; raw CSV remains available |
| `export.scalar_table_value_source_missing` | `extract_all_pairs_in_info_dir()` | A `<prefix>_compressed.csv` exists but neither `<prefix>_address_values.csv` nor `<prefix>.csv` exists | `path = <compressed csv>`; `details.prefix` |
| `export.scalar_table_extraction_failed` | `extract_all_pairs_in_info_dir()` | `extract_one_pair()` raises for a prefix | `path = <compressed csv>`; `details.prefix`, `details.exception` |

`models.manifest.ManifestWarning` preserves these fields, and `ExportManifest.strict_error_warnings()` simply filters `warnings` for `strict_error`. Enforcement is optional in the runner; the warning objects themselves are produced regardless.

#### 2.2.10 Output inventory and naming conventions

Given `out_dir = info_from_excel`, the AS-IS extraction subsystem can write:

```text
info_from_excel\
  <safe-sheet>.csv                    # raw sheet CSV; semicolon; Blatt/Adresse/Formel/Wert
  <safe-sheet>_compressed.csv         # compressed LLM sheet CSV, only if the raw sheet has formulas
  <safe-sheet>_scalar.json            # scalar golden-master expectations, only for compressed prefixes
  <safe-sheet>_table_values.csv       # table golden-master expectations, only for compressed prefixes
  names_manager.csv                   # defined names, only if at least one name exists
  vba\
    <safe-module>.txt                 # non-empty VBA modules
  export_manifest.json                # optional manifest when save_manifest_json=True
```

Compatibility-only input recognized by scalar/table extraction but not produced by current raw extraction:

```text
info_from_excel\<prefix>_address_values.csv
```

Prefix derivation is string-based: `<prefix>_compressed.csv` is discovered by taking `Path.stem` and applying `.replace("_compressed", "")`; `<prefix>_address_values.csv` analogously uses `.replace("_address_values", "")`.

#### 2.2.11 Appendix: observed output shapes from the synthetic KLV workbook

The repository contains raw COM fixtures for the synthetic `Tarifrechner_KLV.xlsm` example (`Kalkulation.csv`, `Tafeln.csv`, `names_manager.csv`, `vba\*.txt`). The compressed/scalar/table examples below were regenerated from those raw fixtures with the current pure-Python `compress_exported_csvs()` and `extract_all_pairs_in_info_dir()` code.

##### Raw sheet CSV (`Kalkulation.csv`)

```csv
Blatt;Adresse;Formel;Wert
Kalkulation;$A$1;Tarifrechner KLV;Tarifrechner KLV
Kalkulation;$J$5;Bxt;Bxt
Kalkulation;$K$6;=VS*K5;4465.6547
Kalkulation;$D$12;ratzu;ratzu
Kalkulation;$E$12;=IF(zw=2,2%,IF(zw=4,3%,IF(zw=12,5%,0)));0.05
```

##### Defined names (`names_manager.csv`)

```csv
Name;Scope;Visible;RefersTo;RefersToLocal;RefersToRangeAddress;ValueEvaluated;Comment
alpha;Worksheet:Tarifrechner_KLV.xlsm;True;=Kalkulation!$E$6;=Kalkulation!$E$6;$E$6;0.025;
BJB;Worksheet:Tarifrechner_KLV.xlsm;True;=Kalkulation!$K$6;=Kalkulation!$K$6;$K$6;4465.6547;
```

##### VBA module text (`vba\mConstants.txt`)

```vb
Public Const rund_lx As Integer = 16
Public Const rund_tx As Integer = 16
Public Const rund_Dx As Integer = 16
Public Const rund_Cx As Integer = 16
Public Const rund_Nx As Integer = 16
Public Const rund_Mx As Integer = 16
Public Const rund_Rx As Integer = 16
Public Const max_Alter As Integer = 123
```

##### Compressed sheet CSV (`Kalkulation_compressed.csv`)

```csv
Section;Blatt;Adresse;Formel;Wert;Anzahl_Zellen;Normalisierte_Formel_R1C1;Label_Adresse;Label_Wert;Label_Formel;Label_Source;LLM_Hint
values;Kalkulation;$J$6;BJB;BJB;;;;;;;
formulas_unique_block;Kalkulation;K6;=VS*K5;;1;=VS*R[-1]C[0];$J$6;BJB;BJB;left;Label(left:$J$6)=BJB | Formula==VS*K5 | Pattern==VS*R[-1]C[0]
formulas_unique_block;Kalkulation;B16:B66;=IF(A16<=n,act_nGrAx(x+$A16,MAX(0,n-$A16),Sex,Tafel,Zins)+Act_Dx(x+n,Sex,Tafel,Zins)/Act_Dx(x+$A16,Sex,Tafel,Zins),0);;51;=IF(R[0]C[-1]<=N,ACT_NGRAX(X+R[0]C1,MAX(0,N-R[0]C1),SEX,TAFEL,ZINS)+ACT_DX(X+N,SEX,TAFEL,ZINS)/ACT_DX(X+R[0]C1,SEX,TAFEL,ZINS),0);$B$15;Axn;Axn;above;Label(above:$B$15)=Axn | Formula==IF(A16<=n,act_nGrAx(x+$A16,MAX(0,n-$A16),Sex,Tafel,Zins)+Act_Dx(x+n,Sex,Tafel,Zins)/Act_Dx(x+$A16,Sex,Tafel,Zins),0) | Pattern==IF(R[0]C[-1]<=N,ACT_NGRAX(X+R[0]C1,MAX(0,N-R[0]C1),SEX,TAFEL,ZINS)+ACT_DX(X+N,SEX,TAFEL,ZINS)/ACT_DX(X+R[0]C1,SEX,TAFEL,ZINS),0)
```

##### Scalar golden master (`Kalkulation_scalar.json`)

```json
{
  "Bxt": 0.044656547026924,
  "BJB": 4465.6547,
  "BZB": 392.8448,
  "Pxt": 0.042392046400377824,
  "ratzu": 0.05
}
```

##### Table golden master (`Kalkulation_table_values.csv`)

```csv
k,Axn,axn,axt,kVx_bpfl,kDRx_bpfl,kVx_bfr,kVx_MRV,flex. Phase,StoAb,RKW,VS_bfr
0.0,0.6508353435792427,20.30143073760709,15.879479153587287,-0.022328273513462005,-2232.8274,0.7015889204232604,0.0,0.0,150.0,0.0,0.0
1.0,0.6608343830624348,19.720058013370043,15.202199054900165,0.016737691921828737,1673.7692,0.7101345280958599,3478.5757,0.0,150.0,3328.5757,4898.4743
```

---

### 2.3 Prompt, context assembly & generation contract (AS-IS)

This subsystem is the old LLM boundary. It builds one giant prompt, calls an SDK client, receives one text response, and validates that the text contains the required `===FILE_START...===` file blocks. In the full-agentic migration this boundary changes: the CLI agent becomes the model, the German prompt content becomes skill instructions, the agent reads input files directly, and deterministic validation remains as scripts/checks.

#### 2.3.1 Source-of-truth identifiers

- Prompt versioning: `prompts\README.md` documents the convention `prompts\v<N>\`; each new version gets its own directory, prompts are not overwritten in place, and active version selection is owned by `PipelineRunner`. Current version is `v1` (first public release, 28.04.2026).
- Main prompt: `prompts\v1\excel_to_py.txt`.
- Legacy regression-test prompt: `prompts\v1\test_advanced.txt`.
- Prompt/context builder: `apply_placeholders`, `format_file_block`, `build_stuffed_inputs_with_metadata`, `StuffedInputs`, `StuffedInputFile` in `src\rechner_pipeline\context\prompt_builder.py`.
- Main output contract: `EXPECTED_MAIN_OUTPUT_FILES`, `PATTERN`, `extract_files_from_text`, `validate_main_output_files` in `src\rechner_pipeline\generate\output.py`.
- Legacy advanced-test extraction: `_TEST_BLOCK_RE` and `extract_test_run_advanced` in `src\rechner_pipeline\orchestrate\runner.py`.
- SDK seam to remove: `build_llm_client`, `build_openai_client`, `build_anthropic_client`, `_ReplayClient`, `resolve_api_key`, and `generate_completion` in `src\rechner_pipeline\generate\client.py`.

#### 2.3.2 Prompt templates and intent

##### Main prompt: `excel_to_py.txt`

The main prompt casts the model as a senior actuarial developer and Python engineer. Its intent is a deterministic 1:1 migration of an Excel tariff calculator, including formulas and VBA, into a pure Python package without Excel or external services.

Hard rules encoded in the prompt:

1. **No guessed Excel cell addresses.** The generated design must expose a clean parameterized API for contract inputs, tariff parameters, and mortality tables.
2. **Exactly six output files, in exactly this order:**
   1. `inputs.py`
   2. `params.py`
   3. `tafeln.xml`
   4. `commutation.py`
   5. `actuarial.py`
   6. `test_run.py`
3. **No outer text.** Each file must be wrapped in the file-block format and there must be no text outside the six blocks.
4. **Architecture/import constraints:**
   - `commutation.py` must not import `actuarial.py`.
   - `actuarial.py` may import `commutation.py`.
   - The only allowed direction is `actuarial.py → commutation.py`.
   - `commutation.py` owns mortality-table access, commutation values, technical/mathematical utilities, and no tariff/product logic.
   - `actuarial.py` owns present values, tariff/product logic, and actuarial target values.
   - Shared utilities such as `excel_round` must live in a lower layer (`commutation.py` or `params.py`), not in `actuarial.py` for import by `commutation.py`.
   - Circular imports, imports inside functions, `try/except ImportError`, and `TYPE_CHECKING` tricks are explicitly prohibited.
5. **`lru_cache` constraints:** `lru_cache` is allowed only when all arguments are strictly hashable; dict/list/set arguments and dataclasses containing such fields are forbidden. The prompt allows string IDs or explicit identity hashing (`eq=False`, `__hash__`) as alternatives.
6. **Input sources are read-only:** CSV sheet exports with `Blatt`, `Adresse`, `Formel`, `Wert`; `*_compressed.csv` when present; `names_manager.csv` when present; and VBA module `.txt` files. If a `*_compressed.csv` exists, the prompt says to use only that compressed export for the corresponding content. Compressed sections named in the prompt are `Section=values` and `Section=formulas_unique_block`.
7. **Formula implementation:** each present-value, commutation, and actuarial formula should become its own deterministic side-effect-free function, with names close to labels/identifiers in the inputs.
8. **Mortality tables:** serialize `qx` into `tafeln.xml`; if no tables are recognizable, emit clear placeholders and explicit `NotImplementedError` with a message.
9. **`test_run.py`:** provide a minimal dummy example, execute main paths, show deterministic behavior, and fail cleanly if tables are missing.

The prompt also defines the mandatory `golden_master_outputs() -> dict` contract in `test_run.py`:

```python
def golden_master_outputs() -> dict:
    """Berechnete Werte für den Golden-Master-Vergleich.
    Namen IDENTISCH zu den Erwartungsdateien (siehe INPUT_FILES:
    *_scalar.json-Schlüssel und *_table_values.csv-Spaltenköpfe)."""
    return {
        "scalars": {"<prefix>": {"<name>": <float>, ...}},
        "tables":  {"<prefix>": [ {"<spalte>": <float>, ...}, ... ]},
    }
```

Contract details from the prompt:

- `<prefix>` is the filename prefix of expectation files, e.g. `Kalkulation`.
- `scalars` contains one dict per `<prefix>_scalar.json`, mapping scalar names to calculated values.
- Completeness is critical: `scalars[<prefix>]` must contain every individually named scalar, meaning every label with `Anzahl_Zellen = 1` in the compressed CSV or every scalar name in the name manager. Derived rates/parameters such as `ratzu` are included; it is not enough to return only actuarial target values.
- `tables` contains one row-dict list per `<prefix>_table_values.csv`, in row order.
- Table keys are the CSV column headers and are case-sensitive. Separator variants such as `A_xn`/`Axn` may be supported, but case must not be normalized.
- Values must come from the same calculation used by the rest of `test_run.py`.

##### Legacy regression-test prompt: `test_advanced.txt`

The second prompt asks for `generated\test_run_advanced.py`. It is legacy because the current fixed harness supersedes an LLM-generated advanced test, but the AS-IS code still contains the prompt and extraction path.

Intent and constraints:

- Run the same calculation as `test_run.py`.
- Test all available results, not only samples.
- Compare generated calculation results against all `*_table_values.csv` and `*_scalar.json` expectation files.
- Assume fixed directories: `generated\` for Python files and `info_from_excel\` for CSV/JSON expectations.
- Scalars: compare every numeric expected value using `round(value, 4)` and report calculated/expected/PASS-FAIL.
- Tables: compare complete result matrices represented as lists of dictionaries.
- Field/column names are case-sensitive; names differing only by case are semantically different. Separator/spelling variants may be considered only without flattening case or mixing semantically different quantities.
- Deviations must be identifiable by index and field name.
- Report tested scalars, full matrix comparisons, and a summary of tests, deviations, and unmapped fields.
- Output exactly one `test_run_advanced.py` file block and no additional explanation.

Both prompt files are reproduced verbatim in appendices 2.3-A and 2.3-B.

#### 2.3.3 Placeholder mechanics

`apply_placeholders(prompt_template: str, placeholders: Dict[str, str]) -> str` performs simple textual replacement:

```python
out = prompt_template
for key, value in placeholders.items():
    out = out.replace("{{" + key + "}}", value)
return out
```

There is no escaping, no required-placeholder validation, no leftover-placeholder validation, and no schema validation. Surrounding template text remains unchanged; for example, the main prompt places the placeholder token inside literal backticks, and replacement only swaps the `{{PIPELINE_META}}` / `{{INPUT_FILES}}` token itself.

Per `prompts\README.md`, both v1 prompts expect `{{PIPELINE_META}}` and `{{INPUT_FILES}}`. `PipelineRunner` supplies them as follows.

##### `main_llm` metadata

`run_main_llm` reads `excel_to_py.txt`, builds stuffed inputs from `manifest.llm_inputs` relative to `self.out_dir`, and passes this object to `json.dumps(..., ensure_ascii=False, indent=2)` as `PIPELINE_META`:

```python
{
    "out_dir": str(self.out_dir),
    "llm_inputs_count": len(manifest.llm_inputs),
    "replacements": manifest.replacements,
}
```

`INPUT_FILES` is `stuffed_inputs.text` with `max_chars_per_file=self.options.main_max_chars_per_file` and `max_total_chars=self.options.main_max_total_chars`.

##### `test_llm` metadata

`run_test_llm` reads `test_advanced.txt`, builds test inputs, and passes this object to `json.dumps(..., ensure_ascii=False, indent=2)` as `PIPELINE_META`:

```python
{
    "info_from_excel_dir": str(self.out_dir),
    "generated_dir": str(self.generated_dir),
    "table_values_count": len(table_values),
    "scalar_json_count": len(scalar_json),
}
```

`table_values` are sorted `*_table_values.csv` files under `info_from_excel`; `scalar_json` are sorted `*_scalar.json` files. Core Python inputs are existing `generated\actuarial.py`, `generated\commutation.py`, `generated\inputs.py`, `generated\params.py`, and `generated\test_run.py`. `INPUT_FILES` is `stuffed_inputs.text` with the test prompt caps.

#### 2.3.4 Context assembly: giant prompt stuffing

`build_stuffed_inputs_with_metadata(base_dir, files, max_chars_per_file, max_total_chars)` creates the AS-IS giant prompt input string. This mechanism is replaced in the full-agentic design: the CLI agent should read files directly instead of receiving a pre-stuffed mega-prompt.

The per-file block format is defined by `format_file_block(label, content)` and includes two leading newlines:

```text


=====BEGIN_INPUT_FILE: {label}=====
{content}
=====END_INPUT_FILE: {label}=====
```

The exact implementation is:

```python
return (
    f"\n\n=====BEGIN_INPUT_FILE: {label}=====\n"
    f"{content}\n"
    f"=====END_INPUT_FILE: {label}=====\n"
)
```

Assembly behavior:

- Files are sorted by `_relkey(base_dir, path)`. `_relkey` returns `str(path.relative_to(base_dir))`, falling back to `path.name` on exception.
- Files are read as UTF-8 text with `errors="replace"` via `read_text`.
- Character counts are Python string lengths, not byte counts.
- If `len(original_text) > max_chars_per_file`, only the first `max_chars_per_file` characters are included and the marker `\n\n[TRUNCATED]\n` is appended. `truncated=True`.
- `original_sha256` is computed over the full original text as `sha256(original_text.encode("utf-8")).hexdigest()`.
- `included_chars` is `len(text)` after any `[TRUNCATED]` marker has been appended.
- Before appending a file block, the builder checks `total + len(block) > max_total_chars`. If true, it appends a synthetic `PIPELINE_NOTICE` input block, sets `total_limit_reached=True`, and stops. The notice content is exactly:

```text
Stopped adding more input files due to max_total_chars limit.
If needed, increase limits or reduce exports.
```

Records returned by the dataclasses:

- `StuffedInputFile`: `path`, `label`, `original_chars`, `included_chars`, `original_sha256`, `truncated`.
- `StuffedInputs`: `text`, `files`, `total_limit_reached`, plus property `truncated` equal to `total_limit_reached or any(item.truncated for item in files)`.

Truncation warnings are created by `PipelineRunner._prompt_warnings(stage, stuffed_inputs)`, not by `prompt_builder.py` itself:

- Per-file truncation produces `ManifestWarning(code="prompt.file_truncated", stage=<stage>, strict_error=True, path=<item.path>)` with message `Prompt input '<label>' was truncated by max_chars_per_file.` and details `label`, `original_chars`, `included_chars`.
- Total-limit truncation produces `ManifestWarning(code="prompt.total_limit_reached", stage=<stage>, strict_error=True)` with message `Prompt input assembly stopped because max_total_chars would have been exceeded.`
- `_prompt_record` stores prompt metadata as `PromptRecord`: `stage`, `template_path`, `debug_prompt_path`, `prompt_chars`, `prompt_sha256`, `input_files`, `total_limit_reached`, and optionally `output_chars`/`output_sha256` after the model response.

#### 2.3.5 Main output contract and validations

The AS-IS text contract for the main generation step is: `generate_completion(...)` returns a single string containing exactly six file blocks, with no text before, between, or after blocks except whitespace.

Expected files are hard-coded in `EXPECTED_MAIN_OUTPUT_FILES`:

```python
(
    "inputs.py",
    "params.py",
    "tafeln.xml",
    "commutation.py",
    "actuarial.py",
    "test_run.py",
)
```

`extract_files_from_text(text)` uses `PATTERN.finditer(text)` and returns a list of `(name, content)` tuples, where `name` is `match.group("name").strip()` and `content` is the raw captured content.

`validate_main_output_files(text)` performs all main-output checks in this order:

1. `_validate_no_outer_text(text)` walks all regex matches and rejects any non-whitespace outside recognized file blocks. The error begins `Unexpected text outside FILE_START/FILE_END blocks:` and includes the first offending snippet with newlines escaped and truncated to 120 characters.
2. `extract_files_from_text(text)` extracts blocks. If none are found, `_validate_main_output_names` raises `No files extracted from LLM output (missing FILE_START/FILE_END blocks).`
3. Path components are rejected. A name is invalid when `Path(name).name != name` or it contains `/` or `\`. The error begins `Unexpected file names with path components:`.
4. Duplicate file names are rejected with `Duplicate file blocks in LLM output:`.
5. Missing and unexpected files are rejected against `EXPECTED_MAIN_OUTPUT_FILES` / `EXPECTED_MAIN_OUTPUT_FILE_SET`; the error begins `Invalid LLM main output:` and lists `missing files:` and/or `unexpected files:`.
6. Exact order is enforced. `names` must equal `list(EXPECTED_MAIN_OUTPUT_FILES)`; otherwise the error begins `Invalid LLM main output order:`.
7. Python files are compiled with `compile(content, filename, "exec")`. The Python file set is every expected output ending in `.py`: `inputs.py`, `params.py`, `commutation.py`, `actuarial.py`, `test_run.py`. `tafeln.xml` is not compiled. Syntax errors are collected as `filename:lineno:offset: message` and raised under `Python files in LLM main output do not compile:`.

After validation, `write_main_output_items_to_generated_dir(items, script_dir)` writes each file to `script_dir / "generated" / filename` using UTF-8 and `newline="\n"`.

##### Legacy advanced-test block extraction

The second prompt path does not use `PATTERN`. `PipelineRunner` contains `_TEST_BLOCK_RE`, which extracts only `test_run_advanced.py`:

```python
_TEST_BLOCK_RE = re.compile(
    r"===FILE_START:\s*test_run_advanced\.py===\s*(.*?)\s*===FILE_END:\s*test_run_advanced\.py===",
    re.DOTALL,
)
```

`extract_test_run_advanced(llm_output)` returns `match.group(1).strip() + "\n"` or `None`. `run_test_llm` raises `RuntimeError("Could not find test_run_advanced.py block in LLM output.")` when extraction fails, then runs the static-security item check and writes `generated\test_run_advanced.py`. This legacy regex is less strict than the main validator: it is not anchored, allows surrounding text, and does not enforce the six-file set because it only targets one fixed file block.

#### 2.3.6 SDK seam to remove in full-agentic design

`src\rechner_pipeline\generate\client.py` is the SDK seam. Its only useful contract to the rest of the AS-IS pipeline is textual: `generate_completion(...) -> str` must return a string containing the expected file blocks. In the full-agentic design, this module's model/client responsibilities disappear. The CLI agent is the model, skill instructions replace the prompt template, and file generation/validation happen through the agent plus deterministic scripts.

##### Secret and client construction

- `load_env_file(env_path)` reads a `.env`-style file if present, skips blank/comment lines, accepts an `export ` prefix, splits on the first `=`, strips matching single/double quotes, and sets keys only when they are not already in `os.environ`.
- `resolve_api_key(key_name, env_path)` calls `load_env_file(env_path)` when provided, then checks `os.getenv(key_name)`, then `os.getenv(f"{key_name}_FILE")`. The file-pointer path is expanded with `Path(file_pointer).expanduser()`, must exist, and must contain a non-empty stripped secret. Errors are `RuntimeError`s that name the missing key or bad file pointer. Because `.env` is loaded before lookup, both direct keys and `*_FILE` pointers can come from `.env`; existing environment variables still win because `load_env_file` does not overwrite them.
- `build_openai_client(env_path)` resolves `OPENAI_API_KEY`, imports `OpenAI` from `openai`, and returns `OpenAI(api_key=api_key)`. Missing dependency error text is `Missing LLM dependency. Run: pip install -e '.[llm]'`.
- `build_anthropic_client(env_path)` resolves `ANTHROPIC_API_KEY`, imports `Anthropic` from `anthropic`, and returns `Anthropic(api_key=api_key)`. Missing dependency error text is `Missing LLM dependency. Run: pip install -e '.[anthropic]'`.
- `build_llm_client(provider, env_path)` dispatches `provider == "openai"`, `"anthropic"`, or `"replay"`; replay uses `Path(os.environ.get("RP_REPLAY_DIR", "demo_fixtures"))`. Unknown providers raise `ValueError` naming the expected provider set.

##### Replay provider

`_ReplayClient` is a deterministic fake client for tests/demos:

- It stores a resolved directory string and sorted `*.txt` files.
- If the directory contains no `*.txt` outputs, it raises `RuntimeError(f"RP_REPLAY_DIR enthält keine *.txt-Ausgaben: {directory}")`.
- `next_output()` uses module-global `_REPLAY_INDEX: dict[str, int]` keyed by directory so the call index survives runner/client re-creation during agentic iterations.
- Each call returns the next `.txt` file as UTF-8 text; after the final file, it repeats the final file.

##### OpenAI provider path

For `provider == "openai"`, `generate_completion` calls:

```python
resp = client.responses.create(
    model=model,
    input=prompt,
    reasoning={"effort": reasoning_effort},
)
return resp.output_text
```

`max_output_tokens` is not passed on this path in the AS-IS code.

##### Anthropic provider path

For `provider == "anthropic"`, `generate_completion` maps `reasoning_effort` through `_ANTHROPIC_THINKING_BUDGET`:

```python
{"low": 0, "medium": 4096, "high": 12288}
```

Unknown effort strings fall back to `0` because the code uses `.get(reasoning_effort, 0)`.

The Anthropic request uses Messages streaming:

- Base kwargs: `model`, `max_tokens=max_output_tokens`, and one user message containing the whole prompt.
- If the thinking budget is greater than zero, it adds `thinking={"type": "enabled", "budget_tokens": thinking_budget}`.
- Because Anthropic requires `max_tokens > budget_tokens`, if `max_tokens <= thinking_budget`, the code sets `max_tokens` to `thinking_budget + max_output_tokens`.
- It calls `client.messages.stream(**kwargs)` and then `stream.get_final_message()`.
- If `resp.stop_reason == "max_tokens"`, it raises a truncation guard `RuntimeError` explaining that the FILE_START/FILE_END contract is incomplete and `--max_output_tokens` should be increased.
- `_anthropic_response_text(resp)` concatenates only content blocks where `block.type == "text"`; thinking blocks are skipped so the parser sees only the file-block output.

#### 2.3.7 Migration implications and caveats

- Preserve the deterministic validators and file-set/order contract even when removing the SDK call. In a full-agentic CLI design, these rules should be skill instructions plus post-generation validation, not a giant prompt sent to an SDK.
- Replace prompt stuffing with direct file reading by the agent. The AS-IS `[TRUNCATED]` marker and `PIPELINE_NOTICE` are artifacts of context-window management, not business rules.
- Keep the `golden_master_outputs()` contract as a generated-code requirement unless the fixed validation harness is redesigned at the same time.
- Do not silently degrade on missing inputs or incomplete generation; the AS-IS code is intentionally fail-fast through `OutputValidationError`, `RuntimeError`, compile checks, and strict prompt warnings.
- Ambiguity/caveat: `apply_placeholders` does not fail on unresolved placeholders.
- Ambiguity/caveat: the OpenAI path does not pass `max_output_tokens`; only the Anthropic path enforces truncation via `stop_reason == "max_tokens"`.
- Ambiguity/caveat: `_TEST_BLOCK_RE` for `test_run_advanced.py` is weaker than the main `PATTERN` validation.
- Ambiguity/caveat: `read_and_cap_file` duplicates the per-file cap behavior but `build_stuffed_inputs_with_metadata` implements the cap inline.

#### Appendix 2.3-A — `prompts\v1\excel_to_py.txt`

The full verbatim text of the main generation prompt is reproduced once in
[§6.1](#61-verbatim-prompt-excel_to_pytxt) to keep a single source of truth. Its role,
non-negotiable output/architecture rules, input sources, and work order are summarized in
§2.3.2–§2.3.5 above. (AS-IS prompt text; superseded in the TARGET design — see §6.7.)

#### Appendix 2.3-B — `prompts\v1\test_advanced.txt`

The full verbatim text of the legacy regression-test prompt is reproduced once in
[§6.2](#62-verbatim-prompt-test_advancedtxt). It governs the optional `test_run_advanced.py`
comparison step summarized in §2.3.2. (AS-IS prompt text; not part of the TARGET acceptance loop.)

#### Appendix 2.3-C — FILE-block grammar (legacy test block)

The canonical FILE-block grammar (`PATTERN` and the canonical block shape) is reproduced once in
[§6.3](#63-file-block-grammar). The only §2.3-specific addition is the **weaker** legacy extractor
for `test_run_advanced.py` in `src\rechner_pipeline\orchestrate\runner.py` (`DOTALL`-only,
unanchored — see the caveat in §2.3.7):

````python
_TEST_BLOCK_RE = re.compile(
    r"===FILE_START:\s*test_run_advanced\.py===\s*(.*?)\s*===FILE_END:\s*test_run_advanced\.py===",
    re.DOTALL,
)
````

---

### 2.4 Quality assurance (AS-IS)

This subsystem is a deterministic QA shell around generated Python calculation code. In the as-is design the model is called through SDK code, but generated code is not trusted: it is statically scanned before it can be written/executed, then executed under runtime filesystem confinement, then compared against Excel-derived golden-master artifacts.

#### Static security gate: `rechner_pipeline.qa.security`

**When it runs.** The static gate is applied to LLM-generated Python before execution:

- `PipelineRunner.run_main_llm()` calls `_run_static_security_check_for_items(main_output_items)` after `validate_main_output_files(llm_output)` and before `write_main_output_items_to_generated_dir(...)` writes the generated main files.
- `PipelineRunner.run_test_llm()` calls `_run_static_security_check_for_items([("test_run_advanced.py", extracted)])` before writing the legacy LLM-generated test harness.
- `PipelineRunner.run_compare()` in `test_mode == "llm"` calls `run_static_security_check()` over `generated\*.py` immediately before executing the legacy generated test file.
- `test_mode == "fixed"` does **not** statically scan `golden_master.py`, because that harness is reviewed repository code, not LLM output. The generated calculation files were already scanned by `run_main_llm()`.

**Blocked import roots (`DANGEROUS_IMPORT_ROOTS`).** Any `import` or `from ... import ...` whose root module is listed below produces category `dangerous_import` with message `Import is blocked because it enables <reason>.`:

| Root | Reason |
|---|---|
| `ftplib` | `network access` |
| `http` | `network access` |
| `httpx` | `network access` |
| `importlib` | `dynamic import` |
| `pathlib` | `filesystem access` |
| `requests` | `network access` |
| `runpy` | `dynamic execution` |
| `shutil` | `filesystem access` |
| `socket` | `network access` |
| `subprocess` | `subprocess execution` |
| `tempfile` | `filesystem access` |
| `urllib` | `network access` |

`import os` is intentionally not blocked by itself; concrete unsafe `os.*` calls are blocked. `import glob` is also allowed, with only `glob.glob` and `glob.iglob` whitelisted as read-only listings whose path scope is enforced at runtime by `qa.fs_confine`.

**Allowed call exceptions (`SAFE_CALL_NAMES`).** These calls are allowed even though their roots otherwise match dangerous prefixes: `os.path.join`, `os.path.dirname`, `os.path.basename`, `os.path.abspath`, `os.path.normpath`, `os.path.split`, `os.path.splitext`, `os.path.relpath`, `os.path.commonpath`, `os.path.commonprefix`, `os.fspath`, `glob.glob`, `glob.iglob`.

**Blocked builtins and calls.** Calls are resolved through import aliases (`_SecurityVisitor.aliases`) and then checked by `_check_call()`:

| Rule | Category | Symbols/semantics |
|---|---|---|
| Dynamic builtins (`DANGEROUS_BUILTIN_CALLS`) | `dangerous_call` | `__import__` -> `dynamic import`; `eval` and `exec` -> `dynamic execution`. |
| Builtin `open()` writes | `dangerous_call` | `open` is allowed only for literal/default read modes. Modes containing `w`, `a`, `x`, or `+` are blocked. A non-literal `mode` is conservatively treated as a write. |
| Filesystem-like method names (`FILESYSTEM_METHODS`) | `filesystem_access` | Any call whose final attribute is one of `chmod`, `exists`, `glob`, `is_dir`, `is_file`, `iterdir`, `mkdir`, `open`, `read_bytes`, `read_text`, `rename`, `replace`, `resolve`, `rglob`, `rmdir`, `stat`, `touch`, `unlink`, `write_bytes`, `write_text`. This blocks e.g. `Path(...).read_text()` and `path.exists()`. |
| Dangerous call prefixes (`DANGEROUS_CALL_PREFIXES`) | `dangerous_call` | Any call starting with `ftplib.`, `glob.`, `http.`, `httpx.`, `importlib.`, `os.`, `pathlib.`, `requests.`, `runpy.`, `shutil.`, `socket.`, `subprocess.`, `tempfile.`, or `urllib.`, except the safe calls listed above. |
| Syntax errors | `syntax_error` | `scan_python_source()` returns one `SecurityViolation` at `ast.parse` with `message=exc.msg`. |

**Violation and report format.** Each `SecurityViolation.to_dict()` emits `path`, `line`, `column`, `category`, `symbol`, `message`. `security_report()` emits:

| Key | Type | Meaning |
|---|---:|---|
| `status` | string | `failed` if any violations exist, otherwise `passed`. |
| `checked_files` | array[string] | Python filenames/paths considered by the scan. |
| `violations` | array[object] | Serialized `SecurityViolation` records. |

`write_security_report()` writes this JSON to `generated\static_security_report.json` using UTF-8, `ensure_ascii=False`, `indent=2`, and `\n` newlines. `raise_for_violations()` raises `StaticSecurityError` if the violation list is non-empty. The exception message summarizes the first five violations as `<basename>:<line>:<column> <category> <symbol>` and appends `+N more` when applicable.

#### Fixed golden-master harness: `rechner_pipeline.qa.golden_master`

`golden_master.py` is the reviewed, fixed harness used by default (`PipelineOptions.test_mode == "fixed"`, CLI `--test-mode fixed`). It replaces the legacy per-run LLM-generated `test_run_advanced.py` harness.

**Runtime contract.** The harness runs with current working directory `generated\`, inserts that directory at the front of `sys.path`, imports generated module `test_run`, and requires `test_run.golden_master_outputs()`. Missing import exits with code `2`; missing `golden_master_outputs` exits with code `3`. The required return shape is:

```json
{
  "scalars": {"<prefix>": {"<name>": <number>, "...": "..."}},
  "tables": {"<prefix>": [{"<column>": <number>, "...": "..."}]}
}
```

The expected data directory is `Path.cwd().parent / "info_from_excel"`.

**Expected scalar loading (`load_expected_scalars`).** Files matching `*_scalar.json` are loaded in sorted order. The prefix is the filename without `_scalar.json`. Values are converted by `_to_float()`: `None`, empty strings, and non-convertible values become `None`; numeric strings/numbers become `float`.

**Expected table loading (`load_expected_tables`).** Files matching `*_table_values.csv` are loaded in sorted order with `csv.DictReader`, UTF-8, and `newline=""`. The prefix is the filename without `_table_values.csv`. Each table record is `(header, rows)`, where `header` is the CSV field-name list and `rows` is a list of raw string dictionaries.

**Comparison semantics.**

| Identifier | Exact behavior |
|---|---|
| `ROUND_DECIMALS` | `4`. |
| `_eq4(a, b)` | Compares `round(a, 4) == round(b, 4)`. |
| `_norm_colname(name)` | Removes `_`, space, and `.` only. It preserves case: `Axn` equals `A_xn`, but `Axn` does **not** equal `axn`. Hyphens and other characters are not normalized. |
| Scalar completeness | For each numeric expected scalar, the computed scalar must exist and be float-convertible under the same `prefix` and `name`; otherwise a deviation `"<prefix>:<name> ohne berechneten Wert"` is recorded. Expected `None` scalars are skipped with status `kein-soll`. Extra computed scalars are ignored. |
| Scalar numeric match | A float-convertible computed value passes only if `_eq4(computed, expected)` is true. Mismatch records `"<prefix>:<name> berechnet=<cv> erwartet=<ev>"`. |
| Table column matching | Computed columns are collected across all computed rows, normalized with `_norm_colname`, and matched to expected header names. Separator variants are accepted; case changes are not. |
| Unmatched table columns | If an expected column with any non-empty expected data cannot be matched, `"<prefix>:<col>"` is appended to `Report.unmatched_columns`. **Caveat:** `Report.ok` only checks `deviations`; unmatched columns are reported but do not by themselves make the process exit non-zero. |
| Table row-by-row matching | For each matched expected column and each expected row index `ri`, numeric expected cells are compared against `comp_rows[ri][matched_column]`. Missing computed rows/cells become `None` and record deviations. Extra computed rows/cells are ignored. Row indices are zero-based in messages. |
| Table numeric match | Each numeric expected table cell increments `table_cells_tested` and must satisfy `_eq4`; otherwise deviation `"<prefix>:<col>[<ri>] berechnet=<cv> erwartet=<ev>"` is recorded. |

**`Report` structure and rendering.** `Report` contains `scalars_tested`, `scalars_skipped`, `table_cells_tested`, `unmatched_columns`, `deviations`, `scalar_rows`, and `table_samples`. `scalar_rows` holds `(prefix, name, expected, computed, status)` with statuses `kein-soll`, `fehlt`, `abw`, `ok`. `table_samples` holds `(prefix, column, row_index, expected, computed, status)` for rows `< 20`, capped at 400 samples, with statuses `fehlt`, `abw`, `ok`. `Report.ok` is `not self.deviations`.

`Report.render()` prints the `GOLDEN-MASTER (fester Harness)` banner, scalar/table counts, the first 20 deviations, the first 10 unmatched columns, all scalar rows, table samples, and `RESULT: ALLE <total> TESTS BESTANDEN` or `RESULT: FEHLGESCHLAGEN`. `main()` exits `0` when `Report.ok` is true and `1` otherwise.

#### Runtime confinement: `rechner_pipeline.qa.fs_confine`

`PipelineRunner.run_compare()` executes the selected harness through a subprocess command:

```text
[sys.executable, fs_confine.__file__, str(repo_root), harness_file]
```

The subprocess current working directory is `generated\`, with `capture_output=True`, `text=True`, and `check=False`. `fs_confine.main()` installs guards, rewrites `sys.argv` to the target script plus remaining arguments, and executes the script with `runpy.run_path(script, run_name="__main__")`.

`install(root)` uses `os.path.realpath(root)` and monkey-patches:

| Guard | Behavior |
|---|---|
| `builtins.open` | Blocks modes containing `w`, `a`, `x`, or `+` with `PermissionError("fs-confine: write access is blocked: ...")`; blocks reads whose real path is not the root itself or below the root with `PermissionError("fs-confine: read outside repo root is blocked: ...")`; otherwise delegates to the original `open`. |
| `glob.iglob` | Delegates to the original `glob.iglob` and yields only paths under the real root. Out-of-root matches are silently filtered. |
| `glob.glob` | Returns `list(guarded_iglob(...))`. |

This runtime layer supplies path confinement for read-only `open` and `glob` calls that the static scanner intentionally allows. Writes, subprocess, network, dynamic import/execution, and broad filesystem APIs are expected to be rejected statically before this subprocess is reached.

#### Extraction backend diff: `rechner_pipeline.qa.extraction_diff`

`extraction_diff.py` compares two `info_from_excel` extraction directories, usually COM as the reference and openpyxl as the candidate. It reports material differences separately from accepted backend differences and cosmetic formatting differences. Its CLI parser is named `extraction-diff`, accepts `com_dir` and `other_dir`, prints `DiffReport.render()`, and exits `1` only when `DiffReport.has_material_differences()` is true.

| Area | Comparison behavior |
|---|---|
| Sheet CSVs | Compares raw sheet CSVs from the COM directory, excluding `names_manager.csv` and files ending `_compressed.csv`, `_scalar.json`, or `_table_values.csv`. CSV delimiter is `;`; keys are `(sheet, address_without_$)`, values are `(formula, value)`. Missing addresses and formula differences are material. Numeric token equality uses `math.isclose(rel_tol=1e-9, abs_tol=1e-12)`. Value differences close to `rel_tol=1e-4, abs_tol=1e-3` are accepted precision differences; larger value differences are material. Exact normalized equality with raw formatting differences is cosmetic. |
| VBA | Compares `vba\*.txt` module name sets and line content after universal newline splitting, right-stripping lines, and removing trailing empty lines. Missing modules, line-count differences, and first differing line summaries are material. |
| `names_manager.csv` | Reads delimiter `;` keyed by `Name`. Missing non-`_xl` names are material; missing `_xl` names are accepted. `ValueEvaluated` differences are accepted for `_xl` names or range `RefersTo` values where the other side is blank; otherwise material. `RefersTo` is normalized only by stripping a leading `=`. Differences in `Scope`, `Visible`, `RefersToLocal`, `RefersToRangeAddress`, and `Comment` are cosmetic. |
| Output model | `FileDiff` has `name`, `material`, `accepted`, `cosmetic`. `DiffReport` aggregates files and reports material/accepted/cosmetic counts. Rendered file markers are `[=]` for identical after normalization, `[X]` when material differences exist, and `[~]` for accepted/cosmetic-only differences. |

#### Full-agentic migration boundary for QA

Preserve these deterministic gates as agent-callable scripts: `qa.security` static scan and `generated\static_security_report.json`; `qa.golden_master` fixed objective harness; `qa.fs_confine` runtime read confinement; `qa.extraction_diff` for extraction backend equivalence. In the full-agentic design, the CLI agent's own tool-use loop decides when to run and repair against these gates. Do **not** preserve the legacy LLM-generated test harness as a default path; `test_mode="llm"` is legacy. Add the planned algebraic/roundtrip tests beside the golden-master harness as additional objective gates.

### 2.5 Orchestration, manifest & dossier (AS-IS)

#### Classic runner: `rechner_pipeline.orchestrate.runner`

The classic orchestrator is `PipelineRunner`. It owns the pipeline paths, calls the SDK-backed model client, writes artifacts, and emits a run dossier whether the run succeeds or fails.

**Options (`PipelineOptions`).**

| Field | Type/default | Meaning |
|---|---|---|
| `model` | `str` | Model name after CLI default resolution. |
| `skip_export` | `bool` | Reuse existing `info_from_excel\export_manifest.json` instead of extracting Excel. |
| `skip_main_llm` | `bool` | Skip generated main-code creation. |
| `skip_test_llm` | `bool` | Skip legacy generated test creation. |
| `skip_compare_run` | `bool` | Skip runtime compare/harness execution. |
| `main_max_chars_per_file` / `main_max_total_chars` | `int` | Prompt input limits for the main generation prompt. |
| `test_max_chars_per_file` / `test_max_total_chars` | `int` | Prompt input limits for the legacy test-generation prompt. |
| `reasoning_effort` | `str` | Passed to `generate_completion`. |
| `strict_manifest_warnings` | `bool=False` | If true, `ManifestWarning.strict_error` warnings fail the run. |
| `provider` | `str="openai"` | SDK provider: `openai`, `anthropic`, or `replay`. |
| `max_output_tokens` | `int=32000` | Passed to `generate_completion`. |
| `export_backend` | `str="openpyxl"` | Excel extraction backend. |
| `test_mode` | `str="fixed"` | `fixed` uses `qa.golden_master`; `llm` uses generated `test_run_advanced.py`. |

**Owned paths.** `PipelineRunner.__init__()` sets: `excel_path` default `examples\Tarifrechner_KLV.xlsm`; `prompts\v1\excel_to_py.txt`; `prompts\v1\test_advanced.txt`; `out_dir=info_from_excel`; `manifest_path=info_from_excel\export_manifest.json`; `generated_dir=generated`; `test_py_path=generated\test_run_advanced.py`; `compare_result_path=generated\test_run_advanced_result.json`; `static_security_report_path=generated\static_security_report.json`; `run_dossier_path=generated\run_dossier.json`.

**Stage sequence.** `PipelineRunner.run()` executes:

1. `assert_required_files()` verifies both prompt templates exist.
2. `prepare_manifest()` extracts or loads the export manifest.
3. `run_main_llm()` unless `skip_main_llm`.
4. `run_test_llm()` only when `test_mode == "llm"` and not `skip_test_llm`.
5. `run_compare()` unless `skip_compare_run`.
6. `write_run_dossier(..., run_status="completed")`, then prints `[DOSSIER] <path>` and `[DONE]`.

The whole body is wrapped in `try/except Exception`: on any exception it writes `write_run_dossier(..., run_status="failed")`, prints `[DOSSIER] <path>`, and re-raises.

**`prepare_manifest()`.** When `skip_export` is false, it creates `info_from_excel\`, calls `export_excel_infos(excel_path=..., out_dir=..., save_manifest_json=True, backend=options.export_backend)`, converts the returned dictionary with `ExportManifest.from_dict()`, refreshes output hashes, writes the manifest, and enforces strict warnings. When `skip_export` is true, it loads the existing manifest or raises `FileNotFoundError`. An empty `manifest.llm_inputs` raises `RuntimeError("manifest['llm_inputs'] is empty.")`.

**`run_main_llm()`.** Reloads the latest manifest, reads `excel_to_py.txt`, stuffs `manifest.llm_inputs` from `info_from_excel\` under the configured limits, and fills placeholders `PIPELINE_META` (`out_dir`, `llm_inputs_count`, `replacements`) and `INPUT_FILES`. If repair context exists, `_append_repair_context()` appends a `## Agentic repair context` section. The prompt is written to `runs\...\main_prompt.txt`; the raw model output is written to `runs\...\main_output.txt`. Prompt warnings and `PromptRecord` metadata are written before and after the SDK call. `validate_main_output_files()` requires the generated main output contract; the expected main files are `inputs.py`, `params.py`, `tafeln.xml`, `commutation.py`, `actuarial.py`, and `test_run.py`. Static security scans the extracted Python items before they are written to `generated\`. Output hashes are refreshed for those files plus `generated\static_security_report.json`.

**`run_test_llm()` (legacy only).** Builds test inputs from `*_table_values.csv`, `*_scalar.json`, and existing generated core files (`actuarial.py`, `commutation.py`, `inputs.py`, `params.py`, `test_run.py`). It fills `test_advanced.txt` placeholders with `info_from_excel_dir`, `generated_dir`, `table_values_count`, `scalar_json_count`, and stuffed input text. The prompt/output go to `runs\...\test_prompt.txt` and `runs\...\test_output.txt`. It extracts `test_run_advanced.py` using exact markers `===FILE_START: test_run_advanced.py===` and `===FILE_END: test_run_advanced.py===`; failure to find the block raises `RuntimeError`. The extracted test is statically scanned before it is written to `generated\test_run_advanced.py`; output hashes are refreshed for the test file and security report.

**`run_compare()`.** In `test_mode == "fixed"`, `harness_file` is `qa.golden_master.__file__`. In `test_mode == "llm"`, `generated\test_run_advanced.py` must exist and `run_static_security_check()` rescans `generated\*.py`; `StaticSecurityError` is wrapped as `RuntimeError("Static security check blocked generated test execution. Structured report written to ...")`. The harness is executed through `qa.fs_confine` as described above. A structured result is written to `generated\test_run_advanced_result.json` with keys `test_file`, `command`, `cwd`, `returncode`, `stdout`, `stderr`, and `status` (`passed` or `failed`). The manifest is refreshed with hashes for `test_run_advanced.py`, the compare result, and the static security report. Non-zero return code raises `RuntimeError("Regression test failed with returncode ...")`.

#### Agentic orchestration: `rechner_pipeline.orchestrate.agentic`

This file wraps the classic runner in a LangGraph `StateGraph`. It is called "agentic" in the repository, but it is still SDK/LangGraph orchestration around model calls, not the target full-agentic CLI design.

**State and options.** `AgenticState` may contain `repo_root`, `excel_path`, `options`, `manifest`, `step_status`, `failed_step`, `errors`, `diagnostics`, `repair_contexts`, `repair_artifacts`, `agentic_diagnostics_path`, `retries`, `gate_decision`, and `human_review_required`. `AgenticOptions` contains `pipeline`, `max_retries_main`, `max_retries_test`, and `fail_on_human_review`. The CLI initializes `retries` with `_max_main` and `_max_test`.

**Node inventory.**

| Node | Function | Behavior |
|---|---|---|
| `prepare` | `prepare_node` | Builds a `PipelineRunner`, verifies prompts, runs `prepare_manifest()`, logs extracted sheets/VBA/inputs/formula samples, sets `step_status.prepare=ok`; on exception records diagnostics and sets `error`. |
| `gate_prepare` | `gate_after_prepare_node` | `_gate_step("prepare", max_retries=0)`: continue on non-error, otherwise human review. |
| `main_llm` | `main_llm_node` | Skips if `options.skip_main_llm`; otherwise calls `runner.run_main_llm(manifest, repair_context=repair_contexts["main_llm"])`, captures replay fixture, logs prompt/code/function/golden-master-output excerpts, clears repair context, sets `ok`; on exception records diagnostics and sets `error`. |
| `repair_main` | `repair_main_node` | Logs a correction message and calls `_repair_node(..., target_step="main_llm")`. |
| `gate_main` | `gate_after_main_node` | `_gate_step("main_llm", max_retries=retries["_max_main"])`: continue, repair, or human review. |
| `test_llm` | `test_llm_node` | Skips when `options.skip_test_llm` or `options.test_mode == "fixed"`; otherwise calls legacy `runner.run_test_llm(...)`, clears repair context, sets `ok`; on exception records diagnostics and sets `error`. |
| `repair_test` | `repair_test_node` | Calls `_repair_node(..., target_step="test_llm")`. |
| `gate_test` | `gate_after_test_node` | `_gate_step("test_llm", max_retries=retries["_max_test"])`: continue, repair, or human review. |
| `compare` | `compare_node` | Skips if `skip_compare_run`; otherwise calls `runner.run_compare()`. On success logs scalar/table summaries and convergence with zero deviations, sets `ok`. On failure parses compare output, logs deviations, records diagnostics, and sets `error`. |
| `gate_compare` | `gate_after_compare_node` | If compare errored, chooses `repair_main` for `test_mode == "fixed"` or `repair_test` for `test_mode != "fixed"`, using `retries["compare"]` bounded by `_max_main` or `_max_test`; otherwise returns `finish`. |
| `human_review` | `human_review_node` | Writes `run_dossier.json` with `run_status="human_review_required"`, prints `[HUMAN_REVIEW_REQUIRED]`, errors, dossier path, diagnostics path, and repair artifacts, then ends. |

**Graph edges and conditional routes.**

| Source | Route/condition | Target |
|---|---|---|
| `START` | direct | `prepare` |
| `prepare` | direct | `gate_prepare` |
| `gate_prepare` | `route_from_gate == "continue"` | `main_llm` |
| `gate_prepare` | `route_from_gate == "human_review"` | `human_review` |
| `main_llm` | direct | `gate_main` |
| `repair_main` | direct | `main_llm` |
| `gate_main` | `continue` | `test_llm` |
| `gate_main` | `repair` | `repair_main` |
| `gate_main` | `human_review` | `human_review` |
| `test_llm` | direct | `gate_test` |
| `repair_test` | direct | `test_llm` |
| `gate_test` | `continue` | `compare` |
| `gate_test` | `repair` | `repair_test` |
| `gate_test` | `human_review` | `human_review` |
| `compare` | direct | `gate_compare` |
| `gate_compare` | `finish` | `END` |
| `gate_compare` | `repair_main` | `repair_main` |
| `gate_compare` | `repair_test` | `repair_test` |
| `gate_compare` | `human_review` | `human_review` |
| `human_review` | direct | `END` |

**Gate, retry, and repair mechanics.** `_gate_step()` treats any non-`error` status as `continue`. For an `error`, it reads the current retry count for that step; if below the configured max, it increments that step key and returns `gate_decision="repair"`; otherwise it sets `human_review_required=True` and routes to human review. `gate_after_prepare_node()` has zero retries. `gate_after_compare_node()` is special: compare failures in fixed mode mean the generated calculation core is wrong, so it routes to `repair_main`; compare failures in legacy `llm` mode route to `repair_test`. It increments `retries["compare"]`, not `retries["main_llm"]` or `retries["test_llm"]`.

**Diagnostics and repair context.** `_record_error()` appends a summary and traceback to `errors`, writes a structured diagnostic to `generated\agentic_diagnostics.json`, and returns `failed_step`, `diagnostics`, and `agentic_diagnostics_path`. `_classify_exception()` maps `OutputValidationError` to `compile` if the message contains `do not compile`, otherwise `output_contract`; `SyntaxError`/`IndentationError` to `compile`; `StaticSecurityError` or messages containing `static security` to `runtime_security`; compare/regression/return-code failures to `test`; everything else to `runtime`. Diagnostics include `created_at`, `step`, `category`, `exception.type`, `exception.message`, `traceback`, `retry_counts`, and `artifacts` for the manifest, static security report, compare result, debug prompt where relevant, and `test_run_advanced.py` where relevant.

`_format_repair_context()` emits JSON with exactly `failed_step`, `category`, `exception`, and `artifacts`. `_repair_node()` writes `generated\agentic_repair_context_<target_step>.json` containing `schema_version`, `created_at`, `target_step`, `source_step`, `category`, and `repair_context`, then stores the string context in `repair_contexts[target_step]`. `runner._append_repair_context()` appends this context under the literal Markdown heading `## Agentic repair context` to the next LLM prompt.

**Convergence logging.** `_compare_summary()` parses `generated\test_run_advanced_result.json` stdout for `ABWEICHUNG:` lines, `Abweichungen: <n>`, and all `getestet=<n>` counters. `_record_convergence()` writes `runs\...\convergence.csv` rows as `iteration;deviations;tested`, overwriting on iteration 1 and appending later. `_iteration_no()` is `retries["compare"] + 1`. `main_llm_node()` also stores per-iteration prompt copies and `gm_return_<n>.txt` excerpts of `golden_master_outputs()` for diffs.

**Human review handoff.** `human_review_node()` writes a dossier and prints diagnostic pointers. After graph completion, `cli.agentic_main()` writes the dossier again using the final state. If `--fail_on_human_review` is set it raises `RuntimeError("Pipeline ended in HUMAN_REVIEW_REQUIRED.")`; otherwise it prints `[DONE_WITH_HUMAN_REVIEW]`. Successful runs write a completed dossier and print `[DONE]`.

**Full-agentic migration boundary for orchestration.** In the target design, the LangGraph nodes, conditional edges, Python retry counters, SDK `generate_completion()` calls, prompt-stuffing limits, `test_mode="llm"`, and repair prompt injection become the CLI agent's own tool-use loop. The objective gates remain as scripts the agent runs and must satisfy: manifest preparation/export, static security, fixed golden-master plus new algebraic/roundtrip tests, filesystem-confined execution, extraction diff, and dossier/manifest provenance writing.

#### Manifest schema: `rechner_pipeline.models.manifest`

All manifest paths serialize as strings. Hashes are SHA-256 hex strings from `text_sha256()` or `file_sha256()`.

**Top-level `ExportManifest.to_dict()`.**

| JSON key | Type | Required on write | Source field / semantics |
|---|---:|---:|---|
| `out_dir` | string | yes | `ExportManifest.out_dir`. |
| `sheet_csvs` | array[string] | yes | Sheet CSV artifact paths. |
| `vba_txts` | array[string] | yes | VBA text artifact paths. |
| `names_manager_csv` | string | yes | Path string, or `""` when `None`. |
| `replacements` | object[string,string] | yes | Replacement map from extraction. |
| `llm_inputs` | array[string] | yes | Files stuffed into the main prompt. |
| `all_outputs` | array[string] | yes | All declared extraction/pipeline outputs. |
| `warnings` | array[`ManifestWarning`] | yes | Manifest warnings. |
| `prompt_runs` | array[`PromptRecord`] | yes | One record per prompt stage; `with_prompt_record()` replaces by matching `stage`. |
| `output_hashes` | array[`FileHashRecord`] | yes | Existing file hashes from `with_output_hashes()`. |

**`ManifestWarning`.**

| JSON key | Type | Required on write | Notes |
|---|---:|---:|---|
| `code` | string | yes | Warning code, e.g. `prompt.file_truncated`. |
| `stage` | string | yes | Stage that produced the warning. |
| `message` | string | yes | Human-readable message. |
| `strict_error` | boolean | yes | Blocks the run when `strict_manifest_warnings` is true. |
| `path` | string | omitted if empty | Optional affected path. |
| `details` | object | omitted if empty/`None` | Optional structured details. |

`ExportManifest.with_warnings()` merges existing and new warnings, deduplicating by `(code, stage, path, message)`. `strict_error_warnings()` returns warnings where `strict_error` is true.

**`PromptInputRecord`.**

| JSON key | Type | Required | Notes |
|---|---:|---:|---|
| `path` | string | yes | Input file path. |
| `label` | string | yes | Prompt label. |
| `original_chars` | integer | yes | Full source length. |
| `included_chars` | integer | yes | Length included in prompt. |
| `original_sha256` | string | yes | SHA-256 of full source text. |
| `truncated` | boolean | yes | Whether per-file truncation occurred. |

**`PromptRecord`.**

| JSON key | Type | Required on write | Notes |
|---|---:|---:|---|
| `stage` | string | yes | Prompt stage, e.g. `main_llm` or `test_llm`. |
| `template_path` | string | yes | Prompt template path. |
| `debug_prompt_path` | string | yes | Written prompt path under `runs\...`. |
| `prompt_chars` | integer | yes | Final prompt length. |
| `prompt_sha256` | string | yes | Final prompt hash. |
| `input_files` | array[`PromptInputRecord`] | yes | Stuffed input metadata. |
| `total_limit_reached` | boolean | yes | Whether total prompt limit stopped input assembly. |
| `output_chars` | integer | omitted if `None` | Raw model output length. |
| `output_sha256` | string | omitted if empty | Raw model output hash. |

**`FileHashRecord`.**

| JSON key | Type | Required | Notes |
|---|---:|---:|---|
| `path` | string | yes | File path. |
| `bytes` | integer | yes | `path.stat().st_size`. |
| `sha256` | string | yes | File SHA-256. |

`ExportManifest.with_output_hashes(paths)` skips duplicate path strings, missing paths, and non-files.

#### Run dossier schema: `rechner_pipeline.orchestrate.dossier`

`write_run_dossier()` writes `generated\run_dossier.json` with UTF-8 JSON, `ensure_ascii=False`, `indent=2`. `build_run_dossier()` returns this structure:

| JSON path | Type | Meaning |
|---|---:|---|
| `schema_version` | integer | Always `1`. |
| `created_at` | string | UTC ISO timestamp from `_utc_now()`. |
| `run.status` | string | Caller-supplied run status, e.g. `completed`, `failed`, `human_review_required`. |
| `run.human_review_required` | boolean | Caller-supplied handoff flag. |
| `run.repo_root` | string | Runner repo root. |
| `run.excel_path` | string | Runner Excel input path. |
| `run.options` | object | Only keys present in `_options_dict()`: `model`, `skip_export`, `skip_main_llm`, `skip_test_llm`, `skip_compare_run`, `main_max_chars_per_file`, `main_max_total_chars`, `test_max_chars_per_file`, `test_max_total_chars`, `reasoning_effort`, `strict_manifest_warnings`. **Caveat:** `provider`, `max_output_tokens`, `export_backend`, and `test_mode` exist on `PipelineOptions` but are not emitted here. |
| `artifacts.run_dossier` | string | Dossier path. |
| `artifacts.manifest` | `PathRecord` | `info_from_excel\export_manifest.json`. |
| `artifacts.static_security_report` | `PathRecord` | `generated\static_security_report.json`. |
| `artifacts.compare_result` | `PathRecord` | `generated\test_run_advanced_result.json`. |
| `artifacts.agentic_diagnostics` | `PathRecord` | `agentic_state.agentic_diagnostics_path` or `generated\agentic_diagnostics.json`. |
| `artifacts.agentic_repair_artifacts` | object[string,string] | Copy of `agentic_state.repair_artifacts`. |
| `manifest.path` | string | Manifest path. |
| `manifest.exists` | boolean | False if no manifest could be loaded. |
| `manifest.out_dir` | string | Present only when manifest exists. |
| `manifest.sheet_csv_count` | integer | Count of `manifest.sheet_csvs`. |
| `manifest.vba_txt_count` | integer | Count of `manifest.vba_txts`. |
| `manifest.names_manager_csv` | string | Path or empty string. |
| `manifest.llm_input_count` | integer | Count of `manifest.llm_inputs`. |
| `manifest.all_output_count` | integer | Count of `manifest.all_outputs`. |
| `manifest.warning_count` | integer | Count of `manifest.warnings`. |
| `manifest.prompt_run_count` | integer | Count of `manifest.prompt_runs`. |
| `manifest.output_hash_count` | integer | Count of `manifest.output_hashes`. |
| `prompt_hashes[]` | array[object] | One per `PromptRecord`: `stage`, `template_path`, `debug_prompt_path`, `prompt_chars`, `prompt_sha256`, `output_chars`, `output_sha256`, `input_file_count`, `total_limit_reached`, `truncated_input_files`. |
| `outputs.all_outputs` | array[string] | Manifest output paths, or empty when manifest missing. |
| `outputs.output_hashes` | array[`FileHashRecord`] | Manifest output hashes, or empty when manifest missing. |
| `generated_files[]` | array[`PathRecord`] | All files recursively under `generated\`, sorted, excluding `run_dossier.json`. |
| `test_summary.status` | string | `not_run` if compare result missing; otherwise payload `status` or `unknown`. |
| `test_summary.result_path` | string | Compare result path. |
| `test_summary.returncode` | integer/null | From compare payload. |
| `test_summary.test_file` | string | From compare payload, default `""`. |
| `test_summary.command` | array | From compare payload, default `[]`. |
| `test_summary.cwd` | string | From compare payload, default `""`. |
| `test_summary.stdout_excerpt` | string | Present if compare payload has `stdout`, capped at 4000 chars plus `... <truncated>`. |
| `test_summary.stderr_excerpt` | string | Present if compare payload has `stderr`, capped at 4000 chars plus `... <truncated>`. |
| `test_summary.read_error` | string | Present if compare JSON could not be read. |
| `warnings[]` | array[`ManifestWarning`] | Serialized manifest warnings. |
| `open_assumptions[]` | array[object] | See below. |

`PathRecord` is `{ "path": string, "exists": boolean }` plus `bytes` and `sha256` when the path exists and is a file.

**`open_assumptions[]` entries.** `_open_assumptions()` may emit:

| `code` | Additional keys | Condition |
|---|---|---|
| `pipeline.skip_export` | `message` | `skip_export` true. |
| `pipeline.skip_main_llm` | `message` | `skip_main_llm` true. |
| `pipeline.skip_test_llm` | `message` | `skip_test_llm` true. |
| `pipeline.skip_compare_run` | `message` | `skip_compare_run` true. |
| `manifest.missing` | `message` | No manifest available. |
| `manifest_warning.<warning.code>` | `message`, `stage`, `path`, `strict_error` | For each manifest warning. |
| `prompt.output_hash_missing` | `message`, `stage` | A prompt record has no `output_sha256`. |
| `compare.result_missing` | `message` | Compare result missing and compare was not explicitly skipped. |
| `compare.failed` | `message`, `returncode` | Compare result status is `failed`. |
| `security_report.missing` | `message` | Generated Python exists but `generated\static_security_report.json` is absent. |
| `human_review.required` | `message` | Human-review handoff flag is true. |

These provenance artifacts must be preserved in the full-agentic migration. They are the audit trail tying extracted Excel inputs, prompts/model outputs or agent actions, generated code, security gates, compare results, and human-review assumptions together.

#### Workflow log helper: `rechner_pipeline.orchestrate.wflog`

`wflog` is formatting-only live logging. It is off by default and enabled by `RP_WFLOG` or `enable()`. It writes to stdout and lazily to `runs\<timestamp>\workflow_log.txt` (or `runs\demo\` for replay/demo; base override `RP_RUN_DIR`; file override `RP_WFLOG_FILE`). `run_stamp()` is `YYYYmmdd_HHMMSS`; `elapsed()` supports summary timing. It provides phase/detail/code/items/iteration/ok/fail/rule/table/diff helpers and caps item lists with `RP_WFLOG_MAX_ITEMS` default `12`. This is not a QA gate; it is operator observability and can be replaced by the full-agentic CLI's transcript plus preserved structured artifacts.

#### CLI entry points and arguments: `rechner_pipeline.cli`

Console scripts are registered as `rechner-pipeline = rechner_pipeline.cli:main` and `rechner-pipeline-agentic = rechner_pipeline.cli:agentic_main`; root wrappers `pipeline.py` and `agentic_pipeline.py` are documented as backward-compatible entry points.

**Common arguments from `_add_common_options()`.**

| Argument | Default / choices | As-is effect | Full-agentic status |
|---|---|---|---|
| `--provider` | default `openai`; choices `openai`, `anthropic`, `replay` | Selects SDK client; also marks replay as demo for `wflog`. | Obsolete: the CLI agent is the model. A replay/demo concept may survive separately for fixtures. |
| `--model` | provider default: `openai=gpt-5.2`, `anthropic=claude-sonnet-4-6`, `replay=replay` | Passed to `PipelineOptions.model`. | Obsolete. |
| `--max_output_tokens` | `32000` | Passed to SDK generation; OpenAI Responses ignores it per help text. | Obsolete. |
| `--excel` | `None` | Absolute path used as-is; relative path resolved against repo root; runner default is `examples\Tarifrechner_KLV.xlsm`. | Survives as source-workbook selection. |
| `--export-backend` | `openpyxl`; choices `openpyxl`, `com` | Selects extraction backend. | Survives if multiple extraction backends remain. |
| `--test-mode` | `fixed`; choices `fixed`, `llm` | Chooses fixed golden-master harness or legacy generated test. | `fixed` concept survives; `llm` becomes obsolete. |
| `--skip_export` | false | Reuse previous manifest/extraction. | Operational cache/diagnostic concept may survive. |
| `--skip_main_llm` | false | Skip model generation stage. | Obsolete as named; full-agentic may use explicit "reuse generated code" controls instead. |
| `--skip_test_llm` | false | Skip legacy test generation. | Obsolete with `test_mode="llm"`. |
| `--skip_compare_run` | false | Skip objective validation. | Dangerous but may survive only as an explicit diagnostic override recorded in dossier. |
| `--main_max_chars_per_file`, `--main_max_total_chars` | `500000`, `2500000` | Prompt stuffing limits for main SDK call. | Obsolete when prompt stuffing is removed. |
| `--test_max_chars_per_file`, `--test_max_total_chars` | `500000`, `2500000` | Prompt stuffing limits for legacy test SDK call. | Obsolete. |
| `--reasoning_effort` | `medium`; choices `low`, `medium`, `high` | Passed to SDK call. | Obsolete. |
| `--strict_manifest_warnings` | false | Treat strict manifest warnings as pipeline errors. | Survives. |

`main()` constructs `PipelineRunner(...).run()`. `agentic_main()` adds `--max_retries_main` (default `1`), `--max_retries_test` (default `1`), and `--fail_on_human_review`; builds the LangGraph state; invokes the graph; prints the optional summary card; writes the final dossier; and prints `[DONE]` or `[DONE_WITH_HUMAN_REVIEW]`. In full-agentic migration, Python-managed retry counts and LangGraph handoff are replaced by the CLI agent's own repair loop, but the concepts of bounded attempts, explicit human-review handoff, failing CI on unresolved review, and preserving diagnostics should remain.

---

### 2.6 Known AS-IS limitations

These are limitations of the current repository behavior, not target-design requirements. The migration must either remove the affected path or add a deterministic, fail-fast gate.

| AS-IS limitation | Impact | Migration requirement |
|---|---|---|
| `golden_master.Report.ok` is `not self.deviations` and ignores `unmatched_columns`. | A table column that never maps to generated output can be printed as unmatched but still exit successfully if no other deviation exists. This is a false acceptance risk. | Fix the gate so any unmatched expected column with data fails; add a regression test that an unmatched table column returns non-zero. |
| `generated\run_dossier.json` omits `provider`, `max_output_tokens`, `export_backend`, and `test_mode` from `run.options`. | The audit trail cannot fully reconstruct which SDK path, backend, token cap, or test mode produced a legacy run. This weakens reproducibility and incident analysis. | Extend/replace the dossier schema so all effective run options, gate commands, tool versions, artifact hashes, and open assumptions are recorded. |
| `apply_placeholders()` silently leaves unresolved `{{...}}` tokens. | A misspelled or missing placeholder can reach the model as literal prompt text and cause generation drift without a configuration failure. | Remove prompt stuffing in the full-agentic path. If any templating remains, fail on unresolved placeholders and unknown placeholder names. |
| The OpenAI provider path does not pass `max_output_tokens`. | The CLI option is misleading for OpenAI runs; output length is not controlled by the advertised setting, and truncation behavior differs from Anthropic. | Remove the OpenAI SDK path. Until removed, document the caveat and do not rely on this option for acceptance. |
| Unknown Anthropic `reasoning_effort` maps to a `0` thinking budget. | A typo silently disables extended thinking instead of failing. The run may look valid but use materially different model settings. | Remove the Anthropic SDK path. Any remaining enum-like option must validate strictly and fail on unknown values. |
| Legacy `_TEST_BLOCK_RE` for `test_run_advanced.py` is weaker than the main six-file validator. | It is not anchored, allows surrounding text, and validates only one file block. A malformed legacy test response can pass extraction that the main contract would reject. | Remove `test_mode="llm"` as a default/supported path; keep one strict validator for the exact generated file contract. |
| COM A1-address formatting is ambiguous: code requests non-absolute A1, but fixtures show `$A$1`; openpyxl always writes `$A$1`. | Downstream scalar/table extraction depends on absolute address keys. Relative COM addresses can cause missed lookups and `None` expectations. | Canonicalize or require `$A$1` addresses before scalar/table extraction; verify COM/openpyxl equivalence. |
| Scalar/table lookup expects `$A$1`-style keys. | Any adapter or backend that emits `A1` keys can silently produce incomplete scalar JSON or table CSV values. | Make address canonicalization part of the input-bundle validator and fail on incompatible keys. |
| Extraction output directories are not cleaned. Existing `_compressed.csv`, `_scalar.json`, and `_table_values.csv` can be reused or globbed. | Stale derived files can pollute `manifest.all_outputs`, prompt inputs, and golden-master expectations, producing false context or false validation. | Extract into a clean/staged directory or delete derived outputs before extraction; record content hashes and fail on unexpected stale artifacts. |
| `openpyxl` reads cached workbook values, not live recalculated Excel values. | If the workbook was not recalculated and saved, formula cells may have missing or stale cached values; the golden master then validates against stale expectations. | State this as the default backend contract. Use COM/recalculation only as an explicit deterministic backend and verify with `extraction_diff` where policy requires it. |
| VBA extraction warnings are strict warning objects, but runner enforcement depends on `strict_manifest_warnings`. | With strict enforcement disabled, a run may proceed after missing VBA modules, compression failures, or scalar/table extraction failures. | In the target acceptance path, blocking extraction warnings must fail unless explicitly recorded as human-review/non-acceptance. |
| Name-manager behavior differs by backend. `openpyxl` evaluates only exactly one destination cell; COM attempts broader Excel evaluation and has scope-label ambiguities. | Generated code can see different name metadata depending on backend, especially for ranges, formulas, and workbook-vs-worksheet scope. | Treat backend differences as material unless covered by `extraction_diff` rules and dossiered exceptions. |
| Prompt stuffing can truncate files or stop at `max_total_chars`; those warnings are strict only if enforced. | The model can miss source artifacts while still producing output when strict warnings are not fatal. | Replace stuffed mega-prompts with direct file reads by the CLI agent and fail on missing required artifacts. |
| The AS-IS evidence base is partly source-verified. Wave-1 extraction notes reported `openpyxl`/`oletools` unavailable in that environment. | Some claims were not re-executed end-to-end by subagents; they are grounded in source inspection and fixtures, not fresh runtime proof. | Re-run baseline extraction/golden tests in the migration environment before changing behavior. |
| Golden-master coverage is limited to exported workbook-observed values. | Passing the current golden master does not prove correctness outside exported cells, product variants, ages, terms, rounding boundaries, or workbook bugs. | Keep golden master as necessary but add algebraic/property, roundtrip, convention, security, and dossier-completeness gates. |
| The current fixed harness can pass zero-comparison situations if no expectation files are present. | Non-Excel or sparse inputs can look "green" without meaningful numeric validation. | Input adapters must declare expectation coverage (`full`, `sparse`, `none`); sparse/none cannot be accepted as full golden equivalence. |

---

## 3 TARGET design (full-agentic, CLI-agnostic)

The target design makes the outer CLI agent the only model and orchestrator. Python no longer hosts Anthropic/OpenAI SDK clients, API-key resolution, prompt stuffing, or LangGraph routing. Instead, the current prompt rules become reusable skill/instruction content, and the deterministic Python code becomes a CLI-agnostic toolbox for extraction, validation, security, golden-master comparison, algebraic/property checks, roundtrips, conventions, and dossier writing. The portable baseline is deliberately the lowest common denominator across Claude CLI, GitHub Copilot CLI, Codex CLI, and OpenCode CLI: every agent can read files, edit files, and run plain shell commands; local stdio MCP is optional and must remain a thin wrapper over those same commands.

### 3.1 Architecture overview

```text
User prompt
  "build a Vergleichsrechenkern from C:\...\Tarifrechner_KLV.xlsm"
        |
        v
+--------------------------------------------------------------+
| CLI-specific instruction adapter                             |
| - Claude: native SKILL.md                                    |
| - Copilot/Codex: project instructions/custom prompt          |
| - OpenCode: command/instructions                             |
+--------------------------------------------------------------+
        |
        v
+--------------------------------------------------------------+
| build-vergleichsrechenkern skill body (§6.7)                 |
| trigger, actuarial rules, exact FILE contract, tool commands,|
| bounded self-repair convention                               |
+--------------------------------------------------------------+
        |
        v
+--------------------------------------------------------------+
| CLI agent = model + planner + repair loop                    |
| No Python SDK model client. No LangGraph orchestration.      |
+--------------------------------------------------------------+
        |
        v
python -m rechner_pipeline.toolbox.extract --input <source> ...
        |
        v
InputBundle / info_from_excel\
  export_manifest.json
  sheet/compressed CSVs, names_manager.csv, source/VBA text,
  *_scalar.json, *_table_values.csv, warnings, hashes
        |
        v
Agent reads bundle artifacts and writes exactly, in this order:
  generated\inputs.py
  generated\params.py
  generated\tafeln.xml
  generated\commutation.py
  generated\actuarial.py
  generated\test_run.py
        |
        v
python -m rechner_pipeline.toolbox.validate      # 6-file/compile/schema
python -m rechner_pipeline.toolbox.security      # static security
python -m rechner_pipeline.toolbox.conventions   # imports/cache/layers
python -m rechner_pipeline.toolbox.golden_master # Excel-observed values
python -m rechner_pipeline.toolbox.algebraic     # identities/properties
python -m rechner_pipeline.toolbox.roundtrip     # XML/extraction/stability
python -m rechner_pipeline.toolbox.dossier       # gate-status ledger
        |
        +---------------- failure JSON ----------------+
        |                                               v
        |                                  Agent edits generated\ only,
        |                                  re-runs required gates,
        |                                  bounded attempts
        v
DONE iff every required gate passes; otherwise human_review_required
```

This design preserves the Excel path 1:1 at the artifact boundary: the agent still consumes the same `info_from_excel\` shapes, and the generated package is still the same six-file package. What changes is the model boundary. The old SDK/LangGraph layer is removed; the CLI agent follows skill instructions, invokes deterministic scripts, and uses their JSON diagnostics to repair. Acceptance is not based on trusting the agent. It is based on deterministic, rerunnable gates over content-addressed inputs and generated files.

### 3.2 Skill spec: build-vergleichsrechenkern

**Trigger phrasing.** Use this skill/instruction set when the user asks for `build-vergleichsrechenkern`, `build a Vergleichsrechenkern`, `Vergleichsrechenkern erstellen`, `Excel/VBA Tarifrechner nach Python migrieren`, `build a comparison kernel`, or explicitly requests generation of `inputs.py`, `params.py`, `tafeln.xml`, `commutation.py`, `actuarial.py`, and `test_run.py` from a workbook or future source bundle.

**Ordered steps.**

1. Resolve the repository root, source path, output directories, adapter selection, and `max_attempts`. Missing source files, unsupported adapters, or invalid paths fail immediately.
2. Run `python -m rechner_pipeline.toolbox.extract`. Stop on non-zero exit; extraction/configuration failures are not blind generation opportunities.
3. Read `export_manifest.json` and the listed bundle artifacts. If both raw and `*_compressed.csv` exist for a sheet, use the compressed CSV for semantic analysis, while keeping raw CSVs for provenance and expectations.
4. Generate or edit exactly the six files in the required order: `inputs.py`, `params.py`, `tafeln.xml`, `commutation.py`, `actuarial.py`, `test_run.py`. Direct file edits are preferred. If a CLI response must be parsed as text, it must use the original `===FILE_START: <name>===` / `===FILE_END: <name>===` wrappers with no outer text.
5. Run the deterministic gates: `validate`, `security`, `conventions`, `golden_master`, `algebraic`, `roundtrip`, and `dossier` as required by policy.
6. On a gate failure, read only the structured JSON diagnostics and repair hints, then repair only the generated files or the explicit QA contract metadata inside them. Do not change extraction artifacts to make the generated code pass.
7. Re-run all required gates after each repair. Do not treat a previously passed gate as still valid after source changes unless the gate explicitly reports a matching input hash.
8. Stop only when the dossier says `accepted`, or when the bounded attempts are exhausted and the dossier says `human_review_required` or `failed`.

**Migrated rules carried by the skill.** The canonical TARGET instruction body is reproduced in full in §6.7 (the AS-IS prompt text is preserved separately in §6.1 for reference only); the skill summary must carry these hard rules:

- Role and goal: senior actuarial developer and Python engineer; deterministic 1:1 migration of Excel formulas and VBA into pure Python without Excel.
- No external services, network calls, subprocess execution, runtime package installation, Excel runtime dependency, hidden randomness, or environment-dependent behavior in generated code.
- No guessed Excel cell addresses. Build a parameterized API from extracted labels, formulas, defined names, VBA/source text, scalar expectations, and table expectations.
- Exact six-file contract and order: `inputs.py`, `params.py`, `tafeln.xml`, `commutation.py`, `actuarial.py`, `test_run.py`.
- Layering: `actuarial.py -> commutation.py` is the only permitted direction between those layers. `commutation.py` owns mortality-table access, commutation values, and technical/math utilities; `actuarial.py` owns tariff/product present-value logic. Circular imports, function-local imports, `try/except ImportError`, and `TYPE_CHECKING` tricks are forbidden.
- Caching: `lru_cache` may be used only with strictly hashable arguments; unknown hashability fails validation.
- Mortality tables: recognized `qx` data must be serialized to `tafeln.xml`; unrecognized tables/products must raise explicit exceptions such as `NotImplementedError`, never invented placeholder tables or silent defaults.
- `test_run.py` must expose `golden_master_outputs() -> dict` with `scalars` and `tables`; scalar names must cover every expected scalar, including derived rates/parameters, and table rows/headers must preserve expected order and case-sensitive names.

**Bounded self-repair convention.** LangGraph retry counters are replaced by an explicit instruction-level bound: default `max_attempts = 4` total generation attempts (initial generation plus three repairs). A user may set `max_attempts=N`; the normal cap is `6` unless the user explicitly overrides it. An attempt is counted after generated files are written/edited and at least one required gate is run. Extraction, missing dependency, unsupported source, permission, or invalid configuration errors fail fast and do not consume repair attempts. On exhaustion, the agent must stop, preserve diagnostics, and mark the run `human_review_required`; it must not silently reduce the gate set or accept partial results.

### 3.3 Deterministic toolbox

All toolbox commands are plain, non-interactive Python modules callable by every supported CLI:

```powershell
python -m rechner_pipeline.toolbox.<command> [flags]
```

Common contract:

- Inputs are explicit flags; optional `--request-json -` may read one UTF-8 JSON request from stdin, but flags must remain available for Windows shell reliability.
- `stdout` is exactly one JSON object and no logs. Human logs go to `stderr`.
- Common JSON fields: `schema_version`, `command`, `status` (`passed`, `failed`, `human_review_required`), `paths`, `summary`, `gate_version`, `input_hashes`, optional `errors`, `repair_hints`, `warnings`, `metrics`, and `diagnostics_path`.
- Exit code `0` means the selected gate passed. Any non-zero exit is blocking and must not be downgraded to a warning by the skill.
- Standard exit codes: `2` usage/configuration, `10` extraction/InputBundle failure, `20` file-contract/compile/schema failure, `21` static security failure, `22` architecture/convention/import failure, `30` golden-master mismatch, `31` algebraic/property/unknown-applicability failure, `32` roundtrip/hash-stability failure, `40` dossier/provenance failure, `50` internal toolbox error.

| Command | Required inputs | JSON stdout summary | Blocking failures |
|---|---|---|---|
| `extract` | `--repo-root`, `--input`, `--out-dir`, optional `--adapter auto|excel|word|...`, `--export-backend openpyxl|com`, `--strict-manifest-warnings` | `InputBundle` paths, manifest path, artifact counts, expectation coverage, warnings, hashes | Missing source, unsupported adapter, dependency unavailable, strict warning, invalid manifest, empty `llm_inputs` |
| `validate` | `--repo-root`, `--generated-dir`, `--info-dir`, optional `--file-block-response <path>` | Extracted file names/order, compile result, `golden_master_outputs()` schema precheck | Missing/extra/out-of-order files, path components, duplicate blocks, outer text, Python syntax errors, malformed `golden_master_outputs()` |
| `security` | `--generated-dir`, `--diagnostics-dir` | Checked Python files and violation list | Network imports/calls, subprocess, dynamic import/execution, write I/O, broad filesystem APIs, time/random/environment-dependent calculation paths, swallowed core exceptions |
| `conventions` | `--generated-dir`, optional `--allowlist <path>` | Import graph, layer edges, cache audit, circularity result | Any edge other than the allowed production graph, `commutation.py -> actuarial.py`, circular imports, function-local imports, `try/except ImportError`, `TYPE_CHECKING` tricks, unknown `lru_cache` hashability |
| `golden_master` | `--repo-root`, `--generated-dir`, `--info-dir`, `--diagnostics-dir` | Scalars tested/skipped, table cells tested, deviations, unmatched columns, computed output hash | Missing callable, wrong schema, runtime confinement failure, missing expected computed values, numeric/table deviations, zero-comparison acceptance when policy requires expectations |
| `algebraic` | `--generated-dir`, `--info-dir`, `--qa-contract`, `--strict` | Selected tiers, identities checked, examples/cases, counterexamples | Unknown applicability, missing function mappings, invalid conventions, property counterexamples, unavailable required test engine |
| `roundtrip` | `--repo-root`, `--generated-dir`, `--info-dir`, `--diagnostics-dir` | `tafeln.xml` canonical hash, re-extraction hash comparison, repeated-output hash comparison | XML parse/serialize mismatch, duplicate ages, invalid `qx`, material extraction hash drift, non-deterministic recomputation |
| `dossier` | `--repo-root`, `--generated-dir`, `--info-dir`, `--diagnostics-dir`, `--status` | `run_dossier.json` / `qa_report.json` paths and final mechanical acceptance status | Missing gate result, missing hashes, unapproved open assumptions, required gate not passed |

Local stdio MCP may later expose the same operations as typed tools, for example `python -m rechner_pipeline.toolbox.mcp_stdio`, but it must be a thin wrapper over the scripts and must not contain separate gate logic. HTTP/SSE MCP is explicitly out of scope. The recommended baseline remains plain scripts because they are transparent, CI-friendly, and portable across all four CLIs.

### 3.4 Pluggable input-adapter seam

The source seam is `InputAdapter -> InputBundle`. Every adapter emits the same filesystem bundle under `info_from_excel\`; downstream generation and QA consume the bundle, not the original document type. The formal schema is cross-referenced as §6.5.

Conceptual contract:

```python
InputBundle(
    contract_version="info_from_excel.v1",
    source_path=...,
    adapter_id="excel|word|...",
    out_dir=Path("info_from_excel"),
    manifest_path=Path("info_from_excel/export_manifest.json"),
    raw_sheet_csvs=[...],
    compressed_csvs=[...],
    names_manager_csv=... | None,
    source_texts=[...],              # compatibility: listed in manifest.vba_txts
    scalar_jsons=[...],
    table_value_csvs=[...],
    expectation_coverage="full|sparse|none",
    warnings=[...],
)
```

| Artifact | Mandatory for every successful bundle | Excel path | Notes |
|---|---:|---|---|
| `info_from_excel\export_manifest.json` | yes | unchanged current `ExportManifest` | Required fields remain `out_dir`, `sheet_csvs`, `vba_txts`, `names_manager_csv`, `replacements`, `llm_inputs`, `all_outputs`, `warnings`, `prompt_runs`, `output_hashes`. |
| Non-empty `manifest.llm_inputs` | yes | unchanged | Every listed path must exist. This is the source-neutral generation input list. |
| Raw CSV `<prefix>.csv` with `Blatt;Adresse;Formel;Wert` | adapter-dependent, but required when a grid or synthetic grid is emitted | yes, for every non-empty worksheet | Non-Excel adapters may use deterministic synthetic A1 anchors, but must preserve provenance. |
| Compressed CSV `<prefix>_compressed.csv` with the current 12-column schema | required when structured facts/rules are available; at least one preferred source representation must be present | unchanged: emitted when current Excel compression writes it | `Section=values` and `Section=formulas_unique_block` remain the portable semantic surface. Non-Excel must not invent fake Excel formulas. |
| `names_manager.csv` | no | unchanged: omitted when empty | Emit only for confidently extracted names/aliases. |
| Source logic text under `vba\*.txt` | required when source logic is not fully represented in CSV | unchanged VBA export | For Word/other, this is source text in the compatibility slot, not actual VBA. |
| `*_scalar.json` | optional by file shape; required for meaningful full golden-master acceptance | unchanged current scalar extraction | Missing/sparse expectations must produce strict warnings unless an explicit non-golden policy is selected. |
| `*_table_values.csv` | optional by file shape; required for meaningful full golden-master acceptance | unchanged current table extraction | Row order matters; headers are case-sensitive apart from the existing separator normalization in the harness. |
| `warnings[]` and `expectation_coverage` | yes | warnings unchanged; coverage may be inferred outside the byte-identical Excel manifest | `full`, `sparse`, or `none` must be explicit in the adapter result/dossier. |

`ExcelAdapter` is a zero-behavior-change wrapper around the current Excel extraction. It calls the existing `export_excel_infos()` with the selected backend and validates the returned manifest without rewriting, normalizing, or adding fields to Excel artifacts. This preserves the Excel path byte-for-byte where the current extractor is the source of truth.

`WordAdapter` and other future adapters may emit an Excel-shaped bundle: a pseudo-sheet CSV with deterministic anchors, a compressed CSV of facts and rule blocks, source logic text with original section/table/row references, and scalar/table expectations from worked examples or sidecar fixtures. The hard caveat is that specifications are not calculators. A Word tariff document may contain parameters, mortality tables, and formula prose, but usually lacks evaluated formula cells, complete model-point scenarios, rounding traces, and full expected output vectors. Sparse expectations therefore cannot honestly claim Excel-equivalent golden-master coverage. If coverage is `sparse` or `none`, the run must either fail fast/handoff or explicitly use a recorded algebraic/property/transcription gate policy; it must never silently run a zero-comparison golden master and call the result accepted.

### 3.5 Quality & reproducibility module

Reproducibility is redefined as reproducible objective acceptance, not reproducible agent thought or identical generated source. A run is accepted **iff** every required deterministic gate passes under recorded versions and hashes, no blocking manifest warning exists, and no unapproved open assumption remains. The agent may produce different source across attempts; the gate suite and dossier make the acceptance classification rerunnable.

| Gate | Required acceptance meaning |
|---|---|
| `G0.extraction-manifest` | `info_from_excel\export_manifest.json` exists, paths are present, hashes are recorded, strict warnings are resolved. |
| `G1.file-contract` | Exactly six generated files, exact order, no path components, no duplicates, no outer FILE-block text when applicable, Python compiles. |
| `G2.static-security` | Generated Python passes the reviewed static rules: no network, subprocess, dynamic execution/import, write I/O, unsafe filesystem APIs, random/time/environment-dependent calculation paths, or failure swallowing that hides wrong calculations. |
| `G3.architecture-conventions` | Only allowed production import direction involving the actuarial layers is `actuarial.py -> commutation.py`; no circular imports, local imports, `try/except ImportError`, `TYPE_CHECKING` tricks, or unknown `lru_cache` hashability. |
| `G4.runtime-confinement` | Any generated-code execution runs under filesystem confinement: read-only within the repo root, no writes, no outside reads. |
| `G5.golden-master` | `test_run.golden_master_outputs()` returns `{"scalars": ..., "tables": ...}` and matches all numeric workbook-derived `*_scalar.json` and `*_table_values.csv` expectations using the fixed harness semantics. |
| `G6.algebraic-properties` | Applicable actuarial identities, bounds, recursions, and product-specific equivalences pass under an explicit QA contract. Unknown applicability is a failure, not a skip. |
| `G7.roundtrips` | `tafeln.xml` parse/serialize/parse is canonical; re-extraction produces stable material hashes; repeated `golden_master_outputs()` in fresh processes is stable. |
| `G8.dossier-completeness` | `run_dossier.json` / `qa_report.json` records gate versions, commands, inputs, generated-file hashes, dependency versions, warnings, failures, and final mechanical status. |

Golden-master remains the primary hard value-regression gate because it compares generated results against cached Excel-observed artifacts: scalar JSONs and table CSVs. Its limit must be stated in every acceptance dossier: it only checks values observed/exported from the workbook; it can preserve workbook errors; it can miss wrong logic outside the workbook scenarios; and 4-decimal comparison can hide internal drift. Therefore golden-master is necessary but not sufficient.

Algebraic/property tests add Excel-independent pressure. They are tiered:

- Universal mortality/table invariants: `0 <= qx <= 1`, `p_x = 1 - q_x`, non-negative deaths, survival recursion, finite values, and explicit terminal-age policy.
- Universal commutation identities, when commutation is declared: `D_x = v^x·l_x`, `N_x = Σ_{k=x}^{ω} D_k`, `N_x = D_x + N_{x+1}`, and analogous `C_x`/`M_x` first-difference identities when present.
- Present-value identities under declared annual effective interest and timing conventions: `A_x + d·ä_x = 1`, `ä_x = (1 - A_x) / d`, `ä_x = 1 + v·p_x·ä_{x+1}`, `A_x = v·q_x + v·p_x·A_{x+1}`, and bounds such as `0 <= A_x <= 1`.
- Product-specific tests only when declared: net premium `P = PV benefits / PV premium annuity`, `PV(benefits) - P·PV(premiums) = 0` for net-premium products, scaling with sum insured where expenses/rounding are excluded, and reserve recursions only when reserves are in scope.

These tests are not mathematical proofs. They are falsification and regression gates over sampled or enumerated domains. If the generated code cannot declare the applicable convention, function mapping, product type, interest basis, or timing assumption, the algebraic gate must fail fast. It must not silently mark identities as inapplicable.

Roundtrips are also blocking: `tafeln.xml` must deserialize and reserialize to the same canonical semantic object and SHA-256; re-running extraction into a deterministic staging location must produce materially stable hashes; and repeated generated-core recomputation must produce the same canonical output hash. Material drift means failure.

Mechanically enforced conventions are part of reproducibility, not style. The gate suite must enforce exact six-file/order, static security, no circular imports, import direction `actuarial.py -> commutation.py` only, conservative `lru_cache` hashability, mandatory `golden_master_outputs()` shape, and no accepted run with missing strict warnings. If Hypothesis or another property engine is adopted, it must be installed only from corporate Artifactory, version/settings must be recorded, and unavailability must fail rather than downgrade to a weaker random loop.

Plain scripts are the reference implementation. A local stdio MCP wrapper may improve tool schemas for some CLIs, but it must call the same scripts and return the same JSON. HTTP/SSE MCP is prohibited. The dossier is the audit ledger: `accepted iff every required=true gate has status=passed and no blocking warning/open assumption remains`.

### 3.6 Per-CLI mapping table

The portable source of truth is one canonical skill/instruction body (§6.7) plus the plain Python toolbox. Per-CLI adapters install or reference that body using each CLI's verified mechanism; do not assume every CLI natively loads `SKILL.md`. (§6.1 is the AS-IS prompt and is **not** the TARGET body.)

| CLI | Skill / instruction file | Subagents | Custom commands | Local stdio MCP config | Project instruction file | Headless invocation |
|---|---|---|---|---|---|---|
| Claude CLI / Claude Code | Native Agent Skills: `.claude\skills\build-vergleichsrechenkern\SKILL.md` or `~\.claude\skills\...`; invoke `/build-vergleichsrechenkern`. | Built-in Explore/Plan/general-purpose plus custom `.claude\agents\`. | Custom commands are merged into skills; prefer the skill. | Local stdio MCP supported through Claude MCP configuration; command target is `python -m rechner_pipeline.toolbox.mcp_stdio`. Exact shared project-file convention: VERIFY. | `CLAUDE.md` plus skills; if common `AGENTS.md` is used, import/reference it from Claude instructions. | `claude -p "..."` / print mode; use appropriate permission/MCP flags per environment. |
| GitHub Copilot CLI | No verified native `SKILL.md`; install the procedure as `AGENTS.md` and/or `.github\copilot-instructions.md`, with optional custom agent/prompt when supported. | Custom agents are preview; exact config path and precedence: VERIFY. | Session slash commands exist; custom-command authoring beyond instructions/plugins: VERIFY. | MCP supported; configure a local stdio toolbox command `python -m rechner_pipeline.toolbox.mcp_stdio`. Exact project/user config path for current CLI: VERIFY. | `AGENTS.md`, `.github\copilot-instructions.md`. | `copilot -p "..."` with tool permissions such as `--allow-tool` / `--allow-all-tools` as policy permits. |
| Codex CLI | No verified native `SKILL.md`; use `AGENTS.md` plus custom prompt content that embeds/references §6.7. | Subagents available via `/codex/subagents`. | Custom prompts/slash-command authoring: VERIFY. | MCP supported via Codex config (for example a local stdio server command `python -m rechner_pipeline.toolbox.mcp_stdio`); exact stanza should be verified against installed Codex. | `AGENTS.md` and Codex configuration. | `codex exec "..."`; choose workspace-write/sandbox/approval flags explicitly. |
| OpenCode CLI | Use `.opencode\commands\build-vergleichsrechenkern.md` or `command` in `opencode.json`; include/reference the same §6.7 body. | Primary and subagents via `opencode.json` or Markdown; invoke with `@agent` when needed. | First-class custom commands in `.opencode\commands\*.md`; invoked `/build-vergleichsrechenkern`. | MCP supported in OpenCode config; use local stdio command `python -m rechner_pipeline.toolbox.mcp_stdio`; no remote MCP. | `AGENTS.md`, OpenCode config, and `opencode.json`. Include/reference the §6.7 body. | `opencode run "..."`; exact headless subcommand/options: VERIFY. |

---

## 4 Migration steps

### 4.1 Component disposition

| AS-IS module/file | Disposition: KEEP / REMOVE / MIGRATE / ADD | Notes |
|---|---|---|
| `src\rechner_pipeline\extract\__init__.py` | KEEP | Package marker only; keep if the Python package layout remains. |
| `src\rechner_pipeline\extract\excel.py` | MIGRATE | Preserve the Excel 1:1 artifact contract as `toolbox.extract` / `ExcelAdapter`; add clean-output or staged-output handling; keep `openpyxl`/COM selection fail-fast. |
| `src\rechner_pipeline\extract\openpyxl_backend.py` | MIGRATE | Keep as the portable default extraction backend; document cached-value semantics and preserve `$A$1` addresses. |
| `src\rechner_pipeline\extract\scalar_table.py` | MIGRATE | Keep expectation-file generation, but validate absolute address keys and fail on stale or incompatible value sources. |
| `src\rechner_pipeline\context\__init__.py` | KEEP | Package marker only if context package remains for compatibility. |
| `src\rechner_pipeline\context\prompt_builder.py` | REMOVE | Giant prompt stuffing and permissive placeholder replacement disappear. The CLI agent reads deterministic artifacts directly; any remaining templating must fail on unresolved placeholders. |
| `src\rechner_pipeline\generate\__init__.py` | REMOVE | Remove with SDK-backed generation package unless retained as an empty compatibility shim. |
| `src\rechner_pipeline\generate\client.py` | REMOVE | Remove SDK model calls, API-key loading, replay client, OpenAI/Anthropic branching, and provider-specific token/reasoning behavior. The external CLI agent is the model. |
| `src\rechner_pipeline\generate\output.py` | MIGRATE | Move/keep the exact six-file validator as `toolbox.validate`: exact names, exact order, no path components, no outer text when parsing FILE blocks, Python compile checks. |
| `prompts\v1\excel_to_py.txt` | MIGRATE | Convert the substantive rules into the canonical instruction/skill body: six files, layering, no external services, compressed CSV precedence, `golden_master_outputs()`, fail-fast behavior. |
| `prompts\v1\test_advanced.txt` | REMOVE | Legacy LLM-generated test harness is replaced by reviewed deterministic gates. |
| `src\rechner_pipeline\qa\__init__.py` | KEEP | Package marker for deterministic QA toolbox. |
| `src\rechner_pipeline\qa\security.py` | MIGRATE | Keep static security as a blocking script; extend for determinism (`random`, time, environment), broad exception swallowing, and generated-test self-approval. |
| `src\rechner_pipeline\qa\golden_master.py` | MIGRATE | Keep as the primary hard value gate, but fix unmatched-column success semantics and add coverage checks for zero-comparison runs. |
| `src\rechner_pipeline\qa\fs_confine.py` | KEEP | Keep runtime read confinement and write blocking around generated-code execution; do not treat AST security as a formal sandbox by itself. |
| `src\rechner_pipeline\qa\extraction_diff.py` | KEEP | Keep as an optional/required policy gate for backend equivalence, especially COM-vs-openpyxl extraction validation. |
| `src\rechner_pipeline\orchestrate\__init__.py` | KEEP | Package marker only if orchestration support code remains. |
| `src\rechner_pipeline\orchestrate\runner.py` | MIGRATE | Split deterministic responsibilities into toolbox commands and dossier writing. Remove SDK generation, prompt stuffing, `test_mode="llm"`, and skip paths from the accepted full-agentic flow. |
| `src\rechner_pipeline\orchestrate\agentic.py` | REMOVE | Remove LangGraph `StateGraph` orchestration. The CLI agent owns generation/repair; deterministic scripts own acceptance. |
| `src\rechner_pipeline\orchestrate\dossier.py` | MIGRATE | Preserve provenance, but extend to record complete options, CLI/tool identity where available, gate versions, hashes, commands, expectation coverage, and open assumptions. |
| `src\rechner_pipeline\orchestrate\wflog.py` | MIGRATE | Keep only if useful as deterministic operator logging; acceptance must rely on structured artifacts, not live logs. |
| `src\rechner_pipeline\models\__init__.py` | KEEP | Package marker. |
| `src\rechner_pipeline\models\manifest.py` | MIGRATE | Preserve current `ExportManifest` compatibility; add adapter/coverage metadata only where it does not break Excel byte identity, or version it explicitly. |
| `src\rechner_pipeline\cli.py` | MIGRATE | Replace provider/model/token/reasoning/test-LLM controls with deterministic toolbox and source-neutral options such as `--input`, `--adapter`, `--strict-manifest-warnings`, and explicit diagnostic overrides. |
| `pipeline.py` | MIGRATE | Keep as a backward-compatible wrapper only if it invokes the deterministic toolbox/full-agentic entrypoint without SDK generation. |
| `agentic_pipeline.py` | REMOVE | Remove or replace with a clear compatibility error/redirect; it currently names the LangGraph path that is no longer target architecture. |
| Dependency `openai` | REMOVE | No Python OpenAI SDK in the target; verify no runtime import or optional dependency remains. |
| Dependency `anthropic` | REMOVE | No Python Anthropic SDK in the target; verify no runtime import or optional dependency remains. |
| Dependency `langgraph` | REMOVE | No Python LangGraph orchestration in the target; verify no `StateGraph`/`langgraph` import remains. |
| ADD: canonical instruction/skill body | ADD | One source-of-truth instruction body. Install/adapt per CLI: Claude skill; Copilot/Codex via verified instruction/custom-agent mechanisms; OpenCode command/instructions. Use `VERIFY` for unconfirmed CLI-specific features. |
| ADD: deterministic toolbox CLI | ADD | Plain Python commands first: `extract`, `validate`, `golden_master`, and preferably `assurance all`. JSON stdout, human logs on stderr, stable exit codes, no network. |
| ADD: optional local stdio MCP wrapper | ADD | Thin wrapper over the same scripts only if useful. No HTTP/SSE MCP. Scripts remain the portability baseline. |
| ADD: algebraic/property tests | ADD | Add objective tests independent of Excel. If using Hypothesis, install only from approved corporate Artifactory, pin/record the version, and fail if unavailable. |
| ADD: roundtrip tests | ADD | `tafeln.xml` canonical parse/serialize, extraction/hash stability, generated-core recomputation stability. |
| ADD: architecture/convention checks | ADD | AST import graph, layer direction, no circular/function-local imports, no `try/except ImportError`, no `TYPE_CHECKING` tricks, conservative `lru_cache` hashability checks. |
| ADD: pluggable input-adapter seam | ADD | `InputAdapter -> info_from_excel.v1`. Excel adapter must wrap current extraction without mutating Excel artifacts; Word/other adapters must declare expectation coverage honestly. |
| ADD: dossier-completeness gate | ADD | Acceptance fails if required gate results, hashes, versions, coverage declarations, or open assumptions are missing. |

### 4.2 Ordered migration checklist

1. **Freeze a baseline on KLV.** Run the current extraction and fixed golden-master path before changing architecture. Verification: current tests pass and the KLV golden-master result is captured with manifest and generated-file hashes.
2. **Lock the Excel artifact contract.** Add/confirm regression coverage for raw CSVs, compressed CSVs, scalar/table expectations, `names_manager.csv`, VBA text, and `export_manifest.json`. Verification: ExcelAdapter output is byte-identical or explicitly diffed with approved differences.
3. **Introduce clean/staged extraction.** Prevent stale `_compressed.csv`, `_scalar.json`, and `_table_values.csv` reuse. Verification: inject a stale derived file, rerun extraction, and confirm it is removed or rejected.
4. **Create the toolbox command surface.** Implement `python -m rechner_pipeline.toolbox.extract`, `validate`, and `golden_master` as plain scripts with JSON stdout and non-zero blocking exits. Verification: each command succeeds on KLV and fails with structured JSON for a deliberate bad input.
5. **Migrate the six-file validator.** Reuse `generate.output` semantics in `toolbox.validate`; optionally parse FILE blocks for CLIs that emit text, but prefer direct file edits. Verification: missing file, wrong order, path component, outer text, and syntax-error fixtures all fail.
6. **Fix golden-master false acceptance.** Make unmatched expected columns fail and reject zero-comparison full-acceptance runs. Verification: a fixture with an unmatched expected column exits non-zero; KLV still passes.
7. **Extend deterministic QA gates.** Add security extensions, convention checks, algebraic/property tests, and roundtrips. Verification: intentional violations fail; KLV passes all applicable gates.
8. **Migrate prompt rules into instructions.** Convert `excel_to_py.txt` rules into the canonical skill/instruction body and thin per-CLI adapters. Verification: no unresolved `{{...}}` placeholders exist; the instruction body contains the six-file, layering, `golden_master_outputs()`, fail-fast, and no-external-service rules.
9. **Remove SDK generation.** Delete or disable `generate.client` and provider/model/token/reasoning CLI paths. Verification: `rg "anthropic|openai|OPENAI_API_KEY|ANTHROPIC_API_KEY" src pyproject.toml` finds no runtime dependency/import path intended for target execution.
10. **Remove LangGraph orchestration.** Delete or retire `orchestrate.agentic` and the `agentic_pipeline.py` path. Verification: `rg "langgraph|StateGraph|rechner-pipeline-agentic"` shows no active target orchestration dependency, or only compatibility documentation/errors.
11. **Migrate the user CLI.** Replace `--excel`-only language with source-neutral `--input`/`--adapter` while retaining `--excel` as a compatibility alias if required. Verification: `rechner-pipeline --help` no longer advertises SDK-provider acceptance paths and documents strict validation behavior.
12. **Add the input-adapter seam.** Implement `ExcelAdapter` as a zero-behavior wrapper and define Word/other adapters as future plugins with explicit coverage. Verification: Excel remains 1:1; a Word source without sidecar expectations produces `sparse`/`none` coverage and cannot be accepted as full golden equivalence.
13. **Upgrade the dossier.** Record gate suite versions, commands, all effective options, artifact hashes, expectation coverage, generated-file hashes, and open assumptions. Verification: a schema test fails when `export_backend`, gate results, or required hashes are omitted.
14. **Add optional local stdio MCP only after scripts work.** If added, expose only script-backed methods and no listener. Verification: config/code contains no HTTP/SSE MCP server and the same gates pass when invoked through scripts directly.
15. **Run final end-to-end acceptance.** Execute extraction, validation, static security, conventions, algebraic/property tests, roundtrips, golden master, and dossier completeness on KLV. Verification: every required gate passes; no unapproved open assumptions remain; removed dependencies do not import.

---

## 5 Risk register, open questions, explicit non-goals

### 5.1 Risk register

| Risk | Likelihood/Impact | Mitigation |
|---|---|---|
| Full-agentic generation is non-deterministic. The same CLI prompt may produce different source code across runs. | High / High | Define reproducibility as objective-gate reproducibility, not same generation path: content-addressed inputs, generated-file hashes, fixed gate versions, deterministic reruns, and acceptance only when all required gates pass. |
| Golden-master is necessary but not sufficient. It covers workbook-observed exported values only and can preserve workbook bugs. | High / High | Keep it as a hard gate, but add algebraic/property, roundtrip, security, convention, and dossier-completeness gates. Document that property tests find counterexamples; they are not proofs. |
| Word/other source inputs have sparse expectations. A Word tariff document is not a calculator and usually lacks executable formula grids, model points, recalculation, and complete expected outputs. | High / High | Add an input-adapter coverage field (`full`, `sparse`, `none`). Require sidecar/worked-example expected values for full golden validation; otherwise mark human-review or run only transcription/property gates honestly. |
| Per-CLI behavior diverges for skills, custom agents, custom commands, MCP configuration, permissions, and headless execution. | Medium / High | Use plain Python scripts as the lowest common denominator. Keep one canonical instruction body plus thin adapters. Residual `VERIFY`: exact Copilot CLI custom-agent/command authoring paths, exact Codex CLI custom-agent/command paths, and OpenCode `run` headless subcommand syntax. |
| Self-repair bounds are instruction-governed after removing LangGraph. | Medium / High | Encode max attempts in the instruction body and, where possible, in headless wrappers/CI scripts. Dossier the attempt count and fail to human review when exhausted. |
| `Report.ok` unmatched-column behavior can create false green runs. | Medium / High | Fix before relying on full-agentic acceptance; add regression tests for unmatched expected columns. |
| Stale extraction artifacts can pollute manifests and golden expectations. | Medium / High | Clean or stage output directories, hash all inputs/outputs, and fail on unexpected files. |
| `$A$1` address assumptions can be broken by backend or adapter changes. | Medium / High | Canonicalize addresses before scalar/table extraction and validate the bundle schema. |
| Cached openpyxl values may not match a live recalculation. | Medium / High | Require workbooks to be calculated/saved for openpyxl baseline; use explicit COM backend/diff only where approved and available. |
| Algebraic identities are convention-dependent. Applying the wrong identity is worse than skipping it. | Medium / High | Require a generated/reviewed QA contract for product conventions and function mappings. Unknown applicability fails fast; no silent skip. |
| New QA dependencies may be unavailable or unapproved. | Medium / Medium | Use corporate Artifactory only. Pin and record versions. If Hypothesis or document parsers are unavailable, fail the relevant gate rather than silently downgrading. |
| AST static security is not a formal sandbox. | Medium / High | Keep static scan, runtime `fs_confine`, subprocess isolation, and fail-fast blocking; do not rely on generated code to police itself. |
| Dossier schema drift can weaken auditability. | Medium / Medium | Make dossier completeness a blocking gate and schema-test required fields, including gate versions, commands, hashes, coverage, and open assumptions. |
| Optional local stdio MCP can become a second implementation path. | Low / Medium | Scripts first; MCP, if any, is a thin local stdio wrapper. No HTTP/SSE MCP and no separate logic. |

### 5.2 Open questions / residual VERIFY items

- VERIFY exact Copilot CLI custom-agent and custom-command authoring paths and precedence before documenting them as supported.
- VERIFY exact Codex CLI custom-agent/custom-command authoring paths in the installed version.
- VERIFY OpenCode headless `run` syntax and locked-down unattended permissions in the target environment.
- VERIFY whether existing consumers require diagnostics under `generated\` before moving detailed run artifacts to `runs\<run-id>\` or `.rechner-pipeline\runs\<run-id>\`.
- Decide whether a headless wrapper, CI job, or CLI-specific mechanism will enforce max attempts in addition to instruction text.
- Decide the sidecar expectation format for non-Excel adapters.
- Decide which optional dependencies (`hypothesis`, `python-docx` or OOXML parser, MCP package if any) are approved in corporate Artifactory and record pinned versions.
- Decide whether COM recalculation remains a supported backend or only a validation/diff tool on approved Windows+Excel hosts.

**Resolved in this document (no longer open):**

- ✅ The versioned schema for the upgraded dossier and input-bundle coverage metadata is now specified in §6.8 (`run_dossier.json` v2 delta §6.8.4, `qa_report.json` §6.8.3, InputBundle coverage block §6.8.5).
- ✅ The canonical TARGET instruction/SKILL body — including the tool loop, gate commands, bounded-repair convention, fail-fast behavior, the complete allowed-import graph, and the retired placeholder allowance — is now reproduced install-neutrally in §6.7; per-CLI adapters in §3.6 reference it (not the AS-IS §6.1 prompt).
- ✅ The TARGET acceptance/toolbox result, gate-result ledger, and `qa_contract.json` formats are specified in §6.8.1–§6.8.6, including the `--qa-contract` shape consumed by the algebraic gate.

### 5.3 Explicit non-goals

- Not building the implementation in this document section.
- Not supporting HTTP/SSE-based MCP servers.
- Not changing the Excel 1:1 output contract for `info_from_excel\` or the six generated deliverables.
- Not preserving Python-hosted `openai`, `anthropic`, or `langgraph` generation/orchestration in the target path.
- Not guaranteeing identical generated source code across Claude, Copilot, Codex, and OpenCode; only objective gate pass/fail is reproducible.
- Not claiming Word or other non-Excel inputs have Excel-equivalent golden-master validation without complete sidecar/worked-example expectations.
- Not installing new software or dependencies from unapproved sources.
- Not silently falling back to weaker validation when a required gate, dependency, adapter, or expectation set is unavailable.

---

## 6 Appendices

### 6.1 Verbatim prompt: excel_to_py.txt

Source: `prompts\v1\excel_to_py.txt`.

````text
---

## **Rolle**

Du bist **Senior-Aktuarsentwickler und Python-Engineer**.
Ziel ist die **deterministische 1:1-Migration eines Excel-Tarifrechners (Formeln + VBA)** in ein **reines Python-Paket ohne Excel**.

---

## **Nicht verhandelbar (absolut strikt)**

### **A. Grundregeln**

* **KEIN Erraten von Excel-Zelladressen**
* Stattdessen: **saubere, parametrisierte API**

  * Vertrags-Inputs
  * Tarifparameter
  * Sterbetafeln
* **Deterministischer Code**

  * keine externen Services
  * keine Excel-Abhängigkeiten

---

### **B. Output (hart validiert)**

* **GENAU 6 Dateien**, keine Abweichung
* **GENAU diese Reihenfolge**:

1. `inputs.py`
2. `params.py`
3. `tafeln.xml`
4. `commutation.py`
5. `actuarial.py`
6. `test_run.py`

* Jede Datei **muss exakt so gekapselt sein**:

```
===FILE_START: <DATEINAME>===
<DATEIINHALT>
===FILE_END: <DATEINAME>===
```

* **Kein Text außerhalb dieser 6 Blöcke**

---

### **C. Architektur (kritisch – Fehler hier ist fatal)**

#### **Import-Regeln (keine Ausnahmen)**

* `commutation.py` **DARF NICHT** `actuarial.py` importieren
* `actuarial.py` **DARF** `commutation.py` importieren

Erlaubte Richtung **ausschließlich**:

```
actuarial.py → commutation.py
```

#### **Layer-Definition**

* **commutation.py**

  * Sterbetafel-Zugriff
  * Kommutationswerte
  * technische / mathematische Utility-Funktionen
  * **keine** Tarif- oder Produktlogik

* **actuarial.py**

  * Barwerte
  * Tarif- / Produktlogik
  * aktuarielle Zielgrößen

#### **Utility-Funktionen**

* Gemeinsame Funktionen (z.B. `excel_round`)

  * müssen in einem **niedrigeren Layer** liegen
    (`commutation.py` oder `params.py`)
* **Verboten**:

  * Utility in `actuarial.py` definieren
  * und von `commutation.py` importieren

#### **Explizit verboten**

* Circular Imports
* Imports innerhalb von Funktionen
* `try/except ImportError`
* `TYPE_CHECKING`-Tricks

---

### **D. Caching**

* `lru_cache` erlaubt **nur**, wenn:

  * alle Argumente **streng hashbar**
  * **keine** dict/list/set
  * **keine** Dataclasses mit solchen Feldern
* Alternativ:

  * String-IDs oder
  * explizites Identitäts-Hashing (`eq=False`, `__hash__`)

---

## **Input-Quellen (nur lesen)**

* CSV-Sheet-Exporte (`Blatt`, `Adresse`, `Formel`, `Wert`)
* `*_compressed.csv` (falls vorhanden)

  * `Section=values`
  * `Section=formulas_unique_block`
* **Wenn `*_compressed.csv` existiert → NUR dieses verwenden**
* `names_manager.csv` (falls vorhanden)
* VBA-Module (`.txt`)

---

## **Arbeitsauftrag**

### **1. Analyse**

Identifiziere aus den Inputs:

* Vertrags-Inputs
* Tarifparameter
* relevante Formeln:

  * Barwerte
  * Kommutationswerte
  * aktuarielle Zielgrößen

---

### **2. Implementierung**

* **Jede Barwert- / Kommutations- / Aktuar-Formel = eigene Funktion**
* Namen möglichst nah an Labels / Bezeichnern aus den Inputs
* Deterministisch, ohne Seiteneffekte

---

### **3. Sterbetafeln**

* Serialisiere `qx` in `tafeln.xml`
* Wenn keine Tafeln erkennbar:

  * klare Platzhalter
  * **explizit `NotImplementedError` mit Message**

---

### **4. Test**

* `test_run.py`:

  * minimales Dummy-Beispiel
  * führt Hauptpfade aus
  * zeigt deterministisches Verhalten
  * bei fehlenden Tafeln: sauberes Scheitern

* **Pflicht-Schnittstelle (Golden-Master-Contract):** `test_run.py` **muss**
  zusätzlich folgende Funktion exponieren — ein **fester, externer**
  Validierungs-Harness ruft sie auf:

  ```python
  def golden_master_outputs() -> dict:
      """Berechnete Werte für den Golden-Master-Vergleich.
      Namen IDENTISCH zu den Erwartungsdateien (siehe INPUT_FILES:
      *_scalar.json-Schlüssel und *_table_values.csv-Spaltenköpfe)."""
      return {
          "scalars": {"<prefix>": {"<name>": <float>, ...}},
          "tables":  {"<prefix>": [ {"<spalte>": <float>, ...}, ... ]},
      }
  ```

  * `<prefix>` = Dateiname-Präfix der Erwartungsdateien (z. B. `Kalkulation`).
  * `scalars`: je `<prefix>_scalar.json` ein Dict {Skalarname → berechneter Wert}.
  * **Vollständigkeit (kritisch):** `scalars[<prefix>]` MUSS **jeden** als
    Einzelwert benannten Skalar enthalten (jedes Label mit `Anzahl_Zellen = 1`
    in der komprimierten CSV bzw. jeder Skalar-Name im Name-Manager) — **auch
    abgeleitete Raten/Parameter** (z. B. `ratzu`), **nicht nur** die
    aktuariellen Zielgrößen. Ein fehlender erwarteter Skalar lässt die
    Golden-Master-Validierung fehlschlagen.
  * `tables`: je `<prefix>_table_values.csv` eine Liste von Zeilen-Dicts in
    Zeilenreihenfolge; Schlüssel = Spaltenköpfe (case-sensitiv; Trennzeichen-
    Varianten wie `A_xn`/`Axn` erlaubt, Groß-/Kleinschreibung NICHT glätten).
  * Die Werte stammen aus **derselben** Berechnung wie der übrige `test_run.py`.

---

## **PIPELINE_META**

(nur Information, **nicht ausgeben**)
`{{PIPELINE_META}}`

---

## **INPUT_FILES**

(nur lesen, **nicht ausgeben**)
`{{INPUT_FILES}}`

---

## **OUTPUT**

Gib **JETZT NUR** die **6 Datei-Blöcke** aus
– in der **exakt vorgegebenen Reihenfolge**,
– mit **exakt korrekten Dateinamen**,
– **ohne jeglichen Zusatztext**.

---

````

### 6.2 Verbatim prompt: test_advanced.txt

Source: `prompts\v1\test_advanced.txt`.

````text
---

## Kontext

Ich arbeite an der Migration eines Excel-basierten Tarifrechners (inkl. VBA-Logik) nach Python.

In meinem Workflow werden automatisch folgende Artefakte erzeugt:

* ein Python-Testskript (`test_run.py`), das eine Tarifberechnung ausführt und Ergebnisse per `print` ausgibt
* eine oder mehrere CSV-Dateien (`*_table_values.csv`) mit vollständigen Erwartungswerten  (z. B. aus Excel exportiert)
* eine oder mehrere JSON-Dateien (`*_scalar.json`) mit einzelnen Erwartungswerten  (Skalare)
* mehrere Python-Module mit der eigentlichen Rechenlogik

---

## Aufgabe

Erstelle ein neues Python-Skript **`test_run_advanced.py`**, das als vollständiger Regressionstest für diesen Workflow dient.

---

## Allgemeines Ziel

Das Skript soll:

* dieselbe Berechnung ausführen wie `test_run.py`
* alle verfügbaren Ergebnisse vollständig testen (nicht nur Stichproben)
* die Resultate mit den automatisch erzeugten CSV- und JSON-Erwartungswerten vergleichen

---

## Verzeichnisstruktur (fest vorgegeben)

* Dieses neue Skript heißt: `test_run_advanced.py`
* Es liegt im Ordner: `generated/`
* Alle CSV- und JSON-Dateien liegen im Ordner: `info_from_excel/`
* Alle Python-Dateien (`actuarial.py`, `commutation.py`, `inputs.py`, `params.py`, `test_run.py`) liegen gemeinsam im Ordner: `generated/`

---

## 1. Skalare (JSON)

* Vergleiche alle numerischen Erwartungswerte
* Vergleich: Rundung auf 4 Nachkommastellen
* Ausgabe: berechnet / erwartet / PASS–FAIL

---

## 2. Matrix / Verlauf (CSV)

* CSV enthält eine vollständige Ergebnismatrix
* Die Berechnung liefert eine entsprechende Liste von Dictionaries

### Regeln für Zuordnung

* Feld- und Spaltennamen sind **case-sensitiv**
* Namen, die sich nur durch Groß-/Kleinschreibung unterscheiden, sind **semantisch verschieden** (z. B. `Axn` ≠ `axn`)
* Die Zuordnung darf Namensvarianten berücksichtigen (z. B. unterschiedliche Schreibweisen/Trennzeichen wie `Axn` vs. `A_xn`), **sofern dabei die Groß-/Kleinschreibung nicht “glattgezogen” wird** und keine semantisch verschiedenen Größen vermischt werden.

---

## 3. Vergleich

* Numerischer Vergleich über `round(value, 4)`
* Abweichungen müssen eindeutig (Index + Feldname) identifizierbar sein

---

## 4. Reporting

Ausgabe:

* getestete Skalare
* vollständige Matrixvergleiche
* Summary (Tests, Abweichungen, nicht zuordenbare Felder)

---

## Ziel

Robuster Regressionstest für die Excel → Python Migration.

---

--- 
## PIPELINE_META
{{PIPELINE_META}}

## INPUT_FILES
{{INPUT_FILES}}
---

## Output-Format (zwingend einzuhalten)

Der erzeugte Code MUSS exakt in folgendem Blockformat ausgegeben werden, damit er automatisch extrahiert werden kann:

```
===FILE_START: test_run_advanced.py===
<DATEIINHALT>
===FILE_END: test_run_advanced.py===
```

Bitte gib **nur diesen Codeblock** aus, ohne zusätzliche Erklärungen.

---
````

### 6.3 FILE-block grammar

Authoritative source: `src\rechner_pipeline\generate\output.py`.

Exact regex:

```python
PATTERN = re.compile(
    r"^===FILE_START:[ \t]*(?P<name>[^=\r\n]+?)[ \t]*===[ \t]*(?:\r?\n)"
    r"(?P<content>.*?)"
    r"^===FILE_END:[ \t]*(?P=name)[ \t]*===[ \t]*(?:\r?\n)?",
    re.DOTALL | re.MULTILINE,
)
```

Expected main output files, including exact order:

```python
EXPECTED_MAIN_OUTPUT_FILES = (
    "inputs.py",
    "params.py",
    "tafeln.xml",
    "commutation.py",
    "actuarial.py",
    "test_run.py",
)
```

Validation rules implemented by `validate_main_output_files(text)`:

| Rule | Source behavior |
|---|---|
| No outer text | `_validate_no_outer_text()` allows only whitespace outside matched `FILE_START` / `FILE_END` blocks; any non-whitespace prefix, infix, or suffix raises `OutputValidationError`. |
| At least one block | `_validate_main_output_names()` raises if no files are extracted. |
| No path components | Every extracted `name` is stripped, and then rejected if `Path(name).name != name`, or if it contains `/` or `\`. |
| No duplicates | Repeated file names are collected and rejected. |
| Exact file set | The actual set must equal `EXPECTED_MAIN_OUTPUT_FILES`: missing files and unexpected files are both errors. |
| Exact order | The extracted names must equal `list(EXPECTED_MAIN_OUTPUT_FILES)`. |
| Must compile | Every expected Python output file (`*.py`) is compiled with `compile(content, filename, "exec")`; any `SyntaxError` raises `OutputValidationError`. `tafeln.xml` is not compiled. |

`extract_files_from_text()` returns `(name, content)` pairs with the block content unchanged and with only the file name stripped.

### 6.4 Manifest & dossier JSON schemas

Authoritative sources: `src\rechner_pipeline\models\manifest.py` and `src\rechner_pipeline\orchestrate\dossier.py`. All serialized paths are strings. Hashes are SHA-256 hex strings.

**`ExportManifest.to_dict()` top-level fields**

| JSON key | Type | Required on write | Semantics |
|---|---:|---:|---|
| `out_dir` | string | yes | Output directory path. `from_dict()` requires this key. |
| `sheet_csvs` | array[string] | yes | Raw per-sheet CSV paths. |
| `vba_txts` | array[string] | yes | Exported VBA/source text paths. |
| `names_manager_csv` | string | yes | Path string, or `""` when no names manager file exists. |
| `replacements` | object[string,string] | yes | Raw CSV path to compressed CSV path mapping. |
| `llm_inputs` | array[string] | yes | Files stuffed into the main prompt. |
| `all_outputs` | array[string] | yes | Declared extraction/pipeline output paths. |
| `warnings` | array[`ManifestWarning`] | yes | Manifest warnings. |
| `prompt_runs` | array[`PromptRecord`] | yes | Prompt provenance records; `with_prompt_record()` replaces records with the same `stage`. |
| `output_hashes` | array[`FileHashRecord`] | yes | Existing file hashes from `with_output_hashes()`. |

**`ManifestWarning` fields**

| JSON key | Type | Required on write | Semantics |
|---|---:|---:|---|
| `code` | string | yes | Warning code. |
| `stage` | string | yes | Producing stage. |
| `message` | string | yes | Human-readable warning. |
| `strict_error` | boolean | yes | Whether strict warning enforcement should fail the run. |
| `path` | string | omitted if empty | Optional affected path. |
| `details` | object | omitted if empty or null | Optional structured details. |

`ExportManifest.with_warnings()` deduplicates by `(code, stage, path, message)`. `strict_error_warnings()` returns only warnings where `strict_error` is true.

**`PromptInputRecord` fields**

| JSON key | Type | Required | Semantics |
|---|---:|---:|---|
| `path` | string | yes | Input file path. |
| `label` | string | yes | Prompt label. |
| `original_chars` | integer | yes | Full source text length. |
| `included_chars` | integer | yes | Characters included in the prompt. |
| `original_sha256` | string | yes | SHA-256 of full source text. |
| `truncated` | boolean | yes | Whether per-file truncation occurred. |

**`PromptRecord` fields**

| JSON key | Type | Required on write | Semantics |
|---|---:|---:|---|
| `stage` | string | yes | Prompt stage. |
| `template_path` | string | yes | Prompt template path. |
| `debug_prompt_path` | string | yes | Written debug prompt path. |
| `prompt_chars` | integer | yes | Final prompt length. |
| `prompt_sha256` | string | yes | Final prompt SHA-256. |
| `input_files` | array[`PromptInputRecord`] | yes | Stuffed input metadata. |
| `total_limit_reached` | boolean | yes | Whether total prompt limit stopped input assembly. |
| `output_chars` | integer | omitted if null | Raw model output length. |
| `output_sha256` | string | omitted if empty | Raw model output SHA-256. |

**`FileHashRecord` fields used by `ExportManifest.output_hashes`**

| JSON key | Type | Required | Semantics |
|---|---:|---:|---|
| `path` | string | yes | File path. |
| `bytes` | integer | yes | `path.stat().st_size`. |
| `sha256` | string | yes | File SHA-256. |

`ExportManifest.with_output_hashes(paths)` skips duplicate path strings, missing paths, and non-files.

**`run_dossier.json` structure**

`write_run_dossier()` writes UTF-8 JSON with `ensure_ascii=False` and `indent=2` to `generated\run_dossier.json` unless the runner provides another `run_dossier_path`.

| JSON path | Type | Meaning |
|---|---:|---|
| `schema_version` | integer | Always `1`. |
| `created_at` | string | UTC ISO timestamp. |
| `run.status` | string | Caller-supplied run status. |
| `run.human_review_required` | boolean | Caller-supplied human-review flag. |
| `run.repo_root` | string | Runner repo root. |
| `run.excel_path` | string | Runner Excel input path. |
| `run.options` | object | Present option keys only from `_options_dict()`: `model`, `skip_export`, `skip_main_llm`, `skip_test_llm`, `skip_compare_run`, `main_max_chars_per_file`, `main_max_total_chars`, `test_max_chars_per_file`, `test_max_total_chars`, `reasoning_effort`, `strict_manifest_warnings`. |
| `artifacts.run_dossier` | string | Dossier path. |
| `artifacts.manifest` | `PathRecord` | Manifest path record. |
| `artifacts.static_security_report` | `PathRecord` | Static security report path record. |
| `artifacts.compare_result` | `PathRecord` | Compare result path record. |
| `artifacts.agentic_diagnostics` | `PathRecord` | Agentic diagnostics path record. |
| `artifacts.agentic_repair_artifacts` | object | Copy of `agentic_state.repair_artifacts`. |
| `manifest.path` | string | Manifest path. |
| `manifest.exists` | boolean | Whether a manifest was loaded. |
| `manifest.out_dir` | string | Present when manifest exists. |
| `manifest.sheet_csv_count` | integer | Count of `manifest.sheet_csvs`. |
| `manifest.vba_txt_count` | integer | Count of `manifest.vba_txts`. |
| `manifest.names_manager_csv` | string | Path or empty string. |
| `manifest.llm_input_count` | integer | Count of `manifest.llm_inputs`. |
| `manifest.all_output_count` | integer | Count of `manifest.all_outputs`. |
| `manifest.warning_count` | integer | Count of `manifest.warnings`. |
| `manifest.prompt_run_count` | integer | Count of `manifest.prompt_runs`. |
| `manifest.output_hash_count` | integer | Count of `manifest.output_hashes`. |
| `prompt_hashes[]` | array[object] | One per prompt record: `stage`, `template_path`, `debug_prompt_path`, `prompt_chars`, `prompt_sha256`, `output_chars`, `output_sha256`, `input_file_count`, `total_limit_reached`, `truncated_input_files`. |
| `outputs.all_outputs` | array[string] | Manifest output paths, or empty when manifest is missing. |
| `outputs.output_hashes` | array[`FileHashRecord`] | Manifest output hashes, or empty when manifest is missing. |
| `generated_files[]` | array[`PathRecord`] | Files under `generated\`, sorted, excluding `run_dossier.json`. |
| `test_summary.status` | string | `not_run` if compare result is absent; otherwise payload `status` or `unknown`. |
| `test_summary.result_path` | string | Compare result path. |
| `test_summary.returncode` | integer or null | From compare payload. |
| `test_summary.test_file` | string | From compare payload, default `""`. |
| `test_summary.command` | array | From compare payload, default `[]`. |
| `test_summary.cwd` | string | From compare payload, default `""`. |
| `test_summary.stdout_excerpt` | string | Present if compare payload has `stdout`, capped at 4000 characters plus `\n... <truncated>`. |
| `test_summary.stderr_excerpt` | string | Present if compare payload has `stderr`, capped at 4000 characters plus `\n... <truncated>`. |
| `test_summary.read_error` | string | Present if compare JSON could not be read. |
| `warnings[]` | array[`ManifestWarning`] | Serialized manifest warnings. |
| `open_assumptions[]` | array[object] | Open assumptions emitted by `_open_assumptions()`. |

`PathRecord` is `{ "path": string, "exists": boolean }`, plus `bytes` and `sha256` when the path exists and is a file.

**`open_assumptions[]` possible entries**

| `code` | Additional keys | Condition |
|---|---|---|
| `pipeline.skip_export` | `message` | `skip_export` true. |
| `pipeline.skip_main_llm` | `message` | `skip_main_llm` true. |
| `pipeline.skip_test_llm` | `message` | `skip_test_llm` true. |
| `pipeline.skip_compare_run` | `message` | `skip_compare_run` true. |
| `manifest.missing` | `message` | No manifest available. |
| `manifest_warning.<warning.code>` | `message`, `stage`, `path`, `strict_error` | For each manifest warning. |
| `prompt.output_hash_missing` | `message`, `stage` | A prompt record has no `output_sha256`. |
| `compare.result_missing` | `message` | Compare result missing and compare was not explicitly skipped. |
| `compare.failed` | `message`, `returncode` | Compare result status is `failed`. |
| `security_report.missing` | `message` | Generated Python exists but static security report is absent. |
| `human_review.required` | `message` | Human-review flag is true. |

### 6.5 InputBundle schema

Derived from `files\brainstorm\B3.md`. The bundle contract is source-neutral but intentionally `info_from_excel`-shaped so existing downstream consumers can continue reading the same files.

| Artifact | Mandatory/optional | Schema |
|---|---|---|
| Bundle metadata | Mandatory | `contract_version = "info_from_excel.v1"`, `source_path`, `adapter_id`, `out_dir`, `manifest_path`. |
| `info_from_excel\export_manifest.json` | Mandatory | Current `ExportManifest` schema from §6.4. For byte-identical Excel output, do not add adapter-only metadata. |
| `manifest.llm_inputs` | Mandatory and non-empty | Array of existing paths. This is the authoritative main-prompt input list. |
| Raw source CSV `<prefix>.csv` | Strongly recommended for every successful bundle; mandatory for every non-empty Excel sheet | UTF-8 semicolon CSV with exact columns `Blatt;Adresse;Formel;Wert`. For non-Excel, use deterministic A1-like anchors and preserve provenance. |
| Compressed CSV `<prefix>_compressed.csv` | Required when the adapter has structured facts/rules; Excel emits it when current compression writes it | UTF-8 semicolon CSV with exact columns `Section;Blatt;Adresse;Formel;Wert;Anzahl_Zellen;Normalisierte_Formel_R1C1;Label_Adresse;Label_Wert;Label_Formel;Label_Source;LLM_Hint`. Allowed `Section` values are `values` and `formulas_unique_block`. |
| `names_manager.csv` | Optional; Excel emits only if names exist | UTF-8 semicolon CSV with exact header `Name;Scope;Visible;RefersTo;RefersToLocal;RefersToRangeAddress;ValueEvaluated;Comment`. Non-Excel adapters should emit it only for confidently extracted aliases/names. |
| Source logic text files | Conditional: required if source contains logic not fully represented in compressed CSV | UTF-8 deterministic text files, currently listed through the compatibility slot `manifest.vba_txts` and included in `llm_inputs`. For Word/other sources these are source text, not actual VBA. |
| `*_scalar.json` | Optional by file-system contract; required for a meaningful fixed golden run when scalar expectations exist | UTF-8 JSON object mapping label text to values. Numeric values are compared by the golden harness; `null`, blank, or non-numeric values are skipped. |
| `*_table_values.csv` | Optional by file-system contract; required for a meaningful fixed golden run when table expectations exist | UTF-8 comma-delimited CSV. Header row is expected column names; row order matters; numeric cells are compared rounded to 4 decimals; blank/non-numeric cells are skipped. |
| `expectation_coverage` | Mandatory bundle metadata | Literal `full`, `sparse`, or `none`. Must be explicit so zero-comparison runs cannot look like successful validation. |
| `warnings[]` | Mandatory, may be empty | `ManifestWarning` schema from §6.4. Use strict warnings for context loss, expectation gaps, ambiguous table normalization, or missing source logic. |

Validation expectations from B3: `out_dir` exists; manifest loads with `ExportManifest.from_dict()`; every manifest path exists except optional empty `names_manager_csv`; compressed CSVs have the exact header; scalar/table expectation files have the minimal schema; expectation coverage is explicit.

### 6.6 Example info_from_excel/ output formats

Repository search found a real `names_manager.csv` fixture at `tests\fixtures\golden_master_com\names_manager.csv`. No real `*_compressed.csv`, `*_scalar.json`, or `*_table_values.csv` files were present in the searched repo tree, so those three examples are illustrative excerpts reused from the verified `as-is-extraction.md` examples.

**Illustrative `Kalkulation_compressed.csv` excerpt**

```csv
Section;Blatt;Adresse;Formel;Wert;Anzahl_Zellen;Normalisierte_Formel_R1C1;Label_Adresse;Label_Wert;Label_Formel;Label_Source;LLM_Hint
values;Kalkulation;$J$6;BJB;BJB;;;;;;;
formulas_unique_block;Kalkulation;K6;=VS*K5;;1;=VS*R[-1]C[0];$J$6;BJB;BJB;left;Label(left:$J$6)=BJB | Formula==VS*K5 | Pattern==VS*R[-1]C[0]
formulas_unique_block;Kalkulation;B16:B66;=IF(A16<=n,act_nGrAx(x+$A16,MAX(0,n-$A16),Sex,Tafel,Zins)+Act_Dx(x+n,Sex,Tafel,Zins)/Act_Dx(x+$A16,Sex,Tafel,Zins),0);;51;=IF(R[0]C[-1]<=N,ACT_NGRAX(X+R[0]C1,MAX(0,N-R[0]C1),SEX,TAFEL,ZINS)+ACT_DX(X+N,SEX,TAFEL,ZINS)/ACT_DX(X+R[0]C1,SEX,TAFEL,ZINS),0);$B$15;Axn;Axn;above;Label(above:$B$15)=Axn | Formula==IF(A16<=n,act_nGrAx(x+$A16,MAX(0,n-$A16),Sex,Tafel,Zins)+Act_Dx(x+n,Sex,Tafel,Zins)/Act_Dx(x+$A16,Sex,Tafel,Zins),0) | Pattern==IF(R[0]C[-1]<=N,ACT_NGRAX(X+R[0]C1,MAX(0,N-R[0]C1),SEX,TAFEL,ZINS)+ACT_DX(X+N,SEX,TAFEL,ZINS)/ACT_DX(X+R[0]C1,SEX,TAFEL,ZINS),0)
```

**Illustrative `Kalkulation_scalar.json` excerpt**

```json
{
  "Bxt": 0.044656547026924,
  "BJB": 4465.6547,
  "BZB": 392.8448,
  "Pxt": 0.042392046400377824,
  "ratzu": 0.05
}
```

**Illustrative `Kalkulation_table_values.csv` excerpt**

```csv
k,Axn,axn,axt,kVx_bpfl,kDRx_bpfl,kVx_bfr,kVx_MRV,flex. Phase,StoAb,RKW,VS_bfr
0.0,0.6508353435792427,20.30143073760709,15.879479153587287,-0.022328273513462005,-2232.8274,0.7015889204232604,0.0,0.0,150.0,0.0,0.0
1.0,0.6608343830624348,19.720058013370043,15.202199054900165,0.016737691921828737,1673.7692,0.7101345280958599,3478.5757,0.0,150.0,3328.5757,4898.4743
```

**Real `names_manager.csv` fixture excerpt**

Source: `tests\fixtures\golden_master_com\names_manager.csv`.

```csv
Name;Scope;Visible;RefersTo;RefersToLocal;RefersToRangeAddress;ValueEvaluated;Comment
_xleta.MAX;Worksheet:Tarifrechner_KLV.xlsm;False;=#NAME?;=#NAME?;;-2146826273;
_xlfn.IFERROR;Worksheet:Tarifrechner_KLV.xlsm;False;=#NAME?;=#NAME?;;-2146826259;
alpha;Worksheet:Tarifrechner_KLV.xlsm;True;=Kalkulation!$E$6;=Kalkulation!$E$6;$E$6;0.025;
B_xt;Worksheet:Tarifrechner_KLV.xlsm;True;=Kalkulation!$K$5;=Kalkulation!$K$5;$K$5;0.044656547026924;
beta1;Worksheet:Tarifrechner_KLV.xlsm;True;=Kalkulation!$E$7;=Kalkulation!$E$7;$E$7;0.025;
```

### 6.7 Canonical TARGET instruction / SKILL body (install-neutral)

This appendix is the **single source of truth for the TARGET full-agentic generation
instructions**. It is the body that every per-CLI adapter installs or references (§3.1,
§3.2, §3.6). It is **install-neutral**: it contains no SDK call, no API key, no LangGraph
node, and no CLI-specific front-matter. Each CLI wraps it with its own delivery mechanism
(Claude `SKILL.md`, OpenCode command, Copilot/Codex `AGENTS.md`/custom prompt) but the
behavioral contract below does not change.

It supersedes the AS-IS prompt in §6.1 for the TARGET path. §6.1/§6.2 remain reproduced
**only** as AS-IS reference. Where §6.1 and this body conflict, this body wins for the
TARGET; the most important deliberate divergence is the **retired placeholder allowance**
(see *Mortality tables* below).

#### Role and goal

Senior actuarial developer and Python engineer. Perform a deterministic **1:1 migration**
of the Excel formulas, defined names, and VBA/source logic of a Tarifrechner into a pure
Python *Vergleichsrechenkern* of exactly six files, **without any Excel runtime**, without
network, without subprocess, and without hidden state. The CLI agent **is** the model: it
plans, generates/edits files, runs the deterministic toolbox, reads the JSON diagnostics,
and repairs — all inside one CLI session.

#### Trigger

Activate on `build-vergleichsrechenkern`, `build a Vergleichsrechenkern`,
`Vergleichsrechenkern erstellen`, `Excel/VBA Tarifrechner nach Python migrieren`,
`build a comparison kernel`, or any explicit request to generate `inputs.py`, `params.py`,
`tafeln.xml`, `commutation.py`, `actuarial.py`, `test_run.py` from a workbook or future
source bundle.

#### Read-only input sources

Read only the artifacts the extraction toolbox produced under the bundle directory
(default `info_from_excel\`); never read the original `.xlsm`/`.docx` directly and never
write into the bundle:

- raw sheet CSVs `<prefix>.csv` (`Blatt;Adresse;Formel;Wert`),
- compressed CSVs `<prefix>_compressed.csv` (`Section=values` / `Section=formulas_unique_block`) —
  **if a `*_compressed.csv` exists for a sheet, use it as the semantic surface and treat the
  raw CSV as provenance only**,
- `names_manager.csv` (if present),
- source-logic text under `vba\*.txt` (actual VBA for Excel; source text in the
  compatibility slot for Word/other adapters),
- `*_scalar.json` and `*_table_values.csv` golden expectations,
- `export_manifest.json` (the authoritative `llm_inputs` list, warnings, hashes,
  `expectation_coverage`).

#### Work order (deterministic loop)

1. **Resolve configuration.** Repo root, source path, bundle/out dir, generated dir,
   adapter, `max_attempts`. Any missing source, unsupported adapter, or invalid path
   **fails immediately** (these are not generation opportunities).
2. **Extract.** `python -m rechner_pipeline.toolbox.extract --repo-root <root> --input <source> --out-dir <bundle> [--adapter auto|excel|word|...] [--export-backend openpyxl|com] [--strict-manifest-warnings]`.
   Stop on non-zero exit.
3. **Read the bundle** per *Read-only input sources*. If `expectation_coverage` is `sparse`
   or `none`, you may not silently run a zero-comparison golden master and call it accepted
   (see *Acceptance*).
4. **Generate/edit** exactly the six files in the exact order below. Prefer direct file
   edits. If a CLI response must be parsed as text, wrap each file in
   `===FILE_START: <name>===` / `===FILE_END: <name>===` with **no outer text**.
5. **Run the gates** (§3.5 G0–G8) via the toolbox: `validate`, `security`, `conventions`,
   `golden_master`, `algebraic`, `roundtrip`, then `dossier`.
6. **Repair.** On any blocking failure read only the structured JSON (`errors`,
   `repair_hints`, `diagnostics_path`) and edit only the six generated files or the explicit
   QA-contract metadata inside them. **Never** edit bundle artifacts to make code pass.
7. **Re-run all required gates** after every repair. A previously-passed gate is invalid
   after any source change unless the gate reports a matching `input_hash`.
8. **Stop** when `dossier` reports `accepted`, or — when bounded attempts are exhausted —
   `human_review_required` / `failed`. Never reduce the gate set or accept partial results.

#### Output contract (hard-validated)

Exactly six files, this exact order, no path components, no duplicates, no outer text;
every `*.py` must compile:

```
inputs.py
params.py
tafeln.xml
commutation.py
actuarial.py
test_run.py
```

`test_run.py` must expose `golden_master_outputs() -> dict` returning
`{"scalars": {...}, "tables": {...}}`. `scalars` must cover **every** expected scalar
(including derived rates/parameters); `tables` must preserve expected row order and
case-sensitive headers.

#### Architecture — complete allowed import graph (MANDATORY)

The only permitted **production** import edges among the six files are listed below. Any
edge not in this table is a `conventions` (G3) failure. This is the authoritative,
complete graph; §6.1 only stated the single `actuarial.py → commutation.py` edge.

| From file | May import | Must NOT import | Layer responsibility |
|---|---|---|---|
| `inputs.py` | stdlib only | `params.py`, `tafeln.xml` loaders, `commutation.py`, `actuarial.py`, `test_run.py` | Input data classes / model-point definitions; no actuarial logic. |
| `params.py` | stdlib, `inputs.py` | `commutation.py`, `actuarial.py`, `test_run.py` | Constants, conventions, shared low-level utilities (e.g. `excel_round`); lowest computation layer. |
| `commutation.py` | stdlib, `inputs.py`, `params.py` | **`actuarial.py`** (forbidden), `test_run.py` | Mortality-table access (reads `tafeln.xml`), commutation values `D/N/C/M`, technical/math utilities. No tariff/product logic. |
| `actuarial.py` | stdlib, `inputs.py`, `params.py`, `commutation.py` | `test_run.py` | Present values, tariff/product logic, actuarial target figures. |
| `test_run.py` | stdlib, `inputs.py`, `params.py`, `commutation.py`, `actuarial.py` | — | Golden-master harness only; exposes `golden_master_outputs()`. |
| `tafeln.xml` | n/a (data file) | n/a | Serialized `qx` mortality tables; read by `commutation.py`. |

Shared utilities (e.g. `excel_round`) must live in a **lower** layer (`params.py` or
`commutation.py`); defining a utility in `actuarial.py` and importing it from
`commutation.py` is forbidden. Also forbidden everywhere: circular imports, imports inside
functions, `try/except ImportError`, and `TYPE_CHECKING` import tricks.

#### Caching

`lru_cache` is permitted **only** when every argument is strictly hashable (no
`dict`/`list`/`set`, no dataclasses with such fields). Otherwise use string IDs or explicit
identity hashing (`eq=False`, custom `__hash__`). Unknown hashability is a `conventions`
failure, not a silent pass.

#### Mortality tables — placeholder allowance RETIRED (fail-fast)

This is the deliberate TARGET divergence from §6.1. In the AS-IS prompt the model was
allowed to emit "klare Platzhalter" and a `NotImplementedError` when mortality tables were
absent. In the TARGET full-agentic design **inventing or guessing `qx` data is forbidden**:

- Recognized `qx` data extracted from the bundle (names manager, tables, source text) must
  be serialized faithfully into `tafeln.xml`.
- If a required mortality table or product is **not** present in the bundle, the generated
  code must raise an explicit exception (e.g. `NotImplementedError` / a dedicated
  `MissingMortalityTableError`) **and** the run must end in `human_review_required`. The
  agent must **never** fabricate a placeholder table, a flat `qx`, an interpolated curve, or
  any silent default to make a gate pass.
- No invented Excel cell addresses. Build a parameterized API from extracted labels,
  formulas, defined names, source text, and scalar/table expectations.

#### Static-security & runtime constraints carried into generated code

No network, no subprocess, no dynamic execution/import (`eval`, `exec`, `__import__`,
`importlib`), no write I/O, no broad filesystem APIs, no `random`/time/environment-dependent
calculation paths, and no exception-swallowing that hides a wrong calculation. Generated
code is executed only under filesystem confinement (read-only within repo root). These are
enforced by `security` (G2) and `fs_confine` (G4); the agent must not rely on the code to
police itself.

#### Acceptance & bounded self-repair

A run is **accepted iff** every required gate (G0–G8, §3.5) reports `passed` under recorded
versions/hashes, no blocking (`strict_error`) manifest warning remains, and no unapproved
open assumption remains. Acceptance is mechanical (the `dossier` gate), never the agent's
self-assessment.

Self-repair is bounded by an explicit instruction-level counter replacing the removed
LangGraph retry state: default `max_attempts = 4` (initial generation + three repairs),
hard normal cap `6` unless the user explicitly overrides. An attempt is counted once
generated files are written/edited and at least one required gate runs. **Fail-fast,
attempt-free errors** (extraction failure, missing dependency, unsupported source,
permission error, invalid configuration) do not consume attempts. On exhaustion the agent
stops, preserves all diagnostics, and marks the run `human_review_required`; it must not
reduce the gate set, downgrade a failure to a warning, or accept partial output.

### 6.8 TARGET acceptance JSON schemas

Authoritative for the TARGET path only. §6.4 reproduces the **AS-IS** manifest/dossier as
currently emitted; this appendix specifies the **new** records the full-agentic toolbox and
dossier must produce. All paths are strings; all hashes are SHA-256 hex; every toolbox
command prints exactly one JSON object to `stdout` (logs go to `stderr`).

#### 6.8.1 Common toolbox result object

Returned by every `python -m rechner_pipeline.toolbox.<command>` (§3.3). `status` mirrors
the exit code (`0` → `passed`; non-zero → `failed`/`human_review_required`).

```json
{
  "schema_version": 1,
  "command": "golden_master",
  "gate": "G5.golden-master",
  "gate_version": "1.0.0",
  "status": "passed",
  "exit_code": 0,
  "paths": {
    "repo_root": "C:\\AG-Bestandsmigration\\rechner-pipeline",
    "generated_dir": "generated",
    "info_dir": "info_from_excel",
    "diagnostics_path": "runs\\<run-id>\\golden_master.diagnostics.json"
  },
  "input_hashes": {
    "info_from_excel\\Kalkulation_scalar.json": "<sha256>",
    "generated\\test_run.py": "<sha256>"
  },
  "summary": { "scalars_tested": 5, "scalars_skipped": 1, "table_cells_tested": 132, "deviations": 0, "unmatched_columns": 0 },
  "metrics": { "duration_ms": 812 },
  "warnings": [],
  "errors": [],
  "repair_hints": []
}
```

Field rules: `status ∈ {passed, failed, human_review_required}`; `gate` is one of
`G0..G8` (§3.5); `errors[]`/`repair_hints[]` are present (possibly empty) on every result so
the agent can repair without parsing prose; `input_hashes` records every file the gate
consumed so a later run can prove a previously-passed gate is still valid (work-order step 7).
Standard exit codes are the §3.3 set (`2,10,20,21,22,30,31,32,40,50`).

#### 6.8.2 Gate-result ledger entry

One entry per gate execution, accumulated by `dossier` into `qa_report.json` (§6.8.3).

```json
{
  "gate": "G3.architecture-conventions",
  "command": "conventions",
  "gate_version": "1.0.0",
  "required": true,
  "status": "passed",
  "attempt": 2,
  "started_at": "<UTC ISO>",
  "input_hashes": { "generated\\actuarial.py": "<sha256>", "generated\\commutation.py": "<sha256>" },
  "diagnostics_path": "runs\\<run-id>\\conventions.diagnostics.json",
  "summary": { "import_edges": ["actuarial.py->commutation.py"], "illegal_edges": [], "circular": false }
}
```

#### 6.8.3 `qa_report.json` (new TARGET aggregate)

The mechanical acceptance record produced by `python -m rechner_pipeline.toolbox.dossier`.
`accepted` is computed, not supplied: `accepted == every required gate has status==passed
AND no strict_error warning AND no unapproved open assumption`.

```json
{
  "schema_version": 1,
  "created_at": "<UTC ISO>",
  "run_id": "<run-id>",
  "decision": "accepted",
  "accepted": true,
  "attempts_used": 2,
  "max_attempts": 4,
  "expectation_coverage": "full",
  "qa_contract_path": "generated\\qa_contract.json",
  "gates": [ { "gate": "G0.extraction-manifest", "required": true, "status": "passed" } ],
  "blocking_warnings": [],
  "open_assumptions": [],
  "generated_file_hashes": [ { "path": "generated\\inputs.py", "bytes": 1234, "sha256": "<sha256>" } ],
  "dependency_versions": { "python": "3.11.x", "openpyxl": "3.x", "hypothesis": "<pinned-or-absent>" },
  "tafeln_xml_canonical_sha256": "<sha256>"
}
```

`decision ∈ {accepted, human_review_required, failed}`. `human_review_required` is the
mandatory terminal state when `max_attempts` is exhausted or a missing mortality table /
sparse-coverage handoff occurred (§6.7). When `decision != accepted`, `accepted` is `false`
and at least one of `gates[].status != passed`, `blocking_warnings`, or `open_assumptions`
is non-empty.

#### 6.8.4 Upgraded `run_dossier.json` (TARGET delta over §6.4)

The TARGET dossier keeps the entire AS-IS `run_dossier.json` structure from §6.4 and
**adds** the fields that were noted as omitted in the AS-IS caveats (§2.6) plus the agentic
provenance. New/added keys:

| JSON path | Type | Meaning |
|---|---:|---|
| `schema_version` | integer | Bumped to `2` for the TARGET dossier. |
| `run.options.provider` | string | Now recorded (AS-IS omitted it): `claude` / `copilot` / `codex` / `opencode` / `replay`. |
| `run.options.max_output_tokens` | integer or null | Now recorded (AS-IS omitted it). |
| `run.options.export_backend` | string | Now recorded (AS-IS omitted it): `openpyxl` / `com`. |
| `run.options.test_mode` | string | Now recorded (AS-IS omitted it): `fixed` / `llm`. |
| `run.options.adapter_id` | string | `excel` / `word` / ... — selected input adapter. |
| `run.options.max_attempts` | integer | Bounded self-repair cap actually used. |
| `run.cli` | object | `{ "name": ..., "headless": bool }` — which CLI/adapter drove the run. |
| `qa_report` | `PathRecord` | Path record for `qa_report.json` (§6.8.3). |
| `gate_results[]` | array[gate-ledger entry] | Full §6.8.2 ledger (mirrors `qa_report.gates`). |
| `attempts[]` | array[object] | `{ "attempt": int, "gates_run": [...], "generated_file_hashes": [...], "outcome": "repaired"|"accepted"|"exhausted" }`. |
| `input_bundle` | object | InputBundle coverage metadata (§6.8.5). |

`PathRecord` is the §6.4 shape `{ "path": string, "exists": boolean }` plus `bytes` and
`sha256` when the path is an existing file.

#### 6.8.5 InputBundle coverage metadata block

Embedded as `run_dossier.input_bundle` and echoed by `extract`'s result `summary`. Makes
the §3.4 coverage decision auditable so a zero-comparison run can never masquerade as a
validated one.

```json
{
  "contract_version": "info_from_excel.v1",
  "adapter_id": "excel",
  "source_path": "C:\\...\\Tarifrechner_KLV.xlsm",
  "manifest_path": "info_from_excel\\export_manifest.json",
  "expectation_coverage": "full",
  "coverage_detail": {
    "scalar_files": 3, "scalar_keys_expected": 12, "scalar_keys_numeric": 11,
    "table_files": 2, "table_cells_expected": 264,
    "sheets_with_compressed": 4, "names_manager_present": true, "source_text_files": 5
  },
  "warnings": []
}
```

`expectation_coverage ∈ {full, sparse, none}`. If `sparse`/`none`, the dossier must record a
`human_review.required` or a recorded non-golden QA-contract policy open-assumption; the run
must not be `accepted` on a zero-comparison golden master (§3.4, §6.7).

#### 6.8.6 `qa_contract.json` (algebraic/property gate contract)

Consumed by `python -m rechner_pipeline.toolbox.algebraic --qa-contract <path> --strict`
(§3.3, gate G6). It is the explicit declaration that lets the algebraic gate select
applicable identities; **unknown applicability is a failure, never a silent skip** (§3.5).

```json
{
  "schema_version": 1,
  "product_type": "endowment_net_premium",
  "interest_basis": { "annual_effective_rate": 0.025, "v": "1/(1+i)", "d": "i/(1+i)" },
  "timing_convention": "annuity_due",
  "terminal_age_policy": { "omega": 121, "q_omega": 1.0 },
  "function_mappings": {
    "qx": "commutation.qx", "lx": "commutation.lx", "Dx": "commutation.Dx", "Nx": "commutation.Nx",
    "Ax": "actuarial.Ax", "aex": "actuarial.aex", "net_premium": "actuarial.net_premium"
  },
  "tiers_enabled": ["mortality_invariants", "commutation_identities", "present_value_identities", "product_specific"],
  "tolerances": { "rel_tol": 1e-9, "abs_tol": 1e-12 },
  "property_engine": { "name": "hypothesis", "version": "<pinned-from-Artifactory-or-absent>", "max_examples": 200 }
}
```

If the generated code cannot supply a required `product_type`, `interest_basis`,
`timing_convention`, or `function_mappings` entry for an enabled tier, the algebraic gate
exits non-zero (`31`) — it must not mark the identity inapplicable. If `property_engine` is
declared but unavailable from corporate Artifactory, the gate fails rather than downgrading
to a weaker random loop.
