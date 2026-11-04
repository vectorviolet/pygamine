"""Rebindable keyboard actions.

A game declares actions with `InputMap.declare` (one rebindable primary key plus
optional fixed alternates) and `InputMap.declare_fixed` (keys that can never be
rebound, such as Esc). Event code then asks `is_action(event, "pause")` instead of
comparing `event.key`. Bindings round-trip through plain dicts of key names
(`pygame.key.name`), so the game can store them in its own settings.

Invariant: every key belongs to at most one action, and a primary key is never
also an alternate or fixed key. Nothing here draws UI or touches a save file; a
CONTROLS screen is the game's job.

`pygame.init()` must have run before declaring keys or saving/loading: pygame only
knows key names after that (an assertion says so).
"""

from __future__ import annotations

from typing import Callable, Iterable

import pygame

from pygamine.util.callbacks import run_callbacks


class KeyBindingError(ValueError):
    """A binding was refused. The message says why."""


class _Action:
    def __init__(self, name: str, default: int | None, keys: tuple[int, ...]) -> None:
        self.name = name
        # The rebindable primary key's default; None for a fixed action.
        self.default = default
        # Keys that always trigger the action (alternates, or a fixed action's keys).
        self.keys = keys

    @property
    def fixed(self) -> bool:
        return self.default is None


def _key_name(key: int) -> str:
    assert pygame.get_init(), "call pygame.init() before using InputMap key names"
    name = pygame.key.name(key)
    if not name:
        raise KeyBindingError(f"key code {key} has no name")
    return name


def _key_code(name: str) -> int:
    assert pygame.get_init(), "call pygame.init() before using InputMap key names"
    try:
        return pygame.key.key_code(name)
    except (ValueError, TypeError) as error:
        raise KeyBindingError(f"unknown key name {name!r}") from error


class InputMap:
    """Named actions bound to keyboard keys, with rebinding and save/load."""

    def __init__(self) -> None:
        self._actions: dict[str, _Action] = {}
        self._primary: dict[str, int] = {}
        # Every key that currently triggers an action -> that action. One key,
        # one action: this map is where the rule is enforced.
        self._owner: dict[int, str] = {}
        # Keys the actions get back on reset_defaults (no new action may use them).
        self._default_keys: set[int] = set()
        self._callbacks: list[Callable[[], None]] = []

    # -- declaring --------------------------------------------------------

    def declare(self, name: str, default: int, alternates: Iterable[int] = ()) -> None:
        """Adds a rebindable action: primary key `default` plus fixed `alternates`
        that keep working when the primary changes. Raises `ValueError` if the
        name or a key is already used (a default key counts as used even while
        its action is rebound) or a key has no name."""
        action = _Action(name, default, tuple(alternates))
        self._add(action, [default, *action.keys])
        self._primary[name] = default
        self._owner[default] = name
        self._default_keys.add(default)

    def declare_fixed(self, name: str, *keys: int) -> None:
        """Adds an action whose keys can't be rebound (Esc, F11). It is listed in
        `actions()` but not in `rebindable()` or `to_dict()`."""
        if not keys:
            raise ValueError(f"fixed action {name!r} needs at least one key")
        self._add(_Action(name, None, keys), list(keys))

    def _add(self, action: _Action, keys: list[int]) -> None:
        if action.name in self._actions:
            raise ValueError(f"action {action.name!r} is already declared")
        if len(set(keys)) != len(keys):
            raise ValueError(f"action {action.name!r} lists a key twice")
        for key in keys:
            try:
                _key_name(key)
            except KeyBindingError as error:
                raise ValueError(f"action {action.name!r}: {error}") from error
        if (self._default_keys | self._owner.keys()) & set(keys):
            raise ValueError(f"action {action.name!r} reuses a declared key")
        self._actions[action.name] = action
        for key in action.keys:
            self._owner[key] = action.name

    def _defaults(self) -> dict[str, int]:
        return {n: a.default for n, a in self._actions.items() if a.default is not None}

    def _set_primaries(self, primary: dict[str, int]) -> None:
        for old in self._primary.values():
            del self._owner[old]
        self._primary = primary
        for name, key in primary.items():
            self._owner[key] = name

    # -- queries ----------------------------------------------------------

    def actions(self) -> list[str]:
        """Every declared action, fixed ones included, in declaration order."""
        return list(self._actions)

    def rebindable(self) -> list[str]:
        """The actions whose primary key can be changed."""
        return [n for n, a in self._actions.items() if not a.fixed]

    def is_fixed(self, name: str) -> bool:
        return self._get(name).fixed

    def key_for(self, name: str) -> int:
        """The key to show for `name`: the primary key, or a fixed action's first key."""
        action = self._get(name)
        return action.keys[0] if action.fixed else self._primary[name]

    def keys_for(self, name: str) -> tuple[int, ...]:
        """Every key that triggers `name` (primary first), e.g. for
        `pygame.key.get_pressed()` checks."""
        action = self._get(name)
        if action.fixed:
            return action.keys
        return (self._primary[name], *action.keys)

    def is_action(self, event: pygame.event.Event, name: str) -> bool:
        """True for a KEYDOWN of any key bound to `name`."""
        self._get(name)
        return event.type == pygame.KEYDOWN and self._owner.get(event.key) == name

    def _get(self, name: str) -> _Action:
        try:
            return self._actions[name]
        except KeyError:
            raise KeyError(f"unknown action {name!r}") from None

    # -- changing ---------------------------------------------------------

    def rebind(self, name: str, key: int) -> str | None:
        """Sets the primary key of `name` to `key`.

        Returns None when the key was applied (or already was `name`'s primary).
        If another action's primary key is `key`, nothing changes and that
        action's name is returned so the game can ask the player and call `swap`.
        Raises `KeyBindingError` if `name` is fixed, `key` has no name, or `key`
        is a fixed key or an alternate of any action.
        """
        if self._get(name).fixed:
            raise KeyBindingError(f"action {name!r} is fixed and can't be rebound")
        key_name = _key_name(key)
        owner = self._owner.get(key)
        if owner is None:
            self._set_primaries({**self._primary, name: key})
            self._fire()
            return None
        if key in self._actions[owner].keys:
            kind = "fixed" if self._actions[owner].fixed else "an alternate of"
            raise KeyBindingError(f"{key_name} is {kind} action {owner!r}")
        return None if owner == name else owner

    def swap(self, a: str, b: str) -> None:
        """Exchanges the primary keys of two rebindable actions."""
        for name in (a, b):
            if self._get(name).fixed:
                raise KeyBindingError(f"action {name!r} is fixed and can't be rebound")
        if a == b:
            return
        self._set_primaries({**self._primary, a: self._primary[b], b: self._primary[a]})
        self._fire()

    def reset_defaults(self) -> None:
        """Restores every primary key to its declared default. Declared keys never
        clash (see `declare`), so the result is always valid."""
        defaults = self._defaults()
        if defaults == self._primary:
            return
        self._set_primaries(defaults)
        self._fire()

    # -- saving -----------------------------------------------------------

    def to_dict(self) -> dict[str, str]:
        """`{action: key name}` for the rebindable actions, for the game's settings."""
        return {n: _key_name(k) for n, k in self._primary.items()}

    def _check_primaries(self, proposed: dict[str, int]) -> None:
        """Raises `KeyBindingError` if `proposed` binds a key twice or uses a
        fixed or alternate key."""
        used: dict[int, str] = {}
        for name, key in proposed.items():
            if key in used:
                raise KeyBindingError(
                    f"{_key_name(key)} is bound to both {used[key]!r} and {name!r}"
                )
            used[key] = name
            owner = self._owner.get(key)
            if owner is not None and key in self._actions[owner].keys:
                raise KeyBindingError(
                    f"{_key_name(key)} for {name!r} is reserved by {owner!r}"
                )

    def from_dict(self, data: dict[str, str]) -> None:
        """Loads bindings from `to_dict()` output. Actions missing from `data`
        take their default; names that are no longer declared (or are now fixed)
        are ignored. The whole dict is validated first: on `KeyBindingError`
        nothing changes. Anything that is not a dict of strings (a corrupted
        save) is a `KeyBindingError` too.
        """
        if not isinstance(data, dict):
            raise KeyBindingError(f"bindings must be a dict, not {type(data).__name__}")
        for name, key_name in data.items():
            if not isinstance(name, str) or not isinstance(key_name, str):
                raise KeyBindingError(
                    f"bindings must map strings to strings, got {name!r}: {key_name!r}"
                )
        proposed = self._defaults()
        for name, key_name in data.items():
            if name in proposed:
                proposed[name] = _key_code(key_name)
        self._check_primaries(proposed)
        if proposed == self._primary:
            return
        self._set_primaries(proposed)
        self._fire()

    # -- change callbacks -------------------------------------------------

    def on_changed(self, callback: Callable[[], None]) -> None:
        """Registers `callback()`, called after bindings change (tooltips, labels)."""
        self._callbacks.append(callback)

    def remove_changed(self, callback: Callable[[], None]) -> None:
        self._callbacks.remove(callback)

    def _fire(self) -> None:
        run_callbacks(self._callbacks, label="input-map callbacks failed")


__all__ = ["InputMap", "KeyBindingError"]
