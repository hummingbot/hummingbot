"""This module handles everything related to X-Addresses."""

from typing import Optional, Tuple

import base58
from typing_extensions import Final

from xrpl.core.addresscodec.codec import decode_classic_address, encode_classic_address
from xrpl.core.addresscodec.exceptions import XRPLAddressCodecException
from xrpl.core.addresscodec.utils import XRPL_ALPHABET

MAX_32_BIT_UNSIGNED_INT: Final[int] = 4294967295

_PREFIX_BYTES_MAIN: Final[bytes] = bytes([0x05, 0x44])  # 5, 68
_PREFIX_BYTES_TEST: Final[bytes] = bytes([0x04, 0x93])  # 4, 147

# To better understand the cryptographic details, visit
# https://github.com/xrp-community/standards-drafts/issues/6

# General format of an X-Address:
# [← 2 byte prefix →|← 160 bits of account ID →|← 8 bits of flags →|← 64 bits of tag →]


def classic_address_to_xaddress(
    classic_address: str, tag: Optional[int], is_test_network: bool
) -> str:
    """
    Returns the X-Address representation of the data.

    Args:
        classic_address: The base58 encoding of the classic address.
        tag: The destination tag.
        is_test_network: Whether it is the test network or the main network.

    Returns:
        The X-Address representation of the data.

    Raises:
        XRPLAddressCodecException: If the classic address does not have enough bytes
            or the tag is invalid.
    """
    classic_address_bytes = decode_classic_address(classic_address)
    if len(classic_address_bytes) != 20:
        raise XRPLAddressCodecException("Account ID must be 20 bytes")

    if tag is not None and tag > MAX_32_BIT_UNSIGNED_INT:
        raise XRPLAddressCodecException("Invalid tag")

    flag = tag is not None
    if tag is None:
        tag = 0

    bytestring = _PREFIX_BYTES_TEST if is_test_network else _PREFIX_BYTES_MAIN
    bytestring += classic_address_bytes
    encoded_tag = bytes(
        [
            flag,
            tag & 0xFF,
            tag >> 8 & 0xFF,
            tag >> 16 & 0xFF,
            tag >> 24 & 0xFF,
            0,
            0,
            0,
            0,
        ]
    )
    bytestring += encoded_tag

    return base58.b58encode_check(bytestring, alphabet=XRPL_ALPHABET).decode("utf-8")


def xaddress_to_classic_address(xaddress: str) -> Tuple[str, Optional[int], bool]:
    """
    Returns a tuple containing the classic address, tag, and whether the address
    is on a test network for an X-Address.

    Args:
        xaddress: base58-encoded X-Address.

    Returns:
        A tuple containing:
            classic_address: the base58 classic address
            tag: the destination tag
            is_test_network: whether the address is on the test network (or main)
    """
    decoded = base58.b58decode_check(
        xaddress, alphabet=XRPL_ALPHABET
    )  # convert b58 to bytes
    is_test_network = _is_test_address(decoded[:2])
    classic_address_bytes = decoded[2:22]
    tag = _get_tag_from_buffer(decoded[22:])  # extracts the destination tag

    classic_address = encode_classic_address(classic_address_bytes)
    return (classic_address, tag, is_test_network)


def ensure_classic_address(account: str) -> str:
    """
    If an address is an X-Address, converts it to a classic address.

    Args:
        account: A classic address or X-address.

    Returns:
        The account's classic address

    Raises:
        XRPLAddressCodecException: if the X-Address has an associated tag.
    """
    if is_valid_xaddress(account):
        classic_address, tag, _ = xaddress_to_classic_address(account)

        """
        Except for special cases, X-addresses used for requests must not
        have an embedded tag. In other words, `tag` should be None.
        """
        if tag is not None:
            raise XRPLAddressCodecException(
                "This command does not support the use of a tag. Use "
                "an address without a tag"
            )

        return classic_address

    return account


def _is_test_address(prefix: bytes) -> bool:
    """
    Returns whether a decoded X-Address is a test address.

    Args:
        prefix: The first 2 bytes of an X-Address.

    Returns:
        Whether a decoded X-Address is a test address.

    Raises:
        XRPLAddressCodecException: If the prefix is invalid.
    """
    if _PREFIX_BYTES_MAIN == prefix:
        return False
    if _PREFIX_BYTES_TEST == prefix:
        return True
    raise XRPLAddressCodecException("Invalid X-Address: bad prefix")


def _get_tag_from_buffer(buffer: bytes) -> Optional[int]:
    """
    Returns the destination tag extracted from the suffix of the X-Address.

    Args:
        buffer: The buffer to extract a destination tag from.

    Returns:
        The destination tag extracted from the suffix of the X-Address.
    """
    flag = buffer[0]
    if flag >= 2:
        raise XRPLAddressCodecException("Unsupported X-Address")
    if flag == 1:  # Little-endian to big-endian
        return (
            buffer[1] + buffer[2] * 0x100 + buffer[3] * 0x10000 + buffer[4] * 0x1000000
        )  # inverse of what happens in encode
    if flag != 0:
        raise XRPLAddressCodecException("Flag must be zero to indicate no tag")
    if bytes.fromhex("0000000000000000") != buffer[1:9]:
        raise XRPLAddressCodecException("Remaining bytes must be zero")
    return None


def is_valid_xaddress(xaddress: str) -> bool:
    """
    Returns whether ``xaddress`` is a valid X-Address.

    Args:
        xaddress: The X-Address to check for validity.

    Returns:
        Whether ``xaddress`` is a valid X-Address.
    """
    try:
        xaddress_to_classic_address(xaddress)
        return True
    except (XRPLAddressCodecException, ValueError):
        return False
