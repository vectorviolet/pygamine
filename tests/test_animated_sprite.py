"""Unit tests for AnimatedSprite and AnimatedSpriteFactory: a GameObject
preconfigured with SpriteRenderer2D + Animator for sheet-based animation.
"""

from __future__ import annotations

import pygame
import pytest

from pygamine.assets.asset_manager import AssetManager
from pygamine.ecs.animated_sprite import AnimatedSprite, AnimatedSpriteFactory
from pygamine.ecs.components.transform import Transform


def _frame(color, size=(10, 10)):
    surf = pygame.Surface(size, pygame.SRCALPHA)
    surf.fill(color)
    return surf


def _frames(*colors, size=(10, 10)):
    return [_frame(c, size) for c in colors]


# ── construction ────────────────────────────────────────────────────────


def test_requires_at_least_one_frame():
    with pytest.raises(ValueError):
        AnimatedSprite(frames=None)
    with pytest.raises(ValueError):
        AnimatedSprite(frames=[])


def test_default_size_uses_the_source_frame_size_without_scaling():
    frames = _frames((255, 0, 0))
    sprite = AnimatedSprite(frames=frames)

    assert sprite.rect.size == (10, 10)
    assert (
        sprite.animator.clips["default"].frames[0] is frames[0]
    )  # not rescaled/copied


def test_size_matching_source_does_not_rescale():
    frames = _frames((255, 0, 0))
    sprite = AnimatedSprite(size=(10, 10), frames=frames)
    assert sprite.animator.clips["default"].frames[0] is frames[0]


def test_size_different_from_source_scales_frames():
    frames = _frames((255, 0, 0))
    sprite = AnimatedSprite(size=(20, 20), frames=frames)

    scaled = sprite.animator.clips["default"].frames[0]
    assert scaled is not frames[0]
    assert scaled.get_size() == (20, 20)
    assert scaled.get_at((5, 5)) == (
        255,
        0,
        0,
        255,
    )  # still the same color, just bigger
    assert sprite.rect.size == (20, 20)


def test_name_defaults_and_can_be_overridden():
    assert AnimatedSprite(frames=_frames((1, 2, 3))).name == "animated_sprite"
    assert AnimatedSprite(frames=_frames((1, 2, 3)), name="coin").name == "coin"


def test_pos_and_parent_position_the_rect():
    parent = Transform(position=(100, 50), size=(200, 100))
    sprite = AnimatedSprite(
        parent=parent, pos=(10, 10), size=(10, 10), frames=_frames((1, 2, 3))
    )
    assert sprite.rect.topleft == (110, 60)


def test_registers_sprite_renderer_and_animator_components():
    from pygamine.ecs.components.animator import Animator
    from pygamine.ecs.components.sprite_renderer2d import SpriteRenderer2D

    sprite = AnimatedSprite(frames=_frames((1, 2, 3)))
    assert sprite.get_component(SpriteRenderer2D) is not None
    assert sprite.get_component(Animator) is sprite.animator


def test_default_clip_starts_playing_immediately():
    frames = _frames((255, 0, 0), (0, 255, 0))
    sprite = AnimatedSprite(frames=frames, fps=8, loop=False)

    assert sprite.animator.is_playing is True
    assert sprite.animator.current_clip == "default"
    assert sprite.animator.clips["default"].fps == 8
    assert sprite.animator.clips["default"].loop is False


def test_first_frame_is_applied_to_the_renderer_on_construction():
    from pygamine.ecs.components.sprite_renderer2d import SpriteRenderer2D

    frames = _frames((255, 0, 0), (0, 255, 0))
    sprite = AnimatedSprite(frames=frames)

    renderer = sprite.get_component(SpriteRenderer2D)
    assert renderer.image.get_at((5, 5)) == (255, 0, 0, 255)


# ── _resolve_size ─────────────────────────────────────────────────────


def test_resolve_size_none_defers_to_source():
    assert AnimatedSprite._resolve_size(None, (10, 20)) == (10, 20)


def test_resolve_size_zero_zero_defers_to_source():
    assert AnimatedSprite._resolve_size((0, 0), (10, 20)) == (10, 20)


def test_resolve_size_accepts_a_pygame_rect():
    assert AnimatedSprite._resolve_size(pygame.Rect(0, 0, 30, 40), (10, 20)) == (30, 40)


def test_resolve_size_wrong_length_raises():
    with pytest.raises(ValueError):
        AnimatedSprite._resolve_size((1, 2, 3), (10, 20))


def test_resolve_size_returns_explicit_nonzero_size_as_is():
    assert AnimatedSprite._resolve_size((15, 25), (10, 20)) == (15, 25)


# ── add_clip / play ─────────────────────────────────────────────────────


def test_add_clip_registers_a_new_named_clip():
    sprite = AnimatedSprite(frames=_frames((1, 2, 3)))
    walk_frames = _frames((10, 20, 30), (40, 50, 60))

    sprite.add_clip("walk", walk_frames, fps=6, loop=False)

    clip = sprite.animator.clips["walk"]
    assert clip.frames == walk_frames
    assert clip.fps == 6
    assert clip.loop is False


def test_play_switches_to_the_named_clip():
    from pygamine.ecs.components.sprite_renderer2d import SpriteRenderer2D

    sprite = AnimatedSprite(frames=_frames((255, 0, 0)))
    walk_frames = _frames((0, 255, 0), (0, 0, 255))
    sprite.add_clip("walk", walk_frames)

    sprite.play("walk")

    assert sprite.animator.current_clip == "walk"
    renderer = sprite.get_component(SpriteRenderer2D)
    assert renderer.image.get_at((5, 5)) == (0, 255, 0, 255)


def test_play_restart_flag_passes_through(fake_ticks):
    sprite = AnimatedSprite(frames=_frames((1, 1, 1), (2, 2, 2), (3, 3, 3)), fps=10)
    fake_ticks["t"] = 100
    sprite.animator.update()
    assert sprite.animator._frame == 1

    sprite.play("default")  # already playing, no restart -> frame preserved
    assert sprite.animator._frame == 1

    sprite.play("default", restart=True)  # explicit restart -> back to frame 0
    assert sprite.animator._frame == 0


# ── AnimatedSpriteFactory ────────────────────────────────────────────────


@pytest.fixture
def assets(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pygame.display.set_mode((1, 1))

    images_dir = tmp_path / "assets" / "images"
    images_dir.mkdir(parents=True)

    strip = pygame.Surface((40, 10), pygame.SRCALPHA)
    for i, color in enumerate([(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]):
        band = pygame.Surface((10, 10), pygame.SRCALPHA)
        band.fill(color)
        strip.blit(band, (i * 10, 0))
    pygame.image.save(strip, str(images_dir / "strip.png"))

    grid = pygame.Surface((20, 20), pygame.SRCALPHA)
    for i, color in enumerate([(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]):
        cell = pygame.Surface((10, 10), pygame.SRCALPHA)
        cell.fill(color)
        grid.blit(cell, ((i % 2) * 10, (i // 2) * 10))
    pygame.image.save(grid, str(images_dir / "grid.png"))

    manifest = tmp_path / "assets.yaml"
    manifest.write_text("images:\n  strip: {name: strip}\n  grid: {name: grid}\n")
    mgr = AssetManager()
    mgr.load_manifest(manifest)
    return mgr


def test_from_strip_builds_a_sprite_from_a_horizontal_strip(assets):
    factory = AnimatedSpriteFactory(assets)
    sprite = factory.from_strip("strip", size=(10, 10), frame_count=4)

    frames = sprite.animator.clips["default"].frames
    assert len(frames) == 4
    expected = [
        (255, 0, 0, 255),
        (0, 255, 0, 255),
        (0, 0, 255, 255),
        (255, 255, 0, 255),
    ]
    for frame, color in zip(frames, expected):
        assert frame.get_at((1, 1)) == color


def test_from_strip_defaults_name_to_the_asset_key(assets):
    factory = AnimatedSpriteFactory(assets)
    sprite = factory.from_strip("strip", size=(10, 10), frame_count=4)
    assert sprite.name == "strip"


def test_from_strip_name_can_be_overridden(assets):
    factory = AnimatedSpriteFactory(assets)
    sprite = factory.from_strip("strip", size=(10, 10), frame_count=4, name="coin")
    assert sprite.name == "coin"


def test_from_grid_builds_a_sprite_from_a_grid(assets):
    factory = AnimatedSpriteFactory(assets)
    sprite = factory.from_grid("grid", size=(10, 10), cols=2, rows=2)

    frames = sprite.animator.clips["default"].frames
    assert len(frames) == 4
    expected = [
        (255, 0, 0, 255),
        (0, 255, 0, 255),
        (0, 0, 255, 255),
        (255, 255, 0, 255),
    ]
    for frame, color in zip(frames, expected):
        assert frame.get_at((1, 1)) == color
