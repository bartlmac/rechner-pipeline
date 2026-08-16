"""Source-neutral console entry point for ``rechner-pipeline``.

This CLI is **deterministic and SDK-free**. It contains no LLM provider,
model, token, reasoning, or ``test_mode=llm`` surface: code generation and
self-repair are owned by the *agent* (the Claude/Copilot/Codex/OpenCode skill,
per ``build-vergleichsrechenkern``), while this CLI exposes only the
deterministic acceptance machinery — the deterministic toolbox gate suite.

Two things are offered:

* a top-level source-neutral surface (``--input``, ``--adapter``,
  ``--export-backend``, ``--strict-manifest-warnings``) that documents the
  deterministic gate flow and strict validation behaviour; and
* the ``assurance`` subcommand — the end-to-end gate orchestrator. It
  runs the existing toolbox gate commands IN ORDER over an already-generated
  ``--generated-dir`` and ends with a ``dossier`` acceptance verdict. It does
  NOT contain any gate logic itself and does NOT generate the six deliverables
  (that is the agent's job); it only drives and aggregates the gates.

Console script: ``rechner-pipeline = rechner_pipeline.cli:main`` (pyproject).

Knoten: system/cli
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable, List, Optional, Sequence

# The deterministic toolbox gate commands. Each exposes ``main(argv) ->
# ToolboxResult`` and is wrapped by ``run_command`` so that invoking it emits
# exactly one JSON object on stdout and returns the standard exit code. We
# import their ``main`` functions and run them through ``run_command`` so the
# orchestrator REUSES the existing gate implementations (no second gate path).
from rechner_pipeline.gates import _common
from rechner_pipeline.gates import (
    algebraic as _algebraic,
    conventions as _conventions,
    dossier as _dossier,
    extract as _extract,
    golden_master as _golden_master,
    roundtrip as _roundtrip,
    security as _security,
    validate as _validate,
)

PROG = "rechner-pipeline"

# --------------------------------------------------------------------------- #
# The ordered gate chain (extract -> ... -> dossier; deterministic toolbox).
#
# Each entry is (name, module-main, argv-builder). The argv-builder maps the
# shared assurance inputs onto the exact flags that gate command accepts — the
# gates do NOT share one uniform flag set (e.g. ``extract`` takes ``--out-dir``,
# ``security``/``conventions`` take only ``--generated-dir``/``--diagnostics-dir``),
# so each builder adapts the shared inputs to the real, EXISTING command flags.
# --------------------------------------------------------------------------- #


class _GateSpec:
    __slots__ = ("name", "main", "build_argv", "stop_on_fail", "skip_when")

    def __init__(
        self,
        name: str,
        main: Callable[[Optional[List[str]]], object],
        build_argv: Callable[["_AssuranceConfig"], List[str]],
        *,
        stop_on_fail: bool,
        skip_when: Optional[Callable[["_AssuranceConfig"], Optional[str]]] = None,
    ) -> None:
        self.name = name
        self.main = main
        self.build_argv = build_argv
        self.stop_on_fail = stop_on_fail
        # Returns a human reason string to skip the gate, or None to run it.
        self.skip_when = skip_when


def _gate_specs() -> List[_GateSpec]:
    """The gate chain in execution order (extract -> ... -> dossier).

    Stop/continue policy (documented, see ``assurance --help``):

    * ``extract`` and ``validate`` are PREREQUISITES — if either fails, the
      downstream gates cannot run meaningfully (no bundle / no compilable
      kernel), so the chain STOPS immediately and ``dossier`` is still run last
      to record the partial, blocked verdict.
    * every QA gate (``security`` .. ``roundtrip``) is CONTINUE-ON-FAIL: a
      failure is recorded in its ``*.gate.json`` ledger and the chain keeps
      going so the operator gets the FULL gate picture in one run, exactly as
      the dossier expects (it aggregates every gate result).
    * ``dossier`` ALWAYS runs last and produces the final mechanical-acceptance
      verdict by aggregating the ledger written by the preceding gates.
    """
    return [
        _GateSpec("extract", _extract.main, _argv_extract, stop_on_fail=True),
        _GateSpec("validate", _validate.main, _argv_validate, stop_on_fail=True),
        _GateSpec("security", _security.main, _argv_security, stop_on_fail=False),
        _GateSpec("conventions", _conventions.main, _argv_conventions, stop_on_fail=False),
        _GateSpec("golden_master", _golden_master.main, _argv_golden_master, stop_on_fail=False),
        _GateSpec(
            "algebraic",
            _algebraic.main,
            _argv_algebraic,
            stop_on_fail=False,
            # The algebraic gate (G6) is unknown-applicability without a product
            # QA contract; per the spec --qa-contract is optional on assurance.
            # When absent we SKIP it honestly (dossier then reports G6 missing)
            # rather than emit a bare usage error into the chain.
            skip_when=lambda c: (
                None if c.qa_contract else "no --qa-contract supplied"
            ),
        ),
        _GateSpec("roundtrip", _roundtrip.main, _argv_roundtrip, stop_on_fail=False),
        _GateSpec("dossier", _dossier.main, _argv_dossier, stop_on_fail=False),
    ]


class _AssuranceConfig:
    """Resolved inputs shared by every gate in the chain."""

    def __init__(self, ns: argparse.Namespace) -> None:
        self.repo_root = str(Path(ns.repo_root).resolve())
        self.input = str(Path(ns.input).resolve()) if ns.input else None
        self.generated_dir = str(Path(ns.generated_dir).resolve())
        self.info_dir = str(Path(ns.info_dir).resolve())
        self.diagnostics_dir = str(Path(ns.diagnostics_dir).resolve())
        self.adapter = ns.adapter
        self.export_backend = ns.export_backend
        self.strict_manifest_warnings = bool(ns.strict_manifest_warnings)
        self.qa_contract = str(Path(ns.qa_contract).resolve()) if ns.qa_contract else None
        self.max_attempts = ns.max_attempts


# --- per-gate argv builders (adapt shared inputs to each command's real flags) #


def _argv_extract(c: _AssuranceConfig) -> List[str]:
    # extract writes the InputBundle into the info dir (its ``--out-dir``).
    argv = [
        "--repo-root", c.repo_root,
        "--input", c.input or "",
        "--out-dir", c.info_dir,
        "--adapter", c.adapter,
        "--export-backend", c.export_backend,
        "--diagnostics-dir", c.diagnostics_dir,
    ]
    if c.strict_manifest_warnings:
        argv.append("--strict-manifest-warnings")
    return argv


def _argv_validate(c: _AssuranceConfig) -> List[str]:
    # validate (G1) MUST receive the shared --diagnostics-dir; otherwise its
    # ledger defaults to <generated-dir>/diagnostics and dossier (which scans the
    # shared dir) reports G1 'gate.missing'. It also pollutes --generated-dir.
    return [
        "--repo-root", c.repo_root,
        "--generated-dir", c.generated_dir,
        "--info-dir", c.info_dir,
        "--diagnostics-dir", c.diagnostics_dir,
    ]


def _argv_security(c: _AssuranceConfig) -> List[str]:
    return ["--generated-dir", c.generated_dir, "--diagnostics-dir", c.diagnostics_dir]


def _argv_conventions(c: _AssuranceConfig) -> List[str]:
    return ["--generated-dir", c.generated_dir, "--diagnostics-dir", c.diagnostics_dir]


def _argv_golden_master(c: _AssuranceConfig) -> List[str]:
    return [
        "--repo-root", c.repo_root,
        "--generated-dir", c.generated_dir,
        "--info-dir", c.info_dir,
        "--diagnostics-dir", c.diagnostics_dir,
    ]


def _argv_algebraic(c: _AssuranceConfig) -> List[str]:
    argv = [
        "--repo-root", c.repo_root,
        "--generated-dir", c.generated_dir,
        "--info-dir", c.info_dir,
        "--diagnostics-dir", c.diagnostics_dir,
    ]
    if c.qa_contract:
        argv += ["--qa-contract", c.qa_contract]
    return argv


def _argv_roundtrip(c: _AssuranceConfig) -> List[str]:
    argv = [
        "--repo-root", c.repo_root,
        "--generated-dir", c.generated_dir,
        "--info-dir", c.info_dir,
        "--diagnostics-dir", c.diagnostics_dir,
    ]
    # G7 check 2 (re-extraction stability) needs the original source document.
    if c.input:
        argv += ["--input", c.input]
    return argv


def _argv_dossier(c: _AssuranceConfig) -> List[str]:
    return [
        "--repo-root", c.repo_root,
        "--generated-dir", c.generated_dir,
        "--info-dir", c.info_dir,
        "--diagnostics-dir", c.diagnostics_dir,
    ]


# --------------------------------------------------------------------------- #
# assurance orchestrator
# --------------------------------------------------------------------------- #


def _resolve_fall_defaults(ns: argparse.Namespace) -> Optional[str]:
    """Map a Fall-Arbeitsbereich onto the chain inputs (explicit flags win).

    Returns an error message (usage/integrity) or None. ``--fall`` is
    always validated as a real workspace and its Eingang is always
    integrity-checked BEFORE anything runs — also when an explicit
    ``--input`` is given, because the run still writes into that
    workspace and its dossier would claim the case as its context.
    """
    if ns.fall is None:
        if ns.quelle is not None:
            return "--quelle setzt --fall voraus"
        fehlend = [flag for flag, wert in (
            ("--generated-dir", ns.generated_dir),
            ("--info-dir", ns.info_dir),
            ("--diagnostics-dir", ns.diagnostics_dir),
        ) if wert is None]
        if fehlend:
            return ("ohne --fall sind erforderlich: " + ", ".join(fehlend))
        return None
    from rechner_pipeline import fall as fall_mod

    fall_pfad = Path(ns.fall)
    v = fall_mod.verzeichnisse(fall_pfad)
    try:
        # Kein Lauf auf einem Pfad, der kein Arbeitsbereich ist: sonst
        # entstuende unter beliebigen Verzeichnissen ein Pseudo-Fall.
        fall_mod.status(fall_pfad)
        if ns.quelle is not None:
            quelle = fall_mod.eingang_datei(fall_pfad, ns.quelle)
            if ns.input is None:
                ns.input = str(quelle)
        elif ns.input is None:
            return ("--fall braucht --quelle NAME (registrierte "
                    "Eingangsdatei) oder ein explizites --input")
        else:
            fehler = fall_mod.pruefen(fall_pfad)
            if fehler:
                return ("Eingang verletzt das Register — kein Lauf auf "
                        "unklarem Eingang: " + "; ".join(fehler))
    except fall_mod.FallFehler as exc:
        return str(exc)
    if ns.generated_dir is None:
        ns.generated_dir = str(v["generated_dir"])
    if ns.info_dir is None:
        ns.info_dir = str(v["info_dir"])
    if ns.diagnostics_dir is None:
        ns.diagnostics_dir = str(v["diagnostics_dir"])
    # Die Gate-Kette verlangt, dass der InputBundle-Ordner unter
    # --repo-root liegt (G5/G7 brechen sonst mitten im Lauf ab). Lieber
    # hier fail-fast mit einer Anweisung als ein halb gelaufener Fall.
    repo_root = Path(ns.repo_root).resolve()
    info_dir = Path(ns.info_dir).resolve()
    if repo_root not in info_dir.parents and info_dir != repo_root:
        return (
            f"Fall-Arbeitsbereich liegt ausserhalb von --repo-root "
            f"({info_dir} nicht unter {repo_root}) — die Gate-Kette "
            "verlangt den InputBundle-Ordner unterhalb der Repo-Wurzel "
            "(G5/G7). Bis das aufgeloest ist: --repo-root auf ein "
            "Verzeichnis setzen, das den Fall enthaelt, oder den Fall "
            "unterhalb der Repo-Wurzel anlegen."
        )
    return None


def _run_assurance(ns: argparse.Namespace) -> int:
    """Run the full gate chain in order and return an aggregate exit code.

    Each gate is executed through ``rechner_pipeline.gates._common.run_command``
    so it behaves EXACTLY as ``python -m rechner_pipeline.gates.<cmd>`` would:
    it emits its single JSON result object on stdout, writes its ``*.gate.json``
    ledger into the shared ``--diagnostics-dir``, and returns its standard exit
    code. ``assurance`` reads each exit code, applies the stop/continue policy,
    and finishes with ``dossier`` (the acceptance verdict). The aggregate exit
    code is the dossier exit code if it ran, else the first blocking prerequisite
    failure — so a non-zero ``assurance`` exit is always honest and never a
    downgraded warning.
    """
    fehler = _resolve_fall_defaults(ns)
    if fehler is not None:
        _log(f"assurance: {fehler}")
        return 2
    config = _AssuranceConfig(ns)

    # Ensure the shared dirs exist so each gate's ledger lands in one place.
    Path(config.diagnostics_dir).mkdir(parents=True, exist_ok=True)
    Path(config.info_dir).mkdir(parents=True, exist_ok=True)

    specs = _gate_specs()
    results: list[tuple[str, int]] = []
    dossier_exit: Optional[int] = None
    stopped_early = False

    _log(f"assurance: repo_root={config.repo_root}")
    _log(f"assurance: input={config.input}")
    _log(f"assurance: generated_dir={config.generated_dir}")
    _log(f"assurance: info_dir={config.info_dir}")
    _log(f"assurance: diagnostics_dir={config.diagnostics_dir}")
    _log(f"assurance: max_attempts={config.max_attempts}")

    for spec in specs:
        is_dossier = spec.name == "dossier"

        if stopped_early and not is_dossier:
            # A prerequisite failed: skip the QA gates but still reach dossier so
            # the partial run produces an honest blocked verdict.
            _log(f"assurance: SKIP {spec.name} (prerequisite failed)")
            continue

        if spec.skip_when is not None:
            reason = spec.skip_when(config)
            if reason:
                _log(f"assurance: SKIP {spec.name} ({reason})")
                continue

        argv = spec.build_argv(config)
        _log(f"assurance: --> {spec.name}")
        # run_command emits the gate's single JSON object on stdout and returns
        # its standard exit code. We do not reimplement any gate logic.
        exit_code = _common.run_command(spec.main, argv)
        results.append((spec.name, exit_code))
        _log(f"assurance: <-- {spec.name} exit={exit_code}")

        if is_dossier:
            dossier_exit = exit_code
            continue

        if exit_code != _common.Exit.OK and spec.stop_on_fail:
            _log(
                f"assurance: prerequisite gate {spec.name!r} failed (exit {exit_code}); "
                "stopping the QA chain and running dossier to record the blocked verdict."
            )
            stopped_early = True

    # Aggregate exit code: dossier verdict if it ran; else the first blocking
    # prerequisite failure; else OK.
    if dossier_exit is not None:
        aggregate = dossier_exit
    else:
        aggregate = next(
            (code for _name, code in results if code != _common.Exit.OK),
            _common.Exit.OK,
        )

    summary = ", ".join(f"{name}={code}" for name, code in results)
    _log(f"assurance: gate results: {summary}")
    _log(f"assurance: aggregate exit={aggregate}")
    return aggregate


# --------------------------------------------------------------------------- #
# argument parsing
# --------------------------------------------------------------------------- #


_TOP_DESCRIPTION = """\
Deterministic, SDK-free actuarial migration acceptance CLI.

This tool runs the DETERMINISTIC gate suite that decides whether an
already-generated comparison kernel is acceptable. Code generation and
self-repair are owned by the migration AGENT (a CLI skill), NOT by this tool:
there is no model/provider/token/reasoning surface and no LLM acceptance path.

Source-neutral inputs:
  --input PATH                 source document to extract (Excel today; the
                               adapter seam keeps other sources future-proof)
  --adapter auto|excel         input adapter (default: auto)
  --export-backend openpyxl|com
                               extraction backend (default: openpyxl, the
                               deterministic platform-neutral baseline; 'com'
                               needs Windows + Excel)
  --strict-manifest-warnings   treat strict_error manifest warnings as blocking

Run the full deterministic acceptance chain with the 'assurance' subcommand:
  extract -> validate -> security -> conventions -> golden_master ->
  algebraic -> roundtrip -> dossier

Strict validation: every gate fails fast with a standard non-zero exit code;
a non-zero exit is BLOCKING and is never downgraded to a warning.
"""


def _build_top_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description=_TOP_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Source-neutral top-level options (informational surface + future direct
    # extract; the heavy lifting is the deterministic toolbox / 'assurance').
    parser.add_argument(
        "--input",
        dest="input",
        default=None,
        help="Path to the source document to migrate (source-neutral).",
    )
    parser.add_argument(
        "--excel",
        dest="excel",
        default=None,
        help="Compatibility ALIAS for --input (a source Excel workbook).",
    )
    parser.add_argument(
        "--adapter",
        dest="adapter",
        default="auto",
        choices=["auto", "excel"],
        help="Input adapter (default: auto).",
    )
    parser.add_argument(
        "--export-backend",
        dest="export_backend",
        default="openpyxl",
        choices=["openpyxl", "com"],
        help=(
            "Extraction backend: openpyxl (default, deterministic, no Excel) or "
            "com (Windows + Excel only)."
        ),
    )
    parser.add_argument(
        "--strict-manifest-warnings",
        dest="strict_manifest_warnings",
        action="store_true",
        help="Treat strict_error manifest warnings as blocking failures.",
    )

    subparsers = parser.add_subparsers(dest="subcommand", metavar="<command>")
    _add_assurance_subparser(subparsers)
    return parser


_ASSURANCE_DESCRIPTION = """\
Run the full deterministic gate suite IN ORDER over an already-generated kernel.

Chain (each step invokes the EXISTING toolbox command; no gate logic lives here):
  extract -> validate -> security -> conventions -> golden_master ->
  algebraic -> roundtrip -> dossier

All gates share one --diagnostics-dir; each writes its single JSON result to
stdout and its <command>.gate.json ledger into that dir. 'dossier' aggregates
the ledger into the final mechanical-acceptance verdict and runs last.

Stop/continue policy:
  * extract and validate are PREREQUISITES; if either fails the QA gates are
    skipped, but 'dossier' still runs to record an honest blocked verdict.
  * security..roundtrip are CONTINUE-ON-FAIL so one run yields the full picture.
  * the aggregate exit code is the dossier exit code (else the first blocking
    prerequisite failure). Non-zero is BLOCKING.

NOTE: 'assurance' does NOT generate the six deliverables — that is the agent's
job (build-vergleichsrechenkern). It runs the gates over --generated-dir.
"""


def _add_assurance_subparser(subparsers: argparse._SubParsersAction) -> None:
    ap = subparsers.add_parser(
        "assurance",
        help="Run the full deterministic gate suite and produce the dossier verdict.",
        description=_ASSURANCE_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--repo-root", dest="repo_root", default=".",
                    help="Repository root (default: .).")
    ap.add_argument("--fall", dest="fall", default=None,
                    help="Fall-Arbeitsbereich (see rechner_pipeline.fall): input "
                         "comes from its registered eingang/, outputs go to "
                         "abgeleitet/. Explicit flags below override.")
    ap.add_argument("--quelle", dest="quelle", default=None,
                    help="Name of the registered eingang file to extract "
                         "(requires --fall; integrity-checked before the run).")
    ap.add_argument("--input", dest="input", default=None,
                    help="Source document to extract (passed to the extract gate).")
    ap.add_argument("--generated-dir", dest="generated_dir", default=None,
                    help="Directory holding the already-generated kernel files "
                         "(required unless --fall is given).")
    ap.add_argument("--info-dir", dest="info_dir", default=None,
                    help="InputBundle dir (extract writes here; gates read it; "
                         "required unless --fall is given).")
    ap.add_argument("--diagnostics-dir", dest="diagnostics_dir", default=None,
                    help="Shared dir for every gate's <command>.gate.json ledger "
                         "(required unless --fall is given).")
    ap.add_argument("--qa-contract", dest="qa_contract", default=None,
                    help="Optional QA contract for the algebraic gate.")
    ap.add_argument("--max-attempts", dest="max_attempts", type=int, default=4,
                    help="Bounded-repair budget recorded for the run (default: 4).")
    ap.add_argument("--adapter", dest="adapter", default="auto",
                    choices=["auto", "excel"], help="Input adapter (default: auto).")
    ap.add_argument("--export-backend", dest="export_backend", default="openpyxl",
                    choices=["openpyxl", "com"], help="Extraction backend (default: openpyxl).")
    ap.add_argument("--strict-manifest-warnings", dest="strict_manifest_warnings",
                    action="store_true",
                    help="Treat strict_error manifest warnings as blocking.")
    ap.set_defaults(_handler=_run_assurance)


def _log(message: str) -> None:
    """Human log to stderr (stdout is reserved for the gates' JSON)."""
    print(message, file=sys.stderr)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Console entry point. Returns a process exit code.

    With no subcommand, prints the source-neutral usage (deterministic gate flow
    + strict validation) and exits 2 (usage/configuration) so the operator
    is pointed at 'assurance' or the toolbox commands. With 'assurance', runs the
    full gate chain and returns the aggregate exit code.
    """
    if argv is None:
        argv = sys.argv[1:]

    parser = _build_top_parser()
    ns = parser.parse_args(list(argv))

    # Compatibility alias: --excel fills --input when --input was not given.
    if getattr(ns, "excel", None) and not getattr(ns, "input", None):
        ns.input = ns.excel

    handler = getattr(ns, "_handler", None)
    if handler is not None:
        return handler(ns)

    # No subcommand: deterministic-CLI usage, no SDK acceptance path advertised.
    parser.print_help(sys.stderr)
    _log("")
    _log("No subcommand given. Run 'rechner-pipeline assurance --help' for the "
         "deterministic gate orchestrator, or invoke a single gate via "
         "'python -m rechner_pipeline.gates.<command>'.")
    return _common.Exit.USAGE


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
