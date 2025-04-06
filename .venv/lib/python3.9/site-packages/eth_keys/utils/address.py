from eth_utils import (
    keccak,
)


def public_key_bytes_to_address(public_key_bytes: bytes) -> bytes:
    return keccak(public_key_bytes)[-20:]
