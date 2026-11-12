"""Blit flag for translucent surfaces.

In the browser build (pygbag / emscripten) pygame's own per-pixel alpha
blend is about six times slower than SDL2's (measured: a full 1280x720
translucent blit takes ~20 ms against ~3.5 ms), and the audio shares the
one browser thread, so it crackles when frames run long. Desktop keeps the
default blend, which is SIMD-accelerated there.
"""

from __future__ import annotations

import sys

import pygame


def alpha_blit_flag(platform: str) -> int:
    """The `special_flags` value for a translucent blit on `platform`
    (a `sys.platform` string)."""
    return pygame.BLEND_ALPHA_SDL2 if platform == "emscripten" else 0


ALPHA_BLIT = alpha_blit_flag(sys.platform)
