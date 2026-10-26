"""Unit tests for PanelLoaderExt: object_templates (extends:) and layout
groups (auto-positioned children), on top of PanelLoader's base loading.
"""

from __future__ import annotations

from pathlib import Path

import pygame
import pytest

from pygamine.assets.asset_manager import AssetManager
from pygamine.ecs.components.transform import Transform
from pygamine.panels.panel_loader_ext import PanelLoaderExt
from pygamine.panels.panel_manager import PanelManager


class _Built:
    def __init__(self, obj_def, parent):
        self.obj_def = obj_def
        self.parent = parent
        size = obj_def.get("size")
        w, h = size if isinstance(size, list) and len(size) == 2 else (10, 10)
        self.rect = pygame.Rect(0, 0, int(w), int(h))


def _factory(obj_def, parent) -> _Built:
    return _Built(obj_def, parent)


@pytest.fixture
def window_transform() -> Transform:
    return Transform(position=(0, 0), size=(800, 600))


@pytest.fixture
def loader(window_transform) -> PanelLoaderExt:
    ld = PanelLoaderExt(PanelManager(), window_transform, AssetManager())
    ld.register("object", _factory, default=True)
    return ld


def _write(tmp_path, text: str) -> Path:
    path = tmp_path / "panels.yaml"
    path.write_text(text)
    return path


# ── object_templates (extends:) ────────────────────────────────────────────


def test_extends_merges_template_into_object(loader, tmp_path):
    path = _write(
        tmp_path,
        "object_templates:\n"
        "  menu_btn:\n"
        "    size: [960, 96]\n"
        "    nine_slice: 8\n"
        "panels:\n"
        "  menu:\n"
        "    objects:\n"
        "      play:\n"
        "        extends: menu_btn\n"
        "        position: [0, 300]\n",
    )
    loader.load(path)
    obj_def = loader.pm["menu"]["play"].obj_def
    assert obj_def["size"] == [960, 96]
    assert obj_def["nine_slice"] == 8
    assert obj_def["position"] == [0, 300]
    assert "extends" not in obj_def


def test_extends_own_keys_win_over_template(loader, tmp_path):
    path = _write(
        tmp_path,
        "object_templates:\n"
        "  menu_btn:\n"
        "    size: [960, 96]\n"
        "panels:\n"
        "  menu:\n"
        "    objects:\n"
        "      play:\n"
        "        extends: menu_btn\n"
        "        size: [100, 100]\n",
    )
    loader.load(path)
    assert loader.pm["menu"]["play"].obj_def["size"] == [100, 100]


def test_extends_unknown_template_raises_keyerror(loader, tmp_path):
    path = _write(
        tmp_path,
        "object_templates:\n"
        "  menu_btn: {size: [10, 10]}\n"
        "panels:\n"
        "  menu:\n"
        "    objects:\n"
        "      play: {extends: nonexistent}\n",
    )
    with pytest.raises(KeyError):
        loader.load(path)


def test_extends_applies_inside_groups_too(loader, tmp_path):
    path = _write(
        tmp_path,
        "object_templates:\n"
        "  menu_btn: {size: [10, 10]}\n"
        "groups:\n"
        "  shared:\n"
        "    back: {extends: menu_btn}\n"
        "panels:\n"
        "  menu:\n"
        "    extends: [shared]\n"
        "    objects: {}\n",
    )
    loader.load(path)
    assert loader.pm["menu"]["back"].obj_def["size"] == [10, 10]


def test_no_object_templates_section_is_fine(loader, tmp_path):
    """A YAML with no object_templates key at all must not crash -- most
    panel files won't use template inheritance."""
    path = _write(tmp_path, "panels:\n  menu:\n    objects:\n      play: {}\n")
    loader.load(path)
    assert "play" in loader.pm["menu"]


# ── layout groups ───────────────────────────────────────────────────────────


def test_vertical_layout_spaces_children_along_y(loader, tmp_path):
    path = _write(
        tmp_path,
        "panels:\n"
        "  menu:\n"
        "    objects:\n"
        "      buttons:\n"
        "        layout: {direction: vertical, start: [50, 100], spacing: 20}\n"
        "        objects:\n"
        "          play: {}\n"
        "          settings: {}\n"
        "          exit: {}\n",
    )
    loader.load(path)
    assert loader.pm["menu"]["play"].obj_def["position"] == [50, 100]
    assert loader.pm["menu"]["settings"].obj_def["position"] == [50, 120]
    assert loader.pm["menu"]["exit"].obj_def["position"] == [50, 140]


def test_horizontal_layout_spaces_children_along_x(loader, tmp_path):
    path = _write(
        tmp_path,
        "panels:\n"
        "  menu:\n"
        "    objects:\n"
        "      toolbar:\n"
        "        layout: {direction: horizontal, start: [0, 10], spacing: 30}\n"
        "        objects:\n"
        "          a: {}\n"
        "          b: {}\n",
    )
    loader.load(path)
    assert loader.pm["menu"]["a"].obj_def["position"] == [0, 10]
    assert loader.pm["menu"]["b"].obj_def["position"] == [30, 10]


def test_layout_group_never_becomes_an_object_itself(loader, tmp_path):
    """The layout group container ('buttons') is replaced by its expanded
    children -- it must not also get loaded as its own object."""
    path = _write(
        tmp_path,
        "panels:\n"
        "  menu:\n"
        "    objects:\n"
        "      buttons:\n"
        "        layout: {direction: vertical, start: [0, 0]}\n"
        "        objects:\n"
        "          play: {}\n",
    )
    loader.load(path)
    assert "buttons" not in loader.pm["menu"]
    assert "play" in loader.pm["menu"]


def test_layout_group_parent_propagates_to_children(loader, tmp_path):
    path = _write(
        tmp_path,
        "panels:\n"
        "  menu:\n"
        "    objects:\n"
        "      panel: {}\n"
        "      buttons:\n"
        "        layout: {direction: vertical, start: [0, 0]}\n"
        "        parent: panel\n"
        "        objects:\n"
        "          play: {}\n",
    )
    loader.load(path)
    assert loader.pm["menu"]["play"].parent is loader.pm["menu"]["panel"].rect


def test_layout_invalid_direction_raises(loader, tmp_path):
    path = _write(
        tmp_path,
        "panels:\n"
        "  menu:\n"
        "    objects:\n"
        "      buttons:\n"
        "        layout: {direction: diagonal, start: [0, 0]}\n"
        "        objects: {play: {}}\n",
    )
    with pytest.raises(ValueError):
        loader.load(path)


def test_layout_missing_start_raises(loader, tmp_path):
    path = _write(
        tmp_path,
        "panels:\n"
        "  menu:\n"
        "    objects:\n"
        "      buttons:\n"
        "        layout: {direction: vertical}\n"
        "        objects: {play: {}}\n",
    )
    with pytest.raises(ValueError):
        loader.load(path)


def test_layout_non_numeric_main_axis_start_raises(loader, tmp_path):
    path = _write(
        tmp_path,
        "panels:\n"
        "  menu:\n"
        "    objects:\n"
        "      buttons:\n"
        "        layout: {direction: vertical, start: [0, CENTER]}\n"
        "        objects: {play: {}}\n",
    )
    with pytest.raises(ValueError):
        loader.load(path)


def test_nested_layout_group_raises(loader, tmp_path):
    path = _write(
        tmp_path,
        "panels:\n"
        "  menu:\n"
        "    objects:\n"
        "      outer:\n"
        "        layout: {direction: vertical, start: [0, 0]}\n"
        "        objects:\n"
        "          inner:\n"
        "            layout: {direction: horizontal, start: [0, 0]}\n"
        "            objects: {play: {}}\n",
    )
    with pytest.raises(ValueError):
        loader.load(path)


def test_layout_duplicate_child_name_across_groups_raises(loader, tmp_path):
    path = _write(
        tmp_path,
        "panels:\n"
        "  menu:\n"
        "    objects:\n"
        "      group_a:\n"
        "        layout: {direction: vertical, start: [0, 0]}\n"
        "        objects: {play: {}}\n"
        "      group_b:\n"
        "        layout: {direction: vertical, start: [0, 0]}\n"
        "        objects: {play: {}}\n",
    )
    with pytest.raises(KeyError):
        loader.load(path)


# ── layout + templates combined (realistic usage) ──────────────────────────


def test_layout_children_can_also_extend_templates(loader, tmp_path):
    path = _write(
        tmp_path,
        "object_templates:\n"
        "  menu_btn: {size: [200, 40]}\n"
        "panels:\n"
        "  menu:\n"
        "    objects:\n"
        "      buttons:\n"
        "        layout: {direction: vertical, start: [10, 10], spacing: 50}\n"
        "        objects:\n"
        "          play: {extends: menu_btn}\n"
        "          exit: {extends: menu_btn}\n",
    )
    loader.load(path)
    play = loader.pm["menu"]["play"].obj_def
    assert play["size"] == [200, 40]
    assert play["position"] == [10, 10]
    assert loader.pm["menu"]["exit"].obj_def["position"] == [10, 60]
