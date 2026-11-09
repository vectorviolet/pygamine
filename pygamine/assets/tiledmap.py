"""Tiled .tmx base map for pygamine.

Loads a Tiled map via pytmx and exposes the parts every game needs regardless
of genre: tile dimensions, object-group iteration, an offscreen pre-render of
the visible tile layers, and a camera-aware draw. Games subclass this to add
their own parsing (enemy paths, buildable grids, entity spawning, ...).

Requires `pytmx`.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pygame
import pytmx
from pytmx.util_pygame import load_pygame


class TiledMap:
    """Loads a Tiled .tmx and exposes the surface + metadata games need."""

    def __init__(self, tmx_path: str | Path) -> None:
        self.tmx = load_pygame(str(tmx_path))
        if self.tmx.tilewidth != self.tmx.tileheight:
            raise ValueError("non-square tiles are not supported")

        self.tile_size: int = self.tmx.tilewidth
        self.cols: int = self.tmx.width
        self.rows: int = self.tmx.height

        self._native_surface: pygame.Surface | None = None
        self._scaled_surface: pygame.Surface | None = None
        self._scaled_factor: float = 1.0

    # ── dimensions ────────────────────────────────────────────────────────────

    @property
    def map_width(self) -> int:
        return self.cols * self.tile_size

    @property
    def map_height(self) -> int:
        return self.rows * self.tile_size

    # ── object access ─────────────────────────────────────────────────────────

    def iter_objects(self, group_name: str) -> Iterator[pytmx.TiledObject]:
        """Yield objects from every object group named `group_name`."""
        for layer in self.tmx.layers:
            if isinstance(layer, pytmx.TiledObjectGroup) and layer.name == group_name:
                yield from layer

    # ── rendering ─────────────────────────────────────────────────────────────

    def pre_render(self, alpha: bool = False) -> pygame.Surface:
        """Render the visible tile layers to an offscreen surface (no camera offset).

        alpha=False (default) yields an opaque surface; pass alpha=True for a
        per-pixel-alpha surface when the map should show through where untiled.
        """
        flags = pygame.SRCALPHA if alpha else 0
        surface = pygame.Surface((self.map_width, self.map_height), flags)
        ts = self.tile_size
        for layer in self.tmx.visible_layers:
            if not isinstance(layer, pytmx.TiledTileLayer):
                continue
            for x, y, image in layer.tiles():
                if image is not None:
                    surface.blit(image, (x * ts, y * ts))
        return surface

    def draw(self, surface: pygame.Surface, camera) -> None:
        """Blit the (camera-scale cached) map at the camera offset, clipped to its viewport."""
        if self._native_surface is None:
            self._native_surface = self.pre_render()
        if (
            self._scaled_surface is None
            or abs(self._scaled_factor - camera.scale) > 1e-6
        ):
            self._scaled_factor = camera.scale
            self._scaled_surface = (
                self._native_surface
                if abs(camera.scale - 1.0) < 1e-6
                else pygame.transform.scale_by(self._native_surface, camera.scale)
            )
        old_clip = surface.get_clip()
        surface.set_clip(camera.rect)
        surface.blit(self._scaled_surface, camera.world_to_screen((0, 0)))
        surface.set_clip(old_clip)
