from eth_typing import (
    ChecksumAddress,
    HexAddress,
)
from eth_utils import (
    keccak,
    to_bytes,
    to_checksum_address,
)
import rlp

from web3.exceptions import (
    Web3ValidationError,
)
from web3.types import (
    HexStr,
    Nonce,
)


def get_create_address(sender: HexAddress, nonce: Nonce) -> ChecksumAddress:
    """
    Determine the resulting `CREATE` opcode contract address for a sender and a nonce.
    """
    contract_address = keccak(rlp.encode([to_bytes(hexstr=sender), nonce])).hex()[-40:]
    return to_checksum_address(contract_address)


def get_create2_address(
    sender: HexAddress, salt: HexStr, init_code: HexStr
) -> ChecksumAddress:
    """
    Determine the resulting `CREATE2` opcode contract address for a sender, salt and
    bytecode.
    """
    if len(to_bytes(hexstr=salt)) != 32:
        raise Web3ValidationError(
            f"`salt` must be 32 bytes, {len(to_bytes(hexstr=salt))} != 32"
        )

    contract_address = keccak(
        b"\xff"
        + to_bytes(hexstr=sender)
        + to_bytes(hexstr=salt)
        + keccak(to_bytes(hexstr=init_code))
    ).hex()[-40:]
    return to_checksum_address(contract_address)
