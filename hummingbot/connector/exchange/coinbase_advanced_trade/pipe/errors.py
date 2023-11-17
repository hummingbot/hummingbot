from typing import Any


class PipeStoppedError(Exception):
    """Raised when an attempt is made to get an item from a stopped Pipe."""
    pass


class PipeFullError(Exception):
    """Raised when an attempt is made to put an item in a full Pipe."""
    def __init__(self, msg: str = None, lost_item: Any = None):
        self.lost_item = lost_item
        super().__init__(msg)


class PipeFullWithItemError(Exception):
    """Raised when an attempt is made to put an item in a full Pipe."""
    def __init__(self, *, msg: str = None, lost_item: Any = None):
        self.lost_item = lost_item
        super().__init__(msg)


class PipeSentinelError(Exception):
    """Raised when an exception occurs related to the SENTINEL of Pipe."""
    pass


class PipeTypeError(Exception):
    """Raised when an exception occurs related to the Pipe structure."""
    pass
