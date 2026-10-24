from __future__ import annotations

from pygame import mixer


class SoundManager:
    """Generic per-channel play/pause/volume helpers on top of pygame.mixer.

    Takes an arbitrary channel number -- use this directly for more channels
    than GameAudio's hardcoded music(0)/sfx(1) pair covers (e.g. per-category
    SFX channels with independent volume). GameAudio builds its named
    music/sfx API and pause/resume state on top of this.
    """

    @staticmethod
    def get_volume(channel: int) -> float:
        return mixer.Channel(channel).get_volume()

    @staticmethod
    def play_sound(channel: int, sound_path, loops=0) -> None:
        mixer.Channel(channel).play(mixer.Sound(str(sound_path)), loops)

    @staticmethod
    def set_volume(channel: int, volume: float) -> None:
        mixer.Channel(channel).set_volume(max(0.0, min(1.0, volume)))

    @staticmethod
    def pause(channel: int) -> None:
        mixer.Channel(channel).pause()

    @staticmethod
    def unpause(channel: int) -> None:
        mixer.Channel(channel).unpause()

    @staticmethod
    def stop(channel: int) -> None:
        mixer.Channel(channel).stop()
