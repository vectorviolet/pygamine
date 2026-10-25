"""pygamine/__init__.py's lazy public-API surface.

Every name it advertises must actually resolve, but resolving a *lightweight*
name (no optional-dependency modules like asset_manager/tilemap involved)
must not eagerly import the *heavy* ones -- some consumers of this package
deliberately don't install pyyaml/pytmx because they don't use
AssetManager/PanelManager/TiledMap at all (see artifical-chaos's CLAUDE.md).
An eager `import pygamine` that pulls in every submodule unconditionally
would force those consumers to install dependencies they never touch.
Exercised via a subprocess so sys.modules starts genuinely empty -- the rest
of this test session already imports plenty of pygamine submodules
directly, which would make an in-process check meaningless.
"""

from __future__ import annotations
import os
import subprocess
import sys

import pygamine


def test_every_advertised_name_actually_resolves():
    missing = [name for name in pygamine.__all__ if not hasattr(pygamine, name)]
    assert missing == []


def test_dir_includes_the_full_public_api():
    assert set(pygamine.__all__) <= set(dir(pygamine))


def _run(code: str) -> str:
    # PYGAME_HIDE_SUPPORT_PROMPT: pygame prints its own "pygame-ce x.y.z
    # (SDL ..., Python ...)" banner to stdout on first import, which would
    # otherwise land ahead of whatever this test actually prints.
    env = {**os.environ, "PYGAME_HIDE_SUPPORT_PROMPT": "1"}
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=__file__.rsplit("tests", 1)[0],
        env=env,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_importing_the_package_does_not_eagerly_load_optional_dependency_modules():
    out = _run(
        "import pygamine\n"
        "import sys\n"
        "print('asset_manager' in sys.modules, 'tilemap' in sys.modules)\n"
    )
    assert out == "False False"


def test_accessing_a_lightweight_name_does_not_pull_in_asset_manager_or_tilemap():
    out = _run(
        "import pygamine\n"
        "pygamine.Application\n"
        "pygamine.GameObject\n"
        "import sys\n"
        "print('pygamine.assets.asset_manager' in sys.modules, 'pygamine.assets.tilemap' in sys.modules)\n"
    )
    assert out == "False False"


def test_accessing_asset_manager_does_import_it_and_caches_the_result():
    out = _run(
        "import pygamine\n"
        "pygamine.AssetManager\n"
        "import sys\n"
        "print('pygamine.assets.asset_manager' in sys.modules)\n"
        "print(pygamine.__dict__['AssetManager'] is pygamine.AssetManager)\n"
    )
    assert out == "True\nTrue"


def test_unknown_attribute_raises_attribute_error():
    import pytest

    with pytest.raises(AttributeError):
        pygamine.ThisNameDoesNotExist
