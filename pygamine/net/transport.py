"""Transport layer: connections, a client, and a server.

GUI-free and application-agnostic on purpose. These classes move bytes around
and tell you (via callbacks) when something happens. They do NOT know what your
messages mean or what a window is — the application logic and any GUI sit on top
and subscribe to the callbacks.

Decoupling rule of thumb: this layer reaches UP only through callbacks, never by
holding a reference to the application.

    transport (this file)  ->  callbacks  ->  application logic  ->  GUI
"""

from __future__ import annotations

import socket
import threading
from typing import Any, Callable

from pygamine.net.protocol import Protocol, ProtocolError


class Connection:
    """One live socket + the protocol used to talk over it.

    Wraps a single peer so the rest of the code never touches a raw socket.
    Sends are serialized with a lock because callers may broadcast from several
    threads at once.
    """

    def __init__(self, sock: socket.socket, address, protocol: Protocol) -> None:
        self.socket = sock
        self.address = address
        self._protocol = protocol
        self._send_lock = threading.Lock()
        self.is_open = True

    def send(self, message: Any) -> None:
        if not self.is_open:
            return
        try:
            with self._send_lock:
                self._protocol.send(self.socket, message)
        except OSError:
            self.close()

    def recv(self) -> Any | None:
        """Block for one message. None means the peer closed cleanly."""
        return self._protocol.recv(self.socket)

    def close(self) -> None:
        if not self.is_open:
            return
        self.is_open = False
        # shutdown() before close() actively sends the TCP FIN and unblocks any
        # thread sitting in recv() on this socket (on both ends). close() alone is
        # unreliable for that across platforms — Linux in particular may leave the
        # peer's blocked recv() hanging, so the other side never sees the drop.
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass  # already disconnected / not connected
        try:
            self.socket.close()
        except OSError:
            pass


# Callback type aliases (purely for readability).
OnMessage = Callable[[Any], None]
OnEvent = Callable[[], None]
OnStatus = Callable[[str], None]


class BaseClient:
    """Connects to a server and pumps incoming messages to a callback.

    Usage (no reference to the application inside the transport):

        client = BaseClient(
            on_message=app.handle_message,
            on_disconnect=app.on_server_lost,
            on_status=app.log,
        )
        client.connect(address)
        ...
        client.send("!SHOOT", angle)
    """

    def __init__(
        self,
        on_message: OnMessage,
        on_disconnect: OnEvent | None = None,
        on_status: OnStatus | None = None,
        protocol: Protocol | None = None,
    ) -> None:
        self._on_message = on_message
        self._on_disconnect = on_disconnect or (lambda: None)
        self._on_status = on_status or (lambda _msg: None)
        self._protocol = protocol or Protocol()
        self._connection: Connection | None = None
        self.is_connected = False

    def connect(self, address) -> bool:
        """Connect and start the background receive loop. Returns success."""
        self._on_status(f"[CLIENT] connecting to {address}")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            sock.connect(address)
        except OSError as exc:
            self._on_status(f"[CLIENT] connect failed: {exc}")
            sock.close()
            return False

        self._connection = Connection(sock, address, self._protocol)
        self.is_connected = True
        self._on_status("[CLIENT] connected")

        threading.Thread(target=self._receive_loop, daemon=True).start()
        return True

    def send(self, command: str, value: Any = None) -> None:
        """Send one message in the {command, value} shape."""
        if self._connection:
            self._connection.send({"command": command, "value": value})

    def disconnect(self) -> None:
        self.is_connected = False
        if self._connection:
            self._connection.close()

    def _receive_loop(self) -> None:
        assert self._connection is not None
        try:
            while self.is_connected:
                message = self._connection.recv()
                if message is None:
                    break  # clean close
                self._on_message(message)
        except (OSError, ProtocolError) as exc:
            self._on_status(f"[CLIENT] receive error: {exc}")
        finally:
            self.is_connected = False
            self._connection.close()
            self._on_disconnect()


class BaseServer:
    """Accepts connections and routes their messages to callbacks.

    Usage (the application logic lives in the callbacks, NOT here):

        server = BaseServer(
            on_connect=app.add_client,
            on_message=app.handle_command,   # (connection, message)
            on_disconnect=app.remove_client,
            on_status=app.log,
        )
        server.start(address)

    Each accepted Connection gets its own reader thread. The server hands the
    Connection object to every callback so the application can address a specific
    client (and build its own id -> connection map) without ever seeing a socket.
    """

    def __init__(
        self,
        on_connect: Callable[[Connection], None] | None = None,
        on_message: Callable[[Connection, Any], None] | None = None,
        on_disconnect: Callable[[Connection], None] | None = None,
        on_status: OnStatus | None = None,
        protocol: Protocol | None = None,
    ) -> None:
        self._on_connect = on_connect or (lambda _conn: None)
        self._on_message = on_message or (lambda _conn, _msg: None)
        self._on_disconnect = on_disconnect or (lambda _conn: None)
        self._on_status = on_status or (lambda _msg: None)
        self._protocol = protocol or Protocol()

        self._server_socket: socket.socket | None = None
        self.is_running = False
        self._connections: set[Connection] = set()
        self._lock = threading.Lock()

    def start(self, address) -> None:
        """Bind, listen, and accept connections until close(). Blocking.

        Run it in a thread if the caller (e.g. a GUI) needs to stay responsive.
        Bind to ("", port) to listen on 0.0.0.0 and avoid hostname-resolution
        flakiness.
        """
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self._server_socket.bind(address)
            self._server_socket.listen()
        except OSError as exc:
            self._on_status(f"[SERVER] bind/listen failed: {exc}")
            return

        self.is_running = True
        self._on_status(f"[SERVER] listening on {address}")

        while self.is_running:
            try:
                sock, peer = self._server_socket.accept()
            except OSError:
                if self.is_running:
                    self._on_status("[SERVER] accept failed")
                break

            connection = Connection(sock, peer, self._protocol)
            with self._lock:
                self._connections.add(connection)

            self._on_status(f"[SERVER] {peer} connected")
            self._on_connect(connection)
            threading.Thread(
                target=self._serve_connection, args=(connection,), daemon=True
            ).start()

    def broadcast(self, message: Any, exclude: Connection | None = None) -> None:
        """Send to every open connection. Snapshot under the lock so a
        disconnecting client can't mutate the set mid-iteration.
        """
        with self._lock:
            targets = [c for c in self._connections if c is not exclude]
        for connection in targets:
            connection.send(message)

    def close(self) -> None:
        self.is_running = False
        with self._lock:
            connections = list(self._connections)
        for connection in connections:
            connection.close()
        if self._server_socket:
            self._server_socket.close()
        self._on_status("[SERVER] closed")

    def _serve_connection(self, connection: Connection) -> None:
        try:
            while self.is_running and connection.is_open:
                message = connection.recv()
                if message is None:
                    break
                self._on_message(connection, message)
        except (OSError, ProtocolError) as exc:
            self._on_status(f"[SERVER] {connection.address} error: {exc}")
        finally:
            connection.close()
            with self._lock:
                self._connections.discard(connection)
            self._on_disconnect(connection)
            self._on_status(f"[SERVER] {connection.address} disconnected")
