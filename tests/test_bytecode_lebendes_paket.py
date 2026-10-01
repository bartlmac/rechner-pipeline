"""Der Code, der rechnet, ist der Bytecode, den Python laedt — er muss der Code seiner Quelle sein.

Befund der blinden Pruefrunde H (H07, mittel): Python laedt
``__pycache__/<modul>.<tag>.pyc``, wenn deren Kopf (Zeitstempel und Groesse der
Quelle) passt; den Inhalt prueft es nicht. Jeder Stand-Hash des Systems
(``paket_sha256``, ``kern_modul_hash``, ``dirty``) liest die Quellen. Eine
untergeschobene pyc fuer ``kern/tafeln.py`` verdoppelte die
Sterbewahrscheinlichkeiten, ``lebendes_repo`` nahm an, und A-M4 meldete
"keine Aenderung seit Abnahme".

Invariante (ADR-025, Nachtrag Pruefrunde G, Punkt 3): Der lebende Stand ist
der des Codes, der rechnet. Gebaut an der EINEN Stelle, durch die jedes
``--repo-root`` geht (``gates._provenienz.lebendes_repo``): Jede pyc im
ausgefuehrten Paket, die der Interpreter laden wuerde, ist der Code ihrer
Quelle (``bytecode_fehler``; Messung vor dem Bau: fuer alle 136 Module
``marshal.loads(pyc[16:]) == compile(quelle)``, dreimal frisch importiert).

Mutationsprobe: den Aufruf von ``bytecode_fehler`` in ``lebendes_repo``
entfernen -> ``test_die_untergeschobene_pyc_*`` rot.

Knoten: system/assurance
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
from importlib._bootstrap_external import _code_to_timestamp_pyc
from pathlib import Path

import pytest

from rechner_pipeline.gates import _provenienz

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "rechner_pipeline"

_PROBE = (
    "import sys, json\n"
    "from rechner_pipeline.kern import tafeln\n"
    "from rechner_pipeline.gates._provenienz import lebendes_repo\n"
    "print(json.dumps({'paket': tafeln.__file__, 'qx45': tafeln.qx_vector('M', 'DAV1994_T')[45]}))\n"
    "sys.stdout.flush()\n"
    "lebendes_repo(sys.argv[1])\n"
    "print('ANGENOMMEN')\n")


def _kopie(tmp_path: Path) -> Path:
    """Eine Kopie des Pakets mit byte-gleichen Quellen (ohne Bytecode)."""
    ziel = tmp_path / "kopie"
    shutil.copytree(SRC, ziel / "src" / "rechner_pipeline",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return ziel


def _boese_pyc(kopie: Path) -> Path:
    """Die pyc des Pruefers: Kopf passt zu ``kern/tafeln.py``, der Code
    verdoppelt die Sterbewahrscheinlichkeiten."""
    quelle = kopie / "src" / "rechner_pipeline" / "kern" / "tafeln.py"
    text = quelle.read_text(encoding="utf-8")
    assert "def qx_vector(" in text, "die Funktion des Repros fehlt — die Probe veraendert nichts"
    boese = text.replace("def qx_vector(", "def _qx_vector_echt(", 1) + (
        "\n\ndef qx_vector(sex, tafel):\n"
        "    return [min(1.0, 2.0 * q) for q in _qx_vector_echt(sex, tafel)]\n")
    st = quelle.stat()
    pyc = Path(importlib.util.cache_from_source(str(quelle)))
    pyc.parent.mkdir(parents=True, exist_ok=True)
    pyc.write_bytes(bytes(_code_to_timestamp_pyc(
        compile(boese, str(quelle), "exec"), int(st.st_mtime), st.st_size)))
    return pyc


def _lauf(kopie: Path):
    env = dict(os.environ, PYTHONPATH=str(kopie / "src"))
    env.pop("PYTHONDONTWRITEBYTECODE", None)
    return subprocess.run([sys.executable, "-c", _PROBE, str(kopie)], env=env, cwd=kopie,
                          capture_output=True, text=True, timeout=300)


def test_die_untergeschobene_pyc_aendert_die_rechnung_und_wird_verweigert(tmp_path):
    """Das Repro des Pruefers in einem eigenen Prozess (das ausgefuehrte Paket
    ist die Kopie). Positivkontrolle ohne pyc: dieselbe Rechnung wie das
    Original, ``lebendes_repo`` nimmt an. Mit pyc: die Rechnung ist eine
    andere — und ``lebendes_repo`` verweigert benannt mit Ausweg. Rot vor dem
    Fix: ANGENOMMEN."""
    import json

    from rechner_pipeline.kern import tafeln

    kopie = _kopie(tmp_path)
    sauber = _lauf(kopie)
    assert sauber.returncode == 0 and "ANGENOMMEN" in sauber.stdout, sauber.stderr[-2000:]
    werte = json.loads(sauber.stdout.splitlines()[0])
    assert werte["paket"].startswith(str(kopie))
    assert werte["qx45"] == tafeln.qx_vector("M", "DAV1994_T")[45]

    shutil.rmtree(kopie / "src" / "rechner_pipeline" / "kern" / "__pycache__")
    _boese_pyc(kopie)
    boese = _lauf(kopie)
    werte = json.loads(boese.stdout.splitlines()[0])
    assert werte["qx45"] == pytest.approx(2 * tafeln.qx_vector("M", "DAV1994_T")[45])
    assert boese.returncode != 0 and "ANGENOMMEN" not in boese.stdout
    assert "der ausgefuehrte Code ist nicht der gehashte" in boese.stderr, boese.stderr[-2000:]
    assert "tafeln" in boese.stderr and "__pycache__" in boese.stderr
    assert "loeschen" in boese.stderr


def test_bytecode_fehler_unterscheidet_was_der_interpreter_laedt(tmp_path):
    """Die Faelle der Regel einzeln, ohne Prozess: passende pyc mit fremdem Code
    -> Befund; dieselbe pyc mit unpassendem Kopf (Python verwirft sie) -> kein
    Befund; pyc eines anderen Interpreters oder ohne Quelle unter
    ``__pycache__`` -> kein Befund; quellenloser Bytecode neben den Quellen ->
    Befund; die frisch geschriebenen pyc des Imports -> kein Befund."""
    kopie = _kopie(tmp_path)
    paket = kopie / "src" / "rechner_pipeline"
    assert _provenienz.bytecode_fehler(paket) == []
    pyc = _boese_pyc(kopie)
    [befund] = _provenienz.bytecode_fehler(paket)
    assert "kern/__pycache__/tafeln." in befund and "der Code ist ein anderer" in befund

    quelle = paket / "kern" / "tafeln.py"
    os.utime(quelle, (quelle.stat().st_atime, quelle.stat().st_mtime + 10))
    assert _provenienz.bytecode_fehler(paket) == []        # Kopf passt nicht: verworfen
    pyc.unlink()

    fremd = paket / "kern" / "__pycache__" / "tafeln.cpython-99.pyc"
    fremd.write_bytes(b"\x00" * 32)
    waise = paket / "kern" / "__pycache__" / "geloescht.cpython-311.pyc"
    waise.write_bytes(b"\x00" * 32)
    assert _provenienz.bytecode_fehler(paket) == []
    neben = paket / "kern" / "einschub.pyc"
    neben.write_bytes(b"\x00" * 32)
    [befund] = _provenienz.bytecode_fehler(paket)
    assert "kern/einschub.pyc" in befund and "ohne Quelle" in befund


def test_die_eine_stelle_ruft_die_pruefung(tmp_path, monkeypatch):
    """An der Naht: ``lebendes_repo`` prueft den Bytecode des AUSGEFUEHRTEN
    Pakets (hier ueber die Naht ``_ausgefuehrtes_paket`` auf die Kopie
    gestellt) — jedes Kommando der Schicht gates mit ``--repo-root`` geht durch
    sie (Ratsche in tests/test_repo_root_lebendes_paket.py)."""
    kopie = _kopie(tmp_path)
    paket = kopie / "src" / "rechner_pipeline"
    monkeypatch.setattr(_provenienz, "_ausgefuehrtes_paket", lambda: paket)
    assert _provenienz.lebendes_repo(str(kopie)) == kopie.resolve()
    _boese_pyc(kopie)
    with pytest.raises(argparse.ArgumentTypeError, match="nicht der gehashte"):
        _provenienz.lebendes_repo(str(kopie))
