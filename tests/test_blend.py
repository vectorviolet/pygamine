"""Unit tests for ALPHA_BLIT, the platform-dependent translucent blit flag."""

from __future__ import annotations

import sys

import pygame
import pytest

import pygamine
from pygamine.app.camera import Camera
from pygamine.ecs.components.sprite_renderer2d import SpriteRenderer2D
from pygamine.ecs.game_object import GameObject
from pygamine.util.blend import ALPHA_BLIT, alpha_blit_flag


def test_flag_is_sdl2_alpha_blend_on_emscripten():
    assert alpha_blit_flag("emscripten") == pygame.BLEND_ALPHA_SDL2


@pytest.mark.parametrize("platform", ["win32", "linux", "darwin"])
def test_flag_is_the_default_blit_on_desktop(platform):
    assert alpha_blit_flag(platform) == 0


def test_exported_constant_matches_the_running_platform():
    assert ALPHA_BLIT == alpha_blit_flag(sys.platform)
    assert pygamine.ALPHA_BLIT == ALPHA_BLIT


@pytest.fixture(params=[0, pygame.BLEND_ALPHA_SDL2], ids=["default", "sdl2"])
def flag(request, monkeypatch):
    """Run the draw code under both flag values, whatever platform the tests run on."""
    monkeypatch.setattr(
        "pygamine.ecs.components.sprite_renderer2d.ALPHA_BLIT", request.param
    )
    monkeypatch.setattr("pygamine.app.camera.ALPHA_BLIT", request.param)
    return request.param


def _half_red() -> pygame.Surface:
    image = pygame.Surface((4, 4), pygame.SRCALPHA)
    image.fill((255, 0, 0, 128))
    return image


def _is_half_blended(pixel) -> bool:
    return 120 <= pixel.r <= 136 and 120 <= pixel.g <= 136 and pixel.b == 0


def test_sprite_renderer_blends_a_translucent_image_with_either_flag(flag):
    go = GameObject()
    go.rect.topleft = (10, 10)
    go.rect.size = (4, 4)
    renderer = go.add_component(SpriteRenderer2D)
    renderer.set_image(_half_red())
    surface = pygame.Surface((50, 50))
    surface.fill((0, 255, 0))

    renderer.draw(surface)

    assert _is_half_blended(surface.get_at((11, 11)))
    assert surface.get_at((0, 0)) == (0, 255, 0, 255)


def test_camera_blends_a_translucent_image_with_either_flag(flag):
    class Sprite:
        image = _half_red()
        rect = pygame.Rect(0, 0, 4, 4)

    camera = Camera(pygame.Rect(0, 0, 50, 50))
    surface = pygame.Surface((50, 50))
    surface.fill((0, 255, 0))

    camera.draw(surface, Sprite())

    assert any(
        _is_half_blended(surface.get_at((x, y))) for x in range(50) for y in range(50)
    )
