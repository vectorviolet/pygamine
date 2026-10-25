"""Component-based StateObject: maps state keys to Surfaces, swaps via one SpriteRenderer2D.

StateObject — single image (or multi-state via add_state / add_surface); state set
via set_state or set_base_state. Exposes `state` (current visual key) and `focused`
(persistent keyboard-focus flag).

HoverableStateObject — adds a parallel _hover_images dict; handle_event swaps to the
hover surface when the mouse enters the rect (per-state, falls through to base if
missing). The hover surface is also shown when `focused` is true, so keyboard-focus
visuals reuse the hover artwork without faking a mouse position.
"""

from __future__ import annotations

from typing import Any
import pygame
from pygamine.assets.asset_path import PathLike
from pygamine.assets.image import load_image
from pygamine.ecs.game_object import GameObject
from pygamine.ecs.components.sprite_renderer2d import SpriteRenderer2D
from pygamine.ecs.components.transform import Transform
from pygamine.util.utils import Anchorable, MouseInteractive


class StateObject(Anchorable, MouseInteractive, GameObject):
    def __init__(
        self,
        parent: Transform | None = None,
        pos=("CENTER", "CENTER"),
        size=(0, 0),
        image_path: PathLike | None = None,
        nine_slice: int = 0,
        anchor: str = "top-left",
    ) -> None:

        super().__init__()

        self.rect.size = size
        self.rect.set_parent(parent)
        self.rect.anchor = anchor
        self.rect.set_position(pos)

        self._size = size
        self._nine_slice = nine_slice
        self._state: Any = None
        self._base_state: Any = None
        self._focused: bool = False
        self.images: dict[Any, pygame.Surface] = {}
        self.on_click_sound: Any = None

        self._renderer = self.add_component(SpriteRenderer2D)

        if image_path is not None:
            self.add_state(None, image_path)

    # ── state lookup / mutation ──────────────────────────────────────────────

    @property
    def state(self) -> Any:
        return self._state

    def add_state(self, state: Any, image_path: PathLike) -> None:
        self.add_surface(state, load_image(image_path, self._size, self._nine_slice))

    def add_surface(self, state: Any, surface: pygame.Surface) -> None:
        """Register a pre-rendered surface under a state key (no file load)."""
        self.images[state] = surface
        if state == self._state:
            self._renderer.set_image(surface)

    def set_state(self, state: Any) -> None:
        self._state = state
        if state in self.images:
            self._renderer.set_image(self._active_surface)

    def set_base_state(self, state: Any) -> None:
        """Set the persistent base state (separate from event-driven hover)."""
        self._base_state = state
        self.set_state(state)

    @property
    def focused(self) -> bool:
        return self._focused

    @focused.setter
    def focused(self, value: bool) -> None:
        if value == self._focused:
            return
        self._focused = value
        if self._state in self.images:
            self._renderer.set_image(self._active_surface)

    @property
    def _active_surface(self) -> pygame.Surface:
        return self.images[self._state]

    def info(self) -> tuple:
        return "StateObject Info:", {
            "state": self._state,
            "pos": self.rect.topleft,
            "size": self.rect.size,
        }


class HoverableStateObject(StateObject):
    def __init__(
        self,
        parent: Transform | None = None,
        pos=("CENTER", "CENTER"),
        size=(None, None),
        image_path: PathLike | None = None,
        hover_image_path: PathLike | None = None,
        nine_slice: int = 0,
        anchor: str = "top-left",
    ) -> None:
        super().__init__(parent, pos, size, image_path, nine_slice, anchor)
        self._hovered = False
        self._hover_images: dict[Any, pygame.Surface] = {}
        if hover_image_path is not None:
            self._hover_images[None] = load_image(
                hover_image_path, self._size, self._nine_slice
            )

    def add_state(
        self, state: Any, image_path: PathLike, hover_image_path: PathLike | None = None
    ) -> None:
        super().add_state(state, image_path)
        if hover_image_path is not None:
            self._hover_images[state] = load_image(
                hover_image_path, self._size, self._nine_slice
            )

    @property
    def _active_surface(self) -> pygame.Surface:
        if self._hovered or self._focused:
            if self._state in self._hover_images:
                return self._hover_images[self._state]
            if None in self._hover_images:
                return self._hover_images[None]
        return self.images[self._state]

    def handle_event(self, event, mouse_pos: tuple) -> None:
        if event.type != pygame.MOUSEMOTION:
            return
        was_hovered = self._hovered
        self._hovered = self.is_mouse_over(mouse_pos)
        if self._hovered != was_hovered:
            self._renderer.set_image(self._active_surface)
