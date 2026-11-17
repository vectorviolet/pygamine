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

Assumes the standard submodule layout, ``<project_root>/src/pygamine/`` --
:func:`resource_root` walks up from this file's location, so a host project
vendoring pygamine somewhere else needs its own variant instead.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


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


def user_data_dir(game: str) -> Path:
    """The per-user folder where ``game`` keeps its saves and databases.

    - Windows: ``%APPDATA%\\VectorViolet\\<game>`` (``~/AppData/Roaming`` if
      ``APPDATA`` is unset)
    - macOS: ``~/Library/Application Support/VectorViolet/<game>``
    - Linux and others: ``$XDG_DATA_HOME/VectorViolet/<game>``, or
      ``~/.local/share/VectorViolet/<game>`` if ``XDG_DATA_HOME`` is unset or empty
    - Web (emscripten): the relative ``userdata/<game>``, since the browser has
      no per-user folder; :class:`~pygamine.assets.save_store.SaveStore` keeps
      its data in ``localStorage`` there anyway.

    Only builds the path; it creates nothing (``SaveStore`` and ``Database``
    create their own folder on first write).
    """
    if sys.platform == "emscripten":
        return Path("userdata") / game
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "VectorViolet" / game
