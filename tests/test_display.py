"""Unit tests for Display, the display stack Application delegates to.

Runs against the SDL dummy driver, with no Application around it: the canvas
size changes are observed through the callback the owner would normally wire.
"""

from __future__ import annotations

import pygame
import pytest

from pygamine.app import application
from pygamine.app.display import (
    COMMON_RESOLUTIONS,
    WINDOW_MARGIN,
    WINDOW_MODES,
    Display,
    fit_rect,
    query_screen_size,
)
from pygamine.app.mouse import Mouse


@pytest.fixture(autouse=True)
def _pygame_ready():
    pygame.init()


class _Recorder:
    def __init__(self) -> None:
        self.sizes: list[tuple[int, int]] = []

    def __call__(self, size: tuple[int, int]) -> None:
        self.sizes.append(size)


def _make(**kwargs) -> tuple[Display, _Recorder]:
    recorder = _Recorder()
    display = Display((320, 240), Mouse(), recorder, **kwargs)
    return display, recorder


def test_query_screen_size_reads_display_info(monkeypatch):
    info = type("Info", (), {"current_w": 2560, "current_h": 1440})()
    monkeypatch.setattr(pygame.display, "Info", lambda: info)
    assert query_screen_size() == (2560, 1440)


def test_init_creates_no_window_and_does_not_fire_callback():
    display, recorder = _make()
    assert recorder.sizes == []
    assert display.window.get_size() == (0, 0)
    assert display.windowed_size == (320, 240)
    assert display.fullscreen_size == (
        display.fullscreen_width,
        display.fullscreen_height,
    )


def test_first_mode_setter_builds_canvas_and_fires_callback_once():
    display, recorder = _make()
    display.set_fullscreen()
    assert recorder.sizes == [display.display_surface.get_size()]
    assert display.window.get_size() == display.display_surface.get_size()
    # Same size again: no new canvas, no callback.
    display.set_fullscreen()
    assert len(recorder.sizes) == 1
    display.set_borderless_fullscreen()
    assert display.window_mode == "borderless"
    assert display.is_fullscreen is False


def test_mode_is_recorded_before_callback_fires():
    seen: list[str] = []
    holder: list[Display] = []

    def callback(size: tuple[int, int]) -> None:
        seen.append(holder[0].window_mode)

    display = Display((320, 240), Mouse(), callback)
    holder.append(display)
    display.set_fullscreen()
    display.set_windowed()
    assert seen == ["fullscreen", "windowed"]


def test_set_window_mode_rejects_unknown_mode_and_keeps_state():
    display, _ = _make()
    display.set_fullscreen()
    with pytest.raises(ValueError):
        display.set_window_mode("maximized")  # type: ignore[arg-type]
    assert display.window_mode == "fullscreen"


def test_cycle_window_mode_wraps_in_window_modes_order():
    display, _ = _make()
    display.set_fullscreen()
    order = [display.window_mode]
    for _ in range(len(WINDOW_MODES)):
        display.cycle_window_mode()
        order.append(display.window_mode)
    assert order == ["fullscreen", "borderless", "windowed", "fullscreen"]
    display.cycle_window_mode(-1)
    assert display.window_mode == "windowed"


def test_custom_window_modes_and_setters_are_used():
    calls: list[str] = []
    display, _ = _make(
        window_modes=("borderless", "windowed"),
        mode_setters={
            "borderless": lambda: calls.append("borderless"),
            "windowed": lambda: calls.append("windowed"),
        },
    )
    display.set_window_mode("windowed")
    assert calls == ["windowed"]
    with pytest.raises(ValueError):
        display.set_window_mode("fullscreen")
    assert calls == ["windowed"]


def test_windowed_physical_size_respects_margin_and_never_upscales():
    display, _ = _make()
    display.fullscreen_width, display.fullscreen_height = 1000, 1000
    display.windowed_width, display.windowed_height = 1000, 500
    assert display.windowed_physical_size() == (
        round(1000 * WINDOW_MARGIN),
        round(500 * WINDOW_MARGIN),
    )
    display.fullscreen_width, display.fullscreen_height = 5000, 5000
    assert display.windowed_physical_size() == (1000, 500)


def test_resolution_override_wins_and_clears():
    display, _ = _make()
    auto = display.resolution
    display.set_fullscreen()
    display.set_resolution((1280, 720))
    assert display.resolution == (1280, 720)
    assert display.window_mode == "fullscreen"  # a pick never switches mode
    assert display.auto_windowed_physical_size() == auto
    assert display.resolution == (1280, 720)  # override survives the auto query
    display.clear_resolution_override()
    assert display.resolution == auto


def test_available_resolutions_filters_and_keeps_current_pick():
    display, _ = _make()
    display.fullscreen_width, display.fullscreen_height = 1920, 1080
    options = display.available_resolutions()
    assert (1280, 720) in options
    assert (3840, 2160) not in options
    assert set(options) <= set(COMMON_RESOLUTIONS) | {display.resolution}
    display.set_resolution((999, 555))
    assert (999, 555) in display.available_resolutions()


def test_window_settings_round_trip_and_unknown_mode_falls_back():
    display, _ = _make()
    display.set_fullscreen()
    display.restore_window_settings(
        {"window_mode": "windowed", "window_size": [800, 600]}
    )
    assert display.window_settings() == {
        "window_mode": "windowed",
        "window_size": [800, 600],
    }
    display.restore_window_settings({"window_mode": "bogus"})
    assert display.window_mode == "fullscreen"
    display.reset_window_settings()
    assert display.window_mode == "fullscreen"
    assert display.window_settings()["window_size"] == list(
        display.auto_windowed_physical_size()
    )


def test_render_scale_resizes_canvas_and_updates_mouse_scale():
    display, recorder = _make()
    display.set_fullscreen()
    full = display.display_surface.get_size()
    recorder.sizes.clear()
    display.set_render_scale(0.5)
    half = (round(full[0] * 0.5), round(full[1] * 0.5))
    assert recorder.sizes == [half]
    assert display.mouse.scale == (half[0] / full[0], half[1] / full[1])
    display.set_render_scale(0.5)  # same value: no rebuild, no callback
    assert recorder.sizes == [half]


def test_fixed_aspect_locks_canvas_and_offsets_mouse():
    display, recorder = _make(fixed_aspect=True)
    display.set_fullscreen()
    assert display.window.get_size() == (320, 240)
    assert recorder.sizes == [(320, 240)]
    rect = fit_rect((320, 240), display.display_surface.get_size())
    assert display.mouse.offset == (rect.x, rect.y)
    assert display.mouse.scale == (320 / rect.width, 240 / rect.height)


def test_present_letterboxes_fixed_aspect_with_black_bars():
    display, _ = _make(fixed_aspect=True)
    display.set_fullscreen()
    display.window.fill((255, 0, 0))
    display.display_surface.fill((0, 255, 0))
    display.present()
    rect = fit_rect((320, 240), display.display_surface.get_size())
    assert display.display_surface.get_at(rect.center)[:3] == (255, 0, 0)
    if rect.size != display.display_surface.get_size():
        assert display.display_surface.get_at((0, 0))[:3] == (0, 0, 0)


def test_present_scaled_fills_display_when_render_scale_below_one():
    display, _ = _make(render_scale=0.5)
    display.set_fullscreen()
    display.window.fill((0, 0, 255))
    display.present()
    w, h = display.display_surface.get_size()
    assert display.display_surface.get_at((w - 1, h - 1))[:3] == (0, 0, 255)


def test_application_reexports_display_names():
    assert application.fit_rect is fit_rect
    assert application.WINDOW_MARGIN == WINDOW_MARGIN
    assert application.COMMON_RESOLUTIONS is COMMON_RESOLUTIONS
    assert application.Application.WINDOW_MODES is WINDOW_MODES
