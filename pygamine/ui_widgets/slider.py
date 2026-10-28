from __future__ import annotations

from typing import Callable

import pygame

from pygamine.ecs.game_object import GameObject
from pygamine.ecs.components.sprite_renderer2d import SpriteRenderer2D
from pygamine.util.math_utils import clamp01
from pygamine.util.utils import Anchorable, MouseInteractive


class Slider(Anchorable, MouseInteractive, GameObject):
    """A horizontal 0..1 slider: a track/fill bar with a draggable handle.

    Drawn procedurally (no image assets) as a rounded track, a fill up to
    the current value, and a handle centered on the fill edge. Clicking
    anywhere on the bar jumps the value to that position; dragging follows
    the mouse. `on_change(value)` fires on every value change -- including
    mid-drag -- so callers get live feedback instead of only on release.
    """

    def __init__(
        self,
        parent=None,
        pos=("CENTER", "CENTER"),
        size=(300, 24),
        value: float = 1.0,
        handle_size: tuple[int, int] | None = None,
        track_color=(0, 0, 0, 120),
        fill_color=(46, 204, 113, 255),
        handle_color=(255, 255, 255, 255),
        anchor: str = "top-left",
        on_change: Callable[[float], None] | None = None,
    ) -> None:
        GameObject.__init__(self)

        self.rect.size = size
        self.rect.set_parent(parent)
        self.rect.anchor = anchor
        self.rect.set_position(pos)

        self._track_color = tuple(track_color)
        self._fill_color = tuple(fill_color)
        self._handle_color = tuple(handle_color)
        # Same height as the track by default -- taller handles overhang the
        # rect used for click/drag hit-testing, so callers opting into that
        # look must accept clicks near the overhang not registering.
        self._handle_size = tuple(handle_size) if handle_size else (size[1], size[1])
        self._value = clamp01(value)
        self._dragging = False
        self.on_change = on_change

        self._renderer = self.add_component(SpriteRenderer2D)
        self._redraw()

    @property
    def value(self) -> float:
        return self._value

    def set_value(self, value: float) -> None:
        """Set the value programmatically (e.g. to sync from saved settings)
        without firing `on_change` -- callers already know the new value."""
        new_value = clamp01(value)
        if new_value == self._value:
            return
        self._value = new_value
        self._redraw()

    def handle_event(self, event: pygame.event.Event, mouse_pos) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and self.is_mouse_over(mouse_pos):
                self._dragging = True
                self._update_from_pointer(mouse_pos[0])
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self._dragging = False
        elif event.type == pygame.MOUSEMOTION and self._dragging:
            self._update_from_pointer(mouse_pos[0])

    def _update_from_pointer(self, mouse_x: float) -> None:
        ratio = (mouse_x - self.rect.left) / self.rect.width if self.rect.width else 0.0
        new_value = clamp01(ratio)
        if new_value == self._value:
            return
        self._value = new_value
        self._redraw()
        if self.on_change:
            self.on_change(self._value)

    def _redraw(self) -> None:
        w, h = self.rect.size
        handle_w, handle_h = self._handle_size
        surf_h = max(h, handle_h)
        surface = pygame.Surface((w, surf_h), pygame.SRCALPHA)

        track_y = (surf_h - h) // 2
        pygame.draw.rect(
            surface, self._track_color, (0, track_y, w, h), border_radius=h // 2
        )

        fill_w = round(w * self._value)
        if fill_w > 0:
            pygame.draw.rect(
                surface, self._fill_color, (0, track_y, fill_w, h), border_radius=h // 2
            )

        handle_x = min(max(fill_w - handle_w / 2, 0), w - handle_w)
        handle_y = (surf_h - handle_h) / 2
        pygame.draw.rect(
            surface,
            self._handle_color,
            (handle_x, handle_y, handle_w, handle_h),
            border_radius=handle_h // 2,
        )

        self._renderer.set_image(surface)
