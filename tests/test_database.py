"""Unit tests for Database: a thin sqlite3 wrapper that connects to
databases/<name>.db (relative to cwd, auto-creating the folder).
"""

from __future__ import annotations

import sqlite3

import pytest

from pygamine.assets.database import Database, DatabaseError


@pytest.fixture(autouse=True)
def _isolate_cwd(tmp_path, monkeypatch):
    """connect() hardcodes a cwd-relative 'databases/' folder -- isolate
    every test in its own tmp_path so nothing touches the real repo."""
    monkeypatch.chdir(tmp_path)


# ── connect ──────────────────────────────────────────────────────────


def test_connect_creates_the_databases_folder(tmp_path):
    db = Database("test")
    db.connect()  # must not raise
    assert (tmp_path / "databases").is_dir()
    assert (tmp_path / "databases" / "test.db").exists()


def test_connect_reuses_an_existing_databases_folder(tmp_path):
    (tmp_path / "databases").mkdir()
    db = Database("test")
    db.connect()  # must not raise just because the dir already exists


def test_connect_sets_a_real_sqlite_connection():
    db = Database("test")
    db.connect()
    assert isinstance(db.connection, sqlite3.Connection)


def test_connect_raises_databaseerror_on_failure(monkeypatch):
    def _raise(*args, **kwargs):
        raise sqlite3.OperationalError("simulated failure")

    monkeypatch.setattr(sqlite3, "connect", _raise)
    db = Database("test")
    with pytest.raises(DatabaseError):
        db.connect()


# ── get_cursor ──────────────────────────────────────────────────────────


def test_get_cursor_before_connect_raises_assertion_error():
    db = Database("test")
    with pytest.raises(AssertionError):
        db.get_cursor()


def test_get_cursor_after_connect_returns_a_real_cursor():
    db = Database("test")
    db.connect()
    assert isinstance(db.get_cursor(), sqlite3.Cursor)


# ── execute ──────────────────────────────────────────────────────────


def test_execute_runs_real_sql():
    db = Database("test")
    db.connect()
    db.execute("CREATE TABLE t (id INTEGER)")
    db.execute("INSERT INTO t VALUES (?)", (42,))
    db.commit()

    rows = db.get_cursor().execute("SELECT * FROM t").fetchall()
    assert rows == [(42,)]


def test_execute_invalid_sql_raises_databaseerror():
    db = Database("test")
    db.connect()
    with pytest.raises(DatabaseError):
        db.execute("THIS IS NOT VALID SQL")


def test_execute_before_connect_raises_assertion_error():
    """execute()'s except clause only catches sqlite3.Error, so
    get_cursor()'s AssertionError (a programming-error precondition, not a
    database failure) propagates unconverted."""
    db = Database("test")
    with pytest.raises(AssertionError):
        db.execute("SELECT 1")


# ── execute_safely ──────────────────────────────────────────────────────


def test_execute_safely_without_fetch_returns_none():
    db = Database("test")
    result = db.execute_safely("CREATE TABLE t (id INTEGER)")
    assert result is None


def test_execute_safely_with_fetch_returns_rows():
    db = Database("test")
    db.execute_safely("CREATE TABLE t (id INTEGER)")
    db.execute_safely("INSERT INTO t VALUES (?)", params=(7,))

    rows = db.execute_safely("SELECT * FROM t", fetch=True)

    assert rows == [(7,)]


def test_execute_safely_disconnects_after_each_call():
    """execute_safely connects, runs the query, then disconnects -- but
    disconnect() only closes the underlying sqlite3 connection, it doesn't
    reset self.connection back to None. So get_cursor() afterward doesn't
    fail with "Database not connected" (that assertion checks for None) --
    it gets past the assertion and fails on the closed connection itself
    with sqlite3.ProgrammingError instead."""
    db = Database("test")
    db.execute_safely("CREATE TABLE t (id INTEGER)")

    with pytest.raises(sqlite3.ProgrammingError):
        db.get_cursor()


def test_execute_safely_disconnects_even_when_the_query_fails():
    db = Database("test")
    db.connect()
    db.disconnect()
    with pytest.raises(DatabaseError):
        db.execute_safely("THIS IS NOT VALID SQL")
    # the connection execute_safely opened must have been closed, not leaked
    with pytest.raises(sqlite3.ProgrammingError):
        db.get_cursor()


def test_execute_safely_raises_databaseerror_when_connect_fails(monkeypatch):
    def _raise(*args, **kwargs):
        raise sqlite3.OperationalError("simulated failure")

    monkeypatch.setattr(sqlite3, "connect", _raise)
    db = Database("test")
    with pytest.raises(DatabaseError):
        db.execute_safely("SELECT 1")


# ── commit / disconnect ─────────────────────────────────────────────


def test_commit_before_connect_raises_assertion_error():
    db = Database("test")
    with pytest.raises(AssertionError):
        db.commit()


def test_disconnect_before_connect_raises_assertion_error():
    db = Database("test")
    with pytest.raises(AssertionError):
        db.disconnect()


def test_disconnect_actually_closes_the_connection():
    db = Database("test")
    db.connect()
    db.disconnect()
    with pytest.raises(sqlite3.ProgrammingError):
        db.connection.execute("SELECT 1")  # closed connections reject new queries
