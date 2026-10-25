"""Shared pytest setup and fixtures for the test suite."""

from __future__ import annotations

import os
import socket
import sys

# Several modules call pygame.init() (e.g. SpatialGrid's Rect-based tests
# construct pygame objects); the dummy SDL video driver lets that run headless
# (e.g. in CI) without opening a real window. Must be set before pygame is
# imported anywhere.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
# Application.init_pygame() also calls mixer.init(); dummy audio avoids
# probing for a real sound device on headless CI runners.
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

# Make the helper module in this directory importable as `import _util`.
sys.path.insert(0, os.path.dirname(__file__))

import pygame
import pytest

# GameObject.invoke/_tick_scheduled and Animator both call pygame.time.get_ticks(),
# which works pre-init (returns 0) but only actually advances once pygame is
# initialized. Tests that need controlled timing monkeypatch get_ticks anyway,
# but this keeps ticks meaningful in any test that reads real time.
pygame.init()


@pytest.fixture
def fake_ticks(monkeypatch):
    """A controllable stand-in for pygame.time.get_ticks().

    Returns a dict; set fake_ticks["t"] = <ms> to move the clock without
    real sleeps, for deterministic tests of invoke/invoke_repeating/Animator.
    """
    state = {"t": 0}
    monkeypatch.setattr(pygame.time, "get_ticks", lambda: state["t"])
    return state


@pytest.fixture
def free_port() -> int:
    """A currently-free TCP port on loopback.

    We bind to port 0 (OS picks a free one), read it back, then release it so
    the test's server can bind it. Using ephemeral ports means tests never
    collide and there is no hardcoded port to clash with a running game.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port
