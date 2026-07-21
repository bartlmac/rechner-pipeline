---
name: build-vergleichsrechenkern
description: >-
  Generate the six-file Python Vergleichsrechenkern (inputs.py, params.py, tafeln.xml,
  commutation.py, actuarial.py, test_run.py) by deterministically migrating an Excel/VBA
  Tarifrechner 1:1 into pure Python, then drive the toolbox gates to mechanical acceptance.
  Trigger when the user asks for `build-vergleichsrechenkern`, `build a Vergleichsrechenkern`,
  `Vergleichsrechenkern erstellen`, `Excel/VBA Tarifrechner nach Python migrieren`,
  `build a comparison kernel`, or explicitly requests generation of any of those six files
  from a workbook or extraction bundle. Skip for: pure read/search questions, authoring or
  editing the toolbox gates themselves (use author-rechner-toolbox-gate), or any task that
  does not produce/repair the six generated kernel files.
---

# Build the Vergleichsrechenkern

## Role and goal

You are a **senior actuarial developer and Python engineer**. Perform a deterministic
**1:1 migration** of the Excel formulas, defined names, and VBA/source logic of a
Tarifrechner into a pure-Python *Vergleichsrechenkern* of **exactly six files**, with
**no Excel runtime**, no network, no subprocess, and no hidden state. You **are** the
model in this loop: you plan, generate/edit files, run the deterministic toolbox, read the
JSON diagnostics, and repair — all inside one CLI session. Acceptance is mechanical (the
`dossier` gate), never your self-assessment.

## Read-only input sources

Read only the artifacts the extraction toolbox produced under the bundle directory
(default `info_from_excel\`). **Never** read the original `.xlsm`/`.docx` directly and
**never** write into the bundle:

- raw sheet CSVs `<prefix>.csv` (`Blatt;Adresse;Formel;Wert`),
- compressed CSVs `<prefix>_compressed.csv` (`Section=values` / `Section=formulas_unique_block`).
  **If a `*_compressed.csv` exists for a sheet, use it as the semantic surface and treat the
  raw CSV as provenance only.**
- `names_manager.csv` (if present),
- source-logic text under `vba\*.txt` (actual VBA for Excel; source text in the
  compatibility slot for other adapters),
- `*_scalar.json` and `*_table_values.csv` golden expectations,
- `export_manifest.json` — the authoritative `llm_inputs` list, warnings, hashes, and
  `expectation_coverage`.

## Work order (deterministic loop)

All gate commands run via `.venv\Scripts\python.exe -m rechner_pipeline.toolbox.<cmd>`.
**Pass one shared `--diagnostics-dir <dir>` to every command** so each gate writes its
`<command>.gate.json` ledger entry into the same directory that `dossier` later aggregates.
Pass `--repo-root` and (where accepted) `--info-dir`/`--generated-dir` consistently; the
`--info-dir` MUST live under `--repo-root` (otherwise the confined child's expectation reads
are blocked).

1. **Resolve configuration.** Repo root, source path, bundle/out dir, generated dir,
   adapter, and `max_attempts`. Any missing source, unsupported adapter, or invalid path
   **fails immediately** — these are not generation opportunities (see *Acceptance*).
2. **Extract.**
   `python -m rechner_pipeline.toolbox.extract --repo-root <root> --input <source> --out-dir <bundle> [--adapter auto|excel] [--export-backend openpyxl|com] [--strict-manifest-warnings] --diagnostics-dir <dir>`.
   Stop on non-zero exit.
3. **Read the bundle** per *Read-only input sources*. Inspect `export_manifest.json` first
   for `llm_inputs`, warnings, and `expectation_coverage`. If `expectation_coverage` is
   `sparse` or `none`, you may **not** silently run a zero-comparison golden master and call
   it accepted.
4. **Generate/edit** exactly the six files in the exact order below. **Prefer direct file
   edits.** If a CLI response must be parsed as text, wrap each file in the FILE blocks
   described under *Output contract*.
5. **Run the gates in order:** `validate` → `security` → `conventions` → `golden_master`
   → `algebraic` → `roundtrip` → `dossier`.
6. **Repair.** On any blocking failure read only the structured JSON of that gate (`errors`,
   `repair_hints`, `diagnostics_path`) and edit **only** the six generated files or the
   explicit QA-contract metadata inside them. **Never** edit bundle artifacts to make code
   pass.
7. **Re-run all required gates after every repair.** A previously-passed gate is invalid
   after any source change unless the gate reports a matching `input_hash`.
8. **Stop** when `dossier` reports `accepted`, or — when bounded attempts are exhausted —
   `human_review_required` / `failed`. Never reduce the gate set or accept partial results.

### Exact gate command surface

| Order | Command | Required flags you pass |
|---|---|---|
| extract | `extract` | `--repo-root --input --out-dir [--adapter] [--export-backend] [--strict-manifest-warnings] --diagnostics-dir` |
| G1 | `validate` | `--repo-root --generated-dir --info-dir --diagnostics-dir` (optionally `--file-block-response PATH` to validate FILE blocks from a text response instead of files on disk) |
| G2 | `security` | `--generated-dir --diagnostics-dir` |
| G3 | `conventions` | `--generated-dir [--allowlist PATH] --diagnostics-dir` |
| G5 | `golden_master` | `--repo-root --generated-dir --info-dir --diagnostics-dir` |
| G6 | `algebraic` | `--repo-root --generated-dir --info-dir --qa-contract PATH [--strict] --diagnostics-dir` |
| G7 | `roundtrip` | `--repo-root --generated-dir --info-dir [--input <source>] --diagnostics-dir` |
| G8 | `dossier` | `--repo-root --generated-dir --info-dir [--status ...] --diagnostics-dir` |

`roundtrip` needs `--input <source>` (the original workbook) for its re-extraction stability
check. `dossier` globs `*.gate.json` in the shared `--diagnostics-dir` and decides
acceptance mechanically; a passed required gate with empty `input_hashes` is **blocked**, so
never bypass the shared diagnostics directory.

### One-command driver (`assurance`) — runs the whole gate chain to a dossier verdict

After the six files are generated, drive acceptance with the single orchestrator (it invokes
each existing gate's `main()` in order — `extract → validate → security → conventions →
golden_master → algebraic → roundtrip → dossier` — over the shared `--diagnostics-dir`; the
aggregate exit code is the dossier verdict, exit 0 = `accepted`, 40 = `human_review_required`):

```
.venv\Scripts\python.exe -m rechner_pipeline.cli assurance ^
    --repo-root . ^
    --input examples\Tarifrechner_KLV.xlsm ^
    --generated-dir generated ^
    --info-dir info_from_excel ^
    --diagnostics-dir diagnostics ^
    --qa-contract qa_contract.json ^
    --adapter excel [--max-attempts 4]
```

`extract` + `validate` are prerequisites (their failure skips the QA gates but still runs
`dossier` for an honest blocked verdict); `security..roundtrip` are continue-on-fail.
**Omitting `--qa-contract` SKIPS G6 (`algebraic`) and dossier then blocks on `gate.missing`
for G6 — fine for a chain smoke-test, NEVER for real acceptance. A real `qa_contract.json` is
required for full acceptance.** You may still run gates individually (table above) when
repairing a specific failure; `assurance` is the full-suite driver.

### Pinned directory layout (all relative to `--repo-root .`)

| Dir | Flag | Purpose / rule |
|---|---|---|
| `info_from_excel/` | extract `--out-dir` **and** gates' `--info-dir` | The extraction bundle. **MUST live under `--repo-root`** or the confined golden_master/roundtrip children cannot read expectations (exit 30 `confinement_failure`). |
| `generated/` | `--generated-dir` | **EXACTLY the six kernel files — nothing else.** G1 (`validate`) re-checks the six-file contract and FAILS on any extra sibling, so `qa_contract.json`, `qa_report.json`, and `run_dossier.json` must NOT live here. |
| `qa_contract.json` | `--qa-contract` | The authored QA contract for G6 (`algebraic`). Lives at **repo root** (outside `--generated-dir`), e.g. `--qa-contract qa_contract.json`. |
| `diagnostics/` | `--diagnostics-dir` | Shared ledger dir every gate writes its `<command>.gate.json` into; `dossier` aggregates it AND writes `qa_report.json` + `run_dossier.json` here (never into `generated/`). |

Keep `--input <source>` (the original workbook, e.g. `examples\Tarifrechner_KLV.xlsm`)
available after extraction — G7 (`roundtrip`) re-extracts it for its stability check.

## Output contract (hard-validated)

Exactly six files, **this exact order**, no path components, no duplicates, no outer text;
every `*.py` must compile:

```
inputs.py
params.py
tafeln.xml
commutation.py
actuarial.py
test_run.py
```

When emitting files as a text response (direct edits are preferred), wrap **each** file as:

```
===FILE_START: inputs.py===
<file content>
===FILE_END: inputs.py===
```

with **no outer text** before, between, or after the blocks. Only whitespace is permitted
outside the matched blocks; any other prefix/infix/suffix is rejected. The file set must
equal the six names above, in order, with no path separators and no duplicates.

`test_run.py` must expose `golden_master_outputs() -> dict` returning
`{"scalars": {...}, "tables": {...}}`. `scalars` must cover **every** expected scalar
(including derived rates/parameters); `tables` must preserve expected **row order** and
**case-sensitive headers**. (Scalar names are matched case-sensitive with no separator
normalization; only table columns get separator leniency, still case-sensitive.)

## Architecture — complete allowed import graph (MANDATORY)

The only permitted **production** import edges among the six files are listed below. Any
edge not in this table is a `conventions` (G3) failure. This is the authoritative, complete
graph.

| From file | May import | Must NOT import | Layer responsibility |
|---|---|---|---|
| `inputs.py` | stdlib only | `params.py`, `tafeln.xml` loaders, `commutation.py`, `actuarial.py`, `test_run.py` | Input data classes / model-point definitions; no actuarial logic. |
| `params.py` | stdlib, `inputs.py` | `commutation.py`, `actuarial.py`, `test_run.py` | Constants, conventions, shared low-level utilities (e.g. `excel_round`); lowest computation layer. |
| `commutation.py` | stdlib, `inputs.py`, `params.py` | **`actuarial.py`** (forbidden), `test_run.py` | Mortality-table access (reads `tafeln.xml`), commutation values `D/N/C/M`, technical/math utilities. No tariff/product logic. |
| `actuarial.py` | stdlib, `inputs.py`, `params.py`, `commutation.py` | `test_run.py` | Present values, tariff/product logic, actuarial target figures. |
| `test_run.py` | stdlib, `inputs.py`, `params.py`, `commutation.py`, `actuarial.py` | — | Golden-master harness only; exposes `golden_master_outputs()`. |
| `tafeln.xml` | n/a (data file) | n/a | Serialized `qx` mortality tables; read by `commutation.py`. |

The only permitted edge **between** the computation layers is `actuarial.py → commutation.py`.
Shared utilities (e.g. `excel_round`) must live in a **lower** layer (`params.py` or
`commutation.py`); defining a utility in `actuarial.py` and importing it from `commutation.py`
is forbidden. Also forbidden everywhere: **circular imports, imports inside functions,
`try/except ImportError`, and `TYPE_CHECKING` import tricks.**

## Caching

`lru_cache` is permitted **only** when every argument is strictly hashable (no
`dict`/`list`/`set`, no dataclasses with such fields). Otherwise use string IDs or explicit
identity hashing (`eq=False`, custom `__hash__`). Unknown hashability is a `conventions`
failure, not a silent pass.

## Mortality tables — placeholder allowance RETIRED (fail-fast)

**Inventing or guessing `qx` data is forbidden.**

- Recognized `qx` data extracted from the bundle (names manager, tables, source text) must
  be serialized faithfully into `tafeln.xml`.
- If a required mortality table or product is **not** present in the bundle, the generated
  code must raise an explicit exception (e.g. `NotImplementedError` or a dedicated
  `MissingMortalityTableError`) **and** the run must end in `human_review_required`. **Never**
  fabricate a placeholder table, a flat `qx`, an interpolated curve, or any silent default to
  make a gate pass.
- **No invented Excel cell addresses.** Build a parameterized API from extracted labels,
  formulas, defined names, source text, and scalar/table expectations.

## Static-security & runtime constraints carried into generated code

No network, no subprocess, no dynamic execution/import (`eval`, `exec`, `__import__`,
`importlib`), no write I/O, no broad filesystem APIs, no `random`/time/environment-dependent
calculation paths, and no exception-swallowing that hides a wrong calculation. Generated code
is executed only under filesystem confinement (read-only within repo root) and these rules are
enforced by `security` (G2) and runtime confinement (G4); do not rely on the code to police
itself.

### Gotchas carried into the generated code (one-liners)

- **No** `time`/`random`/`os.environ`/network/`subprocess`/dynamic-import (`__import__`,
  `importlib`, `eval`, `exec`)/write-I/O — G2 refuses to even execute the kernel otherwise.
- Only the edge `actuarial.py → commutation.py` between computation layers; shared utilities live
  in a lower layer. Dynamic imports do **not** evade G3 — `__import__`/`importlib` are flagged.
- `@lru_cache` only with strictly-/typed-hashable args: a **bare** `tuple`/`Tuple` annotation
  FAILS G3 (unknown element hashability); use `Tuple[int, ...]` etc. or string IDs.
- `golden_master_outputs()` scalar keys must **byte-match** the `*_scalar.json` keys
  (case-sensitive, no separator normalization); only table columns get separator leniency.
- Recognized `qx` → serialize faithfully into `tafeln.xml` at full precision (G7 carries
  >12-decimal qx losslessly now); an unrecognized/missing table → raise `NotImplementedError`
  (or `MissingMortalityTableError`) — **no** placeholder/flat/interpolated curve.
- Kernel must be **deterministic** — G7 (`roundtrip`) re-runs it in fresh processes and the
  golden-master/algebraic children execute it under read-only filesystem confinement.

## The algebraic gate (G6) needs a `qa_contract.json`

`algebraic` requires `--qa-contract <path>` pointing to a JSON contract validated by
`models.schemas.QaContract`. `qa_contract.example.json` at the repo root is a full, schema-valid
template — copy it to `qa_contract.json` at the **repo root** (NOT into `generated/`, where the
six-file G1 `validate` contract would reject it as a 7th file) and fill in the **real** `omega`,
`timing_convention`, and resolved `function_mappings` for YOUR kernel. Below is the **verified KLV
contract** (the exact content on disk at repo-root `qa_contract.json` — the authoritative example;
adapt the values for other tariffs). Note `function_mappings` resolve to the kernel's real callables
(here the single-arg `*_at` adapters), and `version: ""` lets the gate use the installed Hypothesis:

```json
{
  "schema_version": 1,
  "product_type": "endowment_net_premium",
  "interest_basis": { "annual_effective_rate": 0.0175, "v": "1/(1+i)", "d": "i/(1+i)" },
  "timing_convention": "annuity_due",
  "terminal_age_policy": { "omega": 100, "mode": "q_omega_is_one", "q_omega": 1.0 },
  "function_mappings": {
    "qx": "commutation.qx_at", "lx": "commutation.lx_at",
    "Dx": "commutation.Dx_at", "Nx": "commutation.Nx_at", "Cx": "commutation.Cx_at", "Mx": "commutation.Mx_at",
    "Ax": "actuarial.Ax", "aex": "actuarial.aex",
    "net_premium": "actuarial.net_premium", "pv_benefits": "actuarial.pv_benefits", "pv_premiums": "actuarial.pv_premiums"
  },
  "tiers_enabled": ["mortality_invariants", "commutation_identities", "present_value_identities", "product_specific"],
  "tolerances": { "rel_tol": 1e-9, "abs_tol": 1e-12 },
  "property_engine": { "name": "hypothesis", "version": "", "max_examples": 200 }
}
```

Rules (a missing/unresolvable mapping, unknown tier/timing/product, or any unknown applicability
is a HARD fail at **exit 31** — never a silent skip):

- `interest_basis.annual_effective_rate` (numeric, `> -1`) is required and consumed by BOTH the
  commutation and PV tiers; the engine derives `v=1/(1+i)`, `d=i/(1+i)` itself (the `"v"`/`"d"`
  strings in the template are documentation only). `commutation_base_age` is OPTIONAL (default 0
  = `D_x=v^x·l_x`, x=attained age); set it only if Dx is tabulated from a non-zero entry age.
- `timing_convention`: the universal PV tier is defined for `"annuity_due"` **only**; any other
  value with `present_value_identities` enabled fails `timing_unknown`.
- `terminal_age_policy.omega` (int) is required whenever any tier runs (bounds sampling +
  `Nx`/`Mx` closed-form sums). When `mortality_invariants` is enabled you MUST also declare an
  explicit terminal policy: `mode: "q_omega_is_one"` (standard close-the-table, no value needed)
  or `mode: "explicit"` with a numeric `q_omega`. Absence = exit 31 `terminal_age_unknown`.
- To enable `product_specific`, `product_type` must contain `net_premium`. `tiers_enabled` is a
  subset of `{mortality_invariants, commutation_identities, present_value_identities,
  product_specific}`. **Required mappings per enabled tier:** mortality → `qx`,`lx` (opt `px`);
  commutation → `lx`,`Dx`,`Nx` (opt `Cx`,`Mx`); present-value → `qx`,`Ax`,`aex`; product →
  `net_premium`,`pv_benefits`,`pv_premiums`. Values are `"module.func"` resolved against the
  kernel (`commutation.*` / `actuarial.*`). **Do NOT declare a `vpow` mapping — it is not in the
  schema; `D_x=v^x·l_x` is now checked directly from `Dx`+`lx`+the interest basis.**
- `property_engine.name` must be `"hypothesis"`; a concrete `version` must equal the installed
  `6.155.5` (else exit 31 `engine_version_mismatch`), while a placeholder/empty `version` means
  "use the installed reviewed version".

## Acceptance & bounded self-repair

A run is **accepted iff** every required gate (G0–G8) reports `passed` under recorded
versions/hashes, no blocking (`strict_error`) manifest warning remains, and no unapproved open
assumption remains. Acceptance is mechanical — the `dossier` gate decides, never your
self-assessment.

Self-repair is bounded by an explicit instruction-level counter: default `max_attempts = 4`
(initial generation + three repairs), hard normal cap **6** unless the user explicitly
overrides. **An attempt is counted once generated files are written/edited and at least one
required gate runs.** Fail-fast, attempt-free errors — extraction failure, missing dependency,
unsupported source, permission error, invalid configuration — do **not** consume attempts.

On exhaustion, **stop**, preserve all diagnostics, and mark the run `human_review_required`.
Never reduce the gate set, downgrade a failure to a warning, or accept partial output.
