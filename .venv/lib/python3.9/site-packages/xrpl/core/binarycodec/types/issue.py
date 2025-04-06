"""Codec for serializing and deserializing issued currency fields."""

from __future__ import annotations

from typing import Any, Dict, Optional, Type, Union

from typing_extensions import Self

from xrpl.core.binarycodec.binary_wrappers.binary_parser import BinaryParser
from xrpl.core.binarycodec.exceptions import XRPLBinaryCodecException
from xrpl.core.binarycodec.types.account_id import AccountID
from xrpl.core.binarycodec.types.currency import Currency
from xrpl.core.binarycodec.types.serialized_type import SerializedType
from xrpl.models.currencies import XRP as XRPModel
from xrpl.models.currencies import IssuedCurrency as IssuedCurrencyModel


class Issue(SerializedType):
    """Codec for serializing and deserializing issued currency fields."""

    def __init__(self: Self, buffer: bytes) -> None:
        """
        Construct an Issue from given bytes.

        Args:
            buffer: The byte buffer that will be used to store the serialized
                encoding of this field.
        """
        super().__init__(buffer)

    @classmethod
    def from_value(cls: Type[Self], value: Dict[str, str]) -> Self:
        """
        Construct an Issue object from a string or dictionary representation
        of an issued currency.

        Args:
            value: The dictionary to construct an Issue object from.

        Returns:
            An Issue object constructed from value.

        Raises:
            XRPLBinaryCodecException: If the Issue representation is invalid.
        """
        if XRPModel.is_dict_of_model(value):
            currency_bytes = bytes(Currency.from_value(value["currency"]))
            return cls(currency_bytes)

        if IssuedCurrencyModel.is_dict_of_model(value):
            currency_bytes = bytes(Currency.from_value(value["currency"]))
            issuer_bytes = bytes(AccountID.from_value(value["issuer"]))
            return cls(currency_bytes + issuer_bytes)

        raise XRPLBinaryCodecException(
            "Invalid type to construct an Issue: expected str or dict,"
            f" received {value.__class__.__name__}."
        )

    @classmethod
    def from_parser(
        cls: Type[Self],
        parser: BinaryParser,
        length_hint: Optional[int] = None,
    ) -> Self:
        """
        Construct an Issue object from an existing BinaryParser.

        Args:
            parser: The parser to construct the Issue object from.
            length_hint: The number of bytes to consume from the parser.

        Returns:
            The Issue object constructed from a parser.
        """
        currency = Currency.from_parser(parser)
        if currency.to_json() == "XRP":
            return cls(bytes(currency))

        issuer = parser.read(20)  # the length in bytes of an account ID
        return cls(bytes(currency) + issuer)

    def to_json(self: Self) -> Union[str, Dict[Any, Any]]:
        """
        Returns the JSON representation of an issued currency.

        Returns:
            The JSON representation of an Issue.
        """
        parser = BinaryParser(str(self))
        currency: Union[str, Dict[Any, Any]] = Currency.from_parser(parser).to_json()
        if currency == "XRP":
            return {"currency": currency}

        issuer = AccountID.from_parser(parser)
        return {"currency": currency, "issuer": issuer.to_json()}
