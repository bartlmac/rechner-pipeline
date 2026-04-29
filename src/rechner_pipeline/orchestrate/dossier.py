from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from rechner_pipeline.models.manifest import ExportManifest, file_sha256


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path_record(path: Path) -> Dict[str, Any]:
    record: Dict[str, Any] = {"path": str(path), "exists": path.exists()}
    if path.exists() and path.is_file():
        record["bytes"] = path.stat().st_size
        record["sha256"] = file_sha256(path)
    return record


def _read_json(path: Path) -> Dict[str, Any] | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"read_error": f"{exc.__class__.__name__}: {exc}"}
    return loaded if isinstance(loaded, dict) else {"value": loaded}


def _excerpt(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n... <truncated>"


def _options_dict(options: Any) -> Dict[str, Any]:
    keys = (
        "model",
        "skip_export",
        "skip_main_llm",
        "skip_test_llm",
        "skip_compare_run",
        "main_max_chars_per_file",
        "main_max_total_chars",
        "test_max_chars_per_file",
        "test_max_total_chars",
        "reasoning_effort",
        "strict_manifest_warnings",
    )
    return {key: getattr(options, key) for key in keys if hasattr(options, key)}


def _load_manifest(path: Path) -> ExportManifest | None:
    if not path.exists():
        return None
    return ExportManifest.from_dict(json.loads(path.read_text(encoding="utf-8")))


def _manifest_summary(manifest: ExportManifest | None, manifest_path: Path) -> Dict[str, Any]:
    if manifest is None:
        return {"path": str(manifest_path), "exists": False}
    return {
        "path": str(manifest_path),
        "exists": True,
        "out_dir": str(manifest.out_dir),
        "sheet_csv_count": len(manifest.sheet_csvs),
        "vba_txt_count": len(manifest.vba_txts),
        "names_manager_csv": (
            str(manifest.names_manager_csv) if manifest.names_manager_csv else ""
        ),
        "llm_input_count": len(manifest.llm_inputs),
        "all_output_count": len(manifest.all_outputs),
        "warning_count": len(manifest.warnings),
        "prompt_run_count": len(manifest.prompt_runs),
        "output_hash_count": len(manifest.output_hashes),
    }


def _prompt_hashes(manifest: ExportManifest | None) -> List[Dict[str, Any]]:
    if manifest is None:
        return []
    return [
        {
            "stage": item.stage,
            "template_path": item.template_path,
            "debug_prompt_path": item.debug_prompt_path,
            "prompt_chars": item.prompt_chars,
            "prompt_sha256": item.prompt_sha256,
            "output_chars": item.output_chars,
            "output_sha256": item.output_sha256,
            "input_file_count": len(item.input_files),
            "total_limit_reached": item.total_limit_reached,
            "truncated_input_files": [
                input_file.path
                for input_file in item.input_files
                if input_file.truncated
            ],
        }
        for item in manifest.prompt_runs
    ]


def _manifest_outputs(manifest: ExportManifest | None) -> Dict[str, Any]:
    if manifest is None:
        return {"all_outputs": [], "output_hashes": []}
    return {
        "all_outputs": [str(path) for path in manifest.all_outputs],
        "output_hashes": [item.to_dict() for item in manifest.output_hashes],
    }


def _generated_files(generated_dir: Path, excluded: Iterable[Path]) -> List[Dict[str, Any]]:
    excluded_paths = {path.resolve() for path in excluded if path.exists()}
    if not generated_dir.exists():
        return []
    records: List[Dict[str, Any]] = []
    for path in sorted(generated_dir.rglob("*"), key=lambda item: str(item)):
        if not path.is_file():
            continue
        if path.resolve() in excluded_paths:
            continue
        records.append(_path_record(path))
    return records


def _test_summary(compare_result_path: Path) -> Dict[str, Any]:
    payload = _read_json(compare_result_path)
    if payload is None:
        return {"status": "not_run", "result_path": str(compare_result_path)}
    summary = {
        "status": payload.get("status", "unknown"),
        "result_path": str(compare_result_path),
        "returncode": payload.get("returncode"),
        "test_file": payload.get("test_file", ""),
        "command": payload.get("command", []),
        "cwd": payload.get("cwd", ""),
    }
    if "stdout" in payload:
        summary["stdout_excerpt"] = _excerpt(str(payload.get("stdout", "")))
    if "stderr" in payload:
        summary["stderr_excerpt"] = _excerpt(str(payload.get("stderr", "")))
    if "read_error" in payload:
        summary["read_error"] = payload["read_error"]
    return summary


def _warnings(manifest: ExportManifest | None) -> List[Dict[str, Any]]:
    if manifest is None:
        return []
    return [warning.to_dict() for warning in manifest.warnings]


def _open_assumptions(
    *,
    runner: Any,
    manifest: ExportManifest | None,
    test_summary: Dict[str, Any],
    human_review_required: bool,
) -> List[Dict[str, Any]]:
    assumptions: List[Dict[str, Any]] = []
    options = runner.options

    if getattr(options, "skip_export", False):
        assumptions.append(
            {
                "code": "pipeline.skip_export",
                "message": "Excel export was skipped; manifest data may originate from an earlier run.",
            }
        )
    if getattr(options, "skip_main_llm", False):
        assumptions.append(
            {
                "code": "pipeline.skip_main_llm",
                "message": "Main LLM generation was skipped; generated implementation files may be pre-existing.",
            }
        )
    if getattr(options, "skip_test_llm", False):
        assumptions.append(
            {
                "code": "pipeline.skip_test_llm",
                "message": "Test LLM generation was skipped; generated advanced test file may be pre-existing.",
            }
        )
    if getattr(options, "skip_compare_run", False):
        assumptions.append(
            {
                "code": "pipeline.skip_compare_run",
                "message": "Compare/test execution was skipped; no fresh runtime validation is recorded.",
            }
        )

    if manifest is None:
        assumptions.append(
            {
                "code": "manifest.missing",
                "message": "No export manifest was available for this dossier.",
            }
        )
    else:
        for warning in manifest.warnings:
            assumptions.append(
                {
                    "code": f"manifest_warning.{warning.code}",
                    "message": warning.message,
                    "stage": warning.stage,
                    "path": warning.path,
                    "strict_error": warning.strict_error,
                }
            )
        for prompt_run in manifest.prompt_runs:
            if not prompt_run.output_sha256:
                assumptions.append(
                    {
                        "code": "prompt.output_hash_missing",
                        "message": (
                            "Prompt metadata exists without an output hash; "
                            f"stage '{prompt_run.stage}' may not have completed."
                        ),
                        "stage": prompt_run.stage,
                    }
                )

    if test_summary.get("status") == "not_run" and not getattr(
        options, "skip_compare_run", False
    ):
        assumptions.append(
            {
                "code": "compare.result_missing",
                "message": "No compare/test result file was available.",
            }
        )
    if test_summary.get("status") == "failed":
        assumptions.append(
            {
                "code": "compare.failed",
                "message": "Generated test execution failed and requires human review.",
                "returncode": test_summary.get("returncode"),
            }
        )

    generated_python = list(runner.generated_dir.glob("*.py"))
    if generated_python and not runner.static_security_report_path.exists():
        assumptions.append(
            {
                "code": "security_report.missing",
                "message": "Generated Python files exist without a static security report.",
            }
        )

    if human_review_required:
        assumptions.append(
            {
                "code": "human_review.required",
                "message": "Agentic orchestration ended in a human-review handoff.",
            }
        )

    return assumptions


def build_run_dossier(
    runner: Any,
    *,
    manifest: ExportManifest | None = None,
    run_status: str,
    human_review_required: bool = False,
    agentic_state: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    if manifest is None:
        manifest = _load_manifest(runner.manifest_path)

    run_dossier_path = getattr(
        runner,
        "run_dossier_path",
        runner.generated_dir / "run_dossier.json",
    )
    test_summary = _test_summary(runner.compare_result_path)
    agentic_state = agentic_state or {}
    diagnostics_path = agentic_state.get("agentic_diagnostics_path") or str(
        runner.generated_dir / "agentic_diagnostics.json"
    )

    return {
        "schema_version": 1,
        "created_at": _utc_now(),
        "run": {
            "status": run_status,
            "human_review_required": human_review_required,
            "repo_root": str(runner.repo_root),
            "excel_path": str(runner.excel_path),
            "options": _options_dict(runner.options),
        },
        "artifacts": {
            "run_dossier": str(run_dossier_path),
            "manifest": _path_record(runner.manifest_path),
            "static_security_report": _path_record(runner.static_security_report_path),
            "compare_result": _path_record(runner.compare_result_path),
            "agentic_diagnostics": _path_record(Path(diagnostics_path)),
            "agentic_repair_artifacts": dict(agentic_state.get("repair_artifacts", {})),
        },
        "manifest": _manifest_summary(manifest, runner.manifest_path),
        "prompt_hashes": _prompt_hashes(manifest),
        "outputs": _manifest_outputs(manifest),
        "generated_files": _generated_files(
            runner.generated_dir,
            excluded=[run_dossier_path],
        ),
        "test_summary": test_summary,
        "warnings": _warnings(manifest),
        "open_assumptions": _open_assumptions(
            runner=runner,
            manifest=manifest,
            test_summary=test_summary,
            human_review_required=human_review_required,
        ),
    }


def write_run_dossier(
    runner: Any,
    *,
    manifest: ExportManifest | None = None,
    run_status: str,
    human_review_required: bool = False,
    agentic_state: Dict[str, Any] | None = None,
) -> Path:
    path = getattr(runner, "run_dossier_path", runner.generated_dir / "run_dossier.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    dossier = build_run_dossier(
        runner,
        manifest=manifest,
        run_status=run_status,
        human_review_required=human_review_required,
        agentic_state=agentic_state,
    )
    path.write_text(json.dumps(dossier, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
