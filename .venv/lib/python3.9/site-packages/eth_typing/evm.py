"""
Type definitions for the Ethereum Virtual Machine (EVM).
"""

from typing import (
    Literal,
    NewType,
    TypeVar,
    Union,
)

from .encoding import (
    HexStr,
)

Hash32 = NewType("Hash32", bytes)
"""
A 32-byte hash value.
"""
BlockNumber = NewType("BlockNumber", int)
"""
Any integer that represents a valid block number on a chain.
"""
BlockParams = Literal["latest", "earliest", "pending", "safe", "finalized"]
"""
A type which specifies the block reference parameter.

- ``"latest"``: The latest block.
- ``"earliest"``: The earliest block.
- ``"pending"``: The pending block.
- ``"safe"``: The safe block.
- ``"finalized"``: The finalized block.
"""
BlockIdentifier = Union[BlockParams, BlockNumber, Hash32, HexStr, int]
"""
A type that represents a block identifier value.

- ``BlockParams``: A block reference parameter.
- ``BlockNumber``: A block number integer value.
- ``Hash32``: A 32-byte hash value.
- ``HexStr``: A string that represents a hex value.
- ``int``: An integer value.
"""
Address = NewType("Address", bytes)
"""
A type that contains a 32-byte canonical address.
"""
HexAddress = NewType("HexAddress", HexStr)
"""
A type that contains a hex encoded address. This is a 32-byte hex string with a prefix
of "0x".
"""
ChecksumAddress = NewType("ChecksumAddress", HexAddress)
"""
A type that contains a eth_typing.evm.HexAddress that is formatted according to
`ERC55 <https://github.com/ethereum/EIPs/issues/55>`_. This is a 40 character hex
string with a prefix of "0x" and mixed case letters.
"""
AnyAddress = TypeVar("AnyAddress", Address, HexAddress, ChecksumAddress)
"""
A type that represents any type of address.
"""
