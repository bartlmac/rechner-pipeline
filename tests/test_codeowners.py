"""CODEOWNERS hat die Form, die das Maintainer Office beschlossen hat.

Eine Zeile fuer das ganze Repository: das Muster ``*`` und dahinter die
Konten, die freigeben. GitHub uebergeht einen Eintrag, den es nicht lesen
kann, ohne Meldung; eine Zeile ohne Konto verlangt keine Freigabe. Der
Test haelt die Mechanik: genau eine Regelzeile, das Muster ``*``,
mindestens ein Konto, jedes in der Form ``@konto`` oder
``@organisation/team``, keines doppelt. Ob ein Konto Schreibrecht hat,
prueft er nicht.

Knoten: system/architektur
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

REPO = Path(__file__).resolve().parents[1]
CODEOWNERS = REPO / ".github" / "CODEOWNERS"

_KONTO = re.compile(r"@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:/[A-Za-z0-9._-]+)?")


def _regeln() -> List[List[str]]:
    aus: List[List[str]] = []
    for zeile in CODEOWNERS.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if zeile and not zeile.startswith("#"):
            aus.append(zeile.split())
    return aus


def test_codeowners_ist_eine_zeile_fuer_das_ganze_repository():
    muster = [r[0] for r in _regeln()]
    assert len(muster) == 1 and muster[0] == "*", muster


def test_codeowners_nennt_lesbare_konten():
    konten = _regeln()[0][1:]
    assert konten, "CODEOWNERS nennt kein Konto"
    unlesbar = [k for k in konten if not _KONTO.fullmatch(k)]
    assert not unlesbar, f"CODEOWNERS-Eintraege, die GitHub nicht liest: {unlesbar}"
    assert len(set(konten)) == len(konten), f"Konto doppelt: {konten}"
