"""Ein inhaltsadressierter Beleg erscheint ganz oder gar nicht unter seinem Namen.

Angriffsrunde nach T27: gate_entscheid schrieb den P9-Snapshot mit
open("xb") direkt unter dem endgueltigen Namen; ein Abbruch mitten im
Schreiben liess einen Stumpf in entscheide/, der jeden weiteren Entscheid
des Gates und die Registrierung des Falls dauerhaft sperrte.

Knoten: system/abnahme
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from rechner_pipeline.gates import _common

SRC = Path(__file__).resolve().parents[1] / "src"


def test_ein_abbruch_mitten_im_schreiben_hinterlaesst_nichts_unter_dem_namen(tmp_path, monkeypatch):
    """Mutationsprobe: wieder direkt unter dem Namen schreiben -> rot."""
    ziel = tmp_path / "A-M4-abc.json"
    echt = os.fsync

    def stirbt(fd):
        raise KeyboardInterrupt("Prozessende mitten im Schreiben")

    monkeypatch.setattr(_common.os, "fsync", stirbt)
    with pytest.raises(KeyboardInterrupt):
        _common.schreibe_exklusiv(ziel, b'{"halb": ' * 1000)
    monkeypatch.setattr(_common.os, "fsync", echt)
    assert not ziel.exists()
    assert list(tmp_path.glob("*.json")) == []
    _common.schreibe_exklusiv(ziel, b"{}\n")
    assert ziel.read_bytes() == b"{}\n"
    with pytest.raises(FileExistsError):
        _common.schreibe_exklusiv(ziel, b"[]\n")
    assert ziel.read_bytes() == b"{}\n"


def test_kein_beleg_wird_mehr_direkt_unter_seinem_namen_geschrieben():
    """Ratsche: open("xb")/open("x") gibt es in src/ nicht mehr — der eine
    Weg ist schreibe_exklusiv. Positivkontrolle: das Muster erkennt die
    alte Form."""
    muster = re.compile(r"""open\(\s*["']xb?["']""")
    assert muster.search('with ziel.open("xb") as datei:')
    treffer = [f"{p.relative_to(SRC)}:{n}"
               for p in SRC.rglob("*.py")
               for n, zeile in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
               if muster.search(zeile)]
    assert treffer == []
