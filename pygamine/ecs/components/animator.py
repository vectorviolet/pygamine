from __future__ import annotations

import pygame

from pygamine.ecs.components.animation_clip import AnimationClip
from pygamine.ecs.components.component import Component
from pygamine.ecs.components.sprite_renderer2d import SpriteRenderer2D


class Animator(Component):
    def __init__(self) -> None:
        super().__init__()
        self.clips: dict[str, AnimationClip] = {}
        self._clip: AnimationClip | None = None
        self._clip_name: str | None = None
        self._frame: int = 0
        self._last_step_ms: int = 0
        self._playing: bool = False

    def add_clip(self, name: str, clip: AnimationClip) -> None:
        self.clips[name] = clip

    def play(self, name: str, restart: bool = False) -> None:
        if not restart and self._clip_name == name and self._playing:
            return
        clip = self.clips.get(name)
        if clip is None or not clip.frames:
            return
        self._clip = clip
        self._clip_name = name
        self._frame = 0
        self._last_step_ms = pygame.time.get_ticks()
        self._playing = True
        self._apply()

    def stop(self) -> None:
        self._playing = False
        self._frame = 0

    @property
    def is_playing(self) -> bool:
        return self._playing

    @property
    def current_clip(self) -> str | None:
        return self._clip_name

    # Beyond this many frame-durations of accumulated lag, assume the animator
    # was paused (e.g. its panel was hidden) and resume from the current frame
    # rather than snapping forward. Without this, switching back to a panel
    # after several seconds would advance a non-looping clip straight to its
    # last frame on the first tick.
    _RESUME_AFTER_LAG_FACTOR = 4

    def update(self) -> None:
        if not self._playing or self._clip is None:
            return
        duration = self._clip.frame_duration_ms
        if duration <= 0:
            return
        now = pygame.time.get_ticks()
        elapsed = now - self._last_step_ms
        if elapsed < duration:
            return
        if elapsed > duration * self._RESUME_AFTER_LAG_FACTOR:
            self._last_step_ms = now
            return
        steps = elapsed // duration
        self._last_step_ms += steps * duration
        self._advance(int(steps))
        self._apply()

    def _advance(self, steps: int) -> None:
        if self._clip is None:
            return

        end = len(self._clip.frames) - 1
        nxt = self._frame + steps
        if nxt <= end:
            self._frame = nxt
        elif self._clip.loop:
            self._frame = nxt % len(self._clip.frames)
        else:
            self._frame = end
            self._playing = False

    def _apply(self) -> None:
        if self._clip is None:
            return

        renderer = self.get_component(SpriteRenderer2D)
        if renderer is not None:
            renderer.set_image(self._clip.frames[self._frame])
