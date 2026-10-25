"""Unit tests for Rigidbody2D: velocity-based movement via a float-position
accumulator (so slow/fractional velocities don't get truncated to zero every
frame)."""

from __future__ import annotations

from pygame import Vector2

from pygamine.ecs.components.rigidbody2d import Rigidbody2D
from pygamine.ecs.game_object import GameObject


def test_zero_velocity_update_is_a_no_op():
    go = GameObject()
    rb = go.add_component(Rigidbody2D)
    go.rect.topleft = (10, 10)

    rb.update()

    assert go.rect.topleft == (10, 10)
    assert rb._float_pos is None


def test_nonzero_velocity_moves_transform_each_update():
    go = GameObject()
    rb = go.add_component(Rigidbody2D)
    rb.set_velocity((5, 0))

    rb.update()

    assert go.rect.topleft == (5, 0)


def test_fractional_velocity_accumulates_instead_of_truncating_every_frame():
    """The whole point of _float_pos: a 0.5px/frame velocity must still move
    the object 1px after 2 frames, not get rounded to 0 every single frame."""
    go = GameObject()
    rb = go.add_component(Rigidbody2D)
    rb.set_velocity((0.5, 0))

    rb.update()
    assert go.rect.topleft == (0, 0)  # round(0.5) == 0 on the first frame

    rb.update()
    assert go.rect.topleft == (1, 0)  # accumulated float pos is now 1.0


def test_set_velocity_resyncs_float_pos_from_current_transform():
    go = GameObject()
    rb = go.add_component(Rigidbody2D)
    rb.set_velocity((10, 0))
    rb.update()
    assert go.rect.topleft == (10, 0)

    # Something else moved the object directly (e.g. a teleport); changing
    # velocity should re-anchor from the transform's new position, not the
    # stale float_pos.
    go.rect.topleft = (100, 100)
    rb.set_velocity((1, 1))
    assert rb._float_pos is None

    rb.update()
    assert go.rect.topleft == (101, 101)


def test_set_velocity_accepts_tuple_or_vector2():
    go = GameObject()
    rb = go.add_component(Rigidbody2D)
    rb.set_velocity((3, 4))
    assert rb.velocity == Vector2(3, 4)
