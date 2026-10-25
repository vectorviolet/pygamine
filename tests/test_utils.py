"""Unit tests for utils.resolve_size and Anchorable.resolve_pos.

These pin the YAML-driven layout math every panel/UI object goes through
(config/panels.yaml's `size`/`position`/`anchor` keys) -- a regression here
silently misplaces or mis-sizes UI across every consuming project.
"""

from __future__ import annotations

import pytest

from pygamine.util.utils import Anchorable, resolve_size


# ── resolve_size ──────────────────────────────────────────────────────────


def test_resolve_size_window_token_returns_window_size():
    assert resolve_size("WINDOW", (1920, 1080)) == (1920, 1080)


def test_resolve_size_two_element_list_returns_as_tuple():
    assert resolve_size([100, 200], (1920, 1080)) == (100, 200)


def test_resolve_size_rejects_tuple_input():
    """Only a list is accepted -- a tuple falls through to the error path.

    Pinning this because it's a surprising, easy-to-hit distinction: YAML
    always deserializes `[100, 200]` as a list, but hand-constructed Python
    callers might reasonably pass a tuple and get an error instead.
    """
    with pytest.raises(ValueError):
        resolve_size((100, 200), (1920, 1080))


def test_resolve_size_wrong_length_list_raises():
    with pytest.raises(ValueError):
        resolve_size([100], (1920, 1080))


def test_resolve_size_unrecognized_value_raises():
    with pytest.raises(ValueError):
        resolve_size(123, (1920, 1080))


# ── Anchorable.resolve_pos ────────────────────────────────────────────────


def test_resolve_pos_top_left_passes_numeric_pos_through_unchanged():
    assert Anchorable.resolve_pos((10, 20), (100, 100), (30, 30)) == (10, 20)


def test_resolve_pos_top_left_center_token_centers_in_parent():
    pos = Anchorable.resolve_pos(("CENTER", "CENTER"), (100, 100), (30, 30))
    assert pos == (35, 35)


def test_resolve_pos_top_left_center_token_applies_per_axis():
    pos = Anchorable.resolve_pos(("CENTER", 5), (100, 100), (30, 30))
    assert pos == (35, 5)


def test_resolve_pos_center_anchor_offsets_by_half_sizes():
    pos = Anchorable.resolve_pos((0, 0), (200, 100), (20, 10), anchor="center")
    assert pos == (90, 45)


def test_resolve_pos_bottom_right_anchor_insets_from_parent_corner():
    """Docstring example: anchor='bottom-right', position=[-25, -25] insets the
    child's bottom-right corner by 25px from the parent's bottom-right."""
    pos = Anchorable.resolve_pos(
        (-25, -25), (200, 100), (20, 10), anchor="bottom-right"
    )
    assert pos == (155, 65)


def test_resolve_pos_unknown_anchor_raises():
    with pytest.raises(ValueError):
        Anchorable.resolve_pos((0, 0), (1, 1), (1, 1), anchor="bogus")
