from __future__ import annotations

from typing import Any

import pygame


class MouseInteractive:
    """Adds is_mouse_over and is_clicked behavior.

    `self.rect` is expected to already be in absolute coordinates -- a
    Transform's `set_position()` bakes its parent's offset in at
    position-set time, so no separate parent-relative adjustment is needed
    here (or possible: pygame.Rect doesn't support Rect + Rect anyway).
    """

    # `rect` may be a plain pygame.Rect or a Transform (which subclasses pygame.Rect
    # but adds extra methods). Declared as Any to allow either in subclasses.
    rect: Any
    visible: bool = True

    # Press-tracking instance state
    _pressed: bool = False

    def is_mouse_over(self, mouse_pos) -> bool:
        return (
            mouse_pos is not None and self.rect.collidepoint(mouse_pos) and self.visible
        )

    def is_clicked(self, event, mouse_pos) -> bool:
        """Returns True: mouse was pressed AND released over this object."""
        if not self.visible:
            self._pressed = False
            return False

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and self.is_mouse_over(mouse_pos):
                self._pressed = True
            return False

        if event.type == pygame.MOUSEBUTTONUP:
            was_pressed = self._pressed
            self._pressed = False  # always reset
            return was_pressed and event.button == 1 and self.is_mouse_over(mouse_pos)

        return False


def resolve_size(size, window_size) -> tuple:
    if size == "WINDOW":
        return tuple(window_size)
    if isinstance(size, list) and len(size) == 2:
        return tuple(size)
    raise ValueError(f"Invalid size: {size!r}")


# Normalized (x, y) reference point within parent and child rects.
# anchor_xy * size gives the pixel offset for both ends of the anchor relation.
ANCHORS = {
    "top-left": (0.0, 0.0),
    "top": (0.5, 0.0),
    "top-right": (1.0, 0.0),
    "left": (0.0, 0.5),
    "center": (0.5, 0.5),
    "right": (1.0, 0.5),
    "bottom-left": (0.0, 1.0),
    "bottom": (0.5, 1.0),
    "bottom-right": (1.0, 1.0),
}


class Anchorable:
    """Resolves a position spec relative to a named anchor point.

    With the default anchor ('top-left') the legacy 'CENTER' tokens in the
    position spec are honored, so old call sites keep working unchanged.
    When a non-default anchor is given, position is treated as a pixel
    offset from the parent's anchor point applied to the child's matching
    anchor point — e.g. anchor='bottom-right', position=[-25, -25] insets
    the child's bottom-right corner by 25px from the parent's bottom-right.
    """

    @staticmethod
    def resolve_pos(pos, parent_size, obj_size, anchor: str = "top-left") -> tuple:
        x, y = pos
        if anchor == "top-left":
            if x == "CENTER":
                x = (parent_size[0] - obj_size[0]) / 2
            if y == "CENTER":
                y = (parent_size[1] - obj_size[1]) / 2
            return (x, y)
        if anchor not in ANCHORS:
            raise ValueError(
                f"Unknown anchor {anchor!r}; expected one of {sorted(ANCHORS)}"
            )
        ax, ay = ANCHORS[anchor]
        return (
            x + parent_size[0] * ax - obj_size[0] * ax,
            y + parent_size[1] * ay - obj_size[1] * ay,
        )
