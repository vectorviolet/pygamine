"""Unit tests for net.protocol: codecs + length-prefixed framing.

No sockets, no threads. This is where the framing bugs that bite networked apps
(partial reads, truncated streams, garbage bytes) get caught cheaply.
"""

from __future__ import annotations

import struct

import pytest

from pygamine.net.protocol import (
    JSONCodec,
    PickleCodec,
    Protocol,
    ProtocolError,
    TypedJSONCodec,
)
from _util import FakeSocket


MESSAGE = {"command": "!SHOOT", "value": [1, 2.5, "x", None]}


@pytest.mark.parametrize("codec", [JSONCodec(), PickleCodec()])
def test_send_then_recv_round_trips(codec):
    """A message written by send() is read back identically by recv()."""
    proto = Protocol(codec)

    writer = FakeSocket()
    proto.send(writer, MESSAGE)

    reader = FakeSocket(writer.sent)
    assert proto.recv(reader) == MESSAGE


class _Point:
    """Minimal registered type: exercises TypedJSONCodec's to_dict/from_dict and
    the nested-object path, including a tuple that JSON would flatten to a list."""

    def __init__(self, xy, label):
        self.xy = tuple(xy)
        self.label = label

    def to_dict(self):
        return {"__type__": "Point", "xy": list(self.xy), "label": self.label}

    @classmethod
    def from_dict(cls, data):
        return cls(tuple(data["xy"]), data["label"])


def test_typed_json_codec_round_trips_registered_objects():
    """A registered object survives encode->decode, even nested inside a message,
    and comes back as the class (with its tuple restored), not a bare dict."""
    proto = Protocol(TypedJSONCodec({"Point": _Point}))
    message = {"command": "!SPAWN", "value": _Point((3, 4), "base")}

    writer = FakeSocket()
    proto.send(writer, message)
    decoded = proto.recv(FakeSocket(writer.sent))

    point = decoded["value"]
    assert isinstance(point, _Point)
    assert point.xy == (3, 4) and point.label == "base"


def test_typed_json_codec_rejects_unregistered_objects():
    """Encoding an object with no to_dict is a clean TypeError, not silent data loss."""
    codec = TypedJSONCodec({})
    with pytest.raises(TypeError):
        codec.encode({"value": object()})


@pytest.mark.parametrize("chunk", [1, 2, 3, 7])
def test_recv_reassembles_fragmented_stream(chunk):
    """recv() must loop until the whole message arrives, even one byte at a time.

    This is the regression guard for the single-recv bug: a real TCP recv can
    return fewer bytes than asked for.
    """
    proto = Protocol(JSONCodec())
    framed = _frame(MESSAGE, JSONCodec())

    reader = FakeSocket(framed, chunk=chunk)
    assert proto.recv(reader) == MESSAGE


def test_recv_returns_none_on_clean_close():
    """An empty stream (peer closed before sending) reads as None, not an error."""
    proto = Protocol(JSONCodec())
    assert proto.recv(FakeSocket(b"")) is None


def test_recv_raises_on_truncated_body():
    """Header promises N bytes but the peer closes after fewer -> ProtocolError."""
    proto = Protocol(JSONCodec())
    framed = _frame(MESSAGE, JSONCodec())
    truncated = framed[: len(framed) - 3]  # drop the last few body bytes

    with pytest.raises(ProtocolError):
        proto.recv(FakeSocket(truncated))


def test_recv_raises_on_garbage_body():
    """A well-framed but undecodable body is a ProtocolError, not a crash.

    (You can write this honest test against JSON; you cannot against pickle,
    where the honest outcome of hostile bytes is 'arbitrary code runs'.)
    """
    proto = Protocol(JSONCodec())
    body = b"this is not json {{{"
    framed = struct.pack("!I", len(body)) + body

    with pytest.raises(ProtocolError):
        proto.recv(FakeSocket(framed))


def test_send_writes_length_prefixed_frame():
    """The wire format is exactly: 4-byte big-endian length + body."""
    codec = JSONCodec()
    proto = Protocol(codec)

    writer = FakeSocket()
    proto.send(writer, MESSAGE)

    body = codec.encode(MESSAGE)
    assert writer.sent[:4] == struct.pack("!I", len(body))
    assert writer.sent[4:] == body


def _frame(message, codec) -> bytes:
    body = codec.encode(message)
    return struct.pack("!I", len(body)) + body
