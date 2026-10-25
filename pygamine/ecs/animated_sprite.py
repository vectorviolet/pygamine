"""AnimatedSprite + factory: GameObject preconfigured with SpriteRenderer2D and
Animator for sheet-based animation.

Constructor mirrors StateObject (parent + pos + size + "CENTER" support) so the
same class works for UI panels and free game-world entities.

    factory = AnimatedSpriteFactory(assets)
    coin    = factory.from_strip("coin_sheet", pos=(x, y), size=(32, 32),
                                 frame_count=4, fps=8)
    coin.update(); coin.draw(surface)
"""

from __future__ import annotations

import pygame

from pygamine.assets.sprite_sheet import SpriteSheet
from pygamine.ecs.components.animator import Animator
from pygamine.ecs.components.animation_clip import AnimationClip
from pygamine.ecs.components.sprite_renderer2d import SpriteRenderer2D
from pygamine.ecs.components.transform import Transform
from pygamine.ecs.game_object import GameObject


class AnimatedSprite(GameObject):
    """GameObject with a SpriteRenderer2D + Animator preconfigured.

    The supplied frames register as the "default" clip and start playing
    immediately. If size differs from the source frame size, frames are
    scaled once at construction time.
    """

    def __init__(
        self,
        parent: Transform | None = None,
        pos=("CENTER", "CENTER"),
        size: tuple = (0, 0),
        frames: list[pygame.Surface] | None = None,
        fps: float = 12.0,
        loop: bool = True,
        name: str = "animated_sprite",
    ) -> None:
        if frames is None or not frames:
            raise ValueError("AnimatedSprite requires at least one frame")
        super().__init__(name=name)

        src_size = frames[0].get_size()
        resolved_size = self._resolve_size(size, src_size)
        if resolved_size != src_size:
            frames = [pygame.transform.scale(f, resolved_size) for f in frames]

        self.rect.size = resolved_size
        self.rect.set_parent(parent)
        self.rect.set_position(pos)

        self.add_component(SpriteRenderer2D)
        self.animator = self.add_component(Animator)
        self.animator.add_clip("default", AnimationClip(frames, fps=fps, loop=loop))
        self.animator.play("default")

    @staticmethod
    def _resolve_size(size, src_size: tuple[int, int]) -> tuple[int, int]:
        """Normalize the caller's size to a (w, h) 2-tuple, defaulting to src_size."""
        if isinstance(size, pygame.Rect):
            size = size.size

        if not size:
            return src_size

        if len(size) != 2:
            raise ValueError(f"AnimatedSprite size must be (w, h), got {size!r}")

        w, h = size

        if (w, h) == (0, 0):
            return src_size

        return w, h

    def add_clip(
        self,
        name: str,
        frames: list[pygame.Surface],
        fps: float = 12.0,
        loop: bool = True,
    ) -> None:
        self.animator.add_clip(name, AnimationClip(frames, fps=fps, loop=loop))

    def play(self, name: str, restart: bool = False) -> None:
        self.animator.play(name, restart=restart)


class AnimatedSpriteFactory:
    """Builds AnimatedSprite instances from AssetManager-registered spritesheets."""

    def __init__(self, assets):
        self._assets = assets

    def from_strip(
        self,
        asset_key: str,
        parent: Transform | None = None,
        pos=("CENTER", "CENTER"),
        size: tuple = (0, 0),
        frame_count: int = 1,
        fps: float = 12.0,
        loop: bool = True,
        horizontal: bool = True,
        name: str | None = None,
    ) -> AnimatedSprite:
        sheet = SpriteSheet.from_path(self._assets.image_path(asset_key))
        frames = sheet.strip(frame_count, horizontal=horizontal)
        return AnimatedSprite(
            parent=parent,
            pos=pos,
            size=size,
            frames=frames,
            fps=fps,
            loop=loop,
            name=name or asset_key,
        )

    def from_grid(
        self,
        asset_key: str,
        parent: Transform | None = None,
        pos=("CENTER", "CENTER"),
        size: tuple = (0, 0),
        cols: int = 1,
        rows: int = 1,
        fps: float = 12.0,
        loop: bool = True,
        name: str | None = None,
    ) -> AnimatedSprite:
        sheet = SpriteSheet.from_path(self._assets.image_path(asset_key))
        frames = sheet.grid(cols, rows)
        return AnimatedSprite(
            parent=parent,
            pos=pos,
            size=size,
            frames=frames,
            fps=fps,
            loop=loop,
            name=name or asset_key,
        )
