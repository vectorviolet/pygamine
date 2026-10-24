"""Channel-based audio: music on channel 0 (looped), SFX on channel 1.

An opinionated, 2-channel convenience layer on top of SoundManager's generic
per-channel primitives -- adds named music/sfx channels plus music
pause/resume/toggle state SoundManager has no opinion on. Reach for
SoundManager directly instead when a project needs more than these two
channels (e.g. per-category SFX channels for independent volume control).
"""

from __future__ import annotations

import os
from typing import Union

from pygamine.ecs.sound_manager import SoundManager

MUSIC_CHANNEL = 0
SFX_CHANNEL   = 1

PathArg = Union[str, "os.PathLike[str]"]


class GameAudio:
    def __init__(self, music_path: PathArg | None = None, autoplay: bool = True) -> None:
        self._music_paused = False
        if music_path is not None and autoplay:
            self.play_music(music_path)

    # ── music ─────────────────────────────────────────────────────────────────

    def play_music(self, path: PathArg, loops: int = -1) -> None:
        SoundManager.play_sound(MUSIC_CHANNEL, path, loops)
        self._music_paused = False

    def pause_music(self) -> None:
        if self._music_paused:
            return
        SoundManager.pause(MUSIC_CHANNEL)
        self._music_paused = True

    def resume_music(self) -> None:
        if not self._music_paused:
            return
        SoundManager.unpause(MUSIC_CHANNEL)
        self._music_paused = False

    def stop_music(self) -> None:
        """Stops the music outright, freeing its channel -- unlike pause_music(),
        there's nothing left to resume."""
        SoundManager.stop(MUSIC_CHANNEL)
        self._music_paused = False

    def toggle_music(self) -> None:
        if self._music_paused:
            self.resume_music()
        else:
            self.pause_music()

    @property
    def is_music_paused(self) -> bool:
        return self._music_paused

    # ── sfx ───────────────────────────────────────────────────────────────────

    @staticmethod
    def play_sfx(path: PathArg) -> None:
        SoundManager.play_sound(SFX_CHANNEL, path)

    # ── volume ────────────────────────────────────────────────────────────────

    @staticmethod
    def music_volume() -> float:
        return SoundManager.get_volume(MUSIC_CHANNEL)

    @staticmethod
    def sfx_volume() -> float:
        return SoundManager.get_volume(SFX_CHANNEL)

    def set_music_volume(self, volume: float) -> None:
        SoundManager.set_volume(MUSIC_CHANNEL, volume)

    def set_sfx_volume(self, volume: float) -> None:
        SoundManager.set_volume(SFX_CHANNEL, volume)
