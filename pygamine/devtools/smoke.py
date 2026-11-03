"""Drives an Application through its real startup path, for host projects'
headless smoke tests.

Building a Game() and rendering its panels doesn't exercise run(): the
splash, a project's own run() override, and the hand-off into the main
loop. That gap hid a startup crash (highrise's run() showed the splash and
then Application.run() showed it again, which raised IndexError) from CI
while every launch of the real game hit it. run_briefly() calls the real
run() instead:

    from pygamine.devtools.smoke import run_briefly
    run_briefly(Game())

Run headless (SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy), like the rest
of a smoke test.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pygame


def _splash_running(app) -> bool:
    splash = getattr(app, "splash", None)
    return splash is not None and not splash.is_done


@contextmanager
def _fast_forward_splash(
    app, step_ms: int, deadline: float, timeout_message: str
) -> Iterator[None]:
    """While the splash is on screen, jumps pygame's clock `step_ms` ahead on
    every event poll; raises RuntimeError(`timeout_message`) from an event
    poll once time.monotonic() passes `deadline`. The clock stays monotonic:
    the offset gained is kept, and both functions are restored on exit."""
    real_get = pygame.event.get
    real_ticks = pygame.time.get_ticks
    offset_ms = 0

    def ticks() -> int:
        return real_ticks() + offset_ms

    def get_events(*args: Any, **kwargs: Any) -> list[pygame.event.Event]:
        nonlocal offset_ms
        if time.monotonic() > deadline:
            raise RuntimeError(timeout_message)
        if _splash_running(app):
            offset_ms += step_ms
        return real_get(*args, **kwargs)

    pygame.event.get = get_events
    pygame.time.get_ticks = ticks
    try:
        yield
    finally:
        pygame.event.get = real_get
        pygame.time.get_ticks = real_ticks


class _FrameCounter:
    """Counts `app.update()` calls and stops the app's loop after `frames`."""

    def __init__(self, app, frames: int) -> None:
        self.count = 0
        self._app = app
        self._frames = frames

    @contextmanager
    def installed(self) -> Iterator[None]:
        real_update = self._app.update  # bound, so a project's own override is kept

        def update_then_count() -> None:
            real_update()
            self.count += 1
            if self.count >= self._frames:
                self._app._is_running = False

        self._app.update = update_then_count
        try:
            yield
        finally:
            # drop the instance attribute; the class method shows through again
            del self._app.update


def run_briefly(
    app, frames: int = 30, timeout_s: float = 30.0, splash_step_ms: int = 250
) -> int:
    """Runs `app.run()` -- splash included -- for `frames` main-loop frames,
    then stops the loop (without sys.exit). Returns the frames run.

    The splash isn't skipped: while it's on screen, pygame's clock jumps
    `splash_step_ms` ahead on every event poll, so each item plays through
    to its natural end in a fraction of a second (a 10 s clip in ~40
    frames). Skipping would hide bugs that only follow a splash that ran to
    completion -- like the second-run crash above, which a click-skipped
    skip_completely splash never reaches. The clock stays monotonic: the
    offset gained during the splash is kept, never taken back.

    Raises RuntimeError if the splash or the loop hasn't finished within
    timeout_s, so a hang fails CI instead of stalling it.
    """
    counter = _FrameCounter(app, frames)
    timeout_message = (
        f"app didn't finish its splash and {frames} frames within {timeout_s}s"
    )
    with (
        _fast_forward_splash(
            app, splash_step_ms, time.monotonic() + timeout_s, timeout_message
        ),
        counter.installed(),
    ):
        app.run()

    if _splash_running(app):
        raise RuntimeError("run() returned before the splash finished")
    if counter.count < frames:
        raise RuntimeError(
            f"main loop stopped after {counter.count} of {frames} frames"
        )
    return counter.count
