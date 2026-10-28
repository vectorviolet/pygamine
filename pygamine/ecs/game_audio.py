"""Music on a reserved channel (0, looped); SFX on a pool of free channels.

An opinionated convenience layer on top of pygame.mixer and SoundManager's
generic per-channel primitives: named music/SFX APIs plus music
pause/resume/toggle state SoundManager has no opinion on.

Channel layout:

- 0 (MUSIC_CHANNEL): music. Reserved, so no SFX ever lands on it.
- 1 and 2: reserved too and left alone by play_sfx(). 1 is the old shared
  SFX_CHANNEL; both stay free for a game's own SoundManager use (e.g. a
  dedicated alert channel). They're outside the SFX pool, so set_sfx_volume()
  only keeps channel 1 in step for backward compatibility.
- RESERVED_CHANNELS onwards: the SFX pool. Each play_sfx() takes a free
  channel from it, so sounds play side by side instead of cutting each other
  off. When every pool channel is busy, the new sound is dropped (or, with
  configure_sfx(steal_oldest=True), replaces the oldest SFX). The SFX volume is applied to every pool channel, including ones already
  playing.

Volumes: a master volume scales both the music and the SFX. What you hear is
master_volume() * music_volume() for the music and master_volume() *
sfx_volume() for every SFX (pool channels and channel 1), applied live,
including sounds already playing. music_volume() and sfx_volume() return the
values the game set, not multiplied by master, so settings sliders can show
them as they are. A game that plays on a reserved channel of its own (2, say)
sets that channel's volume itself: use effective_sfx_volume() for it so the
master volume applies there too.

The mixer is process-global, so the volumes and the SFX settings (pool size,
what happens when the pool is full) are class-level too, shared by every
GameAudio.
"""

from __future__ import annotations

import os
from typing import ClassVar, Union

from pygame import mixer

from pygamine.ecs.sound_manager import SoundManager
from pygamine.util.math_utils import clamp01

MUSIC_CHANNEL = 0
# The old shared SFX channel. play_sfx() no longer uses it; kept reserved
# (and at the SFX volume) so code that played on it directly still works.
SFX_CHANNEL = 1
# Channels 0..RESERVED_CHANNELS-1 are kept out of the SFX pool.
RESERVED_CHANNELS = 3
DEFAULT_SFX_CHANNELS = 16

PathArg = Union[str, "os.PathLike[str]"]


class GameAudio:
    # Volumes, shared by every instance: the mixer is global. Each is the
    # value set (0-1); the channels play at master * music / master * SFX.
    _master_volume: ClassVar[float] = 1.0
    _music_volume: ClassVar[float] = 1.0
    # SFX state, shared by every instance too.
    _sfx_volume: ClassVar[float] = 1.0
    _sfx_channels: ClassVar[int] = DEFAULT_SFX_CHANNELS
    _steal_oldest: ClassVar[bool] = False
    _max_copies_per_sound: ClassVar[int | None] = None
    # Decoded sounds by path, and the mixer settings they were decoded for.
    _sounds: ClassVar[dict[str, mixer.Sound]] = {}
    _sounds_mixer_init: ClassVar[tuple | None] = None
    # Pool channel index -> play order, to find the oldest playing SFX.
    _play_order: ClassVar[dict[int, int]] = {}
    _play_count: ClassVar[int] = 0

    def __init__(
        self,
        music_path: PathArg | None = None,
        autoplay: bool = True,
        *,
        sfx_channels: int | None = None,
        steal_oldest: bool | None = None,
        max_copies_per_sound: int | None = None,
    ) -> None:
        """The SFX keyword arguments are passed to configure_sfx(); left as
        None, each keeps its current (class-wide) setting."""
        self._music_paused = False
        GameAudio.configure_sfx(
            channels=sfx_channels,
            steal_oldest=steal_oldest,
            max_copies_per_sound=max_copies_per_sound,
        )
        if music_path is not None and autoplay:
            self.play_music(music_path)

    # ── music ─────────────────────────────────────────────────────────────────

    def play_music(self, path: PathArg, loops: int = -1) -> None:
        """Plays on the music channel at the effective music volume."""
        GameAudio._apply_music_volume()
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

    @classmethod
    def configure_sfx(
        cls,
        *,
        channels: int | None = None,
        steal_oldest: bool | None = None,
        max_copies_per_sound: int | None = None,
    ) -> None:
        """Sets up the SFX pool. Arguments left as None keep their setting.

        channels: how many SFX can play at once (default 16).
        steal_oldest: when every pool channel is busy, False (the default)
            drops the new sound; True stops the SFX that has played longest
            and plays the new one in its place.
        max_copies_per_sound: at most this many copies of one sound file play
            at once (off by default; pass 0 to turn it off again). At the
            limit, steal_oldest decides again: drop the new one (default),
            or restart the oldest copy.
        """
        if channels is not None:
            if channels < 1:
                raise ValueError(f"channels must be at least 1, got {channels}")
            cls._sfx_channels = channels
        if steal_oldest is not None:
            cls._steal_oldest = steal_oldest
        if max_copies_per_sound is not None:
            if max_copies_per_sound < 0:
                raise ValueError(
                    f"max_copies_per_sound can't be negative, got {max_copies_per_sound}"
                )
            cls._max_copies_per_sound = max_copies_per_sound or None
        if channels is not None and mixer.get_init():
            mixer.set_num_channels(RESERVED_CHANNELS + cls._sfx_channels)
            mixer.set_reserved(RESERVED_CHANNELS)
            cls._apply_sfx_volume()

    @classmethod
    def play_sfx(cls, path: PathArg) -> mixer.Channel | None:
        """Plays a sound effect on a free pool channel, at the SFX volume.

        Returns the channel it plays on, or None if it was dropped (every
        channel busy, or the per-sound limit reached, with steal_oldest off).
        Callable on the class or an instance.
        """
        cls._ensure_pool()
        sound = cls._load(path)
        index = cls._pick_channel(sound)
        if index is None:
            return None
        channel = mixer.Channel(index)
        channel.set_volume(cls.effective_sfx_volume())
        channel.play(sound)
        cls._play_count += 1
        cls._play_order[index] = cls._play_count
        return channel

    @classmethod
    def _pool(cls) -> range:
        return range(RESERVED_CHANNELS, mixer.get_num_channels())

    @classmethod
    def _ensure_pool(cls) -> None:
        """The mixer resets to 8 channels and no reservations on (re)init."""
        if mixer.get_num_channels() < RESERVED_CHANNELS + cls._sfx_channels:
            mixer.set_num_channels(RESERVED_CHANNELS + cls._sfx_channels)
        mixer.set_reserved(RESERVED_CHANNELS)

    @classmethod
    def _load(cls, path: PathArg) -> mixer.Sound:
        """Each file is decoded once; the cache is dropped if the mixer is
        reinitialised with other settings."""
        init = mixer.get_init()
        if init != cls._sounds_mixer_init:
            cls._sounds = {}
            cls._sounds_mixer_init = init
        key = os.fspath(path)
        sound = cls._sounds.get(key)
        if sound is None:
            sound = cls._sounds[key] = mixer.Sound(key)
        return sound

    @classmethod
    def _play_order_of(cls, index: int) -> int:
        # Channels play_sfx() didn't start count as the oldest.
        return cls._play_order.get(index, 0)

    @classmethod
    def _pick_channel(cls, sound: mixer.Sound) -> int | None:
        busy = [i for i in cls._pool() if mixer.Channel(i).get_busy()]
        if cls._max_copies_per_sound is not None:
            copies = [i for i in busy if mixer.Channel(i).get_sound() is sound]
            if len(copies) >= cls._max_copies_per_sound:
                return (
                    min(copies, key=cls._play_order_of) if cls._steal_oldest else None
                )
        busy_set = set(busy)
        for i in cls._pool():
            if i not in busy_set:
                return i
        if not cls._steal_oldest:
            return None
        return min(busy, key=cls._play_order_of)

    # ── volume ──────────────────────────────────────────────────────────────

    @classmethod
    def master_volume(cls) -> float:
        """The master volume set (0-1, default 1.0)."""
        return cls._master_volume

    @classmethod
    def music_volume(cls) -> float:
        """The music volume set (0-1, default 1.0), not multiplied by the
        master volume. It's the value set, not read back from the mixer, so
        a volume set on channel 0 directly isn't reflected here."""
        return cls._music_volume

    @classmethod
    def sfx_volume(cls) -> float:
        """The SFX volume set (0-1, default 1.0), not multiplied by the
        master volume."""
        return cls._sfx_volume

    @classmethod
    def effective_music_volume(cls) -> float:
        """What the music plays at: master_volume() * music_volume()."""
        return cls._master_volume * cls._music_volume

    @classmethod
    def effective_sfx_volume(cls) -> float:
        """What SFX play at: master_volume() * sfx_volume(). A game that plays
        on a reserved channel of its own sets that channel to this, so the
        master volume applies there too."""
        return cls._master_volume * cls._sfx_volume

    @staticmethod
    def set_master_volume(volume: float) -> None:
        """Scales the music and every SFX, including ones already playing.
        Clamped to 0-1."""
        GameAudio._master_volume = clamp01(volume)
        GameAudio._apply_music_volume()
        GameAudio._apply_sfx_volume()

    @staticmethod
    def set_music_volume(volume: float) -> None:
        """Applies to the music at once. Clamped to 0-1."""
        GameAudio._music_volume = clamp01(volume)
        GameAudio._apply_music_volume()

    @staticmethod
    def set_sfx_volume(volume: float) -> None:
        """Applies to every SFX, including ones already playing. Clamped to
        0-1."""
        GameAudio._sfx_volume = clamp01(volume)
        GameAudio._apply_sfx_volume()

    @classmethod
    def _apply_music_volume(cls) -> None:
        if not mixer.get_init():
            return
        mixer.Channel(MUSIC_CHANNEL).set_volume(cls.effective_music_volume())

    @classmethod
    def _apply_sfx_volume(cls) -> None:
        if not mixer.get_init():
            return
        volume = cls.effective_sfx_volume()
        for i in (SFX_CHANNEL, *cls._pool()):
            mixer.Channel(i).set_volume(volume)
