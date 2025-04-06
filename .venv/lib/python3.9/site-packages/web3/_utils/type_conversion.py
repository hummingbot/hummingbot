from typing import (
    Union,
)

from eth_typing import (
    HexStr,
)
from eth_utils import (
    to_bytes,
    to_hex,
)

from web3.exceptions import (
    Web3ValueError,
)


def to_hex_if_bytes(val: Union[HexStr, str, bytes, bytearray]) -> HexStr:
    """
    Note: This method does not validate against all cases and is only
    meant to work with bytes and hex strings.
    """
    if isinstance(val, str) and not val.startswith("0x"):
        raise Web3ValueError(f"Expected a hex string. Got: {val!r}")

    return to_hex(val) if isinstance(val, (bytes, bytearray)) else to_hex(hexstr=val)


def to_bytes_if_hex(val: Union[HexStr, str, bytes, bytearray]) -> bytes:
    """
    Note: This method does not validate against all cases and is only
    meant to work with bytes and hex strings.
    """
    return to_bytes(hexstr=val) if isinstance(val, str) else val
