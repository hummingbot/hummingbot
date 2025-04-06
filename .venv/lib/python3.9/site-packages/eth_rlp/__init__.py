from importlib.metadata import (
    version as __version,
)

from .main import (
    HashableRLP,
)

__version__ = __version("eth-rlp")
