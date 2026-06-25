from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Dict, List, Tuple


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def format_file_block(label: str, content: str) -> str:
    return (
        f"\n\n=====BEGIN_INPUT_FILE: {label}=====\n"
        f"{content}\n"
        f"=====END_INPUT_FILE: {label}=====\n"
    )


@dataclass(frozen=True)
class StuffedInputFile:
    path: Path
    label: str
    original_chars: int
    included_chars: int
    original_sha256: str
    truncated: bool


@dataclass(frozen=True)
class StuffedInputs:
    text: str
    files: List[StuffedInputFile]
    total_limit_reached: bool

    @property
    def truncated(self) -> bool:
        return self.total_limit_reached or any(item.truncated for item in self.files)


def read_and_cap_file(path: Path, max_chars_per_file: int) -> Tuple[str, bool]:
    text = read_text(path)
    if len(text) > max_chars_per_file:
        return text[:max_chars_per_file] + "\n\n[TRUNCATED]\n", True
    return text, False


def _relkey(base_dir: Path, p: Path) -> str:
    try:
        return str(p.relative_to(base_dir))
    except Exception:
        return p.name


def build_stuffed_inputs_with_metadata(
    base_dir: Path,
    files: List[Path],
    max_chars_per_file: int,
    max_total_chars: int,
) -> StuffedInputs:
    blocks: List[str] = []
    records: List[StuffedInputFile] = []
    total = 0
    total_limit_reached = False
    for path in sorted(files, key=lambda p: _relkey(base_dir, p)):
        label = _relkey(base_dir, path)
        original_text = read_text(path)
        if len(original_text) > max_chars_per_file:
            text = original_text[:max_chars_per_file] + "\n\n[TRUNCATED]\n"
            truncated = True
        else:
            text = original_text
            truncated = False
        block = format_file_block(label, text)

        if total + len(block) > max_total_chars:
            blocks.append(
                format_file_block(
                    "PIPELINE_NOTICE",
                    "Stopped adding more input files due to max_total_chars limit.\n"
                    "If needed, increase limits or reduce exports.",
                )
            )
            total_limit_reached = True
            break

        blocks.append(block)
        total += len(block)
        records.append(
            StuffedInputFile(
                path=path,
                label=label,
                original_chars=len(original_text),
                included_chars=len(text),
                original_sha256=sha256(original_text.encode("utf-8")).hexdigest(),
                truncated=truncated,
            )
        )

    return StuffedInputs(
        text="".join(blocks),
        files=records,
        total_limit_reached=total_limit_reached,
    )


def build_stuffed_inputs(
    base_dir: Path,
    files: List[Path],
    max_chars_per_file: int,
    max_total_chars: int,
) -> str:
    return build_stuffed_inputs_with_metadata(
        base_dir=base_dir,
        files=files,
        max_chars_per_file=max_chars_per_file,
        max_total_chars=max_total_chars,
    ).text


def apply_placeholders(prompt_template: str, placeholders: Dict[str, str]) -> str:
    out = prompt_template
    for key, value in placeholders.items():
        out = out.replace("{{" + key + "}}", value)
    return out
