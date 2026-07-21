"""Pluggable input-adapter seam (§3.4 of MIGRATION.md).

Every adapter turns one source document into the same filesystem bundle under
``info_from_excel\\`` and returns an :class:`~rechner_pipeline.models.bundle.InputBundle`
describing it. Downstream generation and QA consume the bundle, not the original
document type.

The :class:`ExcelAdapter` is a zero-behavior-change wrapper around the current
Excel extraction (``export_excel_infos``). Future adapters (Word, etc.) implement
the same ABC and emit an Excel-shaped bundle with explicit expectation coverage.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from rechner_pipeline.models.bundle import InputBundle

__all__ = ["InputAdapter"]


class InputAdapter(ABC):
    """Abstract source-document adapter producing an :class:`InputBundle`.

    Concrete adapters MUST:

    * declare a stable :attr:`adapter_id` (used as ``InputBundle.adapter_id``);
    * implement :meth:`supports` so the ``auto`` selector can pick an adapter;
    * implement :meth:`extract` to materialize artifacts under ``out_dir`` and
      return a populated :class:`InputBundle` with an explicit
      ``expectation_coverage`` of ``full|sparse|none``.
    """

    #: Stable identifier stamped onto the bundle (e.g. ``"excel"``).
    adapter_id: str = ""

    @classmethod
    @abstractmethod
    def supports(cls, source_path: Path) -> bool:
        """Return whether this adapter can handle ``source_path`` (by shape/suffix)."""
        raise NotImplementedError

    @abstractmethod
    def extract(self, source_path: Path, out_dir: Path) -> InputBundle:
        """Materialize the ``info_from_excel`` bundle for ``source_path``.

        Implementations must write the Excel-shaped artifacts under ``out_dir``,
        build the ``export_manifest.json``, and return an :class:`InputBundle`
        whose ``expectation_coverage`` is set explicitly.
        """
        raise NotImplementedError
