from importlib.metadata import (
    version as __version,
)

from .main import (
    KeyAPI,
    lazy_key_api as keys,
)

__version__ = __version("eth-keys")
