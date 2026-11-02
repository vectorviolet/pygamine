from __future__ import annotations

import pygame
from pygamine.ecs.components.component import Component


class SpriteRenderer2D(Component):
    def __init__(self) -> None:
        super().__init__()
        self.image: pygame.Surface | None = None

    def set_image(self, image: pygame.Surface) -> None:
        self.image = image

    def require_image(self) -> pygame.Surface:
        """`image`, typed as non-Optional: raises RuntimeError if
        set_image() hasn't been called yet."""
        if self.image is None:
            name = getattr(self.game_object, "name", None)
            owner = f" on {name!r}" if name is not None else ""
            raise RuntimeError(f"SpriteRenderer2D{owner} has no image yet")
        return self.image

    def draw(self, surface: pygame.Surface) -> None:
        if self.image is None:
            return
        surface.blit(self.image, self.game_object.rect)
