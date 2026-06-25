"""
Laufzeit-Confinement für ausgeführten, generierten Code (Compare-Stufe).

Ergänzt das statische Security-Gate (:mod:`rechner_pipeline.qa.security`) um die
*Orts*-Beschränkung, die statisch nicht entscheidbar ist: ``open`` und
``glob``/``iglob`` dürfen nur Pfade **unterhalb eines Wurzelverzeichnisses**
(``repo_root``) berühren. Schreib-/Netz-/Subprocess-Zugriffe sind bereits
statisch verboten; hier wird zusätzlich jeder Lesezugriff außerhalb des Repos
zur Laufzeit hart abgewiesen.

Aufruf als Launcher::

    python -m rechner_pipeline.qa.fs_confine <repo_root> <script.py>
    python <pfad>/fs_confine.py <repo_root> <script.py>

installiert das Confinement und führt ``<script.py>`` als ``__main__`` aus
(Exit-Code/SystemExit werden durchgereicht).
"""

from __future__ import annotations

import builtins
import glob as _glob
import os
import runpy
import sys

_WRITE_FLAGS = ("w", "a", "x", "+")


def _is_under(root: str, path: object) -> bool:
    try:
        real = os.path.realpath(os.fspath(path))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    return real == root or real.startswith(root + os.sep)


def install(root: str) -> None:
    """Umhülle open/glob/iglob so, dass nur Lesezugriffe unter ``root`` erlaubt sind."""
    real_root = os.path.realpath(root)
    orig_open = builtins.open
    orig_iglob = _glob.iglob

    def guarded_open(file, mode="r", *args, **kwargs):
        effective_mode = mode if isinstance(mode, str) else "r"
        if any(flag in effective_mode for flag in _WRITE_FLAGS):
            raise PermissionError(f"fs-confine: write access is blocked: {file!r}")
        if not _is_under(real_root, file):
            raise PermissionError(
                f"fs-confine: read outside repo root is blocked: {file!r}"
            )
        return orig_open(file, mode, *args, **kwargs)

    # Wichtig: über orig_iglob filtern, NICHT über orig_glob -- stdlib glob.glob
    # ruft intern das (jetzt gepatchte) modul-globale iglob auf -> Rekursion.
    def guarded_iglob(pathname, *args, **kwargs):
        for p in orig_iglob(pathname, *args, **kwargs):
            if _is_under(real_root, p):
                yield p

    def guarded_glob(pathname, *args, **kwargs):
        return list(guarded_iglob(pathname, *args, **kwargs))

    builtins.open = guarded_open
    _glob.glob = guarded_glob
    _glob.iglob = guarded_iglob


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 2:
        raise SystemExit("usage: fs_confine.py <repo_root> <script.py>")
    root, script = args[0], args[1]
    install(root)
    sys.argv = [script, *args[2:]]
    runpy.run_path(script, run_name="__main__")


if __name__ == "__main__":  # pragma: no cover
    main()
