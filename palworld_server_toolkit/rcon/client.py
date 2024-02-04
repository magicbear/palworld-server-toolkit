"""Common base client."""

from socket import SOCK_STREAM, SocketKind, socket
from typing import Optional


__all__ = ['BaseClient']


class BaseClient:
    """A common RCON client."""

    def __init__(
            self, host: str, port: int, *,
            timeout: Optional[float] = None,
            passwd: Optional[str] = None
    ):
        """Initializes the base client with the SOCK_STREAM socket type."""
        self._socket = socket(type=self._socket_type)
        self.host = host
        self.port = port
        self.timeout = timeout
        self.passwd = passwd

    def __init_subclass__(cls, *, socket_type: SocketKind = SOCK_STREAM):
        cls._socket_type = socket_type

    def __enter__(self):
        """Attempts an auto-login if a password is set."""
        self._socket.__enter__()
        self.connect(login=True)
        return self

    def __exit__(self, typ, value, traceback):
        """Delegates to the underlying socket's exit method."""
        return self._socket.__exit__(typ, value, traceback)

    @property
    def timeout(self) -> float:
        """Returns the socket timeout."""
        return self._socket.gettimeout()

    @timeout.setter
    def timeout(self, timeout: float):
        """Sets the socket timeout."""
        self._socket.settimeout(timeout)

    def connect(self, login: bool = False) -> None:
        """Connects the socket and attempts a
        login if wanted and a password is set.
        """
        self._socket.connect((self.host, self.port))

        if login and self.passwd is not None:
            self.login(self.passwd)

    def close(self) -> None:
        """Closes the socket connection."""
        self._socket.close()

    def login(self, passwd: str) -> bool:
        """Performs a login."""
        raise NotImplementedError()

    def run(self, command: str, *args: str) -> str:
        """Runs a command."""
        raise NotImplementedError()
