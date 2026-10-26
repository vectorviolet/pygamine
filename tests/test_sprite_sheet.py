"""Unit tests for SpriteSheet: slicing a single image into frame Surfaces
via strip (single row/column), grid (rows x cols), and frame (one specific
cell), plus the copy vs. subsurface-view distinction.
"""

from __future__ import annotations

import pygame

from pygamine.assets.asset_manager import AssetManager
from pygamine.assets.sprite_sheet import SpriteSheet


def _banded_strip(colors, band_size=10, horizontal=True) -> pygame.Surface:
    """A strip image made of N equal-sized color bands, laid out either
    left-to-right (horizontal) or top-to-bottom (vertical)."""
    n = len(colors)
    size = (band_size * n, band_size) if horizontal else (band_size, band_size * n)
    strip = pygame.Surface(size, pygame.SRCALPHA)
    for i, color in enumerate(colors):
        band = pygame.Surface((band_size, band_size), pygame.SRCALPHA)
        band.fill(color)
        pos = (i * band_size, 0) if horizontal else (0, i * band_size)
        strip.blit(band, pos)
    return strip


def _grid_image(colors, cols, rows, cell_size=10) -> pygame.Surface:
    """A cols x rows grid image, colors given in row-major order."""
    grid = pygame.Surface((cell_size * cols, cell_size * rows), pygame.SRCALPHA)
    for i, color in enumerate(colors):
        c, r = i % cols, i // cols
        cell = pygame.Surface((cell_size, cell_size), pygame.SRCALPHA)
        cell.fill(color)
        grid.blit(cell, (c * cell_size, r * cell_size))
    return grid


RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)
YELLOW = (255, 255, 0, 255)
CYAN = (0, 255, 255, 255)
MAGENTA = (255, 0, 255, 255)


# ── construction ────────────────────────────────────────────────────────


def test_construction_stores_the_image():
    image = pygame.Surface((10, 10))
    sheet = SpriteSheet(image)
    assert sheet.image is image


def test_from_path_loads_a_real_image(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pygame.display.set_mode((1, 1))  # convert_alpha() needs a display mode set

    images_dir = tmp_path / "assets" / "images"
    images_dir.mkdir(parents=True)
    surf = pygame.Surface((20, 10), pygame.SRCALPHA)
    surf.fill(RED)
    pygame.image.save(surf, str(images_dir / "strip.png"))

    manifest = tmp_path / "assets.yaml"
    manifest.write_text("images:\n  strip: {name: strip}\n")
    assets = AssetManager()
    assets.load_manifest(manifest)

    sheet = SpriteSheet.from_path(assets.image_path("strip"))

    assert sheet.image.get_size() == (20, 10)
    assert sheet.image.get_at((5, 5)) == RED


# ── strip: horizontal ────────────────────────────────────────────────────


def test_strip_horizontal_slices_left_to_right_in_order():
    sheet = SpriteSheet(_banded_strip([RED, GREEN, BLUE, YELLOW]))
    frames = sheet.strip(4)

    assert len(frames) == 4
    for frame, expected in zip(frames, [RED, GREEN, BLUE, YELLOW]):
        assert frame.get_size() == (10, 10)
        assert frame.get_at((5, 5)) == expected


def test_strip_vertical_slices_top_to_bottom_in_order():
    sheet = SpriteSheet(_banded_strip([RED, GREEN, BLUE], horizontal=False))
    frames = sheet.strip(3, horizontal=False)

    assert len(frames) == 3
    for frame, expected in zip(frames, [RED, GREEN, BLUE]):
        assert frame.get_size() == (10, 10)
        assert frame.get_at((5, 5)) == expected


def test_strip_zero_or_negative_frame_count_returns_empty_list():
    sheet = SpriteSheet(_banded_strip([RED, GREEN]))
    assert sheet.strip(0) == []
    assert sheet.strip(-1) == []


def test_strip_uneven_division_uses_floor_division_for_frame_size():
    """A 25px-wide strip sliced into 4 frames gives frames 6px wide
    (25 // 4), not a rounded/fractional size -- the last ~1px column of
    source pixels is simply not covered by any frame."""
    strip = pygame.Surface((25, 10), pygame.SRCALPHA)
    sheet = SpriteSheet(strip)

    frames = sheet.strip(4)

    assert all(f.get_size() == (6, 10) for f in frames)


# ── grid ──────────────────────────────────────────────────────────────


def test_grid_slices_in_row_major_order_for_a_non_square_grid():
    colors = [RED, GREEN, BLUE, YELLOW, CYAN, MAGENTA]  # 3 cols x 2 rows
    sheet = SpriteSheet(_grid_image(colors, cols=3, rows=2))

    frames = sheet.grid(cols=3, rows=2)

    assert len(frames) == 6
    for frame, expected in zip(frames, colors):
        assert frame.get_size() == (10, 10)
        assert frame.get_at((5, 5)) == expected


def test_grid_zero_or_negative_cols_or_rows_returns_empty_list():
    sheet = SpriteSheet(_grid_image([RED, GREEN], cols=2, rows=1))
    assert sheet.grid(cols=0, rows=1) == []
    assert sheet.grid(cols=1, rows=0) == []
    assert sheet.grid(cols=-1, rows=1) == []


# ── frame ─────────────────────────────────────────────────────────────


def test_frame_pulls_a_single_cell_by_explicit_grid_coordinate():
    colors = [RED, GREEN, BLUE, YELLOW]  # 2x2, cell size 10
    sheet = SpriteSheet(_grid_image(colors, cols=2, rows=2))

    top_right = sheet.frame(col=1, row=0, frame_w=10, frame_h=10)
    bottom_left = sheet.frame(col=0, row=1, frame_w=10, frame_h=10)

    assert top_right.get_at((5, 5)) == GREEN
    assert bottom_left.get_at((5, 5)) == BLUE


# ── copy vs. subsurface view ─────────────────────────────────────────


def test_copy_true_returns_an_independent_surface():
    sheet = SpriteSheet(_banded_strip([RED, GREEN]))
    frame = sheet.strip(2, copy=True)[0]

    sheet.image.fill(BLUE)  # mutate the source after slicing

    assert frame.get_at((5, 5)) == RED  # untouched -- it's a real copy


def test_copy_false_returns_a_live_subsurface_view():
    sheet = SpriteSheet(_banded_strip([RED, GREEN]))
    frame = sheet.strip(2, copy=False)[0]
    assert frame.get_at((5, 5)) == RED

    sheet.image.fill(BLUE, pygame.Rect(0, 0, 10, 10))  # mutate just the first band

    assert frame.get_at((5, 5)) == BLUE  # a view into the same pixels, not a copy
