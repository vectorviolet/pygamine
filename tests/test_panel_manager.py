"""Unit tests for PanelManager: named panels of GameObjectDict, dispatching
handle_event/update/draw to only the currently-open panel (unlike
GameObjectDict/GameObjectList, which dispatch to everything they hold).
"""

from __future__ import annotations

import pygame
import pytest

from pygamine.panels.panel_manager import PanelManager


class _Tracked:
    def __init__(self):
        self.events = []
        self.updates = 0
        self.draws = 0

    def handle_event(self, event, mouse_pos):
        self.events.append(event)

    def update(self):
        self.updates += 1

    def draw(self, surface):
        self.draws += 1


# ── construction ────────────────────────────────────────────────────────


def test_defaults():
    pm = PanelManager()
    assert pm.background_colors is None
    assert pm.current_panel == ""
    assert list(pm.keys()) == []


def test_custom_starting_tab_and_background_colors():
    pm = PanelManager(background_colors={"menu": (1, 2, 3)}, starting_tab="menu")
    assert pm.current_panel == "menu"
    assert pm.background_colors == {"menu": (1, 2, 3)}


# ── __getitem__ / __contains__ / keys ──────────────────────────────────


def test_getitem_raises_keyerror_for_unregistered_panel():
    pm = PanelManager()
    with pytest.raises(KeyError):
        pm["nonexistent"]


def test_contains_reflects_registered_panels():
    pm = PanelManager()
    assert "menu" not in pm
    pm.add_panel("menu")
    assert "menu" in pm


def test_keys_lists_registered_panel_names():
    pm = PanelManager()
    pm.add_panel("menu")
    pm.add_panel("game")
    assert set(pm.keys()) == {"menu", "game"}


# ── add_panel ───────────────────────────────────────────────────────────


def test_add_panel_creates_an_empty_panel():
    pm = PanelManager()
    pm.add_panel("menu")
    assert "menu" in pm
    assert list(pm["menu"].values()) == []


def test_add_panel_is_idempotent():
    """Calling add_panel again for an existing name must not wipe its
    contents -- add_object relies on this to lazily create panels."""
    pm = PanelManager()
    pm.add_object("menu", "button", "a button")

    pm.add_panel("menu")

    assert pm["menu"]["button"] == "a button"


# ── add_object / add_object_to_all ──────────────────────────────────────


def test_add_object_auto_creates_the_panel():
    pm = PanelManager()
    pm.add_object("menu", "play_button", "obj")
    assert pm["menu"]["play_button"] == "obj"


def test_add_object_overwrites_same_name_in_same_panel():
    pm = PanelManager()
    pm.add_object("menu", "button", "first")
    pm.add_object("menu", "button", "second")
    assert pm["menu"]["button"] == "second"


def test_add_object_to_all_adds_the_same_object_to_every_named_panel():
    pm = PanelManager()
    obj = object()
    pm.add_object_to_all(("menu", "game", "pause"), "cursor", obj)

    assert pm["menu"]["cursor"] is obj
    assert pm["game"]["cursor"] is obj
    assert pm["pause"]["cursor"] is obj


# ── open_panel ────────────────────────────────────────────────────────


def test_open_panel_sets_current_panel():
    pm = PanelManager()
    pm.open_panel("game")
    assert pm.current_panel == "game"


def test_open_panel_does_not_require_the_panel_to_already_exist():
    pm = PanelManager()
    pm.open_panel("not_yet_registered")  # must not raise
    assert pm.current_panel == "not_yet_registered"


# ── handle_event / update / draw: only the current panel is dispatched ──


def test_only_the_current_panel_receives_update():
    pm = PanelManager()
    menu_obj = _Tracked()
    game_obj = _Tracked()
    pm.add_object("menu", "obj", menu_obj)
    pm.add_object("game", "obj", game_obj)
    pm.open_panel("menu")

    pm.update()

    assert menu_obj.updates == 1
    assert game_obj.updates == 0


def test_switching_panels_changes_which_one_is_dispatched():
    pm = PanelManager()
    menu_obj = _Tracked()
    game_obj = _Tracked()
    pm.add_object("menu", "obj", menu_obj)
    pm.add_object("game", "obj", game_obj)
    pm.open_panel("menu")
    pm.update()

    pm.open_panel("game")
    pm.update()

    assert menu_obj.updates == 1  # only got the one update from before the switch
    assert game_obj.updates == 1


def test_handle_event_reaches_only_the_current_panel():
    pm = PanelManager()
    menu_obj = _Tracked()
    game_obj = _Tracked()
    pm.add_object("menu", "obj", menu_obj)
    pm.add_object("game", "obj", game_obj)
    pm.open_panel("menu")

    event = pygame.event.Event(pygame.USEREVENT)
    pm.handle_event(event, (0, 0))

    assert menu_obj.events == [event]
    assert game_obj.events == []


def test_draw_reaches_only_the_current_panel():
    pm = PanelManager()
    menu_obj = _Tracked()
    game_obj = _Tracked()
    pm.add_object("menu", "obj", menu_obj)
    pm.add_object("game", "obj", game_obj)
    pm.open_panel("menu")

    pm.draw(pygame.Surface((10, 10)))

    assert menu_obj.draws == 1
    assert game_obj.draws == 0


def test_dispatch_to_an_unregistered_current_panel_is_a_no_op():
    pm = PanelManager()
    pm.open_panel("nonexistent")

    pm.handle_event(pygame.event.Event(pygame.USEREVENT), (0, 0))  # must not raise
    pm.update()
    pm.draw(pygame.Surface((10, 10)))


# ── draw: background fill ───────────────────────────────────────────────


def test_draw_fills_background_color_for_the_current_panel():
    pm = PanelManager(background_colors={"menu": (10, 20, 30)})
    pm.open_panel("menu")
    surface = pygame.Surface((10, 10))

    pm.draw(surface)

    assert surface.get_at((5, 5)) == (10, 20, 30, 255)


def test_draw_fills_background_even_if_the_panel_is_not_registered_yet():
    """Background fill runs before the panel-existence check, so a
    background color for a not-yet-populated panel still shows."""
    pm = PanelManager(background_colors={"menu": (10, 20, 30)})
    pm.open_panel("menu")  # never added via add_panel/add_object
    surface = pygame.Surface((10, 10))

    pm.draw(surface)

    assert surface.get_at((5, 5)) == (10, 20, 30, 255)


def test_draw_does_not_fill_when_background_colors_is_none():
    pm = PanelManager(background_colors=None)
    pm.open_panel("menu")
    surface = pygame.Surface((10, 10))
    surface.fill((1, 2, 3))

    pm.draw(surface)

    assert surface.get_at((5, 5)) == (1, 2, 3, 255)  # untouched


def test_draw_does_not_fill_when_current_panel_has_no_matching_color():
    pm = PanelManager(background_colors={"menu": (10, 20, 30)})
    pm.open_panel("game")  # not a key in background_colors
    surface = pygame.Surface((10, 10))
    surface.fill((1, 2, 3))

    pm.draw(surface)

    assert surface.get_at((5, 5)) == (1, 2, 3, 255)
