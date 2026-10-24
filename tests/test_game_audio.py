"""Unit tests for GameAudio and SoundManager: thin real-mixer wrappers
(channel-based playback, pause/resume, and volume, clamped to [0, 1]).

Both operate on real global pygame.mixer.Channel objects, so tests reset
the channels they use before each test rather than assuming a clean slate
-- the mixer's channel state persists across tests in the same process.
"""
from __future__ import annotations

import struct
import wave

import pytest
from pygame import mixer

from pygamine.ecs.game_audio import GameAudio
from pygamine.ecs.sound_manager import SoundManager

MUSIC_CHANNEL = 0
SFX_CHANNEL = 1
OTHER_CHANNEL_A = 2
OTHER_CHANNEL_B = 3


@pytest.fixture
def sound_path(tmp_path):
    path = tmp_path / "sfx.wav"
    with wave.open(str(path), "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(44100)
        f.writeframes(struct.pack("<100h", *([0] * 100)))
    return str(path)


@pytest.fixture(autouse=True)
def _reset_channels():
    """Real mixer channels persist across tests in the same process --
    reset the ones these tests touch to a known state beforehand."""
    for ch in (MUSIC_CHANNEL, SFX_CHANNEL, OTHER_CHANNEL_A, OTHER_CHANNEL_B):
        mixer.Channel(ch).stop()
        mixer.Channel(ch).set_volume(1.0)
    yield


# ── GameAudio construction ──────────────────────────────────────────────


def test_construction_without_music_path_does_not_play_anything():
    GameAudio()
    assert mixer.Channel(MUSIC_CHANNEL).get_busy() is False


def test_construction_with_music_path_autoplays_by_default(sound_path):
    GameAudio(music_path=sound_path)
    assert mixer.Channel(MUSIC_CHANNEL).get_busy() is True


def test_construction_with_autoplay_false_does_not_play(sound_path):
    GameAudio(music_path=sound_path, autoplay=False)
    assert mixer.Channel(MUSIC_CHANNEL).get_busy() is False


def test_construction_starts_unpaused():
    audio = GameAudio()
    assert audio.is_music_paused is False


# ── play_music ────────────────────────────────────────────────────────


def test_play_music_starts_playback_on_the_music_channel(sound_path):
    audio = GameAudio()
    audio.play_music(sound_path)
    assert mixer.Channel(MUSIC_CHANNEL).get_busy() is True


def test_play_music_clears_a_previously_paused_flag(sound_path):
    audio = GameAudio(music_path=sound_path)
    audio.pause_music()
    assert audio.is_music_paused is True

    audio.play_music(sound_path)

    assert audio.is_music_paused is False


# ── pause_music / resume_music / toggle_music ──────────────────────────


def test_pause_then_resume_round_trips_the_flag(sound_path):
    audio = GameAudio(music_path=sound_path)

    audio.pause_music()
    assert audio.is_music_paused is True

    audio.resume_music()
    assert audio.is_music_paused is False


def test_pausing_twice_is_a_no_op(sound_path):
    audio = GameAudio(music_path=sound_path)
    audio.pause_music()
    audio.pause_music()  # must not raise or double-toggle anything
    assert audio.is_music_paused is True


def test_stop_music_frees_the_channel_and_clears_paused(sound_path):
    """Unlike pause, stop leaves nothing playing -- a paused channel still
    counts as busy, so it would stay occupied indefinitely."""
    audio = GameAudio(music_path=sound_path)
    audio.pause_music()

    audio.stop_music()

    assert mixer.Channel(MUSIC_CHANNEL).get_busy() is False
    assert audio.is_music_paused is False


def test_sound_manager_stop_ends_playback_on_that_channel_only(sound_path):
    SoundManager.play_sound(OTHER_CHANNEL_A, sound_path, loops=-1)
    SoundManager.play_sound(OTHER_CHANNEL_B, sound_path, loops=-1)

    SoundManager.stop(OTHER_CHANNEL_A)

    assert mixer.Channel(OTHER_CHANNEL_A).get_busy() is False
    assert mixer.Channel(OTHER_CHANNEL_B).get_busy() is True


def test_resuming_when_not_paused_is_a_no_op():
    audio = GameAudio()
    audio.resume_music()  # never paused -- must not raise
    assert audio.is_music_paused is False


def test_toggle_music_pauses_when_playing(sound_path):
    audio = GameAudio(music_path=sound_path)
    audio.toggle_music()
    assert audio.is_music_paused is True


def test_toggle_music_resumes_when_paused(sound_path):
    audio = GameAudio(music_path=sound_path)
    audio.pause_music()
    audio.toggle_music()
    assert audio.is_music_paused is False


# ── play_sfx ────────────────────────────────────────────────────────────


def test_play_sfx_plays_on_the_sfx_channel_not_the_music_channel(sound_path):
    GameAudio.play_sfx(sound_path)
    assert mixer.Channel(SFX_CHANNEL).get_busy() is True
    assert mixer.Channel(MUSIC_CHANNEL).get_busy() is False


# ── volume ──────────────────────────────────────────────────────────────
#
# SDL's mixer stores channel volume in a quantized (roughly 1/128-step) form,
# not a raw float -- set_volume(0.3) reads back as ~0.296875, not exactly 0.3.
# All volume assertions below use a generous absolute tolerance for this
# reason rather than picking only "safe" values that happen to land exactly
# on a quantization step.


def test_set_music_volume_is_reflected_by_music_volume():
    audio = GameAudio()
    audio.set_music_volume(0.5)
    assert GameAudio.music_volume() == pytest.approx(0.5, abs=0.01)


def test_set_sfx_volume_is_reflected_by_sfx_volume():
    audio = GameAudio()
    audio.set_sfx_volume(0.3)
    assert GameAudio.sfx_volume() == pytest.approx(0.3, abs=0.01)


def test_set_music_volume_clamps_above_one():
    audio = GameAudio()
    audio.set_music_volume(5.0)
    assert GameAudio.music_volume() == pytest.approx(1.0, abs=0.01)


def test_set_music_volume_clamps_below_zero():
    audio = GameAudio()
    audio.set_music_volume(-5.0)
    assert GameAudio.music_volume() == pytest.approx(0.0, abs=0.01)


def test_setting_music_volume_does_not_affect_sfx_channel():
    audio = GameAudio()
    audio.set_sfx_volume(1.0)
    audio.set_music_volume(0.2)
    assert GameAudio.sfx_volume() == pytest.approx(1.0, abs=0.01)


# ── SoundManager ────────────────────────────────────────────────────────


def test_sound_manager_play_sound_plays_on_the_given_channel(sound_path):
    SoundManager.play_sound(OTHER_CHANNEL_A, sound_path)
    assert mixer.Channel(OTHER_CHANNEL_A).get_busy() is True
    assert mixer.Channel(OTHER_CHANNEL_B).get_busy() is False


def test_sound_manager_set_and_get_volume_round_trip():
    SoundManager.set_volume(OTHER_CHANNEL_A, 0.4)
    assert SoundManager.get_volume(OTHER_CHANNEL_A) == pytest.approx(0.4, abs=0.01)


def test_sound_manager_set_volume_clamps_to_valid_range():
    SoundManager.set_volume(OTHER_CHANNEL_A, 5.0)
    assert SoundManager.get_volume(OTHER_CHANNEL_A) == pytest.approx(1.0, abs=0.01)

    SoundManager.set_volume(OTHER_CHANNEL_A, -5.0)
    assert SoundManager.get_volume(OTHER_CHANNEL_A) == pytest.approx(0.0, abs=0.01)


def test_sound_manager_channels_are_independent_of_game_audio_channels(sound_path):
    """SoundManager takes an arbitrary channel number -- using one that
    doesn't collide with GameAudio's hardcoded music(0)/sfx(1) channels
    must not affect those."""
    SoundManager.play_sound(OTHER_CHANNEL_A, sound_path)
    assert mixer.Channel(MUSIC_CHANNEL).get_busy() is False
    assert mixer.Channel(SFX_CHANNEL).get_busy() is False


def test_sound_manager_pause_then_unpause_round_trips_playback(sound_path):
    SoundManager.play_sound(OTHER_CHANNEL_A, sound_path, loops=-1)
    SoundManager.pause(OTHER_CHANNEL_A)
    assert mixer.Channel(OTHER_CHANNEL_A).get_busy() is True  # paused, not stopped

    SoundManager.unpause(OTHER_CHANNEL_A)
    assert mixer.Channel(OTHER_CHANNEL_A).get_busy() is True


# ── GameAudio built on SoundManager ──────────────────────────────────────


def test_game_audio_play_sfx_delegates_to_sound_manager_sfx_channel(sound_path):
    """GameAudio.play_sfx is SoundManager.play_sound(SFX_CHANNEL, ...) under
    the hood -- playing directly via SoundManager on that channel and via
    GameAudio must be indistinguishable to the mixer."""
    GameAudio.play_sfx(sound_path)
    assert mixer.Channel(SFX_CHANNEL).get_busy() is True
    assert SoundManager.get_volume(SFX_CHANNEL) == pytest.approx(1.0, abs=0.01)
