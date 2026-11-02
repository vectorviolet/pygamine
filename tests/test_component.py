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
        def get_component(self, component_type) -> str:
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


def test_require_component_raises_when_unattached():
    with pytest.raises(LookupError, match="Component is not attached"):
        Component().require_component(Component)


def test_require_component_returns_sibling_component():
    from pygamine.ecs.components.sprite_renderer2d import SpriteRenderer2D
    from pygamine.ecs.game_object import GameObject

    go = GameObject()
    renderer = go.add_component(SpriteRenderer2D)
    behaviour = go.add_component(Behaviour)
    assert behaviour.require_component(SpriteRenderer2D) is renderer


def test_require_component_raises_naming_object_and_component_when_missing():
    from pygamine.ecs.components.sprite_renderer2d import SpriteRenderer2D
    from pygamine.ecs.game_object import GameObject

    behaviour = GameObject("enemy").add_component(Behaviour)
    with pytest.raises(
        LookupError, match=r"GameObject 'enemy' has no SpriteRenderer2D component"
    ):
        behaviour.require_component(SpriteRenderer2D)


def test_require_component_works_with_an_owner_that_only_has_get_component():
    class _FakeOwner:
        name = "fake"

        def __init__(self, found) -> None:
            self.found = found

        def get_component(self, component_type):
            return self.found

    found = Component()
    comp = Component()
    comp.game_object = _FakeOwner(found)
    assert comp.require_component(Component) is found

    comp.game_object = _FakeOwner(None)
    with pytest.raises(
        LookupError, match=r"_FakeOwner 'fake' has no Component component"
    ):
        comp.require_component(Component)


def test_describe_names_the_object_unless_it_has_the_default_name():
    from pygamine.ecs.components.component import describe
    from pygamine.ecs.game_object import GameObject

    assert describe(GameObject("tower")) == "GameObject 'tower'"
    assert describe(GameObject()) == "GameObject"
    assert describe(object()) == "object"
