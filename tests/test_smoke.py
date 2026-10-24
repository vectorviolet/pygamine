"""Unit tests for pygamine.devtools.smoke.run_briefly: drives an Application's
real run() -- splash, any run() override, main loop -- for a few frames,
the path host projects' smoke tests otherwise never exercise.
"""
from __future__ import annotations

import pygame
import pytest

from pygamine.app.application import Application
from pygamine.app.splash_screen import ImageMedia, SplashScreen
from pygamine.devtools.smoke import run_briefly


@pytest.fixture(autouse=True)
def display():
    pygame.display.set_mode((1, 1))  # ImageMedia's convert_alpha() needs a display mode set


def _logo(tmp_path, name):
    path = tmp_path / f"{name}.png"
    pygame.image.save(pygame.Surface((8, 4)), str(path))
    return ImageMedia(path)


class CountingApp(Application):
    def __init__(self, splash_items=None, skip_completely=False):
        super().__init__(size=(320, 240), title="Smoke", fps=0)
        self.updates = 0
        if splash_items is not None:
            self.splash = SplashScreen(splash_items, skip_completely=skip_completely)

    def update(self) -> None:
        self.updates += 1


class SplashTwiceApp(CountingApp):
    """highrise's pattern: show the splash itself, then Application.run(),
    which shows it again."""

    def run(self) -> None:
        self.show_splash()
        super().run()


class NeverEndingMedia:
    """A splash item that ignores skips and never finishes."""

    def fit(self, target_size): ...
    def update(self): ...
    def draw(self, surface): ...
    def is_finished(self): return False
    def skip(self): ...


def test_runs_every_splash_item_then_the_requested_frames(tmp_path):
    app = CountingApp([_logo(tmp_path, "a"), _logo(tmp_path, "b")])

    assert run_briefly(app, frames=5) == 5

    assert app.splash.is_done
    assert app.updates == 5


def test_works_without_a_splash():
    app = CountingApp()
    assert run_briefly(app, frames=3) == 3


def test_survives_a_run_override_that_shows_the_splash_twice(tmp_path):
    """Exactly the startup crash this helper exists to catch."""
    app = SplashTwiceApp([_logo(tmp_path, "logo")], skip_completely=True)
    assert run_briefly(app, frames=3) == 3


def test_restores_event_polling_clock_and_update_afterwards(tmp_path):
    real_get, real_ticks = pygame.event.get, pygame.time.get_ticks
    app = CountingApp([_logo(tmp_path, "logo")])

    run_briefly(app, frames=2)

    assert pygame.event.get is real_get
    assert pygame.time.get_ticks is real_ticks
    assert "update" not in vars(app)  # the class method shows through again


def test_errors_propagate_and_still_restore_state(tmp_path):
    real_get = pygame.event.get

    class Crashing(CountingApp):
        def update(self) -> None:
            raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        run_briefly(Crashing([_logo(tmp_path, "logo")]), frames=3)
    assert pygame.event.get is real_get


def test_plays_the_splash_through_rather_than_skipping_it(tmp_path):
    """Each 2.5 s logo must finish on its own, fast -- not via a skip."""
    first, second = _logo(tmp_path, "a"), _logo(tmp_path, "b")
    skipped = []
    for media in (first, second):
        media.skip = lambda m=media: skipped.append(m)

    run_briefly(CountingApp([first, second]), frames=1)

    assert skipped == []
    assert first.is_finished() and second.is_finished()


def test_a_splash_that_never_ends_fails_instead_of_hanging():
    app = CountingApp([NeverEndingMedia()])
    with pytest.raises(RuntimeError, match="didn't finish"):
        run_briefly(app, frames=3, timeout_s=0.2)
