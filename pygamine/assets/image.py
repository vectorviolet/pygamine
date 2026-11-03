from __future__ import annotations

from typing import Literal, overload

import pygame

_cache: dict[str, pygame.Surface] = {}


@overload
def load_image(
    path, size=None, nine_slice: int = 0, return_size: Literal[False] = False
) -> pygame.Surface: ...


@overload
def load_image(
    path, size=None, nine_slice: int = 0, *, return_size: Literal[True]
) -> tuple[pygame.Surface, list[int]]: ...


@overload
def load_image(
    path, size=None, nine_slice: int = 0, return_size: bool = False
) -> pygame.Surface | tuple[pygame.Surface, list[int]]: ...


def load_image(
    path, size=None, nine_slice: int = 0, return_size: bool = False
) -> pygame.Surface | tuple[pygame.Surface, list[int]]:
    """Load (and cache) an image; optionally scale or nine-slice it.

    - size=None or (0, 0): return the original surface.
    - A zero component in `size` means 'keep the source dimension on that axis'.
    - If nine_slice > 0, scale to size using 9-slice (corners pixel-perfect).
    """
    img = _cached_surface(path)
    resolved = _resolve_size(size, img)
    if resolved is None:
        return (img, list(img.get_size())) if return_size else img

    if nine_slice > 0:
        result = nine_slice_scale(img, (resolved[0], resolved[1]), nine_slice)
    else:
        result = pygame.transform.scale(img, resolved)
    return (result, resolved) if return_size else result


def _cached_surface(path) -> pygame.Surface:
    """The converted surface for `path`, loaded from disk on first use."""
    path_str = str(path)
    if path_str not in _cache:
        _cache[path_str] = pygame.image.load(path).convert_alpha()
    return _cache[path_str]


def _resolve_size(size, img: pygame.Surface) -> list[int] | None:
    """The target `[w, h]` for `size`, with a zero component replaced by
    `img`'s dimension on that axis; None if no scaling was asked for
    (size None or (0, 0))."""
    resolved = [0, 0] if size is None else list(size)
    if resolved == [0, 0]:
        return None
    if resolved[0] == 0:
        resolved[0] = img.get_width()
    if resolved[1] == 0:
        resolved[1] = img.get_height()
    return resolved


def scale(image: pygame.Surface, size) -> pygame.Surface:
    return pygame.transform.scale(image, size)


def scale_by(surface: pygame.Surface, factor) -> pygame.Surface:
    if isinstance(factor, (int, float)):
        factor = (factor, factor)
    w = int(surface.get_width() * factor[0])
    h = int(surface.get_height() * factor[1])
    return scale(surface, (w, h))


def nine_slice_scale(
    image: pygame.Surface, target_size: tuple[int, int], corner: int
) -> pygame.Surface:
    """Scale image to target_size using 9-slice.

    corner: size of the corner region in the SOURCE image (pixels).
    Corners are copied at their original pixel size (no distortion).
    Edges are stretched in one axis; the center fills the remaining area.
    """
    src_w, src_h = image.get_size()
    dst_w, dst_h = target_size
    result = pygame.Surface(target_size, pygame.SRCALPHA)

    src_mid_w = src_w - corner * 2  # mid width  in source
    src_mid_h = src_h - corner * 2  # mid height in source
    dst_mid_w = dst_w - corner * 2  # mid width  in dest
    dst_mid_h = dst_h - corner * 2  # mid height in dest

    def _blit(sx, sy, sw, sh, dx, dy, dw, dh) -> None:
        piece = image.subsurface((sx, sy, sw, sh))
        if (sw, sh) != (dw, dh):
            piece = pygame.transform.scale(piece, (dw, dh))
        result.blit(piece, (dx, dy))

    c = corner

    # corners (no scaling)
    _blit(0, 0, c, c, 0, 0, c, c)
    _blit(src_w - c, 0, c, c, dst_w - c, 0, c, c)
    _blit(0, src_h - c, c, c, 0, dst_h - c, c, c)
    _blit(src_w - c, src_h - c, c, c, dst_w - c, dst_h - c, c, c)
    # edges (stretch in one axis)
    _blit(c, 0, src_mid_w, c, c, 0, dst_mid_w, c)
    _blit(c, src_h - c, src_mid_w, c, c, dst_h - c, dst_mid_w, c)
    _blit(0, c, c, src_mid_h, 0, c, c, dst_mid_h)
    _blit(src_w - c, c, c, src_mid_h, dst_w - c, c, c, dst_mid_h)
    # center (stretch in both axes)
    _blit(c, c, src_mid_w, src_mid_h, c, c, dst_mid_w, dst_mid_h)

    return result
