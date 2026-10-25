"""Unit tests for gameplay.spatial_grid.SpatialGrid.

The grid is a correctness-critical optimization: a wrong query means mobs ignore
neighbours they should avoid, or collide against walls they shouldn't (or miss
ones they should). These pin the query semantics.
"""

from __future__ import annotations

import pygame

from pygamine.util.spatial_grid import SpatialGrid


class _Obj:
    def __init__(self, center):
        self.rect = pygame.Rect(0, 0, 10, 10)
        self.rect.center = center


def test_query_radius_returns_near_excludes_far():
    near_a = _Obj((100, 100))
    near_b = _Obj((110, 110))  # adjacent cell
    far = _Obj((1000, 1000))
    grid = SpatialGrid.of([near_a, near_b, far], cell_size=50)

    found = set(grid.query_radius((100, 100), 50))

    assert near_a in found
    assert near_b in found
    assert far not in found


def test_query_rect_returns_overlapping_cells():
    inside = _Obj((100, 100))
    far = _Obj((1000, 1000))
    grid = SpatialGrid.of([inside, far], cell_size=50)

    found = set(grid.query_rect(pygame.Rect(80, 80, 40, 40)))

    assert inside in found
    assert far not in found


def test_query_on_empty_cell_yields_nothing():
    grid = SpatialGrid.of([_Obj((100, 100))], cell_size=50)
    assert list(grid.query_radius((5000, 5000), 50)) == []


def test_static_insert_finds_wall_larger_than_a_cell():
    """A wall bigger than one cell must be found by queries on every cell it
    overlaps, not just the one holding its centre (else mobs phase through)."""
    wall = _Obj((120, 120))
    wall.rect = pygame.Rect(60, 60, 120, 120)  # spans several 50px cells
    grid = SpatialGrid.of_static([wall], cell_size=50)

    # Query a corner cell the wall overlaps but whose centre is far from it.
    found = set(grid.query_rect(pygame.Rect(60, 60, 10, 10)))

    assert wall in found


def test_candidate_set_is_a_superset_not_exact():
    """The grid returns cell-level candidates; precise distance is the caller's job.

    Two objects in the same cell are both returned even if one is just outside the
    radius — callers (e.g. Mob.avoid_mobs) still do the squared-distance check.
    """
    a = _Obj((10, 10))
    b = _Obj((45, 45))  # same 50px cell as a, but ~49px away
    grid = SpatialGrid.of([a, b], cell_size=50)

    assert b in set(grid.query_radius((10, 10), 5))  # tiny radius, same cell
