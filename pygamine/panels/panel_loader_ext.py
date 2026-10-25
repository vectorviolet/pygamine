from __future__ import annotations

import yaml
from pathlib import Path
from pygamine.panels.panel_loader import PanelLoader


class PanelLoaderExt(PanelLoader):
    """PanelLoader extended with object-level template inheritance.

    Adds an ``object_templates`` top-level section to the YAML.  Any object
    (in groups or panels) can write ``extends: <template_name>`` and its
    properties will be merged on top of the template — object keys always win.

    Example YAML
    ------------
    object_templates:
      menu_btn:
        size: [960, 96]
        nine_slice: 8

    panels:
      main_menu:
        objects:
          play:
            extends: menu_btn        # inherits size + nine_slice
            position: [CENTER, 300]  # own keys override / extend the template
            asset: btn_play
            hover: btn_play_hover
    """

    def load(self, path: str | Path) -> None:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Panel definition not found: {path}")
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        templates = data.pop("object_templates", {}) or {}
        self._expand_layouts(data)
        if templates:
            self._resolve_extends(data, templates)

        groups = data.get("groups", {}) or {}
        for tab, panel_def in (data.get("panels", {}) or {}).items():
            self._load_panel(tab, panel_def, groups)

    # ── private ───────────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_extends(data: dict, templates: dict) -> None:
        for group_def in (data.get("groups", {}) or {}).values():
            PanelLoaderExt._apply_templates(group_def, templates)

        for panel_def in (data.get("panels", {}) or {}).values():
            PanelLoaderExt._apply_templates((panel_def.get("objects") or {}), templates)

    @staticmethod
    def _expand_layouts(data: dict) -> None:
        for group_def in (data.get("groups", {}) or {}).values():
            PanelLoaderExt._expand_in(group_def)

        for panel_def in (data.get("panels", {}) or {}).values():
            objects = panel_def.get("objects")
            if objects:
                PanelLoaderExt._expand_in(objects)

    @staticmethod
    def _expand_in(objects: dict) -> None:
        new_entries: dict = {}
        for name, obj_def in objects.items():
            if not isinstance(obj_def, dict) or "layout" not in obj_def:
                new_entries[name] = obj_def
                continue

            layout = obj_def["layout"] or {}
            direction = layout.get("direction", "vertical")
            if direction not in ("vertical", "horizontal"):
                raise ValueError(
                    f"layout group '{name}': direction must be 'vertical' or "
                    f"'horizontal', got {direction!r}"
                )
            start = layout.get("start")
            if not isinstance(start, list) or len(start) != 2:
                raise ValueError(f"layout group '{name}': layout.start must be [x, y]")
            spacing = layout.get("spacing", 0)

            sx, sy = start
            main_axis_is_y = direction == "vertical"
            main_val = sy if main_axis_is_y else sx
            cross_val = sx if main_axis_is_y else sy
            if not isinstance(main_val, (int, float)):
                raise ValueError(
                    f"layout group '{name}': main-axis start "
                    f"({'y' if main_axis_is_y else 'x'}) must be numeric for "
                    f"{direction} layout, got {main_val!r}"
                )

            children = obj_def.get("objects") or {}
            group_parent = obj_def.get("parent")
            for i, (child_name, child_def) in enumerate(children.items()):
                if not isinstance(child_def, dict):
                    raise ValueError(
                        f"layout group '{name}' child '{child_name}' must be a mapping"
                    )
                if "layout" in child_def:
                    raise ValueError(
                        f"layout group '{name}' child '{child_name}' may not "
                        f"itself be a layout group (nesting not supported)"
                    )
                child = dict(child_def)
                offset = i * spacing
                if main_axis_is_y:
                    child["position"] = [cross_val, main_val + offset]
                else:
                    child["position"] = [main_val + offset, cross_val]
                if group_parent is not None:
                    child["parent"] = group_parent
                if child_name in new_entries:
                    raise KeyError(
                        f"duplicate object name '{child_name}' produced by "
                        f"layout group '{name}'"
                    )
                new_entries[child_name] = child

        objects.clear()
        objects.update(new_entries)

    @staticmethod
    def _apply_templates(objects: dict, templates: dict) -> None:
        for name, obj_def in objects.items():
            base_name = obj_def.get("extends")
            if base_name is None:
                continue
            if base_name not in templates:
                raise KeyError(
                    f"Object '{name}' extends unknown template '{base_name}'. "
                    f"Available: {list(templates)}"
                )
            merged = {**templates[base_name], **obj_def}
            del merged["extends"]
            objects[name] = merged
