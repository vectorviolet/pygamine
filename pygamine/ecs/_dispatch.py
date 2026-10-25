"""Shared handle_event/update/draw dispatch loop for GameObjectDict and
GameObjectList -- both forward to a plain iterable of their contents
(dict.values() vs. the list itself), so the loop body only needs to live
once.
"""

from __future__ import annotations

from typing import Iterable

import pygame


def dispatch_handle_event(
    objects: Iterable, event: pygame.event.Event, mouse_position
) -> None:
    for obj in objects:
        if not hasattr(obj, "handle_event"):
            continue
        if hasattr(obj, "active") and not obj.active:
            continue
        obj.handle_event(event, mouse_position)


def dispatch_update(objects: Iterable) -> None:
    for obj in objects:
        if not hasattr(obj, "update"):
            continue
        if hasattr(obj, "active") and not obj.active:
            continue
        obj.update()


def dispatch_draw(objects: Iterable, surface) -> None:
    for obj in objects:
        if not hasattr(obj, "draw"):
            continue
        if hasattr(obj, "active") and not obj.active:
            continue
        obj.draw(surface)
