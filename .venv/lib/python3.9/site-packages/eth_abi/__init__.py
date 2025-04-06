from importlib.metadata import (
    version as __version,
)

from eth_abi.abi import (
    decode,
    encode,
    is_encodable,
    is_encodable_type,
)

__version__ = __version("eth-abi")
