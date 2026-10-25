"""pygamine/licenses/ -- the license texts of what pygame-ce bundles, which
every game's build ships next to its executable. Its README's table and the
files must agree, or a build ships a text nobody listed, or lists one it
doesn't ship."""

from __future__ import annotations

import re
from pathlib import Path

import pygamine

LICENSES_DIR = Path(pygamine.__file__).parent / "licenses"


def _listed_files() -> set[str]:
    readme = (LICENSES_DIR / "README.md").read_text(encoding="utf-8")
    return set(re.findall(r"^\|[^|]+\|[^|]+\| `([^`]+)` \|", readme, re.MULTILINE))


def test_every_listed_license_text_is_there_and_not_empty():
    listed = _listed_files()
    assert listed, "the README's table lists no files"
    for name in listed:
        path = LICENSES_DIR / name
        assert path.is_file() and path.stat().st_size > 0, name


def test_every_license_text_is_listed():
    on_disk = {p.name for p in LICENSES_DIR.glob("*.txt")}
    assert on_disk == _listed_files()


def test_the_lgpl_libraries_ship_the_lgpl_text():
    for name in ("pygame-ce.txt", "libsndfile.txt", "fluidsynth.txt", "alsa-lib.txt"):
        text = (LICENSES_DIR / name).read_text(encoding="utf-8", errors="replace")
        assert "GNU LESSER GENERAL PUBLIC LICENSE" in text, name
