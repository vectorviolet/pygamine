"""Unit tests for SplashScreen, ImageMedia and ImageSequenceMedia:
- ImageMedia handles individual image fade-in/hold sequences.
- ImageSequenceMedia plays a folder of frames in sync with elapsed time.
- SplashScreen manages sequences of SplashMedia items (images/videos),
  advancing via elapsed time, clicks, or Space/Enter/Escape; with
  skip_completely, a skip ends the whole splash instead.
"""
from __future__ import annotations

import time

import pygame
import pytest

from pygamine.app.splash_screen import DEFAULT_SEQUENCE_FPS, ImageMedia, ImageSequenceMedia, SplashScreen
from pygamine.assets.asset_path import SequencePath


def _save_png(path, size, color):
    surf = pygame.Surface(size, pygame.SRCALPHA)
    surf.fill(color)
    pygame.image.save(surf, str(path))


@pytest.fixture
def image_paths(tmp_path):
    pygame.display.set_mode((1, 1))  # convert_alpha() needs a display mode set
    paths = []
    for i, color in enumerate([(255, 0, 0), (0, 255, 0), (0, 0, 255)]):
        path = tmp_path / f"img{i}.png"
        _save_png(path, (20, 10), color)
        paths.append(path)
    return paths


@pytest.fixture
def media_items(image_paths):
    return [ImageMedia(p, fade_ms=100, hold_ms=100) for p in image_paths]


# ── ImageMedia Tests ───────────────────────────────────────────────────


def test_image_media_construction(image_paths):
    media = ImageMedia(image_paths[0], fade_ms=200, hold_ms=100)
    assert media._fade_ms == 200
    assert media._hold_ms == 100
    assert media._finished is False
    assert media._start_time is None


def test_image_media_fit(image_paths):
    media = ImageMedia(image_paths[0])
    media.fit((100, 100))
    assert media._image.get_size() == (100, 50)
    assert media._start_time is not None


def test_image_media_update_fade_and_hold(image_paths, fake_ticks):
    media = ImageMedia(image_paths[0], fade_ms=100, hold_ms=100)
    fake_ticks["t"] = 0
    media.fit((20, 10))

    # Halfway through fade
    fake_ticks["t"] = 50
    media.update()
    assert media._current_alpha == 127
    assert media.is_finished() is False

    # Within hold
    fake_ticks["t"] = 150
    media.update()
    assert media._current_alpha == 255
    assert media.is_finished() is False

    # Past fade + hold
    fake_ticks["t"] = 250
    media.update()
    assert media.is_finished() is True


def test_image_media_skip(image_paths):
    media = ImageMedia(image_paths[0])
    media.fit((20, 10))
    assert media.is_finished() is False
    media.skip()
    assert media.is_finished() is True


def test_image_media_draw(image_paths):
    media = ImageMedia(image_paths[0])
    media.fit((20, 10))
    media._current_alpha = 255

    surface = pygame.Surface((20, 10))
    media.draw(surface)
    assert surface.get_at((10, 5)) == (255, 0, 0, 255)


# ── ImageSequenceMedia Tests ───────────────────────────────────────────


class FakeAudio:
    def __init__(self):
        self.played = []
        self.is_music_paused = False

    def play_music(self, path, loops=-1):
        self.played.append((path, loops))
        self.is_music_paused = False

    def pause_music(self):
        self.is_music_paused = True


@pytest.fixture
def frames_dir(tmp_path):
    pygame.display.set_mode((1, 1))  # convert_alpha() needs a display mode set
    folder = tmp_path / "frames"
    folder.mkdir()
    # Frame i is filled with red value i, so a drawn pixel identifies its frame
    for i in range(10):
        surf = pygame.Surface((20, 10))
        surf.fill((i * 20, 0, 0))
        pygame.image.save(surf, str(folder / f"{i + 1:04d}.jpg"))
    return folder


def _wait_for_buffer(media, count, timeout_s=2.0):
    """Waits until the loader thread has buffered `count` frames."""
    deadline = time.monotonic() + timeout_s
    while media._frame_queue.qsize() < count:
        assert time.monotonic() < deadline, "loader thread never buffered the frames"
        time.sleep(0.005)


def _shown_red(media):
    surface = pygame.Surface((20, 10))
    media.draw(surface)
    return surface.get_at((10, 5)).r


def test_image_sequence_finds_jpg_frames_in_order(frames_dir):
    media = ImageSequenceMedia(frames_dir)
    assert [p.name for p in media._frame_paths][:2] == ["0001.jpg", "0002.jpg"]
    assert media._total_frames == 10
    assert media.is_finished() is False


def test_image_sequence_empty_folder_is_finished(tmp_path):
    assert ImageSequenceMedia(tmp_path).is_finished() is True


def test_image_sequence_fps_defaults_without_meta(frames_dir):
    assert ImageSequenceMedia(frames_dir)._fps == DEFAULT_SEQUENCE_FPS


def test_image_sequence_fps_comes_from_meta_yaml(frames_dir):
    (frames_dir / "meta.yaml").write_text("fps: 24\nframe_count: 10\n")
    media = ImageSequenceMedia(frames_dir)
    assert media._fps == 24
    assert media._total_frames == 10  # meta.yaml isn't mistaken for a frame


def test_image_sequence_fps_argument_overrides_meta_yaml(frames_dir):
    (frames_dir / "meta.yaml").write_text("fps: 24\n")
    assert ImageSequenceMedia(frames_dir, fps=12)._fps == 12


def test_image_sequence_takes_frames_from_a_sequence_path(frames_dir, monkeypatch):
    monkeypatch.chdir(frames_dir.parent)
    png_folder = frames_dir.parent / "assets" / "images" / "intro"
    png_folder.mkdir(parents=True)
    for i in range(3):
        pygame.image.save(pygame.Surface((4, 4)), str(png_folder / f"{i + 1:04d}.png"))
    (png_folder / "meta.yaml").write_text("fps: 15\n")

    media = ImageSequenceMedia(SequencePath("intro", extension="png"))

    assert [p.name for p in media._frame_paths] == ["0001.png", "0002.png", "0003.png"]
    assert media._fps == 15


def test_image_sequence_frame_follows_elapsed_time(frames_dir, fake_ticks):
    media = ImageSequenceMedia(frames_dir, fps=10)  # one frame per 100 ms
    fake_ticks["t"] = 1000
    media.fit((20, 10))
    _wait_for_buffer(media, 10)

    fake_ticks["t"] = 1000
    media.update()
    assert media._shown_frame_idx == 0

    # Updates far apart must not slow playback: 350 ms in is frame 3,
    # even though update() only ran once since frame 0
    fake_ticks["t"] = 1350
    media.update()
    assert media._shown_frame_idx == 3
    assert abs(_shown_red(media) - 60) <= 8  # jpg is lossy
    media.skip()


def test_image_sequence_never_consumes_frames_ahead_of_time(frames_dir, fake_ticks):
    media = ImageSequenceMedia(frames_dir, fps=10)
    fake_ticks["t"] = 0
    media.fit((20, 10))
    _wait_for_buffer(media, 10)

    fake_ticks["t"] = 250
    media.update()
    assert media._shown_frame_idx == 2
    assert media._frame_queue.qsize() == 7  # frames 3..9 still buffered
    media.skip()


def test_image_sequence_finishes_on_time_and_stops_audio(frames_dir, fake_ticks):
    audio = FakeAudio()
    media = ImageSequenceMedia(frames_dir, fps=10, audio_path="intro.ogg", audio_manager=audio)
    fake_ticks["t"] = 0
    media.fit((20, 10))
    assert audio.played == [("intro.ogg", 0)]

    fake_ticks["t"] = 999
    media.update()
    assert media.is_finished() is False

    fake_ticks["t"] = 1000  # 10 frames at 10 fps
    media.update()
    assert media.is_finished() is True
    assert audio.is_music_paused is True
    media._loader.join(timeout=1)
    assert not media._loader.is_alive()


def test_image_sequence_skip_stops_loader_blocked_on_full_buffer(frames_dir, fake_ticks, monkeypatch):
    monkeypatch.setattr(ImageSequenceMedia, "_BUFFER_FRAMES", 2)
    audio = FakeAudio()
    media = ImageSequenceMedia(frames_dir, audio_path="intro.ogg", audio_manager=audio)
    fake_ticks["t"] = 0
    media.fit((20, 10))
    _wait_for_buffer(media, 2)  # buffer full: the loader is now waiting to put

    media.skip()

    media._loader.join(timeout=1)
    assert not media._loader.is_alive()
    assert media._frame_queue.empty()
    assert media.is_finished() is True
    assert audio.is_music_paused is True


# ── SplashScreen Tests ─────────────────────────────────────────────────


def test_splash_screen_construction(media_items):
    splash = SplashScreen(media_items)
    assert len(splash._media_items) == 3
    assert splash._index == 0
    assert splash.is_done is False


def test_splash_screen_empty():
    splash = SplashScreen([])
    surface = pygame.Surface((20, 10))
    clock = pygame.time.Clock()
    splash.run(surface, clock, fps=0)
    assert splash.is_done is True


def test_splash_screen_handle_event_skips_current(media_items):
    splash = SplashScreen(media_items)
    splash._media_items[0].fit((20, 10))

    splash.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1))
    assert splash._media_items[0].is_finished() is True


def test_splash_screen_update_advances_sequence(media_items, fake_ticks):
    splash = SplashScreen(media_items)
    surface_size = (20, 10)

    # Start first media
    splash._media_items[0].fit(surface_size)
    fake_ticks["t"] = 0

    # Finish first media
    fake_ticks["t"] = 300
    splash.update(surface_size)

    assert splash._index == 1
    assert splash.is_done is False


def test_splash_screen_completes_all(media_items, fake_ticks):
    splash = SplashScreen(media_items)
    surface_size = (20, 10)

    splash._media_items[0].fit(surface_size)

    for i in range(3):
        fake_ticks["t"] = (i + 1) * 300
        splash.update(surface_size)

    assert splash.is_done is True


def test_escape_skips_only_the_current_media(media_items):
    splash = SplashScreen(media_items)
    splash._media_items[0].fit((20, 10))

    splash.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    splash.update((20, 10))

    assert splash._media_items[0].is_finished() is True
    assert splash._index == 1
    assert splash.is_done is False


def test_escape_with_skip_completely_ends_the_splash(media_items):
    splash = SplashScreen(media_items, skip_completely=True)
    splash._media_items[0].fit((20, 10))

    splash.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))

    assert splash.is_done is True


def test_run_raises_systemexit_on_quit_event(media_items, monkeypatch):
    splash = SplashScreen(media_items)
    monkeypatch.setattr(pygame.event, "get", lambda: [pygame.event.Event(pygame.QUIT)])
    surface = pygame.Surface((20, 10))

    with pytest.raises(SystemExit):
        splash.run(surface, pygame.time.Clock(), fps=0)


def test_run_advances_through_all_media_via_click(media_items, monkeypatch):
    splash = SplashScreen(media_items)
    monkeypatch.setattr(
        pygame.event, "get", lambda: [pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1)]
    )
    surface = pygame.Surface((20, 10))

    splash.run(surface, pygame.time.Clock(), fps=0)

    assert splash.is_done is True

def test_skip_completely_stops_the_current_media(frames_dir, image_paths, fake_ticks):
    audio = FakeAudio()
    sequence = ImageSequenceMedia(frames_dir, audio_path="intro.ogg", audio_manager=audio)
    splash = SplashScreen([sequence, ImageMedia(image_paths[0])], skip_completely=True)
    sequence.fit((20, 10))

    splash.skip()

    assert splash.is_done is True
    assert sequence.is_finished() is True
    assert audio.is_music_paused is True
    sequence._loader.join(timeout=1)
    assert not sequence._loader.is_alive()
