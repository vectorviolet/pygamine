from __future__ import annotations

from pathlib import Path
from typing import Callable, TypeVar
import pygame
import yaml

from pygamine.assets.asset_path import AssetPath, ImagePath, FontPath, SoundPath

T = TypeVar('T')


class AssetManager:
    """Manifest-driven asset registry. Single source of truth for asset paths."""

    def __init__(self):
        self._images: dict[str, ImagePath] = {}
        self._fonts: dict[str, FontPath] = {}
        self._sounds: dict[str, SoundPath] = {}
        self._image_cache: dict[str, pygame.Surface] = {}

    def load_manifest(self, path: str | Path) -> None:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Asset manifest not found: {path}")

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        self._load_category(data.get("images"), self._images, ImagePath, "png")
        self._load_category(data.get("fonts"), self._fonts, FontPath, "ttf")
        self._load_category(data.get("sounds"), self._sounds, SoundPath, "ogg")

    @staticmethod
    def _load_category(config: dict | None, target_dict: dict, path_class: Callable[..., AssetPath], default_ext: str) -> None:
        for key, cfg in (config or {}).items():
            target_dict[key] = path_class(
                name=cfg["name"],
                folder=cfg.get("folder", ""),
                extension=cfg.get("extension", default_ext),
            )

    def validate(self) -> list[str]:
        """Validate that every registered path exists on disk. Returns the missing ones."""
        missing = []
        all_paths = {**self._images, **self._fonts, **self._sounds}
        for key, path in all_paths.items():
            if not Path(str(path)).exists():
                missing.append(f"{key} → {path}")
        return missing

    @staticmethod
    def _get_path(collection: dict[str, T], key: str, asset_name: str) -> T:
        if key not in collection:
            raise KeyError(f"Unknown {asset_name} asset: '{key}'. Known: {list(collection.keys())[:5]}...")
        return collection[key]

    def image_path(self, key: str) -> ImagePath:
        return self._get_path(self._images, key, "image")

    def get_image(self, key: str) -> pygame.Surface:
        """Cached surface — one instance per key."""
        if key not in self._image_cache:
            self._image_cache[key] = pygame.image.load(self.image_path(key)).convert_alpha()
        return self._image_cache[key]

    def font_path(self, key: str) -> FontPath:
        return self._get_path(self._fonts, key, "font")

    def sound_path(self, key: str) -> SoundPath:
        return self._get_path(self._sounds, key, "sound")
