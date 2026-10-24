from __future__ import annotations

import os
from pathlib import Path
from typing import Union


class AssetPath(os.PathLike):
    """Game asset path — string-compatible but type-safe."""

    def __init__(self, name: str, folder: str = "", extension: str = "png",
                 base: str = "assets"):
        self.name = name
        self.folder = folder
        self.extension = extension.lstrip(".")
        self.base = base

    @property
    def full_path(self) -> str:
        parts = [self.base]
        if self.folder:
            parts.append(self.folder)
        rel = f"{'/'.join(parts)}/{self.name}.{self.extension}"
        # Absolute, not relative. On Android, SDL2's SDL_RWFromFile (used under
        # the hood by pygame.image.load / mixer.Sound / font.Font) treats a
        # *relative* path as an APK-asset lookup via AAssetManager — but p4a
        # unpacks our assets into the private files dir, not the APK asset
        # namespace, so a relative string fails ("No file ... found in working
        # directory"). An absolute path (leading '/') makes SDL fall back to
        # fopen and read the real file. Anchored to the CWD, which is the app
        # root on both desktop (run from the project root) and Android (p4a
        # chdir's to files/app) — the same assumption load_manifest("config/…")
        # already relies on. On desktop this is just a harmless absolute path.
        return os.path.abspath(rel)

    def __str__(self) -> str:
        return self.full_path

    def __fspath__(self) -> str:
        # os.PathLike protocol — pygame.image.load(path) accepts this
        return self.full_path

    def __repr__(self) -> str:
        return f"AssetPath({self.full_path!r})"


class ImagePath(AssetPath):
    def __init__(self, name: str, folder: str = "", extension: str = "png"):
        super().__init__(name, folder, extension, base="assets/images")


class FontPath(AssetPath):
    def __init__(self, name: str, folder: str = "", extension: str = "ttf"):
        super().__init__(name, folder, extension, base="assets/fonts")


class SoundPath(AssetPath):
    def __init__(self, name: str, folder: str = "", extension: str = "ogg"):
        super().__init__(name, folder, extension, base="assets/sounds")


class SequencePath(AssetPath):
    """A folder of numbered frames played as a video (an image sequence),
    e.g. assets/images/branding/publisher_splash/0001.jpg, 0002.jpg, ...

    Points at the folder itself; `extension` is the frames' file type.
    The folder may also hold a `meta.yaml` (see ImageSequenceMedia).
    """

    def __init__(self, name: str, folder: str = "", extension: str = "jpg"):
        super().__init__(name, folder, extension, base="assets/images")

    @property
    def full_path(self) -> str:
        parts = [self.base]
        if self.folder:
            parts.append(self.folder)
        parts.append(self.name)
        return os.path.abspath("/".join(parts))  # absolute: see AssetPath.full_path

    def frame_paths(self) -> list[Path]:
        """The frame files, in playback (file name) order."""
        return sorted(Path(self.full_path).glob(f"*.{self.extension}"))

    def __repr__(self) -> str:
        return f"SequencePath({self.full_path!r})"


PathLike = Union[str, "os.PathLike[str]"]
