"""Generic widget factories for PanelLoader.

Each `make_*_factory(assets)` returns a callable `(cfg, parent) -> object` that
PanelLoader invokes for entries with the matching `type:` key. Projects that
need project-specific factories (e.g. menus, buttons) define their own and
register them alongside these.
"""

from __future__ import annotations

from typing import Any, Callable

import pygame

from pygamine.assets.asset_resolver import AssetResolver
from pygamine.assets.font import load_font
from pygamine.assets.sprite_sheet import SpriteSheet
from pygamine.ui_widgets.text_object import TextObject
from pygamine.ui_widgets.slider import Slider
from pygamine.ui_widgets.scrolling_panel import ScrollingPanel
from pygamine.ecs.animated_sprite import AnimatedSprite
from pygamine.ecs.components.transform import Transform
from pygamine.ecs.state_object import StateObject, HoverableStateObject


def _state_asset(assets: AssetResolver, value: Any) -> Any:
    """Resolves a manifest key (str) to an image path; passes anything else through."""
    return assets.image_path(value) if isinstance(value, str) else value


def _build_color_object(cfg: dict, parent: Transform, size: Any) -> StateObject:
    obj = StateObject(
        parent=parent,
        pos=cfg["position"],
        size=size,
        image_path=None,
        anchor=cfg.get("anchor", "top-left"),
    )
    surf = pygame.Surface(size, pygame.SRCALPHA)
    surf.fill(tuple(cfg["color"]))
    obj.images[None] = surf
    obj.set_state(None)
    return obj


def _build_hoverable_object(
    assets: AssetResolver, cfg: dict, parent: Transform, size: Any
) -> HoverableStateObject:
    obj = HoverableStateObject(
        parent=parent,
        pos=cfg["position"],
        size=size,
        image_path=cfg.get("asset"),
        hover_image_path=cfg.get("hover"),
        nine_slice=cfg.get("nine_slice", 0),
        anchor=cfg.get("anchor", "top-left"),
    )
    for state_key, state_cfg in cfg.get("states", {}).items():
        obj.add_state(
            state_key,
            _state_asset(assets, state_cfg["asset"]),
            _state_asset(assets, state_cfg.get("hover")),
        )
    return obj


def _build_image_object(cfg: dict, parent: Transform, size: Any) -> StateObject:
    return StateObject(
        parent=parent,
        pos=cfg["position"],
        size=size,
        image_path=cfg.get("asset"),
        nine_slice=cfg.get("nine_slice", 0),
        anchor=cfg.get("anchor", "top-left"),
    )


def make_factory(assets: AssetResolver) -> Callable[[dict, Transform], StateObject]:
    def make_gui_object(cfg: dict, parent: Transform) -> StateObject:
        size = tuple(cfg["size"]) if cfg["size"] != "WINDOW" else parent.size

        obj: StateObject
        if cfg.get("color") is not None and cfg.get("asset") is None:
            obj = _build_color_object(cfg, parent, size)
        elif cfg.get("hover") is not None or cfg.get("states", {}):
            obj = _build_hoverable_object(assets, cfg, parent, size)
        else:
            obj = _build_image_object(cfg, parent, size)

        click_sound = cfg.get("on_click_sound")
        if click_sound:
            obj.on_click_sound = assets.sound_path(click_sound)
        return obj

    return make_gui_object


def make_animated_factory(
    assets: AssetResolver,
) -> Callable[[dict, Transform], AnimatedSprite]:
    def make_animated_object(cfg: dict, parent: Transform) -> AnimatedSprite:
        pos = cfg["position"]
        size = tuple(cfg["size"]) if cfg.get("size") not in (None, "WINDOW") else (0, 0)
        sheet_path = cfg["asset"]  # pre-resolved to ImagePath by PanelLoader
        frame_count = cfg.get("frame_count", 1)
        fps = cfg.get("fps", 12.0)
        loop = cfg.get("loop", True)
        horizontal = cfg.get("horizontal", True)

        frames = SpriteSheet.from_path(sheet_path).strip(
            frame_count, horizontal=horizontal
        )
        return AnimatedSprite(
            parent=parent, pos=pos, size=size, frames=frames, fps=fps, loop=loop
        )

    return make_animated_object


def make_slider_factory(assets: AssetResolver) -> Callable[[dict, Transform], Slider]:
    def make_slider(cfg: dict, parent: Transform) -> Slider:
        return Slider(
            parent=parent,
            pos=cfg["position"],
            size=tuple(cfg.get("size", (300, 24))),
            value=cfg.get("value", 1.0),
            anchor=cfg.get("anchor", "top-left"),
        )

    return make_slider


def make_scrolling_panel_factory(
    assets: AssetResolver,
) -> Callable[[dict, Transform], ScrollingPanel]:
    def make_scrolling_panel(cfg: dict, parent: Transform) -> ScrollingPanel:
        size = (
            tuple(cfg["size"]) if cfg.get("size", "WINDOW") != "WINDOW" else parent.size
        )
        return ScrollingPanel(
            parent=parent,
            pos=cfg.get("position", (0, 0)),
            size=size,
            targets=cfg.get("targets", []),
            speed=cfg.get("speed", 60.0),
            loop=cfg.get("loop", True),
            anchor=cfg.get("anchor", "top-left"),
        )

    return make_scrolling_panel


def make_text_factory(assets: AssetResolver) -> Callable[[dict, Transform], TextObject]:
    def make_text_object(cfg: dict, parent: Transform) -> TextObject:
        return TextObject(
            parent,
            cfg["position"],
            cfg.get("text", ""),
            load_font(cfg, assets),
            cfg.get("color", [255, 255, 255]),
            cfg.get("background_color"),
            padding=cfg.get("padding"),
            anchor=cfg.get("anchor", "top-left"),
            states=cfg.get("states"),
            text_key=cfg.get("text_key"),
        )

    return make_text_object
