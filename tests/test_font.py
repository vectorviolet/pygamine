"""Unit tests for load_font: looks up a font in the asset manifest first,
falling back to a system font (SysFont) when it isn't registered.

Dedicated, direct tests for this module -- it already had indirect coverage
via panel_factory's make_text_factory tests, but those only exercise it
through TextObject construction.
"""
from __future__ import annotations

import os

import pygame
import pytest

from pygamine.assets.asset_manager import AssetManager
from pygamine.assets.font import load_font


@pytest.fixture
def assets(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    fonts_dir = tmp_path / "assets" / "fonts"
    fonts_dir.mkdir(parents=True)
    real_font_src = os.path.join(os.path.dirname(pygame.__file__), "freesansbold.ttf")
    (fonts_dir / "registered_font.ttf").write_bytes(open(real_font_src, "rb").read())

    manifest = tmp_path / "assets.yaml"
    manifest.write_text(
        "fonts:\n"
        "  registered_font: {name: registered_font}\n"
        "  broken_font: {name: does_not_exist}\n"
    )
    mgr = AssetManager()
    mgr.load_manifest(manifest)
    return mgr


# ── registered vs. fallback ──────────────────────────────────────────────


def test_falls_back_to_sysfont_when_the_font_is_not_registered(assets):
    font = load_font({"font": "Arial"}, assets)
    assert isinstance(font, pygame.font.Font)


def test_uses_the_real_registered_font_file(assets):
    font = load_font({"font": "registered_font"}, assets)
    assert isinstance(font, pygame.font.Font)


def test_registered_but_missing_file_raises_instead_of_falling_back(assets):
    """load_font's except clause only catches KeyError (unregistered name)
    -- a registered font whose file doesn't actually exist is a real file
    error, not silently swallowed into a SysFont fallback."""
    with pytest.raises(FileNotFoundError):
        load_font({"font": "broken_font"}, assets)


# ── defaults ────────────────────────────────────────────────────────────


def test_defaults_to_arial_size_32_when_cfg_is_empty(assets):
    font = load_font({}, assets)
    assert font.size("x")[1] == pygame.font.SysFont("Arial", 32).size("x")[1]


def test_uses_the_given_size(assets):
    small = load_font({"font": "Arial", "font_size": 10}, assets)
    large = load_font({"font": "Arial", "font_size": 60}, assets)
    assert small.size("x")[1] < large.size("x")[1]


def test_bold_and_italic_default_to_false(assets):
    font = load_font({"font": "Arial"}, assets)
    assert font.get_bold() is False
    assert font.get_italic() is False


def test_bold_and_italic_passthrough_to_sysfont(assets):
    font = load_font({"font": "Arial", "bold": True, "italic": True}, assets)
    assert font.get_bold() is True
    assert font.get_italic() is True


def test_bold_and_italic_also_apply_to_a_registered_font_file(assets):
    """Previously dropped silently for manifest fonts -- only the SysFont
    fallback honoured them."""
    font = load_font({"font": "registered_font", "bold": True, "italic": True}, assets)
    assert font.get_bold() is True
    assert font.get_italic() is True


def test_registered_font_file_is_plain_by_default(assets):
    font = load_font({"font": "registered_font"}, assets)
    assert font.get_bold() is False
    assert font.get_italic() is False


# ── custom key names ────────────────────────────────────────────────────


def test_custom_font_key_name(assets):
    font = load_font({"typeface": "registered_font"}, assets, font_key="typeface")
    assert isinstance(font, pygame.font.Font)


def test_custom_size_key_name(assets):
    small = load_font({"font": "Arial", "text_size": 10}, assets, size_key="text_size")
    large = load_font({"font": "Arial", "text_size": 60}, assets, size_key="text_size")
    assert small.size("x")[1] < large.size("x")[1]


def test_custom_bold_and_italic_key_names(assets):
    font = load_font(
        {"font": "Arial", "is_bold": True, "is_italic": True},
        assets, bold_key="is_bold", italic_key="is_italic",
    )
    assert font.get_bold() is True
    assert font.get_italic() is True
