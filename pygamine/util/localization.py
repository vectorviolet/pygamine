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
from string import Formatter
from typing import TYPE_CHECKING, Any, Callable
from weakref import WeakSet

import yaml

from pygamine.util.callbacks import run_callbacks

if TYPE_CHECKING:
    from pygamine.ui_widgets.text_object import TextObject

DEFAULT_LANGUAGE = "en"
META_KEY = "_meta"


def placeholder_names(text: str) -> set[str]:
    """Names of the `{placeholders}` in `text` (`{{`/`}}` escapes excluded).
    Raises ValueError for malformed braces."""
    names: set[str] = set()
    for _, field, _, _ in Formatter().parse(text):
        if field is not None:
            names.add(field.split(".")[0].split("[")[0])
    return names


def literal_text(text: str) -> str:
    """`text` without its placeholder fields; an escaped `{{` comes out as `{`."""
    return "".join(literal for literal, _, _, _ in Formatter().parse(text))


def flatten_strings(data: dict[str, Any], source: str = "<table>") -> dict[str, str]:
    """Flattens nested string tables to `{"a.b.c": "text"}`, skipping `_meta`.

    Raises ValueError for a leaf that is not a string (e.g. YAML turning a bare
    `yes` or `10` into a bool/int: quote such values) or has malformed braces.
    """
    flat: dict[str, str] = {}

    def walk(node: dict[str, Any], prefix: str) -> None:
        for name, value in node.items():
            key = f"{prefix}{name}"
            if isinstance(value, dict):
                walk(value, f"{key}.")
            elif isinstance(value, str):
                try:
                    placeholder_names(value)
                except ValueError as error:
                    raise ValueError(f"{source}: '{key}': {error}") from error
                flat[key] = value
            else:
                raise ValueError(
                    f"{source}: '{key}' must be a string, got "
                    f"{type(value).__name__} {value!r} (quote it in the YAML)"
                )

    walk({k: v for k, v in data.items() if k != META_KEY}, "")
    return flat


def _lookup(
    tables: dict[str, dict[str, str]],
    language: str,
    key: str,
    params: dict[str, Any],
) -> str:
    text = tables.get(language, {}).get(key)
    if text is None:
        text = tables.get(DEFAULT_LANGUAGE, {}).get(key)
    if text is None:
        raise KeyError(f"Missing localization key '{key}'")
    return text.format_map(params)


class Localization:
    """String tables for every language, the current language, and the live
    registry of `TextObject`s that must re-render when it changes."""

    def __init__(self) -> None:
        self._tables: dict[str, dict[str, str]] = {}
        self._names: dict[str, str] = {}
        self._language = DEFAULT_LANGUAGE
        self._callbacks: list[Callable[[str], None]] = []
        # Weak, as a safety net: panels unregister their labels explicitly.
        self._text_objects: WeakSet[TextObject] = WeakSet()

    # -- loading ----------------------------------------------------------

    def load(self, folder: str | Path) -> None:
        """Loads every `<code>.yaml` in `folder`, replacing earlier tables.

        `en.yaml` must exist (it is the fallback). The new tables are built and
        checked first (including that every key a live label uses still exists
        and renders); only then are they swapped in, live labels re-rendered
        and the language-changed callbacks fired, if the tables or the
        effective language changed. On any error nothing changes. The current
        language is kept if still available, else it falls back to English.
        """
        folder = Path(folder)
        tables: dict[str, dict[str, str]] = {}
        names: dict[str, str] = {}
        for file in sorted(folder.glob("*.yaml")):
            with open(file, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            if not isinstance(data, dict):
                raise ValueError(f"{file}: expected a mapping at the top level")
            meta = data.get(META_KEY) or {}
            if not isinstance(meta, dict):
                raise ValueError(f"{file}: '{META_KEY}' must be a mapping")
            tables[file.stem] = flatten_strings(data, str(file))
            names[file.stem] = str(meta.get("name", file.stem))
        if DEFAULT_LANGUAGE not in tables:
            raise FileNotFoundError(
                f"No {DEFAULT_LANGUAGE}.yaml (the fallback language) in {folder}"
            )
        language = self._language if self._language in tables else DEFAULT_LANGUAGE
        plan = self._plan(tables, language)
        changed = tables != self._tables or language != self._language
        self._tables, self._names, self._language = tables, names, language
        self._apply(plan)
        if changed:
            self._fire(language)

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
        """Text for `key` in the current language, else in English, run through
        `str.format_map(params)` (so `{name}` is filled and `{{` is a literal
        brace, with or without params).

        Raises KeyError if the key is in neither language, so a typo fails in
        tests instead of showing up as a blank or wrong label.
        """
        return _lookup(self._tables, self._language, key, params)

    # -- switching --------------------------------------------------------

    def set_language(self, code: str) -> None:
        """Switches language at once: re-renders every registered `TextObject`
        (all or none: nothing changes if one cannot render), then calls every
        language-changed callback with `code`. If callbacks raise, all still
        run, then the errors are re-raised together as an ExceptionGroup."""
        if code not in self._tables:
            raise KeyError(
                f"Unknown language '{code}'. Available: {list(self._tables)}"
            )
        plan = self._plan(self._tables, code)
        self._language = code
        self._apply(plan)
        self._fire(code)

    def on_language_changed(self, callback: Callable[[str], None]) -> None:
        """Registers `callback(code)`; games use it to re-set text they format
        themselves. Callbacks are held strongly: unregister them when done."""
        self._callbacks.append(callback)

    def remove_language_changed(self, callback: Callable[[str], None]) -> None:
        self._callbacks.remove(callback)

    def register(self, text_object: TextObject) -> None:
        """Tracks a `TextObject` so it re-renders on language change."""
        self._text_objects.add(text_object)

    def unregister(self, text_object: TextObject) -> None:
        """Stops tracking a `TextObject` (panels call this when they drop one)."""
        self._text_objects.discard(text_object)

    def _plan(
        self, tables: dict[str, dict[str, str]], language: str
    ) -> list[tuple[TextObject, str]]:
        """New text of every live label, computed without changing anything."""
        return [
            (obj, _lookup(tables, language, obj.text_key, obj.text_params))
            for obj in list(self._text_objects)
            if obj.text_key is not None
        ]

    @staticmethod
    def _apply(plan: list[tuple[TextObject, str]]) -> None:
        for obj, text in plan:
            obj.apply_localized_text(text)

    def _fire(self, code: str) -> None:
        run_callbacks(self._callbacks, code, label="language-changed callbacks failed")

    # -- CI checks --------------------------------------------------------

    def check_key_coverage(self) -> dict[str, dict[str, Any]]:
        """Compares every language with `en`. Returns only languages with
        differences: `{code: {"missing": [...], "extra": [...], "placeholders":
        {key: {"expected": [...], "found": [...]}}}}` (all sorted). The last one
        lists keys whose `{placeholder}` names differ from `en`. An empty dict
        means every file matches `en.yaml`."""
        reference = self._tables[DEFAULT_LANGUAGE]
        report: dict[str, dict[str, Any]] = {}
        for code, table in self._tables.items():
            if code == DEFAULT_LANGUAGE:
                continue
            missing = sorted(set(reference) - set(table))
            extra = sorted(set(table) - set(reference))
            mismatched: dict[str, dict[str, list[str]]] = {}
            for key in sorted(set(reference) & set(table)):
                expected = placeholder_names(reference[key])
                found = placeholder_names(table[key])
                if expected != found:
                    mismatched[key] = {
                        "expected": sorted(expected),
                        "found": sorted(found),
                    }
            if missing or extra or mismatched:
                report[code] = {
                    "missing": missing,
                    "extra": extra,
                    "placeholders": mismatched,
                }
        return report

    def check_glyph_coverage(
        self, font_path: str | Path | None = None, codes: list[str] | None = None
    ) -> dict[str, list[str]]:
        """Characters of each language's strings (and display name) that the
        font file cannot render: `{code: [chars]}`, only languages with gaps.

        Placeholders are ignored; escaped braces are checked. Pass the font
        file the game really uses (None = pygame's default font). Replacing a
        font is the game's job.
        """
        report: dict[str, list[str]] = {}
        for code in codes or list(self._tables):
            text = self._names[code] + "".join(
                literal_text(t) for t in self._tables[code].values()
            )
            missing = missing_glyphs(font_path, text)
            if missing:
                report[code] = missing
        return report


def missing_glyphs(font_path: str | Path | None, text: str) -> list[str]:
    """Sorted unique non-whitespace characters of `text` the font lacks.

    Uses `pygame.freetype.Font.get_metrics`, which returns None for a glyph the
    font does not contain (unlike `pygame.font.Font.metrics`, which returns the
    `.notdef` box metrics). Control and whitespace characters are skipped.
    """
    import pygame.freetype

    if not pygame.freetype.get_init():
        pygame.freetype.init()
    font = pygame.freetype.Font(None if font_path is None else str(font_path), 20)
    chars = sorted({ch for ch in text if ch.isprintable() and not ch.isspace()})
    if not chars:
        return []
    metrics = font.get_metrics("".join(chars))
    return [ch for ch, m in zip(chars, metrics, strict=True) if m is None]


# The process-wide instance games use; the names below delegate to it.
localization = Localization()
tr = localization.tr
set_language = localization.set_language
