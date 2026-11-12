"""JSON-backed key-value persistence for settings and game saves.

Mirrors Database's `databases/<name>.db` (cwd-relative, auto-creating
folder) convention but for simple, human-readable JSON blobs instead of
SQL -- settings and save-game data are small, don't need relational
queries, and benefit from being easy to inspect/hand-edit for support.
Writes are atomic (temp file + os.replace) so a crash or power loss
mid-write can't corrupt the store.

One class serves both use cases -- a project typically keeps two named
stores, e.g. `SaveStore("settings")` and `SaveStore("save")`, both under
the same `saves/` folder.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class WebStorage(Protocol):
    """The part of the browser's `localStorage` that SaveStore uses."""

    def getItem(self, key: str) -> str | None: ...  # noqa: N802
    def setItem(self, key: str, value: str) -> None: ...  # noqa: N802
    def removeItem(self, key: str) -> None: ...  # noqa: N802


def _browser_storage() -> WebStorage | None:
    """The browser's `localStorage` in a pygbag (emscripten) build, else None.

    pygbag 0.9.3 mounts no persistent file system (files are lost on page
    reload), so saves live in localStorage there: synchronous, persistent
    and plenty for these small JSON blobs. This is the one place that
    gets hold of the browser, so tests can replace it with a fake. If the
    browser refuses access (blocked storage in a private or sandboxed
    frame), it warns and returns None, so saves use the in-memory file
    system for the session instead of crashing."""
    if sys.platform != "emscripten":
        return None
    try:
        import platform  # pygbag's platform module exposes the JS `window`

        return platform.window.localStorage
    except Exception:  # JS errors surface as arbitrary exception types
        logger.warning(
            "localStorage is unavailable; saves won't persist", exc_info=True
        )
        return None


class SaveStore:
    def __init__(self, name: str, directory: str = "saves") -> None:
        self.name = name
        self.directory = Path(directory)
        self.path = self.directory / f"{name}.json"
        self._web = _browser_storage()
        # localStorage is shared by the whole origin, so namespace the key.
        self._web_key = f"pygamine:{self.path.as_posix()}"

    def load(self, default: dict[str, Any] | None = None) -> dict[str, Any]:
        """Read the stored data. Returns a copy of `default` (or {}) if
        the file doesn't exist yet, or is unreadable/corrupt."""
        fallback = dict(default) if default else {}
        try:
            if self._web is not None:
                text = self._read_web()
                if text is None:
                    return fallback
                data = json.loads(text)
            else:
                if not self.path.exists():
                    return fallback
                with self.path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return fallback
        return data if isinstance(data, dict) else fallback

    def save(self, data: dict[str, Any]) -> None:
        """Overwrite the store with `data` (a full replace, not a merge --
        see `update()` for merging). On disk the write is atomic; in the
        browser it is a single localStorage `setItem`, and if the browser
        refuses it (quota exceeded, blocked storage) a warning is logged
        and the previous data stays."""
        if self._web is not None:
            try:
                # Compact JSON: localStorage has a small quota.
                self._web.setItem(
                    self._web_key, json.dumps(data, separators=(",", ":"))
                )
            except Exception:  # JS errors surface as arbitrary exception types
                logger.warning(
                    "Could not write %s to localStorage", self._web_key, exc_info=True
                )
            return
        self.directory.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, self.path)

    def update(self, **changes: Any) -> dict[str, Any]:
        """Merge `changes` into the existing stored data and persist."""
        data = self.load()
        data.update(changes)
        self.save(data)
        return data

    def get(self, key: str, default: Any = None) -> Any:
        return self.load().get(key, default)

    def exists(self) -> bool:
        if self._web is not None:
            return self._read_web() is not None
        return self.path.exists()

    def delete(self) -> None:
        """Remove the store entirely (e.g. clearing a game-over save so
        "Continue" doesn't offer to resume a run that's already lost).
        A no-op if there's nothing to delete."""
        if self._web is not None:
            try:
                self._web.removeItem(self._web_key)
            except Exception:  # JS errors surface as arbitrary exception types
                logger.warning(
                    "Could not delete %s from localStorage",
                    self._web_key,
                    exc_info=True,
                )
            return
        self.path.unlink(missing_ok=True)

    def _read_web(self) -> str | None:
        """The raw stored text, or None if there is none or the browser
        refuses the read. Anything that isn't a `str` (a JS `null` proxy)
        counts as missing."""
        assert self._web is not None
        try:
            text = self._web.getItem(self._web_key)
        except Exception:  # JS errors surface as arbitrary exception types
            logger.warning(
                "Could not read %s from localStorage", self._web_key, exc_info=True
            )
            return None
        return text if isinstance(text, str) else None
