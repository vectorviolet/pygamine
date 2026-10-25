from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, TypeVar, cast
from pygamine.ecs.components.component import Component, Behaviour
from pygamine.ecs.components.transform import Transform
from pygamine.ecs.components.sprite_renderer2d import SpriteRenderer2D
import pygame

C = TypeVar("C", bound=Component)


@dataclass
class _ScheduledCall:
    callback: Callable
    fire_at: int  # pygame ms
    interval: int | None  # None = one-shot; else repeat interval in ms


class GameObject:
    def __init__(self, name: str = "game_object"):
        self.name = name
        self._active: bool = True
        self._parent: GameObject | None = None
        self._children: list[GameObject] = []
        self._scheduled: list[_ScheduledCall] = []
        self.rect: Transform = Transform()
        self.rect.game_object = self
        self._components: dict[str, Component] = {"Transform": self.rect}
        self._image: pygame.Surface | None = None

    # ── active / hierarchy ───────────────────────────────────────────────────

    @property
    def active(self) -> bool:
        if not self._active:
            return False
        return self._parent is None or self._parent.active

    @active.setter
    def active(self, value: bool) -> None:
        if self._active == value:
            return
        old_effective = self.active
        self._active = value
        new_effective = self.active
        if old_effective != new_effective:
            self._on_active_changed(new_effective)

    def set_parent(self, parent: GameObject | None) -> None:
        if self._parent is not None:
            self._parent._children.remove(self)
        self._parent = parent
        if parent is not None:
            parent._children.append(self)

    def on_enable(self): ...
    def on_disable(self): ...

    def _on_active_changed(self, is_active: bool) -> None:
        if is_active:
            self.on_enable()
        else:
            self.on_disable()
        self._invoke_component_method("on_enable" if is_active else "on_disable")
        for child in self._children:
            if child._active:  # self-disabled children are already inactive; skip
                child._on_active_changed(is_active)

    # ── invoke / invoke_repeating ─────────────────────────────────────────────

    def invoke(self, callback: Callable, delay: float) -> None:
        fire_at = pygame.time.get_ticks() + int(delay * 1000)
        self._scheduled.append(_ScheduledCall(callback, fire_at, None))

    def invoke_repeating(
        self, callback: Callable, delay: float, interval: float
    ) -> None:
        fire_at = pygame.time.get_ticks() + int(delay * 1000)
        self._scheduled.append(_ScheduledCall(callback, fire_at, int(interval * 1000)))

    def cancel_invoke(self, callback: Callable | None = None) -> None:
        if callback is None:
            self._scheduled.clear()
        else:
            self._scheduled = [s for s in self._scheduled if s.callback is not callback]

    def _tick_scheduled(self) -> None:
        if not self._scheduled:
            return
        now = pygame.time.get_ticks()
        remaining = []
        for call in self._scheduled:
            if now >= call.fire_at:
                call.callback()
                if call.interval is not None:
                    call.fire_at += call.interval
                    remaining.append(call)
            else:
                remaining.append(call)
        self._scheduled = remaining

    # ── component system ──────────────────────────────────────────────────────

    @property
    def game_object(self) -> GameObject:
        return self

    @game_object.setter
    def game_object(self, value): ...

    def add_component(self, component_type: Callable[..., C], **kwargs) -> C:
        component = component_type(**kwargs)
        component.game_object = self
        self._components[component_type.__name__] = component
        if hasattr(component, "awake"):
            component.awake()
        return component

    def get_component(self, component_type: type[C]) -> C | None:
        return cast("C | None", self._components.get(component_type.__name__))

    @property
    def image(self) -> pygame.Surface | None:
        """Default `Drawable.image` (see camera.py). Settable, backed by
        `_image` -- some entities manage their own image directly (e.g. one
        rendered straight from text, with no SpriteRenderer2D involved at
        all) and expect a plain `self.image = ...` assignment to just work,
        the way it always has; setting it here takes priority over the
        component. Falls back to whatever the attached SpriteRenderer2D is
        currently showing if `_image` was never explicitly set, or None
        with neither. Exists so Camera.draw() never has to know about
        components or rotation -- override this property (not Camera) for
        an entity that switches between multiple images, e.g. a rotated
        variant of its base sprite."""
        if self._image is not None:
            return self._image
        renderer = self.get_component(SpriteRenderer2D)
        return renderer.image if renderer is not None else None

    @image.setter
    def image(self, value: pygame.Surface | None) -> None:
        self._image = value

    def handle_event(self, event: pygame.event.Event, mouse_position) -> None:
        if not self.active:
            return
        self._invoke_component_method("handle_event", event, mouse_position)

    def update(self) -> None:
        if not self.active:
            return
        self._tick_scheduled()
        self._invoke_component_method("update")

    def draw(self, surface: pygame.Surface) -> None:
        if not self.active:
            return
        self._invoke_component_method("draw", surface)

    def _invoke_component_method(self, method_name: str, *args, **kwargs) -> None:
        for component in self._components.values():
            is_enabled = not isinstance(component, Behaviour) or component.enabled
            if not is_enabled:
                continue
            method = getattr(component, method_name, None)
            if callable(method):
                method(*args, **kwargs)
