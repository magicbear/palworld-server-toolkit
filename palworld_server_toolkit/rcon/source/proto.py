"""Low-level protocol stuff."""

from __future__ import annotations
from asyncio import StreamReader
from enum import Enum
from functools import partial
from logging import getLogger
from random import randint
from typing import IO, NamedTuple


__all__ = ['LittleEndianSignedInt32', 'Type', 'Packet', 'random_request_id']


LOGGER = getLogger(__file__)
TERMINATOR = b'\x00\x00'


def random_request_id() -> LittleEndianSignedInt32:
    """Generates a random request ID."""

    return LittleEndianSignedInt32(randint(0, LittleEndianSignedInt32.MAX))


class LittleEndianSignedInt32(int):
    """A little-endian, signed int32."""

    MIN = -2_147_483_648
    MAX = 2_147_483_647

    def __init__(self, *_):
        """Checks the boundaries."""
        super().__init__()

        if not self.MIN <= self <= self.MAX:
            raise ValueError('Signed int32 out of bounds:', int(self))

    def __bytes__(self):
        """Returns the integer as signed little endian."""
        return self.to_bytes(4, 'little', signed=True)

    @classmethod
    async def aread(cls, reader: StreamReader) -> LittleEndianSignedInt32:
        """Reads the integer from an asynchronous file-like object."""
        return cls.from_bytes(await reader.read(4), 'little', signed=True)

    @classmethod
    def read(cls, file: IO) -> LittleEndianSignedInt32:
        """Reads the integer from a file-like object."""
        return cls.from_bytes(file.read(4), 'little', signed=True)


class Type(Enum):
    """RCON packet types."""

    SERVERDATA_AUTH = LittleEndianSignedInt32(3)
    SERVERDATA_AUTH_RESPONSE = LittleEndianSignedInt32(2)
    SERVERDATA_EXECCOMMAND = LittleEndianSignedInt32(2)
    SERVERDATA_RESPONSE_VALUE = LittleEndianSignedInt32(0)

    def __int__(self):
        """Returns the actual integer value."""
        return int(self.value)

    def __bytes__(self):
        """Returns the integer value as little endian."""
        return bytes(self.value)

    @classmethod
    async def aread(cls, reader: StreamReader) -> Type:
        """Reads the type from an asynchronous file-like object."""
        return cls(await LittleEndianSignedInt32.aread(reader))

    @classmethod
    def read(cls, file: IO) -> Type:
        """Reads the type from a file-like object."""
        return cls(LittleEndianSignedInt32.read(file))


class Packet(NamedTuple):
    """An RCON packet."""

    id: LittleEndianSignedInt32
    type: Type
    payload: bytes
    terminator: bytes = TERMINATOR

    def __bytes__(self):
        """Returns the packet as bytes with prepended length."""
        payload = bytes(self.id)
        payload += bytes(self.type)
        payload += self.payload
        payload += self.terminator
        size = bytes(LittleEndianSignedInt32(len(payload)))
        return size + payload

    @classmethod
    async def aread(cls, reader: StreamReader) -> Packet:
        """Reads a packet from an asynchronous file-like object."""
        size = await LittleEndianSignedInt32.aread(reader)
        id_ = await LittleEndianSignedInt32.aread(reader)
        type_ = await Type.aread(reader)
        payload = await reader.read(size - 10)
        terminator = await reader.read(2)

        if terminator != TERMINATOR:
            LOGGER.warning('Unexpected terminator: %s', terminator)

        return cls(id_, type_, payload, terminator)

    @classmethod
    def read(cls, file: IO) -> Packet:
        """Reads a packet from a file-like object."""
        size = LittleEndianSignedInt32.read(file)
        id_ = LittleEndianSignedInt32.read(file)

        type_ = Type.read(file)
        payload = b""
        while len(payload) < size - 8:
            buf = file.read(1)
            if buf == b"":
                break
            payload += buf
            if payload[-2:] == TERMINATOR:
                break
        terminator = payload[-2:]
        # payload = file.read(size - 10)
        # print(payload)
        # terminator = file.read(2)
        # print("Terminator ", terminator)

        if terminator != TERMINATOR:
            LOGGER.warning('Unexpected terminator: %s', terminator)

        return cls(id_, type_, payload, terminator)

    @classmethod
    def make_command(cls, *args: str, encoding: str = 'utf-8') -> Packet:
        """Creates a command packet."""
        return cls(
            random_request_id(), Type.SERVERDATA_EXECCOMMAND,
            b' '.join(map(partial(str.encode, encoding=encoding), args))
        )

    @classmethod
    def make_login(cls, passwd: str, *, encoding: str = 'utf-8') -> Packet:
        """Creates a login packet."""
        return cls(
            random_request_id(), Type.SERVERDATA_AUTH, passwd.encode(encoding)
        )
