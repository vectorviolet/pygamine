"""Integration tests for net.transport over real loopback TCP.

These exercise BaseClient <-> BaseServer end to end (the actual socket path),
but without any game logic. Reliability rules followed here:
  * ephemeral ports (the free_port fixture) so tests never collide;
  * queue/Event with timeouts instead of sleeps, so a lost message fails the
    test fast instead of hanging.
"""

from __future__ import annotations

import queue
import struct
import threading

import pytest

from pygamine.net.transport import BaseClient, BaseServer
from _util import wait_until, start_in_thread, connect_raw

# Real sockets — slower than unit tests, so CI runs these but the pre-commit
# hook skips them via `-m "not integration"`.
pytestmark = pytest.mark.integration


def _serve(port, **callbacks) -> BaseServer:
    """Start a BaseServer on loopback and wait until it is actually listening."""
    server = BaseServer(**callbacks)
    start_in_thread(server.start, ("127.0.0.1", port))
    assert wait_until(lambda: server.is_running), "server never started listening"
    return server


def test_client_server_round_trip(free_port):
    server = _serve(free_port, on_message=lambda conn, msg: conn.send({"echo": msg}))
    inbox: queue.Queue = queue.Queue()
    client = BaseClient(on_message=inbox.put)

    try:
        assert client.connect(("127.0.0.1", free_port))
        client.send("!PING", 1)
        # times out -> test fails (never hangs forever)
        assert inbox.get(timeout=2) == {"echo": {"command": "!PING", "value": 1}}
    finally:
        client.disconnect()
        server.close()


def test_abrupt_client_disconnect_fires_server_callback(free_port):
    gone = threading.Event()
    server = _serve(free_port, on_disconnect=lambda conn: gone.set())
    client = BaseClient(on_message=lambda msg: None)

    assert client.connect(("127.0.0.1", free_port))
    client.disconnect()  # drop the socket

    assert gone.wait(timeout=2), "server did not observe the disconnect"
    server.close()


def test_malformed_input_does_not_crash_server(free_port):
    disconnected = threading.Event()
    server = _serve(
        free_port,
        on_message=lambda conn, msg: None,
        on_disconnect=lambda conn: disconnected.set(),
    )

    # Send a well-framed but undecodable body (server uses the default JSON codec).
    raw = connect_raw(free_port)
    body = b"definitely not json"
    raw.sendall(struct.pack("!I", len(body)) + body)

    assert disconnected.wait(timeout=2), "bad client was not cleaned up"
    raw.close()

    # The bad client must not have taken the server down: a good client still works.
    assert server.is_running
    inbox: queue.Queue = queue.Queue()
    good = BaseClient(on_message=inbox.put)
    server._on_message = lambda conn, msg: conn.send({"ok": True})  # type: ignore[attr-defined]
    try:
        assert good.connect(("127.0.0.1", free_port))
        good.send("!HELLO")
        assert inbox.get(timeout=2) == {"ok": True}
    finally:
        good.disconnect()
        server.close()


def test_broadcast_reaches_every_client(free_port):
    server = _serve(free_port, on_message=lambda conn, msg: None)
    q1: queue.Queue = queue.Queue()
    q2: queue.Queue = queue.Queue()
    c1 = BaseClient(on_message=q1.put)
    c2 = BaseClient(on_message=q2.put)

    try:
        assert c1.connect(("127.0.0.1", free_port))
        assert c2.connect(("127.0.0.1", free_port))
        # Wait until the server has registered both connections before broadcasting.
        assert wait_until(lambda: len(server._connections) == 2)

        server.broadcast({"command": "!HELLO"})

        assert q1.get(timeout=2) == {"command": "!HELLO"}
        assert q2.get(timeout=2) == {"command": "!HELLO"}
    finally:
        c1.disconnect()
        c2.disconnect()
        server.close()


def test_listen_binds_and_marks_the_server_running(free_port):
    statuses: list[str] = []
    server = BaseServer(on_status=statuses.append)
    try:
        assert server._listen(("127.0.0.1", free_port)) is True
        assert server.is_running is True
        assert statuses == [f"[SERVER] listening on ('127.0.0.1', {free_port})"]
    finally:
        server.close()


def test_listen_failure_is_reported_and_start_returns_instead_of_accepting(free_port):
    statuses: list[str] = []
    server = BaseServer(on_status=statuses.append)
    # TEST-NET-1 (RFC 5737) is no local interface, so bind() raises OSError
    # on every platform -- unlike a busy port, which SO_REUSEADDR can share.
    address = ("203.0.113.1", free_port)
    try:
        assert server._listen(address) is False
        server.start(address)  # must return, not block in the accept loop
        assert server.is_running is False
        assert len(statuses) == 2
        assert all(m.startswith("[SERVER] bind/listen failed") for m in statuses)
    finally:
        server.close()


def test_accept_loop_registers_and_announces_each_connection(free_port):
    connected: queue.Queue = queue.Queue()
    server = BaseServer(on_connect=connected.put)
    assert server._listen(("127.0.0.1", free_port))
    # Daemon thread: closing a listening socket doesn't wake a blocked accept()
    # on every platform, so the test doesn't wait for the loop to return.
    threading.Thread(target=server._accept_loop, daemon=True).start()
    client = BaseClient(on_message=lambda msg: None)

    try:
        assert client.connect(("127.0.0.1", free_port))
        connection = connected.get(timeout=2)
        assert connection in server._connections
    finally:
        client.disconnect()
        server.close()
