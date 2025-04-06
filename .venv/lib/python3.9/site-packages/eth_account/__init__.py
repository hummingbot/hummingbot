from importlib.metadata import (
    version as __version,
)

from eth_account.account import (
    Account,
)

__all__ = ["Account"]

__version__ = __version("eth-account")
