"""Unit tests for SpriteRenderer2D: blits its image at the owning
GameObject's rect."""

from __future__ import annotations

import pygame
import pytest

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


def test_require_image_returns_the_image_once_set():
    renderer = GameObject().add_component(SpriteRenderer2D)
    image = pygame.Surface((4, 4))
    renderer.set_image(image)
    assert renderer.require_image() is image


def test_require_image_raises_naming_the_owner_before_set_image():
    renderer = GameObject("tile").add_component(SpriteRenderer2D)
    with pytest.raises(RuntimeError, match=r"SpriteRenderer2D on 'tile' has no image"):
        renderer.require_image()


def test_require_image_raises_when_unattached_and_empty():
    with pytest.raises(RuntimeError, match=r"SpriteRenderer2D has no image"):
        SpriteRenderer2D().require_image()
