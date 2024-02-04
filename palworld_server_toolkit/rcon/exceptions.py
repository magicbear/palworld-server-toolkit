"""Common exceptions."""

__all__ = [
    'ConfigReadError',
    'SessionTimeout',
    'UserAbort',
    'WrongPassword'
]


class ConfigReadError(Exception):
    """Indicates an error while reading the configuration."""


class SessionTimeout(Exception):
    """Indicates that the session timed out."""


class UserAbort(Exception):
    """Indicates that a required action has been aborted by the user."""


class WrongPassword(Exception):
    """Indicates a wrong password."""
