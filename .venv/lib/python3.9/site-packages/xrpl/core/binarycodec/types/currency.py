"""Codec for currency property inside an XRPL issued currency amount json."""

from __future__ import annotations  # Requires Python 3.7+

from typing import Optional, Type

from typing_extensions import Final, Self

from xrpl.constants import HEX_CURRENCY_REGEX, ISO_CURRENCY_REGEX
from xrpl.core.binarycodec.exceptions import XRPLBinaryCodecException
from xrpl.core.binarycodec.types.hash160 import Hash160

_CURRENCY_CODE_LENGTH: Final[int] = 20  # bytes


def _is_iso_code(value: str) -> bool:
    """Tests if value is a valid 3-char iso code."""
    return bool(ISO_CURRENCY_REGEX.fullmatch(value))


def _iso_code_from_hex(value: bytes) -> Optional[str]:
    candidate_iso = value.decode("ascii")
    if candidate_iso == "XRP":
        raise XRPLBinaryCodecException(
            "Disallowed currency code: to indicate the currency "
            "XRP you must use 20 bytes of 0s"
        )
    if _is_iso_code(candidate_iso):
        return candidate_iso
    return None


def _is_hex(value: str) -> bool:
    """Tests if value is a valid 40-char hex string."""
    return bool(HEX_CURRENCY_REGEX.fullmatch(value))


def _iso_to_bytes(iso: str) -> bytes:
    """
    Convert an ISO code to a 160-bit (20 byte) encoded representation.

    See "Currency codes" subheading in
    `Amount Fields <https://xrpl.org/serialization.html#amount-fields>`_
    """
    if not _is_iso_code(iso):
        raise XRPLBinaryCodecException(f"Invalid ISO code: {iso}")

    if iso == "XRP":
        # This code (160 bit all zeroes) is used to indicate XRP in
        # rare cases where a field must specify a currency code for XRP.
        return bytes(_CURRENCY_CODE_LENGTH)

    iso_bytes = iso.encode("ASCII")
    # Currency Codes: https://xrpl.org/currency-formats.html#standard-currency-codes
    # 160 total bits:
    #   8 bits type code (0x00)
    #   88 bits reserved (0's)
    #   24 bits ASCII
    #   16 bits version (0x00)
    #   24 bits reserved (0's)
    return bytes(12) + iso_bytes + bytes(5)


class Currency(Hash160):
    """
    Codec for serializing and deserializing currency codes in issued currency amounts.
    `Amount fields <https://xrpl.org/serialization.html#amount-fields>`_

    Attributes:
        buffer: The byte encoding of this currency.
        _iso: The three-character ISO currency code if standard format, else None.
    """

    LENGTH: Final[int] = 20
    _iso: Optional[str] = None

    def __init__(self: Self, buffer: Optional[bytes] = None) -> None:
        """Construct a Currency."""
        if buffer is not None:
            super().__init__(buffer)
        else:
            super().__init__(bytes(self.LENGTH))

        code_bytes = self.buffer[12:15]
        # Determine whether this currency code is in standard or nonstandard format:
        # https://xrpl.org/currency-formats.html#nonstandard-currency-codes
        if self.buffer[0] != 0:
            # non-standard currency
            self._iso = None
        elif self.buffer.hex() == "0" * 40:  # all 0s
            # the special case for literal XRP
            self._iso = "XRP"
        else:
            self._iso = _iso_code_from_hex(code_bytes)

    @classmethod
    def from_value(cls: Type[Self], value: str) -> Self:
        """
        Construct a Currency object from a string representation of a currency.

        Args:
            value: The string to construct a Currency object from.

        Returns:
            A Currency object constructed from value.

        Raises:
            XRPLBinaryCodecException: If the Currency representation is invalid.
        """
        if not isinstance(value, str):
            raise XRPLBinaryCodecException(
                "Invalid type to construct a Currency: expected str,"
                f" received {value.__class__.__name__}."
            )

        if _is_iso_code(value):
            return cls(_iso_to_bytes(value))
        if _is_hex(value):
            return cls(bytes.fromhex(value))
        raise XRPLBinaryCodecException("Unsupported Currency representation: {value}")

    def to_json(self: Self) -> str:
        """
        Returns the JSON representation of a currency.

        Returns:
            The JSON representation of a Currency.
        """
        if self._iso is not None:
            return self._iso
        return self.buffer.hex().upper()
