"""Unit tests for InputBox: a text-entry widget (click to focus, type,
backspace, auto-widening), built like the rest of the package's widgets
(GameObject-based, parent/pos/size/anchor)."""

from __future__ import annotations

import pygame

from pygamine.ui_widgets.input_box import InputBox


def test_construction_sets_rect_text_and_defaults():
    box = InputBox(pos=(10, 20), size=(200, 32), text="hi")
    assert box.rect.topleft == (10, 20)
    assert box.rect.size == (200, 32)
    assert box.text == "hi"
    assert box.focused is False
    assert box.border_color == box._inactive_color


def test_construction_defaults_to_empty_text():
    box = InputBox(pos=(0, 0), size=(200, 32))
    assert box.text == ""


# ── handle_event: focus via click ──────────────────────────────────────


def test_click_inside_focuses_and_uses_active_color():
    box = InputBox(pos=(0, 0), size=(200, 32))
    event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(10, 10))

    box.handle_event(event, (10, 10))

    assert box.focused is True
    assert box.border_color == box._active_color


def test_click_outside_unfocuses_and_uses_inactive_color():
    box = InputBox(pos=(0, 0), size=(200, 32))
    box.focused = True
    event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(500, 500))

    box.handle_event(event, (500, 500))

    assert box.focused is False
    assert box.border_color == box._inactive_color


# ── handle_event: typing ────────────────────────────────────────────────


def test_keydown_while_focused_appends_character():
    box = InputBox(pos=(0, 0), size=(200, 32), text="ab")
    box.focused = True
    event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_c, unicode="c")

    box.handle_event(event, (0, 0))

    assert box.text == "abc"


def test_backspace_removes_last_character():
    box = InputBox(pos=(0, 0), size=(200, 32), text="abc")
    box.focused = True
    event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_BACKSPACE, unicode="")

    box.handle_event(event, (0, 0))

    assert box.text == "ab"


def test_backspace_on_empty_text_is_a_no_op():
    box = InputBox(pos=(0, 0), size=(200, 32), text="")
    box.focused = True
    event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_BACKSPACE, unicode="")

    box.handle_event(event, (0, 0))

    assert box.text == ""


def test_keydown_while_unfocused_is_ignored():
    box = InputBox(pos=(0, 0), size=(200, 32), text="ab")
    event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_c, unicode="c")

    box.handle_event(event, (0, 0))

    assert box.text == "ab"


def test_unrelated_event_type_is_ignored():
    box = InputBox(pos=(0, 0), size=(200, 32), text="ab")
    box.focused = True
    event = pygame.event.Event(pygame.MOUSEMOTION, pos=(0, 0))

    box.handle_event(event, (0, 0))

    assert box.text == "ab"
    assert box.focused is True


# ── auto-widen ────────────────────────────────────────────────────────


def test_typing_widens_rect_to_fit_long_text():
    box = InputBox(pos=(0, 0), size=(50, 32))
    box.focused = True
    for ch in "a very long string of text indeed":
        box.handle_event(
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, unicode=ch), (0, 0)
        )

    text_width = box.font.render(box.text, True, box.text_color).get_width()
    assert box.rect.w == text_width + 10


def test_never_shrinks_below_the_constructors_min_width():
    box = InputBox(pos=(0, 0), size=(500, 32), text="hi")
    box._redraw()
    assert (
        box.rect.w == 500
    )  # short text, but width never drops below the constructor's size


def test_never_goes_below_the_constructors_floor_even_with_empty_text():
    box = InputBox(pos=(0, 0), size=(80, 32), text="")
    box._redraw()
    assert box.rect.w == 80


# ── draw ──────────────────────────────────────────────────────────────


def test_draw_paints_a_border_in_the_current_color():
    box = InputBox(pos=(10, 10), size=(100, 40))
    surface = pygame.Surface((200, 200))
    surface.fill((0, 0, 0))

    box.draw(surface)

    # a 2px border is drawn at the rect's edge; check a point on the top edge
    assert surface.get_at((50, 10))[:3] == box.border_color
    # and the interior (away from border and text) stays untouched
    assert surface.get_at((50, 30)) == (0, 0, 0, 255)
