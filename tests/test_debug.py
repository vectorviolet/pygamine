"""Unit tests for Debug: the F1 debug-overlay renderer (background panel,
border, and per-source key/value text lines).
"""

from __future__ import annotations

import pygame
import pytest

from pygamine.app.debug import Debug


@pytest.fixture
def font():
    return pygame.font.Font(None, 16)


# ── get_debug_lines ─────────────────────────────────────────────────────


def test_get_debug_lines_with_no_sources_yields_only_the_header():
    lines = list(Debug.get_debug_lines([]))
    assert lines == ["DEBUG MODE", "==============================="]


def test_get_debug_lines_yields_source_and_key_value_lines():
    lines = list(Debug.get_debug_lines([("Player", {"hp": 10, "x": 5})]))
    assert lines == [
        "DEBUG MODE",
        "===============================",
        "Player",
        "hp: 10",
        "x: 5",
        "",
    ]


def test_get_debug_lines_handles_multiple_sources():
    lines = list(
        Debug.get_debug_lines(
            [
                ("Player", {"hp": 10}),
                ("Camera", {"scale": 1.0}),
            ]
        )
    )
    assert lines == [
        "DEBUG MODE",
        "===============================",
        "Player",
        "hp: 10",
        "",
        "Camera",
        "scale: 1.0",
        "",
    ]


def test_get_debug_lines_handles_a_source_with_no_info():
    lines = list(Debug.get_debug_lines([("Empty", {})]))
    assert lines == [
        "DEBUG MODE",
        "===============================",
        "Empty",
        "",
    ]


# ── draw_debug_background ──────────────────────────────────────────────


def test_draw_debug_background_darkens_the_target_area():
    surface = pygame.Surface((100, 100))
    surface.fill((255, 255, 255))

    Debug.draw_debug_background(surface, width=30, height=20)

    # background rect starts at (MARGIN, MARGIN) = (10, 10); alpha=150
    # black over white blends to exactly (105, 105, 105) (verified empirically)
    assert surface.get_at((15, 15)) == (105, 105, 105, 255)


def test_draw_debug_background_does_not_touch_area_outside_the_panel():
    surface = pygame.Surface((100, 100))
    surface.fill((255, 255, 255))

    Debug.draw_debug_background(surface, width=30, height=20)

    assert surface.get_at((90, 90)) == (255, 255, 255, 255)


# ── draw_debug_border ───────────────────────────────────────────────────


def test_draw_debug_border_draws_a_white_outline():
    surface = pygame.Surface((100, 100))
    surface.fill((0, 0, 0))

    Debug.draw_debug_border(surface, width=30, height=20)

    # border starts at (MARGIN - BORDER_WIDTH) = (8, 8)
    assert surface.get_at((8, 8)) == pygame.Color("white")


def test_draw_debug_border_does_not_fill_the_interior():
    surface = pygame.Surface((100, 100))
    surface.fill((0, 0, 0))

    Debug.draw_debug_border(surface, width=30, height=20)

    # well inside the bordered rect, away from the 2px outline
    assert surface.get_at((25, 15)) == (0, 0, 0, 255)


# ── draw_debug_text ─────────────────────────────────────────────────────


def test_draw_debug_text_stacks_surfaces_vertically(font):
    """Renders with an explicit background color so every pixel in each
    line's surface is deterministically foreground-or-background (not
    transparent), making exact pixel checks reliable regardless of glyph
    shapes."""
    surface = pygame.Surface((200, 200))
    line_a = font.render("AAAA", True, "white", (50, 50, 50))
    line_b = font.render("BBBB", True, "white", (80, 80, 80))

    Debug.draw_debug_text(surface, [line_a, line_b])

    # first line's top-left lands at (MARGIN+PADDING, MARGIN+PADDING) = (20, 20)
    assert surface.get_at((20, 20)) == (50, 50, 50, 255)
    # second line starts line_a.get_height() lower, with its own bg color
    second_line_y = 20 + line_a.get_height()
    assert surface.get_at((20, second_line_y)) == (80, 80, 80, 255)


# ── draw (full integration) ─────────────────────────────────────────────


def test_draw_renders_background_border_and_text_without_raising(font):
    surface = pygame.Surface((300, 300))
    surface.fill((0, 0, 0))

    Debug.draw(surface, font, [("Player", {"hp": 10})])

    # border should be visible somewhere near the top-left corner
    assert surface.get_at((8, 8)) == pygame.Color("white")
