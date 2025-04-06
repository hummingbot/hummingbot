from importlib.metadata import (
    version as __version,
)

from .bloom import (
    BloomFilter,
)

__version__ = __version("eth-bloom")
