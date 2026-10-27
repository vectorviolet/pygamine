"""Unit tests for MouseInteractive: the is_mouse_over/is_clicked mixin
StateObject, Slider, and InputBox all build their click handling on top of.

Previously only exercised indirectly through those subclasses' own tests,
which never hit every branch (a non-left mouse button, visibility toggling
mid-press, an unrelated event type) -- these pin the mixin's own contract
directly.
"""

from __future__ import annotations

import pygame

from pygamine.util.utils import MouseInteractive


class _Box(MouseInteractive):
    def __init__(self, rect: pygame.Rect, visible: bool = True) -> None:
        self.rect = rect
        self.visible = visible


def _mousedown(pos, button=1) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=button)


def _mouseup(pos, button=1) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=button)


# ── is_mouse_over ─────────────────────────────────────────────────────────


def test_is_mouse_over_true_for_a_point_inside_the_rect():
    box = _Box(pygame.Rect(0, 0, 100, 100))
    assert box.is_mouse_over((50, 50)) is True


def test_is_mouse_over_false_for_a_point_outside_the_rect():
    box = _Box(pygame.Rect(0, 0, 100, 100))
    assert box.is_mouse_over((500, 500)) is False


def test_is_mouse_over_false_when_not_visible():
    box = _Box(pygame.Rect(0, 0, 100, 100), visible=False)
    assert box.is_mouse_over((50, 50)) is False


def test_is_mouse_over_false_for_none_mouse_pos():
    """mouse_pos is None when the cursor hasn't moved yet this session --
    must not raise trying to collidepoint(None)."""
    box = _Box(pygame.Rect(0, 0, 100, 100))
    assert box.is_mouse_over(None) is False


def test_is_mouse_over_uses_rect_directly_with_no_separate_parent_offset():
    """`self.rect` is expected to already be absolute (a Transform bakes its
    parent's offset in at set_position() time) -- is_mouse_over must not
    apply any further adjustment on top of that."""
    box = _Box(pygame.Rect(200, 200, 20, 20))
    assert box.is_mouse_over((210, 210)) is True
    assert box.is_mouse_over((10, 10)) is False


# ── is_clicked ────────────────────────────────────────────────────────────


def test_is_clicked_true_for_press_and_release_both_inside():
    box = _Box(pygame.Rect(0, 0, 100, 100))
    box.is_clicked(_mousedown((50, 50)), (50, 50))
    assert box.is_clicked(_mouseup((50, 50)), (50, 50)) is True


def test_is_clicked_false_when_release_is_outside_the_press():
    box = _Box(pygame.Rect(0, 0, 100, 100))
    box.is_clicked(_mousedown((50, 50)), (50, 50))
    assert box.is_clicked(_mouseup((500, 500)), (500, 500)) is False


def test_is_clicked_false_without_a_prior_press():
    box = _Box(pygame.Rect(0, 0, 100, 100))
    assert box.is_clicked(_mouseup((50, 50)), (50, 50)) is False


def test_mousedown_returns_false_immediately_never_completes_the_click_alone():
    box = _Box(pygame.Rect(0, 0, 100, 100))
    assert box.is_clicked(_mousedown((50, 50)), (50, 50)) is False


def test_is_clicked_ignores_a_non_left_button_press():
    box = _Box(pygame.Rect(0, 0, 100, 100))
    box.is_clicked(_mousedown((50, 50), button=3), (50, 50))  # right-click
    assert box.is_clicked(_mouseup((50, 50), button=1), (50, 50)) is False


def test_is_clicked_false_for_a_non_left_button_release():
    box = _Box(pygame.Rect(0, 0, 100, 100))
    box.is_clicked(_mousedown((50, 50), button=1), (50, 50))
    assert box.is_clicked(_mouseup((50, 50), button=3), (50, 50)) is False


def test_is_clicked_resets_press_state_even_on_a_non_left_release():
    box = _Box(pygame.Rect(0, 0, 100, 100))
    box.is_clicked(_mousedown((50, 50), button=1), (50, 50))
    box.is_clicked(_mouseup((50, 50), button=3), (50, 50))  # discards the press
    assert box.is_clicked(_mouseup((50, 50), button=1), (50, 50)) is False


def test_is_clicked_false_and_resets_press_state_when_not_visible():
    box = _Box(pygame.Rect(0, 0, 100, 100))
    box.is_clicked(_mousedown((50, 50)), (50, 50))
    box.visible = False
    assert box.is_clicked(_mouseup((50, 50)), (50, 50)) is False

    box.visible = True
    assert (
        box.is_clicked(_mouseup((50, 50)), (50, 50)) is False
    )  # press was discarded above


def test_is_clicked_false_for_an_unrelated_event_type():
    box = _Box(pygame.Rect(0, 0, 100, 100))
    box.is_clicked(_mousedown((50, 50)), (50, 50))
    event = pygame.event.Event(pygame.MOUSEMOTION, pos=(50, 50))
    assert box.is_clicked(event, (50, 50)) is False
    # the pending press survives an unrelated event in between
    assert box.is_clicked(_mouseup((50, 50)), (50, 50)) is True
