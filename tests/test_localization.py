"""Tests for pygamine.util.localization and its TextObject / panel hooks."""

from __future__ import annotations

import gc

import pygame
import pytest

from pygamine.util.localization import Localization, flatten_strings, missing_glyphs
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


def test_registry_does_not_keep_text_objects_alive(loc, font):
    label = TextObject(None, (0, 0), font=font, text_key="menu.play", localization=loc)
    assert len(loc._text_objects) == 1
    del label
    gc.collect()
    assert len(loc._text_objects) == 0
    loc.set_language("tr")  # nothing to refresh, no error


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
        "tr": {"missing": ["menu.only_en"], "extra": ["menu.extra"]}
    }


def test_key_coverage_clean(tmp_path):
    for code in ("en", "tr"):
        (tmp_path / f"{code}.yaml").write_text("a: x\n", encoding="utf-8")
    loc = Localization()
    loc.load(tmp_path)
    assert loc.check_key_coverage() == {}


def test_missing_glyphs(font):
    assert missing_glyphs(font, "ğşıİçöü abc") == []
    assert missing_glyphs(font, "a\u4e2d\u4e2d b") == ["\u4e2d"]


def test_glyph_coverage_report(tmp_path, font):
    (tmp_path / "en.yaml").write_text("a: Hello {name}\n", encoding="utf-8")
    (tmp_path / "tr.yaml").write_text(
        '_meta: {name: "Türkçe"}\na: "Merhaba \u4e2d {x}"\n', encoding="utf-8"
    )
    loc = Localization()
    loc.load(tmp_path)
    assert loc.check_glyph_coverage(font) == {"tr": ["\u4e2d"]}
    assert loc.check_glyph_coverage(font, codes=["en"]) == {}
