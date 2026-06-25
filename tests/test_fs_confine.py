from __future__ import annotations

import builtins
import glob as glob_module
import os
import socket
import subprocess
from pathlib import Path

import pytest

from rechner_pipeline.qa import fs_confine


@pytest.fixture
def _restore_builtins():
    orig_open = builtins.open
    orig_glob = glob_module.glob
    orig_iglob = glob_module.iglob
    # install() patcht zusaetzlich exec-/Netz-Einstiegspunkte -> hier mit
    # sichern und wiederherstellen, sonst lecken die Patches in andere Tests
    # (z. B. run_compare nutzt subprocess.run).
    orig_system = os.system
    orig_popen = os.popen
    orig_popen_cls = subprocess.Popen
    orig_socket = socket.socket
    try:
        yield
    finally:
        builtins.open = orig_open
        glob_module.glob = orig_glob
        glob_module.iglob = orig_iglob
        os.system = orig_system
        os.popen = orig_popen
        subprocess.Popen = orig_popen_cls
        socket.socket = orig_socket


def test_confine_allows_read_inside_root(tmp_path: Path, _restore_builtins):
    inside = tmp_path / "data.txt"
    inside.write_text("hello", encoding="utf-8")

    fs_confine.install(str(tmp_path))

    with open(str(inside), "r", encoding="utf-8") as f:
        assert f.read() == "hello"


def test_confine_blocks_read_outside_root(tmp_path: Path, _restore_builtins):
    outside_dir = tmp_path / "repo"
    outside_dir.mkdir()
    secret = tmp_path / "secret.txt"  # Geschwister, NICHT unter repo
    secret.write_text("sk-ant-xxx", encoding="utf-8")

    fs_confine.install(str(outside_dir))

    with pytest.raises(PermissionError, match="outside repo"):
        open(str(secret), "r")


def test_confine_blocks_write_inside_root(tmp_path: Path, _restore_builtins):
    fs_confine.install(str(tmp_path))
    with pytest.raises(PermissionError, match="write access"):
        open(str(tmp_path / "new.txt"), "w")


def test_confine_glob_filters_to_root(tmp_path: Path, _restore_builtins):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "a.json").write_text("{}", encoding="utf-8")
    (tmp_path / "b.json").write_text("{}", encoding="utf-8")  # außerhalb

    fs_confine.install(str(root))

    found_inside = glob_module.glob(str(root / "*.json"))
    assert found_inside == [str(root / "a.json")]
    # Glob außerhalb der Wurzel liefert nichts.
    assert glob_module.glob(str(tmp_path / "*.json")) == []


def test_confine_blocks_os_system(tmp_path: Path, _restore_builtins):
    fs_confine.install(str(tmp_path))
    with pytest.raises(PermissionError, match="os.system is blocked"):
        os.system("echo hi")


def test_confine_blocks_os_popen(tmp_path: Path, _restore_builtins):
    fs_confine.install(str(tmp_path))
    with pytest.raises(PermissionError, match="os.popen is blocked"):
        os.popen("echo hi")


def test_confine_blocks_subprocess(tmp_path: Path, _restore_builtins):
    fs_confine.install(str(tmp_path))
    # run/call/check_output gehen alle ueber Popen -> ein Patch deckt alle ab.
    with pytest.raises(PermissionError, match="subprocess.Popen is blocked"):
        subprocess.run(["echo", "hi"])
    with pytest.raises(PermissionError, match="subprocess.Popen is blocked"):
        subprocess.Popen(["echo", "hi"])


def test_confine_blocks_socket(tmp_path: Path, _restore_builtins):
    fs_confine.install(str(tmp_path))
    with pytest.raises(PermissionError, match="socket.socket is blocked"):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)
