"""RCON exceptions."""

__all__ = ['RequestIdMismatch']


class RequestIdMismatch(Exception):
    """Indicates a mismatch in request IDs."""

    def __init__(self, sent: int, received: int):
        """Sets the IDs that have been sent and received."""
        super().__init__()
        self.sent = sent
        self.received = received
