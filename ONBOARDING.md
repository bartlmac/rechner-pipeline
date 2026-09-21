# ONBOARDING — rechner-pipeline

## 1. What this is
A system for **life-insurance portfolio migration**, with **no LLM SDK in the
codebase** (the CLI agent *is* the model; Python code pre-digests, validates,
computes and accepts):

The repository carries **four levels** (ADR-017): the developer's work
with the AI (reviews, ADRs, the suite); the **KI-Tool**, the agentic
migration system that any insurer could use unchanged (ontology, spec
contract, gates, roles, skills, report generators); the **Vorzeige**, a
fictional insurer at which the tool shows itself and can be tested
(reference target kernel, portfolio management, the migration case, the
company site); and the **Vorzeige tools** that produce the Vorzeige
(portfolio simulation, source-system generation, direction mechanics).
The layer map records the level of every layer and pins the edges from
the tool into the Vorzeige as a ratchet.

1. **The target kernel** (`rechner_pipeline.kern`, version 3.4.0, part of
   the Vorzeige as the reference target system): a stable, versioned
   calculation kernel formulated entirely in the state-model world
   (semi-Markov backbone, Thiele recursion on pure decrement probabilities).
   Two products — endowment (KLV) and disability (BU) — are *configurations*
   of that backbone, not separate engines. The commutation second kernel is
   out of service (ADR-013); it survives only as an independent witness in
   the algebraic property tests.
2. **The portfolio module** (`rechner_pipeline.bestand`): synthetic,
   forward-projectable portfolios that the target kernel can compute directly.
   Every amount comes from the kernel; the module carries no actuarial
   formulas of its own.
3. **The migration pipeline** (the main path): heterogeneous sources
   (Tarifmeldung DOCX, Tarifrechner XLSM) -> ontology (T-Box/A-Box with
   per-statement provenance and discrepancy objects) -> Tarif-Spez ->
   parametrized kernel -> acceptance against the source calculator, with human
   gates (A-Q1/A-M1/A-M4/A-K1) and immutable decision snapshots.

Read `docs/architektur/migrations-pipeline-v01.md` first, then the role catalog
`docs/architektur/skill-architektur.md`, then the ADRs in
`docs/architektur/`.

**Historical note:** the project started from a one-time *translation act* — a
coding agent ported an Excel/VBA calculator into a six-file Python kernel,
accepted by a deterministic gate chain (617/617 values, 2026-07-22). That proof
is complete. The porting machinery was retired on 2026-08-17; the retired
state is archived by the maintainer (not a published branch).

What replaces it is NOT "every migration is parametrization". That
reading was explicitly corrected in ADR-007: a generation the target
system already covers is parametrization over the model point — the
precedent TG2012 -> TG2015 ran through without a single formula change.
The **normal case is the opposite**: a ceded portfolio brings benefit
features the kernel does not know yet, and the migration is an intensive,
node-bound CODE extension of the one trunk (small increments, landing
only with the full suite green including every other case's frozen reference values,
`integriere-migrationsinkrement`). New products come through the T-Box
(gate A-K1) — in either case not by translating another workbook.

A migration case lives in a **Fall-Arbeitsbereich** (`python -m
rechner_pipeline.fall`, ADR-002). The artifacts of this workspace belong to
**Pfefferminzia Lebensversicherung (PLV)** — the fictitious insurer the
system is demonstrated on. `configs/` holds the PLV portfolio
configurations (TOML, suite-loaded); `tests/fixtures/` holds synthetic
source workbooks for the extraction tests; `lieferungen/` ships the
showcase deliveries of fictitious ceding insurers. There is no
implicit input channel — sources enter a case only through explicit
registration (below).

## 2. Setup
The reference environment is **Linux with CPython 3.11** and the exact
pins below — what CI runs and what the runtime image is built from. The
project does not harden its code for other operating systems (maintainer
decision 2026-09-06): if you are not on Linux, run everything inside the
container, which IS the reference environment.

**On Linux**, no LLM key needed:
```
python -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pip install -e . --no-deps
```
**On Windows, check WSL 2 first.** Docker Desktop's WSL integration
requires a distribution running **WSL version 2**. A Windows machine may
already carry a WSL environment that is still on version 1; the
integration then cannot be enabled at all, and the failure is not
obvious. Check before building:
```
wsl -l -v
```
Every distribution you intend to use must show `VERSION 2`. If none does,
install a fresh one — this is the route a team member actually ran:
```
wsl --install -d Ubuntu
wsl -d Ubuntu
```
Converting an existing version-1 distribution in place is possible
(`wsl --set-version <distribution> 2`, with the name from the first column
of `wsl -l -v`), but nobody here has run that route.

**Anywhere else** (Windows with Docker Desktop and WSL2, macOS): build the
development image once and run the suite in it; the working tree is
mounted, so code changes need no rebuild.
```
docker build -f deploy/dev/Dockerfile -t rechner-pipeline-dev .
docker run --rm -v "$PWD":/workspace rechner-pipeline-dev            # full suite
docker run --rm -it -v "$PWD":/workspace rechner-pipeline-dev bash   # shell
```
**Platforms that have been verified.** The container route is not a
theory here; two team members have run it and reported provenance, not
just a suite line:

| Platform | Measured |
|---|---|
| Windows 11, WSL 2 (Ubuntu), Docker Desktop | suite green 2026-09-14; provenance 2026-09-20 on commit `f518b6a`: 2212 passed, 3 skipped in 908 s |
| macOS 26.6.2, arm64 | same commit `f518b6a`: 2212 passed, 3 skipped in 595 s |

Two results matter beyond "it ran". First, both platforms reported the
SAME `quellcode_sha256` on the same commit (`c4bffa4f...`) — so the
checkout is byte-identical across platforms and the LF pinning in
`.gitattributes` does what it claims; a Windows checkout is not a
different tree. Second, `systemstand` carried real values on Windows,
not `unbekannt`: git reads the mounted tree from inside the container
there too, so gate belege produced on Windows carry the same provenance
as on Linux. That was the actual worry, and it is answered.

The pitfall is the one described above: the WSL environment
preinstalled on a machine may still be version 1, and the Docker Desktop
integration then cannot be enabled at all. Installing a fresh Ubuntu and
working in it is the route that was actually run.

**Reporting an environment.** When you report a run — a new machine, a
platform we have not verified — send the provenance of the code you ran,
not just the suite line. Same container, one command:
```
docker run --rm -v "$PWD":/workspace rechner-pipeline-dev \
  python -c "import json; from pathlib import Path; from rechner_pipeline.gates._provenienz import systemstand; print(json.dumps(systemstand(Path('/workspace')), indent=2))"
```
It prints four values. `quellcode_sha256` covers the package sources
(`.py` and `.xml` under `src/rechner_pipeline/`) and nothing else — a
docs-only or tests-only commit leaves it unchanged, a code change moves
it. `dirty` must read `nein`; otherwise the checkout carries uncommitted
edits and the hash is not comparable. If `commit` or `branch` read
`unbekannt`, git cannot read the tree from inside the container — on
Linux it can, elsewhere this is worth reporting.

The expected `quellcode_sha256` is not printed here on purpose: it belongs
to one commit and would age with the next code change. Whoever asks you to
run this names the value together with the commit it belongs to.

VS Code users open the repo with the Dev Containers extension; the
definition in `.devcontainer/` builds the same image. Keep the checkout on
a Linux filesystem (your WSL2 home, not `/mnt/c`): the suite checks file
permissions and umask, which an NTFS mount does not carry. Line endings
are pinned to LF by `.gitattributes`; deliveries and fixtures are
excluded from that rule because their bytes are hashed.

This is the one documented install path, identical to CI. The pin files
carry the direct dependencies (`pyproject.toml`: `openpyxl`, `oletools`,
`pandas`, `pyarrow`, `matplotlib`, `pydantic`, `pypdf`; dev: `pytest`,
`hypothesis`, `pytest-xdist`) AND their complete transitive closure;
`tests/test_abhaengigkeiten.py` keeps that closure closed. Installing
with `pip install -e ".[dev]"` alone pins only the direct dependencies
and lets pip resolve everything transitive freshly — with
`filterwarnings = ["error"]` on, a new warning in a third-party package
then turns the suite red without anything here having changed. That path
is therefore not documented (external review T19-04/T20-08).
`requirements.txt` / `requirements-dev.txt` pin the direct dependencies
plus their transitive closure as installed from public pypi.org (verified
under CPython 3.11 on 2026-08-19). Nine purely transitive packages
(`annotated-types`, `contourpy`, `cycler`, `fonttools`, `kiwisolver`,
`pillow`, `pydantic-core`, `typing-extensions`, `typing-inspection`) are
still resolved by pip — the closure is tight, not hermetic. Use a lock
tool if you need hermetic.

## 3. Run it
**Create a case and register its sources.** Registration is the ONLY
way into a case — never copy files into `eingang/` by hand. The command
takes the delivery wherever it landed (download folder, scp target),
copies it into `eingang/` (optionally renamed via `--als`), records
SHA-256, origin path and size in the `eingang.json` register, and sets
the copy read-only. Every later statement in the case traces back to
these hashes — the provenance chain starts here:
```
python -m rechner_pipeline.fall anlegen --fall faelle/klv-tg2012 --scope tarif
python -m rechner_pipeline.fall registrieren --fall faelle/klv-tg2012 \
    --datei tests/fixtures/Tarifrechner_KLV_TG2012.xlsm
python -m rechner_pipeline.fall status --fall faelle/klv-tg2012
```
`status` (and every pipeline run) checks the register against the file
system in both directions: a registered file that is missing or whose
content deviates from its hash is a hard error, and so is any
hand-copied file without a register entry. Re-registering the same
content reports `bereits_registriert`; a lost copy is restored from
the source without touching the register; the same name with different
content is a hard conflict showing both hashes — there is no silent
overwrite. If a delivery genuinely replaces an earlier one, set up a
fresh case (or archive the old one under `faelle/archiv/`).

**Run the showcase migration.** `lieferungen/baldrian/` ships the
delivery of the fictitious insurer Baldrian Leben — the inputs of a real
portfolio migration (faulty tariff calculator, tariff notification,
portfolio data delivery with two reporting dates, a GeVo protocol, and
the metadata list of the business events that happened BEFORE the
migration date). Register it into a fresh case — the case is named
`baldrian-uebernahme` throughout the docs, the skills and the ADRs, so
keep that name:
```
python -m rechner_pipeline.fall anlegen --fall faelle/baldrian-uebernahme --scope bestand
for f in lieferungen/baldrian/*.xlsm lieferungen/baldrian/Mitteilung_143_KLV_TG2015.docx \
         lieferungen/baldrian/*.csv; do
  python -m rechner_pipeline.fall registrieren --fall faelle/baldrian-uebernahme --datei "$f"
done
python -m rechner_pipeline.fall status --fall faelle/baldrian-uebernahme
```
Note which file the loop does NOT pick up:
`Aktuarielle_Notiz_Beitragsabsetzung.docx`. The tariff notification does
not describe how a premium reduction is computed, and the delivery is
deliberately incomplete there. The note is what the ceding insurer sends
AFTER the gap has surfaced and someone asked — register it then, not
before. Registering it upfront skips the very step this showcase
demonstrates.
If that workspace already exists, `anlegen` stops with a hard error
("Fall existiert bereits") instead of writing into it — by design, since
`eingang/` is not regenerable (ADR-002). Pick another name or archive the
old one under `faelle/archiv/`.

The stages after registration run through the agent skills
(`migrationsfall-durchfuehren` orchestrates; role catalog in
`docs/architektur/skill-architektur.md`): pre-digestion and extraction
per source, merge into the A-Box, discrepancies to the human gate A-Q1,
transformation of the portfolio extract, Spez, acceptance gates, and the
two-reporting-date migration suite with its HTML acceptance report for
gate A-M4. The deliveries may contain deliberate errors and source-system
quirks — finding them IS the demonstration.

**Pre-digest a source (gate P-Q1):**
```
python -m rechner_pipeline.gates.extract --repo-root . \
    --input faelle/klv-tg2012/eingang/Tarifrechner_KLV_TG2012.xlsm \
    --out-dir faelle/klv-tg2012/abgeleitet/vorverdichtung/xlsm-TG2012 --adapter excel
```
The ontology gates cannot follow directly on a fresh case: P-Q3
(`gates.abox_validate`) validates an A-Box, and P-K1
(`gates.generation_golden`) validates a Tarif-Spez — neither exists
yet. The A-Box is produced by the Stage-1 extraction agents plus the
deterministic merge (`gates.abox_merge`), and the Spez is projected
from the accepted A-Box. Calling P-Q3 or P-K1 on a bare case fails with
exit 2 **by design**: no silent default, the error names what is
missing. Run them the way `migrationsfall-durchfuehren` does — after
the stage that produces their input, and with the same `--generation`
the case actually carries.

**Where the deterministic walkthrough ends — read this before you get
stuck.** `anlegen`, `registrieren`, `status` and the P-Q1 pre-digestion
above are plain Python: they run for anyone who cloned the repo, no key,
no agent. What comes next does not. Extraction per source, the reading
of the Tarifmeldung and the transformation proposal for the portfolio
extract are **agent** steps (that is the point of the architecture — the
model proposes, deterministic code decides), and A-Q1/A-M4 are human
decisions, not commands. So a walkthrough without an agent CLI ends
here, with a non-zero exit that is the contract and not a broken
install. To continue you need Claude Code or Codex in the repo root and
the skills under `.claude/skills/` / `.agents/skills/`.

What you CAN still exercise end-to-end on your own: the portfolio
generator and its report (next), gate P-Q1 on any workbook, the
code-ontology tools, the actuarial documentation
(`docs/mathematik/grundsatzdokumentation.md` for the shared maths,
`docs/tarifplaene/` for each product's elaboration), and the
test suite.

**Generate a portfolio and its report.** A portfolio is built from its
access stream: the run starts empty and every contract enters as a
dated `ZUG` event (ADR-020). `--neuzugang-ab` names the day the stream
starts — for a portfolio built from scratch that is the first sales day
of the oldest generation; `--bis` is the simulation horizon (how far
events are projected). The report's `--stichtag` only marks the
history/projection boundary; it is optional and defaults to
`meta.referenzstichtag` from the config (so it only applies when
`--config` is passed) — the reference date is a property of the
portfolio, kept in its config, and the flag merely overrides it. Setting
`--bis` to "today" silently kills the projection.
```
python -m rechner_pipeline.bestand.cli_fortschreibung \
    --config configs/bestand_gesamt.toml --neuzugang-ab 1994-07-01 \
    --bis 2046-01-01 --out-dir runs/bestand
python -m rechner_pipeline.bestand.cli_report --portfolio runs/bestand/bestand_gesamt.parquet \
    --historie runs/bestand/historie.parquet --ledger runs/bestand/ledger.parquet \
    --scheiben runs/bestand/scheiben.parquet --config configs/bestand_gesamt.toml \
    --bis 2046-01-01 --stichtag 2026-01-01 --out runs/berichte/bestandsbericht.html
```
The run reports `0 Basisvertraege, 4441 Neuzugaenge` — the zero is
correct and the one number that invites misreading: there is no base
portfolio any more, every one of the 4441 contracts is a new entry with
its own `ZUG` in the ledger (1213 of them start after 01.01.2026, the
yearly target shrinks with `neuzugang_trend`). A run given neither
`--portfolio` nor `--uebernahme` nor `--neuzugang-ab` has nothing to
carry and says so (exit 2) instead of inventing a portfolio.

The run also writes `runs/bestand/laufmanifest.json`, its delivery
note: the simulated horizon, the config hash and a SHA-256 per output.
`cli_abschluss` refuses a run directory without it, and `--bis` must
equal the horizon the manifest attests — the horizon is a property of
the run, not of the call that reads it. Gate P-B1 binds the manifest
on request (`--manifest`).

The demo itself does not use this command for its own business: the
Pfefferminzia is run day by day (`betrieb.tageslauf`, same access
stream at daily resolution, see `docs/simulation/tagesbetrieb.md`).
`cli_fortschreibung` is the test track of a migration case
(`--uebernahme`, see the migration skill) and the quickest way to a
synthetic portfolio with full history.

**Navigate the codebase** (fundstellen are derived, not searched — ADR-005):
```
python -m rechner_pipeline.ontologie.code_index --tests tests   # node <-> module/test
python -m rechner_pipeline.ontologie.code_karte                 # layer rules
git diff --name-only | python -m rechner_pipeline.ontologie.impact
python -m rechner_pipeline.ontologie.landkarte --out runs/landkarte.html
```

## 4. The gates
Each gate is one command, writes one JSON to stdout plus a
`<command>.gate.json` ledger into `--diagnostics-dir`. A non-zero exit is
**blocking** and is never softened into a warning.

| Gate | Command | Proves |
|---|---|---|
| P-Q1 | `gates.extract` | deterministic pre-digest of a source workbook (formulas, cached values, defined names via openpyxl; VBA via `oletools.olevba`) |
| P-Q2 | `gates.abox_merge` | fragments merged into the A-Box, with a chain ledger binding it to its sources |
| P-Q3 | `gates.abox_validate` | A-Box against T-Box, coverage, plausibility ranges, formula back-check, chain re-computation; the A-Box must carry the current T-Box version |
| P-K1 | `gates.generation_golden` | the parametrized kernel against the source calculator's expectation values; writes one content-addressed proof per generation, bound to the A-Box and system state; spec, A-Box and code must speak the same T-Box version |
| P9 | `gates.gate_entscheid` | schema- and chain-validated snapshots of the human gates (A-Q1, A-M1, A-M4, A-K1); accepted decisions require an externally held HMAC key, A-M1 and A-M4 require the per-gate evidence roles for the declared case scope, and A-M4 requires a current signed A-M1 acceptance on the same state, pinned as the evidence role `am1_snapshot` (ADR-010); in scope `bestand` A-M4 also requires the release proof `gates.fuehrungsprobe` as evidence role `fuehrungsprobe` — the proof that the portfolio ledger carries the world the acceptances tested (Freischaltung, dev-docs/freischaltung-uebernommener-bestand.md); A-K1 requires the T-Box change record `abgeleitet/tbox/aenderung.json` (old and new version, hash of the T-Box module, change artefact); a simulated role signs only with a mandate (ADR-018); agents may only reject |
| A-M-Vorlagen | `gates.aktuartest --abnahme A-M1\|A-M2\|A-M3` | re-derives the actuarial test result from the inside out (per-contract comparison at each contract's own anchor date, no interpolation, no summation — only residual distribution measures) and renders the decision template for the respective gate A-M1, A-M2 or A-M3 (in scope `bestand` all three are mandatory predecessors of A-M4, in scope `tarif` only A-M1); transport-security digests are reported separately |
| P-B1 | `gates.bestand_validate` | portfolio contract and movement identities |
| G2 template | `gates.abnahmebericht` | passes only with the transformation specification/result, distinct before/after reports, a gap-free suite, congruent row counts, no transformation finding and no unresolved conflict; for scope `bestand`, also validates and binds P-B1, the suite and HTML report on one state |

An accepted P9 decision additionally requires
`--freigabe-schluessel /secure/p9-approval.key`. The human operator keeps this
file outside the case and outside agent access; it must contain at least 32
cryptographically random bytes, have POSIX mode 0600, and exactly one hard
link. Repeat the option with old keys first and the
active signing key last when rotating. Key bytes and paths are never persisted.
P9 revalidates the strict ledger/snapshot schemas, canonical content hash,
full-hash filename, HMAC, predecessor existence, cycles, and the unique chain
tip on every read (ADR-008).

For A-M4, `fall.json` also carries `scope.typ` (`tarif` or `bestand`). Missing
declarations are never inferred from files. A tariff case requires no portfolio
artifacts; a portfolio case requires a green P-B1 ledger, complete suite, a
passed release proof (`gates.fuehrungsprobe`: the migrated portfolio and its
continuation are held against the acceptance engines — same initial state,
same tariff switches, same correction layer) and the HTML report, all bound by
the green `abnahmebericht` ledger. A-M4 rehashes their current bytes, reruns
the P-B1 engines, revalidates the suite and the release proof, and
deterministically rerenders the report for a byte comparison instead of
trusting that editable ledger (ADR-009).

## 5. Non-negotiables
- **Deterministic and SDK-free** in `src/`: no network, no dynamic execution,
  no subprocess; same input -> same output; sorted serialization. There is
  exactly ONE subprocess exception, and it is bounded by a test: the shared
  P-K1/P9 proof provenance (`gates/_provenienz._git_stand`) records the Git
  state proved or decided on with three READING git calls (`rev-parse HEAD`,
  `rev-parse --abbrev-ref HEAD`, `status --porcelain`) — it computes and
  judges nothing. A pure-Python SHA-256 over the installed package sources
  distinguishes different dirty code states. If git is unavailable, its
  fields carry the named value `unbekannt`, never a silent default. Any
  further subprocess import, any
  other command, and any process start via `os` turns
  `tests/test_fachspez_und_p9.py::test_subprozess_bleibt_auf_die_beweisprovenienz_beschraenkt`
  red.
- **Fail-fast, never silent**: no silent overwrite, no silent default. Doubt is
  a named state (`nicht_belegt`/`mehrdeutig`/`widerspruechlich`) or a hard
  error whose message names the way out.
- **Agents never decide** contradictions between sources. Provisional
  resolutions carry `vorlaeufig=true` and block every human acceptance.
- **Nodes** (`Knoten: klv/tg2015`) in every module and test docstring; the same
  IDs as the A-Box and gate P-K1. `code_index` must stay drift-free,
  `code_karte` finding-free.
- **Full suite before every commit** (`.venv/bin/python -m pytest`). The impact
  tool is informational — it never narrows what has to run. CI
  (`.github/workflows/tests.yml`) runs the full suite on every push and
  pull request. The mandatory `tests/test_pk1_fixture_e2e.py` job uses the
  versioned, anonymised `tests/fixtures/pk1_am4_minimal/` data and performs real
  extraction, formula checking and P-K1 from a fresh temporary case. The
  positive path in `tests/test_pk1_am4_beweisvertrag.py` continues through A-M4
  on the same fixture contract. Missing or hash-drifted fixture input is a
  hard failure, never a skip. Local and real case workspaces under `faelle/`
  remain gitignored and are not a prerequisite for a green suite.
- Direct dependencies pinned exactly (`pyproject.toml`), their transitive
  closure pinned in `requirements*.txt` (section 2); new dependencies only
  via ADR. Push is the human's job.

## Laufdaten: was Wegwerf ist und was sich wehrt

`runs/` ist **Wegwerf**: Jeder darf dort loeschen, nichts darin ist die
einzige Kopie von etwas Wichtigem. Was festgehalten werden soll, lebt an
zwei Orten mit eigenem Schutz:

* im **Fall** (`faelle/<fall>/` — `eingang/` und `entscheide/` sind
  unantastbar, `abgeleitet/` ist reproduzierbar), oder
* als **Abschluss** (`bestand.cli_abschluss`): festgeschriebene Staende
  schreiben sich selbst schreibgeschuetzt (0444) — ein `rm` ohne `-f`
  fragt nach, ein Ueberschreiben scheitert. Gegen `rm -rf` schuetzt kein
  Dateirecht; deshalb die Verhaltensregel: vor jedem Aufraeumen unter
  `runs/` pruefen, ob echte Laufdaten dort liegen — besser: sie liegen
  dort gar nicht erst.

Anlass ist ein realer Verlust: 2026-06-05 hat ein aufraeumendes
`rm -r runs` die Artefakte eines echten Laufs zerstoert.
