"""Tests for pygamine.util.localization and its TextObject / panel hooks."""

from __future__ import annotations

import gc
import weakref

import pygame
import pytest

from pygamine.ecs.game_object_dict import GameObjectDict
from pygamine.panels.panel_loader import PanelLoader
from pygamine.panels.panel_manager import PanelManager
from pygamine.util.localization import (
    Localization,
    flatten_strings,
    literal_text,
    missing_glyphs,
    placeholder_names,
)
from pygamine.panels.panel_factory import make_text_factory
from pygamine.ui_widgets.text_object import TextObject

EN = """
_meta: {name: English}
settings:
  title: Settings
  volume: "Volume: {percent}%"
menu:
  play: Play
  only_en: English only
"""
TR = """
_meta: {name: "Türkçe"}
settings:
  title: Ayarlar
  volume: "Ses: %{percent}"
menu:
  play: Oyna
  extra: Fazla
"""


@pytest.fixture
def lang_dir(tmp_path):
    (tmp_path / "en.yaml").write_text(EN, encoding="utf-8")
    (tmp_path / "tr.yaml").write_text(TR, encoding="utf-8")
    return tmp_path


@pytest.fixture
def loc(lang_dir) -> Localization:
    loc = Localization()
    loc.load(lang_dir)
    return loc


@pytest.fixture
def font() -> pygame.font.Font:
    return pygame.font.Font(None, 20)


def test_lookup_nested_and_placeholders(loc):
    assert loc.tr("settings.title") == "Settings"
    assert loc.tr("settings.volume", percent=50) == "Volume: 50%"
    assert loc.languages() == {"en": "English", "tr": "Türkçe"}


def test_set_language_and_fallback_to_english(loc):
    loc.set_language("tr")
    assert loc.language == "tr"
    assert loc.tr("settings.title") == "Ayarlar"
    assert loc.tr("menu.only_en") == "English only"  # missing in tr


def test_missing_everywhere_raises(loc):
    with pytest.raises(KeyError, match="nope"):
        loc.tr("nope")


def test_unknown_language_raises(loc):
    with pytest.raises(KeyError):
        loc.set_language("xx")


def test_load_requires_english(tmp_path):
    (tmp_path / "tr.yaml").write_text(TR, encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        Localization().load(tmp_path)


def test_non_string_leaf_rejected(tmp_path):
    (tmp_path / "en.yaml").write_text("a: yes\n", encoding="utf-8")
    with pytest.raises(ValueError, match="quote it"):
        Localization().load(tmp_path)


def test_non_mapping_file_rejected(tmp_path):
    (tmp_path / "en.yaml").write_text("- a\n", encoding="utf-8")
    with pytest.raises(ValueError):
        Localization().load(tmp_path)


def test_reload_keeps_language_if_still_available(loc, lang_dir):
    loc.set_language("tr")
    loc.load(lang_dir)
    assert loc.language == "tr"
    (lang_dir / "tr.yaml").unlink()
    loc.load(lang_dir)
    assert loc.language == "en"


def test_table_is_a_copy(loc):
    loc.table("en")["x"] = "y"
    assert "x" not in loc.table("en")
    assert flatten_strings({"a": {"b": "c"}, "_meta": {"name": "n"}}) == {"a.b": "c"}


def test_callbacks_fire_and_can_be_removed(loc):
    seen: list[str] = []
    loc.on_language_changed(seen.append)
    loc.set_language("tr")
    loc.remove_language_changed(seen.append)
    loc.set_language("en")
    assert seen == ["tr"]


def test_text_object_text_key_live_rerender(loc, font):
    label = TextObject(
        None, (0, 0), font=font, text_key="settings.title", localization=loc
    )
    assert label.text == "Settings"
    loc.set_language("tr")
    assert label.text == "Ayarlar"
    assert label.text_key == "settings.title"
    loc.set_language("en")
    assert label.text == "Settings"


def test_text_object_set_text_replaces_key(loc, font):
    label = TextObject(
        None, (0, 0), font=font, text_key="settings.title", localization=loc
    )
    label.set_text("100%")
    loc.set_language("tr")
    assert label.text == "100%"
    assert label.text_key is None


def test_literal_text_unaffected(loc, font):
    label = TextObject(None, (0, 0), "Hi", font, localization=loc)
    loc.set_language("tr")
    assert label.text == "Hi"


def test_unknown_text_key_raises_at_construction(loc, font):
    with pytest.raises(KeyError):
        TextObject(None, (0, 0), font=font, text_key="nope", localization=loc)


def test_on_removed_unregisters_deterministically(loc, font):
    label = TextObject(None, (0, 0), font=font, text_key="menu.play", localization=loc)
    assert len(loc._text_objects) == 1
    label.on_removed()
    assert len(loc._text_objects) == 0
    loc.set_language("tr")
    assert label.text == "Play"  # no longer follows the language


def test_game_object_dict_unregisters_on_replace_and_clear(loc, font):
    objects = GameObjectDict()
    a = TextObject(None, (0, 0), font=font, text_key="menu.play", localization=loc)
    b = TextObject(None, (0, 0), font=font, text_key="menu.play", localization=loc)
    objects["x"] = a
    objects["x"] = a  # same object again: stays registered
    assert a in loc._text_objects
    objects["x"] = b
    assert a not in loc._text_objects and b in loc._text_objects
    objects.clear()
    assert len(loc._text_objects) == 0
    objects["plain"] = object()
    objects.clear()


def test_panel_manager_remove_panel_releases(loc, font):
    manager = PanelManager()
    label = TextObject(None, (0, 0), font=font, text_key="menu.play", localization=loc)
    manager.add_object("main", "play", label)
    manager.remove_panel("main")
    assert "main" not in manager
    assert len(loc._text_objects) == 0


def test_weak_safety_net(loc, font):
    label = TextObject(None, (0, 0), font=font, text_key="menu.play", localization=loc)
    ref = weakref.ref(label)
    del label
    gc.collect()
    assert ref() is None


def test_load_refreshes_live_text(loc, lang_dir, font):
    label = TextObject(None, (0, 0), font=font, text_key="menu.play", localization=loc)
    (lang_dir / "en.yaml").write_text(EN.replace("Play", "Start"), encoding="utf-8")
    loc.load(lang_dir)
    assert label.text == "Start"


def test_text_key_in_panel_factory(lang_dir, monkeypatch):
    from pygamine.util import localization as mod

    default = Localization()
    default.load(lang_dir)
    monkeypatch.setattr("pygamine.ui_widgets.text_object.default_localization", default)

    class Assets:
        def font_path(self, name):
            raise KeyError(name)

    factory = make_text_factory(Assets())  # type: ignore[arg-type]
    label = factory({"position": (0, 0), "text_key": "settings.title"}, None)
    assert label.text == "Settings"
    default.set_language("tr")
    assert label.text == "Ayarlar"
    literal = factory({"position": (0, 0), "text": "Plain"}, None)
    assert literal.text == "Plain" and literal.text_key is None
    assert mod.localization is not default


def test_key_coverage_report(loc):
    assert loc.check_key_coverage() == {
        "tr": {
            "missing": ["menu.only_en"],
            "extra": ["menu.extra"],
            "placeholders": {},
        }
    }


def test_key_coverage_clean(tmp_path):
    for code in ("en", "tr"):
        (tmp_path / f"{code}.yaml").write_text("a: x\n", encoding="utf-8")
    loc = Localization()
    loc.load(tmp_path)
    assert loc.check_key_coverage() == {}


def test_missing_glyphs():
    assert missing_glyphs(None, "ğşıİçöü abc") == []
    assert missing_glyphs(None, "a中中 b⠀") == ["⠀", "中"]
    assert missing_glyphs(None, " \n") == []


def test_glyph_coverage_report(tmp_path):
    (tmp_path / "en.yaml").write_text("a: Hello {name}\n", encoding="utf-8")
    (tmp_path / "tr.yaml").write_text(
        '_meta: {name: "Türkçe"}\na: "Merhaba 中 {x}"\nb: "{{⠀}}"\n',
        encoding="utf-8",
    )
    loc = Localization()
    loc.load(tmp_path)
    assert loc.check_glyph_coverage() == {"tr": ["⠀", "中"]}
    assert loc.check_glyph_coverage(codes=["en"]) == {}


def test_placeholder_helpers():
    assert placeholder_names("a {x} {{y}} {z.w} {q[0]:>3}") == {"x", "z", "q"}
    assert literal_text("a {x} {{y}}") == "a  {y}"
    with pytest.raises(ValueError):
        placeholder_names("{oops")


def test_malformed_braces_rejected_at_load(tmp_path):
    (tmp_path / "en.yaml").write_text('a: "{oops"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="en.yaml"):
        Localization().load(tmp_path)


def test_meta_must_be_mapping(tmp_path):
    (tmp_path / "en.yaml").write_text("_meta: English\na: x\n", encoding="utf-8")
    with pytest.raises(ValueError, match="en.yaml"):
        Localization().load(tmp_path)


def test_tr_formats_even_without_params(tmp_path):
    (tmp_path / "en.yaml").write_text('a: "100% {{done}}"\n', encoding="utf-8")
    loc = Localization()
    loc.load(tmp_path)
    assert loc.tr("a") == "100% {done}"
    assert loc.tr("a", x=1) == "100% {done}"


def test_placeholder_mismatch_reported(tmp_path):
    (tmp_path / "en.yaml").write_text('a: "{n} items"\nb: plain\n', encoding="utf-8")
    (tmp_path / "tr.yaml").write_text('a: "{count} öğe"\nb: düz\n', encoding="utf-8")
    loc = Localization()
    loc.load(tmp_path)
    assert loc.check_key_coverage() == {
        "tr": {
            "missing": [],
            "extra": [],
            "placeholders": {"a": {"expected": ["n"], "found": ["count"]}},
        }
    }


def test_text_params_persist_across_switch(loc, font):
    label = TextObject(
        None,
        (0, 0),
        font=font,
        text_key="settings.volume",
        text_params={"percent": 30},
        localization=loc,
    )
    assert label.text == "Volume: 30%"
    loc.set_language("tr")
    assert label.text == "Ses: %30"
    label.set_params(percent=80)
    assert label.text == "Ses: %80"
    loc.set_language("en")
    assert label.text == "Volume: 80%"
    assert label.text_params == {"percent": 80}


def test_set_text_with_explicit_default_state_drops_key(loc, font):
    label = TextObject(
        None, (0, 0), font=font, text_key="settings.title", localization=loc
    )
    label.set_text("X", state="default")
    assert label.text_key is None
    loc.set_language("tr")
    assert label.text == "X"


def test_text_key_with_text_or_default_state_rejected(loc, font):
    with pytest.raises(ValueError):
        TextObject(None, (0, 0), "x", font, text_key="menu.play", localization=loc)
    with pytest.raises(ValueError):
        TextObject(
            None,
            (0, 0),
            font=font,
            states={"default": "x"},
            text_key="menu.play",
            localization=loc,
        )


def test_panel_loader_rejects_text_key_with_text():
    loader = PanelLoader(PanelManager(), None, None)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="'title' in panel 'main'"):
        loader._add_object("main", "title", {"text_key": "a", "text": "b"})
    with pytest.raises(ValueError, match="'title'"):
        loader._add_object(
            "main", "title", {"text_key": "a", "states": {"default": "b"}}
        )


def test_set_language_is_atomic_for_labels(tmp_path, font):
    (tmp_path / "en.yaml").write_text('a: "{n}"\nb: B\n', encoding="utf-8")
    (tmp_path / "tr.yaml").write_text('a: "{m}"\nb: Bt\n', encoding="utf-8")
    loc = Localization()
    loc.load(tmp_path)
    good = TextObject(None, (0, 0), font=font, text_key="b", localization=loc)
    bad = TextObject(
        None, (0, 0), font=font, text_key="a", text_params={"n": 1}, localization=loc
    )
    with pytest.raises(KeyError):  # tr's "{m}" has no value
        loc.set_language("tr")
    assert loc.language == "en"
    assert good.text == "B" and bad.text == "1"


def test_all_callbacks_run_then_errors_group(loc):
    seen: list[str] = []

    def boom(code):
        raise RuntimeError("boom")

    loc.on_language_changed(boom)
    loc.on_language_changed(seen.append)
    with pytest.raises(ExceptionGroup) as info:
        loc.set_language("tr")
    assert seen == ["tr"] and loc.language == "tr"
    assert isinstance(info.value.exceptions[0], RuntimeError)


def test_load_is_atomic_and_fires_callbacks(loc, lang_dir, font):
    label = TextObject(None, (0, 0), font=font, text_key="menu.play", localization=loc)
    seen: list[str] = []
    loc.on_language_changed(seen.append)

    loc.load(lang_dir)  # nothing changed: no callback
    assert seen == []

    (lang_dir / "en.yaml").write_text("other: x\n", encoding="utf-8")
    with pytest.raises(KeyError):  # live label's key is gone
        loc.load(lang_dir)
    assert label.text == "Play" and loc.tr("menu.play") == "Play" and seen == []

    (lang_dir / "en.yaml").write_text(EN.replace("Play", "Start"), encoding="utf-8")
    loc.load(lang_dir)
    assert label.text == "Start" and seen == ["en"]


def test_load_falls_back_to_english_and_notifies(loc, lang_dir, font):
    loc.set_language("tr")
    label = TextObject(None, (0, 0), font=font, text_key="menu.play", localization=loc)
    seen: list[str] = []
    loc.on_language_changed(seen.append)
    (lang_dir / "tr.yaml").unlink()
    loc.load(lang_dir)
    assert loc.language == "en" and label.text == "Play" and seen == ["en"]
