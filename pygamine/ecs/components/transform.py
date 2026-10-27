# Defer annotation evaluation so self-referential hints like `parent: Transform`
# don't raise NameError on Python < 3.14 (pre-PEP-649). Required for the 3.12+
# support floor.
from __future__ import annotations

import pygame
from pygamine.util.utils import Anchorable
from pygamine.ecs.components.component import Component


class Transform(Component, pygame.Rect, Anchorable):
    def __init__(
        self,
        position: tuple = (0, 0),
        size: tuple = (0, 0),
        parent: Transform | None = None,
        anchor: str = "top-left",
    ) -> None:
        Component.__init__(self)
        pygame.Rect.__init__(self, position, size)
        self.parent = parent
        self.anchor = anchor

    def set_position(self, position: tuple) -> None:
        parent_size = self.parent.size if self.parent else self.size
        position = super().resolve_pos(position, parent_size, self.size, self.anchor)
        if self.parent is not None:
            position = (position[0] + self.parent.x, position[1] + self.parent.y)
        self.topleft = position

    def set_parent(self, parent: Transform | None) -> None:
        if not parent:
            self.parent = parent
            return

        assert isinstance(parent, Transform), "Parent must be a Transform."
        self.parent = parent

    def update(self) -> None:  # type: ignore[override]
        # Component lifecycle hook; intentionally shadows pygame.Rect.update,
        # which is unused on Transform (positions are set via topleft/set_position).
        ...
