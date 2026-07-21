"""``extract`` command — turn one source document into the ``info_from_excel`` bundle.

Usage::

    python -m rechner_pipeline.toolbox.extract \\
        --repo-root . \\
        --input examples/Tarifrechner_KLV.xlsm \\
        --out-dir .tmp/klv_info \\
        --adapter excel \\
        --export-backend openpyxl

This is the source-neutral entry to the deterministic toolbox (§3.3, §4.2 steps
1-3 & 12). It selects an :class:`~rechner_pipeline.adapters.base.InputAdapter`,
cleans stale derived files from the out-dir so a re-run cannot inherit stale
``_compressed.csv`` / ``_scalar.json`` / ``_table_values.csv`` (§4.2 step 3), runs
the adapter, and emits the InputBundle coverage block, manifest path, artifact
counts, expectation coverage, warnings, and hashes as exactly one JSON object on
stdout.

Blocking failures all exit 10 (extraction / InputBundle failure): missing source,
unsupported adapter, unavailable dependency, a tripped strict manifest warning,
an invalid manifest, or an empty ``llm_inputs``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from rechner_pipeline.adapters.base import InputAdapter
from rechner_pipeline.adapters.excel import ExcelAdapter, ExcelAdapterError
from rechner_pipeline.models.bundle import InputBundle
from rechner_pipeline.toolbox._common import (
    Exit,
    ToolboxResult,
    add_request_json_arg,
    build_result,
    hash_files,
    log,
    merge_request_into_args,
    read_request_json,
    run_command,
    utc_now,
    write_gate_ledger,
)

GATE_VERSION = "1.0.0"
COMMAND = "extract"

#: Derived-artifact suffixes that must not survive a re-run (§4.2 step 3). These
#: are regenerated deterministically from the raw sheet CSVs; a stale copy left
#: in the out-dir would be silently reused (``compress_exported_csvs`` reuses an
#: existing ``_compressed.csv``) or globbed (``extract_all_pairs_in_info_dir``).
_STALE_DERIVED_SUFFIXES: tuple[str, ...] = (
    "_compressed.csv",
    "_scalar.json",
    "_table_values.csv",
)


def _error(code: str, message: str, **extra) -> dict:
    out = {"code": code, "message": message}
    out.update(extra)
    return out


def _clean_stale_derived(out_dir: Path) -> List[str]:
    """Remove stale derived files from ``out_dir`` before extraction (§4.2 step 3).

    Returns the repo-agnostic names of files that were removed. Only the
    deterministically-regenerated derived artifacts are removed; raw sheet CSVs,
    ``names_manager.csv``, VBA text, and the source workbook are left untouched.
    """
    removed: List[str] = []
    if not out_dir.is_dir():
        return removed
    for path in sorted(out_dir.iterdir()):
        if not path.is_file():
            continue
        if any(path.name.endswith(suffix) for suffix in _STALE_DERIVED_SUFFIXES):
            path.unlink()
            removed.append(path.name)
    return removed


def _select_adapter(adapter: str, source: Path, backend: str) -> InputAdapter:
    """Resolve the adapter id (or ``auto``) to a concrete adapter instance."""
    if adapter == "auto":
        if ExcelAdapter.supports(source):
            return ExcelAdapter(backend=backend)
        raise ExcelAdapterError(
            f"No adapter supports source {source.name!r} "
            f"(suffix {source.suffix!r}); pass --adapter explicitly."
        )
    if adapter == "excel":
        return ExcelAdapter(backend=backend)
    raise ExcelAdapterError(f"Unsupported adapter {adapter!r} (expected 'auto' or 'excel').")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.toolbox.extract",
        description="Extract one source document into the info_from_excel bundle.",
    )
    # Every mergeable flag uses default=None so --request-json can supply it.
    parser.add_argument("--repo-root", dest="repo_root", default=None)
    parser.add_argument("--input", dest="input", default=None)
    parser.add_argument("--out-dir", dest="out_dir", default=None)
    parser.add_argument(
        "--adapter", dest="adapter", default=None, choices=["auto", "excel"]
    )
    parser.add_argument(
        "--export-backend",
        dest="export_backend",
        default=None,
        choices=["openpyxl", "com"],
    )
    parser.add_argument(
        "--strict-manifest-warnings",
        dest="strict_manifest_warnings",
        action="store_true",
        default=None,
        help="Treat any strict_error manifest warning as a blocking failure (exit 10).",
    )
    parser.add_argument(
        "--diagnostics-dir",
        dest="diagnostics_dir",
        default=None,
        help="Directory to write the <command>.gate.json ledger entry into. "
        "Defaults to <out-dir>/diagnostics when omitted.",
    )
    add_request_json_arg(parser)
    return parser


def main(argv: Optional[List[str]] = None) -> ToolboxResult:
    started_at = utc_now()
    parser = _build_parser()
    args = parser.parse_args(argv)

    request = read_request_json(args.request_json)
    merge_request_into_args(args, request)

    # Defaults applied only after request merge (flags/request win over these).
    repo_root = Path(args.repo_root) if args.repo_root else Path.cwd()
    adapter_id = args.adapter or "auto"
    backend = args.export_backend or "openpyxl"
    strict = bool(args.strict_manifest_warnings)

    # Resolve the diagnostics dir for the §6.8.2 gate ledger. Default to
    # <out-dir>/diagnostics (the other gates' convention); falls back to the
    # cwd diagnostics dir when no out-dir is available (early usage errors).
    if args.diagnostics_dir:
        diagnostics_dir = Path(args.diagnostics_dir)
    elif args.out_dir:
        diagnostics_dir = Path(args.out_dir) / "diagnostics"
    else:
        diagnostics_dir = Path.cwd() / "diagnostics"

    def _finalize(result: ToolboxResult) -> ToolboxResult:
        """Write the gate-result ledger entry (side artifact) before returning.

        Called on BOTH pass and fail paths. A ledger-write failure must never
        mask the real command result, so it is logged and swallowed.
        """
        try:
            write_gate_ledger(
                result,
                diagnostics_dir,
                repo_root=repo_root,
                started_at=started_at,
                ended_at=utc_now(),
                command_line=argv if argv is not None else sys.argv[1:],
            )
        except Exception as exc:  # noqa: BLE001 — never let the ledger break the gate
            log(f"extract: gate-ledger write failed: {exc}")
        return result

    if not args.input:
        return _finalize(build_result(
            command=COMMAND,
            gate_version=GATE_VERSION,
            exit_code=Exit.EXTRACTION,
            errors=[_error("missing_input", "--input is required")],
            repair_hints=["Pass --input <path-to-source-document>."],
        ))
    if not args.out_dir:
        return _finalize(build_result(
            command=COMMAND,
            gate_version=GATE_VERSION,
            exit_code=Exit.EXTRACTION,
            errors=[_error("missing_out_dir", "--out-dir is required")],
            repair_hints=["Pass --out-dir <output-directory>."],
        ))

    source = Path(args.input)
    out_dir = Path(args.out_dir)

    if not source.exists():
        return _finalize(build_result(
            command=COMMAND,
            gate_version=GATE_VERSION,
            exit_code=Exit.EXTRACTION,
            errors=[
                _error(
                    "source_missing",
                    f"Source document does not exist: {source}",
                    path=str(source),
                )
            ],
            repair_hints=["Check the --input path; it must point to an existing file."],
        ))

    # Select adapter (unsupported adapter / no auto match -> blocking exit 10).
    try:
        adapter = _select_adapter(adapter_id, source, backend)
    except ExcelAdapterError as exc:
        return _finalize(build_result(
            command=COMMAND,
            gate_version=GATE_VERSION,
            exit_code=Exit.EXTRACTION,
            errors=[_error("unsupported_adapter", str(exc))],
            repair_hints=["Use --adapter excel for an Excel workbook."],
        ))

    # Clean/staged extraction (§4.2 step 3): drop stale derived files so a re-run
    # cannot inherit a stale _compressed.csv / _scalar.json / _table_values.csv.
    out_dir.mkdir(parents=True, exist_ok=True)
    removed = _clean_stale_derived(out_dir)
    if removed:
        log(f"Cleaned {len(removed)} stale derived file(s): {', '.join(removed)}")

    # Run the adapter. Dependency unavailability surfaces as RuntimeError from the
    # extractor's import helpers; an invalid/empty manifest surfaces as
    # ExcelAdapterError. Both are blocking extraction failures (exit 10).
    try:
        bundle: InputBundle = adapter.extract(source, out_dir)
    except FileNotFoundError as exc:
        return _finalize(build_result(
            command=COMMAND,
            gate_version=GATE_VERSION,
            exit_code=Exit.EXTRACTION,
            errors=[_error("source_missing", str(exc))],
            repair_hints=["Check the --input path; it must point to an existing file."],
        ))
    except ExcelAdapterError as exc:
        return _finalize(build_result(
            command=COMMAND,
            gate_version=GATE_VERSION,
            exit_code=Exit.EXTRACTION,
            errors=[_error("invalid_manifest", str(exc))],
            repair_hints=[
                "The extractor ran but produced an invalid/empty bundle; "
                "inspect stderr logs and the out-dir."
            ],
        ))
    except RuntimeError as exc:
        # _import_openpyxl / _import_pandas / _import_vba_parser /
        # _dispatch_excel_application raise RuntimeError when a dependency (or
        # Excel/pywin32 for the COM backend) is unavailable. Fail fast.
        return _finalize(build_result(
            command=COMMAND,
            gate_version=GATE_VERSION,
            exit_code=Exit.EXTRACTION,
            errors=[_error("dependency_unavailable", str(exc), backend=backend)],
            repair_hints=[
                "Install the required export dependency, or select a backend that "
                "is available on this host (the 'com' backend needs Windows + Excel "
                "+ pywin32)."
            ],
        ))

    # Structural validation of the bundle (invalid manifest / empty llm_inputs).
    bundle_errors = bundle.validate()
    manifest = bundle.manifest
    if manifest is None or not manifest.llm_inputs:
        bundle_errors.append("manifest.llm_inputs must be non-empty")
    if bundle_errors:
        return _finalize(build_result(
            command=COMMAND,
            gate_version=GATE_VERSION,
            exit_code=Exit.EXTRACTION,
            errors=[_error("invalid_manifest", e) for e in bundle_errors],
            repair_hints=["The produced bundle failed validation; see errors."],
        ))

    # Strict manifest warnings: a tripped strict_error warning blocks under
    # --strict-manifest-warnings (exit 10); otherwise warnings are reported only.
    strict_warnings = [w for w in manifest.warnings if w.strict_error]
    warning_dicts = [w.to_dict() for w in manifest.warnings]
    if strict and strict_warnings:
        return _finalize(build_result(
            command=COMMAND,
            gate_version=GATE_VERSION,
            exit_code=Exit.EXTRACTION,
            warnings=warning_dicts,
            errors=[
                _error(
                    "strict_manifest_warning",
                    f"{len(strict_warnings)} strict manifest warning(s) tripped "
                    "under --strict-manifest-warnings",
                )
            ],
            repair_hints=[
                "Resolve the strict_error warnings, or drop --strict-manifest-warnings."
            ],
        ))

    # Hashes: every llm_input plus the manifest JSON, keyed repo-relative.
    manifest_path = Path(bundle.manifest_path)
    hash_paths: List[Path] = [Path(p) for p in manifest.llm_inputs]
    hash_paths.append(manifest_path)
    try:
        output_hashes = hash_files(hash_paths, base=repo_root, missing_ok=True)
    except Exception as exc:  # defensive — hashing should not abort the result
        log(f"hashing failed: {exc}")
        output_hashes = {}

    # input_hashes: the genuine extraction INPUT — the source workbook (§6.8.2).
    # G0's ledger needs a non-empty input_hashes or dossier raises hashes.missing.
    # Keyed repo-relative (falls back to its own string when outside repo-root).
    try:
        input_hashes = hash_files([source], base=repo_root, missing_ok=True)
    except Exception as exc:  # defensive — hashing should not abort the result
        log(f"input hashing failed: {exc}")
        input_hashes = {}

    summary = {
        "input_bundle": bundle.coverage_block(),
        "expectation_coverage": bundle.expectation_coverage,
        "artifact_counts": {
            "sheet_csvs": len(manifest.sheet_csvs),
            "compressed_csvs": len(manifest.replacements),
            "vba_txts": len(manifest.vba_txts),
            "names_manager_csv": int(manifest.names_manager_csv is not None),
            "scalar_jsons": bundle.coverage_detail.scalar_files,
            "table_value_csvs": bundle.coverage_detail.table_files,
            "llm_inputs": len(manifest.llm_inputs),
            "all_outputs": len(manifest.all_outputs),
        },
        "cleaned_stale_derived": removed,
    }

    # Persist the InputBundle (incl. expectation_coverage + coverage block) as
    # ``<out-dir>/input_bundle.json`` (§6.8.5). The dossier reads this path to
    # learn the real expectation_coverage AUTOMATICALLY — without it, coverage
    # defaults to "none" and a false ``coverage.not_full`` open assumption blocks
    # acceptance. The coverage block (not the full bundle) is written so it does
    # not embed the in-memory manifest, keeps info_from_excel lean, and matches
    # what dossier/run_dossier consume. This is a derived artifact in --out-dir
    # (the info dir), NOT in --generated-dir, so it never trips G1's six-file
    # validate. ``input_bundle.json`` is not a gate input, so it breaks no gate.
    input_bundle_path = out_dir / "input_bundle.json"
    try:
        input_bundle_path.write_text(
            json.dumps(bundle.coverage_block(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        summary["input_bundle_path"] = str(input_bundle_path)
    except Exception as exc:  # defensive — persistence must not abort the result
        log(f"input_bundle persistence failed: {exc}")

    return _finalize(build_result(
        command=COMMAND,
        gate_version=GATE_VERSION,
        exit_code=Exit.OK,
        paths={
            "out_dir": bundle.out_dir,
            "manifest_path": bundle.manifest_path,
            "source_path": bundle.source_path,
            "llm_inputs": [str(p) for p in manifest.llm_inputs],
            "input_bundle": str(input_bundle_path),
        },
        summary=summary,
        input_hashes=input_hashes,
        output_hashes=output_hashes,
        warnings=warning_dicts,
    ))


if __name__ == "__main__":
    raise SystemExit(run_command(main))
