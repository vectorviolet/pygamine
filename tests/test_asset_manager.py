"""Unit tests for AssetManager: the manifest-driven asset registry every
consuming project loads config/assets.yaml through.
"""
from __future__ import annotations

import pygame
import pytest

from pygamine.assets.asset_manager import AssetManager


def _write_manifest(tmp_path, text: str):
    path = tmp_path / "assets.yaml"
    path.write_text(text)
    return path


# ── load_manifest ────────────────────────────────────────────────────────


def test_load_manifest_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        AssetManager().load_manifest("does_not_exist.yaml")


def test_load_manifest_empty_file_is_fine(tmp_path):
    path = _write_manifest(tmp_path, "")
    mgr = AssetManager()
    mgr.load_manifest(path)  # must not raise
    assert mgr.validate() == []


def test_load_manifest_loads_images_fonts_sounds(tmp_path):
    path = _write_manifest(
        tmp_path,
        "images:\n"
        "  logo: {folder: branding, name: logo}\n"
        "fonts:\n"
        "  title: {name: Kenney Future}\n"
        "sounds:\n"
        "  click: {name: click-a}\n",
    )
    mgr = AssetManager()
    mgr.load_manifest(path)

    assert mgr.image_path("logo").name == "logo"
    assert mgr.image_path("logo").folder == "branding"
    assert mgr.font_path("title").name == "Kenney Future"
    assert mgr.sound_path("click").name == "click-a"


def test_load_manifest_applies_default_extensions_when_omitted(tmp_path):
    path = _write_manifest(
        tmp_path,
        "images:\n  logo: {name: logo}\n"
        "fonts:\n  title: {name: title}\n"
        "sounds:\n  click: {name: click}\n",
    )
    mgr = AssetManager()
    mgr.load_manifest(path)

    assert mgr.image_path("logo").extension == "png"
    assert mgr.font_path("title").extension == "ttf"
    assert mgr.sound_path("click").extension == "ogg"


def test_load_manifest_applies_custom_extension(tmp_path):
    path = _write_manifest(
        tmp_path, "sounds:\n  bg_music: {name: bg, extension: mp3}\n"
    )
    mgr = AssetManager()
    mgr.load_manifest(path)
    assert mgr.sound_path("bg_music").extension == "mp3"


def test_load_manifest_defaults_folder_to_empty_string(tmp_path):
    path = _write_manifest(tmp_path, "images:\n  logo: {name: logo}\n")
    mgr = AssetManager()
    mgr.load_manifest(path)
    assert mgr.image_path("logo").folder == ""


def test_load_manifest_missing_section_leaves_that_category_empty(tmp_path):
    """A manifest with only `images:` (no fonts/sounds) must not crash --
    most manifests don't declare all three categories."""
    path = _write_manifest(tmp_path, "images:\n  logo: {name: logo}\n")
    mgr = AssetManager()
    mgr.load_manifest(path)

    mgr.image_path("logo")  # doesn't raise
    with pytest.raises(KeyError):
        mgr.font_path("anything")


def test_load_manifest_called_twice_accumulates_rather_than_replaces(tmp_path):
    """Loading a second manifest adds to the registry instead of resetting
    it -- a project could plausibly load a base manifest plus an override."""
    first = _write_manifest(tmp_path, "images:\n  logo: {name: logo}\n")
    second = tmp_path / "assets2.yaml"
    second.write_text("images:\n  icon: {name: icon}\n")

    mgr = AssetManager()
    mgr.load_manifest(first)
    mgr.load_manifest(second)

    assert mgr.image_path("logo").name == "logo"
    assert mgr.image_path("icon").name == "icon"


# ── image_path / font_path / sound_path ────────────────────────────────────


def test_image_path_unknown_key_raises_keyerror(tmp_path):
    mgr = AssetManager()
    mgr.load_manifest(_write_manifest(tmp_path, "images: {}\n"))
    with pytest.raises(KeyError):
        mgr.image_path("does_not_exist")


def test_font_path_unknown_key_raises_keyerror():
    with pytest.raises(KeyError):
        AssetManager().font_path("does_not_exist")


def test_sound_path_unknown_key_raises_keyerror():
    with pytest.raises(KeyError):
        AssetManager().sound_path("does_not_exist")


# ── validate ────────────────────────────────────────────────────────────


def test_validate_returns_empty_when_all_files_exist(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "assets" / "images").mkdir(parents=True)
    (tmp_path / "assets" / "images" / "logo.png").write_bytes(b"")

    mgr = AssetManager()
    mgr.load_manifest(_write_manifest(tmp_path, "images:\n  logo: {name: logo}\n"))

    assert mgr.validate() == []


def test_validate_reports_missing_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mgr = AssetManager()
    mgr.load_manifest(_write_manifest(tmp_path, "images:\n  logo: {name: logo}\n"))

    missing = mgr.validate()
    assert len(missing) == 1
    assert "logo" in missing[0]


def test_validate_merges_categories_so_a_duplicate_key_across_categories_collides(
    tmp_path, monkeypatch
):
    """validate() builds one dict via {**images, **fonts, **sounds} -- if the
    same key is used in two categories, one silently shadows the other in
    this merged view. Pinning this as a known quirk, not a desired feature:
    don't reuse a manifest key name across images/fonts/sounds."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "assets" / "sounds").mkdir(parents=True)
    (tmp_path / "assets" / "sounds" / "shared.ogg").write_bytes(b"")

    mgr = AssetManager()
    mgr.load_manifest(
        _write_manifest(
            tmp_path,
            "images:\n  shared: {name: shared}\n"
            "sounds:\n  shared: {name: shared}\n",
        )
    )

    # The image (missing on disk) is shadowed by the sound (present on disk)
    # in validate()'s merged dict, so nothing is reported missing even though
    # assets/images/shared.png does not exist.
    assert mgr.validate() == []


# ── get_image ───────────────────────────────────────────────────────────


def test_get_image_loads_and_caches_same_surface_instance(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pygame.display.set_mode((1, 1))  # convert_alpha() needs a display mode set

    (tmp_path / "assets" / "images").mkdir(parents=True)
    surf = pygame.Surface((4, 4), pygame.SRCALPHA)
    pygame.image.save(surf, str(tmp_path / "assets" / "images" / "logo.png"))

    mgr = AssetManager()
    mgr.load_manifest(_write_manifest(tmp_path, "images:\n  logo: {name: logo}\n"))

    first = mgr.get_image("logo")
    second = mgr.get_image("logo")
    assert first is second


def test_get_image_unknown_key_raises_keyerror():
    with pytest.raises(KeyError):
        AssetManager().get_image("does_not_exist")


# ── sequences ────────────────────────────────────────────────────────────


def test_sequences_load_with_jpg_default_and_resolve_by_key(tmp_path):
    path = _write_manifest(tmp_path, "sequences:\n  intro: {folder: branding, name: intro}\n")
    mgr = AssetManager()
    mgr.load_manifest(path)

    sequence = mgr.sequence_path("intro")

    assert sequence.extension == "jpg"
    assert str(sequence).replace("\\", "/").endswith("assets/images/branding/intro")


def test_sequence_path_unknown_key_raises_keyerror():
    with pytest.raises(KeyError, match="sequence"):
        AssetManager().sequence_path("nope")


def test_validate_reports_a_sequence_folder_without_frames(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = _write_manifest(
        tmp_path,
        "sequences:\n"
        "  filled: {name: filled}\n"
        "  empty: {name: empty}\n"
        "  absent: {name: absent}\n",
    )
    (tmp_path / "assets" / "images" / "filled").mkdir(parents=True)
    (tmp_path / "assets" / "images" / "filled" / "0001.jpg").write_text("")
    (tmp_path / "assets" / "images" / "empty").mkdir(parents=True)
    mgr = AssetManager()
    mgr.load_manifest(path)

    missing = mgr.validate()

    assert len(missing) == 2
    assert any(m.startswith("empty") for m in missing)
    assert any(m.startswith("absent") for m in missing)
