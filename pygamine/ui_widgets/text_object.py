from __future__ import annotations

import pygame

from pygamine.util.utils import Anchorable
from pygamine.ecs.game_object import GameObject
from pygamine.ecs.components.sprite_renderer2d import SpriteRenderer2D


class TextObject(GameObject, Anchorable):
    """A GUI-compatible text label.

    Single-state usage: pass `text=...`. Multi-state: pass `states={"default": ...,
    "hover": ..., "purchased": ...}` and the object auto-syncs to its parent's
    `_state` / `_hovered` on each event tick — drop a TextObject as a child of a
    HoverableStateObject to get state-driven labels without a wrapping Button class.
    """

    def __init__(
        self,
        parent,
        position,
        text: str = "",
        font: pygame.font.Font | None = None,
        color=(255, 255, 255),
        background_color=None,
        padding=None,
        anchor: str = "top-left",
        states: dict | None = None,
    ) -> None:
        GameObject.__init__(self)

        self.rect.parent = parent
        self.rect.anchor = anchor
        self._position_spec = position
        self.font = font
        self.color = self._parse_color(color)
        self.background_color = self._parse_color(background_color)
        self.padding = self._parse_padding(padding)

        self.states: dict = dict(states) if states else {}
        if "default" not in self.states:
            self.states["default"] = text or ""
        self.state: str | None = "default"
        self.text: str = self.states[self.state]

        self.add_component(SpriteRenderer2D)
        self._reflow()

    def set_text(self, text: str, *, state: str | None = None) -> None:
        """Update text content. With no state, edits the currently-active state."""
        target = state if state is not None else (self.state or "default")
        if self.states.get(target) == text:
            return
        self.states[target] = text
        if target == self.state:
            self.text = text
            self._reflow()

    def set_color(self, color) -> None:
        new_color = self._parse_color(color)
        if new_color == self.color:
            return
        self.color = new_color
        self._reflow()

    def set_state(self, state: str | None) -> None:
        if state == self.state:
            return
        if state is not None and state not in self.states:
            return
        self.state = state
        self.text = self.states.get(state, "") if state is not None else ""
        self._reflow()

    def update(self) -> None:
        super().update()
        if len(self.states) <= 1 or self.rect.parent is None:
            return
        parent_obj = getattr(self.rect.parent, "game_object", None)
        if parent_obj is None:
            return
        resolved = self._resolve_state_from(parent_obj)
        if resolved != self.state:
            self.set_state(resolved)

    def _resolve_state_from(self, parent) -> str | None:
        parent_state = getattr(parent, "state", None) or getattr(parent, "_state", None)
        if parent_state is not None and parent_state in self.states:
            return parent_state
        if getattr(parent, "_hovered", False) and "hover" in self.states:
            return "hover"
        if "default" in self.states:
            return "default"
        return self.state

    def _reflow(self) -> None:
        assert self.font is not None, "TextObject requires a font to render"
        text_surface = self.font.render(self.text, True, self.color)
        top, right, bottom, left = self.padding

        if self.background_color is None and self.padding == (0, 0, 0, 0):
            surface = text_surface
        else:
            tw, th = text_surface.get_size()
            surface = pygame.Surface(
                (tw + left + right, th + top + bottom), pygame.SRCALPHA
            )
            if self.background_color is not None:
                surface.fill(self.background_color)
            surface.blit(text_surface, (left, top))

        renderer = self.get_component(SpriteRenderer2D)
        assert renderer is not None
        renderer.set_image(surface)
        self.rect.size = surface.get_size()
        self.rect.set_position(self._position_spec)

    @staticmethod
    def _parse_color(color):
        if color is None:
            return None
        if isinstance(color, (list, tuple)):
            return tuple(color)
        return tuple(pygame.Color(str(color)))

    @staticmethod
    def _parse_padding(padding):
        """CSS-style: int -> all sides; [v, h]; [top, right, bottom, left]."""
        if padding is None:
            return (0, 0, 0, 0)
        if isinstance(padding, (int, float)):
            p = int(padding)
            return (p, p, p, p)
        if isinstance(padding, (list, tuple)):
            vals = [int(v) for v in padding]
            if len(vals) == 1:
                p = vals[0]
                return (p, p, p, p)
            if len(vals) == 2:
                v, h = vals
                return (v, h, v, h)
            if len(vals) == 4:
                return tuple(vals)
        raise ValueError(
            f"Invalid padding: {padding!r} (expected int, [v,h], or [top,right,bottom,left])"
        )
