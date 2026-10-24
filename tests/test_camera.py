"""Unit tests for Camera: world/screen coordinate transforms, edge-scroll,
zoom-at-cursor, and the offset clamping that keeps the map filling its
viewport instead of showing empty space past its edges.
"""
from __future__ import annotations

import pygame
import pytest

from pygamine.app.camera import Camera
from pygamine.ecs.components.sprite_renderer2d import SpriteRenderer2D
from pygamine.ecs.game_object import GameObject


@pytest.fixture
def camera():
    """An 800x600 viewport onto a 1600x1200 map (2x bigger in both axes) --
    big enough that there's real room to scroll and zoom out."""
    rect = pygame.Rect(0, 0, 800, 600)
    return Camera(rect, map_width=1600, map_height=1200)


# ── construction ───────────────────────────────────────────────────────────


def test_scroll_rect_defaults_to_rect():
    rect = pygame.Rect(0, 0, 800, 600)
    cam = Camera(rect)
    assert cam.scroll_rect is rect


def test_scroll_rect_can_be_overridden():
    rect = pygame.Rect(0, 0, 800, 600)
    scroll_rect = pygame.Rect(0, 0, 400, 300)
    cam = Camera(rect, scroll_rect=scroll_rect)
    assert cam.scroll_rect is scroll_rect


def test_map_size_defaults_to_rect_size():
    rect = pygame.Rect(0, 0, 800, 600)
    cam = Camera(rect)
    assert cam._map_width == 800
    assert cam._map_height == 600


def test_initial_state_is_unscaled_and_uncentered():
    rect = pygame.Rect(0, 0, 800, 600)
    cam = Camera(rect)
    assert cam.scale == 1.0
    assert (cam._offset.x, cam._offset.y) == (0.0, 0.0)


# ── world_to_screen / screen_to_world ──────────────────────────────────


def test_world_to_screen_with_no_offset_or_scale_is_identity_plus_rect_origin():
    rect = pygame.Rect(50, 20, 800, 600)
    cam = Camera(rect)
    result = cam.world_to_screen((10, 5))
    assert (result.x, result.y) == (60, 25)


def test_world_to_screen_applies_offset_and_scale():
    rect = pygame.Rect(50, 20, 800, 600)
    cam = Camera(rect)
    cam._offset.update(30, -10)
    cam.scale = 2.0

    result = cam.world_to_screen((10, 5))

    assert (result.x, result.y) == (100, 20)


def test_screen_to_world_is_the_inverse_of_world_to_screen():
    rect = pygame.Rect(50, 20, 800, 600)
    cam = Camera(rect)
    cam._offset.update(30, -10)
    cam.scale = 2.0

    screen_pos = cam.world_to_screen((123, 45))
    back = cam.screen_to_world(screen_pos)

    assert back.x == pytest.approx(123)
    assert back.y == pytest.approx(45)


# ── scale_image / scaled ────────────────────────────────────────────────


def test_scale_image_returns_same_object_when_scale_is_one(camera):
    image = pygame.Surface((10, 10))
    assert camera.scale_image(image) is image


def test_scale_image_scales_when_scale_is_not_one(camera):
    camera.scale = 2.0
    image = pygame.Surface((10, 20))
    scaled = camera.scale_image(image)
    assert scaled.get_size() == (20, 40)


def test_scaled_multiplies_length_by_scale(camera):
    camera.scale = 1.5
    assert camera.scaled(10) == 15


# ── draw ──────────────────────────────────────────────────────────────


def test_draw_blits_sprite_renderer_image_centered_at_world_position(camera):
    entity = GameObject()
    entity.rect.size = (10, 10)
    entity.rect.center = (100, 100)
    renderer = entity.add_component(SpriteRenderer2D)
    image = pygame.Surface((10, 10))
    image.fill((255, 0, 0))
    renderer.set_image(image)

    surface = pygame.Surface((800, 600))
    surface.fill((0, 255, 0))

    camera.draw(surface, entity)

    assert surface.get_at((100, 100)) == (255, 0, 0, 255)
    assert surface.get_at((0, 0)) == (0, 255, 0, 255)


def test_draw_uses_whatever_the_entitys_own_image_property_returns(camera):
    """draw() only ever reads entity.image -- it has no opinion on *why*
    that might differ from a plain SpriteRenderer2D's image (rotation,
    an animation frame, ...); that choice belongs entirely to the entity,
    e.g. a RotatableObject-style class overriding GameObject's default
    `image` property (see ecs/game_object.py) to switch between a rotated
    variant and its base sprite."""
    class _CustomImage:
        def __init__(self):
            self.image = pygame.Surface((10, 10))
            self.image.fill((0, 0, 255))
            self.rect = pygame.Rect(0, 0, 10, 10)
            self.rect.center = (50, 50)

    entity = _CustomImage()
    surface = pygame.Surface((800, 600))
    surface.fill((0, 255, 0))

    camera.draw(surface, entity)

    assert surface.get_at((50, 50)) == (0, 0, 255, 255)


def test_draw_uses_the_game_objects_default_image_property(camera):
    """GameObject's own `.image` property (the default Drawable
    implementation) resolves to its SpriteRenderer2D's image -- draw()
    doesn't need to know a component is involved at all."""
    entity = GameObject()
    entity.rect.size = (10, 10)
    entity.rect.center = (60, 60)
    renderer = entity.add_component(SpriteRenderer2D)
    image = pygame.Surface((10, 10))
    image.fill((255, 0, 255))
    renderer.set_image(image)

    surface = pygame.Surface((800, 600))
    surface.fill((0, 255, 0))

    camera.draw(surface, entity)

    assert surface.get_at((60, 60)) == (255, 0, 255, 255)


# ── handle_event: zoom via mouse wheel ──────────────────────────────────


def test_mousewheel_inside_viewport_zooms(camera):
    event = pygame.event.Event(pygame.MOUSEWHEEL, y=1)
    camera.handle_event(event, (400, 300))
    assert camera.scale > 1.0


def test_mousewheel_outside_viewport_is_ignored(camera):
    event = pygame.event.Event(pygame.MOUSEWHEEL, y=1)
    camera.handle_event(event, (900, 300))  # x=900 is outside the 800-wide rect
    assert camera.scale == 1.0


def test_unrelated_event_type_is_ignored(camera):
    event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a)
    camera.handle_event(event, (400, 300))
    assert camera.scale == 1.0


# ── update_with_mouse: edge scroll ──────────────────────────────────────


def test_mouse_in_the_middle_does_not_scroll(camera):
    camera.update_with_mouse((400, 300))
    assert (camera._offset.x, camera._offset.y) == (0, 0)


def test_mouse_outside_scroll_rect_does_not_scroll(camera):
    camera.update_with_mouse((-10, -10))
    assert (camera._offset.x, camera._offset.y) == (0, 0)


def test_mouse_near_right_edge_scrolls_camera_right(camera):
    """Scrolling right pans the world left on screen, so the offset
    decreases (see world_to_screen's `rect.left + offset + world * scale`)."""
    camera.update_with_mouse((780, 300))  # within 30px of the 800-wide rect's right edge
    assert camera._offset.x == -10
    assert camera._offset.y == 0


def test_mouse_near_left_edge_scrolls_camera_left():
    rect = pygame.Rect(0, 0, 800, 600)
    cam = Camera(rect, map_width=1600, map_height=1200)
    cam._offset.x = -100  # start scrolled right so there's room to scroll back left

    cam.update_with_mouse((10, 300))

    assert cam._offset.x == -90


def test_mouse_near_top_and_bottom_edges_scroll_vertically():
    rect = pygame.Rect(0, 0, 800, 600)
    cam = Camera(rect, map_width=1600, map_height=1200)

    cam.update_with_mouse((400, 590))  # near bottom
    assert cam._offset.y == -10

    cam._offset.y = -100
    cam.update_with_mouse((400, 10))  # near top
    assert cam._offset.y == -90


def test_mouse_near_a_corner_scrolls_both_axes():
    """Diagonal scroll applies dx and dy in the same call. Starting already
    scrolled away from (0, 0) so there's room to move on both axes -- offset
    is clamped to <= 0 (see the clamp tests below), so starting fresh at
    (0, 0) and scrolling toward a top/left edge would just get clamped
    straight back to 0, which wouldn't demonstrate the diagonal move."""
    rect = pygame.Rect(0, 0, 800, 600)
    cam = Camera(rect, map_width=1600, map_height=1200)
    cam._offset.update(-100, -100)

    cam.update_with_mouse((10, 10))  # near left AND top

    assert cam._offset.x == -90
    assert cam._offset.y == -90


def test_mouse_near_top_left_corner_from_origin_is_clamped_back_to_zero():
    """The flip side of the above: at the (0, 0) boundary (map's top-left
    already fully visible), scrolling further toward that same corner has
    nowhere to go and is clamped right back."""
    rect = pygame.Rect(0, 0, 800, 600)
    cam = Camera(rect, map_width=1600, map_height=1200)

    cam.update_with_mouse((10, 10))  # near left AND top, but already at (0, 0)

    assert (cam._offset.x, cam._offset.y) == (0, 0)


def test_edge_scroll_is_clamped_at_the_map_boundary():
    rect = pygame.Rect(0, 0, 800, 600)
    cam = Camera(rect, map_width=1600, map_height=1200)
    cam._offset.x = -795  # 5px away from the -800 clamp limit

    cam.update_with_mouse((780, 300))  # would move -10, overshooting the limit

    assert cam._offset.x == -800


# ── _zoom_at / zoom clamping ─────────────────────────────────────────


def test_zoom_keeps_world_point_under_cursor_stationary(camera):
    """The actual point of zoom-at-cursor: whatever world position was under
    the mouse before zooming must still be under the mouse afterward."""
    mouse_pos = (300, 250)
    world_before = camera.screen_to_world(mouse_pos)

    camera._zoom_at(mouse_pos, 1.5)

    world_after_on_screen = camera.world_to_screen(world_before)
    assert world_after_on_screen.x == pytest.approx(mouse_pos[0])
    assert world_after_on_screen.y == pytest.approx(mouse_pos[1])


def test_zoom_is_clamped_to_zoom_max():
    rect = pygame.Rect(0, 0, 800, 600)
    cam = Camera(rect, map_width=1600, map_height=1200, zoom_max=2.0)
    cam._zoom_at((400, 300), 50.0)
    assert cam.scale == 2.0


def test_zoom_out_is_clamped_so_the_map_still_fills_the_viewport():
    """The floor isn't just zoom_min -- it's max(zoom_min, fit_floor), so you
    can never zoom out past the point where the map stops covering the
    viewport and empty space would show."""
    rect = pygame.Rect(0, 0, 800, 600)
    cam = Camera(rect, map_width=1600, map_height=1200, zoom_min=0.1)
    # fit_floor = max(800/1600, 600/1200) = 0.5, above zoom_min(0.1)
    cam._zoom_at((400, 300), 0.01)
    assert cam.scale == 0.5


def test_zoom_requesting_the_current_scale_is_a_no_op(camera):
    camera._offset.update(-50, -50)
    camera._zoom_at((400, 300), 1.0)  # already at scale 1.0
    assert camera.scale == 1.0
    assert (camera._offset.x, camera._offset.y) == (-50, -50)


# ── _clamp_offset ───────────────────────────────────────────────────────


def test_clamp_offset_keeps_offset_within_map_bounds_when_map_is_larger():
    rect = pygame.Rect(0, 0, 800, 600)
    cam = Camera(rect, map_width=1600, map_height=1200)
    cam._offset.update(500, 500)  # way out of range (offset must be <= 0)

    cam._clamp_offset()

    assert cam._offset.x == 0
    assert cam._offset.y == 0

    cam._offset.update(-5000, -5000)  # way past the other end
    cam._clamp_offset()
    assert cam._offset.x == -800  # rect.width(800) - scaled_w(1600)
    assert cam._offset.y == -600  # rect.height(600) - scaled_h(1200)


def test_clamp_offset_forces_zero_when_map_is_smaller_than_viewport():
    """When the map doesn't fill the viewport, there's nowhere to scroll to
    -- offset is pinned to exactly 0 regardless of what it's set to."""
    rect = pygame.Rect(0, 0, 800, 600)
    cam = Camera(rect, map_width=400, map_height=300)
    cam._offset.update(123, -45)

    cam._clamp_offset()

    assert (cam._offset.x, cam._offset.y) == (0, 0)


# ── info ────────────────────────────────────────────────────────────────


def test_info_reports_rounded_offset_and_scale(camera):
    camera._offset.update(-10.456, 20.789)
    camera.scale = 1.23456
    label, data = camera.info()
    assert label == "Camera Info:"
    assert data["offset"] == (-10.5, 20.8)
    assert data["scale"] == 1.23


def test_edge_scroll_distance_scales_with_frames():
    """frames lets a caller keep the scroll rate frame-rate independent:
    half a frame's worth of time moves half as far, two frames' twice."""
    rect = pygame.Rect(0, 0, 800, 600)
    cam = Camera(rect, map_width=1600, map_height=1200)

    cam.update_with_mouse((780, 300), frames=0.5)
    assert cam._offset.x == -5

    cam.update_with_mouse((780, 300), frames=2.0)
    assert cam._offset.x == -25


# ── center_on ────────────────────────────────────────────────────────


def test_center_on_puts_the_world_point_at_the_viewport_centre():
    rect = pygame.Rect(0, 0, 800, 600)
    cam = Camera(rect, map_width=1600, map_height=1200)

    cam.center_on((800, 600))

    assert cam.world_to_screen((800, 600)) == pygame.math.Vector2(400, 300)


def test_center_on_is_clamped_at_the_map_edges():
    """A point near a corner can't be centred without showing past the
    map edge, so the offset stops at the boundary like an edge scroll."""
    rect = pygame.Rect(0, 0, 800, 600)
    cam = Camera(rect, map_width=1600, map_height=1200)

    cam.center_on((1590, 10))  # top-right corner

    assert (cam._offset.x, cam._offset.y) == (-800, 0)


def test_center_on_accounts_for_zoom():
    rect = pygame.Rect(0, 0, 800, 600)
    cam = Camera(rect, map_width=1600, map_height=1200)
    cam.scale = 2.0

    cam.center_on((800, 600))

    assert cam.world_to_screen((800, 600)) == pygame.math.Vector2(400, 300)
