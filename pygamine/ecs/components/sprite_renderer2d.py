from __future__ import annotations

import pygame
from pygamine.ecs.components.component import Component


class SpriteRenderer2D(Component):
    def __init__(self) -> None:
        super().__init__()
        self.image: pygame.Surface | None = None

    def set_image(self, image: pygame.Surface) -> None:
        self.image = image

    def draw(self, surface: pygame.Surface) -> None:
        if self.image is None:
            return
        surface.blit(self.image, self.game_object.rect)
