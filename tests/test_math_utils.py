"""Unit tests for math_utils: distance and angle helpers used throughout the
engine (camera follow, projectile aiming, AI steering)."""

from __future__ import annotations

import math

from pygame import Vector2

from pygamine.util.math_utils import angle_between_delta, angle_between_points, distance


def test_distance_between_identical_points_is_zero():
    assert distance(Vector2(5, 5), Vector2(5, 5)) == 0


def test_distance_matches_pythagorean_triple():
    assert distance(Vector2(0, 0), Vector2(3, 4)) == 5


def test_angle_between_delta_right_is_zero_degrees():
    assert angle_between_delta(Vector2(1, 0)) == 0


def test_angle_between_delta_down_is_90_degrees():
    # pygame/screen space: +y points down, so "down" is +90 degrees here.
    assert angle_between_delta(Vector2(0, 1)) == 90


def test_angle_between_delta_left_is_180_degrees():
    assert abs(angle_between_delta(Vector2(-1, 0))) == 180


def test_angle_between_points_is_direction_from_origin_to_target():
    origin = Vector2(0, 0)
    target = Vector2(0, 10)
    assert angle_between_points(origin, target) == angle_between_delta(target - origin)


def test_angle_between_points_matches_known_45_degrees():
    origin = Vector2(0, 0)
    target = Vector2(10, 10)
    assert math.isclose(angle_between_points(origin, target), 45)
