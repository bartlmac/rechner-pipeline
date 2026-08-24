"""Publikationshygiene der eingecheckten Office-Quelldateien.

Knoten: klv
"""

from __future__ import annotations

import re
from pathlib import Path
from zipfile import ZipFile

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
OFFICE_DATEIEN = tuple(
    sorted(
        pfad
        for wurzel in (
            REPO_ROOT / "tests" / "fixtures",
            REPO_ROOT / "lieferungen",
        )
        for muster in ("*.xlsm", "*.xlsx", "*.docx")
        for pfad in wurzel.rglob(muster)
    )
)

VERBOTENE_TEXTE = (
    "abspath",
    "customxml",
    "lastmodifiedby",
    "lastprinted",
    "printersettings",
    "sharepoint",
)
PFAD_MUSTER = (
    re.compile(r"\\\\[A-Za-z0-9._-]{3,}\\[A-Za-z0-9._$-]+"),
    re.compile(r"[A-Z]:\\[A-Za-z0-9\\._ -]{6,}", re.IGNORECASE),
)
PFAD_AUSNAHMEN = ("program files", "windows\\system32")


def _dekodierungen(inhalt: bytes):
    """Auch in Binaerteilen versteckte UTF-16-Metadaten sichtbar machen."""
    for kodierung in ("utf-8", "utf-16-le", "latin-1"):
        yield kodierung, inhalt.decode(kodierung, "ignore").lower()


@pytest.mark.parametrize(
    "office_datei",
    OFFICE_DATEIEN,
    ids=lambda pfad: str(pfad.relative_to(REPO_ROOT)),
)
def test_office_dateien_enthalten_keine_internen_metadaten(
    office_datei: Path,
):
    """SharePoint-IDs und Druckserverpfade sind keine fachlichen Quelldaten."""
    with ZipFile(office_datei) as paket:
        teile = tuple(paket.namelist())
        kleingeschrieben = tuple(name.lower() for name in teile)

        assert "docprops/custom.xml" not in kleingeschrieben
        assert not any(name.startswith("customxml/") for name in kleingeschrieben)
        assert not any("printersettings/" in name for name in kleingeschrieben)

        for name in teile:
            inhalt = paket.read(name)
            for kodierung, text in _dekodierungen(inhalt):
                for verboten in VERBOTENE_TEXTE:
                    assert verboten not in text, (name, kodierung, verboten)
                for muster in PFAD_MUSTER:
                    for fund in muster.findall(text):
                        assert any(
                            ausnahme in fund for ausnahme in PFAD_AUSNAHMEN
                        ), (name, kodierung, "interner Pfad")
