"""Unit tests for pygamine.devtools.coverage_badge: turns coverage.json
into a shields.io endpoint badge JSON, written relative to cwd -- the
`pygamine-coverage-badge` console script every host project's CI runs.
"""

from __future__ import annotations

import json

import pytest

from pygamine.devtools.coverage_badge import badge_color, main


@pytest.mark.parametrize(
    ("percent", "color"),
    [
        (0, "red"),
        (49.9, "red"),
        (50, "yellow"),
        (79.9, "yellow"),
        (80, "brightgreen"),
        (100, "brightgreen"),
    ],
)
def test_badge_color_thresholds(percent, color):
    assert badge_color(percent) == color


def test_main_reads_coverage_json_and_writes_badge(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "coverage.json").write_text(
        json.dumps({"totals": {"percent_covered": 87.4}}), encoding="utf-8"
    )

    main()

    out = tmp_path / ".github" / "badges" / "coverage.json"
    badge = json.loads(out.read_text(encoding="utf-8"))
    assert badge == {
        "schemaVersion": 1,
        "label": "coverage",
        "message": "87%",
        "color": "brightgreen",
    }


def test_main_creates_the_badges_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "coverage.json").write_text(
        json.dumps({"totals": {"percent_covered": 10}}), encoding="utf-8"
    )

    main()

    assert (tmp_path / ".github" / "badges" / "coverage.json").exists()
