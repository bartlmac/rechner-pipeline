from __future__ import annotations

import re
from pathlib import Path


PATTERN = re.compile(
    r"===FILE_START:\s*(?P<name>[^=\r\n]+?)\s*===\s*"
    r"(?P<content>.*?)"
    r"\s*===FILE_END:\s*(?P=name)\s*===",
    re.DOTALL,
)


def extract_files_from_text(text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for match in PATTERN.finditer(text):
        name = match.group("name").strip()
        content = match.group("content")
        out.append((name, content))
    return out


def safe_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def write_extracted_files_to_generated_dir(text: str, script_dir: Path) -> int:
    items = extract_files_from_text(text)
    if not items:
        return 0

    written = 0
    for filename, content in items:
        safe_name = Path(filename).name
        out_path = script_dir / "generated" / safe_name
        safe_write(out_path, content)
        written += 1
    return written
