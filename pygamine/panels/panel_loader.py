from __future__ import annotations

from pygamine.assets.asset_manager import AssetManager
from pathlib import Path
from typing import Any, Callable
import yaml

from pygamine.ecs.components.transform import Transform

# Factory signature: config dict + window_size → object
ObjectFactory = Callable[[dict, tuple[int, int]], Any]

class PanelLoader:
    """Reads panel definitions from a YAML file and loads them into PanelManager."""

    def __init__(self, panel_manager, window_transform: Transform, asset_manager: AssetManager):
        self.pm = panel_manager
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

    def register(self, type_name: str, factory: ObjectFactory, *, default: bool = False) -> None:
        self._factories[type_name] = factory
        if default:
            self._default_type = type_name

    def load(self, path: str | Path) -> None:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Panel definition not found: {path}")
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        groups = data.get("groups", {}) or {}
        for tab, panel_def in (data.get("panels", {}) or {}).items():
            self._load_panel(tab, panel_def, groups)

    def _load_panel(self, tab: str, panel_def: dict, groups: dict) -> None:
        for group_name in panel_def.get("extends", []) or []:
            for obj_name, obj_def in groups[group_name].items():
                self._add_object(tab, obj_name, obj_def)
        for obj_name, obj_def in (panel_def.get("objects", {}) or {}).items():
            self._add_object(tab, obj_name, obj_def)
        self._notify_panel_loaded(tab)

    def _notify_panel_loaded(self, tab: str) -> None:
        """Calls `on_panel_loaded(panel)` on every object of the just-loaded
        panel that defines it -- for objects that need their siblings, which
        may be declared after them (e.g. ScrollingPanel adopting its targets).
        Iterates a snapshot, since a hook may remove objects from the panel."""
        if tab not in self.pm:
            return
        panel = self.pm[tab]
        for obj in list(panel.values()):
            hook = getattr(obj, "on_panel_loaded", None)
            if hook is not None:
                hook(panel)

    def _add_object(self, tab: str, name: str, obj_def: dict) -> None:
        obj_def = dict(obj_def)
        type_name = obj_def.get("type", self._default_type)
        if type_name is None:
            raise ValueError(f"Object '{name}' has no type and no default registered")
        if type_name not in self._factories:
            raise KeyError(f"No factory for type '{type_name}'. Registered: {list(self._factories)}")

        parent_name = obj_def.pop("parent", None)
        if parent_name is not None:
            if tab not in self.pm or parent_name not in self.pm[tab]:
                raise KeyError(
                    f"Object '{name}' references unknown parent '{parent_name}' in panel '{tab}'. "
                    f"Parent objects must be declared before their children."
                )
            parent = self.pm[tab][parent_name].rect
        else:
            parent = self.window_transform

        if "asset" in obj_def:
            obj_def["asset"] = self.assets.image_path(obj_def["asset"])
        if "hover" in obj_def:
            obj_def["hover"] = self.assets.image_path(obj_def["hover"])

        self._scale_def(obj_def, window_parented=parent_name is None)

        factory = self._factories[type_name]
        obj = factory(obj_def, parent)
        self.pm.add_object(tab, name, obj)

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
        k = self.scale
        authored = self.authored_size or (
            self.window_transform.width,
            self.window_transform.height,
        )
        same_canvas = (authored[0] == self.window_transform.width) and (
            authored[1] == self.window_transform.height
        )
        if k == 1.0 and same_canvas:
            return  # desktop: authored layout, no scaling needed

        size = obj_def.get("size")
        if isinstance(size, list) and len(size) == 2 and all(
            isinstance(n, (int, float)) for n in size
        ):
            obj_def["size"] = [round(size[0] * k), round(size[1] * k)]

        for key in ("font_size", "text_size"):
            v = obj_def.get(key)
            if isinstance(v, (int, float)):
                obj_def[key] = max(1, round(v * k))

        speed = obj_def.get("speed")
        if isinstance(speed, (int, float)):
            obj_def["speed"] = speed * k

        pos = obj_def.get("position")
        if isinstance(pos, list) and len(pos) == 2:
            fills_window = obj_def.get("size") == "WINDOW"
            if window_parented and not fills_window and obj_def.get("anchor", "top-left") == "top-left":
                # Map authored-window coords → actual-window coords about centre.
                acx, acy = self.window_transform.width / 2, self.window_transform.height / 2
                ocx, ocy = authored[0] / 2, authored[1] / 2
                obj_def["position"] = [
                    round(acx + (pos[0] - ocx) * k) if isinstance(pos[0], (int, float)) else pos[0],
                    round(acy + (pos[1] - ocy) * k) if isinstance(pos[1], (int, float)) else pos[1],
                ]
            else:
                obj_def["position"] = [
                    round(c * k) if isinstance(c, (int, float)) else c for c in pos
                ]