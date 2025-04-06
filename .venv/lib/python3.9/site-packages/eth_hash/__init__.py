from importlib.metadata import (
    version as __version,
)

from .main import (
    Keccak256,
)

__version__ = __version("eth-hash")
