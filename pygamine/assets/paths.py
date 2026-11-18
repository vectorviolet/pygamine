"""Filesystem anchors that work both from source and inside a PyInstaller
bundle.

A frozen game typically loads assets/config with paths relative to the
current working directory, which only holds when the process runs from the
project root. When PyInstaller freezes the app, data files bundled via the
spec's ``datas`` are unpacked next to the executable (onedir) or extracted
to a temp dir (onefile); either way their location is exposed as
``sys._MEIPASS``. A host project's entry point chdirs into
:func:`resource_root` at startup so its existing cwd-relative paths stay
valid in both modes; anything that must resolve a bundled path without
relying on the cwd uses :func:`resource_path` instead.

:func:`user_data_dir` is the per-user, writable folder for a game's saves and
databases, so installs in read-only places (Program Files) still work.
:func:`packaged_data_dir` is the same folder, but only in a packaged build.

Assumes the standard submodule layout, ``<project_root>/src/pygamine/`` --
:func:`resource_root` walks up from this file's location, so a host project
vendoring pygamine somewhere else needs its own variant instead.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _is_packaged() -> bool:
    """Whether this process runs from a PyInstaller bundle (``sys._MEIPASS`` is set).

    The one packaged test: :func:`resource_root` and :func:`packaged_data_dir`
    both use it, so assets and saves can't disagree.
    """
    return getattr(sys, "_MEIPASS", None) is not None


def resource_root() -> Path:
    """Directory that contains the bundled ``assets/`` (and similar) trees.

    Frozen: the PyInstaller extraction dir. From source: the project root,
    walked up from ``src/pygamine/pygamine/assets/paths.py``.
    """
    if _is_packaged():
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parents[4]


def resource_path(*parts: str) -> Path:
    """Absolute path to a bundled resource, e.g. ``resource_path("config", "towers.yaml")``."""
    return resource_root().joinpath(*parts)


def _check_name(label: str, name: str) -> None:
    """Reject anything that isn't one plain folder name."""
    if (
        not name
        or name in (".", "..")
        or "/" in name
        or "\\" in name
        or Path(name).is_absolute()
        or ":" in name
    ):
        raise ValueError(f"{label} must be a single folder name, got {name!r}")


def _packaged_fallback_root() -> Path:
    """Folder next to the packaged executable, for when there's no home folder.

    On macOS, inside ``X.app/Contents/MacOS``, it's the folder that contains the
    ``.app``, never the bundle itself. Raises ``RuntimeError`` if
    ``sys.executable`` is empty: resolving it would land in the cwd, which is
    usually inside the bundle.
    """
    if not sys.executable:
        raise RuntimeError(
            "No home folder and sys.executable is empty; can't pick a writable data folder"
        )
    exe_dir = Path(sys.executable).resolve().parent
    if sys.platform == "darwin":
        for parent in (exe_dir, *exe_dir.parents):
            if parent.suffix == ".app":
                return parent.parent
    return exe_dir


def _data_home() -> Path:
    """The platform's per-user data folder; ``RuntimeError`` if there's no home folder."""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata and Path(appdata).is_absolute():
            return Path(appdata)
        return Path.home() / "AppData" / "Roaming"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg and Path(xdg).is_absolute():
        return Path(xdg)
    return Path.home() / ".local" / "share"


def user_data_dir(game: str, *, vendor: str = "VectorViolet") -> Path:
    """The per-user folder where ``game`` keeps its saves and databases.

    - Windows: ``%APPDATA%\\<vendor>\\<game>`` (``~/AppData/Roaming`` if
      ``APPDATA`` is unset, empty or relative)
    - macOS: ``~/Library/Application Support/<vendor>/<game>``
    - Linux and others: ``$XDG_DATA_HOME/<vendor>/<game>``, or
      ``~/.local/share/<vendor>/<game>`` if ``XDG_DATA_HOME`` is unset, empty
      or relative (the XDG spec says to ignore a relative value)
    - Web (emscripten): ``Path(".")``, so ``user_data_dir(game) / "saves"``
      is exactly the cwd-relative ``saves`` that ``SaveStore`` defaults to,
      and web saves keep their existing ``localStorage`` key. Only
      :class:`~pygamine.assets.save_store.SaveStore` persists there (in
      ``localStorage``); a ``Database`` lives in pygbag's in-memory file
      system and is lost on reload.

    If the home folder can't be determined, it logs a warning naming the
    folder it uses instead:

    - From source: the cwd-relative ``userdata/<game>``.
    - Packaged: ``userdata/<game>`` next to the executable (on macOS, next to
      the ``.app``), never inside the bundle: that is read-only under Program
      Files and wiped by an installer update. A read-only install then fails
      loudly on the first save instead of losing data silently on update.
      Raises ``RuntimeError`` if ``sys.executable`` is empty.

    ``vendor`` is the company folder that groups a studio's games.
    ``game`` and ``vendor`` must each be a single folder name, else
    ``ValueError``. Only builds the path; it creates nothing (``SaveStore``
    and ``Database`` create their own folder on first write).
    """
    _check_name("game", game)
    _check_name("vendor", vendor)
    if sys.platform == "emscripten":
        return Path(".")
    try:
        base = _data_home()
    except RuntimeError:  # Path.home() can't work out the home folder
        fallback = Path("userdata") / game
        if _is_packaged():
            fallback = _packaged_fallback_root() / fallback
        logger.warning(
            "Could not determine the home folder; using %s",
            fallback,
            exc_info=True,
        )
        return fallback
    return base / vendor / game


def packaged_data_dir(
    game: str, sub: str, *, vendor: str = "VectorViolet"
) -> Path | None:
    """Where ``game`` keeps the folder ``sub`` (e.g. ``"saves"``) in a packaged build.

    - Packaged (PyInstaller, ``sys._MEIPASS`` set -- the same test as
      :func:`resource_root`, so assets and saves can't disagree):
      ``user_data_dir(game, vendor=vendor) / sub``, which is never inside the
      bundle (see ``user_data_dir`` for the no-home-folder case).
    - Source runs and the web build: ``None``. A source run keeps each
      checkout's own cwd-relative folder, so worktrees stay isolated, and the
      web build keeps its ``localStorage`` keys.

    ``SaveStore`` and ``Database`` don't accept ``directory=None`` (their
    ``directory`` default is what tests patch to a temp folder). Pass
    ``directory=`` only when this returns a path::

        d = packaged_data_dir("mygame", "saves")
        store = SaveStore("save") if d is None else SaveStore("save", directory=d)

    ``game``, ``sub`` and ``vendor`` must each be a single folder name, else
    ``ValueError`` (checked in every mode). Creates nothing.
    """
    _check_name("game", game)
    _check_name("sub", sub)
    _check_name("vendor", vendor)
    if sys.platform == "emscripten" or not _is_packaged():
        return None
    return user_data_dir(game, vendor=vendor) / sub
