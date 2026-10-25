from __future__ import annotations

import pygame
from typing import Iterable


class Debug:
    BORDER_COLOR = "white"
    BORDER_WIDTH = 2
    PADDING = 10
    MARGIN = 10
    ALPHA = 150
    ANTIALIAS = True
    BACKGROUND_COLOR = (0, 0, 0)

    @staticmethod
    def draw(surface: pygame.Surface, font: pygame.font.Font, debug_info) -> None:
        debug_lines = Debug.get_debug_lines(debug_info)
        debug_surfaces = [
            font.render(line, Debug.ANTIALIAS, "white") for line in debug_lines
        ]
        width = max(surface.get_width() for surface in debug_surfaces)
        height = sum(surface.get_height() for surface in debug_surfaces)

        Debug.draw_debug_background(surface, width, height)
        Debug.draw_debug_border(surface, width, height)
        Debug.draw_debug_text(surface, debug_surfaces)

    @staticmethod
    def get_debug_lines(debug_info) -> Iterable[str]:
        yield "DEBUG MODE"
        yield "==============================="
        for source, info in debug_info:
            yield source
            for key, value in info.items():
                yield f"{key}: {value}"
            yield ""

    @staticmethod
    def draw_debug_background(surface: pygame.Surface, width: int, height: int) -> None:
        debug_background = pygame.Surface(
            (width + Debug.PADDING * 2, height + Debug.PADDING * 2)
        )
        debug_background.fill(Debug.BACKGROUND_COLOR)
        debug_background.set_alpha(Debug.ALPHA)
        surface.blit(debug_background, (Debug.MARGIN, Debug.MARGIN))

    @staticmethod
    def draw_debug_border(surface: pygame.Surface, width: int, height: int) -> None:
        pygame.draw.rect(
            surface,
            Debug.BORDER_COLOR,
            (
                Debug.MARGIN - Debug.BORDER_WIDTH,
                Debug.MARGIN - Debug.BORDER_WIDTH,
                width + Debug.PADDING * 2 + Debug.BORDER_WIDTH,
                height + Debug.PADDING * 2 + Debug.BORDER_WIDTH,
            ),
            Debug.BORDER_WIDTH,
        )

    @staticmethod
    def draw_debug_text(
        surface: pygame.Surface, debug_surfaces: list[pygame.Surface]
    ) -> None:
        x, y = Debug.MARGIN + Debug.PADDING, Debug.MARGIN + Debug.PADDING
        for debug_surface in debug_surfaces:
            surface.blit(debug_surface, (x, y))
            y += debug_surface.get_height()
