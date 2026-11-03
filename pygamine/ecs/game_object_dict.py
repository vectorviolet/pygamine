from __future__ import annotations

from collections.abc import ValuesView
from typing import Any

import pygame

from pygamine.ecs._dispatch import dispatch_draw, dispatch_handle_event, dispatch_update


def _on_removed(obj: Any) -> None:
    """Calls the optional `on_removed()` hook of an object being dropped (e.g. a
    localized TextObject unregisters itself)."""
    hook = getattr(obj, "on_removed", None)
    if hook is not None:
        hook()


class GameObjectDict:
    def __init__(self) -> None:
        self._objects: dict[str, Any] = {}

    def __getitem__(self, key: str) -> Any:
        return self._objects[key]

    def __setitem__(self, key: str, value: Any) -> None:
        old = self._objects.get(key)
        if old is not None and old is not value:
            _on_removed(old)
        self._objects[key] = value

    def __contains__(self, key: object) -> bool:
        return key in self._objects

    def values(self) -> ValuesView[Any]:
        return self._objects.values()

    def clear(self) -> None:
        """Removes every object, calling its `on_removed()` hook if it has one."""
        for obj in self._objects.values():
            _on_removed(obj)
        self._objects.clear()

    def pop(self, key: str) -> Any:
        return self._objects.pop(key)

    def handle_event(self, event: pygame.event.Event, mouse_position) -> None:
        dispatch_handle_event(self._objects.values(), event, mouse_position)

    def update(self) -> None:
        dispatch_update(self._objects.values())

    def draw(self, surface) -> None:
        dispatch_draw(self._objects.values(), surface)
