"""
Klassischer Pipeline-Runner ohne LangGraph.

Public API der Stufen ``prepare_manifest``, ``run_main_llm``, ``run_test_llm``
und ``run_compare`` ist bewusst öffentlich, damit der ``agentic`` Wrapper
sie als Service-Aufrufe verwenden kann (statt private Underscore-Methoden).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List

from rechner_pipeline.context.prompt_builder import (
    apply_placeholders,
    build_stuffed_inputs_with_metadata,
    read_text,
    write_text,
)
from rechner_pipeline.generate.output import (
    EXPECTED_MAIN_OUTPUT_FILES,
    validate_main_output_files,
    write_main_output_items_to_generated_dir,
)
from rechner_pipeline.models.manifest import (
    ExportManifest,
    ManifestWarning,
    PromptInputRecord,
    PromptRecord,
    text_sha256,
)
from rechner_pipeline.qa.security import (
    StaticSecurityError,
    raise_for_violations,
    scan_python_items,
    scan_python_paths,
    write_security_report,
)


GENERATED_SUBDIR_NAME = "info_from_excel"
_TEST_BLOCK_RE = re.compile(
    r"===FILE_START:\s*test_run_advanced\.py===\s*(.*?)\s*===FILE_END:\s*test_run_advanced\.py===",
    re.DOTALL,
)


def extract_test_run_advanced(llm_output: str) -> str | None:
    match = _TEST_BLOCK_RE.search(llm_output)
    if not match:
        return None
    return match.group(1).strip() + "\n"


def _append_repair_context(prompt: str, repair_context: str | None) -> str:
    if not repair_context:
        return prompt
    return (
        f"{prompt.rstrip()}\n\n"
        "## Agentic repair context\n\n"
        "The previous agentic attempt failed. Use the structured diagnostic "
        "context below to repair the next response while still following the "
        "original output contract exactly.\n\n"
        f"{repair_context.strip()}\n"
    )


@dataclass(frozen=True)
class PipelineOptions:
    model: str
    skip_export: bool
    skip_main_llm: bool
    skip_test_llm: bool
    skip_compare_run: bool
    main_max_chars_per_file: int
    main_max_total_chars: int
    test_max_chars_per_file: int
    test_max_total_chars: int
    reasoning_effort: str
    strict_manifest_warnings: bool = False


class PipelineRunner:
    def __init__(
        self,
        repo_root: Path,
        options: PipelineOptions,
        excel_path: Path | None = None,
    ) -> None:
        self.repo_root = repo_root
        self.options = options
        self.excel_path = excel_path or (repo_root / "examples" / "Tarifrechner_KLV.xlsm")
        self.prompts_dir = repo_root / "prompts" / "v1"
        self.prompt_main = self.prompts_dir / "excel_to_py.txt"
        self.prompt_test = self.prompts_dir / "test_advanced.txt"
        self.out_dir = repo_root / GENERATED_SUBDIR_NAME
        self.manifest_path = self.out_dir / "export_manifest.json"
        self.generated_dir = repo_root / "generated"
        self.test_py_path = self.generated_dir / "test_run_advanced.py"
        self.compare_result_path = self.generated_dir / "test_run_advanced_result.json"
        self.static_security_report_path = self.generated_dir / "static_security_report.json"
        self.run_dossier_path = self.generated_dir / "run_dossier.json"
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from rechner_pipeline.generate.client import build_openai_client

            self._client = build_openai_client(env_path=self.repo_root / ".env")
        return self._client

    def run(self) -> None:
        from rechner_pipeline.orchestrate.dossier import write_run_dossier

        manifest = None
        try:
            self.assert_required_files()
            manifest = self.prepare_manifest()
            if not self.options.skip_main_llm:
                manifest = self.run_main_llm(manifest)
            if not self.options.skip_test_llm:
                manifest = self.run_test_llm(manifest)
            if not self.options.skip_compare_run:
                self.run_compare()
            write_run_dossier(self, manifest=manifest, run_status="completed")
            print(f"[DOSSIER] {self.run_dossier_path}")
            print("[DONE]")
        except Exception:
            write_run_dossier(self, manifest=manifest, run_status="failed")
            print(f"[DOSSIER] {self.run_dossier_path}")
            raise

    def assert_required_files(self) -> None:
        for path in [self.prompt_main, self.prompt_test]:
            if not path.exists():
                raise FileNotFoundError(f"Missing: {path}")

    def prepare_manifest(self) -> ExportManifest:
        if not self.options.skip_export:
            from rechner_pipeline.extract.excel import export_excel_infos

            self.out_dir.mkdir(parents=True, exist_ok=True)
            manifest_dict = export_excel_infos(
                excel_path=self.excel_path,
                out_dir=self.out_dir,
                save_manifest_json=True,
            )
            manifest = ExportManifest.from_dict(manifest_dict)
        else:
            if not self.manifest_path.exists():
                raise FileNotFoundError(f"Manifest not found: {self.manifest_path}")
            manifest = ExportManifest.from_dict(
                json.loads(self.manifest_path.read_text(encoding="utf-8"))
            )

        if not manifest.llm_inputs:
            raise RuntimeError("manifest['llm_inputs'] is empty.")
        manifest = self._refresh_output_hashes(manifest)
        self._write_manifest(manifest)
        self._enforce_strict_manifest_warnings(manifest)
        return manifest

    def _write_manifest(self, manifest: ExportManifest) -> None:
        write_text(
            self.manifest_path,
            json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2),
        )

    def _load_latest_manifest(self, fallback: ExportManifest) -> ExportManifest:
        if not self.manifest_path.exists():
            return fallback
        return ExportManifest.from_dict(
            json.loads(self.manifest_path.read_text(encoding="utf-8"))
        )

    def _refresh_output_hashes(
        self,
        manifest: ExportManifest,
        extra_paths: List[Path] | None = None,
    ) -> ExportManifest:
        paths = [path for path in manifest.all_outputs if path != self.manifest_path]
        if extra_paths:
            paths.extend(extra_paths)
        return manifest.with_output_hashes(paths)

    def _enforce_strict_manifest_warnings(self, manifest: ExportManifest) -> None:
        if not self.options.strict_manifest_warnings:
            return
        blocking = manifest.strict_error_warnings()
        if not blocking:
            return
        formatted = "; ".join(
            f"{warning.code}: {warning.message}" for warning in blocking
        )
        raise RuntimeError(
            "Strict manifest warning policy failed. Blocking warnings: "
            f"{formatted}"
        )

    def _write_security_report_and_raise(
        self,
        *,
        checked_files: List[Path | str],
        violations,
    ) -> None:
        write_security_report(
            self.static_security_report_path,
            checked_files=checked_files,
            violations=violations,
        )
        if self.manifest_path.exists():
            manifest = ExportManifest.from_dict(
                json.loads(self.manifest_path.read_text(encoding="utf-8"))
            )
            manifest = self._refresh_output_hashes(
                manifest,
                extra_paths=[self.static_security_report_path],
            )
            self._write_manifest(manifest)
        raise_for_violations(violations)

    def _run_static_security_check_for_items(
        self,
        items: List[tuple[str, str]],
    ) -> None:
        checked_files = [name for name, _content in items if name.endswith(".py")]
        violations = scan_python_items(items)
        write_security_report(
            self.static_security_report_path,
            checked_files=checked_files,
            violations=violations,
        )
        if violations:
            self._write_security_report_and_raise(
                checked_files=checked_files,
                violations=violations,
            )

    def _generated_python_paths(self) -> List[Path]:
        if not self.generated_dir.exists():
            return []
        return sorted(self.generated_dir.glob("*.py"), key=lambda path: path.name)

    def run_static_security_check(self) -> None:
        checked_files = self._generated_python_paths()
        violations = scan_python_paths(checked_files)
        write_security_report(
            self.static_security_report_path,
            checked_files=checked_files,
            violations=violations,
        )
        if violations:
            self._write_security_report_and_raise(
                checked_files=checked_files,
                violations=violations,
            )

    def _prompt_warnings(self, stage: str, stuffed_inputs) -> List[ManifestWarning]:
        warnings: List[ManifestWarning] = []
        for item in stuffed_inputs.files:
            if item.truncated:
                warnings.append(
                    ManifestWarning(
                        code="prompt.file_truncated",
                        stage=stage,
                        message=(
                            f"Prompt input '{item.label}' was truncated by "
                            "max_chars_per_file."
                        ),
                        strict_error=True,
                        path=str(item.path),
                        details={
                            "label": item.label,
                            "original_chars": item.original_chars,
                            "included_chars": item.included_chars,
                        },
                    )
                )
        if stuffed_inputs.total_limit_reached:
            warnings.append(
                ManifestWarning(
                    code="prompt.total_limit_reached",
                    stage=stage,
                    message=(
                        "Prompt input assembly stopped because max_total_chars "
                        "would have been exceeded."
                    ),
                    strict_error=True,
                )
            )
        return warnings

    def _prompt_record(
        self,
        *,
        stage: str,
        template_path: Path,
        debug_prompt_path: Path,
        final_prompt: str,
        stuffed_inputs,
        llm_output: str | None = None,
    ) -> PromptRecord:
        return PromptRecord(
            stage=stage,
            template_path=str(template_path),
            debug_prompt_path=str(debug_prompt_path),
            prompt_chars=len(final_prompt),
            prompt_sha256=text_sha256(final_prompt),
            input_files=[
                PromptInputRecord(
                    path=str(item.path),
                    label=item.label,
                    original_chars=item.original_chars,
                    included_chars=item.included_chars,
                    original_sha256=item.original_sha256,
                    truncated=item.truncated,
                )
                for item in stuffed_inputs.files
            ],
            total_limit_reached=stuffed_inputs.total_limit_reached,
            output_chars=len(llm_output) if llm_output is not None else None,
            output_sha256=text_sha256(llm_output) if llm_output is not None else "",
        )

    def run_main_llm(
        self,
        manifest: ExportManifest,
        repair_context: str | None = None,
    ) -> ExportManifest:
        manifest = self._load_latest_manifest(manifest)
        prompt_template = read_text(self.prompt_main)
        stuffed_inputs = build_stuffed_inputs_with_metadata(
            base_dir=self.out_dir,
            files=manifest.llm_inputs,
            max_chars_per_file=self.options.main_max_chars_per_file,
            max_total_chars=self.options.main_max_total_chars,
        )

        final_prompt = apply_placeholders(
            prompt_template,
            {
                "PIPELINE_META": json.dumps(
                    {
                        "out_dir": str(self.out_dir),
                        "llm_inputs_count": len(manifest.llm_inputs),
                        "replacements": manifest.replacements,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                "INPUT_FILES": stuffed_inputs.text,
            },
        )
        final_prompt = _append_repair_context(final_prompt, repair_context)

        debug_prompt_path = self.repo_root / "DEBUG_first_llm_prompt.txt"
        write_text(debug_prompt_path, final_prompt)
        print("\n[DEBUG] First LLM prompt written to:")
        print(debug_prompt_path)
        print(f"[DEBUG] Prompt length (chars): {len(final_prompt):,}\n")

        manifest = manifest.with_warnings(
            self._prompt_warnings("main_llm", stuffed_inputs)
        )
        manifest = manifest.with_prompt_record(
            self._prompt_record(
                stage="main_llm",
                template_path=self.prompt_main,
                debug_prompt_path=debug_prompt_path,
                final_prompt=final_prompt,
                stuffed_inputs=stuffed_inputs,
            )
        )
        self._write_manifest(manifest)
        self._enforce_strict_manifest_warnings(manifest)

        resp = self.client.responses.create(
            model=self.options.model,
            input=final_prompt,
            reasoning={"effort": self.options.reasoning_effort},
        )
        llm_output = resp.output_text
        main_output_items = validate_main_output_files(llm_output)
        self._run_static_security_check_for_items(main_output_items)
        write_main_output_items_to_generated_dir(main_output_items, self.repo_root)
        generated_paths = [
            self.generated_dir / name for name in EXPECTED_MAIN_OUTPUT_FILES
        ]
        manifest = manifest.with_prompt_record(
            self._prompt_record(
                stage="main_llm",
                template_path=self.prompt_main,
                debug_prompt_path=debug_prompt_path,
                final_prompt=final_prompt,
                stuffed_inputs=stuffed_inputs,
                llm_output=llm_output,
            )
        )
        manifest = self._refresh_output_hashes(
            manifest,
            extra_paths=[*generated_paths, self.static_security_report_path],
        )
        self._write_manifest(manifest)
        self._enforce_strict_manifest_warnings(manifest)
        return manifest

    def _build_test_inputs(self) -> List[Path]:
        table_values = sorted(self.out_dir.glob("*_table_values.csv"), key=lambda p: p.name)
        scalar_json = sorted(self.out_dir.glob("*_scalar.json"), key=lambda p: p.name)
        core_py = [
            self.generated_dir / "actuarial.py",
            self.generated_dir / "commutation.py",
            self.generated_dir / "inputs.py",
            self.generated_dir / "params.py",
            self.generated_dir / "test_run.py",
        ]

        test_inputs: List[Path] = []
        test_inputs.extend(table_values)
        test_inputs.extend(scalar_json)
        test_inputs.extend([path for path in core_py if path.exists()])
        return test_inputs

    def run_test_llm(
        self,
        manifest: ExportManifest,
        repair_context: str | None = None,
    ) -> ExportManifest:
        manifest = self._load_latest_manifest(manifest)
        prompt_template = read_text(self.prompt_test)
        test_inputs = self._build_test_inputs()
        table_values = [p for p in test_inputs if p.name.endswith("_table_values.csv")]
        scalar_json = [p for p in test_inputs if p.name.endswith("_scalar.json")]

        stuffed_inputs = build_stuffed_inputs_with_metadata(
            base_dir=self.repo_root,
            files=test_inputs,
            max_chars_per_file=self.options.test_max_chars_per_file,
            max_total_chars=self.options.test_max_total_chars,
        )
        final_prompt = apply_placeholders(
            prompt_template,
            {
                "PIPELINE_META": json.dumps(
                    {
                        "info_from_excel_dir": str(self.out_dir),
                        "generated_dir": str(self.generated_dir),
                        "table_values_count": len(table_values),
                        "scalar_json_count": len(scalar_json),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                "INPUT_FILES": stuffed_inputs.text,
            },
        )
        final_prompt = _append_repair_context(final_prompt, repair_context)

        debug_prompt_path = self.repo_root / "DEBUG_second_llm_prompt.txt"
        write_text(debug_prompt_path, final_prompt)
        print("\n[DEBUG] Second LLM prompt written to:")
        print(debug_prompt_path)
        print(f"[DEBUG] Prompt length (chars): {len(final_prompt):,}\n")

        manifest = manifest.with_warnings(
            self._prompt_warnings("test_llm", stuffed_inputs)
        )
        manifest = manifest.with_prompt_record(
            self._prompt_record(
                stage="test_llm",
                template_path=self.prompt_test,
                debug_prompt_path=debug_prompt_path,
                final_prompt=final_prompt,
                stuffed_inputs=stuffed_inputs,
            )
        )
        self._write_manifest(manifest)
        self._enforce_strict_manifest_warnings(manifest)

        resp = self.client.responses.create(
            model=self.options.model,
            input=final_prompt,
            reasoning={"effort": self.options.reasoning_effort},
        )
        llm_output = resp.output_text
        extracted = extract_test_run_advanced(llm_output)
        if extracted is None:
            raise RuntimeError("Could not find test_run_advanced.py block in LLM output.")
        self._run_static_security_check_for_items(
            [("test_run_advanced.py", extracted)]
        )
        write_text(self.test_py_path, extracted)
        manifest = manifest.with_prompt_record(
            self._prompt_record(
                stage="test_llm",
                template_path=self.prompt_test,
                debug_prompt_path=debug_prompt_path,
                final_prompt=final_prompt,
                stuffed_inputs=stuffed_inputs,
                llm_output=llm_output,
            )
        )
        manifest = self._refresh_output_hashes(
            manifest,
            extra_paths=[self.test_py_path, self.static_security_report_path],
        )
        self._write_manifest(manifest)
        self._enforce_strict_manifest_warnings(manifest)
        return manifest

    def run_compare(self) -> None:
        if not self.test_py_path.exists():
            raise FileNotFoundError(f"Missing test file: {self.test_py_path}")
        try:
            self.run_static_security_check()
        except StaticSecurityError as exc:
            raise RuntimeError(
                "Static security check blocked generated test execution. "
                f"Structured report written to {self.static_security_report_path}"
            ) from exc
        command = [sys.executable, str(self.test_py_path)]
        completed = subprocess.run(
            command,
            cwd=str(self.generated_dir),
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.stdout:
            print(completed.stdout, end="")
        if completed.stderr:
            print(completed.stderr, end="", file=sys.stderr)

        result = {
            "test_file": str(self.test_py_path),
            "command": command,
            "cwd": str(self.generated_dir),
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "status": "passed" if completed.returncode == 0 else "failed",
        }
        write_text(
            self.compare_result_path,
            json.dumps(result, ensure_ascii=False, indent=2),
        )
        if self.manifest_path.exists():
            manifest = ExportManifest.from_dict(
                json.loads(self.manifest_path.read_text(encoding="utf-8"))
            )
            manifest = self._refresh_output_hashes(
                manifest,
                extra_paths=[
                    self.test_py_path,
                    self.compare_result_path,
                    self.static_security_report_path,
                ],
            )
            self._write_manifest(manifest)

        if completed.returncode != 0:
            raise RuntimeError(
                "Regression test failed with returncode "
                f"{completed.returncode}. Structured result written to "
                f"{self.compare_result_path}"
            )
