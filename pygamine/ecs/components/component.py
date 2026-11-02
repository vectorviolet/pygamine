from __future__ import annotations

from typing import Any, TypeVar

T = TypeVar("T", bound="Component")


class Component:
    def __init__(self) -> None:
        self.game_object: Any = None

    def get_component(self, component_type: type[T]) -> T | None:
        assert self.game_object is not None, "Component is not attached to a GameObject"
        return self.game_object.get_component(component_type)

    def require_component(self, component_type: type[T]) -> T:
        """Like get_component(), but for a sibling component that must be
        there: returns it typed as non-Optional, or raises LookupError
        naming the GameObject and the missing component type."""
        if self.game_object is None:
            raise RuntimeError(f"{type(self).__name__} is not attached to a GameObject")
        component: T = self.game_object.require_component(component_type)
        return component


class Behaviour(Component):
    def __init__(self) -> None:
        super().__init__()
        self.enabled: bool = True


class MonoBehaviour(Behaviour):
    def awake(self) -> None: ...
    def start(self) -> None: ...
    def update(self) -> None: ...
    def on_destroy(self) -> None: ...
    def on_enable(self) -> None: ...
    def on_disable(self) -> None: ...
