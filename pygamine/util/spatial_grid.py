"""Uniform spatial hash grid for fast neighbour / overlap queries.

Buckets objects (anything exposing a `.rect`) into fixed-size cells so a query
only inspects nearby cells instead of every object. This turns O(N^2) all-pairs
scans (e.g. mob-vs-mob avoidance, entity-vs-walls collision) into roughly O(N):
each lookup touches only the handful of objects in adjacent cells.

Rebuild it each frame for moving objects; build it once for static ones.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any


class SpatialGrid:
    def __init__(self, cell_size: int) -> None:
        self.cell_size = max(1, int(cell_size))
        self._cells: dict[tuple[int, int], list] = {}

    def _key(self, x, y) -> tuple[int, int]:
        return (int(x) // self.cell_size, int(y) // self.cell_size)

    def insert(self, obj) -> None:
        """Bucket a small/point-like object by its centre (one cell)."""
        cx, cy = obj.rect.center
        self._cells.setdefault(self._key(cx, cy), []).append(obj)

    def insert_overlapping(self, obj) -> None:
        """Bucket an object into every cell its rect overlaps. For objects that
        may be larger than a cell — centre-only bucketing would let queries on the
        other cells it covers miss it."""
        cs = self.cell_size
        rect = obj.rect
        for gx in range(rect.left // cs, rect.right // cs + 1):
            for gy in range(rect.top // cs, rect.bottom // cs + 1):
                self._cells.setdefault((gx, gy), []).append(obj)

    def query_radius(self, center, radius) -> Iterator[Any]:
        """Yield objects in cells overlapping the bbox of the query circle.

        A superset of the true neighbours — callers still do the precise distance
        check, but only against this small candidate set.
        """
        cx, cy = int(center[0]), int(center[1])
        cs = self.cell_size
        cells = self._cells
        for gx in range((cx - radius) // cs, (cx + radius) // cs + 1):
            for gy in range((cy - radius) // cs, (cy + radius) // cs + 1):
                bucket = cells.get((gx, gy))
                if bucket:
                    yield from bucket

    def query_rect(self, rect) -> Iterator[Any]:
        """Yield objects in cells overlapping `rect` (candidate set for collision)."""
        cs = self.cell_size
        cells = self._cells
        for gx in range(rect.left // cs, rect.right // cs + 1):
            for gy in range(rect.top // cs, rect.bottom // cs + 1):
                bucket = cells.get((gx, gy))
                if bucket:
                    yield from bucket

    @classmethod
    def of(cls, objects, cell_size: int) -> "SpatialGrid":
        """Build from moving point-like objects — centre bucketing."""
        grid = cls(cell_size)
        for obj in objects:
            grid.insert(obj)
        return grid

    @classmethod
    def of_static(cls, objects, cell_size: int) -> "SpatialGrid":
        """Build from static, possibly large objects — overlap bucketing."""
        grid = cls(cell_size)
        for obj in objects:
            grid.insert_overlapping(obj)
        return grid
