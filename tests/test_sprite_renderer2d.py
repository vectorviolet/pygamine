"""Unit tests for SpriteRenderer2D: blits its image at the owning
GameObject's rect."""

from __future__ import annotations

import pygame

from pygamine.ecs.components.sprite_renderer2d import SpriteRenderer2D
from pygamine.ecs.game_object import GameObject


def test_draw_does_nothing_when_no_image_set():
    go = GameObject()
    renderer = go.add_component(SpriteRenderer2D)
    surface = pygame.Surface((100, 100))

    renderer.draw(surface)  # must not raise, no image to blit


def test_draw_blits_image_at_game_object_rect():
    """pygame.Surface is a C type that won't allow monkeypatching .blit, so
    verify the real blit landed in the right place via pixel content instead
    of a call-spy."""
    go = GameObject()
    go.rect.topleft = (10, 20)
    go.rect.size = (5, 5)
    renderer = go.add_component(SpriteRenderer2D)
    image = pygame.Surface((5, 5))
    image.fill((255, 0, 0))
    renderer.set_image(image)

    surface = pygame.Surface((100, 100))
    surface.fill((0, 255, 0))

    renderer.draw(surface)

    assert surface.get_at((12, 22)) == (255, 0, 0, 255)  # inside the blitted image
    assert surface.get_at((0, 0)) == (0, 255, 0, 255)  # untouched background
