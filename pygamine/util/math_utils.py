from __future__ import annotations

from math import atan2, degrees

from pygame import Vector2


def distance(a: Vector2, b: Vector2) -> float:
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5


def angle_between_points(origin_point: Vector2, target_point: Vector2) -> float:
    return angle_of_delta(target_point - origin_point)


def angle_of_delta(delta: Vector2) -> float:
    return degrees(atan2(delta.y, delta.x))


def clamp01(value: float) -> float:
    """`value` clamped to the 0-1 range. NaN returns 1.0 (`min(1.0, nan)` keeps
    1.0), the same as the clamps this replaced."""
    return max(0.0, min(1.0, value))
