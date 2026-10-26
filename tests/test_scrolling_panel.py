"""Unit tests for ScrollingPanel: a clipped viewport that adopts named sibling
objects of its panel and scrolls them upward at a frame-rate-independent
speed, looping or stopping once the content has left the top.
"""

from __future__ import annotations

import pygame
import pytest

from pygamine.ecs.components.transform import Transform
from pygamine.ecs.game_object import GameObject
from pygamine.ecs.game_object_dict import GameObjectDict
from pygamine.panels.panel_factory import make_scrolling_panel_factory
from pygamine.panels.panel_loader import PanelLoader
from pygamine.panels.panel_manager import PanelManager
from pygamine.ui_widgets.scrolling_panel import ScrollingPanel
from pygamine.util.utils import MouseInteractive


class Block(MouseInteractive, GameObject):
    """A solid-color box that records the calls ScrollingPanel forwards."""

    def __init__(self, y, height=20, color=(255, 0, 0)):
        GameObject.__init__(self)
        self.rect.topleft = (0, y)
        self.rect.size = (100, height)
        self.color = color
        self.updates = 0
        self.events = []

    def update(self):
        self.updates += 1

    def draw(self, surface):
        surface.fill(self.color, self.rect)

    def handle_event(self, event, mouse_position):
        self.events.append(event.type)


@pytest.fixture
def parent() -> Transform:
    return Transform(position=(0, 0), size=(200, 400))


def _panel_with(**objects) -> GameObjectDict:
    panel = GameObjectDict()
    for name, obj in objects.items():
        panel[name] = obj
    return panel


def _scroller(parent, targets, **kwargs) -> ScrollingPanel:
    # Viewport y 100..300; content gets adopted from a panel afterwards
    return ScrollingPanel(
        parent=parent, pos=(0, 100), size=(200, 200), targets=targets, **kwargs
    )


def _tick(scroller, fake_ticks, ms):
    fake_ticks["t"] += ms
    scroller.update()


# ── adoption ─────────────────────────────────────────────────────────────


def test_adopts_targets_out_of_the_panel(parent):
    a, b, other = Block(0), Block(50), Block(0)
    scroller = _scroller(parent, ["a", "b"])
    panel = _panel_with(scroller=scroller, a=a, b=b, other=other)

    scroller.on_panel_loaded(panel)

    assert "a" not in panel and "b" not in panel
    assert "other" in panel and "scroller" in panel


def test_unknown_target_raises(parent):
    scroller = _scroller(parent, ["missing"])
    with pytest.raises(KeyError, match="missing"):
        scroller.on_panel_loaded(_panel_with(scroller=scroller))


def test_content_starts_just_below_the_viewport_keeping_its_layout(parent):
    a, b = Block(30), Block(80)
    scroller = _scroller(parent, ["a", "b"])
    scroller.on_panel_loaded(_panel_with(a=a, b=b))

    assert a.rect.top == 300  # viewport bottom
    assert b.rect.top - a.rect.top == 50


# ── scrolling ────────────────────────────────────────────────────────────


def test_scrolls_up_at_speed_pixels_per_second(parent, fake_ticks):
    a = Block(0)
    scroller = _scroller(parent, ["a"], speed=100)
    scroller.on_panel_loaded(_panel_with(a=a))

    scroller.update()  # first update only sets the time baseline
    _tick(scroller, fake_ticks, 50)
    assert a.rect.top == 295

    # Same distance regardless of how the time is split into frames
    for _ in range(5):
        _tick(scroller, fake_ticks, 10)
    assert a.rect.top == 290


def test_long_gap_between_updates_is_capped(parent, fake_ticks):
    a = Block(0)
    scroller = _scroller(parent, ["a"], speed=100)
    scroller.on_panel_loaded(_panel_with(a=a))
    scroller.update()

    _tick(scroller, fake_ticks, 5000)  # e.g. another panel was open

    assert a.rect.top == 300 - 100 * ScrollingPanel.MAX_STEP_MS / 1000


def test_loops_once_content_has_left_the_top(parent, fake_ticks):
    a = Block(0, height=20)
    scroller = _scroller(parent, ["a"], speed=1000)
    scroller.on_panel_loaded(_panel_with(a=a))
    scroller.update()

    # 300 -> its bottom passes the viewport top (100) after 220 px
    for _ in range(3):
        _tick(scroller, fake_ticks, 70)  # 210 px: bottom at 110, still visible
    assert a.rect.top == 90
    _tick(scroller, fake_ticks, 20)  # 230 px: bottom at 90, gone

    assert a.rect.top == 300
    assert scroller.is_finished is False


def test_without_loop_stops_and_reports_finished(parent, fake_ticks):
    a = Block(0, height=20)
    scroller = _scroller(parent, ["a"], speed=1000, loop=False)
    scroller.on_panel_loaded(_panel_with(a=a))
    scroller.update()

    for _ in range(4):
        _tick(scroller, fake_ticks, 70)
    stopped_at = a.rect.top
    _tick(scroller, fake_ticks, 70)

    assert scroller.is_finished is True
    assert a.rect.top == stopped_at


def test_reset_restarts_from_below_the_viewport(parent, fake_ticks):
    a = Block(0)
    scroller = _scroller(parent, ["a"], speed=100, loop=False)
    scroller.on_panel_loaded(_panel_with(a=a))
    scroller.update()
    _tick(scroller, fake_ticks, 100)

    scroller.reset()

    assert a.rect.top == 300
    assert scroller.is_finished is False


def test_offset_survives_a_target_resetting_its_own_position(parent, fake_ticks):
    """A TextObject re-resolves its authored position on a state change in
    its own update(); the scroll offset must still win."""
    a = Block(0)

    def update_that_resets_position():
        a.rect.y = 0

    a.update = update_that_resets_position
    scroller = _scroller(parent, ["a"], speed=100)
    scroller.on_panel_loaded(_panel_with(a=a))
    scroller.update()
    _tick(scroller, fake_ticks, 100)

    assert a.rect.top == 290


# ── update / draw / events ───────────────────────────────────────────────


def test_updates_targets(parent):
    a = Block(0)
    scroller = _scroller(parent, ["a"])
    scroller.on_panel_loaded(_panel_with(a=a))

    scroller.update()

    assert a.updates == 1


def test_draw_is_clipped_to_the_viewport(parent):
    a = Block(0, height=400, color=(255, 0, 0))
    scroller = _scroller(parent, ["a"])
    scroller.on_panel_loaded(_panel_with(a=a))
    a.rect.top = 0  # covers the whole surface, inside and outside the viewport

    surface = pygame.Surface((200, 400))
    scroller.draw(surface)

    assert surface.get_at((50, 150))[:3] == (255, 0, 0)  # inside viewport
    assert surface.get_at((50, 50))[:3] == (0, 0, 0)  # above it
    assert surface.get_at((50, 350))[:3] == (0, 0, 0)  # below it
    assert surface.get_clip() == surface.get_rect()  # clip restored


def test_presses_outside_the_viewport_are_not_forwarded(parent):
    a = Block(0)
    scroller = _scroller(parent, ["a"])
    scroller.on_panel_loaded(_panel_with(a=a))

    press = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1)
    scroller.handle_event(press, (50, 50))  # above the viewport
    scroller.handle_event(press, (50, 150))  # inside it
    scroller.handle_event(pygame.event.Event(pygame.MOUSEMOTION), (50, 50))

    assert a.events == [pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION]


def test_inactive_scroller_does_nothing(parent, fake_ticks):
    a = Block(0)
    scroller = _scroller(parent, ["a"], speed=100)
    scroller.on_panel_loaded(_panel_with(a=a))
    scroller.active = False

    scroller.update()
    _tick(scroller, fake_ticks, 100)
    scroller.handle_event(pygame.event.Event(pygame.MOUSEMOTION), (50, 150))

    assert a.updates == 0 and a.events == []
    assert a.rect.top == 300


# ── through PanelLoader ──────────────────────────────────────────────────


def test_loaded_from_yaml_adopts_targets_declared_after_it(tmp_path, parent):
    yaml_path = tmp_path / "panels.yaml"
    yaml_path.write_text(
        "panels:\n"
        "  credits:\n"
        "    objects:\n"
        "      scroller: {type: scrolling_panel, position: [0, 100], size: [200, 200],\n"
        "                 speed: 50, loop: false, targets: [title]}\n"
        "      title: {type: block, position: [0, 30]}\n"
        "      back: {type: block, position: [0, 0]}\n"
    )
    pm = PanelManager()
    loader = PanelLoader(pm, parent, asset_manager=None)
    loader.register("scrolling_panel", make_scrolling_panel_factory(None))
    loader.register("block", lambda cfg, _parent: Block(cfg["position"][1]))

    loader.load(yaml_path)

    scroller = pm["credits"]["scroller"]
    assert isinstance(scroller, ScrollingPanel)
    assert "title" not in pm["credits"] and "back" in pm["credits"]
    assert (scroller.rect.topleft, scroller.rect.size) == ((0, 100), (200, 200))
    assert scroller.speed == 50 and scroller.loop is False
