"""Unit tests for MenuController: keyboard/mouse focus cycling over a list
of button-like objects.

Uses a minimal fake button (exposing exactly what MenuController actually
touches: .rect, .focused, ._hovered, ._renderer, .is_mouse_over(),
._active_surface) rather than a real HoverableStateObject, which would
pull in asset loading unrelated to this controller's own logic.
"""

from __future__ import annotations

import pygame

from pygamine.ui_widgets.menu_controller import MenuController


class _FakeButton:
    def __init__(self, rect):
        self.rect = rect
        self.focused = False
        self._hovered = False
        self._active_surface = f"surface-for-{rect}"
        self.set_image_calls = []
        self._renderer = self  # so ._renderer.set_image(...) is trackable here

    def set_image(self, image):
        self.set_image_calls.append(image)

    def is_mouse_over(self, pos):
        return self.rect.collidepoint(pos)


class _FakeAudio:
    def __init__(self):
        self.played = []

    def play_sfx(self, path):
        self.played.append(path)


def _buttons(n):
    return [_FakeButton(pygame.Rect(0, i * 50, 100, 40)) for i in range(n)]


# ── construction ────────────────────────────────────────────────────────


def test_first_button_is_focused_on_construction():
    buttons = _buttons(3)
    MenuController(buttons)
    assert buttons[0].focused is True
    assert buttons[1].focused is False
    assert buttons[2].focused is False


def test_empty_button_list_does_not_raise():
    controller = MenuController([])
    assert controller.focused is None


def test_focused_property_returns_the_focused_button():
    buttons = _buttons(3)
    controller = MenuController(buttons)
    assert controller.focused is buttons[0]


# ── keyboard navigation ─────────────────────────────────────────────────


def test_down_key_moves_focus_to_next_button_and_plays_switch_down_sound():
    buttons = _buttons(3)
    audio = _FakeAudio()
    controller = MenuController(
        buttons, audio=audio, switch_up_path="up.wav", switch_down_path="down.wav"
    )

    controller._handle_key(pygame.event.Event(pygame.KEYUP, key=pygame.K_DOWN))

    assert buttons[0].focused is False
    assert buttons[1].focused is True
    assert audio.played == ["down.wav"]


def test_up_key_moves_focus_to_previous_button_and_plays_switch_up_sound():
    buttons = _buttons(3)
    audio = _FakeAudio()
    controller = MenuController(
        buttons, audio=audio, switch_up_path="up.wav", switch_down_path="down.wav"
    )
    controller._handle_key(
        pygame.event.Event(pygame.KEYUP, key=pygame.K_DOWN)
    )  # focus -> 1
    audio.played.clear()

    controller._handle_key(pygame.event.Event(pygame.KEYUP, key=pygame.K_UP))

    assert buttons[0].focused is True
    assert buttons[1].focused is False
    assert audio.played == ["up.wav"]


def test_w_and_s_are_aliases_for_up_and_down():
    buttons = _buttons(2)
    controller = MenuController(buttons)

    controller._handle_key(pygame.event.Event(pygame.KEYUP, key=pygame.K_s))
    assert buttons[1].focused is True

    controller._handle_key(pygame.event.Event(pygame.KEYUP, key=pygame.K_w))
    assert buttons[0].focused is True


def test_down_key_at_last_button_does_not_wrap_or_move():
    buttons = _buttons(2)
    controller = MenuController(buttons)
    controller._handle_key(pygame.event.Event(pygame.KEYUP, key=pygame.K_DOWN))
    assert buttons[1].focused is True

    controller._handle_key(pygame.event.Event(pygame.KEYUP, key=pygame.K_DOWN))

    assert buttons[1].focused is True  # stayed put, no wraparound to index 0


def test_up_key_at_first_button_does_not_wrap_or_move():
    buttons = _buttons(2)
    controller = MenuController(buttons)

    controller._handle_key(pygame.event.Event(pygame.KEYUP, key=pygame.K_UP))

    assert buttons[0].focused is True


def test_unrelated_key_is_a_no_op():
    buttons = _buttons(2)
    controller = MenuController(buttons)

    controller._handle_key(pygame.event.Event(pygame.KEYUP, key=pygame.K_a))

    assert buttons[0].focused is True
    assert buttons[1].focused is False


def test_keyboard_switch_clears_stale_hover_on_other_buttons():
    buttons = _buttons(3)
    controller = MenuController(buttons)
    buttons[2]._hovered = True  # e.g. mouse is still resting over button 2

    controller._handle_key(pygame.event.Event(pygame.KEYUP, key=pygame.K_DOWN))

    assert buttons[2]._hovered is False
    assert buttons[2].set_image_calls == [buttons[2]._active_surface]


def test_keyboard_switch_does_not_touch_hover_on_the_newly_focused_button():
    buttons = _buttons(2)
    controller = MenuController(buttons)

    controller._handle_key(pygame.event.Event(pygame.KEYUP, key=pygame.K_DOWN))

    assert (
        buttons[1].set_image_calls == []
    )  # only stale hover on *other* buttons is cleared


# ── mouse navigation ────────────────────────────────────────────────────


def test_hovering_an_unfocused_button_switches_focus_to_it():
    buttons = _buttons(3)
    audio = _FakeAudio()
    controller = MenuController(
        buttons, audio=audio, switch_up_path="up.wav", switch_down_path="down.wav"
    )

    controller._handle_mouse_motion((10, 2 * 50 + 10))  # inside button 2's rect

    assert buttons[2].focused is True
    assert buttons[0].focused is False


def test_hovering_a_later_button_plays_switch_up_sound():
    """focused_i(0) < target_i(2) -> switch_up_path is used (per the actual
    `focused_i > target_i` condition -- moving focus *forward* through the
    list plays the 'up' sound, which reads oddly but is the real behavior)."""
    buttons = _buttons(3)
    audio = _FakeAudio()
    controller = MenuController(
        buttons, audio=audio, switch_up_path="up.wav", switch_down_path="down.wav"
    )

    controller._handle_mouse_motion((10, 2 * 50 + 10))

    assert audio.played == ["up.wav"]


def test_hovering_an_earlier_button_plays_switch_down_sound():
    buttons = _buttons(3)
    audio = _FakeAudio()
    controller = MenuController(
        buttons, audio=audio, switch_up_path="up.wav", switch_down_path="down.wav"
    )
    controller._handle_mouse_motion((10, 2 * 50 + 10))  # focus -> 2
    audio.played.clear()

    controller._handle_mouse_motion(
        (10, 0 * 50 + 10)
    )  # hover button 0, earlier than focused(2)

    assert audio.played == ["down.wav"]


def test_hovering_the_already_focused_button_does_not_re_trigger():
    buttons = _buttons(2)
    audio = _FakeAudio()
    controller = MenuController(
        buttons, audio=audio, switch_up_path="up.wav", switch_down_path="down.wav"
    )

    controller._handle_mouse_motion((10, 0 * 50 + 10))  # already focused

    assert audio.played == []


def test_mouse_not_over_any_button_is_a_no_op():
    buttons = _buttons(2)
    controller = MenuController(buttons)

    controller._handle_mouse_motion((9999, 9999))

    assert buttons[0].focused is True


# ── handle_event dispatch ───────────────────────────────────────────────


def test_handle_event_dispatches_mousemotion_and_keyup_only():
    buttons = _buttons(2)
    controller = MenuController(buttons)

    controller.handle_event(
        pygame.event.Event(pygame.MOUSEMOTION, pos=(10, 60)), (10, 60)
    )
    assert buttons[1].focused is True

    controller.handle_event(pygame.event.Event(pygame.KEYUP, key=pygame.K_UP), (10, 60))
    assert buttons[0].focused is True

    # an unrelated event type must not raise or change focus
    controller.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(10, 10)), (10, 10)
    )
    assert buttons[0].focused is True


# ── no audio / no sound path ────────────────────────────────────────────


def test_switching_focus_without_audio_does_not_raise():
    buttons = _buttons(2)
    controller = MenuController(buttons, audio=None)
    controller._handle_key(pygame.event.Event(pygame.KEYUP, key=pygame.K_DOWN))
    assert buttons[1].focused is True


def test_switching_focus_with_no_sound_path_does_not_call_audio():
    buttons = _buttons(2)
    audio = _FakeAudio()
    controller = MenuController(
        buttons, audio=audio
    )  # no switch_up_path/switch_down_path
    controller._handle_key(pygame.event.Event(pygame.KEYUP, key=pygame.K_DOWN))
    assert audio.played == []
