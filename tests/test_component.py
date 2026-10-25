"""Unit tests for Component/Behaviour/MonoBehaviour: the base classes every
ECS component (Transform, Rigidbody2D, SpriteRenderer2D, Animator, ...)
builds on.
"""

from __future__ import annotations

import pytest

from pygamine.ecs.components.component import Behaviour, Component, MonoBehaviour


def test_component_game_object_defaults_to_none():
    assert Component().game_object is None


def test_get_component_asserts_when_unattached():
    comp = Component()
    with pytest.raises(AssertionError):
        comp.get_component(Component)


def test_get_component_delegates_to_attached_game_object():
    class _FakeGameObject:
        def get_component(self, component_type):
            return f"got {component_type.__name__}"

    comp = Component()
    comp.game_object = _FakeGameObject()
    assert comp.get_component(Component) == "got Component"


def test_behaviour_defaults_to_enabled():
    assert Behaviour().enabled is True


def test_behaviour_is_a_component():
    assert isinstance(Behaviour(), Component)


def test_mono_behaviour_lifecycle_hooks_are_harmless_no_ops():
    mb = MonoBehaviour()
    mb.awake()
    mb.start()
    mb.update()
    mb.on_destroy()
    mb.on_enable()
    mb.on_disable()  # none of these should raise
