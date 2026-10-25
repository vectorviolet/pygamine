"""Unit tests for pygamine.assets.paths: resource_root()/resource_path(), the
frozen-vs-source filesystem anchor host projects chdir into at startup.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pygamine.assets.paths as paths_module
from pygamine.assets.paths import resource_path, resource_root


def test_resource_root_uses_meipass_when_frozen(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert resource_root() == tmp_path


def test_resource_root_falls_back_to_project_root_when_not_frozen(
    monkeypatch, tmp_path
):
    """Deliberately doesn't rely on *this* checkout's own real location:
    locally it's nested inside a host project (src/pygamine/), but in
    pygamine's own CI it's checked out standalone with no such nesting --
    those disagree, which is exactly what broke here originally (this test
    used to assert against `Path(__file__)`, silently assuming the local
    nested layout, and failed the moment it ran in pygamine's own
    standalone CI). Build a fake <root>/src/pygamine/pygamine/assets/paths.py
    tree in tmp_path and point paths.py's own `__file__` at it instead, so
    the assertion holds the same way regardless of where this test suite
    itself happens to be checked out.

    Also deliberately not just `root.is_dir()`: every ancestor of a real
    file is itself a real, existing directory, so that assertion alone
    would pass even at the wrong depth (e.g. one level short) -- which is
    the regression this originally caught when paths.py moved into
    assets/ and the parents[N] index needed to grow by one but didn't.
    """
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    fake_paths_file = tmp_path / "src" / "pygamine" / "pygamine" / "assets" / "paths.py"
    fake_paths_file.parent.mkdir(parents=True)
    fake_paths_file.touch()
    monkeypatch.setattr(paths_module, "__file__", str(fake_paths_file))

    assert paths_module.resource_root() == tmp_path


def test_resource_path_joins_onto_resource_root(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert resource_path("config", "towers.yaml") == tmp_path / "config" / "towers.yaml"


def test_resource_path_with_no_parts_equals_resource_root(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert resource_path() == Path(tmp_path)
