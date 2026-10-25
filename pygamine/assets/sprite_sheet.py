"""SpriteSheet: slice a single image into a list of frame surfaces.

Pairs naturally with pygamine.ecs.components.animator.AnimationClip:

    sheet  = SpriteSheet.from_path("coin_strip4.png")
    frames = sheet.strip(4)
    clip   = AnimationClip(frames, fps=8, loop=True)

Frames are returned as independent Surfaces (copied out of the sheet) so they
remain valid even if the source sheet is later mutated or evicted from a
caching layer. Pass copy=False for a zero-allocation subsurface view when
you know the source will outlive the frames.
"""

from __future__ import annotations

import pygame
from pygamine.assets.asset_path import PathLike
from pygamine.assets.image import load_image


class SpriteSheet:
    def __init__(self, image: pygame.Surface):
        self.image = image

    @classmethod
    def from_path(cls, path: PathLike) -> "SpriteSheet":
        return cls(load_image(path))

    def strip(
        self, frame_count: int, horizontal: bool = True, copy: bool = True
    ) -> list[pygame.Surface]:
        """Slice an evenly-divided single-row (or single-column) strip into N frames."""
        if frame_count <= 0:
            return []
        w, h = self.image.get_size()
        if horizontal:
            fw, fh = w // frame_count, h
            rects = [(i * fw, 0, fw, fh) for i in range(frame_count)]
        else:
            fw, fh = w, h // frame_count
            rects = [(0, i * fh, fw, fh) for i in range(frame_count)]
        return [self._slice(r, copy) for r in rects]

    def grid(self, cols: int, rows: int, copy: bool = True) -> list[pygame.Surface]:
        """Slice an evenly-divided grid; returns frames in row-major order."""
        if cols <= 0 or rows <= 0:
            return []
        w, h = self.image.get_size()
        fw, fh = w // cols, h // rows
        rects = [(c * fw, r * fh, fw, fh) for r in range(rows) for c in range(cols)]
        return [self._slice(r, copy) for r in rects]

    def frame(
        self, col: int, row: int, frame_w: int, frame_h: int, copy: bool = True
    ) -> pygame.Surface:
        """Pull a single frame at a grid coord, given the source-pixel frame size."""
        return self._slice((col * frame_w, row * frame_h, frame_w, frame_h), copy)

    def _slice(self, rect: tuple, copy: bool) -> pygame.Surface:
        sub = self.image.subsurface(rect)
        return sub.copy() if copy else sub
