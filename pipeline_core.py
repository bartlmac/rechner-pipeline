from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List

from llm_client import build_openai_client
from manifest_model import ExportManifest
from prompt_builder import apply_placeholders, build_stuffed_inputs, read_text, write_text

import matrix_extractor as mx


_TEST_BLOCK_RE = re.compile(
    r"===FILE_START:\s*test_run_advanced\.py===\s*(.*?)\s*===FILE_END:\s*test_run_advanced\.py===",
    re.DOTALL,
)


def extract_test_run_advanced(llm_output: str) -> str | None:
    match = _TEST_BLOCK_RE.search(llm_output)
    if not match:
        return None
    return match.group(1).strip() + "\n"


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


class PipelineRunner:
    def __init__(self, script_dir: Path, options: PipelineOptions) -> None:
        self.script_dir = script_dir
        self.options = options
        self.prompt_main = script_dir / "Promt_excel_to_py.txt"
        self.prompt_test = script_dir / "Prompt_test.txt"
        self.out_dir = script_dir / mx.GENERATED_SUBDIR_NAME
        self.manifest_path = self.out_dir / "export_manifest.json"
        self.generated_dir = script_dir / "generated"
        self.test_py_path = self.generated_dir / "test_run_advanced.py"
        self.client = build_openai_client()

    def run(self) -> None:
        self._assert_required_files()
        manifest = self._load_or_export_manifest()
        if not self.options.skip_main_llm:
            self._run_main_llm(manifest)
        if not self.options.skip_test_llm:
            self._run_test_llm(manifest)
        if not self.options.skip_compare_run:
            self._run_compare()
        print("[DONE]")

    def _assert_required_files(self) -> None:
        for path in [self.prompt_main, self.prompt_test]:
            if not path.exists():
                raise FileNotFoundError(f"Missing: {path}")

    def _load_or_export_manifest(self) -> ExportManifest:
        if not self.options.skip_export:
            manifest_dict = mx.export_excel_infos(
                excel_path=mx.EXCEL_PATH,
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
        return manifest

    def _run_main_llm(self, manifest: ExportManifest) -> None:
        prompt_template = read_text(self.prompt_main)
        stuffed_inputs = build_stuffed_inputs(
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
                "INPUT_FILES": stuffed_inputs,
            },
        )

        debug_prompt_path = self.script_dir / "DEBUG_first_llm_prompt.txt"
        write_text(debug_prompt_path, final_prompt)
        print("\n[DEBUG] First LLM prompt written to:")
        print(debug_prompt_path)
        print(f"[DEBUG] Prompt length (chars): {len(final_prompt):,}\n")

        resp = self.client.responses.create(
            model=self.options.model,
            input=final_prompt,
            reasoning={"effort": self.options.reasoning_effort},
        )
        llm_output = resp.output_text
        written = mx.write_extracted_files_to_generated_dir(llm_output, self.script_dir)
        if written == 0:
            raise RuntimeError(
                "No files extracted from LLM output (missing FILE_START/FILE_END blocks)."
            )

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

    def _run_test_llm(self, manifest: ExportManifest) -> None:
        del manifest  # reserved for future metadata extensions
        prompt_template = read_text(self.prompt_test)
        test_inputs = self._build_test_inputs()
        table_values = [p for p in test_inputs if p.name.endswith("_table_values.csv")]
        scalar_json = [p for p in test_inputs if p.name.endswith("_scalar.json")]

        stuffed_inputs = build_stuffed_inputs(
            base_dir=self.script_dir,
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
                "INPUT_FILES": stuffed_inputs,
            },
        )

        debug_prompt_path = self.script_dir / "DEBUG_second_llm_prompt.txt"
        write_text(debug_prompt_path, final_prompt)
        print("\n[DEBUG] Second LLM prompt written to:")
        print(debug_prompt_path)
        print(f"[DEBUG] Prompt length (chars): {len(final_prompt):,}\n")

        resp = self.client.responses.create(
            model=self.options.model,
            input=final_prompt,
            reasoning={"effort": self.options.reasoning_effort},
        )
        llm_output = resp.output_text
        extracted = extract_test_run_advanced(llm_output)
        if extracted is None:
            raise RuntimeError("Could not find test_run_advanced.py block in LLM output.")
        write_text(self.test_py_path, extracted)

    def _run_compare(self) -> None:
        if not self.test_py_path.exists():
            raise FileNotFoundError(f"Missing test file: {self.test_py_path}")
        subprocess.run(
            [sys.executable, str(self.test_py_path)],
            cwd=str(self.generated_dir),
            check=False,
        )
