"""Unit tests for Slider: a procedurally-drawn 0..1 slider (track + fill +
handle) with click-to-jump and drag interaction.

No image files needed -- Slider draws with pygame.draw rather than loading
assets, so these tests only need a display mode set (dummy SDL driver) for
Surface/SRCALPHA operations.
"""

from __future__ import annotations

import pygame
import pytest

from pygamine.ecs.components.transform import Transform
from pygamine.ui_widgets.slider import Slider


@pytest.fixture(autouse=True)
def display_mode():
    pygame.display.set_mode((1, 1))


@pytest.fixture
def parent():
    return Transform(position=(0, 0), size=(800, 600))


def _down(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos)


def _up(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=pos)


def _move(pos):
    return pygame.event.Event(pygame.MOUSEMOTION, pos=pos)


# ── construction ─────────────────────────────────────────────────────────


def test_construction_positions_and_sizes_the_rect(parent):
    slider = Slider(parent=parent, pos=(10, 20), size=(300, 24))
    assert slider.rect.size == (300, 24)
    assert slider.rect.topleft == (10, 20)


def test_construction_clamps_an_out_of_range_initial_value(parent):
    assert Slider(parent=parent, pos=(0, 0), size=(300, 24), value=1.5).value == 1.0
    assert Slider(parent=parent, pos=(0, 0), size=(300, 24), value=-0.5).value == 0.0


def test_construction_defaults_on_change_to_none(parent):
    slider = Slider(parent=parent, pos=(0, 0), size=(300, 24))
    assert slider.on_change is None


# ── set_value ────────────────────────────────────────────────────────────


def test_set_value_updates_value_and_redraws(parent):
    slider = Slider(parent=parent, pos=(0, 0), size=(300, 24), value=0.0)
    before = slider._renderer.image

    slider.set_value(0.5)

    assert slider.value == 0.5
    assert slider._renderer.image is not before


def test_set_value_clamps_out_of_range_input(parent):
    slider = Slider(parent=parent, pos=(0, 0), size=(300, 24), value=0.0)
    slider.set_value(2.0)
    assert slider.value == 1.0
    slider.set_value(-1.0)
    assert slider.value == 0.0


def test_set_value_to_the_same_value_is_a_no_op(parent):
    slider = Slider(parent=parent, pos=(0, 0), size=(300, 24), value=0.5)
    before = slider._renderer.image

    slider.set_value(0.5)

    assert slider._renderer.image is before  # no redraw triggered


def test_set_value_does_not_call_on_change(parent):
    calls = []
    slider = Slider(
        parent=parent, pos=(0, 0), size=(300, 24), value=0.0, on_change=calls.append
    )

    slider.set_value(0.5)

    assert calls == []


# ── handle_event: click-to-jump ─────────────────────────────────────────


def test_click_inside_the_track_jumps_to_that_position(parent):
    calls = []
    slider = Slider(
        parent=parent, pos=(0, 0), size=(200, 24), value=0.0, on_change=calls.append
    )

    slider.handle_event(_down((100, 12)), (100, 12))  # 50% across

    assert slider.value == 0.5
    assert calls == [0.5]


def test_click_at_the_left_edge_sets_value_to_zero(parent):
    slider = Slider(parent=parent, pos=(0, 0), size=(200, 24), value=1.0)
    slider.handle_event(_down((0, 12)), (0, 12))
    assert slider.value == 0.0


def test_click_past_the_right_edge_clamps_to_one(parent):
    """Shouldn't happen in practice (is_mouse_over gates entry), but the
    ratio math itself must still clamp defensively."""
    slider = Slider(parent=parent, pos=(0, 0), size=(200, 24), value=0.0)
    slider._dragging = True
    slider._update_from_pointer(999)
    assert slider.value == 1.0


def test_click_outside_the_track_does_not_start_dragging_or_change_value(parent):
    calls = []
    slider = Slider(
        parent=parent, pos=(0, 0), size=(200, 24), value=0.3, on_change=calls.append
    )

    slider.handle_event(_down((999, 999)), (999, 999))

    assert slider._dragging is False
    assert slider.value == 0.3
    assert calls == []


# ── handle_event: drag ───────────────────────────────────────────────────


def test_drag_follows_the_mouse_across_multiple_motion_events(parent):
    calls = []
    slider = Slider(
        parent=parent, pos=(0, 0), size=(200, 24), value=0.0, on_change=calls.append
    )

    slider.handle_event(
        _down((0, 12)), (0, 12)
    )  # ratio 0.0 == current value -> no call
    slider.handle_event(_move((50, 12)), (50, 12))
    slider.handle_event(_move((150, 12)), (150, 12))

    assert slider.value == 0.75
    assert calls == [0.25, 0.75]


def test_mouse_motion_without_a_prior_mouse_down_does_not_update_value(parent):
    calls = []
    slider = Slider(
        parent=parent, pos=(0, 0), size=(200, 24), value=0.2, on_change=calls.append
    )

    slider.handle_event(_move((150, 12)), (150, 12))

    assert slider.value == 0.2
    assert calls == []


def test_mouse_up_stops_the_drag(parent):
    calls = []
    slider = Slider(
        parent=parent, pos=(0, 0), size=(200, 24), value=0.0, on_change=calls.append
    )

    slider.handle_event(_down((0, 12)), (0, 12))
    slider.handle_event(_up((0, 12)), (0, 12))
    calls.clear()
    slider.handle_event(_move((150, 12)), (150, 12))

    assert slider.value == 0.0  # unaffected -- drag already ended
    assert calls == []


def test_on_change_not_called_when_the_ratio_rounds_to_the_same_value(parent):
    slider = Slider(parent=parent, pos=(0, 0), size=(200, 24), value=0.0)
    slider._dragging = True

    calls = []
    slider.on_change = calls.append
    slider._update_from_pointer(0)  # ratio 0.0, already at 0.0 -> no change

    assert calls == []
