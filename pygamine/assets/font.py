"""Font loading helper used by panel factories.

Looks up `cfg[font_key]` in the asset manifest first; if no font is registered
under that name, treats it as a system font and falls back to SysFont.

`bold` / `italic` apply either way: SysFont picks a matching system variant
where one exists, while a font file gets pygame's synthetic bold/italic --
so for a real weight, register that weight's own file (e.g. a `*-Bold.ttf`)
and leave the flag off.
"""

from __future__ import annotations

import pygame


def load_font(
    cfg: dict,
    assets,
    font_key: str = "font",
    size_key: str = "font_size",
    bold_key: str = "bold",
    italic_key: str = "italic",
) -> pygame.font.Font:
    name = cfg.get(font_key, "Arial")
    size = cfg.get(size_key, 32)
    bold = cfg.get(bold_key, False)
    italic = cfg.get(italic_key, False)

    try:
        path = assets.font_path(name)
    except KeyError:
        return pygame.font.SysFont(name, size, bold, italic)

    font = pygame.font.Font(str(path), size)
    font.set_bold(bool(bold))
    font.set_italic(bool(italic))
    return font
