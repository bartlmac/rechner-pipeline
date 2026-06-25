from __future__ import annotations

import builtins
import glob as glob_module
from pathlib import Path

import pytest

from rechner_pipeline.qa import fs_confine


@pytest.fixture
def _restore_builtins():
    orig_open = builtins.open
    orig_glob = glob_module.glob
    orig_iglob = glob_module.iglob
    try:
        yield
    finally:
        builtins.open = orig_open
        glob_module.glob = orig_glob
        glob_module.iglob = orig_iglob


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
