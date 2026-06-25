"""
Laufzeit-Confinement für ausgeführten, generierten Code (Compare-Stufe).

Ergänzt das statische Security-Gate (:mod:`rechner_pipeline.qa.security`) um die
*Orts*-Beschränkung, die statisch nicht entscheidbar ist: ``open`` und
``glob``/``iglob`` dürfen nur Pfade **unterhalb eines Wurzelverzeichnisses**
(``repo_root``) berühren; Schreibzugriffe werden hart abgewiesen, und jeder
Lesezugriff außerhalb des Repos ebenfalls. Zusätzlich (Defense-in-depth, vgl.
Review-Finding F1) werden ``subprocess``-, Shell-(``os.system``/``os.popen``)-
und Netz-(``socket``)-Aufrufe **auch zur Laufzeit** abgewiesen — das statische
Gate verbietet sie bereits im generierten Code, der Laufzeit-Block greift
idiom-unabhängig, falls ein Aufruf das statische Gate umgeht. Eine echte
OS-Sandbox (seccomp/Container) bleibt der robustere Weg (CR-004).

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


def _blocked(label: str):
    """Erzeuge einen Ersatz, der jeden Aufruf hart abweist."""

    def _raise(*_args, **_kwargs):
        raise PermissionError(f"fs-confine: {label} is blocked")

    return _raise


def _install_exec_guards() -> None:
    """Defense-in-depth: Subprocess-/Shell-/Netz-Aufrufe zur Laufzeit abweisen.

    Das statische Security-Gate (:mod:`rechner_pipeline.qa.security`) blockiert
    diese Aufrufe bereits im generierten Code; hier wird der Schutz idiom-
    unabhaengig auch zur Laufzeit erzwungen, falls ein Aufruf das statische Gate
    umgeht (vgl. Review-Finding F1 / CR-002 Nachtrag). Eine echte OS-Sandbox
    (seccomp/Container) bleibt der robustere Weg (CR-004); dies ist eine
    fokussierte In-Process-Schranke gegen die haeufigsten Pfade
    (``os.system``/``os.popen``, ``subprocess.Popen`` inkl. ``run``/``call``/
    ``check_*``, ``socket.socket``).
    """
    os.system = _blocked("os.system")  # type: ignore[assignment]
    if hasattr(os, "popen"):
        os.popen = _blocked("os.popen")  # type: ignore[assignment]
    try:
        import subprocess

        # run/call/check_output/check_call instanziieren intern Popen -> ein
        # Patch auf Popen deckt alle High-Level-Helfer mit ab.
        subprocess.Popen = _blocked("subprocess.Popen")  # type: ignore[assignment]
    except Exception:
        pass
    try:
        import socket

        socket.socket = _blocked("socket.socket")  # type: ignore[assignment]
    except Exception:
        pass


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

    _install_exec_guards()


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
