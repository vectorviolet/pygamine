from __future__ import annotations

from typing import Protocol, runtime_checkable

import pygame
from pygame.math import Vector2

from pygamine.assets.image import scale_by

EDGE_SCROLL_ZONE = 30
CAMERA_SPEED     = 10
ZOOM_STEP        = 0.10
ZOOM_MIN         = 0.5
ZOOM_MAX         = 2.0


@runtime_checkable
class Drawable(Protocol):
    """What Camera.draw() needs from an entity -- deliberately just this,
    so Camera never has to know about ECS components, rotation state, or
    any other entity-specific concept. GameObject already satisfies this
    via its own `.image` property (see ecs/game_object.py, which resolves
    to the attached SpriteRenderer2D's image by default); an entity that
    switches between multiple images (e.g. a rotated variant of its base
    sprite) overrides that property itself instead of Camera guessing via
    getattr(entity, 'is_rotated', False) the way this used to work."""
    rect: pygame.Rect
    image: pygame.Surface


class Camera:
    def __init__(self, rect, map_width=None, map_height=None, scroll_rect=None, *,
                 edge_scroll_zone: int = EDGE_SCROLL_ZONE,
                 speed: int = CAMERA_SPEED,
                 zoom_step: float = ZOOM_STEP,
                 zoom_min: float = ZOOM_MIN,
                 zoom_max: float = ZOOM_MAX) -> None:
        self.rect        = rect
        self.scroll_rect = scroll_rect or rect
        self._offset     = Vector2(0.0, 0.0)
        self.scale       = 1.0
        self._map_width  = map_width  or rect.width
        self._map_height = map_height or rect.height

        self._edge_scroll_zone = edge_scroll_zone
        self._speed            = speed
        self._zoom_step        = zoom_step
        self._zoom_min         = zoom_min
        self._zoom_max         = zoom_max

    # ── transforms ────────────────────────────────────────────────────────────

    def world_to_screen(self, world_pos) -> Vector2:
        return Vector2(self.rect.left + self._offset.x + world_pos[0] * self.scale,
                       self.rect.top  + self._offset.y + world_pos[1] * self.scale)

    def screen_to_world(self, screen_pos) -> Vector2:
        return Vector2((screen_pos[0] - self.rect.left - self._offset.x) / self.scale,
                       (screen_pos[1] - self.rect.top  - self._offset.y) / self.scale)

    def scale_image(self, image: pygame.Surface) -> pygame.Surface:
        return image if abs(self.scale - 1.0) < 1e-6 else scale_by(image, self.scale)

    def scaled(self, world_length: float) -> float:
        return world_length * self.scale

    # ── drawing ───────────────────────────────────────────────────────────────

    def draw(self, surface: pygame.Surface, entity: Drawable) -> None:
        scaled = self.scale_image(entity.image)
        center = self.world_to_screen(entity.rect.center)
        rect   = scaled.get_rect(center=(int(center.x), int(center.y)))
        surface.blit(scaled, rect)

    # ── input ─────────────────────────────────────────────────────────────────

    def handle_event(self, event, mouse_pos) -> None:
        if event.type == pygame.MOUSEWHEEL and self._inside_viewport(mouse_pos):
            self._zoom_at(mouse_pos, self.scale * (1.0 + self._zoom_step * event.y))

    def center_on(self, world_pos) -> None:
        """Scroll so `world_pos` sits at the viewport centre, as far as the
        map edges allow (the offset is clamped like any other scroll)."""
        self._offset.x = self.rect.width  / 2 - world_pos[0] * self.scale
        self._offset.y = self.rect.height / 2 - world_pos[1] * self.scale
        self._clamp_offset()

    def update_with_mouse(self, mouse_pos, frames: float = 1.0) -> None:
        """Edge-scroll by `speed` px per frame. `frames` is how many frames'
        worth of motion this call covers -- pass elapsed_ms / frame_ms to
        keep the scroll rate independent of the actual frame rate."""
        if not self.scroll_rect.collidepoint(mouse_pos):
            return
        mx, my = mouse_pos
        step = self._speed * frames
        dx = dy = 0
        if mx > self.scroll_rect.right  - self._edge_scroll_zone: dx = -step
        if mx < self.scroll_rect.left   + self._edge_scroll_zone: dx = +step
        if my > self.scroll_rect.bottom - self._edge_scroll_zone: dy = -step
        if my < self.scroll_rect.top    + self._edge_scroll_zone: dy = +step
        if dx or dy:
            self._offset.x += dx
            self._offset.y += dy
            self._clamp_offset()

    # ── internals ─────────────────────────────────────────────────────────────

    def _inside_viewport(self, screen_pos) -> bool:
        return self.rect.collidepoint(screen_pos)

    def _zoom_at(self, screen_pos, target_scale: float) -> None:
        fit_floor = max(self.rect.width / self._map_width,
                        self.rect.height / self._map_height)
        floor = max(self._zoom_min, fit_floor)
        new_scale = max(floor, min(self._zoom_max, target_scale))
        if new_scale == self.scale:
            return
        world_under_cursor = self.screen_to_world(screen_pos)
        self.scale     = new_scale
        self._offset.x = screen_pos[0] - self.rect.left - world_under_cursor.x * new_scale
        self._offset.y = screen_pos[1] - self.rect.top  - world_under_cursor.y * new_scale
        self._clamp_offset()

    def _clamp_offset(self) -> None:
        scaled_w = self._map_width  * self.scale
        scaled_h = self._map_height * self.scale
        min_x = min(0, self.rect.width  - scaled_w)
        min_y = min(0, self.rect.height - scaled_h)
        self._offset.x = max(min_x, min(0, self._offset.x))
        self._offset.y = max(min_y, min(0, self._offset.y))

    def info(self) -> tuple[str, dict]:
        return "Camera Info:", {
            "offset": (round(self._offset.x, 1), round(self._offset.y, 1)),
            "scale":  round(self.scale, 2),
        }
