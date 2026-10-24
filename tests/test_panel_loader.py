"""Unit tests for PanelLoader: YAML panel definitions -> objects in a
PanelManager.

Covers object/type/parent resolution (the load-time wiring every panel goes
through) and _scale_def in isolation (the UI-rescaling math used when a
game renders at a different resolution than its layout was authored for,
e.g. standoff's desktop-vs-mobile render size).
"""
from __future__ import annotations

import pygame
import pytest

from pygamine.assets.asset_manager import AssetManager
from pygamine.ecs.components.transform import Transform
from pygamine.panels.panel_loader import PanelLoader
from pygamine.panels.panel_manager import PanelManager


class _Built:
    """Minimal stand-in for whatever a real factory (GuiObject, TextObject,
    ...) would build: records what it was called with, and exposes a `.rect`
    so it can serve as another object's parent."""

    def __init__(self, obj_def, parent):
        self.obj_def = obj_def
        self.parent = parent
        size = obj_def.get("size")
        w, h = size if isinstance(size, list) and len(size) == 2 else (10, 10)
        self.rect = pygame.Rect(0, 0, int(w), int(h))


def _factory(obj_def, parent):
    return _Built(obj_def, parent)


@pytest.fixture
def window_transform():
    return Transform(position=(0, 0), size=(800, 600))


@pytest.fixture
def assets(tmp_path):
    manifest = tmp_path / "assets.yaml"
    manifest.write_text(
        "images:\n"
        "  btn_play: {folder: buttons, name: play}\n"
        "  btn_play_hover: {folder: buttons, name: play_hover}\n"
    )
    mgr = AssetManager()
    mgr.load_manifest(manifest)
    return mgr


@pytest.fixture
def loader(window_transform, assets):
    pm = PanelManager()
    ld = PanelLoader(pm, window_transform, assets)
    ld.register("object", _factory, default=True)
    return ld


def _write(tmp_path, text: str):
    path = tmp_path / "panels.yaml"
    path.write_text(text)
    return path


# ── load() / file handling ────────────────────────────────────────────────


def test_load_missing_file_raises(loader):
    with pytest.raises(FileNotFoundError):
        loader.load("does_not_exist.yaml")


# ── type resolution ────────────────────────────────────────────────────────


def test_add_object_uses_default_type_when_unspecified(loader, tmp_path):
    path = _write(tmp_path, "panels:\n  menu:\n    objects:\n      play: {}\n")
    loader.load(path)
    assert isinstance(loader.pm["menu"]["play"], _Built)


def test_add_object_raises_when_no_type_and_no_default(window_transform, assets, tmp_path):
    pm = PanelManager()
    ld = PanelLoader(pm, window_transform, assets)
    ld.register("object", _factory)  # no default=True
    path = _write(tmp_path, "panels:\n  menu:\n    objects:\n      play: {}\n")
    with pytest.raises(ValueError):
        ld.load(path)


def test_add_object_raises_for_unregistered_type(loader, tmp_path):
    path = _write(
        tmp_path,
        "panels:\n  menu:\n    objects:\n      play: {type: text}\n",
    )
    with pytest.raises(KeyError):
        loader.load(path)


# ── parent resolution ──────────────────────────────────────────────────────


def test_object_without_parent_gets_window_transform(loader, tmp_path, window_transform):
    path = _write(tmp_path, "panels:\n  menu:\n    objects:\n      play: {}\n")
    loader.load(path)
    assert loader.pm["menu"]["play"].parent is window_transform


def test_object_with_valid_parent_gets_parent_rect(loader, tmp_path):
    path = _write(
        tmp_path,
        "panels:\n"
        "  menu:\n"
        "    objects:\n"
        "      panel: {}\n"
        "      play: {parent: panel}\n",
    )
    loader.load(path)
    assert loader.pm["menu"]["play"].parent is loader.pm["menu"]["panel"].rect


def test_object_with_unknown_parent_name_raises_keyerror(loader, tmp_path):
    path = _write(
        tmp_path,
        "panels:\n  menu:\n    objects:\n      play: {parent: nonexistent}\n",
    )
    with pytest.raises(KeyError):
        loader.load(path)


def test_object_referencing_parent_declared_later_raises_keyerror(loader, tmp_path):
    """Parent objects must be declared before their children -- YAML dict order
    is load order, so a forward reference is a genuine authoring error."""
    path = _write(
        tmp_path,
        "panels:\n"
        "  menu:\n"
        "    objects:\n"
        "      play: {parent: panel}\n"
        "      panel: {}\n",
    )
    with pytest.raises(KeyError):
        loader.load(path)


def test_object_with_parent_in_different_tab_raises_keyerror(loader, tmp_path):
    path = _write(
        tmp_path,
        "panels:\n"
        "  menu:\n"
        "    objects:\n"
        "      panel: {}\n"
        "  other:\n"
        "    objects:\n"
        "      play: {parent: panel}\n",
    )
    with pytest.raises(KeyError):
        loader.load(path)


# ── groups / extends (panel-level) ─────────────────────────────────────────


def test_panel_extends_pulls_in_group_objects(loader, tmp_path):
    path = _write(
        tmp_path,
        "groups:\n"
        "  shared:\n"
        "    back_button: {}\n"
        "panels:\n"
        "  menu:\n"
        "    extends: [shared]\n"
        "    objects:\n"
        "      play: {}\n",
    )
    loader.load(path)
    assert "back_button" in loader.pm["menu"]
    assert "play" in loader.pm["menu"]


# ── asset resolution ────────────────────────────────────────────────────────


def test_asset_and_hover_keys_resolved_via_asset_manager(loader, tmp_path):
    path = _write(
        tmp_path,
        "panels:\n"
        "  menu:\n"
        "    objects:\n"
        "      play: {asset: btn_play, hover: btn_play_hover}\n",
    )
    loader.load(path)
    obj_def = loader.pm["menu"]["play"].obj_def
    assert obj_def["asset"].name == "play"
    assert obj_def["hover"].name == "play_hover"


def test_unknown_asset_key_raises_keyerror(loader, tmp_path):
    path = _write(
        tmp_path,
        "panels:\n  menu:\n    objects:\n      play: {asset: does_not_exist}\n",
    )
    with pytest.raises(KeyError):
        loader.load(path)


# ── _scale_def ───────────────────────────────────────────────────────────


def test_scale_def_noop_when_scale_is_1_and_same_canvas(loader):
    loader.scale = 1.0
    obj_def = {"position": [10, 20], "size": [100, 50]}
    loader._scale_def(obj_def, window_parented=False)
    assert obj_def == {"position": [10, 20], "size": [100, 50]}


def test_scale_def_scales_size_and_font_size(loader):
    loader.scale = 2.0
    obj_def = {"size": [100, 50], "font_size": 20, "text_size": 3}
    loader._scale_def(obj_def, window_parented=True)
    assert obj_def["size"] == [200, 100]
    assert obj_def["font_size"] == 40
    assert obj_def["text_size"] == 6


def test_scale_def_scales_speed_without_rounding(loader):
    loader.scale = 0.5
    obj_def = {"speed": 45}
    loader._scale_def(obj_def, window_parented=True)
    assert obj_def["speed"] == 22.5


def test_scale_def_font_size_never_rounds_to_zero(loader):
    loader.scale = 0.1
    obj_def = {"font_size": 2}
    loader._scale_def(obj_def, window_parented=True)
    assert obj_def["font_size"] == 1


def test_scale_def_scales_non_window_parented_position_directly(loader):
    loader.scale = 2.0
    obj_def = {"position": [10, 20]}
    loader._scale_def(obj_def, window_parented=False)
    assert obj_def["position"] == [20, 40]


def test_scale_def_preserves_non_numeric_position_component_non_window_parented(loader):
    loader.scale = 2.0
    obj_def = {"position": ["CENTER", 50]}
    loader._scale_def(obj_def, window_parented=False)
    assert obj_def["position"] == ["CENTER", 100]


def test_scale_def_remaps_window_parented_position_between_authored_and_actual_canvas():
    """The core mobile/desktop remap case: layout authored for one canvas size,
    rendered at another. A window-parented position is remapped from the
    authored centre to the actual centre, not just scaled in place."""
    window_transform = Transform(position=(0, 0), size=(1000, 500))
    ld = PanelLoader(PanelManager(), window_transform, AssetManager())
    ld.scale = 1.0
    ld.authored_size = (2000, 1000)

    obj_def = {"position": [1200, 700]}
    ld._scale_def(obj_def, window_parented=True)

    assert obj_def["position"] == [700, 450]


def test_scale_def_preserves_non_numeric_position_component_window_parented():
    window_transform = Transform(position=(0, 0), size=(1000, 500))
    ld = PanelLoader(PanelManager(), window_transform, AssetManager())
    ld.scale = 1.0
    ld.authored_size = (2000, 1000)

    obj_def = {"position": ["CENTER", 500]}
    ld._scale_def(obj_def, window_parented=True)

    assert obj_def["position"][0] == "CENTER"
    assert obj_def["position"][1] == 250


def test_scale_def_scales_a_non_top_left_anchor_directly_instead_of_centre_remapping():
    """A window-parented object anchored to a corner/edge (e.g. bottom-right)
    holds an inset offset, not an absolute authored-canvas coordinate --
    centre-remapping it (like the default top-left anchor) would push it off
    the edge it's meant to hug. This is the exact bug that let
    kenney_logo (anchor: bottom-right, position: [-25,-25]) render partly
    off-screen at a smaller-than-authored window size."""
    window_transform = Transform(position=(0, 0), size=(1000, 500))
    ld = PanelLoader(PanelManager(), window_transform, AssetManager())
    ld.scale = 0.5
    ld.authored_size = (2000, 1000)

    obj_def = {"position": [-25, -25], "anchor": "bottom-right"}
    ld._scale_def(obj_def, window_parented=True)

    assert obj_def["position"] == [-12, -12]  # round(-25 * 0.5) == -12 (banker's rounding) -- plain magnitude scale


def test_scale_def_still_centre_remaps_the_default_top_left_anchor():
    """Sanity check that the fix above doesn't regress the common case: no
    explicit `anchor` key (defaults to top-left) still uses the centre-remap."""
    window_transform = Transform(position=(0, 0), size=(1000, 500))
    ld = PanelLoader(PanelManager(), window_transform, AssetManager())
    ld.scale = 1.0
    ld.authored_size = (2000, 1000)

    obj_def = {"position": [1200, 700]}  # no "anchor" key at all
    ld._scale_def(obj_def, window_parented=True)

    assert obj_def["position"] == [700, 450]


def test_scale_def_keeps_a_window_sized_overlay_at_the_window_origin():
    """A full-screen overlay (size: WINDOW, position [0, 0]) must cover the
    actual window. Centre-remapping its position for a canvas with a
    different aspect ratio than the authored one (here 16:10 vs 16:9)
    pushed it 60px down, leaving an uncovered strip along the top."""
    window_transform = Transform(position=(0, 0), size=(1920, 1200))
    ld = PanelLoader(PanelManager(), window_transform, AssetManager())
    ld.scale = 1.0
    ld.authored_size = (1920, 1080)

    obj_def = {"position": [0, 0], "size": "WINDOW"}
    ld._scale_def(obj_def, window_parented=True)

    assert obj_def["position"] == [0, 0]
    assert obj_def["size"] == "WINDOW"
