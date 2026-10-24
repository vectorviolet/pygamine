from __future__ import annotations

import pygame

from pygamine.ecs._dispatch import dispatch_draw, dispatch_handle_event, dispatch_update
from pygamine.ecs.game_object import GameObject
from pygamine.ecs.game_object_dict import GameObjectDict


class ScrollingPanel(GameObject):
    """A viewport that scrolls a set of objects from its panel upward,
    clipped to its own rect -- e.g. end credits.

    `rect` is the visible viewport. `targets` names sibling objects of the
    same panel, authored at ordinary positions that lay them out relative to
    each other. Once the panel finishes loading, PanelLoader calls
    `on_panel_loaded()` and this takes ownership of them: they're removed
    from the panel, so only this object updates them, draws them (clipped to
    the viewport) and forwards events to them -- no per-frame juggling of
    their `active` flag, and interactive content keeps working.

    Content starts just below the viewport and moves up at `speed` px/s,
    independent of frame rate. Once it has fully left the top it starts over
    (`loop=True`) or stops and sets `is_finished`.
    """

    # Caps one update's step, so returning to a panel that wasn't updated
    # for a while (another panel was open) doesn't jump the scroll.
    MAX_STEP_MS = 100

    def __init__(
        self,
        parent=None,
        pos=(0, 0),
        size=(0, 0),
        targets: list[str] | tuple[str, ...] = (),
        speed: float = 60.0,
        loop: bool = True,
        anchor: str = "top-left",
    ) -> None:
        GameObject.__init__(self)

        self.rect.size = size
        self.rect.set_parent(parent)
        self.rect.anchor = anchor
        self.rect.set_position(pos)

        self.speed = speed
        self.loop = loop
        self.is_finished = False

        self._target_names = list(targets)
        self._targets: list = []
        self._base_y: list[int] = []
        self._content_top = 0
        self._content_bottom = 0
        self._offset = 0.0
        self._last_tick: int | None = None

    def on_panel_loaded(self, panel: GameObjectDict) -> None:
        for name in self._target_names:
            if name not in panel:
                raise KeyError(f"ScrollingPanel target '{name}' is not an object of its panel")
            self._targets.append(panel.pop(name))

        self._base_y = [obj.rect.y for obj in self._targets]
        if self._targets:
            self._content_top = min(obj.rect.top for obj in self._targets)
            self._content_bottom = max(obj.rect.bottom for obj in self._targets)
        self.reset()

    def reset(self) -> None:
        """Restarts the scroll with the content just below the viewport."""
        self._offset = self._start_offset()
        self._last_tick = None
        self.is_finished = False
        self._apply_offset()

    def _start_offset(self) -> float:
        return self.rect.bottom - self._content_top

    def update(self) -> None:
        if not self.active:
            return
        super().update()

        now = pygame.time.get_ticks()
        if self._last_tick is not None and not self.is_finished:
            step_ms = min(now - self._last_tick, self.MAX_STEP_MS)
            self._offset -= self.speed * step_ms / 1000
            if self._content_bottom + self._offset < self.rect.top:
                if self.loop:
                    self._offset = self._start_offset()
                else:
                    self.is_finished = True
        self._last_tick = now

        dispatch_update(self._targets)
        # After the targets' own update: a TextObject re-resolves its
        # authored position when its state changes, so the offset is
        # applied last to win.
        self._apply_offset()

    def _apply_offset(self) -> None:
        offset = round(self._offset)
        for obj, base_y in zip(self._targets, self._base_y):
            obj.rect.y = base_y + offset

    def draw(self, surface: pygame.Surface) -> None:
        if not self.active:
            return
        super().draw(surface)

        old_clip = surface.get_clip()
        surface.set_clip(self.rect.clip(old_clip))
        dispatch_draw(self._targets, surface)
        surface.set_clip(old_clip)

    def handle_event(self, event: pygame.event.Event, mouse_position) -> None:
        if not self.active:
            return
        super().handle_event(event, mouse_position)

        # Content outside the viewport is clipped away, so it mustn't be
        # pressable there; everything else (motion, releases, keys) passes
        # through so hover and drag state stay consistent.
        if event.type == pygame.MOUSEBUTTONDOWN and not self.rect.collidepoint(mouse_position):
            return
        dispatch_handle_event(self._targets, event, mouse_position)
