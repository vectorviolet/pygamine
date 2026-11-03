from __future__ import annotations

from collections.abc import Sequence
from typing import overload

import pygame

from pygamine.util.localization import (
    Localization,
    localization as default_localization,
)
from pygamine.util.utils import Anchorable
from pygamine.ecs.game_object import GameObject
from pygamine.ecs.components.sprite_renderer2d import SpriteRenderer2D


class TextObject(GameObject, Anchorable):
    """A GUI-compatible text label.

    Single-state usage: pass `text=...`. Multi-state: pass `states={"default": ...,
    "hover": ..., "purchased": ...}` and the object auto-syncs to its parent's
    `_state` / `_hovered` on each event tick — drop a TextObject as a child of a
    HoverableStateObject to get state-driven labels without a wrapping Button class.

    With `text_key=...` the default-state text comes from the localization
    table (`tr(text_key)`) and the label re-renders when the language changes;
    `text` and a default state are then an error. `text_params` fills the
    key's `{placeholders}` and persists across language switches (change it
    with `set_params`). Calling `set_text` on the default state replaces the
    key with a literal. Call `on_removed()` when the label is dropped.
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
        text_key: str | None = None,
        text_params: dict | None = None,
        localization: Localization | None = None,
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
        self.text_key = text_key
        self.text_params: dict = dict(text_params) if text_params else {}
        self._localization = localization or default_localization
        if text_key is not None:
            if text or "default" in self.states:
                raise ValueError(
                    f"text_key '{text_key}' cannot be combined with text or "
                    f"a default state"
                )
            text = self._localization.tr(text_key, **self.text_params)
            self._localization.register(self)

        if text_key is not None or "default" not in self.states:
            self.states["default"] = text or ""
        self.state: str | None = "default"
        self.text: str = self.states[self.state]

        self.add_component(SpriteRenderer2D)
        self._reflow()

    def apply_localized_text(self, text: str) -> None:
        """Sets the default-state text from the localization, keeping the key."""
        self._set_state_text("default", text)

    def set_params(self, **params) -> None:
        """Replaces the placeholder values of a `text_key` label and re-renders."""
        assert self.text_key is not None, "set_params() needs a text_key"
        text = self._localization.tr(self.text_key, **params)
        self.text_params = params
        self.apply_localized_text(text)

    def on_removed(self) -> None:
        """Stops following language changes (called when a panel drops the label)."""
        self._localization.unregister(self)

    def set_text(self, text: str, *, state: str | None = None) -> None:
        """Update text content. With no state, edits the currently-active state."""
        target = state if state is not None else (self.state or "default")
        if target == "default":
            # A literal set by the game replaces the key.
            self.text_key = None
            self.on_removed()
        self._set_state_text(target, text)

    def _set_state_text(self, target: str, text: str) -> None:
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

    @overload
    @staticmethod
    def _parse_color(color: None) -> None: ...

    @overload
    @staticmethod
    def _parse_color(color: str | Sequence[int]) -> tuple[int, ...]: ...

    @staticmethod
    def _parse_color(
        color: str | Sequence[int] | None,
    ) -> tuple[int, ...] | None:
        if color is None:
            return None
        if isinstance(color, (list, tuple)):
            return tuple(color)
        return tuple(pygame.Color(str(color)))

    @staticmethod
    def _parse_padding(padding) -> tuple[int, int, int, int]:
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
                top, right, bottom, left = vals
                return (top, right, bottom, left)
        raise ValueError(
            f"Invalid padding: {padding!r} (expected int, [v,h], or [top,right,bottom,left])"
        )
