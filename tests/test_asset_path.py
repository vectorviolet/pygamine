"""Unit tests for AssetPath and its ImagePath/FontPath/SoundPath subclasses:
the path-construction logic AssetManager builds every asset reference from.
"""

from __future__ import annotations

import os

from pygamine.assets.asset_path import (
    AssetPath,
    FontPath,
    ImagePath,
    SequencePath,
    SoundPath,
)


def test_full_path_without_folder():
    path = AssetPath(name="logo", base="assets/images")
    assert path.full_path.replace(os.sep, "/").endswith("assets/images/logo.png")


def test_full_path_with_folder():
    path = AssetPath(name="play", folder="buttons", base="assets/images")
    assert path.full_path.replace(os.sep, "/").endswith(
        "assets/images/buttons/play.png"
    )


def test_full_path_is_absolute():
    path = AssetPath(name="logo", base="assets/images")
    assert os.path.isabs(path.full_path)


def test_leading_dot_in_extension_is_stripped():
    path = AssetPath(name="logo", extension=".png", base="assets/images")
    assert path.full_path.endswith("logo.png")
    assert path.extension == "png"


def test_str_and_fspath_both_return_full_path():
    path = AssetPath(name="logo", base="assets/images")
    assert str(path) == path.full_path
    assert os.fspath(path) == path.full_path


# ── subclass defaults ───────────────────────────────────────────────────────


def test_image_path_defaults():
    path = ImagePath(name="logo")
    assert path.extension == "png"
    assert path.full_path.replace(os.sep, "/").endswith("assets/images/logo.png")


def test_font_path_defaults():
    path = FontPath(name="Kenney Future")
    assert path.extension == "ttf"
    assert path.full_path.replace(os.sep, "/").endswith(
        "assets/fonts/Kenney Future.ttf"
    )


def test_sound_path_defaults():
    path = SoundPath(name="click")
    assert path.extension == "ogg"
    assert path.full_path.replace(os.sep, "/").endswith("assets/sounds/click.ogg")


def test_subclass_extension_override():
    path = SoundPath(name="music", extension="mp3")
    assert path.full_path.endswith("music.mp3")


# ── SequencePath ────────────────────────────────────────────────────────────


def test_sequence_path_points_at_the_folder_without_an_extension():
    path = SequencePath(name="intro", folder="branding")
    assert path.full_path.replace(os.sep, "/").endswith("assets/images/branding/intro")
    assert os.path.isabs(path.full_path)
    assert path.extension == "jpg"


def test_sequence_frame_paths_are_its_frames_in_name_order(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    folder = tmp_path / "assets" / "images" / "intro"
    folder.mkdir(parents=True)
    for name in ("0002.png", "0001.png", "0010.png", "meta.yaml", "cover.jpg"):
        (folder / name).write_text("")

    frames = SequencePath(name="intro", extension="png").frame_paths()

    assert [f.name for f in frames] == ["0001.png", "0002.png", "0010.png"]


def test_sequence_frame_paths_of_a_missing_folder_is_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert SequencePath(name="nope").frame_paths() == []
