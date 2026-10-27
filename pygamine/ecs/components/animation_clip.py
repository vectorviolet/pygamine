from __future__ import annotations

import pygame


class AnimationClip:
    def __init__(
        self, frames: list[pygame.Surface], fps: float = 12.0, loop: bool = True
    ) -> None:
        if fps <= 0:
            raise ValueError(f"AnimationClip fps must be positive, got {fps!r}")
        self.frames = frames
        self.fps = fps
        self.loop = loop

    @property
    def frame_duration_ms(self) -> int:
        return int(1000 / self.fps)
