"""
Laufzeit-Confinement für ausgeführten, generierten Code (Compare-Stufe, Gate
**G4**, MIGRATION.md §2.4 Zeilen 1242-1261, §3.5 G4 Zeile 1746, §2.6
Risikoregister Zeilen 1545-1569).

Ergänzt das statische Security-Gate (:mod:`rechner_pipeline.qa.security`, G2) um
die *Orts*- und *Modus*-Beschränkung, die statisch nicht vollständig entscheidbar
ist: jeder Datei-Lesezugriff darf nur Pfade **unterhalb eines Wurzelverzeichnisses**
(``repo_root``) berühren, Schreibzugriffe sind überall verboten, und
Netz-/Subprozess-Zugriffe werden zur Laufzeit hart abgewiesen.

**Defense-in-depth, KEINE OS-Sandbox (§2.6).** Dieses Modul ist eine zusätzliche
Laufzeit-Schutzschicht, die dem generierten Code NICHT vertraut. Es ist KEIN
formaler Betriebssystem-Sandkasten: ein hinreichend entschlossener Angreifer mit
nativem Code (ctypes, kompilierte C-Extensions, Manipulation von Low-Level-File-
Deskriptoren über os.dup/fork o.ä.) kann ein reines Python-Monkeypatching immer
umgehen. Das eigentliche Vertrauensmodell ist mehrschichtig: G2 (statische
AST-Prüfung, die das gefährliche Konstrukt gar nicht erst durchlässt) + G4 (dieses
Laufzeit-Confinement, das die statisch erlaubten read-only ``open``/``glob``-Aufrufe
auf die Repo-Wurzel begrenzt UND als Tiefenverteidigung die statisch bereits
verbotenen Schreib-/Netz-/Subprozess-Pfade auch zur Laufzeit blockiert) +
Subprozess-Isolation (eigener Kindprozess mit cwd == ``generated/``). Diese
Schicht garantiert, dass der typische LLM-Drift (versehentliches Schreiben,
Lesen eines Secrets außerhalb des Repos, ein ``socket``/``subprocess``-Aufruf,
der durch eine statische Lücke schlüpfte) zur Laufzeit fehlschlägt, statt
unbemerkt auszuführen.

Aufruf als Launcher::

    python -m rechner_pipeline.qa.fs_confine <repo_root> <script.py> [argv...]
    python <pfad>/fs_confine.py <repo_root> <script.py> [argv...]

installiert das Confinement und führt ``<script.py>`` als ``__main__`` aus
(Exit-Code/SystemExit werden durchgereicht).

Implementierungshinweis: Vor dem Patch gilt ``builtins.open is io.open`` (beide
zeigen auf dieselbe C-Funktion). Es genügt daher NICHT, nur ``builtins.open`` zu
ersetzen — ``io.open`` muss eigenständig gepatcht werden, sonst umgeht
``import io; io.open(...)`` das Confinement vollständig. Analog werden die
gefährlichen ``os.*``-Dateisystem-Primitive (``os.open``/``write``/``read``/
``remove``/``unlink``/``rename``/``replace``/``mkdir``/...) und die Netz-/
Subprozess-Module direkt an ihrem Definitionsort umhüllt.
"""

from __future__ import annotations

import builtins
import glob as _glob
import io
import os
import runpy
import sys

#: Modi, die einen Schreib-/Anlege-/Trunkier-Zugriff bedeuten.
_WRITE_FLAGS = ("w", "a", "x", "+")

#: ``os.open``-Flags, die einen Schreibzugriff bedeuten. ``O_RDONLY`` ist 0, daher
#: muss positiv auf eine der Schreib-/Erzeugungs-Flags geprüft werden.
_OS_WRITE_FLAGS = 0
for _flag_name in (
    "O_WRONLY",
    "O_RDWR",
    "O_APPEND",
    "O_CREAT",
    "O_TRUNC",
    "O_EXCL",
    "O_TEMPORARY",
    "O_SHORT_LIVED",
):
    _OS_WRITE_FLAGS |= getattr(os, _flag_name, 0)


def _is_under(root: str, path: object) -> bool:
    try:
        real = os.path.realpath(os.fspath(path))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    return real == root or real.startswith(root + os.sep)


def _mode_is_write(mode: object) -> bool:
    effective = mode if isinstance(mode, str) else "r"
    return any(flag in effective for flag in _WRITE_FLAGS)


class _Restore:
    """Sammelt ``(objekt, attribut, originalwert)`` zum späteren Zurücksetzen.

    Der Launcher-Pfad (``main``) installiert einmalig in einem dedizierten
    Kindprozess und braucht kein Zurücksetzen. In-Process-Tests rufen das
    zurückgegebene Undo auf, damit die globalen Patches (``os.*``, ``io.open``,
    ``socket``/``subprocess``) nicht in andere Tests lecken.
    """

    def __init__(self) -> None:
        self._saved: list[tuple[object, str, object]] = []

    def patch(self, obj: object, attr: str, value: object) -> None:
        self._saved.append((obj, attr, getattr(obj, attr)))
        setattr(obj, attr, value)

    def undo(self) -> None:
        for obj, attr, original in reversed(self._saved):
            setattr(obj, attr, original)
        self._saved.clear()


def install(root: str):
    """Installiere das Laufzeit-Confinement (G4) für ``root``.

    Erzwingt: NUR Lesezugriffe unterhalb ``root`` (read-only), KEINE Schreib-
    zugriffe (überall blockiert), KEINE Lesezugriffe außerhalb ``root``. Zusätzlich
    werden ``socket``- und ``subprocess``-Zugriffe als Tiefenverteidigung zur
    Laufzeit blockiert.

    Gepatcht werden — am jeweiligen Definitionsort, damit Aliase wie ``io.open``
    oder ``os.remove`` nicht daran vorbeikommen:

    * ``builtins.open`` **und** ``io.open`` (pre-patch identisch),
    * ``glob.glob`` / ``glob.iglob`` (Filterung auf ``root``),
    * die schreibenden/öffnenden ``os.*``-Primitive
      (``open``/``remove``/``unlink``/``rename``/``replace``/``mkdir``/...),
      sowie ``os.write`` als Tiefenverteidigung,
    * ``socket.socket`` und die ``subprocess``-Ausführungs-APIs.

    Gibt ein :class:`_Restore`-Objekt zurück, dessen ``undo()`` alle Patches
    zurücksetzt (für In-Process-Tests; im Launcher-Kindprozess ignorierbar).
    """
    real_root = os.path.realpath(root)
    restore = _Restore()

    orig_open = io.open  # builtins.open is io.open vor dem Patch
    orig_iglob = _glob.iglob

    # ----------------------------------------------------------------- open --
    def guarded_open(file, mode="r", *args, **kwargs):
        # Datei-Deskriptoren (int) entstehen nur aus einem bereits geöffneten
        # Pfad; Modus wird trotzdem geprüft, der Pfad kann hier nicht geprüft
        # werden -> Schreibmodi bleiben verboten, Lesen über fd ist read-only.
        if _mode_is_write(mode):
            raise PermissionError(f"fs-confine: write access is blocked: {file!r}")
        if isinstance(file, int):
            return orig_open(file, mode, *args, **kwargs)
        if not _is_under(real_root, file):
            raise PermissionError(
                f"fs-confine: read outside repo root is blocked: {file!r}"
            )
        return orig_open(file, mode, *args, **kwargs)

    # ----------------------------------------------------------------- glob --
    # Wichtig: über orig_iglob filtern, NICHT über orig_glob -- stdlib glob.glob
    # ruft intern das (jetzt gepatchte) modul-globale iglob auf -> Rekursion.
    def guarded_iglob(pathname, *args, **kwargs):
        for p in orig_iglob(pathname, *args, **kwargs):
            if _is_under(real_root, p):
                yield p

    def guarded_glob(pathname, *args, **kwargs):
        return list(guarded_iglob(pathname, *args, **kwargs))

    restore.patch(builtins, "open", guarded_open)
    restore.patch(io, "open", guarded_open)
    restore.patch(_glob, "glob", guarded_glob)
    restore.patch(_glob, "iglob", guarded_iglob)

    # ------------------------------------------------------------------- os --
    _install_os_guards(real_root, restore)

    # ----------------------------------------------------- socket/subprocess --
    _install_network_guards(restore)

    return restore


def _install_os_guards(real_root: str, restore: "_Restore") -> None:
    """Umhülle die schreibenden/öffnenden ``os.*``-Dateisystem-Primitive.

    Lesendes ``os.open`` (read-only) darf nur unter ``real_root`` geöffnet werden;
    jedes schreibende/erzeugende/löschende/umbenennende Primitiv ist überall
    blockiert. ``os.write`` wird zusätzlich überwacht (Tiefenverteidigung gegen
    einen über ``os.dup``/fork erlangten fremden fd); ``os.read`` bleibt erlaubt
    (read-only).
    """
    orig_os_open = os.open
    orig_os_write = os.write

    def guarded_os_open(path, flags, *args, **kwargs):
        if flags & _OS_WRITE_FLAGS:
            raise PermissionError(f"fs-confine: write access is blocked: {path!r}")
        if not _is_under(real_root, path):
            raise PermissionError(
                f"fs-confine: read outside repo root is blocked: {path!r}"
            )
        return orig_os_open(path, flags, *args, **kwargs)

    def guarded_os_write(fd, data):  # noqa: ANN001
        # Schreiben auf reale Dateien ist verboten. stdout(1)/stderr(2) müssen
        # erlaubt bleiben, sonst kann der Kindprozess sein JSON-Ergebnis nicht
        # emittieren; stdin(0) ist kein Schreibziel.
        if fd > 2:
            raise PermissionError(
                f"fs-confine: write access is blocked: os.write(fd={fd})"
            )
        return orig_os_write(fd, data)

    restore.patch(os, "open", guarded_os_open)
    restore.patch(os, "write", guarded_os_write)

    # Mutierende Pfad-Primitive: überall hart blockieren.
    def _blocked(symbol: str):
        def _guard(*_args, **_kwargs):
            raise PermissionError(f"fs-confine: write access is blocked: os.{symbol}")

        return _guard

    for _name in (
        "remove",
        "unlink",
        "rename",
        "renames",
        "replace",
        "rmdir",
        "removedirs",
        "mkdir",
        "makedirs",
        "truncate",
        "ftruncate",
        "link",
        "symlink",
        "chmod",
        "chown",
        "mkfifo",
        "mknod",
    ):
        if hasattr(os, _name):
            restore.patch(os, _name, _blocked(_name))


def _install_network_guards(restore: "_Restore") -> None:
    """Blockiere ``socket`` und ``subprocess`` zur Laufzeit (Tiefenverteidigung).

    Diese Module sind statisch (G2) bereits verboten; hier werden ihre
    gefährlichen Einstiegspunkte zusätzlich zur Laufzeit neutralisiert, damit ein
    Aufruf, der durch eine statische Lücke schlüpfte, hart fehlschlägt statt
    Netz-/Prozess-Seiteneffekte auszulösen. ``import socket`` selbst bleibt
    erlaubt — nur das Erzeugen eines Sockets / das Starten eines Prozesses wird
    abgewiesen.
    """
    import socket
    import subprocess

    def _blocked_net(symbol: str):
        def _guard(*_args, **_kwargs):
            raise PermissionError(
                f"fs-confine: network access is blocked: socket.{symbol}"
            )

        return _guard

    restore.patch(socket, "socket", _blocked_net("socket"))
    for _name in ("create_connection", "create_server"):
        if hasattr(socket, _name):
            restore.patch(socket, _name, _blocked_net(_name))

    def _blocked_proc(symbol: str):
        def _guard(*_args, **_kwargs):
            raise PermissionError(
                f"fs-confine: subprocess execution is blocked: subprocess.{symbol}"
            )

        return _guard

    restore.patch(subprocess, "Popen", _blocked_proc("Popen"))
    for _name in ("run", "call", "check_call", "check_output", "getoutput", "getstatusoutput"):
        if hasattr(subprocess, _name):
            restore.patch(subprocess, _name, _blocked_proc(_name))

    # os.system / os.popen / os.exec*/spawn* sind ebenfalls Prozess-Start-Pfade.
    def _blocked_os_proc(symbol: str):
        def _guard(*_args, **_kwargs):
            raise PermissionError(
                f"fs-confine: subprocess execution is blocked: os.{symbol}"
            )

        return _guard

    for _name in (
        "system",
        "popen",
        "execv",
        "execve",
        "execvp",
        "execvpe",
        "execl",
        "execle",
        "execlp",
        "execlpe",
        "spawnv",
        "spawnve",
        "spawnl",
        "spawnle",
        "spawnlp",
        "spawnlpe",
        "posix_spawn",
        "posix_spawnp",
        "fork",
        "forkpty",
        "startfile",
    ):
        if hasattr(os, _name):
            restore.patch(os, _name, _blocked_os_proc(_name))


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
