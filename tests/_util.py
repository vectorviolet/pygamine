"""Test doubles and helpers shared across the suite.

FakeSocket is the heart of the unit layer: it lets us test logic at the
socket boundary (Protocol) without ever opening a real socket.
"""

from __future__ import annotations

import socket
import threading
import time


class FakeSocket:
    """A stand-in for a TCP socket.

    `recv` hands back the queued bytes in `chunk`-sized pieces, which lets us
    reproduce TCP fragmentation (the exact condition a naive single-recv
    implementation gets wrong). `sendall` just records what was written.
    """

    def __init__(self, data: bytes = b"", chunk: int = 4096) -> None:
        self._recv_data = bytearray(data)
        self._chunk = chunk
        self.sent = bytearray()

    def recv(self, n: int) -> bytes:
        take = min(n, self._chunk, len(self._recv_data))
        chunk = bytes(self._recv_data[:take])
        del self._recv_data[:take]
        return chunk

    def sendall(self, data: bytes) -> None:
        self.sent.extend(data)


def wait_until(predicate, timeout: float = 2.0, interval: float = 0.01) -> bool:
    """Poll `predicate` until it is true or `timeout` elapses.

    Used to wait for asynchronous state (e.g. a server becoming ready) without a
    blind sleep. Returns the final truthiness so callers can assert on it.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return bool(predicate())


def start_in_thread(target, *args) -> threading.Thread:
    thread = threading.Thread(target=target, args=args, daemon=True)
    thread.start()
    return thread


def connect_raw(port: int) -> socket.socket:
    """A plain client socket connected to loopback `port` (for malformed-input tests)."""
    return socket.create_connection(("127.0.0.1", port), timeout=2)
