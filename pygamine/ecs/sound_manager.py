from __future__ import annotations

from pygame import mixer

from pygamine.util.math_utils import clamp01


class SoundManager:
    """Generic per-channel play/pause/volume helpers on top of pygame.mixer.

    Takes an arbitrary channel number -- use this directly for a channel of
    your own (e.g. per-category SFX with independent volume). Stick to the
    channels GameAudio reserves and leaves alone (1 and 2, below
    RESERVED_CHANNELS): channel 0 is its music, and the rest are its SFX pool.
    GameAudio builds its music API and pause/resume state on top of this.
    """

    @staticmethod
    def get_volume(channel: int) -> float:
        return mixer.Channel(channel).get_volume()

    @staticmethod
    def play_sound(channel: int, sound_path, loops=0) -> None:
        mixer.Channel(channel).play(mixer.Sound(str(sound_path)), loops)

    @staticmethod
    def set_volume(channel: int, volume: float) -> None:
        mixer.Channel(channel).set_volume(clamp01(volume))

    @staticmethod
    def pause(channel: int) -> None:
        mixer.Channel(channel).pause()

    @staticmethod
    def unpause(channel: int) -> None:
        mixer.Channel(channel).unpause()

    @staticmethod
    def stop(channel: int) -> None:
        mixer.Channel(channel).stop()
