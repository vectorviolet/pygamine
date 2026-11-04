"""Shared helper for callback lists."""

from __future__ import annotations

from typing import Any, Callable, Iterable


def run_callbacks(
    callbacks: Iterable[Callable[..., None]], *args: Any, label: str
) -> None:
    """Calls every callback with `args`, even if some raise. If any raised, the
    errors are re-raised together as an `ExceptionGroup` named `label`."""
    errors: list[Exception] = []
    for callback in list(callbacks):
        try:
            callback(*args)
        except Exception as error:
            errors.append(error)
    if errors:
        raise ExceptionGroup(label, errors)
