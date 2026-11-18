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


def resource_root() -> Path:
    """Directory that contains the bundled ``assets/`` (and similar) trees.

    Frozen: the PyInstaller extraction dir. From source: the project root,
    walked up from ``src/pygamine/pygamine/assets/paths.py``.
    """
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle is not None:
        return Path(bundle)
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


def user_data_dir(game: str, *, vendor: str = "VectorViolet") -> Path:
    """The per-user folder where ``game`` keeps its saves and databases.

    - Windows: ``%APPDATA%\\<vendor>\\<game>`` (``~/AppData/Roaming`` if
      ``APPDATA`` is unset)
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

    If the home folder can't be determined, it logs a warning and falls back
    to the cwd-relative ``userdata/<game>``.

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
        if sys.platform == "win32":
            appdata = os.environ.get("APPDATA")
            base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        elif sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support"
        else:
            xdg = os.environ.get("XDG_DATA_HOME")
            if xdg and Path(xdg).is_absolute():
                base = Path(xdg)
            else:
                base = Path.home() / ".local" / "share"
    except RuntimeError:  # Path.home() can't work out the home folder
        logger.warning(
            "Could not determine the home folder; using ./userdata/%s",
            game,
            exc_info=True,
        )
        return Path("userdata") / game
    return base / vendor / game


def packaged_data_dir(
    game: str, sub: str, *, vendor: str = "VectorViolet"
) -> Path | None:
    """Where ``game`` keeps the folder ``sub`` (e.g. ``"saves"``) in a packaged build.

    Meant to be passed as the ``directory`` of ``SaveStore`` or ``Database``:
    ``SaveStore(directory=packaged_data_dir("mygame", "saves"))``. Both treat
    ``None`` as "use my cwd-relative default".

    - Packaged (PyInstaller, ``sys._MEIPASS`` set -- the same test as
      :func:`resource_root`, so assets and saves can't disagree):
      ``user_data_dir(game, vendor=vendor) / sub``.
    - Source runs and the web build: ``None``. A source run keeps each
      checkout's own cwd-relative folder, so worktrees stay isolated, and the
      web build keeps its ``localStorage`` keys.

    If the packaged build has no home folder (``user_data_dir`` could only
    give its cwd-relative fallback), the folder would end up inside the
    bundle: read-only under Program Files and wiped by an installer update.
    So it logs a warning and uses ``<folder of the executable>/userdata/<game>/<sub>``
    instead; a read-only install then fails on the first save, loudly, instead
    of losing data silently on update.

    ``game``, ``sub`` and ``vendor`` must each be a single folder name, else
    ``ValueError`` (checked in every mode). Creates nothing.
    """
    _check_name("game", game)
    _check_name("sub", sub)
    _check_name("vendor", vendor)
    if sys.platform == "emscripten" or getattr(sys, "_MEIPASS", None) is None:
        return None
    base = user_data_dir(game, vendor=vendor)
    if not base.is_absolute():
        base = Path(sys.executable).resolve().parent / "userdata" / game
        logger.warning(
            "No per-user data folder in the packaged build; using %s", base / sub
        )
    return base / sub
