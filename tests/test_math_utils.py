"""Unit tests for math_utils: distance and angle helpers used throughout the
engine (camera follow, projectile aiming, AI steering)."""

from __future__ import annotations

import math

from pygame import Vector2

from pygamine.util.math_utils import (
    angle_of_delta,
    angle_between_points,
    clamp01,
    distance,
)


def test_distance_between_identical_points_is_zero():
    assert distance(Vector2(5, 5), Vector2(5, 5)) == 0


def test_distance_matches_pythagorean_triple():
    assert distance(Vector2(0, 0), Vector2(3, 4)) == 5


def test_angle_of_delta_right_is_zero_degrees():
    assert angle_of_delta(Vector2(1, 0)) == 0


def test_angle_of_delta_down_is_90_degrees():
    # pygame/screen space: +y points down, so "down" is +90 degrees here.
    assert angle_of_delta(Vector2(0, 1)) == 90


def test_angle_of_delta_left_is_180_degrees():
    assert abs(angle_of_delta(Vector2(-1, 0))) == 180


def test_angle_between_points_is_direction_from_origin_to_target():
    origin = Vector2(0, 0)
    target = Vector2(0, 10)
    assert angle_between_points(origin, target) == angle_of_delta(target - origin)


def test_angle_between_points_matches_known_45_degrees():
    origin = Vector2(0, 0)
    target = Vector2(10, 10)
    assert math.isclose(angle_between_points(origin, target), 45)


def test_clamp01_keeps_values_inside_the_range():
    assert clamp01(0.0) == 0.0
    assert clamp01(0.25) == 0.25
    assert clamp01(1.0) == 1.0


def test_clamp01_clamps_values_outside_the_range():
    assert clamp01(-0.5) == 0.0
    assert clamp01(1.5) == 1.0


def test_clamp01_is_exported_from_the_package():
    import pygamine

    assert pygamine.clamp01 is clamp01
