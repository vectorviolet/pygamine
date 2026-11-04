"""Tests for pygamine.util.input_map."""

from __future__ import annotations

import pygame
import pytest

from pygamine.util.input_map import InputMap, KeyBindingError


def make() -> InputMap:
    m = InputMap()
    m.declare("pause", pygame.K_SPACE)
    m.declare("tower1", pygame.K_1, alternates=[pygame.K_KP1])
    m.declare("tower2", pygame.K_2, alternates=[pygame.K_KP2])
    m.declare_fixed("menu", pygame.K_ESCAPE)
    m.declare_fixed("fullscreen", pygame.K_F11)
    return m


def key_event(key: int, kind: int = pygame.KEYDOWN) -> pygame.event.Event:
    return pygame.event.Event(kind, key=key)


def test_is_action_matches_primary_alternate_and_fixed() -> None:
    m = make()
    assert m.is_action(key_event(pygame.K_SPACE), "pause")
    assert m.is_action(key_event(pygame.K_KP1), "tower1")
    assert m.is_action(key_event(pygame.K_ESCAPE), "menu")
    assert not m.is_action(key_event(pygame.K_2), "tower1")
    assert not m.is_action(key_event(pygame.K_SPACE, pygame.KEYUP), "pause")
    assert not m.is_action(pygame.event.Event(pygame.MOUSEBUTTONDOWN), "pause")


def test_queries() -> None:
    m = make()
    assert m.actions() == ["pause", "tower1", "tower2", "menu", "fullscreen"]
    assert m.rebindable() == ["pause", "tower1", "tower2"]
    assert m.is_fixed("menu") and not m.is_fixed("pause")
    assert m.key_for("pause") == pygame.K_SPACE
    assert m.key_for("menu") == pygame.K_ESCAPE
    assert m.keys_for("tower1") == (pygame.K_1, pygame.K_KP1)
    with pytest.raises(KeyError):
        m.key_for("nope")


def test_rebind_applies_and_keeps_alternates() -> None:
    m = make()
    assert m.rebind("tower1", pygame.K_q) is None
    assert m.key_for("tower1") == pygame.K_q
    assert m.is_action(key_event(pygame.K_KP1), "tower1")
    assert not m.is_action(key_event(pygame.K_1), "tower1")
    assert m.rebind("tower1", pygame.K_q) is None  # same key: no-op


def test_rebind_conflict_reports_owner_and_changes_nothing() -> None:
    m = make()
    assert m.rebind("tower1", pygame.K_2) == "tower2"
    assert m.key_for("tower1") == pygame.K_1
    assert m.key_for("tower2") == pygame.K_2


def test_swap() -> None:
    m = make()
    m.swap("tower1", "tower2")
    assert m.key_for("tower1") == pygame.K_2
    assert m.key_for("tower2") == pygame.K_1
    assert m.keys_for("tower1") == (pygame.K_2, pygame.K_KP1)


def test_refuses_fixed_keys_and_actions() -> None:
    m = make()
    with pytest.raises(KeyBindingError, match="fixed action 'menu'"):
        m.rebind("pause", pygame.K_ESCAPE)
    with pytest.raises(KeyBindingError, match="alternate"):
        m.rebind("pause", pygame.K_KP2)
    with pytest.raises(KeyBindingError, match="alternate"):
        m.rebind("tower1", pygame.K_KP1)
    with pytest.raises(KeyBindingError, match="can't be rebound"):
        m.rebind("menu", pygame.K_q)
    with pytest.raises(KeyBindingError, match="can't be rebound"):
        m.swap("pause", "menu")
    assert m.key_for("pause") == pygame.K_SPACE


def test_reset_defaults() -> None:
    m = make()
    m.rebind("pause", pygame.K_p)
    m.swap("tower1", "tower2")
    m.reset_defaults()
    assert m.to_dict() == make().to_dict()


def test_to_dict_uses_key_names_and_skips_fixed() -> None:
    m = make()
    m.rebind("pause", pygame.K_p)
    assert m.to_dict() == {"pause": "p", "tower1": "1", "tower2": "2"}


def test_round_trip() -> None:
    a = make()
    a.rebind("pause", pygame.K_p)
    a.swap("tower1", "tower2")
    b = make()
    b.from_dict(a.to_dict())
    assert b.to_dict() == a.to_dict()


def test_from_dict_defaults_missing_and_ignores_unknown() -> None:
    m = make()
    m.rebind("tower1", pygame.K_q)
    m.from_dict({"pause": "p", "removed_action": "x", "menu": "q"})
    assert m.key_for("pause") == pygame.K_p
    assert m.key_for("tower1") == pygame.K_1
    assert m.key_for("menu") == pygame.K_ESCAPE


@pytest.mark.parametrize(
    "bad",
    [
        {"pause": "not a key"},
        {"pause": "1"},  # duplicate of tower1's default
        {"pause": "escape"},  # fixed key
        {"pause": "[2]"},  # alternate (keypad 2)
    ],
)
def test_from_dict_invalid_changes_nothing(bad: dict[str, str]) -> None:
    m = make()
    m.rebind("tower2", pygame.K_w)
    fired: list[int] = []
    m.on_changed(lambda: fired.append(1))
    before = m.to_dict()
    with pytest.raises(KeyBindingError):
        m.from_dict(bad)
    assert m.to_dict() == before
    assert fired == []


def test_callbacks_fire_on_change_only_and_unregister() -> None:
    m = make()
    calls: list[int] = []

    def cb() -> None:
        calls.append(1)

    m.on_changed(cb)
    m.rebind("pause", pygame.K_p)
    m.rebind("pause", pygame.K_p)  # no-op
    m.rebind("pause", pygame.K_2)  # conflict, no change
    assert len(calls) == 1
    m.swap("tower1", "tower2")
    m.reset_defaults()
    m.reset_defaults()  # already default
    assert len(calls) == 3
    m.remove_changed(cb)
    m.rebind("pause", pygame.K_p)
    assert len(calls) == 3


def test_callback_errors_all_run_then_raise_group() -> None:
    m = make()
    ran: list[str] = []

    def bad() -> None:
        ran.append("bad")
        raise RuntimeError("x")

    m.on_changed(bad)
    m.on_changed(lambda: ran.append("ok"))
    with pytest.raises(ExceptionGroup):
        m.rebind("pause", pygame.K_p)
    assert ran == ["bad", "ok"]
    assert m.key_for("pause") == pygame.K_p


def test_declare_validation() -> None:
    m = make()
    with pytest.raises(ValueError, match="already declared"):
        m.declare("pause", pygame.K_p)
    with pytest.raises(ValueError, match="reuses"):
        m.declare("other", pygame.K_SPACE)
    with pytest.raises(ValueError, match="reuses"):
        m.declare("other", pygame.K_p, alternates=[pygame.K_ESCAPE])
    with pytest.raises(ValueError, match="twice"):
        m.declare("other", pygame.K_p, alternates=[pygame.K_p])
    with pytest.raises(ValueError, match="at least one"):
        m.declare_fixed("other")
    assert "other" not in m.actions()
