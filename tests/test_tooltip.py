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


def move(tip: Tooltip, pos: tuple[int, int]) -> None:
    tip.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=pos), pos)


def click(tip: Tooltip, pos: tuple[int, int]) -> None:
    tip.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos), pos)


def show(tip: Tooltip, fake_ticks, pos=(110, 110)) -> None:
    """Hovers `pos` and lets the delay pass."""
    start = fake_ticks["t"]
    move(tip, pos)
    fake_ticks["t"] = start + tip.manager.delay_ms
    tip.update()
    assert tip.shown


def test_shows_after_delay_with_fake_clock(manager, fake_ticks) -> None:
    tip = make(manager)
    move(tip, (110, 110))
    fake_ticks["t"] = 399
    tip.update()
    assert not tip.shown
    fake_ticks["t"] = 400
    tip.update()
    assert tip.shown
    assert manager.current is tip


def test_delay_is_measured_from_entering(manager, fake_ticks) -> None:
    tip = make(manager)
    fake_ticks["t"] = 1000
    move(tip, (110, 110))
    fake_ticks["t"] = 1300
    move(tip, (111, 110))  # still inside: the timer keeps running
    fake_ticks["t"] = 1400
    tip.update()
    assert tip.shown


def test_leave_hides_and_cancels(manager, fake_ticks) -> None:
    tip = make(manager)
    move(tip, (110, 110))
    move(tip, (5, 5))
    fake_ticks["t"] = 1000
    tip.update()
    assert not tip.shown
    show(tip, fake_ticks)
    move(tip, (5, 5))
    assert not tip.shown
    assert manager.current is None


def test_click_hides_until_mouse_leaves(manager, fake_ticks) -> None:
    tip = make(manager)
    show(tip, fake_ticks)
    click(tip, (110, 110))
    assert not tip.shown
    move(tip, (112, 110))
    fake_ticks["t"] = 2000
    tip.update()
    assert not tip.shown
    move(tip, (5, 5))
    show(tip, fake_ticks)


def test_click_elsewhere_keeps_tooltip(manager, fake_ticks) -> None:
    tip = make(manager)
    show(tip, fake_ticks)
    click(tip, (5, 5))
    assert tip.shown


def test_only_one_visible(manager, fake_ticks) -> None:
    a = make(manager, (100, 100, 50, 20))
    b = make(manager, (120, 100, 50, 20), "save")
    show(a, fake_ticks)
    show(b, fake_ticks, (130, 110))
    assert not a.shown
    assert manager.current is b
    a.update()  # a must not pop back up
    assert not a.shown


def test_inactive_target_hides(manager, fake_ticks) -> None:
    tip = make(manager)
    show(tip, fake_ticks)
    tip.target.active = False
    tip.update()
    assert not tip.shown


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


def test_rebind_updates_shown_tooltip(manager, keys, fake_ticks) -> None:
    tip = make(manager)
    show(tip, fake_ticks)
    before = tip.rect.width
    keys.rebind("pause", pygame.K_F6)
    assert tip.key_label == "[F6]"
    assert tip.key_icon is None
    assert tip.rect.width != before  # re-rendered: bracketed text, not the icon


def test_language_change_updates_text(manager, loc, fake_ticks) -> None:
    tip = make(manager)
    show(tip, fake_ticks)
    surface_before = tip._surface
    loc.set_language("tr")
    assert tip.text == "Duraklat"
    assert tip._surface is not surface_before


def test_clamped_to_screen_and_flips_above(manager, fake_ticks) -> None:
    tip = make(manager, (SCREEN.right - 20, SCREEN.bottom - 20, 20, 20))
    show(tip, fake_ticks, (SCREEN.right - 5, SCREEN.bottom - 5))
    assert SCREEN.contains(tip.rect)
    assert tip.rect.bottom <= tip.target.rect.top
    corner = make(manager, (0, 0, 10, 10))
    show(corner, fake_ticks, (1, 1))
    assert SCREEN.contains(corner.rect)
    assert corner.rect.top >= corner.target.rect.bottom


def test_draw_blits_only_when_shown(manager, fake_ticks) -> None:
    tip = make(manager)
    surface = pygame.Surface(SCREEN.size)
    surface.fill((0, 0, 0))
    tip.draw(surface)
    assert pygame.mask.from_threshold(surface, (0, 0, 0), (1, 1, 1)).count() == (
        SCREEN.width * SCREEN.height
    )
    show(tip, fake_ticks)
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


def test_on_removed_hides(manager, fake_ticks) -> None:
    tip = make(manager)
    show(tip, fake_ticks)
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
