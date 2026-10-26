"""Unit tests for TextObject: a GameObject-based text label with optional
multi-state auto-sync to a parent's state/hover flags.
"""

from __future__ import annotations

import pygame
import pytest

from pygamine.ecs.components.sprite_renderer2d import SpriteRenderer2D
from pygamine.ecs.game_object import GameObject
from pygamine.ui_widgets.text_object import TextObject


@pytest.fixture
def font() -> pygame.font.Font:
    return pygame.font.Font(None, 20)


def _renderer(text_obj) -> SpriteRenderer2D | None:
    return text_obj.get_component(SpriteRenderer2D)


# ── construction ────────────────────────────────────────────────────────


def test_single_state_construction_via_text_kwarg(font):
    label = TextObject(None, (0, 0), text="Hi", font=font)
    assert label.states == {"default": "Hi"}
    assert label.state == "default"
    assert label.text == "Hi"


def test_multi_state_construction_auto_inserts_missing_default(font):
    label = TextObject(None, (0, 0), text="fallback", font=font, states={"hover": "H"})
    assert label.states == {"hover": "H", "default": "fallback"}


def test_multi_state_construction_does_not_overwrite_existing_default(font):
    label = TextObject(
        None, (0, 0), text="ignored", font=font, states={"default": "D", "hover": "H"}
    )
    assert label.states["default"] == "D"


def test_construction_renders_and_sizes_to_the_text(font):
    label = TextObject(None, (0, 0), text="Hi", font=font)
    expected_size = font.render("Hi", True, label.color).get_size()
    assert label.rect.size == expected_size
    assert _renderer(label).image is not None


def test_construction_registers_a_sprite_renderer(font):
    label = TextObject(None, (0, 0), text="Hi", font=font)
    assert isinstance(_renderer(label), SpriteRenderer2D)


# ── set_text ────────────────────────────────────────────────────────────


def test_set_text_updates_text_and_reflows(font):
    label = TextObject(None, (0, 0), text="Hi", font=font)
    old_image = _renderer(label).image

    label.set_text("Hello there")

    assert label.text == "Hello there"
    assert label.states["default"] == "Hello there"
    assert _renderer(label).image is not old_image  # reflowed to a new surface
    assert label.rect.size == font.render("Hello there", True, label.color).get_size()


def test_set_text_with_unchanged_value_does_not_reflow(font):
    label = TextObject(None, (0, 0), text="Hi", font=font)
    old_image = _renderer(label).image

    label.set_text("Hi")  # same value as current

    assert _renderer(label).image is old_image  # no new render happened


def test_set_text_for_a_non_active_state_does_not_touch_current_text(font):
    label = TextObject(None, (0, 0), font=font, states={"default": "D", "hover": "H"})
    old_image = _renderer(label).image

    label.set_text("new hover text", state="hover")

    assert label.states["hover"] == "new hover text"
    assert label.text == "D"  # active state ("default") untouched
    assert _renderer(label).image is old_image  # no reflow for an inactive state


# ── set_color ───────────────────────────────────────────────────────────


def test_set_color_changes_color_and_reflows(font):
    label = TextObject(None, (0, 0), text="Hi", font=font, color=(255, 255, 255))
    old_image = _renderer(label).image

    label.set_color((255, 0, 0))

    assert label.color == (255, 0, 0)
    assert _renderer(label).image is not old_image


def test_set_color_with_unchanged_value_does_not_reflow(font):
    label = TextObject(None, (0, 0), text="Hi", font=font, color=(255, 255, 255))
    old_image = _renderer(label).image

    label.set_color((255, 255, 255))

    assert _renderer(label).image is old_image


# ── set_state ─────────────────────────────────────────────────────────


def test_set_state_switches_text_and_reflows(font):
    label = TextObject(None, (0, 0), font=font, states={"default": "D", "hover": "H"})
    old_image = _renderer(label).image

    label.set_state("hover")

    assert label.state == "hover"
    assert label.text == "H"
    assert _renderer(label).image is not old_image


def test_set_state_to_the_same_state_is_a_no_op(font):
    label = TextObject(None, (0, 0), font=font, states={"default": "D", "hover": "H"})
    old_image = _renderer(label).image

    label.set_state("default")

    assert _renderer(label).image is old_image


def test_set_state_to_an_unknown_state_is_a_no_op(font):
    label = TextObject(None, (0, 0), font=font, states={"default": "D", "hover": "H"})

    label.set_state("nonexistent")

    assert label.state == "default"
    assert label.text == "D"


def test_set_state_to_none_clears_text():
    font_obj = pygame.font.Font(None, 20)
    label = TextObject(None, (0, 0), font=font_obj, states={"default": "D"})

    label.set_state(None)

    assert label.state is None
    assert label.text == ""


# ── update(): auto-sync to a parent's state/hover ──────────────────────


def test_update_is_a_no_op_with_only_one_state(font):
    class _Parent(GameObject):
        state = "hover"

    parent = _Parent()
    label = TextObject(
        parent.rect, (0, 0), text="Hi", font=font
    )  # only "default" state

    label.update()

    assert label.state == "default"


def test_update_is_a_no_op_with_no_parent(font):
    label = TextObject(None, (0, 0), font=font, states={"default": "D", "hover": "H"})
    label.update()  # rect.parent is None -- must not raise
    assert label.state == "default"


def test_update_is_a_no_op_when_parent_transform_has_no_game_object(font):
    from pygamine.ecs.components.transform import Transform

    orphan_transform = Transform()  # never attached to a GameObject
    label = TextObject(
        orphan_transform, (0, 0), font=font, states={"default": "D", "hover": "H"}
    )

    label.update()

    assert label.state == "default"


def test_update_follows_parent_state_attribute(font):
    class _Parent(GameObject):
        def __init__(self):
            super().__init__()
            self.state = "hover"

    parent = _Parent()
    label = TextObject(
        parent.rect, (0, 0), font=font, states={"default": "D", "hover": "H"}
    )

    label.update()

    assert label.state == "hover"
    assert label.text == "H"


def test_update_follows_parent_underscore_state_attribute(font):
    class _Parent(GameObject):
        def __init__(self):
            super().__init__()
            self._state = "hover"

    parent = _Parent()
    label = TextObject(
        parent.rect, (0, 0), font=font, states={"default": "D", "hover": "H"}
    )

    label.update()

    assert label.state == "hover"


def test_update_falls_back_to_hover_flag_when_parent_state_does_not_match(font):
    class _Parent(GameObject):
        def __init__(self):
            super().__init__()
            self.state = "purchased"  # not one of label's states
            self._hovered = True

    parent = _Parent()
    label = TextObject(
        parent.rect, (0, 0), font=font, states={"default": "D", "hover": "H"}
    )

    label.update()

    assert label.state == "hover"


def test_update_falls_back_to_default_when_nothing_else_matches(font):
    class _Parent(GameObject):
        def __init__(self):
            super().__init__()
            self.state = "purchased"
            self._hovered = False

    parent = _Parent()
    label = TextObject(
        parent.rect, (0, 0), font=font, states={"default": "D", "hover": "H"}
    )
    label.set_state("hover")  # start somewhere other than default

    label.update()

    assert label.state == "default"


def test_update_stays_put_when_no_fallback_state_is_available(font):
    class _Parent(GameObject):
        def __init__(self):
            super().__init__()
            self.state = "purchased"
            self._hovered = False

    parent = _Parent()
    label = TextObject(parent.rect, (0, 0), font=font, states={"hover": "H"})
    del label.states[
        "default"
    ]  # construction always adds one -- remove it for this edge case
    label.state = "hover"

    label.update()

    assert (
        label.state == "hover"
    )  # nothing matched, so _resolve_state_from returns self.state unchanged


# ── _parse_color / _parse_padding (static helpers) ─────────────────────


def test_parse_color_none_stays_none(font):
    label = TextObject(None, (0, 0), text="x", font=font, background_color=None)
    assert label.background_color is None


def test_parse_color_tuple_passthrough(font):
    label = TextObject(None, (0, 0), text="x", font=font, color=(1, 2, 3))
    assert label.color == (1, 2, 3)


def test_parse_color_string_name(font):
    label = TextObject(None, (0, 0), text="x", font=font, color="red")
    assert label.color == tuple(pygame.Color("red"))


def test_parse_padding_none_is_zero_on_all_sides(font):
    label = TextObject(None, (0, 0), text="x", font=font, padding=None)
    assert label.padding == (0, 0, 0, 0)


def test_parse_padding_int_applies_to_all_sides(font):
    label = TextObject(None, (0, 0), text="x", font=font, padding=5)
    assert label.padding == (5, 5, 5, 5)


def test_parse_padding_two_values_are_vertical_horizontal(font):
    label = TextObject(None, (0, 0), text="x", font=font, padding=[4, 8])
    assert label.padding == (4, 8, 4, 8)


def test_parse_padding_four_values_are_top_right_bottom_left(font):
    label = TextObject(None, (0, 0), text="x", font=font, padding=[1, 2, 3, 4])
    assert label.padding == (1, 2, 3, 4)


def test_parse_padding_invalid_length_raises(font):
    with pytest.raises(ValueError):
        TextObject(None, (0, 0), text="x", font=font, padding=[1, 2, 3])


# ── background/padding rendering ────────────────────────────────────────


def test_background_color_and_padding_produce_a_larger_filled_surface(font):
    label = TextObject(
        None, (0, 0), text="Hi", font=font, background_color=(0, 255, 0), padding=10
    )
    text_only_size = font.render("Hi", True, label.color).get_size()

    assert label.rect.size == (text_only_size[0] + 20, text_only_size[1] + 20)
    image = _renderer(label).image
    assert image.get_at((0, 0)) == (
        0,
        255,
        0,
        255,
    )  # padding area shows the background fill
