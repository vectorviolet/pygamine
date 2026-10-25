"""Unit tests for Animator: clip playback, frame stepping, and the
lag-resume behaviour that keeps a reopened panel from snapping straight to
a non-looping clip's last frame.

All timing is driven through the fake_ticks fixture (patches
pygame.time.get_ticks) so tests are instant and deterministic instead of
depending on real sleeps.
"""

from __future__ import annotations

import pygame
import pytest

from pygamine.ecs.components.animator import Animator, AnimationClip
from pygamine.ecs.components.sprite_renderer2d import SpriteRenderer2D
from pygamine.ecs.game_object import GameObject


def _frames(n):
    return [pygame.Surface((2, 2)) for _ in range(n)]


def _rigged_animator():
    """A GameObject with both SpriteRenderer2D and Animator, matching how
    AnimatedSprite wires them -- Animator._apply() looks up the renderer via
    get_component()."""
    go = GameObject()
    renderer = go.add_component(SpriteRenderer2D)
    animator = go.add_component(Animator)
    return animator, renderer


# ── AnimationClip ────────────────────────────────────────────────────────


def test_animation_clip_rejects_non_positive_fps():
    with pytest.raises(ValueError):
        AnimationClip(_frames(2), fps=0)
    with pytest.raises(ValueError):
        AnimationClip(_frames(2), fps=-5)


def test_animation_clip_frame_duration_ms():
    assert AnimationClip(_frames(2), fps=10).frame_duration_ms == 100
    assert AnimationClip(_frames(2), fps=25).frame_duration_ms == 40


# ── play / stop ────────────────────────────────────────────────────────


def test_play_starts_clip_and_applies_first_frame(fake_ticks):
    animator, renderer = _rigged_animator()
    frames = _frames(3)
    animator.add_clip("walk", AnimationClip(frames, fps=10))

    animator.play("walk")

    assert animator.is_playing
    assert animator.current_clip == "walk"
    assert renderer.image is frames[0]


def test_play_unknown_clip_name_is_a_no_op():
    animator, _ = _rigged_animator()
    animator.play("nonexistent")
    assert not animator.is_playing
    assert animator.current_clip is None


def test_play_clip_with_no_frames_is_a_no_op():
    animator, _ = _rigged_animator()
    animator.add_clip("empty", AnimationClip([], fps=10))
    animator.play("empty")
    assert not animator.is_playing


def test_replaying_same_clip_without_restart_preserves_frame(fake_ticks):
    animator, renderer = _rigged_animator()
    frames = _frames(3)
    animator.add_clip("walk", AnimationClip(frames, fps=10))
    animator.play("walk")

    fake_ticks["t"] = 100
    animator.update()
    assert renderer.image is frames[1]

    animator.play("walk")  # same clip, already playing, no restart requested
    assert renderer.image is frames[1]  # frame preserved, not reset to 0


def test_replaying_same_clip_with_restart_resets_frame(fake_ticks):
    animator, renderer = _rigged_animator()
    frames = _frames(3)
    animator.add_clip("walk", AnimationClip(frames, fps=10))
    animator.play("walk")
    fake_ticks["t"] = 100
    animator.update()
    assert renderer.image is frames[1]

    animator.play("walk", restart=True)
    assert renderer.image is frames[0]


def test_stop_halts_playback_and_resets_frame(fake_ticks):
    animator, renderer = _rigged_animator()
    frames = _frames(3)
    animator.add_clip("walk", AnimationClip(frames, fps=10))
    animator.play("walk")
    fake_ticks["t"] = 100
    animator.update()

    animator.stop()

    assert not animator.is_playing
    # stop() doesn't re-apply the frame to the renderer, only internal state:
    animator.play("walk")
    assert renderer.image is frames[0]


# ── update() frame stepping ────────────────────────────────────────────


def test_update_does_nothing_before_a_frame_duration_elapses(fake_ticks):
    animator, renderer = _rigged_animator()
    frames = _frames(3)
    animator.add_clip("walk", AnimationClip(frames, fps=10))  # 100ms/frame
    animator.play("walk")

    fake_ticks["t"] = 50
    animator.update()

    assert renderer.image is frames[0]


def test_update_advances_one_frame_after_one_duration(fake_ticks):
    animator, renderer = _rigged_animator()
    frames = _frames(3)
    animator.add_clip("walk", AnimationClip(frames, fps=10))
    animator.play("walk")

    fake_ticks["t"] = 100
    animator.update()

    assert renderer.image is frames[1]


def test_update_advances_multiple_frames_in_a_single_call(fake_ticks):
    """A big elapsed gap steps forward by (elapsed // duration), not just 1."""
    animator, renderer = _rigged_animator()
    frames = _frames(5)
    animator.add_clip("walk", AnimationClip(frames, fps=10))
    animator.play("walk")

    fake_ticks["t"] = 250  # 2 whole durations, not enough to trigger lag-resume
    animator.update()

    assert renderer.image is frames[2]


def test_looping_clip_wraps_around_past_the_last_frame(fake_ticks):
    animator, renderer = _rigged_animator()
    frames = _frames(3)
    animator.add_clip("walk", AnimationClip(frames, fps=10, loop=True))
    animator.play("walk")

    fake_ticks["t"] = 350  # 3 whole durations from frame 0: 0+3=3 -> wraps to 0
    animator.update()

    assert renderer.image is frames[0]
    assert animator.is_playing


def test_non_looping_clip_clamps_to_last_frame_and_stops(fake_ticks):
    animator, renderer = _rigged_animator()
    frames = _frames(3)
    animator.add_clip("walk", AnimationClip(frames, fps=10, loop=False))
    animator.play("walk")

    fake_ticks["t"] = 350  # would overshoot the last frame if looping
    animator.update()

    assert renderer.image is frames[2]
    assert not animator.is_playing


def test_large_gap_resumes_from_current_frame_instead_of_snapping_forward(fake_ticks):
    """If the animator was effectively paused (e.g. its panel was hidden) for
    longer than _RESUME_AFTER_LAG_FACTOR frame-durations, resume from the
    current frame rather than fast-forwarding -- otherwise returning to a
    panel after a few seconds would snap a non-looping clip straight to its
    last frame on the very next tick."""
    animator, renderer = _rigged_animator()
    frames = _frames(3)
    animator.add_clip("walk", AnimationClip(frames, fps=10, loop=False))  # 100ms/frame
    animator.play("walk")

    fake_ticks["t"] = 500  # 5 durations elapsed: over the 4x lag threshold
    animator.update()

    assert renderer.image is frames[0]  # unchanged, not fast-forwarded
    assert animator.is_playing  # not stopped either

    # And it resumes normal stepping from here rather than staying stuck:
    fake_ticks["t"] = 600
    animator.update()
    assert renderer.image is frames[1]


def test_update_is_a_no_op_when_not_playing(fake_ticks):
    animator, renderer = _rigged_animator()
    frames = _frames(3)
    animator.add_clip("walk", AnimationClip(frames, fps=10))
    # never played
    fake_ticks["t"] = 1000
    animator.update()
    assert renderer.image is None


def test_update_never_advances_when_frame_duration_rounds_to_zero(fake_ticks):
    """fps high enough that int(1000/fps) == 0 must not advance forever
    (and must not divide-by-zero or loop infinitely)."""
    animator, renderer = _rigged_animator()
    frames = _frames(3)
    animator.add_clip("fast", AnimationClip(frames, fps=2000))
    animator.play("fast")

    fake_ticks["t"] = 10_000
    animator.update()

    assert renderer.image is frames[0]
