"""Unit tests for GameObjectDict and GameObjectList: the two containers
PanelManager (dict, keyed by name) and free-standing entity lists (list)
use to fan out handle_event/update/draw, skipping objects that don't
support a method or are inactive.
"""

from __future__ import annotations

import pygame

from pygamine.ecs.game_object_dict import GameObjectDict
from pygamine.ecs.game_object_list import GameObjectList


class _Tracked:
    def __init__(self, active=True):
        self.active = active
        self.events = []
        self.updates = 0
        self.draws = 0

    def handle_event(self, event, mouse_pos):
        self.events.append(event)

    def update(self):
        self.updates += 1

    def draw(self, surface):
        self.draws += 1


class _NoMethods:
    """An object with none of handle_event/update/draw -- containers must
    tolerate this via hasattr, not assume every entry is a full GameObject."""

    pass


class _NoActiveFlag:
    """An object without an `active` attribute at all -- must be treated as
    always-active (the hasattr(obj, 'active') guard), not skipped."""

    def __init__(self):
        self.updates = 0

    def update(self):
        self.updates += 1


CONTAINERS = [GameObjectDict, GameObjectList]


def _put(container, obj, key="obj"):
    if isinstance(container, GameObjectDict):
        container[key] = obj
    else:
        container.append(obj)


def test_active_objects_receive_update_draw_and_events():
    for cls in CONTAINERS:
        container = cls()
        obj = _Tracked()
        _put(container, obj)

        event = pygame.event.Event(pygame.USEREVENT)
        container.handle_event(event, (0, 0))
        container.update()
        container.draw(pygame.Surface((1, 1)))

        assert obj.events == [event]
        assert obj.updates == 1
        assert obj.draws == 1


def test_inactive_objects_are_skipped():
    for cls in CONTAINERS:
        container = cls()
        obj = _Tracked(active=False)
        _put(container, obj)

        container.handle_event(pygame.event.Event(pygame.USEREVENT), (0, 0))
        container.update()
        container.draw(pygame.Surface((1, 1)))

        assert obj.events == []
        assert obj.updates == 0
        assert obj.draws == 0


def test_objects_missing_the_method_entirely_are_tolerated():
    for cls in CONTAINERS:
        container = cls()
        _put(container, _NoMethods())

        # must not raise for any of the three dispatch methods
        container.handle_event(pygame.event.Event(pygame.USEREVENT), (0, 0))
        container.update()
        container.draw(pygame.Surface((1, 1)))


def test_objects_without_an_active_attribute_are_treated_as_active():
    for cls in CONTAINERS:
        container = cls()
        obj = _NoActiveFlag()
        _put(container, obj)

        container.update()

        assert obj.updates == 1


def test_mixed_population_only_skips_the_inactive_ones():
    for cls in CONTAINERS:
        container = cls()
        active_obj = _Tracked(active=True)
        inactive_obj = _Tracked(active=False)
        _put(container, active_obj, "a")
        _put(container, inactive_obj, "b")

        container.update()

        assert active_obj.updates == 1
        assert inactive_obj.updates == 0
