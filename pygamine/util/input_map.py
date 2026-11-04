"""Rebindable keyboard actions.

A game declares actions with `InputMap.declare` (one rebindable primary key plus
optional fixed alternates) and `InputMap.declare_fixed` (keys that can never be
rebound, such as Esc). Event code then asks `is_action(event, "pause")` instead of
comparing `event.key`. Bindings round-trip through plain dicts of key names
(`pygame.key.name`), so the game can store them in its own settings.

Invariant: every key belongs to at most one action, and a primary key is never
also an alternate or fixed key. Nothing here draws UI or touches a save file; a
CONTROLS screen is the game's job.
"""

from __future__ import annotations

from typing import Callable, Iterable

import pygame


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
    name = pygame.key.name(key)
    if not name:
        raise KeyBindingError(f"key code {key} has no name")
    return name


def _key_code(name: str) -> int:
    try:
        return pygame.key.key_code(name)
    except (ValueError, TypeError) as error:
        raise KeyBindingError(f"unknown key name {name!r}") from error


class InputMap:
    """Named actions bound to keyboard keys, with rebinding and save/load."""

    def __init__(self) -> None:
        self._actions: dict[str, _Action] = {}
        self._primary: dict[str, int] = {}
        self._callbacks: list[Callable[[], None]] = []

    # -- declaring --------------------------------------------------------

    def declare(self, name: str, default: int, alternates: Iterable[int] = ()) -> None:
        """Adds a rebindable action: primary key `default` plus fixed `alternates`
        that keep working when the primary changes."""
        action = _Action(name, default, tuple(alternates))
        self._check_new(action, [default, *action.keys])
        self._actions[name] = action
        self._primary[name] = default

    def declare_fixed(self, name: str, *keys: int) -> None:
        """Adds an action whose keys can't be rebound (Esc, F11). It is listed in
        `actions()` but not in `rebindable()` or `to_dict()`."""
        if not keys:
            raise ValueError(f"fixed action {name!r} needs at least one key")
        action = _Action(name, None, keys)
        self._check_new(action, list(keys))
        self._actions[name] = action

    def _check_new(self, action: _Action, keys: list[int]) -> None:
        if action.name in self._actions:
            raise ValueError(f"action {action.name!r} is already declared")
        if len(set(keys)) != len(keys):
            raise ValueError(f"action {action.name!r} lists a key twice")
        taken = {k for a in self._actions.values() for k in self._all_keys(a)}
        if taken & set(keys):
            raise ValueError(f"action {action.name!r} reuses a declared key")

    def _all_keys(self, action: _Action) -> tuple[int, ...]:
        return self.keys_for(action.name) if action.name in self._actions else ()

    def _defaults(self) -> dict[str, int]:
        return {n: a.default for n, a in self._actions.items() if a.default is not None}

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
        return event.type == pygame.KEYDOWN and event.key in self.keys_for(name)

    def _get(self, name: str) -> _Action:
        try:
            return self._actions[name]
        except KeyError:
            raise KeyError(f"unknown action {name!r}") from None

    def _reserved_by(self, key: int) -> str | None:
        """The action that owns `key` as a fixed or alternate key, if any."""
        for action in self._actions.values():
            if key in action.keys:
                return action.name
        return None

    # -- changing ---------------------------------------------------------

    def rebind(self, name: str, key: int) -> str | None:
        """Sets the primary key of `name` to `key`.

        Returns None when the key was applied (or already was `name`'s primary).
        If another action's primary key is `key`, nothing changes and that
        action's name is returned so the game can ask the player and call `swap`.
        Raises `KeyBindingError` if `name` is fixed, or `key` is a fixed key or
        an alternate of any action.
        """
        if self._get(name).fixed:
            raise KeyBindingError(f"action {name!r} is fixed and can't be rebound")
        if self._primary[name] == key:
            return None
        owner = self._reserved_by(key)
        if owner is not None:
            kind = "fixed" if self._actions[owner].fixed else "an alternate of"
            raise KeyBindingError(f"{_key_name(key)} is {kind} action {owner!r}")
        for other_name, other_key in self._primary.items():
            if other_key == key:
                return other_name
        self._primary[name] = key
        self._fire()
        return None

    def swap(self, a: str, b: str) -> None:
        """Exchanges the primary keys of two rebindable actions."""
        for name in (a, b):
            if self._get(name).fixed:
                raise KeyBindingError(f"action {name!r} is fixed and can't be rebound")
        if a == b:
            return
        self._primary[a], self._primary[b] = self._primary[b], self._primary[a]
        self._fire()

    def reset_defaults(self) -> None:
        """Restores every primary key to its declared default."""
        defaults = self._defaults()
        if defaults == self._primary:
            return
        self._primary = defaults
        self._fire()

    # -- saving -----------------------------------------------------------

    def to_dict(self) -> dict[str, str]:
        """`{action: key name}` for the rebindable actions, for the game's settings."""
        return {n: _key_name(k) for n, k in self._primary.items()}

    def from_dict(self, data: dict[str, str]) -> None:
        """Loads bindings from `to_dict()` output. Actions missing from `data`
        take their default; names that are no longer declared (or are now fixed)
        are ignored. The whole dict is validated first: on `KeyBindingError`
        nothing changes.
        """
        proposed = self._defaults()
        for name, key_name in data.items():
            if name in proposed:
                proposed[name] = _key_code(key_name)
        used: dict[int, str] = {}
        for name, key in proposed.items():
            if key in used:
                raise KeyBindingError(
                    f"{_key_name(key)} is bound to both {used[key]!r} and {name!r}"
                )
            used[key] = name
            owner = self._reserved_by(key)
            if owner is not None:
                raise KeyBindingError(
                    f"{_key_name(key)} for {name!r} is reserved by {owner!r}"
                )
        if proposed == self._primary:
            return
        self._primary = proposed
        self._fire()

    # -- change callbacks -------------------------------------------------

    def on_changed(self, callback: Callable[[], None]) -> None:
        """Registers `callback()`, called after bindings change (tooltips, labels)."""
        self._callbacks.append(callback)

    def remove_changed(self, callback: Callable[[], None]) -> None:
        self._callbacks.remove(callback)

    def _fire(self) -> None:
        errors: list[Exception] = []
        for callback in list(self._callbacks):
            try:
                callback()
            except Exception as error:
                errors.append(error)
        if errors:
            raise ExceptionGroup("input-map callbacks failed", errors)


__all__ = ["InputMap", "KeyBindingError"]
