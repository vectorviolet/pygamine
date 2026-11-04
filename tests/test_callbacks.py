"""Tests for pygamine.util.callbacks."""

from __future__ import annotations

import pytest

from pygamine.util.callbacks import run_callbacks


def test_all_run_then_group_raised() -> None:
    seen: list[str] = []

    def bad(x: int) -> None:
        seen.append("bad")
        raise RuntimeError(str(x))

    with pytest.raises(ExceptionGroup, match="boom") as info:
        run_callbacks([bad, lambda x: seen.append(f"ok{x}")], 7, label="boom")
    assert seen == ["bad", "ok7"]
    assert [str(e) for e in info.value.exceptions] == ["7"]


def test_no_errors_no_raise() -> None:
    run_callbacks([], label="x")
