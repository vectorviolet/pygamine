from __future__ import annotations

from collections.abc import KeysView

import pygame
from pygamine.ecs.game_object_dict import GameObjectDict


class PanelManager:
    def __init__(self, background_colors=None, starting_tab="") -> None:
        self._panels: dict[str, GameObjectDict] = {}
        self.background_colors = background_colors
        self._current_panel = starting_tab

    @property
    def current_panel(self) -> str:
        return self._current_panel

    @current_panel.setter
    def current_panel(self, name: str) -> None:
        """Switches panel; objects of the old one with an `on_hidden()` hook
        (tooltips) are told, so they drop pending state."""
        old = self._current_panel
        self._current_panel = name
        if old != name and old in self._panels:
            for obj in list(self._panels[old].values()):
                hook = getattr(obj, "on_hidden", None)
                if hook is not None:
                    hook()

    def __getitem__(self, name: str) -> GameObjectDict:
        return self._panels[name]

    def __contains__(self, name: object) -> bool:
        return name in self._panels

    def keys(self) -> KeysView[str]:
        return self._panels.keys()

    def handle_event(self, event: pygame.event.Event, mouse_position) -> None:
        if self.current_panel not in self._panels:
            return

        self._panels[self.current_panel].handle_event(event, mouse_position)

    def update(self) -> None:
        if self.current_panel not in self._panels:
            return

        self._panels[self.current_panel].update()

    def draw(self, surface) -> None:
        if self.background_colors and self.current_panel in self.background_colors:
            surface.fill(self.background_colors[self.current_panel])

        if self.current_panel not in self._panels:
            return

        self._panels[self.current_panel].draw(surface)

    def add_object(self, panel: str, name: str, obj) -> None:
        self.add_panel(panel)
        self._panels[panel][name] = obj

    def add_object_to_all(self, panels: tuple[str, ...], name: str, obj) -> None:
        for panel in panels:
            self.add_object(panel, name, obj)

    def add_panel(self, name: str) -> None:
        if name in self._panels:
            return

        self._panels[name] = GameObjectDict()

    def remove_panel(self, name: str) -> None:
        """Drops a panel and releases its objects (e.g. before reloading it)."""
        self._panels.pop(name).clear()

    def open_panel(self, panel: str) -> None:
        self.current_panel = panel
