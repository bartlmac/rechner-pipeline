from __future__ import annotations

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


def read_and_cap_file(path: Path, max_chars_per_file: int) -> Tuple[str, bool]:
    text = read_text(path)
    if len(text) > max_chars_per_file:
        return text[:max_chars_per_file] + "\n\n[TRUNCATED]\n", True
    return text, False


def build_stuffed_inputs(
    base_dir: Path,
    files: List[Path],
    max_chars_per_file: int,
    max_total_chars: int,
) -> str:
    def relkey(p: Path) -> str:
        try:
            return str(p.relative_to(base_dir))
        except Exception:
            return p.name

    blocks: List[str] = []
    total = 0
    for path in sorted(files, key=relkey):
        label = relkey(path)
        text, _truncated = read_and_cap_file(path, max_chars_per_file)
        block = format_file_block(label, text)

        if total + len(block) > max_total_chars:
            blocks.append(
                format_file_block(
                    "PIPELINE_NOTICE",
                    "Stopped adding more input files due to max_total_chars limit.\n"
                    "If needed, increase limits or reduce exports.",
                )
            )
            break

        blocks.append(block)
        total += len(block)

    return "".join(blocks)


def apply_placeholders(prompt_template: str, placeholders: Dict[str, str]) -> str:
    out = prompt_template
    for key, value in placeholders.items():
        out = out.replace("{{" + key + "}}", value)
    return out
