"""Unit tests for GameObject: active/hierarchy propagation, invoke/
invoke_repeating scheduling, the component system, and per-frame dispatch
(handle_event/update/draw) respecting both .active and Behaviour.enabled.
"""

from __future__ import annotations

import pygame

from pygamine.ecs.components.component import Behaviour, Component
from pygamine.ecs.components.transform import Transform
from pygamine.ecs.game_object import GameObject


# ── construction ───────────────────────────────────────────────────────────


def test_construction_defaults():
    go = GameObject()
    assert go.name == "game_object"
    assert go.active is True
    assert isinstance(go.rect, Transform)
    assert go.rect.game_object is go


def test_construction_with_custom_name():
    assert GameObject(name="enemy").name == "enemy"


def test_transform_is_registered_as_a_component():
    go = GameObject()
    assert go.get_component(Transform) is go.rect


# ── active / hierarchy ─────────────────────────────────────────────────────


def test_active_defaults_true_and_is_settable():
    go = GameObject()
    go.active = False
    assert go.active is False
    go.active = True
    assert go.active is True


def test_active_is_false_when_parent_is_inactive():
    parent = GameObject()
    child = GameObject()
    child.set_parent(parent)

    parent.active = False

    assert child.active is False  # own _active is still True, but effectively inactive


def test_active_true_requires_all_ancestors_active():
    grandparent = GameObject()
    parent = GameObject()
    child = GameObject()
    parent.set_parent(grandparent)
    child.set_parent(parent)

    grandparent.active = False

    assert child.active is False


def test_setting_same_active_value_does_not_call_on_enable_disable():
    calls = []

    class _Tracked(GameObject):
        def on_enable(self):
            calls.append("enable")

        def on_disable(self):
            calls.append("disable")

    go = _Tracked()
    go.active = True  # already True -- must be a no-op
    assert calls == []


def test_disabling_calls_on_disable_and_enabling_calls_on_enable():
    calls = []

    class _Tracked(GameObject):
        def on_enable(self):
            calls.append("enable")

        def on_disable(self):
            calls.append("disable")

    go = _Tracked()
    go.active = False
    go.active = True
    assert calls == ["disable", "enable"]


def test_disabling_parent_cascades_on_disable_to_active_children():
    calls = []

    class _Tracked(GameObject):
        def __init__(self, tag):
            super().__init__()
            self.tag = tag

        def on_disable(self):
            calls.append(self.tag)

    parent = _Tracked("parent")
    child = _Tracked("child")
    child.set_parent(parent)

    parent.active = False

    assert calls == ["parent", "child"]


def test_disabling_parent_does_not_cascade_to_already_self_disabled_children():
    calls = []

    class _Tracked(GameObject):
        def __init__(self, tag):
            super().__init__()
            self.tag = tag

        def on_disable(self):
            calls.append(self.tag)

    parent = _Tracked("parent")
    child = _Tracked("child")
    child.set_parent(parent)
    child.active = False
    calls.clear()  # ignore the child's own disable call above

    parent.active = False

    assert calls == ["parent"]  # child was already inactive, not re-notified


def test_set_parent_moves_object_between_parents_children_lists():
    old_parent = GameObject()
    new_parent = GameObject()
    child = GameObject()

    child.set_parent(old_parent)
    assert child in old_parent._children

    child.set_parent(new_parent)
    assert child not in old_parent._children
    assert child in new_parent._children


def test_set_parent_none_detaches():
    parent = GameObject()
    child = GameObject()
    child.set_parent(parent)
    child.set_parent(None)
    assert child not in parent._children
    assert child.active is True  # no parent to be gated by anymore


# ── invoke / invoke_repeating / cancel_invoke ────────────────────────────


def test_invoke_does_not_fire_before_its_delay(fake_ticks):
    calls = []
    go = GameObject()
    go.invoke(lambda: calls.append(1), delay=1.0)  # 1000ms

    fake_ticks["t"] = 500
    go._tick_scheduled()

    assert calls == []


def test_invoke_fires_once_after_its_delay(fake_ticks):
    calls = []
    go = GameObject()
    go.invoke(lambda: calls.append(1), delay=1.0)

    fake_ticks["t"] = 1000
    go._tick_scheduled()
    fake_ticks["t"] = 2000
    go._tick_scheduled()

    assert calls == [1]  # only fired once, not on the second tick too


def test_invoke_repeating_fires_on_each_interval(fake_ticks):
    calls = []
    go = GameObject()
    go.invoke_repeating(
        lambda: calls.append(1), delay=0.1, interval=0.5
    )  # 100ms, 500ms

    fake_ticks["t"] = 100
    go._tick_scheduled()
    assert calls == [1]

    fake_ticks["t"] = 600
    go._tick_scheduled()
    assert calls == [1, 1]

    fake_ticks["t"] = 1100
    go._tick_scheduled()
    assert calls == [1, 1, 1]


def test_cancel_invoke_with_specific_callback_removes_only_that_one(fake_ticks):
    calls_a, calls_b = [], []
    go = GameObject()
    cb_a = lambda: calls_a.append(1)
    cb_b = lambda: calls_b.append(1)
    go.invoke(cb_a, delay=0.1)
    go.invoke(cb_b, delay=0.1)

    go.cancel_invoke(cb_a)
    fake_ticks["t"] = 200
    go._tick_scheduled()

    assert calls_a == []
    assert calls_b == [1]


def test_cancel_invoke_with_no_args_clears_everything(fake_ticks):
    calls = []
    go = GameObject()
    go.invoke(lambda: calls.append(1), delay=0.1)
    go.invoke_repeating(lambda: calls.append(2), delay=0.1, interval=0.1)

    go.cancel_invoke()
    fake_ticks["t"] = 1000
    go._tick_scheduled()

    assert calls == []


def test_tick_scheduled_is_a_no_op_with_nothing_scheduled(fake_ticks):
    go = GameObject()
    go._tick_scheduled()  # must not raise with an empty schedule


# ── component system ────────────────────────────────────────────────────


def test_add_component_registers_and_sets_game_object_back_reference():
    go = GameObject()
    comp = go.add_component(Component)
    assert comp.game_object is go


def test_add_component_calls_awake_if_present():
    calls = []

    class _WithAwake(Component):
        def awake(self):
            calls.append(1)

    go = GameObject()
    go.add_component(_WithAwake)
    assert calls == [1]


def test_add_component_passes_through_kwargs():
    class _Positional(Component):
        def __init__(self, value):
            super().__init__()
            self.value = value

    go = GameObject()
    comp = go.add_component(_Positional, value=42)
    assert comp.value == 42


def test_get_component_returns_none_for_unregistered_type():
    class _Unregistered(Component):
        pass

    go = GameObject()
    assert go.get_component(_Unregistered) is None


# ── image (default Drawable.image -- see camera.py) ─────────────────────


def test_image_is_none_without_a_sprite_renderer():
    go = GameObject()
    assert go.image is None


def test_image_resolves_to_the_sprite_renderers_image():
    from pygamine.ecs.components.sprite_renderer2d import SpriteRenderer2D

    go = GameObject()
    renderer = go.add_component(SpriteRenderer2D)
    surface = pygame.Surface((4, 4))
    renderer.set_image(surface)

    assert go.image is surface


def test_image_reflects_a_later_set_image_call():
    from pygamine.ecs.components.sprite_renderer2d import SpriteRenderer2D

    go = GameObject()
    renderer = go.add_component(SpriteRenderer2D)
    first = pygame.Surface((4, 4))
    renderer.set_image(first)
    assert go.image is first

    second = pygame.Surface((8, 8))
    renderer.set_image(second)
    assert go.image is second


def test_image_is_directly_settable_without_a_sprite_renderer():
    """Regression test: some entities manage their own image directly with
    no SpriteRenderer2D at all (e.g. one rendered straight from text) and
    expect a plain `self.image = ...` assignment to just work -- image
    used to be a read-only property, which broke every one of them the
    instant this property was added (AttributeError: no setter)."""
    go = GameObject()
    surface = pygame.Surface((6, 6))

    go.image = surface

    assert go.image is surface


def test_directly_set_image_takes_priority_over_the_sprite_renderer():
    from pygamine.ecs.components.sprite_renderer2d import SpriteRenderer2D

    go = GameObject()
    renderer = go.add_component(SpriteRenderer2D)
    renderer.set_image(pygame.Surface((4, 4)))

    own_image = pygame.Surface((9, 9))
    go.image = own_image

    assert go.image is own_image


# ── handle_event / update / draw dispatch ──────────────────────────────


def test_inactive_game_object_skips_handle_event_update_and_draw():
    calls = []

    class _Tracked(Component):
        def handle_event(self, event, mouse_pos):
            calls.append("handle_event")

        def update(self):
            calls.append("update")

        def draw(self, surface):
            calls.append("draw")

    go = GameObject()
    go.add_component(_Tracked)
    go.active = False

    go.handle_event(pygame.event.Event(pygame.USEREVENT), (0, 0))
    go.update()
    go.draw(pygame.Surface((1, 1)))

    assert calls == []


def test_update_ticks_scheduled_calls_too(fake_ticks):
    calls = []
    go = GameObject()
    go.invoke(lambda: calls.append(1), delay=0.1)

    fake_ticks["t"] = 200
    go.update()

    assert calls == [1]


def test_disabled_behaviour_component_is_skipped(fake_ticks):
    calls = []

    class _TrackedBehaviour(Behaviour):
        def update(self):
            calls.append(1)

    go = GameObject()
    comp = go.add_component(_TrackedBehaviour)
    comp.enabled = False

    go.update()

    assert calls == []


def test_enabled_behaviour_component_still_runs(fake_ticks):
    calls = []

    class _TrackedBehaviour(Behaviour):
        def update(self):
            calls.append(1)

    go = GameObject()
    go.add_component(_TrackedBehaviour)

    go.update()

    assert calls == [1]


def test_plain_component_without_enabled_flag_always_runs():
    """Only Behaviour subclasses are gated by .enabled -- a plain Component
    has no such flag and must never be skipped for lacking one."""
    calls = []

    class _PlainComponent(Component):
        def update(self):
            calls.append(1)

    go = GameObject()
    go.add_component(_PlainComponent)

    go.update()

    assert calls == [1]
