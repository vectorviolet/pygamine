"""Localization: YAML string tables, a live language switch, English fallback.

A game points `localization.load(folder)` at a folder of `<code>.yaml` files
(e.g. `config/lang/en.yaml`, `tr.yaml`). Each file holds a display name under
`_meta.name` and nested string keys addressed with dots (`settings.title`).
`tr("settings.title")` looks a key up in the current language, falling back to
English; `set_language("tr")` switches instantly, re-renders every live
`TextObject` built from a `text_key` and fires the registered callbacks.

See docs/decisions/0001-localization.md for the reasoning behind the design.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable
from weakref import WeakSet

import yaml

if TYPE_CHECKING:
    import pygame

    from pygamine.ui_widgets.text_object import TextObject

DEFAULT_LANGUAGE = "en"
META_KEY = "_meta"


def flatten_strings(data: dict[str, Any], source: str = "<table>") -> dict[str, str]:
    """Flattens nested string tables to `{"a.b.c": "text"}`, skipping `_meta`.

    Raises ValueError for a leaf that is not a string (e.g. YAML turning a bare
    `yes` or `10` into a bool/int): quote such values in the YAML file.
    """
    flat: dict[str, str] = {}

    def walk(node: dict[str, Any], prefix: str) -> None:
        for name, value in node.items():
            key = f"{prefix}{name}"
            if isinstance(value, dict):
                walk(value, f"{key}.")
            elif isinstance(value, str):
                flat[key] = value
            else:
                raise ValueError(
                    f"{source}: '{key}' must be a string, got "
                    f"{type(value).__name__} {value!r} (quote it in the YAML)"
                )

    walk({k: v for k, v in data.items() if k != META_KEY}, "")
    return flat


class Localization:
    """String tables for every language, the current language, and the live
    registry of `TextObject`s that must re-render when it changes."""

    def __init__(self) -> None:
        self._tables: dict[str, dict[str, str]] = {}
        self._names: dict[str, str] = {}
        self._language = DEFAULT_LANGUAGE
        self._callbacks: list[Callable[[str], None]] = []
        # Weak, so a panel that is reloaded or dropped leaks nothing.
        self._text_objects: WeakSet[TextObject] = WeakSet()

    # -- loading ----------------------------------------------------------

    def load(self, folder: str | Path) -> None:
        """Loads every `<code>.yaml` in `folder`, replacing earlier tables.
        `en.yaml` must exist (it is the fallback). The current language is kept
        if it is still available, else reset to English."""
        folder = Path(folder)
        tables: dict[str, dict[str, str]] = {}
        names: dict[str, str] = {}
        for file in sorted(folder.glob("*.yaml")):
            with open(file, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            if not isinstance(data, dict):
                raise ValueError(f"{file}: expected a mapping at the top level")
            meta = data.get(META_KEY) or {}
            tables[file.stem] = flatten_strings(data, str(file))
            names[file.stem] = str(meta.get("name", file.stem))
        if DEFAULT_LANGUAGE not in tables:
            raise FileNotFoundError(
                f"No {DEFAULT_LANGUAGE}.yaml (the fallback language) in {folder}"
            )
        self._tables = tables
        self._names = names
        if self._language not in tables:
            self._language = DEFAULT_LANGUAGE
        self._refresh()

    @property
    def language(self) -> str:
        return self._language

    def languages(self) -> dict[str, str]:
        """Available language codes mapped to their display names."""
        return dict(self._names)

    def table(self, code: str) -> dict[str, str]:
        """The flattened `{key: text}` table of one language (a copy)."""
        return dict(self._tables[code])

    # -- lookup -----------------------------------------------------------

    def tr(self, key: str, **params: Any) -> str:
        """Text for `key` in the current language, else in English, with
        `{name}` placeholders filled from `params` (str.format).

        Raises KeyError if the key is in neither language, so a typo fails in
        tests instead of showing up as a blank or wrong label.
        """
        text = self._tables.get(self._language, {}).get(key)
        if text is None:
            text = self._tables.get(DEFAULT_LANGUAGE, {}).get(key)
        if text is None:
            raise KeyError(f"Missing localization key '{key}'")
        return text.format(**params) if params else text

    # -- switching --------------------------------------------------------

    def set_language(self, code: str) -> None:
        """Switches language at once: re-renders every registered
        `TextObject`, then calls the language-changed callbacks with `code`."""
        if code not in self._tables:
            raise KeyError(
                f"Unknown language '{code}'. Available: {list(self._tables)}"
            )
        self._language = code
        self._refresh()
        for callback in list(self._callbacks):
            callback(code)

    def on_language_changed(self, callback: Callable[[str], None]) -> None:
        """Registers `callback(code)`; games use it to re-set text they format
        themselves. Callbacks are held strongly: unregister them when done."""
        self._callbacks.append(callback)

    def remove_language_changed(self, callback: Callable[[str], None]) -> None:
        self._callbacks.remove(callback)

    def register(self, text_object: TextObject) -> None:
        """Tracks a `TextObject` (weakly) so it re-renders on language change."""
        self._text_objects.add(text_object)

    def unregister(self, text_object: TextObject) -> None:
        self._text_objects.discard(text_object)

    def _refresh(self) -> None:
        for text_object in list(self._text_objects):
            text_object.relocalize()

    # -- CI checks --------------------------------------------------------

    def check_key_coverage(self) -> dict[str, dict[str, list[str]]]:
        """Compares every language with `en`. Returns only languages with
        differences: `{code: {"missing": [...], "extra": [...]}}` (sorted).
        An empty dict means every file has exactly the keys of `en.yaml`."""
        reference = set(self._tables[DEFAULT_LANGUAGE])
        report: dict[str, dict[str, list[str]]] = {}
        for code, table in self._tables.items():
            if code == DEFAULT_LANGUAGE:
                continue
            keys = set(table)
            missing, extra = sorted(reference - keys), sorted(keys - reference)
            if missing or extra:
                report[code] = {"missing": missing, "extra": extra}
        return report

    def check_glyph_coverage(
        self, font: pygame.font.Font, codes: list[str] | None = None
    ) -> dict[str, list[str]]:
        """Characters of each language's strings (and display name) that `font`
        cannot render: `{code: [chars]}`, only languages with gaps.

        Placeholder names inside `{}` are ignored. Pass the font the game
        really uses for that text (replacing a font is the game's job).
        """
        report: dict[str, list[str]] = {}
        for code in codes or list(self._tables):
            chars: set[str] = set(self._names[code])
            for text in self._tables[code].values():
                chars.update(_without_placeholders(text))
            missing = missing_glyphs(font, "".join(chars))
            if missing:
                report[code] = missing
        return report


def _without_placeholders(text: str) -> str:
    out: list[str] = []
    depth = 0
    for ch in text:
        if ch == "{":
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
        elif not depth:
            out.append(ch)
    return "".join(out)


def missing_glyphs(font: pygame.font.Font, text: str) -> list[str]:
    """Sorted unique non-whitespace characters of `text` that `font` lacks.

    `Font.metrics` does not return None for a missing glyph in pygame-ce 2.5
    (SDL_ttf hands back the font's ".notdef" box), so a character counts as
    missing when it renders pixel-identical to a codepoint no font defines.
    """
    import pygame

    def shape(ch: str) -> tuple[Any, ...]:
        surf = font.render(ch, False, (255, 255, 255))
        return (surf.get_size(), pygame.image.tobytes(surf, "RGBA"))

    notdef = shape("￿")
    chars = {ch for ch in text if ch.isprintable() and not ch.isspace()}
    return sorted(ch for ch in chars if shape(ch) == notdef)


# The process-wide instance games use; the names below delegate to it.
localization = Localization()
tr = localization.tr
set_language = localization.set_language
