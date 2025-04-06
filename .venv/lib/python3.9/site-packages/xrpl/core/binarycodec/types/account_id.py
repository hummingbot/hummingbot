"""Codec for serializing and deserializing AccountID fields.
See `AccountID Fields <https://xrpl.org/serialization.html#accountid-fields>`_
"""

from __future__ import annotations  # Requires Python 3.7+

import re
from typing import Optional, Pattern, Type

from typing_extensions import Final, Self

from xrpl.core.addresscodec import (
    decode_classic_address,
    encode_classic_address,
    is_valid_classic_address,
    is_valid_xaddress,
    xaddress_to_classic_address,
)
from xrpl.core.binarycodec import XRPLBinaryCodecException
from xrpl.core.binarycodec.types.hash160 import Hash160

# matches hex-encoded accounts. this happens to be the same format as the
# hex currency encoding, but that might change so we're redefining it here.
_HEX_REGEX: Final[Pattern[str]] = re.compile("[A-F0-9]{40}")


class AccountID(Hash160):
    """Codec for serializing and deserializing AccountID fields.
    See `AccountID Fields <https://xrpl.org/serialization.html#accountid-fields>`_
    """

    LENGTH: Final[int] = 20  # bytes

    def __init__(self: Self, buffer: Optional[bytes] = None) -> None:
        """
        Construct an AccountID from given bytes.
        If buffer is not provided, default to 20 zero bytes.
        """
        if buffer is not None and len(buffer) > 0:
            super().__init__(buffer)
        else:
            super().__init__(bytes(self.LENGTH))

    @classmethod
    def from_value(cls: Type[Self], value: str) -> Self:
        """
        Construct an AccountID from a hex string or a base58 r-Address.

        Args:
            value: The string to construct an AccountID from.

        Returns:
            The AccountID constructed from value.

        Raises:
            XRPLBinaryCodecException: If the supplied value is of the wrong type.
        """
        if not isinstance(value, str):
            raise XRPLBinaryCodecException(
                "Invalid type to construct an AccountID: expected str,"
                f" received {value.__class__.__name__}."
            )

        if value == "":
            return cls()

        # hex-encoded case
        if _HEX_REGEX.fullmatch(value):
            return cls(bytes.fromhex(value))
        # base58 case
        if is_valid_classic_address(value):
            return cls(decode_classic_address(value))
        if is_valid_xaddress(value):
            classic_address, _, _ = xaddress_to_classic_address(value)
            return cls(decode_classic_address(classic_address))

        raise XRPLBinaryCodecException(
            "Invalid value to construct an AccountID: expected valid classic address "
            f"or X-Address, received {value.__class__.__name__}."
        )

    def to_json(self: Self) -> str:
        """
        Return the value of this AccountID encoded as a base58 string.

        Returns:
            The JSON representation of the AccountID.
        """
        return encode_classic_address(self.buffer)
