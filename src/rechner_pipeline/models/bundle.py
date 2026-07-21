"""``InputBundle`` and the coverage metadata block (§6.5, §6.8.5).

The bundle contract is source-neutral but intentionally ``info_from_excel``-shaped
so existing downstream consumers keep reading the same files. The bundle wraps an
:class:`~rechner_pipeline.models.manifest.ExportManifest` and adds adapter-level
metadata plus the explicit expectation-coverage decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from rechner_pipeline.models.manifest import ExportManifest, ManifestWarning

__all__ = [
    "CONTRACT_VERSION",
    "EXPECTATION_COVERAGE_VALUES",
    "CoverageDetail",
    "InputBundle",
]

#: Bundle metadata contract version (§6.5).
CONTRACT_VERSION = "info_from_excel.v1"

#: Legal ``expectation_coverage`` literals (§6.5 / §6.8.5).
EXPECTATION_COVERAGE_VALUES: tuple[str, ...] = ("full", "sparse", "none")


@dataclass
class CoverageDetail:
    """The auditable coverage breakdown embedded in §6.8.5.

    Makes the §3.4 coverage decision auditable so a zero-comparison run can never
    masquerade as a validated one.
    """

    scalar_files: int = 0
    scalar_keys_expected: int = 0
    scalar_keys_numeric: int = 0
    table_files: int = 0
    table_cells_expected: int = 0
    sheets_with_compressed: int = 0
    names_manager_present: bool = False
    source_text_files: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CoverageDetail":
        return cls(
            scalar_files=int(data.get("scalar_files", 0)),
            scalar_keys_expected=int(data.get("scalar_keys_expected", 0)),
            scalar_keys_numeric=int(data.get("scalar_keys_numeric", 0)),
            table_files=int(data.get("table_files", 0)),
            table_cells_expected=int(data.get("table_cells_expected", 0)),
            sheets_with_compressed=int(data.get("sheets_with_compressed", 0)),
            names_manager_present=bool(data.get("names_manager_present", False)),
            source_text_files=int(data.get("source_text_files", 0)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scalar_files": self.scalar_files,
            "scalar_keys_expected": self.scalar_keys_expected,
            "scalar_keys_numeric": self.scalar_keys_numeric,
            "table_files": self.table_files,
            "table_cells_expected": self.table_cells_expected,
            "sheets_with_compressed": self.sheets_with_compressed,
            "names_manager_present": self.names_manager_present,
            "source_text_files": self.source_text_files,
        }


@dataclass
class InputBundle:
    """Source-neutral input bundle wrapping an :class:`ExportManifest` (§6.5).

    ``manifest`` is optional so the lightweight coverage block (§6.8.5) embedded
    in ``run_dossier.input_bundle`` can be (de)serialized on its own.
    """

    source_path: str
    adapter_id: str
    out_dir: str
    manifest_path: str
    expectation_coverage: str
    contract_version: str = CONTRACT_VERSION
    coverage_detail: CoverageDetail = field(default_factory=CoverageDetail)
    warnings: List[ManifestWarning] = field(default_factory=list)
    manifest: Optional[ExportManifest] = None

    # -- coverage block (§6.8.5): the audit subset embedded in the dossier --- #

    def coverage_block(self) -> Dict[str, Any]:
        """Return the §6.8.5 ``input_bundle`` coverage block.

        This is the subset echoed by ``extract``'s result summary and embedded as
        ``run_dossier.input_bundle``. It deliberately omits the in-memory manifest.
        """
        return {
            "contract_version": self.contract_version,
            "adapter_id": self.adapter_id,
            "source_path": self.source_path,
            "manifest_path": self.manifest_path,
            "expectation_coverage": self.expectation_coverage,
            "coverage_detail": self.coverage_detail.to_dict(),
            "warnings": [w.to_dict() for w in self.warnings],
        }

    def to_dict(self) -> Dict[str, Any]:
        """Full bundle serialization (coverage block plus ``out_dir`` and an
        optional embedded manifest)."""
        out: Dict[str, Any] = {
            "contract_version": self.contract_version,
            "adapter_id": self.adapter_id,
            "source_path": self.source_path,
            "out_dir": self.out_dir,
            "manifest_path": self.manifest_path,
            "expectation_coverage": self.expectation_coverage,
            "coverage_detail": self.coverage_detail.to_dict(),
            "warnings": [w.to_dict() for w in self.warnings],
        }
        if self.manifest is not None:
            out["manifest"] = self.manifest.to_dict()
        return out

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InputBundle":
        manifest_data = data.get("manifest")
        return cls(
            source_path=str(data.get("source_path", "")),
            adapter_id=str(data.get("adapter_id", "")),
            out_dir=str(data.get("out_dir", "")),
            manifest_path=str(data.get("manifest_path", "")),
            expectation_coverage=str(data.get("expectation_coverage", "")),
            contract_version=str(data.get("contract_version", CONTRACT_VERSION)),
            coverage_detail=CoverageDetail.from_dict(
                dict(data.get("coverage_detail") or {})
            ),
            warnings=[
                ManifestWarning.from_dict(item) for item in data.get("warnings", [])
            ],
            manifest=(
                ExportManifest.from_dict(manifest_data)
                if isinstance(manifest_data, dict)
                else None
            ),
        )

    def validate(self) -> List[str]:
        """Return a list of human-readable validation errors (empty == valid).

        Structural checks only (no filesystem access): required metadata present,
        coverage literal explicit, and contract version recognized.
        """
        errors: List[str] = []
        if self.contract_version != CONTRACT_VERSION:
            errors.append(
                f"contract_version must be {CONTRACT_VERSION!r}, got "
                f"{self.contract_version!r}"
            )
        if not self.source_path:
            errors.append("source_path is required")
        if not self.adapter_id:
            errors.append("adapter_id is required")
        if not self.out_dir:
            errors.append("out_dir is required")
        if not self.manifest_path:
            errors.append("manifest_path is required")
        if self.expectation_coverage not in EXPECTATION_COVERAGE_VALUES:
            errors.append(
                "expectation_coverage must be one of "
                f"{EXPECTATION_COVERAGE_VALUES}, got {self.expectation_coverage!r}"
            )
        return errors
