"""
Schlanker Workflow-Logger: die Pipeline gibt ihren tatsächlichen Verlauf
live aus (stdout). Die Inhalte kommen aus den Aufruf-Stellen (echte Daten),
dieses Modul formatiert nur.

Standardmäßig AUS (kein Output, kein Verhaltenswechsel). Aktivierung über
Umgebungsvariable ``RP_WFLOG=1`` oder ``enable()``.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Iterable

_ON = bool(os.environ.get("RP_WFLOG"))
_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")

# Mitschrift: der Log wird zusätzlich in eine Datei geschrieben, damit der
# Verlauf eines Laufs ohne erneuten (API-)Lauf ansehbar ist. Der Default-Name
# trägt einen Zeitstempel, sodass sich aufeinanderfolgende Läufe nicht
# überschreiben. Mit RP_WFLOG_FILE lässt sich ein fester Pfad erzwingen.
_FILE_PATH = os.environ.get("RP_WFLOG_FILE")  # None = Default im Lauf-Verzeichnis
_FILE = None  # lazily geöffnet; False = Öffnen fehlgeschlagen
_RUN_STAMP = None  # pro Prozess einmal
_RUN_DIR = None  # pro Prozess einmal
_START = None  # Startzeitpunkt (für Laufzeit)
_DEMO = False  # Demo/Replay-Lauf -> nicht akkumulierendes runs/demo
_ANSI = re.compile(r"\033\[[0-9;]*m")

# Obergrenze für aufgelistete Namen (items()), damit Ausgaben auch bei sehr
# vielen Artefakten beschränkt bleiben. Überzählige werden als (+N) gezählt.
try:
    _MAX_ITEMS = int(os.environ.get("RP_WFLOG_MAX_ITEMS", "12"))
except (TypeError, ValueError):
    _MAX_ITEMS = 12


def run_stamp() -> str:
    """Pro Prozess einmaliger Zeitstempel ``YYYYmmdd_HHMMSS``.

    Trennt Läufe in Dateinamen (Mitschrift, per-Iteration-Prompts), damit ein
    späterer Lauf einen früheren nicht überschreibt.
    """
    global _RUN_STAMP, _START
    if _RUN_STAMP is None:
        from datetime import datetime

        now = datetime.now()
        _RUN_STAMP = now.strftime("%Y%m%d_%H%M%S")
        _START = now
    return _RUN_STAMP


def elapsed() -> float:
    """Vergangene Sekunden seit Lauf-Start (0.0 falls noch nicht gestartet)."""
    if _START is None:
        return 0.0
    from datetime import datetime

    return (datetime.now() - _START).total_seconds()


def set_demo(flag: bool = True) -> None:
    """Lauf als Demo/Replay markieren. Solche Läufe landen in einem einzigen,
    nicht akkumulierenden ``runs/demo`` (statt ``runs/<zeitstempel>``), damit die
    echten Läufe sauber und unterscheidbar bleiben. Vor dem ersten ``run_dir()``
    aufrufen (die CLI tut das anhand des Providers)."""
    global _DEMO
    _DEMO = bool(flag)


def run_dir() -> Path:
    """Verzeichnis für alle Artefakte eines Laufs (Mitschrift, Prompts,
    Fixtures) — hält das Repo-Root sauber.

    Echte Läufe: ``./runs/<zeitstempel>/`` (akkumulieren). Demo/Replay-Läufe:
    ``./runs/demo/`` (einmalig, wird überschrieben). Basis via ``RP_RUN_DIR``
    überschreibbar; wird bei Bedarf angelegt.
    """
    global _RUN_DIR
    if _RUN_DIR is None:
        base = Path(os.environ.get("RP_RUN_DIR", "runs"))
        _RUN_DIR = (base / "demo") if _DEMO else (base / run_stamp())
        try:
            _RUN_DIR.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
    return _RUN_DIR


def enable(on: bool = True) -> None:
    global _ON
    _ON = on


def enabled() -> bool:
    return _ON


def _c(code: str) -> str:
    return code if (_ON and _COLOR) else ""


_B, _DIM, _G, _R, _C, _X = (
    _c("\033[1m"), _c("\033[2m"), _c("\033[32m"), _c("\033[31m"), _c("\033[36m"), _c("\033[0m"),
)


def _emit(line: str = "") -> None:
    if not _ON:
        return
    print(line, flush=True)
    global _FILE
    if _FILE is None:
        path = _FILE_PATH or (run_dir() / "workflow_log.txt")
        try:
            _FILE = open(path, "w", encoding="utf-8")
        except OSError:
            _FILE = False
    if _FILE:
        _FILE.write(_ANSI.sub("", line) + "\n")
        _FILE.flush()


def phase(name: str, detail: str = "") -> None:
    """Beginn eines Workflow-Schritts."""
    _emit(f"\n{_B}{_C}* {name}{_X}" + (f"  {_DIM}{detail}{_X}" if detail else ""))


def detail(text: str) -> None:
    """Eine inhaltliche Zeile innerhalb eines Schritts."""
    _emit(f"    {text}")


def code(line: str) -> None:
    """Eine wörtliche Quellcode-Zeile (eingerückt, gedimmt)."""
    _emit(f"      {_DIM}| {line}{_X}")


def items(label: str, values: Iterable[str], limit: int | None = None) -> None:
    """Liste ausgeben, auf ``limit`` Einträge beschränkt (Default
    ``RP_WFLOG_MAX_ITEMS``); überzählige werden als ``(+N)`` gezählt."""
    vals = list(values)
    if not vals:
        return
    lim = _MAX_ITEMS if limit is None else limit
    shown = ", ".join(str(v) for v in vals[:lim])
    more = f"  (+{len(vals) - lim})" if len(vals) > lim else ""
    _emit(f"    {label}: {shown}{more}")


def iteration(n: int, text: str = "") -> None:
    """Start einer Schleifen-Iteration (z. B. agentischer Repair-Durchlauf)."""
    _emit(f"\n{_B}-- Iteration {n} --{_X}" + (f"  {_DIM}{text}{_X}" if text else ""))


def ok(text: str) -> None:
    _emit(f"  {_G}-> {text}{_X}")


def fail(text: str) -> None:
    _emit(f"  {_R}-> {text}{_X}")


def rule(text: str = "") -> None:
    """Trennbalken, optional mit Titel (für Abschluss-Karte etc.)."""
    _emit(f"  {_DIM}{'-' * 58}{_X}")
    if text:
        _emit(f"  {_B}{text}{_X}")


def table(headers, rows, aligns=None) -> None:
    """Spaltenbündige Tabelle (Kopf gedimmt). ``aligns``: je Spalte 'l'/'r'."""
    if not _ON:
        return
    cols = [str(h) for h in headers]
    data = [[str(c) for c in r] for r in rows]
    widths = [len(c) for c in cols]
    for r in data:
        for i, c in enumerate(r):
            if i < len(widths):
                widths[i] = max(widths[i], len(c))

    def _row(cells):
        parts = []
        for i, c in enumerate(cells):
            a = aligns[i] if aligns and i < len(aligns) else "l"
            parts.append(c.rjust(widths[i]) if a == "r" else c.ljust(widths[i]))
        return "  ".join(parts).rstrip()

    _emit(f"    {_DIM}{_row(cols)}{_X}")
    for r in data:
        _emit(f"    {_row(r)}")


def diff(sign: str, text: str) -> None:
    """Eine Diff-Zeile: '+' grün, '-' rot, sonst gedimmt."""
    color = _G if sign == "+" else _R if sign == "-" else _DIM
    _emit(f"      {color}{sign} {text}{_X}")
