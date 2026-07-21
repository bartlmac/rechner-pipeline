"""Runtime-confinement tests for :mod:`rechner_pipeline.qa.fs_confine` (gate G4).

Covers the in-process guard installation (open/glob filtering) and the launcher
path used by the golden-master command: a confined child that attempts a file
write must be blocked.
"""

from __future__ import annotations

import glob as glob_module
import subprocess
import sys
from pathlib import Path

import pytest

from rechner_pipeline.qa import fs_confine


@pytest.fixture
def confine():
    """Install fs_confine for a root and guarantee every global patch (open,
    io.open, os.*, glob, socket, subprocess) is reverted after the test so the
    confinement cannot leak into pytest's own tmp-dir creation or other tests."""
    restores = []

    def _install(root: str):
        r = fs_confine.install(str(root))
        restores.append(r)
        return r

    try:
        yield _install
    finally:
        for r in reversed(restores):
            r.undo()


def test_confine_allows_read_inside_root(tmp_path: Path, confine):
    inside = tmp_path / "data.txt"
    inside.write_text("hello", encoding="utf-8")

    confine(tmp_path)

    with open(str(inside), "r", encoding="utf-8") as f:
        assert f.read() == "hello"


def test_confine_blocks_read_outside_root(tmp_path: Path, confine):
    outside_dir = tmp_path / "repo"
    outside_dir.mkdir()
    secret = tmp_path / "secret.txt"  # Geschwister, NICHT unter repo
    secret.write_text("sk-ant-xxx", encoding="utf-8")

    confine(outside_dir)

    with pytest.raises(PermissionError, match="outside repo"):
        open(str(secret), "r")


def test_confine_blocks_write_inside_root(tmp_path: Path, confine):
    confine(tmp_path)
    with pytest.raises(PermissionError, match="write access"):
        open(str(tmp_path / "new.txt"), "w")


def test_confine_glob_filters_to_root(tmp_path: Path, confine):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "a.json").write_text("{}", encoding="utf-8")
    (tmp_path / "b.json").write_text("{}", encoding="utf-8")  # außerhalb

    confine(root)

    found_inside = glob_module.glob(str(root / "*.json"))
    assert found_inside == [str(root / "a.json")]
    # Glob außerhalb der Wurzel liefert nichts.
    assert glob_module.glob(str(tmp_path / "*.json")) == []


def test_confine_blocks_io_open_alias(tmp_path: Path, confine):
    """io.open is the same C function as builtins.open pre-patch; patching only
    builtins.open would leave `import io; io.open(...)` as an escape hatch."""
    import io as io_module

    confine(tmp_path)
    with pytest.raises(PermissionError, match="write access"):
        io_module.open(str(tmp_path / "viaio.txt"), "w")


def test_confine_blocks_os_filesystem_calls(tmp_path: Path, confine):
    """os.open(write), os.remove, os.rename, os.mkdir must all be blocked."""
    import os as os_module

    existing = tmp_path / "keep.txt"
    existing.write_text("x", encoding="utf-8")
    confine(tmp_path)

    with pytest.raises(PermissionError, match="write access"):
        os_module.open(str(tmp_path / "new.bin"), os_module.O_WRONLY | os_module.O_CREAT)
    with pytest.raises(PermissionError, match="write access"):
        os_module.remove(str(existing))
    with pytest.raises(PermissionError, match="write access"):
        os_module.rename(str(existing), str(tmp_path / "renamed.txt"))
    with pytest.raises(PermissionError, match="write access"):
        os_module.mkdir(str(tmp_path / "subdir"))
    # The file was never deleted/renamed.
    assert existing.exists()


def test_confine_os_open_read_outside_blocked(tmp_path: Path, confine):
    root = tmp_path / "repo"
    root.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("sk-ant-xxx", encoding="utf-8")
    import os as os_module

    confine(root)
    with pytest.raises(PermissionError, match="outside repo"):
        os_module.open(str(secret), os_module.O_RDONLY)


def test_confine_blocks_socket_and_subprocess(tmp_path: Path, confine):
    import socket as socket_module
    import subprocess as subprocess_module

    confine(tmp_path)
    with pytest.raises(PermissionError, match="network access is blocked"):
        socket_module.socket()
    with pytest.raises(PermissionError, match="subprocess execution is blocked"):
        subprocess_module.run([sys.executable, "-c", "pass"])


def test_confine_launcher_blocks_write_in_child_process(tmp_path: Path):
    """A kernel executed via the fs_confine launcher that attempts a file write
    must be blocked (PermissionError) by the confinement guard."""
    root = tmp_path / "repo"
    root.mkdir()
    script = root / "writer.py"
    script.write_text(
        "open('escaped.txt', 'w').write('boom')\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [sys.executable, fs_confine.__file__, str(root), str(script)],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "write access is blocked" in proc.stderr
    assert not (root / "escaped.txt").exists()
