"""Unit tests for TiledMap: loads a Tiled .tmx and exposes tile dimensions,
object-group iteration, an offscreen pre-render, and a camera-aware draw.

Builds a real, minimal 2x2 .tmx + tileset.png under tmp_path (pytmx
resolves the tileset image path relative to the .tmx file's own
directory) rather than mocking pytmx away -- this is thin, real
integration with an external library, which is exactly where mocking
would hide the most likely kind of bug (a pytmx API assumption that's
wrong).
"""

from __future__ import annotations

import pygame
import pytest

from pygamine.app.camera import Camera
from pygamine.assets.tilemap import TiledMap

RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)
YELLOW = (255, 255, 0, 255)

TMX_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<map version="1.10" orientation="orthogonal" renderorder="right-down" width="2" height="2" tilewidth="{tw}" tileheight="{th}" infinite="0" nextlayerid="3" nextobjectid="2">
 <tileset firstgid="1" name="tiles" tilewidth="{tw}" tileheight="{th}" tilecount="4" columns="2">
  <image source="tileset.png" width="{iw}" height="{ih}"/>
 </tileset>
 <layer id="1" name="Tile Layer 1" width="2" height="2">
  <data encoding="csv">
1,2,
3,4
</data>
 </layer>
 <objectgroup id="2" name="Spawns">
  <object id="1" name="spawn1" x="8" y="8" width="16" height="16"/>
 </objectgroup>
</map>
"""


@pytest.fixture
def tmx_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pygame.display.set_mode((1, 1))  # convert_alpha() needs a display mode set

    tileset = pygame.Surface((32, 32), pygame.SRCALPHA)
    for i, color in enumerate([RED, GREEN, BLUE, YELLOW]):
        tile = pygame.Surface((16, 16), pygame.SRCALPHA)
        tile.fill(color)
        tileset.blit(tile, ((i % 2) * 16, (i // 2) * 16))
    pygame.image.save(tileset, str(tmp_path / "tileset.png"))

    path = tmp_path / "map.tmx"
    path.write_text(TMX_TEMPLATE.format(tw=16, th=16, iw=32, ih=32))
    return path


@pytest.fixture
def non_square_tmx_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pygame.display.set_mode((1, 1))

    tileset = pygame.Surface((16, 8), pygame.SRCALPHA)
    tileset.fill(RED)
    pygame.image.save(tileset, str(tmp_path / "tileset.png"))

    path = tmp_path / "map.tmx"
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<map version="1.10" orientation="orthogonal" renderorder="right-down" '
        'width="1" height="1" tilewidth="16" tileheight="8" infinite="0" '
        'nextlayerid="2" nextobjectid="1">\n'
        ' <tileset firstgid="1" name="tiles" tilewidth="16" tileheight="8" '
        'tilecount="1" columns="1">\n'
        '  <image source="tileset.png" width="16" height="8"/>\n'
        " </tileset>\n"
        ' <layer id="1" name="L" width="1" height="1">\n'
        '  <data encoding="csv">1</data>\n'
        " </layer>\n"
        "</map>\n"
    )
    return path


# ── construction ────────────────────────────────────────────────────────


def test_construction_reads_tile_dimensions(tmx_path):
    tmap = TiledMap(tmx_path)
    assert tmap.tile_size == 16
    assert tmap.cols == 2
    assert tmap.rows == 2


def test_construction_rejects_non_square_tiles(non_square_tmx_path):
    with pytest.raises(ValueError):
        TiledMap(non_square_tmx_path)


# ── map_width / map_height ──────────────────────────────────────────────


def test_map_dimensions_are_cols_rows_times_tile_size(tmx_path):
    tmap = TiledMap(tmx_path)
    assert tmap.map_width == 32
    assert tmap.map_height == 32


# ── iter_objects ────────────────────────────────────────────────────────


def test_iter_objects_yields_objects_from_the_matching_group(tmx_path):
    tmap = TiledMap(tmx_path)
    objects = list(tmap.iter_objects("Spawns"))
    assert len(objects) == 1
    assert objects[0].name == "spawn1"
    assert objects[0].x == 8
    assert objects[0].y == 8


def test_iter_objects_yields_nothing_for_an_unknown_group(tmx_path):
    tmap = TiledMap(tmx_path)
    assert list(tmap.iter_objects("NoSuchGroup")) == []


# ── pre_render ──────────────────────────────────────────────────────────


def test_pre_render_size_matches_the_map_dimensions(tmx_path):
    tmap = TiledMap(tmx_path)
    surface = tmap.pre_render()
    assert surface.get_size() == (32, 32)


def test_pre_render_places_each_tile_at_its_grid_position(tmx_path):
    tmap = TiledMap(tmx_path)
    surface = tmap.pre_render()

    assert surface.get_at((0, 0)) == RED  # gid 1, col 0 row 0
    assert surface.get_at((16, 0)) == GREEN  # gid 2, col 1 row 0
    assert surface.get_at((0, 16)) == BLUE  # gid 3, col 0 row 1
    assert surface.get_at((16, 16)) == YELLOW  # gid 4, col 1 row 1


def test_pre_render_default_is_opaque_not_per_pixel_alpha(tmx_path):
    tmap = TiledMap(tmx_path)
    surface = tmap.pre_render()
    assert not (surface.get_flags() & pygame.SRCALPHA)


def test_pre_render_alpha_true_gives_a_per_pixel_alpha_surface(tmx_path):
    tmap = TiledMap(tmx_path)
    surface = tmap.pre_render(alpha=True)
    assert surface.get_flags() & pygame.SRCALPHA


# ── draw (camera-aware, cached render) ──────────────────────────────────


def test_draw_blits_the_map_at_the_cameras_world_origin(tmx_path):
    tmap = TiledMap(tmx_path)
    camera = Camera(pygame.Rect(0, 0, 32, 32), map_width=32, map_height=32)
    dest = pygame.Surface((32, 32))

    tmap.draw(dest, camera)

    assert dest.get_at((0, 0)) == RED
    assert dest.get_at((16, 16)) == YELLOW


def test_draw_caches_the_native_prerender_across_calls(tmx_path):
    tmap = TiledMap(tmx_path)
    camera = Camera(pygame.Rect(0, 0, 32, 32), map_width=32, map_height=32)
    dest = pygame.Surface((32, 32))

    tmap.draw(dest, camera)
    native_first = tmap._native_surface
    tmap.draw(dest, camera)

    assert tmap._native_surface is native_first  # not re-rendered


def test_draw_rebuilds_the_scaled_surface_when_camera_scale_changes(tmx_path):
    tmap = TiledMap(tmx_path)
    camera = Camera(pygame.Rect(0, 0, 32, 32), map_width=32, map_height=32)
    dest = pygame.Surface((64, 64))

    tmap.draw(dest, camera)
    assert tmap._scaled_factor == 1.0

    camera.scale = 2.0
    tmap.draw(dest, camera)

    assert tmap._scaled_factor == 2.0
    assert tmap._scaled_surface.get_size() == (64, 64)


def test_draw_offsets_by_the_camera_when_scrolled(tmx_path):
    tmap = TiledMap(tmx_path)
    camera = Camera(pygame.Rect(0, 0, 32, 32), map_width=32, map_height=32)
    camera._offset.update(-16, 0)  # scrolled right by one tile
    dest = pygame.Surface((32, 32))
    dest.fill((9, 9, 9))

    tmap.draw(dest, camera)

    # what was at world (16, 0) [green] is now at screen (0, 0)
    assert dest.get_at((0, 0)) == GREEN
