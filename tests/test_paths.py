"""Unit tests for pygamine.assets.paths: resource_root()/resource_path(), the
frozen-vs-source filesystem anchor host projects chdir into at startup.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import pygamine.assets.paths as paths_module
from pygamine.assets.paths import (
    packaged_data_dir,
    resource_path,
    resource_root,
    user_data_dir,
)


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


def _fake_home(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))


def test_user_data_dir_windows_uses_appdata(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    expected = tmp_path / "roaming" / "VectorViolet" / "chokepoint"
    assert user_data_dir("chokepoint") == expected


def test_user_data_dir_windows_falls_back_without_appdata(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("APPDATA", raising=False)
    _fake_home(monkeypatch, tmp_path)
    expected = tmp_path / "AppData" / "Roaming" / "VectorViolet" / "g"
    assert user_data_dir("g") == expected


def test_user_data_dir_macos(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "darwin")
    _fake_home(monkeypatch, tmp_path)
    expected = tmp_path / "Library" / "Application Support" / "VectorViolet" / "g"
    assert user_data_dir("g") == expected


def test_user_data_dir_linux_uses_xdg_data_home(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    assert user_data_dir("g") == tmp_path / "xdg" / "VectorViolet" / "g"


@pytest.mark.parametrize("xdg", [None, ""])
def test_user_data_dir_linux_falls_back_without_xdg(monkeypatch, tmp_path, xdg):
    monkeypatch.setattr(sys, "platform", "linux")
    _fake_home(monkeypatch, tmp_path)
    if xdg is None:
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    else:
        monkeypatch.setenv("XDG_DATA_HOME", xdg)
    expected = tmp_path / ".local" / "share" / "VectorViolet" / "g"
    assert user_data_dir("g") == expected


def test_user_data_dir_emscripten_is_cwd_and_never_asks_for_home(monkeypatch):
    monkeypatch.setattr(sys, "platform", "emscripten")

    def no_home():
        raise AssertionError("home must not be queried on the web")

    monkeypatch.setattr(Path, "home", staticmethod(no_home))
    assert user_data_dir("g") == Path(".")
    assert (user_data_dir("g") / "saves").as_posix() == "saves"


def test_user_data_dir_linux_ignores_relative_xdg_data_home(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", "relative/dir")
    _fake_home(monkeypatch, tmp_path)
    expected = tmp_path / ".local" / "share" / "VectorViolet" / "g"
    assert user_data_dir("g") == expected


def test_user_data_dir_vendor_replaces_the_company_folder(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert user_data_dir("g", vendor="Acme") == tmp_path / "Acme" / "g"


@pytest.mark.parametrize(
    "name", ["", ".", "..", "a/b", "a\\b", "/abs", "../up", "C:\\x", "C:x"]
)
def test_user_data_dir_rejects_bad_names(name):
    with pytest.raises(ValueError):
        user_data_dir(name)
    with pytest.raises(ValueError):
        user_data_dir("g", vendor=name)


@pytest.mark.parametrize("platform", ["win32", "darwin", "linux"])
def test_user_data_dir_warns_and_falls_back_when_home_is_unknown(
    monkeypatch, caplog, platform
):
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    def no_home():
        raise RuntimeError("Could not determine home directory.")

    monkeypatch.setattr(Path, "home", staticmethod(no_home))
    with caplog.at_level("WARNING", logger="pygamine.assets.paths"):
        assert user_data_dir("g") == Path("userdata") / "g"
    assert "home folder" in caplog.text


def test_user_data_dir_creates_nothing(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    user_data_dir("g")
    assert not (tmp_path / "xdg").exists()


def _packaged(monkeypatch):
    monkeypatch.setattr(sys, "_MEIPASS", "/bundle", raising=False)


def _source(monkeypatch):
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)


def test_packaged_data_dir_is_user_data_dir_plus_sub_when_packaged(
    monkeypatch, tmp_path
):
    _packaged(monkeypatch)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert packaged_data_dir("g", "saves") == tmp_path / "VectorViolet" / "g" / "saves"
    assert (
        packaged_data_dir("g", "databases", vendor="Acme")
        == tmp_path / "Acme" / "g" / "databases"
    )


def test_packaged_data_dir_is_none_from_source(monkeypatch):
    _source(monkeypatch)
    assert packaged_data_dir("g", "saves") is None


def test_packaged_data_dir_is_none_on_the_web(monkeypatch):
    _packaged(monkeypatch)
    monkeypatch.setattr(sys, "platform", "emscripten")
    assert packaged_data_dir("g", "saves") is None


@pytest.mark.parametrize(
    "name", ["", ".", "..", "a/b", "a\\b", "/abs", "../up", "C:\\x", "C:x"]
)
@pytest.mark.parametrize("packaged", [True, False])
def test_packaged_data_dir_rejects_bad_names(monkeypatch, packaged, name):
    (_packaged if packaged else _source)(monkeypatch)
    with pytest.raises(ValueError, match="sub"):
        packaged_data_dir("g", name)
    with pytest.raises(ValueError, match="game"):
        packaged_data_dir(name, "saves")
    with pytest.raises(ValueError, match="vendor"):
        packaged_data_dir("g", "saves", vendor=name)


def _no_home(monkeypatch):
    def no_home():
        raise RuntimeError("Could not determine home directory.")

    monkeypatch.setattr(Path, "home", staticmethod(no_home))
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)


def _bundle(monkeypatch, tmp_path, exe_parts, platform):
    """A packaged build whose _MEIPASS and executable are real folders in tmp_path."""
    root = tmp_path.resolve()
    meipass = root / "bundle"
    meipass.mkdir()
    exe = root.joinpath(*exe_parts)
    exe.parent.mkdir(parents=True, exist_ok=True)
    exe.touch()
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(sys, "platform", platform)
    _no_home(monkeypatch)
    return root, meipass


@pytest.mark.parametrize("platform", ["win32", "linux"])
def test_packaged_without_home_uses_a_folder_next_to_the_executable(
    monkeypatch, caplog, tmp_path, platform
):
    root, meipass = _bundle(monkeypatch, tmp_path, ["app", "game.exe"], platform)
    expected = root / "app" / "userdata" / "g"
    with caplog.at_level("WARNING", logger="pygamine.assets.paths"):
        assert user_data_dir("g") == expected
        assert packaged_data_dir("g", "saves") == expected / "saves"
    assert meipass not in expected.parents
    assert str(expected) in caplog.text


def test_packaged_without_home_on_macos_is_next_to_the_app_bundle(
    monkeypatch, tmp_path
):
    root, _ = _bundle(
        monkeypatch,
        tmp_path,
        ["Apps", "Game.app", "Contents", "MacOS", "game"],
        "darwin",
    )
    assert user_data_dir("g") == root / "Apps" / "userdata" / "g"
    assert packaged_data_dir("g", "saves") == root / "Apps" / "userdata" / "g" / "saves"


@pytest.mark.parametrize("executable", ["", None])
def test_packaged_without_home_and_executable_raises(monkeypatch, tmp_path, executable):
    _bundle(monkeypatch, tmp_path, ["app", "game.exe"], "linux")
    monkeypatch.setattr(sys, "executable", executable)
    with pytest.raises(RuntimeError, match="sys.executable"):
        user_data_dir("g")
    with pytest.raises(RuntimeError, match="sys.executable"):
        packaged_data_dir("g", "saves")


def test_source_without_home_keeps_the_relative_folder_even_without_executable(
    monkeypatch,
):
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "executable", "")
    _no_home(monkeypatch)
    assert user_data_dir("g") == Path("userdata") / "g"


@pytest.mark.parametrize("value", ["", "relative/dir"])
def test_user_data_dir_windows_ignores_empty_or_relative_appdata(
    monkeypatch, tmp_path, value
):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", value)
    _fake_home(monkeypatch, tmp_path)
    expected = tmp_path / "AppData" / "Roaming" / "VectorViolet" / "g"
    assert user_data_dir("g") == expected
