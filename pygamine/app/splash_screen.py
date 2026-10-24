from __future__ import annotations

import os
import queue
import threading
from pathlib import Path
from typing import Protocol, Union

import pygame

from pygamine.assets.asset_path import SequencePath
from pygamine.ecs.game_audio import GameAudio

PathArg = Union[str, "os.PathLike[str]"]

DEFAULT_SEQUENCE_FPS = 30.0

# The shared splash assets every game opens with. Resolved next to this
# package rather than a game's cwd-relative assets/, so one copy serves
# every consumer; a frozen build must bundle this folder as
# "pygamine/branding" (see standard_splash_media()).
BRANDING_DIR = Path(__file__).resolve().parent.parent / "branding"


class SplashMedia(Protocol):
    """One item of a SplashScreen sequence. `fit()` is called once, right
    before the item is shown, with the screen size; it starts the item's
    clock (and audio, if any)."""

    def fit(self, target_size: tuple[int, int]) -> None: ...

    def update(self) -> None: ...

    def draw(self, surface: pygame.Surface) -> None: ...

    def is_finished(self) -> bool: ...

    def skip(self) -> None: ...


class ImageMedia:
    """A single image, scaled to fit the screen, faded in over `fade_ms`
    then held for `hold_ms`."""

    def __init__(
        self, image_path: PathArg, fade_ms: int = 1500, hold_ms: int = 1000
    ) -> None:
        self._original_image = pygame.image.load(image_path).convert_alpha()
        self._image = self._original_image
        self._fade_ms = fade_ms
        self._hold_ms = hold_ms
        self._start_time: int | None = None
        self._current_alpha = 0
        self._finished = False

    def fit(self, target_size: tuple[int, int]) -> None:
        tw, th = target_size
        iw, ih = self._original_image.get_size()
        scale = min(tw / iw, th / ih)
        new_size = (int(iw * scale), int(ih * scale))
        self._image = pygame.transform.smoothscale(self._original_image, new_size)
        self._start_time = pygame.time.get_ticks()

    def update(self) -> None:
        if self._finished or self._start_time is None:
            return

        elapsed = pygame.time.get_ticks() - self._start_time

        if elapsed >= self._fade_ms + self._hold_ms:
            self._finished = True
            return

        self._current_alpha = (
            255 if elapsed >= self._fade_ms else int(255 * elapsed / self._fade_ms)
        )

    def draw(self, surface: pygame.Surface) -> None:
        if self._finished:
            return
        frame = self._image.copy()
        frame.fill(
            (255, 255, 255, self._current_alpha), special_flags=pygame.BLEND_RGBA_MULT
        )
        rect = frame.get_rect(center=surface.get_rect().center)
        surface.blit(frame, rect)

    def is_finished(self) -> bool:
        return self._finished

    def skip(self) -> None:
        self._finished = True


class ImageSequenceMedia:
    """Plays a folder of numbered frames as a video, with optional audio.

    `folder_path` is a SequencePath (frames of its `extension`) or a plain
    folder of .jpg frames. The frame rate is, in order: the `fps` argument,
    the `fps` key of a `meta.yaml` in the folder (written by the mp4
    converter), else DEFAULT_SEQUENCE_FPS. It must match the source video,
    or the picture drifts from the audio and ends early or late.

    Frames are loaded and scaled on a background thread into a small bounded
    queue, so playback starts at once and memory stays flat. The frame shown
    is derived from the time elapsed since fit(), not counted per update(),
    so playback stays in sync with the audio: a frame the loader hasn't
    delivered in time is dropped rather than delaying everything after it.
    """

    _BUFFER_FRAMES = 30
    _PUT_TIMEOUT_S = 0.05

    def __init__(self, folder_path, fps: float | None = None, audio_path=None, audio_manager=None) -> None:
        self._folder = Path(str(folder_path))
        self._fps = fps if fps is not None else self._read_meta_fps(self._folder) or DEFAULT_SEQUENCE_FPS
        self._audio_path = str(audio_path) if audio_path else None
        self._audio = audio_manager

        if isinstance(folder_path, SequencePath):
            self._frame_paths = folder_path.frame_paths()
        else:
            self._frame_paths = sorted(self._folder.glob("*.jpg"))
        self._total_frames = len(self._frame_paths)

        self._frame_queue: queue.Queue[tuple[int, pygame.Surface]] = queue.Queue(maxsize=self._BUFFER_FRAMES)
        self._stop_event = threading.Event()
        self._loader: threading.Thread | None = None

        self._start_time: int | None = None
        self._shown_frame_idx = -1
        self._finished = self._total_frames == 0
        self._current_surface: pygame.Surface | None = None
        self._target_size: tuple[int, int] | None = None

    @staticmethod
    def _read_meta_fps(folder: Path) -> float | None:
        meta_path = folder / "meta.yaml"
        if not meta_path.is_file():
            return None
        import yaml  # deferred like the package's other optional-subsystem imports

        meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
        fps = meta.get("fps")
        return float(fps) if fps else None

    def fit(self, target_size: tuple[int, int]) -> None:
        if self._finished or self._loader is not None:
            return
        self._target_size = target_size
        self._start_time = pygame.time.get_ticks()

        self._loader = threading.Thread(target=self._preload_frames, daemon=True)
        self._loader.start()

        if self._audio and self._audio_path:
            self._audio.play_music(self._audio_path, loops=0)

    def _preload_frames(self) -> None:
        # Runs on the loader thread. A load error isn't caught: it surfaces
        # through threading's excepthook, and playback still ends on time.
        try:
            for idx, path in enumerate(self._frame_paths):
                if self._stop_event.is_set():
                    return
                img = pygame.image.load(str(path))
                if self._target_size:
                    tw, th = self._target_size
                    iw, ih = img.get_size()
                    scale = min(tw / iw, th / ih)
                    new_size = (int(iw * scale), int(ih * scale))
                    if new_size != (iw, ih):
                        img = pygame.transform.smoothscale(img, new_size)
                if not self._put_frame(idx, img):
                    return
        finally:
            # _stop()'s drain frees buffer space, which can let a put() already
            # in flight land afterwards -- so drain again on the way out
            if self._stop_event.is_set():
                self._drain_queue()

    def _put_frame(self, idx: int, img: pygame.Surface) -> bool:
        """Blocks while the buffer is full, but never past a stop request --
        a plain blocking put() would hang this thread forever once playback
        stops consuming. Returns False if stopped."""
        while not self._stop_event.is_set():
            try:
                self._frame_queue.put((idx, img), timeout=self._PUT_TIMEOUT_S)
                return True
            except queue.Full:
                continue
        return False

    def _due_frame_idx(self, start_time: int) -> int:
        elapsed = pygame.time.get_ticks() - start_time
        return int(elapsed * self._fps / 1000)

    def update(self) -> None:
        if self._finished or self._start_time is None:
            return

        due_idx = self._due_frame_idx(self._start_time)
        if due_idx >= self._total_frames:
            self._stop()
            return

        # Pull frames up to the one that's due, keeping only the newest; late
        # frames are dropped. Frames arrive in order, so this never consumes
        # one that isn't due yet.
        newest = None
        while self._shown_frame_idx < due_idx:
            try:
                self._shown_frame_idx, newest = self._frame_queue.get_nowait()
            except queue.Empty:
                break
        if newest is not None:
            # convert_alpha() needs the display, so it stays on the main thread
            self._current_surface = newest.convert_alpha()

    def draw(self, surface: pygame.Surface) -> None:
        if self._finished or self._current_surface is None:
            return
        rect = self._current_surface.get_rect(center=surface.get_rect().center)
        surface.blit(self._current_surface, rect)

    def is_finished(self) -> bool:
        return self._finished

    def skip(self) -> None:
        self._stop()

    def _stop(self) -> None:
        if self._finished:
            return
        self._finished = True
        self._stop_event.set()
        self._stop_audio()
        self._current_surface = None
        # Release buffered surfaces; the loader exits within _PUT_TIMEOUT_S
        self._drain_queue()

    def _drain_queue(self) -> None:
        while True:
            try:
                self._frame_queue.get_nowait()
            except queue.Empty:
                break

    def _stop_audio(self) -> None:
        # Stop, not pause: a paused channel stays occupied, and nothing
        # would ever resume this clip's audio.
        if self._audio and self._audio_path:
            self._audio.stop_music()


def standard_splash_media(audio_manager: GameAudio | None = None) -> list[SplashMedia]:
    """The splash every game opens with: the publisher clip (with its
    audio), then the pygame logo -- so it stays identical across projects
    and changes in one place. Append a game's own items after it, e.g.
    `SplashScreen([*standard_splash_media(self.audio), title_card])`.

    Pass the game's GameAudio so the clip plays at its music volume; without
    one it plays through a GameAudio of its own. Either way the clip stops
    its audio when it ends, so start a game's music after the splash.

    A frozen (PyInstaller) build must bundle BRANDING_DIR as data, e.g.
    `(str(ROOT / "src/pygamine/pygamine/branding"), "pygamine/branding")`.
    """
    return [
        ImageSequenceMedia(
            BRANDING_DIR / "publisher_splash",
            audio_path=BRANDING_DIR / "publisher_splash.ogg",
            audio_manager=audio_manager if audio_manager is not None else GameAudio(),
        ),
        ImageMedia(BRANDING_DIR / "pygame_logo.png"),
    ]


class SplashScreen:
    """Plays a sequence of SplashMedia items (images, image sequences, ...).

    Advances to the next item when the current one finishes, or skips it on
    any mouse click or Space/Enter/Escape. With `skip_completely`, a skip
    ends the whole splash instead of just the current item. When the last
    item is done, is_done = True.
    """

    SKIP_KEYS = [pygame.K_SPACE, pygame.K_RETURN, pygame.K_ESCAPE]

    def __init__(self, media_items: list[SplashMedia], skip_completely: bool = False) -> None:
        self._media_items = media_items
        self._index = 0
        self.is_done = False
        self.skip_completely = skip_completely

    def run(self, surface: pygame.Surface, clock: pygame.time.Clock, fps: int) -> None:
        if not self._media_items:
            self.is_done = True
            return

        self._media_items[self._index].fit(surface.get_size())

        while not self.is_done:
            clock.tick(fps)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    raise SystemExit

                self.handle_event(event)

            self.update(surface.get_size())
            surface.fill((0, 0, 0))
            self.draw(surface)
            pygame.display.update()

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.should_skip(event):
            self.skip()

    def should_skip(self, event: pygame.event.Event) -> bool:
        return event.type == pygame.MOUSEBUTTONDOWN or (event.type == pygame.KEYDOWN and event.key in self.SKIP_KEYS)

    def skip(self) -> None:
        if self.is_done:
            return

        # Always stop the current media, so its audio and loader thread
        # don't outlive the splash when skipping it completely
        self._current_media.skip()
        if self.skip_completely:
            self.is_done = True

    @property
    def _current_media(self) -> SplashMedia:
        return self._media_items[self._index]

    def update(self, surface_size: tuple[int, int]) -> None:
        if self.is_done:
            return

        current = self._current_media
        current.update()

        if current.is_finished():
            self._index += 1
            if self._index < len(self._media_items):
                self._media_items[self._index].fit(surface_size)
            else:
                self.is_done = True

    def draw(self, surface: pygame.Surface) -> None:
        if self.is_done:
            return

        self._current_media.draw(surface)
