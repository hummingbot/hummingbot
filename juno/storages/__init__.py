from typing import Union

from .memory import Memory
from .sqlite import SQLite

Storage = Union[Memory, SQLite]

__all__ = [
    "Memory",
    "SQLite",
]
