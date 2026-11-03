"""Structural type for anything that can resolve asset keys to paths."""

from __future__ import annotations

from typing import Protocol

from pygamine.assets.asset_path import FontPath, ImagePath, SoundPath


class AssetResolver(Protocol):
    """The slice of `AssetManager` that the panel loaders and factories use.

    Lets tests (and games) pass a small fake instead of a full `AssetManager`.
    """

    def image_path(self, key: str) -> ImagePath: ...

    def sound_path(self, key: str) -> SoundPath: ...

    def font_path(self, key: str) -> FontPath: ...
