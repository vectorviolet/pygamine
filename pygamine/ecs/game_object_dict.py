from __future__ import annotations

from typing import Any

import pygame

from pygamine.ecs._dispatch import dispatch_draw, dispatch_handle_event, dispatch_update


class GameObjectDict:
    def __init__(self) -> None:
        self._objects: dict[str, Any] = {}

    def __getitem__(self, key: str) -> Any:
        return self._objects[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._objects[key] = value

    def __contains__(self, key: object) -> bool:
        return key in self._objects

    def values(self):
        return self._objects.values()

    def pop(self, key: str) -> Any:
        return self._objects.pop(key)

    def handle_event(self, event: pygame.event.Event, mouse_position) -> None:
        dispatch_handle_event(self._objects.values(), event, mouse_position)

    def update(self) -> None:
        dispatch_update(self._objects.values())

    def draw(self, surface) -> None:
        dispatch_draw(self._objects.values(), surface)
