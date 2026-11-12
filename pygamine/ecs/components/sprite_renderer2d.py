from __future__ import annotations

import pygame
from pygamine.ecs.components.component import Component, describe
from pygamine.util.blend import ALPHA_BLIT


class SpriteRenderer2D(Component):
    def __init__(self) -> None:
        super().__init__()
        self.image: pygame.Surface | None = None

    def set_image(self, image: pygame.Surface) -> None:
        self.image = image

    def require_image(self) -> pygame.Surface:
        """`image`, typed as non-Optional: raises LookupError naming the
        owner if set_image() hasn't been called yet."""
        if self.image is None:
            owner = (
                f" on {describe(self.game_object)}"
                if self.game_object is not None
                else ""
            )
            raise LookupError(f"{type(self).__name__}{owner} has no image yet")
        return self.image

    def draw(self, surface: pygame.Surface) -> None:
        if self.image is None:
            return
        surface.blit(self.image, self.game_object.rect, special_flags=ALPHA_BLIT)
