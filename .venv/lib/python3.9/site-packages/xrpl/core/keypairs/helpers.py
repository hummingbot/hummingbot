"""Miscellaneous functions that are private to xrpl.core.keypairs."""

import hashlib

import Crypto.Hash.RIPEMD160 as RIPEMD160


def sha512_first_half(message: bytes) -> bytes:
    """
    Returns the first 32 bytes of SHA-512 hash of message.

    Args:
        message: Bytes input to hash.

    Returns:
        The first 32 bytes of SHA-512 hash of message.
    """
    return hashlib.sha512(message).digest()[:32]


def get_account_id(public_key: bytes) -> bytes:
    """
    Returns the account ID for a given public key. See
    https://xrpl.org/cryptographic-keys.html#account-id-and-address
    to learn about the relationship between keys and account IDs.

    Args:
        public_key: Unencoded public key.

    Returns:
        The account ID for the given public key.
    """
    sha_hash = hashlib.sha256(public_key).digest()
    return bytes(RIPEMD160.new(sha_hash).digest())
