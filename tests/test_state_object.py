"""Unit tests for StateObject and HoverableStateObject: a GameObject that
maps state keys to Surfaces via one SpriteRenderer2D, with optional
hover-image swapping.

Uses real image files under tmp_path (load_image needs a real, loadable
file + convert_alpha(), which needs a display mode set even under the
dummy SDL driver) rather than mocking image loading away.
"""

from __future__ import annotations

import pygame
import pytest

from pygamine.ecs.components.transform import Transform
from pygamine.ecs.state_object import HoverableStateObject, StateObject


def _save_png(path, color, size=(20, 20)):
    surf = pygame.Surface(size, pygame.SRCALPHA)
    surf.fill(color)
    pygame.image.save(surf, str(path))


@pytest.fixture
def images(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pygame.display.set_mode((1, 1))  # convert_alpha() needs a display mode set

    base = tmp_path / "base.png"
    hover = tmp_path / "hover.png"
    other_state = tmp_path / "other_state.png"
    _save_png(base, (255, 0, 0))
    _save_png(hover, (0, 255, 0))
    _save_png(other_state, (0, 0, 255))
    return {"base": base, "hover": hover, "other_state": other_state}


@pytest.fixture
def parent():
    return Transform(position=(0, 0), size=(800, 600))


def _color(obj):
    return obj._renderer.image.get_at((5, 5))


# ── StateObject construction ────────────────────────────────────────────


def test_construction_positions_and_sizes_the_rect(parent):
    obj = StateObject(parent=parent, pos=(10, 20), size=(30, 40))
    assert obj.rect.size == (30, 40)
    assert obj.rect.topleft == (10, 20)
    assert obj.rect.parent is parent


def test_construction_with_no_image_registers_no_states():
    obj = StateObject(size=(20, 20))
    assert obj.images == {}
    assert obj.state is None


def test_construction_with_an_image_path_registers_and_applies_it(images):
    obj = StateObject(size=(20, 20), image_path=images["base"])
    assert None in obj.images
    assert _color(obj) == (255, 0, 0, 255)


def test_construction_defaults(images):
    obj = StateObject(size=(20, 20), image_path=images["base"])
    assert obj.focused is False
    assert obj.on_click_sound is None


# ── add_surface / add_state ─────────────────────────────────────────────


def test_add_surface_registers_without_touching_renderer_for_a_different_state():
    obj = StateObject(size=(20, 20))
    surf = pygame.Surface((20, 20))
    surf.fill((1, 2, 3))

    obj.add_surface("other", surf)

    assert obj.images["other"] is surf
    assert obj._renderer.image is None  # current state is still None, unaffected


def test_add_surface_updates_renderer_when_it_matches_the_current_state():
    obj = StateObject(size=(20, 20))
    surf = pygame.Surface((20, 20))
    surf.fill((1, 2, 3))

    obj.add_surface(None, surf)  # current _state is already None

    assert obj._renderer.image is surf


def test_add_state_loads_a_real_image_file(images):
    obj = StateObject(size=(20, 20))
    obj.add_state("purchased", images["other_state"])
    assert obj.images["purchased"].get_at((5, 5)) == (0, 0, 255, 255)


# ── set_state ────────────────────────────────────────────────────────────


def test_set_state_switches_to_a_registered_state(images):
    obj = StateObject(size=(20, 20), image_path=images["base"])
    obj.add_state("other", images["other_state"])

    obj.set_state("other")

    assert obj.state == "other"
    assert _color(obj) == (0, 0, 255, 255)


def test_set_state_to_an_unregistered_state_updates_state_but_not_renderer(images):
    """No guard against setting an unknown state -- .state changes, but the
    renderer is only touched `if state in self.images`."""
    obj = StateObject(size=(20, 20), image_path=images["base"])

    obj.set_state("nonexistent")

    assert obj.state == "nonexistent"
    assert _color(obj) == (255, 0, 0, 255)  # renderer still shows the old image


def test_active_surface_raises_for_an_unregistered_state(images):
    obj = StateObject(size=(20, 20), image_path=images["base"])
    obj.set_state("nonexistent")
    with pytest.raises(KeyError):
        _ = obj._active_surface


# ── set_base_state ───────────────────────────────────────────────────────


def test_set_base_state_sets_both_base_state_and_state(images):
    obj = StateObject(size=(20, 20), image_path=images["base"])
    obj.add_state("other", images["other_state"])

    obj.set_base_state("other")

    assert obj._base_state == "other"
    assert obj.state == "other"
    assert _color(obj) == (0, 0, 255, 255)


# ── focused ──────────────────────────────────────────────────────────────


def test_focused_defaults_to_false(images):
    obj = StateObject(size=(20, 20), image_path=images["base"])
    assert obj.focused is False


def test_setting_focused_to_the_same_value_is_a_no_op():
    obj = StateObject(size=(20, 20))  # no images registered at all
    obj.focused = False  # already False -- must not touch the renderer/raise
    assert obj.focused is False


def test_setting_focused_updates_the_flag(images):
    obj = StateObject(size=(20, 20), image_path=images["base"])
    obj.focused = True
    assert obj.focused is True


def test_setting_focused_without_a_registered_state_does_not_raise():
    obj = StateObject(size=(20, 20))  # _state=None, nothing registered
    obj.focused = True  # guarded by `if self._state in self.images`
    assert obj.focused is True


# ── info ──────────────────────────────────────────────────────────────────


def test_info_reports_state_pos_and_size(images):
    obj = StateObject(pos=(10, 20), size=(30, 40), image_path=images["base"])
    label, data = obj.info()
    assert label == "StateObject Info:"
    assert data["state"] is None
    assert data["pos"] == (10, 20)
    assert data["size"] == (30, 40)


# ── HoverableStateObject construction ────────────────────────────────────


def test_hoverable_construction_with_hover_image(images):
    obj = HoverableStateObject(
        size=(20, 20), image_path=images["base"], hover_image_path=images["hover"]
    )
    assert obj._hover_images[None].get_at((5, 5)) == (0, 255, 0, 255)


def test_hoverable_construction_without_hover_image_leaves_hover_images_empty(images):
    obj = HoverableStateObject(size=(20, 20), image_path=images["base"])
    assert obj._hover_images == {}


def test_hoverable_starts_unhovered(images):
    obj = HoverableStateObject(size=(20, 20), image_path=images["base"])
    assert obj._hovered is False


# ── HoverableStateObject.add_state (override) ────────────────────────────


def test_hoverable_add_state_registers_both_base_and_hover(images):
    obj = HoverableStateObject(size=(20, 20), image_path=images["base"])
    obj.add_state("purchased", images["other_state"], images["hover"])

    assert obj.images["purchased"].get_at((5, 5)) == (0, 0, 255, 255)
    assert obj._hover_images["purchased"].get_at((5, 5)) == (0, 255, 0, 255)


def test_hoverable_add_state_without_hover_only_registers_base(images):
    obj = HoverableStateObject(size=(20, 20), image_path=images["base"])
    obj.add_state("purchased", images["other_state"])

    assert "purchased" in obj.images
    assert "purchased" not in obj._hover_images


# ── HoverableStateObject._active_surface ─────────────────────────────────


def test_active_surface_is_base_image_when_not_hovered_or_focused(images):
    obj = HoverableStateObject(
        size=(20, 20), image_path=images["base"], hover_image_path=images["hover"]
    )
    assert obj._active_surface.get_at((5, 5)) == (255, 0, 0, 255)


def test_active_surface_is_hover_image_when_hovered(images):
    obj = HoverableStateObject(
        size=(20, 20), image_path=images["base"], hover_image_path=images["hover"]
    )
    obj._hovered = True
    assert obj._active_surface.get_at((5, 5)) == (0, 255, 0, 255)


def test_active_surface_is_hover_image_when_focused_without_hovering(images):
    obj = HoverableStateObject(
        size=(20, 20), image_path=images["base"], hover_image_path=images["hover"]
    )
    obj.focused = True
    assert obj._active_surface.get_at((5, 5)) == (0, 255, 0, 255)


def test_active_surface_prefers_per_state_hover_over_default_hover(images):
    obj = HoverableStateObject(
        size=(20, 20), image_path=images["base"], hover_image_path=images["hover"]
    )
    obj.add_state("purchased", images["other_state"])  # no per-state hover registered
    obj.set_state("purchased")
    obj._hovered = True

    # falls through to the default (None-keyed) hover image since "purchased"
    # has none of its own
    assert obj._active_surface.get_at((5, 5)) == (0, 255, 0, 255)


def test_active_surface_falls_back_to_base_image_when_hovered_with_no_hover_image_at_all(
    images,
):
    obj = HoverableStateObject(
        size=(20, 20), image_path=images["base"]
    )  # no hover_image_path
    obj._hovered = True
    assert obj._active_surface.get_at((5, 5)) == (255, 0, 0, 255)


# ── HoverableStateObject.handle_event ─────────────────────────────────────


def test_mouse_entering_the_rect_switches_to_the_hover_image(parent, images):
    obj = HoverableStateObject(
        parent=parent,
        pos=(0, 0),
        size=(20, 20),
        image_path=images["base"],
        hover_image_path=images["hover"],
    )
    event = pygame.event.Event(pygame.MOUSEMOTION, pos=(5, 5))

    obj.handle_event(event, (5, 5))

    assert obj._hovered is True
    assert _color(obj) == (0, 255, 0, 255)


def test_mouse_leaving_the_rect_reverts_to_the_base_image(parent, images):
    obj = HoverableStateObject(
        parent=parent,
        pos=(0, 0),
        size=(20, 20),
        image_path=images["base"],
        hover_image_path=images["hover"],
    )
    obj.handle_event(
        pygame.event.Event(pygame.MOUSEMOTION, pos=(5, 5)), (5, 5)
    )  # enter
    assert obj._hovered is True

    obj.handle_event(
        pygame.event.Event(pygame.MOUSEMOTION, pos=(999, 999)), (999, 999)
    )  # leave

    assert obj._hovered is False
    assert _color(obj) == (255, 0, 0, 255)


def test_mouse_staying_inside_does_not_re_trigger_the_renderer_update(
    parent, images, monkeypatch
):
    obj = HoverableStateObject(
        parent=parent,
        pos=(0, 0),
        size=(20, 20),
        image_path=images["base"],
        hover_image_path=images["hover"],
    )
    obj.handle_event(
        pygame.event.Event(pygame.MOUSEMOTION, pos=(5, 5)), (5, 5)
    )  # enters, hovered=True

    calls = []
    real_set_image = obj._renderer.set_image
    monkeypatch.setattr(
        obj._renderer,
        "set_image",
        lambda img: (calls.append(img), real_set_image(img))[-1],
    )

    obj.handle_event(
        pygame.event.Event(pygame.MOUSEMOTION, pos=(6, 6)), (6, 6)
    )  # still inside

    assert calls == []  # hover state didn't change, so no redundant renderer update


def test_unrelated_event_type_does_not_change_hover_state(parent, images):
    obj = HoverableStateObject(
        parent=parent,
        pos=(0, 0),
        size=(20, 20),
        image_path=images["base"],
        hover_image_path=images["hover"],
    )
    obj.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a), (5, 5))
    assert obj._hovered is False
