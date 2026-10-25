"""Single-line text field: click to focus, type to edit, backspace to delete.

Matches the rest of the package's widget conventions (GameObject-based,
parent/pos/size/anchor, a configurable font) instead of the raw pixel-rect
constructor this had before -- see CHANGELOG for the migration.
"""

from __future__ import annotations

import pygame

from pygamine.ecs.game_object import GameObject
from pygamine.ecs.components.sprite_renderer2d import SpriteRenderer2D
from pygamine.ecs.components.transform import Transform
from pygamine.util.utils import Anchorable, MouseInteractive

_DEFAULT_FONT_SIZE = 32


class InputBox(Anchorable, MouseInteractive, GameObject):
    """A single-line text field: click to focus, type to edit, backspace to
    delete. Grows to fit its content, never shrinking below the
    constructor's `size`."""

    def __init__(
        self,
        parent: Transform | None = None,
        pos=("CENTER", "CENTER"),
        size: tuple[int, int] = (200, 40),
        text: str = "",
        font: pygame.font.Font | None = None,
        text_color=(255, 255, 255),
        active_color=(30, 144, 255),  # ~= pygame.Color("dodgerblue2")
        inactive_color=(136, 172, 190),  # ~= pygame.Color("lightskyblue3")
        anchor: str = "top-left",
    ) -> None:
        GameObject.__init__(self)

        self._min_width = size[0]
        self._position_spec = pos
        self.rect.size = size
        self.rect.set_parent(parent)
        self.rect.anchor = anchor

        self.font = font or pygame.font.Font(None, _DEFAULT_FONT_SIZE)
        self.text = text
        self.text_color = tuple(text_color)
        self._active_color = tuple(active_color)
        self._inactive_color = tuple(inactive_color)
        self.focused = False

        self._renderer = self.add_component(SpriteRenderer2D)
        self._redraw()

    def handle_event(self, event: pygame.event.Event, mouse_position) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.focused = self.is_mouse_over(mouse_position)
            self._redraw()
        elif event.type == pygame.KEYDOWN and self.focused:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            else:
                self.text += event.unicode
            self._redraw()

    @property
    def border_color(self) -> tuple:
        return self._active_color if self.focused else self._inactive_color

    def _redraw(self) -> None:
        text_surface = self.font.render(self.text, True, self.text_color)
        width = max(self._min_width, text_surface.get_width() + 10)
        height = self.rect.height
        self.rect.size = (width, height)
        self.rect.set_position(self._position_spec)

        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        surface.blit(text_surface, (5, 5))
        pygame.draw.rect(surface, self.border_color, surface.get_rect(), 2)
        self._renderer.set_image(surface)
