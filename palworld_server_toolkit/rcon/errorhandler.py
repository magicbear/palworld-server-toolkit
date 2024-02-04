"""Common errors handler."""

from logging import Logger
from socket import timeout

from rcon.exceptions import ConfigReadError
from rcon.exceptions import SessionTimeout
from rcon.exceptions import UserAbort
from rcon.exceptions import WrongPassword


__all__ = ['ErrorHandler']


ERRORS = {
    UserAbort: (1, None),
    ConfigReadError: (2, None),
    ConnectionRefusedError: (3, 'Connection refused.'),
    (TimeoutError, timeout): (4, 'Connection timed out.'),
    WrongPassword: (5, 'Wrong password.'),
    SessionTimeout: (6, 'Session timed out.')
}


class ErrorHandler:
    """Handles common errors and exits."""

    __slots__ = ('logger', 'exit_code')

    def __init__(self, logger: Logger):
        """Sets the logger."""
        self.logger = logger
        self.exit_code = 0

    def __enter__(self):
        return self

    def __exit__(self, _, value: Exception, __):
        """Checks for connection errors and exits respectively."""
        if value is None:
            return True

        for typ, (exit_code, message) in ERRORS.items():
            if isinstance(value, typ):
                self.exit_code = exit_code

                if message:
                    self.logger.error(message)

                return True

        return None
