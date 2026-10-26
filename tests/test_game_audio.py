"""Unit tests for GameAudio and SoundManager: thin real-mixer wrappers
(channel-based playback, pause/resume, and volume, clamped to [0, 1]).

Both operate on real global pygame.mixer.Channel objects, so tests reset
the channels (and GameAudio's class-wide SFX settings) before each test
rather than assuming a clean slate -- the mixer's state persists across
tests in the same process. The dummy audio driver plays sounds in real
time, so tests that check a sound is still playing use long ones.
"""

from __future__ import annotations

import struct
import wave

import pytest
from pygame import mixer

from pygamine.ecs.game_audio import (
    DEFAULT_SFX_CHANNELS,
    RESERVED_CHANNELS,
    GameAudio,
)
from pygamine.ecs.sound_manager import SoundManager

MUSIC_CHANNEL = 0
SFX_CHANNEL = 1
GAME_OWNED_CHANNEL = 2  # reserved, e.g. Chokepoint's life-lost bell
OTHER_CHANNEL_A = 2
OTHER_CHANNEL_B = 3


def _write_wav(path, seconds: float) -> str:
    frames = int(44100 * seconds)
    with wave.open(str(path), "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(44100)
        f.writeframes(struct.pack(f"<{frames}h", *([0] * frames)))
    return str(path)


@pytest.fixture
def sound_path(tmp_path):
    path = tmp_path / "sfx.wav"
    with wave.open(str(path), "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(44100)
        f.writeframes(struct.pack("<100h", *([0] * 100)))
    return str(path)


@pytest.fixture
def long_sound_path(tmp_path):
    return _write_wav(tmp_path / "long.wav", 5)


@pytest.fixture
def other_long_sound_path(tmp_path):
    return _write_wav(tmp_path / "other_long.wav", 5)


@pytest.fixture(autouse=True)
def _reset_channels():
    """Real mixer channels and GameAudio's class-wide SFX settings persist
    across tests in the same process -- reset them beforehand."""
    if not mixer.get_init():
        mixer.init()
    mixer.set_num_channels(RESERVED_CHANNELS + DEFAULT_SFX_CHANNELS)
    for ch in range(mixer.get_num_channels()):
        mixer.Channel(ch).stop()
        mixer.Channel(ch).set_volume(1.0)
    GameAudio._sfx_volume = 1.0
    GameAudio._sfx_channels = DEFAULT_SFX_CHANNELS
    GameAudio._steal_oldest = False
    GameAudio._max_copies_per_sound = None
    GameAudio._started = {}
    GameAudio._play_count = 0
    yield
    for ch in range(mixer.get_num_channels()):
        mixer.Channel(ch).stop()


def _pool():
    return range(RESERVED_CHANNELS, mixer.get_num_channels())


def _busy_pool_channels():
    return [i for i in _pool() if mixer.Channel(i).get_busy()]


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


def test_play_sfx_plays_on_a_pool_channel_not_a_reserved_one(long_sound_path):
    channel = GameAudio.play_sfx(long_sound_path)
    assert channel is not None
    assert channel.get_busy() is True
    assert _busy_pool_channels() == [RESERVED_CHANNELS]
    for reserved in range(RESERVED_CHANNELS):
        assert mixer.Channel(reserved).get_busy() is False


def test_two_sfx_back_to_back_both_play(long_sound_path, other_long_sound_path):
    first = GameAudio.play_sfx(long_sound_path)
    second = GameAudio.play_sfx(other_long_sound_path)
    assert first is not None and second is not None
    assert first.get_busy() is True
    assert second.get_busy() is True
    assert len(_busy_pool_channels()) == 2


def test_the_same_sfx_twice_plays_two_copies(long_sound_path):
    GameAudio.play_sfx(long_sound_path)
    GameAudio.play_sfx(long_sound_path)
    assert len(_busy_pool_channels()) == 2


def test_play_sfx_works_on_an_instance_too(long_sound_path):
    audio = GameAudio()
    assert audio.play_sfx(long_sound_path) is not None


def test_play_sfx_reuses_the_decoded_sound(long_sound_path):
    first = GameAudio.play_sfx(long_sound_path)
    second = GameAudio.play_sfx(long_sound_path)
    assert first.get_sound() is second.get_sound()


def test_play_sfx_never_touches_the_music(long_sound_path, other_long_sound_path):
    audio = GameAudio()
    audio.play_music(long_sound_path)
    music = mixer.Channel(MUSIC_CHANNEL).get_sound()
    for _ in range(DEFAULT_SFX_CHANNELS + 2):  # more than the pool holds
        GameAudio.play_sfx(other_long_sound_path)
    assert mixer.Channel(MUSIC_CHANNEL).get_sound() is music


def test_play_sfx_leaves_a_game_owned_channel_alone(
    long_sound_path, other_long_sound_path
):
    """Channel 2 stays out of the pool, so a game playing its own sound
    there directly (e.g. Chokepoint's life-lost bell) isn't cut off."""
    alert = mixer.Sound(long_sound_path)
    mixer.Channel(GAME_OWNED_CHANNEL).play(alert)
    for _ in range(DEFAULT_SFX_CHANNELS + 2):
        GameAudio.play_sfx(other_long_sound_path)
    assert mixer.Channel(GAME_OWNED_CHANNEL).get_sound() is alert


def test_other_code_playing_a_sound_skips_the_reserved_channels(long_sound_path):
    """A plain Sound.play() elsewhere stays off the music channel too."""
    GameAudio.configure_sfx(channels=2)
    GameAudio.play_sfx(long_sound_path)
    GameAudio.play_sfx(long_sound_path)
    # Every pool channel is busy; the reserved ones are free but not offered.
    assert mixer.Sound(long_sound_path).play() is None
    for reserved in range(RESERVED_CHANNELS):
        assert mixer.Channel(reserved).get_busy() is False


def test_play_sfx_grows_the_mixer_to_the_pool_size(long_sound_path):
    mixer.set_num_channels(8)  # what the mixer starts with
    GameAudio.play_sfx(long_sound_path)
    assert mixer.get_num_channels() == RESERVED_CHANNELS + DEFAULT_SFX_CHANNELS


def test_configure_sfx_sets_the_pool_size():
    GameAudio.configure_sfx(channels=4)
    assert mixer.get_num_channels() == RESERVED_CHANNELS + 4


def test_constructor_passes_sfx_settings_to_configure_sfx():
    GameAudio(sfx_channels=5, steal_oldest=True, max_copies_per_sound=2)
    assert mixer.get_num_channels() == RESERVED_CHANNELS + 5
    assert GameAudio._steal_oldest is True
    assert GameAudio._max_copies_per_sound == 2


def test_constructor_without_sfx_settings_keeps_the_current_ones():
    GameAudio.configure_sfx(channels=5, steal_oldest=True)
    GameAudio()  # e.g. the splash screen's own GameAudio
    assert mixer.get_num_channels() == RESERVED_CHANNELS + 5
    assert GameAudio._steal_oldest is True


def test_configure_sfx_rejects_bad_values():
    with pytest.raises(ValueError):
        GameAudio.configure_sfx(channels=0)
    with pytest.raises(ValueError):
        GameAudio.configure_sfx(max_copies_per_sound=-1)


# ── play_sfx: every channel busy ──────────────────────────────────────


def test_all_busy_drops_the_new_sound_by_default(
    long_sound_path, other_long_sound_path
):
    GameAudio.configure_sfx(channels=3)
    for _ in range(3):
        GameAudio.play_sfx(long_sound_path)

    assert GameAudio.play_sfx(other_long_sound_path) is None

    for i in _pool():
        assert mixer.Channel(i).get_sound() is GameAudio._load(long_sound_path)


def test_all_busy_with_steal_oldest_replaces_the_oldest_sfx(
    long_sound_path, other_long_sound_path
):
    GameAudio.configure_sfx(channels=3, steal_oldest=True)
    for _ in range(3):
        GameAudio.play_sfx(long_sound_path)
    oldest = RESERVED_CHANNELS  # the first one played

    channel = GameAudio.play_sfx(other_long_sound_path)

    assert channel is not None
    assert mixer.Channel(oldest).get_sound() is GameAudio._load(other_long_sound_path)
    # The two younger ones keep playing.
    for i in (oldest + 1, oldest + 2):
        assert mixer.Channel(i).get_sound() is GameAudio._load(long_sound_path)


def test_all_busy_steals_the_oldest_after_wrapping_round(
    long_sound_path, other_long_sound_path
):
    GameAudio.configure_sfx(channels=2, steal_oldest=True)
    GameAudio.play_sfx(long_sound_path)  # first pool channel
    GameAudio.play_sfx(long_sound_path)  # second
    GameAudio.play_sfx(other_long_sound_path)  # steals the first
    GameAudio.play_sfx(other_long_sound_path)  # steals the second
    GameAudio.play_sfx(long_sound_path)  # the first is the oldest again
    first, second = (
        mixer.Channel(RESERVED_CHANNELS),
        mixer.Channel(RESERVED_CHANNELS + 1),
    )
    assert first.get_sound() is GameAudio._load(long_sound_path)
    assert second.get_sound() is GameAudio._load(other_long_sound_path)


def test_all_busy_steals_a_sound_other_code_started_first(
    long_sound_path, other_long_sound_path
):
    GameAudio.configure_sfx(channels=2, steal_oldest=True)
    foreign = mixer.Sound(long_sound_path)
    mixer.Channel(RESERVED_CHANNELS + 1).play(foreign, loops=-1)
    GameAudio.play_sfx(other_long_sound_path)  # takes the free channel
    GameAudio.play_sfx(other_long_sound_path)  # pool full: steals the foreign one
    assert mixer.Channel(RESERVED_CHANNELS + 1).get_sound() is not foreign
    assert mixer.Channel(RESERVED_CHANNELS).get_busy() is True


def test_all_busy_with_steal_oldest_off_drops_the_new_sound(
    long_sound_path, other_long_sound_path
):
    GameAudio.configure_sfx(steal_oldest=True)
    GameAudio.configure_sfx(steal_oldest=False)  # back to the default
    filler = mixer.Sound(long_sound_path)
    for i in _pool():
        mixer.Channel(i).play(filler, loops=-1)

    assert GameAudio.play_sfx(other_long_sound_path) is None

    for i in _pool():
        assert mixer.Channel(i).get_sound() is filler


# ── play_sfx: per-sound limit ─────────────────────────────────────────


def test_no_per_sound_limit_by_default(long_sound_path):
    for _ in range(5):
        GameAudio.play_sfx(long_sound_path)
    assert len(_busy_pool_channels()) == 5


def test_per_sound_limit_with_steal_oldest_restarts_the_oldest_copy(
    long_sound_path, other_long_sound_path
):
    GameAudio.configure_sfx(max_copies_per_sound=2, steal_oldest=True)
    first = GameAudio.play_sfx(long_sound_path)
    other = GameAudio.play_sfx(other_long_sound_path)
    GameAudio.play_sfx(long_sound_path)

    restarted = GameAudio.play_sfx(long_sound_path)

    assert restarted.id == first.id  # the oldest copy's channel
    assert len(_busy_pool_channels()) == 3  # still two copies + the other
    assert other.get_sound() is GameAudio._load(other_long_sound_path)


def test_per_sound_limit_drops_extra_copies_by_default(
    long_sound_path, other_long_sound_path
):
    GameAudio.configure_sfx(max_copies_per_sound=2)
    GameAudio.play_sfx(long_sound_path)
    GameAudio.play_sfx(long_sound_path)

    assert GameAudio.play_sfx(long_sound_path) is None
    assert GameAudio.play_sfx(other_long_sound_path) is not None  # others still play
    assert len(_busy_pool_channels()) == 3


def test_per_sound_limit_zero_turns_it_off_again(long_sound_path):
    GameAudio.configure_sfx(max_copies_per_sound=1)
    GameAudio.configure_sfx(max_copies_per_sound=0)
    for _ in range(3):
        GameAudio.play_sfx(long_sound_path)
    assert len(_busy_pool_channels()) == 3


# ── volume ──────────────────────────────────────────────────────────────
#
# SDL's mixer stores channel volume in a quantized (roughly 1/128-step) form,
# not a raw float -- set_volume(0.3) reads back as ~0.296875, not exactly 0.3.
# All channel-volume assertions below use a generous absolute tolerance for
# this reason rather than picking only "safe" values that happen to land
# exactly on a quantization step.


def test_set_music_volume_is_reflected_by_music_volume():
    audio = GameAudio()
    audio.set_music_volume(0.5)
    assert GameAudio.music_volume() == pytest.approx(0.5, abs=0.01)


def test_set_sfx_volume_is_reflected_by_sfx_volume():
    audio = GameAudio()
    audio.set_sfx_volume(0.3)
    assert GameAudio.sfx_volume() == pytest.approx(0.3, abs=0.01)


def test_sfx_volume_is_callable_from_an_instance_as_a_getter():
    """Chokepoint hands `audio.sfx_volume` to its life-lost bell as a getter."""
    audio = GameAudio()
    getter = audio.sfx_volume
    audio.set_sfx_volume(0.7)
    assert getter() == pytest.approx(0.7)


def test_set_music_volume_clamps_above_one():
    audio = GameAudio()
    audio.set_music_volume(5.0)
    assert GameAudio.music_volume() == pytest.approx(1.0, abs=0.01)


def test_set_music_volume_clamps_below_zero():
    audio = GameAudio()
    audio.set_music_volume(-5.0)
    assert GameAudio.music_volume() == pytest.approx(0.0, abs=0.01)


def test_setting_music_volume_does_not_affect_sfx_volume():
    audio = GameAudio()
    audio.set_sfx_volume(1.0)
    audio.set_music_volume(0.2)
    assert GameAudio.sfx_volume() == pytest.approx(1.0, abs=0.01)


def test_set_sfx_volume_clamps_to_valid_range():
    audio = GameAudio()
    audio.set_sfx_volume(5.0)
    assert GameAudio.sfx_volume() == 1.0
    audio.set_sfx_volume(-5.0)
    assert GameAudio.sfx_volume() == 0.0


def test_play_sfx_plays_at_the_sfx_volume(long_sound_path):
    GameAudio().set_sfx_volume(0.25)
    channel = GameAudio.play_sfx(long_sound_path)
    assert channel.get_volume() == pytest.approx(0.25, abs=0.01)


def test_set_sfx_volume_applies_to_sfx_already_playing(
    long_sound_path, other_long_sound_path
):
    first = GameAudio.play_sfx(long_sound_path)
    second = GameAudio.play_sfx(other_long_sound_path)

    GameAudio().set_sfx_volume(0.4)

    assert first.get_volume() == pytest.approx(0.4, abs=0.01)
    assert second.get_volume() == pytest.approx(0.4, abs=0.01)


def test_set_sfx_volume_covers_every_pool_channel():
    GameAudio().set_sfx_volume(0.6)
    for i in _pool():
        assert mixer.Channel(i).get_volume() == pytest.approx(0.6, abs=0.01)


def test_set_sfx_volume_keeps_the_old_sfx_channel_in_step():
    GameAudio().set_sfx_volume(0.6)
    assert SoundManager.get_volume(SFX_CHANNEL) == pytest.approx(0.6, abs=0.01)


def test_sfx_volume_does_not_change_the_music_volume(
    long_sound_path, other_long_sound_path
):
    audio = GameAudio()
    audio.set_music_volume(0.8)
    audio.play_music(long_sound_path)
    audio.set_sfx_volume(0.1)
    GameAudio.play_sfx(other_long_sound_path)
    assert GameAudio.music_volume() == pytest.approx(0.8, abs=0.01)


def test_sfx_volume_does_not_touch_a_game_owned_channel():
    mixer.Channel(GAME_OWNED_CHANNEL).set_volume(0.9)
    GameAudio().set_sfx_volume(0.2)
    assert mixer.Channel(GAME_OWNED_CHANNEL).get_volume() == pytest.approx(
        0.9, abs=0.01
    )


def test_music_volume_does_not_change_sfx_already_playing(long_sound_path):
    audio = GameAudio()
    audio.set_sfx_volume(0.5)
    channel = GameAudio.play_sfx(long_sound_path)
    audio.set_music_volume(0.1)
    assert channel.get_volume() == pytest.approx(0.5, abs=0.01)


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
    doesn't collide with GameAudio's music(0) channel must not affect it."""
    SoundManager.play_sound(OTHER_CHANNEL_A, sound_path)
    assert mixer.Channel(MUSIC_CHANNEL).get_busy() is False
    assert mixer.Channel(SFX_CHANNEL).get_busy() is False


def test_sound_manager_pause_then_unpause_round_trips_playback(sound_path):
    SoundManager.play_sound(OTHER_CHANNEL_A, sound_path, loops=-1)
    SoundManager.pause(OTHER_CHANNEL_A)
    assert mixer.Channel(OTHER_CHANNEL_A).get_busy() is True  # paused, not stopped

    SoundManager.unpause(OTHER_CHANNEL_A)
    assert mixer.Channel(OTHER_CHANNEL_A).get_busy() is True
