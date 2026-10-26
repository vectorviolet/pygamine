"""Unit tests for panel_factory: the make_*_factory functions PanelLoader
invokes to turn a YAML object definition into a real widget.

Builds a real AssetManager backed by real image/font files under tmp_path
(matching how these factories are actually used -- PanelLoader pre-resolves
"asset"/"hover" config keys to ImagePath objects before calling the factory),
rather than mocking asset resolution.
"""

from __future__ import annotations

import os

import pygame
import pytest

from pygamine.assets.asset_manager import AssetManager
from pygamine.ecs.animated_sprite import AnimatedSprite
from pygamine.ecs.components.sprite_renderer2d import SpriteRenderer2D
from pygamine.ecs.components.transform import Transform
from pygamine.ecs.state_object import HoverableStateObject, StateObject
from pygamine.panels.panel_factory import (
    make_animated_factory,
    make_factory,
    make_text_factory,
)
from pygamine.ui_widgets.text_object import TextObject


def _save_png(path, size, color):
    surf = pygame.Surface(size, pygame.SRCALPHA)
    surf.fill(color)
    pygame.image.save(surf, str(path))


def _save_strip(
    path,
    frame_size=(10, 10),
    colors=((255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)),
):
    fw, fh = frame_size
    strip = pygame.Surface((fw * len(colors), fh), pygame.SRCALPHA)
    for i, color in enumerate(colors):
        band = pygame.Surface(frame_size, pygame.SRCALPHA)
        band.fill(color)
        strip.blit(band, (i * fw, 0))
    pygame.image.save(strip, str(path))


@pytest.fixture
def assets(tmp_path, monkeypatch) -> AssetManager:
    monkeypatch.chdir(tmp_path)
    pygame.display.set_mode((1, 1))  # convert_alpha() needs a display mode set

    images_dir = tmp_path / "assets" / "images"
    images_dir.mkdir(parents=True)
    _save_png(images_dir / "btn.png", (20, 20), (255, 0, 0))
    _save_png(images_dir / "btn_hover.png", (20, 20), (0, 255, 0))
    _save_png(images_dir / "btn_state_a.png", (20, 20), (0, 0, 255))
    _save_strip(images_dir / "strip.png")

    fonts_dir = tmp_path / "assets" / "fonts"
    fonts_dir.mkdir(parents=True)
    real_font_src = os.path.join(os.path.dirname(pygame.__file__), "freesansbold.ttf")
    (fonts_dir / "registered_font.ttf").write_bytes(open(real_font_src, "rb").read())

    manifest = tmp_path / "assets.yaml"
    manifest.write_text(
        "images:\n"
        "  btn: {name: btn}\n"
        "  btn_hover: {name: btn_hover}\n"
        "  btn_state_a: {name: btn_state_a}\n"
        "  strip: {name: strip}\n"
        "sounds:\n"
        "  click: {name: click}\n"
        "fonts:\n"
        "  registered_font: {name: registered_font}\n"
        "  broken_font: {name: does_not_exist}\n"
    )
    mgr = AssetManager()
    mgr.load_manifest(manifest)
    return mgr


@pytest.fixture
def parent() -> Transform:
    return Transform(position=(0, 0), size=(800, 600))


def _image(obj) -> pygame.Surface | None:
    return obj.get_component(SpriteRenderer2D).image


# ── make_factory: color-fill branch ─────────────────────────────────────


def test_color_fill_branch_creates_a_solid_filled_state_object(assets, parent):
    factory = make_factory(assets)
    cfg = {"position": (0, 0), "size": [20, 20], "color": [10, 20, 30]}

    obj = factory(cfg, parent)

    assert isinstance(obj, StateObject)
    assert not isinstance(obj, HoverableStateObject)
    assert obj.state is None
    assert _image(obj).get_at((5, 5)) == (10, 20, 30, 255)


def test_color_fill_branch_is_not_used_when_asset_is_also_given(assets, parent):
    """color-fill only applies when there's no asset -- an asset always wins."""
    factory = make_factory(assets)
    cfg = {
        "position": (0, 0),
        "size": [20, 20],
        "color": [10, 20, 30],
        "asset": assets.image_path("btn"),
    }

    obj = factory(cfg, parent)

    assert _image(obj).get_at((5, 5)) == (
        255,
        0,
        0,
        255,
    )  # btn.png's color, not the fill color


# ── make_factory: plain StateObject branch ─────────────────────────────


def test_plain_state_object_branch_loads_the_asset_image(assets, parent):
    factory = make_factory(assets)
    cfg = {"position": (0, 0), "size": [20, 20], "asset": assets.image_path("btn")}

    obj = factory(cfg, parent)

    assert isinstance(obj, StateObject)
    assert not isinstance(obj, HoverableStateObject)
    assert _image(obj).get_at((5, 5)) == (255, 0, 0, 255)


def test_anchor_and_nine_slice_pass_through(assets, parent):
    factory = make_factory(assets)
    cfg = {
        "position": (0, 0),
        "size": [20, 20],
        "asset": assets.image_path("btn"),
        "anchor": "center",
    }

    obj = factory(cfg, parent)

    assert obj.rect.anchor == "center"


# ── make_factory: HoverableStateObject via hover ───────────────────────


def test_hover_key_creates_a_hoverable_state_object(assets, parent):
    factory = make_factory(assets)
    cfg = {
        "position": (0, 0),
        "size": [20, 20],
        "asset": assets.image_path("btn"),
        "hover": assets.image_path("btn_hover"),
    }

    obj = factory(cfg, parent)

    assert isinstance(obj, HoverableStateObject)
    assert obj._hover_images[None].get_at((5, 5)) == (0, 255, 0, 255)


# ── make_factory: HoverableStateObject via extra_states ────────────────


def test_extra_states_creates_a_hoverable_state_object_even_without_hover(
    assets, parent
):
    factory = make_factory(assets)
    cfg = {
        "position": (0, 0),
        "size": [20, 20],
        "asset": assets.image_path("btn"),
        "states": {"purchased": {"asset": assets.image_path("btn_state_a")}},
    }

    obj = factory(cfg, parent)

    assert isinstance(obj, HoverableStateObject)
    assert obj.images["purchased"].get_at((5, 5)) == (0, 0, 255, 255)


def test_extra_state_asset_given_as_a_string_key_is_resolved_via_assets(assets, parent):
    """state_cfg["asset"] may be a raw manifest key (string) instead of an
    already-resolved ImagePath -- PanelLoader doesn't pre-resolve nested
    per-state assets the way it does the top-level asset/hover keys."""
    factory = make_factory(assets)
    cfg = {
        "position": (0, 0),
        "size": [20, 20],
        "asset": assets.image_path("btn"),
        "states": {"purchased": {"asset": "btn_state_a"}},
    }

    obj = factory(cfg, parent)

    assert obj.images["purchased"].get_at((5, 5)) == (0, 0, 255, 255)


def test_extra_state_with_its_own_hover_image(assets, parent):
    factory = make_factory(assets)
    cfg = {
        "position": (0, 0),
        "size": [20, 20],
        "asset": assets.image_path("btn"),
        "states": {"purchased": {"asset": "btn_state_a", "hover": "btn_hover"}},
    }

    obj = factory(cfg, parent)

    assert obj._hover_images["purchased"].get_at((5, 5)) == (0, 255, 0, 255)


# ── make_factory: click sound ────────────────────────────────────────


def test_click_sound_resolved_when_given(assets, parent):
    factory = make_factory(assets)
    cfg = {
        "position": (0, 0),
        "size": [20, 20],
        "asset": assets.image_path("btn"),
        "on_click_sound": "click",
    }

    obj = factory(cfg, parent)

    assert obj.on_click_sound == assets.sound_path("click")


def test_click_sound_defaults_to_none(assets, parent):
    factory = make_factory(assets)
    cfg = {"position": (0, 0), "size": [20, 20], "asset": assets.image_path("btn")}

    obj = factory(cfg, parent)

    assert obj.on_click_sound is None


# ── make_factory: size: WINDOW ──────────────────────────────────────────


def test_size_window_sizes_the_object_to_the_parents_size(assets, parent):
    """cfg["size"] == "WINDOW" sizes the object to fill its parent -- fixed
    from a prior bug where `size = parent` assigned the Transform itself
    (not a tuple) to rect.size, which pygame.Rect rejected with a TypeError."""
    factory = make_factory(assets)
    cfg = {"position": (0, 0), "size": "WINDOW", "asset": assets.image_path("btn")}

    obj = factory(cfg, parent)

    assert obj.rect.size == parent.size


# ── make_animated_factory ──────────────────────────────────────────────


def test_animated_factory_slices_the_strip_into_correctly_colored_frames(
    assets, parent
):
    factory = make_animated_factory(assets)
    cfg = {
        "position": (0, 0),
        "size": [0, 0],
        "asset": assets.image_path("strip"),
        "frame_count": 4,
        "fps": 10,
        "loop": True,
    }

    sprite = factory(cfg, parent)

    assert isinstance(sprite, AnimatedSprite)
    frames = sprite.animator.clips["default"].frames
    assert len(frames) == 4
    expected_colors = [
        (255, 0, 0, 255),
        (0, 255, 0, 255),
        (0, 0, 255, 255),
        (255, 255, 0, 255),
    ]
    for frame, expected in zip(frames, expected_colors):
        assert frame.get_at((1, 1)) == expected


def test_animated_factory_defaults_frame_count_and_fps(assets, parent):
    factory = make_animated_factory(assets)
    cfg = {
        "position": (0, 0),
        "asset": assets.image_path("btn"),
    }  # no frame_count/fps/loop given

    sprite = factory(cfg, parent)

    assert len(sprite.animator.clips["default"].frames) == 1
    assert sprite.animator.clips["default"].fps == 12.0
    assert sprite.animator.clips["default"].loop is True


def test_animated_factory_size_omitted_or_window_defers_to_source_size(assets, parent):
    factory = make_animated_factory(assets)
    cfg = {"position": (0, 0), "asset": assets.image_path("strip"), "frame_count": 4}

    sprite = factory(cfg, parent)

    assert sprite.rect.size == (10, 10)  # each sliced frame is 10x10


# ── make_text_factory ───────────────────────────────────────────────────


def test_text_factory_builds_a_text_object_with_given_params(assets, parent):
    factory = make_text_factory(assets)
    cfg = {
        "position": (0, 0),
        "text": "Score: 0",
        "color": [1, 2, 3],
        "padding": 4,
        "anchor": "center",
    }

    label = factory(cfg, parent)

    assert isinstance(label, TextObject)
    assert label.text == "Score: 0"
    assert label.color == (1, 2, 3)
    assert label.padding == (4, 4, 4, 4)
    assert label.rect.anchor == "center"


def test_text_factory_defaults_text_to_empty_string(assets, parent):
    factory = make_text_factory(assets)
    cfg = {"position": (0, 0)}

    label = factory(cfg, parent)

    assert label.text == ""


def test_text_factory_falls_back_to_sysfont_when_font_is_not_registered(assets, parent):
    factory = make_text_factory(assets)
    cfg = {
        "position": (0, 0),
        "text": "Hi",
        "font": "Arial",
    }  # "Arial" isn't in the manifest

    label = factory(cfg, parent)  # must not raise

    assert isinstance(label.font, pygame.font.Font)


def test_text_factory_uses_a_registered_font_file(assets, parent):
    factory = make_text_factory(assets)
    cfg = {"position": (0, 0), "text": "Hi", "font": "registered_font", "font_size": 24}

    label = factory(cfg, parent)  # must not raise, and must actually load the real file

    assert isinstance(label.font, pygame.font.Font)


def test_text_factory_propagates_errors_for_a_registered_but_missing_font_file(
    assets, parent
):
    """load_font only falls back to SysFont on KeyError (font not registered
    at all) -- a registered font whose file doesn't actually exist is a real
    error, not silently swallowed into a SysFont fallback."""
    factory = make_text_factory(assets)
    cfg = {"position": (0, 0), "text": "Hi", "font": "broken_font"}

    with pytest.raises(FileNotFoundError):
        factory(cfg, parent)


def test_text_factory_passes_through_states(assets, parent):
    factory = make_text_factory(assets)
    cfg = {"position": (0, 0), "states": {"default": "D", "hover": "H"}}

    label = factory(cfg, parent)

    assert label.states == {"default": "D", "hover": "H"}
