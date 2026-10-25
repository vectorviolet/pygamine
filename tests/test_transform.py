"""Unit tests for Transform: the Rect-based positioning component every
GameObject has (as .rect) and every panel/UI object is placed through.
"""

from __future__ import annotations

import pytest

from pygamine.ecs.components.transform import Transform


def test_default_construction():
    t = Transform()
    assert t.topleft == (0, 0)
    assert t.size == (0, 0)


def test_construction_with_position_and_size():
    t = Transform(position=(10, 20), size=(30, 40))
    assert t.topleft == (10, 20)
    assert t.size == (30, 40)


def test_set_position_numeric_no_parent():
    t = Transform(size=(10, 10))
    t.set_position((5, 7))
    assert t.topleft == (5, 7)


def test_set_position_center_token_without_parent_degenerates_to_own_size():
    """Documented actual behaviour, not necessarily desirable: with no parent,
    resolve_pos's parent_size falls back to the transform's own size, so
    'CENTER' resolves against itself and collapses to (0, 0)."""
    t = Transform(size=(50, 50))
    t.set_position(("CENTER", "CENTER"))
    assert t.topleft == (0, 0)


def test_set_position_center_token_with_parent_centers_within_parent():
    parent = Transform(position=(0, 0), size=(200, 100))
    child = Transform(size=(20, 10), parent=parent)
    child.set_position(("CENTER", "CENTER"))
    assert child.topleft == (90, 45)


def test_set_position_offsets_by_parent_origin():
    parent = Transform(position=(100, 50), size=(200, 100))
    child = Transform(size=(20, 10), parent=parent)
    child.set_position((5, 5))
    assert child.topleft == (105, 55)


def test_set_position_with_named_anchor():
    parent = Transform(position=(0, 0), size=(200, 100))
    child = Transform(size=(20, 10), parent=parent, anchor="bottom-right")
    child.set_position((-25, -25))
    assert child.topleft == (155, 65)


def test_set_parent_none_is_allowed():
    t = Transform()
    t.set_parent(None)
    assert t.parent is None


def test_set_parent_rejects_non_transform():
    t = Transform()
    with pytest.raises(AssertionError):
        t.set_parent(object())


def test_set_parent_accepts_transform():
    parent = Transform(size=(10, 10))
    t = Transform()
    t.set_parent(parent)
    assert t.parent is parent


def test_update_is_a_harmless_no_op():
    t = Transform(position=(1, 2), size=(3, 4))
    t.update()
    assert t.topleft == (1, 2)
    assert t.size == (3, 4)
