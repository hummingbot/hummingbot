"""This module encodes and decodes various types of base58 encodings."""

from typing import Dict, List, Optional, Tuple

import base58
from typing_extensions import Final

from xrpl.constants import CryptoAlgorithm
from xrpl.core.addresscodec.exceptions import XRPLAddressCodecException
from xrpl.core.addresscodec.utils import XRPL_ALPHABET

# base58 encodings: https://xrpl.org/base58-encodings.html
# Account address (20 bytes)
_CLASSIC_ADDRESS_PREFIX: Final[List[int]] = [0x0]
# value is 35; Account public key (33 bytes)
_ACCOUNT_PUBLIC_KEY_PREFIX: Final[List[int]] = [0x23]
# value is 33; Seed value (for secret keys) (16 bytes)
_FAMILY_SEED_PREFIX: Final[List[int]] = [0x21]
# value is 28; Validation public key (33 bytes)
_NODE_PUBLIC_KEY_PREFIX: Final[List[int]] = [0x1C]
# [1, 225, 75]
_ED25519_SEED_PREFIX: Final[List[int]] = [0x01, 0xE1, 0x4B]

SEED_LENGTH: Final[int] = 16

_CLASSIC_ADDRESS_LENGTH: Final[int] = 20
_NODE_PUBLIC_KEY_LENGTH: Final[int] = 33
_ACCOUNT_PUBLIC_KEY_LENGTH: Final[int] = 33

_ALGORITHM_TO_PREFIX_MAP: Final[Dict[CryptoAlgorithm, List[List[int]]]] = {
    CryptoAlgorithm.ED25519: [_ED25519_SEED_PREFIX, _FAMILY_SEED_PREFIX],
    CryptoAlgorithm.SECP256K1: [_FAMILY_SEED_PREFIX],
}  # first is default, rest are other options


def _encode(bytestring: bytes, prefix: List[int], expected_length: int) -> str:
    """
    Returns the base58 encoding of the bytestring, with the given data prefix
    (which indicates type) and while ensuring the bytestring is the expected
    length.
    """
    if expected_length and len(bytestring) != expected_length:
        error_message = """unexpected_payload_length: len(bytestring) does not match
        expected_length. Ensure that the bytes are a bytestring."""
        raise XRPLAddressCodecException(error_message)
    encoded_prefix = bytes(prefix)
    payload = encoded_prefix + bytestring
    return base58.b58encode_check(payload, alphabet=XRPL_ALPHABET).decode("utf-8")


def _decode(b58_string: str, prefix: bytes) -> bytes:
    """
    Args:
        b58_string: A base58 value.
        prefix: The prefix prepended to the bytestring.

    Returns:
        The byte decoding of the base58-encoded string.
    """
    prefix_length = len(prefix)
    decoded = base58.b58decode_check(b58_string, alphabet=XRPL_ALPHABET)
    if decoded[:prefix_length] != prefix:
        raise XRPLAddressCodecException("Provided prefix is incorrect")
    return decoded[prefix_length:]


def encode_seed(entropy: bytes, encoding_type: CryptoAlgorithm) -> str:
    """
    Returns an encoded seed.

    Args:
        entropy: Entropy bytes of SEED_LENGTH.
        encoding_type: Either ED25519 or SECP256K1.

    Returns:
        An encoded seed.

    Raises:
        XRPLAddressCodecException: If entropy is not of length SEED_LENGTH
            or the encoding type is not one of CryptoAlgorithm.
    """
    if len(entropy) != SEED_LENGTH:
        raise XRPLAddressCodecException(f"Entropy must have length {SEED_LENGTH}")
    if encoding_type not in CryptoAlgorithm:
        raise XRPLAddressCodecException(
            f"Encoding type must be one of {CryptoAlgorithm}"
        )

    prefix = _ALGORITHM_TO_PREFIX_MAP[encoding_type][0]
    return _encode(entropy, prefix, SEED_LENGTH)


def decode_seed(
    seed: str, algorithm: Optional[CryptoAlgorithm] = None
) -> Tuple[bytes, CryptoAlgorithm]:
    """
    Returns (decoded seed, its algorithm).

    Args:
        seed: The b58 encoding of a seed.
        algorithm: The encoding algorithm. Inferred from the seed if not included.

    Returns:
        (decoded seed, its algorithm).

    Raises:
        XRPLAddressCodecException: If the seed is invalid.
    """
    if algorithm is not None:
        # check all algorithm prefixes
        for prefix in _ALGORITHM_TO_PREFIX_MAP[algorithm]:
            try:
                decoded_result = _decode(seed, bytes(prefix))
                return decoded_result, algorithm
            except XRPLAddressCodecException:
                # prefix is incorrect, wrong prefix
                continue
        raise XRPLAddressCodecException("Wrong algorithm for the seed type.")

    for algorithm in CryptoAlgorithm:  # use default prefix
        prefix = _ALGORITHM_TO_PREFIX_MAP[algorithm][0]
        try:
            decoded_result = _decode(seed, bytes(prefix))
            return decoded_result, algorithm
        except XRPLAddressCodecException:
            # prefix is incorrect, wrong algorithm
            continue
    raise XRPLAddressCodecException(
        "Invalid seed; could not determine encoding algorithm"
    )


def encode_classic_address(bytestring: bytes) -> str:
    """
    Returns the classic address encoding of these bytes as a base58 string.

    Args:
        bytestring: Bytes to be encoded.

    Returns:
        The classic address encoding of these bytes as a base58 string.
    """
    return _encode(bytestring, _CLASSIC_ADDRESS_PREFIX, _CLASSIC_ADDRESS_LENGTH)


def decode_classic_address(classic_address: str) -> bytes:
    """
    Returns the decoded bytes of the classic address.

    Args:
        classic_address: Classic address to be decoded.

    Returns:
        The decoded bytes of the classic address.
    """
    return _decode(classic_address, bytes(_CLASSIC_ADDRESS_PREFIX))


def encode_node_public_key(bytestring: bytes) -> str:
    """
    Returns the node public key encoding of these bytes as a base58 string.

    Args:
        bytestring: Bytes to be encoded.

    Returns:
        The node public key encoding of these bytes as a base58 string.
    """
    return _encode(bytestring, _NODE_PUBLIC_KEY_PREFIX, _NODE_PUBLIC_KEY_LENGTH)


def decode_node_public_key(node_public_key: str) -> bytes:
    """
    Returns the decoded bytes of the node public key

    Args:
        node_public_key: Node public key to be decoded.

    Returns:
        The decoded bytes of the node public key.

    """
    return _decode(node_public_key, bytes(_NODE_PUBLIC_KEY_PREFIX))


def encode_account_public_key(bytestring: bytes) -> str:
    """
    Returns the account public key encoding of these bytes as a base58 string.

    Args:
        bytestring: Bytes to be encoded.

    Returns:
        The account public key encoding of these bytes as a base58 string.
    """
    return _encode(bytestring, _ACCOUNT_PUBLIC_KEY_PREFIX, _ACCOUNT_PUBLIC_KEY_LENGTH)


def decode_account_public_key(account_public_key: str) -> bytes:
    """
    Returns the decoded bytes of the account public key.

    Args:
        account_public_key: Account public key to be decoded.

    Returns:
        The decoded bytes of the account public key.
    """
    return _decode(account_public_key, bytes(_ACCOUNT_PUBLIC_KEY_PREFIX))


def is_valid_classic_address(classic_address: str) -> bool:
    """
    Returns whether `classic_address` is a valid classic address.

    Args:
        classic_address: The classic address to validate.

    Returns:
        Whether `classic_address` is a valid classic address.
    """
    try:
        decode_classic_address(classic_address)
        return True
    except (XRPLAddressCodecException, ValueError):
        return False
