from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


@dataclass(frozen=True)
class ExportManifest:
    out_dir: Path
    sheet_csvs: List[Path]
    vba_txts: List[Path]
    names_manager_csv: Path | None
    replacements: Dict[str, str]
    llm_inputs: List[Path]
    all_outputs: List[Path]

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
        }
