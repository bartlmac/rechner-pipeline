"""CODEOWNERS zeigt nur auf vorhandene Pfade.

GitHub uebergeht ein Muster, das auf nichts zeigt, ohne Meldung. Zieht ein
Verzeichnis um, waere die Zuordnung zum Modul still verloren. Der Test haelt
die Mechanik: jedes Muster trifft mindestens eine Datei oder ein Verzeichnis.
Wer ein Modul verantwortet, prueft er nicht.

Knoten: system/architektur
"""

from __future__ import annotations

from pathlib import Path
from typing import List

REPO = Path(__file__).resolve().parents[1]
CODEOWNERS = REPO / ".github" / "CODEOWNERS"


def _muster() -> List[str]:
    aus: List[str] = []
    for zeile in CODEOWNERS.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if zeile and not zeile.startswith("#"):
            aus.append(zeile.split()[0])
    return aus


def test_codeowners_hat_rueckfall_zuerst():
    muster = _muster()
    assert muster[0] == "*", muster[:1]


def test_jedes_muster_zeigt_auf_einen_vorhandenen_pfad():
    tot = [m for m in _muster()[1:]
           if not m.startswith("/") or not list(REPO.glob(m.strip("/")))]
    assert not tot, f"CODEOWNERS-Muster ohne Treffer oder ohne fuehrenden Schraegstrich: {tot}"
