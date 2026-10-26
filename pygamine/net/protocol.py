"""Wire protocol: framing + (de)serialization, in ONE place.

Game-agnostic: it only knows how to put a Python message onto a TCP stream and
read it back. The transport (and any app built on it) reuse this so the framing
logic lives exactly once.

Wire format for every message:

    [ 4-byte big-endian unsigned length ][ <length> bytes of serialized body ]

The body codec is pluggable (see `Codec`). The default is JSON, which is safe
to read from an untrusted peer. Pickle is offered too, but read the warning on
`PickleCodec` before you reach for it.
"""

from __future__ import annotations

import json
import pickle
import socket
import struct
from typing import Any, Protocol as TypingProtocol

# Length-prefix size in bytes (a big-endian unsigned int). Defined here so the
# protocol has no dependency on any host application's constants.
HEADER_SIZE = struct.calcsize("!I")


class ProtocolError(Exception):
    """Raised when the stream is malformed or the peer closed mid-message."""


class Codec(TypingProtocol):
    """How a message dict is turned into bytes and back."""

    def encode(self, message: Any) -> bytes: ...
    def decode(self, raw: bytes) -> Any: ...


class JSONCodec:
    """Default codec. Safe against hostile input, but only handles plain data
    (dicts, lists, str, int, float, bool, None) — not arbitrary objects.

    To send custom objects across the wire, give those classes `to_dict()` /
    `from_dict()` and convert at the application layer, not here. That also stops
    the wire format from being coupled to your class definitions.
    """

    def encode(self, message: Any) -> bytes:
        return json.dumps(message).encode("utf-8")

    def decode(self, raw: bytes) -> Any:
        return json.loads(raw.decode("utf-8"))


class TypedJSONCodec:
    """JSON codec that can also carry registered application objects — safely.

    Like JSONCodec it speaks plain JSON (so a hostile peer can at worst feed you
    bad data, never run code), but it round-trips classes that expose
    ``to_dict()`` / ``from_dict()``:

    - encode: any object json can't handle is passed to ``to_dict()``, which must
      tag the dict with a ``"__type__"`` the decoder will recognise and return a
      fully plain (already-nested) structure.
    - decode: every dict carrying a known ``"__type__"`` is rebuilt via that
      class's ``from_dict()``; object_hook runs bottom-up, so nested objects are
      already reconstructed when their container is built.

    The ``registry`` (type tag -> class) is supplied by the application, so this
    class stays game-agnostic — it knows the protocol, not your classes.
    """

    TYPE_KEY = "__type__"

    def __init__(self, registry: dict) -> None:
        self._registry = dict(registry)

    def encode(self, message: Any) -> bytes:
        return json.dumps(message, default=self._to_dict, separators=(",", ":")).encode(
            "utf-8"
        )

    def decode(self, raw: bytes) -> Any:
        return json.loads(raw.decode("utf-8"), object_hook=self._from_dict)

    def _to_dict(self, obj: Any) -> dict[str, Any]:
        to_dict = getattr(obj, "to_dict", None)
        if callable(to_dict):
            return to_dict()
        raise TypeError(f"{type(obj).__name__} is not JSON serializable")

    def _from_dict(self, data: dict[str, Any]) -> Any:
        cls = self._registry.get(data.get(self.TYPE_KEY))
        return cls.from_dict(data) if cls is not None else data


class PickleCodec:
    """Sends whole Python objects.

    WARNING: pickle.loads() on bytes from a socket is arbitrary remote code
    execution — a malicious peer can run code in your process. Only acceptable
    on a fully trusted LAN. Prefer JSONCodec + to_dict/from_dict.
    """

    def encode(self, message: Any) -> bytes:
        return pickle.dumps(message)

    def decode(self, raw: bytes) -> Any:
        return pickle.loads(raw)


def _recv_exactly(sock: socket.socket, length: int) -> bytes | None:
    """Read exactly `length` bytes, or None if the peer closed the connection.

    TCP recv() may return fewer bytes than requested, so we loop. This is the
    single canonical copy of the recv_all logic.
    """
    buffer = bytearray()

    while len(buffer) < length:
        chunk = sock.recv(length - len(buffer))

        if not chunk:  # peer closed the connection
            return None

        buffer.extend(chunk)

    return bytes(buffer)


class Protocol:
    """Length-prefixed message framing over a single socket.

    Stateless apart from the chosen codec, so one instance can be shared by
    every connection (or you can keep one per connection — either is fine).
    """

    def __init__(self, codec: Codec | None = None) -> None:
        self.codec: Codec = codec or JSONCodec()

    def send(self, sock: socket.socket, message: Any) -> None:
        """Serialize, length-prefix, and send a single message."""
        body = self.codec.encode(message)
        header = struct.pack("!I", len(body))
        sock.sendall(header + body)

    def recv(self, sock: socket.socket) -> Any | None:
        """Read a single message, or None if the peer closed cleanly.

        Raises ProtocolError on a truncated/garbled stream.
        """
        header = _recv_exactly(sock, HEADER_SIZE)
        if header is None:
            return None  # clean close before a new message

        (length,) = struct.unpack("!I", header)
        body = _recv_exactly(sock, length)
        if body is None:
            raise ProtocolError("connection closed mid-message")

        try:
            return self.codec.decode(body)
        except (ValueError, pickle.UnpicklingError) as exc:
            raise ProtocolError(f"could not decode message: {exc}") from exc
