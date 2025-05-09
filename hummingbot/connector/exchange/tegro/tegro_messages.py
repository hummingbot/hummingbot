
from typing import Any, Dict, NamedTuple

from eth_utils.curried import ValidationError, text_if_str, to_bytes
from hexbytes import HexBytes

from hummingbot.connector.exchange.tegro.tegro_data_source import get_primary_type, hash_domain, hash_eip712_message

text_to_bytes = text_if_str(to_bytes)


# watch for updates to signature format
class SignableMessage(NamedTuple):
    """
    you can think of EIP-712 as compiling down to an EIP-191 message.
     - :meth:`encode_typed_data`
    """

    version: bytes  # must be length 1
    header: bytes  # aka "version specific data"
    body: bytes  # aka "data to sign"


def encode_typed_data(
    domain_data: Dict[str, Any] = None,
    message_types: Dict[str, Any] = None,
    message_data: Dict[str, Any] = None,
    full_message: Dict[str, Any] = None,
) -> SignableMessage:
    r"""
    Encode an EIP-712_ message in a manner compatible with other implementations
    As exactly three arguments:

        - ``domain_data``, a dict of the EIP-712 domain data
        - ``message_types``, a dict of custom types (do not include a ``EIP712Domain``
          key)
        - ``message_data``, a dict of the data to be signed

    Or as a single argument:

        - ``full_message``, a dict containing the following keys:
            - ``types``, a dict of custom types (may include a ``EIP712Domain`` key)
            - ``primaryType``, (optional) a string of the primary type of the message
            - ``domain``, a dict of the EIP-712 domain data
            - ``message``, a dict of the data to be signed

    Type Coercion:
        - For fixed-size bytes types, smaller values will be padded to fit in larger
          types, but values larger than the type will raise ``ValueOutOfBounds``.
          e.g., an 8-byte value will be padded to fit a ``bytes16`` type, but 16-byte
          value provided for a ``bytes8`` type will raise an error.
        - Fixed-size and dynamic ``bytes`` types will accept ``int``s. Any negative
          values will be converted to ``0`` before being converted to ``bytes``
        - ``int`` and ``uint`` types will also accept strings. If prefixed with ``"0x"``
          , the string will be interpreted as hex. Otherwise, it will be interpreted as
          decimal.

    Noteable differences from ``signTypedData``:
        - Custom types that are not alphanumeric will encode differently.
        - Custom types that are used but not defined in ``types`` will not encode.

    :param domain_data: EIP712 domain data
    :param message_types: custom types used by the `value` data
    :param message_data: data to be signed
    :param full_message: a dict containing all data and types
    :returns: a ``SignableMessage``, an encoded message ready to be signed
    """
    if full_message is not None:
        if (
            domain_data is not None
            or message_types is not None
            or message_data is not None
        ):
            raise ValueError(
                "You may supply either `full_message` as a single argument or "
                "`domain_data`, `message_types`, and `message_data` as three arguments,"
                " but not both."
            )

        full_message_types = full_message["types"].copy()
        full_message_domain = full_message["domain"].copy()

        # If EIP712Domain types were provided, check that they match the domain data
        if "EIP712Domain" in full_message_types:
            domain_data_keys = list(full_message_domain.keys())
            domain_types_keys = [
                field["name"] for field in full_message_types["EIP712Domain"]
            ]

            if set(domain_data_keys) != (set(domain_types_keys)):
                raise ValidationError(
                    "The fields provided in `domain` do not match the fields provided"
                    " in `types.EIP712Domain`. The fields provided in `domain` were"
                    f" `{domain_data_keys}`, but the fields provided in "
                    f"`types.EIP712Domain` were `{domain_types_keys}`."
                )

        full_message_types.pop("EIP712Domain", None)

        # If primaryType was provided, check that it matches the derived primaryType
        if "primaryType" in full_message:
            derived_primary_type = get_primary_type(full_message_types)
            provided_primary_type = full_message["primaryType"]
            if derived_primary_type != provided_primary_type:
                raise ValidationError(
                    "The provided `primaryType` does not match the derived "
                    "`primaryType`. The provided `primaryType` was "
                    f"`{provided_primary_type}`, but the derived `primaryType` was "
                    f"`{derived_primary_type}`."
                )

        parsed_domain_data = full_message_domain
        parsed_message_types = full_message_types
        parsed_message_data = full_message["message"]

    else:
        parsed_domain_data = domain_data
        parsed_message_types = message_types
        parsed_message_data = message_data

    return SignableMessage(
        HexBytes(b"\x01"),
        hash_domain(parsed_domain_data),
        hash_eip712_message(parsed_message_types, parsed_message_data),
    )
