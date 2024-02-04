"""Low-level protocol stuff."""

from __future__ import annotations
from typing import NamedTuple, Union
from zlib import crc32


__all__ = [
    'RESPONSE_TYPES',
    'Header',
    'LoginRequest',
    'LoginResponse',
    'CommandRequest',
    'CommandResponse',
    'ServerMessage',
    'Request',
    'Response'
]


PREFIX = 'BE'
INFIX = 0xff


class Header(NamedTuple):
    """Packet header."""

    crc32: int
    type: int

    def __bytes__(self):
        return b''.join((
            PREFIX.encode('ascii'),
            self.crc32.to_bytes(4, 'little'),
            INFIX.to_bytes(1, 'little'),
            self.type.to_bytes(1, 'little')
        ))

    @classmethod
    def create(cls, typ: int, payload: bytes) -> Header:
        """Creates a header for the given payload."""
        return cls(
            crc32(b''.join((
                INFIX.to_bytes(1, 'little'),
                typ.to_bytes(1, 'little'),
                payload
            ))),
            typ
        )

    @classmethod
    def from_bytes(cls, payload: bytes) -> Header:
        """Creates a header from the given bytes."""
        if (size := len(payload)) != 8:
            raise ValueError('Invalid payload size', size)

        if (prefix := payload[:2].decode('ascii')) != PREFIX:
            raise ValueError('Invalid prefix', prefix)

        if (infix := int.from_bytes(payload[6:7], 'little')) != INFIX:
            raise ValueError('Invalid infix', infix)

        return cls(
            int.from_bytes(payload[2:6], 'little'),
            int.from_bytes(payload[7:8], 'little')
        )


class LoginRequest(str):
    """Login request packet."""

    def __bytes__(self):
        return bytes(self.header) + self.payload

    @property
    def payload(self) -> bytes:
        """Returns the payload."""
        return self.encode('ascii')

    @property
    def header(self) -> Header:
        """Returns the appropriate header."""
        return Header.create(0x00, self.payload)


class LoginResponse(NamedTuple):
    """A login response."""

    header: Header
    success: bool

    @classmethod
    def from_bytes(cls, header: Header, payload: bytes) -> LoginResponse:
        """Creates a login response from the given bytes."""
        return cls(header, bool(int.from_bytes(payload[:1], 'little')))


class CommandRequest(NamedTuple):
    """Command packet."""

    seq: int
    command: str

    def __bytes__(self):
        return bytes(self.header) + self.payload

    @property
    def payload(self) -> bytes:
        """Returns the payload."""
        return b''.join((
            self.seq.to_bytes(1, 'little'),
            self.command.encode('ascii')
        ))

    @property
    def header(self) -> Header:
        """Returns the appropriate header."""
        return Header.create(0x01, self.payload)

    @classmethod
    def from_string(cls, command: str) -> CommandRequest:
        """Creates a command packet from the given string."""
        return cls(0x00, command)

    @classmethod
    def from_command(cls, command: str, *args: str) -> CommandRequest:
        """Creates a command packet from the command and arguments."""
        return cls.from_string(' '.join([command, *args]))


class CommandResponse(NamedTuple):
    """A command response."""

    header: Header
    seq: int
    payload: bytes

    @classmethod
    def from_bytes(cls, header: Header, payload: bytes) -> CommandResponse:
        """Creates a command response from the given bytes."""
        return cls(
            header,
            int.from_bytes(payload[:1], 'little'),
            payload[1:]
        )

    @property
    def message(self) -> str:
        """Returns the text message."""
        return self.payload.decode('ascii')


class ServerMessage(NamedTuple):
    """A message from the server."""

    header: Header
    seq: int
    payload: bytes

    @classmethod
    def from_bytes(cls, header: Header, payload: bytes) -> ServerMessage:
        """Creates a server message from the given bytes."""
        return cls(
            header,
            int.from_bytes(payload[:1], 'little'),
            payload[1:]
        )

    @property
    def message(self) -> str:
        """Returns the text message."""
        return self.payload.decode('ascii')


Request = Union[LoginRequest, CommandRequest]
Response = Union[LoginResponse, CommandResponse, ServerMessage]

RESPONSE_TYPES = {
    0x00: LoginResponse,
    0x01: CommandResponse,
    0x02: ServerMessage
}
