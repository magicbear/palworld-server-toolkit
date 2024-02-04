"""RCON client library."""

from typing import Any, Coroutine
from warnings import warn

from rcon.source import rcon as _rcon
from rcon.source import Client as _Client


class Client(_Client):
    """Backwards compatibility."""

    def __init__(self, *args, **kwargs):
        warn(
            'rcon.Client() is deprecated. Use rcon.source.Client() instead.',
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(*args, **kwargs)


def rcon(*args, **kwargs) -> Coroutine[Any, Any, str]:
    """Backwards compatibility."""

    warn(
        'rcon.rcon() is deprecated. Use rcon.source.rcon() instead.',
        DeprecationWarning,
        stacklevel=2
    )
    return _rcon(*args, **kwargs)
