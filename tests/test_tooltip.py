"""Tests for pygamine.ui_widgets.tooltip and the `tooltip:` panel entry."""

from __future__ import annotations

import pygame
import pytest

from pygamine.assets.asset_manager import AssetManager
from pygamine.ecs.components.transform import Transform
from pygamine.ecs.game_object import GameObject
from pygamine.panels.panel_loader import PanelLoader
from pygamine.panels.panel_manager import PanelManager
from pygamine.ui_widgets.tooltip import Tooltip, TooltipManager
from pygamine.util.input_map import InputMap
from pygamine.util.localization import Localization

SCREEN = pygame.Rect(0, 0, 400, 300)


class Button(GameObject):
    def __init__(self, rect: tuple[int, int, int, int]) -> None:
        super().__init__()
        self.rect.topleft = rect[:2]
        self.rect.size = rect[2:]


@pytest.fixture(autouse=True)
def _display() -> None:
    pygame.display.set_mode((1, 1))  # load_image converts surfaces


@pytest.fixture
def loc(tmp_path) -> Localization:
    folder = tmp_path / "lang"
    folder.mkdir()
    (folder / "en.yaml").write_text("tip: {pause: Pause}\n", encoding="utf-8")
    (folder / "tr.yaml").write_text("tip: {pause: Duraklat}\n", encoding="utf-8")
    lo = Localization()
    lo.load(folder)
    return lo


@pytest.fixture
def keys() -> InputMap:
    m = InputMap()
    m.declare("pause", pygame.K_p)
    m.declare("save", pygame.K_F5)
    return m


@pytest.fixture
def icon_path(tmp_path) -> str:
    path = tmp_path / "p.png"
    pygame.image.save(pygame.Surface((32, 32)), str(path))
    return str(path)


@pytest.fixture
def manager(keys, loc, icon_path) -> TooltipManager:
    return TooltipManager(
        keys, pygame.font.Font(None, 20), {"p": icon_path}, localization=loc
    )


def make(manager, rect=(100, 100, 50, 20), action="pause") -> Tooltip:
    return Tooltip(manager, Button(rect), SCREEN, "tip.pause", action)


class Cursor:
    """The fake mouse: where it is and whether the window has its focus."""

    def __init__(self, monkeypatch) -> None:
        self.pos: tuple[int, int] = (-1, -1)
        self.focused = True
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: self.pos)
        monkeypatch.setattr(pygame.mouse, "get_focused", lambda: self.focused)


@pytest.fixture
def cursor(monkeypatch) -> Cursor:
    return Cursor(monkeypatch)


def click(tip: Tooltip, button: int = 1) -> None:
    tip.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=button, pos=(0, 0)), (0, 0)
    )


def show(tip: Tooltip, fake_ticks, cursor, pos=(110, 110)) -> None:
    """Hovers `pos` and lets the delay pass."""
    cursor.pos = pos
    tip.update()
    fake_ticks["t"] += tip.manager.delay_ms
    tip.update()
    assert tip.shown


def test_shows_after_delay_with_fake_clock(manager, fake_ticks, cursor) -> None:
    tip = make(manager)
    cursor.pos = (110, 110)
    tip.update()
    fake_ticks["t"] = 399
    tip.update()
    assert not tip.shown
    fake_ticks["t"] = 400
    tip.update()
    assert tip.shown
    assert manager.current is tip


def test_delay_is_measured_from_entering(manager, fake_ticks, cursor) -> None:
    tip = make(manager)
    fake_ticks["t"] = 1000
    cursor.pos = (110, 110)
    tip.update()
    fake_ticks["t"] = 1300
    cursor.pos = (111, 110)  # still inside: the timer keeps running
    tip.update()
    fake_ticks["t"] = 1400
    tip.update()
    assert tip.shown


def test_leave_hides_and_cancels(manager, fake_ticks, cursor) -> None:
    tip = make(manager)
    cursor.pos = (110, 110)
    tip.update()
    cursor.pos = (5, 5)
    tip.update()
    fake_ticks["t"] = 1000
    tip.update()
    assert not tip.shown
    show(tip, fake_ticks, cursor)
    cursor.pos = (5, 5)
    tip.update()
    assert not tip.shown
    assert manager.current is None


def test_click_hides_until_mouse_leaves(manager, fake_ticks, cursor) -> None:
    tip = make(manager)
    show(tip, fake_ticks, cursor)
    click(tip)
    assert not tip.shown
    cursor.pos = (112, 110)
    fake_ticks["t"] += 2000
    tip.update()
    assert not tip.shown
    cursor.pos = (5, 5)
    tip.update()
    show(tip, fake_ticks, cursor)


@pytest.mark.parametrize("button", [1, 2, 3])
def test_every_real_button_suppresses(manager, fake_ticks, cursor, button) -> None:
    tip = make(manager)
    show(tip, fake_ticks, cursor)
    click(tip, button)
    assert not tip.shown


@pytest.mark.parametrize("button", [4, 5])
def test_wheel_does_not_hide(manager, fake_ticks, cursor, button) -> None:
    tip = make(manager)
    show(tip, fake_ticks, cursor)
    click(tip, button)
    assert tip.shown


def test_only_one_visible(manager, fake_ticks, cursor) -> None:
    a = make(manager, (100, 100, 50, 20))
    b = make(manager, (120, 100, 50, 20), "save")
    show(a, fake_ticks, cursor)
    show(b, fake_ticks, cursor, (130, 110))
    assert not a.shown
    assert manager.current is b
    a.update()  # a must not pop back up at once
    assert not a.shown


def test_inactive_target_hides(manager, fake_ticks, cursor) -> None:
    tip = make(manager)
    show(tip, fake_ticks, cursor)
    tip.target.active = False
    tip.update()
    assert not tip.shown


def test_cursor_leaving_window_hides(manager, fake_ticks, cursor) -> None:
    tip = make(manager)
    show(tip, fake_ticks, cursor)
    cursor.focused = False  # pygame keeps the last position when the mouse leaves
    tip.update()
    assert not tip.shown


def test_windowleave_event_hides(manager, fake_ticks, cursor) -> None:
    tip = make(manager)
    show(tip, fake_ticks, cursor)
    tip.handle_event(pygame.event.Event(pygame.WINDOWLEAVE), (0, 0))
    assert not tip.shown


def test_target_moving_under_still_cursor(manager, fake_ticks, cursor) -> None:
    tip = make(manager)
    show(tip, fake_ticks, cursor)
    tip.target.rect.x += 200  # e.g. a scrolling panel moves it away
    tip.update()
    assert not tip.shown
    tip.target.rect.x -= 200  # and back under the cursor: a fresh hover
    tip.update()
    assert not tip.shown
    fake_ticks["t"] += manager.delay_ms
    tip.update()
    assert tip.shown


def test_target_arriving_under_still_cursor_shows(manager, fake_ticks, cursor) -> None:
    tip = make(manager)
    cursor.pos = (310, 110)
    tip.update()
    tip.target.rect.x = 300
    tip.update()
    fake_ticks["t"] += manager.delay_ms
    tip.update()
    assert tip.shown


def test_shown_tooltip_follows_moving_target(manager, fake_ticks, cursor) -> None:
    tip = make(manager)
    show(tip, fake_ticks, cursor)
    before = tip.rect.x
    tip.target.rect.x += 5
    tip.update()
    assert tip.rect.x == before + 5


def test_panel_switch_mid_hover_does_not_show_on_return(
    manager, fake_ticks, cursor
) -> None:
    pm = PanelManager(starting_tab="one")
    tip = make(manager)
    pm.add_object("one", "tip", tip)
    pm.add_panel("two")
    cursor.pos = (110, 110)
    pm.update()  # hover starts at t=0
    fake_ticks["t"] = 200
    pm.open_panel("two")
    fake_ticks["t"] = 1000
    pm.open_panel("one")
    pm.update()  # the cursor is still on the button, but hovering restarts
    assert not tip.shown
    fake_ticks["t"] = 1400
    pm.update()
    assert tip.shown


def test_panel_switch_hides_visible_tooltip(manager, fake_ticks, cursor) -> None:
    pm = PanelManager(starting_tab="one")
    tip = make(manager)
    pm.add_object("one", "tip", tip)
    pm.add_panel("two")
    show(tip, fake_ticks, cursor)
    pm.open_panel("two")
    assert not tip.shown and manager.current is None


def test_manager_mouse_is_used_when_given(keys, loc) -> None:
    class FakeMouse:
        position = (110.0, 110.0)

    m = TooltipManager(keys, pygame.font.Font(None, 20), localization=loc)
    m._mouse = FakeMouse()  # type: ignore[assignment]
    assert m.mouse_position() == (110.0, 110.0)


def test_icon_used_when_available(manager) -> None:
    tip = make(manager)
    assert tip.key_name == "p"
    assert tip.key_icon is not None
    assert tip.key_icon.get_height() == manager.font.get_height()
    assert tip.key_label is None


def test_fallback_to_bracketed_key_name(manager) -> None:
    tip = make(manager, action="save")
    assert tip.key_icon is None
    assert tip.key_label == "[F5]"


def test_no_icons_at_all_and_callable_lookup(keys, loc, icon_path) -> None:
    font = pygame.font.Font(None, 20)
    plain = TooltipManager(keys, font, localization=loc)
    assert make(plain).key_label == "[P]"
    lookup = TooltipManager(
        keys, font, lambda n: icon_path if n == "p" else None, localization=loc
    )
    assert make(lookup).key_label is None
    assert make(lookup, action="save").key_label == "[F5]"


def test_no_action_means_text_only(manager) -> None:
    tip = Tooltip(manager, Button((100, 100, 50, 20)), SCREEN, "tip.pause")
    assert tip.key_name is None and tip.key_icon is None and tip.key_label is None


def test_rebind_updates_shown_tooltip(manager, keys, fake_ticks, cursor) -> None:
    tip = make(manager)
    show(tip, fake_ticks, cursor)
    before = tip.rect.width
    keys.rebind("pause", pygame.K_F6)
    assert tip.key_label == "[F6]"
    assert tip.key_icon is None
    assert tip.rect.width != before  # re-rendered: bracketed text, not the icon


def test_language_change_updates_text(manager, loc, fake_ticks, cursor) -> None:
    tip = make(manager)
    show(tip, fake_ticks, cursor)
    surface_before = tip._surface
    loc.set_language("tr")
    assert tip.text == "Duraklat"
    assert tip._surface is not surface_before


def test_clamped_to_screen_and_flips_above(manager, fake_ticks, cursor) -> None:
    tip = make(manager, (SCREEN.right - 20, SCREEN.bottom - 20, 20, 20))
    show(tip, fake_ticks, cursor, (SCREEN.right - 5, SCREEN.bottom - 5))
    assert SCREEN.contains(tip.rect)
    assert tip.rect.bottom <= tip.target.rect.top
    corner = make(manager, (0, 0, 10, 10))
    show(corner, fake_ticks, cursor, (1, 1))
    assert SCREEN.contains(corner.rect)
    assert corner.rect.top >= corner.target.rect.bottom


def test_draw_blits_only_when_shown(manager, fake_ticks, cursor) -> None:
    tip = make(manager)
    surface = pygame.Surface(SCREEN.size)
    surface.fill((0, 0, 0))
    tip.draw(surface)
    assert pygame.mask.from_threshold(surface, (0, 0, 0), (1, 1, 1)).count() == (
        SCREEN.width * SCREEN.height
    )
    show(tip, fake_ticks, cursor)
    tip.draw(surface)
    # The border color is drawn at the box's top-left corner.
    assert surface.get_at(tip.rect.topleft)[:3] == manager.border_color[:3]


def test_on_removed_unregisters_callbacks(manager, keys, loc) -> None:
    tip = make(manager)
    tip.on_removed()
    with pytest.raises(ValueError):
        keys.remove_changed(tip.refresh)
    with pytest.raises(ValueError):
        loc.remove_language_changed(tip._on_language_changed)
    tip.on_removed()  # idempotent


def test_on_removed_hides(manager, fake_ticks, cursor) -> None:
    tip = make(manager)
    show(tip, fake_ticks, cursor)
    tip.on_removed()
    assert manager.current is None


def test_bad_arguments_register_nothing(manager, keys, loc) -> None:
    with pytest.raises(KeyError):
        Tooltip(manager, Button((0, 0, 5, 5)), SCREEN, "tip.missing", "pause")
    with pytest.raises(KeyError):
        Tooltip(manager, Button((0, 0, 5, 5)), SCREEN, "tip.pause", "nope")
    assert keys._callbacks == [] and loc._callbacks == []


# -- panel loader -----------------------------------------------------------


@pytest.fixture
def loader(manager):
    pm = PanelManager()
    ld = PanelLoader(
        pm, Transform(position=(0, 0), size=(400, 300)), AssetManager(), manager
    )
    ld.register("button", lambda cfg, parent: Button((*cfg["position"], 40, 20)))
    return ld


def write(tmp_path, text: str):
    path = tmp_path / "panels.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_loader_adds_tooltip_after_all_objects(loader, tmp_path) -> None:
    loader.load(
        write(
            tmp_path,
            "panels:\n  hud:\n    objects:\n"
            "      pause:\n        type: button\n        position: [10, 10]\n"
            "        tooltip: {text_key: tip.pause, action: pause}\n"
            "      other:\n        type: button\n        position: [60, 10]\n",
        )
    )
    pm = loader.panel_manager
    assert list(pm["hud"]._objects) == ["pause", "other", "pause.tooltip"]
    tip = pm["hud"]["pause.tooltip"]
    assert tip.target is pm["hud"]["pause"] and tip.action == "pause"
    pm.remove_panel("hud")
    with pytest.raises(ValueError):
        tip.manager.input_map.remove_changed(tip.refresh)


@pytest.mark.parametrize(
    "tooltip",
    ["{action: pause}", "{text_key: tip.pause, color: red}", "pause"],
)
def test_loader_rejects_bad_tooltip(loader, tmp_path, tooltip) -> None:
    with pytest.raises(ValueError):
        loader.load(
            write(
                tmp_path,
                "panels:\n  hud:\n    objects:\n      b:\n        type: button\n"
                f"        position: [0, 0]\n        tooltip: {tooltip}\n",
            )
        )


def test_loader_without_manager_rejects_tooltip(tmp_path) -> None:
    ld = PanelLoader(
        PanelManager(), Transform(position=(0, 0), size=(400, 300)), AssetManager()
    )
    ld.register("button", lambda cfg, parent: Button((0, 0, 5, 5)))
    with pytest.raises(ValueError, match="no tooltips"):
        ld.load(
            write(
                tmp_path,
                "panels:\n  hud:\n    objects:\n      b:\n        type: button\n"
                "        position: [0, 0]\n        tooltip: {text_key: tip.pause}\n",
            )
        )


@pytest.mark.parametrize(
    "tooltip, message",
    [
        ("{text_key: tip.pause, action: puase}", "puase"),
        ("{text_key: tip.nope}", "tip.nope"),
        ("{text_key: tip.pause, text_params: 5}", "text_params"),
        ("{text_key: tip.pause, action: 7}", "action must be a string"),
        ("{text_key: 3}", "text_key"),
    ],
)
def test_loader_validation_names_panel_and_object(
    loader, tmp_path, tooltip, message
) -> None:
    with pytest.raises(ValueError, match=message) as info:
        loader.load(
            write(
                tmp_path,
                "panels:\n  hud:\n    objects:\n      b:\n        type: button\n"
                f"        position: [0, 0]\n        tooltip: {tooltip}\n",
            )
        )
    assert "'b' in panel 'hud'" in str(info.value)
    assert "hud" not in loader.panel_manager  # nothing half-loaded
