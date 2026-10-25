"""Thin sqlite3 wrapper that stores `<name>.db` under a `databases/`
folder (cwd-relative, auto-creating), mirroring `save_store.py`'s
`SaveStore` convention but for relational data instead of JSON blobs.

Failures raise `DatabaseError` rather than printing and killing the
process -- a shared library has no business deciding a game process
should exit; that choice belongs to the caller.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


class DatabaseError(Exception):
    """Raised when connecting to or querying the database fails."""


class Database:
    def __init__(self, name: str, directory: str = "databases") -> None:
        self.name = name
        self.directory = Path(directory)
        self.path = self.directory / f"{name}.db"
        self.connection: sqlite3.Connection | None = None

    def connect(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        try:
            self.connection = sqlite3.connect(self.path)
        except sqlite3.Error as error:
            raise DatabaseError(
                f"Failed to connect to database {self.path}: {error}"
            ) from error

    def get_cursor(self) -> sqlite3.Cursor:
        assert self.connection is not None, "Database not connected"
        return self.connection.cursor()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        try:
            return self.get_cursor().execute(sql, params)
        except sqlite3.Error as error:
            raise DatabaseError(f"Failed to execute {sql!r}: {error}") from error

    def commit(self) -> None:
        assert self.connection is not None, "Database not connected"
        self.connection.commit()

    def disconnect(self) -> None:
        assert self.connection is not None, "Database not connected"
        self.connection.close()

    def execute_safely(
        self, query: str, fetch: bool = False, *, params: tuple = ()
    ) -> list[tuple] | None:
        """Connect, run `query`, commit, and disconnect in one call --
        always disconnects (even if the query raises), unlike the
        connect/execute/commit/disconnect building blocks used directly
        for batching multiple statements over one connection."""
        self.connect()
        try:
            cursor = self.execute(query, params)
            result = cursor.fetchall() if fetch else None
            self.commit()
        finally:
            self.disconnect()
        return result
