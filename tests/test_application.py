"""Unit tests for Application: the base game-loop class every project's
Game class extends.

Constructs real Application instances against the dummy SDL driver rather
than mocking pygame.display/mixer wholesale -- this is deliberately an
integration-style test of the loop wiring itself. sys.exit and pygame.quit
are monkeypatched wherever exit() is exercised, since calling them for real
would tear down the shared pygame session for every later test in the suite.
"""

from __future__ import annotations

import os
import sys

import pygame
import pytest

from pygamine.app.application import Application
from pygamine.app.mouse import Mouse


class _TrackedApp(Application):
    def __init__(self, **kwargs):
        self.handled_events = []
        self.update_calls = 0
        self.draw_calls = 0
        self.draw_debug_calls = 0
        super().__init__(size=(320, 240), title="Test App", fps=0, **kwargs)

    def handle_event(self, event):
        self.handled_events.append(event)

    def update(self):
        self.update_calls += 1

    def draw(self):
        self.draw_calls += 1

    def draw_debug(self):
        self.draw_debug_calls += 1


@pytest.fixture
def no_real_exit(monkeypatch):
    """Prevent exit()'s real side effects (pygame.quit tears down the shared
    session; sys.exit raises SystemExit) while still letting us observe that
    they were requested."""
    calls = {"pygame_quit": 0, "sys_exit": 0}
    monkeypatch.setattr(
        pygame,
        "quit",
        lambda: calls.__setitem__("pygame_quit", calls["pygame_quit"] + 1),
    )
    monkeypatch.setattr(
        sys, "exit", lambda: calls.__setitem__("sys_exit", calls["sys_exit"] + 1)
    )
    return calls


# ── construction ───────────────────────────────────────────────────────────


def test_init_stores_basic_attributes():
    app = _TrackedApp()
    assert app._fps == 0
    assert app.mouse_pos == (0, 0)
    assert isinstance(app.mouse, Mouse)
    assert app._is_fullscreen is True  # __init__ ends by calling full_screen()


def test_init_sizes_the_canvas_to_match_the_real_display_1to1():
    """No fixed design resolution any more -- self.window is rebuilt to
    exactly match display_surface (full_screen_size, since __init__ ends in
    full_screen()), not the constructor's `size` hint."""
    app = _TrackedApp()
    assert app.size == app.full_screen_size
    assert app.window.get_size() == app.full_screen_size
    assert app.window.get_size() == app.display_surface.get_size()


def test_init_uses_injected_mouse_instead_of_default():
    custom_mouse = Mouse()
    app = _TrackedApp(mouse=custom_mouse)
    assert app.mouse is custom_mouse


def test_init_sets_window_title():
    _TrackedApp()
    assert Application.get_title() == "Test App"


def test_fetch_screen_dimensions_stores_full_and_minimized_size():
    app = _TrackedApp()
    assert app.minimized_size == (320, 240)  # the constructor's `size` hint
    assert app.full_screen_size == (app.full_screen_width, app.full_screen_height)


def test_center_window_sets_sdl_env_var():
    _TrackedApp()
    assert os.environ["SDL_VIDEO_CENTERED"] == "1"


# ── set_size / minimize / full_screen ──────────────────────────────────


def test_set_size_updates_size_width_height():
    app = _TrackedApp()
    app.set_size((100, 200))
    assert app.size == (100, 200)
    assert app.width == 100
    assert app.height == 200


def test_full_screen_and_minimize_size_the_canvas_to_their_own_actual_size():
    """minimize() and full_screen() each rebuild self.window to match
    whatever physical size *that* mode actually uses -- `.size` tracks the
    real current canvas, not a fixed authored resolution. They differ in
    `.display_surface`'s size/flags and in `._is_fullscreen`, and now also
    in `.size`/`.window` itself."""
    app = _TrackedApp()

    app.minimize()
    assert app.size == app._windowed_physical_size()
    assert app.window.get_size() == app.display_surface.get_size()
    assert app._is_fullscreen is False

    app.full_screen()
    assert app.size == app.full_screen_size
    assert app.window.get_size() == app.display_surface.get_size()
    assert app._is_fullscreen is True


def test_full_screen_display_surface_matches_real_screen_size():
    app = _TrackedApp()
    assert app.display_surface.get_size() == app.full_screen_size


def _pin_dimensions(
    app, *, minimized: tuple[int, int], full_screen: tuple[int, int]
) -> None:
    """Dummy-driver pygame.display.Info() reflects whatever mode the *last*
    set_mode() call in this pytest session requested, not a fixed native
    desktop size -- so tests can't rely on its value being consistent
    across runs/ordering. Pin both sizes directly instead."""
    app.minimized_size = app.minimized_width, app.minimized_height = minimized
    app.full_screen_size = app.full_screen_width, app.full_screen_height = full_screen


def test_windowed_physical_size_shrinks_to_fit_with_margin_when_preferred_size_exceeds_screen():
    """Requesting a preferred windowed size bigger than the screen must
    shrink -- with room to spare for window chrome -- rather than requesting
    a window larger than the screen (the original bug: an oversized bordered
    window has its title bar pushed off-screen and looks indistinguishable
    from fullscreen)."""
    app = _TrackedApp()
    _pin_dimensions(app, minimized=(2000, 1500), full_screen=(1024, 768))

    windowed_size = app._windowed_physical_size()

    assert windowed_size[0] < app.full_screen_width
    assert windowed_size[1] < app.full_screen_height
    assert windowed_size == (
        819,
        614,
    )  # round(2000 * 0.8*1024/2000), round(1500 * 0.8*768/1500)


def test_windowed_physical_size_never_exceeds_the_preferred_size():
    """When the preferred windowed size already comfortably fits the screen,
    windowed mode should use it as-is rather than upscaling it."""
    app = _TrackedApp()
    _pin_dimensions(app, minimized=(320, 240), full_screen=(1024, 768))

    assert app._windowed_physical_size() == (320, 240)


def test_minimize_sets_display_surface_to_windowed_physical_size():
    app = _TrackedApp()
    _pin_dimensions(app, minimized=(2000, 1500), full_screen=(1024, 768))

    app.minimize()

    assert app.display_surface.get_size() == app._windowed_physical_size()
    assert app.display_surface.get_size() != (2000, 1500)


def test_minimize_and_full_screen_keep_mouse_scale_at_identity():
    """self.window is always rebuilt to exactly match display_surface, so
    the physical->logical mouse scale factor is always 1:1 now -- there's
    no separate "design resolution" for real mouse coordinates to be
    rescaled against."""
    app = _TrackedApp()
    _pin_dimensions(app, minimized=(2000, 1500), full_screen=(1024, 768))

    app.minimize()
    assert app.mouse.scale == (1.0, 1.0)

    app.full_screen()
    assert app.mouse.scale == (1.0, 1.0)


def test_sync_mouse_scale_is_a_noop_without_a_mouse():
    app = _TrackedApp(mouse=None)
    app.minimize()  # must not raise with no mouse object
    app.full_screen()


# ── fixed_aspect: letterboxing/pillarboxing instead of matching the display ──
#
# fixed_aspect=True locks self.window to the design resolution (`size`,
# cached as minimized_size) regardless of the real display's own shape --
# the opposite default from fixed_aspect=False (self.window always matches
# the display's aspect, see above). _fit_rect/_present/_sync_mouse_scale
# then center the locked-aspect window inside the display with black bars,
# rather than either distorting it (naive stretch) or letting extra world
# space show through on a mismatched monitor.
#
# _TrackedApp always constructs with size=(320, 240) -- a 4:3 design
# resolution -- so self.window is already locked there once fixed_aspect
# is on. Rather than going through minimize()/full_screen() (the dummy SDL
# driver ignores an arbitrary FULLSCREEN size, and minimize()'s own
# windowed-mode margin/fit math would entangle the numbers), these assign
# display_surface directly to a Surface of the desired physical size and
# re-run just _sync_mouse_scale() -- the same thing either real entry point
# calls after a mode/resolution change -- to exercise the letterbox math in
# isolation against a known display size.


def _set_display_surface(app, size: tuple[int, int]) -> None:
    app.display_surface = pygame.Surface(size)


def test_fit_rect_pillarboxes_when_display_is_wider_than_design_aspect():
    """1600x900 (16:9) is relatively wider than the fixed 320x240 (4:3)
    design resolution, so it's height-constrained -- equal bars land on
    the left/right instead of stretching width and height differently."""
    app = _TrackedApp(fixed_aspect=True)
    _set_display_surface(app, (1600, 900))

    rect = app._fit_rect(app.display_surface.get_size())

    assert rect == pygame.Rect(200, 0, 1200, 900)


def test_fit_rect_letterboxes_when_display_is_taller_than_design_aspect():
    """800x900 is relatively taller/narrower than 4:3, so it's width-
    constrained -- bars land on top/bottom instead."""
    app = _TrackedApp(fixed_aspect=True)
    _set_display_surface(app, (800, 900))

    rect = app._fit_rect(app.display_surface.get_size())

    assert rect == pygame.Rect(0, 150, 800, 600)


def test_fit_rect_fills_the_display_when_aspect_ratios_already_match():
    app = _TrackedApp(fixed_aspect=True)
    _set_display_surface(app, (1280, 960))  # same 4:3 as the 320x240 design

    rect = app._fit_rect(app.display_surface.get_size())

    assert rect == pygame.Rect(0, 0, 1280, 960)


def test_sync_mouse_scale_accounts_for_the_pillarbox_offset():
    app = _TrackedApp(fixed_aspect=True)
    _set_display_surface(app, (1600, 900))

    app._sync_mouse_scale()

    assert app.mouse.offset == (200, 0)
    assert app.mouse.scale == (320 / 1200, 240 / 900)


def test_present_pillarboxes_instead_of_stretching_under_fixed_aspect():
    app = _TrackedApp(fixed_aspect=True)
    _set_display_surface(app, (1600, 900))
    app.window.fill((10, 20, 30))

    app._present()

    # bars outside the fitted rect (x < 200 or x >= 1400) stay black
    assert app.display_surface.get_at((0, 0))[:3] == (0, 0, 0)
    assert app.display_surface.get_at((1599, 0))[:3] == (0, 0, 0)
    # inside the fitted rect shows the scaled window content, not distorted
    assert app.display_surface.get_at((800, 450))[:3] == (10, 20, 30)


def test_present_is_a_plain_scale_with_no_bars_when_aspect_already_matches():
    app = _TrackedApp(fixed_aspect=True)
    _set_display_surface(app, (1280, 960))
    app.window.fill((10, 20, 30))

    app._present()

    assert app.display_surface.get_at((0, 0))[:3] == (10, 20, 30)


def test_fixed_aspect_defaults_to_false():
    app = _TrackedApp()
    assert app.fixed_aspect is False


def test_without_fixed_aspect_window_still_always_matches_the_display():
    """Regression guard: fixed_aspect=False (the default) must keep the
    existing behavior from the section above -- self.window always matches
    display_surface, never letterboxed."""
    app = _TrackedApp()
    _pin_dimensions(app, minimized=(320, 240), full_screen=(1600, 900))

    app.full_screen()

    assert app.window.get_size() == app.display_surface.get_size()
    assert app.mouse.offset == (0.0, 0.0)


# ── resolution picker (available_resolutions / set_resolution / cycle) ──


def test_resolution_reflects_auto_fit_before_any_explicit_pick():
    app = _TrackedApp()
    _pin_dimensions(app, minimized=(2000, 1500), full_screen=(1024, 768))

    assert app.resolution == app._windowed_physical_size() == (819, 614)


def test_resolution_reflects_an_explicit_pick_even_while_fullscreen():
    app = _TrackedApp()
    _pin_dimensions(app, minimized=(1920, 1080), full_screen=(1920, 1080))

    app.set_resolution((1280, 720))
    app.full_screen()

    assert app.resolution == (1280, 720)


def test_available_resolutions_filters_to_what_fits_with_margin():
    app = _TrackedApp()
    _pin_dimensions(app, minimized=(1920, 1080), full_screen=(1920, 1080))

    assert app.available_resolutions() == [
        (1024, 576),
        (1152, 648),
        (1280, 720),
        (1280, 800),
        (1366, 768),
        (1536, 864),
    ]


def test_available_resolutions_always_includes_the_current_selection():
    """A resolution outside COMMON_RESOLUTIONS (e.g. picked previously, or
    an odd design resolution) must never silently disappear from the list
    the player is choosing from."""
    app = _TrackedApp()
    _pin_dimensions(app, minimized=(1920, 1080), full_screen=(1920, 1080))
    app.set_resolution((999, 555))

    assert (999, 555) in app.available_resolutions()


def test_set_resolution_does_not_switch_mode_from_fullscreen():
    """Window mode and resolution are independent settings -- picking a
    resolution while fullscreen (or borderless) must not force a switch to
    windowed. The pick is still remembered (see the "overrides" test below)
    for whenever windowed mode is next entered."""
    app = _TrackedApp()
    _pin_dimensions(app, minimized=(1920, 1080), full_screen=(1920, 1080))
    assert app._is_fullscreen is True
    display_size_before = app.display_surface.get_size()

    app.set_resolution((1024, 576))

    assert app._is_fullscreen is True
    assert (
        app.display_surface.get_size() == display_size_before
    )  # untouched -- still fullscreen


def test_set_resolution_resizes_immediately_when_already_windowed():
    app = _TrackedApp()
    _pin_dimensions(app, minimized=(1920, 1080), full_screen=(1920, 1080))
    app.minimize()

    app.set_resolution((1024, 576))

    assert app._window_mode == "windowed"
    assert app.display_surface.get_size() == (1024, 576)


def test_set_resolution_overrides_the_automatic_fit_calculation():
    app = _TrackedApp()
    _pin_dimensions(app, minimized=(1920, 1080), full_screen=(1920, 1080))

    app.set_resolution((1280, 720))
    app.full_screen()
    app.minimize()  # a later plain minimize() must keep using the explicit choice

    assert app.display_surface.get_size() == (1280, 720)


def test_clear_resolution_override_reverts_to_auto_fit():
    app = _TrackedApp()
    _pin_dimensions(app, minimized=(1920, 1080), full_screen=(1920, 1080))
    app.set_resolution((1280, 720))

    app.clear_resolution_override()

    assert app.resolution == app._auto_windowed_physical_size()


def test_clear_resolution_override_does_not_resize_the_current_window():
    app = _TrackedApp()
    _pin_dimensions(app, minimized=(1920, 1080), full_screen=(1920, 1080))
    app.minimize()
    app.set_resolution((1280, 720))

    app.clear_resolution_override()

    assert app.display_surface.get_size() == (
        1280,
        720,
    )  # unchanged until the next minimize()/F11


def test_cycle_resolution_advances_through_the_sorted_list():
    app = _TrackedApp()
    _pin_dimensions(app, minimized=(1920, 1080), full_screen=(1920, 1080))
    app.minimize()
    options = app.available_resolutions()

    first = app.cycle_resolution(1)

    assert first == options[0]
    assert app.display_surface.get_size() == first
    assert app._is_fullscreen is False

    second = app.cycle_resolution(1)
    assert second == options[1]


def test_cycle_resolution_does_not_switch_mode_from_fullscreen():
    """Same independence as set_resolution() -- cycling while
    fullscreen updates the remembered pick without resizing or switching
    mode."""
    app = _TrackedApp()
    _pin_dimensions(app, minimized=(1920, 1080), full_screen=(1920, 1080))
    options = app.available_resolutions()
    display_size_before = app.display_surface.get_size()

    first = app.cycle_resolution(1)

    assert first == options[0]
    assert app.resolution == options[0]
    assert app._is_fullscreen is True
    assert app.display_surface.get_size() == display_size_before


def test_cycle_resolution_wraps_around_in_both_directions():
    app = _TrackedApp()
    _pin_dimensions(app, minimized=(1920, 1080), full_screen=(1920, 1080))
    options = app.available_resolutions()
    starting = app._auto_windowed_physical_size()

    last = starting
    for _ in range(len(options)):
        last = app.cycle_resolution(1)
    assert last == starting  # a full lap forward returns to the starting resolution

    back = app.cycle_resolution(-1)
    assert back == options[(options.index(starting) - 1) % len(options)]


# ── window settings persistence (restore/window_settings/reset) ────────
#
# Extracted after chokepoint and standoff both grew the exact same three
# methods independently around a SaveStore-backed settings dict.


def test_window_settings_reports_the_current_mode_and_resolution():
    app = _TrackedApp()
    app.minimize()

    settings = app.window_settings()

    assert settings == {"window_mode": "windowed", "window_size": list(app.resolution)}


def test_restore_window_settings_applies_a_saved_windowed_mode_and_size():
    app = _TrackedApp()
    _pin_dimensions(app, minimized=(320, 240), full_screen=(1920, 1080))

    app.restore_window_settings({"window_mode": "windowed", "window_size": [640, 480]})

    assert app._window_mode == "windowed"
    assert app.resolution == (640, 480)
    assert app.display_surface.get_size() == (640, 480)


def test_restore_window_settings_applies_a_saved_borderless_mode():
    app = _TrackedApp()

    app.restore_window_settings({"window_mode": "borderless"})

    assert app._window_mode == "borderless"


def test_restore_window_settings_defaults_to_fullscreen_when_nothing_saved():
    app = _TrackedApp()

    app.restore_window_settings({})

    assert app._window_mode == "fullscreen"


def test_restore_window_settings_defaults_to_fullscreen_for_an_unknown_mode():
    app = _TrackedApp()

    app.restore_window_settings({"window_mode": "some_future_mode"})

    assert app._window_mode == "fullscreen"


def test_window_settings_round_trips_through_restore_window_settings():
    app = _TrackedApp()
    _pin_dimensions(app, minimized=(320, 240), full_screen=(1920, 1080))
    app.set_resolution((800, 600))
    app.minimize()
    saved = app.window_settings()

    app2 = _TrackedApp()
    _pin_dimensions(app2, minimized=(320, 240), full_screen=(1920, 1080))
    app2.restore_window_settings(saved)

    assert app2._window_mode == app._window_mode
    assert app2.resolution == app.resolution


def test_reset_window_settings_returns_to_fullscreen_with_no_override():
    app = _TrackedApp()
    app.set_resolution((640, 480))
    app.minimize()
    assert app._window_mode == "windowed"

    app.reset_window_settings()

    assert app._window_mode == "fullscreen"
    assert app._resolution_override is None


# ── _handle_core_event: debug toggle, F11, escape/quit -> exit ──────────


def test_f1_toggles_debug_mode():
    app = _TrackedApp()
    assert app._is_in_debug_mode is False

    app._handle_core_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F1))
    assert app._is_in_debug_mode is True

    app._handle_core_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F1))
    assert app._is_in_debug_mode is False


def test_f11_calls_borderless_full_screen_when_currently_fullscreen():
    """__init__ ends by calling full_screen(), so _window_mode is already
    "fullscreen" at construction -- the first F11 press must advance to
    borderless, not straight back to windowed or re-enter full_screen()
    (the original bug: checking `self.size == self.minimized_size`
    couldn't tell fullscreen from windowed, since both methods set the
    same `.size`)."""
    app = _TrackedApp()
    assert app._window_mode == "fullscreen"

    calls = []
    app.full_screen = lambda: calls.append("full_screen")
    app.borderless_full_screen = lambda: calls.append("borderless_full_screen")
    app.minimize = lambda: calls.append("minimize")

    app._handle_core_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F11))

    assert calls == ["borderless_full_screen"]


def test_f11_calls_minimize_when_currently_borderless():
    app = _TrackedApp()
    app.borderless_full_screen()
    assert app._window_mode == "borderless"

    calls = []
    app.full_screen = lambda: calls.append("full_screen")
    app.borderless_full_screen = lambda: calls.append("borderless_full_screen")
    app.minimize = lambda: calls.append("minimize")

    app._handle_core_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F11))

    assert calls == ["minimize"]


def test_f11_calls_full_screen_when_currently_windowed():
    app = _TrackedApp()
    app.minimize()
    assert app._window_mode == "windowed"

    calls = []
    app.full_screen = lambda: calls.append("full_screen")
    app.borderless_full_screen = lambda: calls.append("borderless_full_screen")
    app.minimize = lambda: calls.append("minimize")

    app._handle_core_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F11))

    assert calls == ["full_screen"]


def test_f11_cycles_through_all_three_modes_and_wraps_around():
    app = _TrackedApp()
    assert app._window_mode == "fullscreen"

    app._handle_core_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F11))
    assert app._window_mode == "borderless"

    app._handle_core_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F11))
    assert app._window_mode == "windowed"

    app._handle_core_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F11))
    assert app._window_mode == "fullscreen"


def test_borderless_full_screen_sets_display_surface_to_full_screen_size():
    app = _TrackedApp()
    _pin_dimensions(app, minimized=(2000, 1500), full_screen=(1024, 768))

    app.borderless_full_screen()

    assert app.display_surface.get_size() == app.full_screen_size
    assert app._window_mode == "borderless"
    assert app._is_fullscreen is False  # only exclusive FULLSCREEN counts as fullscreen


def test_borderless_full_screen_keeps_mouse_scale_at_identity():
    app = _TrackedApp()
    _pin_dimensions(app, minimized=(2000, 1500), full_screen=(1024, 768))

    app.borderless_full_screen()

    assert app.mouse.scale == (1.0, 1.0)


def test_escape_key_requests_exit(no_real_exit):
    app = _TrackedApp()
    app._handle_core_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))

    assert app._is_running is False
    assert no_real_exit["pygame_quit"] == 1
    assert no_real_exit["sys_exit"] == 1


def test_quit_event_requests_exit(no_real_exit):
    app = _TrackedApp()
    app._handle_core_event(pygame.event.Event(pygame.QUIT))

    assert app._is_running is False


def test_unrelated_key_event_does_not_toggle_debug_or_exit(no_real_exit):
    app = _TrackedApp()
    app._is_running = True

    app._handle_core_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a))

    assert app._is_in_debug_mode is False
    assert app._is_running is True
    assert no_real_exit["sys_exit"] == 0


# ── event dispatch (_handle_events / handle_event) ─────────────────────


def test_handle_events_calls_handle_event_once_per_queued_event(monkeypatch):
    app = _TrackedApp()
    events = [
        pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a),
        pygame.event.Event(pygame.KEYDOWN, key=pygame.K_b),
    ]
    monkeypatch.setattr(pygame.event, "get", lambda: events)

    app._handle_events()

    assert app.handled_events == events


def test_base_handle_event_update_draw_are_harmless_no_ops():
    app = Application(size=(320, 240), title="Base", fps=0)
    app.handle_event(pygame.event.Event(pygame.USEREVENT))
    app.update()
    app.draw()  # none of these should raise


# ── draw_mouse ────────────────────────────────────────────────────────


def test_draw_mouse_calls_mouse_draw_with_window():
    calls = []
    app = _TrackedApp()
    app.mouse.draw = lambda window: calls.append(window)

    app.draw_mouse()

    assert calls == [app.window]


def test_draw_mouse_skips_when_mouse_is_falsy():
    app = _TrackedApp(mouse=None)
    app.draw_mouse()  # must not raise with no mouse object


# ── _present ──────────────────────────────────────────────────────────


def test_present_blits_directly_regardless_of_the_windowed_size_chosen():
    """self.window is always rebuilt to match display_surface exactly, so
    _present() never needs to scale -- even a windowed size much smaller
    than the preferred size (previously the "different sizes" case) still
    blits 1:1."""
    app = _TrackedApp()
    _pin_dimensions(app, minimized=(2000, 1500), full_screen=(1024, 768))
    app.minimize()
    assert app.window.get_size() == app.display_surface.get_size()
    app.window.fill((10, 20, 30))

    app._present()

    assert app.display_surface.get_at((0, 0))[:3] == (10, 20, 30)


# ── render_scale ─────────────────────────────────────────────────────────


def test_render_scale_defaults_to_1_and_window_matches_display():
    app = _TrackedApp()
    assert app.render_scale == 1.0
    assert app.window.get_size() == app.display_surface.get_size()


def test_render_scale_below_1_shrinks_the_logical_window_relative_to_display():
    app = _TrackedApp(render_scale=0.5)
    _pin_dimensions(app, minimized=(2000, 1500), full_screen=(1024, 768))
    app.full_screen()

    assert app.window.get_size() == (512, 384)  # round(1024*0.5), round(768*0.5)
    assert app.display_surface.get_size() == (1024, 768)  # display itself is untouched


def test_render_scale_applies_across_every_window_mode():
    app = _TrackedApp(render_scale=0.5)
    _pin_dimensions(app, minimized=(2000, 1500), full_screen=(1024, 768))

    app.minimize()
    physical = app.display_surface.get_size()
    assert app.window.get_size() == (round(physical[0] * 0.5), round(physical[1] * 0.5))

    app.borderless_full_screen()
    assert app.window.get_size() == (512, 384)


def test_present_upscales_when_render_scale_is_below_1():
    app = _TrackedApp(render_scale=0.5)
    _pin_dimensions(app, minimized=(2000, 1500), full_screen=(1024, 768))
    app.full_screen()
    assert app.window.get_size() != app.display_surface.get_size()
    app.window.fill((10, 20, 30))

    app._present()  # must not raise scaling a smaller surface onto a larger one

    assert app.display_surface.get_at((0, 0))[:3] == (10, 20, 30)


def test_set_render_scale_rebuilds_the_window_and_fires_on_canvas_resized():
    app = _TrackedApp()
    _pin_dimensions(app, minimized=(2000, 1500), full_screen=(1024, 768))
    app.full_screen()
    calls = []
    app.on_canvas_resized = lambda size: calls.append(size)

    app.set_render_scale(0.5)

    assert app.window.get_size() == (512, 384)
    assert calls == [(512, 384)]


def test_set_render_scale_to_the_same_value_is_a_noop():
    app = _TrackedApp(render_scale=0.5)
    _pin_dimensions(app, minimized=(2000, 1500), full_screen=(1024, 768))
    app.full_screen()
    window_before = app.window
    calls = []
    app.on_canvas_resized = lambda size: calls.append(size)

    app.set_render_scale(0.5)

    assert calls == []
    assert app.window is window_before


def test_set_render_scale_updates_mouse_scale():
    app = _TrackedApp()
    _pin_dimensions(app, minimized=(2000, 1500), full_screen=(1024, 768))
    app.full_screen()
    assert app.mouse.scale == (1.0, 1.0)

    app.set_render_scale(0.5)

    assert app.mouse.scale == (0.5, 0.5)


# ── _rebuild_window_surface / on_canvas_resized ─────────────────────────


def test_window_matches_display_surface_after_every_mode_switch():
    app = _TrackedApp()
    _pin_dimensions(app, minimized=(2000, 1500), full_screen=(1024, 768))

    for switch in (
        app.minimize,
        app.full_screen,
        app.borderless_full_screen,
        app.minimize,
    ):
        switch()
        assert app.window.get_size() == app.display_surface.get_size()


def test_on_canvas_resized_fires_with_the_new_size_when_it_actually_changes():
    app = _TrackedApp()
    _pin_dimensions(app, minimized=(2000, 1500), full_screen=(1024, 768))
    calls = []
    app.on_canvas_resized = lambda size: calls.append(size)

    app.minimize()  # 1024x768 -> windowed size, a real change

    assert calls == [app._windowed_physical_size()]


def test_on_canvas_resized_does_not_fire_when_the_size_is_unchanged():
    """full_screen() and borderless_full_screen() both target
    full_screen_size -- toggling between them shouldn't fire a resize hook
    or recreate the surface (avoids a spurious camera/UI re-layout and a
    one-frame black flash)."""
    app = _TrackedApp()
    _pin_dimensions(app, minimized=(2000, 1500), full_screen=(1024, 768))
    app.full_screen()
    window_before = app.window
    calls = []
    app.on_canvas_resized = lambda size: calls.append(size)

    app.borderless_full_screen()

    assert calls == []
    assert app.window is window_before


# ── run() loop ──────────────────────────────────────────────────────────


def test_run_calls_update_and_draw_each_frame_until_stopped(monkeypatch):
    monkeypatch.setattr(pygame.event, "get", lambda: [])

    app = _TrackedApp()

    def _stop_after_first_frame():
        app.update_calls += 1
        if app.update_calls >= 3:
            app._is_running = False

    app.update = _stop_after_first_frame
    app.run()

    assert app.update_calls == 3
    assert app.draw_calls == 3


def test_run_calls_draw_debug_only_in_debug_mode(monkeypatch):
    monkeypatch.setattr(pygame.event, "get", lambda: [])
    app = _TrackedApp()
    app._is_in_debug_mode = True

    call_count = {"n": 0}

    def _stop_after_one():
        call_count["n"] += 1
        if call_count["n"] >= 1:
            app._is_running = False

    app.update = _stop_after_one
    app.run()

    assert app.draw_debug_calls == 1


def test_run_does_not_call_draw_debug_when_disabled(monkeypatch):
    monkeypatch.setattr(pygame.event, "get", lambda: [])
    app = _TrackedApp()
    assert app._is_in_debug_mode is False

    def _stop():
        app._is_running = False

    app.update = _stop
    app.run()

    assert app.draw_debug_calls == 0


def test_run_stops_via_a_queued_quit_event(monkeypatch, no_real_exit):
    """The realistic path: run() processes a real QUIT event through
    _handle_events -> _handle_core_event -> on_exit_request -> exit(),
    which flips _is_running so the loop doesn't continue to a next frame."""
    app = _TrackedApp()
    monkeypatch.setattr(pygame.event, "get", lambda: [pygame.event.Event(pygame.QUIT)])

    app.run()

    assert app._is_running is False
    assert app.update_calls == 1  # completed the frame it was asked to exit on
    assert no_real_exit["sys_exit"] == 1


# ── splash (show_splash / run() integration) ──────────────────────────────
#
# Every project that sets self.splash used to override run() itself to call
# splash.run(...) before super().run() -- five copies of the identical
# comment explaining why (bypassing _present()'s scale step). Moved into
# Application itself: run() always calls show_splash() first, which is a
# no-op while self.splash stays None (the default set in __init__).


class _FakeSplash:
    def __init__(self):
        self.calls = []

    def run(self, surface, clock, fps):
        self.calls.append((surface, clock, fps))


def test_splash_defaults_to_none():
    app = _TrackedApp()
    assert app.splash is None


def test_show_splash_is_a_noop_when_none_is_set():
    app = _TrackedApp()
    app.show_splash()  # must not raise


def test_show_splash_delegates_to_the_splash_screen_with_the_real_display_surface():
    app = _TrackedApp()
    fake = _FakeSplash()
    app.splash = fake

    app.show_splash()

    assert fake.calls == [(app.display_surface, app.clock, app._fps)]


def test_run_shows_the_splash_exactly_once_before_the_main_loop(monkeypatch):
    monkeypatch.setattr(pygame.event, "get", lambda: [])
    app = _TrackedApp()
    fake = _FakeSplash()
    app.splash = fake

    def _stop():
        app.update_calls += 1
        app._is_running = False

    app.update = _stop
    app.run()

    assert len(fake.calls) == 1
    assert app.update_calls == 1  # loop still ran normally afterward


def test_run_skips_splash_entirely_when_none_is_set(monkeypatch):
    monkeypatch.setattr(pygame.event, "get", lambda: [])
    app = _TrackedApp()
    assert app.splash is None

    def _stop():
        app.update_calls += 1
        app._is_running = False

    app.update = _stop
    app.run()  # must not raise despite no splash ever being set

    assert app.update_calls == 1


# ── exit() ──────────────────────────────────────────────────────────────


def test_exit_stops_the_loop_flag_and_calls_quit_and_sys_exit(no_real_exit):
    app = _TrackedApp()
    app._is_running = True

    app.exit()

    assert app._is_running is False
    assert no_real_exit["pygame_quit"] == 1
    assert no_real_exit["sys_exit"] == 1


def test_on_exit_request_delegates_to_exit(no_real_exit):
    app = _TrackedApp()
    calls = []
    app.exit = lambda: calls.append(1)

    app.on_exit_request()

    assert calls == [1]
