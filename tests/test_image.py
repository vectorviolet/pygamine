"""Unit tests for image.py: load_image (cached, with a size-convention mini
DSL), scale, scale_by, and nine_slice_scale.
"""

from __future__ import annotations

from pathlib import Path

import pygame
import pytest

from pygamine.assets.image import load_image, nine_slice_scale, scale, scale_by


def _save_png(path, size, color):
    surf = pygame.Surface(size, pygame.SRCALPHA)
    surf.fill(color)
    pygame.image.save(surf, str(path))


@pytest.fixture
def image_path(tmp_path) -> Path:
    pygame.display.set_mode((1, 1))  # convert_alpha() needs a display mode set
    path = tmp_path / "img.png"
    _save_png(path, (40, 20), (255, 0, 0))
    return path


# ── load_image: caching ─────────────────────────────────────────────────


def test_load_image_returns_the_same_cached_object_on_repeated_calls(image_path):
    first = load_image(image_path)
    second = load_image(image_path)
    assert first is second


# ── load_image: size conventions ────────────────────────────────────────


def test_load_image_default_size_returns_original_dimensions(image_path):
    img = load_image(image_path)
    assert img.get_size() == (40, 20)


def test_load_image_size_zero_zero_is_the_same_as_no_size(image_path):
    img = load_image(image_path, size=(0, 0))
    assert img.get_size() == (40, 20)


def test_load_image_return_size_true_reports_original_size(image_path):
    img, size = load_image(image_path, return_size=True)
    assert img.get_size() == (40, 20)
    assert size == [40, 20]


def test_load_image_zero_component_keeps_that_source_dimension(image_path):
    """A zero on one axis means 'keep the source size on that axis' --
    only the other axis is actually resized."""
    img = load_image(image_path, size=[0, 40])
    assert img.get_size() == (40, 40)  # width kept from source, height forced to 40


def test_load_image_explicit_size_scales_to_it(image_path):
    img = load_image(image_path, size=(80, 10))
    assert img.get_size() == (80, 10)


def test_load_image_accepts_size_as_a_tuple_or_a_list(image_path):
    from_tuple = load_image(image_path, size=(20, 20))
    from_list = load_image(image_path, size=[20, 20])
    assert from_tuple.get_size() == from_list.get_size() == (20, 20)


def test_load_image_return_size_true_with_explicit_size(image_path):
    img, size = load_image(image_path, size=(80, 10), return_size=True)
    assert img.get_size() == (80, 10)
    assert size == [80, 10]


# ── load_image: nine_slice dispatch ────────────────────────────────────


def test_load_image_nine_slice_zero_uses_plain_scale(image_path):
    """nine_slice=0 (default) should behave like a plain resize -- a solid
    fill scales to a solid fill of the same color either way, so this just
    confirms it doesn't error and produces the requested size."""
    img = load_image(image_path, size=(80, 40), nine_slice=0)
    assert img.get_size() == (80, 40)
    assert img.get_at((40, 20)) == (255, 0, 0, 255)


def test_load_image_nine_slice_positive_dispatches_to_nine_slice_scale(image_path):
    img = load_image(image_path, size=(80, 40), nine_slice=5)
    assert img.get_size() == (80, 40)


# ── scale ────────────────────────────────────────────────────────────


def test_scale_resizes_to_the_given_size():
    surf = pygame.Surface((10, 10))
    surf.fill((0, 255, 0))
    result = scale(surf, (20, 5))
    assert result.get_size() == (20, 5)
    assert result.get_at((10, 2)) == (0, 255, 0, 255)


# ── scale_by ─────────────────────────────────────────────────────────


def test_scale_by_single_factor_applies_to_both_axes():
    surf = pygame.Surface((10, 20))
    result = scale_by(surf, 2)
    assert result.get_size() == (20, 40)


def test_scale_by_tuple_factor_applies_per_axis():
    surf = pygame.Surface((10, 20))
    result = scale_by(surf, (3, 0.5))
    assert result.get_size() == (30, 10)


# ── nine_slice_scale ────────────────────────────────────────────────────


RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)
YELLOW = (255, 255, 0, 255)
CYAN = (0, 255, 255, 255)
MAGENTA = (255, 0, 255, 255)
ORANGE = (255, 128, 0, 255)
PURPLE = (128, 0, 128, 255)
PINK = (255, 192, 203, 255)


def _nine_region_image(cell=10) -> pygame.Surface:
    """A 3x3 grid (each cell distinctly colored) to verify nine_slice_scale
    places/stretches each of the 9 regions correctly."""
    colors = [
        [RED, GREEN, BLUE],
        [YELLOW, CYAN, MAGENTA],
        [ORANGE, PURPLE, PINK],
    ]
    img = pygame.Surface((cell * 3, cell * 3), pygame.SRCALPHA)
    for r, row in enumerate(colors):
        for c, color in enumerate(row):
            patch = pygame.Surface((cell, cell), pygame.SRCALPHA)
            patch.fill(color)
            img.blit(patch, (c * cell, r * cell))
    return img


def test_nine_slice_scale_places_corners_pixel_perfect_and_unscaled():
    image = _nine_region_image(cell=10)
    result = nine_slice_scale(image, target_size=(60, 60), corner=10)

    assert result.get_size() == (60, 60)
    assert result.get_at((5, 5)) == RED  # top-left corner
    assert result.get_at((55, 5)) == BLUE  # top-right corner
    assert result.get_at((5, 55)) == ORANGE  # bottom-left corner
    assert result.get_at((55, 55)) == PINK  # bottom-right corner


def test_nine_slice_scale_stretches_edges_in_one_axis():
    image = _nine_region_image(cell=10)
    result = nine_slice_scale(image, target_size=(60, 60), corner=10)

    assert result.get_at((30, 5)) == GREEN  # top edge, stretched horizontally
    assert result.get_at((30, 55)) == PURPLE  # bottom edge
    assert result.get_at((5, 30)) == YELLOW  # left edge, stretched vertically
    assert result.get_at((55, 30)) == MAGENTA  # right edge


def test_nine_slice_scale_stretches_center_in_both_axes():
    image = _nine_region_image(cell=10)
    result = nine_slice_scale(image, target_size=(60, 60), corner=10)

    assert result.get_at((30, 30)) == CYAN


def test_nine_slice_scale_to_the_same_size_is_pixel_identical():
    """When target_size matches the source, each piece's (sw, sh) == (dw, dh)
    so the blit skips the scale() call entirely -- still must reproduce the
    source exactly."""
    image = _nine_region_image(cell=10)
    result = nine_slice_scale(image, target_size=(30, 30), corner=10)

    assert result.get_at((5, 5)) == RED
    assert result.get_at((15, 15)) == CYAN
    assert result.get_at((25, 25)) == PINK
