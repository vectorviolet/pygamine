"""Tooltips: a small panel with a name and a key prompt, shown after hovering.

A game creates one `TooltipManager` (input map, font, key-name-to-icon lookup)
and gives it to `PanelLoader`. A button in the panels YAML then declares

    tooltip: {text_key: hud.pause, action: pause}

and the loader adds a `Tooltip` for it. The tooltip appears after the manager's
`delay_ms` (0.4 s) of hovering, hides on mouse leave and on click, stays inside
the screen, and only one is visible at a time. Its text follows language changes
and its key follows `InputMap` rebinds. The engine ships no icon images: keys the
game's icon lookup doesn't know are drawn as their bracketed name, e.g. [F5].

`PanelManager` hides a panel's tooltips when it stops being current.

See docs/decisions/0004-tooltips.md.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

import pygame

from pygamine.app.mouse import Mouse
from pygamine.assets.image import load_image
from pygamine.ecs.game_object import GameObject
from pygamine.util.input_map import InputMap
from pygamine.util.localization import (
    Localization,
    localization as default_localization,
)

# Key name (`pygame.key.name`, e.g. "f5") -> image path, or None for no icon.
IconLookup = Mapping[str, Any] | Callable[[str], Any]

DEFAULT_DELAY_MS = 400
# Mouse buttons that count as a click (left, middle, right; not the wheel).
CLICK_BUTTONS = (1, 2, 3)


class TooltipManager:
    """Shared settings and state of a game's tooltips: where key names get their
    icons, the look, the hover delay, and which tooltip is visible."""

    def __init__(
        self,
        input_map: InputMap,
        font: pygame.font.Font,
        icons: IconLookup | None = None,
        *,
        localization: Localization | None = None,
        delay_ms: int = DEFAULT_DELAY_MS,
        text_color: tuple[int, ...] = (255, 255, 255),
        background_color: tuple[int, ...] = (30, 30, 40, 235),
        border_color: tuple[int, ...] = (190, 190, 205),
        padding: int = 6,
        gap: int = 6,
        mouse: Mouse | None = None,
    ) -> None:
        self.input_map = input_map
        self.font = font
        self.localization = localization or default_localization
        self.delay_ms = delay_ms
        self.text_color = text_color
        self.background_color = background_color
        self.border_color = border_color
        self.padding = padding
        self.gap = gap
        # The game's `Mouse` gives the cursor in logical coordinates; without
        # one the raw pygame position is used.
        self._mouse = mouse
        self._icons = icons
        self._icon_cache: dict[str, pygame.Surface | None] = {}
        self._current: Tooltip | None = None

    @property
    def current(self) -> Tooltip | None:
        """The visible tooltip, if any."""
        return self._current

    def mouse_position(self) -> tuple[float, float]:
        if self._mouse is not None:
            return self._mouse.position
        return pygame.mouse.get_pos()

    @staticmethod
    def mouse_focused() -> bool:
        return pygame.mouse.get_focused()

    def hide(self) -> None:
        """Hides the visible tooltip. Switching panels does this by itself."""
        if self._current is not None:
            self._current.hide()

    def icon_for(self, key_name: str) -> pygame.Surface | None:
        """The icon for a key name scaled to the font height, or None if the
        game supplied none. Raises if the supplied image can't be loaded."""
        if key_name not in self._icon_cache:
            self._icon_cache[key_name] = self._load_icon(key_name)
        return self._icon_cache[key_name]

    def _load_icon(self, key_name: str) -> pygame.Surface | None:
        if self._icons is None:
            return None
        if callable(self._icons):
            path = self._icons(key_name)
        else:
            path = self._icons.get(key_name)
        if path is None:
            return None
        image = load_image(path)
        height = self.font.get_height()
        width = max(1, round(image.get_width() * height / image.get_height()))
        return pygame.transform.smoothscale(image, (width, height))

    def _show(self, tooltip: Tooltip) -> None:
        if self._current is not None and self._current is not tooltip:
            self._current.hide()
        self._current = tooltip

    def _hidden(self, tooltip: Tooltip) -> None:
        if self._current is tooltip:
            self._current = None


class Tooltip(GameObject):
    """The tooltip of one `target` object (usually a button).

    Shows `text_key` (with `text_params`) and, if `action` is given, the action's
    current key. Call `on_removed()` when dropping it (a panel does this): it
    unregisters the input-map and language callbacks.
    """

    def __init__(
        self,
        manager: TooltipManager,
        target: Any,
        bounds: pygame.Rect,
        text_key: str,
        action: str | None = None,
        text_params: dict[str, Any] | None = None,
    ) -> None:
        GameObject.__init__(self)
        self.manager = manager
        self.target = target
        self.bounds = bounds
        self.text_key = text_key
        self.action = action
        self.text_params: dict[str, Any] = dict(text_params or {})

        self._hover_since: int | None = None
        self._suppressed = False  # clicked: stay hidden until the mouse leaves
        self._shown = False
        self._surface: pygame.Surface | None = None
        self._registered = False

        # Validate before registering anything: a bad key or action must leave
        # nothing behind.
        self.text
        self.key_name
        manager.input_map.on_changed(self.refresh)
        manager.localization.on_language_changed(self._on_language_changed)
        self._registered = True

    # -- content ----------------------------------------------------------

    @property
    def text(self) -> str:
        """The name shown, in the current language."""
        return self.manager.localization.tr(self.text_key, **self.text_params)

    @property
    def key_name(self) -> str | None:
        """`pygame.key.name` of the action's current key, or None without an action."""
        if self.action is None:
            return None
        return pygame.key.name(self.manager.input_map.key_for(self.action))

    @property
    def key_icon(self) -> pygame.Surface | None:
        """The icon of the current key, or None (no action, or no icon)."""
        name = self.key_name
        return None if name is None else self.manager.icon_for(name)

    @property
    def key_label(self) -> str | None:
        """The bracketed key name, e.g. "[F5]", used when the key has no icon;
        None when there is no action or an icon is drawn instead."""
        name = self.key_name
        if name is None or self.manager.icon_for(name) is not None:
            return None
        return f"[{name.upper()}]"

    @property
    def shown(self) -> bool:
        return self._shown

    # -- lifecycle --------------------------------------------------------

    def refresh(self) -> None:
        """Re-reads the text and key (called on rebinds and language changes);
        re-renders now if visible, else on the next show."""
        if self._shown:
            self._build()

    def _on_language_changed(self, code: str) -> None:
        self.refresh()

    def on_removed(self) -> None:
        """Hides the tooltip and unregisters its callbacks (idempotent)."""
        self.hide()
        if not self._registered:
            return
        self._registered = False
        self.manager.input_map.remove_changed(self.refresh)
        self.manager.localization.remove_language_changed(self._on_language_changed)

    def hide(self) -> None:
        """Hides the tooltip and cancels a pending show. It reappears only after
        the mouse leaves and hovers again."""
        self._shown = False
        self._hover_since = None
        self.manager._hidden(self)

    # -- input / update / draw -------------------------------------------

    def _over_target(self) -> bool:
        """Whether the real mouse is on the (active) target right now. Read each
        frame, so it also holds when the cursor leaves the window or the target
        moves under a still cursor."""
        if not (self.target.active and self.manager.mouse_focused()):
            return False
        return bool(self.target.rect.collidepoint(self.manager.mouse_position()))

    def on_hidden(self) -> None:
        """Called by `PanelManager` when its panel stops being the current one:
        drops a visible or pending tooltip so it can't pop up on return."""
        self.hide()
        self._suppressed = False

    def handle_event(self, event: pygame.event.Event, mouse_position: Any) -> None:
        if not self.active:
            return
        if event.type == pygame.WINDOWLEAVE:
            self.on_hidden()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button in CLICK_BUTTONS:
            if self._over_target():
                self.hide()
                self._suppressed = True

    def update(self) -> None:
        if not self.active:
            return
        if not self._over_target():
            self.on_hidden()
            return
        if self._suppressed:
            return
        if self._shown:
            self._place()  # the target may have moved
            return
        now = pygame.time.get_ticks()
        if self._hover_since is None:
            self._hover_since = now
        if now - self._hover_since >= self.manager.delay_ms:
            self._shown = True
            self.manager._show(self)
            self._build()

    def draw(self, surface: pygame.Surface) -> None:
        if not self.active or not self._shown:
            return
        assert self._surface is not None
        surface.blit(self._surface, self.rect.topleft)

    # -- rendering --------------------------------------------------------

    def _build(self) -> None:
        """Renders the box for the current text and key, then places it."""
        self._surface = self._render()
        self.rect.size = self._surface.get_size()
        self._place()

    def _render(self) -> pygame.Surface:
        m = self.manager
        parts = [m.font.render(self.text, True, m.text_color)]
        icon, label = self.key_icon, self.key_label
        if icon is not None:
            parts.append(icon)
        elif label is not None:
            parts.append(m.font.render(label, True, m.text_color))
        width = sum(p.get_width() for p in parts) + m.gap * (len(parts) - 1)
        height = max(p.get_height() for p in parts)
        box = pygame.Surface(
            (width + 2 * m.padding, height + 2 * m.padding), pygame.SRCALPHA
        )
        box.fill(m.background_color)
        pygame.draw.rect(box, m.border_color, box.get_rect(), 1)
        x = m.padding
        for part in parts:
            box.blit(part, (x, m.padding + (height - part.get_height()) // 2))
            x += part.get_width() + m.gap
        return box

    def _place(self) -> None:
        """Below the target, centered on it; above it when there is no room
        below; always clamped inside the screen."""
        gap = self.manager.gap
        target = self.target.rect
        placed = pygame.Rect((0, 0), self.rect.size)
        placed.midtop = (target.centerx, target.bottom + gap)
        if placed.bottom > self.bounds.bottom:
            placed.midbottom = (target.centerx, target.top - gap)
        placed.clamp_ip(self.bounds)
        self.rect.topleft = placed.topleft
