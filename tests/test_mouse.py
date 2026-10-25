"""Unit tests for Mouse: position/tile-position tracking and an optional
GameObject cursor that follows it.
"""

from __future__ import annotations

import pygame

from pygamine.app.mouse import Mouse


class _FakeCursor:
    def __init__(self):
        self.rect = self  # so .rect.set_position(...) lands here
        self.positions = []
        self.draw_calls = []

    def set_position(self, pos):
        self.positions.append(pos)

    def draw(self, window):
        self.draw_calls.append(window)


# ── construction ────────────────────────────────────────────────────────


def test_construction_defaults():
    mouse = Mouse()
    assert mouse.position == (0, 0)
    assert mouse.tile_size is None
    assert mouse.cursor is None


def test_construction_without_tile_size_has_no_tile_pos_attribute():
    mouse = Mouse()
    assert not hasattr(mouse, "tile_pos")


def test_construction_with_tile_size_initializes_tile_pos():
    mouse = Mouse(tile_size=32)
    assert mouse.tile_pos == (0, 0)


# ── set_cursor_visible / set_cursor_image ──────────────────────────────


def test_set_cursor_visible_toggles_the_real_os_cursor():
    Mouse.set_cursor_visible(False)
    assert pygame.mouse.get_visible() is False
    Mouse.set_cursor_visible(True)
    assert pygame.mouse.get_visible() is True


def test_set_cursor_image_stores_the_cursor():
    mouse = Mouse()
    cursor = _FakeCursor()
    mouse.set_cursor_image(cursor)
    assert mouse.cursor is cursor


# ── update ──────────────────────────────────────────────────────────────


def test_update_reads_the_real_mouse_position(monkeypatch):
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (123, 45))
    mouse = Mouse()
    mouse.update()
    assert mouse.position == (123, 45)


def test_default_scale_is_identity():
    assert Mouse().scale == (1.0, 1.0)


def test_update_applies_scale_to_convert_physical_to_logical_position(monkeypatch):
    """Application keeps this in sync with the ratio between the real OS
    window and the game's fixed logical render resolution, so a click at
    physical (100, 100) in a half-size window lands at logical (200, 200)."""
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (100, 100))
    mouse = Mouse()
    mouse.scale = (2.0, 2.0)

    mouse.update()

    assert mouse.position == (200.0, 200.0)


def test_default_offset_is_zero():
    assert Mouse().offset == (0.0, 0.0)


def test_update_applies_offset_before_scale(monkeypatch):
    """Application sets this when fixed_aspect=True letterboxes/pillarboxes
    the design resolution onto a differently-shaped display: the physical
    click first has the bar offset subtracted, then the scale factor is
    applied, so clicks inside the letterboxed content still land correctly."""
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (120, 50))
    mouse = Mouse()
    mouse.offset = (20, 10)
    mouse.scale = (2.0, 2.0)

    mouse.update()

    assert mouse.position == (200.0, 80.0)  # (120-20)*2, (50-10)*2


def test_update_computes_tile_pos_when_tile_size_given(monkeypatch):
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (100, 65))
    mouse = Mouse(tile_size=32)
    mouse.update()
    assert mouse.tile_pos == (3, 2)  # 100//32=3, 65//32=2


def test_update_without_tile_size_does_not_add_tile_pos(monkeypatch):
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (100, 65))
    mouse = Mouse()
    mouse.update()
    assert not hasattr(mouse, "tile_pos")


def test_update_moves_the_cursor_to_the_mouse_position(monkeypatch):
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (50, 60))
    mouse = Mouse()
    cursor = _FakeCursor()
    mouse.set_cursor_image(cursor)

    mouse.update()

    assert cursor.positions == [(50, 60)]


def test_update_without_a_cursor_does_not_raise(monkeypatch):
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (0, 0))
    mouse = Mouse()
    mouse.update()  # no cursor set -- must not raise


# ── draw ──────────────────────────────────────────────────────────────


def test_draw_delegates_to_the_cursor():
    mouse = Mouse()
    cursor = _FakeCursor()
    mouse.set_cursor_image(cursor)
    window = pygame.Surface((10, 10))

    mouse.draw(window)

    assert cursor.draw_calls == [window]


def test_draw_without_a_cursor_does_not_raise():
    mouse = Mouse()
    mouse.draw(pygame.Surface((10, 10)))  # no cursor set -- must not raise


# ── info ──────────────────────────────────────────────────────────────────


def test_info_without_tile_size(monkeypatch):
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (7, 8))
    mouse = Mouse()
    mouse.update()

    label, data = mouse.info()

    assert label == "Mouse Info:"
    assert data["pos"] == (7, 8)
    assert data["tile_pos"] is None


def test_info_with_tile_size(monkeypatch):
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (70, 80))
    mouse = Mouse(tile_size=32)
    mouse.update()

    label, data = mouse.info()

    assert data["pos"] == (70, 80)
    assert data["tile_pos"] == (2, 2)
