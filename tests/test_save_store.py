"""Unit tests for SaveStore: a thin JSON persistence wrapper for
saves/<name>.json (relative to cwd, auto-creating the folder), used for
both settings and game-save data.
"""

from __future__ import annotations

import json

import pytest

from pygamine.assets.save_store import SaveStore


@pytest.fixture(autouse=True)
def _isolate_cwd(tmp_path, monkeypatch):
    """save()/load() default to a cwd-relative 'saves/' folder -- isolate
    every test in its own tmp_path so nothing touches the real repo."""
    monkeypatch.chdir(tmp_path)


# ── load ─────────────────────────────────────────────────────────────


def test_load_before_any_save_returns_empty_dict():
    store = SaveStore("settings")
    assert store.load() == {}


def test_load_before_any_save_returns_the_given_default():
    store = SaveStore("settings")
    assert store.load(default={"volume": 1.0}) == {"volume": 1.0}


def test_load_round_trips_saved_data():
    store = SaveStore("settings")
    store.save({"window_mode": "windowed", "sfx_volume": 0.7})

    assert store.load() == {"window_mode": "windowed", "sfx_volume": 0.7}


def test_load_returns_default_when_the_file_is_corrupt(tmp_path):
    store = SaveStore("settings")
    store.directory.mkdir(parents=True, exist_ok=True)
    store.path.write_text("not valid json{{{", encoding="utf-8")

    assert store.load() == {}
    assert store.load(default={"a": 1}) == {"a": 1}


def test_load_returns_default_when_the_file_is_not_a_json_object(tmp_path):
    """A JSON array or scalar is valid JSON but not the dict shape callers
    expect -- must not raise or return the wrong type."""
    store = SaveStore("settings")
    store.directory.mkdir(parents=True, exist_ok=True)
    store.path.write_text("[1, 2, 3]", encoding="utf-8")

    assert store.load() == {}
    assert store.load(default={"a": 1}) == {"a": 1}


# ── save ─────────────────────────────────────────────────────────────


def test_save_creates_the_saves_folder(tmp_path):
    store = SaveStore("settings")
    store.save({"a": 1})
    assert (tmp_path / "saves").is_dir()
    assert (tmp_path / "saves" / "settings.json").exists()


def test_save_reuses_an_existing_saves_folder(tmp_path):
    (tmp_path / "saves").mkdir()
    store = SaveStore("settings")
    store.save({"a": 1})  # must not raise just because the dir already exists
    assert store.load() == {"a": 1}


def test_save_writes_human_readable_json(tmp_path):
    store = SaveStore("settings")
    store.save({"a": 1})
    raw = (tmp_path / "saves" / "settings.json").read_text(encoding="utf-8")
    assert json.loads(raw) == {"a": 1}
    assert "\n" in raw  # indent=2 -- not a single minified line


def test_save_completely_replaces_previous_content():
    store = SaveStore("settings")
    store.save({"a": 1, "b": 2})
    store.save({"c": 3})
    assert store.load() == {"c": 3}


def test_save_leaves_no_leftover_tmp_file(tmp_path):
    store = SaveStore("settings")
    store.save({"a": 1})
    assert not (tmp_path / "saves" / "settings.tmp").exists()


def test_two_stores_with_different_names_do_not_collide():
    settings = SaveStore("settings")
    save = SaveStore("save")
    settings.save({"sfx_volume": 0.5})
    save.save({"level": 3})

    assert settings.load() == {"sfx_volume": 0.5}
    assert save.load() == {"level": 3}


# ── update ───────────────────────────────────────────────────────────


def test_update_merges_into_existing_data():
    store = SaveStore("settings")
    store.save({"a": 1, "b": 2})

    result = store.update(b=20, c=3)

    assert result == {"a": 1, "b": 20, "c": 3}
    assert store.load() == {"a": 1, "b": 20, "c": 3}


def test_update_on_an_empty_store_creates_it():
    store = SaveStore("settings")
    store.update(a=1)
    assert store.load() == {"a": 1}


# ── get ──────────────────────────────────────────────────────────────


def test_get_returns_an_existing_key():
    store = SaveStore("settings")
    store.save({"sfx_volume": 0.5})
    assert store.get("sfx_volume") == 0.5


def test_get_returns_default_for_a_missing_key():
    store = SaveStore("settings")
    store.save({"a": 1})
    assert store.get("missing") is None
    assert store.get("missing", default="fallback") == "fallback"


# ── exists ───────────────────────────────────────────────────────────


def test_exists_is_false_before_any_save():
    store = SaveStore("settings")
    assert store.exists() is False


def test_exists_is_true_after_save():
    store = SaveStore("settings")
    store.save({"a": 1})
    assert store.exists() is True


# ── delete ───────────────────────────────────────────────────────────


def test_delete_removes_an_existing_store():
    store = SaveStore("save")
    store.save({"level": 3})

    store.delete()

    assert store.exists() is False
    assert store.load() == {}


def test_delete_before_any_save_is_a_no_op():
    store = SaveStore("save")
    store.delete()  # must not raise just because there's nothing to delete
    assert store.exists() is False


def test_delete_does_not_affect_a_different_store():
    settings = SaveStore("settings")
    save = SaveStore("save")
    settings.save({"a": 1})
    save.save({"b": 2})

    save.delete()

    assert settings.exists() is True
    assert settings.load() == {"a": 1}


# ── browser (emscripten) storage ─────────────────────────────────────


class _FakeLocalStorage:
    """Stands in for the browser's localStorage, which hands back None for
    a missing key just like the JS null it maps to."""

    def __init__(self) -> None:
        self.items: dict[str, str] = {}

    def getItem(self, key):  # noqa: N802
        return self.items.get(key)

    def setItem(self, key, value):  # noqa: N802
        self.items[key] = value

    def removeItem(self, key):  # noqa: N802
        self.items.pop(key, None)


@pytest.fixture
def web(monkeypatch, tmp_path) -> _FakeLocalStorage:
    fake = _FakeLocalStorage()
    monkeypatch.setattr("pygamine.assets.save_store._browser_storage", lambda: fake)
    return fake


def test_web_save_and_load_round_trip(web, tmp_path):
    store = SaveStore("save")
    store.save({"wave": 7, "name": "x"})

    assert store.load() == {"wave": 7, "name": "x"}
    assert not (tmp_path / "saves").exists()  # nothing written to disk


def test_web_data_survives_a_new_store_object(web):
    SaveStore("save").save({"wave": 7})

    assert SaveStore("save").load() == {"wave": 7}


def test_web_load_of_a_missing_key_returns_empty_or_default(web):
    store = SaveStore("save")
    assert store.load() == {}
    assert store.load(default={"a": 1}) == {"a": 1}


def test_web_load_of_corrupt_or_non_dict_data_returns_the_default(web):
    store = SaveStore("save")
    web.items[store._web_key] = "{not json"
    assert store.load(default={"a": 1}) == {"a": 1}
    web.items[store._web_key] = "[1, 2]"
    assert store.load() == {}


def test_web_exists_and_delete(web):
    store = SaveStore("save")
    assert store.exists() is False

    store.save({"a": 1})
    assert store.exists() is True

    store.delete()
    assert store.exists() is False
    assert web.items == {}
    store.delete()  # no-op when already gone


def test_web_stores_with_different_names_do_not_collide(web):
    SaveStore("save").save({"a": 1})
    SaveStore("settings").save({"b": 2})

    assert SaveStore("save").load() == {"a": 1}
    assert SaveStore("settings").load() == {"b": 2}


def test_web_update_and_get_merge_through_local_storage(web):
    store = SaveStore("settings")
    store.update(a=1)
    store.update(b=2)

    assert store.get("a") == 1
    assert store.load() == {"a": 1, "b": 2}


def test_desktop_uses_files_not_local_storage(tmp_path):
    from pygamine.assets.save_store import _browser_storage

    assert _browser_storage() is None
    store = SaveStore("save")
    store.save({"a": 1})
    assert (tmp_path / "saves" / "save.json").exists()
