from __future__ import annotations

from pygamine.assets.asset_resolver import AssetResolver
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable
import yaml

from pygamine.ecs.components.transform import Transform
from pygamine.ecs.game_object import GameObject

if TYPE_CHECKING:
    from pygamine.ui_widgets.tooltip import TooltipManager

# Factory signature: config dict + parent Transform → object
ObjectFactory = Callable[[dict, Transform], Any]

# Keys allowed in an object's `tooltip:` mapping.
TOOLTIP_KEYS = frozenset({"text_key", "action", "text_params"})


def require_mapping(where: str, value: Any) -> dict:
    """Returns `value` if it is a mapping; otherwise raises a ValueError naming
    `where`. An empty YAML entry (`name:`) reads as None and lands here."""
    if not isinstance(value, dict):
        raise ValueError(f"{where} must be a mapping, got {value!r}")
    return value


def _where(tab: str, name: str) -> str:
    """How error messages refer to one object of one panel."""
    return f"Object '{name}' in panel '{tab}'"


class PanelLoader:
    """Reads panel definitions from a YAML file and loads them into PanelManager."""

    def __init__(
        self,
        panel_manager,
        window_transform: Transform,
        asset_manager: AssetResolver,
        tooltips: TooltipManager | None = None,
    ) -> None:
        self.panel_manager = panel_manager
        # Needed by objects with a `tooltip:` entry; None means none are allowed.
        self.tooltips = tooltips
        # (object name, object, tooltip config) of the panel being loaded.
        self._pending_tooltips: list[tuple[str, Any, dict]] = []
        self.window_transform = window_transform
        self.assets = asset_manager
        self._factories: dict[str, ObjectFactory] = {}
        self._default_type: str | None = None
        # Global UI scale applied to every object's geometry at load time (see
        # _scale_def). authored_size is the resolution the YAML positions were
        # written for; when the actual window differs (e.g. a lower mobile render
        # resolution), window-parented chrome is remapped from the authored centre
        # to the actual centre so it tracks the panel instead of drifting off.
        self.scale: float = 1.0
        self.authored_size: tuple[int, int] | None = None

    def register(
        self, type_name: str, factory: ObjectFactory, *, default: bool = False
    ) -> None:
        self._factories[type_name] = factory
        if default:
            self._default_type = type_name

    def load(self, path: str | Path) -> None:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Panel definition not found: {path}")
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        # Checked before _preprocess, which reads panels and groups as mappings.
        for group_name, group_def in (data.get("groups", {}) or {}).items():
            require_mapping(f"Group '{group_name}'", group_def)
        for tab, panel_def in (data.get("panels", {}) or {}).items():
            require_mapping(f"Panel '{tab}'", panel_def)

        self._preprocess(data)

        groups = data.get("groups", {}) or {}
        for tab, panel_def in (data.get("panels", {}) or {}).items():
            self._load_panel(tab, panel_def, groups)

    def _preprocess(self, data: dict) -> None:
        """Hook: transform the parsed YAML in place before panels are loaded.
        No-op here; subclasses override it (see PanelLoaderExt)."""

    def _load_panel(self, tab: str, panel_def: dict, groups: dict) -> None:
        self._pending_tooltips = []
        for group_name in panel_def.get("extends", []) or []:
            for obj_name, obj_def in groups[group_name].items():
                self._add_object(tab, obj_name, obj_def)
        for obj_name, obj_def in (panel_def.get("objects", {}) or {}).items():
            self._add_object(tab, obj_name, obj_def)
        self._add_tooltips(tab)
        self._notify_panel_loaded(tab)

    def _add_tooltips(self, tab: str) -> None:
        """Adds a `Tooltip` for every object that declared one, named
        `<object>.tooltip`. They go in after all other objects so they draw on
        top of the panel."""
        pending, self._pending_tooltips = self._pending_tooltips, []
        if not pending:
            return
        from pygamine.ui_widgets.tooltip import Tooltip

        assert self.tooltips is not None  # checked in _check_tooltip_def
        for name, target, config in pending:
            self.panel_manager.add_object(
                tab,
                f"{name}.tooltip",
                Tooltip(
                    self.tooltips,
                    target,
                    self.window_transform,
                    config["text_key"],
                    config.get("action"),
                    config.get("text_params"),
                ),
            )

    def _check_tooltip_def(self, tab: str, name: str, config: Any) -> dict:
        where = _where(tab, name)
        if self.tooltips is None:
            raise ValueError(f"{where} has a tooltip but the loader has no tooltips")
        if not isinstance(config, dict):
            raise ValueError(f"{where}: tooltip must be a mapping")
        unknown = set(config) - TOOLTIP_KEYS
        if unknown:
            raise ValueError(
                f"{where}: unknown tooltip keys {sorted(unknown)}; "
                f"allowed: {sorted(TOOLTIP_KEYS)}"
            )
        self._check_tooltip_content(where, config)
        return config

    def _check_tooltip_content(self, where: str, config: dict) -> None:
        """Checks types, that the action exists and that the text renders."""
        assert self.tooltips is not None
        text_key = config.get("text_key")
        if not isinstance(text_key, str):
            raise ValueError(f"{where}: tooltip needs a text_key string")
        params = config.get("text_params", {})
        if not isinstance(params, dict) or not all(isinstance(k, str) for k in params):
            raise ValueError(f"{where}: tooltip text_params must map names to values")
        action = config.get("action")
        if action is not None:
            if not isinstance(action, str):
                raise ValueError(f"{where}: tooltip action must be a string")
            try:
                self.tooltips.input_map.key_for(action)
            except KeyError:
                raise ValueError(f"{where}: tooltip action {action!r} is unknown")
        try:
            self.tooltips.localization.tr(text_key, **params)
        except (KeyError, IndexError, ValueError) as error:
            raise ValueError(
                f"{where}: tooltip text_key {text_key!r} can't be rendered: {error}"
            ) from error

    def _notify_panel_loaded(self, tab: str) -> None:
        """Calls `on_panel_loaded(panel)` on every object of the just-loaded
        panel that defines it -- for objects that need their siblings, which
        may be declared after them (e.g. ScrollingPanel adopting its targets).
        Iterates a snapshot, since a hook may remove objects from the panel."""
        if tab not in self.panel_manager:
            return
        panel = self.panel_manager[tab]
        for obj in list(panel.values()):
            hook = getattr(obj, "on_panel_loaded", None)
            if hook is not None:
                hook(panel)

    def _add_object(self, tab: str, name: str, obj_def: dict) -> None:
        where = _where(tab, name)
        obj_def = dict(require_mapping(where, obj_def))
        if "states" in obj_def:
            require_mapping(f"{where}: 'states'", obj_def["states"])
        if "text_key" in obj_def and (
            "text" in obj_def or "default" in (obj_def.get("states") or {})
        ):
            raise ValueError(
                f"Object '{name}' in panel '{tab}' has text_key together with "
                f"text or a default state; use one"
            )
        tooltip_def = obj_def.pop("tooltip", None)
        if tooltip_def is not None:
            tooltip_def = self._check_tooltip_def(tab, name, tooltip_def)
        factory = self._factory_for(name, obj_def)
        parent_name = obj_def.pop("parent", None)
        parent_obj = self._parent_for(tab, name, parent_name)
        parent = self.window_transform if parent_obj is None else parent_obj.rect
        self._resolve_asset_keys(where, obj_def)
        self._scale_def(obj_def, window_parented=parent_obj is None)

        obj = factory(obj_def, parent)
        if parent_obj is not None and not isinstance(obj, GameObject):
            raise TypeError(
                f"{where} has a parent but its factory built a "
                f"{type(obj).__name__}, not a GameObject"
            )
        self._detach_replaced(tab, name, obj)
        if parent_obj is not None:
            obj.set_parent(parent_obj)
        self.panel_manager.add_object(tab, name, obj)
        if tooltip_def is not None:
            self._pending_tooltips.append((name, obj, tooltip_def))

    def _factory_for(self, name: str, obj_def: dict) -> ObjectFactory:
        type_name = obj_def.get("type", self._default_type)
        if type_name is None:
            raise ValueError(f"Object '{name}' has no type and no default registered")
        if type_name not in self._factories:
            raise KeyError(
                f"No factory for type '{type_name}'. Registered: {list(self._factories)}"
            )
        return self._factories[type_name]

    def _parent_for(
        self, tab: str, name: str, parent_name: str | None
    ) -> GameObject | None:
        """The GameObject named by `parent:`, or None for the window."""
        if parent_name is None:
            return None
        if tab not in self.panel_manager or parent_name not in self.panel_manager[tab]:
            raise KeyError(
                f"Object '{name}' references unknown parent '{parent_name}' in panel '{tab}'. "
                f"Parent objects must be declared before their children."
            )
        parent_obj = self.panel_manager[tab][parent_name]
        if not isinstance(parent_obj, GameObject):
            raise TypeError(
                f"{_where(tab, name)}: parent '{parent_name}' is a "
                f"{type(parent_obj).__name__}, not a GameObject"
            )
        return parent_obj

    def _detach_replaced(self, tab: str, name: str, new_obj: Any) -> None:
        """Unlinks an object that `new_obj` is about to replace under the same
        name, so it leaves its parent's children."""
        if tab not in self.panel_manager:
            return
        panel = self.panel_manager[tab]
        if name not in panel:
            return
        old = panel[name]
        if isinstance(old, GameObject) and old is not new_obj:
            old.set_parent(None)

    def _resolve_asset_keys(self, where: str, obj_def: dict) -> None:
        """Replaces the `asset` and `hover` manifest keys with image paths, in place.
        Raises ValueError for a key whose value isn't a manifest key string."""
        for key in ("asset", "hover"):
            if key in obj_def:
                value = obj_def[key]
                if not isinstance(value, str):
                    raise ValueError(
                        f"{where}: '{key}' must be an asset key string, got {value!r}"
                    )
                obj_def[key] = self.assets.image_path(value)

    def _scale_def(self, obj_def: dict, window_parented: bool) -> None:
        """Apply the global UI scale (self.scale) to one object's geometry, in place.

        size / font_size / text_size always scale by `scale`, as does `speed`
        (a px/s rate, e.g. ScrollingPanel's) so motion keeps pace with the
        scaled layout instead of crossing a smaller window faster. Positions parented
        to another object scale about that parent's origin, so child offsets grow
        with the (also-scaled) parent box. Window-parented positions with the
        default top-left anchor are remapped from the authored centre to the
        actual-window centre and their spread scaled by `scale`, so fixed chrome
        (title, counters) tracks the panel and stays on-screen even when the
        window is a different size/resolution than the layout was authored for.
        Window-parented positions with any *other* anchor (top-right,
        bottom-center, ...) are edge-relative insets, not absolute authored-
        canvas coordinates -- centre-remapping those would move them off the
        edge they're anchored to, so they're scaled directly instead, same as
        an already-parented child's offset. A window-parented object sized
        "WINDOW" (a full-screen overlay) fills the actual window, so its
        position is scaled directly too -- remapping [0, 0] about the centre
        would shift it off the top-left whenever the window's aspect ratio
        differs from the authored one. Non-numeric values ("CENTER",
        "WINDOW", ...) pass through untouched.
        """
        scale = self.scale
        authored = self.authored_size or (
            self.window_transform.width,
            self.window_transform.height,
        )
        same_canvas = (authored[0] == self.window_transform.width) and (
            authored[1] == self.window_transform.height
        )
        if scale == 1.0 and same_canvas:
            return  # desktop: authored layout, no scaling needed

        self._scale_lengths(obj_def, scale)
        self._scale_position(obj_def, scale, window_parented, authored)

    @staticmethod
    def _scale_lengths(obj_def: dict, scale: float) -> None:
        """Scales size, font_size, text_size and speed by `scale`, in place."""
        size = obj_def.get("size")
        if (
            isinstance(size, list)
            and len(size) == 2
            and all(isinstance(n, (int, float)) for n in size)
        ):
            obj_def["size"] = [round(size[0] * scale), round(size[1] * scale)]

        for key in ("font_size", "text_size"):
            v = obj_def.get(key)
            if isinstance(v, (int, float)):
                obj_def[key] = max(1, round(v * scale))

        speed = obj_def.get("speed")
        if isinstance(speed, (int, float)):
            obj_def["speed"] = speed * scale

    def _scale_position(
        self,
        obj_def: dict,
        scale: float,
        window_parented: bool,
        authored: tuple[int, int],
    ) -> None:
        """Scales (or center-remaps) `position`, in place."""
        pos = obj_def.get("position")
        if not (isinstance(pos, list) and len(pos) == 2):
            return
        fills_window = obj_def.get("size") == "WINDOW"
        if (
            window_parented
            and not fills_window
            and obj_def.get("anchor", "top-left") == "top-left"
        ):
            # Map authored-window coords → actual-window coords about center.
            actual_cx, actual_cy = (
                self.window_transform.width / 2,
                self.window_transform.height / 2,
            )
            authored_cx, authored_cy = authored[0] / 2, authored[1] / 2
            obj_def["position"] = [
                round(actual_cx + (pos[0] - authored_cx) * scale)
                if isinstance(pos[0], (int, float))
                else pos[0],
                round(actual_cy + (pos[1] - authored_cy) * scale)
                if isinstance(pos[1], (int, float))
                else pos[1],
            ]
        else:
            obj_def["position"] = [
                round(c * scale) if isinstance(c, (int, float)) else c for c in pos
            ]
