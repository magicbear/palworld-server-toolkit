"""Synchronous client."""

from rcon.client import BaseClient
from rcon.exceptions import SessionTimeout, WrongPassword
from rcon.source.proto import Packet, Type


__all__ = ['Client']


class Client(BaseClient):
    """An RCON client."""

    def communicate(self, packet: Packet) -> Packet:
        """Sends and receives a packet."""
        with self._socket.makefile('wb') as file:
            file.write(bytes(packet))

        return self.read()

    def read(self) -> Packet:
        """Reads a packet."""
        with self._socket.makefile('rb') as file:
            return Packet.read(file)

    def login(self, passwd: str, *, encoding: str = 'utf-8') -> bool:
        """Performs a login."""
        request = Packet.make_login(passwd, encoding=encoding)
        response = self.communicate(request)

        # Wait for SERVERDATA_AUTH_RESPONSE according to:
        # https://developer.valvesoftware.com/wiki/Source_RCON_Protocol
        while response.type != Type.SERVERDATA_AUTH_RESPONSE:
            response = self.read()

        if response.id == -1:
            raise WrongPassword()

        return True

    def run(self, command: str, *args: str, encoding: str = 'utf-8') -> str:
        """Runs a command."""
        request = Packet.make_command(command, *args, encoding=encoding)
        response = self.communicate(request)

        if response.id != request.id and response.id != 0:
            raise SessionTimeout()

        return response.payload.decode(encoding)
