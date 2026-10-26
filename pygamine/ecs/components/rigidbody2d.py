from __future__ import annotations

from pygame import Vector2
from pygamine.ecs.components.component import Component


class Rigidbody2D(Component):
    def __init__(self) -> None:
        super().__init__()
        self.velocity = Vector2(0, 0)
        self._float_pos: Vector2 | None = None

    def set_velocity(self, velocity: Vector2 | tuple[float, float]) -> None:
        self.velocity = Vector2(velocity)
        self._float_pos = None  # re-sync from transform on next update

    def update(self) -> None:
        if self.velocity == Vector2(0, 0):
            return
        transform = self.game_object.rect
        if self._float_pos is None:
            self._float_pos = Vector2(transform.topleft)
        self._float_pos += self.velocity
        transform.topleft = (round(self._float_pos.x), round(self._float_pos.y))
