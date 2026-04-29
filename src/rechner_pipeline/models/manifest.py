from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, Iterable, List


def text_sha256(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    h = sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class ManifestWarning:
    code: str
    stage: str
    message: str
    strict_error: bool
    path: str = ""
    details: Dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ManifestWarning":
        return cls(
            code=str(data.get("code", "")),
            stage=str(data.get("stage", "")),
            message=str(data.get("message", "")),
            strict_error=bool(data.get("strict_error", False)),
            path=str(data.get("path", "")),
            details=dict(data.get("details") or {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "code": self.code,
            "stage": self.stage,
            "message": self.message,
            "strict_error": self.strict_error,
        }
        if self.path:
            out["path"] = self.path
        if self.details:
            out["details"] = self.details
        return out


@dataclass(frozen=True)
class PromptInputRecord:
    path: str
    label: str
    original_chars: int
    included_chars: int
    original_sha256: str
    truncated: bool

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PromptInputRecord":
        return cls(
            path=str(data.get("path", "")),
            label=str(data.get("label", "")),
            original_chars=int(data.get("original_chars", 0)),
            included_chars=int(data.get("included_chars", 0)),
            original_sha256=str(data.get("original_sha256", "")),
            truncated=bool(data.get("truncated", False)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "label": self.label,
            "original_chars": self.original_chars,
            "included_chars": self.included_chars,
            "original_sha256": self.original_sha256,
            "truncated": self.truncated,
        }


@dataclass(frozen=True)
class PromptRecord:
    stage: str
    template_path: str
    debug_prompt_path: str
    prompt_chars: int
    prompt_sha256: str
    input_files: List[PromptInputRecord]
    total_limit_reached: bool
    output_chars: int | None = None
    output_sha256: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PromptRecord":
        output_chars_raw = data.get("output_chars")
        return cls(
            stage=str(data.get("stage", "")),
            template_path=str(data.get("template_path", "")),
            debug_prompt_path=str(data.get("debug_prompt_path", "")),
            prompt_chars=int(data.get("prompt_chars", 0)),
            prompt_sha256=str(data.get("prompt_sha256", "")),
            input_files=[
                PromptInputRecord.from_dict(item)
                for item in data.get("input_files", [])
            ],
            total_limit_reached=bool(data.get("total_limit_reached", False)),
            output_chars=int(output_chars_raw) if output_chars_raw is not None else None,
            output_sha256=str(data.get("output_sha256", "")),
        )

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "stage": self.stage,
            "template_path": self.template_path,
            "debug_prompt_path": self.debug_prompt_path,
            "prompt_chars": self.prompt_chars,
            "prompt_sha256": self.prompt_sha256,
            "input_files": [item.to_dict() for item in self.input_files],
            "total_limit_reached": self.total_limit_reached,
        }
        if self.output_chars is not None:
            out["output_chars"] = self.output_chars
        if self.output_sha256:
            out["output_sha256"] = self.output_sha256
        return out


@dataclass(frozen=True)
class FileHashRecord:
    path: str
    bytes: int
    sha256: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileHashRecord":
        return cls(
            path=str(data.get("path", "")),
            bytes=int(data.get("bytes", 0)),
            sha256=str(data.get("sha256", "")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "bytes": self.bytes,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class ExportManifest:
    out_dir: Path
    sheet_csvs: List[Path]
    vba_txts: List[Path]
    names_manager_csv: Path | None
    replacements: Dict[str, str]
    llm_inputs: List[Path]
    all_outputs: List[Path]
    warnings: List[ManifestWarning]
    prompt_runs: List[PromptRecord]
    output_hashes: List[FileHashRecord]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExportManifest":
        nm = data.get("names_manager_csv") or ""
        return cls(
            out_dir=Path(data["out_dir"]),
            sheet_csvs=[Path(p) for p in data.get("sheet_csvs", [])],
            vba_txts=[Path(p) for p in data.get("vba_txts", [])],
            names_manager_csv=Path(nm) if nm else None,
            replacements=dict(data.get("replacements", {})),
            llm_inputs=[Path(p) for p in data.get("llm_inputs", [])],
            all_outputs=[Path(p) for p in data.get("all_outputs", [])],
            warnings=[
                ManifestWarning.from_dict(item)
                for item in data.get("warnings", [])
            ],
            prompt_runs=[
                PromptRecord.from_dict(item)
                for item in data.get("prompt_runs", [])
            ],
            output_hashes=[
                FileHashRecord.from_dict(item)
                for item in data.get("output_hashes", [])
            ],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "out_dir": str(self.out_dir),
            "sheet_csvs": [str(p) for p in self.sheet_csvs],
            "vba_txts": [str(p) for p in self.vba_txts],
            "names_manager_csv": str(self.names_manager_csv) if self.names_manager_csv else "",
            "replacements": self.replacements,
            "llm_inputs": [str(p) for p in self.llm_inputs],
            "all_outputs": [str(p) for p in self.all_outputs],
            "warnings": [item.to_dict() for item in self.warnings],
            "prompt_runs": [item.to_dict() for item in self.prompt_runs],
            "output_hashes": [item.to_dict() for item in self.output_hashes],
        }

    def with_warnings(self, warnings: Iterable[ManifestWarning]) -> "ExportManifest":
        merged: List[ManifestWarning] = []
        seen: set[tuple[str, str, str, str]] = set()
        for warning in [*self.warnings, *warnings]:
            key = (warning.code, warning.stage, warning.path, warning.message)
            if key in seen:
                continue
            seen.add(key)
            merged.append(warning)
        return ExportManifest(
            out_dir=self.out_dir,
            sheet_csvs=self.sheet_csvs,
            vba_txts=self.vba_txts,
            names_manager_csv=self.names_manager_csv,
            replacements=self.replacements,
            llm_inputs=self.llm_inputs,
            all_outputs=self.all_outputs,
            warnings=merged,
            prompt_runs=self.prompt_runs,
            output_hashes=self.output_hashes,
        )

    def with_prompt_record(self, record: PromptRecord) -> "ExportManifest":
        prompt_runs = [item for item in self.prompt_runs if item.stage != record.stage]
        prompt_runs.append(record)
        return ExportManifest(
            out_dir=self.out_dir,
            sheet_csvs=self.sheet_csvs,
            vba_txts=self.vba_txts,
            names_manager_csv=self.names_manager_csv,
            replacements=self.replacements,
            llm_inputs=self.llm_inputs,
            all_outputs=self.all_outputs,
            warnings=self.warnings,
            prompt_runs=prompt_runs,
            output_hashes=self.output_hashes,
        )

    def with_output_hashes(self, paths: Iterable[Path]) -> "ExportManifest":
        records: List[FileHashRecord] = []
        seen: set[str] = set()
        for path in paths:
            path = Path(path)
            key = str(path)
            if key in seen or not path.exists() or not path.is_file():
                continue
            seen.add(key)
            records.append(
                FileHashRecord(
                    path=key,
                    bytes=path.stat().st_size,
                    sha256=file_sha256(path),
                )
            )
        return ExportManifest(
            out_dir=self.out_dir,
            sheet_csvs=self.sheet_csvs,
            vba_txts=self.vba_txts,
            names_manager_csv=self.names_manager_csv,
            replacements=self.replacements,
            llm_inputs=self.llm_inputs,
            all_outputs=self.all_outputs,
            warnings=self.warnings,
            prompt_runs=self.prompt_runs,
            output_hashes=records,
        )

    def strict_error_warnings(self) -> List[ManifestWarning]:
        return [warning for warning in self.warnings if warning.strict_error]
