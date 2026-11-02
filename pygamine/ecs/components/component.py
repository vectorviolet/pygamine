from __future__ import annotations

from typing import Any, TypeVar

T = TypeVar("T", bound="Component")

# GameObject's default `name`; describe() treats it as "no name given".
DEFAULT_GAME_OBJECT_NAME = "game_object"


def describe(obj: Any) -> str:
    """Short description of a GameObject (or any object with an optional
    `name`) for error messages: `GameObject 'tower'`, or just `GameObject`
    when it has no name or still has the default one. Shared by the
    require_*() errors so their wording can't drift apart."""
    name = getattr(obj, "name", None)
    cls = type(obj).__name__
    if not isinstance(name, str) or name in ("", DEFAULT_GAME_OBJECT_NAME):
        return cls
    return f"{cls} {name!r}"


class Component:
    def __init__(self) -> None:
        self.game_object: Any = None

    def get_component(self, component_type: type[T]) -> T | None:
        assert self.game_object is not None, "Component is not attached to a GameObject"
        return self.game_object.get_component(component_type)

    def require_component(self, component_type: type[T]) -> T:
        """Like get_component(), but for a sibling component that must be
        there: returns it typed as non-Optional.

        Raises LookupError naming the owner and the component type if the
        owner has no such component, and LookupError too if this component
        isn't attached to an owner at all. Works with any owner that has a
        `get_component()` method."""
        if self.game_object is None:
            raise LookupError(f"{type(self).__name__} is not attached to a GameObject")
        component = self.get_component(component_type)
        if component is None:
            raise LookupError(
                f"{describe(self.game_object)} has no "
                f"{component_type.__name__} component"
            )
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
