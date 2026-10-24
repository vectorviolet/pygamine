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

import pygame


def run_briefly(app, frames: int = 30, timeout_s: float = 30.0, splash_step_ms: int = 250) -> int:
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
    real_get = pygame.event.get
    real_ticks = pygame.time.get_ticks
    deadline = time.monotonic() + timeout_s
    offset_ms = 0
    counted = 0

    def splash_running() -> bool:
        splash = getattr(app, "splash", None)
        return splash is not None and not splash.is_done

    def ticks() -> int:
        return real_ticks() + offset_ms

    def get_events(*args, **kwargs):
        nonlocal offset_ms
        if time.monotonic() > deadline:
            raise RuntimeError(f"app didn't finish its splash and {frames} frames within {timeout_s}s")
        if splash_running():
            offset_ms += splash_step_ms
        return real_get(*args, **kwargs)

    real_update = app.update  # the bound method, so a project's own override is kept

    def update_then_count() -> None:
        nonlocal counted
        real_update()
        counted += 1
        if counted >= frames:
            app._is_running = False

    pygame.event.get = get_events
    pygame.time.get_ticks = ticks
    app.update = update_then_count
    try:
        app.run()
    finally:
        pygame.event.get = real_get
        pygame.time.get_ticks = real_ticks
        del app.update  # drop the instance attribute; the class method shows through again

    if splash_running():
        raise RuntimeError("run() returned before the splash finished")
    if counted < frames:
        raise RuntimeError(f"main loop stopped after {counted} of {frames} frames")
    return counted
